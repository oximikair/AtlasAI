import os
import logging
import asyncio
import json
import threading
from datetime import datetime, timedelta
from flask import Flask

from dotenv import load_dotenv
from google import genai
from google.genai import types
from telegram import Update, ChatPermissions
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

load_dotenv()

# --- تنظیمات لاگ و بارگذاری فایل‌ها ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def load_json(filename):
    with open(filename, 'r', encoding='utf-8') as f:
        return json.load(f)

# بارگذاری تنظیمات از فایل‌های ارسالی شما 
config = load_json('bot_config.json')
personas = load_json('personas.json')
ADMIN_IDS = [int(i.strip()) for i in os.getenv("ADMIN_USER_ID", "").split(',') if i.strip().isdigit()]

# --- تنظیمات Gemini ---
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# --- سرور Flask برای بیدار نگه داشتن ربات در Render ---
app = Flask(__name__)
@app.route('/')
def home(): return "Bot is Online and Interactive!"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

# --- تابع مدیریت و تعامل (ترکیبی) ---
async def handle_interaction(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text
    chat_id = update.effective_chat.id

    # ۱. بررسی دستورات مدیریتی (اگر ریپلای شده باشد و کاربر ادمین باشد)
    if update.message.reply_to_message and user_id in ADMIN_IDS:
        target_user = update.message.reply_to_message.from_user
        
        if any(word in text for word in ["سکوت", "خفه", "mute", "سایلنت"]):
            # استفاده از زمان MUTE_DURATION از فایل کانفیگ 
            duration = config.get('MUTE_DURATION', 60)
            until = datetime.now() + timedelta(minutes=duration)
            
            try:
                await context.bot.restrict_chat_member(
                    chat_id=chat_id,
                    user_id=target_user.id,
                    permissions=ChatPermissions(can_send_messages=False),
                    until_date=until
                )
                await update.message.reply_text(f"✅ اطاعت قربان! {target_user.first_name} برای {duration} دقیقه سایلنت شد.")
                return # دستور اجرا شد، سراغ هوش مصنوعی نمی‌رویم
            except Exception as e:
                logger.error(f"Error in Mute: {e}")

    # ۲. بخش هوش مصنوعی (اگر دستور مدیریتی نبود)
    user_id_str = str(user_id)
    # پیدا کردن پرسونا بر اساس یوزر آیدی از فایل personas.json 
    persona_key = personas["user_personas"].get(user_id_str, "default")
    persona_info = personas["persona_configs"].get(persona_key, personas["persona_configs"]["default"])
    
    try:
        # ارسال متن به جیمینای با دستورالعمل سیستمی مخصوص کاربر 
        response = client.models.generate_content(
            model="gemini-1.5-flash",
            config=types.GenerateContentConfig(system_instruction=persona_info['prompt']),
            contents=[text]
        )
        await update.message.reply_text(response.text)
    except Exception as e:
        logger.error(f"AI Error: {e}")

def main():
    # اجرای وب‌سرور در پس‌زمینه
    threading.Thread(target=run_flask, daemon=True).start()

    application = Application.builder().token(os.getenv("BOT_TOKEN")).build()
    
    # مدیریت تمام پیام‌های متنی
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_interaction))
    
    # دستور استارت
    application.add_handler(CommandHandler("start", lambda u, c: u.message.reply_text("ربات ترکیبی (ادمین + هوش مصنوعی) فعال است!")))

    application.run_polling()

if __name__ == "__main__":
    main()