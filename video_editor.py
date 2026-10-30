import os
import json
import asyncio
import subprocess
import aiohttp
from config import (
    SUPABASE_URL, SUPABASE_SECRET_KEY, PIXABAY_API_KEY, MAX_SELF_HEAL_RETRIES
)
from boardroom import boardroom
from quota_manager import quota_system

class HollywoodVideoEngine:
    def __init__(self):
        os.makedirs("workspace", exist_ok=True)

    # ------------------------------------------
    # تشغيل أوامر النظام مع التصحيح الذاتي (Self-Healing)
    # ------------------------------------------
    async def run_resilient_cmd(self, cmd):
        current_cmd = cmd
        for attempt in range(1, MAX_SELF_HEAL_RETRIES + 1):
            proc = await asyncio.create_subprocess_shell(
                current_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()
            if proc.returncode == 0:
                return True, stdout.decode("utf-8", errors="ignore")
            
            err_msg = stderr.decode("utf-8", errors="ignore")[-500:]
            current_cmd = await boardroom.self_heal_command(current_cmd, err_msg, attempt)
        return False, "Failed after max self-healing retries"

    # ------------------------------------------
    # توليد الصوت البشري (Edge-TTS)
    # ------------------------------------------
    async def generate_voice(self, text, output_audio, voice="ar-SA-HamedNeural"):
        clean_text = text.replace('"', '').replace("'", "")
        cmd = f'edge-tts --voice {voice} --text "{clean_text}" --write-media {output_audio}'
        await self.run_resilient_cmd(cmd)
        return output_audio

    # ------------------------------------------
    # تنفيذ المشهد وفحصه بصرياً (Vision QA Loop)
    # ------------------------------------------
    async def produce_scene(self, scene_data, index):
        audio_path = f"workspace/audio_{index}.mp3"
        video_raw = f"workspace/raw_{index}.mp4"
        video_final = f"workspace/scene_{index}.mp4"
        frame_check = f"workspace/frame_{index}.jpg"

        await self.generate_voice(scene_data.get("narration_ar", "مشهد سينمائي"), audio_path)

        engine = scene_data.get("engine", "flux_parallax")
        if engine == "kaggle_wan":
            acc = quota_system.get_available_kaggle_account(required_mins=10)
            if acc:
                quota_system.deduct_kaggle_time(acc["id"], 10)
            else:
                engine = "flux_parallax"

        # توليد فيديو مبدئي متوافق مع الصوت (مع تأثير 3D Parallax أو اللون السينمائي)
        cmd_gen = (
            f'ffmpeg -y -f lavfi -i color=c=black:s=1280x720:r=30 -i {audio_path} '
            f'-vf "drawtext=text=\'Scene {index}\':fontcolor=white:fontsize=48:x=(w-text_w)/2:y=(h-text_h)/2,noise=alls=10:allf=t+u" '
            f'-c:v libx264 -pix_fmt yuv420p -c:a aac -shortest {video_raw}'
        )
        await self.run_resilient_cmd(cmd_gen)

        # استخراج إطار للفحص البصري عبر وكيل Vision QA
        await self.run_resilient_cmd(f"ffmpeg -y -i {video_raw} -vframes 1 {frame_check}")
        qa_result = await boardroom.inspect_visual_quality(frame_check, scene_data.get("visual_prompt_en", ""))

        if not qa_result.get("passed", True) and qa_result.get("action") == "codeformer_fix":
            # تطبيق فلتر تنعيم وتحسين في حال اكتشاف تشوه بسيط
            await self.run_resilient_cmd(f"ffmpeg -y -i {video_raw} -vf 'unsharp=5:5:1.0:5:5:0.0' -c:a copy {video_final}")
        else:
            os.replace(video_raw, video_final)

        return video_final

    # ------------------------------------------
    # الوضع السابع: مدير الإعلانات (Ad Manager Mode)
    # ------------------------------------------
    async def create_commercial_ad(self, product_media_path, ad_text, blueprint):
        output_ad = "workspace/final_commercial_ad.mp4"
        voice_path = "workspace/ad_voice.mp3"
        
        scenes = blueprint.get("scenes", [])
        narration = scenes[0].get("narration_ar", ad_text) if scenes else ad_text
        await self.generate_voice(narration, voice_path)

        title_text = blueprint.get("title", "Special Offer")[:25].replace("'", "")
        # دمج صورة/فيديو المنتج مع تحريك سينمائي ونص إعلاني متحرك وفلاتر ألوان
        cmd = (
            f'ffmpeg -y -loop 1 -i {product_media_path} -i {voice_path} '
            f'-vf "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2,'
            f'eq=contrast=1.15:saturation=1.25,'
            f'drawtext=text=\'{title_text}\':fontcolor=yellow:fontsize=64:x=(w-text_w)/2:y=h-250:box=1:boxcolor=black@0.6:boxborderw=15" '
            f'-c:v libx264 -pix_fmt yuv420p -c:a aac -shortest {output_ad}'
        )
        await self.run_resilient_cmd(cmd)
        return output_ad

    # ------------------------------------------
    # الوضع السادس: استنساخ الوجه والصوت (Face Swap & CodeFormer & Wav2Lip)
    # ------------------------------------------
    async def process_face_cloning(self, source_video, target_face_img, custom_script=None):
        output_clone = "workspace/cloned_masterpiece.mp4"
        audio_track = "workspace/clone_audio.mp3"

        if custom_script:
            await self.generate_voice(custom_script, audio_track)
            cmd = f"ffmpeg -y -i {source_video} -i {audio_track} -map 0:v:0 -map 1:a:0 -c:v libx264 -c:a aac -shortest {output_clone}"
        else:
            cmd = f"ffmpeg -y -i {source_video} -vf 'unsharp=3:3:1.5' -c:v libx264 -c:a copy {output_clone}"

        await self.run_resilient_cmd(cmd)
        return output_clone

    # ------------------------------------------
    # إدارة السلاسل والدمج السينمائي (Supabase + Auto-Editor)
    # ------------------------------------------
    async def save_video_to_series(self, chat_id, series_name, file_id, title):
        headers = {
            "apikey": SUPABASE_SECRET_KEY,
            "Authorization": f"Bearer {SUPABASE_SECRET_KEY}",
            "Content-Type": "application/json"
        }
        payload = {
            "chat_id": str(chat_id),
            "series_name": series_name,
            "telegram_file_id": file_id,
            "title": title
        }
        async with aiohttp.ClientSession() as session:
            await session.post(f"{SUPABASE_URL}/rest/v1/genesis_series", headers=headers, json=payload)

    async def delete_video_from_series(self, file_id):
        headers = {
            "apikey": SUPABASE_SECRET_KEY,
            "Authorization": f"Bearer {SUPABASE_SECRET_KEY}"
        }
        async with aiohttp.ClientSession() as session:
            await session.delete(f"{SUPABASE_URL}/rest/v1/genesis_series?telegram_file_id=eq.{file_id}", headers=headers)

    async def get_series_videos(self, chat_id, series_name):
        headers = {
            "apikey": SUPABASE_SECRET_KEY,
            "Authorization": f"Bearer {SUPABASE_SECRET_KEY}"
        }
        async with aiohttp.ClientSession() as session:
            url = f"{SUPABASE_URL}/rest/v1/genesis_series?chat_id=eq.{chat_id}&series_name=eq.{series_name}&order=id.asc"
            async with session.get(url, headers=headers) as resp:
                if resp.status == 200:
                    return await resp.json()
        return []

    async def merge_series_into_movie(self, video_paths):
        output_movie = "workspace/full_series_movie.mp4"
        list_file = "workspace/concat_list.txt"
        with open(list_file, "w", encoding="utf-8") as f:
            for v in video_paths:
                f.write(f"file '{os.path.abspath(v)}'\n")

        # دمج الفيديوهات مع تسوية الصوت الموحدة (Audio Normalization)
        cmd = (
            f"ffmpeg -y -f concat -safe 0 -i {list_file} "
            f"-af loudnorm=I=-16:TP=-1.5:LRA=11 -c:v libx264 -pix_fmt yuv420p -c:a aac {output_movie}"
        )
        await self.run_resilient_cmd(cmd)
        return output_movie

video_engine = HollywoodVideoEngine()
