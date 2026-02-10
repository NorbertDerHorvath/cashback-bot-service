import os
import threading
import time
import requests
from flask import Flask
import telebot
import firebase_admin
from firebase_admin import credentials, db
from datetime import datetime

# --- KONFIGURÁCIÓ ---
TOKEN = "8210425098:AAEAkmwRXrIrk9vt2rytnvWhcqSVfxQYa6g"
CHAT_ID = "8494341633" 
JSON_FILE = "coupons-79d9f-firebase-adminsdk-fbsvc-6cfc7ef3a2.json"
RENDER_URL = "https://cashback-bot-service.onrender.com"

# Firebase inicializálás
if not firebase_admin._apps:
    try:
        if os.path.exists(JSON_FILE):
            cred = credentials.Certificate(JSON_FILE)
            firebase_admin.initialize_app(cred, {
                'databaseURL': "https://coupons-79d9f-default-rtdb.europe-west1.firebasedatabase.app/"
            })
            print("✅ Firebase kapcsolat aktív.")
        else:
            print(f"❌ HIBA: {JSON_FILE} hiányzik!")
    except Exception as e:
        print(f"❌ Firebase hiba: {e}")

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

@app.route('/')
def home():
    # Minden egyes látogatáskor (amit pl. a Cron-job generál) frissítjük a Firebase-t is
    if firebase_admin._apps:
        db.reference('system/last_wakeup').set(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    return "Bot status: Active. Pulse sent to Firebase.", 200

# --- KÉTIRÁNYÚ ÉBRENTARTÓ ---
def keep_alive_loop():
    """Körforgás: Render pingeli saját magát ÉS frissíti a Firebase-t"""
    while True:
        try:
            # 1. Saját magunk hívása (Render ébrentartás)
            requests.get(RENDER_URL)
            
            # 2. Firebase frissítése (Adatbázis kapcsolat ébrentartás)
            if firebase_admin._apps:
                db.reference('system/keep_alive_ping').set(time.time())
                
            print(f"💓 Életjel elküldve: {datetime.now().strftime('%H:%M:%S')}")
        except Exception as e:
            print(f"⚠️ Ébrentartási hiba: {e}")
        
        time.sleep(600) # 10 percenként fut le (a 15 perces leállás előtt)

# --- ADMIN FIGYELŐ ---
def watch_admin():
    print("🚀 Admin parancsfigyelő aktív...")
    while True:
        try:
            if firebase_admin._apps:
                ref = db.reference('commands/full_scan')
                cmd = ref.get()
                
                if cmd and cmd.get('processed') == False:
                    db.reference('coupons').delete()
                    bot.send_message(CHAT_ID, "🔄 Admin parancs: Adatbázis ürítve!")
                    ref.update({'processed': True})
        except Exception as e:
            print(f"⚠️ Hiba: {e}")
        time.sleep(5)

def run_server():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

if __name__ == "__main__":
    threading.Thread(target=run_server, daemon=True).start()
    threading.Thread(target=keep_alive_loop, daemon=True).start()
    threading.Thread(target=watch_admin, daemon=True).start()

    try:
        bot.polling(none_stop=True)
    except Exception as e:
        print(f"❌ Telegram hiba: {e}")
