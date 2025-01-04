# استيراد المكتبات اللازمة
import os  # للتعامل مع متغيرات البيئة ونظام التشغيل
import logging  # لتسجيل الأحداث والأخطاء
import sys  # للتعامل مع النظام
from dotenv import load_dotenv  # لتحميل المتغيرات البيئية من ملف .env
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup  # مكونات واجهة تيليجرام
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes  # معالجات تيليجرام
from notion_client import Client  # مكتبة للتعامل مع Notion API
import json  # للتعامل مع بيانات JSON
import io

# إعداد السجلات
import sys
import io

# إعداد الترميز للمخرجات
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

# تعيين مستوى التسجيل للمكتبات الأخرى
logging.getLogger('httpx').setLevel(logging.INFO)
logging.getLogger('telegram').setLevel(logging.INFO)

# تحميل المتغيرات البيئية
load_dotenv()

logger.info("جاري تحميل المتغيرات البيئية...")

# الحصول على التوكن من المتغيرات البيئية
notion_token = os.getenv("NOTION_TOKEN")
if not notion_token:
    logger.error("لم يتم العثور على NOTION_TOKEN في ملف .env")
    sys.exit(1)
    
logger.info(f"Notion token: {notion_token[:4]}...{notion_token[-4:]}")

# إنشاء عميل Notion
try:
    notion = Client(auth=notion_token)
    # اختبار الاتصال
    notion.users.me()
    logger.info("تم الاتصال بـ Notion بنجاح")
except Exception as e:
    logger.error(f"فشل الاتصال بـ Notion: {str(e)}")
    sys.exit(1)

