import os
import logging
import asyncio
import time
import httpx
import re
from flask import Flask
from threading import Thread
from google import genai
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes

# تنظیمات لاگ برای مشاهده وضعیت در رندر
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# --- متغیرهای محیطی ---
BOT_TOKEN = os.environ.get("BOT_TOKEN")
GEMINI_KEY = os.environ.get("GEMINI_KEY")

# نقشه زبان‌ها برای تشخیص در متن کاربر
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
    """
    تابع ترجمه با قابلیت رفع خطای تشخیص زبان خودکار
    """
    try:
        async with httpx.AsyncClient() as client:
            # تلاش اول با تشخیص خودکار زبان
            url = f"https://api.mymemory.translated.net/get?q={text}&langpair=auto|{target_lang_code}"
            response = await client.get(url, timeout=10.0)
            data = response.json()
            
            # اگر سرور خطای زبان داد یا خروجی نامعتبر بود، فرض را بر انگلیسی می‌گذاریم
            if response.status_code != 200 or "INVALID SOURCE LANGUAGE" in str(data):
                logger.info("Auto-detect failed, retrying with English as source...")
                url = f"https://api.mymemory.translated.net/get?q={text}&langpair=en|{target_lang_code}"
                response = await client.get(url, timeout=10.0)
                data = response.json()
                
            return data["responseData"]["translatedText"]
    except Exception as e:
        logger.error(f"Translation Error: {e}")
        return "⚠️ متأسفانه مشکلی در ارتباط با سرور ترجمه پیش آمده."

async def get_ai_response(user_text):
    """
    اتصال به مدل Gemini با مدیریت خطای سهمیه
    """
    try:
        client = genai.Client(api_key=GEMINI_KEY)
        response = client.models.generate_content(model="gemini-2.0-flash", contents=user_text)
        return response.text if response.text else "پاسخی دریافت نشد."
    except Exception as e:
        error_msg = str(e)
        logger.error(f"AI Error: {error_msg}")
        if "429" in error_msg:
            return "⏳ سهمیه پیام‌های اطلس تمام شده. لطفاً دقایقی دیگر امتحان کنید یا از بخش 'ترجمه' استفاده کنید."
        return "❌ در حال حاضر امکان پاسخگویی وجود ندارد."

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text: return
    
    msg_text = update.message.text
    bot_obj = await context.bot.get_me()

    # --- منطق ترجمه ---
    if "ترجمه" in msg_text and update.message.reply_to_message:
        target_code = "fa"  # پیش‌فرض
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
            await update.message.reply_text(f"✨ ترجمه به {target_name}:\n\n{result}")
            return

    # --- منطق هوش مصنوعی (فقط گروه یا ریپلای به بوت) ---
    is_group = update.message.chat.type in ["group", "supergroup"]
    is_mentioned = f"@{bot_obj.username}" in msg_text
    is_reply_to_bot = (update.message.reply_to_message and update.message.reply_to_message.from_user.id == bot_obj.id)

    if is_group and not (is_mentioned or is_reply_to_bot):
        return

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    clean_text = msg_text.replace(f"@{bot_obj.username}", "").strip()
    reply = await get_ai_response(clean_text)
    await update.message.reply_text(reply)

# --- بخش وب‌سرور ---
app = Flask(__name__)
@app.route('/')
def health(): return "Atlas Bot is Running!", 200

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

# --- بخش اصلی اجرا ---
if __name__ == "__main__":
    # ۱. اجرای وب‌سرور در پس‌زمینه
    Thread(target=run_flask, daemon=True).start()
    
    # ۲. وقفه برای بسته شدن نشست‌های قبلی در رندر
    logger.info("Waiting 20 seconds for clean startup...")
    time.sleep(20)
    
    if BOT_TOKEN:
        application = Application.builder().token(BOT_TOKEN).build()
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        
        logger.info("Bot is starting polling...")
        application.run_polling(drop_pending_updates=True)
    else:
        logger.error("BOT_TOKEN not found!")
