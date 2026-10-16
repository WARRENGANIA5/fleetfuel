import csv
import io
import json
import os
import re
import sys
import threading
import time
from datetime import date, datetime, timedelta
from functools import wraps

import joblib
import numpy as np
import pymysql
import pandas as pd
from flask import (Flask, Response, flash, g, redirect, render_template,
                    request, session, url_for)
from flask_wtf import CSRFProtect
from PIL import Image, UnidentifiedImageError
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

import db
from config import Config
from timeutil import now_local, today_local
from model.preprocess import attach_rated_efficiency, build_prediction_frame

app = Flask(__name__)
app.config.from_object(Config)
if app.config["ONLINE"]:
    # Behind the hosting provider's HTTPS proxy: take the visitor's address and
    # scheme from its headers, so login lockouts and sign-up limits apply per
    # visitor instead of to everyone at once.
    from werkzeug.middleware.proxy_fix import ProxyFix
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

_PLACEHOLDER_SECRETS = {"", "change-this-to-a-random-secret-key", "gsu-fleet-fuel-prediction-dev-secret-2026"}
if app.config["SECRET_KEY"] in _PLACEHOLDER_SECRETS or len(app.config["SECRET_KEY"]) < 32:
    import secrets
    app.config["SECRET_KEY"] = secrets.token_hex(32)
    print(" * WARNING: SECRET_KEY in .env is missing or a placeholder; using a temporary random key. "
          "Set a long random SECRET_KEY in .env (everyone is logged out on every restart until you do).")

csrf = CSRFProtect(app)
db.init_app(app)

AVATAR_DIR = os.path.join(app.root_path, "static", "images", "avatars")
AVATAR_MAX_BYTES = 3 * 1024 * 1024
AVATAR_MAX_DIMENSION = 512
try:
    os.makedirs(AVATAR_DIR, exist_ok=True)
except OSError:
    pass  # read-only disk (serverless hosting): photos cannot be saved there

VEHICLE_TYPES = ["Sedan", "SUV", "Van", "Pickup Truck", "Service Bus", "Dump Truck", "Motorcycle"]
TRIP_TYPES = ["Official Business", "Errand", "Hauling", "Airport Transfer", "Field Visit", "Other"]
ROAD_TYPES = ["Paved", "Unpaved", "Mixed"]
TERRAINS = ["Flat", "Hilly", "Mountainous"]
FUEL_TYPES = ["Diesel", "Gasoline"]

REPORT_TYPES = {
    "vehicle": "Vehicle Report",
    "trip": "Trip Report",
    "fuel": "Fuel Consumption Report",
    "prediction": "Prediction Report",
    "model": "Model Performance Report",
}

_MODEL = None
_MODEL_MTIME = None


def get_model():
    """Loads (and hot-reloads if the file changes) the trained Linear
    Regression pipeline. Returns None if no model has been trained yet."""
    global _MODEL, _MODEL_MTIME
    ensure_model_current()
    path = app.config["MODEL_PATH"]
    if not os.path.exists(path):
        return None
    mtime = os.path.getmtime(path)
    if _MODEL is None or mtime != _MODEL_MTIME:
        try:
            _MODEL = _retry_io(lambda: joblib.load(path))
            _MODEL_MTIME = mtime
        except (OSError, EOFError, ValueError):
            if _MODEL is None:
                raise
            app.logger.warning("Model file busy; using the previously loaded model for now")
    return _MODEL


def _retry_io(fn, attempts=20, delay=0.05):
    """Run a file read, retrying briefly while Windows/OneDrive has the file
    locked (e.g. while a retrain is swapping in the new model or metrics)."""
    for i in range(attempts):
        try:
            return fn()
        except (PermissionError, json.JSONDecodeError, EOFError):
            if i == attempts - 1:
                raise
            time.sleep(delay)


_LAST_METRICS = {"value": None}


def get_metrics():
    path = app.config["METRICS_PATH"]
    if not os.path.exists(path):
        return None

    def read():
        with open(path) as f:
            return json.load(f)
    try:
        metrics = _retry_io(read)
        _LAST_METRICS["value"] = dict(metrics)
    except (OSError, json.JSONDecodeError):
        if _LAST_METRICS["value"] is None:
            raise
        app.logger.warning("metrics.json busy; using the last metrics read")
        metrics = dict(_LAST_METRICS["value"])
    try:
        metrics["trained_at_display"] = datetime.fromisoformat(metrics["trained_at"]).strftime("%B %d, %Y %I:%M %p")
    except (KeyError, ValueError):
        metrics["trained_at_display"] = metrics.get("trained_at", "N/A")
    return metrics


_DATASET_STATUS = {"key": None, "value": None}


def dataset_status():
    """Whether the training CSVs are still the synthetic demo files (their
    SHA-256 matches data/dataset_info.json). Re-checked only when a file changes."""
    paths = {"historical_fleet_data.csv": app.config["HISTORICAL_DATA_PATH"],
             "supplementary_data.csv": app.config["SUPPLEMENTARY_DATA_PATH"]}
    info_path = os.path.join(app.config["DATA_DIR"], "dataset_info.json")
    try:
        key = tuple(os.path.getmtime(p) for p in list(paths.values()) + [info_path])
    except OSError:
        return {"synthetic_files": [], "demo": False}
    if _DATASET_STATUS["key"] != key:
        import hashlib
        with open(info_path, encoding="utf-8") as f:
            known = json.load(f).get("synthetic_sha256", {})
        synthetic = []
        for name, path in paths.items():
            with open(path, "rb") as f:
                if known.get(name) == hashlib.sha256(f.read()).hexdigest():
                    synthetic.append(name)
        _DATASET_STATUS.update(key=key, value={"synthetic_files": synthetic, "demo": bool(synthetic)})
    return _DATASET_STATUS["value"]


def format_time(value):
    if isinstance(value, timedelta):
        total = int(value.total_seconds())
        return f"{total // 3600:02d}:{(total % 3600) // 60:02d}"
    return value


def get_known_routes():
    """Routes from the historical dataset plus every route already used in
    the system's trip records, so new routes show up as suggestions."""
    routes = set()
    try:
        df = pd.read_csv(app.config["HISTORICAL_DATA_PATH"])
        routes.update(df["route"].dropna().astype(str).str.strip())
    except Exception:
        pass
    try:
        routes.update(r["route"].strip() for r in db.query_all("SELECT DISTINCT route FROM trip_records") if r["route"])
    except Exception:
        pass
    return sorted(r for r in routes if r)


def avatar_url(path):
    """Static URL for a profile photo, versioned by file time so a new photo
    shows immediately everywhere instead of a cached old one."""
    if not path:
        return None
    full = os.path.join(app.root_path, "static", path)
    version = int(os.path.getmtime(full)) if os.path.exists(full) else 0
    return url_for("static", filename=path) + f"?v={version}"


def password_signature(password_hash):
    """Short fingerprint of the stored hash, kept in the session to notice password changes."""
    import hashlib
    return hashlib.sha256((password_hash or "").encode()).hexdigest()[:16]


def compact_ids(*tables):
    """After a delete, point each table's next ID at MAX(id) + 1, so deleting the
    newest record doesn't leave a gap and IDs keep counting up from 1."""
    for table in tables:
        try:
            db.execute(f"ALTER TABLE {table} AUTO_INCREMENT = 1")
        except Exception:
            app.logger.exception("Could not reset the ID counter of %s", table)


def session_ended(reason):
    """Answer for a page's background request after its session ended (logged
    out, deactivated, password changed): script.js sees the header and opens
    the login page, which shows why. A 200 keeps the browser console clean."""
    return {"error": reason, "session_ended": True}, 200, {"X-Session-Ended": reason, "X-Redirect": url_for("login")}


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            if request.path.startswith("/api/"):
                return session_ended("not_logged_in")
            return redirect(url_for("login"))
        # Re-check the account on every request: a deactivated or deleted
        # account is signed out right away, and name/role/photo changes made
        # elsewhere show up without logging in again.
        user = db.query_one("SELECT id, username, full_name, role, status, profile_photo, password_hash FROM users WHERE id = %s",
                            (session["user_id"],))
        if not user or user["status"] != "active":
            session.clear()
            flash("Your account is no longer active. Please contact the administrator.", "danger")
            if request.path.startswith("/api/"):
                return session_ended("account_inactive")
            return redirect(url_for("login"))
        # A password reset or change signs out every other session of that account
        # (sessions from before this check existed are adopted, not signed out).
        sig = password_signature(user["password_hash"])
        if session.setdefault("pw_sig", sig) != sig:
            session.clear()
            flash("Your password was changed. Please log in with the new password.", "warning")
            if request.path.startswith("/api/"):
                return session_ended("password_changed")
            return redirect(url_for("login"))
        session["username"], session["full_name"] = user["username"], user["full_name"]
        session["role"], session["profile_photo"] = user["role"], user["profile_photo"]
        # Logged in with a default (published) password: only the password
        # change itself is allowed until a new one is set.
        if session.get("must_change_pw") and request.endpoint not in _ALLOWED_BEFORE_PW_CHANGE:
            if request.path.startswith("/api/"):
                return {"error": "password_change_required"}, 200, {"X-Redirect": url_for("settings")}
            flash("Please change the default password first.", "warning")
            return redirect(url_for("settings"))
        return view(*args, **kwargs)
    return wrapped


_ALLOWED_BEFORE_PW_CHANGE = {"settings", "change_password", "api_me", "api_notifications",
                             "api_notifications_seen", "api_notifications_dismiss", "api_notifications_dismiss_all"}


def admin_required(view):
    """Pages and actions for the administrator (GSO) only: approving fuel
    requests, user accounts, vehicles, reports and model monitoring (login is
    checked first)."""
    @wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        if session.get("role") != "admin":
            if request.path.startswith("/api/"):
                flash("That page is for the administrator (General Services Office) only.", "danger")
                return {"error": "forbidden"}, 200, {"X-Redirect": url_for("dashboard")}
            flash("That page is for the administrator (General Services Office) only.", "danger")
            return redirect(url_for("dashboard"))
        return view(*args, **kwargs)
    return wrapped


def _pending_requests():
    if session.get("role") != "admin":
        return 0
    try:
        return db.query_one("SELECT COUNT(*) AS c FROM predictions WHERE approval_status = 'pending'")["c"]
    except Exception:
        return 0


def _pending_accounts():
    if session.get("role") != "admin":
        return 0
    try:
        return db.query_one("SELECT COUNT(*) AS c FROM users WHERE status = 'pending'")["c"]
    except Exception:
        return 0


# ------------------------------------------------------------------
# ORGANIZATION (lets any government office run its own copy of the
# system under its own name; set by an administrator in Settings)
# ------------------------------------------------------------------
ORG_DEFAULTS = {
    "org_name": "Guimaras State University",
    "org_short": "GSU",
    "office_name": "General Services Office",
    "office_short": "GSO",
}
ORG_LIMITS = {"org_name": 120, "org_short": 15, "office_name": 120, "office_short": 15}
_ORG_TABLE_READY = {"ok": False}


def _ensure_org_table():
    if _ORG_TABLE_READY["ok"]:
        return
    db.execute("""
        CREATE TABLE IF NOT EXISTS app_settings (
            setting_key VARCHAR(50) NOT NULL PRIMARY KEY,
            setting_value VARCHAR(255) NOT NULL
        ) ENGINE=InnoDB
    """)
    _ORG_TABLE_READY["ok"] = True


def get_org():
    """The organization's names (defaults until an administrator sets them).
    Never fails: error pages render even when the database is down."""
    if "org" in g:
        return g.org
    org = dict(ORG_DEFAULTS)
    try:
        _ensure_org_table()
        for row in db.query_all("SELECT setting_key, setting_value FROM app_settings"):
            if row["setting_key"] in org and row["setting_value"].strip():
                org[row["setting_key"]] = row["setting_value"]
    except Exception:
        app.logger.exception("Could not load organization settings; using defaults")
    org["system_short"] = f"{org['org_short']} FleetFuel"
    g.org = org
    return org


@app.context_processor
def inject_globals():
    return {
        "org": get_org(),
        "today": today_local().isoformat(),
        "is_admin": session.get("role") == "admin",
        "current_year": today_local().year,
        "notif_count": g.get("notif_count", 0),
        "session_avatar_url": avatar_url(session.get("profile_photo")),
        "dataset": dataset_status() if session.get("user_id") else {"demo": False, "synthetic_files": []},
        "pending_accounts": _pending_accounts(),
        "pending_requests": _pending_requests(),
    }


_NOTIF_TABLE_READY = {"ok": False}
NOTIF_KEY_RE = re.compile(r"[a-z]+:\d+(:[a-z0-9]+)?")


def _ensure_notif_table():
    """Creates the per-user 'removed notifications' table on first use, so an
    existing database needs no manual migration."""
    if _NOTIF_TABLE_READY["ok"]:
        return
    db.execute("""
        CREATE TABLE IF NOT EXISTS notification_dismissals (
            user_id INT NOT NULL,
            notif_key VARCHAR(80) NOT NULL,
            dismissed_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (user_id, notif_key),
            CONSTRAINT fk_notif_dismissals_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        ) ENGINE=InnoDB
    """)
    _NOTIF_TABLE_READY["ok"] = True


def build_notifications(limit=8):
    """Bell notifications for the current user, minus the ones they removed.

    * everyone: vehicles under maintenance;
    * administrators: fuel requests waiting for approval (actionable);
    * staff: approvals / rejections of their own fuel requests, counted as
      new until they open the bell.
    Each item has a `key`; a removed key stays hidden, but a new event gets a
    new key (e.g. an approved request that is later rejected shows up again)."""
    _ensure_notif_table()
    uid, is_admin = session.get("user_id"), session.get("role") == "admin"
    removed = {r["notif_key"] for r in db.query_all(
        "SELECT notif_key FROM notification_dismissals WHERE user_id = %s", (uid,))}
    items, count = [], 0
    if is_admin:
        pending = db.query_all("""
            SELECT p.id, p.predicted_fuel, p.route, p.created_at, v.plate_number, u.full_name
            FROM predictions p LEFT JOIN vehicles v ON p.vehicle_id = v.id LEFT JOIN users u ON p.user_id = u.id
            WHERE p.approval_status = 'pending' ORDER BY p.created_at DESC, p.id DESC
        """)
        pending = [r for r in pending if f"request:{r['id']}" not in removed]
        count += len(pending)
        for r in pending[:limit]:
            items.append({"kind": "request", "id": r["id"], "key": f"request:{r['id']}", "icon": "fa-file-signature",
                          "text": f"Fuel request #{r['id']} needs approval",
                          "sub": f"{r['plate_number'] or 'Manual Entry'} · {float(r['predicted_fuel']):.2f} L predicted · {r['full_name'] or 'Staff'}",
                          "time": r["created_at"].strftime("%b %d, %I:%M %p"),
                          "url": url_for("prediction_result", prediction_id=r["id"]), "new": True})
    else:
        seen = db.query_one("SELECT notif_seen_at FROM users WHERE id = %s", (uid,))["notif_seen_at"]
        decided = db.query_all("""
            SELECT p.id, p.approval_status, p.approved_fuel, p.predicted_fuel, p.reviewed_at, v.plate_number
            FROM predictions p LEFT JOIN vehicles v ON p.vehicle_id = v.id
            WHERE p.user_id = %s AND p.approval_status <> 'pending' AND p.reviewed_at IS NOT NULL
              AND p.reviewed_at >= NOW() - INTERVAL 14 DAY
            ORDER BY p.reviewed_at DESC
        """, (uid,))
        decided = [r for r in decided if f"decision:{r['id']}:{r['approval_status']}" not in removed][:limit]
        for r in decided:
            is_new = seen is None or r["reviewed_at"] > seen
            count += 1 if is_new else 0
            approved = r["approval_status"] == "approved"
            items.append({"kind": "decision", "id": r["id"], "key": f"decision:{r['id']}:{r['approval_status']}",
                          "icon": "fa-circle-check" if approved else "fa-circle-xmark",
                          "text": f"Fuel request #{r['id']} {'approved' if approved else 'rejected'}",
                          "sub": (f"{r['plate_number'] or 'Manual Entry'} · {float(r['approved_fuel']):.2f} L released"
                                  if approved and r["approved_fuel"] is not None else f"{r['plate_number'] or 'Manual Entry'}"),
                          "time": r["reviewed_at"].strftime("%b %d, %I:%M %p"),
                          "url": url_for("prediction_result", prediction_id=r["id"]), "new": is_new,
                          "status": r["approval_status"]})
    maintenance = db.query_all("""
        SELECT id, plate_number, vehicle_type, brand_model, updated_at
        FROM vehicles WHERE status = 'Maintenance' ORDER BY updated_at DESC
    """)
    shown = 0
    for r in maintenance:
        # The timestamp is part of the key: a vehicle sent back to maintenance later alerts again.
        key = f"maintenance:{r['id']}:{r['updated_at']:%Y%m%d%H%M%S}" if r["updated_at"] else f"maintenance:{r['id']}"
        if key in removed:
            continue
        count += 1
        if shown < 10:
            shown += 1
            items.append({"kind": "maintenance", "id": r["id"], "key": key, "icon": "fa-triangle-exclamation",
                          "text": f"{r['plate_number']} needs maintenance",
                          "sub": f"{r['vehicle_type']} · {r['brand_model']}",
                          "time": r["updated_at"].strftime("%b %d, %Y") if r["updated_at"] else "",
                          "url": url_for("vehicles", status="Maintenance"), "new": False})
    return {"count": count, "notifications": items}


@app.before_request
def load_notifications():
    if request.endpoint == "static":  # no DB work for CSS/JS/image requests
        return
    if session.get("user_id"):
        try:
            g.notif_count = build_notifications()["count"]
        except Exception:
            g.notif_count = 0


@app.route("/api/notifications")
@login_required
def api_notifications():
    data = build_notifications()
    if session.get("role") == "admin":
        data.update(pending_requests=_pending_requests(), pending_accounts=_pending_accounts())
    return data


def _dismiss(keys):
    keys = [k for k in keys if isinstance(k, str) and len(k) <= 80 and NOTIF_KEY_RE.fullmatch(k)]
    _ensure_notif_table()
    for k in keys:
        db.execute("INSERT IGNORE INTO notification_dismissals (user_id, notif_key) VALUES (%s, %s)",
                   (session["user_id"], k))
    # Keys of events long past are never shown again; keep the table small.
    db.execute("DELETE FROM notification_dismissals WHERE user_id = %s AND dismissed_at < NOW() - INTERVAL 90 DAY",
               (session["user_id"],))
    return len(keys)


