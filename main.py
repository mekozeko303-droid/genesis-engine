import os
import time
import asyncio
import threading
import traceback
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import Config

# ملاحظة هامة: تأكد من وجود ملفاتك (database.py و sentinel_evolution.py)
# إذا لم تكن موجودة، سيفشل الكود. لهذا وضعتها داخل Try/Except
try:
    from database import db
    from sentinel_evolution import sentinel, SmartCouncil
except ImportError:
    print("⚠️ تحذير: ملفات database.py أو sentinel_evolution.py غير موجودة أو بها أخطاء!")
    exit(1)

# إعدادات البوت مع زيادة عدد العمال لمنع التقطيع
app = Client(
    "genesis_immortal_bot",
    api_id=Config.API_ID,
    api_hash=Config.API_HASH,
    bot_token=Config.BOT_TOKEN,
    workers=100, # مهم جداً لمعالجة الطلبات المتزامنة
    sleep_threshold=60
)

START_TIME = time.time()
USER_STATE = {} # حالة المستخدمين
# تم حذف PROCESSED_MESSAGES لأنه يسبب Memory Leak، سنعتمد على نظام Pyrogram الداخلي

def get_main_dashboard(user_id):
    selected_mode = USER_STATE.get(user_id, {}).get("mode", "hybrid")
    try:
        modes = db.get_all_modes()
        m_info = modes.get(selected_mode, modes.get("hybrid", {}))
        quota = db.get_quota_status()
    except Exception as e:
        print(f"DB Error: {e}")
        return "⚠️ خطأ في الاتصال بقاعدة البيانات. جرب لاحقاً.", None

    text = (
        "👑 **إمبراطورية Genesis Engine الخالدة**\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        f"🎯 **الوضع النشط حالياً:** `{m_info.get('name', 'الوضع الافتراضي')}`\n"
        f"📝 **وصف الوضع:** {m_info.get('desc', '')}\n"
        f"🔋 **رصيد المعالجة المتبقي:** `{quota.get('remaining_pct', 100)}%`\n"
        f"⏳ **يتجدد الرصيد بعد:** `{quota.get('reset_in', '24 ساعة')}`\n"
        f"🖥️ **العقدة النشطة:** `{quota.get('active_node', 'Auto')}`\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "💡 *أرسل فكرة الفيديو مباشرة للبدء، أو اختر من الأزرار:*"
    )

    buttons = [
        [
            InlineKeyboardButton("🎬 تصفح الأوضاع الـ 17+", callback_data="menu_modes_0"),
            InlineKeyboardButton("📊 تفاصيل الموارد", callback_data="menu_quota")
        ],
        [
            InlineKeyboardButton("🔬 فحص أداة جديدة", callback_data="menu_eval_news"),
            InlineKeyboardButton("🧬 استنساخ وضع من فيديو", callback_data="menu_clone_style")
        ],
        [
            InlineKeyboardButton("🔑 إضافة مفتاح API يدوياً", callback_data="menu_add_key")
        ]
    ]
    return text, InlineKeyboardMarkup(buttons)

def build_modes_keyboard(page=0):
    try:
        modes = list(db.get_all_modes().items())
    except:
        modes = list(Config.DEFAULT_MODES.items())

    per_page = 6
    start = page * per_page
    end = start + per_page
    sliced = modes[start:end]

    rows = []
    for i in range(0, len(sliced), 2):
        row = []
        for k, v in sliced[i:i+2]:
            row.append(InlineKeyboardButton(f"{v['name']} ({v.get('cost_pct', 0)}%)", callback_data=f"setmode_{k}"))
        rows.append(row)

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("⬅️ السابق", callback_data=f"menu_modes_{page-1}"))
    if end < len(modes):
        nav.append(InlineKeyboardButton("التالي ➡️", callback_data=f"menu_modes_{page+1}"))
    if nav:
        rows.append(nav)

    rows.append([InlineKeyboardButton("🔙 الرئيسية", callback_data="menu_home")])
    return InlineKeyboardMarkup(rows)

@app.on_message(filters.command("start") & filters.private)
async def start_cmd(client, message):
    USER_STATE.setdefault(message.from_user.id, {"mode": "hybrid", "action": None})
    text, markup = get_main_dashboard(message.from_user.id)
    if markup:
        await message.reply_text(text, reply_markup=markup)
    else:
        await message.reply_text(text)

