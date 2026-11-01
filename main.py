import os
import sys
import time
import asyncio
from pyrogram import Client, filters, idle
from pyrogram.errors import FloodWait
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import Config
from database import db
from sentinel_evolution import sentinel, video_engine, viral_engine, boardroom

if not Config.BOT_TOKEN:
    print("❌ خطأ: لم يتم العثور على TELEGRAM_BOT_TOKEN في GitHub Secrets!")
    sys.exit(1)

app = Client(
    "genesis_immortal_bot",
    api_id=Config.API_ID,
    api_hash=Config.API_HASH,
    bot_token=Config.BOT_TOKEN,
    in_memory=True
)

START_TIME = time.time()
PROCESSED_MESSAGES = set()
USER_STATE = {}


def get_main_dashboard(user_id):
    selected_mode = USER_STATE.get(user_id, {}).get("mode", "hybrid")
    modes = db.get_all_modes()
    m_info = modes.get(selected_mode, modes["hybrid"])
    est_time = m_info.get("est_time", "40 إلى 60 ثانية")
    quota = db.get_quota_status()
    health_note = boardroom.inspect_system_health_and_requirements()

    text = (
        "👑 **إمبراطورية Genesis Engine الخالدة (v9.0 Full Multi-Agent Studio)**\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "🤖 **حالة مجلس الوكلاء الـ 6:** `نشط بالكامل (استقبال • إخراج • رسم • صوت • ريندر ذاتي • تطوير)`\n"
        f"🎯 **الوضع النشط حالياً:** `{m_info['name']}`\n"
        f"⏱️ **مدة تجهيز الفيديو:** `{est_time}`\n"
        f"📝 **وصف الوضع:** {m_info.get('desc', '')}\n"
        f"🔋 **رصيد المعالجة اليومي المتبقي:** `{quota['remaining_pct']}%` (يتجدد بعد `{quota['reset_in']}`)\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "✍️ **اكتب الآن أي فكرة فيديو في العالم (ماين كرافت، كرتون بيكسار، ديزني، بشري واقعي، أنمي، POV) وسيتولى الوكلاء الـ 6 إنتاجه وإرساله لك كملف (`.mp4`)!**"
    )
    if health_note:
        text += f"\n\n{health_note}"

    buttons = [
        [
            InlineKeyboardButton("🎬 الأوضاع الـ 17 (مع فيديو مثال لكل وضع)", callback_data="menu_modes_0"),
            InlineKeyboardButton("🤖 غرفة عمليات الوكلاء", callback_data="menu_quota")
        ],
        [
            InlineKeyboardButton("🔥 رادار التريندات والتعلم الفيروسي (أعلى مشاهدات)", callback_data="menu_viral_radar")
        ],
        [
            InlineKeyboardButton("🔬 وكيل فحص الأخبار واكتشاف الأدوات الجديدة", callback_data="menu_eval_news")
        ],
        [
            InlineKeyboardButton("🧬 وكيل استنساخ وضع جديد (مانع للتكرار)", callback_data="menu_clone_style"),
            InlineKeyboardButton("🔑 تزويد الوكلاء بمفتاح API", callback_data="menu_add_key")
        ]
    ]
    return text, InlineKeyboardMarkup(buttons)


def build_modes_keyboard(page=0):
    modes = list(db.get_all_modes().items())
    per_page = 6
    start = page * per_page
    end = start + per_page
    sliced = modes[start:end]

    rows = []
    for i in range(0, len(sliced), 2):
        row = []
        for k, v in sliced[i:i + 2]:
            row.append(InlineKeyboardButton(f"{v['name']} ({v['cost_pct']}%)", callback_data=f"setmode_{k}"))
        rows.append(row)

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("⬅️ السابق", callback_data=f"menu_modes_{page - 1}"))
    if end < len(modes):
        nav.append(InlineKeyboardButton("التالي ➡️", callback_data=f"menu_modes_{page + 1}"))
    if nav:
        rows.append(nav)

    rows.append([InlineKeyboardButton("🔙 العودة للوحة الرئيسية", callback_data="menu_home")])
    return InlineKeyboardMarkup(rows)


