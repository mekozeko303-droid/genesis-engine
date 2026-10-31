import os

# ==========================================
# 1. إعدادات تيليجرام والحماية (Pyrogram)
# ==========================================
TELEGRAM_API_ID = 31270154
TELEGRAM_API_HASH = "5a056c44d67b3e3318b3f122436cf019"
TELEGRAM_BOT_TOKEN = "9093676549:AAEvZHvi_Vr_M65A1oYdmDHRoJtB2LFmlis"

AUTHORIZED_USERS = []

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

GEMINI_API_KEYS = [
    "AIzaSyDDC8V4JzUDqSMm9JRO4xckLF889ftfY6g",
    "AQ.Ab8RN6LgUo-RsNiuvISI1EemwlA0I5eht83u2FKGDoxyoGzcJg",
    "AQ.Ab8RN6KxKDz4kA_DK_64HlQeWrcv7CQAmlqSazzvc5SGgYtFDQ"
]

PIXABAY_API_KEY = "58313642-74c3e2c37ac5e866948e83ef1"

# ==========================================
# 5. الأوضاع التسعة الشاملة (بما فيها الستوري والكرتون)
# ==========================================
PRODUCTION_MODES = {
    "cinematic": "🎬 سينمائي 100% (هوليوود واقعي)",
    "hybrid": "🧠 المخرج الذكي (هجين ديناميكي)",
    "kids": "👶 كرتون وأنيميشن 3D (Pixar)",
    "story": "📸 ستوري وريلز صوري (بدون تشويه)",
    "dialogue": "🗣️ حوار تمثيلي (رجل وامرأة)",
    "news": "📰 استوديو الأخبار والوثائقيات",
    "fast": "⚡ الوضع السريع (إنتاج خاطف)",
    "ads": "📢 مدير الإعلانات التجارية",
    "cloning": "🧬 استنساخ الوجه والصوت"
}

# ==========================================
# 6. اللغات والأصوات البشرية العصبية (Neural Voices)
# ==========================================
SUPPORTED_LANGUAGES = {
    "ar": {
        "name": "🇸🇦 العربية الفصحى (صوت بشري سينمائي)",
        "male_voice": "ar-SA-HamedNeural",
        "female_voice": "ar-EG-SalmaNeural",
        "kids_voice": "ar-AE-FatimaNeural",
        "rate": "-2%",
        "pitch": "-1Hz"
    },
    "ar_ye": {
        "name": "🇾🇪 اللهجة اليمنية (صوت طبيعي)",
        "male_voice": "ar-YE-SalehNeural",
        "female_voice": "ar-YE-MaryamNeural",
        "kids_voice": "ar-YE-MaryamNeural",
        "rate": "+0%",
        "pitch": "+0Hz"
    },
    "ar_f": {
        "name": "🎙️ العربية (صوت نسائي إعلاني دافئ)",
        "male_voice": "ar-EG-SalmaNeural",
        "female_voice": "ar-SA-ZariyahNeural",
        "kids_voice": "ar-AE-FatimaNeural",
        "rate": "+0%",
        "pitch": "+0Hz"
    },
    "en": {
        "name": "🇺🇸 English (Hollywood Realistic)",
        "male_voice": "en-US-AndrewMultilingualNeural",
        "female_voice": "en-US-AvaMultilingualNeural",
        "kids_voice": "en-US-AnaNeural",
        "rate": "+0%",
        "pitch": "+0Hz"
    },
    "fr": {
        "name": "🇫🇷 Français (Voix Humaine)",
        "male_voice": "fr-FR-RemyMultilingualNeural",
        "female_voice": "fr-FR-VivienneMultilingualNeural",
        "kids_voice": "fr-FR-EloiseNeural",
        "rate": "+0%",
        "pitch": "+0Hz"
    },
    "es": {
        "name": "🇪🇸 Español (Voz Realista)",
        "male_voice": "es-ES-AlvaroNeural",
        "female_voice": "es-ES-ElviraNeural",
        "kids_voice": "es-MX-MarinaNeural",
        "rate": "+0%",
        "pitch": "+0Hz"
    },
    "tr": {
        "name": "🇹🇷 Türkçe (Gerçekçi Ses)",
        "male_voice": "tr-TR-AhmetNeural",
        "female_voice": "tr-TR-EmelNeural",
        "kids_voice": "tr-TR-EmelNeural",
        "rate": "+0%",
        "pitch": "+0Hz"
    }
}

MAX_DEBATE_ROUNDS = 3
MAX_SELF_HEAL_RETRIES = 5
GEMINI_DAILY_LIMIT_PER_KEY = 1500