@app.route("/api/notifications/dismiss", methods=["POST"])
@login_required
def api_notifications_dismiss():
    """Remove one notification from the current user's bell."""
    key = (request.form.get("key") or (request.get_json(silent=True) or {}).get("key") or "").strip()
    if not _dismiss([key]):
        return {"error": "invalid_key"}, 400
    return api_notifications()


@app.route("/api/notifications/dismiss-all", methods=["POST"])
@login_required
def api_notifications_dismiss_all():
    """Remove every notification currently in the current user's bell."""
    _dismiss([n["key"] for n in build_notifications(limit=10_000)["notifications"]])
    return api_notifications()


@app.route("/api/notifications/seen", methods=["POST"])
@login_required
def api_notifications_seen():
    """Opening the bell marks the current decisions as read (staff)."""
    db.execute("UPDATE users SET notif_seen_at = NOW() WHERE id = %s", (session["user_id"],))
    return {"ok": True}


# ------------------------------------------------------------------
# AUTH
# ------------------------------------------------------------------
@app.route("/")
def index():
    return redirect(url_for("dashboard") if session.get("user_id") else url_for("login"))


# Passwords of the seeded demo accounts (seed_data.py / README); anyone who
# reads the guide knows them, so users logging in with one are sent to change it.
DEFAULT_PASSWORDS = {"Admin@12345", "Motorpool@2026"}

# Brute-force protection: 5 failed logins for the same username from the same
# address lock that pair out for 15 minutes.
_LOGIN_FAILURES = {}
_LOGIN_LOCK = threading.Lock()
LOGIN_MAX_FAILURES = 5
LOGIN_LOCK_SECONDS = 15 * 60


def _login_locked_for(key):
    with _LOGIN_LOCK:
        entry = _LOGIN_FAILURES.get(key)
        if not entry:
            return 0
        count, first = entry
        if time.time() - first > LOGIN_LOCK_SECONDS:
            _LOGIN_FAILURES.pop(key, None)
            return 0
        return int(LOGIN_LOCK_SECONDS - (time.time() - first)) if count >= LOGIN_MAX_FAILURES else 0


def _record_login_failure(key):
    with _LOGIN_LOCK:
        count, first = _LOGIN_FAILURES.get(key, (0, time.time()))
        if time.time() - first > LOGIN_LOCK_SECONDS:
            count, first = 0, time.time()
        _LOGIN_FAILURES[key] = (count + 1, first)


@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user_id"):
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        key = (request.remote_addr or "", username.lower())
        wait = _login_locked_for(key)
        if wait:
            flash(f"Too many failed login attempts. Please try again in {wait // 60 + 1} minute(s).", "danger")
            return render_template("login.html")

        user = db.query_one("SELECT * FROM users WHERE username = %s", (username,))
        if user and check_password_hash(user["password_hash"], password) and user["status"] != "active":
            _LOGIN_FAILURES.pop(key, None)
            if user["status"] == "pending":
                flash("Your account is waiting for administrator approval. Please try again once it is approved.", "warning")
            else:
                flash("Your account has been deactivated. Please contact the administrator.", "danger")
            return render_template("login.html")
        if user and check_password_hash(user["password_hash"], password):
            _LOGIN_FAILURES.pop(key, None)
            session.clear()
            session.permanent = True  # honour PERMANENT_SESSION_LIFETIME (8 hours)
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["full_name"] = user["full_name"]
            session["role"] = user["role"]
            session["profile_photo"] = user["profile_photo"]
            session["pw_sig"] = password_signature(user["password_hash"])
            flash(f"Welcome back, {user['full_name']}.", "success")
            if password in DEFAULT_PASSWORDS:
                session["must_change_pw"] = True  # every other page stays locked until it is changed
                flash("You are still using the default password that is printed in the setup guide. "
                      "Change it now under Change Password to continue using the system.", "warning")
                return redirect(url_for("settings"))
            return redirect(url_for("dashboard"))

        _record_login_failure(key)
        flash("Invalid username or password.", "danger")

    return render_template("login.html")


_SIGNUPS = {}
SIGNUP_LIMIT_PER_HOUR = 5


@app.route("/signup", methods=["GET", "POST"])
def signup():
    """Self-registration for GSO and motorpool staff. New accounts are
    created as 'pending' staff accounts and can log in only after an
    administrator approves them under User Accounts."""
    if session.get("user_id"):
        return redirect(url_for("dashboard"))
    form = {}
    if request.method == "POST":
        f = request.form
        form = {"full_name": f.get("full_name", ""), "username": f.get("username", ""), "email": f.get("email", "")}
        ip = request.remote_addr or ""
        with _LOGIN_LOCK:
            recent = [t for t in _SIGNUPS.get(ip, []) if time.time() - t < 3600]
            _SIGNUPS[ip] = recent
        errors, full_name, email = validate_user_form(dict(f, role="staff", status="active"))
        problem = password_problem(f.get("password", ""), f.get("username", ""))
        if problem:
            errors.append(problem)
        elif f.get("password") != f.get("confirm_password"):
            errors.append("Password and confirmation do not match.")
        if not (f.get("email") or "").strip():
            errors.insert(0, "Email is required.")
        if not f.get("agree_terms"):
            errors.append("You must agree to the Terms & Conditions and Privacy Policy.")
        if len(recent) >= SIGNUP_LIMIT_PER_HOUR:
            errors = ["Too many sign-ups from this computer. Please try again later."]
        if errors:
            for e in errors:
                flash(e, "danger")
            return render_template("signup.html", form=form)
        db.execute("""INSERT INTO users (username, password_hash, full_name, email, role, status)
                      VALUES (%s, %s, %s, %s, 'staff', 'pending')""",
                   (f["username"].strip(), generate_password_hash(f["password"]), full_name, email or None))
        with _LOGIN_LOCK:
            _SIGNUPS.setdefault(ip, []).append(time.time())
        flash("Account created! An administrator must approve it before you can log in.", "success")
        return redirect(url_for("login"))
    return render_template("signup.html", form=form)


@app.route("/logout", methods=["GET", "POST"])
def logout():
    # Only a POST (with the CSRF token) logs out, so another website can't
    # sign users out by linking to /logout.
    if request.method == "POST":
        session.clear()
        return redirect(url_for("login"))
    return redirect(url_for("dashboard") if session.get("user_id") else url_for("login"))


# ------------------------------------------------------------------
# DASHBOARD
# ------------------------------------------------------------------
def build_dashboard_context():
    """Fleet Overview for the administrator (GSO): every fuel request, the ones
    waiting for approval and the model status. Staff (motorpool) get their own
    dashboard: only the fuel requests they made, with their status."""
    is_admin = session.get("role") == "admin"
    # Scope of the fuel-request figures: everyone's for the admin, own for staff.
    mine_sql, mine_params = ("", ()) if is_admin else (" AND p.user_id = %s", (session.get("user_id"),))
    total_vehicles = db.query_one("SELECT COUNT(*) AS c FROM vehicles")["c"]
    total_trips = db.query_one("SELECT COUNT(*) AS c FROM trip_records")["c"]
    req = db.query_one(f"""
        SELECT COUNT(*) AS total, SUM(p.approval_status = 'pending') AS pending,
               SUM(p.approval_status = 'approved') AS approved, SUM(p.approval_status = 'rejected') AS rejected
        FROM predictions p WHERE 1=1{mine_sql}""", mine_params)
    total_predictions = int(req["total"] or 0)
    requests_summary = {k: int(req[k] or 0) for k in ("pending", "approved", "rejected")}

    avg_row = db.query_one(
        "SELECT AVG(actual_fuel_consumption) AS avg_fuel FROM trip_records WHERE actual_fuel_consumption IS NOT NULL"
    )
    avg_fuel = avg_row["avg_fuel"]
    if avg_fuel is None:
        avg_row2 = db.query_one("SELECT AVG(predicted_fuel) AS avg_fuel FROM predictions")
        avg_fuel = avg_row2["avg_fuel"]
    avg_fuel = round(float(avg_fuel), 2) if avg_fuel is not None else 0.0

    recent_predictions_rows = db.query_all(f"""
        SELECT p.*, v.plate_number, u.full_name
        FROM predictions p
        LEFT JOIN vehicles v ON p.vehicle_id = v.id
        LEFT JOIN users u ON p.user_id = u.id
        WHERE 1=1{mine_sql}
        ORDER BY p.created_at DESC LIMIT 5
    """, mine_params)
    recent_predictions = [{
        "id": r["id"], "status": r["approval_status"],
        "url": url_for("prediction_result", prediction_id=r["id"]),
        "created_at_display": r["created_at"].strftime("%b %d, %Y %I:%M %p"),
        "plate_number": r["plate_number"] or "N/A",
        "vehicle_type": r["vehicle_type"],
        "distance_km": f"{float(r['distance_km']):.2f}",
        "fuel_type": r["fuel_type"],
        "predicted_fuel": f"{float(r['predicted_fuel']):.2f}",
        "full_name": r["full_name"] or "System",
    } for r in recent_predictions_rows]

    # Last 6 calendar months up to the latest month with fuel records (the
    # logs are often encoded months later), with months that have no fuel
    # records shown as 0 instead of silently skipped.
    latest = db.query_one("SELECT MAX(fuel_date) AS d FROM fuel_records")["d"] or today_local()
    months = []
    y, m = latest.year, latest.month
    for _ in range(6):
        months.append((y, m))
        y, m = (y, m - 1) if m > 1 else (y - 1, 12)
    months.reverse()
    first_month = date(months[0][0], months[0][1], 1)
    trend_rows = db.query_all("""
        SELECT DATE_FORMAT(fuel_date, '%%Y-%%m') AS ym, SUM(liters_consumed) AS total
        FROM fuel_records WHERE fuel_date >= %s
        GROUP BY ym
    """, (first_month,))
    totals = {r["ym"]: float(r["total"]) for r in trend_rows}
    has_fuel_records = db.query_one("SELECT COUNT(*) AS c FROM fuel_records")["c"] > 0
    fuel_trend_labels = [date(y, m, 1).strftime("%b %Y") for y, m in months] if has_fuel_records else []
    fuel_trend_values = [round(totals.get(f"{y:04d}-{m:02d}", 0.0), 2) for y, m in months] if has_fuel_records else []

    # The 10 latest predictions: the predicted liters show as soon as a
    # prediction is made, the actual liters once they are recorded in
    # Prediction History (None = not recorded yet, drawn as a gap).
    avp_rows = db.query_all(f"""
        SELECT p.actual_fuel, p.predicted_fuel, p.created_at FROM predictions p
        WHERE 1=1{mine_sql}
        ORDER BY p.created_at DESC, p.id DESC LIMIT 10
    """, mine_params)
    avp_rows = list(reversed(avp_rows))
    avp_labels = [r["created_at"].strftime("%b %d, %I:%M %p") for r in avp_rows]
    avp_actual = [float(r["actual_fuel"]) if r["actual_fuel"] is not None else None for r in avp_rows]
    avp_predicted = [float(r["predicted_fuel"]) for r in avp_rows]
    avp_missing = sum(a is None for a in avp_actual)

    usage_rows = db.query_all("""
        SELECT v.plate_number, COUNT(t.id) AS trip_count
        FROM trip_records t JOIN vehicles v ON t.vehicle_id = v.id
        GROUP BY v.id ORDER BY trip_count DESC, v.plate_number
    """)
    if len(usage_rows) > 7:
        others = sum(r["trip_count"] for r in usage_rows[6:])
        usage_rows = usage_rows[:6] + [{"plate_number": f"Others ({len(usage_rows) - 6} vehicles)",
                                        "trip_count": others}]
    usage_colors = ["#2697ff", "#26e5ff", "#ffcf26", "#ee2727", "#6c5dd3", "#26e5c5", "#ff8a26"]

    model_summary = get_metrics() if is_admin else None   # model monitoring is the GSO's

    return {
        "stats": {"total_vehicles": total_vehicles, "total_trips": total_trips,
                  "total_predictions": total_predictions, "avg_fuel": avg_fuel, **requests_summary},
        "recent_predictions": recent_predictions,
        "fuel_trend_labels": fuel_trend_labels, "fuel_trend_values": fuel_trend_values,
        "avp_labels": avp_labels, "avp_actual": avp_actual, "avp_predicted": avp_predicted, "avp_missing": avp_missing,
        "vehicle_usage_labels": [r["plate_number"] for r in usage_rows],
        "vehicle_usage_values": [r["trip_count"] for r in usage_rows],
        "usage_colors": usage_colors,
        "model_summary": model_summary,
    }


@app.route("/dashboard")
@login_required
def dashboard():
    ensure_model_current()
    ctx = build_dashboard_context()
    usage_rows = [{"plate_number": p, "trip_count": v}
                   for p, v in zip(ctx["vehicle_usage_labels"], ctx["vehicle_usage_values"])]
    return render_template("dashboard.html", active="dashboard", vehicle_usage=usage_rows, **ctx)


@app.route("/api/dashboard-data")
@login_required
def api_dashboard_data():
    ensure_model_current()
    return build_dashboard_context()


# ------------------------------------------------------------------
# PREDICTION
# ------------------------------------------------------------------
PREDICTION_NUMERIC_LIMITS = {
    # field: (label, min, max, allow_min_equal)
    "odometer_reading": ("Odometer reading", 0, 2_000_000, True),
    "distance_km": ("Distance traveled", 0, 1000, False),
    "duration_minutes": ("Trip duration", 0, 1440, False),
    "avg_speed_kmh": ("Average speed", 0, 160, False),
    "passenger_cargo_load_kg": ("Passenger / cargo load", 0, 20_000, True),
    "engine_displacement": ("Engine displacement", 0, 20, False),
}
PREDICTION_FEATURE_LABELS = {
    "odometer_reading": ("Odometer", "km"), "distance_km": ("Distance", "km"),
    "duration_minutes": ("Duration", "min"), "avg_speed_kmh": ("Average speed", "km/h"),
    "passenger_cargo_load_kg": ("Load", "kg"), "engine_displacement": ("Engine displacement", "L"),
    "year_model": ("Year model", ""),
}
PREDICTION_CATEGORY_LABELS = {
    "vehicle_type": "vehicle type", "fuel_type": "fuel type",
    "road_type": "road type", "terrain_classification": "terrain",
}


def get_prediction_vehicles():
    """Active vehicles with the latest known odometer: the higher of the
    vehicle's recorded odometer and the end of its most recent trip."""
    return db.query_all("""
        SELECT v.id, v.plate_number, v.brand_model, v.vehicle_type, v.engine_displacement,
               v.fuel_type, v.year_model,
               GREATEST(COALESCE(v.current_odometer, 0),
                        COALESCE(MAX(t.odometer_reading + t.distance_km), 0)) AS latest_odometer
        FROM vehicles v LEFT JOIN trip_records t ON t.vehicle_id = v.id
        WHERE v.status = 'Active'
        GROUP BY v.id ORDER BY v.plate_number
    """)


PREDICTION_DEFAULTS = {
    "trip_type": ("Official Business", "trip type"), "departure_time": ("08:00", "departure time"),
    "passenger_cargo_load_kg": ("0", "load (kg)"), "route": ("Not specified", "route"),
    "road_type": ("Paved", "road type"), "terrain_classification": ("Flat", "terrain"),
}


def fill_prediction_defaults(form):
    """Only the distance is required to predict. Every other blank field is
    filled in: vehicle details from the selected vehicle (or the fleet's most
    common vehicle), duration/speed from each other (or the fleet's typical
    average speed), and standard values for the rest. Returns the completed
    form and a list of the values that were assumed."""
    f = {k: (v.strip() if isinstance(v, str) else v) for k, v in form.items()}
    assumed = []

    def blank(field):
        return not (f.get(field) or "").strip()

    def assume(field, value, label):
        f[field] = str(value)
        assumed.append(f"{label}: {value}")

    vehicle = None
    if (f.get("vehicle_id") or "").isdigit():
        vehicle = next((v for v in get_prediction_vehicles() if str(v["id"]) == f["vehicle_id"]), None)
    if vehicle is None and any(blank(k) for k in ("vehicle_type", "engine_displacement", "fuel_type", "year_model")):
        vehicle = db.query_one("""
            SELECT vehicle_type, engine_displacement, fuel_type, year_model, 0 AS latest_odometer
            FROM vehicles GROUP BY vehicle_type, engine_displacement, fuel_type, year_model
            ORDER BY COUNT(*) DESC LIMIT 1""")
    fallback = vehicle or {"vehicle_type": "Van", "engine_displacement": 2.5, "fuel_type": "Diesel",
                           "year_model": today_local().year, "latest_odometer": 0}
    for field, label in (("vehicle_type", "vehicle type"), ("engine_displacement", "engine displacement (L)"),
                         ("fuel_type", "fuel type"), ("year_model", "year model")):
        if blank(field):
            value = fallback[field]
            assume(field, f"{float(value):g}" if field == "engine_displacement" else value, label)
    if blank("odometer_reading"):
        assume("odometer_reading", f"{float(fallback.get('latest_odometer') or 0):.0f}", "odometer (km)")

    try:
        distance = float(f.get("distance_km") or "")
    except ValueError:
        distance = None
    if distance and distance > 0:
        def num(field):
            try:
                v = float(f.get(field) or "")
                return v if v > 0 else None
            except ValueError:
                return None
        duration, speed = num("duration_minutes"), num("avg_speed_kmh")
        if duration is None and speed is None:
            typical = db.query_one("SELECT AVG(avg_speed_kmh) AS s FROM trip_records")["s"]
            speed = round(float(typical), 1) if typical else 40.0
            assume("avg_speed_kmh", f"{speed:g}", "average speed (km/h, fleet typical)")
        if duration is None:
            assume("duration_minutes", f"{min(max(distance / speed * 60, 1), 1439):.1f}", "duration (min, from distance and speed)")
        elif speed is None:
            assume("avg_speed_kmh", f"{min(max(distance / (duration / 60), 0.1), 159):.1f}", "average speed (km/h, from distance and duration)")

    for field, (value, label) in PREDICTION_DEFAULTS.items():
        if blank(field):
            assume(field, value, label)
    return f, assumed


