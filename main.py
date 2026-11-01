import os
import sys
import time
import threading
import asyncio
from pyrogram import Client, filters, idle
from pyrogram.errors import FloodWait
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import Config
from database import db
from sentinel_evolution import sentinel, video_engine, viral_engine, boardroom

if not Config.BOT_TOKEN or not Config.API_ID or not Config.API_HASH:
    print("❌ خطأ صارم: مفاتيح تيليجرام (API_ID / API_HASH / BOT_TOKEN) مفقودة!")
    sys.exit(1)

app = Client(
    "genesis_immortal_bot",
    api_id=Config.API_ID,
    api_hash=Config.API_HASH,
    bot_token=Config.BOT_TOKEN,
    in_memory=True
)

USER_STATE = {}


def start_threaded_watchdog():
    def _watchdog_worker():
        time.sleep(345 * 60)
        print("⏰ Watchdog (345m): Triggering self-respawn before 6h limit...")
        sentinel.trigger_self_respawn()
        time.sleep(8)
        os._exit(0)

    t = threading.Thread(target=_watchdog_worker, daemon=True)
    t.start()


def get_main_dashboard(user_id):
    selected_mode = USER_STATE.get(user_id, {}).get("mode", "hybrid")
    modes = db.get_all_modes()
    m_info = modes.get(selected_mode, modes["hybrid"])
    est_time = m_info.get("est_time", "30 إلى 50 ثانية")
    quota = db.get_quota_status()
    agent_msg = boardroom.build_agent_greeting_and_requirements()

    text = (
        "🎬 **استوديو Genesis السينمائي الخالد (CapCut & Higgsfield Auto-Editor v10.0)**\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        f"🎯 **الوضع النشط:** `{m_info['name']}`\n"
        f"⏱️ **مدة المونتاج والريندر:** `{est_time}`\n"
        f"📖 **طبيعة الوضع:** {m_info.get('desc', '')}\n"
        f"🔋 **رصيد الإنتاج اليومي المتبقي:** `{quota['remaining_pct']}%` (يتجدد بعد `{quota['reset_in']}`)\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        f"{agent_msg}\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "✍️ **اكتب الآن موضوع الفيديو (مثلاً: `جمال وتاريخ اليمن السعيد`، أو `أضرار المشروبات الغازية`، أو `مباراة ماين كرافت`) وسيقوم الوكلاء بدمج لقطات فيديو حقيقية بدون حقوق نشر مع مشاهد الـ AI وإخراج الفيديو كاملاً!**"
    )

    buttons = [
        [
            InlineKeyboardButton("🎬 الأوضاع الـ 17 (مع فيديو مثال لكل وضع)", callback_data="menu_modes_0"),
            InlineKeyboardButton("🤖 غرفة وكلاء المونتاج", callback_data="menu_quota")
        ],
        [
            InlineKeyboardButton("🇾🇪 تجربة فورية: فيديو عن اليمن السعيد", callback_data="quick_vid_yemen"),
            InlineKeyboardButton("🥤 تجربة: أضرار المشروبات الغازية", callback_data="quick_vid_soda")
        ],
        [
            InlineKeyboardButton("🔥 رادار التريندات الفيروسية (أعلى مشاهدات)", callback_data="menu_viral_radar")
        ],
        [
            InlineKeyboardButton("🎥 ترقية محركات الفيديو والصوت", callback_data="menu_eval_news"),
            InlineKeyboardButton("🧬 استنساخ ستايل فيديو جديد", callback_data="menu_clone_style")
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

    wait_text = f"🎥 **وكيل هندسة الفيديو:** جاري معايرة ودمج محرك (`{upg['tool_name']}`)..."
    msg_obj = await status_message.edit_text(wait_text) if status_message else await client.send_message(chat_id, wait_text)

    ok, sandbox_msg = await asyncio.to_thread(
        sentinel.test_in_sandbox_branch,
        upg_id,
        upg["tool_name"],
        upg.get("integration_code_snippet", "")
    )
    if ok:
        ok_merge, merge_msg = await asyncio.to_thread(sentinel.merge_sandbox_to_main, upg_id)
        USER_STATE[uid]["action"] = None
        await msg_obj.edit_text(
            f"🎬 **تقرير المعايرة:** {sandbox_msg}\n\n"
            f"🚀 **حالة التفعيل:** {merge_msg}",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 اللوحة الرئيسية", callback_data="menu_home")]])
        )


@app.on_message(filters.command("start") & filters.private)
async def start_cmd(client, message):
    USER_STATE.setdefault(message.from_user.id, {"mode": "hybrid", "action": None})
    USER_STATE[message.from_user.id]["action"] = None
    text, markup = get_main_dashboard(message.from_user.id)
    await message.reply_text(text, disable_web_page_preview=True, reply_markup=markup)


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
            await client.send_message(uid, text, disable_web_page_preview=True, reply_markup=markup)
        else:
            await cq.message.edit_text(text, disable_web_page_preview=True, reply_markup=markup)

    elif data == "quick_vid_yemen":
        topic = "جمال الطبيعة الخلابة والعمارة التاريخية في اليمن وصنعاء القديمة وجزيرة سقطرى"
        await cq.message.delete()
        status_msg = await client.send_message(uid, f"🇾🇪 **استوديو الوكلاء:** جاري مونتاج وإنتاج فيديو خاص عن اليمن السعيد...")
        asyncio.create_task(produce_video_for_topic(client, uid, topic, status_msg))

    elif data == "quick_vid_soda":
        topic = "أضرار المشروبات الغازية وتأثير السكر على صحة جسم الإنسان"
        await cq.message.delete()
        status_msg = await client.send_message(uid, f"🥤 **استوديو الوكلاء:** جاري مونتاج وإنتاج فيديو عن أضرار المشروبات الغازية...")
        asyncio.create_task(produce_video_for_topic(client, uid, topic, status_msg))

    elif data == "menu_viral_radar":
        wait_v = await cq.message.edit_text("🔥 **وكيل الرادار الفيروسي:** جاري سحب التريندات الحية وتحديث قواعد المونتاج...")
        viral_info = await asyncio.to_thread(viral_engine.learn_new_viral_rule_from_web)
        trends_str = " ، ".join(viral_info["trends"][:6])
        suggested_topic = viral_info["suggested_viral_topic"]
        USER_STATE[uid]["suggested_trend"] = suggested_topic

        msg = (
            "🔥 **تقرير وكيل التريندات والمونتاج الفيروسي:**\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            f"🌍 **المواضيع الرائجة الآن:**\n`{trends_str}`\n\n"
            f"🎥 **قاعدة المونتاج المضافة لذاكرة الوكلاء:**\n{viral_info['rule_ar']}\n\n"
            f"💡 **مشروع مقترح جاهز للتصوير الفوري:**\n`{suggested_topic}`"
        )
        buttons = InlineKeyboardMarkup([
            [InlineKeyboardButton("🎬 صوّر وأنتج هذا الفيديو الآن", callback_data="produce_trend_now")],
            [InlineKeyboardButton("🔄 استخراج قاعدة تصوير جديدة", callback_data="menu_viral_radar")],
            [InlineKeyboardButton("🔙 اللوحة الرئيسية", callback_data="menu_home")]
        ])
        await wait_v.edit_text(msg, reply_markup=buttons)

    elif data == "produce_trend_now":
        trend_topic = USER_STATE.get(uid, {}).get("suggested_trend", "جمال الطبيعة والتراث المعماري في اليمن السعيد")
        await cq.message.delete()
        status_msg = await client.send_message(uid, f"🎬 **مجلس وكلاء الإنتاج:** بدأ تصوير ومونتاج المشروع: `{trend_topic}`")
        asyncio.create_task(produce_video_for_topic(client, uid, trend_topic, status_msg))

    elif data.startswith("switch_produce_"):
        target_mode = data.replace("switch_produce_", "")
        USER_STATE[uid]["mode"] = target_mode
        saved_topic = USER_STATE[uid].get("saved_topic", "جمال الطبيعة في اليمن السعيد")
        await cq.message.delete()
        status_msg = await client.send_message(uid, f"🤖 **وكيل التوجيه:** تم تحويلك للوضع المناسب وبدء مونتاج: `{saved_topic}`")
        asyncio.create_task(produce_video_for_topic(client, uid, saved_topic, status_msg))

    elif data.startswith("menu_modes_"):
        page = int(data.split("_")[-1])
        msg_text = (
            f"🎬 **اختر وضع التصوير والمونتاج المطلوب (صفحة {page + 1}):**\n"
            "*(عند اختيار أي وضع، يعرض لك الوكلاء **فيديو مثال حقيقي `.mp4`** يوضح ستايل هذا الوضع)*"
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

        for field in ["est_time", "voice", "afilt", "vfilter", "sample_topic", "pixabay_query", "desc", "style"]:
            if field in default_mode:
                m_info[field] = default_mode[field]

        caption = (
            f"✅ **تم تفعيل: {m_info['name']}**\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            f"📹 **الفيديو بالأعلى هو مثال حقيقي لما يخرجه الوكلاء في هذا الوضع!**\n\n"
            f"📖 **وصف الوضع:**\n{m_info.get('desc', '')}\n\n"
            f"⏱️ **مدة التجهيز:** `{m_info.get('est_time', '30 إلى 50 ثانية')}` | ⚡ **الاستهلاك:** `{m_info['cost_pct']}%`\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "✍️ **اكتب الآن فكرة الفيديو مباشرة في المحادثة ليبدأ الوكلاء بمونتاجه وإرساله لك!**"
        )
        buttons = InlineKeyboardMarkup([
            [InlineKeyboardButton("📹 تثبيت فيديو تذكيري خاص من جهازي", callback_data=f"setsample_{mode_key}")],
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
            f"🎬 **وكيل المعاينة السينمائية:** جاري تجهيز وإرسال فيديو المثال الحقيقي لوضع ({m_info['name']})..."
        )
        try:
            mp4_sample = await video_engine.get_or_build_mode_sample(mode_key, m_info)
            sent_v = await client.send_video(uid, mp4_sample, caption=caption, reply_markup=buttons)
            await wait_prev.delete()
            if sent_v and sent_v.video:
                db.set_mode_sample_video(mode_key, sent_v.video.file_id)
        except Exception as e:
            await wait_prev.edit_text(f"{caption}\n\n⚠️ *(ملاحظة معاينة: {str(e)[:80]})*", reply_markup=buttons)

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
        req_msg = boardroom.build_agent_greeting_and_requirements()
        msg = (
            "🤖 **غرفة عمليات وكلاء المونتاج والإنتاج السينمائي:**\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            f"{req_msg}\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            f"🔋 **المتبقي من حصة اليوم:** `{q['remaining_pct']}%` (يتجدد بعد `{q['reset_in']}`)\n\n"
            f"🧠 **قواعد التصوير والمونتاج النشطة:**\n`{lessons}`"
        )
        await cq.message.edit_text(msg, disable_web_page_preview=True, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="menu_home")]]))

    elif data == "menu_eval_news":
        USER_STATE[uid]["action"] = "awaiting_news"
        await cq.message.edit_text(
            "🎥 **وكيل ترقية محركات الفيديو والصوت:**\n\n"
            "اكتب **ابحث انت وقلي** أو اسم أي نموذج فيديو جديد ليفحصه الوكيل ويدمجه في استوديو الإنتاج!",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 إلغاء", callback_data="menu_home")]])
        )

    elif data == "menu_clone_style":
        USER_STATE[uid]["action"] = "awaiting_style_clone"
        await cq.message.edit_text(
            "🧬 **وكيل استنساخ الأنماط البصرية (مع حارس عدم التكرار):**\n\n"
            "أرسل الآن **الفيديو مع كتابة اسم النمط الجديد في الوصف**.\n"
            "⛔ *يرفض الوكيل تلقائياً أي نمط مكرر مع الأوضاع الـ 17 الموجودة!*",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 إلغاء", callback_data="menu_home")]])
        )

    elif data.startswith("sandbox_test_"):
        upg_id = data.replace("sandbox_test_", "")
        await execute_upgrade_flow(client, cq.message.chat.id, uid, upg_id, status_message=cq.message)


