<!DOCTYPE html>
<html lang="hu">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Cashback Admin & Public Panel</title>
    <script src="https://www.gstatic.com/firebasejs/8.10.1/firebase-app.js"></script>
    <script src="https://www.gstatic.com/firebasejs/8.10.1/firebase-database.js"></script>
    <style>
        :root { 
            --admin-color: #2c3e50; 
            --accent-color: #e74c3c; 
            --success-color: #27ae60;
            --bg-color: #f4f7f6;
        }
        body { font-family: 'Segoe UI', Arial, sans-serif; background: var(--bg-color); margin: 0; padding: 20px; color: #333; }
        .container { max-width: 1000px; margin: auto; background: white; padding: 30px; border-radius: 15px; box-shadow: 0 10px 30px rgba(0,0,0,0.1); }
        
        header { display: flex; justify-content: space-between; align-items: center; border-bottom: 2px solid #eee; padding-bottom: 20px; margin-bottom: 20px; }
        #status-indicator { font-size: 14px; font-weight: bold; }

        /* Login Szekció */
        #login-section { background: #f9f9f9; padding: 20px; border-radius: 10px; text-align: center; margin-bottom: 25px; border: 1px solid #ddd; }
        input { padding: 12px; margin: 5px; border: 1px solid #ccc; border-radius: 5px; width: 200px; }
        .btn-login { background: var(--admin-color); color: white; border: none; padding: 12px 25px; cursor: pointer; border-radius: 5px; font-weight: bold; }

        /* Admin Vezérlőpult */
        #admin-controls { display: none; background: #fff5f5; padding: 20px; border-radius: 10px; margin-bottom: 25px; border: 1px solid #feb2b2; }
        .btn-reset { background: var(--accent-color); color: white; border: none; padding: 15px; width: 100%; border-radius: 8px; cursor: pointer; font-size: 16px; font-weight: bold; text-transform: uppercase; margin-bottom: 10px; }

        /* Táblázat */
        table { width: 100%; border-collapse: collapse; margin-top: 10px; }
        th { background: #f8fafc; color: #64748b; padding: 15px; text-align: left; font-size: 13px; text-transform: uppercase; border-bottom: 2px solid #edf2f7; }
        td { padding: 15px; border-bottom: 1px solid #edf2f7; vertical-align: middle; }
        tr:hover { background: #f1f5f9; }
        
        a { color: #3182ce; text-decoration: none; font-weight: 500; }
        a:hover { text-decoration: underline; }

        /* Gombok és Badge-ek */
        .btn { padding: 8px 15px; border: none; border-radius: 6px; cursor: pointer; font-size: 12px; font-weight: bold; transition: 0.2s; }
        .btn-approve { background: var(--success-color); color: white; margin-right: 5px; }
        .btn-delete { background: #94a3b8; color: white; }
        .btn:hover { opacity: 0.8; transform: translateY(-1px); }

        .badge { padding: 5px 10px; border-radius: 20px; font-size: 11px; font-weight: bold; text-transform: uppercase; }
        .status-pending { background: #fef3c7; color: #92400e; }
        .status-sent { background: #dcfce7; color: #166534; }
        .status-completed { background: #dbeafe; color: #1e40af; }

        .hidden { display: none; }
    </style>
</head>
<body>

<div class="container">
    <header>
        <h1 id="panel-title" style="margin:0; font-size: 24px;">Cashback Ajánlatok</h1>
        <div id="status-indicator">Kapcsolódás...</div>
    </header>

    <div id="login-section">
        <p style="margin-top:0;">Admin hozzáférés szükséges a kezeléshez:</p>
        <input type="text" id="username" placeholder="Felhasználónév">
        <input type="password" id="password" placeholder="Jelszó">
        <button class="btn-login" onclick="handleLogin()">Belépés</button>
    </div>

    <div id="admin-controls">
        <button class="btn-reset" onclick="triggerReset()">🔄 ADATBÁZIS TELJES ÜRÍTÉSE & ÚJ KERESÉS</button>
        <div style="display: flex; justify-content: space-between; align-items: center;">
            <span style="color: #c53030; font-size: 13px;"><b>Bejelentkezve:</b> Norbi</span>
            <button class="btn" style="background:#eee; color:#333;" onclick="location.reload()">Kijelentkezés</button>
        </div>
    </div>

    <table>
        <thead>
            <tr>
                <th>Idő</th>
                <th>Termék / Ajánlat</th>
                <th>Állapot</th>
                <th class="admin-only hidden">Műveletek</th>
            </tr>
        </thead>
        <tbody id="dealsTableBody">
            <tr><td colspan="4" style="text-align:center; padding: 40px; color: #999;">Betöltés folyamatban...</td></tr>
        </tbody>
    </table>
</div>

<script>
    // 1. Firebase Konfiguráció
    const firebaseConfig = {
        databaseURL: "https://coupons-79d9f-default-rtdb.europe-west1.firebasedatabase.app/"
    };
    firebase.initializeApp(firebaseConfig);
    const database = firebase.database();

    let isAdmin = false;

    // 2. Kapcsolat ellenőrzése
    database.ref('.info/connected').on('value', (snapshot) => {
        const indicator = document.getElementById('status-indicator');
        if (snapshot.val() === true) {
            indicator.innerHTML = "<span style='color: #27ae60;'>🟢 ONLINE</span>";
        } else {
            indicator.innerHTML = "<span style='color: #e74c3c;'>🔴 OFFLINE</span>";
        }
    });

    // 3. Bejelentkezés kezelése
    function handleLogin() {
        const u = document.getElementById('username').value;
        const p = document.getElementById('password').value;

        if (u === "norbi" && p === "norbi") {
            isAdmin = true;
            document.getElementById('login-section').classList.add('hidden');
            document.getElementById('admin-controls').style.display = 'block';
            document.getElementById('panel-title').innerText = "Cashback ADMIN";
            
            // Admin oszlop megjelenítése a táblázat fejlécében
            document.querySelectorAll('.admin-only').forEach(el => el.classList.remove('hidden'));
            
            fetchDeals(); // Adatok újratöltése admin módban
            console.log("Admin bejelentkezve: Norbi");
        } else {
            alert("Hibás felhasználónév vagy jelszó!");
        }
    }

    // 4. Adatok lekérése és megjelenítése
    function fetchDeals() {
        const dealsRef = database.ref('deals');
        dealsRef.on('value', (snapshot) => {
            const data = snapshot.val();
            const tbody = document.getElementById('dealsTableBody');
            tbody.innerHTML = '';

            if (!data) {
                tbody.innerHTML = '<tr><td colspan="4" style="text-align:center; padding: 20px;">Jelenleg nincs aktív ajánlat.</td></tr>';
                return;
            }

            // Kulcsok rendezése (legfrissebb elől)
            const sortedKeys = Object.keys(data).sort((a, b) => {
                return (data[b].timestamp || 0) - (data[a].timestamp || 0);
            });

            sortedKeys.forEach(key => {
                const deal = data[key];

                // SZŰRÉS: Ha nem admin, csak a 'sent' vagy 'completed' állapotút látja
                if (!isAdmin && deal.status === 'pending') return;

                const tr = document.createElement('tr');
                const time = deal.timestamp ? new Date(deal.timestamp * 1000).toLocaleTimeString('hu-HU', {hour: '2-digit', minute:'2-digit'}) : '--:--';

                tr.innerHTML = `
                    <td style="color: #64748b; font-size: 13px;">${time}</td>
                    <td><a href="${deal.link}" target="_blank">${deal.title}</a></td>
                    <td><span class="badge status-${deal.status}">${deal.status}</span></td>
                    <td class="admin-only ${isAdmin ? '' : 'hidden'}">
                        <button class="btn btn-approve" onclick="approveDeal('${key}')">KÜLDÉS</button>
                        <button class="btn btn-delete" onclick="deleteDeal('${key}')">TÖRLÉS</button>
                    </td>
                `;
                tbody.appendChild(tr);
            });
            
            if (tbody.innerHTML === '') {
                tbody.innerHTML = '<tr><td colspan="4" style="text-align:center; padding: 20px;">Nincs jóváhagyott publikus ajánlat.</td></tr>';
            }
        });
    }

    // 5. Műveletek (Admin funkciók)
    function approveDeal(id) {
        if (!isAdmin) return;
        database.ref('deals/' + id).update({
            status: 'sent'
        }).catch(err => alert("Hiba az élesítésnél: " + err.message));
    }

    function deleteDeal(id) {
        if (!isAdmin) return;
        if (confirm("Biztosan törlöd ezt az ajánlatot?")) {
            database.ref('deals/' + id).remove()
            .catch(err => alert("Hiba a törlésnél: " + err.message));
        }
    }

    function triggerReset() {
        if (!isAdmin) return;
        if (confirm("FIGYELEM: Ez minden jelenlegi ajánlatot töröl és új keresést indít. Biztosan mehet?")) {
            // 1. Deals ág ürítése
            database.ref('deals').remove()
            .then(() => {
                // 2. Parancs küldése a botnak
                return database.ref('commands/full_scan').set({
                    processed: false,
                    timestamp: Date.now() / 1000
                });
            })
            .then(() => {
                alert("Adatbázis ürítve, a parancs elküldve a botnak!");
            })
            .catch(err => alert("Hiba a reset során: " + err.message));
        }
    }

    // Kezdő futtatás (Public mód)
    fetchDeals();

</script>
</body>
</html>
