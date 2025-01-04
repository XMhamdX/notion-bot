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

# قاموس لتخزين الصفحات المرتبطة بكل محادثة/توبيك
STORAGE_FILE = 'topic_pages.json'

def load_topic_pages() -> dict:
    """
    تحميل الروابط المخزنة بين التوبيكات والصفحات
    """
    if os.path.exists(STORAGE_FILE):
        try:
            with open(STORAGE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"خطأ في قراءة ملف التخزين: {str(e)}")
    return {}

def save_topic_pages(topic_pages: dict):
    """
    حفظ الروابط بين التوبيكات والصفحات
    """
    try:
        with open(STORAGE_FILE, 'w', encoding='utf-8') as f:
            json.dump(topic_pages, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"خطأ في حفظ ملف التخزين: {str(e)}")

# تحميل الروابط المخزنة عند بدء البوت
topic_pages = load_topic_pages()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    معالج أمر /start - يستخدم لربط التوبيك أو المحادثة بصفحة Notion
    """
    try:
        message = update.message
        if not message:
            return
            
        logger.info(f"تم استلام أمر start من المستخدم {message.from_user.id}")
        
        # التحقق من نوع المحادثة
        chat_type = message.chat.type
        chat_id = str(message.chat.id)  # تحويل معرف المحادثة إلى نص
        thread_id = str(message.message_thread_id) if message.is_topic_message else chat_id  # تحويل معرف التوبيك إلى نص
        
        logger.info(f"نوع المحادثة: {chat_type}")
        logger.info(f"معرف المحادثة: {chat_id}")
        logger.info(f"معرف التوبيك: {thread_id}")
        
        # في حالة المجموعة
        if chat_type in ['group', 'supergroup']:
            if not message.chat.is_forum:
                logger.info("المجموعة لا تدعم التوبيكات")
                await message.reply_text("عذراً، هذا الأمر يعمل فقط في المجموعات التي تدعم التوبيكات أو في المحادثة المباشرة مع البوت.")
                return
                
            if not message.is_topic_message:
                logger.info("الرسالة ليست في توبيك")
                await message.reply_text("عذراً، يجب استخدام هذا الأمر داخل توبيك.")
                return
                
            # التحقق من صلاحيات المستخدم في المجموعة
            user = message.from_user
            chat_member = await context.bot.get_chat_member(message.chat.id, user.id)
            if not chat_member.status in ['creator', 'administrator']:
                logger.info(f"المستخدم {user.id} ليس مشرفاً")
                await message.reply_text("عذراً، هذا الأمر متاح فقط للمشرفين في المجموعات.")
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
                    
                    # في حالة المجموعة، نستخدم معرف التوبيك
                    # في حالة المحادثة المباشرة، نستخدم معرف المحادثة
                    callback_data = f"page_{thread_id}_{page_id}"
                    
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
                "اختر الصفحة التي تريد ربطها:",
                reply_markup=reply_markup
            )
            logger.info(f"تم إرسال قائمة الصفحات للمستخدم {message.from_user.id}")
            
        except Exception as e:
            logger.error(f"خطأ في البحث عن صفحات Notion: {str(e)}")
            await message.reply_text("حدث خطأ أثناء البحث عن الصفحات. الرجاء المحاولة مرة أخرى.")
            
    except Exception as e:
        logger.error(f"خطأ في معالجة أمر start: {str(e)}")
        await update.message.reply_text("حدث خطأ غير متوقع. الرجاء المحاولة مرة أخرى.")

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    معالج الضغط على الأزرار
    """
    try:
        query = update.callback_query
        await query.answer()  # نجيب على الضغطة لإزالة علامة التحميل
        
        logger.info(f"تم الضغط على زر: {query.data}")
        
        if not query.data.startswith("page_"):
            logger.warning(f"نوع زر غير معروف: {query.data}")
            return
            
        # استخراج معرف التوبيك ومعرف الصفحة
        _, thread_id, page_id = query.data.split("_")
        
        # تخزين الربط بين التوبيك والصفحة
        topic_pages[thread_id] = page_id
        # حفظ التغييرات في الملف
        save_topic_pages(topic_pages)
        
        logger.info(f"تم ربط المحادثة/التوبيك {thread_id} بالصفحة {page_id}")
        logger.info(f"قائمة المحادثات المرتبطة: {topic_pages}")
        
        # تحديث الرسالة
        await query.edit_message_text("تم ربط المحادثة بالصفحة بنجاح! يمكنك الآن إرسال الرسائل وسيتم حفظها في Notion.")
        
    except Exception as e:
        logger.error(f"خطأ في معالجة الضغط على الزر: {str(e)}")
        await query.edit_message_text("حدث خطأ أثناء ربط المحادثة بالصفحة. الرجاء المحاولة مرة أخرى.")

