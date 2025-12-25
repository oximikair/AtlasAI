import os
import logging
import asyncio
from flask import Flask
from threading import Thread
from telegram.ext import Application, CommandHandler
from telegram import Bot

# ۱. تنظیمات لاگ برای دیباگ در پنل رندر
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

# ۲. وب‌سرور برای جلوگیری از ارور Port در رندر
app = Flask(__name__)

@app.route('/')
def health():
    return "Bot is alive!", 200

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

# ۳. عملیات اجباری برای بستن تمام اتصال‌های قبلی
async def clear_conflicts(token):
    try:
        bot = Bot(token)
        # حذف وبهوک و پاکسازی آپدیت‌های منتظر که باعث تداخل می‌شوند
        await bot.delete_webhook(drop_pending_updates=True)
        logger.info("✅ All previous sessions cleared successfully.")
    except Exception as e:
        logger.error(f"❌ Error clearing conflicts: {e}")

# ۴. دستورات ربات
async def start(update, context):
    await update.message.reply_text("ربات با موفقیت فعال شد و تداخل‌ها برطرف شدند! 🚀")

# ۵. اجرای اصلی
def main():
    TOKEN = os.environ.get("BOT_TOKEN")
    if not TOKEN:
        print("❌ BOT_TOKEN is missing!")
        return

    # الف) اجرای وب‌سرور در پس‌زمینه
    Thread(target=run_flask, daemon=True).start()

    # ب) پاکسازی اجباری قبل از استارت ربات
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    loop.run_until_complete(clear_conflicts(TOKEN))

    # ج) راه‌اندازی ربات
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))

    print("--- 🚀 Bot is starting now ---")
    application.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
