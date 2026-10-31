import os
import asyncio

try:
    asyncio.get_event_loop()
except RuntimeError:
    asyncio.set_event_loop(asyncio.new_event_loop())

from pyrogram import Client, filters
from pyrogram.types import (
    ReplyKeyboardMarkup,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)
import config
from quota_manager import quota_system
from boardroom import boardroom
from media_engine import media_engine, SUPPORTED_LANGUAGES

TELEGRAM_API_ID = getattr(config, "TELEGRAM_API_ID", 31270154)
TELEGRAM_API_HASH = getattr(config, "TELEGRAM_API_HASH", "")
TELEGRAM_BOT_TOKEN = getattr(config, "TELEGRAM_BOT_TOKEN", "")
AUTHORIZED_USERS = getattr(config, "AUTHORIZED_USERS", [])

DEFAULT_MODES = {
    "cinematic": "🎬 سينمائي 100% (هوليوود واقعي)",
    "hybrid": "🧠 المخرج الذكي (هجين ديناميكي)",
    "kids": "👶 كرتون وأنيميشن 3D (Pixar)",
    "story": "📸 ستوري وريلز صوري (بدون تشويه)",
    "dialogue": "🗣️ حوار تمثيلي (رجل وامرأة)",
    "news": "📰 استوديو الأخبار والوثائقيات",
    "fast": "⚡ الوضع السريع (إنتاج خاطف)",
    "ads": "📢 مدير الإعلانات التجارية",
    "cloning": "🧬 استنساخ الوجه والصوت"
}
PRODUCTION_MODES = {**DEFAULT_MODES, **getattr(config, "PRODUCTION_MODES", {})}

app = Client(
    "genesis_studio_bot",
    api_id=TELEGRAM_API_ID,
    api_hash=TELEGRAM_API_HASH,
    bot_token=TELEGRAM_BOT_TOKEN,
    in_memory=True
)

user_sessions = {}


def get_session(chat_id):
    if chat_id not in user_sessions:
        user_sessions[chat_id] = {
            "mode": "hybrid",
            "lang": "ar",
            "scenes": 5,
            "story_photos": [],
            "story_audio": None,
            "clone_face": None,
            "clone_video": None,
            "produced_videos": []
        }
    return user_sessions[chat_id]


def get_main_keyboard():
    return ReplyKeyboardMarkup(
        [
            ["🎬 سينمائي 100%", "🧠 المخرج الذكي (هجين)"],
            ["👶 كرتون وأنيميشن 3D", "📸 ستوري وريلز صوري"],
            ["🗣️ حوار تمثيلي", "📢 مدير الإعلانات", "📰 أخبار"],
            ["🧬 استنساخ الوجه والصوت", "⚡ سريع"],
            ["🌐 اللغة والصوت البشري", "💡 فحص ترقيات النظام"],
            ["🎞️ دمج سلسلة في فيلم طويل (/make_movie)"]
        ],
        resize_keyboard=True
    )


@app.on_message(filters.command("start"))
async def start_handler(client, message):
    chat_id = message.chat.id
    if AUTHORIZED_USERS and chat_id not in AUTHORIZED_USERS:
        await message.reply_text("🔒 عذراً، هذا الاستوديو خاص ومغلق للمالك فقط.")
        return

    sess = get_session(chat_id)
    kaggle_mins = quota_system.get_total_kaggle_mins()
    lang_name = SUPPORTED_LANGUAGES.get(sess["lang"], SUPPORTED_LANGUAGES["ar"])["name"]
    mode_name = PRODUCTION_MODES.get(sess["mode"], sess["mode"])

    welcome = (
        f"🎬 **مرحباً بك يا زكريا في استوديو Genesis Engine (الإصدار الخارق v{boardroom.upgrade_level}.0)!**\n\n"
        f"🤖 **مجلس الإدارة:** يعمل الآن بـ **20 وكيل ذكاء اصطناعي** مع حارس منع الشاشة السوداء ومحرك الصور الفوري `FLUX.1-Schnell`.\n"
        f"🎛️ **الوضع الحالي:** `{mode_name}`\n"
        f"🌐 **اللغة والصوت البشري:** `{lang_name}`\n"
        f"🔋 **رصيد أسطول Kaggle المتاح:** `{kaggle_mins}` دقيقة\n\n"
        f"👇 **اختر وضع الإنتاج أو أرسل فكرتك مباشرة للبدء:**"
    )
    await message.reply_text(welcome, reply_markup=get_main_keyboard())


