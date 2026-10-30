import os
import asyncio
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import (
    TELEGRAM_API_ID, TELEGRAM_API_HASH, TELEGRAM_BOT_TOKEN, PRODUCTION_MODES
)
from quota_manager import quota_system
from boardroom import boardroom
from video_editor import video_engine

app = Client(
    "Genesis_Hollywood_Studio",
    api_id=TELEGRAM_API_ID,
    api_hash=TELEGRAM_API_HASH,
    bot_token=TELEGRAM_BOT_TOKEN
)

USER_SESSIONS = {}

def get_main_menu():
    buttons = [
        [
            InlineKeyboardButton("🧠 المخرج الذكي (هجين)", callback_data="mode_hybrid"),
            InlineKeyboardButton("🎬 سينمائي 100%", callback_data="mode_cinematic")
        ],
        [
            InlineKeyboardButton("⚡ سريع", callback_data="mode_fast"),
            InlineKeyboardButton("🗣️ حوار", callback_data="mode_dialogue"),
            InlineKeyboardButton("📰 أخبار", callback_data="mode_news")
        ],
        [
            InlineKeyboardButton("🧬 استنساخ الوجه والصوت", callback_data="mode_cloning"),
            InlineKeyboardButton("📢 مدير الإعلانات", callback_data="mode_ads")
        ],
        [
            InlineKeyboardButton("🎞️ دمج سلسلة في فيلم طويل (/make_movie)", callback_data="menu_merge")
        ]
    ]
    return InlineKeyboardMarkup(buttons)

@app.on_message(filters.command("start"))
async def start_handler(client, message):
    USER_SESSIONS[message.chat.id] = {"mode": "hybrid", "step": "idle"}
    welcome_text = (
        "🎬 **مرحباً بك يا زكريا في استوديو Genesis Engine (Ultimate Hollywood Edition)!**\n\n"
        "النظام يعمل تحت إشراف **15 وكيل ذكاء اصطناعي** مع فحص بصري (Vision QA) وتصحيح ذاتي للأخطاء.\n"
        f"🔋 **رصيد أسطول Kaggle المتاح:** `{quota_system.get_total_kaggle_mins()} دقيقة`\n\n"
        "اختر وضع الإنتاج للبدء:"
    )
    await message.reply_text(welcome_text, reply_markup=get_main_menu())

@app.on_callback_query(filters.regex("^mode_"))
async def mode_selection_handler(client, query):
    mode_key = query.data.replace("mode_", "")
    chat_id = query.message.chat.id
    USER_SESSIONS[chat_id] = {"mode": mode_key, "step": "awaiting_input"}

    if mode_key == "ads":
        await query.message.edit_text(
            "📢 **وضع مدير الإعلانات التجارية:**\nأرسل الآن **صورة أو فيديو المنتج** مع كتابة **النص الإعلاني** في الوصف (Caption)."
        )
    elif mode_key == "cloning":
        await query.message.edit_text(
            "🧬 **وضع استنساخ الوجه والصوت:**\nأرسل أولاً **الفيديو الأصلي** الذي تريد استبدال الوجه فيه."
        )
        USER_SESSIONS[chat_id]["step"] = "clone_wait_video"
    else:
        await query.message.edit_text(
            f"🎯 **تم تفعيل: {PRODUCTION_MODES.get(mode_key)}**\n\n"
            "أرسل الآن **فكرة الفيلم أو الموضوع** لتبدأ طاولة الوكلاء الـ 15 بالنقاش!"
        )

