import os
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


class Config:
    # Session cookie key. Set a long random value in .env (placeholders are rejected).
    SECRET_KEY = os.environ.get("SECRET_KEY", "")

    # Firebase service account key: a file path in FIREBASE_CREDENTIALS
    # (default firebase-key.json) or the JSON text in FIREBASE_CREDENTIALS_JSON.
    # Never commit it.
    FIREBASE_CREDENTIALS = os.environ.get("FIREBASE_CREDENTIALS") or os.path.join(BASE_DIR, "firebase-key.json")
    FIREBASE_CREDENTIALS_JSON = os.environ.get("FIREBASE_CREDENTIALS_JSON", "")
    DB_BACKEND = os.environ.get("DB_BACKEND", "firestore")  # "memory" for tests
    # always PH time, even on a UTC server
    DB_TIME_ZONE = os.environ.get("DB_TIME_ZONE", "+08:00")

    PERMANENT_SESSION_LIFETIME = 60 * 60 * 8  # 8 hours
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    # ONLINE=1 on HTTPS hosting: secure cookies and proxy headers
    ONLINE = os.environ.get("ONLINE") == "1"
    SESSION_COOKIE_SECURE = ONLINE
    # Vercel is serverless and read-only: no threads, uploads or backups
    SERVERLESS = bool(os.environ.get("VERCEL"))
    # cache static files for a week online (URLs have ?v= for busting)
    SEND_FILE_MAX_AGE_DEFAULT = 7 * 24 * 60 * 60 if ONLINE else None

    MAX_CONTENT_LENGTH = 5 * 1024 * 1024  # 5 MB upload limit

    MODEL_DIR = os.path.join(BASE_DIR, "model")
    MODEL_PATH = os.path.join(MODEL_DIR, "linear_regression_pipeline.joblib")
    METRICS_PATH = os.path.join(MODEL_DIR, "metrics.json")

    DATA_DIR = os.path.join(BASE_DIR, "data")
    HISTORICAL_DATA_PATH = os.path.join(DATA_DIR, "historical_fleet_data.csv")
    SUPPLEMENTARY_DATA_PATH = os.path.join(DATA_DIR, "supplementary_data.csv")

    REPORTS_DIR = os.path.join(BASE_DIR, "reports")

    WTF_CSRF_TIME_LIMIT = None

    # reload edited templates without a restart
    TEMPLATES_AUTO_RELOAD = True
