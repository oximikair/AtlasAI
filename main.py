import os
import logging
import asyncio
import time
import httpx
from flask import Flask
from threading import Thread
from google import genai
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes, CommandHandler

# --- تنظیمات لاگ ---
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# --- متغیرهای محیطی ---
BOT_TOKEN = os.environ.get("BOT_TOKEN")
GEMINI_KEY = os.environ.get("GEMINI_KEY")

LANG_MAP = {
    "انگلیسی": "en", "آلمانی": "de", "فرانسوی": "fr", "عربی": "ar",
    "ترکی": "tr", "اسپانیایی": "es", "روسی": "ru", "ایتالیایی": "it", "فارسی": "fa"
}

# حافظه موقت برای وضعیت AI کاربران در پی‌وی
user_ai_status = {}

# --- تابع ترجمه هوشمند ---
async def translate_text(text, target_lang_code):
    try:
        async with httpx.AsyncClient() as client:
            url = f"https://api.mymemory.translated.net/get?q={text}&langpair=auto|{target_lang_code}"
            response = await client.get(url, timeout=10.0)
            data = response.json()
            if "DISTINCT LANGUAGES" in str(data.get("responseDetails", "")):
                return f"این متن در حال حاضر به زبان {target_lang_code} است."
            if data.get("responseStatus") != 200:
                pair = f"fa|{target_lang_code}" if target_lang_code != "fa" else "en|fa"
                url = f"https://api.mymemory.translated.net/get?q={text}&langpair={pair}"
                response = await client.get(url, timeout=10.0)
                data = response.json()
            return data["responseData"]["translatedText"]
    except: return "⚠️ خطا در سرور ترجمه."

# --- تابع Gemini ---
async def get_ai_response(user_text):
    try:
        client = genai.Client(api_key=GEMINI_KEY)
        response = client.models.generate_content(model="gemini-2.0-flash", contents=user_text)
        return response.text if response.text else "پاسخی دریافت نشد."
    except Exception as e:
        if "429" in str(e): return "⏳ سهمیه AI تمام شده."
        return "❌ خطا در اتصال به هوش مصنوعی."

# --- دستور فعال/غیرفعال کردن AI در پی‌وی ---
async def toggle_ai(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    current_status = user_ai_status.get(user_id, False)
    user_ai_status[user_id] = not current_status
    
    status_text = "✅ هوش مصنوعی در پی‌وی فعال شد." if user_ai_status[user_id] else "❌ هوش مصنوعی در پی‌وی غیرفعال شد. حالا فقط ترجمه انجام می‌دهم."
    await update.message.reply_text(status_text)

# --- هندلر اصلی پیام‌ها ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text: return
    
    msg_text = update.message.text
    user_id = update.effective_user.id
    is_private = update.message.chat.type == "private"
    bot_obj = await context.bot.get_me()

    # ۱. اولویت اول: ترجمه (همیشه و همه جا کار می‌کند)
    if "ترجمه" in msg_text:
        target_code, target_name = "fa", "فارسی"
        for k, v in LANG_MAP.items():
            if k in msg_text: target_code, target_name = v, k; break
        
        text_to_tr = ""
        if update.message.reply_to_message:
            text_to_tr = update.message.reply_to_message.text
        elif is_private:
            text_to_tr = msg_text.replace("ترجمه", "").replace(target_name, "").strip()
        
        if text_to_tr:
            await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
            res = await translate_text(text_to_tr, target_code)
            await update.message.reply_text(f"✨ ترجمه به {target_name}:\n\n{res}")
            return

    # ۲. اولویت دوم: هوش مصنوعی
    should_respond_ai = False
    
    if is_private:
        # در پی‌وی فقط اگر قبلاً با دستور /ai فعال شده باشد
        if user_ai_status.get(user_id, False):
            should_respond_ai = True
    else:
        # در گروه فقط با منشن یا ریپلای به بوت
        is_mentioned = f"@{bot_obj.username}" in msg_text
        is_reply_to_bot = (update.message.reply_to_message and update.message.reply_to_message.from_user.id == bot_obj.id)
        if is_mentioned or is_reply_to_bot:
            should_respond_ai = True

    if should_respond_ai:
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
        clean_text = msg_text.replace(f"@{bot_obj.username}", "").strip()
        reply = await get_ai_response(clean_text)
        await update.message.reply_text(reply)

# --- وب‌سرور و اجرا ---
app = Flask(__name__)
@app.route('/')
def health(): return "OK", 200

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

if __name__ == "__main__":
    Thread(target=run_flask, daemon=True).start()
    time.sleep(20)
    
    if BOT_TOKEN:
        application = Application.builder().token(BOT_TOKEN).build()
        # اضافه کردن دستور /ai برای کنترل در پی‌وی
        application.add_handler(CommandHandler("ai", toggle_ai))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        application.run_polling(drop_pending_updates=True)
