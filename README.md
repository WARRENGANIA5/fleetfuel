# Performance of Linear Regression Model in Predicting Fuel Consumption for the Government Fleets

A thesis/capstone web system for **Guimaras State University's General Services Office (GSO)**,
predicting government fleet fuel consumption using a **Linear Regression** model trained on
the local trip records (Monthly Report of Official Travel) and a supplementary online dataset, served through a Flask web application with a Firebase Firestore database.

---

## 1. Tech Stack

Python, Flask, HTML5, CSS3, JavaScript, Bootstrap 5, Firebase Firestore, Pandas, NumPy, Scikit-learn,
Joblib, Statsmodels (VIF and regression assumption tests), Matplotlib, Seaborn, Chart.js (live charts),
Waitress (production WSGI server), Google Colab (notebook), Font Awesome.

## 2. Project Structure

```
gov-fleets/
├── app.py                     Flask application (routes, auth, CRUD)
├── config.py                  Configuration (reads .env)
├── db.py                      Firebase Firestore data layer (real-time sync)
├── init_db.py                 Checks Firestore; creates the first administrator (online setup)
├── requirements.txt          Web app libraries (what Vercel installs)
├── requirements-train.txt    + training, diagnostics and Waitress (office server)
├── model/
│   ├── preprocess.py           Shared preprocessing (train + predict)
│   ├── train_model.py          Trains & saves the Linear Regression pipeline
│   ├── diagnostics.py          VIF + LINE assumption tests (statsmodels)
│   ├── evaluate_model.py       Generates the evaluation figures for the paper (reports/figures/)
│   ├── linear_regression_pipeline.joblib   (generated)
│   └── metrics.json            (generated)
├── data/
│   ├── build_supplementary_dataset.py  Builds supplementary_data.csv from the online dataset
│   ├── add_eea_diesel_vans.py        Adds the EEA diesel vans to supplementary_data.csv
│   ├── historical_fleet_data.csv     Optional extra local trips (same columns)
│   └── supplementary_data.csv        Online trips: distance, engine power, fuel type, fuel consumed
├── templates/                  Jinja2 templates (login, dashboard, ...)
├── static/
│   ├── css/style.css
│   ├── js/script.js
│   └── images/ (favicon, generated charts/)
├── colab/                      Google Colab notebooks + the three training CSV files
├── start_server.bat            Backs up the database, starts the web app
├── backup_database.py          Database backup to backups/ (keeps the newest 30)
├── allow_network_access.bat    One-time firewall rule for LAN access
└── reports/figures/            Evaluation figures (generated)
```

## 3. About the Dataset

The model predicts the **fuel consumed per trip (L)** from three predictors and one interaction term:

    ŷ = β0 + β1(Distance) + β2(Engine Power) + β3(Fuel Type) + β4(Distance × Engine Power)

with fuel type encoded **1 = Gasoline, 0 = Diesel**.

* **Local data:** the GSO Monthly Report of Official Travel — date of travel, vehicle, distance traveled
  (km) and fuel consumed (L) — entered in **Trip Records**, merged with the **vehicle records** (plate number,
  vehicle model, fuel type, engine power in kW) using the plate number.
* **Supplementary dataset:** `data/supplementary_data.csv`, real-world records with the same variables from two
  open online datasets: gasoline trips (Fan & Song 2022) and diesel vans of many engine sizes (EEA 2024)
  (see `data/SUPPLEMENTARY_DATASET_SOURCE.md`).

## 4. Setup Instructions (Windows / VS Code)

### 4.1 Prerequisites
- Python 3.10+
- Internet connection and a Firebase project (free Spark plan is enough)

### 4.2 Create a virtual environment and install dependencies
```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements-train.txt
```

### 4.3 Create the Firebase Firestore database
1. Open https://console.firebase.google.com, **Add project** (e.g. `gsu-fleetfuel`).
2. **Build > Firestore Database > Create database**, choose a location near the Philippines
   (e.g. `asia-southeast1`), and start in **production mode** (only the server reads and writes it).
