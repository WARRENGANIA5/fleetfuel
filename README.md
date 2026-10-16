# Performance of Linear Regression Model in Predicting Fuel Consumption for the Government Fleets

A thesis/capstone web system for **Guimaras State University's General Services Office (GSO)**,
predicting government fleet fuel consumption using a **Linear Regression** model trained on
historical trip and fuel records, served through a Flask + MySQL web application.

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
├── requirements.txt
├── model/
│   ├── preprocess.py           Shared preprocessing (train + predict)
│   ├── train_model.py          Trains & saves the Linear Regression pipeline
│   ├── diagnostics.py          VIF variable selection + LINE assumption tests (statsmodels)
│   ├── evaluate_model.py       Generates the evaluation figures for the paper (reports/figures/)
│   ├── linear_regression_pipeline.joblib   (generated)
│   └── metrics.json            (generated)
├── data/
│   ├── generate_dataset.py     Builds the historical + supplementary datasets
│   ├── historical_fleet_data.csv     (generated)
│   ├── supplementary_data.csv        (generated)
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

Guimaras State University does not yet have a digitized historical trip/fuel logbook, so
`data/generate_dataset.py` generates a physically-consistent **synthetic historical dataset**
(1,500 trip/fuel records across 11 representative fleet vehicle types) that stands in for that
collection. Fuel consumption in this dataset is generated from realistic relationships
(terrain, road type, load, speed, vehicle age, trip type) plus random noise — it is **training
data**, not a prediction formula. The Linear Regression model in `model/train_model.py` learns
its own coefficients from this data via scikit-learn; nothing is hardcoded at prediction time.

**To use real GSU fleet records instead:** replace `data/historical_fleet_data.csv` with the
real, digitized trip/fuel export, keeping the same column names, then re-run
`model/train_model.py`.

## 4. Setup Instructions (Windows / VS Code)

### 4.1 Prerequisites
- Python 3.10+
- MySQL Server (e.g. XAMPP's MySQL/MariaDB, or standalone MySQL)

### 4.2 Create a virtual environment and install dependencies
```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
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

### 4.5 Generate the dataset and train the model
```bash
python data/generate_dataset.py
python model/train_model.py
python model/evaluate_model.py
```
This creates `model/linear_regression_pipeline.joblib`, `model/metrics.json`, and the 4 charts
used on the Model Performance page. **Predictions will not work until this step is done** — the
Prediction page will show "Model unavailable" until a trained model file exists.

### 4.6 Seed the database
```bash
python seed_data.py
```
Creates the administrator account and demo vehicles/drivers/trips/fuel records so the
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

- a trip record with an actual fuel value is added, edited, imported (Trip Records > Import CSV) or deleted;
- a vehicle's type, engine, fuel type or year model is edited, or a vehicle is deleted;
- `data/historical_fleet_data.csv` or `data/supplementary_data.csv` is replaced.

The model trains on the CSV dataset **plus** every trip record in the system that has an actual
fuel value. The Prediction, Dashboard and Model Performance pages switch to the new model by
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

1. Load historical dataset + merge supplementary vehicle efficiency ratings
2. Clean missing values, filter invalid ranges, remove target outliers (IQR)
3. Select predictors: distance, duration, avg. speed, load, engine displacement, year model,
   odometer, rated efficiency (numeric) + trip type, departure period, route, road type,
   terrain, vehicle type, fuel type (categorical, one-hot encoded)
4. 80/20 train/test split
5. Train Linear Regression inside a scikit-learn `Pipeline` (preprocessing + model bundled)
6. Evaluate with R², MAE, RMSE on the held-out test set
7. 5-Fold Cross-Validation on the full dataset
8. Save the fitted pipeline via Joblib and metrics to `model/metrics.json`
9. Flask loads the same pipeline to preprocess and predict on live form input — training and
   prediction always use identical preprocessing because it is the same saved object.

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
* **Historical dataset:** replace `data/historical_fleet_data.csv` (same column names). The app detects
  the change and retrains.
* **Supplementary dataset (open online sources):** put the online trip records in
  `data/supplementary_data.csv` with the same column names as the historical file (it must include
  `actual_fuel_consumption`). The rows are merged into the training data and every predictor the online
  dataset does not have is dropped from the model, as stated in the Scope and Limitations. The merge
  result (sources and dropped variables) is shown on Model Performance. The current file is a per-vehicle-type
  rated-efficiency table, which is joined on `vehicle_type` instead.

## Variable selection and assumption checks

Training first removes numeric predictors with **no measurable link to fuel use** (|r| < 0.10 with fuel
consumption), then removes predictors with **VIF > 5** (highest first), then tests the LINE conditions on
the training residuals: Ramsey RESET (linearity), Durbin-Watson (independence), Jarque-Bera (normality),
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

## Using the system in another government office

Each office runs its **own copy** on its own server PC, so every agency's data stays separate:

1. Copy the project folder (without `backups/`, `static/images/avatars/` and `.env`) to the new server PC
   and follow sections 4.1–4.7 and the database security steps above. Create a new random `SECRET_KEY`.
2. Log in as the administrator, open **Settings → Organization**, and enter the agency name, short name,
   office name and office short name. The login page, sidebar, page titles, printed reports and the
   Terms & Privacy Policy change immediately.
3. Replace the demo vehicles, trips and routes with the office's own records (Trip Records → Import CSV).
   The model retrains automatically on that office's data.

## Roles and fuel requests

* **Staff (GSO / motorpool):** predict fuel for a planned trip (each prediction is a *fuel request*), encode
  trip tickets and fuel logs (add, edit, CSV import), record the actual fuel after the trip, and view the
  dashboard, vehicles, model performance and reports. The bell notifies them in real time when a request is
  approved (with the liters released) or rejected.
* **Administrators:** everything staff can do, plus approve/reject fuel requests and set the fuel to release
  (the predicted figure and range are the reference), manage vehicles, delete records and manage user
  accounts (including approving sign-ups). The bell and sidebar show pending requests in real time.
* After a trip, the actual fuel is flagged **outside the predicted range** when it differs from the prediction
  by more than the model's RMSE.

