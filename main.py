import os
import logging
import asyncio
from flask import Flask
from threading import Thread
from google import genai
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# ۱. تنظیمات لاگ (برای اینکه بفهمیم توی رندر چه خبره)
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# ۲. تنظیمات هوش مصنوعی (Gemini)
GEMINI_KEY = os.environ.get("GEMINI_KEY")
ai_client = genai.Client(api_key=GEMINI_KEY) if GEMINI_KEY else None

async def get_ai_response(user_text):
    try:
        if not ai_client:
            return "❌ کلید هوش مصنوعی ست نشده است."
        
        # استفاده از مدل Flash که سهمیه بسیار بالایی دارد
        response = ai_client.models.generate_content(
            model="gemini-2.0-flash", 
            contents=user_text
        )
        return response.text
    except Exception as e:
        logger.error(f"AI Error: {e}")
        return "سرور هوش مصنوعی فعلاً شلوغه، ولی من هنوز بیدارم! چند لحظه دیگه بپرس."

# ۳. هندلرهای ربات تلگرام
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("سلام! من ربات جدیدت هستم که از صفر بازنویسی شدم. 🚀\nهر سوالی داری ازم بپرس!")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    
    # نمایش حالت "در حال تایپ" در تلگرام برای حس بهتر کاربر
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    
    # گرفتن جواب از هوش مصنوعی
    ai_reply = await get_ai_response(user_text)
    await update.message.reply_text(ai_reply)

# ۴. بخش وب‌سرور (برای زنده نگه داشتن در رندر)
app = Flask(__name__)
@app.route('/')
def health_check(): return "Bot is Online", 200

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

# ۵. اجرای اصلی
if __name__ == "__main__":
    # الف) اجرای وب‌سرور در ترد جداگانه
    Thread(target=run_flask, daemon=True).start()

    # ب) تنظیم و اجرای ربات
    TOKEN = os.environ.get("BOT_TOKEN")
    application = Application.builder().token(TOKEN).build()

    # اضافه کردن قابلیت‌ها
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("--- Bot is Running ---")
    application.run_polling(drop_pending_updates=True)
