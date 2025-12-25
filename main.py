import os
import logging
import asyncio
from flask import Flask
from threading import Thread
from google import genai
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# --- تنظیمات لاگ ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', 
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- بررسی متغیرهای محیطی (عیب‌یابی خودکار) ---
BOT_TOKEN = os.environ.get("BOT_TOKEN")
GEMINI_KEY = os.environ.get("GEMINI_KEY")

if not BOT_TOKEN:
    logger.error("❌ متغیر BOT_TOKEN یافت نشد!")
if not GEMINI_KEY:
    logger.error("❌ متغیر GEMINI_KEY یافت نشد! نام را در پنل رندر چک کنید.")
else:
    logger.info(f"✅ کلید هوش مصنوعی شناسایی شد (شروع با: {GEMINI_KEY[:5]}...)")

# --- تنظیمات هوش مصنوعی ---
try:
    ai_client = genai.Client(api_key=GEMINI_KEY) if GEMINI_KEY else None
except Exception as e:
    logger.error(f"❌ خطا در راه اندازی Gemini: {e}")
    ai_client = None

async def get_ai_response(user_text):
    try:
        if not ai_client:
            return "❌ سیستم هوش مصنوعی فعلاً متصل نیست (کلید یافت نشد)."
        
        # استفاده از مدل سریع و پرقدرت Flash 2.0
        response = ai_client.models.generate_content(
            model="gemini-2.0-flash", 
            contents=user_text
        )
        return response.text if response.text else "متأسفانه پاسخی دریافت نشد."
    except Exception as e:
        logger.error(f"AI Error: {e}")
        if "429" in str(e):
            return "شرمنه، سهمیه پیام‌های من تموم شده. کمی صبر کن یا بعداً بپرس. ⏳"
        return f"یک خطای فنی رخ داد: {str(e)[:50]}..."

# --- هندلرهای تلگرام ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await update.message.reply_html(
        rf"سلام {user.mention_html()}! 🤖"
        "\nمن به هوش مصنوعی Gemini وصل شدم. هر سوالی داری ازم بپرس!"
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    # نمایش وضعیت در حال تایپ
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    
    user_text = update.message.text
    ai_reply = await get_ai_response(user_text)
    
    await update.message.reply_text(ai_reply)

# --- وب‌سرور برای رندر ---
app = Flask(__name__)

@app.route('/')
def health():
    return "Bot is alive and running!", 200

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

# --- بخش اصلی اجرا ---
def main():
    if not BOT_TOKEN:
        return

    # ۱. اجرای وب‌سرور در ترد جداگانه
    Thread(target=run_flask, daemon=True).start()

    # ۲. ساخت و اجرای اپلیکیشن تلگرام
    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("🚀 ربات در حال اجراست...")
    application.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
