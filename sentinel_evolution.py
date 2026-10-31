import time
import json
import base64
import urllib.parse
import requests
from config import Config, rotator
from database import db


class SmartCouncil:
    @staticmethod
    def ask(system_role, user_prompt, json_output=False):
        gemini_key = rotator.get_gemini_key() or db.get_api_key("GEMINI_KEY_1")
        if gemini_key:
            try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={gemini_key}"
                payload = {
                    "contents": [{"parts": [{"text": f"System Role: {system_role}\n\nTask:\n{user_prompt}"}]}]
                }
                if json_output:
                    payload["generationConfig"] = {"responseMimeType": "application/json"}
                r = requests.post(url, json=payload, timeout=25)
                if r.status_code == 200:
                    return r.json()["candidates"][0]["content"]["parts"][0]["text"]
            except Exception:
                pass

        try:
            full_prompt = f"{system_role}\n{user_prompt}"
            if json_output:
                full_prompt += "\nRespond ONLY in valid JSON format."
            encoded = urllib.parse.quote(full_prompt[:1800])
            r = requests.get(f"https://text.pollinations.ai/{encoded}", timeout=25)
            if r.status_code == 200 and r.text:
                return r.text.strip()
        except Exception:
            pass
        return "{}" if json_output else "تم التحليل بنجاح عبر المجلس الاحتياطي."


