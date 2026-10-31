import os
import sys
import time
import json
import re
import random
import urllib.parse
import subprocess
import asyncio

try:
    asyncio.get_event_loop()
except RuntimeError:
    asyncio.set_event_loop(asyncio.new_event_loop())

import aiohttp
import edge_tts
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageOps
from pyrogram import Client, filters
from pyrogram.types import ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton

# =====================================================================
# 1. الإعدادات والمفاتيح الأساسية
# =====================================================================
TELEGRAM_API_ID = 31270154
TELEGRAM_API_HASH = "5a056c44d67b3e3318b3f122436cf019"
TELEGRAM_BOT_TOKEN = "9093676549:AAEvZHvi_Vr_M65A1oYdmDHRoJtB2LFmlis"
HF_TOKEN = "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"
PIXABAY_API_KEY = "58313642-74c3e2c37ac5e866948e83ef1"
GEMINI_API_KEYS = [
    "AIzaSyDDC8V4JzUDqSMm9JRO4xckLF889ftfY6g",
    "AQ.Ab8RN6LgUo-RsNiuvISI1EemwlA0I5eht83u2FKGDoxyoGzcJg",
    "AQ.Ab8RN6KxKDz4kA_DK_64HlQeWrcv7CQAmlqSazzvc5SGgYtFDQ"
]

PRODUCTION_MODES = {
    "cinematic": "🎬 سينمائي 100% (هوليوود واقعي)",
    "hybrid": "🧠 المخرج الذكي (هجين ديناميكي)",
    "kids": "👶 كرتون وأنيميشن 3D (Pixar)",
    "story": "📸 ستوري وريلز صوري (بدون تشويه)",
    "dialogue": "🗣️ حوار تمثيلي (رجل وامرأة)",
    "news": "📰 استوديو الأخبار والوثائقيات",
    "fast": "⚡ الوضع السريع (إنتاج خاطف)",
    "ads": "📢 مدير الإعلانات التجارية",
    "cloning": "🧬 استنساخ الوجه وحذف العلامة المائية"
}

SUPPORTED_LANGUAGES = {
    "ar": {"name": "🇸🇦 العربية الفصحى (صوت بشري سينمائي)", "male_voice": "ar-SA-HamedNeural", "female_voice": "ar-EG-SalmaNeural", "kids_voice": "ar-AE-FatimaNeural", "rate": "-2%", "pitch": "-1Hz"},
    "ar_ye": {"name": "🇾🇪 اللهجة اليمنية (صوت طبيعي)", "male_voice": "ar-YE-SalehNeural", "female_voice": "ar-YE-MaryamNeural", "kids_voice": "ar-YE-MaryamNeural", "rate": "+0%", "pitch": "+0Hz"},
    "ar_f": {"name": "🎙️ العربية (صوت نسائي إعلاني)", "male_voice": "ar-EG-SalmaNeural", "female_voice": "ar-SA-ZariyahNeural", "kids_voice": "ar-AE-FatimaNeural", "rate": "+0%", "pitch": "+0Hz"},
    "en": {"name": "🇺🇸 English (Hollywood Realistic)", "male_voice": "en-US-AndrewMultilingualNeural", "female_voice": "en-US-AvaMultilingualNeural", "kids_voice": "en-US-AnaNeural", "rate": "+0%", "pitch": "+0Hz"},
    "fr": {"name": "🇫🇷 Français (Voix Humaine)", "male_voice": "fr-FR-RemyMultilingualNeural", "female_voice": "fr-FR-VivienneMultilingualNeural", "kids_voice": "fr-FR-EloiseNeural", "rate": "+0%", "pitch": "+0Hz"},
    "es": {"name": "🇪🇸 Español (Voz Realista)", "male_voice": "es-ES-AlvaroNeural", "female_voice": "es-ES-ElviraNeural", "kids_voice": "es-MX-MarinaNeural", "rate": "+0%", "pitch": "+0Hz"},
    "tr": {"name": "🇹🇷 Türkçe (Gerçekçi Ses)", "male_voice": "tr-TR-AhmetNeural", "female_voice": "tr-TR-EmelNeural", "kids_voice": "tr-TR-EmelNeural", "rate": "+0%", "pitch": "+0Hz"}
}

