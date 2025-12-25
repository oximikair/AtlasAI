import os
import logging
import asyncio
import time
from flask import Flask
from threading import Thread
from google import genai
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# ۱. تنظیمات لاگ برای ردیابی در رندر
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# ۲. دریافت توکن‌ها از Environment Variables
BOT_TOKEN = os.environ.get("BOT_TOKEN")
GEMINI_KEY = os.environ.get("GEMINI_KEY")

def get_ai_client():
    if not GEMINI_KEY: return None
    try:
        return genai.Client(api_key=GEMINI_KEY)
    except Exception as e:
        logger.error(f"Error creating AI client: {e}")
        return None

# ۳. تابع هوش مصنوعی با متن خطای اختصاصی شما
async def get_ai_response(user_text):
    client = get_ai_client()
    try:
        if not client: raise Exception("No API Key")
        
        response = client.models.generate_content(
            model="gemini-2.0-flash", 
            contents=user_text
        )
        return response.text if response.text else "پاسخی یافت نشد."
    except Exception as e:
        logger.error(f"AI Error: {e}")
        return "اطلس در حال حاضر قادر به پاسخگویی نیست اما شما میتوانید از دیگر قابلیت های آن استفاده کنید"

# ۴. هندلر اصلی پیام‌ها با شرط ریپلای و منشن
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    # بررسی نوع چت (گروه یا شخصی)
    chat_type = update.message.chat.type
    is_group = chat_type in ["group", "supergroup"]
    
    # بررسی ریپلای به ربات
    is_reply_to_bot = (
        update.message.reply_to_message and 
        update.message.reply_to_message.from_user.id == context.bot.id
    )
    
    # بررسی منشن شدن ربات
    bot_username = (await context.bot.get_me()).username
    is_mentioned = f"@{bot_username}" in update.message.text

    # منطق پاسخگویی: در گروه فقط اگر ریپلای یا منشن باشد جواب بده
    if is_group and not (is_reply_to_bot or is_mentioned):
        return

    # نمایش وضعیت در حال تایپ
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    
    # پاکسازی متن از منشن ربات برای پردازش بهتر توسط هوش مصنوعی
    clean_text = update.message.text.replace(f"@{bot_username}", "").strip()
    
    # دریافت جواب و ارسال
    reply_text = await get_ai_response(clean_text)
    await update.message.reply_text(reply_text)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("سلام! من اطلس هستم. در خدمت شما!")

# ۵. وب‌سرور برای زنده نگه داشتن در Render
app = Flask(__name__)
@app.route('/')
def health(): return "Atlas is Online!", 200

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

# ۶. اجرای برنامه
if __name__ == "__main__":
    # اجرای وب‌سرور
    Thread(target=run_flask, daemon=True).start()

    # وقفه ۱۰ ثانیه‌ای برای جلوگیری از تداخل نسخه‌های رندر
    logger.info("Waiting 10s for session cleanup...")
    time.sleep(10)

    if BOT_TOKEN:
        application = Application.builder().token(BOT_TOKEN).build()
        application.add_handler(CommandHandler("start", start))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

        logger.info("🚀 Atlas Bot Started!")
        application.run_polling(drop_pending_updates=True)
    else:
        logger.error("❌ BOT_TOKEN found!")