async def produce_video_for_topic(client, uid, topic_text, status_msg):
    try:
        mode_key = USER_STATE.get(uid, {}).get("mode", "hybrid")
        modes = db.get_all_modes()
        m_info = modes.get(mode_key, modes["hybrid"])
        default_mode = Config.DEFAULT_MODES.get(mode_key, {})
        for field in ["est_time", "voice", "afilt", "vfilter", "style", "pixabay_query"]:
            if field in default_mode:
                m_info[field] = default_mode[field]

        est_time = m_info.get("est_time", "30 إلى 50 ثانية")

        async def update_progress(step_text):
            try:
                await status_msg.edit_text(
                    f"🎬 **استوديو الوكلاء يصمم الفيديو الخاص بك الآن (CapCut & AI)...**\n"
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
            f"✅ **تم مونتاج وإنتاج الفيديو بنجاح!**\n"
            f"🎬 **العنوان:** `{script_data.get('title_ar', '')}`\n\n"
            f"🎙️ **السيناريو الصوتي العربي:**\n{script_data.get('voiceover_ar', '')}\n\n"
            f"📈 **هاشتاجات الانتشار:**\n`{script_data.get('hashtags', '#اكسبلور #تريند')}`\n\n"
            f"💬 **التعليق المثبت لرفع اللايكات:**\n`{script_data.get('pinned_comment', '')}`\n"
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
    except Exception as e:
        try:
            await status_msg.edit_text(
                f"⚠️ **تقرير وكيل الريندر:** حدث خطأ أثناء الإرسال (`{str(e)[:120]}`)، يرجى إعادة المحاولة.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 اللوحة الرئيسية", callback_data="menu_home")]])
            )
        except Exception:
            pass