3. **Project settings (gear) > Service accounts > Generate new private key**. Save the downloaded
   file in this folder as **`firebase-key.json`**. Keep it secret: it is ignored by git.

Firestore needs no tables. The collections `users`, `vehicles`, `trip_records`, `predictions` and
`notification_dismissals` appear with their first record; `_counters/_changes` counts the saves (see `db.py`).

### 4.4 Configure environment variables
Copy `.env.example` to `.env` and set a long random `SECRET_KEY`. The key file is found automatically
as `firebase-key.json`; set `FIREBASE_CREDENTIALS` only if it is saved elsewhere.

### 4.5 Train the model
```bash
python model/train_model.py
python model/evaluate_model.py
```
This creates `model/linear_regression_pipeline.joblib`, `model/metrics.json`, and the figures in
`reports/figures/`. (The running app also trains the model by itself.) **Predictions will not work until this step is done** — the
Prediction page will show "Model unavailable" until a trained model file exists.

### 4.6 Create the administrator account
```bash
set ADMIN_PASSWORD=...
python init_db.py
```
Checks that Firestore can be reached and, on an empty database, creates the administrator account.
Vehicles and trips are entered in the system (Vehicle Management, Trip Records); no sample data is added.

**Administrator:** there is exactly one administrator account, created with the username **`admin1114`**
(`ADMIN_ACCOUNT` in `app.py`). It is recognized by its administrator role, so it opens the administrator
pages: every other account is staff and no other account can be made an administrator. Every account,
the administrator included, changes its own username, name, email and password under **Account Settings**;
User Accounts cannot change the administrator account. Never write `ADMIN_PASSWORD` in a file in git.

### 4.7 Run the application
```bash
python app.py
```
Visit **http://127.0.0.1:5000**.

> **Port note:** Flask's default port is 5000. If another local application is already using
> port 5000, either stop it first or run this app on a different port, e.g.:
> `python -c "from app import app; app.run(port=5050)"`.

## 5. Retraining the Model

Retraining is automatic. While the app runs, a background watcher retrains the Linear Regression
model within a few seconds whenever the training data changes:

- a trip record is added, edited or deleted;
- a vehicle's plate number, fuel type or engine power is edited, or a vehicle is deleted;
- `data/historical_fleet_data.csv` or `data/supplementary_data.csv` is replaced.

The model trains on the supplementary dataset **plus** every trip record in the system (merged with its
vehicle record). The Prediction, Dashboard and Model Performance pages switch to the new model by
themselves; no restart is needed. `python model/train_model.py` and `python model/evaluate_model.py`
still work for training outside the app and for regenerating the figures in `reports/figures/`.

## 5a. Database Backups

`start_server.bat` backs up every Firestore collection to a `.json` file in `backups/` every time the
system starts, and the running app backs it up again every 24 hours. The newest 30 backups are kept.
To make a backup at any time:
```bash
venv\Scripts\python.exe backup_database.py
```
To restore a backup (this **replaces** the records with the same IDs):
```bash
venv\Scripts\python.exe backup_database.py --restore backups\<file>.json
```
Copy the `backups/` folder to a USB drive or cloud storage now and then.

## 5b. Real-time data

While the server runs, Firestore snapshot listeners keep an up-to-date copy of every collection in
memory: a change saved from any computer reaches all pages within a moment (the pages refresh their
data every few seconds), and those refreshes cost no Firestore reads, so the system stays within the
free plan.

## 6. Machine Learning Pipeline Summary

1. Merge the trip records with the vehicle records by plate number; add the supplementary dataset
2. Clean: drop records with missing values or zero distance; remove outliers with the IQR rule on
   fuel used per 100 km, within each engine-power group
