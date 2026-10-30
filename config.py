import os
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


class Config:
    # Signs the session cookie. Must be a long random value kept secret in .env;
    # app.py refuses the known placeholder values (anyone knowing the key
    # could forge a logged-in session).
    SECRET_KEY = os.environ.get("SECRET_KEY", "")

    # Database: Firebase Firestore. The service account key of the Firebase
    # project (Project settings > Service accounts > Generate new private key)
    # is read from FIREBASE_CREDENTIALS (a file path, default firebase-key.json
    # next to this file) or, on hosting without files, from the key's JSON text
    # in FIREBASE_CREDENTIALS_JSON. Keep the key secret: it is not in git.
    FIREBASE_CREDENTIALS = os.environ.get("FIREBASE_CREDENTIALS") or os.path.join(BASE_DIR, "firebase-key.json")
    FIREBASE_CREDENTIALS_JSON = os.environ.get("FIREBASE_CREDENTIALS_JSON", "")
    DB_BACKEND = os.environ.get("DB_BACKEND", "firestore")  # "memory" only for automated tests
    # Dates and times follow Philippine time even on a server that runs in UTC.
    DB_TIME_ZONE = os.environ.get("DB_TIME_ZONE", "+08:00")

    PERMANENT_SESSION_LIFETIME = 60 * 60 * 8  # sessions expire after 8 hours
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    # Online (HTTPS) deployments set ONLINE=1: the session cookie is then sent
    # over HTTPS only, and the client address is read from the hosting proxy.
    ONLINE = os.environ.get("ONLINE") == "1"
    SESSION_COOKIE_SECURE = ONLINE
    # Vercel runs the app as short-lived serverless functions on a read-only
    # disk: no background threads, no retraining, no saved photos or backups.
    SERVERLESS = bool(os.environ.get("VERCEL"))
    # Online, let browsers keep CSS/JS/images for a week (their URLs carry a
    # ?v= version, so a changed file is still fetched again).
    SEND_FILE_MAX_AGE_DEFAULT = 7 * 24 * 60 * 60 if ONLINE else None

    MAX_CONTENT_LENGTH = 5 * 1024 * 1024  # reject request bodies over 5 MB before reading them

    MODEL_DIR = os.path.join(BASE_DIR, "model")
    # Online, deploy/start.sh points MODEL_STORE at the persistent volume, so a
    # model uploaded from Google Colab survives redeploys.
    MODEL_STORE = os.environ.get("MODEL_STORE") or MODEL_DIR
    MODEL_PATH = os.path.join(MODEL_STORE, "linear_regression_pipeline.joblib")
    METRICS_PATH = os.path.join(MODEL_STORE, "metrics.json")

    DATA_DIR = os.path.join(BASE_DIR, "data")
    HISTORICAL_DATA_PATH = os.path.join(DATA_DIR, "historical_fleet_data.csv")
    SUPPLEMENTARY_DATA_PATH = os.path.join(DATA_DIR, "supplementary_data.csv")

    REPORTS_DIR = os.path.join(BASE_DIR, "reports")

    WTF_CSRF_TIME_LIMIT = None

    # Pick up edited templates without restarting the server (Waitress runs
    # without debug mode, which otherwise caches them until a restart).
    TEMPLATES_AUTO_RELOAD = True