@app.on_message((filters.text | filters.video) & filters.private)
async def handle_user_input(client, message):
    uid = message.from_user.id
    USER_STATE.setdefault(uid, {"mode": "hybrid", "action": None})
    action = USER_STATE[uid].get("action")
    mode_key = USER_STATE[uid].get("mode", "hybrid")
    text = (message.text or message.caption or "").strip()

    # الأولوية القصوى رقم 1: التقاط أي مفتاح API يرسله المستخدم حتى لو كان داخل أي قائمة!
    auto_key_name, auto_key_val = boardroom.detect_auto_api_key_in_message(text)
    if auto_key_name and auto_key_val:
        USER_STATE[uid]["action"] = None
        db.save_api_key(auto_key_name, auto_key_val)
        await message.reply_text(
            f"✅ **وكيل التجهيز:** التقطتُ المفتاح `{auto_key_name}` وحفظته في الذاكرة الدائمة بنجاح!\n"
            "🚀 جميع محركات الفيديو والـ GPU متصلة الآن وجاهزة لإنتاج فيديوهاتك.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 اللوحة الرئيسية", callback_data="menu_home")]])
        )
        return

    if action and action.startswith("confirm_upgrade_"):
        upg_id = action.replace("confirm_upgrade_", "")
        if text in ["نعم", "ايوه", "أيوه", "موافق", "ايه", "اضفه", "تحديث", "طوره", "yes", "ok"]:
            await execute_upgrade_flow(client, message.chat.id, uid, upg_id)
            return
        elif text in ["لا", "الغي", "إلغاء", "رفض", "no"]:
            USER_STATE[uid]["action"] = None
            db.remove_pending_upgrade(upg_id)
            await message.reply_text("❌ تم إلغاء الترقية.")
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
            await message.reply_text("⚠️ يرجى إرسال ملف فيديو صالح.")
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
            desc=style_data.get("desc", "نمط سينمائي مخصص"),
            sample_file_id=sample_fid,
            video_unique_id=vid_uniq
        )

        if not added_ok:
            await wait_msg.edit_text(
                f"⛔ **وكيل منع التكرار: هذا الوضع موجود في نظامك من قبل!**\n\n"
                f"🏷️ **الوضع الموجود عندك:** `{result_mode['name']}`",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🎬 الذهاب للوضع الموجود", callback_data="menu_modes_0")]])
            )
            return

        USER_STATE[uid]["mode"] = style_data["mode_id"]
        await wait_msg.edit_text(
            f"✅ **تمت إضافة الوضع الجديد بنجاح!**\n🏷️ **الاسم:** `{result_mode['name']}`",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("👁️ فتح الوضع الجديد", callback_data=f"setmode_{style_data['mode_id']}")]])
        )
        return

    if message.video and mode_key == "cloning":
        proc_msg = await message.reply_text("🧬 **وكيل ترميم الفيديو:** جاري قص العلامات المائية وترميم الجودة...")
        dl_path = await message.download(file_name=f"/tmp/input_{message.id}.mp4")
        cleaned_path = await video_engine.clean_and_enhance_video(dl_path)
        quota_after = db.consume_quota(8.0)
        await client.send_video(
            uid,
            cleaned_path,
            caption=f"✅ **تم تنظيف وترميم الفيديو بنجاح!**\n🔋 **الحصة المتبقية:** `{quota_after['remaining_pct']}%`",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 اللوحة الرئيسية", callback_data="menu_home")]])
        )
        await proc_msg.delete()
        return

    if action == "awaiting_news":
        USER_STATE[uid]["action"] = None
        wait_msg = await message.reply_text("🎥 **وكيل ترقية الفيديو:** جاري البحث عن أحدث محركات التصوير والمونتاج...")
        report = await asyncio.to_thread(sentinel.evaluate_user_news, text)
        upg_id = f"upg_{int(time.time()) % 100000}"
        db.save_pending_upgrade(upg_id, report)
        USER_STATE[uid]["action"] = f"confirm_upgrade_{upg_id}"

        reply = (
            f"🎥 **تقرير وكيل ترقية محركات الفيديو حول: `{report.get('tool_name')}`**\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            f"{report.get('comparison_ar')}\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "❓ **هل تريد تفعيل هذا المحرك في استوديو الإنتاج؟** *(اكتب **نعم** أو اضغط الزر)*"
        )
        buttons = [
            [InlineKeyboardButton("✅ نعم، فعّل المحرك الآن", callback_data=f"sandbox_test_{upg_id}")],
            [InlineKeyboardButton("❌ إلغاء", callback_data="menu_home")]
        ]
        await wait_msg.edit_text(reply, reply_markup=InlineKeyboardMarkup(buttons))
        return

    req_check = boardroom.analyze_user_request_requirements(text, bool(message.video), mode_key)
    if not req_check.get("ready"):
        USER_STATE[uid]["saved_topic"] = req_check.get("saved_topic", text)
        btns = []
        if req_check.get("quick_topics"):
            btns.append([InlineKeyboardButton("🇾🇪 أنتج فيديو عن اليمن السعيد الآن", callback_data="quick_vid_yemen")])
            btns.append([InlineKeyboardButton("🥤 أنتج فيديو عن أضرار المشروبات الغازية", callback_data="quick_vid_soda")])
        if req_check.get("suggest_switch_mode"):
            sm = req_check["suggest_switch_mode"]
            btns.append([InlineKeyboardButton("🎬 نعم، صوّر وأنتج الفيديو الآن!", callback_data=f"switch_produce_{sm}")])
        btns.append([InlineKeyboardButton("🏠 اللوحة الرئيسية", callback_data="menu_home")])
        await message.reply_text(req_check["missing_msg"], reply_markup=InlineKeyboardMarkup(btns))
        return

    modes = db.get_all_modes()
    m_info = modes.get(mode_key, modes["hybrid"])
    est_time = m_info.get("est_time", "30 إلى 50 ثانية")

    status_msg = await message.reply_text(
        f"🎬 **استلم وكلاء المونتاج والإنتاج مشروعك!**\n"
        f"▪️ **الموضوع:** `{text[:50]}`\n"
        f"▪️ **الوضع:** `{m_info['name']}` (المدة المقدرة: `{est_time}`)\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "⏳ *جاري سحب اللقطات الحقيقية وتوليد المشاهد...*"
    )
    asyncio.create_task(produce_video_for_topic(client, uid, text, status_msg))


async def start_genesis():
    print("🚀 Starting Genesis Cinema Studio v10.0 (CapCut Hybrid + Strict Geo-Lock)...")
    start_threaded_watchdog()
    while True:
        try:
            await app.start()
            break
        except FloodWait as e:
            wait_sec = int(getattr(e, "value", 60)) + 5
            print(f"⏳ FloodWait active: sleeping {wait_sec}s...")
            await asyncio.sleep(wait_sec)

    asyncio.create_task(video_engine.prewarm_all_modes_background())
    print("✅ Studio is online 24/7 with embedded HF & Pixabay keys!")
    await idle()
    await app.stop()


if __name__ == "__main__":
    app.run(start_genesis())