def validate_prediction_form(form):
    """Server-side validation (the browser checks can be bypassed).
    Returns a list of error messages; empty means the input is usable."""
    errors = []
    if not (form.get("distance_km") or "").strip():
        return ["Please enter the Distance Traveled (km) — it is the only required field."]

    for field, (label, lo, hi, allow_lo) in PREDICTION_NUMERIC_LIMITS.items():
        raw = form.get(field, "0" if field == "passenger_cargo_load_kg" else "")
        try:
            value = float(raw or 0)
        except ValueError:
            errors.append(f"{label} must be a number.")
            continue
        if value != value or value > hi or value < lo or (value == lo and not allow_lo):
            errors.append(f"{label} must be {'at least' if allow_lo else 'greater than'} {lo:,} and at most {hi:,}.")
    try:
        year = int(form["year_model"])
        if not 1980 <= year <= today_local().year + 1:
            errors.append(f"Year model must be between 1980 and {today_local().year + 1}.")
    except ValueError:
        errors.append("Year model must be a whole number.")
    if not re.fullmatch(r"([01][0-9]|2[0-3]):[0-5][0-9]", form["departure_time"].strip()):
        errors.append("Departure time must be a valid 24-hour time, e.g. 08:30.")
    for field, options, label in (("trip_type", TRIP_TYPES, "trip type"), ("road_type", ROAD_TYPES, "road type"),
                                  ("terrain_classification", TERRAINS, "terrain"),
                                  ("vehicle_type", VEHICLE_TYPES, "vehicle type"), ("fuel_type", FUEL_TYPES, "fuel type")):
        if form[field] not in options:
            errors.append(f"Please choose a valid {label}.")
    if len(form["route"].strip()) > 150:
        errors.append("Route must be at most 150 characters.")
    vehicle_id = form.get("vehicle_id") or ""
    if vehicle_id and not (vehicle_id.isdigit() and db.query_one("SELECT id FROM vehicles WHERE id = %s", (vehicle_id,))):
        errors.append("The selected vehicle no longer exists. Please choose another vehicle.")
    return errors


def prediction_warnings(values, metrics, raw_prediction=None):
    """Plain-language cautions shown with a result: inputs outside what the
    model was trained on, or a non-positive raw model output."""
    warnings = []
    ranges = (metrics or {}).get("feature_ranges") or {}
    # Only predictors the model actually uses: a value the variable selection
    # removed (e.g. odometer) cannot make the estimate less reliable.
    used = (metrics or {}).get("selected_numeric_features")
    for field, (label, unit) in PREDICTION_FEATURE_LABELS.items():
        if field not in ranges or values.get(field) in (None, "") or (used is not None and field not in used):
            continue
        lo, hi = ranges[field]
        v = float(values[field])
        if v < lo or v > hi:
            warnings.append(f"{label} ({v:g} {unit}".rstrip() + f") is outside the range the model was trained on "
                            f"({lo:g}–{hi:g} {unit}".rstrip() + ").")
    # Categories with no training trips at all: the model cannot know how they
    # change fuel use, so the estimate falls back to what it learned elsewhere.
    seen = (metrics or {}).get("category_values") or {}
    for field, label in PREDICTION_CATEGORY_LABELS.items():
        value = str(values.get(field) or "")
        if value and field in seen and value not in seen[field]:
            warnings.append(f"The model has no trip records yet for {label} \"{value}\" (it was trained on "
                            f"{', '.join(seen[field])}), so this estimate does not reflect how it changes fuel use.")
    try:
        d, t, sp = float(values["distance_km"]), float(values["duration_minutes"]), float(values["avg_speed_kmh"])
        implied = d / (t / 60) if t else 0
        if implied and abs(implied - sp) / sp > 0.5:
            warnings.append(f"Distance and duration imply about {implied:.0f} km/h, but the average speed entered is {sp:g} km/h. "
                            "Please double-check these values.")
    except (KeyError, ValueError, TypeError, ZeroDivisionError):
        pass
    if raw_prediction is not None and raw_prediction <= 0:
        warnings.append("The model's estimate for this trip was at or below zero, so the minimum of 0.1 L is shown.")
    return warnings


def model_input_fields(metrics):
    """Form fields the current model actually uses after merging and variable
    selection; the others are only recorded with the request. None when unknown."""
    if not metrics or metrics.get("selected_numeric_features") is None:
        return None
    used = set(metrics["selected_numeric_features"]) | set(metrics.get("selected_categorical_features") or [])
    if "departure_period" in used:  # derived from the departure time
        used.add("departure_time")
    return used


def render_prediction_page(form=None, errors=None, status=200):
    model = get_model()
    metrics = get_metrics()
    return render_template(
        "prediction.html", active="prediction",
        model_available=model is not None, model_metrics=metrics, model_fields=model_input_fields(metrics),
        vehicles=get_prediction_vehicles(), vehicle_types=VEHICLE_TYPES, trip_types=TRIP_TYPES,
        road_types=ROAD_TYPES, terrains=TERRAINS, routes=get_known_routes(),
        form=form or {}, errors=errors or [], max_year=today_local().year + 1,
    ), status


@app.route("/prediction", methods=["GET", "POST"])
@login_required
def prediction():
    if request.method == "GET":
        return render_prediction_page()

    model = get_model()
    if model is None:
        return render_prediction_page(request.form, ["Model unavailable. Please train the model before making predictions."])
    form, assumed = fill_prediction_defaults(request.form)
    errors = validate_prediction_form(form)
    if errors:
        return render_prediction_page(request.form, errors)

    try:
        row = build_prediction_frame(form)
        row = attach_rated_efficiency(row, app.config["SUPPLEMENTARY_DATA_PATH"])
        raw_prediction = float(model.predict(row)[0])
    except (ValueError, KeyError) as e:
        return render_prediction_page(request.form, [f"Invalid input values: {e}"])
    predicted_fuel = max(round(raw_prediction, 2), 0.1)

    f = form
    pred_id = db.execute("""
        INSERT INTO predictions (
            user_id, vehicle_id, odometer_reading, distance_km, duration_minutes,
            avg_speed_kmh, trip_type, departure_time, passenger_cargo_load_kg, route,
            road_type, terrain_classification, vehicle_type, engine_displacement,
            fuel_type, year_model, predicted_fuel
        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
    """, (
        session["user_id"], f.get("vehicle_id") or None, f["odometer_reading"], f["distance_km"],
        f["duration_minutes"], f["avg_speed_kmh"], f["trip_type"], f["departure_time"].strip(),
        f.get("passenger_cargo_load_kg", 0) or 0, f["route"].strip(), f["road_type"],
        f["terrain_classification"], f["vehicle_type"], f["engine_displacement"], f["fuel_type"],
        f["year_model"], predicted_fuel,
    ))
    flash("Prediction saved and submitted as a fuel request for administrator approval.", "success")
    if assumed:
        flash("Blank fields were filled in with: " + "; ".join(assumed) + ".", "info")
    _link_actuals_quietly()  # the trip ticket may already be encoded
    return redirect(url_for("prediction_result", prediction_id=pred_id))


@app.route("/api/prediction-options")
@login_required
def api_prediction_options():
    """Live data for the prediction form: vehicles, route suggestions and
    the model currently used for predictions."""
    metrics = get_metrics() or {}
    return {
        "vehicles": [{
            "id": v["id"], "label": f"{v['plate_number']} — {v['brand_model']}", "type": v["vehicle_type"],
            "displacement": str(v["engine_displacement"]), "fuel": v["fuel_type"], "year": v["year_model"],
            "odometer": f"{float(v['latest_odometer']):.2f}",
        } for v in get_prediction_vehicles()],
        "routes": get_known_routes(),
        "model": {"available": get_model() is not None, "version": metrics.get("model_version"),
                  "r2": metrics.get("r2_score"), "mae": metrics.get("mae"), "retraining": _WATCHER["retraining"]},
    }


@app.route("/prediction/result/<int:prediction_id>")
@login_required
def prediction_result(prediction_id):
    pred = db.query_one("""
        SELECT p.*, v.plate_number FROM predictions p
        LEFT JOIN vehicles v ON p.vehicle_id = v.id
        WHERE p.id = %s
    """, (prediction_id,))
    if not pred or not can_see_prediction(pred):
        flash("Prediction record not found.", "danger")
        return redirect(url_for("prediction"))
    clamped = float(pred["predicted_fuel"]) <= 0.1  # model output was at/below the 0.1 L floor
    warnings = prediction_warnings(pred, get_metrics(), raw_prediction=0 if clamped else None)
    reviewer = db.query_one("SELECT full_name FROM users WHERE id = %s", (pred["reviewed_by"],)) if pred["reviewed_by"] else None
    tolerance = float((get_metrics() or {}).get("rmse") or 2.0)
    predicted = float(pred["predicted_fuel"])
    return render_template("prediction_result.html", active="prediction", pred=pred, warnings=warnings,
                           reviewer=reviewer["full_name"] if reviewer else None,
                           predicted_range=f"{max(predicted - tolerance, 0):.2f} – {predicted + tolerance:.2f}",
                           tolerance=f"{tolerance:.2f}")


@app.route("/api/prediction/<int:prediction_id>/status")
@login_required
def api_prediction_status(prediction_id):
    """Polled by the result page so an approval / rejection shows up live."""
    p = db.query_one("""SELECT user_id, approval_status, approved_fuel, reviewed_at, review_note, actual_fuel
                        FROM predictions WHERE id = %s""", (prediction_id,))
    if not p or not can_see_prediction(p):
        return {"exists": False}
    return {"exists": True, "signature": "|".join(str(p[k]) for k in
            ("approval_status", "approved_fuel", "reviewed_at", "review_note", "actual_fuel"))}


def can_see_prediction(pred):
    """Staff see only the fuel requests they made; the administrator sees all."""
    return session.get("role") == "admin" or pred["user_id"] == session.get("user_id")


def back_to_list(endpoint):
    """Redirect back to the page the form was submitted from (keeping its
    filters and page number), but only within this site."""
    ref = request.referrer or ""
    if ref.startswith(request.host_url):
        return redirect(ref)
    return redirect(url_for(endpoint))


