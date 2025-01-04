import os
import logging
import sys
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from notion_client import Client
import json

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Load environment variables
logger.info("جاري تحميل المتغيرات البيئية...")
load_dotenv()

# Initialize Notion client
token = os.getenv("NOTION_TOKEN")
logger.info(f"Notion token: {token[:4]}...{token[-4:]}")
notion = Client(auth=token)

# Store user's page selections
user_pages = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send welcome message and initialize the bot."""
    try:
        logger.info("بدء البحث عن الصفحات في Notion...")
        
        # Try to search without filter first
        response = notion.search(
            query="",
            sort={
                "direction": "ascending",
                "timestamp": "last_edited_time"
            }
        )
        
        pages = response.get("results", [])
        logger.info(f"تم العثور على {len(pages)} صفحة")
        
        for page in pages:
            logger.info(f"معلومات الصفحة: {page.get('id')} - {page.get('url')} - {page.get('object')}")
        
        # Create keyboard with available pages
        keyboard = []
        for page in pages:
            try:
                if page.get("object") != "page":
                    continue
                    
                # Get page info
                page_info = notion.pages.retrieve(page_id=page["id"])
                logger.info(f"معلومات تفصيلية للصفحة: {page_info}")
                
                # Try to get title
                page_title = None
                
                # Try to get it from properties
                if "properties" in page_info:
                    for prop_name, prop_value in page_info["properties"].items():
                        if prop_value["type"] == "title":
                            title_items = prop_value.get("title", [])
                            if title_items:
                                page_title = title_items[0].get("plain_text", "")
                                break

                # If still no title, use URL
                if not page_title:
                    page_title = page.get("url", "صفحة بدون عنوان").split("/")[-1]

                page_id = page["id"]
                logger.info(f"إضافة صفحة: {page_title} (ID: {page_id})")
                keyboard.append([InlineKeyboardButton(page_title, callback_data=f"page_{page_id}")])
            except Exception as e:
                logger.error(f"خطأ في معالجة الصفحة: {str(e)}", exc_info=True)
                continue

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
    """Handle button presses."""
    try:
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        page_id = query.data.replace("page_", "")
        
        if user_id not in user_pages:
            user_pages[user_id] = []
        
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
    """Handle incoming messages and add them to Notion."""
    try:
        user_id = update.message.from_user.id
        message_text = update.message.text
        
        if user_id not in user_pages or not user_pages[user_id]:
            await update.message.reply_text("الرجاء اختيار صفحة أولاً باستخدام الأمر /start")
            return
        
        # Add message to all selected pages
        for page_id in user_pages[user_id]:
            try:
                notion.blocks.children.append(
                    block_id=page_id,
                    children=[
                        {
                            "object": "block",
                            "type": "paragraph",
                            "paragraph": {
                                "rich_text": [{"type": "text", "text": {"content": ""}}]
                            }
                        },
                        {
                            "object": "block",
                            "type": "paragraph",
                            "paragraph": {
                                "rich_text": [{"type": "text", "text": {"content": message_text}}]
                            }
                        },
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
    """Start the bot."""
    try:
        # Get the token
        token = os.getenv("TELEGRAM_BOT_TOKEN")
        if not token:
            raise ValueError("لم يتم العثور على توكن البوت! تأكد من ملف .env")
            
        # Create the Application
        logger.info("جاري تهيئة البوت...")
        application = Application.builder().token(token).build()
        logger.info("تم تهيئة البوت بنجاح!")

        # Add handlers
        logger.info("جاري إضافة معالجات الأوامر...")
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CallbackQueryHandler(button))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        logger.info("تم إضافة معالجات الأوامر بنجاح!")

        # Start the bot
        logger.info("جاري تشغيل البوت...")
        application.run_polling(allowed_updates=Update.ALL_TYPES)
        logger.info("تم تشغيل البوت بنجاح!")
    except Exception as e:
        logger.error(f"حدث خطأ في main: {str(e)}")
        raise e

if __name__ == '__main__':
    main()
