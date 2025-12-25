import os
import logging
import asyncio
import httpx
from flask import Flask
from threading import Thread
from google import genai  # اصلاح شده برای نسخه جدید
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

# تنظیمات لاگ
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# --- تنظیمات متغیرهای محیطی ---
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GENAI_API_KEY = os.getenv("GENAI_API_KEY")
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
VOICE_ID = "21m00Tcm4lS96DGzAsAn"  # آی‌دی صدای پیش‌فرض

# مقداردهی کلاینت Gemini
client = genai.Client(api_key=GENAI_API_KEY)

# ایجاد اپلیکیشن فلاسک برای زنده نگه داشتن در رندر
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running!"

def run_flask():
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))

# --- توابع کمکی ---

async def text_to_voice(text):
    """تبدیل متن به صدا با ElevenLabs"""
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}"
    headers = {
        "Accept": "audio/mpeg",
        "Content-Type": "application/json",
        "xi-api-key": ELEVENLABS_API_KEY
    }
    data = {
        "text": text,
        "model_id": "eleven_multilingual_v2",
        "voice_settings": {"stability": 0.5, "similarity_boost": 0.5}
    }
    
    async with httpx.AsyncClient() as http_client:
        response = await http_client.post(url, json=data, headers=headers)
        if response.status_code == 200:
            file_path = "voice.mp3"
            with open(file_path, "wb") as f:
                f.write(response.content)
            return file_path
        else:
            logging.error(f"ElevenLabs Error: {response.status_code} - {response.text}")
            return None

async def get_gemini_response(prompt):
    """دریافت پاسخ از Gemini"""
    try:
        response = client.models.generate_content(model="gemini-2.0-flash", contents=prompt)
        return response.text
    except Exception as e:
        logging.error(f"Gemini Error: {e}")
        return "❌ متأسفانه در حال حاضر نمی‌توانم پاسخ دهم."

# --- هندلرهای ربات ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("سلام! من اطلس هستم. چطور می‌تونم کمکت کنم؟")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    text = update.message.text.strip()
    
    # قابلیت "بخون" برای تبدیل متن ریپلای شده به صدا
    if text == "بخون" and update.message.reply_to_message:
        target_text = update.message.reply_to_message.text
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="record_voice")
        voice_file = await text_to_voice(target_text)
        if voice_file:
            await update.message.reply_voice(voice=open(voice_file, "rb"))
            os.remove(voice_file)
        else:
            await update.message.reply_text("خطا در تولید صدا. اعتبار ElevenLabs را چک کنید.")
        return

    # پاسخ معمولی با Gemini
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    response = await get_gemini_response(text)
    await update.message.reply_text(response)

# --- اجرای اصلی ---

if __name__ == '__main__':
    # اجرای فلاسک در یک ترد جداگانه
    Thread(target=run_flask).start()
    
    # اجرای ربات تلگرام
    application = ApplicationBuilder().token(TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    
    logging.info("Bot started...")
    application.run_polling()
