import os
import time
import asyncio
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import Config
from database import db
from sentinel_evolution import sentinel, SmartCouncil

app = Client(
    "genesis_immortal_bot",
    api_id=Config.API_ID,
    api_hash=Config.API_HASH,
    bot_token=Config.BOT_TOKEN
)

START_TIME = time.time()
PROCESSED_MESSAGES = set()
USER_STATE = {}

def get_main_dashboard(user_id):
    selected_mode = USER_STATE.get(user_id, {}).get("mode", "hybrid")
    modes = db.get_all_modes()
    m_info = modes.get(selected_mode, modes["hybrid"])
    quota = db.get_quota_status()

    text = (
        "👑 **إمبراطورية Genesis Engine الخالدة (v5.5 Immortal)**\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        f"🎯 **الوضع النشط حالياً:** `{m_info['name']}`\n"
        f"📝 **وصف الوضع:** {m_info.get('desc', '')}\n"
        f"🔋 **رصيد المعالجة اليومي المتبقي:** `{quota['remaining_pct']}%`\n"
        f"⏳ **يتجدد الرصيد بالكامل بعد:** `{quota['reset_in']}`\n"
        f"🖥️ **عقدة كاجل النشطة:** `{quota['active_node']} (60h Fleet)`\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "💡 *أرسل فكرة الفيديو مباشرة للبدء، أو اختر من الأزرار:*"
    )

    buttons = [
        [
            InlineKeyboardButton("🎬 تصفح الأوضاع الـ 17+ (مع الصور)", callback_data="menu_modes_0"),
            InlineKeyboardButton("📊 تفاصيل الموارد والذاكرة", callback_data="menu_quota")
        ],
        [
            InlineKeyboardButton("🔬 فحص خبر / أداة جديدة وتطوير النظام", callback_data="menu_eval_news")
        ],
        [
            InlineKeyboardButton("🧬 استنساخ وضع جديد من فيديو", callback_data="menu_clone_style"),
            InlineKeyboardButton("🔑 إضافة مفتاح API يدوياً", callback_data="menu_add_key")
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
        for k, v in sliced[i:i+2]:
            row.append(InlineKeyboardButton(f"{v['name']} ({v['cost_pct']}%)", callback_data=f"setmode_{k}"))
        rows.append(row)

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("⬅️ السابق", callback_data=f"menu_modes_{page-1}"))
    if end < len(modes):
        nav.append(InlineKeyboardButton("التالي ➡️", callback_data=f"menu_modes_{page+1}"))
    if nav:
        rows.append(nav)

    rows.append([InlineKeyboardButton("🔙 العودة للوحة الرئيسية", callback_data="menu_home")])
    return InlineKeyboardMarkup(rows)

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
            f"🎬 **اختر وضع الإنتاج المطلوب (صفحة {page+1}):**\n"
            "*(عند الضغط على أي وضع، سيظهر لك مثال بصري يذكرك بشكل الفيديو الذي ينتجه هذا الوضع)*"
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

        caption = (
            f"✅ **تم تفعيل: {m_info['name']}**\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            f"📖 **تذكير بنوع الفيديو في هذا الوضع:**\n{m_info.get('desc', 'إنتاج احترافي متكامل.')}\n\n"
            f"🎨 **البصمة البصرية (Style Prompt):**\n`{m_info['style']}`\n\n"
            f"⚡ **الاستهلاك لكل مشروع:** `{m_info['cost_pct']}%` من الحصة اليومية\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "✍️ **اكتب الآن فكرة الفيديو مباشرة في المحادثة لنبدأ إنتاجه بهذا النمط!**"
        )
        buttons = InlineKeyboardMarkup([
            [InlineKeyboardButton("📹 حفظ فيديو تذكيري خاص لهذا الوضع", callback_data=f"setsample_{mode_key}")],
            [InlineKeyboardButton("🔄 تغيير الوضع", callback_data="menu_modes_0"), InlineKeyboardButton("🏠 الرئيسية", callback_data="menu_home")]
        ])

        await cq.message.delete()
        sample_vid = m_info.get("sample_file_id", "")
        preview_img = m_info.get("preview_url", "")

        try:
            if sample_vid:
                await client.send_video(uid, sample_vid, caption=caption, reply_markup=buttons)
            elif preview_img:
                await client.send_photo(uid, preview_img, caption=caption, reply_markup=buttons)
            else:
                await client.send_message(uid, caption, reply_markup=buttons)
        except Exception:
            await client.send_message(uid, caption, reply_markup=buttons)

    elif data.startswith("setsample_"):
        mode_key = data.replace("setsample_", "")
        USER_STATE[uid]["action"] = f"awaiting_sample_vid_{mode_key}"
        await client.send_message(
            uid,
            "📹 **أرسل الآن مقطع فيديو قصير (أو GIF) تريد حفظه كمثال تذكيري لهذا الوضع**، وسيظهر لك دائماً عند اختيار هذا الوضع:",
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
            "🔬 **مختبر فحص الأخبار والأدوات الذكي (Truth Sentinel):**\n\n"
            "اكتب لي الآن أي خبر سمعته أو اسم أداة/نموذج جديد.\n"
            "سأفحصه في HuggingFace و GitHub، وأقارنه بما لديك، وإذا كان مكرراً سأنبهك، وإذا كان جديداً ومفيداً سأختبره في `staging-sandbox` وأدمجه بموافقتك!",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 إلغاء", callback_data="menu_home")]])
        )

    elif data == "menu_clone_style":
        USER_STATE[uid]["action"] = "awaiting_style_clone"
        await cq.message.edit_text(
            "🧬 **وكيل الهندسة العكسية واستنساخ الأنماط (مع كاشف التكرار):**\n\n"
            "أرسل لي الآن **فيديو** أعجبك في الإنترنت (أو اكتب وصفاً للستايل الذي تريده).\n"
            "⚠️ *ملاحظة: إذا كان الوضع موجوداً مسبقاً في نظامك، سيرفض النظام إضافته ويخبرك باسم الوضع الموجود عندك لمنع الفوضى!*",
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
        upg = db.get_pending_upgrade(upg_id)
        if not upg:
            await cq.answer("انتهت صلاحية هذا الطلب.", show_alert=True)
            return

        if upg.get("requires_api_key") and upg.get("key_env_name"):
            key_name = upg["key_env_name"]
            if not db.get_api_key(key_name):
                USER_STATE[uid]["action"] = f"awaiting_upgrade_key_{upg_id}"
                await cq.message.edit_text(
                    f"🔑 **هذه الأداة (`{upg['tool_name']}`) تتطلب مفتاح API خاص بك لتعمل:**\n\n"
                    f"1️⃣ ادخل على الرابط الرسمي التالي وسجل حساباً مجانياً:\n🔗 {upg.get('signup_url', 'https://huggingface.co/settings/tokens')}\n\n"
                    f"2️⃣ انسخ الـ API Key وأرسله لي هنا مباشرة، وسأحفظه تلقائياً باسم `{key_name}` وأبدأ اختبار Sandbox!",
                    disable_web_page_preview=True,
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 إلغاء", callback_data="menu_home")]])
                )
                return

        await cq.message.edit_text(f"⏳ **جاري إنشاء فرع معزول (`{Config.SANDBOX_BRANCH}`) واختبار الكود الجديد لأداة `{upg['tool_name']}`...**")
        ok, msg = await asyncio.to_thread(
            sentinel.test_in_sandbox_branch,
            upg_id,
            upg["tool_name"],
            upg.get("integration_code_snippet", "# Verified Plugin\n")
        )
        if ok:
            buttons = [
                [InlineKeyboardButton("✅ نعم، اعتمد الترقية للنظام الأساسي", callback_data=f"sandbox_merge_{upg_id}")],
                [InlineKeyboardButton("❌ رفض وإلغاء", callback_data="menu_home")]
            ]
            await cq.message.edit_text(
                f"🧪 **نجح الاختبار في البيئة المعزولة (Sandbox)!**\n\n"
                f"📌 **التفاصيل:** {msg}\n\n"
                f"هل توافق الآن على دمج هذا التطور في نظامك الأساسي (`main`)؟",
                reply_markup=InlineKeyboardMarkup(buttons)
            )
        else:
            await cq.message.edit_text(
                f"⚠️ **نتيجة فحص البيئة المعزولة:**\n{msg}",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="menu_home")]])
            )

    elif data.startswith("sandbox_merge_"):
        upg_id = data.replace("sandbox_merge_", "")
        await cq.message.edit_text("🚀 **جاري دمج الترقية في النظام الأساسي (`main`)...**")
        ok, msg = await asyncio.to_thread(sentinel.merge_sandbox_to_main, upg_id)
        await cq.message.edit_text(
            f"{msg}\n\n✨ نظامك الآن تطور ذاتياً بنجاح!",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 اللوحة الرئيسية", callback_data="menu_home")]])
        )

