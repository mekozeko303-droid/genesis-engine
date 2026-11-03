# -*- coding: utf-8 -*-
import os
from dataclasses import dataclass
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
SAMPLES_DIR = DATA_DIR / "samples"
TEMP_DIR = Path("/tmp/genesis_studio")

DATA_DIR.mkdir(parents=True, exist_ok=True)
SAMPLES_DIR.mkdir(parents=True, exist_ok=True)
TEMP_DIR.mkdir(parents=True, exist_ok=True)


def _env(keys: list[str], default: str = "") -> str:
    for k in keys:
        val = os.getenv(k, "").strip()
        if val:
            return val
    return default


API_ID = int(_env(["TELEGRAM_API_ID", "API_ID"], "31270154"))
API_HASH = _env(["TELEGRAM_API_HASH", "API_HASH"], "")
BOT_TOKEN = _env(["TELEGRAM_BOT_TOKEN", "BOT_TOKEN"], "")

_raw_admins = _env(["ADMIN_IDS", "ADMIN_ID"], "9165452838")
ADMIN_IDS: set[int] = {int(x.strip()) for x in _raw_admins.split(",") if x.strip().isdigit()}

HF_TOKEN = _env(["HF_TOKEN", "HUGGINGFACE_TOKEN"], "")
PIXABAY_API_KEY = _env(["PIXABAY_API_KEY", "PIXABAY_KEY"], "")
SUPABASE_URL = _env(["SUPABASE_URL"], "")
SUPABASE_KEY = _env(["SUPABASE_SECRET_KEY", "SUPABASE_KEY", "SUPABASE_PUB_KEY"], "")

MAX_CONCURRENT_JOBS = 2
JOB_TIMEOUT = 1800
DAILY_LIMIT = 20
MIN_IDEA_CHARS = 4
MAX_IDEA_CHARS = 4000

DURATIONS = {
    30: "⏱ 30 ثانية (شورتس خاطف)",
    60: "⏱ 1 دقيقة (ريلز قياسي)",
    180: "⏱ 3 دقائق (قصة كاملة)",
    300: "⏱ 5 دقائق (تقرير مفصل)",
    600: "⏱ 10 دقائق (حلقة كاملة)",
}


@dataclass(frozen=True)
class Mode:
    id: str
    name_ar: str
    emoji: str
    engine: str
    voice: str
    voice_rate: str
    vfilter: str
    style_en: str
    pixabay_q: str
    desc_ar: str
    sample_idea: str


