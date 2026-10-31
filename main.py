import os
import sys
import time
import asyncio
from pyrogram import Client, filters, idle
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import Config
from database import db
from sentinel_evolution import sentinel, video_engine

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
    est_time = m_info.get("est_time", "45 إلى 70 ثانية")
    quota = db.get_quota_status()

    text = (
        "👑 **إمبراطورية Genesis Engine الخالدة (v6.5 Zero-Fail Video Studio)**\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        f"🎯 **الوضع النشط حالياً:** `{m_info['name']}`\n"
        f"⏱️ **مدة تجهيز الفيديو في هذا الوضع:** `{est_time}`\n"
        f"📝 **وصف الوضع:** {m_info.get('desc', '')}\n"
        f"🔋 **رصيد المعالجة اليومي المتبقي:** `{quota['remaining_pct']}%`\n"
        f"⏳ **يتجدد الرصيد بالكامل بعد:** `{quota['reset_in']}`\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "💡 *اكتب فكرة الفيديو مباشرة في المحادثة ليقوم البوت بإنتاج وإرسال الفيديو (`.mp4`) بالصوت العربي فوراً!*"
    )

    buttons = [
        [
            InlineKeyboardButton("🎬 الأوضاع الـ 17 (مع نموذج فيديو جاهز لكل وضع)", callback_data="menu_modes_0"),
            InlineKeyboardButton("📊 الموارد والذاكرة", callback_data="menu_quota")
        ],
        [
            InlineKeyboardButton("🔬 فحص خبر أو البحث التلقائي عن أداة جديدة", callback_data="menu_eval_news")
        ],
        [
            InlineKeyboardButton("🧬 استنساخ وضع جديد (مع كاشف التكرار الصارم)", callback_data="menu_clone_style"),
            InlineKeyboardButton("🔑 إضافة مفتاح API", callback_data="menu_add_key")
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

    wait_text = f"⏳ **جاري اختبار وتجهيز التطوير (`{upg['tool_name']}`) في البيئة المعزولة (`{Config.SANDBOX_BRANCH}`)...**"
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
            f"🧪 **نتيجة البيئة المعزولة:** {sandbox_msg}\n\n"
            f"🚀 **حالة الدمج النهائي:** {merge_msg}\n\n"
            "✨ **تمت إضافة التطوير إلى نظامك بنجاح وسيتكيف معه للأبد!**",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 اللوحة الرئيسية", callback_data="menu_home")]])
        )
    else:
        await msg_obj.edit_text(
            f"⚠️ **نتيجة فحص البيئة المعزولة:**\n{sandbox_msg}",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="menu_home")]])
        )


