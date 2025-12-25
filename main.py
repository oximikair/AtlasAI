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

# --- متغیرهای محیطی ---
BOT_TOKEN = os.environ.get("BOT_TOKEN")
GEMINI_KEY = os.environ.get("GEMINI_KEY")

# نقشه زبان‌ها برای تشخیص هوشمند مقصد
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

# --- تابع ترجمه فوق‌هوشمند (بدون توکن) ---
async def translate_text(text, target_lang_code):
    try:
        async with httpx.AsyncClient() as client:
            # گام ۱: تلاش با تشخیص خودکار (Auto) برای پوشش همه زبان‌ها (روسی، چینی و...)
            url = f"https://api.mymemory.translated.net/get?q={text}&langpair=auto|{target_lang_code}"
            response = await client.get(url, timeout=10.0)
            data = response.json()
            
            error_details = str(data.get("responseDetails", "")).upper()
            status = data.get("responseStatus")

            # گام ۲: اگر زبان مبدأ و مقصد یکی بود (مثلاً انگلیسی به انگلیسی)
            if "DISTINCT LANGUAGES" in error_details:
                return f"این متن در حال حاضر به زبان مورد نظر ({target_lang_code}) است."

            # گام ۳: اگر سیستم گیج شد (برای متن‌های خیلی کوتاه مثل 'میکا')
            if status != 200 or "INVALID SOURCE" in error_details:
                # Fallback: اگر هدف فارسی نیست، فرض می‌کنیم مبدأ فارسی است و برعکس
                pair = f"fa|{target_lang_code}" if target_lang_code != "fa" else "en|fa"
                logger.info(f"Auto-detect failed. Using fallback: {pair}")
                url = f"https://api.mymemory.translated.net/get?q={text}&langpair={pair}"
                response = await client.get(url, timeout=10.0)
                data = response.json()

            return data["responseData"]["translatedText"]
    except Exception as e:
        logger.error(f"Translation Error: {e}")
        return "⚠️ مشکلی در ارتباط با سرور ترجمه پیش آمد."

# --- تابع هوش مصنوعی Gemini ---
async def get_ai_response(user_text):
    try:
        if not GEMINI_KEY: return "کلید API یافت نشد."
        client = genai.Client(api_key=GEMINI_KEY)
        response = client.models.generate_content(model="gemini-2.0-flash", contents=user_text)
        return response.text if response.text else "پاسخی دریافت نشد."
    except Exception as e:
        if "429" in str(e):
            return "⏳ سهمیه هوش مصنوعی تمام شده. اما بخش 'ترجمه' فعال است! روی متن ریپلای کنید و بنویسید 'ترجمه'."
        return "❌ سرویس اطلس موقتاً در دسترس نیست."

# --- هندلر اصلی پیام‌ها ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text: return
    
    msg_text = update.message.text
    bot_obj = await context.bot.get_me()

    # ۱. اولویت اول: بررسی دستور ترجمه روی ریپلای
    if "ترجمه" in msg_text and update.message.reply_to_message:
        target_code = "fa" # پیش‌فرض فارسی
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
            return # خروج فوری برای جلوگیری از مصرف سهمیه Gemini

    # ۲. اولویت دوم: هوش مصنوعی (فقط با منشن یا ریپلای به بوت)
    is_group = update.message.chat.type in ["group", "supergroup"]
    is_mentioned = f"@{bot_obj.username}" in msg_text
    is_reply_to_bot = (update.message.reply_to_message and update.message.reply_to_message.from_user.id == bot_obj.id)

    if is_group and not (is_mentioned or is_reply_to_bot):
        return

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    clean_text = msg_text.replace(f"@{bot_obj.username}", "").strip()
    reply = await get_ai_response(clean_text)
    await update.message.reply_text(reply)

# --- تنظیمات سرور رندر ---
app = Flask(__name__)
@app.route('/')
def health(): return "Atlas is Online", 200

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

if __name__ == "__main__":
    Thread(target=run_flask, daemon=True).start()
    
    # وقفه ۲۰ ثانیه‌ای برای پایداری در رندر
    logger.info("Initializing Atlas... Please wait.")
    time.sleep(20)
    
    if BOT_TOKEN:
        application = Application.builder().token(BOT_TOKEN).build()
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        
        logger.info("Polling started successfully.")
        application.run_polling(drop_pending_updates=True)
