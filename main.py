import firebase_admin
from firebase_admin import credentials, db
import requests
from bs4 import BeautifulSoup
import time
import threading
import os
from flask import Flask

# --- FLASK SZERVER ---
app = Flask(__name__)

@app.route('/')
def health_check():
    return "A Cashback Bot él és dolgozik!", 200

# --- KONFIGURÁCIÓ ---
JSON_FILE = "coupons-79d9f-firebase-adminsdk-fbsvc-6cfc7ef3a2.json" 
DB_URL = "https://coupons-79d9f-default-rtdb.europe-west1.firebasedatabase.app/"
TELEGRAM_TOKEN = "8210425098:AAEAkmwRXrIrk9vt2rytnvWhcqSVfxQYa6g"
CHAT_ID = "8494341633" 

# Firebase Inicializálása és Kapcsolat ellenőrzése
if not firebase_admin._apps:
    try:
        cred = credentials.Certificate(JSON_FILE)
        firebase_admin.initialize_app(cred, {'databaseURL': DB_URL})
        print(">>> Firebase hitelesítés sikeres!")
        
        # KÉNYSZERÍTETT ÍRÁSI TESZT: Megnézzük, tényleg látja-e az adatbázist
        db.reference('server_status').update({
            'last_boot': time.ctime(),
            'online': True
        })
        print(">>> Firebase írási teszt sikeres! Nézd meg a konzolban a 'server_status' ágat.")
        
    except Exception as e:
        print(f">>> KRITIKUS HIBA a Firebase csatlakozásnál: {e}")

# --- FUNKCIÓK ---

def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try: 
        r = requests.post(url, json={
            "chat_id": CHAT_ID, 
            "text": message, 
            "parse_mode": "Markdown"
        }, timeout=15)
        return r.status_code == 200
    except Exception as e: 
        print(f">>> Telegram hiba: {e}")
        return False

def perform_scan(force_reset=False):
    if force_reset:
        print("!!! RESET: Adatbázis ürítése !!!")
        db.reference('deals').delete()
        send_telegram("🗑️ *Adatbázis ürítve, új keresés indul!*")

    ref = db.reference('deals')
    feeds = ["https://rss.app/feeds/UBlHGZPrkiBFdRod.xml", "https://rss.app/feeds/WsCQbaznNvga5E3d.xml"]
    keywords = ["geld", "cashback", "gratis", "100%", "probieren", "test"]
    
    for url in feeds:
        try:
            r = requests.get(url, timeout=20)
            soup = BeautifulSoup(r.content, "xml")
            items = soup.find_all('item')
            for item in items:
                t = item.title.text.strip()
                l = item.link.text.strip()
                if any(k in t.lower() for k in keywords):
                    snapshot = ref.order_by_child('link').equal_to(l).get()
                    if not snapshot:
                        ref.push({'title': t, 'link': l, 'status': 'pending', 'timestamp': time.time()})
        except Exception as e: 
            print(f">>> RSS hiba: {e}")

# --- FŐ BOT HUROK ---
def bot_loop():
    print("--- Polling folyamat elindítva ---")
    last_rss_check = 0
    
    while True:
        try:
            # 1. RESET ELLENŐRZÉSE
            # Fontos: a reference-nél nincs per jel az elején!
            cmd_ref = db.reference('commands/full_scan').get()
            
            if cmd_ref and isinstance(cmd_ref, dict):
                is_processed = cmd_ref.get('processed')
                print(f"--- Ellenőrzés: processed={is_processed} ---") # Ez fog látszódni a logban
                
                if is_processed == False:
                    perform_scan(force_reset=True)
                    db.reference('commands/full_scan').update({'processed': True})

            # 2. ÉLESÍTÉS ELLENŐRZÉSE
            deals = db.reference('deals').order_by_child('status').equal_to('sent').get()
            if deals:
                for d_id, d_data in deals.items():
                    msg = f"🚀 *AKCIÓ ÉLESÍTVE!*\n\n📌 {d_data['title']}\n\n🔗 {d_data['link']}"
                    if send_telegram(msg):
                        db.reference(ff'deals/{d_id}').update({'status': 'completed'})

            # 3. ÜTEMEZETT SCAN
            if time.time() - last_rss_check > 1800:
                perform_scan()
                last_rss_check = time.time()

        except Exception as e:
            print(f">>> Hiba a hurokban: {e}")
        
        time.sleep(10) # 10 másodpercre emeltem, hogy ne blokkoljon a Firebase

if __name__ == "__main__":
    threading.Thread(target=bot_loop, daemon=True).start()
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
