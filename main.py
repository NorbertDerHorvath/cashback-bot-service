import os
import threading
import time
from flask import Flask
import telebot
import firebase_admin
from firebase_admin import credentials, db

# --- KONFIGURÁCIÓ ---
TOKEN = "8210425098:AAEAkmwRXrIrk9vt2rytnvWhcqSVfxQYa6g"
CHAT_ID = "634893700" 
# A GitHubon található pontos fájlnév:
JSON_FILE = "coupons-79d9f-firebase-adminsdk-fbsvc-6cfc7ef3a2.json"

# Firebase inicializálás
if not firebase_admin._apps:
    try:
        if os.path.exists(JSON_FILE):
            cred = credentials.Certificate(JSON_FILE)
            firebase_admin.initialize_app(cred, {
                'databaseURL': "https://coupons-79d9f-default-rtdb.europe-west1.firebasedatabase.app/"
            })
            print("✅ Firebase csatlakozva a megadott JSON fájllal!")
        else:
            print(f"❌ HIBA: A {JSON_FILE} nem található a gyökérkönyvtárban!")
    except Exception as e:
        print(f"❌ Firebase hiba: {e}")

bot = telebot.TeleBot(TOKEN)

# --- WEBSZERVER A RENDERNEK (Ébrentartáshoz) ---
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is active!", 200

def run_server():
    # A Render portjának kezelése
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

# --- ADMIN PARANCSOK FIGYELÉSE ---
def watch_admin():
    print("🚀 Admin parancsfigyelő indítása...")
    while True:
        try:
            if firebase_admin._apps:
                cmd_ref = db.reference('commands/full_scan')
                cmd = cmd_ref.get()
                
                if cmd and cmd.get('processed') == False:
                    print("🔔 ADMIN RESET PARANCS ÉRZLELVE!")
                    bot.send_message(CHAT_ID, "🔄 Adatbázis ürítve, új keresés indul!")
                    
                    # Itt hívhatod meg a scraper függvényedet, ha van
                    # start_scraping_process()
                    
                    cmd_ref.update({'processed': True})
        except Exception as e:
            print(f"⚠️ Hiba a parancsfigyelőben: {e}")
        time.sleep(10)

# --- INDÍTÁS ---
if __name__ == "__main__":
    # 1. Flask szerver indítása (hogy a Render/Cron-job lássa és ne aludjon el)
    threading.Thread(target=run_server, daemon=True).start()
    
    # 2. Firebase parancsok figyelése (Reset/Törlés gomb)
    threading.Thread(target=watch_admin, daemon=True).start()

    print("🤖 Bot polling indítása...")
    try:
        bot.polling(none_stop=True)
    except Exception as e:
        print(f"❌ Telegram hiba: {e}")