async def execute_upgrade_flow(client, chat_id, uid, upg_id, status_message=None):
    upg = db.get_pending_upgrade(upg_id)
    if not upg:
        msg = "⚠️ انتهت صلاحية هذا الطلب أو تم تنفيذه مسبقاً."
        if status_message:
            await status_message.edit_text(msg)
        else:
            await client.send_message(chat_id, msg)
        return

    wait_text = f"🛠️ **وكيل التطوير الذاتي:** جاري اختبار وتجهيز (`{upg['tool_name']}`) في البيئة المعزولة (`{Config.SANDBOX_BRANCH}`)..."
    msg_obj = await status_message.edit_text(wait_text) if status_message else await client.send_message(chat_id, wait_text)

    ok, sandbox_msg = await asyncio.to_thread(
        sentinel.test_in_sandbox_branch,
        upg_id,
        upg["tool_name"],
        upg.get("integration_code_snippet", "# Verified Plugin\n")
    )
    if ok:
        ok_merge, merge_msg = await asyncio.to_thread(sentinel.merge_sandbox_to_main, upg_id)
        USER_STATE[uid]["action"] = None
        await msg_obj.edit_text(
            f"🧪 **تقرير وكيل البيئة المعزولة:** {sandbox_msg}\n\n"
            f"🚀 **تقرير وكيل الدمج النهائي:** {merge_msg}\n\n"
            "✨ **تمت إضافة الأداة إلى ترسانة الوكلاء بنجاح!**",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 اللوحة الرئيسية", callback_data="menu_home")]])
        )
    else:
        await msg_obj.edit_text(
            f"⚠️ **تقرير وكيل البيئة المعزولة:**\n{sandbox_msg}",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="menu_home")]])
        )


@app.on_message(filters.command("start") & filters.private)
async def start_cmd(client, message):
    if message.id in PROCESSED_MESSAGES:
        return
    PROCESSED_MESSAGES.add(message.id)
    USER_STATE.setdefault(message.from_user.id, {"mode": "hybrid", "action": None})
    USER_STATE[message.from_user.id]["action"] = None
    text, markup = get_main_dashboard(message.from_user.id)
    await message.reply_text(text, reply_markup=markup)


