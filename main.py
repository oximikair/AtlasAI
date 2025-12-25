import os
import logging
import httpx
import google.generativeai as genai
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters

# ================= تنظیمات کلیدها (جایگزین کن) =================
ELEVEN_KEY = "کلید_ای_پی_آی_یازده_لبز" 
GEMINI_KEY = "کلید_ای_پی_آی_جمنای"
BOT_TOKEN = "توکن_ربات_تلگرام"
# ==========================================================

# تنظیمات هوش مصنوعی جمنای
genai.configure(api_key=GEMINI_KEY)
# استفاده از مدل فلش برای سرعت بیشتر و ارور کمتر
model = genai.GenerativeModel("gemini-1.5-flash")

# تنظیمات لاگ برای مشاهده در کنسول رندر
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    
    # مرحله ۱: ترجمه و پاسخ توسط جمنای
    # به جمنای دستور می‌دهیم که زبان را تشخیص دهد و ترجمه کند
    prompt = (
        f"You are Atlas, a polyglot assistant. Translate the following text to the requested language. "
        f"If the user didn't specify a language, translate it to English. "
        f"Only return the translated text itself, no extra words: {user_text}"
    )
    
    try:
        await update.message.chat.send_action("typing")
        response = model.generate_content(prompt)
        translated_text = response.text.strip()
    except Exception as e:
        print(f"❌ GEMINI ERROR: {str(e)}")
        await update.message.reply_text("مشکلی در جمنای پیش آمد. لاگ را چک کنید.")
        return

    # ارسال متن ترجمه شده به کاربر
    await update.message.reply_text(f"✨ {translated_text}")

    # مرحله ۲: تبدیل متن به صدا با ElevenLabs
    url = "https://api.elevenlabs.io/v1/text-to-speech/21m00Tcm4lS96DGzAsAn"
    headers = {
        "Accept": "audio/mpeg",
        "Content-Type": "application/json",
        "xi-api-key": ELEVEN_KEY
    }
    payload = {
        "text": translated_text,
        "model_id": "eleven_multilingual_v2", # پشتیبانی از تمام زبان‌ها
        "voice_settings": {"stability": 0.5, "similarity_boost": 0.75}
    }

    try:
        await update.message.chat.send_action("record_voice")
        async with httpx.AsyncClient() as client:
            res = await client.post(url, json=payload, headers=headers, timeout=30)
            
            if res.status_code == 200:
                with open("voice.mp3", "wb") as f:
                    f.write(res.content)
                await update.message.reply_voice(voice=open("voice.mp3", "rb"))
            else:
                print(f"❌ ELEVENLABS ERROR {res.status_code}: {res.text}")
    except Exception as e:
        print(f"❌ VOICE GENERATION ERROR: {str(e)}")

if __name__ == '__main__':
    print("🚀 Atlas Bot is starting...")
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    app.run_polling()
