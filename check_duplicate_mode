import os
import json
import time
import difflib
import requests
from config import Config

class GenesisDatabase:
    def __init__(self):
        self.base_url = f"{Config.SUPABASE_URL.rstrip('/')}/rest/v1"
        self.headers = {
            "apikey": Config.SUPABASE_SECRET_KEY,
            "Authorization": f"Bearer {Config.SUPABASE_SECRET_KEY}",
            "Content-Type": "application/json",
            "Prefer": "return=representation"
        }
        self.local_file = "genesis_persistent_memory.json"
        self._init_local_cache()

    def _init_local_cache(self):
        if not os.path.exists(self.local_file):
            initial_data = {
                "modes": Config.DEFAULT_MODES,
                "api_keys": {},
                "lessons": [
                    {"context": "hands", "rule": "Always add 'perfect anatomy, five fingers' and avoid extreme close-ups on hands."},
                    {"context": "faces", "rule": "Apply CodeFormer restoration and use 'detailed expressive eyes, natural skin texture'."}
                ],
                "quota": {
                    "used_pct": 0.0,
                    "last_reset": time.time(),
                    "active_node": "Node_1"
                },
                "pending_upgrades": {}
            }
            self._save_local(initial_data)
        else:
            # ضمان تحديث الصور التوضيحية لأي وضع افتراضي
            data = self._load_local()
            modes = data.get("modes", {})
            for k, v in Config.DEFAULT_MODES.items():
                if k not in modes:
                    modes[k] = v
                else:
                    modes[k].setdefault("preview_url", v["preview_url"])
                    modes[k].setdefault("desc", v["desc"])
                    modes[k].setdefault("sample_file_id", "")
            data["modes"] = modes
            self._save_local(data)

    def _load_local(self):
        try:
            with open(self.local_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            with open(self.local_file, "w", encoding="utf-8") as f:
                json.dump({"modes": Config.DEFAULT_MODES, "api_keys": {}, "lessons": [], "quota": {"used_pct": 0.0, "last_reset": time.time(), "active_node": "Node_1"}, "pending_upgrades": {}}, f)
            return {"modes": Config.DEFAULT_MODES, "api_keys": {}, "lessons": [], "quota": {"used_pct": 0.0, "last_reset": time.time(), "active_node": "Node_1"}, "pending_upgrades": {}}

    def _save_local(self, data):
        with open(self.local_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _supabase_sync(self, table, payload):
        try:
            requests.post(f"{self.base_url}/{table}", headers=self.headers, json=payload, timeout=5)
        except Exception:
            pass

    def get_all_modes(self):
        return self._load_local().get("modes", Config.DEFAULT_MODES)

    # --- فحص التكرار الذكي قبل إضافة أي وضع جديد ---
    def check_duplicate_mode(self, mode_id, arabic_name, style_prompt):
        modes = self.get_all_modes()
        clean_new_name = arabic_name.replace("✨", "").strip()

        for existing_id, info in modes.items():
            existing_name = info.get("name", "").replace("✨", "").strip()
            existing_style = info.get("style", "")

            if existing_id == mode_id or clean_new_name in existing_name or existing_name in clean_new_name:
                return True, info

            name_sim = difflib.SequenceMatcher(None, clean_new_name, existing_name).ratio()
            style_sim = difflib.SequenceMatcher(None, style_prompt.lower(), existing_style.lower()).ratio()
            if name_sim > 0.72 or style_sim > 0.70:
                return True, info

        return False, None

    def add_dynamic_mode(self, mode_id, name, style_prompt, desc="نمط مخصص تم استنساخه بالذكاء الاصطناعي", sample_file_id="", cost_pct=4.0):
        is_dup, existing_info = self.check_duplicate_mode(mode_id, name, style_prompt)
        if is_dup:
            return False, existing_info

        data = self._load_local()
        encoded_prompt = requests.utils.quote(style_prompt[:120])
        preview_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=720&height=480&nologo=true"

        new_mode = {
            "name": f"✨ {name}",
            "engine": "hybrid_router",
            "cost_pct": cost_pct,
            "style": style_prompt,
            "desc": desc,
            "preview_url": preview_url,
            "sample_file_id": sample_file_id
        }
        data["modes"][mode_id] = new_mode
        self._save_local(data)
        self._supabase_sync("system_modes", {"mode_id": mode_id, **new_mode})
        return True, new_mode

    def set_mode_sample_video(self, mode_id, file_id):
        """حفظ فيديو قصير تذكيري لأي وضع في تيليجرام"""
        data = self._load_local()
        if mode_id in data["modes"]:
            data["modes"][mode_id]["sample_file_id"] = file_id
            self._save_local(data)
            return True
        return False

    def save_api_key(self, service_name, api_key):
        data = self._load_local()
        data["api_keys"][service_name.upper()] = api_key.strip()
        self._save_local(data)
        self._supabase_sync("api_keys", {"service": service_name.upper(), "key_val": api_key.strip()})

    def get_api_key(self, service_name):
        data = self._load_local()
        return data.get("api_keys", {}).get(service_name.upper()) or os.getenv(service_name.upper(), "")

    def save_lesson(self, context_tag, rule_learned):
        data = self._load_local()
        lesson = {"context": context_tag, "rule": rule_learned, "timestamp": int(time.time())}
        data["lessons"].append(lesson)
        if len(data["lessons"]) > 30:
            data["lessons"] = data["lessons"][-30:]
        self._save_local(data)
        self._supabase_sync("learning_memory", lesson)

    def get_relevant_lessons(self):
        lessons = self._load_local().get("lessons", [])
        return " | ".join([l["rule"] for l in lessons[-8:]])

    def get_quota_status(self):
        data = self._load_local()
        q = data["quota"]
        elapsed = time.time() - q["last_reset"]
        if elapsed >= 86400:
            q["used_pct"] = 0.0
            q["last_reset"] = time.time()
            self._save_local(data)
            elapsed = 0
        rem_pct = max(0.0, round(100.0 - q["used_pct"], 1))
        rem_seconds = max(0, int(86400 - elapsed))
        hours = rem_seconds // 3600
        minutes = (rem_seconds % 3600) // 60
        return {
            "used_pct": round(q["used_pct"], 1),
            "remaining_pct": rem_pct,
            "reset_in": f"{hours} ساعة و {minutes} دقيقة",
            "active_node": q.get("active_node", "Node_1")
        }

    def consume_quota(self, cost_pct):
        data = self._load_local()
        data["quota"]["used_pct"] = min(100.0, data["quota"]["used_pct"] + cost_pct)
        data["quota"]["active_node"] = "Node_2" if data["quota"]["used_pct"] >= 50.0 else "Node_1"
        self._save_local(data)
        return self.get_quota_status()

    def save_pending_upgrade(self, upgrade_id, details):
        data = self._load_local()
        data["pending_upgrades"][upgrade_id] = details
        self._save_local(data)

    def get_pending_upgrade(self, upgrade_id):
        return self._load_local().get("pending_upgrades", {}).get(upgrade_id)

    def remove_pending_upgrade(self, upgrade_id):
        data = self._load_local()
        if upgrade_id in data.get("pending_upgrades", {}):
            del data["pending_upgrades"][upgrade_id]
            self._save_local(data)

db = GenesisDatabase()
