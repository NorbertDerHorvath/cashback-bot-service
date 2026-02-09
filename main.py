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
        print(f">>> Firebase hiba az indulásnál: {e}")

# --- FUNKCIÓK ---

def send_telegram(message):
    print(f">>> Telegram küldés megkísérlése...")
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try: 
        r = requests.post(url, json={
            "chat_id": CHAT_ID, 
            "text": message, 
            "parse_mode": "Markdown",
            "disable_web_page_preview": False
        }, timeout=15)
        print(f">>> Telegram válasz státusz: {r.status_code}")
        return r.status_code == 200
    except Exception as e: 
        print(f">>> Telegram küldési hiba: {e}")
        return False

def perform_scan(force_reset=False):
    if force_reset:
        print("!!! RESET MŰVELET: Adatbázis ürítése folyamatban... !!!")
        db.reference('deals').delete()
        send_telegram("🗑️ *Az adatbázis törölve. Új szkennelés indult!*")

    ref = db.reference('deals')
    feeds = ["https://rss.app/feeds/UBlHGZPrkiBFdRod.xml", "https://rss.app/feeds/WsCQbaznNvga5E3d.xml"]
    keywords = ["geld", "cashback", "gratis", "100%", "probieren", "test"]
    
    for url in feeds:
        try:
            r = requests.get(url, timeout=20)
            soup = BeautifulSoup(r.content, "xml")
            items = soup.find_all('item')
            print(f">>> RSS Scan ({url}): {len(items)} elem letöltve.")
            
            for item in items:
                t = item.title.text.strip()
                l = item.link.text.strip()
                
                if any(k in t.lower() for k in keywords):
                    snapshot = ref.order_by_child('link').equal_to(l).get()
                    if not snapshot:
                        print(f">>> ÚJ TALÁLAT: {t}")
                        ref.push({
                            'title': t, 
                            'link': l, 
                            'status': 'pending', 
                            'timestamp': time.time()
                        })
        except Exception as e: 
            print(f">>> Szkennelési hiba ({url}): {e}")

# --- FŐ BOT HUROK (Polling) ---
def bot_loop():
    print("--- Háttérfolyamat elindítva (Polling mód) ---")
    last_rss_check = 0
    
    while True:
        try:
            # 1. DEBUG: Kiírjuk a logba, mit látunk épp a Firebase-ben
            cmd_ref = db.reference('commands/full_scan').get()
            print(f"DEBUG: Firebase parancs állapota jelenleg: {cmd_ref}")

            # 2. RESET ELLENŐRZÉSE
            if cmd_ref and isinstance(cmd_ref, dict):
                if cmd_ref.get('processed') == False:
                    print(">>> Reset parancsot észleltem (processed=False)!")
                    perform_scan(force_reset=True)
                    db.reference('commands/full_scan').update({'processed': True})
                    print(">>> Reset parancs feldolgozva, processed=True-ra állítva.")

            # 3. ÉLESÍTÉS ELLENŐRZÉSE
            deals = db.reference('deals').order_by_child('status').equal_to('sent').get()
            if deals:
                print(f">>> {len(deals)} db 'sent' státuszú elemet találtam. Küldés...")
                for deal_id, deal_data in deals.items():
                    msg = f"🚀 *AKCIÓ ÉLESÍTVE!*\n\n📌 {deal_data['title']}\n\n🔗 [Kattints ide]({deal_data['link']})"
                    if send_telegram(msg):
                        db.reference(f'deals/{deal_id}').update({'status': 'completed'})
                        print(f">>> {deal_data['title']} sikeresen elküldve és archiválva.")

            # 4. RSS SZKENNELÉS (30 percenként)
            current_time = time.time()
            if current_time - last_rss_check > 1800:
                print(">>> Ütemezett RSS szkennelés indul...")
                perform_scan()
                last_rss_check = current_time

        except Exception as e:
            print(f">>> Hiba a polling hurokban: {e}")
        
        time.sleep(5) 

# --- INDÍTÁS ---
if __name__ == "__main__":
    # Bot indítása külön szálon
    threading.Thread(target=bot_loop, daemon=True).start()
    
    # Flask indítása
    port = int(os.environ.get("PORT", 10000))
    print(f">>> Flask szerver indul a {port} porton...")
    app.run(host='0.0.0.0', port=port)
