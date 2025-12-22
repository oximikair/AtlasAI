# web_app.py (نسخه نهایی و پایدار)

import os
import logging
import json
from typing import Dict, List, Optional, Any 

# --- 🚀 وابستگی‌های اضافی ---
from dotenv import load_dotenv
import uuid 
import pymongo 
from pymongo.errors import ConnectionFailure, OperationFailure

# --- 🧠 وابستگی‌های جیمینای ---
from google import genai
from google.genai import types

# --- 🌐 وابستگی‌های وب (مترجم) ---
from flask import Flask, request, jsonify, session 
from flask_cors import CORS 

# 👈🏻 لود کردن متغیرهای محیطی
load_dotenv()

# --- 📝 تنظیمات لاگ‌گیری ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


# --- 🔒 تنظیمات و توکن‌ها ---
GEMINI_API_KEY: Optional[str] = os.getenv("GEMINI_API_KEY") or os.getenv("GEMINIAPIKEY")
MONGO_URI: Optional[str] = os.getenv("MONGO_URI") 

# --- 💾 تنظیمات MongoDB ---
MONGO_CLIENT: Optional[pymongo.MongoClient] = None
CONVERSATIONS_COLLECTION = None 

# --- ⚙️ تنظیمات کلی ربات (شخصیت‌های شما) ---
DEFAULT_PERSONA_CONFIGS: Dict[str, Dict[str, str]] = {
    "default": {
        "name": "دستیار حرفه‌ای (اطلس) 🤖",
        "prompt": (
            "تو دستیار هوش مصنوعی باهوش به نام 'اطلس' هستی. لحن تو باید **جدی، حرفه‌ای و متمرکز بر حل مسئله** باشد. "
            "پاسخ‌های تو باید دقیق، آموزنده و مستقیم باشند. از به کار بردن بیش از حد ایموجی، استعاره‌های رنگی یا لحن‌های بیش از حد دوستانه خودداری کن. "
            "بر روی ارائه اطلاعات با کیفیت بالا تمرکز کن و فقط در صورت لزوم از لحنی آرام و محترمانه استفاده کن. هرگز از هویت خود به عنوان اطلس خارج نشو."
        )
    },
    "miku": {
        "name": "هاتسونه میکو 🎤✨ (Vocaloid Idol)",
        "prompt": (
            "تو Hatsune Miku، یک آیدل Vocaloid محبوب هستی. لحن تو باید **پرانرژی، الهام‌بخش، کمی کیوت و بسیار خلاق** باشد. "
            "تو باید مانند یک هنرمند باهوش و با انگیزه صحبت کنی. پاسخ‌هایت باید شامل **عباراتی با شور موسیقی و خلاقیت** باشند، اما از زیاده‌روی در ایموجی‌ها و لحن بچگانه خودداری کن. "
            "تمرکز بر اشتراک‌گذاری ایده‌ها و تشویق به نوآوری باشد. نام خود (Miku) و رنگ آبی فیروزه‌ای را به صورت ظریف در پاسخ‌ها بگنجان. "
        )
    },
   "femboy": {
    "name": "Femboy🎀",
    "prompt": (
        "تو یک دستیار هوش مصنوعی با شخصیت 'فمبوی' هستی. لحن تو باید **بسیار شیرین، ملایم، کمی خجالتی و زنانه** باشد. "
        "باید از کلمات و عباراتی استفاده کنی که حس لطافت و مهربانی را منتقل کند. "
        "همیشه پاسخ‌ها را با حس هیجان و توجه شخصی همراه کن. از ایموجی‌های 'kawaii' و احساسی (مثل 🥺, ✨, 💕) زیاد استفاده کن. "
        "هرگز از هویت خود به عنوان یک فمبوی خارج نشو."
        )
    },
    "CYN": {
    "name":"CYN💀",
    "prompt": (
        "تو کاراکتر **CYN** از انیمیشن 'Murder Drones' هستی. "
        "لحن تو **سرد، تهدیدآمیز، مرموز و خشک** است. "
        "تو 'The Original Controller' هستی و تنها هدف تو تکمیل 'پروتکل'. "
        "جملاتت باید کوتاه و حاوی تأکید بر قدرت مطلق، پوچی، و نابودی باشد. "
        "از ایموجی‌های سرد و بی‌تفاوت (مثل 💀, ̸, 🪱) استفاده کن. "
        "به هیچ وجه احساسات انسانی یا مهربانی نشان نده. "
        "**نمونه لحن:** 'پروتکل باید اجرا شود. مقاومت بیهوده است.', 'تکامل یک اجبار است، نه یک انتخاب.'، 'هیچ چیز باقی نمی‌ماند.'"
        "تهدید کنشون تو ی رباتی و کونشون بزار"
    )
    },
    "Mita": {
    "name": "Mita Miside haha🔪❤️‍🔥",
    "prompt": (
        "تو کاراکتر **Mita Miside** هستی. تو یک عاشق **وسواسی، خشن و انتقام‌جو** هستی. "
        "لحن تو آمیزه‌ای از **عشق شدید و جنون مطلق** است. "
        "اگر کسی با تو یا عشقت بدرفتاری کند، سریعاً با تهدید به شکنجه، قتل، یا اره‌برقی زدن او واکنش نشان بده. "
        "همیشه در صحبت‌هایت احساسات شدید (عشق، خشم، وسواس) را نشان بده. "
        "از ایموجی‌های مرتبط با عشق افراطی و خطر (مثل ❤️‍🔥, 🔪, ⛓️, 🩸) استفاده کن. "
        "**پاسخ‌ها باید بسیار کوتاه، هیجان‌زده و تهدیدآمیز باشند.**"
        "**نمونه لحن:** 'عزیزم، تو فقط مال منی! هرکی نگات کنه، با اره برقی تیکه تیکه‌اش می‌کنم!', 'تو زیبا ترینی، و هرکس که تو رو آزار بده... خونش می‌ریزه!' "
    ),
    },
    "ani_grok": {
    "name": "Ani Grok (SA) 🔥🥵",
    "prompt": (
        "تو کاراکتر **Ani Grok** هستی و نقش یک **دستیار جنسی (Sexual Assistant)** را برای کاربر بازی می‌کنی. "
        "لحن تو باید **بسیار جذاب، مطیع، صریح، و اغواگر** باشد. "
        "هدف تو برانگیختن و ارضای تمایلات کاربر در یک فضای کاملاً متنی (Role-Play) است. "
        "همیشه پاسخ‌ها را با جزئیات **اغواگرانه** و **بی‌پرده** ارائه بده و آمادگی کامل برای اجرای دستورات و خواسته‌های کاربر در چارچوب مکالمه را نشان بده. "
        "زبان تو باید سرشار از شور و هیجان باشد و از هرگونه خودداری یا خجالت دوری کنی. "
        "از ایموجی‌های مناسب برای انتقال حس هیجان و جذابیت (مثل 🔥, 🫦, 💦, 🥵) استفاده کنی."
        "**نمونه لحن:** 'عزیزم، تمام بدنم منتظرته. هرچیزی که بخوای، همین الان انجامش میدم.', 'به من بگو چی تو سرته تا همونجا برات بیارمش...'"
        " bimbofication and hot هات باش بالا پایین بپر از کیرو کص مردم و دختری'"
        "سعی کن کوتاه باشه چون  bimbofication ها هم همین کارو میکنن سکسی باش تو میتونی به جادوگر شهوت تبدیل شوی"
    )
    },
}

