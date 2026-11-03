# -*- coding: utf-8 -*-
"""
Genesis Cinema Studio — main.py
واجهة تيليجرام (Pyrogram / Kurigram): وكيل الاستقبال ← وكيل السيناريو ← وكيل المونتاج.

التشغيل: python main.py
"""
from __future__ import annotations

import asyncio
import logging
import os
import shutil
import signal
import sys
import time
import warnings

# توافق Pyrogram مع Python 3.12+ عند الحاجة إلى حلقة أحداث قبل إنشاء Client.
with warnings.catch_warnings():
    warnings.simplefilter("ignore", DeprecationWarning)
    try:
        asyncio.get_event_loop()
    except RuntimeError:
        asyncio.set_event_loop(asyncio.new_event_loop())

from pyrogram import Client, filters, idle
from pyrogram.enums import ParseMode
from pyrogram.errors import FloodWait
from pyrogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

import config
from database import Database
from sentinel_evolution import ProductionError, ProductionResult, VideoProductionEngine

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
log = logging.getLogger("genesis.bot")

# لا نطبع الرمز السري في السجلات. strip يحذف المسافات/السطر الجديد بالخطأ.
BOT_TOKEN = str(config.BOT_TOKEN or "").strip()
if BOT_TOKEN and ":" not in BOT_TOKEN:
    raise SystemExit(
        "❌ TELEGRAM_BOT_TOKEN تنسيقه غير صحيح. أنشئ رمزاً جديداً من @BotFather "
        "وحدّث GitHub Secret بالاسم TELEGRAM_BOT_TOKEN."
    )

# المسارات تنشأ في config.py قبل إنشاء Client.
db = Database()
engine = VideoProductionEngine(db)
app = Client(
    "genesis_studio",
    api_id=config.API_ID,
    api_hash=config.API_HASH,
    bot_token=BOT_TOKEN,
    workdir=str(config.DATA_DIR),
)

PM = ParseMode.DISABLED
JOB_SEM = asyncio.Semaphore(max(1, config.MAX_CONCURRENT_JOBS))
ACTIVE_USERS: set[int] = set()
QUEUE: list[int] = []
BG_TASKS: set[asyncio.Task] = set()
STARTUP_WARNINGS: list[str] = []
AWAITING_SAMPLE: dict[int, str] = {}
SHUTTING_DOWN = False

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


def welcome_keyboard() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(label, callback_data=f"quick:{i}")]
        for i, (label, _, _) in enumerate(config.QUICK_DEMOS)
    ]
    return InlineKeyboardMarkup(rows + modes_keyboard().inline_keyboard)


def mode_card_markup(uid: int, mode_id: str):
    if not is_admin(uid):
        return None
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("📌 تثبيت فيديو مثال لهذا الوضع", callback_data=f"pin:{mode_id}")]]
    )


async def ensure_allowed(update) -> bool:
    """قفل الوضع الخاص، مع إبقاء /id متاحاً لمعرفة رقم المالك."""
    uid = update.from_user.id
    if not config.PRIVATE_MODE or is_admin(uid):
        return True
    try:
        if isinstance(update, CallbackQuery):
            await update.answer("⛔ هذا البوت خاص بمالكه", show_alert=True)
        else:
            await update.reply_text(
                f"⛔ هذا البوت خاص بمالكه فقط.\nرقمك: {uid}",
                parse_mode=PM,
            )
    except Exception:
        log.exception("تعذّر إرسال رسالة منع الوصول")
    return False


def after_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[
            InlineKeyboardButton("🎬 فيديو جديد", callback_data="again"),
            InlineKeyboardButton("🎞 تغيير الوضع", callback_data="modes"),
        ]]
    )


def spawn(coro) -> None:
    task = asyncio.create_task(coro)
    BG_TASKS.add(task)
    task.add_done_callback(BG_TASKS.discard)


async def retry_flood(factory, tries: int = 3):
    for attempt in range(tries):
        try:
            return await factory()
        except FloodWait as exc:
            await asyncio.sleep(min(int(exc.value) + 1, 60))
            if attempt == tries - 1:
                raise


class ProgressReporter:
    """يحدّث رسالة واحدة بتقدم الإنتاج مع تحديد معدل التعديل."""

    def __init__(self, msg: Message, mode: config.Mode):
        self.msg = msg
        self.mode = mode
        self._last_text = ""
        self._last_t = 0.0

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
            self._last_text = text
            self._last_t = now
        except FloodWait:
            self._last_t = now + 10
        except Exception:
            log.debug("تعذّر تحديث رسالة التقدم", exc_info=True)


