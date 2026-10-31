import os
import asyncio
import subprocess
import urllib.parse
import random
import aiohttp
import edge_tts
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageOps
import config

HF_TOKEN = getattr(config, "HF_TOKEN", "")
PIXABAY_API_KEY = getattr(config, "PIXABAY_API_KEY", "")
DEFAULT_LANGUAGES = {
    "ar": {"name": "العربية", "male_voice": "ar-SA-HamedNeural", "female_voice": "ar-EG-SalmaNeural", "kids_voice": "ar-AE-FatimaNeural", "rate": "-2%", "pitch": "-1Hz"},
    "ar_ye": {"name": "اليمنية", "male_voice": "ar-YE-SalehNeural", "female_voice": "ar-YE-MaryamNeural", "kids_voice": "ar-YE-MaryamNeural", "rate": "+0%", "pitch": "+0Hz"},
    "en": {"name": "English", "male_voice": "en-US-AndrewMultilingualNeural", "female_voice": "en-US-AvaMultilingualNeural", "kids_voice": "en-US-AnaNeural", "rate": "+0%", "pitch": "+0Hz"}
}
SUPPORTED_LANGUAGES = getattr(config, "SUPPORTED_LANGUAGES", DEFAULT_LANGUAGES)


class StudioMediaEngine:
    def __init__(self):
        self.work_dir = "workspace"
        os.makedirs(self.work_dir, exist_ok=True)
        self.upgrade_active = True
        self.face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
        self.profile_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_profileface.xml")

    def _run_ffmpeg(self, cmd):
        try:
            res = subprocess.run(
                cmd,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=180
            )
            return res.returncode == 0, res.stderr
        except Exception as e:
            return False, str(e)

    def _get_audio_duration(self, audio_path):
        if not os.path.exists(audio_path) or os.path.getsize(audio_path) < 100:
            return 5.0
        cmd = f'ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "{audio_path}"'
        try:
            out = subprocess.check_output(cmd, shell=True, text=True).strip()
            return max(3.0, float(out))
        except Exception:
            return 5.0

    # ==========================================================
    # 1. توليد الصوت البشري الفائق + موسيقى خلفية سينمائية
    # ==========================================================
    async def generate_human_voice(self, text, output_path, voice_id="ar-SA-HamedNeural", rate="-2%", pitch="-1Hz", mood="epic"):
        raw_voice = output_path.replace(".mp3", "_raw.mp3")
        clean_text = str(text).replace('"', '').replace("'", "").strip()
        if not clean_text:
            clean_text = "..."

        success = False
        for attempt in range(2):
            try:
                if attempt == 0:
                    comm = edge_tts.Communicate(clean_text, voice_id, rate=rate, pitch=pitch)
                else:
                    comm = edge_tts.Communicate(clean_text, voice_id)
                await comm.save(raw_voice)
                if os.path.exists(raw_voice) and os.path.getsize(raw_voice) > 200:
                    success = True
                    break
            except Exception:
                await asyncio.sleep(1)

        if not success:
            try:
                from gtts import gTTS
                lang_short = voice_id.split("-")[0] if "-" in voice_id else "ar"
                tts = gTTS(text=clean_text, lang=lang_short)
                tts.save(raw_voice)
                success = True
            except Exception:
                self._run_ffmpeg(f'ffmpeg -y -f lavfi -i anullsrc=r=44100:cl=stereo -t 4 "{raw_voice}"')

        dur = self._get_audio_duration(raw_voice)

        if mood == "upbeat":
            synth_expr = "0.04*sin(2*PI*220*t)+0.03*sin(2*PI*330*t)+0.02*sin(2*PI*440*t)"
        elif mood == "dramatic":
            synth_expr = "0.04*sin(2*PI*110*t)+0.03*sin(2*PI*165*t)"
        else:
            synth_expr = "0.05*sin(2*PI*98*t)+0.03*sin(2*PI*147*t)+0.02*sin(2*PI*196*t)"

        mix_cmd = (
            f'ffmpeg -y -i "{raw_voice}" -f lavfi -i "aevalsrc={synth_expr}:s=44100:d={dur}" '
            f'-filter_complex "[0:a]volume=1.35[v];[1:a]afade=t=in:st=0:d=0.5,afade=t=out:st={max(0.5, dur-0.8)}:d=0.8[bg];'
            f'[v][bg]amix=inputs=2:duration=first:dropout_transition=1" -c:a libmp3lame -q:a 2 "{output_path}"'
        )
        ok, _ = self._run_ffmpeg(mix_cmd)
        if not ok or not os.path.exists(output_path):
            if os.path.exists(raw_voice):
                os.replace(raw_voice, output_path)
        return dur

    # ==========================================================
    # 2. محرك الصور رباعي الطبقات (مانع الشاشة السوداء 100%)
    # ==========================================================
    async def fetch_real_scene_image(self, visual_prompt, search_query, output_jpg, aspect="16:9", mode="hybrid", scene_num=1):
        target_w, target_h = (720, 1280) if aspect == "9:16" else (1280, 720)
        seed = random.randint(1000, 999999)
        headers_browser = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=25)) as session:
            if HF_TOKEN and HF_TOKEN.startswith("hf_"):
                hf_models = [
                    "black-forest-labs/FLUX.1-schnell",
                    "stabilityai/stable-diffusion-xl-base-1.0"
                ]
                for hf_model in hf_models:
                    try:
                        hf_url = f"https://api-inference.huggingface.co/models/{hf_model}"
                        hf_headers = {"Authorization": f"Bearer {HF_TOKEN}"}
                        async with session.post(hf_url, headers=hf_headers, json={"inputs": f"{visual_prompt}, seed {seed}"}) as resp:
                            if resp.status == 200:
                                img_bytes = await resp.read()
                                if len(img_bytes) > 5000:
                                    with open(output_jpg, "wb") as f:
                                        f.write(img_bytes)
                                    if self._normalize_image(output_jpg, target_w, target_h, mode):
                                        return True
                    except Exception:
                        continue

            for model_name in ["flux", "turbo"]:
                try:
                    encoded_p = urllib.parse.quote(visual_prompt[:380])
                    pol_url = f"https://image.pollinations.ai/prompt/{encoded_p}?width={target_w}&height={target_h}&seed={seed}&model={model_name}&nologo=true"
                    async with session.get(pol_url, headers=headers_browser, allow_redirects=True) as resp:
                        if resp.status == 200:
                            img_bytes = await resp.read()
                            if len(img_bytes) > 5000:
                                with open(output_jpg, "wb") as f:
                                    f.write(img_bytes)
                                if self._normalize_image(output_jpg, target_w, target_h, mode):
                                    return True
                except Exception:
                    continue

            if PIXABAY_API_KEY:
                for q in [search_query, "cinematic nature", "landscape"]:
                    try:
                        enc_q = urllib.parse.quote(str(q))
                        px_url = f"https://pixabay.com/api/?key={PIXABAY_API_KEY}&q={enc_q}&image_type=photo&per_page=10"
                        async with session.get(px_url, headers=headers_browser) as resp:
                            if resp.status == 200:
                                data = await resp.json()
                                hits = data.get("hits", [])
                                if hits:
                                    chosen = hits[(scene_num - 1) % len(hits)]
                                    img_url = chosen.get("largeImageURL") or chosen.get("webformatURL")
                                    if img_url:
                                        async with session.get(img_url, headers=headers_browser) as img_resp:
                                            if img_resp.status == 200:
                                                with open(output_jpg, "wb") as f:
                                                    f.write(await img_resp.read())
                                                if self._normalize_image(output_jpg, target_w, target_h, mode):
                                                    return True
                    except Exception:
                        continue

        self._create_stylized_artwork(output_jpg, target_w, target_h, mode, scene_num)
        return True

    def _normalize_image(self, img_path, target_w, target_h, mode="hybrid"):
        try:
            with Image.open(img_path) as im:
                im = im.convert("RGB")
                im = ImageOps.fit(im, (target_w, target_h), method=Image.Resampling.LANCZOS)

                if mode == "kids":
                    im = ImageEnhance.Color(im).enhance(1.45)
                    im = ImageEnhance.Brightness(im).enhance(1.08)
                elif mode == "cinematic":
                    im = ImageEnhance.Contrast(im).enhance(1.25)
                    im = ImageEnhance.Color(im).enhance(0.88)
                elif mode == "ads":
                    im = ImageEnhance.Contrast(im).enhance(1.2)
                    im = ImageEnhance.Color(im).enhance(1.3)
                    im = ImageEnhance.Sharpness(im).enhance(1.4)
                elif mode == "news":
                    draw = ImageDraw.Draw(im)
                    bar_h = int(target_h * 0.12)
                    draw.rectangle([0, target_h - bar_h, target_w, target_h], fill=(15, 25, 45))
                    draw.rectangle([0, target_h - bar_h, int(target_w * 0.22), target_h], fill=(200, 20, 20))

                im.save(img_path, "JPEG", quality=95)
            return True
        except Exception:
            return False

    def _create_stylized_artwork(self, img_path, w, h, mode, scene_num):
        palettes = {
            "kids": [(45, 140, 255), (255, 190, 40)],
            "cinematic": [(15, 22, 38), (95, 55, 30)],
            "ads": [(80, 15, 95), (240, 60, 90)],
            "news": [(10, 35, 65), (30, 90, 140)]
        }
        c1, c2 = palettes.get(mode, [(20, 30, 50), (70, 100, 140)])
        img = Image.new("RGB", (w, h), c1)
        draw = ImageDraw.Draw(img)
        for y in range(h):
            ratio = y / float(h)
            r = int(c1[0] * (1 - ratio) + c2[0] * ratio)
            g = int(c1[1] * (1 - ratio) + c2[1] * ratio)
            b = int(c1[2] * (1 - ratio) + c2[2] * ratio)
            draw.line([(0, y), (w, y)], fill=(r, g, b))
        img.save(img_path, "JPEG", quality=92)

    def render_animated_scene(self, image_path, audio_path, output_mp4, duration, scene_idx=1, aspect="16:9"):
        w, h = (720, 1280) if aspect == "9:16" else (1280, 720)
        frames = max(75, int(duration * 25) + 10)

        if scene_idx % 3 == 1:
            z_expr = "min(zoom+0.0016,1.28)"
            x_expr = "iw/2-(iw/zoom/2)"
            y_expr = "ih/2-(ih/zoom/2)"
        elif scene_idx % 3 == 2:
            z_expr = "if(eq(on,1),1.25,max(1.0,zoom-0.0015))"
            x_expr = "iw/2-(iw/zoom/2)"
            y_expr = "ih/2-(ih/zoom/2)"
        else:
            z_expr = "1.18"
            x_expr = "if(eq(on,1),0,min(iw-iw/zoom,x+1.2))"
            y_expr = "ih/2-(ih/zoom/2)"

        vf = (
            f"scale={int(w*1.3)}:{int(h*1.3)},"
            f"zoompan=z='{z_expr}':x='{x_expr}':y='{y_expr}':d={frames}:s={w}x{h}:fps=25,"
            f"fade=t=in:st=0:d=0.35,fade=t=out:st={max(0.4, duration-0.35)}:d=0.35,"
            f"format=yuv420p"
        )

        cmd = (
            f'ffmpeg -y -i "{image_path}" -i "{audio_path}" '
            f'-vf "{vf}" -c:v libx264 -preset veryfast -crf 21 '
            f'-c:a aac -b:a 192k -t {duration} -shortest "{output_mp4}"'
        )
        ok, _ = self._run_ffmpeg(cmd)
        if not ok or not os.path.exists(output_mp4) or os.path.getsize(output_mp4) < 1000:
            fallback_cmd = (
                f'ffmpeg -y -loop 1 -i "{image_path}" -i "{audio_path}" '
                f'-vf "scale={w}:{h},format=yuv420p" -c:v libx264 -preset ultrafast '
                f'-c:a aac -t {duration} -shortest "{output_mp4}"'
            )
            self._run_ffmpeg(fallback_cmd)
        return os.path.exists(output_mp4)

    # ==========================================================
    # 3. قاطع العلامات المائية وشاشة نهاية إنستجرام الذكي
    # ==========================================================
    def clean_video_watermarks_and_outro(self, input_video, cleaned_output):
        cap = cv2.VideoCapture(input_video)
        if not cap.isOpened():
            return input_video

        fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        duration = total_frames / fps if fps > 0 else 10.0

        # 1. فحص الإطارات لاكتشاف الأشرطة السوداء التي تحمل العلامة المائية (@MOSTAFA_HAZEM911 وغيرها)
        sample_indices = [int(total_frames * r) for r in [0.15, 0.3, 0.45, 0.6] if int(total_frames * r) < total_frames]
        y_tops, y_bottoms = [], []

        for idx in sample_indices:
            cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
            ret, frame = cap.read()
            if not ret or frame is None:
                continue
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            row_means = np.mean(gray, axis=1)
            # الصفوف المضيئة الفعّالة (تجاهل نص العلامة المائية الضعيف داخل الشريط الأسود)
            active_rows = np.where(row_means > 22)[0]
            if len(active_rows) > 20:
                y_tops.append(int(active_rows[0]))
                y_bottoms.append(int(active_rows[-1]))

        # 2. فحص نهاية الفيديو لقص شاشة إنستجرام السوداء في آخر الثواني
        cut_duration = duration
        if duration > 7.0:
            mid_frame_idx = int(total_frames * 0.4)
            cap.set(cv2.CAP_PROP_POS_FRAMES, mid_frame_idx)
            ret_m, frame_m = cap.read()
            mid_brightness = np.mean(cv2.cvtColor(frame_m, cv2.COLOR_BGR2GRAY)) if ret_m and frame_m is not None else 80.0

            # فحص آخر 4.5 ثانية لاكتشاف لحظة تعتيم الشاشة وظهور شعار إنستجرام
            start_check_sec = max(3.0, duration - 4.5)
            for sec in np.arange(start_check_sec, duration - 0.3, 0.25):
                f_idx = int(sec * fps)
                cap.set(cv2.CAP_PROP_POS_FRAMES, f_idx)
                ret_e, frame_e = cap.read()
                if ret_e and frame_e is not None:
                    gray_e = cv2.cvtColor(frame_e, cv2.COLOR_BGR2GRAY)
                    if np.mean(gray_e) < mid_brightness * 0.48:
                        cut_duration = max(3.0, sec - 0.15)
                        break

        cap.release()

        # تحديد منطقة القص النظيفة لإزالة الأشرطة السوداء والعلامات المائية
        if y_tops and y_bottoms:
            y1 = int(np.median(y_tops))
            y2 = int(np.median(y_bottoms))
            active_h = y2 - y1
            if active_h > height * 0.25 and active_h < height * 0.88:
                # قص الشريط الأسود العلوي والسفلي بالكامل حيث توجد العلامة المائية
                crop_y = max(0, y1 + 4)
                crop_h = max(200, min(height - crop_y, active_h - 8))
                crop_h = crop_h - (crop_h % 2)
                crop_w = width - (width % 2)
                vf_clean = f"crop={crop_w}:{crop_h}:0:{crop_y},scale=1280:720,format=yuv420p"
            else:
                # إذا كان الفيديو ملء الشاشة، نقص الحواف بنسبة 6% لإزالة أي شعارات في الزوايا
                cw = int(width * 0.92) - (int(width * 0.92) % 2)
                ch = int(height * 0.88) - (int(height * 0.88) % 2)
                cx = (width - cw) // 2
                cy = (height - ch) // 2
                vf_clean = f"crop={cw}:{ch}:{cx}:{cy},format=yuv420p"
        else:
            vf_clean = "format=yuv420p"

        cmd = (
            f'ffmpeg -y -i "{input_video}" -t {cut_duration:.2f} '
            f'-vf "{vf_clean}" -c:v libx264 -preset veryfast -crf 20 -c:a aac -b:a 192k "{cleaned_output}"'
        )
        ok, _ = self._run_ffmpeg(cmd)
        return cleaned_output if (ok and os.path.exists(cleaned_output)) else input_video

    # ==========================================================
    # 4. محرك استنساخ الوجه الحقيقي (Seamless Face Swap + Color Match)
    # ==========================================================
    def _extract_source_face(self, face_path):
        img = cv2.imread(face_path)
        if img is None:
            return None
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        faces = self.face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=4, minSize=(40, 40))
        if len(faces) > 0:
            faces = sorted(faces, key=lambda b: b[2] * b[3], reverse=True)
            x, y, w, h = faces[0]
            # أخذ منطقة الملامح الداخلية للوجه (العينين والأنف والفم) لدمج طبيعي
            pad_x = int(w * 0.08)
            pad_y = int(h * 0.08)
            return img[max(0, y + pad_y):min(img.shape[0], y + h - pad_y), max(0, x + pad_x):min(img.shape[1], x + w - pad_x)]
        # إذا كانت الصورة قريبة جداً للوجه أصلاً
        h, w = img.shape[:2]
        return img[int(h * 0.12):int(h * 0.88), int(w * 0.12):int(w * 0.88)]

    def _match_skin_tone(self, src_face, dst_face_roi):
        try:
            src_lab = cv2.cvtColor(src_face, cv2.COLOR_BGR2LAB).astype(np.float32)
            dst_lab = cv2.cvtColor(dst_face_roi, cv2.COLOR_BGR2LAB).astype(np.float32)

            src_mean, src_std = cv2.meanStdDev(src_lab)
            dst_mean, dst_std = cv2.meanStdDev(dst_lab)

            for c in range(3):
                s_std = max(src_std[c][0], 1.0)
                d_std = max(dst_std[c][0], 1.0)
                src_lab[:, :, c] = (src_lab[:, :, c] - src_mean[c][0]) * (d_std / s_std) * 0.75 + dst_mean[c][0] * 0.75 + src_mean[c][0] * 0.25

            src_lab = np.clip(src_lab, 0, 255).astype(np.uint8)
            return cv2.cvtColor(src_lab, cv2.COLOR_LAB2BGR)
        except Exception:
            return src_face

    def _swap_face_on_frame(self, frame, src_face_crop, last_box=None):
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = self.face_cascade.detectMultiScale(gray, scaleFactor=1.12, minNeighbors=4, minSize=(36, 36))
        if len(faces) == 0:
            faces = self.profile_cascade.detectMultiScale(gray, scaleFactor=1.12, minNeighbors=4, minSize=(36, 36))

        box = None
        if len(faces) > 0:
            faces = sorted(faces, key=lambda b: b[2] * b[3], reverse=True)
            fx, fy, fw, fh = [int(v) for v in faces[0]]
            if last_box is not None:
                # تنعيم حركة تتبع الوجه بين الإطارات لمنع أي اهتزاز
                lx, ly, lw, lh, _ = last_box
                fx = int(0.65 * fx + 0.35 * lx)
                fy = int(0.65 * fy + 0.35 * ly)
                fw = int(0.65 * fw + 0.35 * lw)
                fh = int(0.65 * fh + 0.35 * lh)
            box = (fx, fy, fw, fh, 0)
        elif last_box is not None and last_box[4] < 8:
            # الحفاظ على الوجه لعدة إطارات إذا التفت الممثل سريعاً
            box = (last_box[0], last_box[1], last_box[2], last_box[3], last_box[4] + 1)

        if box is None:
            return frame, None

        x, y, w, h, missed = box
        fh_img, fw_img = frame.shape[:2]
        x = max(2, min(x, fw_img - w - 2))
        y = max(2, min(y, fh_img - h - 2))
        if w < 20 or h < 20 or x + w >= fw_img or y + h >= fh_img:
            return frame, box

        target_roi = frame[y:y + h, x:x + w]
        resized_src = cv2.resize(src_face_crop, (w, h), interpolation=cv2.INTER_LANCZOS4)
        color_matched_src = self._match_skin_tone(resized_src, target_roi)

        # قناع بيضاوي متدرج الحواف لدمج ملامح الوجه بدون حواف حادة
        mask = np.zeros((h, w), dtype=np.float32)
        cv2.ellipse(mask, (w // 2, h // 2), (int(w * 0.43), int(h * 0.46)), 0, 0, 360, 1.0, -1)
        blur_k = max(5, (min(w, h) // 5) | 1)
        mask = cv2.GaussianBlur(mask, (blur_k, blur_k), 0)

        try:
            mask_u8 = np.clip(mask * 255, 0, 255).astype(np.uint8)
            center_pt = (x + w // 2, y + h // 2)
            frame = cv2.seamlessClone(color_matched_src, frame, mask_u8, center_pt, cv2.NORMAL_CLONE)
        except Exception:
            mask_3d = mask[:, :, np.newaxis]
            blended = (color_matched_src.astype(np.float32) * mask_3d + target_roi.astype(np.float32) * (1.0 - mask_3d)).astype(np.uint8)
            frame[y:y + h, x:x + w] = blended

        return frame, box

    async def process_face_cloning_video(self, face_path, video_path, custom_caption=""):
        session_id = random.randint(10000, 99999)
        cleaned_vid = os.path.join(self.work_dir, f"cleaned_{session_id}.mp4")
        swapped_silent = os.path.join(self.work_dir, f"swapped_silent_{session_id}.mp4")
        output_cloned = os.path.join(self.work_dir, f"cloned_master_{session_id}.mp4")

        # الخطوة 1: إزالة العلامة المائية (@MOSTAFA_HAZEM911) والأشرطة السوداء وشاشة نهاية إنستجرام أولاً!
        working_video = await asyncio.to_thread(self.clean_video_watermarks_and_outro, video_path, cleaned_vid)

        # الخطوة 2: استخراج ملامح وجهك وتطبيق الاستنساخ الحقيقي إطاراً بإطار فوق وجه الممثل
        src_face_crop = await asyncio.to_thread(self._extract_source_face, face_path)
        if src_face_crop is not None:
            def _process_frames():
                cap = cv2.VideoCapture(working_video)
                if not cap.isOpened():
                    return False
                fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
                w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                fourcc = cv2.VideoWriter_fourcc(*"mp4v")
                writer = cv2.VideoWriter(swapped_silent, fourcc, fps, (w, h))
                last_box = None
                while True:
                    ret, frame = cap.read()
                    if not ret or frame is None:
                        break
                    swapped_frame, last_box = self._swap_face_on_frame(frame, src_face_crop, last_box)
                    writer.write(swapped_frame)
                cap.release()
                writer.release()
                return os.path.exists(swapped_silent)

            ok_swap = await asyncio.to_thread(_process_frames)
            video_source = swapped_silent if ok_swap else working_video
        else:
            video_source = working_video

        # الخطوة 3: دمج الصوت الأصلي (أو الصوت البشري المولد) وإخراج الفيديو النهائي النظيف
        if custom_caption and len(custom_caption.strip()) > 2:
            aud_p = os.path.join(self.work_dir, f"clone_aud_{session_id}.mp3")
            await self.generate_human_voice(custom_caption, aud_p, mood="dramatic")
            cmd = (
                f'ffmpeg -y -i "{video_source}" -i "{aud_p}" '
                f'-map 0:v:0 -map 1:a:0 -c:v libx264 -preset veryfast -crf 20 -c:a aac -shortest "{output_cloned}"'
            )
        else:
            cmd = (
                f'ffmpeg -y -i "{video_source}" -i "{working_video}" '
                f'-map 0:v:0 -map 1:a:0? -c:v libx264 -preset veryfast -crf 20 -c:a aac -shortest "{output_cloned}"'
            )

        ok, _ = self._run_ffmpeg(cmd)
        return output_cloned if (ok and os.path.exists(output_cloned)) else working_video

    def _apply_smart_face_composite(self, face_img_path, target_scene_path):
        try:
            src_crop = self._extract_source_face(face_img_path)
            frame = cv2.imread(target_scene_path)
            if src_crop is not None and frame is not None:
                swapped, _ = self._swap_face_on_frame(frame, src_crop)
                cv2.imwrite(target_scene_path, swapped)
        except Exception:
            pass

    async def produce_full_video(self, blueprint, status_callback=None, custom_face_path=None):
        scenes = blueprint.get("scenes", [])
        mode = blueprint.get("mode", "hybrid")
        aspect = blueprint.get("aspect", "16:9")
        mood = blueprint.get("bg_music_mood", "epic")
        session_id = random.randint(10000, 99999)
        scene_videos = []

        for idx, sc in enumerate(scenes):
            sc_num = idx + 1
            if status_callback:
                try:
                    await status_callback(f"🎥 **جاري تصوير ومونتاج المشهد ({sc_num}/{len(scenes)})**\n• الوضع: `{mode}` | الصوت: `{sc.get('voice_id')}`...")
                except Exception:
                    pass

            img_path = os.path.join(self.work_dir, f"img_{session_id}_{sc_num}.jpg")
            aud_path = os.path.join(self.work_dir, f"aud_{session_id}_{sc_num}.mp3")
            vid_path = os.path.join(self.work_dir, f"vid_{session_id}_{sc_num}.mp4")

            dur = await self.generate_human_voice(
                text=sc.get("narration_ar", ""),
                output_path=aud_path,
                voice_id=sc.get("voice_id", "ar-SA-HamedNeural"),
                rate=sc.get("voice_rate", "-2%"),
                pitch=sc.get("voice_pitch", "-1Hz"),
                mood=mood
            )

            await self.fetch_real_scene_image(
                visual_prompt=sc.get("visual_prompt_en", ""),
                search_query=sc.get("search_query_en", "cinematic"),
                output_jpg=img_path,
                aspect=aspect,
                mode=mode,
                scene_num=sc_num
            )

            if custom_face_path and os.path.exists(custom_face_path):
                self._apply_smart_face_composite(custom_face_path, img_path)

            if self.render_animated_scene(img_path, aud_path, vid_path, dur, scene_idx=sc_num, aspect=aspect):
                scene_videos.append(vid_path)

        if not scene_videos:
            return None

        final_output = os.path.join(self.work_dir, f"genesis_master_{session_id}.mp4")
        concat_list = os.path.join(self.work_dir, f"list_{session_id}.txt")
        with open(concat_list, "w", encoding="utf-8") as f:
            for v in scene_videos:
                f.write(f"file '{os.path.abspath(v)}'\n")

        concat_cmd = f'ffmpeg -y -f concat -safe 0 -i "{concat_list}" -c copy "{final_output}"'
        ok, _ = self._run_ffmpeg(concat_cmd)
        if not ok or not os.path.exists(final_output):
            return scene_videos[0]
        return final_output

    async def produce_personal_story_reel(self, photo_paths, caption_text="", custom_audio_path=None, lang_code="ar"):
        session_id = random.randint(10000, 99999)
        w, h = 720, 1280
        prepared_imgs = []

        for idx, p_path in enumerate(photo_paths):
            if not os.path.exists(p_path):
                continue
            out_img = os.path.join(self.work_dir, f"story_img_{session_id}_{idx}.jpg")
            try:
                with Image.open(p_path) as im:
                    im = im.convert("RGB")
                    bg = ImageOps.fit(im, (w, h), method=Image.Resampling.LANCZOS).filter(ImageFilter.GaussianBlur(28))
                    bg = ImageEnhance.Brightness(bg).enhance(0.65)

                    fg = im.copy()
                    fg.thumbnail((w, int(h * 0.88)), Image.Resampling.LANCZOS)
                    fg = ImageEnhance.Sharpness(fg).enhance(1.2)
                    fg = ImageEnhance.Contrast(fg).enhance(1.08)

                    paste_x = (w - fg.width) // 2
                    paste_y = (h - fg.height) // 2
                    bg.paste(fg, (paste_x, paste_y))
                    bg.save(out_img, "JPEG", quality=96)
                    prepared_imgs.append(out_img)
            except Exception:
                continue

        if not prepared_imgs:
            return None

        story_audio = os.path.join(self.work_dir, f"story_audio_{session_id}.mp3")
        if custom_audio_path and os.path.exists(custom_audio_path):
            story_audio = custom_audio_path
            total_dur = self._get_audio_duration(story_audio)
        elif caption_text and len(caption_text.strip()) > 2:
            lang_info = SUPPORTED_LANGUAGES.get(lang_code, DEFAULT_LANGUAGES["ar"])
            total_dur = await self.generate_human_voice(
                caption_text, story_audio, voice_id=lang_info["male_voice"], mood="upbeat"
            )
            total_dur = max(total_dur, len(prepared_imgs) * 3.2)
        else:
            total_dur = max(6.0, len(prepared_imgs) * 3.5)
            synth = "0.06*sin(2*PI*220*t)+0.04*sin(2*PI*330*t)+0.03*sin(2*PI*440*t)"
            self._run_ffmpeg(f'ffmpeg -y -f lavfi -i "aevalsrc={synth}:s=44100:d={total_dur}" -c:a libmp3lame "{story_audio}"')

        per_slide_dur = max(2.8, total_dur / len(prepared_imgs))
        clip_paths = []
        for idx, img_p in enumerate(prepared_imgs):
            clip_p = os.path.join(self.work_dir, f"story_clip_{session_id}_{idx}.mp4")
            frames = int(per_slide_dur * 25)
            z_dir = "min(zoom+0.0018,1.22)" if idx % 2 == 0 else "if(eq(on,1),1.22,max(1.0,zoom-0.0018))"
            vf = (
                f"scale=936:1664,"
                f"zoompan=z='{z_dir}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={frames}:s={w}x{h}:fps=25,"
                f"fade=t=in:st=0:d=0.25,fade=t=out:st={max(0.3, per_slide_dur-0.25)}:d=0.25,format=yuv420p"
            )
            cmd = f'ffmpeg -y -i "{img_p}" -vf "{vf}" -t {per_slide_dur} -c:v libx264 -preset veryfast -crf 20 "{clip_p}"'
            if self._run_ffmpeg(cmd)[0] and os.path.exists(clip_p):
                clip_paths.append(clip_p)

        if not clip_paths:
            return None

        merged_silent = os.path.join(self.work_dir, f"story_silent_{session_id}.mp4")
        list_txt = os.path.join(self.work_dir, f"story_list_{session_id}.txt")
        with open(list_txt, "w", encoding="utf-8") as f:
            for c in clip_paths:
                f.write(f"file '{os.path.abspath(c)}'\n")

        self._run_ffmpeg(f'ffmpeg -y -f concat -safe 0 -i "{list_txt}" -c copy "{merged_silent}"')
        final_story = os.path.join(self.work_dir, f"story_final_{session_id}.mp4")
        mux_cmd = f'ffmpeg -y -i "{merged_silent}" -i "{story_audio}" -c:v copy -c:a aac -b:a 192k -shortest "{final_story}"'
        self._run_ffmpeg(mux_cmd)
        return final_story if os.path.exists(final_story) else merged_silent


media_engine = StudioMediaEngine()