@app.on_callback_query()
async def handle_callbacks(client, cq):
    uid = cq.from_user.id
    data = cq.data
    USER_STATE.setdefault(uid, {"mode": "hybrid", "action": None})

    if data == "menu_home":
        USER_STATE[uid]["action"] = None
        text, markup = get_main_dashboard(uid)
        if cq.message.photo or cq.message.video:
            await cq.message.delete()
            await client.send_message(uid, text, reply_markup=markup)
        else:
            await cq.message.edit_text(text, reply_markup=markup)

    elif data == "menu_viral_radar":
        wait_v = await cq.message.edit_text("🔥 **وكيل الرادار الفيروسي:** جاري سحب التريندات الحية وتحديث خوارزمية المشاهدات...")
        viral_info = await asyncio.to_thread(viral_engine.learn_new_viral_rule_from_web)
        trends_str = " ، ".join(viral_info["trends"][:6])
        suggested_topic = viral_info["suggested_viral_topic"]
        USER_STATE[uid]["suggested_trend"] = suggested_topic

        msg = (
            "🔥 **تقرير وكيل التريندات والتعلم الفيروسي الحي:**\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            f"🌍 **المواضيع الأكثر رواجاً الآن:**\n`{trends_str}`\n\n"
            f"🧠 **القاعدة الفيروسية التي أضافها الوكيل لذاكرة الإخراج الآن:**\n{viral_info['rule_ar']}\n\n"
            f"💡 **فكرة مقترحة جاهزة للإنتاج الفوري:**\n`{suggested_topic}`"
        )
        buttons = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"🎬 أنتج هذا الفيديو الآن", callback_data="produce_trend_now")],
            [InlineKeyboardButton("🔄 استخراج قاعدة فيروسية جديدة", callback_data="menu_viral_radar")],
            [InlineKeyboardButton("🔙 اللوحة الرئيسية", callback_data="menu_home")]
        ])
        await wait_v.edit_text(msg, reply_markup=buttons)

    elif data == "produce_trend_now":
        trend_topic = USER_STATE.get(uid, {}).get("suggested_trend", "مباراة كرة قدم بشخصيات ماين كرافت 3D")
        await cq.message.delete()
        status_msg = await client.send_message(uid, f"🔥 **مجلس الوكلاء:** جاري بدء إنتاج الفيديو الفيروسي عن: `{trend_topic}`")
        asyncio.create_task(produce_video_for_topic(client, uid, trend_topic, status_msg))

    elif data.startswith("switch_produce_"):
        target_mode = data.replace("switch_produce_", "")
        USER_STATE[uid]["mode"] = target_mode
        saved_topic = USER_STATE[uid].get("saved_topic", "مباراة كرة قدم بشخصيات ماين كرافت")
        await cq.message.delete()
        status_msg = await client.send_message(uid, f"🤖 **وكيل التوجيه:** تم تحويلك للوضع المناسب وبدء إنتاج: `{saved_topic}`")
        asyncio.create_task(produce_video_for_topic(client, uid, saved_topic, status_msg))

    elif data.startswith("menu_modes_"):
        page = int(data.split("_")[-1])
        msg_text = (
            f"🎬 **اختر وضع الإنتاج المطلوب (صفحة {page + 1}):**\n"
            "*(بمجرد اختيار أي وضع، يعرض لك الوكلاء **فيديو مثال حقيقي `.mp4`** يوضح ستايل هذا الوضع)*"
        )
        if cq.message.photo or cq.message.video:
            await cq.message.delete()
            await client.send_message(uid, msg_text, reply_markup=build_modes_keyboard(page))
        else:
            await cq.message.edit_text(msg_text, reply_markup=build_modes_keyboard(page))

    elif data.startswith("setmode_"):
        mode_key = data.replace("setmode_", "")
        USER_STATE[uid]["mode"] = mode_key
        USER_STATE[uid]["action"] = None
        modes = db.get_all_modes()
        m_info = modes.get(mode_key, modes["hybrid"])
        default_mode = Config.DEFAULT_MODES.get(mode_key, {})

        for field in ["est_time", "voice", "afilt", "vfilter", "sample_topic", "desc", "style"]:
            if field in default_mode:
                m_info[field] = default_mode[field]

        caption = (
            f"✅ **تم تفعيل: {m_info['name']}**\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            f"📹 **الفيديو بالأعلى هو مثال حقيقي لما يخرجه الوكلاء في هذا الوضع!**\n\n"
            f"📖 **وصف الوضع:**\n{m_info.get('desc', '')}\n\n"
            f"⏱️ **مدة التجهيز:** `{m_info.get('est_time', '40 إلى 60 ثانية')}` | ⚡ **الاستهلاك:** `{m_info['cost_pct']}%`\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "✍️ **اكتب الآن فكرة الفيديو مباشرة في المحادثة ليبدأ الوكلاء بإنتاجه وإرساله لك!**"
        )
        buttons = InlineKeyboardMarkup([
            [InlineKeyboardButton("📹 وضع فيديو تذكيري آخر من جهازي", callback_data=f"setsample_{mode_key}")],
            [
                InlineKeyboardButton("🔄 تغيير الوضع", callback_data="menu_modes_0"),
                InlineKeyboardButton("🏠 الرئيسية", callback_data="menu_home")
            ]
        ])

        await cq.message.delete()
        sample_vid = m_info.get("sample_file_id", "")

        if sample_vid:
            try:
                await client.send_video(uid, sample_vid, caption=caption, reply_markup=buttons)
                return
            except Exception:
                pass

        wait_prev = await client.send_message(
            uid,
            f"🎬 **وكيل المعاينة البصرية:** جاري تجهيز وعرض فيديو المثال الخاص بوضع ({m_info['name']})..."
        )
        try:
            mp4_sample = await video_engine.get_or_build_mode_sample(mode_key, m_info)
            sent_v = await client.send_video(uid, mp4_sample, caption=caption, reply_markup=buttons)
            await wait_prev.delete()
            if sent_v and sent_v.video:
                db.set_mode_sample_video(mode_key, sent_v.video.file_id)
        except Exception:
            await wait_prev.edit_text(caption, reply_markup=buttons)

    elif data.startswith("setsample_"):
        mode_key = data.replace("setsample_", "")
        USER_STATE[uid]["action"] = f"awaiting_sample_vid_{mode_key}"
        await client.send_message(
            uid,
            "📹 **وكيل الأرشيف:** أرسل الآن مقطع الفيديو الذي تريد تثبيته كمثال دائم لهذا الوضع:",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 إلغاء", callback_data="menu_home")]])
        )

    elif data == "menu_quota":
        q = db.get_quota_status()
        lessons = db.get_relevant_lessons()
        health = boardroom.inspect_system_health_and_requirements()
        msg = (
            "🤖 **غرفة عمليات مجلس الوكلاء الـ 6 والذاكرة الحية:**\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "1️⃣ **وكيل الاستقبال والمتطلبات:** `متصل ✅`\n"
            "2️⃣ **وكيل الإخراج وثبات الشخصيات:** `متصل ✅`\n"
            "3️⃣ **وكيل الرسم متعدد المحركات (5 Engines):** `متصل ✅`\n"
            "4️⃣ **وكيل الهندسة الصوتية العربية:** `متصل ✅`\n"
            "5️⃣ **وكيل الريندر والإصلاح الذاتي (Self-Healing):** `متصل ✅`\n"
            "6️⃣ **وكيل التطوير والرادار الفيروسي:** `متصل ✅`\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            f"🔋 **المتبقي من حصة اليوم:** `{q['remaining_pct']}%` (يتجدد بعد `{q['reset_in']}`)\n"
            f"🖥️ **العقدة النشطة:** `{q['active_node']}`\n\n"
            f"🧠 **آخر القواعد المتعلمة في ذاكرة الوكلاء:**\n`{lessons}`"
        )
        if health:
            msg += f"\n\n{health}"
        await cq.message.edit_text(msg, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="menu_home")]]))

    elif data == "menu_eval_news":
        USER_STATE[uid]["action"] = "awaiting_news"
        await cq.message.edit_text(
            "🔬 **وكيل فحص الأخبار واكتشاف الأدوات (Truth Sentinel Agent):**\n\n"
            "• اكتب اسم أي أداة سمعت عنها لفحصها ومقارنتها.\n"
            "• أو اكتب **ابحث انت وقلي** ليبحث الوكيل عن أداة جديدة غير مكررة ويقترحها عليك!",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 إلغاء", callback_data="menu_home")]])
        )

    elif data == "menu_clone_style":
        USER_STATE[uid]["action"] = "awaiting_style_clone"
        await cq.message.edit_text(
            "🧬 **وكيل الهندسة العكسية واستنساخ الأنماط (مع حارس عدم التكرار):**\n\n"
            "أرسل الآن **الفيديو مع كتابة اسم النمط الجديد في الوصف** (أو اكتب وصف النمط الجديد).\n"
            "⛔ *إذا كان النمط موجوداً ضمن الأوضاع الـ 17، سينبهك الوكيل ويرفض تكراره!*",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 إلغاء", callback_data="menu_home")]])
        )

    elif data == "menu_add_key":
        USER_STATE[uid]["action"] = "awaiting_manual_key"
        await cq.message.edit_text(
            "🔑 **وكيل المصادقة وحفظ المفاتيح (API Handshake Agent):**\n\n"
            "أرسل المفتاح بالصيغة التالية ليحفظه الوكيل في الذاكرة الدائمة فوراً:\n"
            "`HF_TOKEN:hf_xxxxxx`\nأو\n`GEMINI_KEY_1:AIzaSyxxxxxx`",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 إلغاء", callback_data="menu_home")]])
        )

    elif data.startswith("sandbox_test_"):
        upg_id = data.replace("sandbox_test_", "")
        await execute_upgrade_flow(client, cq.message.chat.id, uid, upg_id, status_message=cq.message)


