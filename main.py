# -*- coding: utf-8 -*-
"""
Genesis Cinema Studio — main.py
واجهة تيليجرام المتكاملة (18 وضعاً + تحكم بالمدة حتى 10 دقائق + وضع فصوع 3D).
"""
import asyncio

try:
    asyncio.get_event_loop()
except RuntimeError:
    asyncio.set_event_loop(asyncio.new_event_loop())

import logging
import shutil
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
app = Client(
    "genesis_studio",
    api_id=config.API_ID,
    api_hash=config.API_HASH,
    bot_token=config.BOT_TOKEN,
    workdir=str(config.DATA_DIR),
)

PM = ParseMode.DISABLED
JOB_SEM = asyncio.Semaphore(config.MAX_CONCURRENT_JOBS)
ACTIVE_USERS: set[int] = set()
QUEUE: list[int] = []
BG_TASKS: set[asyncio.Task] = set()
STARTUP_WARNINGS: list[str] = []
AWAITING_SAMPLE_FOR: dict[int, str] = {}

A_RECEPTION = "🛎 وكيل الاستقبال"
A_WRITER = "✍️ وكيل السيناريو"
A_VOICE = "🎙 وكيل الصوت"
A_EDITOR = "🎬 وكيل المونتاج"

STAGES = ["queue", "script", "voice", "assets", "render", "finalize", "upload"]


def is_admin(uid: int) -> bool:
    return not config.ADMIN_IDS or (uid in config.ADMIN_IDS)


def check_access(uid: int) -> bool:
    return is_admin(uid)


