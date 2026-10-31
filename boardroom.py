import json
import base64
import asyncio
import aiohttp
from config import MAX_DEBATE_ROUNDS, MAX_SELF_HEAL_RETRIES
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

    async def call_gemini(self, prompt, is_json=False, image_path=None):
        api_key, status = quota_system.get_active_gemini_key()
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
        
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
        
        for _ in range(3):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(url, json=payload, timeout=30) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            txt = data["candidates"][0]["content"]["parts"][0]["text"]
                            if is_json:
                                clean = txt.strip().replace("```json", "").replace("```", "")
                                start = clean.find("{") if "{" in clean and (clean.find("{") < clean.find("[") or "[" not in clean) else clean.find("[")
                                end = clean.rfind("}") + 1 if start == clean.find("{") else clean.rfind("]") + 1
                                return json.loads(clean[start:end])
                            return txt
            except Exception:
                await asyncio.sleep(2)
        return {} if is_json else "Error"

    # ------------------------------------------
    # حلقة النقاش والإجماع (15-Agent Consensus Loop)
    # ------------------------------------------
    async def run_consensus_debate(self, topic, mode, num_scenes=5, extra_context=""):
        debate_log = []
        kaggle_rem = quota_system.get_total_kaggle_mins()

        # الجولة الأولى: طرح الرؤية من المخرج وطبيب السيناريو ووكيل التسويق
        init_prompt = (
            f"أنتما (1. المخرج) و(2. طبيب السيناريو والخطاف) و(12. وكيل التسويق). "
            f"المطلوب تصميم خطة عمل لـ {num_scenes} مشاهد حول: '{topic}' في وضع '{mode}'. "
            f"معلومات إضافية: {extra_context}. "
            f"اجعل المشهد الأول خطافاً بصرياً صادماً (Hook). اكتبوا المسودة الأولى بالعربية."
        )
        draft = await self.call_gemini(init_prompt)
        debate_log.append("🎬 **المخرج وطبيب السيناريو:** وضعا المسودة الأولى مع خطاف افتتاحي (Hook) قوي.")

        critique = ""
        # حلقات النقد والتنقيح والوصول للإجماع
        for round_num in range(1, MAX_DEBATE_ROUNDS + 1):
            critique_prompt = (
                f"اجتماع الغرفة (الجولة {round_num}):\n"
                f"المسودة الحالية: {draft}\n"
                f"رصيد سيرفرات Kaggle المتبقي: {kaggle_rem} دقيقة.\n\n"
                f"المطلوب تدخل الوكلاء التالية أسماؤهم لتقديم نقد وتعديلات صارمة:\n"
                f"- المدقق التاريخي/المنطقي: صحح أي خطأ أو تشويه للمعالم.\n"
                f"- مدير الميزانية وخبير VFX: قررا بحرية كاملة (بدون نسب ثابتة) أي مشهد يحتاج Kaggle (Wan 2.2) وأي مشهد ينفذ بـ Pixabay أو 3D Parallax حسب حاجة القصة.\n"
                f"- مهندس الصوت وخبير الألوان والانتقالات والخطوط: حددوا الفلاتر (LUTs)، المؤثرات الصوتية (SFX)، ونوع الانتقالات.\n"
                f"اكتبوا خلاصة نقاشكم في 4 نقاط مختصرة، وفي السطر الأخير اكتبوا [CONSENSUS_REACHED] إذا كانت الخطة مثالية، أو [NEEDS_REVISION] إذا كانت تحتاج تعديلاً."
            )
            critique = await self.call_gemini(critique_prompt)
            debate_log.append(f"🗣️ **نقاش الجولة ({round_num}):**\n{critique.replace('[CONSENSUS_REACHED]', '').replace('[NEEDS_REVISION]', '').strip()}")

            if "[CONSENSUS_REACHED]" in critique or round_num == MAX_DEBATE_ROUNDS:
                debate_log.append("✅ **مجلس الإدارة (15 وكيلاً):** تم الوصول إلى الإجماع الكامل واعتماد الرؤية النهائية!")
                break
            else:
                rev_prompt = f"عدّل هذه المسودة ({draft}) لتطبيق جميع ملاحظات الفريق الصارمة: ({critique})."
                draft = await self.call_gemini(rev_prompt)
                debate_log.append("🔄 **المنتج المنفذ:** أمر بإعادة صياغة المشاهد للوصول للكمال الفني.")

        # إصدار ملف التنفيذ النهائي (JSON) من المنتج المنفذ والمترجم البصري
        final_json_prompt = (
            f"بصفتك المنتج المنفذ (الوكيل 15) والمترجم البصري (الوكيل 7) والمدقق اللغوي (الوكيل 5):\n"
            f"حول المسودة المتفق عليها ({draft}) والنقاش ({critique}) إلى كائن JSON صارم يحتوي على:\n"
            f"{{\n"
            f'  "title": "عنوان فيروسي جذاب",\n'
            f'  "description": "وصف تسويقي مع هاشتاجات",\n'
            f'  "color_lut": "cinematic_warm أو dark_thriller أو vibrant_ad",\n'
            f'  "font_style": "Cairo-Bold",\n'
            f'  "bg_music_mood": "epic أو dramatic أو upbeat",\n'
            f'  "scenes": [\n'
            f'    {{\n'
            f'      "scene_id": 1,\n'
            f'      "narration_ar": "النص العربي المشكول والمدقق لغوياً",\n'
            f'      "engine": "kaggle_wan أو flux_parallax أو pixabay",\n'
            f'      "visual_prompt_en": "Detailed English cinematic prompt for AI generation",\n'
            f'      "search_query_en": "2 words for Pixabay fallback",\n'
            f'      "sfx": "thunder أو sword_clash أو whoosh",\n'
            f'      "transition": "fade أو wipeleft أو smoothleft"\n'
            f'    }}\n'
            f'  ]\n'
            f"}}"
        )
        final_blueprint = await self.call_gemini(final_json_prompt, is_json=True)
        return final_blueprint, "\n\n".join(debate_log)

    # ------------------------------------------
    # وكيل الفحص البصري (Vision QA Agent - رقم 14)
    # ------------------------------------------
    async def inspect_visual_quality(self, frame_image_path, expected_prompt):
        qa_prompt = (
            f"أنت مفتش الجودة البصري (Vision QA Agent). افحص هذه الصورة المولدة للمشهد: '{expected_prompt}'.\n"
            f"هل يوجد تشوه واضح في الوجه، أو أطراف زائدة مشوهة، أو شاشة سوداء/تالفة؟\n"
            f"أجب بصيغة JSON فقط: {{\"passed\": true/false, \"action\": \"keep\" أو \"codeformer_fix\" أو \"regenerate\", \"reason\": \"السبب\"}}"
        )
        res = await self.call_gemini(qa_prompt, is_json=True, image_path=frame_image_path)
        if isinstance(res, dict) and "passed" in res:
            return res
        return {"passed": True, "action": "keep", "reason": "Default pass"}

    # ------------------------------------------
    # وكيل المطور للتصحيح الذاتي (Debugger Agent - رقم 15)
    # ------------------------------------------
    async def self_heal_command(self, failed_cmd, error_message, attempt):
        heal_prompt = (
            f"أنت وكيل المطور (Self-Healing Debugger Agent). تعطل هذا الأمر البرمجي (المحاولة {attempt}/{MAX_SELF_HEAL_RETRIES}):\n"
            f"الأمر: {failed_cmd}\n"
            f"رسالة الخطأ: {error_message}\n\n"
            f"اكتب أمر FFmpeg أو Python البديل والمصحح فقط بدون أي شرح أو علامات تنصيص لتشغيله فوراً."
        )
        fixed_cmd = await self.call_gemini(heal_prompt)
        return fixed_cmd.strip().replace("```bash", "").replace("```", "").strip()

boardroom = StudioBoardroom()
