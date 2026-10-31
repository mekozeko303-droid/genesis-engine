import os
import itertools

class Config:
    # --- 1. إعدادات تيليجرام المعتمدة (تعمل فوراً بدون أخطاء) ---
    API_ID = int(os.getenv("TELEGRAM_API_ID") or 6)
    API_HASH = os.getenv("TELEGRAM_API_HASH") or "eb06d4abfb49dc3eeb1aeb98ae0f581e"
    BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8091724654:AAFsjE0G1lJ7N9i2K3vL4mX8pQ5wZ6y1v8s")

    # --- 2. إعدادات GitHub للتجدد الذاتي 24/7 والبيئة المعزولة (Sandbox) ---
    GITHUB_TOKEN = os.getenv("GH_TOKEN", "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")
    GITHUB_REPO = os.getenv("GITHUB_REPO", "mekozeko303-droid/genesis-engine")
    WORKFLOW_FILENAME = "main.yml"
    SANDBOX_BRANCH = "staging-sandbox"
    MAIN_BRANCH = "main"

    # --- 3. إعدادات قاعدة البيانات السحابية (Supabase) ---
    SUPABASE_URL = os.getenv("SUPABASE_URL", "https://maabijsnlytxewkscvam.supabase.co")
    SUPABASE_PUB_KEY = os.getenv("SUPABASE_PUB_KEY", "sb_publishable_XMJawz1nsssh9EQ2g3CuzA_SyyhGVLB")
    SUPABASE_SECRET_KEY = os.getenv("SUPABASE_SECRET_KEY", "sb_secret_c86h0j_iH62neK-xjNMhBA_DNe7RbEw")

    # --- 4. أسطول حسابات Kaggle (توزيع الأحمال 60 ساعة أسبوعياً) ---
    KAGGLE_FLEET = [
        {
            "id": "Node_1",
            "username": os.getenv("KAGGLE_USER_1", "mekozeko303"),
            "key": os.getenv("KAGGLE_KEY_1", "6052b08d7dedd1a70dfc09d276ca2dda"),
            "weekly_quota_hours": 30.0
        },
        {
            "id": "Node_2",
            "username": os.getenv("KAGGLE_USER_2", "zekomeko"),
            "key": os.getenv("KAGGLE_KEY_2", "f4f9fd09ecea62b09b6ba5217716d899"),
            "weekly_quota_hours": 30.0
        }
    ]

    # --- 5. مفاتيح الذكاء الاصطناعي والوسائط ---
    GEMINI_API_KEYS = [
        k for k in [
            os.getenv("GEMINI_KEY_1", ""),
            os.getenv("GEMINI_KEY_2", ""),
            os.getenv("GEMINI_KEY_3", ""),
            os.getenv("GEMINI_KEY_4", "")
        ] if k
    ]
    HF_TOKEN = os.getenv("HF_TOKEN", "")
    PIXABAY_API_KEY = os.getenv("PIXABAY_API_KEY", "")

    # --- 6. الأوضاع الـ 17 الإمبراطورية (مع صورة معاينة توضيحية لكل وضع للتذكير) ---
    DEFAULT_MODES = {
        "fast": {
            "name": "⚡ الوضع السريع",
            "engine": "github_ffmpeg",
            "cost_pct": 0.5,
            "style": "High-contrast fast viral cuts, dynamic kinetic typography, punchy transitions",
            "desc": "فيديوهات خاطفة سريعة الإيقاع للتريندات والأخبار السريعة بدون استهلاك كاجل.",
            "preview_url": "https://image.pollinations.ai/prompt/High-contrast%20fast%20viral%20video%20editing%20neon%20cyberpunk%20style?width=720&height=480&nologo=true",
            "sample_file_id": ""
        },
        "cinematic": {
            "name": "🎬 الوضع السينمائي",
            "engine": "kaggle_wan",
            "cost_pct": 12.0,
            "style": "Hollywood photorealistic 4K, dramatic anamorphic lighting, 35mm lens, shallow depth of field",
            "desc": "مشاهد درامية واقعية بهوليوود ستايل 100% AI مع ترميم الوجوه ودقة 4K.",
            "preview_url": "https://image.pollinations.ai/prompt/Hollywood%20photorealistic%204k%20cinematic%20movie%20scene%20dramatic%20lighting%20anamorphic?width=720&height=480&nologo=true",
            "sample_file_id": ""
        },
        "dialogue": {
            "name": "💬 الحوار التمثيلي",
            "engine": "kaggle_wan",
            "cost_pct": 10.0,
            "style": "Two characters conversing, expressive facial acting, shot-reverse-shot cinematic framing",
            "desc": "مشهد تمثيلي يتحدث فيه شخصيتان بالتناوب بأصوات بشرية معبرة.",
            "preview_url": "https://image.pollinations.ai/prompt/Two%20cinematic%20characters%20talking%20in%20a%20dramatic%20coffee%20shop%20film%20still?width=720&height=480&nologo=true",
            "sample_file_id": ""
        },
        "news": {
            "name": "📰 الأخبار والوثائقيات",
            "engine": "hybrid_router",
            "cost_pct": 3.0,
            "style": "Broadcast journalism, professional newsroom and field footage, lower-third graphics",
            "desc": "تقارير إخبارية وميدانية مع شريط إخباري سفلي وإضاءة واقعية.",
            "preview_url": "https://image.pollinations.ai/prompt/Modern%20breaking%20news%20broadcast%20studio%20screen%20journalism%204k?width=720&height=480&nologo=true",
            "sample_file_id": ""
        },
        "hybrid": {
            "name": "🏛️ المخرج الذكي الهجين",
            "engine": "dynamic_router",
            "cost_pct": 6.0,
            "style": "Smart mix of Hero AI shots and 4K cinematic B-Roll with unified color grading",
            "desc": "المخرج الذكي: يوزع المشاهد تلقائياً بين اللقطات الحقيقية ومشاهد الـ AI الحاسمة.",
            "preview_url": "https://image.pollinations.ai/prompt/Epic%20historical%20battle%20mixed%20with%20realistic%20nature%20cinematic%204k?width=720&height=480&nologo=true",
            "sample_file_id": ""
        },
        "cloning": {
            "name": "🧬 استنساخ الوجه والحذف",
            "engine": "kaggle_face",
            "cost_pct": 8.0,
            "style": "Frame-by-frame face swap, CodeFormer restoration, and automatic watermark cropping",
            "desc": "تنظيف الفيديوهات من العلامات المائية مع دمج الوجه إطاراً بإطار.",
            "preview_url": "https://image.pollinations.ai/prompt/Futuristic%20digital%20face%20scanning%20biometric%20cloning%20hologram%20cinema?width=720&height=480&nologo=true",
            "sample_file_id": ""
        },
        "stickman": {
            "name": "🖍️ الستيك مان الفيروسي",
            "engine": "flux_2d",
            "cost_pct": 1.0,
            "style": "Clean 2D stickman animation style, black stick bodies, white round filled expressive faces, colorful background",
            "desc": "رسوم ستيك مان 2D الشهيرة التي تحصد ملايين المشاهدات في الشروحات والقصص[span_1](start_span)[span_1](end_span).",
            "preview_url": "https://image.pollinations.ai/prompt/Clean%202D%20stickman%20cartoon%20character%20with%20white%20round%20head%20and%20black%20stick%20body%20in%20forest?width=720&height=480&nologo=true",
            "sample_file_id": ""
        },
        "anime": {
            "name": "🌸 الأنمي والمانجا",
            "engine": "flux_anime",
            "cost_pct": 2.0,
            "style": "Studio Ghibli and Makoto Shinkai vibrant anime aesthetic, lush painted clouds, warm lighting",
            "desc": "تحريك ورسم بأسلوب الأنمي الياباني الدافئ واستوديو جيبلي[span_2](start_span)[span_2](end_span).",
            "preview_url": "https://image.pollinations.ai/prompt/Studio%20Ghibli%20anime%20style%20scenic%20green%20meadow%20and%20dramatic%20clouds?width=720&height=480&nologo=true",
            "sample_file_id": ""
        },
        "kids": {
            "name": "👶 كرتون 3D للأطفال",
            "engine": "flux_3d",
            "cost_pct": 2.5,
            "style": "Pixar and Disney 3D cute animation style, soft subsurface scattering, vibrant joyful colors",
            "desc": "أفلام كرتون ثلاثية الأبعاد بأسلوب ديزني وبيكسار بألوان زاهية[span_3](start_span)[span_3](end_span).",
            "preview_url": "https://image.pollinations.ai/prompt/Pixar%20Disney%203d%20cute%20animated%20character%20in%20magical%20forest%20vibrant?width=720&height=480&nologo=true",
            "sample_file_id": ""
        },
        "story": {
            "name": "📸 استوديو الستوري والريلز",
            "engine": "github_kenburns",
            "cost_pct": 0.5,
            "style": "Vertical 9:16 dynamic pan and zoom Ken Burns effect with beat-synced audio",
            "desc": "تحويل صورك الشخصية أو صور منتجاتك إلى ريلز عمودي مع حركات كاميرا وموسيقى.",
            "preview_url": "https://image.pollinations.ai/prompt/Vertical%20social%20media%20reels%20aesthetic%20photography%20studio%20lighting?width=720&height=480&nologo=true",
            "sample_file_id": ""
        },
        "ads": {
            "name": "📢 مدير الإعلانات التجارية",
            "engine": "hybrid_router",
            "cost_pct": 5.0,
            "style": "Luxury commercial product cinematography, slow-motion macro shots, studio rim lighting",
            "desc": "إعلانات تجارية فاخرة للمنتجات مع إضاءة استوديو ومؤثرات جذابة[span_4](start_span)[span_4](end_span).",
            "preview_url": "https://image.pollinations.ai/prompt/Luxury%20perfume%20bottle%20commercial%20product%20shot%20water%20splash%20studio%20lighting?width=720&height=480&nologo=true",
            "sample_file_id": ""
        },
        "beatsync": {
            "name": "🎵 الإيقاع الموسيقي",
            "engine": "github_ffmpeg",
            "cost_pct": 1.0,
            "style": "High-energy visual cuts synchronized to bass drops and musical beats",
            "desc": "تقطيع المشاهد ومزامنتها تلقائياً مع دقات الموسيقى الحماسية (Edits).",
            "preview_url": "https://image.pollinations.ai/prompt/Music%20equalizer%20bass%20drop%20neon%20concert%20visuals%204k?width=720&height=480&nologo=true",
            "sample_file_id": ""
        },
        "deepdive": {
            "name": "🕵️ الوثائقي العميق",
            "engine": "hybrid_router",
            "cost_pct": 4.0,
            "style": "Historical archival documentary style mixed with dramatic cinematic recreations",
            "desc": "دمج الحقائق التاريخية الموثقة من الموسوعات مع مشاهد تمثيلية بالذكاء الاصطناعي.",
            "preview_url": "https://image.pollinations.ai/prompt/Ancient%20history%20documentary%20archival%20map%20and%20cinematic%20pharaoh%20temple?width=720&height=480&nologo=true",
            "sample_file_id": ""
        },
        "ambient": {
            "name": "🌧️ الخلفيات المريحة ASMR",
            "engine": "loop_engine",
            "cost_pct": 2.0,
            "style": "Cozy atmospheric rain on window, warm fireplace, seamless visual loop",
            "desc": "فيديوهات استرخاء ومطر ونار هادئة مع أصوات طبيعة مريحة.",
            "preview_url": "https://image.pollinations.ai/prompt/Cozy%20cabin%20fireplace%20with%20rain%20outside%20window%20night%20lofi%20aesthetic?width=720&height=480&nologo=true",
            "sample_file_id": ""
        },
        "podcast": {
            "name": "🎙️ البودكاست المرئي",
            "engine": "github_ffmpeg",
            "cost_pct": 1.0,
            "style": "Dark professional podcast studio aesthetic with Shure microphone and dynamic waveform",
            "desc": "تحويل النصوص والمقالات إلى مقاطع بودكاست مرئية مع موجات صوتية.",
            "preview_url": "https://image.pollinations.ai/prompt/Dark%20moody%20podcast%20studio%20microphone%20neon%20sign%20cinematic?width=720&height=480&nologo=true",
            "sample_file_id": ""
        },
        "explainer": {
            "name": "📈 الشرح التعليمي والتقني",
            "engine": "flux_2d",
            "cost_pct": 1.5,
            "style": "Clean modern 2D vector motion graphics illustration, flat minimalist educational style",
            "desc": "فيديوهات تعليمية وتقنية برسوم توضيحية مبسطة (2D Illustration)[span_5](start_span)[span_5](end_span).",
            "preview_url": "https://image.pollinations.ai/prompt/Clean%202D%20vector%20illustration%20educational%20infographic%20design%20minimalist?width=720&height=480&nologo=true",
            "sample_file_id": ""
        },
        "thriller": {
            "name": "🔥 الإثارة والغموض",
            "engine": "kaggle_wan",
            "cost_pct": 9.0,
            "style": "Dark moody psychological thriller color grading, fog, eerie shadows, suspenseful framing",
            "desc": "قصص غموض ورعب وتشويق بفلاتر مظلمة ومؤثرات صوتية مرعبة.",
            "preview_url": "https://image.pollinations.ai/prompt/Dark%20mysterious%20foggy%20street%20silhouette%20thriller%20movie%20scene%204k?width=720&height=480&nologo=true",
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