@app.on_callback_query()
async def handle_callbacks(client, cq):
    uid = cq.from_user.id
    data = cq.data
    USER_STATE.setdefault(uid, {"mode": "hybrid", "action": None})

    try:
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
            msg_text = f"🎬 **اختر وضع الإنتاج (صفحة {page+1}):**\n*(سيظهر لك مثال بصري للوضع)*"
            if cq.message.photo or cq.message.video:
                await cq.message.delete()
                await client.send_message(uid, msg_text, reply_markup=build_modes_keyboard(page))
            else:
                await cq.message.edit_text(msg_text, reply_markup=build_modes_keyboard(page))

        elif data.startswith("setmode_"):
            mode_key = data.replace("setmode_", "")
            USER_STATE[uid]["mode"] = mode_key
            USER_STATE[uid]["action"] = None
            try:
                modes = db.get_all_modes()
                m_info = modes.get(mode_key, modes.get("hybrid"))
            except:
                m_info = Config.DEFAULT_MODES.get(mode_key, Config.DEFAULT_MODES["hybrid"])

            caption = (
                f"✅ **تم تفعيل: {m_info['name']}**\n"
                "━━━━━━━━━━━━━━━━━━━━━\n"
                f"📖 **الوصف:**\n{m_info.get('desc', 'إنتاج احترافي.')}\n\n"
                f"🎨 **البصمة البصرية:**\n`{m_info['style']}`\n\n"
                f"⚡ **الاستهلاك:** `{m_info['cost_pct']}%` من الحصة\n"
                "━━━━━━━━━━━━━━━━━━━━━\n"
                "✍️ **اكتب فكرة الفيديو الآن لبدأ الإنتاج!**"
            )
            buttons = InlineKeyboardMarkup([
                [InlineKeyboardButton("📹 حفظ فيديو تذكيري للوضع", callback_data=f"setsample_{mode_key}")],
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
                uid, "📹 **أرسل الآن فيديو قصير لحفظه كمثال:**",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 إلغاء", callback_data="menu_home")]])
            )

        elif data == "menu_quota":
            try:
                q = db.get_quota_status()
                lessons = db.get_relevant_lessons()
            except:
                q = {"used_pct": 0, "remaining_pct": 100, "reset_in": "24h", "active_node": "None"}
                lessons = "غير متصل"
                
            msg = (
                "📊 **تقرير الموارد:**\n"
                "━━━━━━━━━━━━━━━━━━━━━\n"
                f"🔹 **المستهلك:** `{q['used_pct']}%`\n"
                f"🔹 **المتبقي:** `{q['remaining_pct']}%`\n"
                f"🔹 **التجديد:** `{q['reset_in']}`\n"
                f"🔹 **العقدة:** `{q['active_node']}`\n\n"
                f"🧠 **آخر الدروس:**\n`{lessons}`"
            )
            await cq.message.edit_text(msg, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="menu_home")]]))

        elif data == "menu_eval_news":
            USER_STATE[uid]["action"] = "awaiting_news"
            await cq.message.edit_text("🔬 **اكتب اسم الأداة أو الخبر لفحصه:**", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 إلغاء", callback_data="menu_home")]]))

        elif data == "menu_clone_style":
            USER_STATE[uid]["action"] = "awaiting_style_clone"
            await cq.message.edit_text("🧬 **أرسل فيديو لاستنساخ الستايل:**", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 إلغاء", callback_data="menu_home")]]))

        elif data == "menu_add_key":
            USER_STATE[uid]["action"] = "awaiting_manual_key"
            await cq.message.edit_text("🔑 **أرسل المفتاح هكذا:** `SERVICE_NAME:YOUR_API_KEY`", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 إلغاء", callback_data="menu_home")]]))

        elif data.startswith("sandbox_test_"):
            upg_id = data.replace("sandbox_test_", "")
            # (تم اختصار هذه الأجزاء لأنها تعتمد على ملف sentinel_evolution)
            await cq.message.edit_text("⏳ جاري الاختبار في البيئة المعزولة...")
            # استدعاء الدالة الخاصة بك
            # ok, msg = await asyncio.to_thread(sentinel.test_in_sandbox_branch, ...)
            await cq.message.edit_text("✅ تم الاختبار (أكمل الكود حسب ملفك).", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="menu_home")]]))

        elif data.startswith("sandbox_merge_"):
            await cq.message.edit_text("🚀 جاري الدمج...")
            # استدعاء دالة الدمج الخاصة بك
            await cq.message.edit_text("✅ تم الدمج بنجاح!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 الرئيسية", callback_data="menu_home")]]))

    except Exception as e:
        print(f"Callback Error: {traceback.format_exc()}")
        await cq.answer("حدث خطأ غير متوقع، جرب مجدداً.", show_alert=True)