def modes_keyboard(uid: int) -> InlineKeyboardMarkup:
    cur_dur = db.get_duration(uid)
    dur_label = config.DURATIONS.get(cur_dur, f"⏱ {cur_dur} ثانية")
    rows = [
        [InlineKeyboardButton(f"⏱ المدة المختارة حالياً: {dur_label} (اضغط لتغييرها)", callback_data="menu:durations")],
        [
            InlineKeyboardButton("🐃 تجربة: فصوع العراقي 3D", callback_data="quick:fasso"),
            InlineKeyboardButton("🇾🇪 تجربة: اليمن السعيد", callback_data="quick:yemen"),
        ],
    ]
    row = []
    for mid in config.MODE_ORDER:
        m = config.MODES[mid]
        row.append(InlineKeyboardButton(f"{m.emoji} {m.name_ar}", callback_data=f"mode:{mid}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    return InlineKeyboardMarkup(rows)


def durations_keyboard(selected_sec: int) -> InlineKeyboardMarkup:
    rows = []
    for sec, label in config.DURATIONS.items():
        mark = "✅ " if sec == selected_sec else ""
        rows.append([InlineKeyboardButton(f"{mark}{label}", callback_data=f"dur:{sec}")])
    rows.append([InlineKeyboardButton("🔙 رجوع للأوضاع", callback_data="modes")])
    return InlineKeyboardMarkup(rows)


def after_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🎬 فيديو جديد", callback_data="again"),
            InlineKeyboardButton("⏱ تغيير المدة", callback_data="menu:durations"),
        ],
        [
            InlineKeyboardButton("🎞 تغيير الوضع", callback_data="modes"),
        ],
    ])


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
    def __init__(self, msg: Message, mode: config.Mode):
        self.msg, self.mode = msg, mode
        self._last_text, self._last_t = "", 0.0

    def render(self, stage: str, detail: str = "") -> str:
        idx = STAGES.index(stage) if stage in STAGES else 0
        pct = int(idx / (len(STAGES) - 1) * 100)
        bar = "▰" * (idx + 1) + "▱" * (len(STAGES) - idx - 1)
        lines = {
            "queue": f"{A_RECEPTION}: فكرتك في الطابور — ترتيبك {detail} ⏳",
            "script": f"{A_WRITER}: أؤلف القصة وأقسمها إلى مشاهد وفصول {detail} ✍️",
            "voice": f"{A_VOICE}: أسجل التعليق الصوتي البشري الطبيعي {detail} 🎙",
            "assets": f"{A_EDITOR}: أولّد المشاهد واللقطات المطابقة للوضع {detail} 🎞",
            "render": f"{A_EDITOR}: المونتاج وتحريك الكاميرا والدمج {detail} 🎬",
            "finalize": f"{A_EDITOR}: التجميع النهائي والفحص ✅",
            "upload": f"{A_RECEPTION}: أرفع الفيديو إليك الآن 📤",
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
            pass


def make_caption(r: ProductionResult) -> str:
    return f"🎬 {r.title}\n\n{' '.join(r.hashtags)}"[:1000]


async def send_mode_card(client: Client, chat_id: int, uid: int, mode: config.Mode) -> None:
    cur_dur = db.get_duration(uid)
    dur_label = config.DURATIONS.get(cur_dur, f"{cur_dur} ثانية")
    text = (
        f"{mode.emoji} تم تفعيل وضع «{mode.name_ar}»\n"
        f"📖 {mode.desc_ar}\n"
        f"⏱ المدة المحددة حالياً: {dur_label}\n\n"
        f"✍️ أرسل الآن فكرة الفيديو أو السيناريو (أو اذكر المدة التي تريدها داخل رسالتك).\n"
        f"💡 مثال: {mode.sample_idea}"
    )
    btns = [
        [InlineKeyboardButton(f"⏱ تغيير مدة الفيديو ({dur_label})", callback_data="menu:durations")],
        [InlineKeyboardButton("📌 تثبيت فيديو مثال لهذا الوضع من جهازي", callback_data=f"setsample:{mode.id}")],
        [InlineKeyboardButton("🎞 تغيير الوضع", callback_data="modes")],
    ]
    markup = InlineKeyboardMarkup(btns)

    sample = db.get_sample(mode.id)
    if sample:
        for src in (sample.get("file_id"), sample.get("path")):
            if not src:
                continue
            try:
                await client.send_video(chat_id, src, caption=text, parse_mode=PM, reply_markup=markup, supports_streaming=True)
                return
            except Exception as e:
                log.warning("تعذر إرسال مثال %s: %s", mode.id, str(e)[:100])
    await client.send_message(chat_id, text, parse_mode=PM, reply_markup=markup)


async def run_job(client: Client, chat_id: int, uid: int, idea: str, mode_id: str) -> None:
    mode = config.MODES[mode_id]
    user_dur = db.get_duration(uid)
    status = await client.send_message(chat_id, f"{A_RECEPTION}: استلمت طلبك، جاري التجهيز ✅", parse_mode=PM)
    rep = ProgressReporter(status, mode)
    QUEUE.append(uid)
    try:
        if JOB_SEM.locked():
            await rep("queue", str(len(QUEUE)))
        async with JOB_SEM:
            if uid in QUEUE:
                QUEUE.remove(uid)
            result = await asyncio.wait_for(
                engine.produce(idea, mode_id, target_duration=user_dur, progress=rep),
                timeout=config.JOB_TIMEOUT,
            )

        await rep("upload")
        sent = await retry_flood(
            lambda: client.send_video(
                chat_id,
                str(result.video_path),
                caption=make_caption(result),
                parse_mode=PM,
                duration=int(result.duration),
                width=result.width,
                height=result.height,
                thumb=str(result.thumb_path) if result.thumb_path else None,
                supports_streaming=True,
            )
        )
        await db.record_success(uid, mode_id, idea, result.title, result.used_assets)

        notes = f"\nℹ️ {' | '.join(result.notes)}" if result.notes else ""
        await client.send_message(
            chat_id,
            f"📌 التعليق المثبت المقترح:\n{result.pinned_comment}{notes}",
            parse_mode=PM,
            reply_markup=after_keyboard(),
        )
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
        await _fail(status, "استغرق الإنتاج وقتاً أطول من المسموح. جرب تقليل المدة أو أعد المحاولة.")
    except Exception as e:
        log.exception("خطأ غير متوقع أثناء الإنتاج")
        await db.record_failure(uid, mode_id, idea, repr(e))
        await _fail(status, f"حدث خطأ أثناء الإنتاج: {str(e)[:120]}")
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
    mode_id = db.get_mode(uid)
    if uid in ACTIVE_USERS:
        await client.send_message(chat_id, "⏳ لديك فيديو قيد الإنتاج الآن. انتظر حتى يكتمل.", parse_mode=PM)
        return
    ACTIVE_USERS.add(uid)
    await db.set_mode(uid, mode_id, name)
    spawn(run_job(client, chat_id, uid, idea, mode_id))


@app.on_message(filters.private & filters.command("id"))
async def cmd_id(client: Client, message: Message):
    await message.reply_text(f"🆔 معرف حسابك في تيليجرام هو: {message.from_user.id}", parse_mode=PM)


@app.on_message(filters.private & filters.command(["start", "help", "modes"]))
async def cmd_start(client: Client, message: Message):
    uid = message.from_user.id
    if not check_access(uid):
        await message.reply_text(f"⛔ هذا البوت خاص بالمشرف فقط.\nمعرفك: {uid}", parse_mode=PM)
        return
    db.user(uid)
    cur_mode = config.MODES[db.get_mode(uid)]
    cur_dur = config.DURATIONS.get(db.get_duration(uid), "1 دقيقة")
    welcome_text = (
        "🎬 أهلاً بك يا زكريا في Genesis Cinema Studio\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        f"🎯 الوضع النشط: {cur_mode.emoji} {cur_mode.name_ar}\n"
        f"⏱ المدة المحددة: {cur_dur}\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "١) اختر الوضع (فصوع 3D، سينمائي، أنمي، كرتون 3D، ماين كرافت، ستيك مان، الوثائقي اليمني...)\n"
        "٢) حدد مدة الفيديو التي تريدها (من 30 ثانية حتى 10 دقائق)\n"
        "٣) أرسل فكرتك أو السيناريو ليبدأ الإنتاج فوراً!"
    )
    await message.reply_text(welcome_text, reply_markup=modes_keyboard(uid), parse_mode=PM)


