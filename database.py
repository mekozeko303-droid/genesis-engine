# -*- coding: utf-8 -*-
import datetime
import json
import logging
from pathlib import Path
from typing import Any

import requests
import config

log = logging.getLogger("genesis.db")


class Database:
    def __init__(self):
        self.file_path: Path = config.DATA_DIR / "studio_state.json"
        self.data: dict[str, Any] = {
            "users": {},
            "samples": {},
            "stats": {"videos": 0, "failures": 0},
        }
        self._supa_url = config.SUPABASE_URL.rstrip("/")
        self._supa_key = config.SUPABASE_KEY

    async def load(self) -> None:
        if self.file_path.exists():
            try:
                self.data = json.loads(self.file_path.read_text(encoding="utf-8"))
            except Exception as e:
                log.warning("تعذر قراءة ملف الذاكرة المحلي: %s", e)

        # جلب الأمثلة المثبتة من Supabase إن وجدت
        if self._supa_url and self._supa_key:
            try:
                r = requests.get(
                    f"{self._supa_url}/rest/v1/mode_samples?select=mode_id,file_id",
                    headers={"apikey": self._supa_key, "Authorization": f"Bearer {self._supa_key}"},
                    timeout=8,
                )
                if r.status_code == 200:
                    for row in r.json():
                        mid = row.get("mode_id")
                        fid = row.get("file_id")
                        if mid and fid:
                            self.data.setdefault("samples", {})[mid] = {"file_id": fid, "path": ""}
            except Exception as e:
                log.warning("تعذر جلب الأمثلة من Supabase: %s", e)

    async def flush(self) -> None:
        try:
            self.file_path.write_text(json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as e:
            log.warning("تعذر حفظ الذاكرة المحلية: %s", e)

    def _today(self) -> str:
        return datetime.date.today().isoformat()

    def user(self, uid: int) -> dict[str, Any]:
        u = self.data.setdefault("users", {}).setdefault(
            str(uid),
            {"mode": "fasso", "duration": 60, "name": "", "pending": "", "day": self._today(), "used": 0},
        )
        if u.get("day") != self._today():
            u["day"] = self._today()
            u["used"] = 0
        u.setdefault("duration", 60)
        return u

    def get_mode(self, uid: int) -> str:
        m = self.user(uid).get("mode", "fasso")
        return m if m in config.MODES else "fasso"

    async def set_mode(self, uid: int, mode_id: str, name: str = "") -> None:
        u = self.user(uid)
        u["mode"] = mode_id
        if name:
            u["name"] = name
        await self.flush()

    def get_duration(self, uid: int) -> int:
        return int(self.user(uid).get("duration", 60))

    async def set_duration(self, uid: int, seconds: int) -> None:
        u = self.user(uid)
        u["duration"] = int(seconds)
        await self.flush()

    async def set_pending(self, uid: int, idea: str) -> None:
        self.user(uid)["pending"] = idea
        await self.flush()

    async def pop_pending(self, uid: int) -> str:
        u = self.user(uid)
        val = u.get("pending", "")
        u["pending"] = ""
        await self.flush()
        return val

    def get_sample(self, mode_id: str) -> dict[str, str] | None:
        return self.data.get("samples", {}).get(mode_id)

    async def set_sample(self, mode_id: str, path: str, file_id: str) -> None:
        self.data.setdefault("samples", {})[mode_id] = {"path": path, "file_id": file_id}
        await self.flush()
        if self._supa_url and self._supa_key and file_id:
            try:
                requests.post(
                    f"{self._supa_url}/rest/v1/mode_samples",
                    headers={
                        "apikey": self._supa_key,
                        "Authorization": f"Bearer {self._supa_key}",
                        "Content-Type": "application/json",
                        "Prefer": "resolution=merge-duplicates",
                    },
                    json={"mode_id": mode_id, "file_id": file_id},
                    timeout=8,
                )
            except Exception:
                pass

    def remaining_quota(self, uid: int, is_admin: bool = False) -> int:
        if is_admin:
            return 999
        u = self.user(uid)
        return max(0, config.DAILY_LIMIT - int(u.get("used", 0)))

    async def record_success(self, uid: int, mode_id: str, idea: str, title: str, used_assets: list[str]) -> None:
        u = self.user(uid)
        u["used"] = int(u.get("used", 0)) + 1
        self.data.setdefault("stats", {})["videos"] = int(self.data["stats"].get("videos", 0)) + 1
        await self.flush()

    async def record_failure(self, uid: int, mode_id: str, idea: str, reason: str) -> None:
        self.data.setdefault("stats", {})["failures"] = int(self.data["stats"].get("failures", 0)) + 1
        await self.flush()

    def stats(self) -> dict[str, int]:
        st = self.data.get("stats", {})
        return {
            "videos": int(st.get("videos", 0)),
            "failures": int(st.get("failures", 0)),
            "users": len(self.data.get("users", {})),
            "samples": len(self.data.get("samples", {})),
        }
