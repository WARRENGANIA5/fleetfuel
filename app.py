import csv
import io
import json
import os
import re
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
from model.preprocess import build_prediction_frame

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

FUEL_TYPES = ["Diesel", "Gasoline"]

REPORT_TYPES = {
    "vehicle": "Vehicle Report",
    "trip": "Trip Report",
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


def _pending_counts():
    """Sidebar badges (administrator only): both counts in one database round trip."""
    if session.get("role") != "admin":
        return {"requests": 0, "accounts": 0}
    try:
        return db.query_one("""
            SELECT (SELECT COUNT(*) FROM predictions WHERE approval_status = 'pending') AS requests,
                   (SELECT COUNT(*) FROM users WHERE status = 'pending') AS accounts
        """)
    except Exception:
        return {"requests": 0, "accounts": 0}


# ------------------------------------------------------------------
# ORGANIZATION (the study covers the Guimaras State University fleet only)
# ------------------------------------------------------------------
ORG = {
    "org_name": "Guimaras State University",
    "org_short": "GSU",
    "office_name": "General Services Office",
    "office_short": "GSO",
    "system_short": "GSU FleetFuel",
}


def get_org():
    return dict(ORG)


@app.context_processor
def inject_globals():
    pending = _pending_counts()
    return {
        "org": get_org(),
        "today": today_local().isoformat(),
        "is_admin": session.get("role") == "admin",
        "current_year": today_local().year,
        "notif_count": g.get("notif_count", 0),
        "session_avatar_url": avatar_url(session.get("profile_photo")),
        "dataset": dataset_status() if session.get("user_id") else {"demo": False, "synthetic_files": []},
        "pending_accounts": pending["accounts"],
        "pending_requests": pending["requests"],
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
    return {"count": count, "notifications": items}


# Pages don't build the notification list themselves: the bell in the top bar
# asks /api/notifications as soon as the page has loaded (and every 5 seconds),
# which saves four database round trips on every click.


@app.route("/api/notifications")
@login_required
def api_notifications():
    data = build_notifications()
    if session.get("role") == "admin":
        pending = _pending_counts()
        data.update(pending_requests=pending["requests"], pending_accounts=pending["accounts"])
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
        name = session.get("full_name")
        session.clear()
        flash(f"You have been logged out{', ' + name if name else ''}. See you next time!", "success")
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
    # The fleet-wide figures in one round trip (each query to the cloud database
    # costs about a tenth of a second).
    fleet = db.query_one("""
        SELECT (SELECT COUNT(*) FROM vehicles) AS total_vehicles,
               (SELECT COUNT(*) FROM trip_records) AS total_trips,
               (SELECT AVG(actual_fuel_consumption) FROM trip_records
                 WHERE actual_fuel_consumption IS NOT NULL) AS avg_actual,
               (SELECT AVG(predicted_fuel) FROM predictions) AS avg_predicted,
               (SELECT MAX(trip_date) FROM trip_records
                 WHERE actual_fuel_consumption IS NOT NULL) AS latest_fuel_date,
               (SELECT COUNT(*) FROM trip_records
                 WHERE actual_fuel_consumption IS NOT NULL) AS fuel_trips""")
    total_vehicles, total_trips = fleet["total_vehicles"], fleet["total_trips"]
    req = db.query_one(f"""
        SELECT COUNT(*) AS total, SUM(p.approval_status = 'pending') AS pending,
               SUM(p.approval_status = 'approved') AS approved, SUM(p.approval_status = 'rejected') AS rejected
        FROM predictions p WHERE 1=1{mine_sql}""", mine_params)
    total_predictions = int(req["total"] or 0)
    requests_summary = {k: int(req[k] or 0) for k in ("pending", "approved", "rejected")}

    avg_fuel = fleet["avg_actual"] if fleet["avg_actual"] is not None else fleet["avg_predicted"]
    avg_fuel = round(float(avg_fuel), 2) if avg_fuel is not None else 0.0

    # The 10 latest requests serve both the Recent list (first 5) and the chart.
    latest_rows = db.query_all(f"""
        SELECT p.*, v.plate_number, v.brand_model, u.full_name
        FROM predictions p
        LEFT JOIN vehicles v ON p.vehicle_id = v.id
        LEFT JOIN users u ON p.user_id = u.id
        WHERE 1=1{mine_sql}
        ORDER BY p.created_at DESC, p.id DESC LIMIT 10
    """, mine_params)
    recent_predictions_rows = latest_rows[:5]
    recent_predictions = [{
        "id": r["id"], "status": r["approval_status"],
        "url": url_for("prediction_result", prediction_id=r["id"]),
        "created_at_display": r["created_at"].strftime("%b %d, %Y %I:%M %p"),
        "plate_number": r["plate_number"] or "Manual Entry",
        "vehicle_model": r["brand_model"] or "",
        "distance_km": f"{float(r['distance_km']):.2f}",
        "fuel_type": r["fuel_type"],
        "predicted_fuel": f"{float(r['predicted_fuel']):.2f}",
        "full_name": r["full_name"] or "System",
    } for r in recent_predictions_rows]

    # Fuel consumed per month from the trip records (Monthly Report of Official
    # Travel): the last 6 calendar months up to the latest month with records
    # (the reports are often encoded months later), empty months shown as 0.
    latest = fleet["latest_fuel_date"] or today_local()
    months = []
    y, m = latest.year, latest.month
    for _ in range(6):
        months.append((y, m))
        y, m = (y, m - 1) if m > 1 else (y - 1, 12)
    months.reverse()
    first_month = date(months[0][0], months[0][1], 1)
    trend_rows = db.query_all("""
        SELECT DATE_FORMAT(trip_date, '%%Y-%%m') AS ym, SUM(actual_fuel_consumption) AS total
        FROM trip_records WHERE trip_date >= %s AND actual_fuel_consumption IS NOT NULL
        GROUP BY ym
    """, (first_month,))
    totals = {r["ym"]: float(r["total"]) for r in trend_rows}
    has_fuel_records = fleet["fuel_trips"] > 0
    fuel_trend_labels = [date(y, m, 1).strftime("%b %Y") for y, m in months] if has_fuel_records else []
    fuel_trend_values = [round(totals.get(f"{y:04d}-{m:02d}", 0.0), 2) for y, m in months] if has_fuel_records else []
    fuel_trend_months = [f"{y:04d}-{m:02d}" for y, m in months] if has_fuel_records else []  # click -> that month's trips

    # The 10 latest predictions: the predicted liters show as soon as a
    # prediction is made, the actual liters once they are recorded in
    # Prediction History (None = not recorded yet, drawn as a gap).
    avp_rows = list(reversed(latest_rows))
    avp_labels = [r["created_at"].strftime("%b %d, %I:%M %p") for r in avp_rows]
    avp_actual = [float(r["actual_fuel"]) if r["actual_fuel"] is not None else None for r in avp_rows]
    avp_predicted = [float(r["predicted_fuel"]) for r in avp_rows]
    avp_missing = sum(a is None for a in avp_actual)
    avp_urls = [url_for("prediction_result", prediction_id=r["id"]) for r in avp_rows]  # click a point -> that request

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
        "fuel_trend_months": fuel_trend_months,
        "avp_labels": avp_labels, "avp_actual": avp_actual, "avp_predicted": avp_predicted, "avp_missing": avp_missing,
        "avp_urls": avp_urls,
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
    hour = now_local().hour
    greeting = "Good morning" if hour < 12 else ("Good afternoon" if hour < 18 else "Good evening")
    return render_template("dashboard.html", active="dashboard", vehicle_usage=usage_rows,
                           greeting=greeting, today_long=now_local().strftime("%A, %B %d, %Y"), **ctx)


@app.route("/api/dashboard-data")
@login_required
def api_dashboard_data():
    ensure_model_current()
    return build_dashboard_context()


# ------------------------------------------------------------------
# PREDICTION
# ------------------------------------------------------------------
PREDICTION_FEATURE_LABELS = {"distance_km": ("Distance", "km"), "engine_power_kw": ("Engine power", "kW")}


def get_prediction_vehicles():
    """Every registered vehicle with what the model needs from its record:
    engine power (kW) and fuel type."""
    _ensure_vehicle_columns()
    return db.query_all("""
        SELECT id, plate_number, brand_model, fuel_type, engine_power_kw
        FROM vehicles ORDER BY plate_number
    """)


def validate_prediction_form(form):
    """Server-side validation (the browser checks can be bypassed). The staff
    select a vehicle and enter the trip distance; the vehicle's engine power and
    fuel type come from its record. Returns (errors, vehicle)."""
    vehicle_id = (form.get("vehicle_id") or "").strip()
    vehicle = None
    if not vehicle_id:
        return ["Please select the vehicle for the trip."], None
    if vehicle_id.isdigit():
        vehicle = next((v for v in get_prediction_vehicles() if v["id"] == int(vehicle_id)), None)
    if vehicle is None:
        return ["The selected vehicle no longer exists. Please choose another vehicle."], None
    raw = (form.get("distance_km") or "").strip()
    if not raw:
        return ["Please enter the Distance Traveled (km) of the planned trip."], vehicle
    try:
        distance = float(raw)
    except ValueError:
        return ["Distance traveled must be a number."], vehicle
    if distance != distance or not 0 < distance <= 1000:
        return ["Distance traveled must be greater than 0 and at most 1,000 km."], vehicle
    errors = []
    if vehicle["engine_power_kw"] is None or float(vehicle["engine_power_kw"]) <= 0:
        errors.append(f"{vehicle['plate_number']} has no engine power (kW) in its vehicle record yet. "
                      "Please add it in Vehicle Management first.")
    if vehicle["fuel_type"] not in FUEL_TYPES:
        errors.append(f"{vehicle['plate_number']} has no valid fuel type in its vehicle record.")
    return errors, vehicle


def prediction_warnings(values, metrics, raw_prediction=None):
    """Plain-language cautions shown with a result: inputs outside what the
    model was trained on, a fuel type it has no trips for, or a non-positive
    raw model output."""
    warnings = []
    ranges = (metrics or {}).get("feature_ranges") or {}
    for field, (label, unit) in PREDICTION_FEATURE_LABELS.items():
        if field not in ranges or values.get(field) in (None, ""):
            continue
        lo, hi = ranges[field]
        v = float(values[field])
        if v < lo or v > hi:
            warnings.append(f"{label} ({v:g} {unit}) is outside the range the model was trained on ({lo:g}–{hi:g} {unit}).")
    # The ranges of the trips of this fuel type: the diesel trips may cover far
    # fewer vehicles and distances than the gasoline trips.
    fuel_ranges = ((metrics or {}).get("ranges_by_fuel") or {}).get(str(values.get("fuel_type") or ""))
    if fuel_ranges and not warnings:
        for field, (label, unit) in PREDICTION_FEATURE_LABELS.items():
            if field not in fuel_ranges or values.get(field) in (None, ""):
                continue
            lo, hi = fuel_ranges[field]
            v = float(values[field])
            if v < lo or v > hi:
                span = f"{lo:g} {unit}" if lo == hi else f"{lo:g}–{hi:g} {unit}"
                warnings.append(f"{label} ({v:g} {unit}) is outside the {values['fuel_type']} trips the model was trained on "
                                f"({span}, {fuel_ranges.get('records', 0)} trips), so this estimate is an extrapolation.")
    seen = ((metrics or {}).get("category_values") or {}).get("fuel_type")
    fuel = str(values.get("fuel_type") or "")
    if seen and fuel and fuel not in seen:
        warnings.append(f"The model has no trip records yet for fuel type \"{fuel}\" (it was trained on "
                        f"{', '.join(seen)}), so this estimate does not reflect how it changes fuel use.")
    if raw_prediction is not None and raw_prediction <= 0:
        warnings.append("The model's estimate for this trip was at or below zero, so the minimum of 0.1 L is shown.")
    return warnings


def render_prediction_page(form=None, errors=None, status=200):
    model = get_model()
    metrics = get_metrics()
    return render_template(
        "prediction.html", active="prediction",
        model_available=model is not None, model_metrics=metrics,
        vehicles=get_prediction_vehicles(), form=form or {}, errors=errors or [],
    ), status


@app.route("/prediction", methods=["GET", "POST"])
@login_required
def prediction():
    if request.method == "GET":
        return render_prediction_page()

    model = get_model()
    if model is None:
        return render_prediction_page(request.form, ["Model unavailable. Please train the model before making predictions."])
    errors, vehicle = validate_prediction_form(request.form)
    if errors:
        return render_prediction_page(request.form, errors)

    # The system retrieves the engine power and fuel type of the selected vehicle
    # from its records and passes them to the model with the trip distance.
    values = {"distance_km": float(request.form["distance_km"]),
              "engine_power_kw": float(vehicle["engine_power_kw"]), "fuel_type": vehicle["fuel_type"]}
    try:
        raw_prediction = float(model.predict(build_prediction_frame(values))[0])
    except (ValueError, KeyError) as e:
        return render_prediction_page(request.form, [f"Invalid input values: {e}"])
    predicted_fuel = max(round(raw_prediction, 2), 0.1)

    pred_id = db.execute("""
        INSERT INTO predictions (user_id, vehicle_id, distance_km, engine_power_kw, fuel_type, predicted_fuel)
        VALUES (%s,%s,%s,%s,%s,%s)
    """, (session["user_id"], vehicle["id"], values["distance_km"], values["engine_power_kw"],
          values["fuel_type"], predicted_fuel))
    flash("Prediction saved and submitted as a fuel request for administrator approval.", "success")
    _link_actuals_quietly()  # the trip may already be encoded
    return redirect(url_for("prediction_result", prediction_id=pred_id))


@app.route("/api/prediction-options")
@login_required
def api_prediction_options():
    """Live data for the prediction form: vehicles and the model currently
    used for predictions."""
    metrics = get_metrics() or {}
    return {
        "vehicles": [{
            "id": v["id"], "label": f"{v['plate_number']} — {v['brand_model']}", "fuel": v["fuel_type"],
            "power": "" if v["engine_power_kw"] is None else f"{float(v['engine_power_kw']):g}",
        } for v in get_prediction_vehicles()],
        "model": {"available": get_model() is not None, "version": metrics.get("model_version"),
                  "r2": metrics.get("r2_score"), "mae": metrics.get("mae"), "retraining": _WATCHER["retraining"]},
    }


@app.route("/prediction/result/<int:prediction_id>")
@login_required
def prediction_result(prediction_id):
    pred = db.query_one("""
        SELECT p.*, v.plate_number, v.brand_model FROM predictions p
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
        where.append("(v.plate_number LIKE %s OR v.brand_model LIKE %s"
                     " OR (p.vehicle_id IS NULL AND 'Manual Entry' LIKE %s))")
        params += [like] * 3
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
        SELECT p.*, v.plate_number, v.brand_model, u.full_name, r.full_name AS reviewer_name,
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
            "vehicle": p["plate_number"] or "Manual Entry", "vehicle_model": p["brand_model"] or "",
            "vehicle_label": f"{p['plate_number']} ({p['brand_model']})" if p["plate_number"] else "Manual Entry",
            "fuel_type": p["fuel_type"],
            "engine_power_kw": f"{float(p['engine_power_kw']):g}" if p.get("engine_power_kw") is not None else "",
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


VEHICLE_EXTRA_COLUMNS = (
    ("engine_power_kw", "DECIMAL(6,2) NULL"),
)
# Columns from the earlier design that the study no longer collects (the
# vehicle records are plate number, model, fuel type and engine power; the
# Monthly Report of Official Travel records date, distance and fuel consumed).
# They stay in the database with their old values but are no longer required.
OPTIONAL_LEGACY_COLUMNS = {
    "vehicles": ("vehicle_type", "engine_displacement", "year_model"),
    "trip_records": ("trip_type", "departure_time", "route", "road_type", "terrain_classification",
                     "odometer_reading", "duration_minutes", "avg_speed_kmh"),
    "predictions": ("odometer_reading", "duration_minutes", "avg_speed_kmh", "trip_type", "departure_time",
                    "route", "road_type", "terrain_classification", "vehicle_type", "engine_displacement",
                    "year_model"),
}
# Engine power (kW) from published manufacturer specifications matched to each
# fleet vehicle's model and fuel type (Scope and Limitations). Filled in only
# where a vehicle has none yet; corrected values are edited in Vehicle Management.
PUBLISHED_ENGINE_POWER_KW = {
    "SFA 4712": 95, "SFA 4713": 95, "SFA 4714": 95,  # Nissan NV350 Urvan 2.5 diesel, 129 PS
    "SFA 1172": 130,  # Toyota HiAce GL Grandia 2.8 diesel (1GD-FTV), 174 hp
    "SFA 1173": 128,  # Toyota Innova 2.8 diesel (1GD-FTV), 174 PS
    "SEF 535": 51,    # Mitsubishi L300 2.5 diesel (4D56), 70 hp
    "SJC 955": 62,    # Isuzu Crosswind 2.5 diesel (4JA1-L), 85 PS
    "SGF 810": 63,    # Toyota Revo diesel (2L-II), 85 PS (to be confirmed)
    "SFA 1741": 209,  # Hino bus 7.7 L diesel (J08E), 280 hp (to be confirmed)
}
_VEHICLE_COLUMNS_READY = {"ok": False}


def _ensure_vehicle_columns():
    """One-time schema update on first use, so an existing database needs no
    manual migration: adds the vehicle columns (incl. engine power), adds engine
    power to the fuel requests, makes the columns the study no longer collects
    optional, and fills in the published engine power of the fleet vehicles."""
    if _VEHICLE_COLUMNS_READY["ok"]:
        return
    columns = db.query_all("""
        SELECT TABLE_NAME AS t, COLUMN_NAME AS c, COLUMN_TYPE AS ty, IS_NULLABLE AS n
        FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME IN ('vehicles', 'trip_records', 'predictions')
    """)
    have = {(r["t"], r["c"]): r for r in columns}
    for name, ddl in VEHICLE_EXTRA_COLUMNS:
        if ("vehicles", name) not in have:
            db.execute(f"ALTER TABLE vehicles ADD COLUMN {name} {ddl}")
    if ("predictions", "engine_power_kw") not in have:
        db.execute("ALTER TABLE predictions ADD COLUMN engine_power_kw DECIMAL(6,2) NULL")
    for table, names in OPTIONAL_LEGACY_COLUMNS.items():
        for name in names:
            col = have.get((table, name))
            if col and col["n"] == "NO":
                db.execute(f"ALTER TABLE {table} MODIFY {name} {col['ty']} NULL")
    for plate, kw in PUBLISHED_ENGINE_POWER_KW.items():
        db.execute("UPDATE vehicles SET engine_power_kw = %s WHERE plate_number = %s AND engine_power_kw IS NULL",
                   (kw, plate))
    _VEHICLE_COLUMNS_READY["ok"] = True


def query_vehicles():
    """Vehicles with how many trip records depend on each one and its last trip."""
    _ensure_vehicle_columns()
    return db.query_all("""
        SELECT v.*,
               (SELECT COUNT(*) FROM trip_records t WHERE t.vehicle_id = v.id) AS trip_count,
               (SELECT MAX(t.trip_date) FROM trip_records t WHERE t.vehicle_id = v.id) AS last_trip_date
        FROM vehicles v
        ORDER BY v.plate_number
    """)


def vehicle_record(v, num):
    """JSON-safe row used by the table, the shared modals and the live API."""
    return {
        "id": v["id"], "num": num, "plate_number": v["plate_number"], "brand_model": v["brand_model"],
        "fuel_type": v["fuel_type"],
        "engine_power_kw": f"{float(v['engine_power_kw']):g}" if v.get("engine_power_kw") is not None else "",
        "trip_count": int(v["trip_count"]),
        "last_trip_date": str(v["last_trip_date"]) if v["last_trip_date"] else "",
    }


def validate_vehicle_form(f, vehicle_id=None):
    """Vehicle records: plate number, vehicle model, fuel type and engine power (kW)."""
    errors = []
    plate = (f.get("plate_number") or "").strip().upper()
    if not plate:
        errors.append("Plate number is required.")
    elif len(plate) > 20 or not re.fullmatch(r"[A-Z0-9][A-Z0-9 \-]*", plate):
        errors.append("Plate number may only contain letters, numbers, spaces and dashes (max 20 characters).")
    elif db.query_one("SELECT id FROM vehicles WHERE plate_number = %s AND id <> %s", (plate, vehicle_id or 0)):
        errors.append(f"Plate number {plate} is already registered to another vehicle.")
    model = (f.get("brand_model") or "").strip()
    if not model or len(model) > 100:
        errors.append("Vehicle model is required (max 100 characters).")
    if f.get("fuel_type") not in FUEL_TYPES:
        errors.append("Please choose a valid fuel type.")
    try:
        power = float(f.get("engine_power_kw") or "")
        # power != power catches "nan", which passes every comparison.
        if power != power or not 0 < power <= 1000:
            raise ValueError
    except ValueError:
        errors.append("Engine power must be a number greater than 0 and at most 1,000 kW.")
    return errors


def _vehicle_values(f):
    return (f["plate_number"].strip().upper(), f["brand_model"].strip(), f["fuel_type"],
            round(float(f["engine_power_kw"]), 2))


def render_vehicles_page(reopen=None):
    """`reopen` (after a rejected save) opens the same form again with what the
    user typed, instead of losing it."""
    rows = [vehicle_record(v, i) for i, v in enumerate(query_vehicles(), 1)]
    return render_template("vehicles.html", active="vehicles", vehicles=rows, reopen=reopen)


@app.route("/vehicles")
@login_required
def vehicles():
    return render_vehicles_page()


@app.route("/api/vehicles")
@login_required
def api_vehicles():
    return {"vehicles": [vehicle_record(v, i) for i, v in enumerate(query_vehicles(), 1)]}


@app.route("/vehicles/add", methods=["POST"])
@admin_required
def add_vehicle():
    errors = validate_vehicle_form(request.form)
    if errors:
        flash("Could not add vehicle: " + " ".join(errors), "danger")
        return render_vehicles_page({"modal": "addVehicleModal", "values": request.form.to_dict()})
    try:
        _ensure_vehicle_columns()
        db.execute("""
            INSERT INTO vehicles (plate_number, brand_model, fuel_type, engine_power_kw)
            VALUES (%s,%s,%s,%s)
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
        return render_vehicles_page({"modal": "editVehicleModal", "vehicle_id": vehicle_id,
                                     "values": request.form.to_dict()})
    try:
        _ensure_vehicle_columns()
        db.execute("""
            UPDATE vehicles SET plate_number=%s, brand_model=%s, fuel_type=%s, engine_power_kw=%s
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
        # The vehicle's trip records cascade in the database schema.
        db.execute("DELETE FROM vehicles WHERE id = %s", (vehicle_id,))
        compact_ids("vehicles", "trip_records", "fuel_records", "predictions")
        flash(f"Vehicle {v['plate_number']} and its trip records were deleted.", "success")
    except Exception:
        app.logger.exception("Deleting vehicle failed")
        flash("Could not delete vehicle due to a database error. Please try again.", "danger")
    return redirect(url_for("vehicles"))


# ------------------------------------------------------------------
# TRIP RECORDS
# ------------------------------------------------------------------
TRIP_NUMERIC_LIMITS = (
    # field, label, min, max -- both are required (Monthly Report of Official Travel)
    ("distance_km", "Distance traveled", 0, 1000),
    ("actual_fuel_consumption", "Fuel consumed", 0, 1000),
)
# A trip using less or more than this many liters per 100 km is saved, but the
# user is asked to double-check it (likely an encoding error on the report).
TRIP_EFFICIENCY_WARN = (3, 60)


def trip_record(t, num):
    """JSON-safe trip row used by the table, the shared modals and the live API."""
    return {
        "id": t["id"], "num": num, "vehicle_id": t["vehicle_id"],
        "trip_date": str(t["trip_date"]), "plate_number": t["plate_number"], "brand_model": t["brand_model"],
        "distance_km": str(t["distance_km"]),
        "actual_fuel_consumption": str(t["actual_fuel_consumption"]) if t["actual_fuel_consumption"] is not None else "",
        "remarks": t["remarks"] or "",
    }


def query_trips():
    _ensure_vehicle_columns()
    rows = db.query_all("""
        SELECT t.id, t.vehicle_id, t.trip_date, t.distance_km, t.actual_fuel_consumption, t.remarks,
               v.plate_number, v.brand_model
        FROM trip_records t
        JOIN vehicles v ON t.vehicle_id = v.id
        ORDER BY t.trip_date, t.id
    """)
    # Oldest first (January to December, like the Monthly Report of Official
    # Travel); a newly added or edited trip lands in its date's place automatically.
    return [trip_record(r, i) for i, r in enumerate(rows, 1)]


def validate_trip_form(f, trip_id=None):
    """Monthly Report of Official Travel: date of travel, vehicle, distance
    traveled (km) and fuel consumed (L). Returns (errors, warnings). Errors
    block saving; warnings are shown but the trip is still saved."""
    errors, warnings = [], []
    vid = (f.get("vehicle_id") or "").strip()
    if not (vid.isdigit() and db.query_one("SELECT id FROM vehicles WHERE id = %s", (vid,))):
        errors.append("Please choose a valid vehicle.")
    try:
        trip_date = date.fromisoformat((f.get("trip_date") or "").strip())
        if not date(2000, 1, 1) <= trip_date <= today_local():
            errors.append(f"Date of travel must be between 2000-01-01 and today ({today_local().isoformat()}).")
    except ValueError:
        errors.append("Date of travel must be a valid date.")
    if len((f.get("remarks") or "").strip()) > 255:
        errors.append("Remarks must be at most 255 characters.")
    values = {}
    for field, label, lo, hi in TRIP_NUMERIC_LIMITS:
        raw = (f.get(field) or "").strip().replace(",", "")
        try:
            value = float(raw)
            # value != value catches "nan", which passes every comparison.
            if value != value or not lo < value <= hi:
                raise ValueError
            values[field] = value
        except ValueError:
            errors.append(f"{label} must be a number greater than {lo:,} and at most {hi:,}.")
    if not errors:
        per_100 = values["actual_fuel_consumption"] / values["distance_km"] * 100
        lo, hi = TRIP_EFFICIENCY_WARN
        if not lo <= per_100 <= hi:
            warnings.append(f"This trip used {per_100:.1f} L per 100 km, which is unusual. Please double-check the "
                            "distance and the fuel consumed.")
    return errors, warnings


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


def _trip_payload(f):
    return (
        f["vehicle_id"], f["trip_date"].strip(),
        round(float(f["distance_km"].strip().replace(",", "")), 2),
        round(float(f["actual_fuel_consumption"].strip().replace(",", "")), 2),
        (f.get("remarks") or "").strip() or None,
    )


def render_trips_page(reopen=None, status=200):
    vehicles_list = db.query_all("SELECT id, plate_number, brand_model FROM vehicles ORDER BY plate_number")
    return render_template(
        "trips.html", active="trips", trips=query_trips(), vehicles=vehicles_list,
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
    _ensure_vehicle_columns()
    errors, warnings = validate_trip_form(request.form)
    if errors:
        flash("Could not add trip record: " + " ".join(errors), "danger")
        return render_trips_page({"modal": "addTripModal", "values": request.form.to_dict()})
    try:
        db.execute("""
            INSERT INTO trip_records (vehicle_id, trip_date, distance_km, actual_fuel_consumption, remarks)
            VALUES (%s,%s,%s,%s,%s)
        """, _trip_payload(request.form))
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
    _ensure_vehicle_columns()
    errors, warnings = validate_trip_form(request.form, trip_id)
    if errors:
        flash("Could not update trip record: " + " ".join(errors), "danger")
        return render_trips_page({"modal": "editTripModal", "trip_id": trip_id,
                                  "values": request.form.to_dict()})
    try:
        db.execute("""
            UPDATE trip_records SET vehicle_id=%s, trip_date=%s, distance_km=%s, actual_fuel_consumption=%s, remarks=%s
            WHERE id=%s
        """, _trip_payload(request.form) + (trip_id,))
        flash("Trip record updated successfully.", "success")
        for w in warnings:
            flash(w, "warning")
        _link_actuals_quietly()
    except Exception:
        app.logger.exception("Updating trip failed")
        flash("Could not update trip record due to a database error. Please try again.", "danger")
    return redirect(url_for("trips"))


# CSV import of the Monthly Report of Official Travel (one row per trip).
IMPORT_COLUMNS = ["plate_number", "trip_date", "distance_km", "actual_fuel_consumption", "remarks"]
IMPORT_OPTIONAL = {"remarks"}
IMPORT_MAX_ROWS = 5000
IMPORT_EXAMPLE_REMARK = "example row - delete before importing"
IMPORT_NUMERIC = {"distance_km", "actual_fuel_consumption"}
# Other header spellings people type in Excel, after _header_key() normalisation.
IMPORT_HEADER_ALIASES = {
    "plate": "plate_number", "plate_no": "plate_number", "vehicle": "plate_number", "vehicle_plate": "plate_number",
    "date": "trip_date", "date_of_travel": "trip_date", "travel_date": "trip_date",
    "distance": "distance_km", "distance_traveled": "distance_km", "distance_travelled": "distance_km",
    "actual_fuel": "actual_fuel_consumption", "fuel": "actual_fuel_consumption", "fuel_consumed": "actual_fuel_consumption",
    "fuel_consumption": "actual_fuel_consumption", "liters": "actual_fuel_consumption",
    "gasoline_diesoline_consumed": "actual_fuel_consumption", "consumed": "actual_fuel_consumption",
    "remark": "remarks",
}
IMPORT_DATE_FORMATS = ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%Y/%m/%d", "%m-%d-%Y", "%d-%b-%Y", "%d-%b-%y",
                       "%b %d, %Y", "%B %d, %Y", "%d %b %Y", "%d %B %Y")


def _header_key(header):
    """'Distance (km)' -> 'distance', 'Plate Number' -> 'plate_number'."""
    key = re.sub(r"\(.*?\)", "", (header or "").replace("﻿", "")).strip().lower()
    key = re.sub(r"[^a-z0-9]+", "_", key).strip("_")
    return key if key in IMPORT_COLUMNS else IMPORT_HEADER_ALIASES.get(key, key)


def _normalize_import_row(row):
    """Accept common spreadsheet formats: many date styles and numbers with
    thousands separators."""
    out = {k: (row.get(k) or "").strip() for k in IMPORT_COLUMNS}
    d = out["trip_date"].split(" ")[0] if re.match(r"\d{4}-\d{2}-\d{2} ", out["trip_date"]) else out["trip_date"]
    for fmt in IMPORT_DATE_FORMATS:
        try:
            out["trip_date"] = datetime.strptime(d, fmt).date().isoformat()
            break
        except ValueError:
            continue
    for field in IMPORT_NUMERIC:
        out[field] = out[field].replace(",", "").replace(" ", "")
    return out


def _decode_csv(raw):
    """CSV UTF-8 from Excel, or plain 'CSV (Comma delimited)', which Excel
    saves in the Windows (ANSI) encoding."""
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return raw.decode("cp1252", errors="replace")


def _trip_key(vehicle_id, trip_date, distance, fuel):
    """Identity of a trip on the report, used to skip rows that were already imported."""
    return (int(vehicle_id), str(trip_date), round(float(distance), 2), round(float(fuel), 2))


@app.route("/trips/import-template.csv")
@admin_required
def trip_import_template():
    output = io.StringIO()
    output.write("﻿")
    writer = csv.writer(output)
    writer.writerow(IMPORT_COLUMNS)
    writer.writerow(["SFA 4714", "2026-07-01", "120", "12.0", IMPORT_EXAMPLE_REMARK])
    return Response(output.getvalue(), mimetype="text/csv; charset=utf-8",
                    headers={"Content-Disposition": "attachment; filename=trip_records_template.csv"})


@app.route("/trips/import", methods=["POST"])
@admin_required
def import_trips():
    """Bulk-import the Monthly Report of Official Travel from a CSV (e.g. saved
    from Excel). All rows are validated first; nothing is saved unless every
    row is valid."""
    _ensure_vehicle_columns()
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
    existing = {_trip_key(t["vehicle_id"], t["trip_date"], t["distance_km"], t["actual_fuel_consumption"])
                for t in db.query_all("""SELECT vehicle_id, trip_date, distance_km, actual_fuel_consumption
                                         FROM trip_records WHERE actual_fuel_consumption IS NOT NULL""")}
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
        key = _trip_key(vid, row["trip_date"], row["distance_km"], row["actual_fuel_consumption"])
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
                INSERT INTO trip_records (vehicle_id, trip_date, distance_km, actual_fuel_consumption, remarks)
                VALUES (%s,%s,%s,%s,%s)
            """, payloads)
        conn.commit()
    except Exception:
        conn.rollback()
        app.logger.exception("Trip import failed")
        flash("Nothing was imported because of a database error. Please try again.", "danger")
        return redirect(url_for("trips"))
    msg = f"Imported {len(payloads)} trip record(s). The model retrains automatically."
    if skipped:
        msg += " " + "; ".join(skipped).capitalize() + "."
    if warnings_count:
        msg += f" {warnings_count} row(s) have an unusual fuel use per 100 km; please review them."
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
        # The old auto-logged fuel record of this trip (from the earlier design)
        # describes the same trip, so it goes too. A database created from the
        # current schema has no fuel_records table.
        try:
            db.execute("DELETE FROM fuel_records WHERE trip_record_id = %s", (trip_id,))
        except Exception:
            pass
        # A fuel request whose actual fuel came from this trip loses it (and may
        # be matched again to another trip below); manual entries are kept.
        _ensure_prediction_link_columns()
        db.execute("""UPDATE predictions SET actual_fuel = NULL, trip_record_id = NULL, actual_source = NULL
                      WHERE trip_record_id = %s AND actual_source = 'trip'""", (trip_id,))
        db.execute("UPDATE predictions SET trip_record_id = NULL WHERE trip_record_id = %s", (trip_id,))
        db.execute("DELETE FROM trip_records WHERE id = %s", (trip_id,))
        compact_ids("trip_records", "fuel_records")
        flash("Trip record deleted successfully.", "success")
        _link_actuals_quietly()
    except Exception:
        app.logger.exception("Deleting trip failed")
        flash("Could not delete trip record due to a database error. Please try again.", "danger")
    return redirect(url_for("trips"))


# ------------------------------------------------------------------
# MODEL PERFORMANCE
# ------------------------------------------------------------------
_MODEL_CHARTS_CACHE = {"key": None, "data": None}
_RETRAIN_LOCK = threading.Lock()
_LAST_DATA_CHECK = {"at": 0.0}

# Every value the model trains on from a trip and its vehicle, so adding,
# editing or deleting a trip record (or editing a vehicle) changes the fingerprint.
_SYSTEM_DATA_FINGERPRINT_SQL = """
    SELECT COUNT(*) AS n,
           COALESCE(SUM(CRC32(CONCAT_WS('|', t.id, t.trip_date, t.distance_km, t.actual_fuel_consumption,
               v.plate_number, v.fuel_type, v.engine_power_kw))), 0) AS crc
    FROM trip_records t JOIN vehicles v ON t.vehicle_id = v.id
    WHERE t.actual_fuel_consumption IS NOT NULL
"""


def load_system_trip_records():
    """The trips in the system (Monthly Report of Official Travel: date,
    plate number, distance, fuel consumed) merged with the vehicle records
    (engine power and fuel type) using the plate number."""
    from model.preprocess import merge_trips_and_vehicles
    _ensure_vehicle_columns()
    trips = pd.DataFrame(db.query_all("""
        SELECT t.trip_date, v.plate_number, t.distance_km, t.actual_fuel_consumption
        FROM trip_records t JOIN vehicles v ON t.vehicle_id = v.id
        WHERE t.actual_fuel_consumption IS NOT NULL
        ORDER BY t.trip_date, t.id
    """))
    if trips.empty:
        return trips
    vehicles = pd.DataFrame(db.query_all("SELECT plate_number, brand_model, fuel_type, engine_power_kw FROM vehicles"))
    df = merge_trips_and_vehicles(trips, vehicles)
    df["trip_date"] = df["trip_date"].astype(str)
    for col in ("distance_km", "actual_fuel_consumption", "engine_power_kw"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def load_training_frame():
    """Local trips (historical CSV + the trips in the system) merged with the
    supplementary dataset."""
    from model.preprocess import load_and_merge_datasets
    return load_and_merge_datasets(app.config["HISTORICAL_DATA_PATH"],
                                   app.config["SUPPLEMENTARY_DATA_PATH"],
                                   extra_df=load_system_trip_records())


def current_data_fingerprint():
    """Changes whenever the CSV datasets or any trip/vehicle data the model
    trains on changes."""
    _ensure_vehicle_columns()
    fp = db.query_one(_SYSTEM_DATA_FINGERPRINT_SQL)
    mtimes = [os.path.getmtime(app.config[k]) for k in ("HISTORICAL_DATA_PATH", "SUPPLEMENTARY_DATA_PATH")]
    return f"{mtimes[0]:.0f}-{mtimes[1]:.0f}-{int(fp['n'])}-{int(fp['crc'])}"


def retrain_model(log=None):
    """Retrain on the local trips + supplementary dataset and save model + metrics."""
    from model.train_model import train_and_save
    from model.preprocess import load_and_merge_datasets, supplementary_info
    fingerprint = current_data_fingerprint()
    system_records = load_system_trip_records()
    info = supplementary_info(app.config["SUPPLEMENTARY_DATA_PATH"])
    extra = {"data_fingerprint": fingerprint, "system_records": int(len(system_records)),
             "supplementary_kind": info["kind"]}
    df = load_and_merge_datasets(app.config["HISTORICAL_DATA_PATH"],
                                 app.config["SUPPLEMENTARY_DATA_PATH"], extra_df=system_records)
    return train_and_save(df, extra_metrics=extra, log=log or (lambda *a, **k: None))


_WATCHER = {"running": False, "retraining": False, "last_check": None}
_WATCHER_WAKE = threading.Event()
WATCHER_INTERVAL_SECONDS = 3
RETRAIN_RETRY_SECONDS = 60  # wait this long before retrying a retrain that failed

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
        saved, outdated = None, False
        if os.path.exists(app.config["METRICS_PATH"]) and os.path.exists(app.config["MODEL_PATH"]):
            with open(app.config["METRICS_PATH"]) as f:
                saved_metrics = json.load(f)
            saved = saved_metrics.get("data_fingerprint")
            # Trained by an earlier version of the training code (before the
            # Distance x Engine Power equation and cross-validated MAE/RMSE): train again once.
            outdated = saved_metrics.get("centering") is None or saved_metrics.get("cv_mean_rmse") is None
        _WATCHER["last_check"] = now_local().isoformat(timespec="seconds")
        if saved != fingerprint or outdated:
            # After a failed retrain, try the same data again only after a pause,
            # instead of every few seconds (which would keep the server PC busy).
            failed = _WATCHER.get("failed")
            if failed and failed["fingerprint"] == fingerprint and time.time() - failed["at"] < RETRAIN_RETRY_SECONDS:
                return
            app.logger.info("Training data changed; retraining model automatically...")
            _WATCHER["retraining"] = True
            try:
                retrain_model()
                _WATCHER["failed"] = None
            except Exception:
                _WATCHER["failed"] = {"fingerprint": fingerprint, "at": time.time()}
                raise
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
    from model.preprocess import FEATURE_COLUMNS, MODEL_TERMS, TARGET_COLUMN, clean_data

    pipeline = get_model()
    metrics = get_metrics()
    if pipeline is None or metrics is None or metrics.get("equation_terms") is None:
        return None
    key = metrics.get("model_version")
    if _MODEL_CHARTS_CACHE["key"] == key:
        return _MODEL_CHARTS_CACHE["data"]

    df = clean_data(load_training_frame())
    X_train, X_test, y_train, y_test = train_test_split(
        df[FEATURE_COLUMNS], df[TARGET_COLUMN], test_size=0.2, random_state=42)
    y_pred = pipeline.predict(X_test)
    actual = [round(float(v), 2) for v in y_test.values]
    predicted = [round(float(v), 2) for v in y_pred]
    residuals = np.asarray(actual) - np.asarray(predicted)
    lo, hi = min(actual + predicted), max(actual + predicted)

    # Residual histogram (normality check) on "nice" fixed-width bins centred on 0.
    spread = float(np.abs(residuals).max()) or 1.0
    width = next(w for w in (0.1, 0.2, 0.25, 0.5, 1, 2, 2.5, 5, 10, 25, 50) if 2 * spread / w <= 24)
    half = np.ceil(spread / width) * width
    edges = np.arange(-half, half + width * 1.001, width)
    counts, edges = np.histogram(residuals, bins=edges)
    fmt = (lambda v: f"{v:g}")

    # Correlation heatmap of the equation's terms and the fuel consumed. A term
    # with the same value in every record has no defined correlation; it is
    # left out instead of showing a misleading 0.00.
    terms = pipeline.named_steps["encoder"].transform(df[FEATURE_COLUMNS]).assign(**{TARGET_COLUMN: df[TARGET_COLUMN].astype(float)})
    corr_cols = [c for c in MODEL_TERMS if terms[c].nunique() > 1] + [TARGET_COLUMN]
    corr = terms[corr_cols].corr().round(2).fillna(0)

    data = {
        "avp_points": [{"x": a, "y": p} for a, p in zip(actual, predicted)],
        "avp_line": [{"x": round(lo, 2), "y": round(lo, 2)}, {"x": round(hi, 2), "y": round(hi, 2)}],
        "residual_points": [{"x": p, "y": round(a - p, 2)} for a, p in zip(actual, predicted)],
        "residual_range": [round(min(predicted), 2), round(max(predicted), 2)],
        "resid_labels": [f"{fmt(round(edges[i], 2))} to {fmt(round(edges[i + 1], 2))}" for i in range(len(counts))],
        "resid_counts": [int(c) for c in counts],
        "resid_stats": {
            "records": int(len(residuals)),
            "mean": round(float(residuals.mean()), 3),
            "std": round(float(residuals.std()), 3),
            "min": round(float(residuals.min()), 2),
            "max": round(float(residuals.max()), 2),
            "within_1": round(float((np.abs(residuals) <= 1).mean() * 100), 1),
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
    (notebooks/fuel_consumption_linear_regression.ipynb), as the three CSV files
    of Chapter III (How the Project Will Work):

    * trip_records - the Monthly Report of Official Travel: date of travel,
      plate number, distance traveled and fuel consumed of every local trip
      (historical CSV + the trips in the system);
    * vehicle_records - plate number, vehicle model, fuel type and engine power;
    * supplementary_data - the supplementary dataset, unchanged."""
    from model.preprocess import TRIP_COLUMNS, VEHICLE_COLUMNS
    if name == "supplementary_data":
        with open(app.config["SUPPLEMENTARY_DATA_PATH"], "rb") as f:
            body = f.read()
    elif name == "trip_records":
        historical = pd.read_csv(app.config["HISTORICAL_DATA_PATH"])
        system = load_system_trip_records()
        frames = [f.reindex(columns=TRIP_COLUMNS) for f in (historical, system) if f is not None and not f.empty]
        data = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=TRIP_COLUMNS)
        body = data.to_csv(index=False).encode("utf-8")
    elif name == "vehicle_records":
        _ensure_vehicle_columns()
        data = pd.DataFrame(db.query_all("SELECT plate_number, brand_model, fuel_type, engine_power_kw FROM vehicles "
                                         "ORDER BY plate_number"), columns=VEHICLE_COLUMNS)
        body = data.to_csv(index=False).encode("utf-8")
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
    "trip": ["date_from", "date_to", "vehicle_id"],
    "prediction": ["date_from", "date_to", "vehicle_id", "fuel_type"],
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
    return f, errors


def _num(v, places=2):
    return f"{float(v):,.{places}f}"


def build_report(f):
    """Returns (columns, rows, totals) for validated filters `f`. All cell
    values are strings so the same data serves HTML, JSON and CSV."""
    from model.preprocess import TERM_LABELS
    report_type = f["type"]
    date_from, date_to = f.get("date_from"), f.get("date_to")
    vehicle_id, fuel_type = f.get("vehicle_id"), f.get("fuel_type")
    dash = "—"

    if report_type == "vehicle":
        # The vehicle records: plate number, vehicle model, fuel type and engine power.
        columns = ["No.", "Plate Number", "Vehicle Model", "Fuel Type", "Engine Power (kW)", "Trips"]
        where, params = ["1=1"], []
        if vehicle_id:
            where.append("v.id = %s"); params.append(vehicle_id)
        if fuel_type:
            where.append("v.fuel_type = %s"); params.append(fuel_type)
        _ensure_vehicle_columns()
        rows_db = db.query_all(f"""
            SELECT v.*, (SELECT COUNT(*) FROM trip_records t WHERE t.vehicle_id = v.id) AS trip_count
            FROM vehicles v WHERE {' AND '.join(where)} ORDER BY v.plate_number""", params)
        rows = [{"No.": str(i), "Plate Number": r["plate_number"], "Vehicle Model": r["brand_model"],
                 "Fuel Type": r["fuel_type"],
                 "Engine Power (kW)": f"{float(r['engine_power_kw']):g}" if r["engine_power_kw"] is not None else dash,
                 "Trips": str(r["trip_count"])} for i, r in enumerate(rows_db, 1)]
        totals = {"Vehicles": str(len(rows))}

    elif report_type == "trip":
        # The Monthly Report of Official Travel: date, vehicle, distance and fuel consumed.
        columns = ["No.", "Date of Travel", "Vehicle", "Distance (km)", "Fuel Consumed (L)", "L/100 km"]
        where, params = ["1=1"], []
        if date_from: where.append("t.trip_date >= %s"); params.append(date_from)
        if date_to: where.append("t.trip_date <= %s"); params.append(date_to)
        if vehicle_id: where.append("t.vehicle_id = %s"); params.append(vehicle_id)
        rows_db = db.query_all(f"""
            SELECT t.*, v.plate_number FROM trip_records t JOIN vehicles v ON t.vehicle_id=v.id
            WHERE {' AND '.join(where)} ORDER BY t.trip_date, t.id
        """, params)
        rows = []
        for i, r in enumerate(rows_db, 1):
            fuel = r["actual_fuel_consumption"]
            per_100 = float(fuel) / float(r["distance_km"]) * 100 if fuel is not None and float(r["distance_km"]) else None
            rows.append({"No.": str(i), "Date of Travel": str(r["trip_date"]), "Vehicle": r["plate_number"],
                         "Distance (km)": str(r["distance_km"]),
                         "Fuel Consumed (L)": str(fuel) if fuel is not None else dash,
                         "L/100 km": f"{per_100:.2f}" if per_100 is not None else dash})
        fuel_vals = [float(r["actual_fuel_consumption"]) for r in rows_db if r["actual_fuel_consumption"] is not None]
        totals = {"Trips": str(len(rows)),
                  "Total Distance": _num(sum(float(r["distance_km"]) for r in rows_db)) + " km",
                  "Total Fuel Consumed": _num(sum(fuel_vals)) + " L",
                  "Avg Fuel / Trip": (_num(sum(fuel_vals) / len(fuel_vals)) + " L") if fuel_vals else dash}

    elif report_type == "prediction":
        columns = ["No.", "Date", "Vehicle", "Distance (km)", "Engine Power (kW)", "Fuel Type", "Predicted Fuel (L)",
                   "Actual Fuel (L)", "Difference (L)"]
        where, params = ["1=1"], []
        if date_from: where.append("DATE(p.created_at) >= %s"); params.append(date_from)
        if date_to: where.append("DATE(p.created_at) <= %s"); params.append(date_to)
        if vehicle_id: where.append("p.vehicle_id = %s"); params.append(vehicle_id)
        if fuel_type: where.append("p.fuel_type = %s"); params.append(fuel_type)
        _ensure_vehicle_columns()
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
                         "Distance (km)": str(r["distance_km"]),
                         "Engine Power (kW)": f"{float(r['engine_power_kw']):g}" if r.get("engine_power_kw") is not None else dash,
                         "Fuel Type": r["fuel_type"],
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
                ("Model Version", m.get("model_version")),
                ("Train-Test Split", "80% training / 20% testing"),
                ("R² Score", m.get("r2_score")), ("MAE (L)", m.get("mae")), ("RMSE (L)", m.get("rmse")),
                ("Cross-Validation Folds", m.get("cv_folds")), ("CV Mean R²", m.get("cv_mean_r2")),
                ("CV Std. Deviation", m.get("cv_std_r2")),
                ("CV Mean MAE (L)", m.get("cv_mean_mae")), ("CV Mean RMSE (L)", m.get("cv_mean_rmse")),
                ("Training Set Size", m.get("train_size")),
                ("Testing Set Size", m.get("test_size")), ("Total Dataset Records", m.get("total_records")),
                ("Local Trip Records Used", (m.get("data_sources") or {}).get("system")),
                ("Supplementary Records Used", (m.get("data_sources") or {}).get("supplementary")),
                ("Trained At", m.get("trained_at_display")), ("Model Status", (m.get("status") or "").capitalize()),
            ):
                if value is not None:
                    rows.append({"Metric": label, "Value": str(value)})
            if m.get("coefficients"):
                centering = m.get("centering") or {}
                for name, value in (("mean distance", centering.get("distance_km")), ("mean engine power", centering.get("engine_power_kw"))):
                    if value is not None:
                        rows.append({"Metric": f"Centering: {name}", "Value": str(value)})
                rows.append({"Metric": "Intercept (β₀), centered", "Value": str(m.get("intercept"))})
                for i, term in enumerate(m.get("equation_terms") or [], 1):
                    rows.append({"Metric": f"β{i} {TERM_LABELS.get(term, term)}, centered", "Value": str(m["coefficients"].get(term))})
                if m.get("raw_coefficients"):
                    rows.append({"Metric": "Intercept (β₀), original units", "Value": str(m.get("raw_intercept"))})
                    for i, term in enumerate(m.get("equation_terms") or [], 1):
                        rows.append({"Metric": f"β{i} {TERM_LABELS.get(term, term)}, original units",
                                     "Value": str(m["raw_coefficients"].get(term))})
            for term, value in (m.get("vif") or {}).items():
                rows.append({"Metric": f"VIF {TERM_LABELS.get(term, term)}", "Value": "—" if value is None else str(value)})
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
        vehicles=vehicles_list, generated=generated, report=report,
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
