import os

# ==========================================
# 1. إعدادات تيليجرام (Pyrogram - دعم حتى 2GB)
# ==========================================
TELEGRAM_API_ID = int(os.environ.get("TELEGRAM_API_ID", "31270154"))
TELEGRAM_API_HASH = os.environ.get("TELEGRAM_API_HASH", "5a056c44d67b3e3318b3f122436cf019")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "PUT_YOUR_BOT_TOKEN_HERE")

# ==========================================
# 2. أسطول خوادم كاجل (Kaggle Fleet - 60 ساعة GPU)
# ==========================================
KAGGLE_FLEET = [
    {
        "id": "kaggle_1",
        "username": os.environ.get("KAGGLE_USER_1", "zekomeko"),
        "key": os.environ.get("KAGGLE_KEY_1", "02a28b3f438e7083cb81822896c2952a"),
        "mins_remaining": 1800  # 30 ساعة أسبوعياً
    },
    {
        "id": "kaggle_2",
        "username": os.environ.get("KAGGLE_USER_2", "mekozeko303"),
        "key": os.environ.get("KAGGLE_KEY_2", "16ff7d7940338dacd288a7fceee0b47e"),
        "mins_remaining": 1800  # 30 ساعة أسبوعياً
    }
]

# ==========================================
# 3. قاعدة البيانات السحابية (Supabase State & Vector RAG)
# ==========================================
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://maabijsnlytxewkscvam.supabase.co")
SUPABASE_PUBLISHABLE_KEY = os.environ.get("SUPABASE_KEY", "sb_publishable_XMJawz1nsssh9EQ2g3CuzA_SyyhGVLB")
SUPABASE_SECRET_KEY = os.environ.get("SUPABASE_SECRET_KEY", "sb_secret_c86h0j_iH62neK-xjNMhBA_DNe7RbEw")

# ==========================================
# 4. مفاتيح الذكاء الاصطناعي والنماذج والوسائط
# ==========================================
HF_TOKEN = os.environ.get("HF_TOKEN", "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")

# دعم التناوب بين مفتاحين لـ Gemini (3000 طلب يومياً)
GEMINI_API_KEYS = [
    os.environ.get("GEMINI_API_KEY_1", "PUT_GEMINI_KEY_1_HERE"),
    os.environ.get("GEMINI_API_KEY_2", "PUT_GEMINI_KEY_2_HERE")
]

PIXABAY_API_KEY = os.environ.get("PIXABAY_API_KEY", "PUT_PIXABAY_KEY_HERE")

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