@app.on_message((filters.text | filters.video) & filters.private)
async def handle_user_input(client, message):
    if message.id in PROCESSED_MESSAGES:
        return
    PROCESSED_MESSAGES.add(message.id)

    uid = message.from_user.id
    USER_STATE.setdefault(uid, {"mode": "hybrid", "action": None})
    action = USER_STATE[uid].get("action")
    text = (message.text or message.caption or "").strip()

    # 0. حفظ فيديو تذكيري لوضع معين
    if action and action.startswith("awaiting_sample_vid_"):
        mode_key = action.replace("awaiting_sample_vid_", "")
        USER_STATE[uid]["action"] = None
        if message.video:
            db.set_mode_sample_video(mode_key, message.video.file_id)
            await message.reply_text(
                "✅ **تم حفظ الفيديو التذكيري لهذا الوضع بنجاح!** سيظهر لك دائماً عند اختيار هذا الوضع.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🎬 عرض الوضع الآن", callback_data=f"setmode_{mode_key}")]])
            )
        else:
            await message.reply_text("⚠️ يرجى إرسال ملف فيديو صالح.")
        return

    # 1. استنساخ نمط جديد مع فحص التكرار الصارم
    if action == "awaiting_style_clone" or message.video:
        USER_STATE[uid]["action"] = None
        wait_msg = await message.reply_text("🔍 **جاري تحليل النمط وفحص قاعدة البيانات للتأكد من عدم وجوده مسبقاً...**")
        style_data = await asyncio.to_thread(sentinel.reverse_engineer_video_style, text or "Viral dynamic cinematic video")

        # فحص إذا قرر الوكيل أنه مكرر
        if style_data.get("is_duplicate"):
            await wait_msg.edit_text(
                f"⛔ **تم رفض الطلب: هذا الوضع موجود لديك مسبقاً!**\n\n"
                f"📌 **الوضع المطابق في نظامك:** `{style_data.get('matched_mode_name', 'وضع حالي')}`\n"
                "لا حاجة لإضافته مرة أخرى، يمكنك استخدامه مباشرة من قائمة الأوضاع.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🎬 فتح قائمة الأوضاع", callback_data="menu_modes_0")]])
            )
            return

        sample_fid = message.video.file_id if message.video else ""
        added_ok, result_mode = db.add_dynamic_mode(
            style_data["mode_id"],
            style_data["arabic_name"],
            style_data["style_prompt"],
            desc=style_data.get("desc", "نمط مستنسخ بالذكاء الاصطناعي"),
            sample_file_id=sample_fid
        )

        if not added_ok:
            await wait_msg.edit_text(
                f"⛔ **تم رفض الإضافة: هذا النمط يتطابق مع وضع موجود لديك مسبقاً!**\n\n"
                f"🏷️ **الوضع الموجود:** `{result_mode['name']}`\n"
                f"🎨 **وصفه:** {result_mode.get('desc', '')}",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🎬 الذهاب للأوضاع", callback_data="menu_modes_0")]])
            )
            return

        USER_STATE[uid]["mode"] = style_data["mode_id"]
        await wait_msg.edit_text(
            f"✅ **تم استنساخ النمط الجديد وإضافته لنظامك للأبد!**\n\n"
            f"🏷️ **اسم الوضع الجديد:** `{result_mode['name']}`\n"
            f"📖 **الوصف:** {result_mode['desc']}\n"
            f"🎨 **الكود البصري المستخرج:**\n`{result_mode['style']}`",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("👁️ معاينة الوضع الجديد", callback_data=f"setmode_{style_data['mode_id']}")]])
        )
        return

    # 2. فحص خبر أو أداة جديدة
    if action == "awaiting_news":
        USER_STATE[uid]["action"] = None
        wait_msg = await message.reply_text("🛰️ **جاري فحص الخبر في HuggingFace و GitHub ومقارنته بما نملكه...**")
        report = await asyncio.to_thread(sentinel.evaluate_user_news, text)

        if report.get("verdict") == "ALREADY_HAVE":
            await wait_msg.edit_text(
                f"⛔ **تقرير مجلس الوكلاء: هذه الميزة/الأداة (`{report.get('tool_name')}`) موجودة في نظامك بالفعل!**\n\n"
                f"📊 **التفاصيل:**\n{report.get('comparison_ar')}\n\n"
                "لذلك تم رفض التكرار للحفاظ على نظافة وكفاءة النظام.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 اللوحة الرئيسية", callback_data="menu_home")]])
            )
            return

        upg_id = f"upg_{int(time.time()) % 100000}"
        db.save_pending_upgrade(upg_id, report)

        verdict_map = {
            "BETTER": "🟢 **إضافة حقيقية وأقوى (ينصح بالترقية)**",
            "FAKE_HYPE": "🔴 **دعاية مبالغ فيها / غير متاح مجاناً (لا ينصح به)**"
        }
        v_text = verdict_map.get(report.get("verdict"), "🟢 **متاح للاختبار**")

        reply = (
            f"🔬 **تقرير مجلس الوكلاء الهندسي حول: `{report.get('tool_name')}`**\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            f"⚖️ **الحكم النهائي:** {v_text}\n\n"
            f"📊 **المقارنة والدراسة:**\n{report.get('comparison_ar')}\n\n"
            f"🔑 **هل يحتاج مفتاح API خارجي؟** `{'نعم' if report.get('requires_api_key') else 'لا (مجاني ومفتوح)'}`\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "هل تريد اختبار هذه الإضافة في البيئة المعزولة (`staging-sandbox`) وتجهيزها للدمج؟"
        )
        buttons = [
            [InlineKeyboardButton("🧪 نعم، اختبرها وطوّر النظام", callback_data=f"sandbox_test_{upg_id}")],
            [InlineKeyboardButton("❌ لا، تجاهلها", callback_data="menu_home")]
        ]
        await wait_msg.edit_text(reply, reply_markup=InlineKeyboardMarkup(buttons))
        return

    # 3. استقبال مفتاح API لترقية معلقة
    if action and action.startswith("awaiting_upgrade_key_"):
        upg_id = action.replace("awaiting_upgrade_key_", "")
        USER_STATE[uid]["action"] = None
        upg = db.get_pending_upgrade(upg_id)
        if upg:
            key_name = upg.get("key_env_name", "CUSTOM_API_KEY")
            db.save_api_key(key_name, text)
            await message.reply_text(
                f"✅ **تم حفظ المفتاح `{key_name}` تلقائياً في قاعدة البيانات!**\n"
                "اضغط الزر أدناه لإكمال الاختبار في البيئة المعزولة:",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🧪 بدء اختبار Sandbox الآن", callback_data=f"sandbox_test_{upg_id}")]])
            )
        return

    # 4. استقبال مفتاح API يدوي
    if action == "awaiting_manual_key":
        USER_STATE[uid]["action"] = None
        if ":" in text:
            k_name, k_val = text.split(":", 1)
            db.save_api_key(k_name.strip(), k_val.strip())
            await message.reply_text(f"✅ **تم حفظ المفتاح `{k_name.strip()}` بنجاح في الذاكرة الدائمة!**")
        else:
            await message.reply_text("⚠️ الصيغة غير صحيحة. أرسله هكذا: `NAME:KEY`")
        return

    # 5. الإنتاج الفعلي حسب الوضع المختار
    mode_key = USER_STATE[uid].get("mode", "hybrid")
    modes = db.get_all_modes()
    m_info = modes.get(mode_key, modes["hybrid"])
    quota_before = db.get_quota_status()

    if quota_before["remaining_pct"] < m_info["cost_pct"]:
        await message.reply_text(
            f"⚠️ **رصيد اليوم ({quota_before['remaining_pct']}%) لا يكفي لهذا الوضع ({m_info['cost_pct']}%).**\n"
            f"⏳ سيتجدد الرصيد بالكامل بعد: `{quota_before['reset_in']}`، أو اختر الوضع السريع/الستيك مان."
        )
        return

    status_msg = await message.reply_text(
        f"🎬 **بدأ مجلس الوكلاء العمل على مشروعك!**\n"
        f"▪️ **الوضع:** `{m_info['name']}`\n"
        f"▪️ **الاستهلاك المقدر:** `{m_info['cost_pct']}%` من الحصة اليومية\n"
        f"▪️ **العقدة النشطة:** `{quota_before['active_node']}`\n"
        "⏳ *جاري تطبيق الدروس السابقة وبناء السيناريو وتوزيع المشاهد...*"
    )

    learned_rules = db.get_relevant_lessons()
    director_prompt = (
        f"أنت المخرج الذكي الشامل. الفكرة: {text}\n"
        f"النمط المطلوب: {m_info['style']}\n"
        f"قواعد التعلم السابقة التي يجب الالتزام بها: {learned_rules}\n"
        "اكتب خطة إنتاج سينمائية مفصلة من 3 مشاهد مع تحديد المحرك لكل مشهد (Hero Shot على Kaggle أو Fast Shot) وبرومبت إنجليزي دقيق."
    )
    plan = await asyncio.to_thread(SmartCouncil.ask, "أنت مخرج سينمائي محترف.", director_prompt, False)
    quota_after = db.consume_quota(m_info["cost_pct"])

    await status_msg.edit_text(
        f"✅ **اكتمل التخطيط والتوجيه الهندسي للمشروع!**\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        f"{plan[:3000]}\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        f"🔋 **الحصة المتبقية لك اليوم:** `{quota_after['remaining_pct']}%` (تتجدد بعد `{quota_after['reset_in']}`)",
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

if __name__ == "__main__":
    print("🚀 Genesis Immortal Engine v5.5 is running...")
    loop = asyncio.get_event_loop()
    loop.create_task(immortal_lifecycle_watchdog())
    app.run()