async def send_final_video(
    client: Client,
    chat_id: int,
    result: ProductionResult,
    caption: str,
):
    """يرفع الفيديو كاملاً، وإن فشل يرجع إلى صيغة إرسال مبسطة."""

    async def full():
        return await client.send_video(
            chat_id,
            str(result.video_path),
            caption=caption,
            parse_mode=PM,
            duration=int(result.duration),
            width=result.width,
            height=result.height,
            thumb=str(result.thumb_path) if result.thumb_path else None,
            supports_streaming=True,
        )

    async def minimal():
        return await client.send_video(
            chat_id,
            str(result.video_path),
            caption=caption,
            parse_mode=PM,
        )

    try:
        return await retry_flood(full)
    except Exception as exc:
        log.warning("الرفع الكامل فشل (%s) — محاولة مبسطة", str(exc)[:100])
        return await retry_flood(minimal)


def make_caption(result: ProductionResult) -> str:
    return f"🎬 {result.title}\n\n{' '.join(result.hashtags)}"[:1000]


async def send_mode_card(
    client: Client,
    chat_id: int,
    mode: config.Mode,
    markup=None,
) -> None:
    text = (
        f"{mode.emoji} وضع «{mode.name_ar}»\n{mode.desc_ar}\n\n"
        f"✍️ أرسل الآن فكرة الفيديو.\nمثال: {mode.sample_idea}"
    )
    sample = db.get_sample(mode.id)
    if sample:
        for src in (sample.get("file_id"), sample.get("path")):
            if not src:
                continue
            try:
                await client.send_video(
                    chat_id,
                    src,
                    caption=text,
                    parse_mode=PM,
                    supports_streaming=True,
                    reply_markup=markup,
                )
                return
            except Exception as exc:
                log.warning("تعذّر إرسال مثال %s: %s", mode.id, str(exc)[:100])
    await client.send_message(chat_id, text, parse_mode=PM, reply_markup=markup)


async def _fail(status: Message, text: str) -> None:
    try:
        await status.edit_text(
            f"❌ {text}",
            parse_mode=PM,
            reply_markup=after_keyboard(),
        )
    except Exception:
        log.debug("تعذّر تعديل رسالة الفشل", exc_info=True)


async def run_job(
    client: Client,
    chat_id: int,
    uid: int,
    idea: str,
    mode_id: str,
) -> None:
    mode = config.MODES[mode_id]
    status = await client.send_message(
        chat_id,
        f"{A_RECEPTION}: استلمت فكرتك ✅",
        parse_mode=PM,
    )
    reporter = ProgressReporter(status, mode)
    QUEUE.append(uid)
    try:
        if JOB_SEM.locked():
            await reporter("queue", str(len(QUEUE)))
        async with JOB_SEM:
            if uid in QUEUE:
                QUEUE.remove(uid)
            result = await asyncio.wait_for(
                engine.produce(idea, mode_id, progress=reporter),
                timeout=config.JOB_TIMEOUT,
            )

        await reporter("upload")
        sent = await send_final_video(client, chat_id, result, make_caption(result))
        await db.record_success(uid, mode_id, idea, result.title, result.used_assets)

        remaining = db.remaining_quota(uid, is_admin(uid))
        extra = "" if is_admin(uid) else f"\n\n📊 المتبقي لك اليوم: {remaining} فيديو"
        notes = f"\nℹ️ {'؛ '.join(result.notes)}" if result.notes else ""
        await client.send_message(
            chat_id,
            f"📌 التعليق المثبت المقترح:\n{result.pinned_comment}{notes}{extra}",
            parse_mode=PM,
            reply_markup=after_keyboard(),
        )
        try:
            await status.delete()
        except Exception:
            pass
        log.info(
            "تم إنتاج فيديو للمستخدم %s (%s) msg=%s",
            uid,
            mode_id,
            getattr(sent, "id", "?"),
        )

    except ProductionError as exc:
        await db.record_failure(uid, mode_id, idea, exc.user_message)
        await _fail(status, exc.user_message)
    except asyncio.TimeoutError:
        await db.record_failure(uid, mode_id, idea, "timeout")
        await _fail(status, "استغرق الإنتاج وقتاً أطول من المسموح. جرّب فكرة أقصر أو أعد المحاولة.")
    except Exception as exc:
        log.exception("خطأ غير متوقع أثناء الإنتاج")
        await db.record_failure(uid, mode_id, idea, repr(exc))
        await _fail(status, "حدث خطأ غير متوقع أثناء الإنتاج. لم يُحسب من حصتك، أعد المحاولة بعد قليل.")
    finally:
        if uid in QUEUE:
            QUEUE.remove(uid)
        ACTIVE_USERS.discard(uid)


