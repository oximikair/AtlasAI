import os
import logging
import httpx
import google.generativeai as genai
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters

# ================= تنظیمات کلیدها (دریافت از رندر) =================
# حتماً این ۳ کلید را در بخش Environment Variables رندر وارد کنید
ELEVEN_KEY = os.getenv("ELEVEN_KEY")
GEMINI_KEY = os.getenv("GEMINI_KEY")
BOT_TOKEN = os.getenv("BOT_TOKEN")
# ==========================================================

# تنظیمات هوش مصنوعی جمنای
genai.configure(api_key=GEMINI_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")

# تنظیمات لاگ برای مشاهده در پنل رندر
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    if not user_text: return

    # مرحله ۱: ترجمه هوشمند توسط جمنای
    prompt = (
        f"You are a professional polyglot translator. Translate the input text based on these rules:\n"
        f"1. If the user specifies a language (e.g. 'سلام به ایتالیایی'), translate to that language.\n"
        f"2. If no language is specified, translate to English.\n"
        f"3. Return ONLY the translated text without any explanations.\n"
        f"Input: {user_text}"
    )
    
    try:
        await update.message.chat.send_action("typing")
        response = model.generate_content(prompt)
        translated_text = response.text.strip()
        
        # ارسال متن ترجمه شده به کاربر
        await update.message.reply_text(f"✨ {translated_text}")
    except Exception as e:
        logging.error(f"GEMINI ERROR: {str(e)}")
        await update.message.reply_text("❌ خطا در ترجمه توسط جمنای.")
        return

    # مرحله ۲: تبدیل متن به صدا با ElevenLabs
    # آیدی صدای Rachel که چندزبانه است
    voice_id = "21m00Tcm4lS96DGzAsAn" 
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
    
    headers = {
        "Accept": "audio/mpeg",
        "Content-Type": "application/json",
        "xi-api-key": ELEVEN_KEY
    }
    
    payload = {
        "text": translated_text,
        "model_id": "eleven_multilingual_v2",
        "voice_settings": {
            "stability": 0.5,
            "similarity_boost": 0.8
        }
    }

    try:
        await update.message.chat.send_action("record_voice")
        async with httpx.AsyncClient() as client:
            res = await client.post(url, json=payload, headers=headers, timeout=30)
            
            if res.status_code == 200:
                voice_path = "voice.mp3"
                with open(voice_path, "wb") as f:
                    f.write(res.content)
                await update.message.reply_voice(voice=open(voice_path, "rb"))
            elif res.status_code == 401:
                await update.message.reply_text("❌ خطای ElevenLabs: کلید API معتبر نیست.")
            elif res.status_code == 429:
                await update.message.reply_text("❌ خطای ElevenLabs: سهمیه کاراکتر شما تمام شده است.")
            else:
                logging.error(f"ELEVENLABS ERROR {res.status_code}: {res.text}")
                await update.message.reply_text(f"❌ خطا در تولید صدا (کد {res.status_code})")
    except Exception as e:
        logging.error(f"VOICE GENERATION ERROR: {str(e)}")

if __name__ == '__main__':
    if not all([ELEVEN_KEY, GEMINI_KEY, BOT_TOKEN]):
        print("❌ ERROR: One or more Environment Variables are missing!")
    else:
        print("🚀 Atlas Bot is starting...")
        app = ApplicationBuilder().token(BOT_TOKEN).build()
        app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
        app.run_polling()