@app.on_callback_query()
async def callback_handler(client, query):
    chat_id = query.message.chat.id
    sess = get_session(chat_id)
    data = query.data

    if data.startswith("setlang_"):
        lang_code = data.replace("setlang_", "")
        if lang_code in SUPPORTED_LANGUAGES:
            sess["lang"] = lang_code
            lang_info = SUPPORTED_LANGUAGES[lang_code]
            await query.message.edit_text(
                f"✅ **تم تفعيل اللغة والصوت البشري بنجاح!**\n"
                f"• **اللغة:** {lang_info['name']}\n"
                f"• **الحنجرة العصبية:** `{lang_info['male_voice']}`\n\n"
                f"أرسل الآن فكرة الفيديو ليتم إنتاجه بهذه اللغة!"
            )
    elif data == "activate_upgrade":
        msg_txt = boardroom.activate_supreme_upgrade()
        media_engine.upgrade_active = True
        await query.message.edit_text(msg_txt)
    elif data == "start_story_render":
        if not sess["story_photos"]:
            await query.answer("أرسل صورة واحدة على الأقل أولاً!", show_alert=True)
            return
        await query.message.edit_text("⏳ **الوكيل 16 (مخرج الستوري):** جاري تصميم ومونتاج الستوري الاحترافي من صورك الشخصية (بدون أي تشويه)...")
        out_vid = await media_engine.produce_personal_story_reel(
            photo_paths=sess["story_photos"],
            caption_text="",
            custom_audio_path=sess["story_audio"],
            lang_code=sess["lang"]
        )
        if out_vid and os.path.exists(out_vid):
            await client.send_video(
                chat_id,
                out_vid,
                caption="📸 **تم إنتاج الستوري/الريلز الاحترافي من صورك بنجاح!**"
            )
            sess["produced_videos"].append(out_vid)
            sess["story_photos"] = []
            sess["story_audio"] = None
        else:
            await query.message.edit_text("⚠️ حدث خطأ أثناء دمج الصور، تأكد من إرسال صور صالحة.")


@app.on_message(filters.photo | filters.video | filters.voice | filters.audio)
async def media_upload_handler(client, message):
    chat_id = message.chat.id
    sess = get_session(chat_id)
    os.makedirs("workspace", exist_ok=True)

    if sess["mode"] == "story":
        if message.photo:
            p_path = await message.download(file_name=f"workspace/user_story_{chat_id}_{len(sess['story_photos'])+1}.jpg")
            sess["story_photos"].append(p_path)
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton(f"🚀 ابدأ مونتاج الستوري الآن ({len(sess['story_photos'])} صور)", callback_data="start_story_render")]
            ])
            await message.reply_text(
                f"📸 **تم استلام الصورة رقم ({len(sess['story_photos'])}) بنجاح!**\n"
                f"• يمكنك إرسال المزيد من الصور، أو إرسال مقطع صوتي بصوتك، أو كتابة نص للستوري، أو الضغط على الزر أدناه للبدء فوراً:",
                reply_markup=kb
            )
            return
        elif message.voice or message.audio:
            a_path = await message.download(file_name=f"workspace/user_voice_{chat_id}.mp3")
            sess["story_audio"] = a_path
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("🚀 ابدأ مونتاج الستوري بصوتي الآن", callback_data="start_story_render")]
            ])
            await message.reply_text("🎙️ **تم حفظ صوتك الشخصي للستوري!** اضغط الزر أدناه لدمجه مع صورك:", reply_markup=kb)
            return

    if message.photo:
        f_path = await message.download(file_name=f"workspace/user_face_{chat_id}.jpg")
        sess["clone_face"] = f_path
        sess["story_photos"].append(f_path)
        await message.reply_text(
            "🧬 **تم حفظ صورتك الشخصية بنجاح!**\n\n"
            "• **خيار 1:** أرسل الآن فيديو ليتم دمج صورتك وصوتك عليه.\n"
            "• **خيار 2:** اكتب فكرة فيلم مباشرة وسيدمج الوكلاء صورتك داخل المشاهد السينمائية!\n"
            "• **خيار 3:** إذا أردت تحويلها إلى ستوري احترافي اضغط زر `📸 ستوري وريلز صوري`."
        )
        return

    if message.video:
        v_path = await message.download(file_name=f"workspace/user_vid_{chat_id}.mp4")
        sess["clone_video"] = v_path
        if sess["clone_face"] and os.path.exists(sess["clone_face"]):
            wait_msg = await message.reply_text("🧬 **الوكيل 13 و17:** جاري معالجة الفيديو ودمج صورتك وهندسة الألوان والصوت...")
            cloned_out = await media_engine.process_face_cloning_video(
                face_path=sess["clone_face"],
                video_path=v_path,
                custom_caption=message.caption or ""
            )
            await client.send_video(chat_id, cloned_out, caption="🧬 **تم إنتاج فيديو الاستنساخ المدمج بنجاح!**")
            await wait_msg.delete()
        else:
            await message.reply_text("📹 تم استلام الفيديو! أرسل الآن **صورتك الشخصية** ليتم دمجها عليه.")