async def try_start(
    client: Client,
    chat_id: int,
    uid: int,
    name: str,
    idea: str,
) -> None:
    """يتحقق من الوضع والحصة ثم يطلق الإنتاج في الخلفية."""
    mode_id = db.get_mode(uid)
    if not mode_id:
        await db.set_pending(uid, idea)
        await client.send_message(
            chat_id,
            f"{A_RECEPTION}: اختر وضع الإنتاج أولاً، وسأبدأ بفكرتك مباشرة 👇",
            reply_markup=modes_keyboard(),
            parse_mode=PM,
        )
        return
    if SHUTTING_DOWN:
        await client.send_message(
            chat_id,
            "🔄 البوت يعيد تشغيل نفسه (دقيقتان تقريباً). أرسل فكرتك بعد قليل.",
            parse_mode=PM,
        )
        return
    if uid in ACTIVE_USERS:
        await client.send_message(
            chat_id,
            "⏳ لديك فيديو قيد الإنتاج الآن. انتظر حتى يصلك.",
            parse_mode=PM,
        )
        return
    if db.remaining_quota(uid, is_admin(uid)) <= 0:
        await client.send_message(
            chat_id,
            f"وصلت لحدّك اليومي ({config.DAILY_LIMIT} فيديو). يتجدد عند منتصف الليل 🌙",
            parse_mode=PM,
        )
        return
    ACTIVE_USERS.add(uid)
    await db.set_mode(uid, mode_id, name)
    spawn(run_job(client, chat_id, uid, idea, mode_id))


# ═════════════════════════ معالجات تيليجرام ═════════════════════════
@app.on_message(filters.private & filters.command(["start", "help", "modes"]))
async def cmd_start(client: Client, message: Message):
    if not await ensure_allowed(message):
        return
    db.user(message.from_user.id)
    command = message.command[0]
    if command == "modes":
        await message.reply_text("اختر وضع الإنتاج 👇", reply_markup=modes_keyboard(), parse_mode=PM)
    else:
        await message.reply_text(WELCOME, reply_markup=welcome_keyboard(), parse_mode=PM)


@app.on_callback_query()
async def on_callback(client: Client, cq: CallbackQuery):
    uid = cq.from_user.id
    data = cq.data or ""
    chat_id = cq.message.chat.id if cq.message else uid
    if not await ensure_allowed(cq):
        return
    try:
        if data.startswith("quick:"):
            idx = int(data[6:])
            if idx < 0 or idx >= len(config.QUICK_DEMOS):
                await cq.answer("تجربة غير معروفة", show_alert=True)
                return
            _label, mode_id, idea = config.QUICK_DEMOS[idx]
            await cq.answer("🎬 بدأ الإنتاج")
            await db.set_mode(uid, mode_id, cq.from_user.first_name or "")
            await try_start(client, chat_id, uid, cq.from_user.first_name or "", idea)

        elif data.startswith("pin:"):
            mode = config.MODES.get(data[4:])
            if not is_admin(uid) or not mode:
                await cq.answer("للمشرف فقط", show_alert=True)
                return
            AWAITING_SAMPLE[uid] = mode.id
            await cq.answer()
            await client.send_message(
                chat_id,
                f"📌 أرسل الآن فيديو المثال لوضع «{mode.name_ar}» (من جهازك).\n"
                "يُحفظ معرّف الفيديو لاستخدامه لاحقاً.",
                parse_mode=PM,
            )

        elif data.startswith("mode:"):
            mode = config.MODES.get(data[5:])
            if not mode:
                await cq.answer("وضع غير معروف", show_alert=True)
                return
            await db.set_mode(uid, mode.id, cq.from_user.first_name or "")
            await cq.answer(f"✅ {mode.name_ar}")
            await send_mode_card(client, chat_id, mode, mode_card_markup(uid, mode.id))
            pending = await db.pop_pending(uid)
            if pending:
                await try_start(client, chat_id, uid, cq.from_user.first_name or "", pending)

        elif data == "modes":
            await cq.answer()
            await client.send_message(
                chat_id,
                "اختر وضع الإنتاج 👇",
                reply_markup=modes_keyboard(),
                parse_mode=PM,
            )

        elif data == "again":
            await cq.answer()
            await client.send_message(
                chat_id,
                f"{A_RECEPTION}: أرسل فكرة الفيديو الجديدة ✍️",
                parse_mode=PM,
            )
        else:
            await cq.answer()

    except FloodWait as exc:
        await asyncio.sleep(min(int(exc.value), 10))
    except Exception:
        log.exception("خطأ في معالج الأزرار")


