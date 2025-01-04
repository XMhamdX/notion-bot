import asyncio
import logging
import os
from telegram import Update, Message, Video, Bot
from telegram.ext import ContextTypes, Application
from bot import handle_message, topic_pages
from dotenv import load_dotenv

# تحميل المتغيرات البيئية
load_dotenv()
bot_token = os.getenv("TELEGRAM_BOT_TOKEN")

# إعداد السجلات
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    encoding='utf-8'
)
logger = logging.getLogger(__name__)

async def close_bot(bot):
    """
    إغلاق جلسة البوت بأمان
    """
    try:
        await bot.close()
    except Exception as e:
        logger.warning(f"حدث خطأ أثناء إغلاق البوت: {str(e)}")

async def test_text_message():
    """
    اختبار معالجة الرسائل النصية
    """
    # إنشاء تطبيق البوت
    application = Application.builder().token(bot_token).build()
    
    # إنشاء رسالة وهمية
    message_dict = {
        'message_id': 1,
        'date': 1234567890,
        'chat': {
            'id': 123456789,
            'type': 'supergroup',
            'title': 'Test Group',
            'is_forum': True  # تفعيل المنتدى للتوبيكات
        },
        'message_thread_id': 1,  # معرف التوبيك
        'is_topic_message': True,  # تأكيد أن الرسالة من توبيك
        'from': {
            'id': 123456789,
            'is_bot': False,
            'first_name': 'Test',
            'username': 'test_user'
        },
        'text': 'هذه رسالة اختبار'
    }
    
    # إضافة توبيك وهمي للاختبار
    topic_pages[1] = "1285eaef-55e9-8002-bcbf-cd2f71e42c9f"
    
    # إنشاء كائن Update وهمي
    bot = Bot(token=bot_token)
    message = Message.de_json(message_dict, bot)
    update = Update(1, message=message)
    
    # إنشاء سياق وهمي
    context = ContextTypes.DEFAULT_TYPE(application=application)
    
    try:
        # اختبار معالجة الرسالة
        logger.info("بدء اختبار معالجة الرسالة النصية...")
        await handle_message(update, context)
        logger.info("انتهى اختبار معالجة الرسالة النصية")
    finally:
        # إغلاق جلسة البوت
        await close_bot(bot)

async def test_video_message():
    """
    اختبار معالجة رسائل الفيديو
    """
    # إنشاء تطبيق البوت
    application = Application.builder().token(bot_token).build()
    
    # إنشاء فيديو وهمي
    video_dict = {
        'file_id': 'test_file_id',
        'file_unique_id': 'test_unique_id',
        'width': 1280,
        'height': 720,
        'duration': 30,
        'file_name': 'test_video.mp4',
        'mime_type': 'video/mp4',
        'file_size': 1024,
        'file_path': 'https://example.com/test_video.mp4'
    }
    
    # إنشاء رسالة وهمية
    message_dict = {
        'message_id': 2,
        'date': 1234567890,
        'chat': {
            'id': 123456789,
            'type': 'supergroup',
            'title': 'Test Group',
            'is_forum': True
        },
        'message_thread_id': 1,
        'is_topic_message': True,
        'from': {
            'id': 123456789,
            'is_bot': False,
            'first_name': 'Test',
            'username': 'test_user'
        },
        'video': video_dict,
        'caption': 'هذا فيديو اختباري'  # إضافة وصف للفيديو
    }
    
    # إضافة توبيك وهمي للاختبار
    topic_pages[1] = "1285eaef-55e9-8002-bcbf-cd2f71e42c9f"
    
    # إنشاء كائن Update وهمي
    bot = Bot(token=bot_token)
    message = Message.de_json(message_dict, bot)
    update = Update(2, message=message)
    
    # إنشاء سياق وهمي
    context = ContextTypes.DEFAULT_TYPE(application=application)
    
    try:
        # اختبار معالجة الرسالة
        logger.info("بدء اختبار معالجة رسالة الفيديو...")
        await handle_message(update, context)
        logger.info("انتهى اختبار معالجة رسالة الفيديو")
    finally:
        # إغلاق جلسة البوت
        await close_bot(bot)

async def run_tests():
    """
    تشغيل جميع الاختبارات
    """
    logger.info("بدء تشغيل الاختبارات...")
    
    try:
        # اختبار الرسائل النصية
        await test_text_message()
        
        # انتظار قليلاً بين الاختبارات
        await asyncio.sleep(1)
        
        # اختبار رسائل الفيديو
        await test_video_message()
        
        logger.info("انتهت جميع الاختبارات")
    except Exception as e:
        logger.error(f"حدث خطأ أثناء تشغيل الاختبارات: {str(e)}")
        raise

if __name__ == "__main__":
    try:
        # تشغيل الاختبارات
        asyncio.run(run_tests())
    except KeyboardInterrupt:
        logger.info("تم إيقاف الاختبارات بواسطة المستخدم")
    except Exception as e:
        logger.error(f"حدث خطأ غير متوقع: {str(e)}")
        raise
