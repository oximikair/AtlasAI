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

# دیتابیس موقت برای وضعیت AI کاربران (در حافظه)
user_ai_enabled = {} 

LANG_MAP = {
    "انگلیسی": "en", "آلمانی": "de", "فرانسوی": "fr", "عربی": "ar",
    "ترکی": "tr", "اسپانیایی": "es", "روسی": "ru", "ایتالیایی": "it", "فارسی": "fa"
}

# --- تابع ترجمه ---
async def translate_text(text, target_code):
    try:
        async with httpx.AsyncClient() as client:
            url = f"https://api.mymemory.translated.net/get?q={text}&langpair=auto|{target_code}"
            resp = await client.get(url, timeout=10.0)
            data = resp.json()
            # اگر خطا داد یا زبان تکراری بود، Fallback به فارسی/انگلیسی
            if resp.status_code != 200 or "DISTINCT" in str(data):
                pair = f"fa|{target_code}" if target_code != "fa" else "en|fa"
                url = f"https://api.mymemory.translated.net/get?q={text}&langpair={pair}"
                resp = await client.get(url, timeout=10.0)
                data = resp.json()
            return data["responseData"]["translatedText"]
    except: return "⚠️ خطا در سرور ترجمه."

# --- تابع Gemini ---
async def get_ai_response(user_text):
    try:
        client = genai.Client(api_key=GEMINI_KEY)
        response = client.models.generate_content(model="gemini-2.0-flash", contents=user_text)
        return response.text if response.text else "پاسخی دریافت نشد."
    except Exception as e:
        if "429" in str(e): return "⏳ سهمیه Gemini تمام شد. از ترجمه استفاده کنید."
        return "❌ اطلس فعلاً پاسخگو نیست."

# --- دستور /ai ---
async def ai_toggle_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    # تغییر وضعیت (Toggle)
    is_on = user_ai_enabled.get(user_id, False)
    user_ai_enabled[user_id] = not is_on
    
    msg = "✅ هوش مصنوعی برای شما فعال شد." if user_ai_enabled[user_id] else "❌ هوش مصنوعی خاموش شد. فقط ترجمه انجام می‌دهم."
    await update.message.reply_text(msg)

# --- مدیریت پیام‌های متنی ---
async def handle_all_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text: return
    
    msg_text = update.message.text
    user_id = update.effective_user.id
    chat_type = update.message.chat.type
    bot_obj = await context.bot.get_me()

    # --- اولویت ۱: دستور ترجمه (در هر شرایطی) ---
    if "ترجمه" in msg_text:
        target_code, target_name = "fa", "فارسی"
        for k, v in LANG_MAP.items():
            if k in msg_text: target_code, target_name = v, k; break
        
        text_to_tr = ""
        if update.message.reply_to_message:
            text_to_tr = update.message.reply_to_message.text
        elif chat_type == "private":
            text_to_tr = msg_text.replace("ترجمه", "").replace(target_name, "").strip()
        
        if text_to_tr:
            await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
            res = await translate_text(text_to_tr, target_code)
            await update.message.reply_text(f"✨ ترجمه به {target_name}:\n\n{res}")
            return # توکن هدر نمی‌رود و چت تمام می‌شود

    # --- اولویت ۲: هوش مصنوعی (با فیلتر شدید) ---
    should_ai_work = False
    
    if chat_type == "private":
        # در پی‌وی فقط اگر خودِ کاربر با دستور /ai روشن کرده باشد
        if user_ai_enabled.get(user_id, False):
            should_ai_work = True
    else:
        # در گروه‌ها فقط با منشن یا ریپلای به بوت
        is_mentioned = f"@{bot_obj.username}" in msg_text
        is_reply_to_bot = (update.message.reply_to_message and update.message.reply_to_message.from_user.id == bot_obj.id)
        if is_mentioned or is_reply_to_bot:
            should_ai_work = True

    if should_ai_work:
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
        clean_text = msg_text.replace(f"@{bot_obj.username}", "").strip()
        reply = await get_ai_response(clean_text)
        await update.message.reply_text(reply)

# --- وب‌سرور و راه اندازی ---
app = Flask(__name__)
@app.route('/')
def health(): return "Atlas Online", 200

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

if __name__ == "__main__":
    Thread(target=run_flask, daemon=True).start()
    time.sleep(20)
    
    if BOT_TOKEN:
        application = Application.builder().token(BOT_TOKEN).build()
        
        # هندلر دستورات
        application.add_handler(CommandHandler("ai", ai_toggle_command))
        # هندلر تمام پیام‌های متنی
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_all_messages))
        
        application.run_polling(drop_pending_updates=True)