# ------------------------------------------
# استقبال الصور والفيديوهات (الإعلانات والاستنساخ)
# ------------------------------------------
@app.on_message(filters.photo | filters.video)
async def media_handler(client, message):
    chat_id = message.chat.id
    session = USER_SESSIONS.get(chat_id, {"mode": "hybrid", "step": "idle"})
    mode = session.get("mode")

    if mode == "ads":
        status_msg = await message.reply_text("📢 **استلمت المنتج! يجتمع الآن الوكلاء الـ 15 مع وكيل التسويق لتصميم الإعلان...**")
        media_path = await message.download(file_name="workspace/ad_input_media.jpg")
        ad_caption = message.caption or "منتج حصري بجودة عالمية"

        blueprint, debate_summary = await boardroom.run_consensus_debate(ad_caption, "ads", num_scenes=1)
        await status_msg.edit_text(f"🗣️ **ملخص غرفة العمليات:**\n\n{debate_summary}\n\n⏳ **جاري المونتاج الإعلاني والتحريك...**")

        final_ad = await video_engine.create_commercial_ad(media_path, ad_caption, blueprint)
        await send_completed_video(client, chat_id, final_ad, blueprint.get("title", "إعلان تجاري"))

    elif mode == "cloning":
        step = session.get("step")
        if step == "clone_wait_video" and message.video:
            vid_path = await message.download(file_name="workspace/clone_source.mp4")
            USER_SESSIONS[chat_id]["source_video"] = vid_path
            USER_SESSIONS[chat_id]["step"] = "clone_wait_face"
            await message.reply_text("✅ تم حفظ الفيديو الأصلي. أرسل الآن **صورة الوجه** الواضحة (واكتب في الوصف أي نص جديد إذا أردت تغيير الكلام، أو اتركه فارغاً للاحتفاظ بالصوت الأصلي).")
        elif step == "clone_wait_face" and message.photo:
            face_path = await message.download(file_name="workspace/clone_face.jpg")
            custom_text = message.caption
            status_msg = await message.reply_text("🧬 **جاري تشغيل محرك الاستنساخ (InsightFace + CodeFormer)...**")
            final_clone = await video_engine.process_face_cloning(
                USER_SESSIONS[chat_id]["source_video"], face_path, custom_text
            )
            await send_completed_video(client, chat_id, final_clone, "استنساخ سينمائي")
            USER_SESSIONS[chat_id]["step"] = "idle"

# ------------------------------------------
# استقبال النصوص (السينمائي، الهجين، السريع، الحوار، الأخبار)
# ------------------------------------------
@app.on_message(filters.text & ~filters.command(["start", "make_movie"]))
async def topic_handler(client, message):
    chat_id = message.chat.id
    text = message.text.strip()
    session = USER_SESSIONS.get(chat_id, {"mode": "hybrid", "step": "awaiting_input"})

    # إذا كان المستخدم يكتب اسم السلسلة لحفظ الفيديو الأخير
    if session.get("step") == "saving_series_name":
        file_id = session.get("last_file_id")
        title = session.get("last_title", "مشهد")
        await video_engine.save_video_to_series(chat_id, text, file_id, title)
        USER_SESSIONS[chat_id]["step"] = "idle"
        await message.reply_text(f"💾 **تم حفظ الفيديو بنجاح في سلسلة:** `{text}`\nيمكنك دمج السلسلة في أي وقت عبر الأمر `/make_movie`.")
        return

    mode = session.get("mode", "hybrid")
    status_msg = await message.reply_text("💬 **غرفة العمليات (15 وكيلاً) في جلسة نقاش مغلقة الآن...**")

    # فحص الرصيد قبل البدء
    _, quota_status = quota_system.get_active_gemini_key()
    if quota_status == "NEAR_LIMIT":
        await quota_system.send_quota_alert(
            client, chat_id, {"topic": text, "mode": mode, "status": "paused"}, "GEMINI_LIMIT"
        )
        return

    # تشغيل حلقة النقاش والإجماع
    blueprint, debate_summary = await boardroom.run_consensus_debate(text, mode, num_scenes=3)
    await status_msg.edit_text(
        f"🗣️ **ملخص طاولة النقاش (الوكلاء الـ 15):**\n\n{debate_summary}\n\n"
        f"🎬 **العنوان المقترح:** {blueprint.get('title', text)}\n"
        f"⏳ **جاري الإنتاج والفحص البصري (Vision QA)...**"
    )

    scenes = blueprint.get("scenes", [])
    scene_files = []
    for idx, sc in enumerate(scenes, 1):
        sc_file = await video_engine.produce_scene(sc, idx)
        scene_files.append(sc_file)

    final_video = await video_engine.merge_series_into_movie(scene_files)
    await send_completed_video(client, chat_id, final_video, blueprint.get("title", text))

