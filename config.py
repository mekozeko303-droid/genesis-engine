import os
import itertools


def get_env(key, default=""):
    val = os.getenv(key, "")
    if val is None:
        return default
    val = val.strip()
    return val if val else default


def get_int_env(key, default):
    val = get_env(key, "")
    if val.isdigit() and int(val) > 1000:
        return int(val)
    return int(default)


class Config:
    # --- 1. إعدادات تيليجرام المعتمدة ---
    API_ID = get_int_env("TELEGRAM_API_ID", 31270154)
    _raw_hash = get_env("TELEGRAM_API_HASH", "5a056c44d67b3e3318b3f122436cf019")
    API_HASH = _raw_hash if len(_raw_hash) == 32 else "5a056c44d67b3e3318b3f122436cf019"
    BOT_TOKEN = get_env("TELEGRAM_BOT_TOKEN", "")

    # --- 2. إعدادات GitHub للتجدد الذاتي 24/7 والبيئة المعزولة ---
    GITHUB_TOKEN = get_env("GH_TOKEN", "")
    GITHUB_REPO = get_env("GITHUB_REPO", "mekozeko303-droid/genesis-engine")
    WORKFLOW_FILENAME = "main.yml"
    SANDBOX_BRANCH = "staging-sandbox"
    MAIN_BRANCH = "main"

    # --- 3. إعدادات قاعدة البيانات السحابية (Supabase) ---
    SUPABASE_URL = get_env("SUPABASE_URL", "https://maabijsnlytxewkscvam.supabase.co")
    SUPABASE_PUB_KEY = get_env("SUPABASE_PUB_KEY", "")
    SUPABASE_SECRET_KEY = get_env("SUPABASE_SECRET_KEY", "")

    # --- 4. أسطول حسابات Kaggle ---
    KAGGLE_FLEET = [
        {
            "id": "Node_1",
            "username": get_env("KAGGLE_USER_1", "mekozeko303"),
            "key": get_env("KAGGLE_KEY_1", ""),
            "weekly_quota_hours": 30.0
        },
        {
            "id": "Node_2",
            "username": get_env("KAGGLE_USER_2", "zekomeko"),
            "key": get_env("KAGGLE_KEY_2", ""),
            "weekly_quota_hours": 30.0
        }
    ]

    # --- 5. مفاتيح الذكاء الاصطناعي والوسائط ---
    GEMINI_API_KEYS = [
        k for k in [
            get_env("GEMINI_KEY_1", ""),
            get_env("GEMINI_KEY_2", ""),
            get_env("GEMINI_KEY_3", ""),
            get_env("GEMINI_KEY_4", "")
        ] if k
    ]
    HF_TOKEN = get_env("HF_TOKEN", "")
    PIXABAY_API_KEY = get_env("PIXABAY_API_KEY", "")

    # --- 6. الأوضاع الـ 17 الإمبراطورية (مع نموذج فيديو مطابق للأصل لكل وضع) ---
    DEFAULT_MODES = {
        "fast": {
            "name": "⚡ الوضع السريع",
            "engine": "github_ffmpeg",
            "cost_pct": 0.5,
            "est_time": "35 إلى 45 ثانية",
            "voice": "ar-SA-HamedNeural",
            "afilt": "atempo=1.12,equalizer=f=120:width_type=h:width=100:g=4",
            "vfilter": "eq=contrast=1.22:saturation=1.35",
            "keywords": ["سريع", "خاطف", "فيروسي", "تريند", "داينمك", "ديناميكي", "fast", "viral", "rapid"],
            "sample_topic": "أسرار النجاح السريع في عصر الذكاء الاصطناعي",
            "style": "High-contrast fast viral cuts, dynamic kinetic typography, punchy transitions",
            "desc": "فيديوهات خاطفة سريعة الإيقاع للتريندات والأخبار السريعة بدون استهلاك كاجل.",
            "sample_file_id": ""
        },
        "cinematic": {
            "name": "🎬 الوضع السينمائي",
            "engine": "kaggle_wan",
            "cost_pct": 12.0,
            "est_time": "60 إلى 90 ثانية",
            "voice": "ar-SA-HamedNeural",
            "afilt": "equalizer=f=80:width_type=h:width=80:g=6,aecho=0.8:0.88:40:0.15",
            "vfilter": "eq=contrast=1.18:saturation=1.12,unsharp=5:5:0.8:5:5:0.0",
            "keywords": ["سينمائي", "هوليوود", "فيلم", "درامي", "واقعي", "cinematic", "hollywood", "movie"],
            "sample_topic": "محقق يسير تحت المطر في شوارع مدينة مظلمة مضاءة بالنيون",
            "style": "Hollywood photorealistic 4K, dramatic anamorphic lighting, 35mm lens, shallow depth of field",
            "desc": "مشاهد درامية واقعية بهوليوود ستايل 100% AI مع ترميم الوجوه ودقة فائقة.",
            "sample_file_id": ""
        },
        "dialogue": {
            "name": "💬 الحوار التمثيلي",
            "engine": "kaggle_wan",
            "cost_pct": 10.0,
            "est_time": "60 إلى 85 ثانية",
            "voice": "ar-EG-ShakirNeural",
            "afilt": "equalizer=f=150:width_type=h:width=100:g=3",
            "vfilter": "eq=contrast=1.12:saturation=1.15",
            "keywords": ["حوار", "تمثيل", "محادثة", "شخصيتين", "dialogue", "conversation", "acting"],
            "sample_topic": "حوار فلسفي بين حكيم وشاب طموح في مقهى كلاسيكي",
            "style": "Two characters conversing, expressive facial acting, shot-reverse-shot cinematic framing",
            "desc": "مشهد تمثيلي درامي يتحدث فيه الشخصيات بأصوات بشرية معبرة.",
            "sample_file_id": ""
        },
        "news": {
            "name": "📰 الأخبار والوثائقيات",
            "engine": "hybrid_router",
            "cost_pct": 3.0,
            "est_time": "50 إلى 70 ثانية",
            "voice": "ar-SA-HamedNeural",
            "afilt": "atempo=1.05,equalizer=f=100:width_type=h:width=100:g=5",
            "vfilter": "eq=contrast=1.15:saturation=1.08",
            "keywords": ["أخبار", "اخبار", "تقرير", "مذيع", "نشرة", "صحافة", "news", "broadcast"],
            "sample_topic": "تقرير إخباري عاجل حول إطلاق الجيل الجديد من الروبوتات الذكية",
            "style": "Broadcast journalism, professional newsroom and field footage, lower-third graphics",
            "desc": "تقارير إخبارية وميدانية بصوت مذيع رسمي وإضاءة واقعية.",
            "sample_file_id": ""
        },
        "hybrid": {
            "name": "🏛️ المخرج الذكي الهجين",
            "engine": "dynamic_router",
            "cost_pct": 6.0,
            "est_time": "55 إلى 80 ثانية",
            "voice": "ar-SA-HamedNeural",
            "afilt": "equalizer=f=90:width_type=h:width=90:g=5",
            "vfilter": "eq=contrast=1.16:saturation=1.2",
            "keywords": ["هجين", "مخرج", "ذكي", "مدمج", "hybrid", "director"],
            "sample_topic": "رحلة استكشافية عبر الحضارات القديمة ومستقبل الفضاء",
            "style": "Smart mix of Hero AI shots and 4K cinematic B-Roll with unified color grading",
            "desc": "المخرج الذكي: يوزع المشاهد تلقائياً بين اللقطات الحقيقية ومشاهد الـ AI الحاسمة.",
            "sample_file_id": ""
        },
        "cloning": {
            "name": "🧬 استنساخ الوجه والحذف",
            "engine": "kaggle_face",
            "cost_pct": 8.0,
            "est_time": "45 إلى 75 ثانية",
            "voice": "ar-SA-HamedNeural",
            "afilt": "equalizer=f=100:width_type=h:width=100:g=4",
            "vfilter": "unsharp=5:5:1.2:5:5:0.0,eq=contrast=1.12:saturation=1.15",
            "keywords": ["وجه", "استنساخ", "حذف", "علامة مائية", "ترميم", "face", "clone", "watermark"],
            "sample_topic": "تقنية المسح الرقمي وترميم الملامح البشرية بدقة فائقة",
            "style": "Frame-by-frame face swap, CodeFormer restoration, and automatic watermark cropping",
            "desc": "تنظيف الفيديوهات من العلامات المائية مع ترميم جودة الوجه والملامح إطاراً بإطار.",
            "sample_file_id": ""
        },
        "stickman": {
            "name": "🖍️ الستيك مان الفيروسي",
            "engine": "flux_2d",
            "cost_pct": 1.0,
            "est_time": "40 إلى 50 ثانية",
            "voice": "ar-EG-ShakirNeural",
            "afilt": "atempo=1.08",
            "vfilter": "eq=contrast=1.25:saturation=1.3",
            "keywords": ["ستيك مان", "رجل العصا", "رسم بسيط", "stickman", "stick figure"],
            "sample_topic": "قصة ستيك مان يتعلم كيف يبني مشروعه الأول بذكاء",
            "style": "Clean 2D stickman animation style, black stick bodies, white round filled expressive faces, colorful background",
            "desc": "رسوم ستيك مان 2D الشهيرة التي تحصد ملايين المشاهدات في الشروحات والقصص.",
            "sample_file_id": ""
        },
        "anime": {
            "name": "🌸 الأنمي والمانجا",
            "engine": "flux_anime",
            "cost_pct": 2.0,
            "est_time": "45 إلى 65 ثانية",
            "voice": "ar-SA-ZariyahNeural",
            "afilt": "atempo=1.04",
            "vfilter": "eq=saturation=1.4:brightness=0.03:contrast=1.1",
            "keywords": ["أنمي", "انمي", "مانجا", "جيبلي", "ياباني", "anime", "manga", "ghibli"],
            "sample_topic": "محارب الساموراي يقف فوق تلة خضراء تحت سماء مليئة بالغيوم المرسومة",
            "style": "Studio Ghibli and Makoto Shinkai vibrant anime aesthetic, lush painted clouds, warm lighting",
            "desc": "تحريك ورسم بأسلوب الأنمي الياباني الدافئ واستوديو جيبلي.",
            "sample_file_id": ""
        },
        "kids": {
            "name": "👶 كرتون 3D للأطفال",
            "engine": "flux_3d",
            "cost_pct": 2.5,
            "est_time": "50 إلى 70 ثانية",
            "voice": "ar-SA-ZariyahNeural",
            "afilt": "atempo=1.05",
            "vfilter": "eq=saturation=1.45:brightness=0.04",
            "keywords": ["أطفال", "اطفال", "كرتون", "بيكسار", "ديزني", "ثلاثي الأبعاد", "kids", "cartoon", "pixar", "disney", "3d"],
            "sample_topic": "طفل صغير يلعب كرة القدم بحماس في ملعب أخضر مشمس بأسلوب بيكسار",
            "style": "Pixar and Disney 3D cute animation style, soft subsurface scattering, vibrant joyful colors",
            "desc": "أفلام كرتون ثلاثية الأبعاد بأسلوب ديزني وبيكسار بألوان زاهية ومبهجة.",
            "sample_file_id": ""
        },
        "story": {
            "name": "📸 استوديو الستوري والريلز",
            "engine": "github_kenburns",
            "cost_pct": 0.5,
            "est_time": "35 إلى 45 ثانية",
            "voice": "ar-SA-ZariyahNeural",
            "afilt": "atempo=1.08",
            "vfilter": "eq=contrast=1.15:saturation=1.25",
            "keywords": ["ستوري", "ريلز", "تيك توك", "شورتس", "عمودي", "story", "reels", "shorts", "tiktok"],
            "sample_topic": "جولة سريعة في أجمل المدن الذكية حول العالم",
            "style": "Vertical 9:16 dynamic pan and zoom Ken Burns effect with beat-synced audio",
            "desc": "فيديوهات ريلز وستوري عمودية سريعة مع حركات كاميرا جذابة وتعليق صوتي.",
            "sample_file_id": ""
        },
        "ads": {
            "name": "📢 مدير الإعلانات التجارية",
            "engine": "hybrid_router",
            "cost_pct": 5.0,
            "est_time": "50 إلى 70 ثانية",
            "voice": "ar-SA-HamedNeural",
            "afilt": "equalizer=f=100:width_type=h:width=100:g=5",
            "vfilter": "eq=contrast=1.2:saturation=1.25,unsharp=5:5:1.0:5:5:0.0",
            "keywords": ["إعلان", "اعلان", "تجاري", "منتج", "تسويق", "عطر", "ads", "commercial", "product"],
            "sample_topic": "إعلان فاخر لزجاجة عطر ملكية وسط قطرات الماء المتناثرة وإضاءة الاستوديو",
            "style": "Luxury commercial product cinematography, slow-motion macro shots, studio rim lighting",
            "desc": "إعلانات تجارية فاخرة للمنتجات مع إضاءة استوديو وتعليق تسويقي جذاب.",
            "sample_file_id": ""
        },
        "beatsync": {
            "name": "🎵 الإيقاع الموسيقي",
            "engine": "github_ffmpeg",
            "cost_pct": 1.0,
            "est_time": "40 إلى 55 ثانية",
            "voice": "ar-EG-ShakirNeural",
            "afilt": "atempo=1.1,equalizer=f=70:width_type=h:width=60:g=7",
            "vfilter": "eq=contrast=1.3:saturation=1.4",
            "keywords": ["موسيقى", "إيقاع", "ايقاع", "حماسي", "ايديت", "beat", "music", "edits"],
            "sample_topic": "سيارة رياضية تنطلق بسرعة البرق وسط أضواء النيون المتزامنة مع الإيقاع",
            "style": "High-energy visual cuts synchronized to bass drops and musical beats",
            "desc": "تقطيع المشاهد ومزامنتها تلقائياً مع الإيقاع الحماسي (Edits).",
            "sample_file_id": ""
        },
        "deepdive": {
            "name": "🕵️ الوثائقي العميق",
            "engine": "hybrid_router",
            "cost_pct": 4.0,
            "est_time": "55 إلى 80 ثانية",
            "voice": "ar-SA-HamedNeural",
            "afilt": "equalizer=f=85:width_type=h:width=80:g=5",
            "vfilter": "eq=contrast=1.2:saturation=0.85:brightness=-0.03",
            "keywords": ["وثائقي", "تاريخي", "عميق", "أرشيف", "حضارة", "documentary", "history", "deepdive"],
            "sample_topic": "الأسرار الهندسية المفقودة وراء بناء الأهرامات والحضارات القديمة",
            "style": "Historical archival documentary style mixed with dramatic cinematic recreations",
            "desc": "دمج الحقائق التاريخية الموثقة مع مشاهد تمثيلية بالذكاء الاصطناعي.",
            "sample_file_id": ""
        },
        "ambient": {
            "name": "🌧️ الخلفيات المريحة ASMR",
            "engine": "loop_engine",
            "cost_pct": 2.0,
            "est_time": "40 إلى 55 ثانية",
            "voice": "ar-SA-ZariyahNeural",
            "afilt": "aecho=0.8:0.88:60:0.2",
            "vfilter": "eq=brightness=-0.04:saturation=1.15",
            "keywords": ["مطر", "استرخاء", "هادئ", "طبيعة", "نوم", "ambient", "asmr", "rain", "cozy"],
            "sample_topic": "ليلة هادئة أمام المدفأة الدافئة بينما تتساقط قطرات المطر خلف النافذة",
            "style": "Cozy atmospheric rain on window, warm fireplace, seamless visual loop",
            "desc": "فيديوهات استرخاء ومطر ونار هادئة مع سرد هادئ ومريح.",
            "sample_file_id": ""
        },
        "podcast": {
            "name": "🎙️ البودكاست المرئي",
            "engine": "github_ffmpeg",
            "cost_pct": 1.0,
            "est_time": "40 إلى 50 ثانية",
            "voice": "ar-SA-HamedNeural",
            "afilt": "equalizer=f=95:width_type=h:width=90:g=6",
            "vfilter": "eq=contrast=1.18:brightness=-0.05:saturation=1.1",
            "keywords": ["بودكاست", "مايكروفون", "إذاعة", "صوتي", "استوديو", "podcast", "radio", "mic"],
            "sample_topic": "حلقة بودكاست خاصة حول كيف تتحكم في وقتك وتبني عادات القوة",
            "style": "Dark professional podcast studio aesthetic with Shure microphone and dynamic waveform",
            "desc": "تحويل الأفكار والمواضيع إلى مقاطع بودكاست مرئية بصوت إذاعي فخم.",
            "sample_file_id": ""
        },
        "explainer": {
            "name": "📈 الشرح التعليمي والتقني",
            "engine": "flux_2d",
            "cost_pct": 1.5,
            "est_time": "45 إلى 60 ثانية",
            "voice": "ar-EG-ShakirNeural",
            "afilt": "atempo=1.06",
            "vfilter": "eq=contrast=1.15:saturation=1.25",
            "keywords": ["شرح", "تعليمي", "تقني", "انفوجرافيك", "موشن", "explainer", "educational", "infographic"],
            "sample_topic": "شرح مبسط لكيفية عمل شبكات الإنترنت والأقمار الصناعية حول الأرض",
            "style": "Clean modern 2D vector motion graphics illustration, flat minimalist educational style",
            "desc": "فيديوهات تعليمية وتقنية برسوم توضيحية مبسطة (2D Illustration).",
            "sample_file_id": ""
        },
        "thriller": {
            "name": "🔥 الإثارة والغموض",
            "engine": "kaggle_wan",
            "cost_pct": 9.0,
            "est_time": "55 إلى 85 ثانية",
            "voice": "ar-SA-HamedNeural",
            "afilt": "equalizer=f=75:width_type=h:width=70:g=6,aecho=0.8:0.9:50:0.18",
            "vfilter": "eq=contrast=1.3:brightness=-0.08:saturation=0.65",
            "keywords": ["غموض", "إثارة", "اثارة", "رعب", "تشويق", "مظلم", "thriller", "mystery", "horror", "dark"],
            "sample_topic": "رجل غامض يقف وسط الضباب الكثيف في شارع مهجور يخفي سراً قديماً",
            "style": "Dark moody psychological thriller color grading, fog, eerie shadows, suspenseful framing",
            "desc": "قصص غموض ورعب وتشويق بفلاتر مظلمة وسرد صوتي غامض.",
            "sample_file_id": ""
        }
    }


class KeyRotator:
    def __init__(self):
        self.gemini_cycle = itertools.cycle(Config.GEMINI_API_KEYS) if Config.GEMINI_API_KEYS else None
        self.kaggle_cycle = itertools.cycle(Config.KAGGLE_FLEET)

    def get_gemini_key(self):
        return next(self.gemini_cycle) if self.gemini_cycle else None

    def get_kaggle_node(self):
        return next(self.kaggle_cycle)


rotator = KeyRotator()