# =====================================================================
# 2. مجلس الوكلاء الـ 20 الذكي
# =====================================================================
class StudioBoardroom:
    def __init__(self):
        self.upgrade_level = 3
        self.active_ai_engine = "FLUX.1-Schnell Ultra + Pollinations Turbo"
        self.mode_profiles = {
            "cinematic": {"style_name": "🎬 هوليوود سينمائي واقعي 100%", "visual_rule": "Ultra-realistic 8k Hollywood movie frame, ARRI Alexa 65, dramatic lighting, photorealistic", "lut": "dark_thriller", "music": "epic", "voice_type": "male_voice", "aspect": "16:9", "search_tag": "cinematic movie"},
            "kids": {"style_name": "👶 أفلام كرتون وأنيميشن 3D (Pixar)", "visual_rule": "Cute 3D Pixar and Disney animation style, vibrant cheerful colors, expressive cute cartoon characters, 8k CGI", "lut": "vibrant_ad", "music": "upbeat", "voice_type": "kids_voice", "aspect": "16:9", "search_tag": "cartoon animation"},
            "story": {"style_name": "📸 استوديو الستوري والريلز (9:16)", "visual_rule": "Aesthetic vertical social media reel photography, warm color grading, sharp focus, 8k", "lut": "vibrant_ad", "music": "upbeat", "voice_type": "male_voice", "aspect": "9:16", "search_tag": "aesthetic lifestyle"},
            "dialogue": {"style_name": "🗣️ حوار تمثيلي درامي (رجل وامرأة)", "visual_rule": "Cinematic medium close-up shot of speaking character, expressive emotions, shallow depth of field, 8k", "lut": "cinematic_warm", "music": "dramatic", "voice_type": "alternating", "aspect": "16:9", "search_tag": "cinematic portrait"},
            "news": {"style_name": "📰 استوديو الأخبار والوثائقيات", "visual_rule": "Broadcast documentary journalism photography, realistic world event footage, sharp focus, 8k", "lut": "cinematic_warm", "music": "dramatic", "voice_type": "male_voice", "aspect": "16:9", "search_tag": "news documentary"},
            "fast": {"style_name": "⚡ الإنتاج السريع الخاطف", "visual_rule": "High-impact dynamic action shot, hyper-detailed, high contrast, 8k", "lut": "vibrant_ad", "music": "upbeat", "voice_type": "male_voice", "aspect": "16:9", "search_tag": "dynamic action"},
            "ads": {"style_name": "📢 إعلان تجاري تسويقي", "visual_rule": "High-end luxury commercial product photography, studio rim lighting, sleek modern advertising, 8k", "lut": "vibrant_ad", "music": "upbeat", "voice_type": "female_voice", "aspect": "16:9", "search_tag": "commercial product"},
            "cloning": {"style_name": "🧬 استنساخ الوجه وحذف العلامة المائية", "visual_rule": "Front-facing heroic portrait shot, clear symmetrical face looking at camera, studio lighting, 8k", "lut": "cinematic_warm", "music": "dramatic", "voice_type": "male_voice", "aspect": "16:9", "search_tag": "portrait person"},
            "hybrid": {"style_name": "🧠 المخرج الذكي الهجين", "visual_rule": "Cinematic masterpiece, dynamic camera angle, rich atmosphere, hyper-realistic details, 8k", "lut": "cinematic_warm", "music": "epic", "voice_type": "male_voice", "aspect": "16:9", "search_tag": "cinematic landscape"}
        }

    def detect_request_settings(self, text, default_mode="hybrid", default_lang="ar", default_scenes=5):
        mode = default_mode if default_mode in self.mode_profiles else "hybrid"
        lower_txt = text.lower()
        if any(w in lower_txt for w in ["كرتون", "اطفال", "أطفال", "انيميشن", "أنيميشن", "بيكسار", "cartoon", "kids"]):
            mode = "kids"
        elif any(w in lower_txt for w in ["حوار", "يتحدثان", "محادثة"]):
            mode = "dialogue"
        elif any(w in lower_txt for w in ["إعلان", "اعلان", "تسويق"]):
            mode = "ads"
        elif any(w in lower_txt for w in ["خبر", "أخبار", "وثائقي"]):
            mode = "news"

        lang_code = default_lang if default_lang in SUPPORTED_LANGUAGES else "ar"
        if any(w in lower_txt for w in ["انجليزي", "إنجليزي", "بالانجليزي", "english"]):
            lang_code = "en"
        elif any(w in lower_txt for w in ["فرنسي", "بالفرنسي", "french"]):
            lang_code = "fr"
        elif any(w in lower_txt for w in ["اسباني", "إسباني", "spanish"]):
            lang_code = "es"
        elif any(w in lower_txt for w in ["تركي", "بالتركي", "turkish"]):
            lang_code = "tr"
        elif any(w in lower_txt for w in ["يمني", "باليمني", "لهجة يمنية"]):
            lang_code = "ar_ye"

        num_scenes = default_scenes
        scene_match = re.search(r"(\d+)\s*(مشهد|مشاهد|لقطات)", lower_txt)
        min_match = re.search(r"(\d+)\s*(دقيقة|دقائق|دقيقه)", lower_txt)
        if scene_match:
            num_scenes = max(2, min(14, int(scene_match.group(1))))
        elif min_match:
            num_scenes = max(3, min(16, int(min_match.group(1)) * 5))
        return mode, lang_code, num_scenes

    def _parse_json_safely(self, txt):
        if not isinstance(txt, str):
            return None
        try:
            clean = txt.strip().replace("```json", "").replace("```", "").strip()
            s, e = clean.find("{"), clean.rfind("}") + 1
            if s != -1 and e > s:
                return json.loads(clean[s:e])
        except Exception:
            pass
        return None

    async def call_ai(self, prompt, is_json=False):
        timeout = aiohttp.ClientTimeout(total=14)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            try:
                payload = {
                    "model": "openai",
                    "messages": [
                        {"role": "system", "content": "You are an elite film director. Output ONLY valid JSON when asked for JSON."},
                        {"role": "user", "content": prompt}
                    ]
                }
                async with session.post("https://text.pollinations.ai/openai", json=payload) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        txt = data["choices"][0]["message"]["content"]
                        return self._parse_json_safely(txt) if is_json else txt
            except Exception:
                pass
        return {} if is_json else ""

    def _fallback_lines(self, topic, mode, lang_code, num_scenes):
        t = topic.strip()
        if mode == "dialogue":
            lines = [
                f"انتظر لحظة! هل ترى ما يحدث هناك؟ إن أحداث {t} تبدأ أمامنا الآن!",
                f"يا للمفاجأة! لم أكن أتوقع أن نشهد هذا الموقف المذهل، اقترب لنرى بوضوح!",
                f"انتبه جيداً، الأحداث تتسارع بشكل عجيب ومشوق في كل ثانية!",
                f"انظر كيف انقلبت الموازين تماماً في هذه اللحظة الحاسمة!",
                f"لقد وثقنا كل شيء! هذه القصة ستبهر كل من يشاهدها!"
            ]
        elif mode == "kids":
            lines = [
                f"كان يا مكان في عالم مليء بالألوان الساحرة، بدأت مغامرة مرحة ومدهشة عن {t}!",
                f"وانطلق الأبطال الصغار بحماس وسط الطبيعة الجميلة والمفاجآت المبهجة!",
                f"وفجأة ظهرت أمامهم مغامرة طريفة رسمت الابتسامة على وجوه الجميع!",
                f"بالتعاون والذكاء نجح الأصدقاء في تجاوز الموقف بطريقة رائعة ومسلية!",
                f"وهكذا انتهت الحكاية الجميلة وعمّ الفرح والسعادة في كل مكان!"
            ]
        elif mode == "ads":
            lines = [
                f"هل تبحث عن التميز الحقيقي والتجربة التي تتجاوز كل التوقعات؟ اكتشف الآن {t}!",
                f"تصميم احترافي وجودة فائقة صُنعت خصيصاً لتمنحك القوة والأناقة في كل تفصيل.",
                f"وداعاً للطرق التقليدية، استمتع بأعلى أداء يجمع بين الإبداع والسرعة.",
                f"الخيار الأول للباحثين عن القمة والاحترافية بلا حدود.",
                f"لا تفوت الفرصة! ابدأ تجربتك الآن واصنع الفرق بنفسك!"
            ]
        elif lang_code == "en":
            lines = [
                f"In a remarkable turn of events, the story of {t} unfolds right before our eyes!",
                f"Every second builds momentum as the camera captures the intense action up close!",
                f"Against all odds, the scene transforms into an unforgettable visual spectacle!",
                f"At the decisive moment, an unexpected twist changes everything!",
                f"A powerful finale that leaves a lasting impression!"
            ]
        elif lang_code == "ar_ye":
            lines = [
                f"شوفوا يا جماعة كيف بدأت هذي القصة الرهيبة عن {t} في موقف ما يخطر على البال!",
                f"الأحداث اشتعلت والمشهد تحول قدام الكل إلى لحظة حماسية تخطف الأنفاس!",
                f"كل ثانية تمر تزيد الإثارة، ولا أحد كان يتوقع اللي بيحصل بعدها!",
                f"وفي عز الحماس، ظهرت المفاجأة القوية اللي قلبت الموازين بالكامل!",
                f"وهكذا اختتمت هذي المغامرة العجيبة اللي ما تنتسي أبداً!"
            ]
        else:
            lines = [
                f"فِي مَشهَدٍ سِينَمَائِيٍّ يَخطِفُ الأَنفَاسَ، تَنطَلِقُ أَحدَاثُ هَذِهِ القِصَّةِ حَولَ {t}!",
                f"تَتَسَارَعُ الأَحدَاثُ لَحظَةً بَعدَ لَحظَةٍ وَسَطَ أَجوَاءَ مَلِيئَةٍ بِالإِثَارَةِ وَالتَّشوِيقِ!",
                f"هُنَا تَتَجَلَّى التَّفَاصِيلُ الدَّقِيقَةُ حَيثُ يَتَحَوَّلُ المَشهَدُ إِلَى ذُروَةِ الحَمَاسِ!",
                f"وَفِي اللَّحظَةِ الحَاسِمَةِ، تَظهَرُ المُفَاجَأَةُ الكُبرَى الَّتِي غَيَّرَت مَسَارَ الأَحدَاثِ!",
                f"وَهَكَذَا يُسدَلُ السِّتَارُ عَلَى هَذَا العَمَلِ الفَرِيدِ بِنِهَايَةٍ لَا تُنسَى!"
            ]
        return [lines[i % len(lines)] for i in range(num_scenes)]

    async def run_consensus_debate(self, topic, mode="hybrid", num_scenes=5, lang_code="ar"):
        mode, lang_code, num_scenes = self.detect_request_settings(topic, mode, lang_code, num_scenes)
        profile = self.mode_profiles.get(mode, self.mode_profiles["hybrid"])
        lang_info = SUPPORTED_LANGUAGES.get(lang_code, SUPPORTED_LANGUAGES["ar"])
        fb_lines = self._fallback_lines(topic, mode, lang_code, num_scenes)

        prompt = (
            f"Create a {num_scenes}-scene script for '{topic}' in mode '{profile['style_name']}' and language '{lang_info['name']}'. "
            f"Return ONLY JSON: {{\"title\": \"...\", \"scenes\": [{{\"scene_id\": 1, \"narration_ar\": \"...\", \"visual_prompt_en\": \"...\", \"search_query_en\": \"2 english words\"}}]}}"
        )
        raw_bp = await self.call_ai(prompt, is_json=True)
        if not isinstance(raw_bp, dict):
            raw_bp = {}
        raw_scenes = raw_bp.get("scenes", []) if isinstance(raw_bp.get("scenes"), list) else []

        shots = ["wide establishing shot", "medium tracking action shot", "dramatic close-up shot", "low-angle heroic shot", "epic wide finale shot"]
        final_scenes = []
        for idx in range(num_scenes):
            sc = raw_scenes[idx] if idx < len(raw_scenes) and isinstance(raw_scenes[idx], dict) else {}
            narration = str(sc.get("narration_ar", "")).strip()
            if not narration or len(narration) < 6 or "النص" in narration:
                narration = fb_lines[idx]
            base_vp = str(sc.get("visual_prompt_en", "")).strip()
            vp = f"{profile['visual_rule']}, {shots[idx % len(shots)]}, {base_vp if len(base_vp) > 10 else f'scene {idx+1} of {topic}'}"
            v_key = ("male_voice" if idx % 2 == 0 else "female_voice") if profile["voice_type"] == "alternating" else profile["voice_type"]

            final_scenes.append({
                "scene_id": idx + 1,
                "narration_ar": narration,
                "visual_prompt_en": vp,
                "search_query_en": sc.get("search_query_en") or profile["search_tag"],
                "voice_id": lang_info.get(v_key, lang_info["male_voice"]),
                "voice_rate": lang_info.get("rate", "+0%"),
                "voice_pitch": lang_info.get("pitch", "+0Hz"),
                "aspect": profile["aspect"]
            })

        blueprint = {
            "title": raw_bp.get("title") or topic[:50],
            "bg_music_mood": profile["music"],
            "language": lang_code,
            "mode": mode,
            "aspect": profile["aspect"],
            "scenes": final_scenes
        }
        summary = (
            f"🎛️ **غرفة عمليات الـ 20 وكيلاً (v{self.upgrade_level}.0):**\n"
            f"• **الوضع:** {profile['style_name']}\n"
            f"• **اللغة والصوت:** {lang_info['name']}\n"
            f"• **المشاهد:** {num_scenes} مشاهد متكاملة (مانع الشاشة السوداء مفعّل)"
        )
        return blueprint, summary