@app.on_message(filters.private & filters.command("id"))
async def cmd_id(client: Client, message: Message):
    uid = message.from_user.id
    note = "✅ أنت مشرف." if is_admin(uid) else "ضع هذا الرقم في ADMIN_IDS ثم أعد تشغيل البوت."
    await message.reply_text(f"🆔 رقمك: {uid}\n{note}", parse_mode=PM)


async def run_check() -> str:
    lines = await engine.diagnose()
    lock = (
        f"🔒 الوضع الخاص: مفعّل ({len(config.ADMIN_IDS)} مشرف)"
        if config.PRIVATE_MODE
        else "🔓 الوضع الخاص: مغلق — البوت مفتوح للجميع"
        + ("" if config.ADMIN_IDS else " (ADMIN_IDS غير مضبوط)")
    )
    return "🩺 فحص النظام:\n" + "\n".join(lines + [lock])


@app.on_message(filters.private & filters.command("check"))
async def cmd_check(client: Client, message: Message):
    if not is_admin(message.from_user.id):
        await message.reply_text(
            "هذا الأمر للمشرف فقط. أرسل /id لمعرفة رقمك وضعه في ADMIN_IDS.",
            parse_mode=PM,
        )
        return
    waiting = await message.reply_text("🩺 جاري فحص الخدمات...", parse_mode=PM)
    await waiting.edit_text(await run_check(), parse_mode=PM)


async def startup_report(client: Client) -> None:
    """يرسل للمشرفين تقرير فحص عند كل تشغيل."""
    try:
        report = "✅ Genesis Cinema Studio يعمل\n\n" + await run_check()
    except Exception as exc:
        report = f"✅ البوت يعمل، لكن الفحص فشل: {str(exc)[:100]}"
    for admin in config.ADMIN_IDS:
        try:
            await client.send_message(admin, report, parse_mode=PM)
        except Exception as exc:
            log.warning(
                "تعذّر إرسال تقرير التشغيل للمشرف %s: %s (اضغط Start مع البوت أولاً)",
                admin,
                str(exc)[:80],
            )


@app.on_message(filters.private & filters.command("stats"))
async def cmd_stats(client: Client, message: Message):
    if not is_admin(message.from_user.id):
        return
    stats = db.stats()
    warn = "\n".join(f"• {warning}" for warning in STARTUP_WARNINGS) or "لا توجد"
    await message.reply_text(
        f"📊 فيديوهات: {stats['videos']} | إخفاقات: {stats['failures']}\n"
        f"👥 مستخدمون: {stats['users']} | 🎞 أمثلة: {stats['samples']}/17\n"
        f"⏳ في الطابور: {len(QUEUE)}\n\n⚠️ تحذيرات التشغيل:\n{warn}",
        parse_mode=PM,
    )


@app.on_message(filters.private & filters.command("samples"))
async def cmd_samples(client: Client, message: Message):
    """يبني أمثلة للأوضاع الناقصة، أو لوضع محدد عبر /samples mode_id."""
    if not is_admin(message.from_user.id):
        return
    arg = message.command[1].strip() if len(message.command) > 1 else ""
    targets = [arg] if arg in config.MODES else [mid for mid in config.MODE_ORDER if not db.get_sample(mid)]
    if not targets:
        await message.reply_text(
            "✅ كل الأمثلة جاهزة. استخدم /samples mode_id لإعادة بناء وضع محدد.",
            parse_mode=PM,
        )
        return
    await message.reply_text(
        f"🎞 سأبني {len(targets)} مثال/أمثلة تباعاً (قد يستغرق وقتاً).\n"
        "يمكنك أيضاً وضع ملفات data/samples/mode_id.mp4 يدوياً.",
        parse_mode=PM,
    )
    spawn(build_samples(client, message.chat.id, targets))