def prediction_history_data(args):
    q = (args.get("q") or "").strip()
    fuel_type = args.get("fuel_type", "")
    status = args.get("status", "")
    try:
        page = max(int(args.get("page") or 1), 1)
    except ValueError:
        page = 1
    per_page = 15

    where, params = ["1=1"], []
    if q:
        like = "%" + q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        where.append("(v.plate_number LIKE %s OR p.route LIKE %s OR p.vehicle_type LIKE %s OR p.trip_type LIKE %s"
                     " OR (p.vehicle_id IS NULL AND 'Manual Entry' LIKE %s))")
        params += [like] * 5
    if fuel_type in FUEL_TYPES:
        where.append("p.fuel_type = %s")
        params.append(fuel_type)
    if status in ("pending", "approved", "rejected"):
        where.append("p.approval_status = %s")
        params.append(status)
    # Staff see only the fuel requests they made; the administrator sees all.
    mine = args.get("mine") == "1" or session.get("role") != "admin"
    if mine:
        where.append("p.user_id = %s")
        params.append(session.get("user_id"))
    where_clause = " AND ".join(where)
    # "Predicted range" = predicted fuel ± the model's RMSE (its typical error in liters).
    tolerance = float((get_metrics() or {}).get("rmse") or 2.0)

    stats = db.query_one(f"""
        SELECT COUNT(*) AS total,
               SUM(p.actual_fuel IS NOT NULL) AS with_actual,
               AVG(ABS(p.predicted_fuel - p.actual_fuel)) AS mae,
               AVG(ABS(p.predicted_fuel - p.actual_fuel) <= 2) AS within2,
               SUM(p.approval_status = 'pending') AS pending,
               SUM(ABS(p.predicted_fuel - p.actual_fuel) > %s) AS outside
        FROM predictions p LEFT JOIN vehicles v ON p.vehicle_id = v.id
        WHERE {where_clause}
    """, [tolerance] + params)
    total = int(stats["total"] or 0)
    total_pages = max((total + per_page - 1) // per_page, 1)
    page = min(page, total_pages)
    offset = (page - 1) * per_page

    # First come, first served: requests are listed in the order they were made,
    # and each keeps its request number (1 = the first request ever made) even
    # when the list is filtered or paged, so "No." always names the same request.
    rows = db.query_all(f"""
        SELECT p.*, v.plate_number, u.full_name, r.full_name AS reviewer_name,
               (SELECT COUNT(*) FROM predictions p2
                WHERE p2.created_at < p.created_at OR (p2.created_at = p.created_at AND p2.id <= p.id)) AS request_no
        FROM predictions p
        LEFT JOIN vehicles v ON p.vehicle_id = v.id
        LEFT JOIN users u ON p.user_id = u.id
        LEFT JOIN users r ON p.reviewed_by = r.id
        WHERE {where_clause}
        ORDER BY p.created_at, p.id LIMIT %s OFFSET %s
    """, params + [per_page, offset])

    records = []
    for p in rows:
        actual = float(p["actual_fuel"]) if p["actual_fuel"] is not None else None
        predicted = float(p["predicted_fuel"])
        diff = round(predicted - actual, 2) if actual is not None else None
        records.append({
            "id": p["id"], "num": int(p["request_no"]),
            "created_at": p["created_at"].strftime("%b %d, %Y %I:%M %p"),
            "created_at_long": p["created_at"].strftime("%B %d, %Y %I:%M %p"),
            "vehicle": p["plate_number"] or "Manual Entry", "vehicle_type": p["vehicle_type"],
            "vehicle_label": f"{p['plate_number'] or 'Manual Entry'} ({p['vehicle_type']})",
            "route": p["route"], "fuel_type": p["fuel_type"],
            "distance_km": f"{float(p['distance_km']):.2f}",
            "predicted_fuel": f"{predicted:.2f}",
            "actual_fuel": f"{actual:.2f}" if actual is not None else "",
            "difference": f"{diff:.2f}" if diff is not None else "",
            "diff_ok": diff is not None and abs(diff) <= tolerance,
            "outside_range": diff is not None and abs(diff) > tolerance,
            "range": f"{max(predicted - tolerance, 0):.2f}–{predicted + tolerance:.2f}",
            "user": p["full_name"] or "System",
            "status": p["approval_status"],
            "reviewer": p["reviewer_name"] or "",
            "reviewed_at": p["reviewed_at"].strftime("%b %d, %Y %I:%M %p") if p["reviewed_at"] else "",
            "review_note": p["review_note"] or "",
            "approved_fuel": f"{float(p['approved_fuel']):.2f}" if p["approved_fuel"] is not None else "",
            "mine": p["user_id"] == session.get("user_id"),
            "actual_from_trip": p.get("actual_source") == "trip" and actual is not None,
        })
    with_actual = int(stats["with_actual"] or 0)
    summary = {
        "total": total, "with_actual": with_actual,
        "mae": f"{float(stats['mae']):.2f}" if stats["mae"] is not None else "—",
        "within2": f"{float(stats['within2']) * 100:.0f}%" if stats["within2"] is not None else "—",
        "pending": int(stats["pending"] or 0),
        "outside": int(stats["outside"] or 0),
        "tolerance": f"{tolerance:.2f}",
    }
    return {"predictions": records, "page": page, "total_pages": total_pages, "summary": summary,
            "q": q, "fuel_type": fuel_type if fuel_type in FUEL_TYPES else "",
            "status": status if status in ("pending", "approved", "rejected") else "",
            "is_admin": session.get("role") == "admin", "mine": mine}


@app.route("/prediction-history")
@login_required
def prediction_history():
    data = prediction_history_data(request.args)
    return render_template("prediction_history.html", active="prediction_history", **data)


@app.route("/api/prediction-history")
@login_required
def api_prediction_history():
    return prediction_history_data(request.args)


@app.route("/prediction-history/<int:prediction_id>/actual", methods=["POST"])
@login_required
def record_actual_fuel(prediction_id):
    pred = db.query_one("SELECT id, user_id, approval_status FROM predictions WHERE id = %s", (prediction_id,))
    if not pred or not can_see_prediction(pred):
        flash("That prediction no longer exists.", "danger")
        return back_to_list("prediction_history")
    if pred["approval_status"] == "rejected":
        flash("This fuel request was rejected, so no fuel was released and there is no actual fuel to record.", "danger")
        return back_to_list("prediction_history")
    raw = (request.form.get("actual_fuel") or "").strip()
    try:
        value = None if raw == "" else round(float(raw), 2)
        if value is not None and not (0 < value <= 1000):
            raise ValueError
    except ValueError:
        flash("Actual fuel must be a number greater than 0 and at most 1,000 liters.", "danger")
    else:
        _ensure_prediction_link_columns()
        # Typed in by hand: never changed by the automatic matching from trips.
        db.execute("""UPDATE predictions SET actual_fuel = %s, actual_source = %s,
                      trip_record_id = CASE WHEN %s IS NULL THEN NULL ELSE trip_record_id END
                      WHERE id = %s""", (value, "manual" if value is not None else None, value, prediction_id))
        if value is None:
            _link_actuals_quietly()  # cleared: let it be matched to its trip again
        flash("Actual fuel consumption recorded." if value is not None else "Actual fuel consumption cleared.", "success")
    return back_to_list("prediction_history")


@app.route("/prediction-history/<int:prediction_id>/review", methods=["POST"])
@admin_required
def review_fuel_request(prediction_id):
    """Administrator approves or rejects a fuel request, using the predicted
    fuel figure as the computed reference (Chapter I: administrators approve
    fuel requests; the prediction replaces manual judgment)."""
    pred = db.query_one("SELECT id, approval_status, predicted_fuel FROM predictions WHERE id = %s", (prediction_id,))
    if not pred:
        flash("That fuel request no longer exists.", "danger")
        return back_to_list("prediction_history")
    decision = request.form.get("decision")
    if decision not in ("approved", "rejected"):
        flash("Please choose Approve or Reject.", "danger")
        return back_to_list("prediction_history")
    note = (request.form.get("review_note") or "").strip()[:255] or None
    approved_fuel = None
    if decision == "approved":
        # Fuel allocation: liters to release for the trip (the predicted figure is the reference).
        try:
            approved_fuel = round(float(request.form.get("approved_fuel") or ""), 2)
            if not 0 < approved_fuel <= 1000:
                raise ValueError
        except ValueError:
            flash("Enter the fuel to release: a number greater than 0 and at most 1,000 liters.", "danger")
            return back_to_list("prediction_history")
    db.execute("""UPDATE predictions SET approval_status=%s, approved_fuel=%s, reviewed_by=%s, reviewed_at=NOW(), review_note=%s
                  WHERE id=%s""", (decision, approved_fuel, session["user_id"], note, prediction_id))
    flash(f"Fuel request #{prediction_id} {decision}" + (f": {approved_fuel:.2f} L to release." if approved_fuel else "."), "success")
    _link_actuals_quietly()  # a rejection frees its trip for another request
    return back_to_list("prediction_history")


@app.route("/prediction-history/<int:prediction_id>/delete", methods=["POST"])
@admin_required
def delete_prediction(prediction_id):
    if not db.query_one("SELECT id FROM predictions WHERE id = %s", (prediction_id,)):
        flash("That prediction no longer exists.", "danger")
        return back_to_list("prediction_history")
    db.execute("DELETE FROM predictions WHERE id = %s", (prediction_id,))
    compact_ids("predictions")
    flash("Prediction record deleted.", "success")
    return back_to_list("prediction_history")


VEHICLE_STATUSES = ["Active", "Maintenance", "Inactive"]


VEHICLE_EXTRA_COLUMNS = (
    ("seating_capacity", "INT NULL"),
    ("station", "VARCHAR(100) NULL"),
    ("assigned_driver", "VARCHAR(100) NULL"),
    ("remarks", "VARCHAR(255) NULL"),
)
_VEHICLE_COLUMNS_READY = {"ok": False}


def _ensure_vehicle_columns():
    """Adds the GSO vehicle-list columns (seating capacity, station, driver,
    remarks) on first use, so an existing database needs no manual migration."""
    if _VEHICLE_COLUMNS_READY["ok"]:
        return
    have = {r["c"] for r in db.query_all("""
        SELECT COLUMN_NAME AS c FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'vehicles'
    """)}
    for name, ddl in VEHICLE_EXTRA_COLUMNS:
        if name not in have:
            db.execute(f"ALTER TABLE vehicles ADD COLUMN {name} {ddl}")
    _VEHICLE_COLUMNS_READY["ok"] = True


def query_vehicles(status=""):
    """Vehicles with live figures from their records: the latest known
    odometer (recorded value or end of the latest trip, whichever is higher)
    and how many trip / fuel records depend on each vehicle."""
    _ensure_vehicle_columns()
    where, params = "", ()
    if status in VEHICLE_STATUSES:
        where, params = "WHERE v.status = %s", (status,)
    return db.query_all(f"""
        SELECT v.*,
               GREATEST(COALESCE(v.current_odometer, 0),
                        COALESCE((SELECT MAX(t.odometer_reading + t.distance_km) FROM trip_records t WHERE t.vehicle_id = v.id), 0)
               ) AS latest_odometer,
               (SELECT COUNT(*) FROM trip_records t WHERE t.vehicle_id = v.id) AS trip_count,
               (SELECT COUNT(*) FROM fuel_records f WHERE f.vehicle_id = v.id) AS fuel_count,
               (SELECT MAX(t.trip_date) FROM trip_records t WHERE t.vehicle_id = v.id) AS last_trip_date
        FROM vehicles v {where}
        ORDER BY v.plate_number
    """, params)


def vehicle_record(v, num):
    """JSON-safe row used by the table, the shared modals and the live API."""
    return {
        "id": v["id"], "num": num, "plate_number": v["plate_number"], "vehicle_type": v["vehicle_type"],
        "brand_model": v["brand_model"], "engine_displacement": str(v["engine_displacement"]),
        "fuel_type": v["fuel_type"], "year_model": v["year_model"], "status": v["status"],
        "seating_capacity": v["seating_capacity"] if v["seating_capacity"] is not None else "",
        "station": v["station"] or "", "assigned_driver": v["assigned_driver"] or "", "remarks": v["remarks"] or "",
        # The edit form gets the vehicle's own recorded reading; the table shows
        # the latest known one (recorded value or end of the latest trip).
        # Feeding the latter into the form made every save copy trip mileage
        # into the vehicle, so a corrected or deleted trip left it too high.
        "current_odometer": f"{float(v['current_odometer'] or 0):.2f}",
        "odometer": f"{float(v['latest_odometer']):.2f}",
        "trip_count": int(v["trip_count"]), "fuel_count": int(v["fuel_count"]),
        "last_trip_date": str(v["last_trip_date"]) if v["last_trip_date"] else "",
    }


def validate_vehicle_form(f, vehicle_id=None):
    errors = []
    plate = (f.get("plate_number") or "").strip().upper()
    if not plate:
        errors.append("Plate number is required.")
    elif len(plate) > 20 or not re.fullmatch(r"[A-Z0-9][A-Z0-9 \-]*", plate):
        errors.append("Plate number may only contain letters, numbers, spaces and dashes (max 20 characters).")
    elif db.query_one("SELECT id FROM vehicles WHERE plate_number = %s AND id <> %s", (plate, vehicle_id or 0)):
        errors.append(f"Plate number {plate} is already registered to another vehicle.")
    if f.get("vehicle_type") not in VEHICLE_TYPES:
        errors.append("Please choose a valid vehicle type.")
    model = (f.get("brand_model") or "").strip()
    if not model or len(model) > 100:
        errors.append("Model is required (max 100 characters).")
    if f.get("fuel_type") not in FUEL_TYPES:
        errors.append("Please choose a valid fuel type.")
    if f.get("status") not in VEHICLE_STATUSES:
        errors.append("Please choose a valid status.")
    checks = (("engine_displacement", "Engine displacement", 0, 20, False),
              ("current_odometer", "Current odometer", 0, 2_000_000, True))
    for field, label, lo, hi, allow_lo in checks:
        try:
            value = float(f.get(field) or "")
            if value > hi or value < lo or (value == lo and not allow_lo):
                raise ValueError
        except ValueError:
            errors.append(f"{label} must be a number {'from' if allow_lo else 'greater than'} {lo:,} {'to' if allow_lo else 'and at most'} {hi:,}.")
    try:
        year = int(f.get("year_model") or "")
        if not 1980 <= year <= today_local().year + 1:
            raise ValueError
    except ValueError:
        errors.append(f"Year model must be a whole number from 1980 to {today_local().year + 1}.")
    seats = (f.get("seating_capacity") or "").strip()
    if seats and not (seats.isdigit() and 1 <= int(seats) <= 100):
        errors.append("Seating capacity must be a whole number from 1 to 100 (or left blank).")
    for field, label, limit in (("station", "Station", 100), ("assigned_driver", "Driver", 100),
                                ("remarks", "Remarks", 255)):
        if len((f.get(field) or "").strip()) > limit:
            errors.append(f"{label} must be at most {limit} characters.")
    return errors


def _vehicle_values(f):
    def optional(field):
        return (f.get(field) or "").strip() or None
    return (f["plate_number"].strip().upper(), f["vehicle_type"], f["brand_model"].strip(),
            f["engine_displacement"], f["fuel_type"], f["year_model"], f["current_odometer"], f["status"],
            optional("seating_capacity"), optional("station"), optional("assigned_driver"), optional("remarks"))


@app.route("/vehicles")
@login_required
def vehicles():
    status = request.args.get("status", "")
    rows = [vehicle_record(v, i) for i, v in enumerate(query_vehicles(status), 1)]
    return render_template("vehicles.html", active="vehicles", vehicles=rows, vehicle_types=VEHICLE_TYPES,
                           statuses=VEHICLE_STATUSES, max_year=today_local().year + 1)


@app.route("/api/vehicles")
@login_required
def api_vehicles():
    status = request.args.get("status", "")
    return {"vehicles": [vehicle_record(v, i) for i, v in enumerate(query_vehicles(status), 1)]}


@app.route("/vehicles/add", methods=["POST"])
@admin_required
def add_vehicle():
    errors = validate_vehicle_form(request.form)
    if errors:
        flash("Could not add vehicle: " + " ".join(errors), "danger")
        return redirect(url_for("vehicles"))
    try:
        _ensure_vehicle_columns()
        db.execute("""
            INSERT INTO vehicles (plate_number, vehicle_type, brand_model, engine_displacement,
                fuel_type, year_model, current_odometer, status,
                seating_capacity, station, assigned_driver, remarks)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, _vehicle_values(request.form))
        flash("Vehicle added successfully.", "success")
    except Exception:
        app.logger.exception("Adding vehicle failed")
        flash("Could not add vehicle due to a database error. Please try again.", "danger")
    return redirect(url_for("vehicles"))


@app.route("/vehicles/<int:vehicle_id>/edit", methods=["POST"])
@admin_required
def edit_vehicle(vehicle_id):
    if not db.query_one("SELECT id FROM vehicles WHERE id = %s", (vehicle_id,)):
        flash("That vehicle no longer exists.", "danger")
        return redirect(url_for("vehicles"))
    errors = validate_vehicle_form(request.form, vehicle_id)
    if errors:
        flash("Could not update vehicle: " + " ".join(errors), "danger")
        return redirect(url_for("vehicles"))
    try:
        _ensure_vehicle_columns()
        db.execute("""
            UPDATE vehicles SET plate_number=%s, vehicle_type=%s, brand_model=%s,
                engine_displacement=%s, fuel_type=%s, year_model=%s, current_odometer=%s, status=%s,
                seating_capacity=%s, station=%s, assigned_driver=%s, remarks=%s
            WHERE id = %s
        """, _vehicle_values(request.form) + (vehicle_id,))
        flash("Vehicle updated successfully.", "success")
    except Exception:
        app.logger.exception("Updating vehicle failed")
        flash("Could not update vehicle due to a database error. Please try again.", "danger")
    return redirect(url_for("vehicles"))


@app.route("/vehicles/<int:vehicle_id>/delete", methods=["POST"])
@admin_required
def delete_vehicle(vehicle_id):
    v = db.query_one("SELECT plate_number FROM vehicles WHERE id = %s", (vehicle_id,))
    if not v:
        flash("That vehicle no longer exists.", "danger")
        return redirect(url_for("vehicles"))
    try:
        # trip_records / fuel_records cascade in the database schema.
        db.execute("DELETE FROM vehicles WHERE id = %s", (vehicle_id,))
        compact_ids("vehicles", "trip_records", "fuel_records", "predictions")
        flash(f"Vehicle {v['plate_number']} and its trip and fuel records were deleted.", "success")
    except Exception:
        app.logger.exception("Deleting vehicle failed")
        flash("Could not delete vehicle due to a database error. Please try again.", "danger")
    return redirect(url_for("vehicles"))


# ------------------------------------------------------------------
# TRIP RECORDS
# ------------------------------------------------------------------
TRIP_NUMERIC_LIMITS = (
    # field, label, min, max, min allowed?, required?
    ("odometer_reading", "Odometer reading", 0, 2_000_000, True, True),
    ("distance_km", "Distance traveled", 0, 1000, False, True),
    ("duration_minutes", "Duration", 0, 1440, False, True),
    ("avg_speed_kmh", "Average speed", 0, 160, False, True),
    ("passenger_cargo_load_kg", "Passenger / cargo load", 0, 20_000, True, False),
    ("actual_fuel_consumption", "Gasoline/diesoline consumed", 0, 1000, False, False),
    ("balance_in_tank", "Balance in the tank", -1000, 1000, True, False),
    ("fuel_received", "Fuel received", 0, 1000, False, False),
)

# Columns of the GSO "Monthly Report of Official Travel" kept with each trip
# (added on first use, so an existing database needs no migration).
_TRIP_SHEET_READY = {"ok": False}


def _ensure_trip_sheet_columns():
    if _TRIP_SHEET_READY["ok"]:
        return
    have = {r["c"] for r in db.query_all("""
        SELECT COLUMN_NAME AS c FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'trip_records'""")}
    for column, ddl in (("balance_in_tank", "DECIMAL(9,3) NULL COMMENT 'liters, as on the monthly report'"),
                        ("fuel_received", "DECIMAL(9,3) NULL COMMENT 'liters'"),
                        ("or_invoice_no", "VARCHAR(60) NULL")):
        if column not in have:
            db.execute(f"ALTER TABLE trip_records ADD COLUMN {column} {ddl}")
    _TRIP_SHEET_READY["ok"] = True


def _fmt_liters(value):
    return f"{float(value):.3f}" if value is not None else ""


def trip_record(t, num):
    """JSON-safe trip row used by the table, the shared modals and the live API."""
    dep = format_time(t["departure_time"])
    return {
        "id": t["id"], "num": num, "vehicle_id": t["vehicle_id"],
        "trip_date": str(t["trip_date"]), "departure_time": dep, "trip_type": t["trip_type"],
        "route": t["route"], "road_type": t["road_type"], "terrain_classification": t["terrain_classification"],
        "odometer_reading": str(t["odometer_reading"]), "distance_km": str(t["distance_km"]),
        "duration_minutes": str(t["duration_minutes"]), "avg_speed_kmh": str(t["avg_speed_kmh"]),
        "passenger_cargo_load_kg": str(t["passenger_cargo_load_kg"]),
        "actual_fuel_consumption": str(t["actual_fuel_consumption"]) if t["actual_fuel_consumption"] is not None else "",
        "remarks": t["remarks"] or "", "plate_number": t["plate_number"],
        "balance_in_tank": _fmt_liters(t.get("balance_in_tank")), "fuel_received": _fmt_liters(t.get("fuel_received")),
        "or_invoice_no": t.get("or_invoice_no") or "",
        "destination": t["route"] + (f" — {t['remarks']}" if t["remarks"] else ""),
        "date_time": f"{t['trip_date']} {dep}", "road_terrain": f"{t['road_type']} / {t['terrain_classification']}",
    }


def query_trips():
    _ensure_trip_sheet_columns()
    rows = db.query_all("""
        SELECT t.*, v.plate_number
        FROM trip_records t
        JOIN vehicles v ON t.vehicle_id = v.id
        ORDER BY t.trip_date, t.departure_time, t.id
    """)
    # Oldest first (January to December, like the GSO monthly travel reports);
    # a newly added or edited trip lands in its date's place automatically.
    return [trip_record(r, i) for i, r in enumerate(rows, 1)]


def validate_trip_form(f, trip_id=None):
    """Returns (errors, warnings). Errors block saving; warnings are shown
    but the trip is still saved. `trip_id` is the trip being edited, if any."""
    errors, warnings = [], []
    vid = (f.get("vehicle_id") or "").strip()
    if not (vid.isdigit() and db.query_one("SELECT id FROM vehicles WHERE id = %s", (vid,))):
        errors.append("Please choose a valid vehicle.")
    try:
        trip_date = date.fromisoformat((f.get("trip_date") or "").strip())
        if not date(2000, 1, 1) <= trip_date <= today_local():
            errors.append(f"Trip date must be between 2000-01-01 and today ({today_local().isoformat()}).")
    except ValueError:
        errors.append("Trip date must be a valid date.")
    if not re.fullmatch(r"([01][0-9]|2[0-3]):[0-5][0-9](:[0-5][0-9])?", (f.get("departure_time") or "").strip()):
        errors.append("Departure time must be a valid 24-hour time, e.g. 08:30.")
    for field, options, label in (("trip_type", TRIP_TYPES, "trip type"), ("road_type", ROAD_TYPES, "road type"),
                                  ("terrain_classification", TERRAINS, "terrain")):
        if f.get(field) not in options:
            errors.append(f"Please choose a valid {label}.")
    route = (f.get("route") or "").strip()
    if not route or len(route) > 150:
        errors.append("Route is required (max 150 characters).")
    if len((f.get("remarks") or "").strip()) > 255:
        errors.append("Remarks must be at most 255 characters.")
    if len((f.get("or_invoice_no") or "").strip()) > 60:
        errors.append("OR / Invoice no. must be at most 60 characters.")
    values = {}
    for field, label, lo, hi, allow_lo, required in TRIP_NUMERIC_LIMITS:
        raw = (f.get(field) or "").strip()
        if raw == "" and not required:
            continue
        try:
            value = float(raw)
            if value != value or value > hi or value < lo or (value == lo and not allow_lo):
                raise ValueError
            values[field] = value
        except ValueError:
            errors.append(f"{label} must be a number {'from' if allow_lo else 'greater than'} {lo:,} "
                          f"{'to' if allow_lo else 'and at most'} {hi:,}.")
    if not errors and {"distance_km", "duration_minutes", "avg_speed_kmh"} <= values.keys():
        implied = values["distance_km"] / (values["duration_minutes"] / 60)
        if abs(implied - values["avg_speed_kmh"]) / values["avg_speed_kmh"] > 0.5:
            warnings.append(f"Distance and duration imply about {implied:.0f} km/h, but the average speed entered is "
                            f"{values['avg_speed_kmh']:g} km/h. Please double-check this trip.")
    if not errors and {"odometer_reading", "distance_km"} <= values.keys():
        warnings.extend(_odometer_warnings(vid, trip_date, values["odometer_reading"], values["distance_km"], trip_id))
    return errors, warnings


def _odometer_warnings(vehicle_id, trip_date, odometer, distance, trip_id=None):
    """The odometer (reading at the start of the trip) must not go backwards:
    not below where the vehicle's previous trip ended, and this trip must end
    before the next trip starts."""
    warnings = []
    prev = db.query_one("""SELECT MAX(odometer_reading + distance_km) AS km FROM trip_records
                           WHERE vehicle_id = %s AND trip_date < %s AND id <> %s""",
                        (vehicle_id, trip_date, trip_id or 0))["km"]
    if prev is not None and odometer < float(prev) - 0.5:
        warnings.append(f"The odometer ({odometer:,.0f} km) is lower than where this vehicle's previous trip ended "
                        f"({float(prev):,.0f} km). Please double-check it.")
    nxt = db.query_one("""SELECT MIN(odometer_reading) AS km FROM trip_records
                          WHERE vehicle_id = %s AND trip_date > %s AND id <> %s""",
                       (vehicle_id, trip_date, trip_id or 0))["km"]
    if nxt is not None and odometer + distance > float(nxt) + 0.5:
        warnings.append(f"This trip ends at {odometer + distance:,.0f} km, past the odometer of this vehicle's next trip "
                        f"({float(nxt):,.0f} km). Please double-check the odometer and distance.")
    return warnings


_PREDICTION_LINK_READY = {"ok": False}
ACTUAL_MATCH_DISTANCE_TOLERANCE = 0.20   # trip distance within ±20% of the requested distance
ACTUAL_MATCH_DAYS_BEFORE, ACTUAL_MATCH_DAYS_AFTER = 1, 7


def _ensure_prediction_link_columns():
    """predictions.trip_record_id / actual_source: which trip the actual fuel
    came from and whether it was recorded automatically ('trip') or by hand
    ('manual'). Added on first use, so an existing database needs no migration."""
    if _PREDICTION_LINK_READY["ok"]:
        return
    have = {r["c"] for r in db.query_all("""
        SELECT COLUMN_NAME AS c FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'predictions'""")}
    if "trip_record_id" not in have:
        db.execute("ALTER TABLE predictions ADD COLUMN trip_record_id INT NULL")
    if "actual_source" not in have:
        db.execute("ALTER TABLE predictions ADD COLUMN actual_source VARCHAR(10) NULL")
    _PREDICTION_LINK_READY["ok"] = True


def link_predictions_to_trips():
    """Record the actual fuel of fuel requests automatically from Trip Records.

    1. A request already filled from a trip follows that trip (its liters are
       kept in step when the trip is edited, cleared if the trip lost them).
    2. A request with no actual fuel yet is matched to the trip ticket of the
       same vehicle dated from 1 day before to 7 days after the request, whose
       distance is within ±20% of the requested distance (closest first), and
       that is not already matched to another request.
    Manually recorded actual fuel is never changed. Returns the request ids filled."""
    _ensure_prediction_link_columns()
    db.execute("""
        UPDATE predictions p JOIN trip_records t ON p.trip_record_id = t.id
        SET p.actual_fuel = t.actual_fuel_consumption
        WHERE p.actual_source = 'trip' AND NOT (p.actual_fuel <=> t.actual_fuel_consumption)""")
    db.execute("""
        UPDATE predictions SET trip_record_id = NULL, actual_source = NULL
        WHERE actual_source = 'trip' AND actual_fuel IS NULL""")
    # A rejected request released no fuel: it never takes a trip's actual fuel,
    # and frees any trip it was matched to before it was rejected.
    db.execute("""
        UPDATE predictions SET actual_fuel = NULL, trip_record_id = NULL, actual_source = NULL
        WHERE actual_source = 'trip' AND approval_status = 'rejected'""")
    filled = []
    pending = db.query_all("""
        SELECT id, vehicle_id, distance_km, created_at FROM predictions
        WHERE actual_fuel IS NULL AND vehicle_id IS NOT NULL AND trip_record_id IS NULL
          AND approval_status <> 'rejected'
        ORDER BY created_at, id""")
    for p in pending:
        d = float(p["distance_km"])
        trip = db.query_one("""
            SELECT t.id, t.actual_fuel_consumption FROM trip_records t
            WHERE t.vehicle_id = %s AND t.actual_fuel_consumption IS NOT NULL
              AND t.trip_date BETWEEN DATE(%s) - INTERVAL %s DAY AND DATE(%s) + INTERVAL %s DAY
              AND ABS(t.distance_km - %s) <= %s
              AND NOT EXISTS (SELECT 1 FROM predictions q WHERE q.trip_record_id = t.id)
            ORDER BY ABS(t.distance_km - %s), ABS(DATEDIFF(t.trip_date, %s)), t.id
            LIMIT 1""", (p["vehicle_id"], p["created_at"], ACTUAL_MATCH_DAYS_BEFORE, p["created_at"],
                         ACTUAL_MATCH_DAYS_AFTER, d, d * ACTUAL_MATCH_DISTANCE_TOLERANCE, d, p["created_at"]))
        if trip:
            db.execute("""UPDATE predictions SET actual_fuel = %s, trip_record_id = %s, actual_source = 'trip'
                          WHERE id = %s AND actual_fuel IS NULL""",
                       (trip["actual_fuel_consumption"], trip["id"], p["id"]))
            filled.append(p["id"])
    return filled


def _link_actuals_quietly():
    """Run the automatic actual-fuel matching after a trip change; a problem
    there must never undo or block saving the trip itself."""
    try:
        filled = link_predictions_to_trips()
        if filled:
            flash(f"Actual fuel recorded automatically for {len(filled)} fuel request(s) from the matching trip record.", "info")
    except Exception:
        app.logger.exception("Automatic actual-fuel matching failed")


def _sync_trip_fuel_records(trip_id=None):
    """Keep Fuel Records in step with Trip Records: a trip with actual fuel
    consumption has a linked fuel record (created as "Auto-logged from trip"),
    and editing the trip updates the date, vehicle, liters and odometer
    (end of trip) of its linked record. With no trip_id, every trip with
    actual fuel but no fuel record gets one (used after a CSV import)."""
    if trip_id is not None:
        db.execute("""
            UPDATE fuel_records f JOIN trip_records t ON f.trip_record_id = t.id JOIN vehicles v ON t.vehicle_id = v.id
            SET f.vehicle_id = t.vehicle_id, f.fuel_date = t.trip_date, f.fuel_type = v.fuel_type,
                f.liters_consumed = t.actual_fuel_consumption, f.odometer_reading = t.odometer_reading + t.distance_km
            WHERE t.id = %s AND t.actual_fuel_consumption IS NOT NULL
        """, (trip_id,))
    db.execute(f"""
        INSERT INTO fuel_records (vehicle_id, trip_record_id, fuel_date, fuel_type, liters_consumed, odometer_reading, remarks)
        SELECT t.vehicle_id, t.id, t.trip_date, v.fuel_type, t.actual_fuel_consumption,
               t.odometer_reading + t.distance_km, 'Auto-logged from trip'
        FROM trip_records t JOIN vehicles v ON t.vehicle_id = v.id
        WHERE t.actual_fuel_consumption IS NOT NULL
          AND NOT EXISTS (SELECT 1 FROM fuel_records f WHERE f.trip_record_id = t.id)
          {"AND t.id = %s" if trip_id is not None else ""}
    """, (trip_id,) if trip_id is not None else ())


def _trip_payload(f):
    return (
        f["vehicle_id"], f["trip_date"].strip(), f["trip_type"],
        f["departure_time"].strip(), f["route"].strip(), f["road_type"], f["terrain_classification"],
        f["odometer_reading"], f["distance_km"], f["duration_minutes"], f["avg_speed_kmh"],
        (f.get("passenger_cargo_load_kg") or "").strip() or 0,
        (f.get("actual_fuel_consumption") or "").strip() or None, (f.get("remarks") or "").strip() or None,
        (f.get("balance_in_tank") or "").strip() or None, (f.get("fuel_received") or "").strip() or None,
        (f.get("or_invoice_no") or "").strip() or None,
    )


def render_trips_page(reopen=None, status=200):
    vehicles_list = db.query_all("SELECT * FROM vehicles ORDER BY plate_number")
    return render_template(
        "trips.html", active="trips", trips=query_trips(), vehicles=vehicles_list,
        trip_types=TRIP_TYPES, road_types=ROAD_TYPES, terrains=TERRAINS,
        today=today_local().isoformat(), reopen=reopen,
    ), status


@app.route("/trips")
@login_required
def trips():
    return render_trips_page()


@app.route("/api/trips")
@login_required
def api_trips():
    return {"trips": query_trips()}


@app.route("/trips/add", methods=["POST"])
@login_required
def add_trip():
    _ensure_trip_sheet_columns()
    errors, warnings = validate_trip_form(request.form)
    if errors:
        flash("Could not add trip record: " + " ".join(errors), "danger")
        return render_trips_page({"modal": "addTripModal", "values": request.form.to_dict()})
    try:
        trip_id = db.execute("""
            INSERT INTO trip_records (vehicle_id, trip_date, trip_type, departure_time,
                route, road_type, terrain_classification, odometer_reading, distance_km,
                duration_minutes, avg_speed_kmh, passenger_cargo_load_kg, actual_fuel_consumption, remarks,
                balance_in_tank, fuel_received, or_invoice_no)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, _trip_payload(request.form))
        _sync_trip_fuel_records(trip_id)
        flash("Trip record added successfully.", "success")
        for w in warnings:
            flash(w, "warning")
        _link_actuals_quietly()
    except Exception:
        app.logger.exception("Adding trip failed")
        flash("Could not add trip record due to a database error. Please try again.", "danger")
    return redirect(url_for("trips"))


@app.route("/trips/<int:trip_id>/edit", methods=["POST"])
@login_required
def edit_trip(trip_id):
    if not db.query_one("SELECT id FROM trip_records WHERE id = %s", (trip_id,)):
        flash("That trip record no longer exists.", "danger")
        return redirect(url_for("trips"))
    _ensure_trip_sheet_columns()
    errors, warnings = validate_trip_form(request.form, trip_id)
    if errors:
        flash("Could not update trip record: " + " ".join(errors), "danger")
        return render_trips_page({"modal": "editTripModal", "trip_id": trip_id,
                                  "values": request.form.to_dict()})
    try:
        db.execute("""
            UPDATE trip_records SET vehicle_id=%s, trip_date=%s, trip_type=%s,
                departure_time=%s, route=%s, road_type=%s, terrain_classification=%s,
                odometer_reading=%s, distance_km=%s, duration_minutes=%s, avg_speed_kmh=%s,
                passenger_cargo_load_kg=%s, actual_fuel_consumption=%s, remarks=%s,
                balance_in_tank=%s, fuel_received=%s, or_invoice_no=%s
            WHERE id=%s
        """, _trip_payload(request.form) + (trip_id,))
        _sync_trip_fuel_records(trip_id)
        flash("Trip record updated successfully.", "success")
        for w in warnings:
            flash(w, "warning")
        _link_actuals_quietly()
    except Exception:
        app.logger.exception("Updating trip failed")
        flash("Could not update trip record due to a database error. Please try again.", "danger")
    return redirect(url_for("trips"))


IMPORT_COLUMNS = ["plate_number", "trip_date", "departure_time", "trip_type", "route", "road_type",
                  "terrain_classification", "odometer_reading", "distance_km", "duration_minutes",
                  "avg_speed_kmh", "passenger_cargo_load_kg", "actual_fuel_consumption", "remarks",
                  "balance_in_tank", "fuel_received", "or_invoice_no"]
IMPORT_OPTIONAL = {"passenger_cargo_load_kg", "actual_fuel_consumption", "remarks",
                   "balance_in_tank", "fuel_received", "or_invoice_no"}
IMPORT_MAX_ROWS = 5000
IMPORT_EXAMPLE_REMARK = "example row - delete before importing"
IMPORT_NUMERIC = {"odometer_reading", "distance_km", "duration_minutes", "avg_speed_kmh",
                  "passenger_cargo_load_kg", "actual_fuel_consumption", "balance_in_tank", "fuel_received"}
# Other header spellings people type in Excel, after _header_key() normalisation.
IMPORT_HEADER_ALIASES = {
    "plate": "plate_number", "plate_no": "plate_number", "vehicle": "plate_number", "vehicle_plate": "plate_number",
    "date": "trip_date", "time": "departure_time", "departure": "departure_time",
    "terrain": "terrain_classification", "odometer": "odometer_reading",
    "distance": "distance_km", "duration": "duration_minutes", "duration_min": "duration_minutes",
    "avg_speed": "avg_speed_kmh", "average_speed": "avg_speed_kmh", "speed": "avg_speed_kmh",
    "load": "passenger_cargo_load_kg", "passenger_cargo_load": "passenger_cargo_load_kg", "load_kg": "passenger_cargo_load_kg",
    "actual_fuel": "actual_fuel_consumption", "fuel": "actual_fuel_consumption",
    "fuel_consumption": "actual_fuel_consumption", "liters": "actual_fuel_consumption", "remark": "remarks",
    "gasoline_diesoline_consumed": "actual_fuel_consumption", "consumed": "actual_fuel_consumption",
    "balance": "balance_in_tank", "balance_in_the_tank": "balance_in_tank",
    "fuel_received_in_liters": "fuel_received", "received": "fuel_received",
    "or_no": "or_invoice_no", "or_no_invoce_no": "or_invoice_no", "or_no_invoice_no": "or_invoice_no",
    "invoice_no": "or_invoice_no", "destination": "route", "destinations": "route",
}
IMPORT_DATE_FORMATS = ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%Y/%m/%d", "%m-%d-%Y", "%d-%b-%Y", "%d-%b-%y",
                       "%b %d, %Y", "%B %d, %Y", "%d %b %Y", "%d %B %Y")


