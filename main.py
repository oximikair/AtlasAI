import os, logging, asyncio, time, httpx
from flask import Flask
from threading import Thread
from google import genai
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes, CommandHandler

# --- تنظیمات لاگ ---
logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# --- متغیرها ---
BOT_TOKEN = os.environ.get("BOT_TOKEN")
GEMINI_KEY = os.environ.get("GEMINI_KEY")

# حافظه وضعیت AI (در اجراهای طولانی رندر، این ریست می‌شود - برای دائمی شدن دیتابیس لازم است)
user_ai_enabled = {} 

LANG_MAP = {
    "انگلیسی": "en", "آلمانی": "de", "فرانسوی": "fr", "عربی": "ar",
    "ترکی": "tr", "اسپانیایی": "es", "روسی": "ru", "ایتالیایی": "it", "فارسی": "fa"
}

# --- تابع ترجمه گوگل (دقیق و بدون نیاز به کلید) ---
async def translate_text(text, target_code):
    try:
        url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl=auto&tl={target_code}&dt=t&q={text}"
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, timeout=10.0)
            if resp.status_code == 200:
                data = resp.json()
                # چسباندن بخش‌های مختلف متن ترجمه شده
                translated = "".join([part[0] for part in data[0] if part[0]])
                return translated
            return "⚠️ سرویس گوگل پاسخگو نبود."
    except Exception as e:
        logger.error(f"Translation Error: {e}")
        return "⚠️ خطا در عملیات ترجمه."

# --- تابع Gemini ---
async def get_ai_response(user_text):
    try:
        client = genai.Client(api_key=GEMINI_KEY)
        response = client.models.generate_content(model="gemini-2.0-flash", contents=user_text)
        return response.text if response.text else "پاسخی دریافت نشد."
    except Exception as e:
        if "429" in str(e): return "⏳ سهمیه هوش مصنوعی تمام شده."
        return "❌ اطلس فعلاً در دسترس نیست."

# --- دستور /ai (روشن و خاموش کردن) ---
async def ai_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    is_on = user_ai_enabled.get(user_id, False)
    user_ai_enabled[user_id] = not is_on
    
    msg = "✅ هوش مصنوعی فعال شد." if user_ai_enabled[user_id] else "❌ هوش مصنوعی خاموش شد. (فقط ترجمه فعال است)"
    await update.message.reply_text(msg)

# --- مدیریت اصلی پیام‌ها ---
async def handle_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text: return
    
    msg_text = update.message.text
    user_id = update.effective_user.id
    chat_type = update.message.chat.type
    bot_obj = await context.bot.get_me()

    # ۱. بخش ترجمه (اولویت مطلق)
    if "ترجمه" in msg_text:
        target_code, target_name = "fa", "فارسی"
        for k, v in LANG_MAP.items():
            if k in msg_text:
                target_code, target_name = v, k
                break
        
        text_to_tr = ""
        # اگر ریپلای بود، متن ریپلای را ترجمه کن
        if update.message.reply_to_message:
            text_to_tr = update.message.reply_to_message.text
        # اگر در پی‌وی بود و ریپلای نبود، کل متن را (بدون کلمه ترجمه) ترجمه کن
        elif chat_type == "private":
            text_to_tr = msg_text.replace("ترجمه", "").replace(target_name, "").strip()
        
        if text_to_tr:
            await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
            res = await translate_text(text_to_tr, target_code)
            await update.message.reply_text(f"🌐 **Google Translate ({target_name}):**\n\n{res}", parse_mode="Markdown")
            return 

    # ۲. بخش هوش مصنوعی (فقط اگر روشن باشد یا در گروه منشن شود)
    should_ai = False
    if chat_type == "private":
        if user_ai_enabled.get(user_id, False):
            should_ai = True
    else:
        # در گروه: منشن یا ریپلای به بوت
        is_mentioned = f"@{bot_obj.username}" in msg_text
        is_reply_to_bot = (update.message.reply_to_message and update.message.reply_to_message.from_user.id == bot_obj.id)
        if is_mentioned or is_reply_to_bot:
            should_ai = True

    if should_ai:
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
        clean_text = msg_text.replace(f"@{bot_obj.username}", "").strip()
        reply = await get_ai_response(clean_text)
        await update.message.reply_text(reply)

# --- وب‌سرور ---
app = Flask(__name__)
@app.route('/')
def health(): return "Atlas Status: Perfect", 200

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

if __name__ == "__main__":
    Thread(target=run_flask, daemon=True).start()
    time.sleep(20) # وقفه برای پایداری رندر
    
    if BOT_TOKEN:
        application = Application.builder().token(BOT_TOKEN).build()
        application.add_handler(CommandHandler("ai", ai_toggle))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_all))
        
        logger.info("Atlas is running...")
        application.run_polling(drop_pending_updates=True)
