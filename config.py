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
    GITHUB_TOKEN = get_env("GITHUB_TOKEN", "") or get_env("GH_TOKEN", "")
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

    # --- 6. الأوضاع الـ 17 الإمبراطورية ---
    DEFAULT_MODES = {
        "fast": {
            "name": "⚡ الوضع السريع",
            "engine": "github_ffmpeg",
            "cost_pct": 0.5,
            "est_time": "30 إلى 45 ثانية",
            "voice": "ar-SA-HamedNeural",
            "afilt": "atempo=1.10",
            "vfilter": "eq=contrast=1.18:saturation=1.28",
            "keywords": ["سريع", "خاطف", "فيروسي", "تريند", "داينمك", "ديناميكي", "fast", "viral", "rapid"],
            "sample_topic": "سباق سيارات نيون مستقبلي يخترق شوارع طوكيو المضيئة بسرعة البرق",
            "style": "High-contrast fast viral action shot, dynamic neon rim lighting, ultra-sharp 8k",
            "desc": "فيديوهات خاطفة سريعة الإيقاع للتريندات والأخبار السريعة بدون استهلاك كاجل.",
            "sample_file_id": ""
        },
        "cinematic": {
            "name": "🎬 الوضع السينمائي",
            "engine": "kaggle_wan",
            "cost_pct": 12.0,
            "est_time": "45 إلى 70 ثانية",
            "voice": "ar-SA-HamedNeural",
            "afilt": "atempo=1.02",
            "vfilter": "eq=contrast=1.16:saturation=1.10",
            "keywords": ["سينمائي", "هوليوود", "فيلم", "درامي", "واقعي", "بشري", "cinematic", "hollywood", "movie"],
            "sample_topic": "محقق بشري واقعي يسير تحت المطر الغزير في شوارع مدينة مظلمة مضاءة بالنيون",
            "style": "Hollywood IMAX 70mm photorealistic movie still, real human actors, dramatic anamorphic lighting, 35mm lens",
            "desc": "مشاهد درامية واقعية بهوليوود ستايل 100% AI مع ملامح بشرية حقيقية ودقة فائقة.",
            "sample_file_id": ""
        },
        "dialogue": {
            "name": "💬 الحوار التمثيلي",
            "engine": "kaggle_wan",
            "cost_pct": 10.0,
            "est_time": "45 إلى 65 ثانية",
            "voice": "ar-EG-ShakirNeural",
            "afilt": "atempo=1.04",
            "vfilter": "eq=contrast=1.10:saturation=1.12",
            "keywords": ["حوار", "تمثيل", "محادثة", "شخصيتين", "dialogue", "conversation", "acting"],
            "sample_topic": "حوار درامي بين رجلين داخل مقهى خشبي كلاسيكي دافئ",
            "style": "Cinematic movie dialogue frame, two expressive realistic characters conversing, warm bokeh lighting",
            "desc": "مشهد تمثيلي درامي يتحدث فيه الشخصيات بأصوات بشرية معبرة.",
            "sample_file_id": ""
        },
        "news": {
            "name": "📰 الأخبار والوثائقيات",
            "engine": "hybrid_router",
            "cost_pct": 3.0,
            "est_time": "40 إلى 55 ثانية",
            "voice": "ar-SA-HamedNeural",
            "afilt": "atempo=1.06",
            "vfilter": "eq=contrast=1.12:saturation=1.05",
            "keywords": ["أخبار", "اخبار", "تقرير", "مذيع", "نشرة", "صحافة", "news", "broadcast"],
            "sample_topic": "مذيع أخبار تلفزيوني يقدم تقريراً عاجلاً أمام شاشة استوديو عالمية",
            "style": "Live 4K television news broadcast studio and field photojournalism, crisp realistic lighting",
            "desc": "تقارير إخبارية وميدانية بصوت مذيع رسمي وإضاءة واقعية.",
            "sample_file_id": ""
        },
        "hybrid": {
            "name": "🏛️ المخرج الذكي الهجين",
            "engine": "dynamic_router",
            "cost_pct": 6.0,
            "est_time": "45 إلى 65 ثانية",
            "voice": "ar-SA-HamedNeural",
            "afilt": "atempo=1.05",
            "vfilter": "eq=contrast=1.15:saturation=1.18",
            "keywords": ["هجين", "مخرج", "ذكي", "مدمج", "hybrid", "director"],
            "sample_topic": "معبد فرعوني ذهبي عملاق يفتح بواباته تحت سماء مليئة بالنجوم والمجرات",
            "style": "Epic blockbuster visual combining photorealistic historical grandeur and modern cinema lighting, 8k",
            "desc": "المخرج الذكي: يوزع المشاهد تلقائياً بين اللقطات الواقعية ومشاهد الـ AI الحاسمة.",
            "sample_file_id": ""
        },
        "cloning": {
            "name": "🧬 استنساخ الوجه والحذف",
            "engine": "kaggle_face",
            "cost_pct": 8.0,
            "est_time": "35 إلى 60 ثانية",
            "voice": "ar-SA-HamedNeural",
            "afilt": "atempo=1.04",
            "vfilter": "eq=contrast=1.12:saturation=1.15",
            "keywords": ["وجه", "استنساخ", "حذف", "علامة مائية", "ترميم", "face", "clone", "watermark"],
            "sample_topic": "مهندس ذكاء اصطناعي يفحص هولوجرام ثلاثي الأبعاد لوجه بشري فائق الدقة",
            "style": "Ultra-detailed photorealistic human portrait, biometric hologram scanning, crystal clear skin texture",
            "desc": "أرسل أي فيديو هنا ليقوم الوكيل بقص العلامات المائية منه وترميم الجودة والملامح فوراً.",
            "sample_file_id": ""
        },
        "stickman": {
            "name": "🖍️ الستيك مان الفيروسي",
            "engine": "flux_2d",
            "cost_pct": 1.0,
            "est_time": "35 إلى 45 ثانية",
            "voice": "ar-EG-ShakirNeural",
            "afilt": "atempo=1.08",
            "vfilter": "eq=contrast=1.22:saturation=1.25",
            "keywords": ["ستيك مان", "رجل العصا", "رسم بسيط", "stickman", "stick figure"],
            "sample_topic": "شخصية ستيك مان كرتونية تبني صاروخاً فضائياً فوق تلة خضراء",
            "style": "Clean 2D viral stickman animation style, black stick body, round white expressive head, flat colorful background",
            "desc": "رسوم ستيك مان 2D الشهيرة التي تحصد ملايين المشاهدات في الشروحات والقصص.",
            "sample_file_id": ""
        },
        "anime": {
            "name": "🌸 الأنمي والمانجا",
            "engine": "flux_anime",
            "cost_pct": 2.0,
            "est_time": "40 إلى 55 ثانية",
            "voice": "ar-SA-ZariyahNeural",
            "afilt": "atempo=1.05",
            "vfilter": "eq=saturation=1.35:contrast=1.10",
            "keywords": ["أنمي", "انمي", "مانجا", "جيبلي", "ياباني", "anime", "manga", "ghibli"],
            "sample_topic": "محارب أنمي ياباني يقف فوق جرف أخضر تحت سماء غروب ملونة بالغيوم",
            "style": "Masterpiece Japanese Anime frame, Studio Ghibli and Makoto Shinkai vibrant cel-shaded style, lush clouds",
            "desc": "تحريك ورسم بأسلوب الأنمي الياباني الدافئ واستوديو جيبلي.",
            "sample_file_id": ""
        },
        "kids": {
            "name": "👶 كرتون 3D للأطفال",
            "engine": "flux_3d",
            "cost_pct": 2.5,
            "est_time": "40 إلى 55 ثانية",
            "voice": "ar-SA-ZariyahNeural",
            "afilt": "atempo=1.06",
            "vfilter": "eq=saturation=1.38:contrast=1.08",
            "keywords": ["أطفال", "اطفال", "كرتون", "بيكسار", "ديزني", "ثلاثي الأبعاد", "kids", "cartoon", "pixar", "disney", "3d"],
            "sample_topic": "طفل كرتوني ثلاثي الأبعاد بأسلوب بيكسار يركل كرة القدم بحماس في ملعب أخضر مشمس",
            "style": "Cute Disney Pixar 3D animated movie frame, adorable expressive 3D cartoon characters, joyful bright colors, Unreal Engine 5",
            "desc": "أفلام كرتون ثلاثية الأبعاد بأسلوب ديزني وبيكسار وماين كرافت بألوان زاهية ومبهجة.",
            "sample_file_id": ""
        },
        "story": {
            "name": "📸 استوديو الستوري والريلز",
            "engine": "github_kenburns",
            "cost_pct": 0.5,
            "est_time": "30 إلى 45 ثانية",
            "voice": "ar-SA-ZariyahNeural",
            "afilt": "atempo=1.08",
            "vfilter": "eq=contrast=1.14:saturation=1.22",
            "keywords": ["ستوري", "ريلز", "تيك توك", "شورتس", "عمودي", "story", "reels", "shorts", "tiktok", "pov"],
            "sample_topic": "جولة منظور الشخص الأول POV داخل بيت سبونج بوب الكرتوني المصنوع في الواقع",
            "style": "First-person POV realistic handheld camera entering a famous cartoon house in real life, hyper-realistic textures, 9:16 vertical",
            "desc": "فيديوهات ريلز وستوري عمودية بأسلوب POV الواقعي وحركات الكاميرا الجذابة.",
            "sample_file_id": ""
        },
        "ads": {
            "name": "📢 مدير الإعلانات التجارية",
            "engine": "hybrid_router",
            "cost_pct": 5.0,
            "est_time": "40 إلى 55 ثانية",
            "voice": "ar-SA-HamedNeural",
            "afilt": "atempo=1.05",
            "vfilter": "eq=contrast=1.18:saturation=1.22",
            "keywords": ["إعلان", "اعلان", "تجاري", "منتج", "تسويق", "عطر", "ads", "commercial", "product"],
            "sample_topic": "زجاجة عطر ذهبية فاخرة تتطاير حولها قطرات الماء الكريستالية وإضاءة الاستوديو",
            "style": "Luxury commercial product cinematography, slow-motion water droplets, dramatic studio rim lighting, macro 4k",
            "desc": "إعلانات تجارية فاخرة للمنتجات مع إضاءة استوديو وتعليق تسويقي جذاب.",
            "sample_file_id": ""
        },
        "beatsync": {
            "name": "🎵 الإيقاع الموسيقي",
            "engine": "github_ffmpeg",
            "cost_pct": 1.0,
            "est_time": "35 إلى 50 ثانية",
            "voice": "ar-EG-ShakirNeural",
            "afilt": "atempo=1.10",
            "vfilter": "eq=contrast=1.25:saturation=1.35",
            "keywords": ["موسيقى", "إيقاع", "ايقاع", "حماسي", "ايديت", "beat", "music", "edits"],
            "sample_topic": "سيارة رياضية سوداء تنزلق بدخان الإطارات وسط أضواء النيون البنفسجية",
            "style": "High-energy drift car edit, motion blur, purple and cyan neon reflections, aggressive wide-angle lens",
            "desc": "تقطيع المشاهد ومزامنتها تلقائياً مع الإيقاع الحماسي (Edits).",
            "sample_file_id": ""
        },
        "deepdive": {
            "name": "🕵️ الوثائقي العميق",
            "engine": "hybrid_router",
            "cost_pct": 4.0,
            "est_time": "45 إلى 65 ثانية",
            "voice": "ar-SA-HamedNeural",
            "afilt": "atempo=1.02",
            "vfilter": "eq=contrast=1.18:saturation=0.88",
            "keywords": ["وثائقي", "تاريخي", "عميق", "أرشيف", "حضارة", "documentary", "history", "deepdive"],
            "sample_topic": "عمال الفراعنة القدماء يرفعون المسلات الحجرية العملاقة في الصحراء الذهبية",
            "style": "National Geographic historical documentary recreation, dramatic chiaroscuro lighting, authentic ancient textures",
            "desc": "دمج الحقائق التاريخية الموثقة مع مشاهد تمثيلية بالذكاء الاصطناعي.",
            "sample_file_id": ""
        },
        "ambient": {
            "name": "🌧️ الخلفيات المريحة ASMR",
            "engine": "loop_engine",
            "cost_pct": 2.0,
            "est_time": "35 إلى 50 ثانية",
            "voice": "ar-SA-ZariyahNeural",
            "afilt": "atempo=0.98",
            "vfilter": "eq=saturation=1.15",
            "keywords": ["مطر", "استرخاء", "هادئ", "طبيعة", "نوم", "ambient", "asmr", "rain", "cozy"],
            "sample_topic": "غرفة كابينة خشبية دافئة مع مدفأة مشتعلة بينما تتساقط قطرات المطر خلف النافذة ليلاً",
            "style": "Cozy atmospheric lo-fi cabin, warm fireplace glow, raindrops on glass window, peaceful night mood",
            "desc": "فيديوهات استرخاء ومطر ونار هادئة مع سرد هادئ ومريح.",
            "sample_file_id": ""
        },
        "podcast": {
            "name": "🎙️ البودكاست المرئي",
            "engine": "github_ffmpeg",
            "cost_pct": 1.0,
            "est_time": "35 إلى 45 ثانية",
            "voice": "ar-SA-HamedNeural",
            "afilt": "atempo=1.04",
            "vfilter": "eq=contrast=1.15:saturation=1.10",
            "keywords": ["بودكاست", "مايكروفون", "إذاعة", "صوتي", "استوديو", "podcast", "radio", "mic"],
            "sample_topic": "مذيع بودكاست يتحدث أمام مايكروفون احترافي في استوديو مظلم بإضاءة نيون دافئة",
            "style": "Professional dark moody podcast studio, close-up Shure SM7B microphone, warm neon sign, cinematic depth",
            "desc": "تحويل الأفكار والمواضيع إلى مقاطع بودكاست مرئية بصوت إذاعي فخم.",
            "sample_file_id": ""
        },
        "explainer": {
            "name": "📈 الشرح التعليمي والتقني",
            "engine": "flux_2d",
            "cost_pct": 1.5,
            "est_time": "40 إلى 55 ثانية",
            "voice": "ar-EG-ShakirNeural",
            "afilt": "atempo=1.06",
            "vfilter": "eq=contrast=1.15:saturation=1.25",
            "keywords": ["شرح", "تعليمي", "تقني", "انفوجرافيك", "موشن", "explainer", "educational", "infographic"],
            "sample_topic": "أقمار صناعية تدور حول الكرة الأرضية وترسل حزم بيانات مضيئة بأسلوب انفوجرافيك",
            "style": "Clean modern 2D flat vector motion graphics illustration, Kurzgesagt educational style, vibrant geometric shapes",
            "desc": "فيديوهات تعليمية وتقنية برسوم توضيحية مبسطة (2D Illustration).",
            "sample_file_id": ""
        },
        "thriller": {
            "name": "🔥 الإثارة والغموض",
            "engine": "kaggle_wan",
            "cost_pct": 9.0,
            "est_time": "45 إلى 65 ثانية",
            "voice": "ar-SA-HamedNeural",
            "afilt": "atempo=1.00",
            "vfilter": "eq=contrast=1.25:saturation=0.70",
            "keywords": ["غموض", "إثارة", "اثارة", "رعب", "تشويق", "مظلم", "thriller", "mystery", "horror", "dark"],
            "sample_topic": "ظل رجل غامض يقف تحت عمود إنارة يرتجف وسط الضباب الكثيف في زقاق مظلم",
            "style": "Dark psychological horror thriller cinematography, thick volumetric fog, eerie silhouettes, cold shadow grading",
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
