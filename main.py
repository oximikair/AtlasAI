import os
import logging
import asyncio
import time
from flask import Flask
from threading import Thread
from google import genai
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# --- توکن‌ها ---
BOT_TOKEN = os.environ.get("BOT_TOKEN")
GEMINI_KEY = os.environ.get("GEMINI_KEY")

async def get_ai_response(user_text):
    try:
        # اگر کلید اشتباه ست شده باشد، این بخش خطا می‌دهد
        client = genai.Client(api_key=GEMINI_KEY)
        response = client.models.generate_content(model="gemini-2.0-flash", contents=user_text)
        return response.text if response.text else "متوجه نشدم."
    except Exception as e:
        logger.error(f"AI Error: {e}")
        return "اطلس در حال حاضر قادر به پاسخگویی نیست اما شما میتوانید از دیگر قابلیت های آن استفاده کنید"

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text: return

    # اطلاعات ربات و پیام
    bot_obj = await context.bot.get_me()
    is_group = update.message.chat.type in ["group", "supergroup"]
    
    # تشخیص منشن
    is_mentioned = f"@{bot_obj.username}" in update.message.text
    
    # تشخیص ریپلای (آیا ریپلای شده روی پیامی که فرستنده‌اش خودِ ربات بوده؟)
    is_reply_to_bot = (
        update.message.reply_to_message and 
        update.message.reply_to_message.from_user.id == bot_obj.id
    )

    # اگر توی گروه بودیم و نه منشن بود و نه ریپلای، کلاً هیچ کاری نکن
    if is_group and not (is_mentioned or is_reply_to_bot):
        return

    # ارسال وضعیت Typing
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    
    # تمیز کردن متن از منشن
    clean_text = update.message.text.replace(f"@{bot_obj.username}", "").strip()
    
    reply = await get_ai_response(clean_text)
    await update.message.reply_text(reply)

# --- وب‌سرور ---
app = Flask(__name__)
@app.route('/')
def health(): return "OK", 200

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

if __name__ == "__main__":
    Thread(target=run_flask, daemon=True).start()
    
    # وقفه برای جلوگیری از Conflict
    time.sleep(10)
    
    if BOT_TOKEN and ":" in BOT_TOKEN: # چک کردن ظاهری توکن تلگرام
        application = Application.builder().token(BOT_TOKEN).build()
        application.add_handler(CommandHandler("start", lambda u, c: u.message.reply_text("اطلس آنلاین است!")))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        application.run_polling(drop_pending_updates=True)
    else:
        logger.error("❌ توکن تلگرام اشتباه است! در پنل رندر جابجا ست کرده‌اید.")