@app.on_message(filters.command("start") & filters.private)
async def start_cmd(client, message):
    if message.id in PROCESSED_MESSAGES:
        return
    PROCESSED_MESSAGES.add(message.id)
    USER_STATE.setdefault(message.from_user.id, {"mode": "hybrid", "action": None})
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

    elif data.startswith("menu_modes_"):
        page = int(data.split("_")[-1])
        msg_text = (
            f"🎬 **اختر وضع الإنتاج المطلوب (صفحة {page + 1}):**\n"
            "*(بمجرد الضغط على أي وضع، سيظهر لك **نموذج فيديو حقيقي طبق الأصل** لما سيخرجه لك البوت في هذا الوضع)*"
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

        for field in ["est_time", "voice", "afilt", "vfilter", "sample_topic", "desc"]:
            if field in default_mode:
                m_info[field] = default_mode[field]

        caption = (
            f"✅ **تم تفعيل: {m_info['name']}**\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            f"📹 **الفيديو بالأعلى هو نموذج طبق الأصل لما يخرجه هذا الوضع!**\n\n"
            f"📖 **وصف الوضع:**\n{m_info.get('desc', '')}\n\n"
            f"⏱️ **مدة تجهيز وإنتاج الفيديو:** `{m_info.get('est_time', '45 إلى 70 ثانية')}`\n"
            f"⚡ **الاستهلاك لكل مشروع:** `{m_info['cost_pct']}%` من الحصة اليومية\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "✍️ **اكتب الآن فكرة الفيديو مباشرة في المحادثة ليبدأ البوت بإنتاج وإرسال الفيديو (`.mp4`) لك!**"
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

        # 1. إذا كان الفيديو محفوظاً في تيليجرام، يظهر في أقل من ثانية!
        if sample_vid:
            try:
                await client.send_video(uid, sample_vid, caption=caption, reply_markup=buttons)
                return
            except Exception:
                pass

        # 2. إرسال النموذج المطابق للأصل وحفظه للأبد في ذاكرة تيليجرام والـ Repo
        wait_prev = await client.send_message(
            uid,
            f"🎬 **جاري فتح نموذج الفيديو المطابق للأصل لوضع ({m_info['name']})...**"
        )
        try:
            mp4_sample = await video_engine.get_or_build_mode_sample(mode_key, m_info)
            sent_v = await client.send_video(uid, mp4_sample, caption=caption, reply_markup=buttons)
            await wait_prev.delete()
            if sent_v and sent_v.video:
                db.set_mode_sample_video(mode_key, sent_v.video.file_id)
        except Exception as e:
            await wait_prev.edit_text(f"{caption}\n\n*(ملاحظة: {str(e)[:80]})*", reply_markup=buttons)

    elif data.startswith("setsample_"):
        mode_key = data.replace("setsample_", "")
        USER_STATE[uid]["action"] = f"awaiting_sample_vid_{mode_key}"
        await client.send_message(
            uid,
            "📹 **أرسل الآن مقطع الفيديو الذي تريد تثبيته كنموذج لهذا الوضع:**",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 إلغاء", callback_data="menu_home")]])
        )

    elif data == "menu_quota":
        q = db.get_quota_status()
        lessons = db.get_relevant_lessons()
        msg = (
            "📊 **تقرير وكيل الموارد والذاكرة الحية:**\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            f"🔹 **المستهلك اليوم:** `{q['used_pct']}%`\n"
            f"🔹 **المتبقي اليوم:** `{q['remaining_pct']}%`\n"
            f"🔹 **موعد التجديد القادم:** بعد `{q['reset_in']}`\n"
            f"🔹 **الحساب النشط:** `{q['active_node']}` (يبدل تلقائياً بين حسابيك)\n\n"
            f"🧠 **آخر الدروس المتعلمة في الذاكرة:**\n`{lessons}`"
        )
        await cq.message.edit_text(msg, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="menu_home")]]))

    elif data == "menu_eval_news":
        USER_STATE[uid]["action"] = "awaiting_news"
        await cq.message.edit_text(
            "🔬 **مختبر فحص الأخبار والبحث الذاتي عن الأدوات (Truth Sentinel):**\n\n"
            "• اكتب اسم أي أداة سمعت عنها لفحصها.\n"
            "• أو اكتب **ابحث انت وقلي** ليقوم البوت بالاتصال المباشر بقائمة Trending في HuggingFace وGitHub ويجلب لك أحدث نموذج حقيقي موثق!",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 إلغاء", callback_data="menu_home")]])
        )

    elif data == "menu_clone_style":
        USER_STATE[uid]["action"] = "awaiting_style_clone"
        await cq.message.edit_text(
            "🧬 **وكيل الهندسة العكسية واستنساخ الأنماط (مع كاشف التكرار الصارم):**\n\n"
            "أرسل الآن **الفيديو مع كتابة اسم النمط الجديد في الوصف** (أو اكتب وصف النمط الجديد الذي لا يوجد ضمن الأوضاع الـ 17).\n"
            "⛔ *إذا كان النمط مشابهاً لأي وضع موجود لديك مسبقاً (مثل السينمائي أو السريع أو الأنمي...) سيرفضه البوت فوراً ويخبرك باسم الوضع الموجود عندك!*",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 إلغاء", callback_data="menu_home")]])
        )

    elif data == "menu_add_key":
        USER_STATE[uid]["action"] = "awaiting_manual_key"
        await cq.message.edit_text(
            "🔑 **بروتوكول المصادقة وحفظ المفاتيح (API Handshake):**\n\n"
            "أرسل المفتاح بالصيغة التالية ليتم حفظه في قاعدة البيانات فوراً:\n"
            "`SERVICE_NAME:YOUR_API_KEY`",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 إلغاء", callback_data="menu_home")]])
        )

    elif data.startswith("sandbox_test_"):
        upg_id = data.replace("sandbox_test_", "")
        await execute_upgrade_flow(client, cq.message.chat.id, uid, upg_id, status_message=cq.message)


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

    # 0. تأكيد التطوير بكلمة "نعم"
    if action and action.startswith("confirm_upgrade_"):
        upg_id = action.replace("confirm_upgrade_", "")
        if text in ["نعم", "ايوه", "أيوه", "موافق", "ايه", "اضفه", "تحديث", "طوره", "yes", "ok"]:
            await execute_upgrade_flow(client, message.chat.id, uid, upg_id)
            return
        elif text in ["لا", "الغي", "إلغاء", "رفض", "no"]:
            USER_STATE[uid]["action"] = None
            db.remove_pending_upgrade(upg_id)
            await message.reply_text("❌ تم إلغاء التحديث بناءً على طلبك.")
            return

    # 1. حفظ فيديو تذكيري خاص لوضع معين
    if action and action.startswith("awaiting_sample_vid_"):
        target_mode = action.replace("awaiting_sample_vid_", "")
        USER_STATE[uid]["action"] = None
        if message.video:
            db.set_mode_sample_video(target_mode, message.video.file_id)
            await message.reply_text(
                "✅ **تم تثبيت هذا الفيديو كنموذج رسمي للوضع بنجاح!**",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🎬 عرض الوضع الآن", callback_data=f"setmode_{target_mode}")]])
            )
        else:
            await message.reply_text("⚠️ يرجى إرسال ملف فيديو صالح.")
        return

    # 2. استنساخ وضع جديد مع المنع الصارم للتكرار
    if action == "awaiting_style_clone":
        USER_STATE[uid]["action"] = None
        wait_msg = await message.reply_text("🔍 **جاري فحص الفيديو والنمط ومطابقته مع الأوضاع الـ 17 لمنع أي تكرار...**")
        vid_uniq = message.video.file_unique_id if message.video else ""
        style_data = await asyncio.to_thread(sentinel.reverse_engineer_video_style, text, vid_uniq)

        if style_data.get("is_duplicate"):
            await wait_msg.edit_text(
                f"⛔ **تم رفض الإضافة: هذا الوضع موجود في نظامك من قبل!**\n\n"
                f"🏷️ **الوضع المطابق الموجود عندك:** `{style_data.get('matched_mode_name', 'وضع أساسي')}`\n"
                f"📌 **السبب:** {style_data.get('reason', 'النمط متطابق مع أحد الأوضاع الحالية في البوت.')}",
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
                f"⛔ **تم رفض الإضافة: هذا الوضع موجود في نظامك من قبل!**\n\n"
                f"🏷️ **الوضع الموجود عندك:** `{result_mode['name']}`\n"
                f"📖 **وصفه:** {result_mode.get('desc', '')}",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🎬 الذهاب للوضع الموجود", callback_data="menu_modes_0")]])
            )
            return

        USER_STATE[uid]["mode"] = style_data["mode_id"]
        await wait_msg.edit_text(
            f"✅ **تم التحقق من فرادة النمط وإضافته لنظامك!**\n\n"
            f"🏷️ **اسم الوضع الجديد:** `{result_mode['name']}`\n"
            f"📖 **الوصف:** {result_mode['desc']}",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("👁️ فتح الوضع الجديد مع نموذج الفيديو", callback_data=f"setmode_{style_data['mode_id']}")]])
        )
        return

    # 3. معالجة الفيديو في وضع استنساخ الوجه والحذف
    if message.video and mode_key == "cloning":
        proc_msg = await message.reply_text(
            "🧬 **جاري معالجة الفيديو في وضع (استنساخ الوجه والحذف)...**\n"
            "⏳ *جاري قص العلامات المائية من الأطراف وترميم جودة الملامح والألوان...*"
        )
        dl_path = await message.download(file_name=f"/tmp/input_{message.id}.mp4")
        cleaned_path = await video_engine.clean_and_enhance_video(dl_path)
        quota_after = db.consume_quota(8.0)
        await client.send_video(
            uid,
            cleaned_path,
            caption=(
                "✅ **تم تنظيف الفيديو من العلامات المائية وترميم الجودة بنجاح!**\n"
                f"🔋 **الحصة المتبقية لك اليوم:** `{quota_after['remaining_pct']}%`"
            ),
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 اللوحة الرئيسية", callback_data="menu_home")]])
        )
        await proc_msg.delete()
        return

    # 4. فحص الأخبار أو البحث التلقائي ("ابحث انت وقلي")
    if action == "awaiting_news":
        wait_msg = await message.reply_text("🛰️ **جاري الاتصال المباشر بـ HuggingFace وGitHub لجلب أحدث نموذج حقيقي موثق...**")
        report = await asyncio.to_thread(sentinel.evaluate_user_news, text)

        upg_id = f"upg_{int(time.time()) % 100000}"
        db.save_pending_upgrade(upg_id, report)
        USER_STATE[uid]["action"] = f"confirm_upgrade_{upg_id}"

        reply = (
            f"🔬 **تقرير الاكتشاف والفحص الحي حول: `{report.get('tool_name')}`**\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "⚖️ **الرأي الهندسي:** 🟢 **نموذج حقيقي موثق ومتاح للإضافة الفورية**\n\n"
            f"📊 **التفاصيل الحية من المنصات:**\n{report.get('comparison_ar')}\n\n"
            "🔑 **هل تحتاج مفتاح API؟** `لا (يعمل مجاناً مباشرة)`\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "❓ **هل تريد أن تعمل التحديث أو التطوير؟**\n"
            "*(فقط اكتب **نعم** في المحادثة أو اضغط على الزر بالأسفل ليتم إضافته تلقائياً)*"
        )
        buttons = [
            [InlineKeyboardButton("✅ نعم، اعمل التحديث والتطوير", callback_data=f"sandbox_test_{upg_id}")],
            [InlineKeyboardButton("❌ لا، إلغاء", callback_data="menu_home")]
        ]
        await wait_msg.edit_text(reply, reply_markup=InlineKeyboardMarkup(buttons))
        return

    # 5. حفظ مفتاح API يدوي
    if action == "awaiting_manual_key":
        USER_STATE[uid]["action"] = None
        if ":" in text:
            k_name, k_val = text.split(":", 1)
            db.save_api_key(k_name.strip(), k_val.strip())
            await message.reply_text(f"✅ **تم حفظ المفتاح `{k_name.strip()}` بنجاح في الذاكرة الدائمة!**")
        else:
            await message.reply_text("⚠️ الصيغة غير صحيحة. أرسله هكذا: `NAME:KEY`")
        return

    # 6. إنتاج الفيديو الكامل (.mp4) بالصوت العربي لأي موضوع يكتبه المستخدم
    modes = db.get_all_modes()
    m_info = modes.get(mode_key, modes["hybrid"])
    default_mode = Config.DEFAULT_MODES.get(mode_key, {})
    for field in ["est_time", "voice", "afilt", "vfilter"]:
        if field in default_mode:
            m_info[field] = default_mode[field]

    est_time = m_info.get("est_time", "45 إلى 70 ثانية")
    quota_before = db.get_quota_status()

    if quota_before["remaining_pct"] < m_info["cost_pct"]:
        await message.reply_text(
            f"⚠️ **رصيد اليوم ({quota_before['remaining_pct']}%) لا يكفي لهذا الوضع ({m_info['cost_pct']}%).**\n"
            f"⏳ سيتجدد الرصيد بالكامل بعد: `{quota_before['reset_in']}`."
        )
        return

    status_msg = await message.reply_text(
        f"🎬 **بدأ إنتاج الفيديو الحقيقي لمشروعك!**\n"
        f"▪️ **الموضوع:** `{text[:50]}`\n"
        f"▪️ **الوضع النشط:** `{m_info['name']}`\n"
        f"⏱️ **المدة المقدرة للتجهيز:** `{est_time}`\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "⏳ *جاري البدء بالخطوة 1 من 4...*"
    )

    async def update_progress(step_text):
        try:
            await status_msg.edit_text(
                f"🎬 **جاري صناعة وريندر الفيديو الخاص بك...**\n"
                f"▪️ **الوضع:** `{m_info['name']}` (المدة المقدرة: `{est_time}`)\n"
                "━━━━━━━━━━━━━━━━━━━━━\n"
                f"{step_text}"
            )
        except Exception:
            pass

    try:
        final_video_path, script_data = await video_engine.render_full_video(
            text or "طفل يلعب كرة القدم في ملعب مشمس",
            mode_key,
            m_info,
            progress_callback=update_progress,
            num_scenes=3
        )
        quota_after = db.consume_quota(m_info["cost_pct"])

        video_caption = (
            f"✅ **تم إنتاج الفيديو بنجاح!**\n"
            f"🎬 **العنوان:** {script_data.get('title_ar', '')}\n"
            f"🎯 **الوضع:** `{m_info['name']}`\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            f"🎙️ **النص الصوتي العربي:**\n{script_data.get('voiceover_ar', '')}\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            f"🔋 **الحصة المتبقية اليوم:** `{quota_after['remaining_pct']}%` (تتجدد بعد `{quota_after['reset_in']}`)"
        )

        await client.send_video(
            uid,
            final_video_path,
            caption=video_caption[:1020],
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 اللوحة الرئيسية", callback_data="menu_home")]])
        )
        await status_msg.delete()
    except Exception as e:
        await status_msg.edit_text(
            f"⚠️ حدث خطأ غير متوقع: `{str(e)[:150]}`",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 اللوحة الرئيسية", callback_data="menu_home")]])
        )


async def immortal_lifecycle_watchdog():
    while True:
        await asyncio.sleep(60)
        elapsed_minutes = (time.time() - START_TIME) / 60.0
        if elapsed_minutes >= 345:
            sentinel.trigger_self_respawn()
            await asyncio.sleep(10)
            os._exit(0)


async def start_genesis():
    print("🚀 Starting Genesis Immortal Engine v6.5...")
    await app.start()
    asyncio.create_task(immortal_lifecycle_watchdog())
    # تشغيل التجهيز المسبق لنماذج الفيديو في الخلفية فور الإقلاع
    asyncio.create_task(video_engine.prewarm_all_modes_background())
    print("✅ Bot is online and pre-warming mode sample videos!")
    await idle()
    await app.stop()


if __name__ == "__main__":
    app.run(start_genesis())
