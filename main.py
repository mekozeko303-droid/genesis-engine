# -*- coding: utf-8 -*-
import asyncio
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

STAGES = ["queue", "script", "voice", "assets", "render", "finalize", "upload"]


def check_access(uid: int) -> bool:
    return not config.ADMIN_IDS or (uid in config.ADMIN_IDS)


def modes_keyboard(uid: int) -> InlineKeyboardMarkup:
    cur_dur = db.get_duration(uid)
    dur_label = config.DURATIONS.get(cur_dur, f"⏱ {cur_dur} ثانية")
    rows = [
        [InlineKeyboardButton(f"⏱ المدة المحددة: {dur_label} (اضغط لتغييرها)", callback_data="menu:durations")],
        [
            InlineKeyboardButton("🐃 تجربة: فصوع 3D", callback_data="quick:fasso"),
            InlineKeyboardButton("🇾🇪 تجربة: اليمن", callback_data="quick:yemen"),
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
            "queue": f"🛎 في الطابور — ترتيبك {detail} ⏳",
            "script": f"✍️ أؤلف القصة وأقسّمها إلى مشاهد {detail}",
            "voice": f"🎙 أسجل التعليق الصوتي الطبيعي {detail}",
            "assets": f"🎞 أولّد اللقطات والمشاهد البصرية {detail}",
            "render": f"🎬 المونتاج وتحريك الكاميرا {detail}",
            "finalize": f"✅ التجميع النهائي والفحص",
            "upload": f"📤 أرفع الفيديو إليك الآن",
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
        f"⏱ المدة المحددة: {dur_label}\n\n"
        f"✍️ أرسل الآن فكرة الفيديو أو السيناريو (أو اذكر المدة التي تريدها).\n"
        f"💡 مثال: {mode.sample_idea}"
    )
    btns = [
        [InlineKeyboardButton(f"⏱ تغيير المدة ({dur_label})", callback_data="menu:durations")],
        [InlineKeyboardButton("📌 تثبيت فيديو مثال من جهازي", callback_data=f"setsample:{mode.id}")],
        [InlineKeyboardButton("🎞 تغيير الوضع", callback_data="modes")],
    ]
    await client.send_message(chat_id, text, parse_mode=PM, reply_markup=InlineKeyboardMarkup(btns))


async def run_job(client: Client, chat_id: int, uid: int, idea: str, mode_id: str) -> None:
    mode = config.MODES[mode_id]
    user_dur = db.get_duration(uid)
    status = await client.send_message(chat_id, "🛎 استلمت طلبك، جاري بدء الإنتاج والمونتاج...", parse_mode=PM)
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
        await retry_flood(
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

        await client.send_message(
            chat_id,
            f"📌 التعليق المثبت المقترح:\n{result.pinned_comment}",
            parse_mode=PM,
            reply_markup=after_keyboard(),
        )
        try:
            await status.delete()
        except Exception:
            pass
    except ProductionError as e:
        await db.record_failure(uid, mode_id, idea, e.user_message)
        await _fail(status, e.user_message)
    except asyncio.TimeoutError:
        await db.record_failure(uid, mode_id, idea, "timeout")
        await _fail(status, "استغرق الإنتاج وقتاً طويلًا. جرب تقليل المدة.")
    except Exception as e:
        log.exception("خطأ في الإنتاج")
        await db.record_failure(uid, mode_id, idea, repr(e))
        await _fail(status, f"خطأ: {str(e)[:100]}")
    finally:
        if uid in QUEUE:
            QUEUE.remove(uid)
        ACTIVE_USERS.discard(uid)


async def _fail(status: Message, text: str) -> None:
    try:
        await status.edit_text(f"❌ {text}", parse_mode=PM, reply_markup=after_keyboard())
    except Exception:
        pass


@app.on_message(filters.private & filters.command("id"))
async def cmd_id(client: Client, message: Message):
    await message.reply_text(f"🆔 معرف حسابك: {message.from_user.id}", parse_mode=PM)


@app.on_message(filters.private & filters.command(["start", "help", "modes"]))
async def cmd_start(client: Client, message: Message):
    uid = message.from_user.id
    if not check_access(uid):
        await message.reply_text(f"⛔ هذا البوت خاص بالمشرف.\nمعرفك: {uid}", parse_mode=PM)
        return
    db.user(uid)
    cur_mode = config.MODES[db.get_mode(uid)]
    cur_dur = config.DURATIONS.get(db.get_duration(uid), "1 دقيقة")
    text = (
        f"🎬 أهلاً بك في Genesis Cinema Studio\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"🎯 الوضع: {cur_mode.emoji} {cur_mode.name_ar}\n"
        f"⏱ المدة: {cur_dur}\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"✍️ أرسل فكرة الفيديو أو السيناريو:"
    )
    await message.reply_text(text, reply_markup=modes_keyboard(uid), parse_mode=PM)


@app.on_callback_query()
async def on_callback(client: Client, cq: CallbackQuery):
    uid, data = cq.from_user.id, cq.data or ""
    chat_id = cq.message.chat.id
    if not check_access(uid):
        await cq.answer("⛔ خاص بالمشرف", show_alert=True)
        return

    try:
        if data.startswith("mode:"):
            mode = config.MODES.get(data[5:])
            if not mode:
                return
            await db.set_mode(uid, mode.id, cq.from_user.first_name or "")
            await cq.answer(f"✅ {mode.name_ar}")
            await send_mode_card(client, chat_id, uid, mode)

        elif data == "menu:durations":
            await cq.answer()
            await client.send_message(chat_id, "⏱ اختر مدة الفيديو:", reply_markup=durations_keyboard(db.get_duration(uid)), parse_mode=PM)

        elif data.startswith("dur:"):
            sec = int(data.split(":")[1])
            await db.set_duration(uid, sec)
            label = config.DURATIONS.get(sec, f"{sec} ثانية")
            await cq.answer(f"✅ تم ضبط المدة: {label}")
            await cq.message.edit_text(f"✅ تم ضبط المدة على: {label}\n\n✍️ أرسل فكرتك الآن:", reply_markup=modes_keyboard(uid), parse_mode=PM)

        elif data.startswith("setsample:"):
            mid = data.split(":")[1]
            AWAITING_SAMPLE_FOR[uid] = mid
            await cq.answer()
            await client.send_message(chat_id, "📹 أرسل الفيديو من جهازك الآن لتثبيته كمثال:", parse_mode=PM)

        elif data.startswith("quick:"):
            qtype = data.split(":")[1]
            if qtype == "fasso":
                await db.set_mode(uid, "drama_3d", cq.from_user.first_name or "")
                await cq.answer("🐃 جاري بدء فصوع 3D")
                ACTIVE_USERS.add(uid)
                spawn(run_job(client, chat_id, uid, "شخصية شعبية تبكي بحرقة في الحارة القديمة", "drama_3d"))
            elif qtype == "yemen":
                await db.set_mode(uid, "yemen_doc", cq.from_user.first_name or "")
                await cq.answer("🇾🇪 جاري بدء وثائقي اليمن")
                ACTIVE_USERS.add(uid)
                spawn(run_job(client, chat_id, uid, "جمال الطبيعة الساحرة والتاريخ العريق في اليمن وصنعاء وسقطرى", "yemen_doc"))

        elif data == "modes":
            await cq.answer()
            await client.send_message(chat_id, "اختر الوضع 👇", reply_markup=modes_keyboard(uid), parse_mode=PM)

        elif data == "again":
            await cq.answer()
            await client.send_message(chat_id, "✍️ أرسل فكرة الفيديو الجديدة:", parse_mode=PM)
    except Exception:
        log.exception("خطأ الأزرار")


@app.on_message(filters.private & filters.video)
async def on_video_upload(client: Client, message: Message):
    uid = message.from_user.id
    if not check_access(uid):
        return
    if uid in AWAITING_SAMPLE_FOR:
        mid = AWAITING_SAMPLE_FOR.pop(uid)
        await db.set_sample(mid, "", message.video.file_id)
        await message.reply_text("✅ تم تثبيت الفيديو كمثال دائم لهذا الوضع!", parse_mode=PM, reply_markup=modes_keyboard(uid))


@app.on_message(filters.private & filters.text & ~filters.command(["id", "start", "help", "modes"]))
async def on_idea(client: Client, message: Message):
    uid = message.from_user.id
    if not check_access(uid):
        return
    idea = (message.text or "").strip()
    if len(idea) < config.MIN_IDEA_CHARS:
        return
    if uid in ACTIVE_USERS:
        await message.reply_text("⏳ لديك فيديو قيد الإنتاج الآن.", parse_mode=PM)
        return
    ACTIVE_USERS.add(uid)
    spawn(run_job(client, message.chat.id, uid, message.from_user.first_name or "", idea))


async def amain() -> None:
    await db.load()
    fatal, warn = await engine.start()
    if fatal:
        for f in fatal:
            log.error("❌ %s", f)
        await engine.close()
        return

    await app.start()
    me = await app.get_me()
    log.info("✅ Genesis Cinema Studio يعمل بنجاح: @%s", me.username)

    for admin_id in config.ADMIN_IDS:
        try:
            await app.send_message(admin_id, "🟢 البوت متصل وشغال الآن!", reply_markup=modes_keyboard(admin_id), parse_mode=PM)
        except Exception:
            pass

    await idle()
    await app.stop()
    await engine.close()
    await db.flush()


if __name__ == "__main__":
    if config.missing_required():
        sys.exit(1)
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(amain())
    except KeyboardInterrupt:
        pass