def _header_key(header):
    """'Distance (km)' -> 'distance', 'Plate Number' -> 'plate_number'."""
    key = re.sub(r"\(.*?\)", "", (header or "").replace("﻿", "")).strip().lower()
    key = re.sub(r"[^a-z0-9]+", "_", key).strip("_")
    return key if key in IMPORT_COLUMNS else IMPORT_HEADER_ALIASES.get(key, key)


def _canonical_choice(value, options):
    """'errand' -> 'Errand' (Excel users often change letter case)."""
    return next((o for o in options if o.lower() == value.strip().lower()), value.strip())


def _normalize_import_row(row):
    """Accept common spreadsheet formats: many date styles, 12- or 24-hour
    times, numbers with thousands separators and any letter case."""
    out = {k: (row.get(k) or "").strip() for k in IMPORT_COLUMNS}
    d = out["trip_date"].split(" ")[0] if re.match(r"\d{4}-\d{2}-\d{2} ", out["trip_date"]) else out["trip_date"]
    for fmt in IMPORT_DATE_FORMATS:
        try:
            out["trip_date"] = datetime.strptime(d, fmt).date().isoformat()
            break
        except ValueError:
            continue
    m = re.fullmatch(r"(\d{1,2}):(\d{2})(?::\d{2})?\s*([AaPp]\.?[Mm]\.?)?", out["departure_time"])
    if m:
        hour, ampm = int(m.group(1)), (m.group(3) or "").lower().replace(".", "")
        if ampm and 1 <= hour <= 12:
            hour = hour % 12 + (12 if ampm == "pm" else 0)
        out["departure_time"] = f"{hour:02d}:{m.group(2)}" if hour <= 23 else out["departure_time"]
    for field in IMPORT_NUMERIC:
        out[field] = out[field].replace(",", "").replace(" ", "")
    out["trip_type"] = _canonical_choice(out["trip_type"], TRIP_TYPES)
    out["road_type"] = _canonical_choice(out["road_type"], ROAD_TYPES)
    out["terrain_classification"] = _canonical_choice(out["terrain_classification"], TERRAINS)
    return out


def _decode_csv(raw):
    """CSV UTF-8 from Excel, or plain 'CSV (Comma delimited)', which Excel
    saves in the Windows (ANSI) encoding."""
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return raw.decode("cp1252", errors="replace")


def _trip_key(vehicle_id, trip_date, departure_time, odometer, distance):
    """Identity of a trip ticket, used to skip rows that were already imported."""
    return (int(vehicle_id), str(trip_date), str(departure_time)[:5], round(float(odometer), 2), round(float(distance), 2))


@app.route("/trips/import-template.csv")
@admin_required
def trip_import_template():
    output = io.StringIO()
    output.write("\ufeff")
    writer = csv.writer(output)
    writer.writerow(IMPORT_COLUMNS)
    writer.writerow(["SFA 4714", "2026-07-01", "08:00", "Official Business", "RASUC/RCAF", "Paved", "Flat",
                     "16368", "120", "180", "40", "0", "12.0", IMPORT_EXAMPLE_REMARK, "23.000", "35.000", "008500"])
    return Response(output.getvalue(), mimetype="text/csv; charset=utf-8",
                    headers={"Content-Disposition": "attachment; filename=trip_records_template.csv"})


@app.route("/trips/import", methods=["POST"])
@admin_required
def import_trips():
    """Bulk-import trip tickets from a CSV (e.g. saved from Excel). All rows
    are validated first; nothing is saved unless every row is valid."""
    _ensure_trip_sheet_columns()
    file = request.files.get("file")
    if not file or not file.filename.lower().endswith(".csv"):
        flash("Please choose a .csv file (in Excel: File > Save As > CSV UTF-8).", "danger")
        return redirect(url_for("trips"))
    text = _decode_csv(file.read())
    first_line = text.split("\n", 1)[0]
    delimiter = max((",", ";", "\t"), key=first_line.count)  # Excel uses ';' in some regional settings
    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    headers = [_header_key(h) for h in (reader.fieldnames or [])]
    reader.fieldnames = headers
    missing = [c for c in IMPORT_COLUMNS if c not in IMPORT_OPTIONAL and c not in headers]
    if missing:
        flash("The CSV is missing these columns: " + ", ".join(missing) + ". Download the template for the exact headers.", "danger")
        return redirect(url_for("trips"))

    vehicles_by_plate = {v["plate_number"].upper(): v["id"] for v in db.query_all("SELECT id, plate_number FROM vehicles")}
    existing = {_trip_key(t["vehicle_id"], t["trip_date"], format_time(t["departure_time"]), t["odometer_reading"],
                          t["distance_km"])
                for t in db.query_all("SELECT vehicle_id, trip_date, departure_time, odometer_reading, distance_km FROM trip_records")}
    payloads, errors, warnings_count, duplicates, examples = [], [], 0, 0, 0
    rows = list(reader)
    if len(rows) > IMPORT_MAX_ROWS:
        flash(f"Import at most {IMPORT_MAX_ROWS} rows at a time.", "danger")
        return redirect(url_for("trips"))
    for line_no, raw in enumerate(rows, start=2):  # row 1 is the header
        if not any(str(v or "").strip() for k, v in raw.items() if k is not None):
            continue
        row = _normalize_import_row(raw)
        if row["remarks"].lower() == IMPORT_EXAMPLE_REMARK:
            examples += 1  # the template's sample row, left in by mistake
            continue
        vid = vehicles_by_plate.get(row["plate_number"].upper())
        if not vid:
            errors.append(f"Row {line_no}: unknown plate number '{row['plate_number']}' (add the vehicle first).")
            continue
        form = dict(row, vehicle_id=str(vid))
        row_errors, row_warnings = validate_trip_form(form)
        errors.extend(f"Row {line_no}: {e}" for e in row_errors)
        if row_errors:
            continue
        key = _trip_key(vid, row["trip_date"], row["departure_time"], row["odometer_reading"], row["distance_km"])
        if key in existing:
            duplicates += 1  # already in the system (e.g. the same file imported twice)
            continue
        existing.add(key)
        warnings_count += len(row_warnings)
        payloads.append(_trip_payload(form))
    if errors:
        shown = errors[:8]
        more = f" ...and {len(errors) - 8} more." if len(errors) > 8 else ""
        flash("Nothing was imported. Fix these rows and try again: " + " ".join(shown) + more, "danger")
        return redirect(url_for("trips"))
    skipped = []
    if duplicates:
        skipped.append(f"{duplicates} row(s) skipped because the trip is already recorded")
    if examples:
        skipped.append("the template's example row was skipped")
    if not payloads:
        flash(("No new trip records to import: " + "; ".join(skipped) + ".") if skipped else "The CSV has no data rows.",
              "warning" if skipped else "danger")
        return redirect(url_for("trips"))

    conn = db.get_db()
    try:
        conn.begin()
        with conn.cursor() as cur:
            cur.executemany("""
                INSERT INTO trip_records (vehicle_id, trip_date, trip_type, departure_time,
                    route, road_type, terrain_classification, odometer_reading, distance_km,
                    duration_minutes, avg_speed_kmh, passenger_cargo_load_kg, actual_fuel_consumption, remarks,
                    balance_in_tank, fuel_received, or_invoice_no)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """, payloads)
        conn.commit()
    except Exception:
        conn.rollback()
        app.logger.exception("Trip import failed")
        flash("Nothing was imported because of a database error. Please try again.", "danger")
        return redirect(url_for("trips"))
    try:
        _sync_trip_fuel_records()  # fuel records for the imported trips with actual fuel
    except Exception:
        app.logger.exception("Auto-logging fuel records after import failed")
    msg = f"Imported {len(payloads)} trip record(s). The model retrains automatically."
    if skipped:
        msg += " " + "; ".join(skipped).capitalize() + "."
    if warnings_count:
        msg += f" {warnings_count} row(s) have a distance/duration/speed mismatch; please review them."
    flash(msg, "success")
    _link_actuals_quietly()
    return redirect(url_for("trips"))