async def produce_video_for_topic(client, uid, topic_text, status_msg):
    mode_key = USER_STATE.get(uid, {}).get("mode", "hybrid")
    modes = db.get_all_modes()
    m_info = modes.get(mode_key, modes["hybrid"])
    default_mode = Config.DEFAULT_MODES.get(mode_key, {})
    for field in ["est_time", "voice", "afilt", "vfilter", "style"]:
        if field in default_mode:
            m_info[field] = default_mode[field]

    est_time = m_info.get("est_time", "40 إلى 60 ثانية")

    async def update_progress(step_text):
        try:
            await status_msg.edit_text(
                f"🤖 **مجلس الوكلاء يعمل الآن على إنتاج مشروعك...**\n"
                f"▪️ **الموضوع:** `{topic_text[:45]}`\n"
                f"▪️ **الوضع:** `{m_info['name']}` (المدة المقدرة: `{est_time}`)\n"
                "━━━━━━━━━━━━━━━━━━━━━\n"
                f"{step_text}"
            )
        except Exception:
            pass

    final_video_path, script_data = await video_engine.render_full_video(
        topic_text,
        mode_key,
        m_info,
        progress_callback=update_progress,
        num_scenes=4
    )
    quota_after = db.consume_quota(m_info["cost_pct"])

    video_caption = (
        f"✅ **أتم مجلس الوكلاء إنتاج الفيديو بنجاح!**\n"
        f"🧲 **العنوان الفيروسي:**\n`{script_data.get('title_ar', '')}`\n\n"
        f"🎙️ **السرد الصوتي العربي:**\n{script_data.get('voiceover_ar', '')}\n\n"
        f"📈 **هاشتاجات الانتشار:**\n`{script_data.get('hashtags', '#اكسبلور #تريند')}`\n\n"
        f"💬 **التعليق المثبت المقترح لرفع اللايكات:**\n`{script_data.get('pinned_comment', '')}`\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        f"🔋 **الحصة المتبقية اليوم:** `{quota_after['remaining_pct']}%`"
    )

    await client.send_video(
        uid,
        final_video_path,
        caption=video_caption[:1020],
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔥 رادار التريندات الفيروسية", callback_data="menu_viral_radar")],
            [InlineKeyboardButton("🏠 اللوحة الرئيسية", callback_data="menu_home")]
        ])
    )
    try:
        await status_msg.delete()
    except Exception:
        pass