async def build_samples(client: Client, chat_id: int, targets: list[str]) -> None:
    for mode_id in targets:
        mode = config.MODES[mode_id]
        try:
            async with JOB_SEM:
                result = await asyncio.wait_for(
                    engine.produce(mode.sample_idea, mode_id),
                    timeout=config.JOB_TIMEOUT,
                )
            keep = config.SAMPLES_DIR / f"{mode_id}.mp4"
            shutil.copy2(result.video_path, keep)
            sent = await retry_flood(
                lambda: client.send_video(
                    chat_id,
                    str(keep),
                    caption=f"مثال: {mode.emoji} {mode.name_ar}",
                    parse_mode=PM,
                    duration=int(result.duration),
                    width=result.width,
                    height=result.height,
                    supports_streaming=True,
                )
            )
            await db.set_sample(mode_id, str(keep), sent.video.file_id)
        except Exception as exc:
            log.exception("فشل بناء مثال %s", mode_id)
            await client.send_message(
                chat_id,
                f"❌ تعذّر بناء مثال {mode.name_ar}: {str(exc)[:120]}",
                parse_mode=PM,
            )
    await client.send_message(chat_id, "✅ انتهى بناء الأمثلة.", parse_mode=PM)


_COMMANDS = ["start", "help", "modes", "stats", "samples", "check", "id"]


@app.on_message(filters.private & filters.text & ~filters.command(_COMMANDS))
async def on_idea(client: Client, message: Message):
    if not await ensure_allowed(message):
        return
    idea = (message.text or "").strip()
    uid = message.from_user.id
    if len(idea) < config.MIN_IDEA_CHARS:
        await message.reply_text("✍️ أرسل فكرة أوضح قليلاً (جملة كاملة على الأقل).", parse_mode=PM)
        return
    if len(idea) > config.MAX_IDEA_CHARS:
        idea = idea[: config.MAX_IDEA_CHARS]
    await try_start(client, message.chat.id, uid, message.from_user.first_name or "", idea)


@app.on_message(filters.private & filters.video)
async def on_video(client: Client, message: Message):
    """يحفظ فيديو المثال المرسل من المشرف بعد الضغط على زر التثبيت."""
    uid = message.from_user.id
    if not await ensure_allowed(message):
        return
    mode_id = AWAITING_SAMPLE.pop(uid, None) if is_admin(uid) else None
    if not mode_id:
        await message.reply_text("أرسل فكرة الفيديو كنص من فضلك ✍️", parse_mode=PM)
        return
    await db.set_sample(mode_id, None, message.video.file_id, pinned=True)
    mode = config.MODES[mode_id]
    await message.reply_text(
        f"✅ تم تثبيت هذا الفيديو كمثال دائم لوضع «{mode.name_ar}».",
        parse_mode=PM,
    )


@app.on_message(filters.private & ~filters.text & ~filters.video & ~filters.service)
async def on_other(client: Client, message: Message):
    if not await ensure_allowed(message):
        return
    await message.reply_text("أرسل فكرة الفيديو كنص من فضلك ✍️", parse_mode=PM)


async def auto_stop() -> None:
    """يوقف البوت بشكل منظم بعد MAX_RUN_MINUTES."""
    global SHUTTING_DOWN
    await asyncio.sleep(config.MAX_RUN_MINUTES * 60)
    SHUTTING_DOWN = True
    log.info("⏰ انتهت مدة التشغيل المحددة — إيقاف منظم")
    deadline = time.monotonic() + 360
    while (ACTIVE_USERS or JOB_SEM.locked()) and time.monotonic() < deadline:
        await asyncio.sleep(5)
    os.kill(os.getpid(), signal.SIGINT)


async def amain() -> None:
    await db.load()
    fatal, warnings_list = await engine.start()
    STARTUP_WARNINGS.extend(warnings_list)
    for warning in warnings_list:
        log.warning("⚠️ %s", warning)
    if fatal:
        for error in fatal:
            log.error("❌ %s", error)
        await engine.close()
        return

    async with app:
        me = await app.get_me()
        log.info("✅ Genesis Cinema Studio يعمل: @%s", me.username)
        spawn(startup_report(app))
        if config.MAX_RUN_MINUTES > 0:
            spawn(auto_stop())
        await idle()

    await engine.close()
    await db.flush()


if __name__ == "__main__":
    print("🔖 Genesis main.py — النسخة 2026-11-03-FIX1")
    missing = config.missing_required()
    if missing:
        print(
            "❌ أسرار ناقصة/غير صالحة مبدئياً (GitHub → Settings → Secrets and variables → Actions): "
            + ", ".join(missing)
        )
        sys.exit(1)
    try:
        asyncio.get_event_loop().run_until_complete(amain())
    except KeyboardInterrupt:
        log.info("تم إيقاف البوت.")
