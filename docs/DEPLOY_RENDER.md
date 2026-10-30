# Pag-upload sang FleetFuel sa Render (libre)

Pagkatapos sini, may HTTPS link ang system (halimbawa `https://fleetfuel.onrender.com`).
Ang database amo gihapon ang **Firebase Firestore** (pareho sa office computer), gani pareho ang data.

> **Limitasyon sang libre nga plan:**
> - Nagatulog ang system kon 15 minutos wala sing nagbukas. Ang masunod nga nagbukas maghulat mga
>   1 minuto samtang nagabugtaw ini. (Mga 230 ka Firestore reads kada bugtaw: wala problema sa 50,000/adlaw.)
> - Wala sing permanente nga disk: ang **backups** kag ang **model nga gin-upload** sa website madula
>   kon mag-restart ukon mag-redeploy. Ang model sa `model/` sang GitHub repo ang gamiton liwat.
>   Para permanente ang bag-o nga model, ibutang ini sa `model/` kag i-push sa GitHub.
>
> **Antes mag-upload sang data sang gobyerno online,** pamangkot anay sa Data Protection Officer ukon
> ICT office (RA 10173, Data Privacy Act).

## Mga steps

### 1. I-push ang project sa GitHub
Ang Render nagabuild halin sa GitHub repo `WARRENGANIA5/fleetfuel`, gani i-push anay ang pinakabag-o.

### 2. Himo sang Render account
Kadto sa <https://render.com> → **Get Started** → mag-sign up gamit ang **GitHub** account.

### 3. Himo sang service halin sa Blueprint
1. Sa dashboard: **New → Blueprint**.
2. Pili-a ang repo `fleetfuel` (kon wala, i-click ang **Configure GitHub** kag hatagi sang access).
3. Basahon sang Render ang `render.yaml`: isa ka web service nga `fleetfuel`, **Free**, Singapore.
4. I-click ang **Apply**. Ang una nga build mga 5–10 minutos.

### 4. I-upload ang Firebase key (Secret File)
1. Buksan ang `fleetfuel` service → **Environment** → **Secret Files** → **Add Secret File**.
2. Filename: `firebase-key.json`
3. Contents: i-paste ang bug-os nga sulod sang `firebase-key.json` sa project folder.
4. **Save Changes**. Magaredeploy ang Render sa iya lang.

Ang `SECRET_KEY` ginahimo na sang Render sa iya lang. Ang mga account (admin1114 kag staff) yara na sa
Firestore, gani amo man gihapon ang login.

### 5. Buksan ang link
Sa ibabaw sang service page may link (`https://fleetfuel-xxxx.onrender.com`). Amo ini ang ihatag sa
mga user. Kon ang Logs nagasiling `Serving on http://127.0.0.1:10000 (Waitress)`, nagadalagan na ini.

## Pag-update
Kada `git push` sa `main`, automatic nga nagabuild kag nagaupdate ang Render.

## Kon may problema
- **"Could not reach the database"** sa Logs: tan-awa kon husto ang Secret File (`firebase-key.json`).
- **Build failed**: tan-awa ang Logs; i-redeploy gamit ang **Manual Deploy → Deploy latest commit**.
- **Daw hinay sa una nga bukas**: normal ini sa libre nga plan (nagabugtaw).
