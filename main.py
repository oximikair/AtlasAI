import os, logging, asyncio, time, httpx
from flask import Flask
from threading import Thread
from google import genai
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes, CommandHandler

# --- تنظیمات لاگ ---
logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# --- متغیرهای محیطی ---
BOT_TOKEN = os.environ.get("BOT_TOKEN")
GEMINI_KEY = os.environ.get("GEMINI_KEY")
ELEVEN_KEY = os.environ.get("ELEVENLABS_KEY")
VOICE_ID = "21m00Tcm4lS96DGzAsAn" # صدای باکیفیت Bella

user_ai_enabled = {} 
LANG_MAP = {"انگلیسی": "en", "آلمانی": "de", "فرانسوی": "fr", "عربی": "ar", "ترکی": "tr", "روسی": "ru", "فارسی": "fa"}

# --- تابع تبدیل متن به صدا (ElevenLabs) ---
async def text_to_voice(text):
    if not ELEVEN_KEY: return None
    try:
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}"
        headers = {"xi-api-key": ELEVEN_KEY, "Content-Type": "application/json"}
        data = {
            "text": text,
            "model_id": "eleven_multilingual_v2",
            "voice_settings": {"stability": 0.5, "similarity_boost": 0.75}
        }
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, json=data, timeout=30.0)
            if resp.status_code == 200:
                file_path = "voice.ogg"
                with open(file_path, "wb") as f:
                    f.write(resp.content)
                return file_path
        return None
    except Exception as e:
        logger.error(f"TTS Error: {e}")
        return None

# --- تابع ترجمه گوگل ---
async def translate_text(text, target_code):
    try:
        url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl=auto&tl={target_code}&dt=t&q={text}"
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, timeout=10.0)
            data = resp.json()
            return "".join([part[0] for part in data[0] if part[0]])
    except: return "⚠️ خطا در ترجمه."

# --- تابع هوش مصنوعی Gemini ---
async def get_ai_response(user_text):
    try:
        client = genai.Client(api_key=GEMINI_KEY)
        response = client.models.generate_content(model="gemini-2.0-flash", contents=user_text)
        return response.text if response.text else "پاسخی دریافت نشد."
    except Exception as e:
        if "429" in str(e): return "⏳ سهمیه هوش مصنوعی تمام شده."
        return "❌ اطلس فعلاً در دسترس نیست."

# --- دستور /ai (فقط پی‌وی) ---
async def ai_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.chat.type != "private":
        await update.message.reply_text("❌ این دستور فقط در پی‌وی کار می‌کند.")
        return
    user_id = update.effective_user.id
    is_on = user_ai_enabled.get(user_id, False)
    user_ai_enabled[user_id] = not is_on
    msg = "✅ هوش مصنوعی فعال شد." if user_ai_enabled[user_id] else "❌ هوش مصنوعی خاموش شد."
    await update.message.reply_text(msg)

# --- مدیریت اصلی پیام‌ها ---
async def handle_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text: return
    msg_text = update.message.text.strip()
    chat_type = update.message.chat.type
    bot_obj = await context.bot.get_me()

    # ۱. قابلیت "بخون" (برای همه اعضا با ریپلای)
    if msg_text == "بخون":
        if update.message.reply_to_message and update.message.reply_to_message.text:
            text_to_read = update.message.reply_to_message.text
            if len(text_to_read) > 1000:
                await update.message.reply_text("⚠️ متن طولانی است! (حداکثر ۱۰۰۰ کاراکتر)")
                return
            await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="record_voice")
            voice_file = await text_to_voice(text_to_read)
            if voice_file:
                await update.message.reply_voice(voice=open(voice_file, "rb"), caption="🎙")
                os.remove(voice_file)
            else:
                await update.message.reply_text("❌ خطا در تولید صدا (سهمیه یا تنظیمات را چک کنید).")
        else:
            await update.message.reply_text("👇 روی یک متن ریپلای کنید و بنویسید «بخون»")
        return

    # ۲. بخش ترجمه
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
            await update.message.reply_text(f"✨ **ترجمه متن شما:**\n\n{res}")
            return

    # ۳. بخش هوش مصنوعی
    should_ai = False
    if chat_type == "private" and user_ai_enabled.get(update.effective_user.id, False):
        should_ai = True
    elif chat_type in ["group", "supergroup"]:
        if f"@{bot_obj.username}" in msg_text or (update.message.reply_to_message and update.message.reply_to_message.from_user.id == bot_obj.id):
            should_ai = True

    if should_ai:
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
        reply = await get_ai_response(msg_text.replace(f"@{bot_obj.username}", "").strip())
        await update.message.reply_text(reply)

# --- وب‌سرور برای رندر ---
app = Flask(__name__)
@app.route('/')
def health(): return "Atlas Online", 200

def run_flask():
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))

if __name__ == "__main__":
    Thread(target=run_flask, daemon=True).start()
    time.sleep(20)
    if BOT_TOKEN:
        application = Application.builder().token(BOT_TOKEN).build()
        application.add_handler(CommandHandler("ai", ai_toggle))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_all))
        application.run_polling(drop_pending_updates=True)
