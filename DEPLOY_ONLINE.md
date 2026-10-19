# Pag-upload sang FleetFuel online (Railway)

Pagkatapos sini, may HTTPS link ang system (halimbawa `https://gsu-fleetfuel.up.railway.app`)
nga mabuksan sa bisan ano nga phone, tablet, ukon computer nga may internet.

> **Ngaa indi Vercel?** Indi magkasya sa Vercel ang Python libraries sang model (mga 350 MB). Wala man
> sini sang background tasks (backup kag reconnect sa Firestore) kag storage para sa backups. Ang Railway
> may tanan sina. Ang database amo gihapon ang **Firebase Firestore** (pareho sa office computer).

> **Antes mag-upload sang data sang gobyerno online,** pamangkot anay sa Data Protection Officer ukon
> ICT office sang agency (RA 10173, Data Privacy Act). Ang Railway kag ang Firebase nagabutang sang data
> sa servers sa gwa sang Pilipinas.

## Mga steps

### 1. Himo sang account
Kadto sa <https://railway.com> kag mag-sign up. May trial credits sa umpisa. Para sa stable nga
paggamit, kinahanglan ang **Hobby plan (mga $5 kada bulan)**.

### 2. I-install ang Railway CLI kag mag-login
Sa terminal (PowerShell) sa sulod sang project folder:
```
npm install -g @railway/cli
railway login
railway init
```
Sa `railway init`, pili-a ang **Create new project** kag hatagi sang pangalan (halimbawa `gsu-fleetfuel`).

### 3. Ihanda ang Firebase key
Gamita ang Firebase project kag ang `firebase-key.json` sa README (4.3). Indi ginaupload ang file mismo;
ang sulod sini ang ibutang sa Variables (step 5). Para makuha ini sa isa ka linya:
`venv\Scripts\python.exe -c "import json; print(json.dumps(json.load(open('firebase-key.json'))))"`

### 4. I-upload ang system
```
railway up
```
Ginaupload sini ang folder kag ginabuild ang `Dockerfile`. Ang `venv`, `.env`, kag `backups`
indi upod (`.railwayignore`). Ang una nga build mga 5–10 minutos.

### 5. I-set ang Variables sang app service
Sa dashboard, i-click ang app service → **Variables** → **Raw Editor**, kag i-paste ini.
Ilisan ang mga value nga may `<...>`:
```
FIREBASE_CREDENTIALS_JSON=<ang isa ka linya halin sa step 3>
SECRET_KEY=<64 ka random characters>
ADMIN_PASSWORD=<password: 8+ characters, may letra kag numero>
ADMIN_FULL_NAME=<pangalan sang admin>
```
Para makahimo sang `SECRET_KEY`, padalagana ini sa project folder:
`venv\Scripts\python.exe -c "import secrets; print(secrets.token_hex(32))"`

### 6. Dugangi sang Volume (para sa backups)
I-right-click ang app service → **Attach Volume** → Mount path: `/data`.

### 7. Himo sang public link
App service → **Settings → Networking → Generate Domain**. Amo ini ang link nga ihatag sa mga user.
Buksan ini sa phone.

### 8. Pagkatapos sang una nga login
1. Mag-login gamit ang `admin1114` kag ang `ADMIN_PASSWORD`.
2. **Panason ang `ADMIN_PASSWORD`** sa Variables (indi na ini kinahanglan).
3. Dugangi ang mga vehicle, dayon ang trip records (Trip Records → Add Trip Record). Ang model
   magatrain sa iya lang gamit ang data sang GSU fleet.
4. Ang staff mag-sign up sa link, kag ang admin ang mag-approve sa **User Accounts**.

## Mga automatic nga nagadalagan online
- **HTTPS**: ginahatag sang Railway. Secure-only man ang login cookie.
- **Auto-restart**: kon mag-crash ang app, ginastart ini liwat sang Railway.
- **Model**: indi nagatrain liwat ang system sa iya lang. I-train sa Google Colab kag i-upload sa
  **Model Performance → Upload Trained Model**.
- **Backup kada 24 oras**: nakatago sa volume (`/data/backups`).
- **Philippine time**: sa dates kag sa oras sang records.

## Data halin sa office computer
Indi na kinahanglan ilipat: ang office computer kag ang online system nagagamit sang pareho nga
Firebase Firestore database, gani pareho ang ila nga data kag dayon makita ang pagbag-o sa duha.
