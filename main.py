import os, logging, asyncio, time, httpx
from flask import Flask
from threading import Thread
from google import genai
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes, CommandHandler

# --- تنظیمات لاگ برای عیب‌یابی در رندر ---
logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# --- متغیرهای محیطی ---
BOT_TOKEN = os.environ.get("BOT_TOKEN")
GEMINI_KEY = os.environ.get("GEMINI_KEY")
ELEVEN_KEY = os.environ.get("dc19b835bcd3a48e6fd50f06c7c63c56593d9c7f853cd4f3ffcb1bc4ff662788")
VOICE_ID = "21m00Tcm4lS96DGzAsAn" # صدای پیش‌فرض Bella (بسیار طبیعی برای فارسی و انگلیسی)

user_ai_enabled = {} 
LANG_MAP = {"انگلیسی": "en", "آلمانی": "de", "فرانسوی": "fr", "عربی": "ar", "ترکی": "tr", "روسی": "ru", "فارسی": "fa"}

# --- تابع قدرتمند تولید صدا (ElevenLabs) ---
async def text_to_voice(text):
    if not ELEVEN_KEY:
        logger.error("خطا: کلید ELEVENLABS_KEY در تنظیمات رندر تعریف نشده است.")
        return None
    try:
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}"
        headers = {
            "xi-api-key": ELEVEN_KEY,
            "Content-Type": "application/json",
            "accept": "audio/mpeg"
        }
        data = {
            "text": text,
            "model_id": "eleven_multilingual_v2",
            "voice_settings": {"stability": 0.5, "similarity_boost": 0.5}
        }
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, json=data, timeout=30.0)
            if resp.status_code == 200:
                file_path = "voice_output.mp3"
                with open(file_path, "wb") as f:
                    f.write(resp.content)
                return file_path
            else:
                # لاگ کردن دلیل دقیق خطا در پنل رندر
                logger.error(f"ElevenLabs API Error: {resp.status_code} - {resp.text}")
                return None
    except Exception as e:
        logger.error(f"TTS Exception: {e}")
        return None

# --- تابع ترجمه گوگل ---
async def translate_text(text, target_code):
    try:
        url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl=auto&tl={target_code}&dt=t&q={text}"
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, timeout=10.0)
            if resp.status_code == 200:
                data = resp.json()
                return "".join([part[0] for part in data[0] if part[0]])
        return "⚠️ سرویس ترجمه موقتاً در دسترس نیست."
    except: return "⚠️ خطا در عملیات ترجمه."

# --- تابع هوش مصنوعی Gemini ---
async def get_ai_response(user_text):
    try:
        client = genai.Client(api_key=GEMINI_KEY)
        response = client.models.generate_content(model="gemini-2.0-flash", contents=user_text)
        return response.text if response.text else "پاسخی دریافت نشد."
    except Exception as e:
        if "429" in str(e): return "⏳ سهمیه روزانه هوش مصنوعی تمام شده است."
        return "❌ اطلس فعلاً قادر به پاسخگویی نیست."

# --- دستور /ai (فقط در پی‌وی کار می‌کند) ---
async def ai_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.chat.type != "private":
        await update.message.reply_text("❌ این دستور فقط در چت شخصی (PV) کار می‌کند.")
        return
    user_id = update.effective_user.id
    is_on = user_ai_enabled.get(user_id, False)
    user_ai_enabled[user_id] = not is_on
    msg = "✅ هوش مصنوعی برای شما فعال شد." if user_ai_enabled[user_id] else "❌ هوش مصنوعی خاموش شد. (فقط ترجمه و بخون فعال است)"
    await update.message.reply_text(msg)

# --- مدیریت اصلی تمام پیام‌ها ---
async def handle_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text: return
    msg_text = update.message.text.strip()
    chat_type = update.message.chat.type
    bot_obj = await context.bot.get_me()

    # ۱. قابلیت "بخون" (ریپلای هوشمند)
    if msg_text == "بخون":
        if update.message.reply_to_message and update.message.reply_to_message.text:
            text_to_read = update.message.reply_to_message.text
            
            # محدودیت کاراکتر برای حفظ سهمیه ElevenLabs
            if len(text_to_read) > 800:
                await update.message.reply_text("⚠️ متن طولانی است! برای صرفه‌جویی در سهمیه، لطفاً متن‌های کمتر از ۸۰۰ کاراکتر بفرستید.")
                return

            await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="record_voice")
            voice_file = await text_to_voice(text_to_read)
            
            if voice_file:
                await update.message.reply_voice(voice=open(voice_file, "rb"), caption="🎙")
                os.remove(voice_file) # حذف فایل بعد از ارسال
            else:
                await update.message.reply_text("❌ خطا در تولید صدا. اگر مدیر ربات هستید، لاگ‌های رندر و سهمیه ElevenLabs را چک کنید.")
        else:
            await update.message.reply_text("👇 لطفاً این کلمه را روی یک پیام متنی ریپلای کنید.")
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

    # ۳. بخش هوش مصنوعی Gemini
    should_ai = False
    if chat_type == "private" and user_ai_enabled.get(update.effective_user.id, False):
        should_ai = True
    elif chat_type in ["group", "supergroup"]:
        # در گروه‌ها: فقط منشن یا ریپلای مستقیم به ربات
        is_mentioned = f"@{bot_obj.username}" in msg_text
        is_reply_to_bot = (update.message.reply_to_message and update.message.reply_to_message.from_user.id == bot_obj.id)
        if is_mentioned or is_reply_to_bot:
            should_ai = True

    if should_ai:
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
        clean_text = msg_text.replace(f"@{bot_obj.username}", "").strip()
        reply = await get_ai_response(clean_text)
        await update.message.reply_text(reply)

# --- راه اندازی سرور و ربات ---
app = Flask(__name__)
@app.route('/')
def health(): return "Atlas is Online", 200

def run_flask():
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))

if __name__ == "__main__":
    Thread(target=run_flask, daemon=True).start()
    time.sleep(15) # وقفه برای پایداری در شروع
    
    if BOT_TOKEN:
        application = Application.builder().token(BOT_TOKEN).build()
        application.add_handler(CommandHandler("ai", ai_toggle))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_all))
        
        logger.info("Atlas Bot Started Successfully!")
        application.run_polling(drop_pending_updates=True)

