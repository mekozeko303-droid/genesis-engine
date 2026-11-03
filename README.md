Genesis Cinema Studio - ملفات الاستبدال

محتويات الحزمة:
1) main.py
2) config.py
3) .github/workflows/genesis.yml

طريقة الاستبدال:
- استبدل main.py و config.py في جذر مستودع GitHub بالملفين الموجودين هنا.
- ضع genesis.yml داخل .github/workflows/ (يمكنك حذف ملف workflow القديم أو استبدال محتواه).
- لا تحذف database.py أو sentinel_evolution.py أو requirements.txt أو بقية ملفات المشروع.
- تأكد أن requirements.txt يتضمن المكتبات التي يستخدمها مشروعك.

GitHub Secrets المطلوبة لأجل اتصال تيليجرام:
- TELEGRAM_API_ID
- TELEGRAM_API_HASH
- TELEGRAM_BOT_TOKEN
- ADMIN_IDS (مطلوب لتحديد المشرفين عند PRIVATE_MODE=1)

مهم جداً:
رسالة Telegram 400 ACCESS_TOKEN_INVALID تعني أن تيليجرام رفض قيمة BOT TOKEN نفسها.
لا يستطيع تعديل main.py أو config.py تحويل الرمز الملغى/الخاطئ إلى رمز صالح.
أنشئ رمزاً جديداً من @BotFather ثم افتح GitHub > Settings > Secrets and variables > Actions
واستبدل قيمة TELEGRAM_BOT_TOKEN بالرمز الجديد. لا تضع الرمز داخل أي ملف ولا ترسله في المحادثة.

اسم السر المستخدم في workflow هو TELEGRAM_BOT_TOKEN وهو متوافق مع config.py.