@app.route("/trips/<int:trip_id>/delete", methods=["POST"])
@admin_required
def delete_trip(trip_id):
    if not db.query_one("SELECT id FROM trip_records WHERE id = %s", (trip_id,)):
        flash("That trip record no longer exists.", "danger")
        return redirect(url_for("trips"))
    try:
        # Its fuel record describes this trip, so it goes too (otherwise it is
        # left behind unlinked and Fuel Records no longer matches Trip Records).
        removed_fuel = db.query_one("SELECT COUNT(*) AS c FROM fuel_records WHERE trip_record_id = %s", (trip_id,))["c"]
        db.execute("DELETE FROM fuel_records WHERE trip_record_id = %s", (trip_id,))
        # A fuel request whose actual fuel came from this trip loses it (and may
        # be matched again to another trip below); manual entries are kept.
        _ensure_prediction_link_columns()
        db.execute("""UPDATE predictions SET actual_fuel = NULL, trip_record_id = NULL, actual_source = NULL
                      WHERE trip_record_id = %s AND actual_source = 'trip'""", (trip_id,))
        db.execute("UPDATE predictions SET trip_record_id = NULL WHERE trip_record_id = %s", (trip_id,))
        db.execute("DELETE FROM trip_records WHERE id = %s", (trip_id,))
        compact_ids("trip_records", "fuel_records")
        flash("Trip record deleted successfully." + (f" Its fuel record was deleted too." if removed_fuel else ""), "success")
        _link_actuals_quietly()
    except Exception:
        app.logger.exception("Deleting trip failed")
        flash("Could not delete trip record due to a database error. Please try again.", "danger")
    return redirect(url_for("trips"))


# ------------------------------------------------------------------
# FUEL RECORDS
# ------------------------------------------------------------------
def fuel_record(f, num):
    """JSON-safe fuel row used by the table, the shared modal and the live API."""
    return {
        "id": f["id"], "num": num, "vehicle_id": f["vehicle_id"], "trip_record_id": f["trip_record_id"] or "",
        "fuel_date": str(f["fuel_date"]), "fuel_type": f["fuel_type"],
        "liters_consumed": str(f["liters_consumed"]), "odometer_reading": str(f["odometer_reading"]),
        "fuel_cost": str(f["fuel_cost"]) if f["fuel_cost"] is not None else "",
        "remarks": f["remarks"] or "", "plate_number": f["plate_number"],
    }


def fuel_records_data():
    rows = db.query_all("""
        SELECT f.*, v.plate_number FROM fuel_records f
        JOIN vehicles v ON f.vehicle_id = v.id
        ORDER BY f.fuel_date, f.id
    """)  # oldest first (January to December), like Trip Records
    summary_row = db.query_one("""
        SELECT COALESCE(SUM(liters_consumed),0) AS total_liters,
               COALESCE(AVG(liters_consumed),0) AS avg_liters,
               SUM(trip_record_id IS NOT NULL) AS linked_count,
               COUNT(*) AS record_count
        FROM fuel_records
    """)
    summary = {
        "total_liters": f"{float(summary_row['total_liters']):,.2f}",
        "avg_liters": f"{float(summary_row['avg_liters']):,.2f}",
        "linked_count": int(summary_row["linked_count"] or 0),
        "record_count": summary_row["record_count"],
    }
    return [fuel_record(r, i) for i, r in enumerate(rows, 1)], summary


def validate_fuel_form(f):
    """Returns (errors, warnings). Errors block saving; warnings are shown
    but the record is still saved."""
    errors, warnings = [], []
    vid = (f.get("vehicle_id") or "").strip()
    vehicle = db.query_one("SELECT id, plate_number, fuel_type FROM vehicles WHERE id = %s", (vid,)) if vid.isdigit() else None
    if not vehicle:
        errors.append("Please choose a valid vehicle.")
    tid = (f.get("trip_record_id") or "").strip()
    if tid:
        trip = db.query_one("SELECT id, vehicle_id FROM trip_records WHERE id = %s", (tid,)) if tid.isdigit() else None
        if not trip:
            errors.append("The selected trip record does not exist.")
        elif vehicle and trip["vehicle_id"] != vehicle["id"]:
            errors.append(f"The selected trip belongs to a different vehicle, not {vehicle['plate_number']}.")
    try:
        fuel_date = date.fromisoformat((f.get("fuel_date") or "").strip())
        if not date(2000, 1, 1) <= fuel_date <= today_local():
            errors.append(f"Date must be between 2000-01-01 and today ({today_local().isoformat()}).")
    except ValueError:
        errors.append("Date must be a valid date.")
    if f.get("fuel_type") not in FUEL_TYPES:
        errors.append("Please choose a valid fuel type.")
    elif vehicle and f["fuel_type"] != vehicle["fuel_type"]:
        warnings.append(f"{vehicle['plate_number']} is registered as a {vehicle['fuel_type']} vehicle, "
                        f"but this record says {f['fuel_type']}. Please double-check.")
    for field, label, lo, hi, allow_lo, required in (
        ("liters_consumed", "Liters consumed", 0, 1000, False, True),
        ("odometer_reading", "Odometer reading", 0, 2_000_000, True, True),
        ("fuel_cost", "Fuel cost", 0, 1_000_000, True, False),
    ):
        raw = (f.get(field) or "").strip()
        if raw == "" and not required:
            continue
        try:
            value = float(raw)
            if value != value or value > hi or value < lo or (value == lo and not allow_lo):
                raise ValueError
        except ValueError:
            errors.append(f"{label} must be a number {'from' if allow_lo else 'greater than'} {lo:,} "
                          f"{'to' if allow_lo else 'and at most'} {hi:,}.")
    if len((f.get("remarks") or "").strip()) > 255:
        errors.append("Remarks must be at most 255 characters.")
    return errors, warnings


def _fuel_payload(f):
    # Fuel cost is not collected (financial reporting is outside the study's scope).
    return (
        f["vehicle_id"], (f.get("trip_record_id") or "").strip() or None, f["fuel_date"].strip(), f["fuel_type"],
        f["liters_consumed"], f["odometer_reading"], None, (f.get("remarks") or "").strip() or None,
    )


def fuel_trip_options():
    # Every trip (not just the latest 200), so editing an older record keeps its link.
    return db.query_all("""
        SELECT t.id, t.trip_date, t.vehicle_id, v.plate_number FROM trip_records t
        JOIN vehicles v ON t.vehicle_id = v.id ORDER BY t.trip_date DESC, t.id DESC
    """)


def render_fuel_page(reopen=None, status=200):
    rows, summary = fuel_records_data()
    vehicles_list = db.query_all("SELECT * FROM vehicles ORDER BY plate_number")
    trips_list = fuel_trip_options()
    return render_template(
        "fuel_records.html", active="fuel_records", fuel_records=rows, summary=summary,
        vehicles=vehicles_list, trips=trips_list, today=today_local().isoformat(), reopen=reopen,
    ), status


@app.route("/fuel-records")
@login_required
def fuel_records():
    return render_fuel_page()


@app.route("/api/fuel-records")
@login_required
def api_fuel_records():
    rows, summary = fuel_records_data()
    trips = [{"id": t["id"], "vehicle_id": t["vehicle_id"],
              "label": f"#{t['id']} - {t['plate_number']} ({t['trip_date']})"} for t in fuel_trip_options()]
    return {"fuel_records": rows, "summary": summary, "trips": trips}


@app.route("/fuel-records/add", methods=["POST"])
@login_required
def add_fuel_record():
    errors, warnings = validate_fuel_form(request.form)
    if errors:
        flash("Could not add fuel record: " + " ".join(errors), "danger")
        return render_fuel_page({"modal": "addFuelModal", "values": request.form.to_dict()})
    try:
        db.execute("""
            INSERT INTO fuel_records (vehicle_id, trip_record_id, fuel_date, fuel_type,
                liters_consumed, odometer_reading, fuel_cost, remarks)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
        """, _fuel_payload(request.form))
        flash("Fuel record added successfully.", "success")
        for w in warnings:
            flash(w, "warning")
    except Exception:
        app.logger.exception("Adding fuel record failed")
        flash("Could not add fuel record due to a database error. Please try again.", "danger")
    return redirect(url_for("fuel_records"))


@app.route("/fuel-records/<int:record_id>/edit", methods=["POST"])
@login_required
def edit_fuel_record(record_id):
    if not db.query_one("SELECT id FROM fuel_records WHERE id = %s", (record_id,)):
        flash("That fuel record no longer exists.", "danger")
        return redirect(url_for("fuel_records"))
    errors, warnings = validate_fuel_form(request.form)
    if errors:
        flash("Could not update fuel record: " + " ".join(errors), "danger")
        return render_fuel_page({"modal": "editFuelModal", "record_id": record_id,
                                 "values": request.form.to_dict()})
    try:
        db.execute("""
            UPDATE fuel_records SET vehicle_id=%s, trip_record_id=%s, fuel_date=%s, fuel_type=%s,
                liters_consumed=%s, odometer_reading=%s, fuel_cost=%s, remarks=%s
            WHERE id=%s
        """, _fuel_payload(request.form) + (record_id,))
        flash("Fuel record updated successfully.", "success")
        for w in warnings:
            flash(w, "warning")
    except Exception:
        app.logger.exception("Updating fuel record failed")
        flash("Could not update fuel record due to a database error. Please try again.", "danger")
    return redirect(url_for("fuel_records"))


@app.route("/fuel-records/<int:record_id>/delete", methods=["POST"])
@admin_required
def delete_fuel_record(record_id):
    if not db.query_one("SELECT id FROM fuel_records WHERE id = %s", (record_id,)):
        flash("That fuel record no longer exists.", "danger")
        return redirect(url_for("fuel_records"))
    try:
        db.execute("DELETE FROM fuel_records WHERE id = %s", (record_id,))
        compact_ids("fuel_records")
        flash("Fuel record deleted successfully.", "success")
    except Exception:
        app.logger.exception("Deleting fuel record failed")
        flash("Could not delete fuel record due to a database error. Please try again.", "danger")
    return redirect(url_for("fuel_records"))


# ------------------------------------------------------------------
# MODEL PERFORMANCE
# ------------------------------------------------------------------
_MODEL_CHARTS_CACHE = {"key": None, "data": None}
_RETRAIN_LOCK = threading.Lock()
_LAST_DATA_CHECK = {"at": 0.0}

# Every model feature column of a trip + its vehicle, so adding, editing or
# deleting any trip record (or editing a vehicle) changes the fingerprint.
_SYSTEM_DATA_FINGERPRINT_SQL = """
    SELECT COUNT(*) AS n,
           COALESCE(SUM(CRC32(CONCAT_WS('|', t.id, t.trip_type, t.departure_time, t.route, t.road_type,
               t.terrain_classification, t.odometer_reading, t.distance_km, t.duration_minutes,
               t.avg_speed_kmh, t.passenger_cargo_load_kg, t.actual_fuel_consumption,
               v.vehicle_type, v.engine_displacement, v.fuel_type, v.year_model))), 0) AS crc
    FROM trip_records t JOIN vehicles v ON t.vehicle_id = v.id
    WHERE t.actual_fuel_consumption IS NOT NULL
"""


def load_system_trip_records():
    """Trip records entered in the system that have a measured fuel value,
    shaped like the historical CSV so they can be trained on together."""
    from model.preprocess import departure_period_from_time
    rows = db.query_all("""
        SELECT v.vehicle_type, v.brand_model, v.engine_displacement, v.fuel_type, v.year_model,
               t.odometer_reading, t.distance_km, t.duration_minutes, t.avg_speed_kmh, t.trip_type,
               t.departure_time, t.passenger_cargo_load_kg, t.route, t.road_type,
               t.terrain_classification, t.actual_fuel_consumption
        FROM trip_records t JOIN vehicles v ON t.vehicle_id = v.id
        WHERE t.actual_fuel_consumption IS NOT NULL
    """)
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df["departure_time"] = df["departure_time"].map(lambda t: format_time(t) if isinstance(t, timedelta) else str(t))
    df["departure_period"] = df["departure_time"].map(departure_period_from_time)
    numeric = ["engine_displacement", "year_model", "odometer_reading", "distance_km", "duration_minutes",
               "avg_speed_kmh", "passenger_cargo_load_kg", "actual_fuel_consumption"]
    df[numeric] = df[numeric].astype(float)
    return df


def load_training_frame():
    """Historical CSV + system trip records, merged with rated efficiency."""
    from model.preprocess import load_and_merge_datasets
    return load_and_merge_datasets(app.config["HISTORICAL_DATA_PATH"],
                                   app.config["SUPPLEMENTARY_DATA_PATH"],
                                   extra_df=load_system_trip_records())


def current_data_fingerprint():
    """Changes whenever the CSV datasets or any trip/vehicle data the model
    trains on changes."""
    fp = db.query_one(_SYSTEM_DATA_FINGERPRINT_SQL)
    mtimes = [os.path.getmtime(app.config[k]) for k in ("HISTORICAL_DATA_PATH", "SUPPLEMENTARY_DATA_PATH")]
    return f"{mtimes[0]:.0f}-{mtimes[1]:.0f}-{int(fp['n'])}-{int(fp['crc'])}"


def retrain_model(log=None):
    """Retrain on CSV + system trip records and save model + metrics."""
    from model.train_model import train_and_save
    fingerprint = current_data_fingerprint()
    system_records = load_system_trip_records()
    from model.preprocess import load_and_merge_datasets, supplementary_info
    info = supplementary_info(app.config["SUPPLEMENTARY_DATA_PATH"])
    extra = {"data_fingerprint": fingerprint, "system_records": int(len(system_records)),
             "supplementary_kind": info["kind"]}
    df = load_and_merge_datasets(app.config["HISTORICAL_DATA_PATH"],
                                 app.config["SUPPLEMENTARY_DATA_PATH"], extra_df=system_records)
    return train_and_save(df, extra_metrics=extra, log=log or (lambda *a, **k: None),
                          excluded_features=info["dropped_features"])


_WATCHER = {"running": False, "retraining": False, "last_check": None}
_WATCHER_WAKE = threading.Event()
WATCHER_INTERVAL_SECONDS = 3

# Form submissions that change the model's training data; after any of these
# the watcher is woken immediately instead of waiting for its next tick.
_DATA_CHANGING_ENDPOINTS = {
    "add_trip", "edit_trip", "delete_trip", "import_trips",
    "add_vehicle", "edit_vehicle", "delete_vehicle",
}


def _check_and_retrain():
    """Retrain now if the CSV datasets or any trip/vehicle data the model
    trains on changed since the model was last trained."""
    if not all(os.path.exists(app.config[k]) for k in ("HISTORICAL_DATA_PATH", "SUPPLEMENTARY_DATA_PATH")):
        return
    with _RETRAIN_LOCK:
        fingerprint = current_data_fingerprint()
        saved = None
        if os.path.exists(app.config["METRICS_PATH"]) and os.path.exists(app.config["MODEL_PATH"]):
            with open(app.config["METRICS_PATH"]) as f:
                saved = json.load(f).get("data_fingerprint")
        _WATCHER["last_check"] = now_local().isoformat(timespec="seconds")
        if saved != fingerprint:
            app.logger.info("Training data changed; retraining model automatically...")
            _WATCHER["retraining"] = True
            try:
                retrain_model()
            finally:
                _WATCHER["retraining"] = False


def ensure_model_current():
    """Request-time fallback for when the background watcher is not running
    (e.g. the app is imported by a script). With the watcher running this is
    a no-op, so pages never wait on a retrain. Serverless hosting keeps the
    model trained on the office computer (its disk is read-only)."""
    if _WATCHER["running"] or app.config["SERVERLESS"]:
        return
    if time.time() - _LAST_DATA_CHECK["at"] < 3:
        return
    _LAST_DATA_CHECK["at"] = time.time()
    try:
        _check_and_retrain()
    except Exception:
        app.logger.exception("Automatic model retraining failed")


def _model_watcher_loop():
    while True:
        _WATCHER_WAKE.wait(WATCHER_INTERVAL_SECONDS)
        _WATCHER_WAKE.clear()
        try:
            with app.app_context():
                _check_and_retrain()
        except Exception:
            app.logger.exception("Automatic model retraining failed")


def start_model_watcher():
    """Background thread that keeps the model in sync with the data, whether
    or not anyone has a page open. Also catches edits made directly in the
    database or to the CSV files."""
    if _WATCHER["running"]:
        return
    _WATCHER["running"] = True
    threading.Thread(target=_model_watcher_loop, name="model-watcher", daemon=True).start()
    _WATCHER_WAKE.set()  # check once right away on startup


BACKUP_INTERVAL_HOURS = 24


def _latest_backup_age_hours():
    from backup_database import BACKUP_DIR
    try:
        files = [os.path.join(BACKUP_DIR, f) for f in os.listdir(BACKUP_DIR)
                 if f.startswith(app.config["MYSQL_DB"] + "_") and f.endswith(".sql")]
    except FileNotFoundError:
        return None
    if not files:
        return None
    return (time.time() - max(os.path.getmtime(f) for f in files)) / 3600


def _backup_loop():
    """Backs up the database every BACKUP_INTERVAL_HOURS while the server
    runs (start_server.bat also backs up on every start)."""
    import backup_database
    while True:
        try:
            age = _latest_backup_age_hours()
            if age is None or age >= BACKUP_INTERVAL_HOURS:
                backup_database.main()
        except Exception:
            app.logger.exception("Scheduled database backup failed")
        time.sleep(15 * 60)


def start_backup_scheduler():
    threading.Thread(target=_backup_loop, name="db-backup", daemon=True).start()


