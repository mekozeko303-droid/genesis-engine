import os
import re
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
                "schema_version": 12,
                "modes": Config.DEFAULT_MODES,
                "cloned_video_ids": {},
                "api_keys": {},
                "lessons": [
                    {"context": "higgsfield_style", "rule": "Use multi-shot storytelling: Wide establishing shot, Medium action shot, Close-up expressive shot, Epic climax shot."},
                    {"context": "character_lock", "rule": "Lock character clothing, age, and facial features across every scene in the project."}
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
            data = self._load_local()
            stored_modes = data.get("modes", {})
            # مسح جميع فيديوهات الشاشة الزرقاء القديمة (أقل من الإصدار 12) نهائياً
            reset_blue_videos = data.get("schema_version", 0) < 12
            clean_modes = {}

            for k, v in Config.DEFAULT_MODES.items():
                old_sample = "" if reset_blue_videos else stored_modes.get(k, {}).get("sample_file_id", "")
                clean_modes[k] = {**v, "sample_file_id": old_sample}

            for k, v in stored_modes.items():
                if k not in Config.DEFAULT_MODES:
                    is_dup, _ = self._check_against_dict(clean_modes, k, v.get("name", ""), v.get("style", ""))
                    if not is_dup:
                        if reset_blue_videos:
                            v["sample_file_id"] = ""
                        clean_modes[k] = v

            data["schema_version"] = 12
            data["modes"] = clean_modes
            data.setdefault("cloned_video_ids", {})
            data.setdefault("pending_upgrades", {})
            data.setdefault("api_keys", {})
            self._save_local(data)

    def _load_local(self):
        try:
            with open(self.local_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            fallback = {
                "schema_version": 12,
                "modes": Config.DEFAULT_MODES,
                "cloned_video_ids": {},
                "api_keys": {},
                "lessons": [],
                "quota": {"used_pct": 0.0, "last_reset": time.time(), "active_node": "Node_1"},
                "pending_upgrades": {}
            }
            self._save_local(fallback)
            return fallback

    def _save_local(self, data):
        with open(self.local_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    @staticmethod
    def _normalize_text(txt):
        txt = re.sub(r"[^\w\s]", " ", txt.lower())
        stop_words = {"وضع", "الوضع", "فيديو", "نمط", "استوديو", "مدير", "و", "في", "على", "مع", "من", "style", "video", "mode"}
        tokens = [w.removeprefix("ال") for w in txt.split() if w not in stop_words and len(w) > 2]
        return set(tokens)

    def _check_against_dict(self, modes_dict, mode_id, arabic_name, style_prompt, video_unique_id=""):
        data = self._load_local()
        if video_unique_id:
            mapped_mode = data.get("cloned_video_ids", {}).get(video_unique_id)
            if mapped_mode and mapped_mode in modes_dict:
                return True, modes_dict[mapped_mode]

        new_tokens = self._normalize_text(f"{arabic_name} {style_prompt}")

        for existing_id, info in modes_dict.items():
            if existing_id == mode_id:
                return True, info

            existing_keywords = set(info.get("keywords", []))
            existing_tokens = self._normalize_text(
                f"{info.get('name', '')} {info.get('desc', '')} {info.get('style', '')} {' '.join(existing_keywords)}"
            )

            overlap = new_tokens.intersection(existing_tokens)
            keyword_hits = new_tokens.intersection({k.removeprefix("ال").lower() for k in existing_keywords})

            if len(keyword_hits) >= 1 or len(overlap) >= 2:
                return True, info

            name_sim = difflib.SequenceMatcher(None, arabic_name, info.get("name", "")).ratio()
            style_sim = difflib.SequenceMatcher(None, style_prompt.lower(), info.get("style", "").lower()).ratio()
            if name_sim > 0.58 or style_sim > 0.58:
                return True, info

        return False, None

    def get_all_modes(self):
        return self._load_local().get("modes", Config.DEFAULT_MODES)

    def check_duplicate_mode(self, mode_id, arabic_name, style_prompt, video_unique_id=""):
        return self._check_against_dict(self.get_all_modes(), mode_id, arabic_name, style_prompt, video_unique_id)

    def add_dynamic_mode(self, mode_id, name, style_prompt, desc="نمط مخصص", sample_file_id="", video_unique_id="", cost_pct=4.0):
        is_dup, existing_info = self.check_duplicate_mode(mode_id, name, style_prompt, video_unique_id)
        if is_dup:
            return False, existing_info

        data = self._load_local()
        new_mode = {
            "name": f"✨ {name.replace('✨', '').strip()}",
            "engine": "hybrid_router",
            "cost_pct": cost_pct,
            "est_time": "45 إلى 65 ثانية",
            "voice": "ar-SA-HamedNeural",
            "afilt": "atempo=1.05",
            "vfilter": "eq=contrast=1.18:saturation=1.22",
            "keywords": list(self._normalize_text(name)),
            "sample_topic": f"مشهد تطبيقي يستعرض نمط {name}",
            "style": style_prompt,
            "desc": desc,
            "sample_file_id": sample_file_id
        }
        data["modes"][mode_id] = new_mode
        if video_unique_id:
            data.setdefault("cloned_video_ids", {})[video_unique_id] = mode_id
        self._save_local(data)
        return True, new_mode

    def set_mode_sample_video(self, mode_id, file_id):
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

    def get_api_key(self, service_name):
        data = self._load_local()
        return data.get("api_keys", {}).get(service_name.upper()) or os.getenv(service_name.upper(), "").strip()

    def save_lesson(self, context_tag, rule_learned):
        data = self._load_local()
        lesson = {"context": context_tag, "rule": rule_learned, "timestamp": int(time.time())}
        data.setdefault("lessons", []).append(lesson)
        if len(data["lessons"]) > 30:
            data["lessons"] = data["lessons"][-30:]
        self._save_local(data)

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
