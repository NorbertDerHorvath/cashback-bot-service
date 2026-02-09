import firebase_admin
from firebase_admin import credentials, db
import requests
from bs4 import BeautifulSoup
import time
import threading
import os
from flask import Flask

# --- MINI WEBSZERVER A RENDERNEK ---
app = Flask(__name__)

@app.route('/')
def health_check():
    return "Bot is running!", 200

# --- KONFIGURÁCIÓ ---
JSON_FILE = "coupons-79d9f-firebase-adminsdk-fbsvc-6cfc7ef3a2.json" 
DB_URL = "https://coupons-79d9f-default-rtdb.europe-west1.firebasedatabase.app/"
TELEGRAM_TOKEN = "8210425098:AAEAkmwRXrIrk9vt2rytnvWhcqSVfxQYa6g"
CHAT_ID = "8494341633" 

if not firebase_admin._apps:
    cred = credentials.Certificate(JSON_FILE)
    firebase_admin.initialize_app(cred, {'databaseURL': DB_URL})

def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try: 
        requests.post(url, json={"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"}, timeout=10)
    except Exception as e: 
        print(f"Telegram hiba: {e}")

def perform_scan(force_reset=False):
    if force_reset:
        db.reference('deals').delete()
        send_telegram("🗑️ *Adatbázis ürítve.*")

    ref = db.reference('deals')
    feeds = ["https://rss.app/feeds/UBlHGZPrkiBFdRod.xml", "https://rss.app/feeds/WsCQbaznNvga5E3d.xml"]
    keywords = ["geld", "cashback", "gratis", "100%", "probieren", "test"]
    
    new_found = 0
    for url in feeds:
        try:
            r = requests.get(url, timeout=20)
            soup = BeautifulSoup(r.content, "xml")
            for item in soup.find_all('item'):
                t, l = item.title.text.strip(), item.link.text.strip()
                if any(k in t.lower() for k in keywords):
                    exists = ref.order_by_child('link').equal_to(l).get()
                    if not exists:
                        ref.push({'title': t, 'link': l, 'status': 'pending', 'timestamp': time.time()})
                        send_telegram(f"🔍 *Új találat!*\n📌 {t}\n🔗 {l}")
                        new_found += 1
        except Exception as e: print(f"Szkennelési hiba: {e}")

def approval_listener(event):
    if event.data == 'sent' and 'status' in event.path:
        try:
            path_parts = event.path.strip('/').split('/')
            deal_id = path_parts[0]
            deal = db.reference(f'deals/{deal_id}').get()
            if deal:
                send_telegram(f"🚀 *ÉLESÍTVE!*\n📌 {deal['title']}\n🔗 {deal['link']}")
        except: pass

def command_listener(event):
    if event.data and isinstance(event.data, dict):
        if event.data.get('processed') == False:
            perform_scan(force_reset=True)
            db.reference('commands/full_scan').update({'processed': True})

# Listenerek és Ütemező indítása
def start_bot_logic():
    db.reference('deals').listen(approval_listener)
    db.reference('commands/full_scan').listen(command_listener)
    while True:
        perform_scan()
        time.sleep(1800)

if __name__ == "__main__":
    # A bot logikája egy külön szálon fut
    threading.Thread(target=start_bot_logic, daemon=True).start()
    # A Flask szerver pedig a fő szálon (a Render portján)
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
