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

app = Flask(__name__)

# Firebase inicializálása globálisan, de hibakezeléssel
try:
    if not firebase_admin._apps:
        if os.path.exists(JSON_FILE):
            cred = credentials.Certificate(JSON_FILE)
            firebase_admin.initialize_app(cred, {
                'databaseURL': "https://coupons-79d9f-default-rtdb.europe-west1.firebasedatabase.app/"
            })
            print("✅ Firebase OK")
except Exception as e:
    print(f"❌ Firebase hiba: {e}")

@app.route('/')
def home():
    return "Bot is running", 200

# --- ADMIN PARANCS FIGYELŐ ---
def watch_admin():
    bot = telebot.TeleBot(TOKEN)
    print("🚀 Figyelő szál elindult...")
    while True:
        try:
            ref = db.reference('commands/full_scan')
            cmd = ref.get()
            if cmd and cmd.get('processed') == False:
                print("🔔 RESET ESEMÉNY!")
                db.reference('coupons').delete()
                db.reference('deals').delete()
                bot.send_message(CHAT_ID, "🔄 Adatbázis ürítve, keresés indul!")
                ref.update({'processed': True})
        except Exception as e:
            print(f"Admin hiba: {e}")
        time.sleep(5)

# --- ÖNHÍVÓ (ÉBRENTARTÓ) ---
def keep_alive():
    while True:
        time.sleep(600)
        try:
            requests.get(RENDER_URL)
            db.reference('system/keep_alive_ping').set(time.time())
        except:
            pass

# --- INDÍTÁS ---
if __name__ == "__main__":
    # A kritikus rész: először indítjuk a szálakat
    t1 = threading.Thread(target=watch_admin, daemon=True)
    t1.start()
    
    t2 = threading.Thread(target=keep_alive, daemon=True)
    t2.start()

    # Majd a Flask szervert, ami "megfogja" a főszálat
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
