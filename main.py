import firebase_admin
from firebase_admin import credentials, db
import requests
from bs4 import BeautifulSoup
import time
import threading
import os
from flask import Flask

# --- FLASK SZERVER (A Render ébren tartásához) ---
app = Flask(__name__)

@app.route('/')
def health_check():
    return "A Cashback Bot él és dolgozik!", 200

# --- KONFIGURÁCIÓ ---
# Fontos: A JSON fájl neve pontosan egyezzen meg a GitHub-on lévővel!
JSON_FILE = "coupons-79d9f-firebase-adminsdk-fbsvc-6cfc7ef3a2.json" 
DB_URL = "https://coupons-79d9f-default-rtdb.europe-west1.firebasedatabase.app/"
TELEGRAM_TOKEN = "8210425098:AAEAkmwRXrIrk9vt2rytnvWhcqSVfxQYa6g"
CHAT_ID = "8494341633" 

# Firebase Inicializálása
if not firebase_admin._apps:
    try:
        cred = credentials.Certificate(JSON_FILE)
        firebase_admin.initialize_app(cred, {'databaseURL': DB_URL})
        print(">>> Firebase sikeresen csatlakozva!")
    except Exception as e:
        print(f">>> Firebase hiba: {e}")

# --- FUNKCIÓK ---

def send_telegram(message):
    print(f">>> Telegram küldés: {message[:50]}...")
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try: 
        r = requests.post(url, json={
            "chat_id": CHAT_ID, 
            "text": message, 
            "parse_mode": "Markdown",
            "disable_web_page_preview": False
        }, timeout=15)
        print(f">>> Telegram válasz: {r.status_code}")
        return r.status_code == 200
    except Exception as e: 
        print(f">>> Telegram küldési hiba: {e}")
        return False

def perform_scan(force_reset=False):
    if force_reset:
        print("!!! RESET INDÍTVA: Adatbázis ürítése !!!")
        db.reference('deals').delete()
        send_telegram("🗑️ *Az adatbázis törölve. Új szkennelés indult!*")

    ref = db.reference('deals')
    # Az RSS feedjeid
    feeds = ["https://rss.app/feeds/UBlHGZPrkiBFdRod.xml", "https://rss.app/feeds/WsCQbaznNvga5E3d.xml"]
    keywords = ["geld", "cashback", "gratis", "100%", "probieren", "test"]
    
    for url in feeds:
        try:
            r = requests.get(url, timeout=20)
            soup = BeautifulSoup(r.content, "xml")
            items = soup.find_all('item')
            print(f">>> {url} szkennelése: {len(items)} elem található.")
            
            for item in items:
                t = item.title.text.strip()
                l = item.link.text.strip()
                
                if any(k in t.lower() for k in keywords):
                    # Ellenőrizzük, hogy ez a link szerepel-e már
                    snapshot = ref.order_by_child('link').equal_to(l).get()
                    if not snapshot:
                        print(f">>> Új találat: {t}")
                        ref.push({
                            'title': t, 
                            'link': l, 
                            'status': 'pending', 
                            'timestamp': time.time()
                        })
                        # Opcionális: értesítés az adminnak az új találatról
                        # send_telegram(f"🔍 *Új találat vár jóváhagyásra:*\n{t}")
        except Exception as e: 
            print(f">>> Szkennelési hiba ({url}): {e}")

# --- FŐ BOT HUROK (Polling) ---
def bot_loop():
    print("--- A háttérfolyamat elindult (Polling mód) ---")
    last_rss_check = 0
    
    while True:
        try:
            # 1. RESET PARANCS ELLENŐRZÉSE
            cmd_ref = db.reference('commands/full_scan').get()
            if cmd_ref and cmd_ref.get('processed') == False:
                perform_scan(force_reset=True)
                db.reference('commands/full_scan').update({'processed': True})

            # 2. ÉLESÍTENDŐ (APPROVED) ELEMEK ELLENŐRZÉSE
            # Az admin felületen 'sent' státuszra állítottuk a gombbal
            deals = db.reference('deals').order_by_child('status').equal_to('sent').get()
            if deals:
                for deal_id, deal_data in deals.items():
                    print(f">>> Élesítés folyamatban: {deal_data['title']}")
                    msg = f"🚀 *AKCIÓ ÉLESÍTVE!*\n\n📌 {deal_data['title']}\n\n🔗 [Kattints ide az ajánlathoz]({deal_data['link']})"
                    if send_telegram(msg):
                        # Ha elment, átállítjuk completed-re, hogy ne küldje újra
                        db.reference(f'deals/{deal_id}').update({'status': 'completed'})

            # 3. AUTOMATIKUS RSS SZKENNELÉS (30 percenként)
            current_time = time.time()
            if current_time - last_rss_check > 1800:
                print(">>> Ütemezett RSS szkennelés indítása...")
                perform_scan()
                last_rss_check = current_time

        except Exception as e:
            print(f">>> Hiba a bot hurokban: {e}")
        
        time.sleep(5) # 5 másodpercenként néz rá az adatbázisra

# --- INDÍTÁS ---
if __name__ == "__main__":
    # A bot logikáját elindítjuk egy külön szálon
    threading.Thread(target=bot_loop, daemon=True).start()
    
    # Elindítjuk a Flask szervert (Render portján)
    port = int(os.environ.get("PORT", 10000))
    print(f">>> Flask szerver indul a {port} porton...")
    app.run(host='0.0.0.0', port=port)
