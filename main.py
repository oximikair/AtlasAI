import os
import logging
from flask import Flask
from threading import Thread
from telegram.ext import Application, CommandHandler

# ۱. تنظیمات لاگ برای دیدن جزئیات در رندر
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

# ۲. ساخت یک سرور وب کوچک برای اینکه Render سرویس را آفلاین نکند
app = Flask(__name__)

@app.route('/')
def health_check():
    return "Bot is Running!", 200

def run_flask():
    # Render معمولاً پورت 10000 را می‌خواهد
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

# ۳. توابع ربات تلگرام
async def start(update, context):
    await update.message.reply_text('سلام! من با موفقیت روی رندر اجرا شدم.')

# ۴. بخش اصلی اجراکننده
def main():
    # توکن را از Environment Variables بخوانید
    TOKEN = os.environ.get("BOT_TOKEN")
    
    if not TOKEN:
        logger.error("No BOT_TOKEN found in environment variables!")
        return

    # ساخت اپلیکیشن ربات
    application = Application.builder().token(TOKEN).build()

    # افزودن دستورات
    application.add_handler(CommandHandler("start", start))

    # شروع سرور Flask در یک ترد (Thread) جداگانه
    flask_thread = Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()

    # شروع به کار ربات با تنظیمات ضد تداخل
    logger.info("Starting bot polling...")
    
    # drop_pending_updates=True باعث می‌شود پیام‌های قدیمی که باعث Conflict می‌شوند نادیده گرفته شوند
    application.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()
