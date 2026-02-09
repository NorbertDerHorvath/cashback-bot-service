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
    return "Bot Online", 200

# --- KONFIG ---
JSON_FILE = "coupons-79d9f-firebase-adminsdk-fbsvc-6cfc7ef3a2.json" 
DB_URL = "https://coupons-79d9f-default-rtdb.europe-west1.firebasedatabase.app/"
TELEGRAM_TOKEN = "8210425098:AAEAkmwRXrIrk9vt2rytnvWhcqSVfxQYa6g"
CHAT_ID = "8494341633" 

try:
    if not firebase_admin._apps:
        cred = credentials.Certificate(JSON_FILE)
        firebase_admin.initialize_app(cred, {'databaseURL': DB_URL})
        print(">>> Firebase hitelesítés OK.")
except Exception as e:
    print(f">>> Firebase hiba: {e}")

def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try: 
        requests.post(url, json={"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"}, timeout=10)
    except: pass

def perform_scan(force_reset=False):
    if force_reset:
        db.reference('deals').delete()
        send_telegram("🗑️ *Adatbázis ürítve, új keresés indul!*")

    ref = db.reference('deals')
    feeds = ["https://rss.app/feeds/UBlHGZPrkiBFdRod.xml", "https://rss.app/feeds/WsCQbaznNvga5E3d.xml"]
    keywords = ["geld", "cashback", "gratis", "100%", "probieren", "test"]
    
    for url in feeds:
        try:
            r = requests.get(url, timeout=20)
            items = BeautifulSoup(r.content, "xml").find_all('item')
            for item in items:
                t, l = item.title.text.strip(), item.link.text.strip()
                if any(k in t.lower() for k in keywords):
                    # Megnézzük, létezik-e már
                    exists = ref.order_by_child('link').equal_to(l).get()
                    if not exists:
                        # AZONNALI KÜLDÉS TELEGRAMRA
                        send_telegram(f"🔔 *ÚJ AJÁNLAT TALÁLVA!*\n\n📌 {t}\n\n🔗 {l}")
                        
                        # Mentés az adatbázisba 'pending' státusszal
                        ref.push({
                            'title': t, 
                            'link': l, 
                            'status': 'pending', 
                            'timestamp': time.time()
                        })
        except Exception as e:
            print(f"Szkennelési hiba: {e}")

def bot_loop():
    print(">>> Bot hurok aktív.")
    last_rss_check = 0
    while True:
        try:
            # 1. RESET FIGYELÉS
            cmd = db.reference('commands/full_scan').get()
            if isinstance(cmd, dict) and cmd.get('processed') is False:
                perform_scan(force_reset=True)
                db.reference('commands/full_scan').update({'processed': True})

            # 2. ÉLESÍTÉS FIGYELÉS (Ha kézzel nyomsz rá az adminban)
            deals = db.reference('deals').order_by_child('status').equal_to('sent').get()
            if deals:
                for d_id, d_data in deals.items():
                    send_telegram(f"🚀 *ADMIN ÉLESÍTETTE!*\n\n{d_data['title']}\n\n{d_data['link']}")
                    db.reference(f'deals/{d_id}').update({'status': 'completed'})

            # 3. RSS ÜTEMEZÉS
            if time.time() - last_rss_check > 1800:
                perform_scan()
                last_rss_check = time.time()

        except Exception as e:
            print(f"Hurok hiba: {e}")
        
        time.sleep(15)

threading.Thread(target=bot_loop, daemon=True).start()

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
