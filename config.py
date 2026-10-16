import os
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


class Config:
    # Signs the session cookie. Must be a long random value kept secret in .env;
    # app.py refuses the known placeholder values (anyone knowing the key
    # could forge a logged-in session).
    SECRET_KEY = os.environ.get("SECRET_KEY", "")

    # The MYSQL* names (no underscore) are the ones a Railway MySQL service
    # provides, so an online deployment needs no extra mapping.
    MYSQL_HOST = os.environ.get("MYSQL_HOST") or os.environ.get("MYSQLHOST") or "127.0.0.1"
    MYSQL_PORT = int(os.environ.get("MYSQL_PORT") or os.environ.get("MYSQLPORT") or 3306)
    MYSQL_USER = os.environ.get("MYSQL_USER") or os.environ.get("MYSQLUSER") or "root"
    MYSQL_PASSWORD = os.environ.get("MYSQL_PASSWORD") or os.environ.get("MYSQLPASSWORD") or ""
    MYSQL_DB = os.environ.get("MYSQL_DB") or os.environ.get("MYSQLDATABASE") or "government_fleet_fuel_prediction"
    # Cloud MySQL services (TiDB Cloud, Aiven, ...) only accept encrypted connections.
    MYSQL_SSL = (os.environ.get("MYSQL_SSL") or "").lower() in ("1", "true", "yes")
    # Dates and NOW() follow Philippine time even on a server that runs in UTC.
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

    MAX_CONTENT_LENGTH = 5 * 1024 * 1024  # reject request bodies over 5 MB before reading them

    MODEL_DIR = os.path.join(BASE_DIR, "model")
    MODEL_PATH = os.path.join(MODEL_DIR, "linear_regression_pipeline.joblib")
    METRICS_PATH = os.path.join(MODEL_DIR, "metrics.json")

    DATA_DIR = os.path.join(BASE_DIR, "data")
    HISTORICAL_DATA_PATH = os.path.join(DATA_DIR, "historical_fleet_data.csv")
    SUPPLEMENTARY_DATA_PATH = os.path.join(DATA_DIR, "supplementary_data.csv")

    REPORTS_DIR = os.path.join(BASE_DIR, "reports")

    WTF_CSRF_TIME_LIMIT = None

    # Pick up edited templates without restarting the server (Waitress runs
    # without debug mode, which otherwise caches them until a restart).
    TEMPLATES_AUTO_RELOAD = True
