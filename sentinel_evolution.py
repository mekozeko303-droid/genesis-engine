# -*- coding: utf-8 -*-
"""
Genesis Cinema Studio — sentinel_evolution.py
محرك الإخراج السينمائي:
1. فلترة أوامر المستخدم الطويلة ومنع قراءتها حرفياً في الصوت.
2. التحكم الدقيق بمدة الفيديو (من 30 ثانية حتى 10 دقائق) بتقسيم الفيديو إلى فصول ومشاهد.
3. الاتصال بكروت الشاشة المجانية (HuggingFace Spaces LTX-Video + FLUX.1) وفيديوهات Pixabay وWikimedia.
"""
import asyncio
import json
import logging
import os
import random
import re
import shutil
import subprocess
import time
import urllib.parse
from dataclasses import dataclass, field
from pathlib import Path

import edge_tts
import requests
from gtts import gTTS
from PIL import Image

import config

log = logging.getLogger("genesis.engine")

try:
    import imageio_ffmpeg
    FFMPEG_BIN = shutil.which("ffmpeg") or imageio_ffmpeg.get_ffmpeg_exe()
except Exception:
    FFMPEG_BIN = shutil.which("ffmpeg") or "ffmpeg"

try:
    from mutagen.mp3 import MP3
except Exception:
    MP3 = None

try:
    from gradio_client import Client as GradioClient
except Exception:
    GradioClient = None

BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Accept": "application/json, image/avif, image/webp, image/apng, image/*, video/*, */*;q=0.8",
}

GEO_LOCK_MAP = {
    "اليمن": (["Sanaa Yemen architecture", "Socotra Island Yemen", "Taiz Cairo Castle Yemen", "Shibam Hadramout Yemen"], "mountains ancient castle clouds"),
    "يمن": (["Sanaa Old City Yemen", "Socotra Dragon Blood Tree", "Green mountains Ibb Yemen", "Dar al-Hajar Yemen"], "mountains ancient architecture"),
    "صنعاء": (["Old City of Sanaa Yemen", "Bab al-Yemen Sanaa", "Dar al-Hajar Rock Palace"], "ancient city architecture"),
    "تعز": (["Cairo Castle Taiz Yemen", "Sabir Mountain Taiz", "Taiz Yemen landscape"], "mountain castle green"),
    "عدن": (["Aden Yemen harbor", "Aden coast sea", "Shamsan Mountain Aden"], "sea coast harbor"),
    "سقطرى": (["Socotra Island Yemen", "Dragon Blood Tree Socotra", "Detwah Lagoon Socotra"], "island tropical beach"),
    "فصوع": (["3D anthropomorphic buffalo character in Iraqi alley", "3D talking donkey character in mud brick house", "3D animal characters running in dusty village street"], "desert village alley"),
    "ماين كرافت": (["Minecraft 3D blocky characters stadium", "Minecraft voxel world action", "Minecraft Steve blocky character"], "video game blocks 3d"),
    "مني كرافت": (["Minecraft 3D blocky characters stadium", "Minecraft voxel world action", "Minecraft Steve blocky character"], "video game blocks 3d"),
    "كرة القدم": (["football match stadium players action", "soccer player kicking ball goal", "football fans cheering stadium", "soccer training fitness pitch"], "soccer football stadium match"),
    "كره القدم": (["football match stadium players action", "soccer player kicking ball goal", "football fans cheering stadium", "soccer training fitness pitch"], "soccer football stadium match"),
    "المشروبات الغازية": (["pouring cola soda into glass with ice", "fizzy soft drink bubbles macro", "healthy water vs sugary soda"], "cola soda ice glass"),
}


class ProductionError(Exception):
    def __init__(self, user_message: str):
        super().__init__(user_message)
        self.user_message = user_message


@dataclass
class ProductionResult:
    video_path: Path
    thumb_path: Path | None
    title: str
    duration: float
    width: int
    height: int
    hashtags: list[str]
    pinned_comment: str
    used_assets: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