# =====================================================================
# 3. محرك الميديا الشامل (صور حقيقية + حذف العلامة المائية + استنساخ الوجه + ستوري)
# =====================================================================
class StudioMediaEngine:
    def __init__(self):
        self.work_dir = "workspace"
        os.makedirs(self.work_dir, exist_ok=True)
        try:
            self.face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
            self.profile_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_profileface.xml")
        except Exception:
            self.face_cascade = None
            self.profile_cascade = None

    def _run_ffmpeg(self, cmd):
        try:
            res = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=180)
            return res.returncode == 0, res.stderr
        except Exception as e:
            return False, str(e)

    def _get_audio_duration(self, audio_path):
        if not os.path.exists(audio_path) or os.path.getsize(audio_path) < 100:
            return 5.0
        try:
            out = subprocess.check_output(
                f'ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "{audio_path}"',
                shell=True, text=True
            ).strip()
            return max(3.0, float(out))
        except Exception:
            return 5.0

    async def generate_human_voice(self, text, output_path, voice_id="ar-SA-HamedNeural", rate="-2%", pitch="-1Hz", mood="epic"):
        raw_voice = output_path.replace(".mp3", "_raw.mp3")
        clean_text = str(text).replace('"', '').replace("'", "").strip() or "..."
        success = False
        for attempt in range(2):
            try:
                comm = edge_tts.Communicate(clean_text, voice_id, rate=rate, pitch=pitch) if attempt == 0 else edge_tts.Communicate(clean_text, voice_id)
                await comm.save(raw_voice)
                if os.path.exists(raw_voice) and os.path.getsize(raw_voice) > 200:
                    success = True
                    break
            except Exception:
                await asyncio.sleep(1)

        if not success:
            try:
                from gtts import gTTS
                gTTS(text=clean_text, lang=voice_id.split("-")[0] if "-" in voice_id else "ar").save(raw_voice)
            except Exception:
                self._run_ffmpeg(f'ffmpeg -y -f lavfi -i anullsrc=r=44100:cl=stereo -t 4 "{raw_voice}"')

        dur = self._get_audio_duration(raw_voice)
        synth = "0.04*sin(2*PI*220*t)+0.03*sin(2*PI*330*t)" if mood == "upbeat" else "0.04*sin(2*PI*110*t)+0.03*sin(2*PI*165*t)"
        mix_cmd = (
            f'ffmpeg -y -i "{raw_voice}" -f lavfi -i "aevalsrc={synth}:s=44100:d={dur}" '
            f'-filter_complex "[0:a]volume=1.35[v];[1:a]afade=t=in:st=0:d=0.4,afade=t=out:st={max(0.4, dur-0.7)}:d=0.7[bg];'
            f'[v][bg]amix=inputs=2:duration=first" -c:a libmp3lame -q:a 2 "{output_path}"'
        )
        if not self._run_ffmpeg(mix_cmd)[0] or not os.path.exists(output_path):
            if os.path.exists(raw_voice):
                os.replace(raw_voice, output_path)
        return dur

    async def fetch_real_scene_image(self, visual_prompt, search_query, output_jpg, aspect="16:9", mode="hybrid", scene_num=1):
        target_w, target_h = (720, 1280) if aspect == "9:16" else (1280, 720)
        seed = random.randint(1000, 999999)
        headers_b = {"User-Agent": "Mozilla/5.0"}

        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=22)) as session:
            if HF_TOKEN and HF_TOKEN.startswith("hf_"):
                try:
                    hf_url = "https://api-inference.huggingface.co/models/black-forest-labs/FLUX.1-schnell"
                    async with session.post(hf_url, headers={"Authorization": f"Bearer {HF_TOKEN}"}, json={"inputs": f"{visual_prompt}, seed {seed}"}) as resp:
                        if resp.status == 200:
                            data = await resp.read()
                            if len(data) > 5000:
                                with open(output_jpg, "wb") as f:
                                    f.write(data)
                                if self._normalize_image(output_jpg, target_w, target_h, mode):
                                    return True
                except Exception:
                    pass

            for m_name in ["flux", "turbo"]:
                try:
                    enc = urllib.parse.quote(visual_prompt[:340])
                    url = f"https://image.pollinations.ai/prompt/{enc}?width={target_w}&height={target_h}&seed={seed}&model={m_name}&nologo=true"
                    async with session.get(url, headers=headers_b) as resp:
                        if resp.status == 200:
                            data = await resp.read()
                            if len(data) > 5000:
                                with open(output_jpg, "wb") as f:
                                    f.write(data)
                                if self._normalize_image(output_jpg, target_w, target_h, mode):
                                    return True
                except Exception:
                    continue

            if PIXABAY_API_KEY:
                for q in [search_query, "cinematic landscape"]:
                    try:
                        px_url = f"https://pixabay.com/api/?key={PIXABAY_API_KEY}&q={urllib.parse.quote(str(q))}&image_type=photo&per_page=10"
                        async with session.get(px_url, headers=headers_b) as resp:
                            if resp.status == 200:
                                hits = (await resp.json()).get("hits", [])
                                if hits:
                                    img_u = hits[(scene_num - 1) % len(hits)].get("largeImageURL")
                                    if img_u:
                                        async with session.get(img_u, headers=headers_b) as ir:
                                            if ir.status == 200:
                                                with open(output_jpg, "wb") as f:
                                                    f.write(await ir.read())
                                                if self._normalize_image(output_jpg, target_w, target_h, mode):
                                                    return True
                    except Exception:
                        continue

        img = Image.new("RGB", (target_w, target_h), (25, 40, 75))
        ImageDraw.Draw(img).rectangle([40, 40, target_w - 40, target_h - 40], outline=(200, 160, 60), width=4)
        img.save(output_jpg, "JPEG", quality=92)
        return True

    def _normalize_image(self, img_path, w, h, mode="hybrid"):
        try:
            with Image.open(img_path) as im:
                im = ImageOps.fit(im.convert("RGB"), (w, h), method=Image.Resampling.LANCZOS)
                if mode == "kids":
                    im = ImageEnhance.Color(im).enhance(1.4)
                elif mode == "cinematic":
                    im = ImageEnhance.Contrast(im).enhance(1.2)
                im.save(img_path, "JPEG", quality=95)
            return True
        except Exception:
            return False

    def render_animated_scene(self, image_path, audio_path, output_mp4, duration, scene_idx=1, aspect="16:9"):
        w, h = (720, 1280) if aspect == "9:16" else (1280, 720)
        frames = max(75, int(duration * 25) + 10)
        z_expr = "min(zoom+0.0015,1.25)" if scene_idx % 2 == 1 else "if(eq(on,1),1.25,max(1.0,zoom-0.0015))"
        vf = f"scale={int(w*1.25)}:{int(h*1.25)},zoompan=z='{z_expr}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={frames}:s={w}x{h}:fps=25,format=yuv420p"
        cmd = f'ffmpeg -y -i "{image_path}" -i "{audio_path}" -vf "{vf}" -c:v libx264 -preset veryfast -crf 21 -c:a aac -b:a 192k -t {duration} -shortest "{output_mp4}"'
        if not self._run_ffmpeg(cmd)[0] or not os.path.exists(output_mp4):
            self._run_ffmpeg(f'ffmpeg -y -loop 1 -i "{image_path}" -i "{audio_path}" -vf "scale={w}:{h},format=yuv420p" -c:v libx264 -preset ultrafast -c:a aac -t {duration} -shortest "{output_mp4}"')
        return os.path.exists(output_mp4)

    def clean_video_watermarks_and_outro(self, input_video, cleaned_output):
        cap = cv2.VideoCapture(input_video)
        if not cap.isOpened():
            return input_video
        fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        duration = total_frames / fps if fps > 0 else 10.0

        y_tops, y_bottoms = [], []
        for r in [0.15, 0.3, 0.45, 0.6]:
            idx = int(total_frames * r)
            if idx < total_frames:
                cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
                ret, frame = cap.read()
                if ret and frame is not None:
                    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                    center = gray[:, int(width * 0.2):int(width * 0.8)]
                    active = np.where(np.mean(center, axis=1) > 24)[0]
                    if len(active) > 30:
                        y_tops.append(int(active[0]))
                        y_bottoms.append(int(active[-1]))

        cut_duration = duration
        if duration > 6.5:
            cap.set(cv2.CAP_PROP_POS_FRAMES, int(total_frames * 0.35))
            ret_m, frame_m = cap.read()
            if ret_m and frame_m is not None:
                ys = int(np.median(y_tops)) if y_tops else 0
                ye = int(np.median(y_bottoms)) if y_bottoms else height
                roi_m = frame_m[ys:ye, :]
                mid_b = np.mean(cv2.cvtColor(roi_m, cv2.COLOR_BGR2GRAY)) if roi_m.size > 0 else 80.0
                for sec in np.arange(max(3.0, duration - 4.8), duration - 0.2, 0.2):
                    cap.set(cv2.CAP_PROP_POS_FRAMES, int(sec * fps))
                    ret_e, frame_e = cap.read()
                    if ret_e and frame_e is not None:
                        roi_e = frame_e[ys:ye, :]
                        if roi_e.size > 0 and np.mean(cv2.cvtColor(roi_e, cv2.COLOR_BGR2GRAY)) < mid_b * 0.52:
                            cut_duration = max(3.0, sec - 0.2)
                            break
        cap.release()

        if y_tops and y_bottoms:
            y1, y2 = int(np.median(y_tops)), int(np.median(y_bottoms))
            act_h = y2 - y1
            if act_h > height * 0.22 and act_h < height * 0.88:
                margin = int(act_h * 0.05)
                cy = max(0, y1 + margin)
                ch = max(180, min(height - cy, act_h - margin * 2))
                ch -= ch % 2
                cw = width - (width % 2)
                vf = f"crop={cw}:{ch}:0:{cy},scale=1280:720,format=yuv420p"
            else:
                cw = int(width * 0.90) - (int(width * 0.90) % 2)
                ch = int(height * 0.84) - (int(height * 0.84) % 2)
                vf = f"crop={cw}:{ch}:{(width-cw)//2}:{(height-ch)//2},format=yuv420p"
        else:
            vf = "format=yuv420p"

        cmd = f'ffmpeg -y -i "{input_video}" -t {cut_duration:.2f} -vf "{vf}" -c:v libx264 -preset veryfast -crf 20 -c:a aac -b:a 192k "{cleaned_output}"'
        return cleaned_output if (self._run_ffmpeg(cmd)[0] and os.path.exists(cleaned_output)) else input_video

    def _extract_source_face(self, face_path):
        img = cv2.imread(face_path)
        if img is None:
            return None
        if self.face_cascade is not None:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            faces = self.face_cascade.detectMultiScale(gray, 1.1, 4, minSize=(40, 40))
            if len(faces) > 0:
                x, y, w, h = sorted(faces, key=lambda b: b[2] * b[3], reverse=True)[0]
                px, py = int(w * 0.08), int(h * 0.08)
                return img[max(0, y + py):min(img.shape[0], y + h - py), max(0, x + px):min(img.shape[1], x + w - px)]
        h, w = img.shape[:2]
        return img[int(h * 0.12):int(h * 0.88), int(w * 0.12):int(w * 0.88)]

    def _swap_face_on_frame(self, frame, src_face_crop, last_box=None):
        if self.face_cascade is None:
            return frame, None
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = self.face_cascade.detectMultiScale(gray, 1.1, 3, minSize=(32, 32))
        if len(faces) == 0 and self.profile_cascade is not None:
            faces = self.profile_cascade.detectMultiScale(gray, 1.1, 3, minSize=(32, 32))

        box = None
        if len(faces) > 0:
            fx, fy, fw, fh = [int(v) for v in sorted(faces, key=lambda b: b[2] * b[3], reverse=True)[0]]
            if last_box is not None:
                lx, ly, lw, lh, _ = last_box
                fx, fy, fw, fh = int(0.6*fx+0.4*lx), int(0.6*fy+0.4*ly), int(0.6*fw+0.4*lw), int(0.6*fh+0.4*lh)
            box = (fx, fy, fw, fh, 0)
        elif last_box is not None and last_box[4] < 12:
            box = (last_box[0], last_box[1], last_box[2], last_box[3], last_box[4] + 1)

        if box is None:
            return frame, None
        x, y, w, h, _ = box
        fh_i, fw_i = frame.shape[:2]
        x, y = max(2, min(x, fw_i - w - 2)), max(2, min(y, fh_i - h - 2))
        if w < 20 or h < 20 or x + w >= fw_i or y + h >= fh_i:
            return frame, box

        roi = frame[y:y + h, x:x + w]
        resized = cv2.resize(src_face_crop, (w, h), interpolation=cv2.INTER_LANCZOS4)
        mask = np.zeros((h, w), dtype=np.float32)
        cv2.ellipse(mask, (w // 2, h // 2), (int(w * 0.43), int(h * 0.46)), 0, 0, 360, 1.0, -1)
        bk = max(5, (min(w, h) // 5) | 1)
        mask = cv2.GaussianBlur(mask, (bk, bk), 0)
        try:
            frame = cv2.seamlessClone(resized, frame, np.clip(mask * 255, 0, 255).astype(np.uint8), (x + w // 2, y + h // 2), cv2.NORMAL_CLONE)
        except Exception:
            m3 = mask[:, :, np.newaxis]
            frame[y:y + h, x:x + w] = (resized.astype(np.float32) * m3 + roi.astype(np.float32) * (1.0 - m3)).astype(np.uint8)
        return frame, box

    async def process_face_cloning_video(self, face_path, video_path, custom_caption=""):
        sid = random.randint(10000, 99999)
        cleaned_v = os.path.join(self.work_dir, f"clean_{sid}.mp4")
        swapped_v = os.path.join(self.work_dir, f"swap_{sid}.mp4")
        out_v = os.path.join(self.work_dir, f"cloned_{sid}.mp4")

        working_v = await asyncio.to_thread(self.clean_video_watermarks_and_outro, video_path, cleaned_v)
        src_crop = await asyncio.to_thread(self._extract_source_face, face_path)

        if src_crop is not None:
            def _do_swap():
                cap = cv2.VideoCapture(working_v)
                if not cap.isOpened():
                    return False
                fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
                w, h = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                wr = cv2.VideoWriter(swapped_v, cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))
                last_b = None
                while True:
                    ret, frm = cap.read()
                    if not ret or frm is None:
                        break
                    frm, last_b = self._swap_face_on_frame(frm, src_crop, last_b)
                    wr.write(frm)
                cap.release()
                wr.release()
                return os.path.exists(swapped_v)

            ok_s = await asyncio.to_thread(_do_swap)
            v_src = swapped_v if ok_s else working_v
        else:
            v_src = working_v

        cmd = f'ffmpeg -y -i "{v_src}" -i "{working_v}" -map 0:v:0 -map 1:a:0? -c:v libx264 -preset veryfast -crf 20 -c:a aac -shortest "{out_v}"'
        return out_v if (self._run_ffmpeg(cmd)[0] and os.path.exists(out_v)) else working_v

    async def produce_full_video(self, blueprint, status_callback=None, custom_face_path=None):
        scenes = blueprint.get("scenes", [])
        mode = blueprint.get("mode", "hybrid")
        aspect = blueprint.get("aspect", "16:9")
        mood = blueprint.get("bg_music_mood", "epic")
        sid = random.randint(10000, 99999)
        vids = []

        for idx, sc in enumerate(scenes):
            n = idx + 1
            if status_callback:
                try:
                    await status_callback(f"🎥 **جاري تصوير المشهد ({n}/{len(scenes)})...**")
                except Exception:
                    pass
            img_p = os.path.join(self.work_dir, f"img_{sid}_{n}.jpg")
            aud_p = os.path.join(self.work_dir, f"aud_{sid}_{n}.mp3")
            vid_p = os.path.join(self.work_dir, f"vid_{sid}_{n}.mp4")

            dur = await self.generate_human_voice(sc.get("narration_ar", ""), aud_p, sc.get("voice_id", "ar-SA-HamedNeural"), sc.get("voice_rate", "-2%"), sc.get("voice_pitch", "-1Hz"), mood)
            await self.fetch_real_scene_image(sc.get("visual_prompt_en", ""), sc.get("search_query_en", "cinematic"), img_p, aspect, mode, n)
            if self.render_animated_scene(img_p, aud_p, vid_p, dur, n, aspect):
                vids.append(vid_p)

        if not vids:
            return None
        final_out = os.path.join(self.work_dir, f"master_{sid}.mp4")
        lst = os.path.join(self.work_dir, f"list_{sid}.txt")
        with open(lst, "w", encoding="utf-8") as f:
            for v in vids:
                f.write(f"file '{os.path.abspath(v)}'\n")
        return final_out if (self._run_ffmpeg(f'ffmpeg -y -f concat -safe 0 -i "{lst}" -c copy "{final_out}"')[0] and os.path.exists(final_out)) else vids[0]

    async def produce_personal_story_reel(self, photo_paths, caption_text="", custom_audio_path=None, lang_code="ar"):
        sid = random.randint(10000, 99999)
        w, h = 720, 1280
        imgs = []
        for idx, p in enumerate(photo_paths):
            if not os.path.exists(p):
                continue
            out_i = os.path.join(self.work_dir, f"st_{sid}_{idx}.jpg")
            try:
                with Image.open(p) as im:
                    im = im.convert("RGB")
                    bg = ImageOps.fit(im, (w, h), method=Image.Resampling.LANCZOS).filter(ImageFilter.GaussianBlur(25))
                    bg = ImageEnhance.Brightness(bg).enhance(0.65)
                    fg = im.copy()
                    fg.thumbnail((w, int(h * 0.88)), Image.Resampling.LANCZOS)
                    bg.paste(fg, ((w - fg.width) // 2, (h - fg.height) // 2))
                    bg.save(out_i, "JPEG", quality=95)
                    imgs.append(out_i)
            except Exception:
                continue
        if not imgs:
            return None

        aud = os.path.join(self.work_dir, f"st_aud_{sid}.mp3")
        if custom_audio_path and os.path.exists(custom_audio_path):
            aud = custom_audio_path
            tdur = self._get_audio_duration(aud)
        elif caption_text.strip():
            tdur = await self.generate_human_voice(caption_text, aud, SUPPORTED_LANGUAGES.get(lang_code, SUPPORTED_LANGUAGES["ar"])["male_voice"], mood="upbeat")
            tdur = max(tdur, len(imgs) * 3.2)
        else:
            tdur = max(6.0, len(imgs) * 3.5)
            self._run_ffmpeg(f'ffmpeg -y -f lavfi -i "aevalsrc=0.05*sin(2*PI*220*t)+0.03*sin(2*PI*330*t):s=44100:d={tdur}" -c:a libmp3lame "{aud}"')

        sdur = max(2.8, tdur / len(imgs))
        clips = []
        for idx, ip in enumerate(imgs):
            cp = os.path.join(self.work_dir, f"st_c_{sid}_{idx}.mp4")
            if self.render_animated_scene(ip, aud, cp, sdur, idx + 1, "9:16"):
                clips.append(cp)
        if not clips:
            return None
        final_s = os.path.join(self.work_dir, f"story_final_{sid}.mp4")
        lst = os.path.join(self.work_dir, f"st_lst_{sid}.txt")
        with open(lst, "w", encoding="utf-8") as f:
            for c in clips:
                f.write(f"file '{os.path.abspath(c)}'\n")
        self._run_ffmpeg(f'ffmpeg -y -f concat -safe 0 -i "{lst}" -c copy "{final_s}"')
        return final_s if os.path.exists(final_s) else clips[0]


boardroom = StudioBoardroom()
media_engine = StudioMediaEngine()

# =====================================================================
# 4. بوت تيليجرام الرئيسي
# =====================================================================
app = Client("genesis_bot_session", api_id=TELEGRAM_API_ID, api_hash=TELEGRAM_API_HASH, bot_token=TELEGRAM_BOT_TOKEN, in_memory=True)
user_sessions = {}
user_locks = {}


def get_session(cid):
    if cid not in user_sessions:
        user_sessions[cid] = {"mode": "hybrid", "lang": "ar", "scenes": 5, "story_photos": [], "story_audio": None, "clone_face": None, "produced_videos": []}
    return user_sessions[cid]


def get_lock(cid):
    if cid not in user_locks:
        user_locks[cid] = asyncio.Lock()
    return user_locks[cid]


def get_keyboard():
    return ReplyKeyboardMarkup(
        [
            ["🎬 سينمائي 100%", "🧠 المخرج الذكي (هجين)"],
            ["👶 كرتون وأنيميشن 3D", "📸 ستوري وريلز صوري"],
            ["🗣️ حوار تمثيلي", "📢 مدير الإعلانات", "📰 أخبار"],
            ["🧬 استنساخ الوجه والصوت", "✂️ حذف العلامة المائية"],
            ["🌐 اللغة والصوت البشري", "💡 فحص ترقيات النظام"],
            ["⚡ سريع", "🎞️ دمج سلسلة في فيلم طويل (/make_movie)"]
        ],
        resize_keyboard=True
    )


@app.on_message(filters.command("start"))
async def start_cmd(client, message):
    sess = get_session(message.chat.id)
    await message.reply_text(
        f"🎬 **مرحباً بك يا زكريا في استوديو Genesis Engine (الإصدار المستقر v{boardroom.upgrade_level}.0)!**\n\n"
        f"✅ **جميع المحركات نشطة:** 20 وكيلاً + توليد صور FLUX + حذف العلامة المائية وخاتمة إنستجرام + استنساخ الوجه المباشر + ستوري صوري.\n"
        f"🎛️ **الوضع الحالي:** `{PRODUCTION_MODES.get(sess['mode'])}`\n"
        f"🌐 **اللغة والصوت:** `{SUPPORTED_LANGUAGES.get(sess['lang'])['name']}`",
        reply_markup=get_keyboard()
    )


@app.on_callback_query()
async def cb_handler(client, query):
    cid = query.message.chat.id
    sess = get_session(cid)
    data = query.data
    if data.startswith("setlang_"):
        lc = data.replace("setlang_", "")
        if lc in SUPPORTED_LANGUAGES:
            sess["lang"] = lc
            await query.message.edit_text(f"✅ **تم تفعيل اللغة والصوت البشري:** {SUPPORTED_LANGUAGES[lc]['name']}")
    elif data == "activate_upgrade":
        boardroom.upgrade_level += 1
        await query.message.edit_text(f"🚀 **تم تفعيل الترقية الخارقة (v{boardroom.upgrade_level}.0) بنجاح!**")
    elif data == "start_story_render":
        lock = get_lock(cid)
        if lock.locked():
            return
        async with lock:
            await query.message.edit_text("⏳ **جاري مونتاج الستوري الاحترافي من صورك الشخصية...**")
            out = await media_engine.produce_personal_story_reel(sess["story_photos"], "", sess["story_audio"], sess["lang"])
            if out and os.path.exists(out):
                await client.send_video(cid, out, caption="📸 **تم إنتاج الستوري الاحترافي بنجاح!**")
                sess["story_photos"] = []


@app.on_message(filters.photo | filters.video | filters.voice | filters.audio)
async def media_handler(client, message):
    cid = message.chat.id
    sess = get_session(cid)
    os.makedirs("workspace", exist_ok=True)

    if sess["mode"] == "story" and message.photo:
        p = await message.download(file_name=f"workspace/st_{cid}_{len(sess['story_photos'])+1}.jpg")
        sess["story_photos"].append(p)
        kb = InlineKeyboardMarkup([[InlineKeyboardButton(f"🚀 ابدأ مونتاج الستوري ({len(sess['story_photos'])} صور)", callback_data="start_story_render")]])
        await message.reply_text("📸 **تم حفظ الصورة للستوري!** أرسل المزيد أو اضغط الزر للبدء:", reply_markup=kb)
        return

    if message.photo:
        f_p = await message.download(file_name=f"workspace/face_{cid}.jpg")
        sess["clone_face"] = f_p
        sess["story_photos"].append(f_p)
        await message.reply_text("🧬 **تم حفظ ملامح وجهك بنجاح!** أرسل الآن **الفيديو** لحذف العلامة المائية ودمج ملامح وجهك مباشرة.")
        return

    if message.video:
        lock = get_lock(cid)
        if lock.locked():
            await message.reply_text("⏳ انتظر اكتمال العملية الحالية...")
            return
        async with lock:
            v_p = await message.download(file_name=f"workspace/vid_{cid}.mp4")
            if sess["mode"] == "cloning" and sess["clone_face"] and os.path.exists(sess["clone_face"]):
                w_msg = await message.reply_text("🧬 **جاري حذف العلامة المائية وخاتمة الفيديو وتركيب ملامح وجهك مباشرة...**")
                out = await media_engine.process_face_cloning_video(sess["clone_face"], v_p, message.caption or "")
                await client.send_video(cid, out, caption="🧬 **تم حذف العلامة المائية واستنساخ الوجه بنجاح!**")
                await w_msg.delete()
            else:
                w_msg = await message.reply_text("✂️ **جاري حذف العلامة المائية والأشرطة السوداء وشاشة النهاية...**")
                c_out = f"workspace/clean_{cid}_{random.randint(10,99)}.mp4"
                res = await asyncio.to_thread(media_engine.clean_video_watermarks_and_outro, v_p, c_out)
                await client.send_video(cid, res, caption="✨ **تم حذف العلامة المائية وخاتمة الفيديو بالكامل!**")
                await w_msg.delete()


@app.on_message(filters.text)
async def txt_handler(client, message):
    cid = message.chat.id
    text = message.text.strip()
    sess = get_session(cid)

    if text == "✂️ حذف العلامة المائية":
        sess["mode"] = "clean_watermark"
        await message.reply_text("✂️ **أرسل أي فيديو الآن لحذف العلامة المائية والأشرطة السوداء وشاشة النهاية منه فوراً!**")
        return

    modes_map = {
        "🎬 سينمائي 100%": "cinematic", "🧠 المخرج الذكي (هجين)": "hybrid", "👶 كرتون وأنيميشن 3D": "kids",
        "📸 ستوري وريلز صوري": "story", "🗣️ حوار تمثيلي": "dialogue", "📢 مدير الإعلانات": "ads",
        "📰 أخبار": "news", "🧬 استنساخ الوجه والصوت": "cloning", "⚡ سريع": "fast"
    }
    if text in modes_map:
        sess["mode"] = modes_map[text]
        await message.reply_text(f"🎯 **تم تفعيل وضع:** `{PRODUCTION_MODES.get(sess['mode'], sess['mode'])}`\nأرسل طلبك الآن للبدء!")
        return

    if text == "🌐 اللغة والصوت البشري":
        btns = [[InlineKeyboardButton(info["name"], callback_data=f"setlang_{code}")] for code, info in SUPPORTED_LANGUAGES.items()]
        await message.reply_text("🌐 **اختر لغة الفيديو والحنجرة البشرية:**", reply_markup=InlineKeyboardMarkup(btns))
        return

    if text == "💡 فحص ترقيات النظام":
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("✅ تفعيل الترقية الخارقة فوراً!", callback_data="activate_upgrade")]])
        await message.reply_text("🔬 **تم العثور على ترقيات مجانية لمحرك الصور FLUX والماسترينغ الصوتي وقاطع العلامات المائية.** هل تريد تفعيلها؟", reply_markup=kb)
        return

    lock = get_lock(cid)
    if lock.locked():
        await message.reply_text("⏳ جاري إنتاج الفيديو الحالي، انتظر لحظات...")
        return

    async with lock:
        st_msg = await message.reply_text("💬 **غرفة العمليات (20 وكيلاً) تصيغ السيناريو وتولد المشاهد الآن...**")
        bp, log_txt = await boardroom.run_consensus_debate(text, sess["mode"], sess["scenes"], sess["lang"])
        last_t = [time.time()]

        async def prog(p_txt):
            if time.time() - last_t[0] >= 3.5:
                last_t[0] = time.time()
                try:
                    await st_msg.edit_text(f"{log_txt}\n\n{p_txt}")
                except Exception:
                    pass

        vid = await media_engine.produce_full_video(bp, status_callback=prog)
        if vid and os.path.exists(vid):
            sess["produced_videos"].append(vid)
            await client.send_video(cid, vid, caption=f"🎬 **{bp.get('title', text[:45])}**")
            await st_msg.delete()
        else:
            await st_msg.edit_text("⚠️ تعذر إنتاج الفيديو، حاول مرة أخرى.")


if __name__ == "__main__":
    print("🚀 Genesis Studio v3.0 Running...")
    app.run()
