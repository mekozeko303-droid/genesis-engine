# -*- coding: utf-8 -*-
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
            fatal.append("برنامج FFmpeg غير متوفر.")
        if not config.PIXABAY_API_KEY:
            warn.append("PIXABAY_API_KEY غير مضبوط (سيتم الاعتماد على الذكاء الاصطناعي وWikimedia).")
        return fatal, warn

    async def close(self) -> None:
        pass

    @staticmethod
    def parse_requested_duration(idea_text: str, user_default_sec: int = 60) -> int:
        m_min = re.search(r"(\d+)\s*(?:دقائق|دقيقة|دقيقه|دقايق|minutes|min)", idea_text, re.IGNORECASE)
        if m_min:
            mins = min(int(m_min.group(1)), 12)
            return max(30, mins * 60)

        m_sec = re.search(r"(\d+)\s*(?:ثانية|ثانيه|ثواني|seconds|sec)", idea_text, re.IGNORECASE)
        if m_sec:
            return max(20, min(int(m_sec.group(1)), 720))

        return max(30, min(user_default_sec, 720))

    @classmethod
    def build_full_script(cls, raw_idea: str, mode: config.Mode, target_sec: int) -> dict:
        """
        يصفي رسالة المستخدم من التعليمات الحرفية، ويؤلف سيناريو غنياً يغطي المدة المطلوبة بالكامل (من 30 ثانية حتى 10 دقائق).
        """
        # تصفية أي جمل توجيهية حتى لا يقرأها المعلق
        cleaned_text = raw_idea
        for pat in ["أنت كاتب سيناريو", "المطلوب منك", "الفئة المستهدفة", "الأسلوب:", "اجعل التوقيتات", "أخرج النتيجة"]:
            cleaned_text = cleaned_text.replace(pat, "")

        if len(cleaned_text.strip()) < 5:
            cleaned_text = mode.sample_idea

        if target_sec <= 45:
            num_scenes = 3
        elif target_sec <= 90:
            num_scenes = 5
        elif target_sec <= 200:
            num_scenes = 10
        elif target_sec <= 360:
            num_scenes = 15
        else:
            num_scenes = 24

        sys_role = (
            "أنت كاتب سيناريو ومخرج محترف. مهمتك تحويل فكرة المستخدم إلى نص تعليق صوتي فصيح ومؤثر للمشاهد.\n"
            f"الفكرة الأساسية: {cleaned_text}\n"
            f"الوضع: {mode.name_ar} ({mode.desc_ar})\n"
            f"قسّم السيناريو إلى {num_scenes} مشاهد متسلسلة تغطي مدة {target_sec} ثانية.\n"
            "أخرج JSON فقط بهذه الصيغة:\n"
            "{\n"
            '  "title": "عنوان جذاب بالعربية",\n'
            '  "pinned_comment": "سؤال تفاعلي للمشاهدين",\n'
            '  "scenes": [\n'
            '    {"narration_ar": "نص التعليق الصوتي للمشهد (35 إلى 50 كلمة)", "visual_en": "Detailed English visual prompt"}\n'
            "  ]\n"
            "}"
        )

        try:
            r = requests.post(
                "https://text.pollinations.ai/",
                json={
                    "messages": [
                        {"role": "system", "content": sys_role},
                        {"role": "user", "content": cleaned_text},
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
                        return {
                            "title": parsed.get("title") or f"{mode.emoji} {cleaned_text[:40]}",
                            "pinned_comment": parsed.get("pinned_comment") or f"ما رأيك في هذا الفيديو؟ شاركنا برأيك! 👇",
                            "vid_search_en": mode.pixabay_q,
                            "scenes": parsed["scenes"],
                            "hashtags": ["#اكسبلور", "#تريند", "#فيديو", "#shorts", f"#{mode.id}"],
                        }
        except Exception:
            pass

        # خطة بديلة لإنشاء المشاهد إذا لم يستجب الـ LLM
        scenes = []
        for i in range(num_scenes):
            scenes.append({
                "narration_ar": f"في هذا الفصل نستعرض تفاصيل {cleaned_text[:45]}، وكيف تترك أثراً عميقاً ومذهلاً بأسلوب متجدد وممتع.",
                "visual_en": f"{mode.style_en}, scene {i+1} depicting {cleaned_text[:30]}, masterpiece 8k",
            })

        return {
            "title": f"{mode.emoji} {cleaned_text[:40]}",
            "pinned_comment": "ما رأيك في هذا الفيديو؟ شاركنا برأيك في التعليقات! 👇",
            "vid_search_en": mode.pixabay_q,
            "scenes": scenes,
            "hashtags": ["#اكسبلور", "#تريند", "#فيديو", "#shorts", f"#{mode.id}"],
        }

    @staticmethod
    async def synthesize_voice_segment(text_ar: str, voice_name: str, rate_str: str, out_mp3: Path) -> float:
        raw_audio = out_mp3.with_suffix(".raw.mp3")
        ok = False
        try:
            comm = edge_tts.Communicate(text_ar, voice_name, rate=rate_str)
            await asyncio.wait_for(comm.save(str(raw_audio)), timeout=10)
            if raw_audio.exists() and raw_audio.stat().st_size > 500:
                ok = True
        except Exception:
            ok = False

        if not ok:
            try:
                def _gtts():
                    gTTS(text=text_ar, lang="ar", slow=False).save(str(raw_audio))
                await asyncio.to_thread(_gtts)
                if raw_audio.exists() and raw_audio.stat().st_size > 500:
                    ok = True
            except Exception:
                ok = False

        if ok:
            cmd = [
                FFMPEG_BIN, "-y", "-i", str(raw_audio),
                "-ar", "44100", "-ac", "2", "-b:a", "128k", str(out_mp3)
            ]
            await asyncio.to_thread(subprocess.run, cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if not out_mp3.exists():
                shutil.copyfile(raw_audio, out_mp3)
        else:
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
    def fetch_pixabay_videos(cls, query_en: str, work_dir: Path, max_clips: int = 6) -> list[Path]:
        if not config.PIXABAY_API_KEY:
            return []
        clips = []
        queries = [query_en, "cinematic nature"]
        seen = set()
        for q in queries:
            clean_q = re.sub(r"[^\w\s]", " ", q).strip()
            if not clean_q or len(clips) >= max_clips:
                continue
            try:
                url = f"[https://pixabay.com/api/videos/?key=](https://pixabay.com/api/videos/?key=){config.PIXABAY_API_KEY}&q={urllib.parse.quote(clean_q)}&per_page=10"
                r = requests.get(url, headers=BROWSER_HEADERS, timeout=10)
                if r.status_code == 200:
                    for h in r.json().get("hits", []):
                        if len(clips) >= max_clips:
                            break
                        vids = h.get("videos", {})
                        v_url = vids.get("medium", {}).get("url") or vids.get("small", {}).get("url")
                        if v_url and v_url not in seen:
                            seen.add(v_url)
                            vr = requests.get(v_url, headers=BROWSER_HEADERS, timeout=12)
                            if vr.status_code == 200 and len(vr.content) > 20000:
                                p = work_dir / f"stock_{len(clips)}.mp4"
                                p.write_bytes(vr.content)
                                clips.append(p)
            except Exception:
                pass
        return clips

    @classmethod
    def fetch_scene_visual_image(cls, prompt_en: str, mode: config.Mode, out_jpg: Path, seed: int, idx: int) -> bool:
        clean_prompt = re.sub(r"[^\w\s,.-]", " ", prompt_en)
        clean_prompt = " ".join(clean_prompt.split())[:200]
        s_val = seed + idx * 17

        # 1. محرك Pollinations Flux
        for mdl in ["flux", "turbo"]:
            try:
                enc = urllib.parse.quote(clean_prompt)
                url = f"[https://image.pollinations.ai/prompt/](https://image.pollinations.ai/prompt/){enc}?width=576&height=1024&seed={s_val}&nologo=true&model={mdl}"
                r = requests.get(url, headers=BROWSER_HEADERS, timeout=12)
                if r.status_code == 200 and cls._save_valid_img(r.content, out_jpg):
                    return True
            except Exception:
                pass

        # 2. صور فوتوغرافية حقيقية من Picsum
        try:
            r = requests.get(f"[https://picsum.photos/seed/](https://picsum.photos/seed/){s_val + 77}/576/1024", headers=BROWSER_HEADERS, timeout=10)
            if r.status_code == 200 and cls._save_valid_img(r.content, out_jpg):
                return True
        except Exception:
            pass

        return False

    async def produce(self, idea: str, mode_id: str, target_duration: int = 60, progress=None) -> ProductionResult:
        mode = config.MODES.get(mode_id, config.MODES["cinematic"])
        effective_target_sec = self.parse_requested_duration(idea, target_duration)

        job_dir = config.TEMP_DIR / f"job_{mode.id}_{int(time.time())}_{random.randint(100, 999)}"
        job_dir.mkdir(parents=True, exist_ok=True)

        if progress:
            await progress("script", f"(المدة: {effective_target_sec} ثانية)")

        script = await asyncio.to_thread(self.build_full_script, idea, mode, effective_target_sec)
        scenes = script["scenes"]
        num_scenes = len(scenes)
        min_scene_dur = max(3.0, round(effective_target_sec / num_scenes, 2))

        if progress:
            await progress("voice")

        audio_paths: list[Path] = []
        scene_durations: list[float] = []
        for idx, sc in enumerate(scenes):
            a_path = job_dir / f"voice_{idx}.mp3"
            dur = await self.synthesize_voice_segment(sc["narration_ar"], mode.voice, mode.voice_rate, a_path)
            audio_paths.append(a_path)
            scene_durations.append(max(min_scene_dur, dur + 0.4))

        if progress:
            await progress("assets")

        stock_clips = []
        if mode.engine in ("hybrid_video", "stock_video"):
            stock_clips = await asyncio.to_thread(self.fetch_pixabay_videos, script["vid_search_en"], job_dir, min(num_scenes, 4))

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

            used_clip = stock_clips[idx % len(stock_clips)] if (stock_clips and idx % 2 == 1) else None
            if used_clip and used_clip.exists():
                used_assets.append("Pixabay-HD-MP4")
                cmd = [
                    FFMPEG_BIN, "-y", "-stream_loop", "-1", "-i", str(used_clip),
                    "-i", str(a_path), "-t", str(seg_dur),
                    "-vf", f"scale=576:1024:force_original_aspect_ratio=increase,crop=576:1024,{mode.vfilter},format=yuv420p",
                    "-map", "0:v:0", "-map", "1:a:0", "-c:v", "libx264", "-preset", "ultrafast", "-r", "24",
                    "-c:a", "aac", "-b:a", "128k", str(seg_out),
                ]
                await asyncio.to_thread(subprocess.run, cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            if not seg_out.exists() or seg_out.stat().st_size < 1500:
                img_p = job_dir / f"frame_{idx:03d}.jpg"
                await asyncio.to_thread(self.fetch_scene_visual_image, sc["visual_en"], mode, img_p, seed, idx)
                if first_thumb is None and img_p.exists():
                    first_thumb = img_p
                used_assets.append("AI-Scene-Render")

                cam_moves = [
                    f"zoompan=z='min(zoom+0.0020,1.24)':d={frames}:x='iw/2-(iw/zoom/2)':y='ih/2-(iw/zoom/2)':s=576x1024:fps=24",
                    f"zoompan=z='1.18':d={frames}:x='(iw-iw/zoom)*(on/{frames})':y='ih/2-(ih/zoom/2)':s=576x1024:fps=24",
                ]
                zp = cam_moves[idx % len(cam_moves)]
                cmd_zp = [
                    FFMPEG_BIN, "-y", "-loop", "1", "-i", str(img_p),
                    "-i", str(a_path), "-t", str(seg_dur),
                    "-vf", f"{zp},{mode.vfilter},format=yuv420p",
                    "-map", "0:v:0", "-map", "1:a:0", "-c:v", "libx264", "-preset", "ultrafast", "-r", "24",
                    "-c:a", "aac", "-b:a", "128k", str(seg_out),
                ]
                await asyncio.to_thread(subprocess.run, cmd_zp, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

                if not seg_out.exists() or seg_out.stat().st_size < 1500:
                    cmd_simple = [
                        FFMPEG_BIN, "-y", "-loop", "1", "-t", str(seg_dur), "-i", str(img_p),
                        "-i", str(a_path), "-vf", "scale=576:1024,format=yuv420p",
                        "-map", "0:v:0", "-map", "1:a:0", "-c:v", "libx264", "-preset", "ultrafast", "-r", "24",
                        "-c:a", "aac", "-b:a", "128k", "-shortest", str(seg_out),
                    ]
                    await asyncio.to_thread(subprocess.run, cmd_simple, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            if seg_out.exists() and seg_out.stat().st_size > 1000:
                rendered_segments.append(seg_out)

        if not rendered_segments:
            raise ProductionError("تعذر تجميع مشاهد الفيديو.")

        if progress:
            await progress("finalize")

        concat_file = job_dir / "concat.txt"
        concat_file.write_text("\n".join(f"file '{p.name}'" for p in rendered_segments), encoding="utf-8")

        final_mp4 = job_dir / f"genesis_{mode.id}_final.mp4"
        merge_cmd = [
            FFMPEG_BIN, "-y", "-f", "concat", "-safe", "0", "-i", str(concat_file),
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", "26",
            "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k", str(final_mp4),
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
            notes=[f"الوضع: {mode.name_ar}", f"المدة الفعلية: {int(total_dur)} ثانية"],
        )