@app.after_request
def wake_model_watcher(response):
    if request.method == "POST" and request.endpoint in _DATA_CHANGING_ENDPOINTS:
        _WATCHER_WAKE.set()
    return response


def build_model_charts():
    """Chart data for the Model Performance page, computed from the same
    data and 80/20 split (random_state=42) the current model was trained
    on. Cached per model version, so it refreshes after every retrain."""
    from sklearn.model_selection import train_test_split
    from model.preprocess import FEATURE_COLUMNS, NUMERIC_FEATURES, TARGET_COLUMN, clean_data

    pipeline = get_model()
    metrics = get_metrics()
    if pipeline is None or metrics is None:
        return None
    key = metrics.get("model_version")
    if _MODEL_CHARTS_CACHE["key"] == key:
        return _MODEL_CHARTS_CACHE["data"]

    # Rebuild exactly the frame this model version was trained on: a model
    # trained before system records were included is charted on the CSV only.
    if metrics.get("system_records") is None:
        from model.preprocess import load_and_merge_datasets
        frame = load_and_merge_datasets(app.config["HISTORICAL_DATA_PATH"], app.config["SUPPLEMENTARY_DATA_PATH"])
    else:
        frame = load_training_frame()
    df = clean_data(frame)
    X_train, X_test, y_train, y_test = train_test_split(
        df[FEATURE_COLUMNS], df[TARGET_COLUMN], test_size=0.2, random_state=42)
    y_pred = pipeline.predict(X_test)
    actual = [round(float(v), 2) for v in y_test.values]
    predicted = [round(float(v), 2) for v in y_pred]
    lo, hi = min(actual + predicted), max(actual + predicted)

    # Histogram on "nice" fixed-width bins (1, 2, 2.5, 5 or 10 L) so every bar
    # covers the same, readable range, e.g. 0–2.5 L, 2.5–5 L, ...
    fuel = df[TARGET_COLUMN]
    fuel_max = float(fuel.max())
    width = next(w for w in (1, 2, 2.5, 5, 10, 25, 50) if fuel_max / w <= 20)
    edges = np.arange(0, np.floor(fuel_max / width) * width + width * 1.001, width)
    counts, edges = np.histogram(fuel, bins=edges)
    fmt = (lambda v: f"{v:g}")
    mode_i = int(np.argmax(counts))
    # A variable with the same value in every record has no defined
    # correlation; leave it out instead of showing a misleading 0.00.
    corr_cols = [c for c in NUMERIC_FEATURES if df[c].astype(float).nunique() > 1] + [TARGET_COLUMN]
    corr = df[corr_cols].corr().round(2).fillna(0)

    data = {
        "avp_points": [{"x": a, "y": p} for a, p in zip(actual, predicted)],
        "avp_line": [{"x": round(lo, 2), "y": round(lo, 2)}, {"x": round(hi, 2), "y": round(hi, 2)}],
        "residual_points": [{"x": p, "y": round(a - p, 2)} for a, p in zip(actual, predicted)],
        "residual_range": [round(min(predicted), 2), round(max(predicted), 2)],
        "dist_labels": [f"{fmt(edges[i])}–{fmt(edges[i + 1])}" for i in range(len(counts))],
        "dist_counts": [int(c) for c in counts],
        "dist_stats": {
            "records": int(len(fuel)),
            "mean": round(float(fuel.mean()), 2),
            "median": round(float(fuel.median()), 2),
            "min": round(float(fuel.min()), 2),
            "max": round(fuel_max, 2),
            "std": round(float(fuel.std()), 2),
            "mode_range": f"{fmt(edges[mode_i])}–{fmt(edges[mode_i + 1])}",
            "mode_count": int(counts[mode_i]),
            "bin_width": width,
        },
        "corr_labels": corr_cols,
        "corr_matrix": corr.values.tolist(),
        "corr_records": int(len(df)),
    }
    _MODEL_CHARTS_CACHE.update(key=key, data=data)
    return data


@app.route("/model-performance")
@admin_required
def model_performance():
    ensure_model_current()
    return render_template("model_performance.html", active="model_performance", metrics=get_metrics())


@app.route("/model-performance/dataset/<name>.csv")
@admin_required
def export_training_dataset(name):
    """The model's training data for the Google Colab notebook
    (notebooks/fuel_consumption_linear_regression.ipynb), which reads
    historical_fleet_data.csv and supplementary_data.csv:

    * historical_fleet_data - the rows of the historical CSV plus every trip
      record in the system with actual fuel, in the same columns and order the
      web application trains on, so the notebook reproduces its results;
    * supplementary_data - the supplementary dataset, unchanged."""
    if name == "supplementary_data":
        with open(app.config["SUPPLEMENTARY_DATA_PATH"], "rb") as f:
            body = f.read()
    elif name == "historical_fleet_data":
        columns = list(pd.read_csv(app.config["HISTORICAL_DATA_PATH"], nrows=0).columns)
        historical = pd.read_csv(app.config["HISTORICAL_DATA_PATH"])
        system = load_system_trip_records()
        frames = [f for f in (historical, system.reindex(columns=columns) if not system.empty else None)
                  if f is not None and not f.empty]
        data = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=columns)
        body = data[columns].to_csv(index=False).encode("utf-8")
    else:
        flash("Unknown dataset.", "danger")
        return redirect(url_for("model_performance"))
    return Response(body, mimetype="text/csv",  # Flask adds "; charset=utf-8"
                    headers={"Content-Disposition": f"attachment; filename={name}.csv"})


@app.route("/api/model-status")
@login_required
def api_model_status():
    """Tiny, cheap endpoint the pages poll every couple of seconds; they only
    fetch the full chart data when the model version changes."""
    metrics = get_metrics() or {}
    return {
        "model_version": metrics.get("model_version"),
        "retraining": _WATCHER["retraining"],
        "last_check": _WATCHER["last_check"],
    }


@app.route("/api/model-performance-data")
@admin_required
def api_model_performance_data():
    ensure_model_current()
    return {"metrics": get_metrics(), "charts": build_model_charts(), "dataset": dataset_status()}


# ------------------------------------------------------------------
# REPORTS
# ------------------------------------------------------------------
# Which filters each report actually uses (the page disables the others).
REPORT_FILTERS = {
    "vehicle": ["vehicle_id", "fuel_type"],
    "trip": ["date_from", "date_to", "vehicle_id", "trip_type"],
    "fuel": ["date_from", "date_to", "vehicle_id", "fuel_type"],
    "prediction": ["date_from", "date_to", "vehicle_id", "fuel_type", "trip_type"],
    "model": [],
}


def parse_report_args(args):
    """Validate the report filters. Returns (filters, errors); filters only
    contains the ones that apply to the chosen report type."""
    errors = []
    report_type = args.get("type", "")
    if report_type not in REPORT_TYPES:
        return {"type": None}, ["Please choose a valid report type."]
    f = {"type": report_type}
    allowed = REPORT_FILTERS[report_type]
    for key in ("date_from", "date_to"):
        raw = (args.get(key) or "").strip()
        if key in allowed and raw:
            try:
                f[key] = date.fromisoformat(raw)
            except ValueError:
                errors.append(f"{'Date From' if key == 'date_from' else 'Date To'} is not a valid date.")
    if f.get("date_from") and f.get("date_to") and f["date_from"] > f["date_to"]:
        errors.append("Date From must be on or before Date To.")
    vid = (args.get("vehicle_id") or "").strip()
    if "vehicle_id" in allowed and vid:
        v = db.query_one("SELECT id, plate_number FROM vehicles WHERE id = %s", (vid,)) if vid.isdigit() else None
        if v:
            f["vehicle_id"], f["vehicle_label"] = v["id"], v["plate_number"]
        else:
            errors.append("The selected vehicle does not exist.")
    ft = args.get("fuel_type") or ""
    if "fuel_type" in allowed and ft:
        if ft in FUEL_TYPES:
            f["fuel_type"] = ft
        else:
            errors.append("Please choose a valid fuel type.")
    tt = args.get("trip_type") or ""
    if "trip_type" in allowed and tt:
        if tt in TRIP_TYPES:
            f["trip_type"] = tt
        else:
            errors.append("Please choose a valid trip type.")
    return f, errors


def _num(v, places=2):
    return f"{float(v):,.{places}f}"


def build_report(f):
    """Returns (columns, rows, totals) for validated filters `f`. All cell
    values are strings so the same data serves HTML, JSON and CSV."""
    report_type = f["type"]
    date_from, date_to = f.get("date_from"), f.get("date_to")
    vehicle_id, fuel_type, trip_type = f.get("vehicle_id"), f.get("fuel_type"), f.get("trip_type")
    dash = "—"

    if report_type == "vehicle":
        # Same columns as the GSO vehicle list, plus the specs the model uses.
        columns = ["No.", "Vehicle Model", "Plate Number", "Seating Capacity", "Station", "Driver", "Remarks",
                   "Vehicle Type", "Engine (L)", "Fuel Type", "Year Model", "Status"]
        where, params = ["1=1"], []
        if vehicle_id:
            where.append("id = %s"); params.append(vehicle_id)
        if fuel_type:
            where.append("fuel_type = %s"); params.append(fuel_type)
        _ensure_vehicle_columns()
        rows_db = db.query_all(f"SELECT * FROM vehicles WHERE {' AND '.join(where)} ORDER BY plate_number", params)
        rows = [{"No.": str(i), "Vehicle Model": r["brand_model"], "Plate Number": r["plate_number"],
                 "Seating Capacity": str(r["seating_capacity"]) if r["seating_capacity"] is not None else dash,
                 "Station": r["station"] or dash, "Driver": r["assigned_driver"] or dash, "Remarks": r["remarks"] or dash,
                 "Vehicle Type": r["vehicle_type"], "Engine (L)": str(r["engine_displacement"]),
                 "Fuel Type": r["fuel_type"], "Year Model": str(r["year_model"]), "Status": r["status"]} for i, r in enumerate(rows_db, 1)]
        totals = {"Vehicles": str(len(rows))}
        for st in VEHICLE_STATUSES:
            totals[st] = str(sum(1 for r in rows_db if r["status"] == st))

    elif report_type == "trip":
        columns = ["No.", "Date", "Vehicle", "Trip Type", "Route", "Distance (km)", "Duration (min)", "Avg Speed (km/h)", "Actual Fuel (L)"]
        where, params = ["1=1"], []
        if date_from: where.append("t.trip_date >= %s"); params.append(date_from)
        if date_to: where.append("t.trip_date <= %s"); params.append(date_to)
        if vehicle_id: where.append("t.vehicle_id = %s"); params.append(vehicle_id)
        if trip_type: where.append("t.trip_type = %s"); params.append(trip_type)
        rows_db = db.query_all(f"""
            SELECT t.*, v.plate_number FROM trip_records t JOIN vehicles v ON t.vehicle_id=v.id
            WHERE {' AND '.join(where)} ORDER BY t.trip_date, t.departure_time, t.id
        """, params)
        rows = [{"No.": str(i), "Date": str(r["trip_date"]), "Vehicle": r["plate_number"], "Trip Type": r["trip_type"],
                 "Route": r["route"], "Distance (km)": str(r["distance_km"]), "Duration (min)": str(r["duration_minutes"]),
                 "Avg Speed (km/h)": str(r["avg_speed_kmh"]),
                 "Actual Fuel (L)": str(r["actual_fuel_consumption"]) if r["actual_fuel_consumption"] is not None else dash}
                for i, r in enumerate(rows_db, 1)]
        fuel_vals = [float(r["actual_fuel_consumption"]) for r in rows_db if r["actual_fuel_consumption"] is not None]
        totals = {"Trips": str(len(rows)),
                  "Total Distance": _num(sum(float(r["distance_km"]) for r in rows_db)) + " km",
                  "Total Actual Fuel": _num(sum(fuel_vals)) + " L",
                  "Avg Fuel / Trip": (_num(sum(fuel_vals) / len(fuel_vals)) + " L") if fuel_vals else dash}

    elif report_type == "fuel":
        # No cost column: fuel budget monitoring / financial reporting is outside the study's scope.
        columns = ["No.", "Date", "Vehicle", "Fuel Type", "Liters", "Odometer (km)", "Remarks"]
        where, params = ["1=1"], []
        if date_from: where.append("f.fuel_date >= %s"); params.append(date_from)
        if date_to: where.append("f.fuel_date <= %s"); params.append(date_to)
        if vehicle_id: where.append("f.vehicle_id = %s"); params.append(vehicle_id)
        if fuel_type: where.append("f.fuel_type = %s"); params.append(fuel_type)
        rows_db = db.query_all(f"""
            SELECT f.*, v.plate_number FROM fuel_records f JOIN vehicles v ON f.vehicle_id=v.id
            WHERE {' AND '.join(where)} ORDER BY f.fuel_date, f.id
        """, params)
        rows = [{"No.": str(i), "Date": str(r["fuel_date"]), "Vehicle": r["plate_number"], "Fuel Type": r["fuel_type"],
                 "Liters": str(r["liters_consumed"]), "Odometer (km)": str(r["odometer_reading"]),
                 "Remarks": r["remarks"] or dash} for i, r in enumerate(rows_db, 1)]
        totals = {"Records": str(len(rows)),
                  "Total Liters": _num(sum(float(r["liters_consumed"]) for r in rows_db)) + " L",
                  "Avg Liters / Record": (_num(sum(float(r["liters_consumed"]) for r in rows_db) / len(rows_db)) + " L")
                  if rows_db else "—"}

    elif report_type == "prediction":
        columns = ["No.", "Date", "Vehicle", "Distance (km)", "Fuel Type", "Predicted Fuel (L)", "Actual Fuel (L)", "Difference (L)"]
        where, params = ["1=1"], []
        if date_from: where.append("DATE(p.created_at) >= %s"); params.append(date_from)
        if date_to: where.append("DATE(p.created_at) <= %s"); params.append(date_to)
        if vehicle_id: where.append("p.vehicle_id = %s"); params.append(vehicle_id)
        if fuel_type: where.append("p.fuel_type = %s"); params.append(fuel_type)
        if trip_type: where.append("p.trip_type = %s"); params.append(trip_type)
        rows_db = db.query_all(f"""
            SELECT p.*, v.plate_number FROM predictions p LEFT JOIN vehicles v ON p.vehicle_id=v.id
            WHERE {' AND '.join(where)} ORDER BY p.created_at, p.id
        """, params)  # in request order, like Prediction History
        rows, errs = [], []
        for i, r in enumerate(rows_db, 1):
            diff = None
            if r["actual_fuel"] is not None:
                diff = float(r["predicted_fuel"]) - float(r["actual_fuel"])
                errs.append(abs(diff))
            rows.append({"No.": str(i), "Date": r["created_at"].strftime("%Y-%m-%d"),
                         "Vehicle": r["plate_number"] or "Manual Entry",
                         "Distance (km)": str(r["distance_km"]), "Fuel Type": r["fuel_type"],
                         "Predicted Fuel (L)": str(r["predicted_fuel"]),
                         "Actual Fuel (L)": str(r["actual_fuel"]) if r["actual_fuel"] is not None else dash,
                         "Difference (L)": f"{diff:.2f}" if diff is not None else dash})
        totals = {"Predictions": str(len(rows)),
                  "Total Predicted": _num(sum(float(r["predicted_fuel"]) for r in rows_db)) + " L",
                  "With Actual": str(len(errs)),
                  "Average Error": (_num(sum(errs) / len(errs)) + " L") if errs else dash}

    else:  # model
        columns = ["Metric", "Value"]
        m = get_metrics()
        rows = []
        if m:
            for label, value in (
                ("Model Version", m.get("model_version")), ("R² Score", m.get("r2_score")),
                ("MAE (L)", m.get("mae")), ("RMSE (L)", m.get("rmse")),
                ("Cross-Validation Folds", m.get("cv_folds")), ("CV Mean R²", m.get("cv_mean_r2")),
                ("CV Std. Deviation", m.get("cv_std_r2")), ("Training Set Size", m.get("train_size")),
                ("Testing Set Size", m.get("test_size")), ("Total Dataset Records", m.get("total_records")),
                ("System Trip Records Used", m.get("system_records")),
                ("Trained At", m.get("trained_at_display")), ("Model Status", (m.get("status") or "").capitalize()),
            ):
                if value is not None:
                    rows.append({"Metric": label, "Value": str(value)})
            removed = m.get("removed_features") or []
            if m.get("vif_initial") is not None:
                rows.append({"Metric": f"Predictors removed (VIF > {m.get('vif_threshold', 5):g})",
                             "Value": ", ".join(f"{r['feature']} ({r['vif']})" for r in removed) or "None"})
                rows.append({"Metric": "Numeric predictors used",
                             "Value": ", ".join(m.get("selected_numeric_features") or [])})
            for t in (m.get("diagnostics") or {}).get("tests", []):
                p = "" if t["p_value"] is None else f", p = {t['p_value']}"
                rows.append({"Metric": f"{t['assumption']} ({t['test']})",
                             "Value": f"{'Met' if t['passed'] else 'Not met'} (statistic {t['statistic']}{p})"})
        totals = {}

    return columns, rows, totals


def report_payload(args):
    f, errors = parse_report_args(args)
    if errors:
        return {"errors": errors, "columns": [], "rows": [], "totals": [], "title": ""}
    columns, rows, totals = build_report(f)
    applied = []
    if f.get("date_from") or f.get("date_to"):
        applied.append(f"Date: {f.get('date_from') or 'start'} to {f.get('date_to') or 'today'}")
    if f.get("vehicle_label"):
        applied.append(f"Vehicle: {f['vehicle_label']}")
    if f.get("fuel_type"):
        applied.append(f"Fuel: {f['fuel_type']}")
    if f.get("trip_type"):
        applied.append(f"Trip type: {f['trip_type']}")
    return {"errors": [], "type": f["type"], "title": REPORT_TYPES[f["type"]], "columns": columns, "rows": rows,
            # A list keeps the display order (JSON objects get their keys sorted).
            "totals": list(totals.items()), "applied": applied or ["All records"],
            "generated_at": now_local().strftime("%B %d, %Y %I:%M:%S %p")}


@app.route("/reports")
@admin_required
def reports():
    vehicles_list = db.query_all("SELECT * FROM vehicles ORDER BY plate_number")
    generated = "type" in request.args
    report = report_payload(request.args) if generated else None
    return render_template(
        "reports.html", active="reports", report_types=REPORT_TYPES, report_filters=REPORT_FILTERS,
        vehicles=vehicles_list, trip_types=TRIP_TYPES, generated=generated, report=report,
    )


