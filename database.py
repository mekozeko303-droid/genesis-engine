# -*- coding: utf-8 -*-
"""
Genesis Cinema Studio — database.py
الذاكرة الدائمة: وضع كل مستخدم، الحصة اليومية، فيديوهات الأمثلة (file_id)،
والمقاطع المستخدمة سابقاً (لمنع التكرار). تُحفظ في ملف JSON بكتابة آمنة (atomic)،
مع نسخة احتياطية اختيارية في Supabase.

جدول Supabase (نفّذ مرة واحدة في SQL Editor إن أردت النسخ الاحتياطي):
    create table if not exists genesis_state (
        id text primary key,
        data jsonb not null,
        updated_at timestamptz default now()
    );
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import httpx

import config

log = logging.getLogger("genesis.db")

_MAX_USED_ASSETS = 400   # نتذكر آخر 400 مقطع لكل مصدر لمنع إعادة استخدامها
_MAX_HISTORY = 200


def _default() -> dict:
    return {
        "version": 1,
        "users": {},
        "assets": {"pixabay": [], "wikimedia": []},
        "samples": {},
        "history": [],
        "stats": {"videos": 0, "failures": 0},
    }


class Database:
    def __init__(self, path: Path = config.DB_PATH):
        self.path = Path(path)
        self.data: dict = _default()
        self._lock = asyncio.Lock()
        self._used: dict[str, set] = {}

    # ───────────────────────── تحميل / حفظ ─────────────────────────
    async def load(self) -> None:
        loaded: Optional[dict] = None
        if self.path.exists():
            try:
                loaded = json.loads(self.path.read_text(encoding="utf-8"))
            except Exception as e:  # ملف تالف → نحتفظ به باسم آخر ونبدأ نظيفاً
                bad = self.path.with_suffix(f".corrupt-{int(time.time())}.json")
                try:
                    self.path.rename(bad)
                except OSError:
                    pass
                log.error("ملف الذاكرة تالف (%s) — نُقل إلى %s", e, bad.name)
        if loaded is None:
            loaded = await self._remote_pull()
        if isinstance(loaded, dict):
            base = _default()
            base.update(loaded)
            for k, v in _default().items():
                base.setdefault(k, v)
            self.data = base
        self._rebuild_used()
        log.info("الذاكرة جاهزة: %d مستخدم", len(self.data["users"]))

    def _rebuild_used(self) -> None:
        self._used = {k: set(v) for k, v in self.data.get("assets", {}).items()}

    def _write_atomic(self, text: str) -> None:
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(text, encoding="utf-8")
        os.replace(tmp, self.path)

    async def save(self, remote: bool = False) -> None:
        async with self._lock:
            text = json.dumps(self.data, ensure_ascii=False)
            try:
                await asyncio.to_thread(self._write_atomic, text)
            except Exception:
                log.exception("تعذّر حفظ الذاكرة محلياً")
        if remote:
            await self._remote_push()

    async def flush(self) -> None:
        await self.save(remote=True)

    # ───────────────────────── Supabase (اختياري) ─────────────────────────
    def _remote_enabled(self) -> bool:
        return bool(config.SUPABASE_URL and config.SUPABASE_KEY)

    def _remote_headers(self) -> dict:
        return {
            "apikey": config.SUPABASE_KEY,
            "Authorization": f"Bearer {config.SUPABASE_KEY}",
            "Content-Type": "application/json",
        }

    async def _remote_pull(self) -> Optional[dict]:
        if not self._remote_enabled():
            return None
        try:
            async with httpx.AsyncClient(timeout=15) as c:
                r = await c.get(
                    f"{config.SUPABASE_URL}/rest/v1/{config.SUPABASE_TABLE}",
                    params={"id": "eq.state", "select": "data"},
                    headers=self._remote_headers(),
                )
            if r.status_code == 200 and r.json():
                log.info("تمت استعادة الذاكرة من Supabase")
                return r.json()[0]["data"]
        except Exception as e:
            log.warning("فشل سحب Supabase: %s", e)
        return None

    async def _remote_push(self) -> None:
        if not self._remote_enabled():
            return
        try:
            async with httpx.AsyncClient(timeout=15) as c:
                r = await c.post(
                    f"{config.SUPABASE_URL}/rest/v1/{config.SUPABASE_TABLE}",
                    params={"on_conflict": "id"},
                    headers={**self._remote_headers(), "Prefer": "resolution=merge-duplicates"},
                    content=json.dumps({"id": "state", "data": self.data}, ensure_ascii=False).encode("utf-8"),
                )
            if r.status_code >= 300:
                log.warning("Supabase رفض الحفظ: %s %s", r.status_code, r.text[:120])
        except Exception as e:
            log.warning("فشل دفع Supabase: %s", e)

    # ───────────────────────── المستخدمون ─────────────────────────
    @staticmethod
    def _today() -> str:
        tz = timezone(timedelta(hours=config.TZ_OFFSET_HOURS))
        return datetime.now(tz).strftime("%Y-%m-%d")

    def user(self, uid: int) -> dict:
        key = str(uid)
        u = self.data["users"].get(key)
        if u is None:
            u = {"mode": None, "pending": None, "name": "", "total": 0,
                 "daily": {"date": "", "count": 0}, "first_seen": int(time.time())}
            self.data["users"][key] = u
        return u

    def get_mode(self, uid: int) -> Optional[str]:
        m = self.user(uid).get("mode")
        return m if m in config.MODES else None

    async def set_mode(self, uid: int, mode_id: str, name: str = "") -> None:
        u = self.user(uid)
        u["mode"] = mode_id
        if name:
            u["name"] = name[:40]
        await self.save()

    async def set_pending(self, uid: int, idea: Optional[str]) -> None:
        self.user(uid)["pending"] = idea
        await self.save()

    async def pop_pending(self, uid: int) -> Optional[str]:
        u = self.user(uid)
        idea = u.get("pending")
        if idea:
            u["pending"] = None
            await self.save()
        return idea

    def used_today(self, uid: int) -> int:
        d = self.user(uid)["daily"]
        return d["count"] if d.get("date") == self._today() else 0

    def remaining_quota(self, uid: int, is_admin: bool = False) -> int:
        if is_admin:
            return 999
        return max(0, config.DAILY_LIMIT - self.used_today(uid))

    # ───────────────────────── السجل والإحصاءات ─────────────────────────
    async def record_success(self, uid: int, mode_id: str, idea: str, title: str, clip_ids: dict[str, list[str]]) -> None:
        u = self.user(uid)
        today = self._today()
        if u["daily"].get("date") != today:
            u["daily"] = {"date": today, "count": 0}
        u["daily"]["count"] += 1
        u["total"] = u.get("total", 0) + 1
        self.data["stats"]["videos"] += 1
        self._push_history({"ts": int(time.time()), "uid": uid, "mode": mode_id,
                            "idea": idea[:160], "ok": True, "title": title[:80]})
        for kind, ids in clip_ids.items():
            self._mark_used(kind, ids)
        await self.save(remote=True)

    async def record_failure(self, uid: int, mode_id: str, idea: str, reason: str) -> None:
        self.data["stats"]["failures"] += 1
        self._push_history({"ts": int(time.time()), "uid": uid, "mode": mode_id,
                            "idea": idea[:160], "ok": False, "reason": reason[:160]})
        await self.save()

    def _push_history(self, item: dict) -> None:
        h = self.data["history"]
        h.append(item)
        del h[:-_MAX_HISTORY]

    def stats(self) -> dict:
        s = dict(self.data["stats"])
        s["users"] = len(self.data["users"])
        s["samples"] = len(self.data["samples"])
        return s

    # ───────────────────────── منع تكرار المقاطع ─────────────────────────
    def is_asset_used(self, kind: str, ref: str) -> bool:
        return str(ref) in self._used.get(kind, set())

    def _mark_used(self, kind: str, refs) -> None:
        lst = self.data["assets"].setdefault(kind, [])
        for r in refs:
            r = str(r)
            if r not in lst:
                lst.append(r)
        del lst[:-_MAX_USED_ASSETS]
        self._used[kind] = set(lst)

    # ───────────────────────── فيديوهات الأمثلة ─────────────────────────
    def get_sample(self, mode_id: str) -> Optional[dict]:
        """يرجع {"file_id":..., "path":...} أو None. الأولوية لملف يضعه المالك يدوياً في data/samples."""
        manual = config.SAMPLES_DIR / f"{mode_id}.mp4"
        rec = self.data["samples"].get(mode_id, {})
        file_id = rec.get("file_id")
        if manual.exists() and manual.stat().st_size > 1024:
            return {"file_id": file_id if rec.get("path") == str(manual) else None, "path": str(manual)}
        if file_id:
            return {"file_id": file_id, "path": None}
        return None

    async def set_sample(self, mode_id: str, path: Optional[str], file_id: Optional[str]) -> None:
        self.data["samples"][mode_id] = {"path": path, "file_id": file_id, "ts": int(time.time())}
        await self.save(remote=True)