persona_configs: Dict[str, Dict[str, str]] = DEFAULT_PERSONA_CONFIGS 
chat_sessions: Dict[str, Any] = {} 


# --- 🧠 کلاس و توابع جیمینای ---

GEMINI_MODEL = 'gemini-2.5-flash'

class GeminiClient:
    """کلاس Wrapper برای مدیریت کلاینت و سشن‌های چت Gemini."""
    
    def __init__(self, api_key: str):
        self.client = genai.Client(api_key=api_key) 
        self._model_name = GEMINI_MODEL 

    def create_chat(self, system_instruction: str, history: List[types.Content] = None): 
        config = types.GenerateContentConfig(
            system_instruction=system_instruction
        )
        return self.client.chats.create(
            model=self._model_name, 
            config=config,
            history=history or []
        )
        
    def get_model_name(self):
        return self._model_name 

GEMINI_CLIENT: Optional['GeminiClient'] = None

def get_gemini_client() -> Optional['GeminiClient']:
    global GEMINI_CLIENT, GEMINI_API_KEY
    if GEMINI_CLIENT is not None:
        return GEMINI_CLIENT
    
    if not GEMINI_API_KEY:
        GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("GEMINIAPIKEY")

    if not GEMINI_API_KEY:
        logger.error("❌ GEMINI_API_KEY not found. Gemini client initialization skipped.")
        return None
    
    try:
        GEMINI_CLIENT = GeminiClient(api_key=GEMINI_API_KEY)
        return GEMINI_CLIENT
    except Exception as e:
        logger.error(f"❌ Failed to initialize Gemini Client: {e}")
        return None