async def create_media_block(media_obj, media_type: str, caption: str = None) -> dict:
    """
    إنشاء بلوك وسائط لـ Notion
    """
    try:
        logger.info(f"جاري إنشاء بلوك {media_type}")
        
        # إنشاء رابط للملف
        message_link = f"https://t.me/c/{str(media_obj.file_unique_id)}"
        
        # إنشاء نص الرابط
        link_text = f"{media_type}"
        if caption:
            link_text = f"{caption}\n{link_text}"
            
        return {
            "object": "block",
            "type": "paragraph",
            "paragraph": {
                "rich_text": [
                    {
                        "type": "text",
                        "text": {
                            "content": link_text + ": ",
                        }
                    },
                    {
                        "type": "text",
                        "text": {
                            "content": message_link,
                            "link": {"url": message_link}
                        }
                    }
                ]
            }
        }
    except Exception as e:
        logger.error(f"خطأ في إنشاء بلوك الوسائط: {str(e)}")
        raise

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    معالجة الرسائل الواردة من المستخدمين
    """
    try:
        message = update.message
        if not message:
            return
            
        # التعامل مع المحادثات المباشرة والتوبيكات
        chat_id = str(message.chat.id)  # تحويل معرف المحادثة إلى نص
        thread_id = str(message.message_thread_id) if message.is_topic_message else chat_id  # تحويل معرف التوبيك إلى نص
        
        logger.info(f"معالجة رسالة من المحادثة/التوبيك: {thread_id}")
        logger.info(f"قائمة المحادثات المرتبطة: {topic_pages}")
        
        # التحقق من وجود ربط للمحادثة/التوبيك
        if thread_id not in topic_pages:
            logger.info("المحادثة/التوبيك غير مرتبط بأي صفحة")
            return
            
        # الحصول على معرف الصفحة المرتبطة
        page_id = topic_pages[thread_id]
        logger.info(f"معرف الصفحة: {page_id}")
        
        # إنشاء رابط للرسالة
        chat_id_str = str(message.chat.id)[4:] if str(message.chat.id).startswith('-100') else str(message.chat.id)
        
        if message.is_topic_message:
            message_link = f"https://t.me/c/{chat_id_str}/{message.message_thread_id}/{message.message_id}"
        else:
            message_link = f"https://t.me/c/{chat_id_str}/{message.message_id}"
            
        logger.info(f"رابط الرسالة: {message_link}")
        
        # معالجة أنواع مختلفة من الرسائل
        content = None
        
        if message.text:
            # رسالة نصية
            logger.info(f"رسالة نصية: {message.text}")
            content = await create_text_block(message.text)
            
        elif message.photo:
            # صورة
            logger.info("رسالة صورة")
            content = {
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": []
                }
            }
            
            # إضافة الوصف إذا وجد
            if message.caption:
                content["paragraph"]["rich_text"].append({
                    "type": "text",
                    "text": {
                        "content": f"{message.caption}\n",
                    }
                })
            
            # إضافة رابط الصورة
            content["paragraph"]["rich_text"].append({
                "type": "text",
                "text": {
                    "content": "صورة: ",
                }
            })
            content["paragraph"]["rich_text"].append({
                "type": "text",
                "text": {
                    "content": message_link,
                    "link": {"url": message_link}
                }
            })
                
        elif message.video:
            # فيديو
            logger.info("رسالة فيديو")
            content = {
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": []
                }
            }
            
            # إضافة الوصف إذا وجد
            if message.caption:
                content["paragraph"]["rich_text"].append({
                    "type": "text",
                    "text": {
                        "content": f"{message.caption}\n",
                    }
                })
            
            # إضافة رابط الفيديو
            content["paragraph"]["rich_text"].append({
                "type": "text",
                "text": {
                    "content": "فيديو: ",
                }
            })
            content["paragraph"]["rich_text"].append({
                "type": "text",
                "text": {
                    "content": message_link,
                    "link": {"url": message_link}
                }
            })
                
        elif message.voice:
            # رسالة صوتية
            logger.info("رسالة صوتية")
            content = {
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [
                        {
                            "type": "text",
                            "text": {
                                "content": "رسالة صوتية: ",
                            }
                        },
                        {
                            "type": "text",
                            "text": {
                                "content": message_link,
                                "link": {"url": message_link}
                            }
                        }
                    ]
                }
            }
                
        elif message.audio:
            # ملف صوتي
            logger.info("ملف صوتي")
            title = message.audio.title if message.audio.title else "بدون عنوان"
            performer = message.audio.performer if message.audio.performer else "غير معروف"
            content = {
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [
                        {
                            "type": "text",
                            "text": {
                                "content": f"العنوان: {title}\nالمؤدي: {performer}\nملف صوتي: ",
                            }
                        },
                        {
                            "type": "text",
                            "text": {
                                "content": message_link,
                                "link": {"url": message_link}
                            }
                        }
                    ]
                }
            }
                
        elif message.document:
            # مستند
            logger.info("مستند")
            file_name = message.document.file_name if message.document.file_name else "بدون اسم"
            content = {
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [
                        {
                            "type": "text",
                            "text": {
                                "content": f"اسم الملف: {file_name}\nمستند: ",
                            }
                        },
                        {
                            "type": "text",
                            "text": {
                                "content": message_link,
                                "link": {"url": message_link}
                            }
                        }
                    ]
                }
            }
        
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