@app.route("/api/reports")
@admin_required
def api_reports():
    payload = report_payload(request.args)
    # Keeps the page's Vehicle filter in sync with vehicles added/removed elsewhere.
    payload["vehicles"] = [{"id": v["id"], "plate_number": v["plate_number"]}
                           for v in db.query_all("SELECT id, plate_number FROM vehicles ORDER BY plate_number")]
    return payload


def _csv_safe(value):
    """Stop spreadsheet apps from running cell text as a formula (CSV injection)."""
    text = "" if value is None else str(value)
    return "'" + text if text[:1] in ("=", "+", "-", "@", "\t", "\r") and not _looks_numeric(text) else text


def _looks_numeric(text):
    try:
        float(text.replace(",", ""))
        return True
    except ValueError:
        return False


@app.route("/reports/export-csv")
@admin_required
def export_report_csv():
    report = report_payload(request.args)
    if report["errors"]:
        flash("Could not export report: " + " ".join(report["errors"]), "danger")
        return redirect(url_for("reports", **request.args))
    output = io.StringIO()
    output.write("\ufeff")  # BOM so Excel shows R², ₱ and — correctly
    writer = csv.writer(output)
    writer.writerow([report["title"]])
    writer.writerow(["Generated", report["generated_at"]])
    writer.writerow(["Filters", "; ".join(report["applied"])])
    writer.writerow([])
    writer.writerow(report["columns"])
    for row in report["rows"]:
        writer.writerow([_csv_safe(row[c]) for c in report["columns"]])
    if report["totals"]:
        writer.writerow([])
        for label, value in report["totals"]:
            writer.writerow([label, _csv_safe(value)])
    return Response(
        output.getvalue(), mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename={report['type']}_report_{today_local().isoformat()}.csv"},
    )


# ------------------------------------------------------------------
# SETTINGS
# ------------------------------------------------------------------
EMAIL_RE = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")


def render_settings(form=None, status=200):
    user = db.query_one("SELECT * FROM users WHERE id = %s", (session["user_id"],))
    return render_template("settings.html", active="settings", user=user, form=form or {},
                           avatar=avatar_url(user["profile_photo"])), status


@app.route("/settings")
@login_required
def settings():
    return render_settings()


@app.route("/settings/organization", methods=["POST"])
@admin_required
def update_organization():
    values, errors = {}, []
    labels = {"org_name": "Agency / organization name", "org_short": "Short name",
              "office_name": "Office name", "office_short": "Office short name"}
    for key, limit in ORG_LIMITS.items():
        value = re.sub(r"\s+", " ", request.form.get(key, "")).strip()
        if not value:
            errors.append(f"{labels[key]} is required.")
        elif len(value) > limit:
            errors.append(f"{labels[key]} must be at most {limit} characters.")
        values[key] = value
    if errors:
        for e in errors:
            flash(e, "danger")
        return redirect(url_for("settings"))
    _ensure_org_table()
    for key, value in values.items():
        db.execute("""INSERT INTO app_settings (setting_key, setting_value) VALUES (%s, %s)
                      ON DUPLICATE KEY UPDATE setting_value = VALUES(setting_value)""", (key, value))
    g.pop("org", None)
    flash("Organization details saved. Every page now shows the new name.", "success")
    return redirect(url_for("settings"))


@app.route("/api/me")
@login_required
def api_me():
    """Current account details, polled by every page so the name and photo
    in the top bar (and the settings form) stay in sync across tabs."""
    user = db.query_one("SELECT username, full_name, email, role, profile_photo FROM users WHERE id = %s",
                        (session["user_id"],))
    return {
        "username": user["username"], "full_name": user["full_name"], "email": user["email"] or "",
        "role": user["role"].capitalize(), "initial": (user["full_name"] or "U")[0].upper(),
        "avatar_url": avatar_url(user["profile_photo"]),
    }


@app.route("/settings/profile", methods=["POST"])
@login_required
def update_profile():
    full_name = " ".join((request.form.get("full_name") or "").split())
    email = (request.form.get("email") or "").strip()
    errors = []
    if not 2 <= len(full_name) <= 100:
        errors.append("Full name must be 2 to 100 characters.")
    if email:
        if len(email) > 120 or not EMAIL_RE.fullmatch(email):
            errors.append("Please enter a valid email address.")
        elif db.query_one("SELECT id FROM users WHERE LOWER(email) = LOWER(%s) AND id <> %s", (email, session["user_id"])):
            errors.append("That email address is already used by another account.")
    if errors:
        flash("Could not save profile: " + " ".join(errors), "danger")
        return render_settings({"full_name": request.form.get("full_name", ""), "email": email})
    db.execute("UPDATE users SET full_name=%s, email=%s WHERE id=%s", (full_name, email or None, session["user_id"]))
    session["full_name"] = full_name
    flash("Profile updated successfully.", "success")
    return redirect(url_for("settings"))


@app.route("/settings/photo", methods=["POST"])
@login_required
def update_profile_photo():
    file = request.files.get("photo")
    if not file or not file.filename:
        return {"success": False, "message": "No file selected."}

    ext = os.path.splitext(secure_filename(file.filename))[1].lower().lstrip(".")
    if ext not in {"png", "jpg", "jpeg", "webp"}:
        return {"success": False, "message": "Only PNG, JPG, or WEBP images are allowed."}

    file.seek(0, os.SEEK_END)
    size = file.tell()
    file.seek(0)
    if size > AVATAR_MAX_BYTES:
        return {"success": False, "message": "Image must be smaller than 3 MB."}

    try:
        image = Image.open(file)
        image.verify()
        file.seek(0)
        image = Image.open(file).convert("RGB")
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError, Image.DecompressionBombWarning):
        return {"success": False, "message": "That file is not a valid image (or its dimensions are too large)."}

    image.thumbnail((AVATAR_MAX_DIMENSION, AVATAR_MAX_DIMENSION))

    user_id = session["user_id"]
    for existing in (os.listdir(AVATAR_DIR) if os.path.isdir(AVATAR_DIR) else []):
        if existing.startswith(f"user_{user_id}."):
            try:
                os.remove(os.path.join(AVATAR_DIR, existing))
            except OSError:
                pass

    filename = f"user_{user_id}.jpg"
    try:
        image.save(os.path.join(AVATAR_DIR, filename), "JPEG", quality=88)
    except OSError:
        return {"success": False, "message": "Profile photos cannot be saved on this online server."}

    relative_path = f"images/avatars/{filename}"
    db.execute("UPDATE users SET profile_photo=%s WHERE id=%s", (relative_path, user_id))
    session["profile_photo"] = relative_path

    return {"success": True, "url": avatar_url(relative_path)}


@app.route("/settings/photo/remove", methods=["POST"])
@login_required
def remove_profile_photo():
    user_id = session["user_id"]
    for existing in (os.listdir(AVATAR_DIR) if os.path.isdir(AVATAR_DIR) else []):
        if existing.startswith(f"user_{user_id}."):
            try:
                os.remove(os.path.join(AVATAR_DIR, existing))
            except OSError:
                pass

    db.execute("UPDATE users SET profile_photo=NULL WHERE id=%s", (user_id,))
    session["profile_photo"] = None

    return {"success": True}


@app.route("/settings/password", methods=["POST"])
@login_required
def change_password():
    user = db.query_one("SELECT * FROM users WHERE id = %s", (session["user_id"],))
    current_password = request.form.get("current_password", "")
    new_password = request.form.get("new_password", "")
    confirm_password = request.form.get("confirm_password", "")

    if not check_password_hash(user["password_hash"], current_password):
        flash("Current password is incorrect.", "danger")
    elif password_problem(new_password, user["username"]):
        flash("New " + password_problem(new_password, user["username"])[0].lower()
              + password_problem(new_password, user["username"])[1:], "danger")
    elif check_password_hash(user["password_hash"], new_password):
        flash("New password must be different from your current password.", "danger")
    elif new_password != confirm_password:
        flash("New password and confirmation do not match.", "danger")
    else:
        new_hash = generate_password_hash(new_password)
        db.execute("UPDATE users SET password_hash=%s WHERE id=%s", (new_hash, session["user_id"]))
        session["pw_sig"] = password_signature(new_hash)  # stay logged in here; other sessions are signed out
        session.pop("must_change_pw", None)
        flash("Password updated successfully. You were signed out on your other devices.", "success")
    return redirect(url_for("settings"))


# ------------------------------------------------------------------
# USER ACCOUNTS (admin only)
# ------------------------------------------------------------------
USER_ROLES = ["admin", "staff"]
USER_STATUSES = ["active", "inactive"]
USERNAME_RE = re.compile(r"[A-Za-z0-9_.-]{3,50}")


def password_problem(password, username=""):
    """Shared password policy (Settings and User Accounts). None when valid."""
    if not 8 <= len(password) <= 128:
        return "Password must be 8 to 128 characters long."
    if password in DEFAULT_PASSWORDS:
        return "Password must not be one of the default passwords printed in the setup guide."
    if not (re.search(r"[A-Za-z]", password) and re.search(r"\d", password)):
        return "Password must contain at least one letter and one number."
    if username and password.lower() == username.lower():
        return "Password must not be the same as the username."
    return None


def user_record(u, num):
    return {"id": u["id"], "num": num, "username": u["username"], "full_name": u["full_name"],
            "email": u["email"] or "", "role": u["role"], "status": u["status"],
            "created_at": u["created_at"].strftime("%b %d, %Y") if u["created_at"] else "",
            "is_self": u["id"] == session.get("user_id")}


def query_users():
    rows = db.query_all("SELECT * FROM users ORDER BY status = 'pending' DESC, role = 'admin' DESC, full_name")
    return [user_record(u, i) for i, u in enumerate(rows, 1)]


def validate_user_form(f, user_id=None):
    errors = []
    full_name = " ".join((f.get("full_name") or "").split())
    email = (f.get("email") or "").strip()
    if user_id is None:
        username = (f.get("username") or "").strip()
        if not USERNAME_RE.fullmatch(username):
            errors.append("Username must be 3-50 characters: letters, numbers, dot, dash or underscore.")
        elif db.query_one("SELECT id FROM users WHERE LOWER(username) = LOWER(%s)", (username,)):
            errors.append(f"Username {username} is already taken.")
    if not 2 <= len(full_name) <= 100:
        errors.append("Full name must be 2 to 100 characters.")
    if email:
        if len(email) > 120 or not EMAIL_RE.fullmatch(email):
            errors.append("Please enter a valid email address.")
        elif db.query_one("SELECT id FROM users WHERE LOWER(email) = LOWER(%s) AND id <> %s", (email, user_id or 0)):
            errors.append("That email address is already used by another account.")
    if f.get("role") not in USER_ROLES:
        errors.append("Please choose a valid role.")
    if f.get("status") not in USER_STATUSES:
        errors.append("Please choose a valid status.")
    return errors, full_name, email


def _would_remove_last_admin(user_id, new_role, new_status):
    """True if this change leaves no active administrator."""
    if new_role == "admin" and new_status == "active":
        return False
    others = db.query_one("SELECT COUNT(*) AS c FROM users WHERE role = 'admin' AND status = 'active' AND id <> %s",
                          (user_id,))["c"]
    return others == 0


@app.route("/users")
@admin_required
def users():
    return render_template("users.html", active="users", users=query_users(), roles=USER_ROLES, statuses=USER_STATUSES)


@app.route("/api/users")
@admin_required
def api_users():
    users_list = query_users()
    return {"users": users_list, "pending": sum(1 for u in users_list if u["status"] == "pending")}


@app.route("/users/add", methods=["POST"])
@admin_required
def add_user():
    f = request.form
    errors, full_name, email = validate_user_form(f)
    problem = password_problem(f.get("password", ""), f.get("username", ""))
    if problem:
        errors.append(problem)
    elif f.get("password") != f.get("confirm_password"):
        errors.append("Password and confirmation do not match.")
    if errors:
        flash("Could not create account: " + " ".join(errors), "danger")
        return redirect(url_for("users"))
    db.execute("""INSERT INTO users (username, password_hash, full_name, email, role, status)
                  VALUES (%s, %s, %s, %s, %s, %s)""",
               (f["username"].strip(), generate_password_hash(f["password"]), full_name, email or None,
                f["role"], f["status"]))
    flash(f"Account {f['username'].strip()} created. Share the username and password with the user.", "success")
    return redirect(url_for("users"))


@app.route("/users/<int:user_id>/edit", methods=["POST"])
@admin_required
def edit_user(user_id):
    target = db.query_one("SELECT * FROM users WHERE id = %s", (user_id,))
    if not target:
        flash("That account no longer exists.", "danger")
        return redirect(url_for("users"))
    f = request.form
    errors, full_name, email = validate_user_form(f, user_id)
    if not errors and user_id == session["user_id"] and (f["role"] != "admin" or f["status"] != "active"):
        errors.append("You cannot remove your own administrator access or deactivate your own account.")
    if not errors and _would_remove_last_admin(user_id, f["role"], f["status"]):
        errors.append("At least one active administrator account must remain.")
    if errors:
        flash("Could not update account: " + " ".join(errors), "danger")
        return redirect(url_for("users"))
    db.execute("UPDATE users SET full_name=%s, email=%s, role=%s, status=%s WHERE id=%s",
               (full_name, email or None, f["role"], f["status"], user_id))
    flash(f"Account {target['username']} updated.", "success")
    return redirect(url_for("users"))


@app.route("/users/<int:user_id>/approve", methods=["POST"])
@admin_required
def approve_user(user_id):
    target = db.query_one("SELECT * FROM users WHERE id = %s", (user_id,))
    if not target or target["status"] != "pending":
        flash("That sign-up request no longer exists or was already handled.", "danger")
        return redirect(url_for("users"))
    db.execute("UPDATE users SET status = 'active' WHERE id = %s", (user_id,))
    flash(f"Account {target['username']} approved. The user can now log in.", "success")
    return redirect(url_for("users"))


@app.route("/users/<int:user_id>/reject", methods=["POST"])
@admin_required
def reject_user(user_id):
    target = db.query_one("SELECT * FROM users WHERE id = %s", (user_id,))
    if not target or target["status"] != "pending":
        flash("That sign-up request no longer exists or was already handled.", "danger")
        return redirect(url_for("users"))
    db.execute("DELETE FROM users WHERE id = %s AND status = 'pending'", (user_id,))
    compact_ids("users")
    flash(f"Sign-up request from {target['username']} was rejected and removed.", "success")
    return redirect(url_for("users"))


@app.route("/users/<int:user_id>/reset-password", methods=["POST"])
@admin_required
def reset_user_password(user_id):
    target = db.query_one("SELECT * FROM users WHERE id = %s", (user_id,))
    if not target:
        flash("That account no longer exists.", "danger")
        return redirect(url_for("users"))
    password = request.form.get("password", "")
    problem = password_problem(password, target["username"])
    if not problem and password != request.form.get("confirm_password"):
        problem = "Password and confirmation do not match."
    if problem:
        flash("Could not reset password: " + problem, "danger")
        return redirect(url_for("users"))
    new_hash = generate_password_hash(password)
    db.execute("UPDATE users SET password_hash=%s WHERE id=%s", (new_hash, user_id))
    if user_id == session["user_id"]:
        session["pw_sig"] = password_signature(new_hash)
    flash(f"Password for {target['username']} was reset and the user was signed out of any open sessions. "
          "Give the new password to the user.", "success")
    return redirect(url_for("users"))


# ------------------------------------------------------------------
# ERROR HANDLING
# ------------------------------------------------------------------
from flask_wtf.csrf import CSRFError
import warnings
warnings.simplefilter("error", Image.DecompressionBombWarning)  # treat oversized images as invalid


def _wants_json():
    return request.path.startswith("/api/") or request.path == "/settings/photo" or \
        request.accept_mimetypes.best == "application/json"


@app.errorhandler(CSRFError)
def handle_csrf_error(e):
    if _wants_json():
        return {"success": False, "message": "Your session expired. Please reload the page and try again."}, 400
    flash("Your session expired or the form was out of date. Please try again.", "danger")
    ref = request.referrer or ""
    return redirect(ref if ref.startswith(request.host_url) else url_for("index"))


@app.errorhandler(413)
def handle_too_large(e):
    if _wants_json():
        return {"success": False, "message": "The file is too large (maximum 5 MB)."}, 413
    flash("The uploaded data is too large (maximum 5 MB).", "danger")
    return redirect(request.referrer or url_for("index"))


@app.errorhandler(404)
def handle_not_found(e):
    if _wants_json():
        return {"error": "not_found"}, 404
    return render_template("error.html", code=404, title="Page not found",
                           message="The page you are looking for does not exist or was moved."), 404


@app.errorhandler(500)
def handle_server_error(e):
    app.logger.exception("Unhandled server error")
    # MySQL stopped (e.g. stopped or closed in the XAMPP Control Panel): say so plainly.
    original = getattr(e, "original_exception", None)
    if isinstance(original, pymysql.err.OperationalError) and original.args and original.args[0] in (2003, 2006, 2013):
        if _wants_json():
            return {"error": "database_unavailable"}, 503
        message = ("The online database cannot be reached right now. Please try again in a few minutes; "
                   "if it keeps happening, contact the system administrator.") if app.config["ONLINE"] else \
                  "MySQL is not running. Open the XAMPP Control Panel, press Start on MySQL, then reload this page."
        return render_template("error.html", code=503, title="Database is not running", message=message), 503
    if _wants_json():
        return {"error": "server_error"}, 500
    return render_template("error.html", code=500, title="Something went wrong",
                           message="An unexpected error occurred. Please try again; if it keeps happening, "
                                   "contact the system administrator."), 500


if __name__ == "__main__":
    # Serve with Waitress: on this Windows setup the Werkzeug development
    # server intermittently cut larger pages short (stalling ~19 s and
    # dropping the end of the HTML, including the page's JavaScript).
    # Set USE_DEV_SERVER=1 to use Flask's auto-reloading debug server instead.
    if os.environ.get("USE_DEV_SERVER") == "1":
        if os.environ.get("WERKZEUG_RUN_MAIN") == "true":  # reloader child only
            start_model_watcher()
        app.run(debug=True, host="0.0.0.0", port=5000, threaded=True)
    else:
        from waitress import serve
        start_model_watcher()
        start_backup_scheduler()
        port = int(os.environ.get("PORT", 5000))  # hosting providers choose the port
        print(f" * Serving on http://127.0.0.1:{port} (Waitress)")
        serve(app, host="0.0.0.0", port=port, threads=8)
