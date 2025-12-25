import os
import logging
import asyncio
import time
from flask import Flask
from threading import Thread
from google import genai
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# ۱. تنظیمات لاگ
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', 
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ۲. تنظیمات کلیدها
BOT_TOKEN = os.environ.get("BOT_TOKEN")
GEMINI_KEY = os.environ.get("GEMINI_KEY")

def get_ai_client():
    if not GEMINI_KEY:
        return None
    try:
        return genai.Client(api_key=GEMINI_KEY)
    except Exception as e:
        logger.error(f"Error creating AI client: {e}")
        return None

# ۳. تابع گرفتن پاسخ از هوش مصنوعی
async def get_ai_response(user_text):
    client = get_ai_client()
    try:
        if not client:
            raise Exception("No API Key")
        
        # استفاده از مدل Gemini 2.0 Flash
        response = client.models.generate_content(
            model="gemini-2.0-flash", 
            contents=user_text
        )
        
        if response and response.text:
            return response.text
        else:
            raise Exception("Empty Response")

    except Exception as e:
        logger.error(f"AI Error: {e}")
        # متنی که خودت گفتی
        return "اطلس در حال حاضر قادر به پاسخگویی نیست اما شما میتوانید از دیگر قابلیت های آن استفاده کنید"

# ۴. هندلرهای ربات
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("سلام! من اطلس هستم. 🤖 بنویس تا با هم گپ بزنیم!")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    # نمایش وضعیت در حال تایپ
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    
    user_text = update.message.text
    reply_text = await get_ai_response(user_text)
    
    await update.message.reply_text(reply_text)

# ۵. وب‌سرور Flask برای Render
app = Flask(__name__)

@app.route('/')
def health_check():
    return "Atlas Bot is Online!", 200

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

# ۶. اجرای اصلی
if __name__ == "__main__":
    # اجرای وب‌سرور
    Thread(target=run_flask, daemon=True).start()

    # وقفه ۱۰ ثانیه‌ای برای جلوگیری از تداخل (Conflict) در رندر
    logger.info("Waiting 10 seconds to avoid session conflict...")
    time.sleep(10)

    if not BOT_TOKEN:
        logger.error("❌ BOT_TOKEN یافت نشد.")
    else:
        application = Application.builder().token(BOT_TOKEN).build()

        application.add_handler(CommandHandler("start", start))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

        logger.info("🚀 Atlas Bot is starting...")
        application.run_polling(drop_pending_updates=True)
