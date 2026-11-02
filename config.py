# -*- coding: utf-8 -*-
"""
Genesis Cinema Studio — config.py
الإعدادات المركزية + الأوضاع الـ 17 + بيانات القفل الجغرافي (Geo-Lock).
كل القيم الحساسة تُقرأ من متغيرات البيئة (.env) — لا تضع مفاتيحك داخل الكود.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

try:  # اختياري: قراءة ملف .env إن وُجد
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # pragma: no cover
    pass


# ───────────────────────── أدوات قراءة البيئة ─────────────────────────
def _s(name: str, default: str = "") -> str:
    return (os.getenv(name) or default).strip()


def _first(*names: str) -> str:
    """أول متغير غير فارغ من عدة أسماء (لدعم أسماء Secrets في GitHub وأسماء .env معاً)."""
    for n in names:
        v = _s(n)
        if v:
            return v
    return ""


def _i(name: str, default: int) -> int:
    try:
        return int(_s(name, str(default)))
    except ValueError:
        return default


def _f(name: str, default: float) -> float:
    try:
        return float(_s(name, str(default)))
    except ValueError:
        return default


def _b(name: str, default: bool) -> bool:
    return _s(name, "1" if default else "0").lower() in ("1", "true", "yes", "on")


# ───────────────────────── المسارات ─────────────────────────
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(_s("DATA_DIR", str(BASE_DIR / "data")))
WORK_DIR = DATA_DIR / "work"          # ملفات مؤقتة لكل مهمة (تُحذف تلقائياً)
OUTPUT_DIR = DATA_DIR / "output"      # الفيديوهات النهائية
SAMPLES_DIR = DATA_DIR / "samples"    # فيديوهات الأمثلة: <mode_id>.mp4
DB_PATH = DATA_DIR / "genesis_db.json"
ASSETS_DIR = BASE_DIR / "assets"
FONTS_DIR = ASSETS_DIR / "fonts"      # ضع هنا خطاً عربياً مثل Cairo-Bold.ttf
MUSIC_DIR = ASSETS_DIR / "music"      # اختياري: ملفات mp3 خلفية (بدون حقوق)

for _d in (DATA_DIR, WORK_DIR, OUTPUT_DIR, SAMPLES_DIR, FONTS_DIR, MUSIC_DIR):
    _d.mkdir(parents=True, exist_ok=True)

# ───────────────────────── تيليجرام ─────────────────────────
try:
    API_ID = int(_first("API_ID", "TELEGRAM_API_ID") or 0)
except ValueError:
    API_ID = 0
API_HASH = _first("API_HASH", "TELEGRAM_API_HASH")
BOT_TOKEN = _first("BOT_TOKEN", "TELEGRAM_BOT_TOKEN")
ADMIN_IDS = {int(x) for x in _s("ADMIN_IDS").replace(" ", "").split(",") if x.isdigit()}

# ───────────────────────── المفاتيح المجانية ─────────────────────────
# يدعم حتى مفتاحين لكل خدمة (حسابان): عند استنفاد الأول أو تحديد المعدل يتبدّل البوت للثاني تلقائياً.
PIXABAY_KEYS = [k for k in dict.fromkeys(
    [_first("PIXABAY_KEY", "PIXABAY_KEY_1"), _first("PIXABAY_KEY_2")]) if k]    # https://pixabay.com/api/docs/
HF_TOKENS = [k for k in dict.fromkeys(
    [_first("HF_TOKEN", "HF_TOKEN_1"), _first("HF_TOKEN_2")]) if k]             # https://huggingface.co/settings/tokens
PIXABAY_KEY = PIXABAY_KEYS[0] if PIXABAY_KEYS else ""
HF_TOKEN = HF_TOKENS[0] if HF_TOKENS else ""

# ───────────────────────── Supabase (اختياري — نسخ احتياطي للذاكرة) ─────────────────────────
SUPABASE_URL = _s("SUPABASE_URL").rstrip("/")
SUPABASE_KEY = _first("SUPABASE_KEY", "SUPABASE_SECRET_KEY")
SUPABASE_TABLE = _s("SUPABASE_TABLE", "genesis_state")

# ───────────────────────── نماذج الذكاء الاصطناعي (قابلة للتغيير من .env) ─────────────────────────
HF_LLM_MODEL = _s("HF_LLM_MODEL", "Qwen/Qwen2.5-72B-Instruct")
HF_LLM_FALLBACK_MODEL = _s("HF_LLM_FALLBACK_MODEL", "meta-llama/Llama-3.3-70B-Instruct")
HF_IMAGE_MODEL = _s("HF_IMAGE_MODEL", "black-forest-labs/FLUX.1-schnell")

# ───────────────────────── الصوت ─────────────────────────
TTS_FALLBACK_VOICES = ("ar-SA-HamedNeural", "ar-SA-ZariyahNeural", "ar-EG-ShakirNeural", "ar-EG-SalmaNeural")

# ───────────────────────── الفيديو ─────────────────────────
VIDEO_W, VIDEO_H = 1080, 1920
FPS = _i("FPS", 30)
X264_PRESET = _s("X264_PRESET", "veryfast")
MIN_SCENES, MAX_SCENES = 5, 8
SCENE_PAD = 0.35                      # ثوانٍ تُضاف بعد كل تعليق صوتي
SUBTITLES_ENABLED = _b("SUBTITLES", True)
FONT_FAMILY = _s("FONT_FAMILY", "Cairo")   # اسم عائلة الخط داخل ملف الخط الذي وضعته في assets/fonts
SUB_FONT_SIZE = _i("SUB_FONT_SIZE", 78)
MUSIC_VOLUME = _f("MUSIC_VOLUME", 0.10)
MAX_FINAL_MB = _i("MAX_FINAL_MB", 48)  # حد رفع البوتات في تيليجرام = 50MB

# ───────────────────────── حدود التشغيل ─────────────────────────
DAILY_LIMIT = _i("DAILY_LIMIT", 5)               # فيديوهات/مستخدم/يوم (المشرفون بلا حد)
MAX_CONCURRENT_JOBS = _i("MAX_CONCURRENT_JOBS", 1)
MAX_RUN_MINUTES = _i("MAX_RUN_MINUTES", 0)       # >0: يوقف البوت بشكل منظم بعد هذه المدة (للمنصات ذات حد زمني)
JOB_TIMEOUT = _i("JOB_TIMEOUT", 1200)            # ثوانٍ لكل فيديو
FFMPEG_TIMEOUT = _i("FFMPEG_TIMEOUT", 300)
ASSET_CONCURRENCY = _i("ASSET_CONCURRENCY", 3)
TZ_OFFSET_HOURS = _i("TZ_OFFSET_HOURS", 3)       # لحساب "اليوم" (3 = توقيت الجزيرة العربية)
KEEP_WORK_FILES = _b("KEEP_WORK_FILES", False)
OUTPUT_TTL_HOURS = _i("OUTPUT_TTL_HOURS", 24)
MAX_IDEA_CHARS = 700
MIN_IDEA_CHARS = 8


def missing_required() -> list[str]:
    """المتغيرات الإلزامية الناقصة لتشغيل البوت."""
    out = []
    if not API_ID:
        out.append("API_ID")
    if not API_HASH:
        out.append("API_HASH")
    if not BOT_TOKEN:
        out.append("BOT_TOKEN")
    return out


# ═════════════════════════ الأوضاع الـ 17 ═════════════════════════
@dataclass(frozen=True)
class Mode:
    id: str
    emoji: str
    name_ar: str
    name_en: str
    desc_ar: str
    tone: str               # أسلوب السرد (يُمرَّر لوكيل السيناريو)
    visual_style: str       # البصمة البصرية (تُضاف لكل برومبت صورة)
    color_filter: str       # فلتر سينمائي لـ FFmpeg (تدرج لوني)
    broll_ratio: float      # احتمال تفضيل لقطات الفيديو الحقيقية على الصور المولّدة (0..1)
    stock_hints: tuple      # كلمات بحث احتياطية في Pixabay
    sample_idea: str        # فكرة المثال التي تُستخدم لبناء فيديو العينة
    voice: str = "ar-SA-HamedNeural"
    voice_rate: str = "+0%"
    motion: float = 0.12    # قوة حركة الكاميرا (Ken Burns) على الصور


_M = Mode  # اختصار

MODES: dict[str, Mode] = {m.id: m for m in (
    _M("documentary", "🎥", "وثائقي سينمائي", "Cinematic documentary",
       "سرد وثائقي هادئ بأسلوب القنوات العالمية، حقائق وصور واقعية.",
       "calm, authoritative BBC-style documentary narration; vivid verified facts; dramatic pauses",
       "cinematic documentary photography, natural light, 35mm lens, shallow depth of field, fine film grain, muted teal-orange grade, ultra detailed",
       "eq=contrast=1.08:saturation=1.1,colorbalance=rs=0.04:bs=-0.04:rh=0.03:bh=-0.03,vignette=PI/6,noise=alls=6:allf=t",
       0.55, ("aerial landscape", "city timelapse"),
       "كيف بُنيت أهرامات الجيزة ولماذا ما زالت تحيّر العلماء؟"),
    _M("history", "🏛", "حكايات التاريخ", "History tales",
       "قصص تاريخية ملحمية مبنية على وقائع موثّقة.",
       "epic yet factual storyteller; chronological; grounded strictly in documented history",
       "historical epic cinematic still, golden hour, dusty atmosphere, period-accurate architecture and costumes, warm sepia grade",
       "eq=contrast=1.1:saturation=0.85,colorbalance=rs=0.08:gs=0.02:bs=-0.1,vignette=PI/4.5,noise=alls=8:allf=t",
       0.35, ("ancient ruins", "old city"),
       "قصة سقوط الأندلس وآخر أيام غرناطة"),
    _M("mystery", "🕵️", "ألغاز وغموض", "Mystery",
       "تشويق وأسئلة معلّقة وكشف تدريجي للحقيقة.",
       "suspenseful, hushed delivery; open questions; reveal slowly; end on a haunting twist",
       "moody noir cinematic still, drifting fog, low-key lighting, deep shadows, cold blue-green grade",
       "eq=contrast=1.15:saturation=0.8:brightness=-0.04,colorbalance=bs=0.08:bm=0.05:rs=-0.05,vignette=PI/4",
       0.40, ("fog forest", "dark corridor"),
       "لغز مثلث برمودا: ماذا حدث فعلاً للسفن المفقودة؟",
       voice_rate="-4%"),
    _M("horror", "👻", "رعب", "Horror",
       "رعب نفسي بطيء بدون دماء، جمل قصيرة وتوتر متصاعد.",
       "dark, slow creeping dread; short sentences; psychological horror; absolutely no gore",
       "horror cinematic still, dark atmosphere, thick fog, a single practical light source, desaturated, grainy, unsettling but not gory",
       "eq=contrast=1.2:saturation=0.6:brightness=-0.07,colorbalance=gs=0.05:bs=0.03,vignette=PI/3.2,noise=alls=14:allf=t",
       0.30, ("dark forest night", "abandoned house"),
       "قصة البيت المهجور الذي يسمع زواره خطوات كل ليلة",
       voice_rate="-6%", motion=0.16),
    _M("motivation", "🔥", "تحفيز وإلهام", "Motivation",
       "كلمات قوية ومباشرة تشعل الحماس.",
       "powerful, direct, second-person, energetic; short punchy sentences; strong hook and closing line",
       "inspirational cinematic still, golden sunrise light, lone silhouette, epic wide landscapes, high-contrast warm grade",
       "eq=contrast=1.12:saturation=1.2,colorbalance=rs=0.06:rh=0.05:bs=-0.06,vignette=PI/6",
       0.50, ("sunrise mountain", "running athlete"),
       "لماذا يفشل أغلب الناس في الأسبوع الثالث من أي هدف؟",
       voice_rate="+4%", motion=0.15),
    _M("moral_stories", "📖", "قصص وعِبَر", "Moral stories",
       "حكاية مؤثرة بعبرة واضحة (بدون تجسيد أي شخصيات دينية).",
       "warm wise storyteller; a simple moving story with a clear moral; never depict prophets, companions or religious figures",
       "storybook cinematic still, soft warm light, humble village life, expressive non-religious characters, painterly realism",
       "eq=contrast=1.04:saturation=1.05,colorbalance=rs=0.05:bs=-0.04,vignette=PI/6",
       0.25, ("village life", "old man walking"),
       "قصة التاجر الصادق الذي رفض الغش وكيف تغيّرت حياته",
       voice_rate="-2%"),
    _M("science", "🔬", "علوم ومعرفة", "Science & knowledge",
       "معلومات علمية مبسّطة وتصحيح مفاهيم شائعة.",
       "curious, clear, myth-busting; simple everyday analogies; accurate and cautious with claims",
       "clean macro and scientific visualization cinematic still, crisp lighting, high detail, cool blue accents",
       "eq=contrast=1.08:saturation=1.1,colorbalance=bs=0.06:bh=0.04,unsharp=5:5:0.6",
       0.45, ("laboratory science", "microscope"),
       "ماذا يحدث داخل جسمك عندما تنام؟"),
    _M("space", "🚀", "فضاء وكون", "Space",
       "رحلة في الكون ومقارنات مذهلة للأحجام والمسافات.",
       "awe-inspiring; vast scale comparisons; wonder and humility; scientifically accurate",
       "deep space cinematic still, realistic astrophotography, nebula, volumetric light, IMAX scale",
       "eq=contrast=1.15:saturation=1.25:brightness=-0.02,colorbalance=bs=0.08:rs=0.03,vignette=PI/5",
       0.35, ("galaxy stars", "planet earth space"),
       "ما حجم الكون الحقيقي؟ رحلة من الأرض إلى حافة المجرات"),
    _M("nature", "🌿", "طبيعة وحياة برية", "Nature & wildlife",
       "عالم الحيوان والطبيعة بلقطات حقيقية.",
       "calm, wonder-filled nature-documentary narration; surprising animal behaviour facts",
       "Planet Earth style wildlife photography, telephoto lens, golden light, ultra sharp, rich natural colors",
       "eq=contrast=1.08:saturation=1.3,vignette=PI/7",
       0.85, ("wildlife animals", "forest river"),
       "أغرب 5 حقائق عن الأخطبوط الذي يملك ثلاثة قلوب"),
    _M("travel", "✈️", "سفر وبلدان", "Travel",
       "دليل سياحي ممتع بمعلومات عملية وتفاصيل حسّية.",
       "enthusiastic travel guide; practical tips; sensory details of places and food",
       "travel cinematic photography, vibrant natural colors, golden hour, wide-angle lens, authentic local life",
       "eq=contrast=1.07:saturation=1.25,colorbalance=rs=0.04:bs=-0.03",
       0.70, ("travel destination", "street market"),
       "أجمل 5 أماكن يجب زيارتها في تركيا"),
    _M("scifi", "🤖", "خيال علمي", "Sci-fi",
       "مستقبل وتقنيات وعوالم افتراضية بأجواء نيون.",
       "futuristic, thought-provoking; speculative but grounded; cinematic tension",
       "futuristic sci-fi cinematic still, neon accents, volumetric haze, anamorphic lens flares, teal and magenta grade",
       "eq=contrast=1.15:saturation=1.3,colorbalance=bs=0.1:rs=0.05:gm=-0.03,vignette=PI/5",
       0.15, ("futuristic city", "technology hologram"),
       "كيف سيبدو العالم بعد 100 سنة إذا سيطر الذكاء الاصطناعي؟",
       motion=0.14),
    _M("crime", "🚔", "جريمة وتحقيق", "True crime",
       "قضايا غامضة وتحقيقات (بدون مشاهد عنف).",
       "gripping investigative narration; facts first; tasteful, never graphic; no real victims' faces",
       "gritty crime drama cinematic still, night, rain, neon reflections, desaturated, high contrast, no gore",
       "eq=contrast=1.2:saturation=0.7:brightness=-0.05,colorbalance=gs=0.04:bs=0.05,vignette=PI/3.5,noise=alls=10:allf=t",
       0.35, ("night city rain", "police lights"),
       "قضية الجريمة الكاملة التي كشفها دليل صغير"),
    _M("epic", "⚔️", "ملاحم ومعارك", "Epic battles",
       "معارك وملاحم تاريخية بأسلوب سينمائي (بدون دماء).",
       "grand, rousing war-epic narration; strategy and turning points; never graphic",
       "epic war film cinematic still, dramatic stormy sky, dust and smoke, vast battlefield scenery, no gore, bronze grade",
       "eq=contrast=1.18:saturation=0.8,colorbalance=rs=0.06:bs=-0.08,vignette=PI/4,noise=alls=8:allf=t",
       0.20, ("storm clouds", "castle fortress"),
       "معركة حطين: كيف غيّر صلاح الدين مجرى التاريخ؟",
       voice_rate="-2%"),
    _M("luxury", "💎", "أعمال وفخامة", "Business & luxury",
       "نجاح وأعمال وأسلوب حياة راقٍ.",
       "confident, polished business storytelling; clear lessons; aspirational but honest",
       "luxury lifestyle commercial photography, clean modern interiors, soft studio lighting, gold accents, high-end",
       "eq=contrast=1.1:saturation=1.05:brightness=0.01,colorbalance=rh=0.04:bh=-0.03,unsharp=5:5:0.5",
       0.60, ("luxury interior", "business city skyline"),
       "كيف بنت علامات الفخامة العالمية قيمتها؟"),
    _M("food", "🍽", "طعام ومطبخ", "Food & cooking",
       "وصفات وقصص أطباق بلقطات شهية.",
       "warm, appetizing, sensory language; clear simple steps; food history tidbits",
       "professional food photography, macro, rising steam, warm side-light, shallow depth of field, appetizing",
       "eq=contrast=1.08:saturation=1.35:brightness=0.02,colorbalance=rs=0.06:gs=0.02",
       0.75, ("cooking food", "kitchen chef"),
       "سر الكبسة اليمنية الأصلية وتاريخ الأرز في الجزيرة العربية"),
    _M("sports", "⚽", "رياضة", "Sports",
       "قصص أبطال ولحظات رياضية حماسية.",
       "high-energy sports commentary; heroic arcs; punchy facts and numbers (only if certain)",
       "dynamic sports photography, motion-blur accents, stadium lights, dramatic freeze-frame, high contrast",
       "eq=contrast=1.15:saturation=1.3,unsharp=5:5:0.7",
       0.60, ("stadium crowd", "athlete training"),
       "قصة صعود لاعب من حيّ فقير إلى نجومية العالم",
       voice_rate="+3%", motion=0.15),
    _M("fantasy", "🧚", "خيال وحكايات", "Fantasy tales",
       "حكايات خيالية وعوالم سحرية للصغار والكبار.",
       "enchanting fairy-tale narrator; gentle wonder; simple vocabulary; a kind ending",
       "high-fantasy cinematic illustration-like still, magical glowing light, drifting mist, enchanted forests and castles, rich colors",
       "eq=contrast=1.08:saturation=1.3,colorbalance=bs=0.05:rs=0.03,vignette=PI/6",
       0.10, ("enchanted forest", "castle mist"),
       "حكاية الأرنب الصغير الذي وجد مفتاح الغابة السحرية",
       voice="ar-SA-ZariyahNeural", voice_rate="-3%"),
)}

assert len(MODES) == 17, "يجب أن يكون عدد الأوضاع 17"
MODE_ORDER = list(MODES.keys())


# ═════════════════════════ القفل الجغرافي (Strict Geo-Lock) ═════════════════════════
# (كلمات عربية للبحث في فكرة المستخدم, الاسم الإنجليزي للبرومبتات, وسوم يجب أن تظهر في وسوم Pixabay/Wikimedia)
# المدن أولاً ثم الدول؛ يُختار أول موضع يظهر في نص المستخدم.
GEO_LOCKS: list[tuple[tuple[str, ...], str, tuple[str, ...]]] = [
    # مدن ومواقع
    (("صنعاء",), "Sanaa, Yemen", ("sanaa", "sana'a", "yemen")),
    (("عدن",), "Aden, Yemen", ("aden", "yemen")),
    (("حضرموت", "شبام"), "Hadramawt, Yemen", ("hadramawt", "hadhramaut", "shibam", "yemen")),
    (("سقطرى",), "Socotra island, Yemen", ("socotra", "yemen")),
    (("مأرب", "مارب"), "Marib, Yemen", ("marib", "yemen")),
    (("تعز",), "Taiz, Yemen", ("taiz", "yemen")),
    (("القاهرة",), "Cairo, Egypt", ("cairo", "egypt")),
    (("الاسكندرية",), "Alexandria, Egypt", ("alexandria", "egypt")),
    (("الاقصر",), "Luxor, Egypt", ("luxor", "egypt")),
    (("الجيزه", "الاهرامات", "اهرامات"), "Giza pyramids, Egypt", ("giza", "pyramid", "egypt")),
    (("دمشق",), "Damascus, Syria", ("damascus", "syria")),
    (("حلب",), "Aleppo, Syria", ("aleppo", "syria")),
    (("بغداد",), "Baghdad, Iraq", ("baghdad", "iraq")),
    (("القدس",), "Jerusalem", ("jerusalem", "palestine")),
    (("مكه", "مكه المكرمه"), "Makkah, Saudi Arabia", ("mecca", "makkah", "saudi")),
    (("المدينه المنوره",), "Madinah, Saudi Arabia", ("medina", "madinah", "saudi")),
    (("الرياض",), "Riyadh, Saudi Arabia", ("riyadh", "saudi")),
    (("جده",), "Jeddah, Saudi Arabia", ("jeddah", "saudi")),
    (("دبي",), "Dubai, UAE", ("dubai", "uae", "emirates")),
    (("ابوظبي",), "Abu Dhabi, UAE", ("abu dhabi", "uae", "emirates")),
    (("الدوحه",), "Doha, Qatar", ("doha", "qatar")),
    (("مسقط",), "Muscat, Oman", ("muscat", "oman")),
    (("بيروت",), "Beirut, Lebanon", ("beirut", "lebanon")),
    (("مراكش",), "Marrakech, Morocco", ("marrakech", "marrakesh", "morocco")),
    (("الرباط",), "Rabat, Morocco", ("rabat", "morocco")),
    (("الخرطوم",), "Khartoum, Sudan", ("khartoum", "sudan")),
    (("اسطنبول", "استانبول"), "Istanbul, Turkey", ("istanbul", "turkey")),
    (("الاندلس", "غرناطه", "قرطبه", "اشبيليه"), "Andalusia, Spain", ("andalusia", "granada", "cordoba", "seville", "spain")),
    # دول
    (("اليمن", "يمن"), "Yemen", ("yemen",)),
    (("مصر",), "Egypt", ("egypt",)),
    (("السعوديه", "المملكه العربيه السعوديه"), "Saudi Arabia", ("saudi",)),
    (("الامارات",), "United Arab Emirates", ("uae", "emirates", "dubai", "abu dhabi")),
    (("دوله قطر",), "Qatar", ("qatar", "doha")),
    (("الكويت",), "Kuwait", ("kuwait",)),
    (("البحرين",), "Bahrain", ("bahrain",)),
    (("سلطنه عمان", "عمان"), "Oman", ("oman", "muscat")),
    (("العراق",), "Iraq", ("iraq", "baghdad")),
    (("سوريا", "سورية"), "Syria", ("syria", "damascus")),
    (("لبنان",), "Lebanon", ("lebanon", "beirut")),
    (("الاردن",), "Jordan", ("jordan", "petra")),
    (("فلسطين",), "Palestine", ("palestine", "jerusalem")),
    (("السودان",), "Sudan", ("sudan", "khartoum")),
    (("ليبيا",), "Libya", ("libya",)),
    (("تونس",), "Tunisia", ("tunisia", "tunis")),
    (("الجزائر",), "Algeria", ("algeria", "algiers")),
    (("المغرب",), "Morocco", ("morocco",)),
    (("موريتانيا",), "Mauritania", ("mauritania",)),
    (("الصومال",), "Somalia", ("somalia",)),
    (("تركيا",), "Turkey", ("turkey", "istanbul", "anatolia")),
    (("ايران",), "Iran", ("iran", "persia")),
    (("الهند",), "India", ("india",)),
    (("باكستان",), "Pakistan", ("pakistan",)),
    (("اندونيسيا",), "Indonesia", ("indonesia", "bali")),
    (("ماليزيا",), "Malaysia", ("malaysia", "kuala lumpur")),
    (("اليابان",), "Japan", ("japan", "tokyo", "kyoto")),
    (("الصين",), "China", ("china", "beijing", "shanghai")),
    (("روسيا",), "Russia", ("russia", "moscow")),
    (("امريكا", "الولايات المتحده"), "United States", ("usa", "united states", "america", "new york")),
    (("بريطانيا", "انجلترا"), "United Kingdom", ("uk", "england", "britain", "london")),
    (("فرنسا",), "France", ("france", "paris")),
    (("ايطاليا",), "Italy", ("italy", "rome", "venice")),
    (("اسبانيا",), "Spain", ("spain", "madrid", "barcelona")),
    (("المانيا",), "Germany", ("germany", "berlin")),
    (("سويسرا",), "Switzerland", ("switzerland", "swiss", "alps")),
    (("اليونان",), "Greece", ("greece", "athens")),
    (("البرازيل",), "Brazil", ("brazil", "rio")),
    (("المالديف",), "Maldives", ("maldives",)),
]
