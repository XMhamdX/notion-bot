# استيراد المكتبات اللازمة
import os  # للتعامل مع متغيرات البيئة ونظام التشغيل
import logging  # لتسجيل الأحداث والأخطاء
import sys  # للتعامل مع النظام
from dotenv import load_dotenv  # لتحميل المتغيرات البيئية من ملف .env
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup  # مكونات واجهة تيليجرام
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes  # معالجات تيليجرام
from notion_client import Client  # مكتبة للتعامل مع Notion API
import json  # للتعامل مع بيانات JSON

# إعداد التسجيل (Logging)
logging.basicConfig(
    level=logging.INFO,  # مستوى التسجيل: معلومات
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',  # تنسيق رسائل التسجيل
    handlers=[
        logging.StreamHandler(sys.stdout)  # عرض السجلات في الطرفية
    ]
)
logger = logging.getLogger(__name__)  # إنشاء مسجل خاص بهذا الملف

# تحميل المتغيرات البيئية من ملف .env
logger.info("جاري تحميل المتغيرات البيئية...")
load_dotenv()

# تهيئة عميل Notion
token = os.getenv("NOTION_TOKEN")  # الحصول على توكن Notion من المتغيرات البيئية
logger.info(f"Notion token: {token[:4]}...{token[-4:]}")  # طباعة جزء من التوكن للتأكد من تحميله
notion = Client(auth=token)  # إنشاء عميل Notion

