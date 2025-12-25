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

# --- تنظیمات لاگ ---
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# --- متغیرهای سیستمی ---
BOT_TOKEN = os.environ.get("BOT_TOKEN")
GEMINI_KEY = os.environ.get("GEMINI_KEY")

# لیست زبان‌ها برای تشخیص در دستور ترجمه
LANG_MAP = {
    "انگلیسی": "en",
    "آلمانی": "de",
    "فرانسوی": "fr",
    "عربی": "ar",
    "ترکی": "tr",
    "اسپانیایی": "es",
    "روسی": "ru",
    "ایتالیایی": "it",
    "فارسی": "fa"
}

# --- بخش ترجمه (بدون نیاز به توکن) ---
async def translate_text(text, target_lang_code):
    try:
        async with httpx.AsyncClient() as client:
            # تلاش اول: تشخیص خودکار زبان مبدأ
            url = f"https://api.mymemory.translated.net/get?q={text}&langpair=auto|{target_lang_code}"
            response = await client.get(url, timeout=10.0)
            data = response.json()
            
            # اگر خطای زبان داد، فرض می‌کنیم متن ورودی انگلیسی است و دوباره تلاش می‌کنیم
            if response.status_code != 200 or "INVALID SOURCE LANGUAGE" in str(data):
                url = f"https://api.mymemory.translated.net/get?q={text}&langpair=en|{target_lang_code}"
                response = await client.get(url, timeout=10.0)
                data = response.json()
                
            return data["responseData"]["translatedText"]
    except Exception as e:
        logger.error(f"Translation Error: {e}")
        return "⚠️ متأسفانه مشکلی در سرور ترجمه پیش آمد."

# --- بخش هوش مصنوعی (Gemini) ---
async def get_ai_response(user_text):
    try:
        if not GEMINI_KEY: return "کلید API ست نشده است."
        client = genai.Client(api_key=GEMINI_KEY)
        response = client.models.generate_content(model="gemini-2.0-flash", contents=user_text)
        return response.text if response.text else "پاسخی دریافت نشد."
    except Exception as e:
        if "429" in str(e):
            return "⏳ سهمیه اطلس تمام شده. برای ترجمه، روی متن ریپلای کنید و بنویسید 'ترجمه'."
        return "❌ اطلس فعلاً در دسترس نیست."

# --- مدیریت پیام‌ها ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text: return
    
    msg_text = update.message.text
    bot_obj = await context.bot.get_me()

    # ۱. بررسی دستور ترجمه روی ریپلای (اولویت اول)
    if "ترجمه" in msg_text and update.message.reply_to_message:
        target_code = "fa" 
        target_name = "فارسی"
        
        for lang_name, lang_code in LANG_MAP.items():
            if lang_name in msg_text:
                target_code = lang_code
                target_name = lang_name
                break
        
        original_text = update.message.reply_to_message.text
        if original_text:
            await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
            result = await translate_text(original_text, target_code)
            await update.message.reply_text(f"✅ ترجمه به {target_name}:\n\n{result}")
            return # کار تمام است، سراغ هوش مصنوعی نمی‌رود

    # ۲. منطق هوش مصنوعی (فقط در صورت منشن یا ریپلای به بوت)
    is_group = update.message.chat.type in ["group", "supergroup"]
    is_mentioned = f"@{bot_obj.username}" in msg_text
    is_reply_to_bot = (update.message.reply_to_message and update.message.reply_to_message.from_user.id == bot_obj.id)

    if is_group and not (is_mentioned or is_reply_to_bot):
        return

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    clean_text = msg_text.replace(f"@{bot_obj.username}", "").strip()
    reply = await get_ai_response(clean_text)
    await update.message.reply_text(reply)

# --- وب‌سرور زنده نگهدار ---
app = Flask(__name__)
@app.route('/')
def health(): return "Atlas is Online!", 200

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

# --- اجرای نهایی ---
if __name__ == "__main__":
    Thread(target=run_flask, daemon=True).start()
    
    # وقفه ۲۰ ثانیه‌ای برای اطمینان از بسته شدن نسخه قبلی در Render
    logger.info("Starting up in 20 seconds...")
    time.sleep(20)
    
    if BOT_TOKEN:
        application = Application.builder().token(BOT_TOKEN).build()
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        
        logger.info("Atlas Bot is now polling...")
        application.run_polling(drop_pending_updates=True)
    else:
        logger.error("No BOT_TOKEN found in Environment Variables!")
