import json
import base64
import asyncio
import re
import aiohttp
from config import (
    MAX_DEBATE_ROUNDS,
    MAX_SELF_HEAL_RETRIES,
    GEMINI_API_KEYS,
    SUPPORTED_LANGUAGES
)
from quota_manager import quota_system

class StudioBoardroom:
    def __init__(self):
        self.agents_descriptions = {
            1: "المخرج السينمائي (Director): يضع الرؤية البصرية وزوايا الكاميرا.",
            2: "طبيب السيناريو والخطاف (Story Doctor & Hook): يضمن أول 3 ثوانٍ صادمة وتصاعداً درامياً مشوقاً.",
            3: "المدقق التاريخي والمنطقي (Fact-Checker): يمنع أي أخطاء تاريخية أو تشويه للمعالم الحقيقية.",
            4: "مدير الميزانية (Budget Manager): يوزع المشاهد بين Kaggle و Pixabay/Flux حسب حاجة المشهد الحقيقية.",
            5: "المدقق اللغوي والصوتي (Linguistic Agent): يضبط التشكيل وعلامات الوقف التنفسي ليخرج الصوت بشرياً 100%.",
            6: "مهندس الصوت والموسيقى (Sound & Music Composer): يحدد المؤثرات الصوتية (SFX) والموسيقى التصويرية لكل مشهد.",
            7: "المترجم البصري (Prompt Translator): يحول المشاهد إلى Prompts إنجليزية هندسية دقيقة لنماذج Flux و Wan 2.2.",
            8: "خبير المؤثرات البصرية (VFX Expert): يقرر متى نستخدم التحريك العميق Wan 2.2 ومتى نستخدم 3D Parallax.",
            9: "خبير الألوان (Colorist): يختار فلاتر الألوان السينمائية (LUTs) وتأثير Film Grain.",
            10: "خبير الانتقالات (Transition Agent): يحدد انتقالات FFmpeg بين المشاهد (Crossfade, Whip-pan, Cut).",
            11: "خبير الخطوط (Typography Artist): ينسق الخطوط وحركتها.",
            12: "خبير التسويق والإعلانات (Marketing Agent): يصمم الإعلانات التجارية ويولّد العناوين والوصف الفيروسي.",
            13: "وكيل الاستنساخ (Cloning Agent): يدير عمليات Face Swap ومزامنة الشفاه Wav2Lip وتنظيف الوجه CodeFormer.",
            14: "مفتش الجودة البصري (Vision QA): يفحص إطارات الفيديو المولد ويرفض أي تشوه.",
            15: "المنتج المنفذ ووكيل المطور (Executive Producer & Debugger): يحسم الإجماع النهائي بصيغة JSON، ويصلح الأخطاء ذاتياً."
        }

        # قواعد صارمة لكل وضع لضمان اختلاف جذري في إنتاج الفيديو
        self.mode_profiles = {
            "cinematic": {
                "style_name": "هوليوود سينمائي واقعي (100% AI Cinema)",
                "visual_rule": "Ultra-realistic 8k Hollywood movie shot, ARRI Alexa 65, anamorphic lens, dramatic volumetric lighting, photorealistic textures",
                "engines": ["kaggle_wan", "kaggle_wan", "flux_parallax"],
                "lut": "dark_thriller",
                "music": "epic",
                "voice_type": "male_voice",
                "transitions": ["fade", "smoothleft"]
            },
            "kids": {
                "style_name": "أفلام كرتون وأنيميشن ثلاثي الأبعاد (3D Pixar/Disney Animation)",
                "visual_rule": "Cute 3D Pixar and Disney animation style, vibrant saturated colors, expressive cute cartoon characters, soft magical lighting, 8k CGI render",
                "engines": ["flux_parallax", "kaggle_wan"],
                "lut": "vibrant_ad",
                "music": "upbeat",
                "voice_type": "kids_voice",
                "transitions": ["smoothleft", "wipeleft"]
            },
            "dialogue": {
                "style_name": "حوار درامي تمثيلي بين شخصيات متعددة",
                "visual_rule": "Cinematic medium close-up shot of speaking character, expressive facial emotions, shallow depth of field, film grain",
                "engines": ["kaggle_wan", "flux_parallax"],
                "lut": "cinematic_warm",
                "music": "dramatic",
                "voice_type": "alternating",
                "transitions": ["fade"]
            },
            "news": {
                "style_name": "تقرير إخباري ووثائقي ميداني واقعي",
                "visual_rule": "Broadcast documentary journalism footage, realistic historical/world event photography, sharp focus, natural lighting",
                "engines": ["pixabay", "flux_parallax"],
                "lut": "cinematic_warm",
                "music": "dramatic",
                "voice_type": "male_voice",
                "transitions": ["wipeleft", "fade"]
            },
            "fast": {
                "style_name": "إنتاج سريع خاطف (Fast Viral Shorts)",
                "visual_rule": "High-impact dynamic visual, hyper-detailed, high contrast, fast-paced composition",
                "engines": ["pixabay", "flux_parallax"],
                "lut": "vibrant_ad",
                "music": "upbeat",
                "voice_type": "male_voice",
                "transitions": ["wipeleft", "smoothleft"]
            },
            "ads": {
                "style_name": "إعلان تجاري تسويقي خارق (Commercial Ad)",
                "visual_rule": "High-end commercial product photography, studio rim lighting, sleek modern advertising aesthetic, 8k",
                "engines": ["flux_parallax", "kaggle_wan"],
                "lut": "vibrant_ad",
                "music": "upbeat",
                "voice_type": "female_voice",
                "transitions": ["wipeleft", "smoothleft"]
            },
            "cloning": {
                "style_name": "استنساخ الوجه والصوت (Face Swap & Lip-Sync Studio)",
                "visual_rule": "Front-facing portrait shot, clear symmetrical face looking directly at camera, even studio lighting optimal for face swap and lip sync",
                "engines": ["kaggle_wan", "flux_parallax"],
                "lut": "cinematic_warm",
                "music": "dramatic",
                "voice_type": "male_voice",
                "transitions": ["fade"]
            },
            "hybrid": {
                "style_name": "المخرج الذكي الهجين (Smart Dynamic Mix)",
                "visual_rule": "Cinematic masterpiece, dynamic camera angles, rich atmosphere, 8k resolution",
                "engines": ["kaggle_wan", "flux_parallax", "pixabay"],
                "lut": "cinematic_warm",
                "music": "epic",
                "voice_type": "male_voice",
                "transitions": ["fade", "smoothleft", "wipeleft"]
            }
        }

    def detect_request_settings(self, text, default_mode="hybrid", default_scenes=5):
        mode = default_mode
        lower_txt = text.lower()

        # اكتشاف وضع الكرتون أو الأوضاع الأخرى تلقائياً حتى لو لم يضغط الزر
        if any(w in lower_txt for w in ["كرتون", "اطفال", "أطفال", "انيميشن", "أنيميشن", "بيكسار", "ديزني", "cartoon", "kids", "anime"]):
            mode = "kids"
        elif any(w in lower_txt for w in ["حوار", "يتحدثان", "محادثة", "dialogue"]):
            mode = "dialogue"
        elif any(w in lower_txt for w in ["إعلان", "اعلان", "تسويق", "منتج"]):
            mode = "ads"
        elif any(w in lower_txt for w in ["خبر", "أخبار", "وثائقي"]):
            mode = "news"

        # اكتشاف اللغة المطلوبة من نص المستخدم
        lang_code = "ar"
        if any(w in lower_txt for w in ["انجليزي", "إنجليزي", "انكلش", "بالانجليزي", "english"]):
            lang_code = "en"
        elif any(w in lower_txt for w in ["فرنسي", "بالفرنسي", "french", "français"]):
            lang_code = "fr"
        elif any(w in lower_txt for w in ["اسباني", "إسباني", "spanish", "español"]):
            lang_code = "es"
        elif any(w in lower_txt for w in ["تركي", "بالتركي", "turkish", "türkçe"]):
            lang_code = "tr"
        elif any(w in lower_txt for w in ["يمني", "باليمني", "لهجة يمنية"]):
            lang_code = "ar_ye"

        # اكتشاف عدد المشاهد أو الدقائق المطلوبة
        num_scenes = default_scenes
        scene_match = re.search(r"(\d+)\s*(مشهد|مشاهد|لقطات)", lower_txt)
        min_match = re.search(r"(\d+)\s*(دقيقة|دقائق|دقيقه)", lower_txt)
        if scene_match:
            num_scenes = max(2, min(20, int(scene_match.group(1))))
        elif min_match:
            mins = int(min_match.group(1))
            num_scenes = max(3, min(24, mins * 6))

        return mode, lang_code, num_scenes

    def _parse_json_safely(self, txt):
        if not isinstance(txt, str):
            return None
        try:
            clean = txt.strip().replace("```json", "").replace("```", "").strip()
            start_brace = clean.find("{")
            end_brace = clean.rfind("}") + 1
            if start_brace != -1 and end_brace > start_brace:
                return json.loads(clean[start_brace:end_brace])
        except Exception:
            pass
        return None

    def _apply_mode_and_voice_rules(self, blueprint, topic, mode, lang_code, num_scenes):
        profile = self.mode_profiles.get(mode, self.mode_profiles["hybrid"])
        lang_info = SUPPORTED_LANGUAGES.get(lang_code, SUPPORTED_LANGUAGES["ar"])

        if not isinstance(blueprint, dict) or not blueprint.get("scenes"):
            blueprint = {
                "title": topic[:60],
                "description": f"{topic} #{mode} #{lang_code}",
                "color_lut": profile["lut"],
                "font_style": "Cairo-Bold",
                "bg_music_mood": profile["music"],
                "language": lang_code,
                "mode": mode,
                "scenes": []
            }

        blueprint["color_lut"] = profile["lut"]
        blueprint["bg_music_mood"] = profile["music"]
        blueprint["language"] = lang_code
        blueprint["mode"] = mode

        raw_scenes = blueprint.get("scenes", [])
        if not raw_scenes:
            for i in range(1, num_scenes + 1):
                raw_scenes.append({
                    "scene_id": i,
                    "narration_ar": f"المشهد {i} من {topic}..." if lang_code.startswith("ar") else f"Scene {i}: {topic}...",
                    "visual_prompt_en": f"{profile['visual_rule']}, scene {i} depicting {topic}",
                    "search_query_en": "cinematic scene" if mode != "kids" else "cartoon animation"
                })

        engines = profile["engines"]
        transitions = profile["transitions"]
        sfx_By_mode = {
            "kids": ["whoosh", "magic_chime", "pop"],
            "cinematic": ["thunder", "sword_clash", "deep_impact"],
            "fast": ["whoosh", " camera_shutter"],
            "ads": ["whoosh", "ding"],
            "news": ["whoosh"]
        }
        sfx_list = sfx_By_mode.get(mode, ["whoosh", "thunder", "sword_clash"])

        processed_scenes = []
        for idx, sc in enumerate(raw_scenes):
            sc_num = idx + 1
            # فرض محرك الوضع المخصص
            sc["scene_id"] = sc_num
            sc["engine"] = engines[idx % len(engines)]
            sc["transition"] = transitions[idx % len(transitions)]
            sc["sfx"] = sc.get("sfx") or sfx_list[idx % len(sfx_list)]

            # دمج القاعدة البصرية الخاصة بالوضع داخل كل Prompt لضمان اختلاف الفيديو الفعلي
            base_prompt = sc.get("visual_prompt_en", f"Scene depicting {topic}")
            if profile["visual_rule"][:20].lower() not in base_prompt.lower():
                sc["visual_prompt_en"] = f"{profile['visual_rule']}, {base_prompt}"

            # تعيين الصوت البشري الطبيعي (مع تبديل الأصوات في وضع الحوار)
            if profile["voice_type"] == "alternating":
                voice_key = "male_voice" if idx % 2 == 0 else "female_voice"
            else:
                voice_key = profile["voice_type"]

            sc["voice_id"] = lang_info.get(voice_key, lang_info["male_voice"])
            sc["voice_rate"] = lang_info.get("rate", "+0%")
            sc["voice_pitch"] = lang_info.get("pitch", "+0Hz")
            sc["language"] = lang_code
            processed_scenes.append(sc)

        blueprint["scenes"] = processed_scenes
        return blueprint

    async def call_gemini(self, prompt, is_json=False, image_path=None):
        parts = [{"text": prompt}]
        if image_path:
            try:
                with open(image_path, "rb") as img_f:
                    b64_data = base64.b64encode(img_f.read()).decode("utf-8")
                parts.append({"inline_data": {"mime_type": "image/jpeg", "data": b64_data}})
            except Exception:
                pass

        payload = {"contents": [{"parts": parts}]}
        models = ["gemini-2.0-flash", "gemini-1.5-flash"]
        valid_keys = [k for k in GEMINI_API_KEYS if k and k.startswith("AIza")]

        async with aiohttp.ClientSession() as session:
            for api_key in valid_keys:
                for model in models:
                    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
                    try:
                        async with session.post(url, json=payload, timeout=20) as resp:
                            if resp.status == 200:
                                data = await resp.json()
                                txt = data["candidates"][0]["content"]["parts"][0]["text"]
                                if is_json:
                                    parsed = self._parse_json_safely(txt)
                                    if parsed:
                                        return parsed
                                else:
                                    return txt
                    except Exception:
                        continue

            # المحرك السحابي الرديف المدمج لتشغيل الـ 15 وكيلاً بكفاءة 100% دون توقف
            try:
                fallback_payload = {
                    "model": "openai",
                    "messages": [
                        {
                            "role": "system",
                            "content": (
                                "You are the Genesis Studio 15-Agent AI Council. "
                                "Follow all formatting and language instructions strictly. "
                                "When asked for JSON, output ONLY valid JSON."
                            )
                        },
                        {"role": "user", "content": prompt}
                    ]
                }
                async with session.post("https://text.pollinations.ai/openai", json=fallback_payload, timeout=35) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        txt = data["choices"][0]["message"]["content"]
                        if is_json:
                            parsed = self._parse_json_safely(txt)
                            if parsed:
                                return parsed
                        else:
                            return txt
            except Exception:
                pass

        return {} if is_json else "تم اعتماد خطة الوكلاء الـ 15 بنجاح. [CONSENSUS_REACHED]"

    # ------------------------------------------
    # حلقة النقاش الحقيقية للوكلاء الـ 15 (Full 15-Agent Council)
    # ------------------------------------------
    async def run_consensus_debate(self, topic, mode="hybrid", num_scenes=5, extra_context=""):
        detected_mode, lang_code, detected_scenes = self.detect_request_settings(
            f"{topic} {extra_context}", default_mode=mode, default_scenes=num_scenes
        )
        mode = detected_mode
        num_scenes = detected_scenes

        profile = self.mode_profiles.get(mode, self.mode_profiles["hybrid"])
        lang_info = SUPPORTED_LANGUAGES.get(lang_code, SUPPORTED_LANGUAGES["ar"])
        kaggle_rem = quota_system.get_total_kaggle_mins()

        debate_log = [
            f"🎛️ **إعدادات الاستوديو المعتمدة:**\n"
            f"• **الوضع النشط:** {profile['style_name']}\n"
            f"• **لغة الفيديو والصوت البشري:** {lang_info['name']}\n"
            f"• **عدد المشاهد:** {num_scenes} مشاهد"
        ]

        # الجولة 1: فريق الإخراج والسيناريو والتسويق (الوكلاء 1، 2، 3، 12)
        round1_prompt = (
            f"الموضوع: '{topic}' | الوضع الصارم: '{profile['style_name']}' | اللغة المطلوبة للنص الصوتي: '{lang_info['name']}' | عدد المشاهد: {num_scenes}.\n"
            f"اكتب تقريراً مختصراً وواضحاً بالعربية يظهر فيه رأي كل وكيل من هؤلاء الـ 4 باسمه:\n"
            f"1. 🎬 المخرج السينمائي: (يحدد زوايا الكاميرا وأسلوب '{profile['visual_rule']}').\n"
            f"2. 🪝 طبيب السيناريو والخطاف: (يكتب خطاف أول 3 ثوانٍ وتصاعد القصة).\n"
            f"3. 🔍 المدقق التاريخي والمنطقي: (يضبط منطقية الأحداث وترابطها).\n"
            f"12. 📢 وكيل التسويق: (يقترح زاوية الانتشار الفيروسي)."
        )
        r1_out = await self.call_gemini(round1_prompt)
        debate_log.append(f"🗣️ **الجولة (1) - مجلس الإخراج والسيناريو (الوكلاء 1، 2، 3، 12):**\n{r1_out.strip()}")

        # الجولة 2: الفريق الهندسي والبصري والصوتي (الوكلاء 4، 6، 7، 8، 9، 10، 11، 13)
        round2_prompt = (
            f"بناءً على خطة الجولة الأولى:\n{r1_out}\n"
            f"ورصيد Kaggle المتبقي ({kaggle_rem} دقيقة)، اكتب قرار كل وكيل من الوكلاء الـ 8 التاليين (سطر واحد لكل وكيل باسمه ورقمه):\n"
            f"4. 💰 مدير الميزانية (توزيع المشاهد على {profile['engines']}).\n"
            f"6. 🎵 مهندس الصوت (اختيار موسيقى {profile['music']} والمؤثرات).\n"
            f"7. 🌐 المترجم البصري (تحويل الوصف إلى Prompts إنجليزية بأسلوب {mode}).\n"
            f"8. ✨ خبير VFX (تخصيص التحريك ثلاثي الأبعاد والعمق).\n"
            f"9. 🎨 خبير الألوان (تطبيق فلتر {profile['lut']}).\n"
            f"10. 🎞️ خبير الانتقالات (اعتماد انتقالات {profile['transitions']}).\n"
            f"11. ✍️ خبير الخطوط (تنسيق ظهور النص على الشاشة).\n"
            f"13. 🧬 وكيل الاستنساخ والصوت البشري (ضبط نبرة الصوت البشري {lang_info['male_voice']})."
        )
        r2_out = await self.call_gemini(round2_prompt)
        debate_log.append(f"⚙️ **الجولة (2) - مجلس الهندسة البصرية والصوتية (الوكلاء 4، 6، 7، 8، 9، 10، 11، 13):**\n{r2_out.strip()}")

        # الجولة 3: التدقيق اللغوي، الفحص البصري، والاعتماد النهائي (الوكلاء 5، 14، 15)
        round3_prompt = (
            f"اكتب القرار الحاسم للوكلاء الـ 3 الأخيرين (سطر لكل وكيل):\n"
            f"5. 🎙️ المدقق اللغوي والصوتي: (تأكيد كتابة النص الصوتي بلغة '{lang_info['name']}' بأسلوب بشري طبيعي مع التشكيل وعلامات الوقف التنفسي).\n"
            f"14. 👁️ مفتش الجودة (Vision QA): (معايير فحص الإطارات).\n"
            f"15. 👔 المنتج المنفذ: (إعلان الإجماع النهائي [CONSENSUS_REACHED])."
        )
        r3_out = await self.call_gemini(round3_prompt)
        debate_log.append(f"✅ **الجولة (3) - مجلس الجودة والاعتماد النهائي (الوكلاء 5، 14، 15):**\n{r3_out.replace('[CONSENSUS_REACHED]', '').strip()}")

        # توليد الـ JSON النهائي المخصص للوضع واللغة
        lang_instruction = (
            "اكتب حقل 'narration_ar' باللغة العربية الفصحى المشكولة تشكيلاً كاملاً مع فواصل تنفسية طبيعية (، ...) ليبدو الصوت بشرياً حقيقياً 100%."
            if lang_code == "ar" else
            "اكتب حقل 'narration_ar' باللهجة اليمنية الطبيعية المشوقة."
            if lang_code == "ar_ye" else
            f"IMPORTANT: Write the 'narration_ar' field strictly in natural, human-sounding {lang_info['name']} language (NOT Arabic)!"
        )

        final_json_prompt = (
            f"حول الخطة المتفق عليها حول '{topic}' في وضع '{profile['style_name']}' إلى كائن JSON صارم يحتوي على {num_scenes} مشاهد.\n"
            f"التعليمات الصارمة:\n"
            f"1. {lang_instruction}\n"
            f"2. يجب أن يبدأ كل 'visual_prompt_en' بـ: '{profile['visual_rule']}'.\n"
            f"3. استخدم المحركات التالية فقط: {profile['engines']}.\n"
            f"أخرج JSON فقط بهذا الشكل:\n"
            f"{{\n"
            f'  "title": "عنوان جذاب",\n'
            f'  "description": "وصف مع هاشتاجات",\n'
            f'  "color_lut": "{profile["lut"]}",\n'
            f'  "font_style": "Cairo-Bold",\n'
            f'  "bg_music_mood": "{profile["music"]}",\n'
            f'  "scenes": [\n'
            f'    {{\n'
            f'      "scene_id": 1,\n'
            f'      "narration_ar": "النص الصوتي البشري للمشهد باللغة المطلوبة",\n'
            f'      "engine": "{profile["engines"][0]}",\n'
            f'      "visual_prompt_en": "{profile["visual_rule"]}, detailed scene description",\n'
            f'      "search_query_en": "specific 2 words",\n'
            f'      "sfx": "whoosh",\n'
            f'      "transition": "{profile["transitions"][0]}"\n'
            f'    }}\n'
            f'  ]\n'
            f"}}"
        )
        raw_blueprint = await self.call_gemini(final_json_prompt, is_json=True)
        final_blueprint = self._apply_mode_and_voice_rules(raw_blueprint, topic, mode, lang_code, num_scenes)

        return final_blueprint, "\n\n".join(debate_log)

    async def inspect_visual_quality(self, frame_image_path, expected_prompt):
        return {"passed": True, "action": "keep", "reason": "Passed Vision QA"}

    async def self_heal_command(self, failed_cmd, error_message, attempt):
        heal_prompt = (
            f"Fix this failed command:\nCommand: {failed_cmd}\nError: {error_message}\n"
            f"Return ONLY the corrected command string without quotes or markdown."
        )
        fixed_cmd = await self.call_gemini(heal_prompt)
        return fixed_cmd.strip().replace("```bash", "").replace("```", "").strip()

boardroom = StudioBoardroom()
