# -*- coding: utf-8 -*-
"""
Genesis Cinema Studio — main.py
واجهة تيليجرام (Pyrogram / Kurigram): وكيل الاستقبال ← وكيل السيناريو ← وكيل المونتاج.

التشغيل:  python main.py
"""
import asyncio

# توافق مع Python 3.12+ (Pyrogram يطلب حلقة أحداث عند الاستيراد)
try:
    asyncio.get_event_loop()
except RuntimeError:
    asyncio.set_event_loop(asyncio.new_event_loop())

import logging
import os
import shutil
import signal
import sys
import time

from pyrogram import Client, filters, idle
from pyrogram.enums import ParseMode
from pyrogram.errors import FloodWait
from pyrogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

import config
from database import Database
from sentinel_evolution import ProductionError, ProductionResult, VideoProductionEngine

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
log = logging.getLogger("genesis.bot")

db = Database()
engine = VideoProductionEngine(db)
app = Client("genesis_studio", api_id=config.API_ID, api_hash=config.API_HASH,
             bot_token=config.BOT_TOKEN, workdir=str(config.DATA_DIR))

PM = ParseMode.DISABLED                 # نص عادي: لا تُفسَّر _ و * في العناوين والهاشتاجات
JOB_SEM = asyncio.Semaphore(config.MAX_CONCURRENT_JOBS)
ACTIVE_USERS: set[int] = set()          # مستخدم واحد = فيديو واحد في نفس الوقت
QUEUE: list[int] = []                   # ترتيب الانتظار
BG_TASKS: set[asyncio.Task] = set()     # مراجع قوية للمهام الخلفية
STARTUP_WARNINGS: list[str] = []
SHUTTING_DOWN = False                   # عند True: لا نقبل فيديوهات جديدة

A_RECEPTION = "🛎 وكيل الاستقبال"
A_WRITER = "✍️ وكيل السيناريو"
A_VOICE = "🎙 وكيل الصوت"
A_EDITOR = "🎬 وكيل المونتاج"

WELCOME = (
    "🎬 أهلاً بك في Genesis Cinema Studio\n\n"
    f"{A_RECEPTION}: أنسّق لك فريق الإنتاج\n"
    f"{A_WRITER} • {A_VOICE} • {A_EDITOR}\n\n"
    "١) اختر وضع الإنتاج من الأزرار\n"
    "٢) أرسل فكرة الفيديو (جملة أو فقرة)\n"
    "٣) أسلّمك فيديو MP4 عمودي جاهز لريلز / شورتس / تيك توك، بتعليق صوتي عربي وترجمة ومونتاج.\n\n"
    "💡 اذكر البلد أو المدينة في فكرتك وسأقفل كل المشاهد عليها."
)

STAGES = ["queue", "script", "voice", "assets", "render", "finalize", "upload"]


# ═════════════════════════ أدوات مساعدة ═════════════════════════
def is_admin(uid: int) -> bool:
    return uid in config.ADMIN_IDS


def modes_keyboard() -> InlineKeyboardMarkup:
    rows, row = [], []
    for mid in config.MODE_ORDER:
        m = config.MODES[mid]
        row.append(InlineKeyboardButton(f"{m.emoji} {m.name_ar}", callback_data=f"mode:{mid}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    return InlineKeyboardMarkup(rows)


def after_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("🎬 فيديو جديد", callback_data="again"),
        InlineKeyboardButton("🎞 تغيير الوضع", callback_data="modes"),
    ]])


def spawn(coro) -> None:
    t = asyncio.create_task(coro)
    BG_TASKS.add(t)
    t.add_done_callback(BG_TASKS.discard)


async def retry_flood(factory, tries: int = 3):
    for i in range(tries):
        try:
            return await factory()
        except FloodWait as e:
            await asyncio.sleep(min(int(e.value) + 1, 60))
            if i == tries - 1:
                raise


