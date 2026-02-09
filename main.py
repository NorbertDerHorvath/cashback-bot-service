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
        print(">>> Firebase SIKERES csatlakozás.")
except Exception as e:
    print(f">>> Firebase hiba: {e}")

def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try: 
        requests.post(url, json={"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"}, timeout=10)
    except Exception as e:
        print(f"Telegram hiba: {e}")

def perform_scan(force_reset=False):
    if force_reset:
        print("!!! RESET FOLYAMATBAN !!!")
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
                t = item.title.text.strip()
                l = item.link.text.strip()
                if any(k in t.lower() for k in keywords):
                    # Ellenőrzés: Létezik-e már a link?
                    exists = ref.order_by_child('link').equal_to(l).get()
                    if not exists:
                        print(f"Új ajánlat: {t}")
                        send_telegram(f"🔔 *ÚJ AJÁNLAT!*\n\n📌 {t}\n\n🔗 {l}")
                        ref.push({
                            'title': t, 
                            'link': l, 
                            'status': 'pending', 
                            'timestamp': time.time()
                        })
        except Exception as e:
            print(f"Szkennelési hiba ({url}): {e}")

def bot_loop():
    print(">>> Bot hurok elindítva...")
    last_rss_check = 0
    
    while True:
        try:
            # 1. RESET PARANCS FIGYELÉSE (Javított, robusztusabb verzió)
            cmd_ref = db.reference('commands/full_scan')
            cmd = cmd_ref.get()
            
            if cmd is not None:
                # Kezeljük ha dict, és ha sima boolean is
                is_processed = cmd.get('processed') if isinstance(cmd, dict) else True
                
                if is_processed is False:
                    print(">>> Reset parancs észlelve!")
                    perform_scan(force_reset=True)
                    cmd_ref.update({'processed': True, 'last_action': time.time()})

            # 2. ADMIN ÉLESÍTÉS FIGYELÉSE
            deals = db.reference('deals').order_by_child('status').equal_to('sent').get()
            if deals:
                for d_id, d_data in deals.items():
                    send_telegram(f"🚀 *ADMIN ÉLESÍTETTE!*\n\n{d_data['title']}\n\n{d_data['link']}")
                    db.reference(f'deals/{d_id}').update({'status': 'completed'})

            # 3. RSS SZKENNELÉS (30 percenként)
            now = time.time()
            if now - last_rss_check > 1800:
                perform_scan()
                last_rss_check = now

        except Exception as e:
            print(f"Hiba a hurokban: {e}")
        
        time.sleep(10) # 10 másodpercenként néz rá a parancsokra

# Flask futtatása külön szálon nem kell, az app.run blokkoló, 
# ezért a botot indítjuk threading-el.
threading.Thread(target=bot_loop, daemon=True).start()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