@app.on_callback_query()
async def on_callback(client: Client, cq: CallbackQuery):
    uid, data = cq.from_user.id, cq.data or ""
    chat_id = cq.message.chat.id
    if not check_access(uid):
        await cq.answer("⛔ بوت خاص بالمشرف", show_alert=True)
        return

    try:
        if data.startswith("mode:"):
            mode = config.MODES.get(data[5:])
            if not mode:
                await cq.answer("وضع غير معروف", show_alert=True)
                return
            await db.set_mode(uid, mode.id, cq.from_user.first_name or "")
            await cq.answer(f"✅ {mode.name_ar}")
            await send_mode_card(client, chat_id, uid, mode)
            pending = await db.pop_pending(uid)
            if pending:
                await try_start(client, chat_id, uid, cq.from_user.first_name or "", pending)

        elif data == "menu:durations":
            await cq.answer()
            await client.send_message(
                chat_id,
                "⏱ اختر مدة الفيديو التي تريد إنتاجها في أي وضع:",
                reply_markup=durations_keyboard(db.get_duration(uid)),
                parse_mode=PM,
            )

        elif data.startswith("dur:"):
            sec = int(data.split(":")[1])
            await db.set_duration(uid, sec)
            label = config.DURATIONS.get(sec, f"{sec} ثانية")
            await cq.answer(f"✅ تم ضبط المدة: {label}")
            await cq.message.edit_text(
                f"✅ تم ضبط مدة الفيديوهات القادمة على: {label}\n\n✍️ أرسل الآن فكرة الفيديو أو اختر وضع الإنتاج:",
                reply_markup=modes_keyboard(uid),
                parse_mode=PM,
            )

        elif data.startswith("setsample:"):
            mid = data.split(":")[1]
            AWAITING_SAMPLE_FOR[uid] = mid
            m_name = config.MODES[mid].name_ar
            await cq.answer()
            await client.send_message(
                chat_id,
                f"📹 أرسل الآن مقطع الفيديو من جهازك لتثبيته كمثال دائم لوضع «{m_name}»:",
                parse_mode=PM,
            )

        elif data == "quick:fasso":
            await cq.answer("🐃 جاري بدء تجربة فصوع 3D")
            await db.set_mode(uid, "fasso", cq.from_user.first_name or "")
            await try_start(
                client,
                chat_id,
                uid,
                cq.from_user.first_name or "",
                "فصوع يركض في الحارة الشعبية ويبكي بحرقة على صديقه في مشهد درامي مؤثر",
            )

        elif data == "quick:yemen":
            await cq.answer("🇾🇪 جاري بدء تجربة اليمن السعيد")
            await db.set_mode(uid, "yemen_doc", cq.from_user.first_name or "")
            await try_start(
                client,
                chat_id,
                uid,
                cq.from_user.first_name or "",
                "جمال الطبيعة الساحرة والعمارة التاريخية في اليمن وصنعاء القديمة وجزيرة سقطرى",
            )

        elif data == "modes":
            await cq.answer()
            await client.send_message(chat_id, "اختر وضع الإنتاج 👇", reply_markup=modes_keyboard(uid), parse_mode=PM)

        elif data == "again":
            await cq.answer()
            await client.send_message(chat_id, f"{A_RECEPTION}: أرسل فكرة الفيديو الجديدة ✍️", parse_mode=PM)
        else:
            await cq.answer()
    except FloodWait as e:
        await asyncio.sleep(min(int(e.value), 10))
    except Exception:
        log.exception("خطأ في معالج الأزرار")


