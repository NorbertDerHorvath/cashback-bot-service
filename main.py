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
    return "Bot is active and polling!", 200

# --- KONFIGURÁCIÓ ---
JSON_FILE = "coupons-79d9f-firebase-adminsdk-fbsvc-6cfc7ef3a2.json" 
DB_URL = "https://coupons-79d9f-default-rtdb.europe-west1.firebasedatabase.app/"
TELEGRAM_TOKEN = "8210425098:AAEAkmwRXrIrk9vt2rytnvWhcqSVfxQYa6g"
CHAT_ID = "8494341633" 

if not firebase_admin._apps:
    cred = credentials.Certificate(JSON_FILE)
    firebase_admin.initialize_app(cred, {'databaseURL': DB_URL})

def send_telegram(message):
    print(f">>> KÜLDÉS: {message[:50]}...")
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try: 
        r = requests.post(url, json={"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"}, timeout=15)
        print(f">>> Telegram válasz: {r.status_code}")
    except Exception as e: 
        print(f">>> Telegram hiba: {e}")

def perform_scan(force_reset=False):
    if force_reset:
        print("!!! RESET INDÍTVA !!!")
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
                    # Ellenőrizzük, létezik-e már
                    exists = ref.order_by_child('link').equal_to(l).get()
                    if not exists:
                        ref.push({'title': t, 'link': l, 'status': 'pending', 'timestamp': time.time()})
                        send_telegram(f"🔍 *Új találat!*\n📌 {t}\n🔗 {l}")
        except Exception as e: print(f"Szkennelési hiba: {e}")

def bot_loop():
    print("--- Bot hurok elindult (Polling mód) ---")
    last_rss_check = 0
    
    while True:
        try:
            # 1. Parancsok ellenőrzése (Reset)
            cmd_ref = db.reference('commands/full_scan').get()
            if cmd_ref and cmd_ref.get('processed') == False:
                perform_scan(force_reset=True)
                db.reference('commands/full_scan').update({'processed': True})

            # 2. Élesítendő alkuk ellenőrzése
            deals = db.reference('deals').order_by_child('status').equal_to('sent').get()
            if deals:
                for deal_id, deal_data in deals.items():
                    # Itt egy kis trükk: átállítjuk 'archived'-ra, hogy ne küldje el többször
                    send_telegram(f"🚀 *ÉLESÍTVE!*\n📌 {deal_data['title']}\n🔗 {deal_data['link']}")
                    db.reference(f'deals/{deal_id}').update({'status': 'completed'})

            # 3. RSS szkennelés (30 percenként)
            current_time = time.time()
            if current_time - last_rss_check > 1800:
                perform_scan()
                last_rss_check = current_time

        except Exception as e:
            print(f"Hiba a hurokban: {e}")
        
        time.sleep(5) # 5 másodpercenként néz rá az adatbázisra

if __name__ == "__main__":
    # Indítás
    threading.Thread(target=bot_loop, daemon=True).start()
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
