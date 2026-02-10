import os
import threading
import time
import requests
from flask import Flask
import telebot
import firebase_admin
from firebase_admin import credentials, db

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
            print("✅ Firebase kapcsolat felépítve.")
        else:
            print(f"❌ HIBA: {JSON_FILE} hiányzik!")
    except Exception as e:
        print(f"❌ Firebase hiba: {e}")

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot status: Online and watching Firebase", 200

# --- ÉBRENTARTÓ FUNKCIÓ ---
def keep_alive_ping():
    """A bot 5 percenként meghívja saját magát, hogy a Render ne altassa el"""
    while True:
        try:
            requests.get(RENDER_URL)
            print("Self-ping sikeres.")
        except Exception as e:
            print(f"Self-ping hiba: {e}")
        time.sleep(300) # 5 perc

# --- ADMIN FIGYELŐ ÉS TÖRLŐ ---
def watch_admin():
    print("🚀 Admin parancsfigyelő aktív...")
    while True:
        try:
            if firebase_admin._apps:
                ref = db.reference('commands/full_scan')
                cmd = ref.get()
                
                if cmd and cmd.get('processed') == False:
                    print("🔔 RESET PARANCS ÉRZÉKELVE!")
                    
                    # 1. Adatbázis ürítése Pythonból
                    db.reference('coupons').delete()
                    
                    # 2. Telegram értesítés
                    bot.send_message(CHAT_ID, "🔄 Admin parancs: Adatbázis kiürítve, új keresés indul!")
                    
                    # 3. Parancs nyugtázása a Firebase-ben
                    ref.update({'processed': True})
        except Exception as e:
            print(f"⚠️ Firebase figyelő hiba: {e}")
        
        time.sleep(5)

def run_server():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

if __name__ == "__main__":
    threading.Thread(target=run_server, daemon=True).start()
    threading.Thread(target=keep_alive_ping, daemon=True).start()
    threading.Thread(target=watch_admin, daemon=True).start()

    print("🤖 Bot polling indítása...")
    try:
        bot.polling(none_stop=True)
    except Exception as e:
        print(f"❌ Telegram hiba: {e}")