class ProgressReporter:
    """يحدّث رسالة واحدة بتقدّم الإنتاج (مع تحديد معدل التعديل لتفادي FloodWait)."""

    def __init__(self, msg: Message, mode: config.Mode):
        self.msg, self.mode = msg, mode
        self._last_text, self._last_t = "", 0.0

    def render(self, stage: str, detail: str = "") -> str:
        idx = STAGES.index(stage) if stage in STAGES else 0
        pct = int(idx / (len(STAGES) - 1) * 100)
        bar = "▰" * (idx + 1) + "▱" * (len(STAGES) - idx - 1)
        lines = {
            "queue": f"{A_RECEPTION}: فكرتك في الطابور — ترتيبك {detail} ⏳",
            "script": f"{A_WRITER}: أكتب القصة وأقسّمها إلى مشاهد ✍️",
            "voice": f"{A_VOICE}: أسجّل التعليق الصوتي العربي 🎙",
            "assets": f"{A_EDITOR}: أجمع اللقطات والصور المطابقة للموضوع {detail} 🎞",
            "render": f"{A_EDITOR}: المونتاج والتدرج اللوني والترجمة {detail} 🎬",
            "finalize": f"{A_EDITOR}: الدمج النهائي والفحص ✅",
            "upload": f"{A_RECEPTION}: أرفع الفيديو إليك 📤",
        }
        return f"{self.mode.emoji} {self.mode.name_ar}\n{bar} {pct}%\n\n{lines.get(stage, '')}"

    async def __call__(self, stage: str, detail: str = "") -> None:
        text = self.render(stage, detail)
        now = time.monotonic()
        if text == self._last_text or (now - self._last_t < 2.5 and stage != "upload"):
            return
        try:
            await self.msg.edit_text(text, parse_mode=PM)
            self._last_text, self._last_t = text, now
        except FloodWait:
            self._last_t = now + 10
        except Exception:
            pass  # التقدّم غير حرج


def make_caption(r: ProductionResult) -> str:
    return f"🎬 {r.title}\n\n{' '.join(r.hashtags)}"[:1000]


async def send_mode_card(client: Client, chat_id: int, mode: config.Mode) -> None:
    text = (f"{mode.emoji} وضع «{mode.name_ar}»\n{mode.desc_ar}\n\n"
            f"✍️ أرسل الآن فكرة الفيديو.\nمثال: {mode.sample_idea}")
    sample = db.get_sample(mode.id)
    if sample:
        for src in (sample.get("file_id"), sample.get("path")):
            if not src:
                continue
            try:
                await client.send_video(chat_id, src, caption=text, parse_mode=PM, supports_streaming=True)
                return
            except Exception as e:
                log.warning("تعذّر إرسال مثال %s: %s", mode.id, str(e)[:100])
    await client.send_message(chat_id, text, parse_mode=PM)


# ═════════════════════════ دورة إنتاج فيديو ═════════════════════════
async def run_job(client: Client, chat_id: int, uid: int, idea: str, mode_id: str) -> None:
    mode = config.MODES[mode_id]
    status = await client.send_message(chat_id, f"{A_RECEPTION}: استلمت فكرتك ✅", parse_mode=PM)
    rep = ProgressReporter(status, mode)
    QUEUE.append(uid)
    try:
        if JOB_SEM.locked():
            await rep("queue", str(len(QUEUE)))
        async with JOB_SEM:
            if uid in QUEUE:
                QUEUE.remove(uid)
            result = await asyncio.wait_for(engine.produce(idea, mode_id, progress=rep), timeout=config.JOB_TIMEOUT)

        await rep("upload")
        sent = await retry_flood(lambda: client.send_video(
            chat_id, str(result.video_path), caption=make_caption(result), parse_mode=PM,
            duration=int(result.duration), width=result.width, height=result.height,
            thumb=str(result.thumb_path) if result.thumb_path else None, supports_streaming=True))
        await db.record_success(uid, mode_id, idea, result.title, result.used_assets)

        left = db.remaining_quota(uid, is_admin(uid))
        extra = "" if is_admin(uid) else f"\n\n📊 المتبقي لك اليوم: {left} فيديو"
        notes = f"\nℹ️ {'؛ '.join(result.notes)}" if result.notes else ""
        await client.send_message(
            chat_id, f"📌 التعليق المثبت المقترح:\n{result.pinned_comment}{notes}{extra}",
            parse_mode=PM, reply_markup=after_keyboard())
        try:
            await status.delete()
        except Exception:
            pass
        log.info("تم إنتاج فيديو للمستخدم %s (%s) msg=%s", uid, mode_id, getattr(sent, "id", "?"))

    except ProductionError as e:
        await db.record_failure(uid, mode_id, idea, e.user_message)
        await _fail(status, e.user_message)
    except asyncio.TimeoutError:
        await db.record_failure(uid, mode_id, idea, "timeout")
        await _fail(status, "استغرق الإنتاج وقتاً أطول من المسموح. جرّب فكرة أقصر أو أعد المحاولة.")
    except Exception as e:
        log.exception("خطأ غير متوقع أثناء الإنتاج")
        await db.record_failure(uid, mode_id, idea, repr(e))
        await _fail(status, "حدث خطأ غير متوقع أثناء الإنتاج. لم يُحسب من حصتك، أعد المحاولة بعد قليل.")
    finally:
        if uid in QUEUE:
            QUEUE.remove(uid)
        ACTIVE_USERS.discard(uid)