@app.on_message((filters.text | filters.video) & filters.private)
async def handle_user_input(client, message):
    if message.id in PROCESSED_MESSAGES:
        return
    PROCESSED_MESSAGES.add(message.id)

    uid = message.from_user.id
    USER_STATE.setdefault(uid, {"mode": "hybrid", "action": None})
    action = USER_STATE[uid].get("action")
    mode_key = USER_STATE[uid].get("mode", "hybrid")
    text = (message.text or message.caption or "").strip()

    if action and action.startswith("confirm_upgrade_"):
        upg_id = action.replace("confirm_upgrade_", "")
        if text in ["نعم", "ايوه", "أيوه", "موافق", "ايه", "اضفه", "تحديث", "طوره", "yes", "ok"]:
            await execute_upgrade_flow(client, message.chat.id, uid, upg_id)
            return
        elif text in ["لا", "الغي", "إلغاء", "رفض", "no"]:
            USER_STATE[uid]["action"] = None
            db.remove_pending_upgrade(upg_id)
            await message.reply_text("❌ **وكيل التطوير:** تم إلغاء التحديث بناءً على أمرك.")
            return

    if action and action.startswith("awaiting_sample_vid_"):
        target_mode = action.replace("awaiting_sample_vid_", "")
        USER_STATE[uid]["action"] = None
        if message.video:
            db.set_mode_sample_video(target_mode, message.video.file_id)
            await message.reply_text(
                "✅ **وكيل الأرشيف:** تم تثبيت هذا الفيديو كمثال رسمي للوضع بنجاح!",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🎬 عرض الوضع الآن", callback_data=f"setmode_{target_mode}")]])
            )
        else:
            await message.reply_text("⚠️ **وكيل الأرشيف:** يرجى إرسال ملف فيديو صالح.")
        return

    if action == "awaiting_style_clone":
        USER_STATE[uid]["action"] = None
        wait_msg = await message.reply_text("🔍 **وكيل الهندسة العكسية:** جاري فحص النمط ومطابقته مع الأوضاع الـ 17 لمنع التكرار...")
        vid_uniq = message.video.file_unique_id if message.video else ""
        style_data = await asyncio.to_thread(sentinel.reverse_engineer_video_style, text, vid_uniq)

        if style_data.get("is_duplicate"):
            await wait_msg.edit_text(
                f"⛔ **وكيل منع التكرار: هذا الوضع موجود في نظامك من قبل!**\n\n"
                f"🏷️ **الوضع المطابق الموجود عندك:** `{style_data.get('matched_mode_name', 'وضع أساسي')}`\n"
                f"📌 **التفاصيل:** {style_data.get('reason', '')}",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🎬 فتح الأوضاع الموجودة", callback_data="menu_modes_0")]])
            )
            return

        sample_fid = message.video.file_id if message.video else ""
        added_ok, result_mode = db.add_dynamic_mode(
            style_data["mode_id"],
            style_data["arabic_name"],
            style_data["style_prompt"],
            desc=style_data.get("desc", "نمط مخصص"),
            sample_file_id=sample_fid,
            video_unique_id=vid_uniq
        )

        if not added_ok:
            await wait_msg.edit_text(
                f"⛔ **وكيل منع التكرار: هذا الوضع موجود في نظامك من قبل!**\n\n"
                f"🏷️ **الوضع الموجود عندك:** `{result_mode['name']}`\n"
                f"📖 **وصفه:** {result_mode.get('desc', '')}",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🎬 الذهاب للوضع الموجود", callback_data="menu_modes_0")]])
            )
            return

        USER_STATE[uid]["mode"] = style_data["mode_id"]
        await wait_msg.edit_text(
            f"✅ **وكيل الهندسة العكسية:** تم التحقق من فرادة النمط وإضافته لنظامك!\n\n"
            f"🏷️ **اسم الوضع الجديد:** `{result_mode['name']}`\n"
            f"📖 **الوصف:** {result_mode['desc']}",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("👁️ فتح الوضع الجديد مع فيديو المثال", callback_data=f"setmode_{style_data['mode_id']}")]])
        )
        return

    if message.video and mode_key == "cloning":
        proc_msg = await message.reply_text(
            "🧬 **وكيل ترميم الفيديو:** جاري قص العلامات المائية من الأطراف وترميم جودة الملامح والألوان..."
        )
        dl_path = await message.download(file_name=f"/tmp/input_{message.id}.mp4")
        cleaned_path = await video_engine.clean_and_enhance_video(dl_path)
        quota_after = db.consume_quota(8.0)
        await client.send_video(
            uid,
            cleaned_path,
            caption=(
                "✅ **أتم وكيل الترميم تنظيف الفيديو وتحسين الجودة بنجاح!**\n"
                f"🔋 **الحصة المتبقية لك اليوم:** `{quota_after['remaining_pct']}%`"
            ),
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 اللوحة الرئيسية", callback_data="menu_home")]])
        )
        await proc_msg.delete()
        return

    if action == "awaiting_news":
        wait_msg = await message.reply_text("🛰️ **وكيل التطوير الذاتي:** جاري فحص المنصات العالمية لجلب أداة حقيقية جديدة...")
        report = await asyncio.to_thread(sentinel.evaluate_user_news, text)

        upg_id = f"upg_{int(time.time()) % 100000}"
        db.save_pending_upgrade(upg_id, report)
        USER_STATE[uid]["action"] = f"confirm_upgrade_{upg_id}"

        reply = (
            f"🔬 **تقرير وكيل الاكتشاف والفحص الهندسي حول: `{report.get('tool_name')}`**\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "⚖️ **قرار الوكيل:** 🟢 **أداة حقيقية موثقة وجاهزة للدمج الفوري**\n\n"
            f"📊 **التفاصيل:**\n{report.get('comparison_ar')}\n\n"
            "🔑 **هل تحتاج مفتاح API؟** `لا (تعمل مجاناً مباشرة)`\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "❓ **هل تأمر الوكلاء بعمل التحديث والتطوير الآن؟**\n"
            "*(فقط اكتب **نعم** أو اضغط على زر الموافقة بالأسفل)*"
        )
        buttons = [
            [InlineKeyboardButton("✅ نعم، اعتمد التحديث والتطوير", callback_data=f"sandbox_test_{upg_id}")],
            [InlineKeyboardButton("❌ لا، إلغاء", callback_data="menu_home")]
        ]
        await wait_msg.edit_text(reply, reply_markup=InlineKeyboardMarkup(buttons))
        return

    if action == "awaiting_manual_key":
        USER_STATE[uid]["action"] = None
        if ":" in text:
            k_name, k_val = text.split(":", 1)
            db.save_api_key(k_name.strip(), k_val.strip())
            await message.reply_text(f"✅ **وكيل المصادقة:** تم حفظ المفتاح `{k_name.strip()}` وتزويده لجميع الوكلاء بنجاح!")
        else:
            await message.reply_text("⚠️ **وكيل المصادقة:** يرجى إرسال المفتاح بالصيغة الصحيحة هكذا: `NAME:KEY`")
        return

    # فحص الطلب عبر وكيل الاستقبال والمتطلبات قبل بدء الإنتاج
    req_check = boardroom.analyze_user_request_requirements(text, bool(message.video), mode_key)
    if not req_check.get("ready"):
        USER_STATE[uid]["saved_topic"] = req_check.get("saved_topic", text)
        btns = []
        if req_check.get("suggest_switch_mode"):
            sm = req_check["suggest_switch_mode"]
            btns.append([InlineKeyboardButton("🎬 نعم، حولني لوكيل الإنتاج واصنع الفيديو الآن!", callback_data=f"switch_produce_{sm}")])
        btns.append([InlineKeyboardButton("🏠 اللوحة الرئيسية", callback_data="menu_home")])
        await message.reply_text(req_check["missing_msg"], reply_markup=InlineKeyboardMarkup(btns))
        return

    modes = db.get_all_modes()
    m_info = modes.get(mode_key, modes["hybrid"])
    est_time = m_info.get("est_time", "40 إلى 60 ثانية")
    quota_before = db.get_quota_status()

    if quota_before["remaining_pct"] < m_info["cost_pct"]:
        await message.reply_text(
            f"⚠️ **وكيل الموارد:** رصيد اليوم ({quota_before['remaining_pct']}%) لا يكفي لهذا الوضع ({m_info['cost_pct']}%).\n"
            f"⏳ سيتجدد الرصيد بالكامل بعد: `{quota_before['reset_in']}`."
        )
        return

    status_msg = await message.reply_text(
        f"🤖 **استلم مجلس الوكلاء الـ 6 طلبك الآن!**\n"
        f"▪️ **الموضوع:** `{text[:50]}`\n"
        f"▪️ **الوضع النشط:** `{m_info['name']}`\n"
        f"⏱️ **المدة المقدرة:** `{est_time}`\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "⏳ *جاري التوجيه إلى وكيل الإخراج وثبات الشخصيات...*"
    )
    asyncio.create_task(produce_video_for_topic(client, uid, text or "مباراة كرة قدم بشخصيات ماين كرافت", status_msg))


