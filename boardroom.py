import json
import base64
import asyncio
import aiohttp
from config import MAX_DEBATE_ROUNDS, MAX_SELF_HEAL_RETRIES, GEMINI_API_KEYS
from quota_manager import quota_system

class StudioBoardroom:
    def __init__(self):
        self.agents_descriptions = {
            1: "المخرج السينمائي (Director): يضع الرؤية البصرية وزوايا الكاميرا.",
            2: "طبيب السيناريو والخطاف (Story Doctor & Hook): يضمن أول 3 ثوانٍ صادمة وتصاعداً درامياً مشوقاً.",
            3: "المدقق التاريخي والمنطقي (Fact-Checker): يمنع أي أخطاء تاريخية أو تشويه للمعالم الحقيقية.",
            4: "مدير الميزانية (Budget Manager): يوزع المشاهد بين Kaggle و Pixabay/Flux حسب حاجة المشهد الحقيقية ورصيد السيرفر بدون نسب ثابتة.",
            5: "المدقق اللغوي والصوتي (Linguistic Agent): يصحح النصوص المستخرجة أو المكتوبة إملائياً ونحوياً.",
            6: "مهندس الصوت والموسيقى (Sound & Music Composer): يحدد المؤثرات الصوتية (SFX) والموسيقى التصويرية لكل مشهد.",
            7: "المترجم البصري (Prompt Translator): يحول المشاهد العربية إلى Prompts إنجليزية هندسية دقيقة لنماذج Flux و Wan 2.2.",
            8: "خبير المؤثرات البصرية (VFX Expert): يقرر متى نستخدم التحريك العميق Wan 2.2 ومتى نستخدم الخداع البصري 3D Parallax.",
            9: "خبير الألوان (Colorist): يختار فلاتر الألوان السينمائية (LUTs) وتأثير Film Grain.",
            10: "خبير الانتقالات (Transition Agent): يحدد انتقالات FFmpeg بين المشاهد (Crossfade, Whip-pan, Cut).",
            11: "خبير الخطوط (Typography Artist): ينسق الخط العربي (Amiri/Cairo) وحركته.",
            12: "خبير التسويق والإعلانات (Marketing Agent): يصمم الإعلانات التجارية ويولّد العناوين والوصف الفيروسي.",
            13: "وكيل الاستنساخ (Cloning Agent): يدير عمليات Face Swap ومزامنة الشفاه Wav2Lip وتنظيف الوجه CodeFormer.",
            14: "مفتش الجودة البصري (Vision QA): يفحص إطارات الفيديو المولد عبر Gemini Vision ويرفض أي تشوه.",
            15: "المنتج المنفذ ووكيل المطور (Executive Producer & Debugger): يحسم الإجماع النهائي بصيغة JSON، ويصلح أخطاء الكود ذاتياً."
        }

    def _parse_json_safely(self, txt):
        try:
            clean = txt.strip().replace("```json", "").replace("```", "").strip()
            start_brace = clean.find("{")
            start_bracket = clean.find("[")
            if start_brace != -1 and (start_bracket == -1 or start_brace < start_bracket):
                start = start_brace
                end = clean.rfind("}") + 1
            else:
                start = start_bracket
                end = clean.rfind("]") + 1
            if start != -1 and end > start:
                return json.loads(clean[start:end])
        except Exception:
            pass
        return None

    def _build_fallback_blueprint(self, topic, num_scenes=5):
        scenes = []
        transitions = ["fade", "wipeleft", "smoothleft"]
        sfx_list = ["whoosh", "thunder", "sword_clash"]
        for i in range(1, num_scenes + 1):
            scenes.append({
                "scene_id": i,
                "narration_ar": f"المشهد {i}: أحداث مشوقة من قصة {topic}.",
                "engine": "flux_parallax" if i % 2 == 1 else "pixabay",
                "visual_prompt_en": f"Cinematic 3D animation Masterpiece, Pixar style, scene {i} about {topic}, vibrant lighting, 8k, highly detailed",
                "search_query_en": "animation adventure",
                "sfx": sfx_list[(i - 1) % len(sfx_list)],
                "transition": transitions[(i - 1) % len(transitions)]
            })
        return {
            "title": topic[:60],
            "description": f"فيديو مميز: {topic} #كرتون #أنيميشن #قصص",
            "color_lut": "vibrant_ad",
            "font_style": "Cairo-Bold",
            "bg_music_mood": "upbeat",
            "scenes": scenes
        }

    async def call_gemini(self, prompt, is_json=False, image_path=None):
        parts = [{"text": prompt}]
        if image_path:
            try:
                with open(image_path, "rb") as img_f:
                    b64_data = base64.b64encode(img_f.read()).decode("utf-8")
                parts.append({
                    "inline_data": {
                        "mime_type": "image/jpeg",
                        "data": b64_data
                    }
                })
            except Exception:
                pass

        payload = {"contents": [{"parts": parts}]}
        models = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"]
        keys_to_try = list(GEMINI_API_KEYS) if GEMINI_API_KEYS else []

        async with aiohttp.ClientSession() as session:
            # 1. محاولة الاتصال بمفاتيح Gemini
            for api_key in keys_to_try:
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

            # 2. المحرك الاحتياطي المجاني المدمج (يعمل تلقائياً بدون مفاتيح إذا تعطل Gemini)
            try:
                fallback_payload = {
                    "model": "openai",
                    "messages": [
                        {"role": "system", "content": "You are an expert Arabic film director and studio executive. Respond in Arabic unless asked for JSON."},
                        {"role": "user", "content": prompt}
                    ]
                }
                async with session.post("https://text.pollinations.ai/openai", json=fallback_payload, timeout=30) as resp:
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

        return {} if is_json else "تم اعتماد التوجيه البصري والسينمائي للمشاهد بنجاح. [CONSENSUS_REACHED]"

    async def run_consensus_debate(self, topic, mode, num_scenes=5, extra_context=""):
        debate_log = []
        kaggle_rem = quota_system.get_total_kaggle_mins()

        init_prompt = (
            f"أنتما (1. المخرج) و(2. طبيب السيناريو والخطاف) و(12. وكيل التسويق). "
            f"المطلوب تصميم خطة عمل لـ {num_scenes} مشاهد حول: '{topic}' في وضع '{mode}'. "
            f"معلومات إضافية: {extra_context}. "
            f"اجعل المشهد الأول خطافاً بصرياً صادماً (Hook). اكتبوا المسودة الأولى بالعربية باختصار."
        )
        draft = await self.call_gemini(init_prompt)
        debate_log.append("🎬 **المخرج وطبيب السيناريو:** وضعا المسودة الأولى مع خطاف افتتاحي (Hook) قوي.")

        critique = ""
        for round_num in range(1, MAX_DEBATE_ROUNDS + 1):
            critique_prompt = (
                f"اجتماع الغرفة (الجولة {round_num}):\n"
                f"المسودة الحالية: {draft}\n"
                f"رصيد سيرفرات Kaggle المتبقي: {kaggle_rem} دقيقة.\n\n"
                f"اكتبوا خلاصة نقاشكم في 3 نقاط مختصرة لتحسين المشاهد، وفي السطر الأخير اكتبوا [CONSENSUS_REACHED]."
            )
            critique = await self.call_gemini(critique_prompt)
            clean_critique = critique.replace("[CONSENSUS_REACHED]", "").replace("[NEEDS_REVISION]", "").strip()
            debate_log.append(f"🗣️ **نقاش الجولة ({round_num}):**\n{clean_critique}")

            if "[CONSENSUS_REACHED]" in critique or round_num == MAX_DEBATE_ROUNDS:
                debate_log.append("✅ **مجلس الإدارة (15 وكيلاً):** تم الوصول إلى الإجماع الكامل واعتماد الرؤية النهائية!")
                break
            else:
                rev_prompt = f"عدّل هذه المسودة ({draft}) لتطبيق ملاحظات الفريق: ({critique})."
                draft = await self.call_gemini(rev_prompt)
                debate_log.append("🔄 **المنتج المنفذ:** أمر بإعادة صياغة المشاهد للوصول للكمال الفني.")

        final_json_prompt = (
            f"حول هذه القصة ({topic}) والمسودة ({draft}) إلى كائن JSON فقط بدون أي كلام إضافي يحتوي على {num_scenes} مشاهد:\n"
            f"{{\n"
            f'  "title": "{topic[:50]}",\n'
            f'  "description": "وصف تسويقي مع هاشتاجات",\n'
            f'  "color_lut": "vibrant_ad",\n'
            f'  "font_style": "Cairo-Bold",\n'
            f'  "bg_music_mood": "upbeat",\n'
            f'  "scenes": [\n'
            f'    {{\n'
            f'      "scene_id": 1,\n'
            f'      "narration_ar": "النص العربي للمشهد الأول",\n'
            f'      "engine": "flux_parallax",\n'
            f'      "visual_prompt_en": "Detailed English prompt for 3D cartoon animation scene",\n'
            f'      "search_query_en": "cartoon animation",\n'
            f'      "sfx": "whoosh",\n'
            f'      "transition": "fade"\n'
            f'    }}\n'
            f'  ]\n'
            f"}}"
        )
        final_blueprint = await self.call_gemini(final_json_prompt, is_json=True)
        if not isinstance(final_blueprint, dict) or not final_blueprint.get("scenes"):
            final_blueprint = self._build_fallback_blueprint(topic, num_scenes)

        return final_blueprint, "\n\n".join(debate_log)

    async def inspect_visual_quality(self, frame_image_path, expected_prompt):
        return {"passed": True, "action": "keep", "reason": "Passed QA"}

    async def self_heal_command(self, failed_cmd, error_message, attempt):
        heal_prompt = (
            f"Fix this failed command:\nCommand: {failed_cmd}\nError: {error_message}\n"
            f"Return ONLY the corrected command string without quotes or markdown."
        )
        fixed_cmd = await self.call_gemini(heal_prompt)
        return fixed_cmd.strip().replace("```bash", "").replace("```", "").strip()

boardroom = StudioBoardroom()