# قاموس لتخزين الصفحات المرتبطة بكل توبيك
topic_pages = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    معالج أمر /start - يستخدم لربط التوبيك بصفحة Notion
    """
    try:
        message = update.message
        logger.info(f"تم استلام أمر start من المستخدم {message.from_user.id}")
        
        # التحقق من أن الرسالة في مجموعة وفي توبيك
        if not message.chat.is_forum:
            logger.info("المجموعة لا تدعم التوبيكات")
            await message.reply_text("عذراً، هذا الأمر يعمل فقط في المجموعات التي تدعم التوبيكات.")
            return
            
        if not message.is_topic_message:
            logger.info("الرسالة ليست في توبيك")
            await message.reply_text("عذراً، يجب استخدام هذا الأمر داخل توبيك.")
            return
            
        # التحقق من صلاحيات المستخدم
        user = message.from_user
        chat_member = await context.bot.get_chat_member(message.chat.id, user.id)
        if not chat_member.status in ['creator', 'administrator']:
            logger.info(f"المستخدم {user.id} ليس مشرفاً")
            await message.reply_text("عذراً، هذا الأمر متاح فقط للمشرفين.")
            return
            
        logger.info("جاري البحث عن صفحات Notion...")
        try:
            # البحث عن الصفحات في Notion
            pages = notion.search(
                **{
                    "filter": {
                        "value": "page",
                        "property": "object"
                    }
                }
            ).get("results", [])
            
            if not pages:
                logger.info("لم يتم العثور على صفحات")
                await message.reply_text("لم يتم العثور على صفحات في حساب Notion الخاص بك.")
                return
                
            # إنشاء أزرار للصفحات
            keyboard = []
            for page in pages[:10]:  # نأخذ أول 10 صفحات فقط
                try:
                    # الحصول على عنوان الصفحة
                    page_id = page["id"]
                    page_title = None
                    
                    # محاولة الحصول على العنوان من خصائص الصفحة
                    if "properties" in page:
                        title_property = page["properties"].get("title", {})
                        if title_property and "title" in title_property:
                            title_items = title_property["title"]
                            if title_items:
                                page_title = title_items[0].get("plain_text", "")
                    
                    # إذا لم نجد العنوان، نستخدم عنواناً افتراضياً
                    if not page_title:
                        page_title = "صفحة بدون عنوان"
                    
                    logger.info(f"تمت إضافة صفحة: {page_title} (ID: {page_id})")
                    callback_data = f"page_{message.message_thread_id}_{page_id}"
                    keyboard.append([InlineKeyboardButton(page_title, callback_data=callback_data)])
                    
                except Exception as e:
                    logger.error(f"خطأ في معالجة الصفحة {page.get('id', 'unknown')}: {str(e)}")
                    continue
                
            if not keyboard:
                logger.warning("لم يتم العثور على صفحات صالحة")
                await message.reply_text(
                    "لم يتم العثور على صفحات يمكن استخدامها.\n"
                    "تأكد من:\n"
                    "1. إضافة integration إلى الصفحات في Notion\n"
                    "2. منح الصلاحيات المناسبة للـ integration"
                )
                return
                
            reply_markup = InlineKeyboardMarkup(keyboard)
            await message.reply_text(
                "اختر الصفحة التي تريد ربط هذا التوبيك بها:",
                reply_markup=reply_markup
            )
            logger.info(f"تم إرسال قائمة الصفحات للمستخدم {user.id}")
            
        except Exception as e:
            logger.error(f"خطأ في البحث عن صفحات Notion: {str(e)}")
            await message.reply_text("حدث خطأ أثناء البحث عن الصفحات. الرجاء المحاولة مرة أخرى.")
            
    except Exception as e:
        logger.error(f"خطأ في معالجة أمر start: {str(e)}")
        await update.message.reply_text("حدث خطأ غير متوقع. الرجاء المحاولة مرة أخرى.")

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    معالج الأزرار - يستخدم لمعالجة اختيار الصفحة
    """
    try:
        query = update.callback_query
        await query.answer()
        
        # التحقق من صحة البيانات
        if not query.data.startswith("page_"):
            logger.error(f"بيانات غير صالحة: {query.data}")
            await query.edit_message_text("حدث خطأ. الرجاء المحاولة مرة أخرى.")
            return
            
        # استخراج معرف التوبيك ومعرف الصفحة
        _, topic_id, page_id = query.data.split("_")
        topic_id = int(topic_id)
        
        # تخزين الربط بين التوبيك والصفحة
        topic_pages[topic_id] = page_id
        logger.info(f"تم ربط التوبيك {topic_id} بالصفحة {page_id}")
        
        # تحديث الرسالة
        await query.edit_message_text(f"تم ربط هذا التوبيك بالصفحة بنجاح! يمكنك الآن إرسال الرسائل وسيتم حفظها في Notion.")
        
    except Exception as e:
        logger.error(f"خطأ في معالجة الزر: {str(e)}")
        await query.edit_message_text("حدث خطأ أثناء ربط الصفحة. الرجاء المحاولة مرة أخرى.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    معالجة الرسائل الواردة من المستخدمين
    
    Args:
        update (Update): تحديث تيليجرام الذي يحتوي على الرسالة
        context (ContextTypes.DEFAULT_TYPE): سياق البوت
    """
    try:
        logger.info("تم استلام رسالة جديدة")
        logger.info(f"نوع التحديث: {type(update)}")
        logger.info(f"محتويات التحديث: {update.to_dict()}")
        
        message = update.message
        if not message:
            logger.info("لا توجد رسالة في التحديث")
            return
            
        logger.info(f"معلومات الرسالة: {message.to_dict()}")
        
        # التحقق من أن الرسالة من توبيك
        is_topic_message = message.is_topic_message if hasattr(message, 'is_topic_message') else False
        logger.info(f"هل الرسالة من توبيك؟ {is_topic_message}")
        
        if not is_topic_message:
            logger.info("الرسالة ليست من توبيك")
            return
        
        # الحصول على معرف التوبيك
        topic_id = message.message_thread_id
        logger.info(f"معرف التوبيك: {topic_id}")
        
        # التحقق من وجود التوبيك في القاموس
        if topic_id not in topic_pages:
            logger.info("معرف التوبيك غير مرتبط بأي صفحة")
            return
            
        logger.info(f"معرف التوبيك: {topic_id}")
        logger.info(f"قائمة التوبيكات المرتبطة: {topic_pages}")
        
        # الحصول على معرف الصفحة المرتبطة بالتوبيك
        page_id = topic_pages[topic_id]
        logger.info(f"معرف الصفحة: {page_id}")
        
        # معالجة أنواع مختلفة من الرسائل
        content = None
        
        if message.text:
            # رسالة نصية
            logger.info(f"رسالة نصية: {message.text}")
            content = await create_text_block(message.text)
            
        elif message.photo:
            # صورة
            logger.info("رسالة صورة")
            content = await create_media_block(message.photo[-1], "صورة", message.caption)
                
        elif message.video:
            # فيديو
            logger.info("رسالة فيديو")
            content = await create_media_block(message.video, "فيديو", message.caption)
                
        elif message.voice:
            # رسالة صوتية
            logger.info("رسالة صوتية")
            content = await create_media_block(message.voice, "رسالة صوتية")
                
        elif message.audio:
            # ملف صوتي
            logger.info("ملف صوتي")
            title = message.audio.title if message.audio.title else "بدون عنوان"
            performer = message.audio.performer if message.audio.performer else "غير معروف"
            caption = f"العنوان: {title}\nالمؤدي: {performer}"
            content = await create_media_block(message.audio, "ملف صوتي", caption)
                
        elif message.document:
            # مستند
            logger.info("مستند")
            file_name = message.document.file_name if message.document.file_name else "بدون اسم"
            content = await create_media_block(message.document, "مستند", f"اسم الملف: {file_name}")
        
        if content:
            # إضافة المحتوى إلى Notion
            logger.info("جاري إضافة المحتوى إلى Notion...")
            try:
                # إضافة سطر فارغ قبل المحتوى
                notion.blocks.children.append(
                    page_id,
                    children=[
                        {
                            "object": "block",
                            "type": "paragraph",
                            "paragraph": {
                                "rich_text": []
                            }
                        },
                        content,
                        {
                            "object": "block",
                            "type": "paragraph",
                            "paragraph": {
                                "rich_text": []
                            }
                        }
                    ]
                )
                logger.info("تم إضافة المحتوى بنجاح إلى Notion")
                await message.reply_text("تم حفظ الرسالة في Notion بنجاح!")
            except Exception as e:
                logger.error(f"خطأ في إضافة المحتوى إلى Notion: {str(e)}")
                await message.reply_text("حدث خطأ أثناء حفظ الرسالة في Notion. الرجاء المحاولة مرة أخرى.")
        else:
            logger.warning("نوع الرسالة غير مدعوم")
            await message.reply_text("عذراً، هذا النوع من الرسائل غير مدعوم حالياً.")
            
    except Exception as e:
        logger.error(f"حدث خطأ في handle_message: {str(e)}")
        await message.reply_text("حدث خطأ غير متوقع. الرجاء المحاولة مرة أخرى.")

async def create_text_block(text: str) -> dict:
    """
    إنشاء كتلة نص لـ Notion
    
    Args:
        text (str): النص المراد إضافته
        
    Returns:
        dict: كتلة Notion
    """
    return {
        "object": "block",
        "type": "paragraph",
        "paragraph": {
            "rich_text": [{
                "type": "text",
                "text": {
                    "content": text
                }
            }]
        }
    }

async def create_media_block(media_obj, media_type: str, caption: str = None) -> dict:
    """
    إنشاء كتلة وسائط لـ Notion
    
    Args:
        media_obj: كائن الوسائط من تيليجرام
        media_type (str): نوع الوسائط (صورة، فيديو، إلخ)
        caption (str, optional): وصف الوسائط
        
    Returns:
        dict: كتلة Notion
    """
    try:
        file = await media_obj.get_file()
        content = f"{media_type}: {file.file_path}"
        if caption:
            content += f"\n{caption}"
            
        return await create_text_block(content)
    except Exception as e:
        logger.error(f"خطأ في الحصول على رابط {media_type}: {str(e)}")
        return None

def main():
    """
    الدالة الرئيسية لتشغيل البوت
    """
    try:
        # الحصول على توكن البوت من المتغيرات البيئية
        bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        if not bot_token:
            logger.error("لم يتم العثور على توكن البوت")
            return
            
        # إنشاء تطبيق البوت
        application = Application.builder().token(bot_token).build()
        
        # إضافة معالج الأمر /start
        application.add_handler(CommandHandler("start", start))
        
        # إضافة معالج الأزرار
        application.add_handler(CallbackQueryHandler(button))
        
        # إضافة معالج الرسائل
        application.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_message))
        
        # بدء تشغيل البوت
        logger.info("جاري بدء تشغيل البوت...")
        application.run_polling(allowed_updates=Update.ALL_TYPES)
        
    except Exception as e:
        logger.error(f"حدث خطأ في main: {str(e)}")

# نقطة بداية البرنامج
if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("تم إيقاف البوت بواسطة المستخدم")
    except Exception as e:
        logger.error(f"حدث خطأ غير متوقع: {str(e)}")