3. Encode fuel type (1 = Gasoline, 0 = Diesel); mean-center distance and engine power and add the interaction term Distance × Engine Power
4. Check multicollinearity with the Variance Inflation Factor (above 5 = high collinearity)
5. 80/20 train/test split
6. Train Linear Regression inside a scikit-learn `Pipeline` (encoding + model bundled)
7. Evaluate with R², MAE and RMSE on the test set and with 5-fold cross-validation
8. Residual plot and residual histogram; Durbin-Watson on the local trips arranged by date of travel
9. Save the fitted pipeline via Joblib and metrics to `model/metrics.json`
10. Prediction: staff select the vehicle and enter the distance; the system takes the vehicle's engine
    power and fuel type from its record, predicts the fuel, and stores the prediction in the history.

## 7. Security Notes

- Passwords hashed with Werkzeug's `generate_password_hash` (scrypt) — never stored in plain
  text or hardcoded.
- The database is only reached by the server with the Firebase service account key (`firebase-key.json`,
  never in git); the browser never talks to Firestore directly, so Firestore security rules can deny all
  client access.
- CSRF protection via Flask-WTF on all state-changing forms.
- All dashboard/module routes require an authenticated session (`login_required`).
- Change the default `SECRET_KEY` before any real deployment.

---

## Collecting the real data

* **Trip tickets:** Trip Records → **Add Trip Record** (one trip of the Monthly Report of Official Travel
  each). The model retrains automatically.
* **Supplementary dataset (open online sources):** `data/supplementary_data.csv` with the columns
  `distance_km, engine_power_kw, fuel_type, actual_fuel_consumption`. The app detects a replaced file and retrains.

## Multicollinearity and assumption checks

Distance and engine power are **mean-centered** (training-set means) before the interaction term is formed;
this removes the collinearity between the interaction and its components without changing any prediction, and
the fitted equation is also shown in the original units. Training reports the **VIF** of every term (above 5 =
high collinearity), uses **HC3 robust standard errors** for the coefficient p-values, and tests the LINE
conditions on the residuals: Ramsey RESET (linearity), Durbin-Watson (independence), Jarque-Bera (normality),
Breusch-Pagan (equal variance) and VIF (multicollinearity). Results appear on **Model Performance** and in the
Colab notebook. `python model/evaluate_model.py` saves print-ready
figures to `reports/figures/`.

## User accounts

The administrator manages the staff accounts under **User Accounts**: create an account,
edit its name and email, reset its password, and approve or reject sign-up requests. Resetting a password
signs that user out right away.

## Deployment on the GSO network

1. Connect the server PC to the GSO network and set that network to **Private** in Windows
   (Settings > Network > Properties). Run `allow_network_access.bat` once **as Administrator**; it opens
   port 5000 for Private/Domain networks only, never on public Wi-Fi.
2. Double-click `start_server.bat` (backs up the database, then starts the app with Waitress). If the
   app ever stops unexpectedly, the script starts it again after 10 seconds.
3. Other computers on the same network open `http://<this-PC-IP>:5000` (the script prints the address).
4. To start the system automatically whenever Windows signs in, run `install_autostart.bat` once
   (`uninstall_autostart.bat` turns it off). Also turn off Sleep on the server PC.
5. Before turning the server PC off, run `stop_server.bat`. The data itself lives in Firebase Firestore, so
   it is safe even if the PC is turned off suddenly; the server PC only needs an internet connection.

## Roles and fuel requests

* **Staff (GSO / motorpool):** predict fuel for a planned trip (each prediction is a *fuel request*), encode
  trips from the Monthly Report of Official Travel (add, edit), record the actual fuel after the trip, and view the
  dashboard and vehicles. The bell notifies them in real time when a request is
  approved (with the liters released) or rejected.
* **Administrators:** everything staff can do, plus approve/reject fuel requests and set the fuel to release
  (the predicted figure and range are the reference), manage vehicles, delete records and manage user
  accounts (including approving sign-ups). The bell and sidebar show pending requests and sign-ups in real time.
* **Sign up:** a new account waits for approval. The sign-up page checks the username, email and password
  while they are typed; after signing up (or logging in to a pending account) the waiting page checks every
  3 seconds and signs the user in automatically as soon as an administrator approves the account.
* After a trip, the actual fuel is flagged **outside the predicted range** when it differs from the prediction
  by more than the model's RMSE.

