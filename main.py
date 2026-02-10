import os
import threading
import time
from flask import Flask
import telebot
import firebase_admin
from firebase_admin import credentials, db

# --- KONFIGURÁCIÓ ---
# Ide írd a saját adataidat!
TOKEN = "A_TE_TELEGRAM_BOT_TOKENED"
CHAT_ID = "A_TE_CHAT_ID-D"

# Firebase inicializálás
if not firebase_admin._apps:
    try:
        # Ügyelj rá, hogy a firebase_kulcs.json is fent legyen GitHubon!
        cred = credentials.Certificate("firebase_kulcs.json")
        firebase_admin.initialize_app(cred, {
            'databaseURL': "https://coupons-79d9f-default-rtdb.europe-west1.firebasedatabase.app/"
        })
    except Exception as e:
        print(f"Firebase hiba: {e}")

bot = telebot.TeleBot(TOKEN)

# --- WEBSZERVER A RENDERNEK (Ébrentartáshoz) ---
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is active!", 200

def run_server():
    # A Render automatikusan kioszt egy portot, azt használjuk
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

# --- ADMIN PARANCSOK FIGYELÉSE ---
def watch_admin():
    print("Admin parancsfigyelő aktív...")
    while True:
        try:
            cmd_ref = db.reference('commands/full_scan')
            cmd = cmd_ref.get()
            
            if cmd and cmd.get('processed') == False:
                print("RESET PARANCS ÉSZLELVE!")
                bot.send_message(CHAT_ID, "🔄 Admin parancs: Új keresés indul!")
                # Itt hívnád meg a kereső funkciódat
                cmd_ref.update({'processed': True})
        except Exception as e:
            print(f"Hiba: {e}")
        time.sleep(10)

# --- INDÍTÁS ---
if __name__ == "__main__":
    # Webszerver indítása szálon
    threading.Thread(target=run_server, daemon=True).start()
    
    # Parancsfigyelő indítása szálon
    threading.Thread(target=watch_admin, daemon=True).start()

    print("Bot elindult...")
    bot.polling(none_stop=True)