MODES: dict[str, Mode] = {
    "drama_3d": Mode(
        id="drama_3d",
        name_ar="الدراما الشعبية المجسمة 3D",
        emoji="🐃",
        engine="ai_character",
        voice="ar-IQ-BasselNeural",
        voice_rate="-2%",
        vfilter="eq=contrast=1.18:saturation=1.12",
        style_en="3D anthropomorphic character wearing traditional Middle Eastern work clothes in a dusty alley, crying expressive eyes, cinematic Unreal Engine 5 render",
        pixabay_q="desert village alley dramatic",
        desc_ar="قصص درامية وشعبية بأسلوب مجسم 3D تعبيري باللهجة العراقية والعربية المؤثرة.",
        sample_idea="شخصية شعبية تبكي بحرقة على صديقها في حارة قديمة"
    ),
    "cinematic": Mode(
        id="cinematic",
        name_ar="الأفلام السينمائية الواقعية",
        emoji="🎬",
        engine="ai_character",
        voice="ar-SA-HamedNeural",
        voice_rate="-4%",
        vfilter="eq=contrast=1.20:saturation=1.10",
        style_en="Hollywood IMAX 70mm photorealistic movie frame, real human actors, dramatic anamorphic lighting, 35mm lens",
        pixabay_q="cinematic city night rain",
        desc_ar="مشاهد درامية واقعية بهوليوود ستايل مع ملامح بشرية حقيقية ودقة فائقة.",
        sample_idea="محقق يمشي تحت المطر في شوارع مظلمة ويكتشف سراً خطيراً"
    ),
    "kids": Mode(
        id="kids",
        name_ar="كرتون بيكسار وديزني 3D",
        emoji="👶",
        engine="ai_character",
        voice="ar-SA-ZariyahNeural",
        voice_rate="+2%",
        vfilter="eq=saturation=1.38:contrast=1.08",
        style_en="Cute Disney Pixar 3D animated movie frame, adorable expressive 3D cartoon character, joyful bright colors, 8k render",
        pixabay_q="cartoon 3d animation colorful",
        desc_ar="أفلام كرتون ثلاثية الأبعاد بأسلوب ديزني وبيكسار بألوان زاهية ومبهجة.",
        sample_idea="طفل موهوب يسجل هدف الفوز في الدقيقة الأخيرة وسط أصدقائه"
    ),
    "anime": Mode(
        id="anime",
        name_ar="الأنمي والمانجا اليابانية",
        emoji="🌸",
        engine="ai_anime",
        voice="ar-SA-HamedNeural",
        voice_rate="+0%",
        vfilter="eq=saturation=1.35:contrast=1.12",
        style_en="Masterpiece Japanese Anime frame, Studio Ghibli and Makoto Shinkai style, vibrant cel shading, sunset clouds",
        pixabay_q="anime landscape sunset clouds",
        desc_ar="تحريك ورسم بأسلوب الأنمي الياباني الدافئ واستوديو جيبلي.",
        sample_idea="محارب ساموراي شاب يقف فوق قمة جبلية لحماية قريته عند الغروب"
    ),
    "minecraft": Mode(
        id="minecraft",
        name_ar="عالم ماين كرافت المكعب 3D",
        emoji="🟩",
        engine="ai_character",
        voice="ar-SA-HamedNeural",
        voice_rate="+4%",
        vfilter="eq=saturation=1.32:contrast=1.15",
        style_en="Minecraft 3D Voxel video game animation style, iconic blocky cubic characters, voxel world made of blocks",
        pixabay_q="blocks pixel game 3d",
        desc_ar="مغامرات ومباريات حماسية بشخصيات وعالم ماين كرافت المكعب ثلاثي الأبعاد.",
        sample_idea="مباراة كرة قدم حماسية بشخصيات ماين كرافت في ملعب عملاق"
    ),
    "stickman": Mode(
        id="stickman",
        name_ar="الستيك مان الفيروسي (2D)",
        emoji="🖍️",
        engine="ai_2d",
        voice="ar-EG-ShakirNeural",
        voice_rate="+6%",
        vfilter="eq=contrast=1.25:saturation=1.30",
        style_en="Clean 2D viral stickman cartoon animation style, black stick figure body, round white head, colorful vector background",
        pixabay_q="sketch drawing cartoon",
        desc_ar="رسوم ستيك مان 2D الشهيرة للقصص والشروحات السريعة.",
        sample_idea="كيف تبني عادات النجاح وتتخلص من الكسل بأسلوب ستيك مان"
    ),
    "yemen_doc": Mode(
        id="yemen_doc",
        name_ar="الوثائقي اليمني والتاريخي",
        emoji="🇾🇪",
        engine="hybrid_video",
        voice="ar-YE-SalehNeural",
        voice_rate="-2%",
        vfilter="eq=contrast=1.16:saturation=1.18",
        style_en="National Geographic 8K documentary photography of Yemen, Old City of Sanaa, Socotra trees, green mountains",
        pixabay_q="mountains ancient castle architecture clouds",
        desc_ar="وثائقيات مخصصة لتاريخ وجمال ومعالم اليمن السعيد والحضارات العريقة بصوت يمني أصيل.",
        sample_idea="جمال الطبيعة الساحرة والعمارة التاريخية في اليمن وصنعاء وسقطرى"
    ),
    "cloning": Mode(
        id="cloning",
        name_ar="استنساخ الوجه وترميم الفيديو",
        emoji="🧬",
        engine="kaggle_face",
        voice="ar-SA-HamedNeural",
        voice_rate="+0%",
        vfilter="eq=contrast=1.12:saturation=1.15",
        style_en="Ultra-detailed photorealistic human portrait, biometric hologram scanning, crystal clear skin texture",
        pixabay_q="technology digital face artificial intelligence",
        desc_ar="أرسل أي فيديو هنا ليقوم الوكيل بمعالجته، إزالة العلامات المائية، وترميم جودة الملامح.",
        sample_idea="أرسل فيديو من جهازك لمعالجته وترميمه"
    ),
    "explainer": Mode(
        id="explainer",
        name_ar="الشرح التعليمي والصحي",
        emoji="📈",
        engine="hybrid_video",
        voice="ar-EG-ShakirNeural",
        voice_rate="+4%",
        vfilter="eq=contrast=1.15:saturation=1.22",
        style_en="Clean modern 3D educational & medical explainer visualization, macro photography mixed with clear infographic",
        pixabay_q="science health sport fitness",
        desc_ar="فيديوهات تعليمية وصحية ورياضية تجمع اللقطات الحقيقية والرسوم التوضيحية.",
        sample_idea="فوائد ممارسة كرة القدم للصحة الجسدية والنفسية والاجتماعية"
    ),
    "fast": Mode(
        id="fast",
        name_ar="الوضع السريع والتريندات",
        emoji="⚡",
        engine="hybrid_video",
        voice="ar-SA-HamedNeural",
        voice_rate="+8%",
        vfilter="eq=contrast=1.20:saturation=1.30",
        style_en="High-contrast fast viral action shot, dynamic neon rim lighting, ultra-sharp 8k",
        pixabay_q="sports action speed neon",
        desc_ar="مونتاج سريع الإيقاع للتريندات والمعلومات الخاطفة.",
        sample_idea="أغرب 5 حقائق علمية ستدهشك في دقيقة واحدة"
    ),
    "dialogue": Mode(
        id="dialogue",
        name_ar="الحوار التمثيلي",
        emoji="💬",
        engine="ai_character",
        voice="ar-EG-ShakirNeural",
        voice_rate="+0%",
        vfilter="eq=contrast=1.12:saturation=1.14",
        style_en="Cinematic movie dialogue frame, two expressive characters conversing in a warm atmospheric setting",
        pixabay_q="people talking coffee shop",
        desc_ar="مشاهد حوارية تمثيلية بين الشخصيات بأداء صوتي معبر.",
        sample_idea="حوار ملهم بين حكيم وشاب يبحث عن سر النجاح"
    ),
    "news": Mode(
        id="news",
        name_ar="الأخبار والتقارير",
        emoji="📰",
        engine="hybrid_video",
        voice="ar-SA-HamedNeural",
        voice_rate="+4%",
        vfilter="eq=contrast=1.14:saturation=1.06",
        style_en="Live 4K television news broadcast studio and field photojournalism, crisp realistic lighting",
        pixabay_q="news studio world technology",
        desc_ar="تقارير إخبارية وميدانية بصوت مذيع رسمي ولقطات واقعية.",
        sample_idea="تقرير شامل حول ثورة الذكاء الاصطناعي في عام 2026"
    ),
    "hybrid": Mode(
        id="hybrid",
        name_ar="المخرج الهجين (CapCut Pro)",
        emoji="🏛️",
        engine="hybrid_video",
        voice="ar-SA-HamedNeural",
        voice_rate="+2%",
        vfilter="eq=contrast=1.16:saturation=1.20",
        style_en="Epic blockbuster visual combining real 4K footage and AI hero shots with unified cinematic color grading",
        pixabay_q="cinematic nature city aerial",
        desc_ar="يدمج مقاطع الفيديو الحقيقية بدون حقوق نشر مع مشاهد الذكاء الاصطناعي بأسلوب كاب كات.",
        sample_idea="رحلة بصرية عبر أجمل عجائب الطبيعة والمدن الذكية"
    ),
    "story": Mode(
        id="story",
        name_ar="الستوري والريلز (POV)",
        emoji="📸",
        engine="ai_character",
        voice="ar-SA-ZariyahNeural",
        voice_rate="+5%",
        vfilter="eq=contrast=1.15:saturation=1.25",
        style_en="First-person POV realistic handheld camera walking inside an iconic fantasy world, hyper-realistic 9:16 vertical",
        pixabay_q="tropical walk pov waterfall",
        desc_ar="فيديوهات منظور الشخص الأول (POV) للدخول إلى العوالم الخيالية والواقعية.",
        sample_idea="جولة من منظور الشخص الأول داخل بيت سحري في الغابة"
    ),
    "ads": Mode(
        id="ads",
        name_ar="الإعلانات التجارية",
        emoji="📢",
        engine="hybrid_video",
        voice="ar-SA-HamedNeural",
        voice_rate="+3%",
        vfilter="eq=contrast=1.22:saturation=1.25",
        style_en="Luxury commercial product cinematography, slow-motion water droplets, dramatic studio rim lighting, macro 4k",
        pixabay_q="luxury perfume gold water",
        desc_ar="إعلانات تسويقية فاخرة للمنتجات والخدمات.",
        sample_idea="إعلان فاخر لعطر ملكي جديد مستوحى من العود العربي"
    ),
    "beatsync": Mode(
        id="beatsync",
        name_ar="الإيقاع الحماسي (Edits)",
        emoji="🎵",
        engine="hybrid_video",
        voice="ar-EG-ShakirNeural",
        voice_rate="+8%",
        vfilter="eq=contrast=1.28:saturation=1.35",
        style_en="High-energy drift car and sports edit, motion blur, neon reflections, aggressive wide-angle lens",
        pixabay_q="sports car drift night neon",
        desc_ar="تقطيع حماسي سريع للمباريات والسيارات والأكشن.",
        sample_idea="أقوى لحظات الحسم والمهارات في تاريخ كرة القدم"
    ),
    "ambient": Mode(
        id="ambient",
        name_ar="الخلفيات المريحة والـ ASMR",
        emoji="🌧️",
        engine="stock_video",
        voice="ar-SA-ZariyahNeural",
        voice_rate="-8%",
        vfilter="eq=saturation=1.15",
        style_en="Cozy atmospheric cabin with warm fireplace glow while rain falls on glass window at night",
        pixabay_q="rain window fireplace night",
        desc_ar="فيديوهات هادئة ومريحة للأعصاب مع سرد تأملي دافئ.",
        sample_idea="أمسية هادئة تحت صوت المطر للتأمل والراحة النفسية"
    ),
    "podcast": Mode(
        id="podcast",
        name_ar="البودكاست المرئي",
        emoji="🎙️",
        engine="ai_character",
        voice="ar-SA-HamedNeural",
        voice_rate="-2%",
        vfilter="eq=contrast=1.16:saturation=1.08",
        style_en="Professional dark moody podcast studio, close-up Shure SM7B microphone, warm neon sign",
        pixabay_q="microphone podcast studio",
        desc_ar="مقاطع بودكاست مرئية بصوت إذاعي فخم وإضاءة استوديو.",
        sample_idea="حلقة بودكاست عن كيف تبني الانضباط الذاتي وتحقق أهدافك"
    ),
    "thriller": Mode(
        id="thriller",
        name_ar="الإثارة والغموض",
        emoji="🔥",
        engine="ai_character",
        voice="ar-SA-HamedNeural",
        voice_rate="-5%",
        vfilter="eq=contrast=1.28:saturation=0.68",
        style_en="Dark psychological thriller cinematography, thick volumetric fog, eerie silhouettes under streetlamp",
        pixabay_q="dark forest fog night mystery",
        desc_ar="قصص غموض وتشويق بفلاتر مظلمة وسرد صوتي مشوق.",
        sample_idea="لغز السفينة المختفية التي ظهرت فجأة وسط الضباب بعد 50 عاماً"
    ),
}

MODE_ORDER = list(MODES.keys())


def missing_required() -> list[str]:
    miss = []
    if not API_ID:
        miss.append("TELEGRAM_API_ID")
    if not API_HASH:
        miss.append("TELEGRAM_API_HASH")
    if not BOT_TOKEN:
        miss.append("TELEGRAM_BOT_TOKEN")
    return miss
