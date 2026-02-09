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
    return "Bot is watching!", 200

# --- KONFIGURÁCIÓ ---
JSON_FILE = "coupons-79d9f-firebase-adminsdk-fbsvc-6cfc7ef3a2.json" 
DB_URL = "https://coupons-79d9f-default-rtdb.europe-west1.firebasedatabase.app/"
TELEGRAM_TOKEN = "8210425098:AAEAkmwRXrIrk9vt2rytnvWhcqSVfxQYa6g"
CHAT_ID = "8494341633" 

if not firebase_admin._apps:
    cred = credentials.Certificate(JSON_FILE)
    firebase_admin.initialize_app(cred, {'databaseURL': DB_URL})

def send_telegram(message):
    print(f">>> Telegram küldés indítva: {message[:40]}...")
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try: 
        r = requests.post(url, json={"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"}, timeout=15)
        print(f">>> Telegram válasz státusz: {r.status_code}")
    except Exception as e: 
        print(f">>> Telegram hiba: {e}")

def perform_scan(force_reset=False):
    if force_reset:
        print("!!! RESET PARANCS ÉRZÉKELVE - Törlés indítása !!!")
        db.reference('deals').delete()
        send_telegram("🗑️ *Adatbázis ürítve, új szkennelés indul...*")

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

# --- LISTENEREK ---
def start_bot_logic():
    print("--- Listenerek konfigurálása ---")
    
    def cmd_listener(event):
        if event.data and isinstance(event.data, dict) and event.data.get('processed') == False:
            perform_scan(force_reset=True)
            db.reference('commands/full_scan').update({'processed': True})

    def deal_listener(event):
        # Csak akkor reagálunk, ha a 'status' mező változik 'sent'-re
        if event.data == 'sent' and 'status' in event.path:
            deal_id = event.path.split('/')[1]
            deal = db.reference(f'deals/{deal_id}').get()
            if deal:
                send_telegram(f"🚀 *ÉLESÍTVE!*\n📌 {deal['title']}\n🔗 {deal['link']}")

    db.reference('commands/full_scan').listen(cmd_listener)
    db.reference('deals').listen(deal_listener)
    
    while True:
        perform_scan()
        print("Szkennelés lefutott, 30 perc pihenő...")
        time.sleep(1800)

if __name__ == "__main__":
    # Külön szálon indítjuk a bot logikáját
    threading.Thread(target=start_bot_logic, daemon=True).start()
    
    # Flask szerver indítása (a Render portján)
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
