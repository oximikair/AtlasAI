import os
import logging
import httpx
import google.generativeai as genai
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters

# --- تنظیمات کلیدها (حتماً جایگزین کن) ---
ELEVEN_KEY = "اینجا_کلید_ای_پی_آی_خودت_را_بنویس" 
GEMINI_KEY = "اینجا_کلید_جمنای_خودت_را_بنویس"
BOT_TOKEN = "اینجا_توکن_ربات_تلگرامت_را_بنویس"

# تنظیمات مدل‌ها
genai.configure(api_key=GEMINI_KEY)
gemini_model = genai.GenerativeModel("gemini-1.5-flash")

# تنظیمات لاگ برای دیدن جزئیات در رندر
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

async def translate_and_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    
    # ۱. پردازش توسط جمنای (ترجمه به هر زبانی که کاربر بخواهد)
    prompt = f"Translate the following text to the requested language. If no language is specified, translate it to English. Only return the translated text: {user_text}"
    
    try:
        response = gemini_model.generate_content(prompt)
        translated_text = response.text.strip()
    except Exception as e:
        print(f"❌ Gemini Error: {e}")
        await update.message.reply_text("خطا در ارتباط با هوش مصنوعی (Gemini)")
        return

    await update.message.reply_text(f"✨ ترجمه: \n{translated_text}")

    # ۲. تولید وویس با ElevenLabs
    url = "https://api.elevenlabs.io/v1/text-to-speech/21m00Tcm4lS96DGzAsAn"
    headers = {
        "Accept": "audio/mpeg",
        "Content-Type": "application/json",
        "xi-api-key": ELEVEN_KEY
    }
    data = {
        "text": translated_text,
        "model_id": "eleven_multilingual_v2", # پشتیبانی از تمام زبان‌ها
        "voice_settings": {"stability": 0.5, "similarity_boost": 0.75}
    }

    try:
        await update.message.chat.send_action("record_voice")
        async with httpx.AsyncClient() as client:
            res = await client.post(url, json=data, headers=headers, timeout=30)
            if res.status_code == 200:
                with open("output.mp3", "wb") as f:
                    f.write(res.content)
                await update.message.reply_voice(voice=open("output.mp3", "rb"))
            else:
                print(f"❌ ElevenLabs Error {res.status_code}: {res.text}")
    except Exception as e:
        print(f"❌ Voice Error: {e}")

# --- اجرای ربات ---
if __name__ == '__main__':
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), translate_and_voice))
    print("Atlas Bot is running...")
    app.run_polling()
