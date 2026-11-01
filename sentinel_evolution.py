# -*- coding: utf-8 -*-
"""
Genesis Cinema Studio — sentinel_evolution.py
محرك الإنتاج والمونتاج: VideoProductionEngine

خط الإنتاج (لكل فيديو):
  1) وكيل السيناريو  : فكرة المستخدم → سيناريو عربي فصيح مقسّم لمشاهد (LLM عبر HuggingFace) + قفل جغرافي + قفل شخصيات
  2) وكيل الصوت     : تعليق صوتي عربي لكل مشهد (edge-tts ثم gTTS احتياطياً) → مدة كل مشهد تُقاس بدقة
  3) وكيل المونتاج  : لكل مشهد لقطة حقيقية (Pixabay MP4) أو صورة مولّدة (FLUX) أو صورة ويكيميديا (PD/CC0)
                      ثم FFmpeg: تدرج لوني للوضع + حركة كاميرا + ترجمة عربية محروقة + دمج الصوت
  4) الإصلاح الذاتي : فحص كل mp4 بـ ffprobe، وإعادة ترميز تلقائية عند أي تلف، ومهلة زمنية لكل أمر (لا تعليق أبداً)

القاعدة: لا يفشل الإنتاج بسبب مصدر واحد — كل مرحلة لها بدائل (fallbacks).
"""
from __future__ import annotations

import asyncio
import hashlib
import io
import json
import logging
import random
import re
import shutil
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Awaitable, Callable, Optional

import httpx

import config
from config import Mode
from database import Database

try:
    import edge_tts  # TTS رئيسي (مجاني)
except Exception:  # pragma: no cover
    edge_tts = None
try:
    from gtts import gTTS  # TTS احتياطي
except Exception:  # pragma: no cover
    gTTS = None
try:
    from huggingface_hub import AsyncInferenceClient
except Exception:  # pragma: no cover
    AsyncInferenceClient = None
try:
    from PIL import Image
except Exception:  # pragma: no cover
    Image = None

log = logging.getLogger("genesis.engine")

ProgressCB = Callable[[str, str], Awaitable[None]]
W, H, FPS = config.VIDEO_W, config.VIDEO_H, config.FPS


class ProductionError(Exception):
    """خطأ إنتاج برسالة جاهزة للعرض على المستخدم."""

    def __init__(self, user_message: str):
        super().__init__(user_message)
        self.user_message = user_message


# ═════════════════════════ أدوات النظام: تشغيل الأوامر والفحص والإصلاح ═════════════════════════
async def run_cmd(*args: str, timeout: int = 300, cwd: Optional[Path] = None) -> tuple[int, str, str]:
    """يشغّل أمراً خارجياً بمهلة زمنية؛ عند انتهاء المهلة يُقتل الأمر (لا تعليق)."""
    try:
        proc = await asyncio.create_subprocess_exec(
            *[str(a) for a in args],
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            cwd=str(cwd) if cwd else None,
        )
    except FileNotFoundError:
        return 127, "", f"{args[0]} غير مثبّت"
    try:
        out, err = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        try:
            proc.kill()
        except ProcessLookupError:
            pass
        await proc.wait()
        return 124, "", "timeout"
    return proc.returncode or 0, out.decode("utf-8", "ignore"), err.decode("utf-8", "ignore")


_FF = ("ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y")


async def ffmpeg(*args, cwd: Optional[Path] = None, timeout: Optional[int] = None) -> tuple[bool, str]:
    code, _, err = await run_cmd(*_FF, *args, cwd=cwd, timeout=timeout or config.FFMPEG_TIMEOUT)
    return code == 0, err.strip()[-500:]


