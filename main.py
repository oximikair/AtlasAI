import os
import logging
import asyncio
import json
import io
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta, timezone

# --- 🚀 وابستگی‌های اضافی ---
from dotenv import load_dotenv
from PIL import Image

# --- 🧠 وابستگی‌های جیمینای ---
from google import genai
from google.genai import types

from telegram import Update, ChatPermissions, InlineKeyboardButton, InlineKeyboardMarkup, ChatMember, ReplyKeyboardMarkup, KeyboardButton
# 🟢 فیکس: اضافه کردن import برای مدیریت خطای رایج تلگرام
from telegram.error import BadRequest, TelegramError 
from telegram.constants import ChatType, ParseMode
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
)

# 👈🏻 لود کردن متغیرهای محیطی از فایل .env
load_dotenv()

# --- 📝 تنظیمات لاگ‌گیری ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# 🟢 دستور چاپ برای اشکال‌زدایی فوری در Railway
print("--- 🟢 Railway Initialization Check: Starting main.py Process ---")


# --- 🔒 تنظیمات و توکن‌ها (خوانده شده از .env شما) ---

BOT_TOKEN: str = os.getenv("BOT_TOKEN", os.getenv("TELEGRAM_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN"))
GEMINI_API_KEY: Optional[str] = os.getenv("GEMINI_API_KEY") or os.getenv("GEMINIAPIKEY")

admin_id_str = os.getenv("ADMIN_USER_ID", "")
ADMIN_IDS: List[int] = [int(i.strip()) for i in admin_id_str.split(',') if i.strip().isdigit()]

# 🟢 متغیر جدید برای کانال لاگ
LOG_CHANNEL_ID: Optional[str] = os.getenv("LOG_CHANNEL_ID") 


# ⚠️ اگر کلید جیمینای موجود نباشد، ربات اجرا نخواهد شد.
if not GEMINI_API_KEY:
    logger.error("❌ GEMINI_API_KEY در متغیرهای محیطی یافت نشد. ربات نمی‌تواند ادامه دهد.")
    print("--- ❌ CRITICAL ERROR: GEMINI_API_KEY Missing ---") 


# ---------------------------------------------------------------------
# 🛎️ توابع کمکی و اصلی
# ---------------------------------------------------------------------

# 🟢 تابع notify_admin_of_message (اصلاح شده برای کانال و رفع خطای فرمت)
async def notify_admin_of_message(message: str, context: ContextTypes.DEFAULT_TYPE) -> None:
    """ارسال پیام نظارتی به کانال لاگ."""
    
    target_id = LOG_CHANNEL_ID 
    
    if not target_id:
        logger.warning("LOG_CHANNEL_ID تنظیم نشده است. ارسال لاگ امکان‌پذیر نیست.")
        return

    # 🟢 چاپ برای اشکال‌زدایی
    print(f"--- 🟢 Trying to send log to Channel {target_id} ---")

    try:
        await context.bot.send_message(
            chat_id=target_id, 
            text=message,
            parse_mode=None # 👈🏻 فیکس: غیرفعال کردن ParseMode برای جلوگیری از خطای فرمت
        )
    except BadRequest as e:
        logger.error(f"Error sending log to channel {target_id}: {e}")
        print(f"--- 💥 Telegram Error: BadRequest to Channel {target_id} ({e}) ---")
    except TelegramError as e:
        logger.error(f"General Telegram Error sending log to channel {target_id}: {e}")
        print(f"--- 💥 General Telegram Error to Channel {target_id} ({e}) ---")
    except Exception as e:
        logger.error(f"Unknown error notifying channel {target_id}: {e}")
        print(f"--- 💥 Unknown Error to Channel {target_id} ({e}) ---")

# 💡 توابع هندلر (لطفاً توابع handle_start، get_command_aliases و ... را از فایل قبلی خود به اینجا کپی کنید.)

async def handle_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # 💡 کدهای هندلر استارت خود را اینجا قرار دهید.
    await update.message.reply_text("ربات فعال است.")

async def handle_gemini_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """هندلر اصلی پیام متنی: لاگ می‌گیرد و با Gemini پاسخ می‌دهد."""
    # ⚠️ این تابع باید اولین کارش، فراخوانی notify_admin_of_message باشد.
    user_info = f"@{update.effective_user.username}" if update.effective_user.username else f"User ID: {update.effective_user.id}"
    message_content = update.message.text
    # 🟢 پیام لاگ برای کانال
    notification_message = f"**[ربات تلگرام]**\n\n**فرستنده:** {user_info}\n**محتوا:** {message_content}"
    await notify_admin_of_message(notification_message, context) # 👈🏻 لاگ‌گیری
    
    # 💡 کدهای اصلی اتصال به Gemini برای پاسخ‌گویی را اینجا قرار دهید.
    await update.message.reply_text("پیام نظارتی ارسال شد و اکنون منتظر پاسخ Gemini است...") 
    pass # ادامه کدهای شما

async def update_user_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """این تابع آمارگیری است که موقتاً در main() غیرفعال شده است."""
    pass


def main() -> None:
    """شروع به اجرای ربات (Polling) می‌کند."""

    # 🟢 چاپ برای اشکال‌زدایی
    print(f"--- 🔑 BOT_TOKEN status: {'Set' if BOT_TOKEN else 'Missing'} ---")
    print(f"--- 🔑 LOG_CHANNEL_ID status: {'Set' if LOG_CHANNEL_ID else 'Missing'} ---")
    
    try:
        # 1. ساخت Application 
        application = Application.builder().token(BOT_TOKEN).build()
    except Exception as e:
        # اگر مشکلی در توکن یا ساخت Application بود، اینجا چاپ می‌شود.
        print(f"--- 💥 CRITICAL ERROR in Application Build: {e} ---")
        logger.error(f"CRITICAL ERROR in Application Build: {e}")
        return # پایان برنامه

    # 2. ثبت هندلرها
    
    # الف) هندلرهای دستورات (Commands)
    
    # 💡 تمام CommandHandlerهای خود را اینجا قرار دهید.
    application.add_handler(CommandHandler("start", handle_start)) 
    # ... (CommandHandlerهای قبلی خود را در اینجا قرار دهید.) ...
    
    
    # ج) هندلر پیام‌های متنی (Text Messages)
    
    # 🥇 هندلر Gemini: فقط روی متن‌هایی که دستور نیستند اجرا می‌شود.
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_gemini_message))
    
    
    # د) هندلر آمارگیری (General Updates)
    
    # ❌ هندلر آمارگیری که از filters.ALL استفاده می‌کرد، موقتاً کامنت شده است.
    # application.add_handler(MessageHandler(filters.ALL, update_user_stats))
    
    
    # 4. شروع Polling
    logger.info("Telebot has started polling...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