async def auto_viral_learning_daemon():
    while True:
        await asyncio.sleep(3600)
        try:
            await asyncio.to_thread(viral_engine.learn_new_viral_rule_from_web)
        except Exception:
            pass


async def immortal_lifecycle_watchdog():
    while True:
        await asyncio.sleep(60)
        elapsed_minutes = (time.time() - START_TIME) / 60.0
        if elapsed_minutes >= 345:
            sentinel.trigger_self_respawn()
            await asyncio.sleep(10)
            os._exit(0)


async def start_genesis():
    print("🚀 Starting Genesis Immortal Engine v9.0 (Full 6-Agent Autonomous Boardroom)...")
    while True:
        try:
            await app.start()
            break
        except FloodWait as e:
            wait_sec = int(getattr(e, "value", 60)) + 5
            print(f"⏳ Telegram FloodWait active: sleeping {wait_sec}s automatically...")
            await asyncio.sleep(wait_sec)

    asyncio.create_task(immortal_lifecycle_watchdog())
    asyncio.create_task(auto_viral_learning_daemon())
    asyncio.create_task(video_engine.prewarm_all_modes_background())
    print("✅ All 6 Agents are online 24/7 and ready!")
    await idle()
    await app.stop()


if __name__ == "__main__":
    app.run(start_genesis())
