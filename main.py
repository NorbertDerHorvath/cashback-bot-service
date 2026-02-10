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

# Flask inicializálása elölre, hogy azonnal válaszolni tudjon
app = Flask(__name__)

@app.route('/')
def home():
    if firebase_admin._apps:
        try:
            db.reference('system/last_wakeup').set(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        except:
            pass
    return "Bot status: Active", 200

# --- BOT ÉS FIREBASE FOLYAMATOK ---
def start_bot_logic():
    # Csak a szálon belül inicializáljuk a Firebase-t
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

    # Belső funkció az admin figyeléshez
    def watch_admin():
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
            time.sleep(10)

    # Belső funkció az önhívóhoz
    def keep_alive():
        while True:
            try:
                requests.get(RENDER_URL)
                if firebase_admin._apps:
                    db.reference('system/keep_alive_ping').set(time.time())
            except:
                pass
            time.sleep(600)

    # Szálak indítása a bot logikán belül
    threading.Thread(target=watch_admin, daemon=True).start()
    threading.Thread(target=keep_alive, daemon=True).start()

    print("🤖 Bot polling indítása...")
    try:
        bot.polling(none_stop=True)
    except Exception as e:
        print(f"❌ Telegram hiba: {e}")

# --- INDÍTÁS ---
if __name__ == "__main__":
    # 1. A bot logikát egy külön szálon indítjuk el, hogy ne blokkolja a Flask-et
    threading.Thread(target=start_bot_logic, daemon=True).start()
    
    # 2. A Flask szerver indítása a főszálon
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
