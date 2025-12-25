import os
import logging
import threading
from datetime import datetime, timedelta
from flask import Flask

from dotenv import load_dotenv
from google import genai
from google.genai import types
from telegram import Update, ChatPermissions
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

load_dotenv()

# --- تنظیمات لاگ ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- بارگذاری فایل‌های کانفیگ ---
def load_json(filename):
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            import json
            return json.load(f)
    except:
        return {"persona_configs": {"default": {"prompt": ""}}, "user_personas": {}}

config = {"MUTE_DURATION": 60} # پیش‌فرض
personas = load_json('personas.json')
# تبدیل آیدی ادمین به لیست اعداد
ADMIN_IDS = [int(i.strip()) for i in os.getenv("ADMIN_USER_ID", "").split(',') if i.strip().isdigit()]

# --- تنظیمات Gemini ---
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# --- سرور Flask برای Render ---
app = Flask(__name__)
@app.route('/')
def home(): return "Bot is Alive!"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

# --- تابع اصلی تعامل ---
async def handle_interaction(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # جلوگیری از خطای NoneType: فقط اگر پیام حاوی متن بود ادامه بده
    if not update.message or not update.message.text:
        return

    user_id = update.effective_user.id
    text = update.message.text
    chat_id = update.effective_chat.id

    # ۱. بخش مدیریت (سکوت کردن)
    if update.message.reply_to_message and user_id in ADMIN_IDS:
        if any(word in text for word in ["سکوت", "خفه", "mute"]):
            target_user = update.message.reply_to_message.from_user
            until = datetime.now() + timedelta(minutes=config.get('MUTE_DURATION', 60))
            try:
                await context.bot.restrict_chat_member(
                    chat_id=chat_id,
                    user_id=target_user.id,
                    permissions=ChatPermissions(can_send_messages=False),
                    until_date=until
                )
                await update.message.reply_text(f"🤐 کاربر {target_user.first_name} سایلنت شد.")
                return 
            except Exception as e:
                logger.error(f"Mute Error: {e}")

    # ۲. بخش هوش مصنوعی Gemini
    user_id_str = str(user_id)
    persona_key = personas.get("user_personas", {}).get(user_id_str, "default")
    persona_prompt = personas.get("persona_configs", {}).get(persona_key, {}).get("prompt", "")

    try:
        # اصلاح شده: نام مدل بدون کلمه models/
        response = client.models.generate_content(
            model="gemini-1.5-flash", 
            config=types.GenerateContentConfig(system_instruction=persona_prompt),
            contents=[text]
        )
        if response.text:
            await update.message.reply_text(response.text)
    except Exception as e:
        logger.error(f"AI Error: {e}")
        # اگر خطا 404 بود، احتمالا بخاطر ورژن API است که اینجا مدیریت می‌شود

def main():
    threading.Thread(target=run_flask, daemon=True).start()

    application = Application.builder().token(os.getenv("BOT_TOKEN")).build()
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_interaction))
    
    print("--- ربات با موفقیت در حالت ترکیبی اجرا شد ---")

    application.run_polling(drop_pending_updates=True, close_loop=True)

if __name__ == "__main__":
    main()

