import os

# ==========================================
# 1. إعدادات تيليجرام (Pyrogram)
# ==========================================
TELEGRAM_API_ID = 31270154
TELEGRAM_API_HASH = "5a056c44d67b3e3318b3f122436cf019"
TELEGRAM_BOT_TOKEN = "9093676549:AAEvZHvi_Vr_M65A1oYdmDHRoJtB2LFmlis"

# ==========================================
# 2. أسطول خوادم كاجل (Kaggle Fleet)
# ==========================================
KAGGLE_FLEET = [
    {
        "id": "kaggle_1",
        "username": "zekomeko",
        "key": "02a28b3f438e7083cb81822896c2952a",
        "mins_remaining": 1800
    },
    {
        "id": "kaggle_2",
        "username": "mekozeko303",
        "key": "16ff7d7940338dacd288a7fceee0b47e",
        "mins_remaining": 1800
    }
]

# ==========================================
# 3. قاعدة البيانات السحابية (Supabase)
# ==========================================
SUPABASE_URL = "https://maabijsnlytxewkscvam.supabase.co"
SUPABASE_PUBLISHABLE_KEY = "sb_publishable_XMJawz1nsssh9EQ2g3CuzA_SyyhGVLB"
SUPABASE_SECRET_KEY = "sb_secret_c86h0j_iH62neK-xjNMhBA_DNe7RbEw"

# ==========================================
# 4. مفاتيح الذكاء الاصطناعي والنماذج والوسائط
# ==========================================
HF_TOKEN = "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"

# مفتاحان للتناوب (Load Balancing) لتجنب حظر Gemini
GEMINI_API_KEYS = [
    "AIzaSyDDC8V4JzUDqSMm9JRO4xckLF889ftfY6g",
    "AQ.Ab8RN6ICU0MCQpfvOg4DLdhG2XxNPPp_Fe3vn6kqbkIXsW-e2Q"
]

PIXABAY_API_KEY = "58313642-74c3e2c37ac5e866948e83ef1"

# ==========================================
# 5. إعدادات النظام والأوضاع السبعة
# ==========================================
PRODUCTION_MODES = {
    "fast": "⚡ الوضع السريع (وثائقي/أخبار سريعة)",
    "cinematic": "🎬 الوضع السينمائي (أفلام ذكاء اصطناعي 100%)",
    "dialogue": "🗣️ وضع الحوار (شخصيات متعددة)",
    "news": "📰 استوديو الأخبار والتقارير",
    "hybrid": "🧠 المخرج الذكي (هجين ديناميكي بلا نسب ثابتة)",
    "cloning": "🧬 استنساخ الوجه والصوت (Face Swap & Lip-Sync)",
    "ads": "📢 مدير الإعلانات التجارية (Ad Manager)"
}

MAX_DEBATE_ROUNDS = 3
MAX_SELF_HEAL_RETRIES = 5
GEMINI_DAILY_LIMIT_PER_KEY = 1500