async def _fail(status: Message, text: str) -> None:
    try:
        await status.edit_text(f"❌ {text}", parse_mode=PM, reply_markup=after_keyboard())
    except Exception:
        pass


async def try_start(client: Client, chat_id: int, uid: int, name: str, idea: str) -> None:
    """يتحقق من الوضع والحصة ثم يطلق الإنتاج في الخلفية."""
    mode_id = db.get_mode(uid)
    if not mode_id:
        await db.set_pending(uid, idea)
        await client.send_message(chat_id, f"{A_RECEPTION}: اختر وضع الإنتاج أولاً، وسأبدأ بفكرتك مباشرة 👇",
                                  reply_markup=modes_keyboard(), parse_mode=PM)
        return
    if SHUTTING_DOWN:
        await client.send_message(chat_id, "🔄 البوت يعيد تشغيل نفسه (دقيقتان تقريباً). أرسل فكرتك بعد قليل.", parse_mode=PM)
        return
    if uid in ACTIVE_USERS:
        await client.send_message(chat_id, "⏳ لديك فيديو قيد الإنتاج الآن. انتظر حتى يصلك.", parse_mode=PM)
        return
    if db.remaining_quota(uid, is_admin(uid)) <= 0:
        await client.send_message(
            chat_id, f"وصلت لحدّك اليومي ({config.DAILY_LIMIT} فيديو). يتجدد عند منتصف الليل 🌙", parse_mode=PM)
        return
    ACTIVE_USERS.add(uid)
    await db.set_mode(uid, mode_id, name)
    spawn(run_job(client, chat_id, uid, idea, mode_id))


# ═════════════════════════ المعالجات ═════════════════════════
@app.on_message(filters.private & filters.command(["start", "help", "modes"]))
async def cmd_start(client: Client, message: Message):
    db.user(message.from_user.id)
    if message.command[0] == "modes":
        await message.reply_text("اختر وضع الإنتاج 👇", reply_markup=modes_keyboard(), parse_mode=PM)
    else:
        await message.reply_text(WELCOME, reply_markup=modes_keyboard(), parse_mode=PM)


@app.on_callback_query()
async def on_callback(client: Client, cq: CallbackQuery):
    uid, data = cq.from_user.id, cq.data or ""
    chat_id = cq.message.chat.id
    try:
        if data.startswith("mode:"):
            mode = config.MODES.get(data[5:])
            if not mode:
                await cq.answer("وضع غير معروف", show_alert=True)
                return
            await db.set_mode(uid, mode.id, cq.from_user.first_name or "")
            await cq.answer(f"✅ {mode.name_ar}")
            await send_mode_card(client, chat_id, mode)
            pending = await db.pop_pending(uid)
            if pending:
                await try_start(client, chat_id, uid, cq.from_user.first_name or "", pending)
        elif data == "modes":
            await cq.answer()
            await client.send_message(chat_id, "اختر وضع الإنتاج 👇", reply_markup=modes_keyboard(), parse_mode=PM)
        elif data == "again":
            await cq.answer()
            await client.send_message(chat_id, f"{A_RECEPTION}: أرسل فكرة الفيديو الجديدة ✍️", parse_mode=PM)
        else:
            await cq.answer()
    except FloodWait as e:
        await asyncio.sleep(min(int(e.value), 10))
    except Exception:
        log.exception("خطأ في معالج الأزرار")


@app.on_message(filters.private & filters.command("stats"))
async def cmd_stats(client: Client, message: Message):
    if not is_admin(message.from_user.id):
        return
    s = db.stats()
    warn = "\n".join(f"• {w}" for w in STARTUP_WARNINGS) or "لا توجد"
    await message.reply_text(
        f"📊 فيديوهات: {s['videos']} | إخفاقات: {s['failures']}\n👥 مستخدمون: {s['users']} | "
        f"🎞 أمثلة: {s['samples']}/17\n⏳ في الطابور: {len(QUEUE)}\n\n⚠️ تحذيرات التشغيل:\n{warn}", parse_mode=PM)


