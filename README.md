# Performance of Linear Regression Model in Predicting Fuel Consumption for the Government Fleets

A thesis/capstone web system for **Guimaras State University's General Services Office (GSO)**,
predicting government fleet fuel consumption using a **Linear Regression** model trained on
the local trip records (Monthly Report of Official Travel) and a supplementary online dataset, served through a Flask + MySQL web application.

This is an original system adapted from the general fuel-prediction concept (Auto MPG +
Linear Regression) demonstrated in [Kanchu1147/Fuel_Consumption_Prediction_Of_Vehicles](https://github.com/Kanchu1147/Fuel_Consumption_Prediction_Of_Vehicles),
redesigned end-to-end (data schema, features, UI, database, and workflow) for a government
fleet / university motorpool context.

---

## 1. Tech Stack

Python, Flask, HTML5, CSS3, JavaScript, Bootstrap 5, MySQL, Pandas, NumPy, Scikit-learn,
Joblib, Statsmodels (VIF and regression assumption tests), Matplotlib, Seaborn, Chart.js (live charts),
Waitress (production WSGI server), Google Colab (notebook), Font Awesome.

## 2. Project Structure

```
gov-fleets/
├── app.py                     Flask application (routes, auth, CRUD)
├── config.py                  Configuration (reads .env)
├── db.py                      MySQL connection helper (PyMySQL)
├── seed_data.py                Seeds admin account + demo fleet data
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
│   ├── historical_fleet_data.csv     Optional extra local trips (same columns)
│   ├── supplementary_data.csv        Online trips: distance, engine power, fuel type, fuel consumed
│   └── dataset_info.json       Fingerprints of the synthetic files ("Demo data" label)
├── database/
│   └── government_fleet_fuel.sql
├── templates/                  Jinja2 templates (login, dashboard, ...)
├── static/
│   ├── css/style.css
│   ├── js/script.js
│   └── images/ (favicon, generated charts/)
├── notebooks/
│   └── fuel_consumption_linear_regression.ipynb   Google Colab workflow
├── start_server.bat            Starts MySQL, backs up the database, starts the web app
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
* **Supplementary dataset:** `data/supplementary_data.csv`, real-world trips from an open online dataset with
  the same variables (see `data/SUPPLEMENTARY_DATASET_SOURCE.md`).

## 4. Setup Instructions (Windows / VS Code)

### 4.1 Prerequisites
- Python 3.10+
- MySQL Server (e.g. XAMPP's MySQL/MariaDB, or standalone MySQL)

### 4.2 Create a virtual environment and install dependencies
```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements-train.txt
```

### 4.3 Create the database
Start your MySQL server, then import the schema:
```bash
mysql -u root -p < database/government_fleet_fuel.sql
```
(If your MySQL root user has no password, omit `-p`.)

### 4.4 Configure environment variables
Copy `.env.example` to `.env` and adjust if your MySQL credentials differ from the defaults
(`root` / no password / `localhost:3306`).

### 4.5 Train the model
```bash
python model/train_model.py
python model/evaluate_model.py
```
This creates `model/linear_regression_pipeline.joblib`, `model/metrics.json`, and the figures in
`reports/figures/`. (The running app also trains the model by itself.) **Predictions will not work until this step is done** — the
Prediction page will show "Model unavailable" until a trained model file exists.

### 4.6 Seed the database
```bash
python seed_data.py
```
Creates the administrator account and demo vehicles and trip records so the
dashboard and modules are populated on first run.

**Default login:**
- Username: `admin`
- Password: `Admin@12345`

(A second account `motorpool` / `Motorpool@2026` with the `staff` role is also created.)
Change these passwords after first login via **Settings**. Anyone who logs in with one of these
default passwords is sent straight to Settings with a reminder until it is changed.

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

- a trip record is added, edited, imported (Trip Records > Import CSV) or deleted;
- a vehicle's plate number, fuel type or engine power is edited, or a vehicle is deleted;
- `data/historical_fleet_data.csv` or `data/supplementary_data.csv` is replaced.

The model trains on the supplementary dataset **plus** every trip record in the system (merged with its
vehicle record). The Prediction, Dashboard and Model Performance pages switch to the new model by
themselves; no restart is needed. `python model/train_model.py` and `python model/evaluate_model.py`
still work for training outside the app and for regenerating the figures in `reports/figures/`.

## 5a. Database Backups

`start_server.bat` backs up the whole MySQL database to `backups/` every time the system starts,
and the running app backs it up again every 24 hours. The newest 30 backups are kept. To make a
backup at any time:
```bash
venv\Scripts\python.exe backup_database.py
```
To restore a backup (this **replaces** the current data):
```bash
C:\xampp\mysql\bin\mysql.exe -u root government_fleet_fuel_prediction < backups\<file>.sql
```
Copy the `backups/` folder to a USB drive or cloud storage now and then, so the collected
records survive if the computer fails.

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
- All SQL queries use parameterized statements (PyMySQL `%s` placeholders).
- CSRF protection via Flask-WTF on all state-changing forms.
- All dashboard/module routes require an authenticated session (`login_required`).
- Change the default `SECRET_KEY` and demo account passwords before any real deployment.

---

## Collecting the real data

Until the synthetic CSV files in `data/` are replaced, every model page shows a **"Demo data"** label
(detected automatically from `data/dataset_info.json`), so demo results are never reported as findings.

* **Trip tickets:** Trip Records → **Import CSV** (download the template there). Every row is validated;
  nothing is imported unless all rows are valid. The model retrains automatically.
* **Supplementary dataset (open online sources):** `data/supplementary_data.csv` with the columns
  `distance_km, engine_power_kw, fuel_type, actual_fuel_consumption`. The app detects a replaced file and retrains.

## Multicollinearity and assumption checks

Distance and engine power are **mean-centered** (training-set means) before the interaction term is formed;
this removes the collinearity between the interaction and its components without changing any prediction, and
the fitted equation is also shown in the original units. Training reports the **VIF** of every term (above 5 =
high collinearity), uses **HC3 robust standard errors** for the coefficient p-values, and tests the LINE
conditions on the residuals: Ramsey RESET (linearity), Durbin-Watson (independence), Jarque-Bera (normality),
Breusch-Pagan (equal variance) and VIF (multicollinearity). Results appear on **Model Performance**, in the
**Model Performance Report**, and in the Colab notebook. `python model/evaluate_model.py` saves print-ready
figures to `reports/figures/`.

## User accounts

Administrators manage accounts under **User Accounts** (create, edit role/status, reset password).
Staff accounts use the rest of the system. Deactivated accounts are signed out immediately; at least one
active administrator always remains.

## Deployment on the GSO network

1. Connect the server PC to the GSO network and set that network to **Private** in Windows
   (Settings > Network > Properties). Run `allow_network_access.bat` once **as Administrator**; it opens
   port 5000 for Private/Domain networks only, never on public Wi-Fi.
2. Double-click `start_server.bat` (starts XAMPP MySQL if needed, then the app with Waitress). If the
   app ever stops unexpectedly, the script starts it again after 10 seconds.
3. Other computers on the same network open `http://<this-PC-IP>:5000` (the script prints the address).
4. To start the system automatically whenever Windows signs in, run `install_autostart.bat` once
   (`uninstall_autostart.bat` turns it off). Also turn off Sleep on the server PC.
5. Before turning the server PC off, run `stop_server.bat`: it shuts MySQL down cleanly. (Turning the PC
   off while MySQL runs can corrupt its tables; `start_server.bat` checks and repairs them on every start.)

### Database security (do this on every server PC)

The database must only be reachable by the app on the same PC, never from the network:

1. In `C:\xampp\mysql\bin\my.ini`, under `[mysqld]`, set `bind-address="127.0.0.1"` and restart MySQL.
2. Give the app its own MySQL account instead of `root` (replace the password with a long random one):
   ```sql
   CREATE USER 'fleetfuel'@'127.0.0.1' IDENTIFIED BY '<long-random-password>';
   GRANT ALL PRIVILEGES ON government_fleet_fuel_prediction.* TO 'fleetfuel'@'127.0.0.1';
   GRANT SELECT ON mysql.proc TO 'fleetfuel'@'127.0.0.1';
   ```
3. In `.env` set `MYSQL_HOST=127.0.0.1`, `MYSQL_USER=fleetfuel` and `MYSQL_PASSWORD=<that password>`.
   Use `127.0.0.1`, not `localhost`: on Windows `localhost` tries IPv6 first and every page waits ~2 s.

## Roles and fuel requests

* **Staff (GSO / motorpool):** predict fuel for a planned trip (each prediction is a *fuel request*), encode
  trips from the Monthly Report of Official Travel (add, edit, CSV import), record the actual fuel after the trip, and view the
  dashboard, vehicles, model performance and reports. The bell notifies them in real time when a request is
  approved (with the liters released) or rejected.
* **Administrators:** everything staff can do, plus approve/reject fuel requests and set the fuel to release
  (the predicted figure and range are the reference), manage vehicles, delete records and manage user
  accounts (including approving sign-ups). The bell and sidebar show pending requests in real time.
* After a trip, the actual fuel is flagged **outside the predicted range** when it differs from the prediction
  by more than the model's RMSE.

