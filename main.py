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

# Firebase Inicializálása
try:
    if not firebase_admin._apps:
        cred = credentials.Certificate(JSON_FILE)
        firebase_admin.initialize_app(cred, {'databaseURL': DB_URL})
        print(">>> Firebase hitelesítés SIKERES!")
        
        # Állapot jelzése a Firebase-ben
        db.reference('server_status').update({
            'last_boot': time.ctime(),
            'online': True,
            'status': 'Bot loop starting...'
        })
except Exception as e:
    print(f">>> Firebase hiba: {e}")

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
    except: 
        return False

def perform_scan(force_reset=False):
    if force_reset:
        print("!!! RESET INDÍTVA !!!")
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
                        ref.push({
                            'title': t, 
                            'link': l, 
                            'status': 'pending', 
                            'timestamp': time.time()
                        })
        except Exception as e:
            print(f"Szkennelési hiba ({url}): {e}")

# --- BOT CIKLUS ---
def bot_loop():
    # Rövid várakozás, hogy a szerver teljesen felálljon
    time.sleep(5)
    print("--- Háttérfolyamat elindult ---")
    last_rss_check = 0
    
    while True:
        try:
            # 1. RESET PARANCS FIGYELÉSE
            cmd_ref = db.reference('commands/full_scan').get()
            
            # Ellenőrizzük, hogy dict-e és a processed értéke pontosan false-e
            if isinstance(cmd_ref, dict) and cmd_ref.get('processed') is False:
                print(">>> RESET parancs észlelve! Végrehajtás...")
                perform_scan(force_reset=True)
                # Azonnal visszaírjuk true-ra, hogy ne fusson végtelen ciklusban
                db.reference('commands/full_scan').update({'processed': True})
                print(">>> RESET kész, állapot frissítve.")

            # 2. ÉLESÍTÉS (SENT STÁTUSZ) FIGYELÉSE
            deals = db.reference('deals').order_by_child('status').equal_to('sent').get()
            if deals:
                print(f">>> {len(deals)} db élesítésre váró alkut találtam.")
                for d_id, d_data in deals.items():
                    msg = f"🚀 *AKCIÓ ÉLESÍTVE!*\n\n📌 {d_data['title']}\n\n🔗 {d_data['link']}"
                    if send_telegram(msg):
                        db.reference(f'deals/{d_id}').update({'status': 'completed'})

            # 3. ÜTEMEZETT RSS SZKENNELÉS (30 percenként)
            if time.time() - last_rss_check > 1800:
                print(">>> Automatikus RSS szkennelés indítása...")
                perform_scan()
                last_rss_check = time.time()
                # Frissítjük a szerver állapotát is, hogy lássuk, még él
                db.reference('server_status').update({'last_check': time.ctime()})

        except Exception as e:
            print(f"Hiba a bot hurokban: {e}")
        
        # 15 másodperc várakozás, hogy ne kapjunk 429 Too Many Requests hibát
        time.sleep(15)

# Háttérszál indítása
threading.Thread(target=bot_loop, daemon=True).start()

if __name__ == "__main__":
    # Render specifikus port beállítás
    port = int(os.environ.get("PORT", 10000))
    print(f">>> Flask indítása a {port} porton...")
    app.run(host='0.0.0.0', port=port)