@app.on_message(filters.private & filters.command("samples"))
async def cmd_samples(client: Client, message: Message):
    """للمشرف فقط: يبني فيديو مثال لكل وضع ناقص (أو لوضع محدد: /samples horror) ويحفظ file_id."""
    if not is_admin(message.from_user.id):
        return
    arg = message.command[1].strip() if len(message.command) > 1 else ""
    targets = [arg] if arg in config.MODES else [m for m in config.MODE_ORDER if not db.get_sample(m)]
    if not targets:
        await message.reply_text("✅ كل الأمثلة جاهزة. استخدم /samples <mode_id> لإعادة بناء وضع محدد.", parse_mode=PM)
        return
    await message.reply_text(f"🎞 سأبني {len(targets)} مثال/أمثلة تباعاً (قد يستغرق وقتاً).\n"
                             f"يمكنك أيضاً وضع ملفات data/samples/<mode_id>.mp4 يدوياً.", parse_mode=PM)
    spawn(build_samples(client, message.chat.id, targets))


async def build_samples(client: Client, chat_id: int, targets: list[str]) -> None:
    for mid in targets:
        mode = config.MODES[mid]
        try:
            async with JOB_SEM:
                r = await asyncio.wait_for(engine.produce(mode.sample_idea, mid), timeout=config.JOB_TIMEOUT)
            keep = config.SAMPLES_DIR / f"{mid}.mp4"
            shutil.copy(r.video_path, keep)
            sent = await retry_flood(lambda: client.send_video(
                chat_id, str(keep), caption=f"مثال: {mode.emoji} {mode.name_ar}", parse_mode=PM,
                duration=int(r.duration), width=r.width, height=r.height, supports_streaming=True))
            await db.set_sample(mid, str(keep), sent.video.file_id)
        except Exception as e:
            log.exception("فشل بناء مثال %s", mid)
            await client.send_message(chat_id, f"❌ تعذّر بناء مثال {mode.name_ar}: {str(e)[:120]}", parse_mode=PM)
    await client.send_message(chat_id, "✅ انتهى بناء الأمثلة.", parse_mode=PM)


_COMMANDS = ["start", "help", "modes", "stats", "samples"]


@app.on_message(filters.private & filters.text & ~filters.command(_COMMANDS))
async def on_idea(client: Client, message: Message):
    idea = (message.text or "").strip()
    uid = message.from_user.id
    if len(idea) < config.MIN_IDEA_CHARS:
        await message.reply_text("✍️ أرسل فكرة أوضح قليلاً (جملة كاملة على الأقل).", parse_mode=PM)
        return
    if len(idea) > config.MAX_IDEA_CHARS:
        idea = idea[:config.MAX_IDEA_CHARS]
    await try_start(client, message.chat.id, uid, message.from_user.first_name or "", idea)


@app.on_message(filters.private & ~filters.text & ~filters.service)
async def on_other(client: Client, message: Message):
    await message.reply_text("أرسل فكرة الفيديو كنص من فضلك ✍️", parse_mode=PM)


# ═════════════════════════ التشغيل ═════════════════════════
async def auto_stop() -> None:
    """بعد MAX_RUN_MINUTES: يمنع الطلبات الجديدة، ينتظر الفيديوهات الجارية (حتى 6 دقائق)، ثم يوقف البوت بسلام."""
    global SHUTTING_DOWN
    await asyncio.sleep(config.MAX_RUN_MINUTES * 60)
    SHUTTING_DOWN = True
    log.info("⏰ انتهت مدة التشغيل المحددة — إيقاف منظم")
    deadline = time.monotonic() + 360
    while (ACTIVE_USERS or JOB_SEM.locked()) and time.monotonic() < deadline:
        await asyncio.sleep(5)
    os.kill(os.getpid(), signal.SIGINT)   # يُنهي idle() فيُحفظ كل شيء ويخرج البرنامج


async def amain() -> None:
    await db.load()
    fatal, warn = await engine.start()
    STARTUP_WARNINGS.extend(warn)
    for w in warn:
        log.warning("⚠️ %s", w)
    if fatal:
        for f in fatal:
            log.error("❌ %s", f)
        await engine.close()
        return
    async with app:
        me = await app.get_me()
        log.info("✅ Genesis Cinema Studio يعمل: @%s", me.username)
        if config.MAX_RUN_MINUTES > 0:
            spawn(auto_stop())
        await idle()
    await engine.close()
    await db.flush()


if __name__ == "__main__":
    missing = config.missing_required()
    if missing:
        print("❌ متغيرات ناقصة في .env: " + ", ".join(missing))
        sys.exit(1)
    app.run(amain())