@app.on_message(filters.private & filters.video)
async def on_video_upload(client: Client, message: Message):
    uid = message.from_user.id
    if not check_access(uid):
        return
    if uid in AWAITING_SAMPLE_FOR:
        mid = AWAITING_SAMPLE_FOR.pop(uid)
        m = config.MODES[mid]
        await db.set_sample(mid, "", message.video.file_id)
        await message.reply_text(
            f"✅ تم تثبيت هذا الفيديو كمثال دائم لوضع «{m.emoji} {m.name_ar}» بنجاح!",
            parse_mode=PM,
            reply_markup=modes_keyboard(uid),
        )
    else:
        await message.reply_text(
            "📌 لتثبيت هذا الفيديو كمثال لأحد الأوضاع، اختر الوضع أولاً ثم اضغط زر «تثبيت فيديو مثال لهذا الوضع».",
            parse_mode=PM,
        )


@app.on_message(filters.private & filters.command(["stats", "check"]))
async def cmd_stats(client: Client, message: Message):
    if not check_access(message.from_user.id):
        return
    s = db.stats()
    warn = "\n".join(f"• {w}" for w in STARTUP_WARNINGS) or "لا توجد (جميع المحركات جاهزة ✅)"
    await message.reply_text(
        f"📊 إحصائيات الاستوديو:\n"
        f"• الفيديوهات المنتجة: {s['videos']}\n"
        f"• الأمثلة المثبتة: {s['samples']}/{len(config.MODES)}\n"
        f"• في الطابور حالياً: {len(QUEUE)}\n\n"
        f"🔧 حالة المحركات:\n{warn}",
        parse_mode=PM,
    )


_COMMANDS = ["start", "help", "modes", "stats", "check", "id"]


@app.on_message(filters.private & filters.text & ~filters.command(_COMMANDS))
async def on_idea(client: Client, message: Message):
    uid = message.from_user.id
    if not check_access(uid):
        return
    idea = (message.text or "").strip()
    if len(idea) < config.MIN_IDEA_CHARS:
        await message.reply_text("✍️ أرسل فكرة أوضح قليلاً (جملة كاملة على الأقل).", parse_mode=PM)
        return
    if len(idea) > config.MAX_IDEA_CHARS:
        idea = idea[:config.MAX_IDEA_CHARS]
    await try_start(client, message.chat.id, uid, message.from_user.first_name or "", idea)


# ═════════════════════════ التشغيل المضمون ═════════════════════════
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

    while True:
        try:
            await app.start()
            break
        except FloodWait as e:
            wait_s = int(getattr(e, "value", 30)) + 5
            log.warning("⏳ FloodWait من تيليجرام: انتظار %s ثانية...", wait_s)
            await asyncio.sleep(wait_s)

    me = await app.get_me()
    log.info("✅ Genesis Cinema Studio يعمل بنجاح: @%s", me.username)
    await idle()
    await app.stop()
    await engine.close()
    await db.flush()


if __name__ == "__main__":
    missing = config.missing_required()
    if missing:
        print("❌ متغيرات ناقصة في Secrets: " + ", ".join(missing))
        sys.exit(1)
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(amain())
    except KeyboardInterrupt:
        pass
