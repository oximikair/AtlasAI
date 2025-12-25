import os
import logging
import asyncio
import httpx
from flask import Flask
from threading import Thread
from google import genai
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

# --- تنظیمات لاگ برای عیب‌یابی ---
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# --- متغیرهای محیطی (از پنل Render خوانده می‌شوند) ---
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GENAI_API_KEY = os.getenv("GENAI_API_KEY")
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
VOICE_ID = "21m00Tcm4lS96DGzAsAn" # آی‌دی صدا (قابل تغییر)

# --- مقداردهی جمن‌آی با مدیریت خطا ---
try:
    if GENAI_API_KEY:
        client = genai.Client(api_key=GENAI_API_KEY)
        logging.info("Gemini Client initialized successfully.")
    else:
        client = None
        logging.warning("GENAI_API_KEY missing! Gemini features won't work.")
except Exception as e:
    client = None
    logging.error(f"Failed to init Gemini: {e}")

# --- وب‌سرور برای زنده نگه داشتن بات در Render ---
app = Flask(__name__)

@app.route('/')
def home():
    return "Atlas AI is running smoothly!"

def run_flask():
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)

# --- بخش هوش مصنوعی و صدا ---

async def get_gemini_response(prompt):
    if not client:
        return "⚠️ کلید Gemini در تنظیمات رندر وارد نشده است."
    try:
        # مدل جدید و پرسرعت
        response = client.models.generate_content(model="gemini-2.0-flash", contents=prompt)
        return response.text
    except Exception as e:
        logging.error(f"Gemini Error: {e}")
        return "❌ خطا در برقراری ارتباط با هوش مصنوعی."

async def text_to_voice(text):
    if not ELEVENLABS_API_KEY:
        logging.error("ElevenLabs API Key is missing!")
        return None
    
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}"
    headers = {
        "Accept": "audio/mpeg",
        "Content-Type": "application/json",
        "xi-api-key": ELEVENLABS_API_KEY
    }
    # ارسال حداکثر ۱۰۰۰ کاراکتر برای صرفه‌جویی در سهمیه
    data = {
        "text": text[:1000],
        "model_id": "eleven_multilingual_v2",
        "voice_settings": {"stability": 0.5, "similarity_boost": 0.75}
    }
    
    async with httpx.AsyncClient(timeout=45.0) as http_client:
        try:
            response = await http_client.post(url, json=data, headers=headers)
            if response.status_code == 200:
                file_path = "voice.mp3"
                with open(file_path, "wb") as f:
                    f.write(response.content)
                return file_path
            else:
                logging.error(f"ElevenLabs Error {response.status_code}: {response.text}")
                return None
        except Exception as e:
            logging.error(f"ElevenLabs Connection Failed: {e}")
            return None

# --- هندلرهای تلگرام ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_text = (
        "سلام! من اطلس هستم. 🤖\n\n"
        "🔹 سوالت رو بپرس تا جواب بدم.\n"
        "🔹 روی یک متن ریپلای کن و بنویس 'بخون' تا صوتیش کنم."
    )
    await update.message.reply_text(welcome_text)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    user_text = update.message.text.strip()
    
    # قابلیت تبدیل به صدا (Voice)
    if user_text == "بخون" and update.message.reply_to_message:
        target_text = update.message.reply_to_message.text
        if not target_text:
            await update.message.reply_text("متنی برای خواندن پیدا نکردم.")
            return

        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="record_voice")
        path = await text_to_voice(target_text)
        
        if path:
            with open(path, "rb") as voice_file:
                await update.message.reply_voice(voice=voice_file)
            os.remove(path)
        else:
            await update.message.reply_text("❌ خطا در تولید صدا. (ممکن است سهمیه ElevenLabs تمام شده باشد)")
        return

    # پاسخ متنی هوش مصنوعی
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    answer = await get_gemini_response(user_text)
    await update.message.reply_text(answer)

# --- اجرای نهایی ---

if __name__ == '__main__':
    # راه اندازی وب‌سرور در پس‌زمینه
    Thread(target=run_flask, daemon=True).start()
    
    # راه اندازی بات تلگرام
    if not TOKEN:
        logging.critical("CRITICAL ERROR: TELEGRAM_BOT_TOKEN is not set!")
    else:
        app_bot = ApplicationBuilder().token(TOKEN).build()
        app_bot.add_handler(CommandHandler("start", start))
        app_bot.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
        
        logging.info("Atlas AI Bot is starting...")
        app_bot.run_polling()