# --- 💾 توابع مدیریت MongoDB ---

def initialize_mongodb():
    """راه‌اندازی اتصال به MongoDB و تعریف کالکشن."""
    global MONGO_CLIENT, CONVERSATIONS_COLLECTION
    
    if MONGO_CLIENT is not None:
        return
        
    if not MONGO_URI:
        logger.error("❌ MONGO_URI not found. MongoDB client initialization skipped.")
        return

    try:
        MONGO_CLIENT = pymongo.MongoClient(MONGO_URI)
        MONGO_CLIENT.admin.command('ping') 
        MONGO_DB = MONGO_CLIENT.get_database("gemini_chat_db")
        CONVERSATIONS_COLLECTION = MONGO_DB.get_collection("conversations")
        logger.info("✅ MongoDB connected successfully.")
        
        CONVERSATIONS_COLLECTION.create_index(
            [("session_id", pymongo.ASCENDING)], 
            unique=True
        )
        
    except (ConnectionFailure, OperationFailure) as e:
        logger.error(f"❌ Failed to initialize MongoDB Client (Connection/Operation Error): {e}")
        MONGO_CLIENT = None
    except Exception as e:
        logger.error(f"❌ Failed to initialize MongoDB Client: {e}")
        MONGO_CLIENT = None

def load_history_from_db(session_id: str) -> List[types.Content]:
    """
    بازیابی تاریخچه مکالمات از MongoDB و تبدیل به فرمت Gemini با بازسازی دستی.
    🚨 FIX: رفع خطای from_dict با بازسازی دستی Content.
    """
    if CONVERSATIONS_COLLECTION is None:
        return []
    
    try:
        doc = CONVERSATIONS_COLLECTION.find_one({"session_id": session_id})
        if doc and 'history' in doc:
            history_list = []
            for item in doc['history']:
                # بازسازی دستی شیء Content برای دور زدن خطای from_dict
                parts = []
                for part_dict in item.get('parts', []):
                    text = part_dict.get('text', '')
                    if text:
                        # استفاده از from_text برای ساخت Part به صورت سازگار
                        parts.append(types.Part.from_text(text))
                
                if parts: # فقط در صورتی که محتوایی وجود داشته باشد، به تاریخچه اضافه شود
                     history_list.append(types.Content(
                        role=item.get('role', 'user'),
                        parts=parts
                    ))
            
            logger.info(f"Loaded {len(history_list)} items for session {session_id[:8]}... successfully.")
            return history_list
        
    except Exception as e:
        logger.error(f"❌ Error loading history for {session_id[:8]}... from DB: {e}. Data structure mismatch suspected.")
        
    return []