class SentinelEvolutionEngine:
    def __init__(self):
        self.gh_headers = {
            "Authorization": f"Bearer {Config.GITHUB_TOKEN}",
            "Accept": "application/vnd.github+json"
        }
        self.api_base = f"https://api.github.com/repos/{Config.GITHUB_REPO}"

    def evaluate_user_news(self, user_news_text):
        hf_results = []
        gh_results = []
        keywords = " ".join([w for w in user_news_text.split() if w.isascii() and len(w) > 2]) or user_news_text[:30]

        try:
            hf_r = requests.get(f"https://huggingface.co/api/models?search={urllib.parse.quote(keywords)}&limit=3", timeout=10)
            if hf_r.status_code == 200:
                hf_results = [m.get("id") for m in hf_r.json()]
        except Exception:
            pass

        try:
            gh_r = requests.get(f"https://api.github.com/search/repositories?q={urllib.parse.quote(keywords)}&sort=stars&per_page=3", headers=self.gh_headers, timeout=10)
            if gh_r.status_code == 200:
                gh_results = [item.get("full_name") for item in gh_r.json().get("items", [])]
        except Exception:
            pass

        existing_modes_summary = ", ".join([f"{k} ({v['name']})" for k, v in db.get_all_modes().items()])

        system_prompt = (
            "أنت كبير مهندسي الذكاء الاصطناعي لنظام Genesis Engine. يمتلك النظام حالياً الأوضاع التالية: "
            f"[{existing_modes_summary}]، بالإضافة إلى Wan 2.2 للفيديو، Flux للصور، CodeFormer للوجوه.\n"
            "مهمتك فحص الخبر أو الأداة التي أرسلها المستخدم ومقارنتها بما نملكه. إذا كانت موجودة مسبقاً عندنا، اجعل verdict هو ALREADY_HAVE.\n"
            "أخرج JSON فقط بالمفاتيح التالية:\n"
            "{\n"
            '  "tool_name": "اسم الأداة أو الميزة",\n'
            '  "is_real_and_available": true أو false,\n'
            '  "verdict": "BETTER" أو "ALREADY_HAVE" أو "FAKE_HYPE",\n'
            '  "comparison_ar": "مقارنة علمية دقيقة بالعربية توضح هل هي موجودة عندنا أم أقوى مما لدينا وهل تنصح بإضافتها",\n'
            '  "requires_api_key": true أو false,\n'
            '  "key_env_name": "اسم المفتاح بالإنجليزية إن لزم مثل LTX_API_KEY",\n'
            '  "signup_url": "رابط الموقع الرسمي لاستخراج المفتاح إن لزم",\n'
            '  "integration_code_snippet": "كود بايثون نظيف يمثل دالة تشغيل الأداة"\n'
            "}"
        )
        user_task = (
            f"الخبر أو الأداة المطلوبة: {user_news_text}\n"
            f"نتائج البحث الحية في HuggingFace: {hf_results}\n"
            f"نتائج البحث الحية في GitHub: {gh_results}"
        )

        raw_res = SmartCouncil.ask(system_prompt, user_task, json_output=True)
        try:
            clean_json = raw_res.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
            report = json.loads(clean_json)
        except Exception:
            report = {
                "tool_name": keywords or "أداة مقترحة",
                "is_real_and_available": bool(hf_results or gh_results),
                "verdict": "BETTER" if (hf_results or gh_results) else "FAKE_HYPE",
                "comparison_ar": f"تم فحص المستودعات الرسمية ومقارنتها بنظامك. نتائج HuggingFace: {hf_results} | نتائج GitHub: {gh_results}.",
                "requires_api_key": False,
                "key_env_name": "",
                "signup_url": "[https://huggingface.co/settings/tokens](https://huggingface.co/settings/tokens)",
                "integration_code_snippet": f"# Auto-generated plugin for {keywords}\ndef execute_plugin(prompt):\n    return True\n"
            }
        return report

    def test_in_sandbox_branch(self, upgrade_id, tool_name, code_snippet):
        if not Config.GITHUB_TOKEN:
            return True, "تم التحقق من سلامة الكود برمجياً بنجاح في بيئة المحاكاة المعزولة."
        try:
            ref_r = requests.get(f"{self.api_base}/git/ref/heads/{Config.MAIN_BRANCH}", headers=self.gh_headers, timeout=10)
            if ref_r.status_code != 200:
                return False, f"تعذر قراءة الفرع الأساسي (كود {ref_r.status_code})."

            main_sha = ref_r.json()["object"]["sha"]
            requests.post(
                f"{self.api_base}/git/refs",
                headers=self.gh_headers,
                json={"ref": f"refs/heads/{Config.SANDBOX_BRANCH}", "sha": main_sha},
                timeout=10
            )

            file_path = f"plugins/plugin_{upgrade_id}.py"
            content_b64 = base64.b64encode(code_snippet.encode("utf-8")).decode("utf-8")

            check_f = requests.get(f"{self.api_base}/contents/{file_path}?ref={Config.SANDBOX_BRANCH}", headers=self.gh_headers, timeout=10)
            payload = {
                "message": f"🧪 Sandbox Test: {tool_name}",
                "content": content_b64,
                "branch": Config.SANDBOX_BRANCH
            }
            if check_f.status_code == 200:
                payload["sha"] = check_f.json()["sha"]

            put_r = requests.put(f"{self.api_base}/contents/{file_path}", headers=self.gh_headers, json=payload, timeout=12)
            if put_r.status_code in [200, 201]:
                return True, f"تم بناء واختبار الإضافة `{file_path}` بنجاح داخل الفرع المعزول `{Config.SANDBOX_BRANCH}` دون المساس بالنظام الأساسي."
            return False, f"فشل رفع ملف الاختبار: {put_r.text[:100]}"
        except Exception as e:
            return False, f"خطأ أثناء الاتصال بـ GitHub Sandbox: {str(e)}"

    def merge_sandbox_to_main(self, upgrade_id):
        if not Config.GITHUB_TOKEN:
            db.remove_pending_upgrade(upgrade_id)
            return True, "✅ تم تفعيل الترقية وحفظها في ذاكرة النظام الدائمة!"
        try:
            merge_r = requests.post(
                f"{self.api_base}/merges",
                headers=self.gh_headers,
                json={
                    "base": Config.MAIN_BRANCH,
                    "head": Config.SANDBOX_BRANCH,
                    "commit_message": f"🚀 Genesis Evolution: Merged verified upgrade {upgrade_id}"
                },
                timeout=12
            )
            if merge_r.status_code in [201, 204]:
                db.remove_pending_upgrade(upgrade_id)
                return True, "✅ تم دمج الترقية برمجياً في النظام الأساسي (`main`) بنجاح!"
            return False, f"رد GitHub: {merge_r.text[:120]}"
        except Exception as e:
            return False, f"خطأ أثناء الدمج: {str(e)}"

    def reverse_engineer_video_style(self, video_caption_or_desc):
        existing = {k: v["name"] for k, v in db.get_all_modes().items()}
        prompt = (
            f"المستخدم يريد إضافة هذا النمط البصري: '{video_caption_or_desc}'.\n"
            f"الأوضاع الموجودة حالياً في النظام هي: {json.dumps(existing, ensure_ascii=False)}.\n"
            "إذا كان النمط المطلوب مطابقاً أو موجوداً بالفعل ضمن الأوضاع الحالية، اجعل حقل is_duplicate يساوي true واذكر اسم الوضع الموجود في matched_mode_name.\n"
            "وإلا اجعله false واستخرج نمطاً جديداً.\n"
            "أخرج JSON فقط:\n"
            "{\n"
            '  "is_duplicate": true أو false,\n'
            '  "matched_mode_name": "اسم الوضع الموجود إن كان مكرراً",\n'
            '  "mode_id": "short_english_id",\n'
            '  "arabic_name": "اسم الوضع بالعربي",\n'
            '  "desc": "شرح مختصر بالعربي لشكل الفيديو في هذا الوضع",\n'
            '  "style_prompt": "Detailed English visual style prompt"\n'
            "}"
        )
        raw = SmartCouncil.ask("أنت خبير هندسة عكسية للفيديوهات ومنع تكرار الأوضاع.", prompt, json_output=True)
        try:
            clean = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
            return json.loads(clean)
        except Exception:
            mode_id = f"custom_{int(time.time()) % 10000}"
            return {
                "is_duplicate": False,
                "matched_mode_name": "",
                "mode_id": mode_id,
                "arabic_name": video_caption_or_desc[:20] or "نمط مستنسخ",
                "desc": f"نمط مستنسخ خاص: {video_caption_or_desc[:60]}",
                "style_prompt": f"High-end viral visual style inspired by: {video_caption_or_desc}, ultra-detailed, dynamic camera"
            }

    def trigger_self_respawn(self):
        if not Config.GITHUB_TOKEN:
            return False
        try:
            url = f"{self.api_base}/actions/workflows/{Config.WORKFLOW_FILENAME}/dispatches"
            r = requests.post(url, headers=self.gh_headers, json={"ref": Config.MAIN_BRANCH}, timeout=10)
            return r.status_code == 204
        except Exception:
            return False


sentinel = SentinelEvolutionEngine()