class VideoProductionEngine:
    def __init__(self, db):
        self.db = db

    async def start(self) -> tuple[list[str], list[str]]:
        fatal, warn = [], []
        if not FFMPEG_BIN:
            fatal.append("برنامج FFmpeg غير متوفر على السيرفر.")
        if not config.PIXABAY_API_KEY:
            warn.append("PIXABAY_API_KEY غير مضبوط في Secrets (سيتم الاعتماد على التوليد بالذكاء الاصطناعي وWikimedia).")
        if not config.HF_TOKEN:
            warn.append("HF_TOKEN غير مضبوط في Secrets (سيتم استخدام محركات Flux المفتوحة).")
        return fatal, warn

    async def close(self) -> None:
        pass

    @staticmethod
    def parse_requested_duration(idea_text: str, user_default_sec: int = 60) -> int:
        """يكتشف المدة إذا كتبها المستخدم في النص مثل (10 دقائق) أو يستخدم المدة المختارة من الأزرار"""
        m_min = re.search(r"(\d+)\s*(?:دقائق|دقيقة|دقيقه|دقايق|minutes|min)", idea_text, re.IGNORECASE)
        if m_min:
            mins = min(int(m_min.group(1)), 12)
            return max(30, mins * 60)

        m_sec = re.search(r"(\d+)\s*(?:ثانية|ثانيه|ثواني|seconds|sec)", idea_text, re.IGNORECASE)
        if m_sec:
            return max(20, min(int(m_sec.group(1)), 720))

        return max(30, min(user_default_sec, 720))

    @staticmethod
    def extract_clean_topic_and_axes(raw_idea: str) -> tuple[str, list[str]]:
        """
        يمسح جميع تعليمات البرومبت (مثل: أنت كاتب سيناريو / المطلوب منك / اجعل التوقيتات 0:00-0:45)
        حتى لا يقرأها المعلق الصوتي أبداً، ويستخرج الموضوع الفعلي والمحاور فقط!
        """
        # 1. البحث عن موضوع بين علامتي تنصيص مثل: عن موضوع: "كرة القدم وفوائدها"
        quoted = re.search(r"(?:موضوع|عنوان)\s*[:：]?\s*[\"«”']([^\"»”'\n]+)[\"»”']", raw_idea)
        main_subject = quoted.group(1).strip() if quoted else ""

        meta_phrases = [
            "أنت كاتب سيناريو", "انت كاتب سيناريو", "مخرج فيديو محترف", "أريد منك إنشاء",
            "تكون مدة الفيديو", "الفئة المستهدفة", "الأسلوب:", "اللغة:", "المطلوب منك",
            "عنوان جذاب للفيديو", "وصف مختصر للفيديو", "تقسيم الفيديو إلى مشاهد",
            "لكل مشهد:", "التعليق الصوتي", "وصف المشهد البصري", "نوع الموسيقى",
            "النص الذي يظهر على الشاشة", "اجعل التوقيتات", "أضف اقتراحات للقطات",
            "لا تذكر معلومات", "أخرج النتيجة بصيغة", "يتضمن هذه المحاور", "المحاور الأساسية"
        ]

        axes = []
        for line in raw_idea.splitlines():
            s = line.strip()
            if not s:
                continue
            # تخطي أسطر التوقيتات مثل 0:00-0:45
            if re.match(r"^\d{1,2}:\d{2}\s*[-–—]\s*\d{1,2}:\d{2}", s):
                s = re.sub(r"^\d{1,2}:\d{2}\s*[-–—]\s*\d{1,2}:\d{2}\s*", "", s).strip()
            if any(mp in s for mp in meta_phrases):
                continue
            s_clean = re.sub(r"^[\d\-\•\*\)\(\.]+\s*", "", s).strip()
            if len(s_clean) > 6:
                axes.append(s_clean)

        if not main_subject:
            main_subject = axes[0][:60] if axes else raw_idea[:60]

        if not axes:
            axes = [main_subject]

        return main_subject, axes

    @staticmethod
    def translate_to_english(text_ar: str) -> str:
        try:
            url = "https://translate.googleapis.com/translate_a/single"
            params = {"client": "gtx", "sl": "auto", "tl": "en", "dt": "t", "q": text_ar[:250]}
            r = requests.get(url, params=params, headers=BROWSER_HEADERS, timeout=7)
            if r.status_code == 200:
                data = r.json()
                return "".join([p[0] for p in data[0] if p[0]]).strip()
        except Exception:
            pass
        return "cinematic dramatic story"

    @classmethod
    def build_full_script(cls, raw_idea: str, mode: config.Mode, target_sec: int) -> dict:
        """
        يبني سيناريو احترافياً كاملاً يغطي المدة المطلوبة (سواء 30 ثانية أو 10 دقائق)
        دون أن ينطق أي جملة من تعليمات المستخدم!
        """
        main_subject, axes = cls.extract_clean_topic_and_axes(raw_idea)
        subject_en = cls.translate_to_english(main_subject)

        # حساب عدد المشاهد بناءً على المدة (كل مشهد مدته نحو 12 إلى 15 ثانية من السرد الغني)
        if target_sec <= 45:
            num_scenes = 3
        elif target_sec <= 90:
            num_scenes = 5
        elif target_sec <= 200:
            num_scenes = 10
        elif target_sec <= 360:
            num_scenes = 15
        else:
            num_scenes = 22  # يغطي 6 إلى 10 دقائق من السرد المتواصل الغني

        # التحقق من القفل الجغرافي أو الموضوعي
        locked_img_queries = []
        locked_vid_query = mode.pixabay_q
        for k_ar, (img_list, vid_q) in GEO_LOCK_MAP.items():
            if k_ar in raw_idea or k_ar in main_subject:
                locked_img_queries = img_list
                locked_vid_query = vid_q
                break

        # محاولة التوليد الذكي عبر LLM
        sys_role = (
            "أنت كاتب سيناريو ومخرج سينمائي محترف. مهمتك كتابة النص الصوتي الفعلي الذي سينطقه المعلق مباشرة للمشاهدين.\n"
            "تحذير صارم: يُمنع منعاً باتاً قول 'أنت كاتب سيناريو' أو قراءة تعليمات الطلب، بل ابدأ فوراً بسرد الموضوع بأسلوب مشوق!\n"
            f"الموضوع الأساسي: {main_subject}\n"
            f"الأسلوب: {mode.name_ar} ({mode.desc_ar})\n"
            f"المطلوب تقسيم السيناريو إلى {min(num_scenes, 10)} فصول/مشاهد غنية ومفصلة.\n"
            "أخرج JSON فقط بهذه الصيغة:\n"
            "{\n"
            '  "title": "عنوان جذاب للفيديو بالعربية",\n'
            '  "pinned_comment": "سؤال تفاعلي للمشاهدين في التعليقات",\n'
            '  "scenes": [\n'
            '    {"narration_ar": "نص التعليق الصوتي المشوق لهذا المشهد (35 إلى 50 كلمة)", "visual_en": "Detailed English visual description of the scene"}\n'
            "  ]\n"
            "}"
        )

        llm_scenes = []
        title_ar = f"{mode.emoji} {main_subject[:50]}"
        pinned_ar = f"ما رأيك في {main_subject[:30]}؟ شاركنا تجربتك في التعليقات! 👇🔥"

        try:
            r = requests.post(
                "https://text.pollinations.ai/",
                json={
                    "messages": [
                        {"role": "system", "content": sys_role},
                        {"role": "user", "content": f"الموضوع: {main_subject}\nالمحاور المطلوب تغطيتها: {' | '.join(axes[:10])}"},
                    ],
                    "model": "openai",
                    "jsonMode": True,
                },
                headers=BROWSER_HEADERS,
                timeout=25,
            )
            if r.status_code == 200 and r.text.strip():
                clean = r.text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
                s_i, e_i = clean.find("{"), clean.rfind("}")
                if s_i != -1 and e_i != -1:
                    parsed = json.loads(clean[s_i : e_i + 1])
                    if parsed.get("scenes"):
                        title_ar = parsed.get("title") or title_ar
                        pinned_ar = parsed.get("pinned_comment") or pinned_ar
                        llm_scenes = parsed["scenes"]
        except Exception as e:
            log.warning("انتقل محرك السيناريو للبناء الهيكلي المباشر: %s", e)

        # إذا كان الفيديو طويلاً (مثل 5 أو 10 دقائق) أو لم يكفِ رد الـ LLM، نبني الفصول الاحترافية الكاملة لتغطية كل المحاور والمدة!
        final_scenes = []
        chapter_templates = [
            ("مقدمة مشوقة", "هل تساءلت يوماً لماذا يخطف {axis} قلوب الملايين حول العالم؟ في هذه الرحلة البصرية سنكشف لك أسراراً وتفاصيل مذهلة تغير نظرتك تماماً وتمنحك طاقة وإلهاماً لا يتوقف."),
            ("الجذور والأهمية", "عندما نتحدث عن {axis}، فنحن نتحدث عن شغف حقيقي يجمع الناس بمختلف ثقافاتهم، ويصنع لحظات تاريخية خالدة تبقى في الذاكرة وتلهم الأجيال جيلاً بعد جيل."),
            ("الأثر الجسدي والحيوي", "ومن الناحية العملية والصحية، فإن التركيز على {axis} ينشط الدورة الدموية، ويرفع اللياقة البدنية والمرونة، ويمنح الجسم قوة هائلة وقدرة عالية على التحمل والنشاط اليومي."),
            ("القوة النفسية والذهنية", "ولا يتوقف الأمر عند الجسد فحسب، بل يمتد أثر {axis} ليمنح العقل صفاءً ذهنياً مذهلاً، فيقضي على التوتر والقلق، ويعزز الثقة بالنفس والانضباط الإيجابي في كل خطوة."),
            ("الروح الاجتماعية والعمل الجماعي", "وفي قلب التجربة، يعلمنا {axis} معنى روح الفريق والتعاون الحقيقي، حيث تتلاقى القلوب وتُبنى الصداقات المتينة من خلال التواصل المستمر والهدف المشترك."),
            ("قواعد الأمان والاحتراف", "ولتحقيق أقصى استفادة ممكنة في {axis}، يحرص المحترفون دائماً على الإحماء السليم، والتدرج الذكي في الأداء، وشرب الماء الكافي للوقاية من الإجهاد ومواصلة التألق بأمان."),
            ("قصص ملهمة وأرقام قياسية", "عبر التاريخ، رأينا كيف حوّل {axis} أحلام البسطاء إلى قصص نجاح عالمية أبهرت الجميع، وأثبتت أن الإرادة الصلبة والتدريب المستمر يصنعان المعجزات على أرض الواقع."),
            ("خاتمة تحفيزية", "والآن حان دورك لتبدأ خطوتك الأولى في عالم {axis}! لا تؤجل شغفك إلى الغد، شارك هذا الفيديو مع أصدقائك واكتب لنا في التعليقات رأيك وتجربتك الخاصة!"),
        ]

        for idx in range(num_scenes):
            if idx < len(llm_scenes) and llm_scenes[idx].get("narration_ar"):
                nar = llm_scenes[idx]["narration_ar"]
                vis = llm_scenes[idx].get("visual_en") or f"{subject_en} scene {idx + 1}"
            else:
                axis_text = axes[idx % len(axes)]
                _, tpl = chapter_templates[idx % len(chapter_templates)]
                nar = tpl.format(axis=axis_text)
                axis_en = cls.translate_to_english(axis_text)
                vis = f"{subject_en}, {axis_en}, dynamic cinematic shot {idx + 1}"

            img_kw = locked_img_queries[idx % len(locked_img_queries)] if locked_img_queries else f"{subject_en} {vis[:40]}"
            final_scenes.append({
                "narration_ar": nar,
                "visual_en": f"{mode.style_en}, {vis}, ultra detailed 8k masterpiece",
                "search_kw": img_kw,
            })

        return {
            "title": title_ar,
            "pinned_comment": pinned_ar,
            "vid_search_en": locked_vid_query,
            "scenes": final_scenes,
            "hashtags": ["#اكسبلور", "#تريند", "#ريلز", "#شورتس", "#تيك_توك", f"#{mode.id}"],
        }

    @staticmethod
    async def synthesize_voice_segment(text_ar: str, voice_name: str, rate_str: str, out_mp3: Path) -> float:
        """يسجل الصوت العربي الطبيعي لكل مشهد ويحسب مدته الدقيقة بالثواني"""
        raw_mp3 = out_mp3.with_suffix(".raw.mp3")
        ok = False

        # 1. أصوات مايكروسوفت العصبية الطبيعية (عراقي، يمني، سعودي، مصري)
        try:
            comm = edge_tts.Communicate(text_ar, voice_name, rate=rate_str)
            await asyncio.wait_for(comm.save(str(raw_mp3)), timeout=12)
            if raw_mp3.exists() and raw_mp3.stat().st_size > 600:
                ok = True
        except Exception:
            ok = False

        # 2. البديل الصوتي المضمون gTTS
        if not ok:
            try:
                def _gtts():
                    gTTS(text=text_ar, lang="ar", slow=False).save(str(raw_mp3))
                await asyncio.to_thread(_gtts)
                if raw_mp3.exists() and raw_mp3.stat().st_size > 600:
                    ok = True
            except Exception:
                ok = False

        if ok:
            cmd = [
                FFMPEG_BIN, "-y", "-i", str(raw_mp3),
                "-ar", "44100", "-ac", "2", "-b:a", "128k", str(out_mp3)
            ]
            await asyncio.to_thread(subprocess.run, cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if not out_mp3.exists():
                shutil.copyfile(raw_mp3, out_mp3)
        else:
            # مسار صوتي احتياطي صامت حتى لا يتوقف الريندر
            cmd = [
                FFMPEG_BIN, "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
                "-t", "8", "-c:a", "libmp3lame", str(out_mp3)
            ]
            await asyncio.to_thread(subprocess.run, cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        if MP3 is not None and out_mp3.exists():
            try:
                info = MP3(str(out_mp3)).info
                if info and info.length > 1.0:
                    return float(info.length)
            except Exception:
                pass
        return 10.0

    @staticmethod
    def _save_valid_img(raw_bytes: bytes, out_path: Path, width: int = 576, height: int = 1024) -> bool:
        try:
            out_path.write_bytes(raw_bytes)
            img = Image.open(out_path).convert("RGB")
            # قص وتوسيط الصورة بأبعاد 9:16 العمودية بدون مط أو تشويه
            src_w, src_h = img.size
            target_ratio = width / height
            src_ratio = src_w / src_h
            if src_ratio > target_ratio:
                new_w = int(src_h * target_ratio)
                left = (src_w - new_w) // 2
                img = img.crop((left, 0, left + new_w, src_h))
            else:
                new_h = int(src_w / target_ratio)
                top = (src_h - new_h) // 2
                img = img.crop((0, top, src_w, top + new_h))
            img = img.resize((width, height), Image.Resampling.LANCZOS)
            extrema = img.getextrema()
            if all((mx - mn) < 12 for mn, mx in extrema):
                return False
            img.save(out_path, "JPEG", quality=93)
            return out_path.exists() and out_path.stat().st_size > 3500
        except Exception:
            return False

    @classmethod
    def try_free_gpu_video_space(cls, prompt_en: str, out_mp4: Path) -> bool:
        """يتصل بكرت الشاشة المجاني على HuggingFace Spaces (LTX-Video) لتوليد لقطة فيديو متحركة بالذكاء الاصطناعي"""
        if GradioClient is None:
            return False
        try:
            client = GradioClient("Lightricks/LTX-Video", hf_token=config.HF_TOKEN or None)
            res = client.predict(prompt=prompt_en[:200], api_name="/predict")
            vid_file = res[0] if isinstance(res, (list, tuple)) else res
            if isinstance(vid_file, dict):
                vid_file = vid_file.get("video") or vid_file.get("path")
            if vid_file and os.path.exists(str(vid_file)):
                shutil.copyfile(str(vid_file), str(out_mp4))
                return out_mp4.exists() and out_mp4.stat().st_size > 10000
        except Exception:
            pass
        return False

    @classmethod
    def fetch_pixabay_videos(cls, query_en: str, work_dir: Path, max_clips: int = 6) -> list[Path]:
        if not config.PIXABAY_API_KEY:
            return []
        clips = []
        queries = [query_en, " ".join(query_en.split()[:2]), "cinematic nature sport"]
        seen = set()
        for q in queries:
            clean_q = re.sub(r"[^\w\s]", " ", q).strip()
            if not clean_q or len(clips) >= max_clips:
                continue
            try:
                url = f"[https://pixabay.com/api/videos/?key=](https://pixabay.com/api/videos/?key=){config.PIXABAY_API_KEY}&q={urllib.parse.quote(clean_q)}&per_page=15"
                r = requests.get(url, headers=BROWSER_HEADERS, timeout=12)
                if r.status_code == 200:
                    hits = r.json().get("hits", [])
                    for h in hits:
                        if len(clips) >= max_clips:
                            break
                        vids = h.get("videos", {})
                        v_url = (
                            vids.get("medium", {}).get("url")
                            or vids.get("small", {}).get("url")
                            or vids.get("tiny", {}).get("url")
                        )
                        if v_url and v_url not in seen:
                            seen.add(v_url)
                            vr = requests.get(v_url, headers=BROWSER_HEADERS, timeout=16)
                            if vr.status_code == 200 and len(vr.content) > 25000:
                                p = work_dir / f"stock_{len(clips)}.mp4"
                                p.write_bytes(vr.content)
                                clips.append(p)
            except Exception:
                pass
        return clips

    @classmethod
    def fetch_scene_visual_image(cls, prompt_en: str, search_kw: str, mode: config.Mode, out_jpg: Path, seed: int, idx: int) -> bool:
        clean_prompt = re.sub(r"[^\w\s,.-]", " ", prompt_en)
        clean_prompt = " ".join(clean_prompt.split())[:220]
        s_val = seed + idx * 17

        # 1. للأوضاع الفنية والشخصيات (فصوع، أنمي، ستيك مان، كرتون 3D، ماين كرافت): الأولوية القصوى لمحرك الرسم بالذكاء الاصطناعي FLUX!
        if config.HF_TOKEN:
            for hf_url in [
                "[https://router.huggingface.co/hf-inference/models/black-forest-labs/FLUX.1-schnell](https://router.huggingface.co/hf-inference/models/black-forest-labs/FLUX.1-schnell)",
                "[https://api-inference.huggingface.co/models/black-forest-labs/FLUX.1-schnell](https://api-inference.huggingface.co/models/black-forest-labs/FLUX.1-schnell)",
            ]:
                try:
                    r = requests.post(
                        hf_url,
                        headers={"Authorization": f"Bearer {config.HF_TOKEN}"},
                        json={"inputs": clean_prompt},
                        timeout=18,
                    )
                    if r.status_code == 200 and cls._save_valid_img(r.content, out_jpg):
                        return True
                except Exception:
                    pass

        # 2. محرك Pollinations Flux المباشر
        for mdl in ["flux", "turbo"]:
            try:
                enc = urllib.parse.quote(clean_prompt)
                url = f"[https://image.pollinations.ai/prompt/](https://image.pollinations.ai/prompt/){enc}?width=576&height=1024&seed={s_val}&nologo=true&model={mdl}"
                r = requests.get(url, headers=BROWSER_HEADERS, timeout=15)
                if r.status_code == 200 and cls._save_valid_img(r.content, out_jpg):
                    return True
            except Exception:
                pass

        # 3. البحث الموثق في Wikimedia Commons (ممتاز لصور اليمن والمعالم والرياضة)
        for sq in [search_kw, " ".join(search_kw.split()[:2])]:
            if not sq.strip():
                continue
            try:
                params = {
                    "action": "query",
                    "generator": "search",
                    "gsrsearch": f"filetype:bitmap {sq}",
                    "gsrlimit": 15,
                    "prop": "imageinfo",
                    "iiprop": "url",
                    "iiurlwidth": 800,
                    "format": "json",
                }
                r = requests.get("[https://commons.wikimedia.org/w/api.php](https://commons.wikimedia.org/w/api.php)", params=params, headers=BROWSER_HEADERS, timeout=10)
                if r.status_code == 200:
                    pages = list(r.json().get("query", {}).get("pages", {}).values())
                    urls = [
                        p.get("imageinfo", [{}])[0].get("thumburl") or p.get("imageinfo", [{}])[0].get("url")
                        for p in pages
                    ]
                    urls = [u for u in urls if u and any(u.lower().endswith(ext) for ext in [".jpg", ".jpeg", ".png"])]
                    if urls:
                        u = urls[(idx + seed) % len(urls)]
                        ir = requests.get(u, headers=BROWSER_HEADERS, timeout=12)
                        if ir.status_code == 200 and cls._save_valid_img(ir.content, out_jpg):
                            return True
            except Exception:
                pass

        # 4. صور Pixabay عالية الدقة
        if config.PIXABAY_API_KEY:
            for q_try in [search_kw, mode.pixabay_q, "nature mountains"]:
                clean_q = re.sub(r"[^\w\s]", " ", q_try).strip()
                if not clean_q:
                    continue
                try:
                    url = f"[https://pixabay.com/api/?key=](https://pixabay.com/api/?key=){config.PIXABAY_API_KEY}&q={urllib.parse.quote(clean_q)}&image_type=photo&per_page=15"
                    r = requests.get(url, headers=BROWSER_HEADERS, timeout=10)
                    if r.status_code == 200:
                        hits = r.json().get("hits", [])
                        if hits:
                            img_u = hits[(idx + seed) % len(hits)].get("largeImageURL")
                            ir = requests.get(img_u, headers=BROWSER_HEADERS, timeout=12)
                            if ir.status_code == 200 and cls._save_valid_img(ir.content, out_jpg):
                                return True
                except Exception:
                    pass

        # 5. صورة فوتوغرافية حقيقية من Picsum (تمنع الشاشة السوداء تماماً)
        try:
            r = requests.get(f"[https://picsum.photos/seed/](https://picsum.photos/seed/){s_val + 333}/576/1024", headers=BROWSER_HEADERS, timeout=12)
            if r.status_code == 200 and cls._save_valid_img(r.content, out_jpg):
                return True
        except Exception:
            pass

        return False

    async def produce(self, idea: str, mode_id: str, target_duration: int = 60, progress=None) -> ProductionResult:
        mode = config.MODES.get(mode_id, config.MODES["fasso"])
        effective_target_sec = self.parse_requested_duration(idea, target_duration)

        job_dir = config.TEMP_DIR / f"job_{mode.id}_{int(time.time())}_{random.randint(100, 999)}"
        job_dir.mkdir(parents=True, exist_ok=True)

        if progress:
            await progress("script", f"(المدة المستهدفة: {effective_target_sec} ثانية)")

        script = await asyncio.to_thread(self.build_full_script, idea, mode, effective_target_sec)
        scenes = script["scenes"]
        num_scenes = len(scenes)

        # إذا كان الفيديو طويلاً، نوزع الكلمات أو الثواني بحيث يغطي المدة المطلوبة
        min_scene_dur = max(3.5, round(effective_target_sec / num_scenes, 2))

        if progress:
            await progress("voice", f"({num_scenes} مشاهد متسلسلة)")

        # تسجيل الصوت لكل مشهد بالتوازي
        audio_paths: list[Path] = []
        scene_durations: list[float] = []
        for idx, sc in enumerate(scenes):
            a_path = job_dir / f"voice_{idx}.mp3"
            dur = await self.synthesize_voice_segment(sc["narration_ar"], mode.voice, mode.voice_rate, a_path)
            audio_paths.append(a_path)
            scene_durations.append(max(min_scene_dur, dur + 0.4))

        if progress:
            await progress("assets", f"({num_scenes} لقطات بصرية)")

        # جلب لقطات فيديو حقيقية مساعدة للأوضاع الهجينة والوثائقية
        stock_clips: list[Path] = []
        if mode.engine in ("hybrid_video", "stock_video") and not any(w in idea for w in ["يمن", "اليمن", "فصوع", "كرافت", "ستيك"]):
            stock_clips = await asyncio.to_thread(self.fetch_pixabay_videos, script["vid_search_en"], job_dir, min(num_scenes, 6))

        seed = abs(hash(f"{mode.id}_{idea}")) % 700000 + 10000
        rendered_segments: list[Path] = []
        used_assets: list[str] = []
        first_thumb: Path | None = None

        for idx, sc in enumerate(scenes):
            if progress and idx % 2 == 0:
                await progress("render", f"({idx + 1}/{num_scenes})")

            seg_dur = scene_durations[idx]
            a_path = audio_paths[idx]
            seg_out = job_dir / f"seg_{idx:03d}.mp4"
            frames = max(60, int(seg_dur * 24))

            # 1. للأوضاع الدرامية (مثل فصوع أو السينمائي)، نحاول في المشهد الافتتاحي الاتصال بكرت الشاشة المجاني LTX-Video
            gpu_vid = job_dir / f"gpu_{idx}.mp4"
            used_clip: Path | None = None

            if idx == 0 and mode.engine == "ai_character":
                ok_gpu = await asyncio.to_thread(self.try_free_gpu_video_space, sc["visual_en"], gpu_vid)
                if ok_gpu:
                    used_clip = gpu_vid
                    used_assets.append("LTX-Video-GPU")

            # 2. استخدام لقطات الفيديو الحقيقية للأوضاع الهجينة
            if not used_clip and stock_clips and (mode.engine == "stock_video" or idx % 2 == 1):
                used_clip = stock_clips[idx % len(stock_clips)]
                used_assets.append("Pixabay-HD-MP4")

            if used_clip and used_clip.exists():
                cmd = [
                    FFMPEG_BIN, "-y",
                    "-stream_loop", "-1", "-i", str(used_clip),
                    "-i", str(a_path),
                    "-t", str(seg_dur),
                    "-vf", f"scale=576:1024:force_original_aspect_ratio=increase,crop=576:1024,{mode.vfilter},format=yuv420p",
                    "-map", "0:v:0", "-map", "1:a:0",
                    "-c:v", "libx264", "-preset", "ultrafast", "-r", "24",
                    "-c:a", "aac", "-b:a", "128k", str(seg_out),
                ]
                await asyncio.to_thread(subprocess.run, cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            # 3. رسم المشهد المخصص بالذكاء الاصطناعي وتحريكه بالكاميرا
            if not seg_out.exists() or seg_out.stat().st_size < 1500:
                img_p = job_dir / f"frame_{idx:03d}.jpg"
                await asyncio.to_thread(self.fetch_scene_visual_image, sc["visual_en"], sc["search_kw"], mode, img_p, seed, idx)
                if first_thumb is None and img_p.exists():
                    first_thumb = img_p
                used_assets.append("AI-Scene-Render")

                cam_moves = [
                    f"zoompan=z='min(zoom+0.0020,1.24)':d={frames}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=576x1024:fps=24",
                    f"zoompan=z='1.18':d={frames}:x='(iw-iw/zoom)*(on/{frames})':y='ih/2-(ih/zoom/2)':s=576x1024:fps=24",
                    f"zoompan=z='if(lte(zoom,1.0),1.24,max(1.001,zoom-0.0020))':d={frames}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=576x1024:fps=24",
                    f"zoompan=z='min(zoom+0.0022,1.26)':d={frames}:x='iw/2-(iw/zoom/2)':y='(ih-ih/zoom)*(on/{frames})':s=576x1024:fps=24",
                ]
                zp = cam_moves[idx % len(cam_moves)]

                cmd_zp = [
                    FFMPEG_BIN, "-y",
                    "-loop", "1", "-i", str(img_p),
                    "-i", str(a_path),
                    "-t", str(seg_dur),
                    "-vf", f"{zp},{mode.vfilter},format=yuv420p",
                    "-map", "0:v:0", "-map", "1:a:0",
                    "-c:v", "libx264", "-preset", "ultrafast", "-r", "24",
                    "-c:a", "aac", "-b:a", "128k", str(seg_out),
                ]
                await asyncio.to_thread(subprocess.run, cmd_zp, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

                if not seg_out.exists() or seg_out.stat().st_size < 1500:
                    cmd_simple = [
                        FFMPEG_BIN, "-y",
                        "-loop", "1", "-t", str(seg_dur), "-i", str(img_p),
                        "-i", str(a_path),
                        "-vf", "scale=576:1024,format=yuv420p",
                        "-map", "0:v:0", "-map", "1:a:0",
                        "-c:v", "libx264", "-preset", "ultrafast", "-r", "24",
                        "-c:a", "aac", "-b:a", "128k", "-shortest", str(seg_out),
                    ]
                    await asyncio.to_thread(subprocess.run, cmd_simple, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            if seg_out.exists() and seg_out.stat().st_size > 1000:
                rendered_segments.append(seg_out)

        if not rendered_segments:
            raise ProductionError("تعذر تجميع مشاهد الفيديو، يرجى المحاولة مرة أخرى.")

        if progress:
            await progress("finalize")

        concat_file = job_dir / "concat.txt"
        concat_file.write_text("\n".join(f"file '{p.name}'" for p in rendered_segments), encoding="utf-8")

        final_mp4 = job_dir / f"genesis_{mode.id}_final.mp4"
        merge_cmd = [
            FFMPEG_BIN, "-y",
            "-f", "concat", "-safe", "0", "-i", str(concat_file),
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", "26",
            "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k",
            str(final_mp4),
        ]
        await asyncio.to_thread(subprocess.run, merge_cmd, cwd=str(job_dir), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        total_dur = sum(scene_durations)
        return ProductionResult(
            video_path=final_mp4,
            thumb_path=first_thumb,
            title=script["title"],
            duration=total_dur,
            width=576,
            height=1024,
            hashtags=script["hashtags"],
            pinned_comment=script["pinned_comment"],
            used_assets=list(dict.fromkeys(used_assets)),
            notes=[f"الوضع: {mode.name_ar}", f"المدة الفعلية: {int(total_dur)} ثانية ({len(rendered_segments)} مشاهد)"],
        )
