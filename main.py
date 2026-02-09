import firebase_admin
from firebase_admin import credentials, db
import requests
from bs4 import BeautifulSoup
import time
import threading
import os
from flask import Flask

app = Flask(__name__)

@app.route('/')
def health_check():
    return "Bot is alive and watching!", 200

# --- KONFIGURÁCIÓ ---
JSON_FILE = "coupons-79d9f-firebase-adminsdk-fbsvc-6cfc7ef3a2.json" 
DB_URL = "https://coupons-79d9f-default-rtdb.europe-west1.firebasedatabase.app/"
TELEGRAM_TOKEN = "8210425098:AAEAkmwRXrIrk9vt2rytnvWhcqSVfxQYa6g"
CHAT_ID = "8494341633" 

if not firebase_admin._apps:
    cred = credentials.Certificate(JSON_FILE)
    firebase_admin.initialize_app(cred, {'databaseURL': DB_URL})

def send_telegram(message):
    print(f"Telegram küldés: {message[:30]}...") # Logoljuk a konzolra is!
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try: 
        r = requests.post(url, json={"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"}, timeout=10)
        print(f"Telegram válasz: {r.status_code}")
    except Exception as e: 
        print(f"Telegram hiba: {e}")

def perform_scan(force_reset=False):
    if force_reset:
        print("RESET INDÍTVA...")
        db.reference('deals').delete()
        send_telegram("🗑️ *Adatbázis ürítve, szkennelés újraindult.*")

    ref = db.reference('deals')
    feeds = ["https://rss.app/feeds/UBlHGZPrkiBFdRod.xml", "https://rss.app/feeds/WsCQbaznNvga5E3d.xml"]
    keywords = ["geld", "cashback", "gratis", "100%", "probieren", "test"]
    
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
        except Exception as e: 
            print(f"Szkennelési hiba: {e}")

# --- ESEMÉNY FIGYELŐK ---
def start_listeners():
    print("Listenerek indítása...")
    
    # Reset figyelő
    def cmd_callback(event):
        if event.data and event.data.get('processed') == False:
            perform_scan(force_reset=True)
            db.reference('commands/full_scan').update({'processed': True})
    
    db.reference('commands/full_scan').listen(cmd_callback)

    # Élesítés figyelő
    def approval_callback(event):
        # Ha a státusz megváltozik 'sent'-re
        if event.data == 'sent':
            # Kinyerjük a deal ID-t az elérési útból
            path_parts = event.path.strip('/').split('/')
            deal_id = path_parts[0]
            deal = db.reference(f'deals/{deal_id}').get()
            if deal:
                send_telegram(f"🚀 *ÉLESÍTVE!*\n📌 {deal['title']}\n🔗 {deal['link']}")

    db.reference('deals').listen(approval_callback)

# --- FŐ CIKLUS ---
def main_loop():
    start_listeners()
    while True:
        perform_scan()
        print("Szkennelés kész, alvás 30 percig...")
        time.sleep(1800)

if __name__ == "__main__":
    # Indítjuk a botot egy külön szálon
    t = threading.Thread(target=main_loop)
    t.daemon = True
    t.start()
    
    # Flask indítása
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