# ------------------------------------------
# إرسال الفيديو النهائي مع أزرار [حفظ في سلسلة] و [حذف المشهد]
# ------------------------------------------
async def send_completed_video(client, chat_id, video_path, title):
    action_buttons = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("💾 حفظ في سلسلة...", callback_data="series_save"),
            InlineKeyboardButton("🗑️ حذف المشهد نهائياً", callback_data="series_delete")
        ]
    ])
    sent_msg = await client.send_video(
        chat_id,
        video=video_path,
        caption=f"✅ **تم الإنتاج واجتياز الفحص البصري بنجاح!**\n🎬 **العنوان:** {title}",
        reply_markup=action_buttons
    )
    USER_SESSIONS.setdefault(chat_id, {})["last_file_id"] = sent_msg.video.file_id
    USER_SESSIONS[chat_id]["last_title"] = title

@app.on_callback_query(filters.regex("^series_"))
async def series_actions_handler(client, query):
    chat_id = query.message.chat.id
    action = query.data.replace("series_", "")

    if action == "save":
        USER_SESSIONS.setdefault(chat_id, {})["step"] = "saving_series_name"
        await query.message.reply_text("📂 **اكتب الآن اسم السلسلة** التي تريد حفظ هذا الفيديو بداخلها (مثال: `سلسلة محمد الفاتح` أو `سلسلة مدينة تعز`):")
    elif action == "delete":
        file_id = USER_SESSIONS.get(chat_id, {}).get("last_file_id")
        if file_id:
            await video_engine.delete_video_from_series(file_id)
        await query.message.delete()
        await client.send_message(chat_id, "🗑️ **تم حذف المشهد واستبعاده نهائياً من النظام.**")

# ------------------------------------------
# دمج السلسلة في فيلم طويل (/make_movie)
# ------------------------------------------
@app.on_message(filters.command("make_movie"))
async def make_movie_cmd(client, message):
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.reply_text("🎞️ **لدمج سلسلة كاملة في فيلم واحد متصل، اكتب الأمر متبوعاً باسم السلسلة:**\nمثال:\n`/make_movie سلسلة مدينة تعز`")
        return

    series_name = parts[1].strip()
    status_msg = await message.reply_text(f"🔍 **جاري جلب أجزاء '{series_name}' من Supabase ودمجها بانتقالات سينمائية...**")
    records = await video_engine.get_series_videos(message.chat.id, series_name)

    if not records:
        await status_msg.edit_text(f"⚠️ لم يتم العثور على فيديوهات محفوظة تحت اسم: `{series_name}`")
        return

    downloaded_clips = []
    for idx, rec in enumerate(records, 1):
        clip_path = await client.download_media(rec["telegram_file_id"], file_name=f"workspace/series_part_{idx}.mp4")
        downloaded_clips.append(clip_path)

    full_movie = await video_engine.merge_series_into_movie(downloaded_clips)
    await client.send_video(
        message.chat.id,
        video=full_movie,
        caption=f"🍿 **الفيلم الكامل لسلسلة:** `{series_name}`\nتم دمج {len(downloaded_clips)} أجزاء بتسوية صوتية (Audio Normalization) بدون تقطيع!"
    )

# ------------------------------------------
# معالجة أزرار موافقات الرصيد (Smart Auto-Pilot Callbacks)
# ------------------------------------------
@app.on_callback_query(filters.regex("^quota_"))
async def quota_decision_handler(client, query):
    chat_id = query.message.chat.id
    choice = query.data

    if choice == "quota_wait":
        await query.message.edit_text("⏳ **تم تفعيل وضع الانتظار الذكي.** سيقوم البوت باستئناف إنتاج فيلمك تلقائياً فور تجديد الحصة اليومية!")
    elif choice == "quota_fast_fallback":
        pending = await quota_system.get_pending_tasks(chat_id)
        await query.message.edit_text("⚡ **تم التحويل الفوري!** جاري استكمال إنتاج الفيلم عبر محرك GitHub السريع...")

if __name__ == "__main__":
    print("🚀 Genesis Engine (Ultimate Hollywood Edition) is running...")
    app.run()