async def probe(path: Path) -> dict:
    """معلومات الملف عبر ffprobe. يرجع {} إذا كان الملف غير صالح."""
    if not Path(path).exists():
        return {}
    code, out, _ = await run_cmd(
        "ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path), timeout=40)
    if code != 0:
        return {}
    try:
        d = json.loads(out)
    except json.JSONDecodeError:
        return {}
    streams = d.get("streams") or []
    v = next((s for s in streams if s.get("codec_type") == "video"), None)
    a = next((s for s in streams if s.get("codec_type") == "audio"), None)
    try:
        dur = float((d.get("format") or {}).get("duration") or 0)
    except (TypeError, ValueError):
        dur = 0.0
    return {
        "duration": dur,
        "has_video": v is not None,
        "has_audio": a is not None,
        "width": int(v.get("width", 0)) if v else 0,
        "height": int(v.get("height", 0)) if v else 0,
        "size": Path(path).stat().st_size,
    }


async def valid_media(path: Path, need_video: bool = True, need_audio: bool = False, min_dur: float = 0.4) -> bool:
    i = await probe(path)
    if not i or i["size"] < 1024 or i["duration"] < min_dur:
        return False
    if need_video and not i["has_video"]:
        return False
    if need_audio and not i["has_audio"]:
        return False
    return True


async def validate_and_heal(path: Path, need_audio: bool = True) -> bool:
    """فحص ملف mp4 وإصلاحه ذاتياً: (1) إعادة تغليف (2) إعادة ترميز كاملة."""
    path = Path(path)
    if await valid_media(path, need_audio=need_audio):
        return True
    log.warning("ملف mp4 غير سليم، بدء الإصلاح الذاتي: %s", path.name)
    fixed = path.with_name(path.stem + ".fix1.mp4")
    ok, _ = await ffmpeg("-err_detect", "ignore_err", "-i", path, "-c", "copy", "-movflags", "+faststart", fixed)
    if ok and await valid_media(fixed, need_audio=need_audio):
        shutil.move(str(fixed), str(path))
        return True
    fixed2 = path.with_name(path.stem + ".fix2.mp4")
    ok, _ = await ffmpeg("-err_detect", "ignore_err", "-i", path, "-c:v", "libx264", "-preset", config.X264_PRESET,
                         "-crf", "23", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k",
                         "-movflags", "+faststart", fixed2)
    if ok and await valid_media(fixed2, need_audio=need_audio):
        shutil.move(str(fixed2), str(path))
        return True
    for p in (fixed, fixed2):
        p.unlink(missing_ok=True)
    return False


# ═════════════════════════ أدوات النص: عربي / جغرافيا ═════════════════════════
_AR_MARKS = re.compile(r"[\u064B-\u065F\u0670\u0640]")
_AR_LETTERS = "\u0621-\u064A"
_EMOJI = re.compile("[\U00010000-\U0010ffff\u2600-\u27BF\u2B00-\u2BFF\uFE0F\u200d\u200e\u200f]")
_NOT_GEO = ("جنات عدن", "جنه عدن", "صلاه المغرب", "اذان المغرب", "وقت المغرب", "قطر الدائره",
            "قطر الارض", "قطر القمر", "قطر الشمس")


def ar_norm(s: str) -> str:
    s = _AR_MARKS.sub("", s)
    for a, b in (("أ", "ا"), ("إ", "ا"), ("آ", "ا"), ("ٱ", "ا"), ("ى", "ي"), ("ة", "ه"), ("ؤ", "و"), ("ئ", "ي")):
        s = s.replace(a, b)
    return s.lower()


def clean_tts_text(t: str) -> str:
    t = re.sub(r"https?://\S+", " ", str(t))
    t = _EMOJI.sub(" ", t)
    t = re.sub(r"[*_#~`>|\[\]{}]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


@dataclass(frozen=True)
class GeoLock:
    name: str          # الاسم الإنجليزي للبرومبتات
    tags: tuple        # وسوم يجب أن تظهر في نتائج Pixabay/Wikimedia


def detect_geo(text: str) -> Optional[GeoLock]:
    """القفل الجغرافي الصارم: يستخرج الدولة/المدينة من نص المستخدم نفسه (لا نثق بالـ LLM وحده)."""
    t = ar_norm(text)
    for bad in _NOT_GEO:
        t = t.replace(bad, " ")
    best: Optional[tuple[int, GeoLock]] = None
    for keys, name, tags in config.GEO_LOCKS:
        for k in keys:
            kn = ar_norm(k)
            if kn.startswith("ال"):
                core = re.escape(kn[2:])
                pat = rf"(?<![{_AR_LETTERS}])(?:[وبفك]|ل)?(?:ال|ل){core}(?![{_AR_LETTERS}])"
            else:
                pat = rf"(?<![{_AR_LETTERS}])(?:[وبفك]|ل)?(?:ال)?{re.escape(kn)}(?![{_AR_LETTERS}])"
            m = re.search(pat, t)
            if m and (best is None or m.start() < best[0]):
                best = (m.start(), GeoLock(name, tuple(tags)))
    if best:
        return best[1]
    tl = text.lower()
    for _, name, tags in config.GEO_LOCKS:
        if re.search(rf"\b{re.escape(tags[0])}\b", tl):
            return GeoLock(name, tuple(tags))
    return None


def tags_match(hit_tags: str, geo_tags: tuple) -> bool:
    ht = hit_tags.lower()
    return any(t in ht for t in geo_tags)


# ═════════════════════════ نماذج البيانات ═════════════════════════
@dataclass
class Visual:
    kind: str              # "video" | "image"
    path: Path
    source: str            # pixabay | flux | wikimedia | card
    ref_id: str = ""


@dataclass
class Scene:
    narration: str
    visual_prompt: str
    broll_query: str
    audio_path: Optional[Path] = None
    duration: float = 0.0
    visual: Optional[Visual] = None


@dataclass
class Script:
    title: str
    hashtags: list
    pinned_comment: str
    character_sheet: str
    scenes: list
    degraded: bool = False


@dataclass
class JobCtx:
    job_id: str
    dir: Path
    mode: Mode
    geo: Optional[GeoLock]
    rng: random.Random
    seed: int
    script: Optional[Script] = None


@dataclass
class ProductionResult:
    video_path: Path
    thumb_path: Optional[Path]
    duration: float
    width: int
    height: int
    title: str
    hashtags: list
    pinned_comment: str
    mode_id: str
    notes: list = field(default_factory=list)
    used_assets: dict = field(default_factory=dict)


# ═════════════════════════ وكيل السيناريو ═════════════════════════
_SHOTS = ("wide establishing shot", "intimate close-up detail", "aerial drone view", "low-angle hero shot",
          "slow tracking shot", "over-the-shoulder view", "macro texture shot", "silhouette against light")

_SYSTEM = (
    "You are a world-class short-form video screenwriter and cinematographer. "
    "You write vertical videos (TikTok / Reels / Shorts) whose narration is in Modern Standard Arabic (فصحى). "
    "You reply with ONE valid JSON object only: no markdown, no commentary."
)

_USER_TMPL = """Mode: {mode_en} — tone: {tone}
User idea (Arabic): {idea}
{geo_line}
Return JSON with exactly this schema:
{{
  "title": "viral Arabic title, max 60 characters",
  "character_sheet": "ENGLISH fixed description of recurring characters (age, face, hair, clothing) and the main location; empty string if none",
  "hashtags": ["#..." x 6-8, Arabic or English, no spaces inside a tag],
  "pinned_comment": "Arabic pinned comment that sparks engagement (a question)",
  "scenes": [
    {{"narration": "Arabic narration, {wmin}-{wmax} words",
      "visual_prompt": "ENGLISH cinematic shot description",
      "broll_query": "2-3 ENGLISH words to search stock footage"}}
  ]
}}
Rules:
- Exactly {n} scenes. Scene 1 opens with a powerful hook (a question or a shocking fact). The last scene ends with a short call to action (follow / comment).
- Narration must be natural, flowing, easy to read aloud; no emojis, no markdown, no stage directions.
- Every visual_prompt must differ in subject, shot size and angle, and must NOT contain readable text, logos or watermarks.
- Keep characters and clothing identical across scenes by reusing the character_sheet details.
- Facts must be accurate. If unsure, stay general instead of inventing names, dates or numbers.
- Never depict prophets, companions of the Prophet or religious figures. Never name or depict real private individuals.
"""


def extract_json(text: str) -> dict:
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.M).strip()
    a, b = t.find("{"), t.rfind("}")
    if a < 0 or b <= a:
        raise ValueError("no json object")
    raw = t[a:b + 1]
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return json.loads(re.sub(r",\s*([}\]])", r"\1", raw))


def _trim_words(text: str, limit: int = 42) -> str:
    words = text.split()
    if len(words) <= limit:
        return text
    cut = " ".join(words[:limit])
    m = max(cut.rfind("."), cut.rfind("؟"), cut.rfind("!"), cut.rfind("،"))
    return cut[:m + 1] if m > len(cut) * 0.5 else cut


class ScriptWriter:
    def __init__(self, hf: Optional["AsyncInferenceClient"]):
        self.hf = hf

    async def write(self, idea: str, mode: Mode, geo: Optional[GeoLock]) -> Script:
        if self.hf is not None and config.HF_TOKEN:
            n = 7
            geo_line = (f"The idea is tied to: {geo.name}. Every visual must clearly show this real place, "
                        f"its authentic architecture, landscape and people. Never show any other country.") if geo else ""
            user = _USER_TMPL.format(mode_en=mode.name_en, tone=mode.tone, idea=idea, geo_line=geo_line,
                                     n=n, wmin=18, wmax=28)
            models = [config.HF_LLM_MODEL, config.HF_LLM_MODEL, config.HF_LLM_FALLBACK_MODEL]
            for i, model in enumerate(models):
                if not model:
                    continue
                try:
                    resp = await asyncio.wait_for(self.hf.chat_completion(
                        messages=[{"role": "system", "content": _SYSTEM}, {"role": "user", "content": user}],
                        model=model, max_tokens=2600, temperature=0.8), timeout=150)
                    data = extract_json(resp.choices[0].message.content or "")
                    return self._build(data, idea, mode, geo)
                except Exception as e:
                    log.warning("فشل السيناريو (محاولة %d، %s): %s", i + 1, model, str(e)[:160])
                    if any(w in str(e).lower() for w in ("402", "429", "credit", "quota")):
                        break
        return self._fallback(idea, mode, geo)

    # ── تنظيف وتحقق ──
    def _build(self, d: dict, idea: str, mode: Mode, geo: Optional[GeoLock]) -> Script:
        scenes: list[Scene] = []
        for i, s in enumerate(d.get("scenes") or []):
            narr = _trim_words(clean_tts_text(s.get("narration", "")))
            if len(narr.split()) < 4:
                continue
            vp = str(s.get("visual_prompt", "")).strip()
            if not vp or re.search(r"[\u0600-\u06FF]", vp):
                vp = f"{_SHOTS[i % len(_SHOTS)]}, {mode.name_en} mood"
            bq = re.sub(r"[^A-Za-z0-9 \-']", " ", str(s.get("broll_query", ""))).strip()[:40]
            scenes.append(Scene(narr, vp, bq))
        if len(scenes) < 3:
            raise ValueError("عدد المشاهد غير كافٍ")
        scenes = scenes[:config.MAX_SCENES]
        if geo:  # قفل جغرافي: كل برومبت يحمل اسم المكان
            for sc in scenes:
                if geo.name.split(",")[0].lower() not in sc.visual_prompt.lower():
                    sc.visual_prompt += f", in {geo.name}"
        tags = []
        for h in d.get("hashtags") or []:
            h = "#" + re.sub(r"[\s#]+", "_", str(h)).strip("_")
            if len(h) > 1 and h not in tags:
                tags.append(h)
        for extra in ("#ريلز", "#شورتس", "#تيك_توك", "#فيديو"):
            if len(tags) < 6 and extra not in tags:
                tags.append(extra)
        title = clean_tts_text(d.get("title", "")) or idea[:60]
        pinned = clean_tts_text(d.get("pinned_comment", "")) or "ما رأيك؟ شاركنا رأيك في التعليقات 👇"
        return Script(title[:80], tags[:8], pinned, clean_tts_text(d.get("character_sheet", ""))[:600], scenes)

    def _fallback(self, idea: str, mode: Mode, geo: Optional[GeoLock]) -> Script:
        """سيناريو مبسّط من كلمات المستخدم نفسها عند تعذّر الـ LLM (لا يتوقف الإنتاج)."""
        text = clean_tts_text(idea)
        words = text.split()
        chunks = [" ".join(words[i:i + 22]) for i in range(0, len(words), 22)][:4] or [text]
        narr = ["هل تعلم قصة مذهلة؟ تابع للنهاية."] + chunks + ["إذا أعجبك الفيديو فتابعنا واكتب رأيك في التعليقات."]
        place = geo.name if geo else mode.name_en
        scenes = []
        for i, n in enumerate(narr):
            hint = mode.stock_hints[i % len(mode.stock_hints)]
            scenes.append(Scene(n, f"{_SHOTS[i % len(_SHOTS)]}, {place}, {mode.name_en} mood", hint))
        tags = ["#ريلز", "#شورتس", "#تيك_توك", "#فيديو", "#معلومات", "#قصص"]
        return Script(text[:60] or "فيديو جديد", tags, "ما رأيك؟ شاركنا رأيك في التعليقات 👇", "", scenes, degraded=True)


# ═════════════════════════ وكيل الصوت ═════════════════════════
class VoiceOver:
    async def synth(self, text: str, out: Path, mode: Mode) -> float:
        voices = [mode.voice] + [v for v in config.TTS_FALLBACK_VOICES if v != mode.voice]
        if edge_tts is not None:
            for v in voices[:3]:
                try:
                    comm = edge_tts.Communicate(text, v, rate=mode.voice_rate)
                    await asyncio.wait_for(comm.save(str(out)), timeout=60)
                    d = (await probe(out)).get("duration", 0)
                    if d > 0.5:
                        return d
                except Exception as e:
                    log.warning("edge-tts فشل (%s): %s", v, str(e)[:120])
        if gTTS is not None:
            try:
                await asyncio.wait_for(asyncio.to_thread(lambda: gTTS(text=text, lang="ar").save(str(out))), timeout=60)
                d = (await probe(out)).get("duration", 0)
                if d > 0.5:
                    return d
            except Exception as e:
                log.warning("gTTS فشل: %s", str(e)[:120])
        raise ProductionError("تعذّر توليد التعليق الصوتي. تأكد من اتصال الخادم بالإنترنت وحدّث edge-tts.")


# ═════════════════════════ وكيل المشاهد: Pixabay / FLUX / Wikimedia ═════════════════════════
_PIX_CACHE: dict[str, tuple[float, list]] = {}


def _http_status(e: Exception) -> Optional[int]:
    r = getattr(e, "response", None)
    return getattr(r, "status_code", None)


def _save_image(img, dest: Path) -> bool:
    """يحفظ صورة (PIL أو bytes) كـ JPEG سليم."""
    if Image is None:
        return False
    try:
        if isinstance(img, (bytes, bytearray)):
            img = Image.open(io.BytesIO(img))
        img = img.convert("RGB")
        if min(img.size) < 256:
            return False
        img.save(dest, "JPEG", quality=92)
        return True
    except Exception:
        return False


def _check_image(path: Path) -> bool:
    if Image is None:
        return path.exists() and path.stat().st_size > 2048
    try:
        with Image.open(path) as im:
            im.verify()
        return True
    except Exception:
        return False


def _pick_video_url(videos: dict) -> Optional[str]:
    for q in ("large", "medium", "small"):
        v = videos.get(q) or {}
        if v.get("url") and (v.get("size") or 0) < 90 * 1048576:
            return v["url"]
    return None


class AssetHub:
    """يجلب لكل مشهد أفضل مصدر بصري متاح، مع بدائل متتالية، دون تكرار المقاطع."""

    def __init__(self, http: httpx.AsyncClient, hf, db: Database):
        self.http, self.hf, self.db = http, hf, db
        self.flux_dead = False
        self.notes: set[str] = set()
        self.used_pixabay: list[str] = []
        self.used_wiki: list[str] = []
        self._sem = asyncio.Semaphore(config.ASSET_CONCURRENCY)

    async def get_visual(self, scene: Scene, idx: int, ctx: JobCtx) -> Visual:
        async with self._sem:
            order = ["stock", "flux", "wiki"] if ctx.rng.random() < ctx.mode.broll_ratio else ["flux", "stock", "wiki"]
            for step in order:
                try:
                    v = await getattr(self, f"_try_{step}")(scene, idx, ctx)
                except Exception as e:
                    log.warning("مصدر %s فشل للمشهد %d: %s", step, idx, str(e)[:140])
                    v = None
                if v:
                    return v
            self.notes.add("بعض المشاهد استُخدمت لها خلفية سينمائية بسيطة لعدم توفر مصدر مطابق")
            return await self.card(idx, ctx)

    # ── Pixabay: فيديو حقيقي ──
    async def _pixabay(self, q: str) -> list:
        c = _PIX_CACHE.get(q)
        if c and time.time() - c[0] < 3600:
            return list(c[1])
        r = await self.http.get("https://pixabay.com/api/videos/", timeout=25, params={
            "key": config.PIXABAY_KEY, "q": q, "per_page": 20, "safesearch": "true", "video_type": "film"})
        if r.status_code != 200:
            log.warning("Pixabay HTTP %s", r.status_code)
            return []
        hits = r.json().get("hits", [])
        _PIX_CACHE[q] = (time.time(), hits)
        return list(hits)

    async def _try_stock(self, scene: Scene, idx: int, ctx: JobCtx) -> Optional[Visual]:
        if not config.PIXABAY_KEY:
            return None
        geo, bq = ctx.geo, scene.broll_query.strip()
        queries: list[str] = []
        if geo:
            place = geo.name.split(",")[0]
            queries = [f"{place} {bq}".strip(), place]
        else:
            if bq:
                queries.append(bq)
            queries.append(ctx.mode.stock_hints[0])
        for q in dict.fromkeys(queries):
            hits = await self._pixabay(q[:100])
            ctx.rng.shuffle(hits)
            for hit in hits:
                vid = str(hit.get("id"))
                if vid in self.used_pixabay or self.db.is_asset_used("pixabay", vid):
                    continue
                if geo and not tags_match(str(hit.get("tags", "")), geo.tags):
                    continue  # قفل جغرافي صارم: لا نقبل لقطة لا تحمل وسم المكان
                url = _pick_video_url(hit.get("videos") or {})
                if not url:
                    continue
                dest = ctx.dir / f"stock_{idx:02d}.mp4"
                if await self._download(url, dest, 90) and await valid_media(dest):
                    self.used_pixabay.append(vid)
                    return Visual("video", dest, "pixabay", vid)
        return None

    # ── FLUX: صورة سينمائية مولّدة ──
    async def _try_flux(self, scene: Scene, idx: int, ctx: JobCtx) -> Optional[Visual]:
        if self.hf is None or not config.HF_TOKEN or self.flux_dead or Image is None:
            return None
        parts = []
        if ctx.script and ctx.script.character_sheet:
            parts.append(f"Consistent characters and setting: {ctx.script.character_sheet}")
        parts.append(scene.visual_prompt.rstrip(". "))
        if ctx.geo:
            parts.append(f"Authentic location: {ctx.geo.name}, true to the real place, its architecture and people")
        parts.append(ctx.mode.visual_style)
        parts.append("vertical 9:16 composition, photorealistic, no text, no letters, no watermark, no logo")
        prompt = ". ".join(parts)
        dest = ctx.dir / f"img_{idx:02d}.jpg"
        for kw in ({"width": 768, "height": 1344, "seed": ctx.seed, "num_inference_steps": 4},
                   {"width": 768, "height": 1344}, {}):
            try:
                img = await asyncio.wait_for(
                    self.hf.text_to_image(prompt, model=config.HF_IMAGE_MODEL, **kw), timeout=160)
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                msg, st = str(e).lower(), _http_status(e)
                if st in (402, 429) or "credit" in msg or "quota" in msg or "rate limit" in msg:
                    self.flux_dead = True
                    self.notes.add("انتهت حصة توليد الصور المجانية (FLUX) — استُخدمت مصادر بديلة")
                    return None
                log.warning("FLUX فشل (%s): %s", list(kw), msg[:140])
                continue
            if await asyncio.to_thread(_save_image, img, dest):
                return Visual("image", dest, "flux")
        return None

    # ── Wikimedia: صور حرة (نطاق عام / CC0 فقط) ──
    async def _try_wiki(self, scene: Scene, idx: int, ctx: JobCtx) -> Optional[Visual]:
        q = scene.broll_query.strip() or ctx.mode.stock_hints[0]
        if ctx.geo:
            q = f"{ctx.geo.name.split(',')[0]} {q}"
        r = await self.http.get("https://commons.wikimedia.org/w/api.php", timeout=25, params={
            "action": "query", "format": "json", "generator": "search", "gsrnamespace": 6, "gsrlimit": 15,
            "gsrsearch": f"{q} filetype:bitmap", "prop": "imageinfo", "iiprop": "url|size|mime|extmetadata",
            "iiurlwidth": 1600, "iiextmetadatafilter": "LicenseShortName"})
        if r.status_code != 200:
            return None
        pages = ((r.json().get("query") or {}).get("pages") or {}).values()
        for p in sorted(pages, key=lambda x: x.get("index", 99)):
            ii = (p.get("imageinfo") or [{}])[0]
            lic = str(((ii.get("extmetadata") or {}).get("LicenseShortName") or {}).get("value", "")).lower()
            if not (lic.startswith("cc0") or "public domain" in lic or lic.startswith("pd")):
                continue
            if ii.get("width", 0) < 800 or ii.get("height", 0) < 600:
                continue
            if str(ii.get("mime", "")) not in ("image/jpeg", "image/png", "image/webp"):
                continue
            pid = str(p.get("pageid"))
            if pid in self.used_wiki or self.db.is_asset_used("wikimedia", pid):
                continue
            if ctx.geo and not any(t in str(p.get("title", "")).lower() for t in ctx.geo.tags):
                continue
            url = ii.get("thumburl") or ii.get("url")
            dest = ctx.dir / f"wiki_{idx:02d}.jpg"
            if url and await self._download(url, dest, 30) and await asyncio.to_thread(_check_image, dest):
                self.used_wiki.append(pid)
                return Visual("image", dest, "wikimedia", pid)
        return None

    # ── آخر بديل: خلفية سينمائية داكنة (بدون أي رسومات وهمية) ──
    async def card(self, idx: int, ctx: JobCtx) -> Visual:
        dest = ctx.dir / f"card_{idx:02d}.jpg"
        ok, _ = await ffmpeg("-f", "lavfi", "-i",
                             f"gradients=s={W}x{H}:c0=0x0b0f14:c1=0x1d2b3a:x0=0:y0=0:x1=0:y1={H}:d=1",
                             "-frames:v", "1", dest)
        if not ok:
            ok, err = await ffmpeg("-f", "lavfi", "-i", f"color=c=0x0b0f14:s={W}x{H}:d=1", "-frames:v", "1", dest)
            if not ok:
                raise ProductionError(f"FFmpeg لا يعمل بشكل صحيح على الخادم: {err[:120]}")
        return Visual("image", dest, "card")

    async def _download(self, url: str, dest: Path, max_mb: int) -> bool:
        try:
            async with self.http.stream("GET", url, timeout=60) as r:
                if r.status_code != 200:
                    return False
                size = 0
                with open(dest, "wb") as f:
                    async for chunk in r.aiter_bytes(262144):
                        size += len(chunk)
                        if size > max_mb * 1048576:
                            return False
                        f.write(chunk)
            return dest.stat().st_size > 2048
        except Exception as e:
            log.warning("فشل التحميل: %s", str(e)[:120])
            return False


# ═════════════════════════ الترجمة العربية (ASS) ═════════════════════════
def _ass_time(t: float) -> str:
    cs = int(round(t * 100))
    return f"{cs // 360000}:{(cs // 6000) % 60:02d}:{(cs // 100) % 60:02d}.{cs % 100:02d}"


def split_phrases(text: str, max_words: int = 4) -> list[str]:
    chunks, cur = [], []
    for w in text.split():
        cur.append(w)
        if len(cur) >= max_words or (len(cur) >= 2 and w[-1] in ".،,؟?!؛:"):
            chunks.append(" ".join(cur))
            cur = []
    if cur:
        if chunks and len(cur) == 1:
            chunks[-1] += " " + cur[0]
        else:
            chunks.append(" ".join(cur))
    return [c.strip(" .،,؛:!؟?") or c for c in chunks]


def build_ass(text: str, duration: float) -> str:
    phrases = split_phrases(text)
    total = sum(len(p) for p in phrases) or 1
    span, t, events = max(0.6, duration - 0.05), 0.0, []
    for p in phrases:
        d = span * len(p) / total
        safe = p.replace("{", "").replace("}", "").replace("\n", "\\N")
        events.append(f"Dialogue: 0,{_ass_time(t)},{_ass_time(t + d)},Default,,0,0,0,,{safe}")
        t += d
    return (
        "[Script Info]\nScriptType: v4.00+\nPlayResX: %d\nPlayResY: %d\nWrapStyle: 0\nScaledBorderAndShadow: yes\n\n"
        "[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
        "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
        "Alignment, MarginL, MarginR, MarginV, Encoding\n"
        "Style: Default,%s,%d,&H00FFFFFF,&H000000FF,&H00000000,&H64000000,-1,0,0,0,100,100,0,0,1,6,2,2,90,90,380,1\n\n"
        "[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n%s\n"
    ) % (W, H, config.FONT_FAMILY, config.SUB_FONT_SIZE, "\n".join(events))


# ═════════════════════════ المحرك الرئيسي ═════════════════════════
async def _noop(stage: str, detail: str = "") -> None:
    return None


class VideoProductionEngine:
    def __init__(self, db: Database):
        self.db = db
        self.http: Optional[httpx.AsyncClient] = None
        self.hf = None
        self.writer: Optional[ScriptWriter] = None
        self.voice = VoiceOver()
        self.has_subtitles_filter = True
        self.has_fonts = False
        self._subs_ok = False

    # ── دورة الحياة ──
    async def start(self) -> tuple[list[str], list[str]]:
        """يهيّئ المحرك ويرجع (أخطاء قاتلة، تحذيرات)."""
        self.http = httpx.AsyncClient(follow_redirects=True, timeout=30, headers={
            "User-Agent": "GenesisCinemaStudio/1.0 (Telegram video bot; contact: bot owner)"})
        if AsyncInferenceClient is not None and config.HF_TOKEN:
            try:
                self.hf = AsyncInferenceClient(api_key=config.HF_TOKEN, timeout=150)
            except Exception as e:
                log.warning("تعذّر تهيئة HuggingFace: %s", e)
        self.writer = ScriptWriter(self.hf)
        fatal, warn = [], []
        code, out, _ = await run_cmd("ffmpeg", "-hide_banner", "-filters", timeout=30)
        if code != 0:
            fatal.append("FFmpeg غير مثبّت (sudo apt install ffmpeg)")
        else:
            for f in ("zoompan", "subtitles", "colorbalance", "vignette"):
                if not re.search(rf"\s{f}\s", out):
                    if f == "subtitles":
                        self.has_subtitles_filter = False
                        warn.append("FFmpeg بدون libass: لن تُحرق الترجمة العربية")
                    else:
                        fatal.append(f"FFmpeg ينقصه الفلتر {f}")
        code, _, _ = await run_cmd("ffprobe", "-version", timeout=15)
        if code != 0:
            fatal.append("ffprobe غير موجود")
        self.has_fonts = any(p.suffix.lower() in (".ttf", ".otf") for p in config.FONTS_DIR.glob("*"))
        if config.SUBTITLES_ENABLED and not self.has_fonts:
            warn.append(f"لا يوجد خط عربي في assets/fonts — ضع {config.FONT_FAMILY}-Bold.ttf لجودة أفضل للترجمة")
        if not config.PIXABAY_KEY:
            warn.append("PIXABAY_KEY غير مضبوط: لن تُستخدم لقطات الفيديو الحقيقية")
        if not config.HF_TOKEN:
            warn.append("HF_TOKEN غير مضبوط: سيناريو مبسّط وبدون صور FLUX")
        if edge_tts is None and gTTS is None:
            fatal.append("ثبّت edge-tts (pip install edge-tts) للتعليق الصوتي")
        if Image is None:
            warn.append("Pillow غير مثبّت: لن تعمل صور FLUX وويكيميديا")
        return fatal, warn

    async def close(self) -> None:
        if self.http:
            await self.http.aclose()

    async def _cleanup_old(self) -> None:
        limit = time.time() - config.OUTPUT_TTL_HOURS * 3600
        for d in (config.OUTPUT_DIR, config.WORK_DIR):
            for p in d.glob("*"):
                try:
                    if p.stat().st_mtime < limit:
                        shutil.rmtree(p, ignore_errors=True) if p.is_dir() else p.unlink(missing_ok=True)
                except OSError:
                    pass

    # ── نقطة الدخول ──
    async def produce(self, idea: str, mode_id: str, progress: Optional[ProgressCB] = None) -> ProductionResult:
        mode = config.MODES[mode_id]
        cb = progress or _noop

        async def say(stage: str, detail: str = "") -> None:
            try:
                await cb(stage, detail)
            except Exception:
                pass

        job_id = uuid.uuid4().hex[:10]
        seed = int(hashlib.sha256(job_id.encode()).hexdigest()[:8], 16) % (2 ** 31)
        job_dir = config.WORK_DIR / job_id
        job_dir.mkdir(parents=True, exist_ok=True)
        ctx = JobCtx(job_id, job_dir, mode, detect_geo(idea), random.Random(seed), seed)
        notes: list[str] = []
        try:
            await self._cleanup_old()

            # 1) السيناريو
            await say("script")
            script = await self.writer.write(idea, mode, ctx.geo)
            ctx.script = script
            if script.degraded:
                notes.append("استُخدم سيناريو مبسّط لأن خدمة الكتابة الذكية غير متاحة حالياً")
            scenes = script.scenes

            # 2) الصوت (بالتوازي) — مدة كل مشهد تُقاس من ملف الصوت نفسه
            await say("voice")
            sem = asyncio.Semaphore(3)

            async def _voice(i: int, sc: Scene):
                async with sem:
                    sc.audio_path = job_dir / f"voice_{i:02d}.mp3"
                    sc.duration = await self.voice.synth(sc.narration, sc.audio_path, mode)

            res = await asyncio.gather(*[_voice(i, s) for i, s in enumerate(scenes)], return_exceptions=True)
            scenes = [s for s, r in zip(scenes, res) if not isinstance(r, Exception)]
            if len(scenes) < 3:
                err = next((r for r in res if isinstance(r, ProductionError)), None)
                raise err or ProductionError("تعذّر توليد الصوت لمعظم المشاهد.")
            script.scenes = scenes

            # 3) المشاهد البصرية
            hub = AssetHub(self.http, self.hf, self.db)
            done = 0

            async def _asset(i: int, sc: Scene):
                nonlocal done
                sc.visual = await hub.get_visual(sc, i, ctx)
                done += 1
                await say("assets", f"{done}/{len(scenes)}")

            await say("assets", f"0/{len(scenes)}")
            await asyncio.gather(*[_asset(i, s) for i, s in enumerate(scenes)])

            # 4) المونتاج
            if config.FONTS_DIR.exists() and self.has_fonts:
                (job_dir / "fonts").mkdir(exist_ok=True)
                for f in config.FONTS_DIR.glob("*"):
                    if f.suffix.lower() in (".ttf", ".otf"):
                        shutil.copy(f, job_dir / "fonts" / f.name)
            self._subs_ok = config.SUBTITLES_ENABLED and self.has_subtitles_filter
            parts: list[Path] = []
            for i, sc in enumerate(scenes):
                await say("render", f"{i + 1}/{len(scenes)}")
                parts.append(await self._render_scene(i, sc, ctx, hub))
            if config.SUBTITLES_ENABLED and not self._subs_ok:
                notes.append("تعذّر حرق الترجمة العربية (تأكد من libass وخط عربي في assets/fonts)")

            await say("finalize")
            final = await self._assemble(parts, ctx, sum(s.duration + config.SCENE_PAD for s in scenes))
            info = await probe(final)
            thumb = await self._thumbnail(final, ctx)
            notes += sorted(hub.notes)
            return ProductionResult(
                video_path=final, thumb_path=thumb, duration=info.get("duration", 0.0),
                width=info.get("width", W), height=info.get("height", H), title=script.title,
                hashtags=script.hashtags, pinned_comment=script.pinned_comment, mode_id=mode_id, notes=notes,
                used_assets={"pixabay": hub.used_pixabay, "wikimedia": hub.used_wiki})
        finally:
            if not config.KEEP_WORK_FILES:
                shutil.rmtree(job_dir, ignore_errors=True)

    # ── مونتاج مشهد واحد ──
    def _motion(self, idx: int, frames: int, mag: float) -> str:
        c_x, c_y = "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"
        k = idx % 4
        if k == 0:    # تقريب
            z, x, y = f"1+{mag:.4f}*on/{frames}", c_x, c_y
        elif k == 1:  # تبعيد
            z, x, y = f"1+{mag:.4f}-{mag:.4f}*on/{frames}", c_x, c_y
        elif k == 2:  # تحريك يمين
            z, x, y = f"{1 + mag:.4f}", f"(iw-iw/zoom)*on/{frames}", c_y
        else:         # تحريك يسار
            z, x, y = f"{1 + mag:.4f}", f"(iw-iw/zoom)*(1-on/{frames})", c_y
        return f"zoompan=z='{z}':x='{x}':y='{y}':d={frames}:s={W}x{H}:fps={FPS}"

    async def _render_once(self, idx: int, sc: Scene, visual: Visual, ctx: JobCtx, subs: bool, out: Path) -> tuple[bool, str]:
        D = sc.duration + config.SCENE_PAD
        frames = max(2, int(round(D * FPS)))
        grade = f"{ctx.mode.color_filter},format=yuv420p"
        if visual.kind == "image":
            pre = f"scale={int(W * 1.5)}:{int(H * 1.5)}:force_original_aspect_ratio=increase,crop={int(W * 1.5)}:{int(H * 1.5)}"
            vf = f"{pre},{self._motion(idx, frames, ctx.mode.motion)},setsar=1,{grade}"
            inputs = ["-i", visual.path]
        else:
            vf = f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},setsar=1,fps={FPS},{grade}"
            dur = (await probe(visual.path)).get("duration", 0.0)
            start = ctx.rng.uniform(0, dur - D - 0.5) if dur > D + 1.0 else 0.0
            inputs = ["-stream_loop", "-1", "-ss", f"{start:.2f}", "-i", visual.path]
        if idx > 0:
            vf += ",fade=t=in:st=0:d=0.15"
        if subs:
            ass = ctx.dir / f"sub_{idx:02d}.ass"
            ass.write_text(build_ass(sc.narration, sc.duration), encoding="utf-8")
            vf += f",subtitles={ass.name}" + (":fontsdir=fonts" if (ctx.dir / "fonts").exists() else "")
        return await ffmpeg(
            *inputs, "-i", sc.audio_path, "-map", "0:v:0", "-map", "1:a:0", "-vf", vf,
            "-af", "aresample=44100,apad", "-t", f"{D:.3f}",
            "-c:v", "libx264", "-preset", config.X264_PRESET, "-crf", "23", "-r", str(FPS), "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "160k", "-ac", "2", out, cwd=ctx.dir)

    async def _render_scene(self, idx: int, sc: Scene, ctx: JobCtx, hub: AssetHub) -> Path:
        out = ctx.dir / f"scene_{idx:02d}.mp4"
        # خطة المحاولات: (1) مع الترجمة (2) بدون ترجمة (3) بديل أخير: خلفية بسيطة
        plan: list[tuple[Optional[Visual], bool]] = []
        if self._subs_ok:
            plan.append((sc.visual, True))
        plan += [(sc.visual, False), (None, False)]
        subs_failed, last_err = False, ""
        for n, (vis, subs) in enumerate(plan):
            if vis is None:
                vis = await hub.card(idx, ctx)
            ok, err = await self._render_once(idx, sc, vis, ctx, subs, out)
            if ok and await valid_media(out, need_audio=True):
                if subs_failed and vis is sc.visual:
                    self._subs_ok = False  # الترجمة فشلت وبدونها نجح → نوقفها لبقية المشاهد
                return out
            if subs:
                subs_failed = True
            last_err = err
            log.warning("فشل مونتاج المشهد %d (المحاولة %d): %s", idx, n + 1, err[:200])
        raise ProductionError(f"فشل مونتاج أحد المشاهد: {last_err[:150]}")

    # ── التجميع النهائي ──
    async def _assemble(self, parts: list[Path], ctx: JobCtx, total: float) -> Path:
        lst = ctx.dir / "list.txt"
        lst.write_text("".join(f"file '{p.name}'\n" for p in parts), encoding="utf-8")
        base = ctx.dir / "base.mp4"
        ok, err = await ffmpeg("-f", "concat", "-safe", "0", "-i", lst.name, "-c:v", "copy", "-c:a", "aac",
                               "-b:a", "160k", "-movflags", "+faststart", base, cwd=ctx.dir)
        if not ok:
            raise ProductionError(f"فشل دمج المشاهد: {err[:150]}")
        final = config.OUTPUT_DIR / f"{ctx.job_id}.mp4"

        tracks = [p for p in config.MUSIC_DIR.glob("*") if p.suffix.lower() in (".mp3", ".m4a", ".wav", ".ogg")]
        mixed = False
        if tracks:  # موسيقى خلفية اختيارية بصوت منخفض
            music = ctx.rng.choice(tracks)
            ok, _ = await ffmpeg(
                "-i", base, "-stream_loop", "-1", "-i", music, "-filter_complex",
                f"[1:a]volume={config.MUSIC_VOLUME}[m];[0:a][m]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[a]",
                "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "160k",
                "-shortest", "-movflags", "+faststart", final)
            mixed = ok and await valid_media(final, need_audio=True)
        if not mixed:
            shutil.copy(base, final)

        if not await validate_and_heal(final, need_audio=True):
            raise ProductionError("الفيديو الناتج تالف ولم يمكن إصلاحه. حاول مرة أخرى.")
        await self._shrink_if_needed(final, total)
        return final

    async def _shrink_if_needed(self, path: Path, duration: float) -> None:
        limit = config.MAX_FINAL_MB * 1048576
        if path.stat().st_size <= limit:
            return
        dur = max(5.0, (await probe(path)).get("duration", duration))
        kbps = max(500, int(config.MAX_FINAL_MB * 8192 / dur) - 160)
        tmp = path.with_name(path.stem + ".small.mp4")
        ok, _ = await ffmpeg("-i", path, "-c:v", "libx264", "-preset", config.X264_PRESET, "-b:v", f"{kbps}k",
                             "-maxrate", f"{kbps}k", "-bufsize", f"{kbps * 2}k", "-c:a", "aac", "-b:a", "128k",
                             "-movflags", "+faststart", tmp)
        if ok and await valid_media(tmp, need_audio=True):
            shutil.move(str(tmp), str(path))
        else:
            tmp.unlink(missing_ok=True)

    async def _thumbnail(self, video: Path, ctx: JobCtx) -> Optional[Path]:
        thumb = config.OUTPUT_DIR / f"{ctx.job_id}.jpg"
        for ss in ("1", "0"):
            ok, _ = await ffmpeg("-ss", ss, "-i", video, "-frames:v", "1", "-vf", "scale=320:-2", thumb)
            if ok and thumb.exists() and thumb.stat().st_size > 500:
                return thumb
        return None