@app.on_message(filters.text)
async def text_handler(client, message):
    chat_id = message.chat.id
    text = message.text.strip()
    sess = get_session(chat_id)

    mode_buttons = {
        "🎬 سينمائي 100%": "cinematic",
        "🧠 المخرج الذكي (هجين)": "hybrid",
        "👶 كرتون وأنيميشن 3D": "kids",
        "📸 ستوري وريلز صوري": "story",
        "🗣️ حوار تمثيلي": "dialogue",
        "📢 مدير الإعلانات": "ads",
        "📰 أخبار": "news",
        "🧬 استنساخ الوجه والصوت": "cloning",
        "⚡ سريع": "fast"
    }

    if text in mode_buttons:
        sess["mode"] = mode_buttons[text]
        if sess["mode"] == "story":
            sess["story_photos"] = []
            sess["story_audio"] = None
            await message.reply_text(
                "📸 **تم تفعيل: استوديو الستوري والريلز الشخصي (9:16)!**\n\n"
                "1️⃣ أرسل الآن **صورك الشخصية** أو صور منتجاتك (صورة واحدة أو عدة صور).\n"
                "2️⃣ (اختياري) أرسل بصمة صوتية بصوتك أو اكتب جملة ليقرأها المعلق.\n"
                "3️⃣ سيقوم النظام بإنتاج ستوري احترافي بحركة كاميرا وفلاتر ألوان **دون تغيير أو تشويه ملامح صورك أبداً!**"
            )
        elif sess["mode"] == "cloning":
            await message.reply_text(
                "🧬 **تم تفعيل: استنساخ الوجه والصوت!**\n\n"
                "• أرسل **صورتك الشخصية** ثم أرسل **الفيديو** (أو اكتب فكرة سيناريو) ليقوم الوكيل 13 و17 بدمج صورتك وإنتاج الفيديو!"
            )
        else:
            await message.reply_text(
                f"🎯 **تم تفعيل وضع:** `{PRODUCTION_MODES.get(sess['mode'], sess['mode'])}`\n"
                f"🌐 **اللغة الحالية:** `{SUPPORTED_LANGUAGES.get(sess['lang'], SUPPORTED_LANGUAGES['ar'])['name']}`\n\n"
                f"أرسل الآن فكرة الفيلم (ويمكنك تحديد عدد المشاهد مثل: *5 مشاهد عن...*) لتبدأ طاولة الـ 20 وكيلاً!"
            )
        return

    if text == "🌐 اللغة والصوت البشري":
        buttons = []
        for code, info in SUPPORTED_LANGUAGES.items():
            buttons.append([InlineKeyboardButton(info["name"], callback_data=f"setlang_{code}")])
        await message.reply_text(
            "🌐 **اختر لغة الفيديو والحنجرة البشرية (Neural Human Voice):**",
            reply_markup=InlineKeyboardMarkup(buttons)
        )
        return

    if text == "💡 فحص ترقيات النظام":
        wait_u = await message.reply_text("🔍 **يقوم الوكلاء الـ 20 الآن بمسح ودراسة أحدث الترقيات المجانية المتاحة...**")
        report = await boardroom.run_upgrade_research()
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ نعم، فعّل الترقية الخارقة فوراً!", callback_data="activate_upgrade")]
        ])
        await wait_u.edit_text(report, reply_markup=kb)
        return

    if "/make_movie" in text or "دمج سلسلة" in text:
        if len(sess["produced_videos"]) < 2:
            await message.reply_text("🎞️ يجب أن تنتج مقطعين على الأقل في هذه الجلسة ليتم دمجهما في فيلم طويل!")
            return
        wait_m = await message.reply_text("🎞️ **جاري دمج جميع المقاطع المنتجة في فيلم سينمائي طويل واحد...**")
        list_p = f"workspace/movie_list_{chat_id}.txt"
        out_movie = f"workspace/full_movie_{chat_id}.mp4"
        with open(list_p, "w", encoding="utf-8") as f:
            for v in sess["produced_videos"]:
                if os.path.exists(v):
                    f.write(f"file '{os.path.abspath(v)}'\n")
        media_engine._run_ffmpeg(f'ffmpeg -y -f concat -safe 0 -i "{list_p}" -c copy "{out_movie}"')
        if os.path.exists(out_movie):
            await client.send_video(chat_id, out_movie, caption="🎬 **الفيلم السينمائي الطويل المدمج جاهز!**")
            await wait_m.delete()
        return

    if sess["mode"] == "story" and sess["story_photos"]:
        wait_s = await message.reply_text("📸 **جاري مونتاج صورك الشخصية مع التعليق الصوتي والموسيقى...**")
        out_vid = await media_engine.produce_personal_story_reel(
            photo_paths=sess["story_photos"],
            caption_text=text,
            custom_audio_path=sess["story_audio"],
            lang_code=sess["lang"]
        )
        if out_vid and os.path.exists(out_vid):
            await client.send_video(chat_id, out_vid, caption=f"📸 **ستوري احترافي:** {text[:60]}")
            sess["produced_videos"].append(out_vid)
            sess["story_photos"] = []
            sess["story_audio"] = None
            await wait_s.delete()
            return

    status_msg = await message.reply_text("💬 **غرفة العمليات (20 وكيلاً) تصيغ السيناريو وتولد اللوحات البصرية الآن...**")

    blueprint, debate_log = await boardroom.run_consensus_debate(
        topic=text,
        mode=sess["mode"],
        num_scenes=sess["scenes"],
        lang_code=sess["lang"]
    )

    await status_msg.edit_text(f"{debate_log}\n\n⏳ **جاري الآن توليد الصور الحقيقية (FLUX HD) والتمثيل الصوتي البشري...**")

    async def update_progress(prog_txt):
        try:
            await status_msg.edit_text(f"{debate_log}\n\n{prog_txt}")
        except Exception:
            pass

    custom_face = sess["clone_face"] if sess["mode"] == "cloning" else None
    final_video = await media_engine.produce_full_video(
        blueprint,
        status_callback=update_progress,
        custom_face_path=custom_face
    )

    if final_video and os.path.exists(final_video):
        sess["produced_videos"].append(final_video)
        caption = (
            f"🎬 **{blueprint.get('title', text[:50])}**\n"
            f"• **الوضع:** `{PRODUCTION_MODES.get(blueprint.get('mode'), sess['mode'])}`\n"
            f"• **اللغة:** `{SUPPORTED_LANGUAGES.get(blueprint.get('language', 'ar'), SUPPORTED_LANGUAGES['ar'])['name']}`\n"
            f"• **إشراف:** مجلس الـ 20 وكيلاً (v{boardroom.upgrade_level}.0)"
        )
        await client.send_video(chat_id, final_video, caption=caption)
        await status_msg.delete()
    else:
        await status_msg.edit_text("⚠️ تعذر إنتاج الفيديو، يرجى المحاولة مرة أخرى.")


if __name__ == "__main__":
    print("🚀 Genesis Studio Engine v20-Agents is running...")
    app.run()
