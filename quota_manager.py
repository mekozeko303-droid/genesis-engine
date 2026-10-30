import os
import json
import asyncio
import aiohttp
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import (
    KAGGLE_FLEET, GEMINI_API_KEYS, GEMINI_DAILY_LIMIT_PER_KEY,
    SUPABASE_URL, SUPABASE_SECRET_KEY
)

class QuotaAndFleetManager:
    def __init__(self):
        self.gemini_usage = {0: 0, 1: 0}
        self.current_gemini_idx = 0
        self.kaggle_accounts = KAGGLE_FLEET
        self.current_kaggle_idx = 0
        self.paused_tasks = {}

    # ------------------------------------------
    # إدارة مفاتيح Gemini بالتناوب (Load Balancing)
    # ------------------------------------------
    def get_active_gemini_key(self):
        for _ in range(len(GEMINI_API_KEYS)):
            idx = self.current_gemini_idx
            if self.gemini_usage[idx] < (GEMINI_DAILY_LIMIT_PER_KEY * 0.90):
                self.gemini_usage[idx] += 1
                self.current_gemini_idx = (idx + 1) % len(GEMINI_API_KEYS)
                return GEMINI_API_KEYS[idx], "OK"
            self.current_gemini_idx = (idx + 1) % len(GEMINI_API_KEYS)
        return GEMINI_API_KEYS[0], "NEAR_LIMIT"

    # ------------------------------------------
    # موزع أحمال أسطول كاجل (Kaggle Fleet Failover)
    # ------------------------------------------
    def get_available_kaggle_account(self, required_mins=10):
        for _ in range(len(self.kaggle_accounts)):
            acc = self.kaggle_accounts[self.current_kaggle_idx]
            self.current_kaggle_idx = (self.current_kaggle_idx + 1) % len(self.kaggle_accounts)
            if acc["mins_remaining"] >= required_mins:
                return acc
        return None

    def deduct_kaggle_time(self, account_id, mins_used):
        for acc in self.kaggle_accounts:
            if acc["id"] == account_id:
                acc["mins_remaining"] = max(0, acc["mins_remaining"] - mins_used)

    def get_total_kaggle_mins(self):
        return sum(acc["mins_remaining"] for acc in self.kaggle_accounts)

    # ------------------------------------------
    # حفظ واستئناف الحالة في Supabase (State Management)
    # ------------------------------------------
    async def save_project_state(self, chat_id, project_data):
        headers = {
            "apikey": SUPABASE_SECRET_KEY,
            "Authorization": f"Bearer {SUPABASE_SECRET_KEY}",
            "Content-Type": "application/json",
            "Prefer": "return=representation"
        }
        payload = {
            "chat_id": str(chat_id),
            "topic": project_data.get("topic", ""),
            "mode": project_data.get("mode", "hybrid"),
            "state_json": json.dumps(project_data, ensure_ascii=False),
            "status": project_data.get("status", "paused")
        }
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{SUPABASE_URL}/rest/v1/genesis_states"
                await session.post(url, headers=headers, json=payload, timeout=15)
        except Exception:
            self.paused_tasks[chat_id] = project_data

    async def get_pending_tasks(self, chat_id):
        if chat_id in self.paused_tasks:
            return self.paused_tasks[chat_id]
        headers = {
            "apikey": SUPABASE_SECRET_KEY,
            "Authorization": f"Bearer {SUPABASE_SECRET_KEY}"
        }
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{SUPABASE_URL}/rest/v1/genesis_states?chat_id=eq.{chat_id}&status=eq.paused"
                async with session.get(url, headers=headers, timeout=15) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if data:
                            return json.loads(data[-1]["state_json"])
        except Exception:
            pass
        return None

    # ------------------------------------------
    # نظام الإشعارات والموافقات الذكي (Smart Auto-Pilot)
    # ------------------------------------------
    async def send_quota_alert(self, app, chat_id, project_data, reason="GEMINI_LIMIT"):
        await self.save_project_state(chat_id, project_data)
        
        if reason == "GEMINI_LIMIT":
            msg = (
                "⚠️ **تنبيه الإدارة الذاتية (Smart Auto-Pilot):**\n\n"
                "أوشك رصيد طلبات Gemini اليومي على النفاد (وصل إلى 90%).\n"
                "تم حفظ حالة فيلمك بالكامل في قاعدة بيانات Supabase لضمان عدم ضياع أي مشهد.\n\n"
                "كيف تفضل التصرف الآن؟"
            )
        else:
            msg = (
                "⚠️ **تنبيه أسطول السيرفرات (Kaggle GPU):**\n\n"
                "رصيد الساعات السينمائية في الحسابين أوشك على الانتهاء لهذا الأسبوع.\n"
                "تم حفظ تقدم المشروع بأمان. اختر القرار المناسب:"
            )

        buttons = InlineKeyboardMarkup([
            [InlineKeyboardButton("⏳ موافق، انتظر التجديد واستأنف تلقائياً", callback_data="quota_wait")],
            [InlineKeyboardButton("⚡ تحويل المتبقي لمحرك GitHub السريع فوراً", callback_data="quota_fast_fallback")]
        ])
        await app.send_message(chat_id, msg, reply_markup=buttons)

quota_system = QuotaAndFleetManager()