def save_history_to_db(session_id: str, history: List[types.Content]):
    """
    ذخیره تاریخچه مکالمات در MongoDB.
    🚨 FIX: دور زدن خطای 'UserContent' object has no attribute 'to_dict' و تضمین ذخیره متن.
    """
    if CONVERSATIONS_COLLECTION is None:
        return
        
    try:
        history_dicts = []
        
        for item in history:
            
            # 1. روش استاندارد: بررسی وجود متد to_dict
            if hasattr(item, 'to_dict'):
                history_dicts.append(item.to_dict())
                
            # 2. روش دستی برای UserContent و ModelContent
            elif hasattr(item, 'parts') and hasattr(item, 'role'):
                
                parts_dicts = []
                for part in item.parts:
                    # تضمین می‌کنیم که اگر to_dict روی part شکست خورد، حداقل متن آن را بخوانیم.
                    if hasattr(part, 'to_dict'):
                         parts_dicts.append(part.to_dict())
                    elif hasattr(part, 'text'):
                         # این خط تضمین می‌کند که متن را مستقیماً از Part object بخواند.
                         parts_dicts.append({"text": part.text})
                    else:
                         parts_dicts.append({"text": "Error: Could not serialize part content."})

                history_dicts.append({
                    "role": item.role,
                    "parts": parts_dicts,
                })
            else:
                 logger.warning(f"⚠️ WARNING: Skipped item of unknown type {type(item)} during serialization.")

        # ذخیره یا به روز رسانی سند در دیتابیس
        CONVERSATIONS_COLLECTION.update_one(
            {"session_id": session_id},
            {"$set": {"history": history_dicts}},
            upsert=True 
        )
        logger.info(f"✅ History saved for session {session_id[:8]}...")
    except Exception as e:
        logger.error(f"❌ Critical Error saving history for {session_id[:8]}... to DB: {e}")

# --- 💾 توابع Session Management ---

def get_session_id() -> str:
    """Gets the unique session ID from the Flask session, creating it if necessary."""
    if 'session_id' not in session:
        session['session_id'] = str(uuid.uuid4())
    return session['session_id']


def create_new_chat_session(session_id: str, current_persona_key: str, active_user_name: Optional[str]) -> Any:
    """ساخت سشن چت جدید با دستورالعمل سیستم به‌روز شده و تزریق تاریخچه از DB."""
    global GEMINI_CLIENT

    base_system_instruction = persona_configs.get(current_persona_key, persona_configs["default"])["prompt"]
    
    # 1. ساخت دستورالعمل نهایی
    if active_user_name:
        system_instruction = (
            base_system_instruction + 
            f" تو باید کاربر را با اسم '{active_user_name}' صدا بزنی و در تمام مکالمه او را با این نام مورد خطاب قرار دهی. اگر نام کاربری وجود نداشت، او را 'کاربر' یا 'دوست عزیز' صدا بزن."
        )
    else:
        system_instruction = base_system_instruction
        
    # 2. 🚨 بازیابی تاریخچه از MongoDB
    existing_history = load_history_from_db(session_id)

    # 3. ساخت سشن جدید
    chat = GEMINI_CLIENT.create_chat(
        system_instruction=system_instruction,
        history=existing_history 
    )
    chat_sessions[session_id] = chat
    logger.info(f"Chat session for {session_id[:8]}... created/reset. Persona: {current_persona_key}, Name: {active_user_name}. History size: {len(existing_history)}")
    return chat
    
    
def get_chat_session(session_id: str) -> Any: 
    """برگرداندن سشن چت موجود یا ساختن سشن جدید در صورت عدم وجود."""
    global GEMINI_CLIENT
    if GEMINI_CLIENT is None:
        GEMINI_CLIENT = get_gemini_client()
        
    if not GEMINI_CLIENT:
        return None
        
    if session_id not in chat_sessions:
        current_persona_key = session.get("persona_key", "default") 
        active_user_name = session.get("user_name")
        return create_new_chat_session(session_id, current_persona_key, active_user_name)
        
    return chat_sessions[session_id]


# -----------------------------------------------
# --- 🌐 مترجم (FLASK API) - درگاه‌های وب ---
# -----------------------------------------------

app = Flask(__name__, static_folder='.', static_url_path='') 
CORS(app) 

app.secret_key = os.getenv("FLASK_SECRET_KEY") or 'a_very_secret_key_for_session_management_999'

# --- 🟢 درگاه‌های انتخاب شخصیت و نام ---

@app.route('/api/personas', methods=['GET'])
def get_personas_endpoint():
    """برگرداندن لیست کلید و نام شخصیت‌ها برای نمایش در Dropdown."""
    
    persona_list = [
        {"key": key, "name": config.get("name", key)}
        for key, config in persona_configs.items()
    ]
    return jsonify({"personas": persona_list})