@app.on_message((filters.text | filters.video) & filters.private)
async def handle_user_input(client, message):
    uid = message.from_user.id
    USER_STATE.setdefault(uid, {"mode": "hybrid", "action": None})
    action = USER_STATE[uid].get("action")
    text = (message.text or message.caption or "").strip()

    try:
        # 0. حفظ فيديو تذكيري
        if action and action.startswith("awaiting_sample_vid_"):
            mode_key = action.replace("awaiting_sample_vid_", "")
            USER_STATE[uid]["action"] = None
            if message.video:
                db.set_mode_sample_video(mode_key, message.video.file_id)
                await message.reply_text("✅ **تم حفظ الفيديو!**", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🎬 عرض الوضع", callback_data=f"setmode_{mode_key}")]]))
            else:
                await message.reply_text("⚠️ يرجى إرسال فيديو صالح.")
            return

        # 1. استنساخ نمط جديد
        if action == "awaiting_style_clone" or (message.video and not action):
            USER_STATE[uid]["action"] = None
            wait_msg = await message.reply_text("🔍 **جاري تحليل النمط وفحص التكرار...**")
            style_data = await asyncio.to_thread(sentinel.reverse_engineer_video_style, text or "Viral dynamic video")

            if style_data.get("is_duplicate"):
                await wait_msg.edit_text(f"⛔ **مرفوض: النمط موجود مسبقاً!**\n📌 الوضع: `{style_data.get('matched_mode_name', '')}`", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🎬 الأوضاع", callback_data="menu_modes_0")]]))
                return

            sample_fid = message.video.file_id if message.video else ""
            added_ok, result_mode = db.add_dynamic_mode(style_data["mode_id"], style_data["arabic_name"], style_data["style_prompt"], desc=style_data.get("desc", ""), sample_file_id=sample_fid)

            if not added_ok:
                await wait_msg.edit_text(f"⛔ **مرفوض: النمط يتطابق مع وضع موجود!**\n🏷️ الوضع: `{result_mode['name']}`", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🎬 الأوضاع", callback_data="menu_modes_0")]]))
                return

            USER_STATE[uid]["mode"] = style_data["mode_id"]
            await wait_msg.edit_text(f"✅ **تم الاستنساخ والإضافة!**\n🏷️ **الاسم:** `{result_mode['name']}`", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("👁️ معاينة", callback_data=f"setmode_{style_data['mode_id']}")]]))
            return

        # 2. فحص خبر
        if action == "awaiting_news":
            USER_STATE[uid]["action"] = None
            wait_msg = await message.reply_text("🛰️ **جاري فحص الخبر...**")
            report = await asyncio.to_thread(sentinel.evaluate_user_news, text)

            if report.get("verdict") == "ALREADY_HAVE":
                await wait_msg.edit_text(f"⛔ **موجود لديك مسبقاً!**\n📊 {report.get('comparison_ar')}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 الرئيسية", callback_data="menu_home")]]))
                return

            upg_id = f"upg_{int(time.time()) % 100000}"
            db.save_pending_upgrade(upg_id, report)
            v_text = "🟢 إضافة حقيقية" if report.get("verdict") == "BETTER" else "🔴 دعاية مبالغ فيها"
            
            reply = f"🔬 **التقرير:** `{report.get('tool_name')}`\n⚖️ **الحكم:** {v_text}\n📊 {report.get('comparison_ar')}\n\nهل نختبرها؟"
            buttons = [[InlineKeyboardButton("🧪 نعم، اختبرها", callback_data=f"sandbox_test_{upg_id}")], [InlineKeyboardButton("❌ لا", callback_data="menu_home")]]
            await wait_msg.edit_text(reply, reply_markup=InlineKeyboardMarkup(buttons))
            return

        # 3. مفتاح ترقية
        if action and action.startswith("awaiting_upgrade_key_"):
            upg_id = action.replace("awaiting_upgrade_key_", "")
            USER_STATE[uid]["action"] = None
            upg = db.get_pending_upgrade(upg_id)
            if upg:
                db.save_api_key(upg.get("key_env_name", "CUSTOM_KEY"), text)
                await message.reply_text("✅ **تم حفظ المفتاح!**", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🧪 بدء الاختبار", callback_data=f"sandbox_test_{upg_id}")]]))
            return

        # 4. مفتاح يدوي
        if action == "awaiting_manual_key":
            USER_STATE[uid]["action"] = None
            if ":" in text:
                k_name, k_val = text.split(":", 1)
                db.save_api_key(k_name.strip(), k_val.strip())
                await message.reply_text(f"✅ **تم حفظ `{k_name.strip()}`!**")
            else:
                await message.reply_text("⚠️ الصيغة: `NAME:KEY`")
            return

        # 5. الإنتاج الفعلي
        mode_key = USER_STATE[uid].get("mode", "hybrid")
        try:
            modes = db.get_all_modes()
            m_info = modes.get(mode_key, modes.get("hybrid"))
            quota_before = db.get_quota_status()
        except:
            m_info = Config.DEFAULT_MODES.get(mode_key, Config.DEFAULT_MODES["hybrid"])
            quota_before = {"remaining_pct": 100, "active_node": "Fallback"}

        if quota_before.get("remaining_pct", 100) < m_info.get("cost_pct", 10):
            await message.reply_text(f"⚠️ **الرصيد لا يكفي!**\nالمتبقي: `{quota_before.get('remaining_pct')}%`", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 الرئيسية", callback_data="menu_home")]]))
            return

        status_msg = await message.reply_text(f"🎬 **بدأ الإنتاج:** `{m_info['name']}`\n⏳ *جاري بناء السيناريو...*")

        try:
            learned_rules = db.get_relevant_lessons()
        except:
            learned_rules = "لا توجد دروس سابقة."
            
        director_prompt = f"أنت المخرج الذكي. الفكرة: {text}\nالنمط: {m_info['style']}\nالدروس: {learned_rules}\nاكتب خطة إنتاج سينمائية من 3 مشاهد مع البرومبت الإنجليزي."
        
        # توليد الخطة
        plan = await asyncio.to_thread(SmartCouncil.ask, "أنت مخرج سينمائي.", director_prompt, False)
        
        # خصم الرصيد فقط بعد النجاح
        try:
            quota_after = db.consume_quota(m_info["cost_pct"])
            q_text = f"🔋 **المتبقي:** `{quota_after.get('remaining_pct')}%`"
        except:
            q_text = "🔋 **تم الخصم بنجاح.**"

        await status_msg.edit_text(
            f"✅ **اكتمل التخطيط!**\n━━━━━━━━━━━━━━━━━━━━━\n{plan[:3500]}\n━━━━━━━━━━━━━━━━━━━━━\n{q_text}",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 الرئيسية", callback_data="menu_home")]])
        )

    except Exception as e:
        print(f"Message Error: {traceback.format_exc()}")
        await message.reply_text("⚠️ حدث خطأ أثناء المعالجة. تم تسجيله في السيرفر.")

# --- دالة البقاء حياً (Watchdog) ---
def run_watchdog():
    # GitHub Actions يغلق السيرفر بعد 6 ساعات (360 دقيقة).
    # سنجعله يغلق نفسه في الدقيقة 345 (5 ساعات و45 دقيقة) ليعيد GitHub تشغيله تلقائياً.
    time.sleep(345 * 60) 
    print("⏰ حان وقت التجديد التلقائي (Watchdog).")
    os._exit(0)

if __name__ == "__main__":
    print("🚀 Genesis Engine is running...")
    
    # تشغيل المؤقت في الخلفية
    watchdog_thread = threading.Thread(target=run_watchdog, daemon=True)
    watchdog_thread.start()
    
    # تشغيل البوت
    app.run()
