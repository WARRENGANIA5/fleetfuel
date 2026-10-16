# Pag-upload sang FleetFuel online (Railway)

Pagkatapos sini, may HTTPS link ang system (halimbawa `https://gsu-fleetfuel.up.railway.app`)
nga mabuksan sa bisan ano nga phone, tablet, ukon computer nga may internet.

> **Ngaa indi Vercel?** Indi magkasya sa Vercel ang Python libraries sang model (mga 350 MB). Wala man
> sini sang MySQL, background tasks (auto-retrain kag backup), kag storage para sa photos. Ang Railway
> may tanan sina.

> **Antes mag-upload sang data sang gobyerno online,** pamangkot anay sa Data Protection Officer ukon
> ICT office sang agency (RA 10173, Data Privacy Act). Ang Railway nagabutang sang data sa servers sa gwa
> sang Pilipinas.

## Kada agency, isa ka Railway project

Ang kada agency (GSU, LGU, DepEd, kag iban pa) may kaugalingon nga **project** sa Railway nga may
kaugalingon nga database, gani indi makita sang isa ka agency ang data sang iban. Ulita lang ini nga
mga steps para sa kada agency.

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

### 3. Dugangi sang MySQL database
Sa Railway dashboard sang project: **+ New → Database → MySQL**.

### 4. I-upload ang system
```
railway up
```
Ginaupload sini ang folder kag ginabuild ang `Dockerfile`. Ang `venv`, `.env`, `backups`, kag photos
indi upod (`.railwayignore`). Ang una nga build mga 5–10 minutos.

### 5. I-set ang Variables sang app service
Sa dashboard, i-click ang app service → **Variables** → **Raw Editor**, kag i-paste ini.
Ilisan ang mga value nga may `<...>`:
```
MYSQLHOST=${{MySQL.MYSQLHOST}}
MYSQLPORT=${{MySQL.MYSQLPORT}}
MYSQLUSER=${{MySQL.MYSQLUSER}}
MYSQLPASSWORD=${{MySQL.MYSQLPASSWORD}}
MYSQLDATABASE=${{MySQL.MYSQLDATABASE}}
SECRET_KEY=<64 ka random characters>
ADMIN_USERNAME=<username sang admin>
ADMIN_PASSWORD=<password: 8+ characters, may letra kag numero>
ADMIN_FULL_NAME=<pangalan sang admin>
```
Para makahimo sang `SECRET_KEY`, padalagana ini sa project folder:
`venv\Scripts\python.exe -c "import secrets; print(secrets.token_hex(32))"`

### 6. Dugangi sang Volume (para sa photos kag backups)
I-right-click ang app service → **Attach Volume** → Mount path: `/data`.

### 7. Himo sang public link
App service → **Settings → Networking → Generate Domain**. Amo ini ang link nga ihatag sa mga user.
Buksan ini sa phone.

### 8. Pagkatapos sang una nga login
1. Mag-login gamit ang `ADMIN_USERNAME` kag `ADMIN_PASSWORD`.
2. **Panason ang `ADMIN_PASSWORD`** sa Variables (indi na ini kinahanglan).
3. **Settings → Organization**: isulat ang pangalan sang agency kag opisina.
4. Dugangi ang mga vehicle, dayon i-import ang trip records (Trip Records → Import CSV). Ang model
   magatrain sa iya lang gamit ang data sang agency.
5. Ang staff mag-sign up sa link, kag ang admin ang mag-approve sa **User Accounts**.

## Mga automatic nga nagadalagan online
- **HTTPS**: ginahatag sang Railway. Secure-only man ang login cookie.
- **Auto-restart**: kon mag-crash ang app, ginastart ini liwat sang Railway.
- **Auto-retrain**: ang model nagatrain liwat kon magbag-o ang trips ukon vehicles.
- **Backup kada 24 oras**: nakatago sa volume (`/data/backups`).
- **Philippine time**: sa dates kag sa oras sang records.

## Opsyonal: ilipat ang data halin sa office computer
Kon gusto mo dalhon online ang data nga ara na sa XAMPP:
1. Sa Railway, buksan ang MySQL service → **Variables**, kag kopyaha ang `MYSQL_PUBLIC_URL`
   (host, port, password).
2. Sa office computer:
   ```
   C:\xampp\mysql\bin\mysqldump.exe -u root government_fleet_fuel_prediction > export.sql
   C:\xampp\mysql\bin\mysql.exe -h <public host> -P <public port> -u root -p railway < export.sql
   ```
   Himua ini **antes** mag-login sa online system, kay ang `export.sql` nagatanda sa mga tables.
