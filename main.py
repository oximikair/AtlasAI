import os
import logging
import asyncio
import time
import httpx
from flask import Flask
from threading import Thread
from google import genai
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# --- تنظیمات توکن‌ها ---
BOT_TOKEN = os.environ.get("BOT_TOKEN")
GEMINI_KEY = os.environ.get("GEMINI_KEY")

# لیست زبان‌ها برای تشخیص در پیام
LANG_MAP = {
    "انگلیسی": "en",
    "فارسی": "fa",
    "آلمانی": "de",
    "فرانسوی": "fr",
    "عربی": "ar",
    "ترکی": "tr",
    "اسپانیایی": "es",
    "روسی": "ru",
    "ایتالیایی": "it"
}

async def translate_text(text, target_lang_code):
    try:
        url = f"https://api.mymemory.translated.net/get?q={text}&langpair=auto|{target_lang_code}"
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=10.0)
            data = response.json()
            return data["responseData"]["translatedText"]
    except Exception as e:
        logger.error(f"Translation Error: {e}")
        return "متأسفانه در حال حاضر مشکلی در سرویس ترجمه وجود دارد."

async def get_ai_response(user_text):
    try:
        client = genai.Client(api_key=GEMINI_KEY)
        response = client.models.generate_content(model="gemini-2.0-flash", contents=user_text)
        return response.text if response.text else "متوجه نشدم."
    except Exception as e:
        logger.error(f"AI Error: {e}")
        return "اطلس در حال حاضر قادر به پاسخگویی نیست."

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text: return
    
    msg_text = update.message.text
    bot_obj = await context.bot.get_me()

    # --- بخش اول: قابلیت ترجمه هوشمند ---
    if "ترجمه" in msg_text and update.message.reply_to_message:
        target_code = "fa"  # پیش‌فرض فارسی
        target_name = "فارسی"
        
        # چک کردن اینکه آیا زبان خاصی مد نظر هست یا نه
        for lang_name, lang_code in LANG_MAP.items():
            if lang_name in msg_text:
                target_code = lang_code
                target_name = lang_name
                break
        
        text_to_tr = update.message.reply_to_message.text
        if text_to_tr:
            await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
            result = await translate_text(text_to_tr, target_code)
            await update.message.reply_text(f"✅ ترجمه به {target_name}:\n\n{result}")
            return

    # --- بخش دوم: منطق هوش مصنوعی (Gemini) ---
    is_group = update.message.chat.type in ["group", "supergroup"]
    is_mentioned = f"@{bot_obj.username}" in msg_text
    is_reply_to_bot = (update.message.reply_to_message and update.message.reply_to_message.from_user.id == bot_obj.id)

    if is_group and not (is_mentioned or is_reply_to_bot):
        return

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    clean_text = msg_text.replace(f"@{bot_obj.username}", "").strip()
    reply = await get_ai_response(clean_text)
    await update.message.reply_text(reply)

# --- وب‌سرور برای زنده نگه داشتن در Render ---
app = Flask(__name__)
@app.route('/')
def health(): return "OK", 200

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

if __name__ == "__main__":
    Thread(target=run_flask, daemon=True).start()
    time.sleep(20) # وقفه برای جلوگیری از Conflict
    
    if BOT_TOKEN:
        application = Application.builder().token(BOT_TOKEN).build()
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        application.run_polling(drop_pending_updates=True)