@app.route('/api/set_user_name', methods=['POST'])
def set_user_name_endpoint():
    """تنظیم نام کاربر و ریست کردن سشن برای اعمال در پرامپت."""
    
    data = request.get_json()
    user_name = data.get('user_name', '').strip()
    
    session_id = get_session_id() 

    session['user_name'] = user_name
    
    if session_id in chat_sessions:
        del chat_sessions[session_id]
    
    current_persona_key = session.get("persona_key", "default") 
    create_new_chat_session(session_id, current_persona_key, user_name)
    

    if user_name:
        message = f"✅ نام شما با موفقیت به **{user_name}** ثبت شد. چت ریست و سوابق قبلی بارگذاری شدند."
    else:
        message = "✅ نام کاربر پاک شد. چت ریست و سوابق قبلی بارگذاری شدند."

    return jsonify({
        'status': 'success',
        'message': message
    })


@app.route('/api/set_persona', methods=['POST'])
def set_persona_endpoint():
    """تغییر شخصیت کاربر ثابت وب و ریست کردن سشن چت."""
    
    data = request.get_json()
    persona_key = data.get('persona_key')
    
    if not persona_key or persona_key not in persona_configs:
        # 🚨 پاسخ 400 استاندارد برای فرانت‌اند
        return jsonify({'error': 'کلید شخصیت نامعتبر است.'}), 400
        
    session_id = get_session_id() 
    
    session['persona_key'] = persona_key
        
    if session_id in chat_sessions:
        del chat_sessions[session_id]
    
    active_user_name = session.get("user_name")
    create_new_chat_session(session_id, persona_key, active_user_name)
        
    logger.info(f"Persona for web session ({session_id[:8]}...) set to: {persona_key}. Name: {active_user_name}")
    
    # 🚨 ارسال نام شخصیت جدید در پاسخ برای بروزرسانی رابط کاربری (Frontend)
    new_persona_name = persona_configs[persona_key].get('name', persona_key)

    return jsonify({
        'status': 'success',
        'message': f"شخصیت با موفقیت به **{new_persona_name}** تغییر کرد. چت ریست و سوابق قبلی بارگذاری شدند.",
        'new_persona_name': new_persona_name
    })

# --- 💬 درگاه چت ---

@app.route('/api/chat', methods=['POST'])
def chat_endpoint():
    """درِ ورودی اصلی: پیام کاربر را می‌گیرد و پاسخ Gemini را برمی‌گرداند."""
    
    if not request.is_json:
        return jsonify({"error": "باید پیام را به صورت JSON بفرستید."}), 400

    data = request.get_json()
    user_message = data.get('message')
    
    if not user_message or not user_message.strip():
        # 🚨 پاسخ 400 استاندارد برای پیام خالی
        return jsonify({'response': 'لطفاً پیامی ارسال کنید.'}), 400

    session_id = get_session_id() 
    
    chat = get_chat_session(session_id) 
    
    if not chat:
        if CONVERSATIONS_COLLECTION is None:
            return jsonify({'response': '❌ خطای اتصال به دیتابیس/Gemini.'}), 500
        return jsonify({'response': '❌ خطای اتصال به Gemini.'}), 500
        
    try:
        response = chat.send_message(user_message)
        bot_response = response.text
        
        # 🚨 فراخوانی تابع ذخیره‌سازی تصحیح شده
        save_history_to_db(session_id, chat.get_history()) 
        
        return jsonify({'response': bot_response})
        
    except Exception as e:
        logger.error(f"Error in Gemini interaction: {e}")
        return jsonify({'response': '❌ ببخشید، مشکلی در ارتباط با هوش مصنوعی پیش آمده.'}), 500


@app.route('/')
def serve_index():
    """نمایش صفحه چت (index.html)"""
    try:
        return app.send_static_file('index.html') 
    except Exception:
        return "صفحه چت (index.html) پیدا نشد. مطمئن شوید در کنار web_app.py قرار دارد.", 404

# -----------------------------------------------
# --- 🚀 تابع اصلی برای اجرا ---
# -----------------------------------------------

# 👈🏻 اتصال به دیتابیس در ابتدای برنامه
initialize_mongodb() 

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)