# تخزين اختيارات المستخدمين للصفحات
# user_id -> [page_id1, page_id2, ...]
user_pages = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    معالج أمر /start
    يقوم بعرض قائمة الصفحات المتاحة في Notion للمستخدم
    
    المعاملات:
        update (Update): تحديث من تيليجرام يحتوي على معلومات الرسالة والمستخدم
        context (ContextTypes.DEFAULT_TYPE): سياق المحادثة
    """
    try:
        logger.info("بدء البحث عن الصفحات في Notion...")
        
        # البحث عن جميع الصفحات في Notion
        # ترتيب النتائج حسب آخر تعديل
        response = notion.search(
            query="",  # بحث بدون كلمات مفتاحية
            sort={
                "direction": "ascending",  # ترتيب تصاعدي
                "timestamp": "last_edited_time"  # حسب وقت آخر تعديل
            }
        )
        
        # استخراج الصفحات من النتيجة
        pages = response.get("results", [])
        logger.info(f"تم العثور على {len(pages)} صفحة")
        
        # طباعة معلومات كل صفحة في السجلات للتشخيص
        for page in pages:
            logger.info(f"معلومات الصفحة: {page.get('id')} - {page.get('url')} - {page.get('object')}")
        
        # إنشاء لوحة مفاتيح تفاعلية مع أزرار للصفحات
        keyboard = []
        for page in pages:
            try:
                # تجاهل أي شيء ليس صفحة (مثل قواعد البيانات)
                if page.get("object") != "page":
                    continue
                    
                # الحصول على معلومات تفصيلية عن الصفحة
                page_info = notion.pages.retrieve(page_id=page["id"])
                logger.info(f"معلومات تفصيلية للصفحة: {page_info}")
                
                # محاولة الحصول على عنوان الصفحة
                page_title = None
                
                # البحث عن العنوان في خصائص الصفحة
                if "properties" in page_info:
                    for prop_name, prop_value in page_info["properties"].items():
                        if prop_value["type"] == "title":
                            title_items = prop_value.get("title", [])
                            if title_items:
                                page_title = title_items[0].get("plain_text", "")
                                break

                # إذا لم نجد عنواناً، نستخدم الرابط
                if not page_title:
                    page_title = page.get("url", "صفحة بدون عنوان").split("/")[-1]

                # إضافة زر للصفحة في لوحة المفاتيح
                page_id = page["id"]
                logger.info(f"إضافة صفحة: {page_title} (ID: {page_id})")
                keyboard.append([InlineKeyboardButton(page_title, callback_data=f"page_{page_id}")])
            except Exception as e:
                logger.error(f"خطأ في معالجة الصفحة: {str(e)}", exc_info=True)
                continue

        # إذا لم نجد أي صفحات، نعرض رسالة خطأ
        if not keyboard:
            error_msg = (
                "لم يتم العثور على أي صفحات. تأكد من:\n"
                "1. إضافة integration إلى الصفحات في Notion (Share -> Add connections -> TELEGRAM-BOT)\n"
                "2. منح الصلاحيات المناسبة للـ integration\n"
                "3. وجود صفحات في مساحة العمل الخاصة بك\n"
                "4. أن الـ integration لديه صلاحية الوصول للصفحات"
            )
            logger.error(error_msg)
            await update.message.reply_text(error_msg)
            return

        # إنشاء وإرسال لوحة المفاتيح التفاعلية
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "مرحباً! الرجاء اختيار الصفحات التي تريد الوصول إليها:",
            reply_markup=reply_markup
        )
    except Exception as e:
        error_msg = (
            f"حدث خطأ أثناء بدء البوت: {str(e)}\n"
            "تأكد من:\n"
            "1. صحة توكن Notion\n"
            "2. إضافة integration إلى الصفحات (Share -> Add connections -> TELEGRAM-BOT)\n"
            "3. منح الصلاحيات المناسبة"
        )
        logger.error(error_msg, exc_info=True)
        await update.message.reply_text(error_msg)

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    معالج الضغط على الأزرار في لوحة المفاتيح التفاعلية
    يقوم بحفظ اختيار المستخدم للصفحة
    
    المعاملات:
        update (Update): تحديث من تيليجرام يحتوي على معلومات الضغطة والمستخدم
        context (ContextTypes.DEFAULT_TYPE): سياق المحادثة
    """
    try:
        # الحصول على معلومات الضغطة
        query = update.callback_query
        await query.answer()  # إرسال إشعار للمستخدم بأن الضغطة تم استلامها
        
        # استخراج معرف المستخدم ومعرف الصفحة
        user_id = query.from_user.id
        page_id = query.data.replace("page_", "")  # إزالة البادئة page_ من معرف الصفحة
        
        # إنشاء قائمة للمستخدم إذا لم تكن موجودة
        if user_id not in user_pages:
            user_pages[user_id] = []
        
        # إضافة الصفحة لقائمة المستخدم إذا لم تكن مضافة
        if page_id not in user_pages[user_id]:
            user_pages[user_id].append(page_id)
            await query.edit_message_text(f"تم إضافة الصفحة إلى قائمة صفحاتك المتاحة!")
        else:
            await query.edit_message_text("هذه الصفحة مضافة مسبقاً!")
    except Exception as e:
        logger.error(f"حدث خطأ في button: {str(e)}")
        if query:
            await query.edit_message_text("حدث خطأ أثناء معالجة الزر!")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    معالج الرسائل النصية
    يقوم بإضافة الرسالة إلى صفحات Notion المحددة
    
    المعاملات:
        update (Update): تحديث من تيليجرام يحتوي على معلومات الرسالة والمستخدم
        context (ContextTypes.DEFAULT_TYPE): سياق المحادثة
    """
    try:
        # الحصول على معرف المستخدم ونص الرسالة
        user_id = update.message.from_user.id
        message_text = update.message.text
        
        # التحقق من أن المستخدم قد اختار صفحات
        if user_id not in user_pages or not user_pages[user_id]:
            await update.message.reply_text("الرجاء اختيار صفحة أولاً باستخدام الأمر /start")
            return
        
        # إضافة الرسالة إلى كل الصفحات المحددة
        for page_id in user_pages[user_id]:
            try:
                # إضافة الرسالة كفقرات في الصفحة
                notion.blocks.children.append(
                    block_id=page_id,
                    children=[
                        # فقرة فارغة قبل الرسالة
                        {
                            "object": "block",
                            "type": "paragraph",
                            "paragraph": {
                                "rich_text": [{"type": "text", "text": {"content": ""}}]
                            }
                        },
                        # فقرة تحتوي على الرسالة
                        {
                            "object": "block",
                            "type": "paragraph",
                            "paragraph": {
                                "rich_text": [{"type": "text", "text": {"content": message_text}}]
                            }
                        },
                        # فقرة فارغة بعد الرسالة
                        {
                            "object": "block",
                            "type": "paragraph",
                            "paragraph": {
                                "rich_text": [{"type": "text", "text": {"content": ""}}]
                            }
                        }
                    ]
                )
                await update.message.reply_text("تمت إضافة رسالتك إلى Notion!")
            except Exception as e:
                logger.error(f"حدث خطأ في إضافة الرسالة: {str(e)}")
                await update.message.reply_text(f"حدث خطأ أثناء إضافة الرسالة: {str(e)}")
    except Exception as e:
        logger.error(f"حدث خطأ في handle_message: {str(e)}")
        await update.message.reply_text("حدث خطأ أثناء معالجة الرسالة!")

def main():
    """
    الدالة الرئيسية لتشغيل البوت
    تقوم بتهيئة البوت وإضافة معالجات الأوامر وتشغيل البوت
    """
    try:
        # الحصول على توكن البوت
        token = os.getenv("TELEGRAM_BOT_TOKEN")
        if not token:
            raise ValueError("لم يتم العثور على توكن البوت! تأكد من ملف .env")
            
        # إنشاء تطبيق البوت
        logger.info("جاري تهيئة البوت...")
        application = Application.builder().token(token).build()
        logger.info("تم تهيئة البوت بنجاح!")

        # إضافة معالجات الأوامر
        logger.info("جاري إضافة معالجات الأوامر...")
        application.add_handler(CommandHandler("start", start))  # معالج أمر /start
        application.add_handler(CallbackQueryHandler(button))  # معالج الضغط على الأزرار
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))  # معالج الرسائل النصية
        logger.info("تم إضافة معالجات الأوامر بنجاح!")

        # تشغيل البوت
        logger.info("جاري تشغيل البوت...")
        application.run_polling(allowed_updates=Update.ALL_TYPES)
        logger.info("تم تشغيل البوت بنجاح!")
    except Exception as e:
        logger.error(f"حدث خطأ في main: {str(e)}")
        raise e

# نقطة بداية البرنامج
if __name__ == '__main__':
    main()
