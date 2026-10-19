import json
import os
import re
import threading
import time
from datetime import date, datetime, timedelta
from functools import wraps

import joblib
import numpy as np
import pandas as pd
from flask import (Flask, Response, flash, g, redirect, render_template,
                    request, session, url_for)
from flask_wtf import CSRFProtect
from werkzeug.security import check_password_hash, generate_password_hash

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

FUEL_TYPES = ["Diesel", "Gasoline"]

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


def format_time(value):
    if isinstance(value, timedelta):
        total = int(value.total_seconds())
        return f"{total // 3600:02d}:{(total % 3600) // 60:02d}"
    return value


def password_signature(password_hash):
    """Short fingerprint of the stored hash, kept in the session to notice password changes."""
    import hashlib
    return hashlib.sha256((password_hash or "").encode()).hexdigest()[:16]


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
        # Re-check the account on every request: a deleted
        # account is signed out right away, and name/role/photo changes made
        # elsewhere show up without logging in again.
        user = db.get("users", session["user_id"])
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
        session["role"] = effective_role(user)
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


# The one administrator account (GSO). Only this username, with its own
# password, opens the administrator pages; every other account is staff, and
# this account cannot be demoted or given a new password from the
# system.
ADMIN_ACCOUNT = "admin1114"


def effective_role(user):
    return "admin" if user["role"] == "admin" and user["username"] == ADMIN_ACCOUNT else "staff"


def admin_required(view):
    """Pages and actions for the administrator (GSO) only: approving fuel
    requests, user accounts, vehicles and model monitoring (login is
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
    """Sidebar badges (administrator only)."""
    if session.get("role") != "admin":
        return {"requests": 0, "accounts": 0}
    try:
        return {"requests": len(db.find("predictions", approval_status="pending")),
                "accounts": len(db.find("users", status="pending"))}
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
        "pending_accounts": pending["accounts"],
        "pending_requests": pending["requests"],
    }

NOTIF_KEY_RE = re.compile(r"[a-z]+:\d+(:[a-z0-9]+)?")


def build_notifications(limit=8):
    """Bell notifications for the current user, minus the ones they removed.

    * administrators: sign-ups and fuel requests waiting for approval (actionable);
    * staff: approvals / rejections of their own fuel requests, counted as
      new until they open the bell.
    Each item has a `key`; a removed key stays hidden, but a new event gets a
    new key (e.g. an approved request that is later rejected shows up again)."""
    uid, is_admin = session.get("user_id"), session.get("role") == "admin"
    removed = {r["notif_key"] for r in db.find("notification_dismissals", user_id=uid)}
    items, count = [], 0
    newest = lambda rows, field: sorted(rows, key=lambda r: (r[field] or datetime.min, r["id"]), reverse=True)
    if is_admin:
        users_by_id = {u["id"]: u for u in db.records("users")}
        vehicles_by_id = {v["id"]: v for v in db.records("vehicles")}
        signups = [r for r in newest(db.find("users", status="pending"), "created_at")
                   if f"account:{r['id']}" not in removed]
        count += len(signups)
        for r in signups[:limit]:
            items.append({"kind": "account", "id": r["id"], "key": f"account:{r['id']}", "icon": "fa-user-plus",
                          "text": f"New sign-up: {r['full_name']}",
                          "sub": f"{r['username']} · waiting for approval",
                          "time": r["created_at"].strftime("%b %d, %I:%M %p"),
                          "url": url_for("users"), "new": True})
        pending = [r for r in newest(db.find("predictions", approval_status="pending"), "created_at")
                   if f"request:{r['id']}" not in removed]
        count += len(pending)
        for r in pending[:limit]:
            v, u = vehicles_by_id.get(r["vehicle_id"]), users_by_id.get(r["user_id"])
            items.append({"kind": "request", "id": r["id"], "key": f"request:{r['id']}", "icon": "fa-file-signature",
                          "text": f"Fuel request #{r['id']} needs approval",
                          "sub": f"{v['plate_number'] if v else 'Vehicle deleted'} · {float(r['predicted_fuel']):.2f} L predicted · {u['full_name'] if u else 'Staff'}",
                          "time": r["created_at"].strftime("%b %d, %I:%M %p"),
                          "url": url_for("prediction_result", prediction_id=r["id"]), "new": True})
    else:
        seen = (db.get("users", uid) or {}).get("notif_seen_at")
        since = now_local() - timedelta(days=14)
        vehicles_by_id = {v["id"]: v for v in db.records("vehicles")}
        decided = [p for p in db.find("predictions", user_id=uid)
                   if p["approval_status"] != "pending" and p["reviewed_at"] is not None and p["reviewed_at"] >= since]
        decided = [r for r in newest(decided, "reviewed_at")
                   if f"decision:{r['id']}:{r['approval_status']}" not in removed][:limit]
        for r in decided:
            is_new = seen is None or r["reviewed_at"] > seen
            count += 1 if is_new else 0
            approved = r["approval_status"] == "approved"
            v = vehicles_by_id.get(r["vehicle_id"])
            plate = v["plate_number"] if v else "Vehicle deleted"
            items.append({"kind": "decision", "id": r["id"], "key": f"decision:{r['id']}:{r['approval_status']}",
                          "icon": "fa-circle-check" if approved else "fa-circle-xmark",
                          "text": f"Fuel request #{r['id']} {'approved' if approved else 'rejected'}",
                          "sub": (f"{plate} · {float(r['approved_fuel']):.2f} L released"
                                  if approved and r["approved_fuel"] is not None else plate),
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
    uid = session["user_id"]
    for k in keys:
        doc_id = f"{uid}_{k.replace(':', '-')}"
        if not db.get("notification_dismissals", doc_id):
            db.put("notification_dismissals", doc_id, {"user_id": uid, "notif_key": k, "dismissed_at": now_local()})
    # Keys of events long past are never shown again; keep the collection small.
    cutoff = now_local() - timedelta(days=90)
    for r in db.find("notification_dismissals", user_id=uid):
        if r["dismissed_at"] and r["dismissed_at"] < cutoff:
            db.delete("notification_dismissals", r["id"])
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
    db.update("users", session["user_id"], notif_seen_at=now_local())
    return {"ok": True}


# ------------------------------------------------------------------
# AUTH
# ------------------------------------------------------------------
@app.route("/")
def index():
    return redirect(url_for("dashboard") if session.get("user_id") else url_for("login"))


# Default passwords of earlier installations; anyone who
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


def start_session(user):
    """Signs the account in on this browser (after a correct password, or
    automatically once an administrator approves a sign-up made here)."""
    session.clear()
    session.permanent = True  # honour PERMANENT_SESSION_LIFETIME (8 hours)
    session["user_id"] = user["id"]
    session["username"] = user["username"]
    session["full_name"] = user["full_name"]
    session["role"] = effective_role(user)
    session["pw_sig"] = password_signature(user["password_hash"])


def wait_for_approval(user):
    """Remember, on this browser only, the pending account whose password was
    just given: the waiting page then signs it in by itself once approved."""
    session.clear()
    session.permanent = True
    session["pending_user_id"] = user["id"]
    session["pending_pw_sig"] = password_signature(user["password_hash"])
    return redirect(url_for("signup_pending"))


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

        user = find_user(username)
        if user and check_password_hash(user["password_hash"], password):
            _LOGIN_FAILURES.pop(key, None)
            if user["status"] == "pending":
                return wait_for_approval(user)
            if user["status"] != "active":
                flash("Your account has been deactivated. Please contact the administrator.", "danger")
                return render_template("login.html")
            start_session(user)
            flash(f"Welcome back, {user['full_name']}.", "success")
            if password in DEFAULT_PASSWORDS and user["username"] != ADMIN_ACCOUNT:
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


def find_user(username):
    """Account with this username (exact match, like the login form)."""
    return next((u for u in db.records("users") if u["username"] == username), None)


def username_taken(username, except_id=None):
    name = (username or "").strip().lower()
    return any(u["username"].lower() == name and u["id"] != except_id for u in db.records("users"))


def email_taken(email, except_id=None):
    email = (email or "").strip().lower()
    return any((u["email"] or "").lower() == email and u["id"] != except_id for u in db.records("users"))


def signup_field_problem(field, value):
    """Live check of one sign-up field (the same rules run again on submit). None when valid."""
    value = (value or "").strip()
    if field == "username":
        if not USERNAME_RE.fullmatch(value):
            return "3-50 characters: letters, numbers, dot, dash or underscore."
        if username_taken(value):
            return f"Username {value} is already taken."
    elif field == "email":
        if not value:
            return "Email is required."
        if len(value) > 120 or not EMAIL_RE.fullmatch(value):
            return "Please enter a valid email address."
        if email_taken(value):
            return "That email address is already used by another account."
    return None


@app.route("/api/signup/check")
def api_signup_check():
    """Checked while the user types on the sign-up page."""
    field = request.args.get("field", "")
    if field not in ("username", "email"):
        return {"error": "invalid_field"}, 400
    problem = signup_field_problem(field, request.args.get("value", ""))
    return {"ok": problem is None, "message": problem or ("Username is available." if field == "username" else "")}


@app.route("/signup", methods=["GET", "POST"])
def signup():
    """Self-registration for GSO and motorpool staff. New accounts are
    created as 'pending' staff accounts; the browser that signed up waits on
    the approval page and is signed in automatically once an administrator
    approves the account under User Accounts."""
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
        errors, full_name, email = validate_user_form(dict(f, role="staff"))
        if not (f.get("email") or "").strip():
            errors.insert(0, "Email is required.")
        problem = password_problem(f.get("password", ""), f.get("username", ""))
        if problem:
            errors.append(problem)
        elif f.get("password") != f.get("confirm_password"):
            errors.append("Password and confirmation do not match.")
        if len(recent) >= SIGNUP_LIMIT_PER_HOUR:
            errors = ["Too many sign-ups from this computer. Please try again later."]
        if errors:
            for e in errors:
                flash(e, "danger")
            return render_template("signup.html", form=form)
        user_id = db.insert("users", {"username": f["username"].strip(), "password_hash": generate_password_hash(f["password"]),
                                      "full_name": full_name, "email": email or None, "role": "staff", "status": "pending"})
        with _LOGIN_LOCK:
            _SIGNUPS.setdefault(ip, []).append(time.time())
        return wait_for_approval(db.get("users", user_id))
    return render_template("signup.html", form=form)


def _pending_account():
    """The account this browser waits on and its state: 'pending', 'approved',
    'inactive', or 'gone' (rejected, or its password was reset meanwhile)."""
    uid = session.get("pending_user_id")
    if not uid:
        return None, None
    user = db.get("users", uid)
    if not user or password_signature(user["password_hash"]) != session.get("pending_pw_sig"):
        return None, "gone"
    return user, {"active": "approved"}.get(user["status"], user["status"])


def _end_wait(state):
    session.clear()
    flash("Your sign-up request was not approved. Please contact the administrator." if state == "gone"
          else "Your account has been deactivated. Please contact the administrator.", "danger")


@app.route("/signup/pending")
def signup_pending():
    if session.get("user_id"):
        return redirect(url_for("dashboard"))
    user, state = _pending_account()
    if state is None:
        return redirect(url_for("login"))
    if state == "approved":
        start_session(user)
        flash(f"Your account was approved. Welcome, {user['full_name']}!", "success")
        return redirect(url_for("dashboard"))
    if state != "pending":
        _end_wait(state)
        return redirect(url_for("login"))
    return render_template("signup_pending.html", user=user)


@app.route("/api/signup/status")
def api_signup_status():
    """Polled by the waiting page every few seconds. Once the administrator
    approves the account, this browser is signed in right away."""
    user, state = _pending_account()
    if state is None:
        return {"state": "none", "redirect": url_for("login")}
    if state == "approved":
        start_session(user)
        flash(f"Your account was approved. Welcome, {user['full_name']}!", "success")
        return {"state": "approved", "redirect": url_for("dashboard")}
    if state != "pending":
        _end_wait(state)
        return {"state": state, "redirect": url_for("login")}
    return {"state": "pending"}


@app.route("/signup/cancel", methods=["POST"])
def signup_cancel():
    """Stop waiting on this browser (the request stays for the administrator)."""
    session.pop("pending_user_id", None)
    session.pop("pending_pw_sig", None)
    flash("You can log in once the administrator approves your account.", "info")
    return redirect(url_for("login"))


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
    vehicles_by_id = {v["id"]: v for v in db.records("vehicles")}
    users_by_id = {u["id"]: u for u in db.records("users")}
    trips = db.records("trip_records")
    fuel_trips = [t for t in trips if t["actual_fuel_consumption"] is not None]
    all_predictions = db.records("predictions")
    # Scope of the fuel-request figures: everyone's for the admin, own for staff.
    scoped = all_predictions if is_admin else [p for p in all_predictions if p["user_id"] == session.get("user_id")]
    total_vehicles, total_trips = len(vehicles_by_id), len(trips)
    total_predictions = len(scoped)
    requests_summary = {k: sum(p["approval_status"] == k for p in scoped) for k in ("pending", "approved", "rejected")}

    if fuel_trips:
        avg_fuel = sum(float(t["actual_fuel_consumption"]) for t in fuel_trips) / len(fuel_trips)
    elif all_predictions:
        avg_fuel = sum(float(p["predicted_fuel"]) for p in all_predictions) / len(all_predictions)
    else:
        avg_fuel = None
    avg_fuel = round(float(avg_fuel), 2) if avg_fuel is not None else 0.0

    # The 10 latest requests serve both the Recent list (first 5) and the chart.
    latest_rows = sorted(scoped, key=lambda p: (p["created_at"], p["id"]), reverse=True)[:10]
    for r in latest_rows:
        v, u = vehicles_by_id.get(r["vehicle_id"]), users_by_id.get(r["user_id"])
        r.update(plate_number=v["plate_number"] if v else None, brand_model=v["brand_model"] if v else None,
                 full_name=u["full_name"] if u else None)
    recent_predictions_rows = latest_rows[:5]
    recent_predictions = [{
        "id": r["id"], "status": r["approval_status"],
        "url": url_for("prediction_result", prediction_id=r["id"]),
        "created_at_display": r["created_at"].strftime("%b %d, %Y %I:%M %p"),
        "plate_number": r["plate_number"] or "Vehicle deleted",
        "vehicle_model": r["brand_model"] or "",
        "distance_km": f"{float(r['distance_km']):.2f}",
        "engine_power_kw": f"{float(r['engine_power_kw']):g} kW" if r["engine_power_kw"] is not None else "—",
        "fuel_type": r["fuel_type"],
        "predicted_fuel": f"{float(r['predicted_fuel']):.2f}",
        "full_name": r["full_name"] or "System",
    } for r in recent_predictions_rows]

    # Fuel consumed per month from the trip records (Monthly Report of Official
    # Travel): the last 6 calendar months up to the latest month with records
    # (the reports are often encoded months later), empty months shown as 0.
    latest = max((t["trip_date"] for t in fuel_trips), default=None) or today_local()
    months = []
    y, m = latest.year, latest.month
    for _ in range(6):
        months.append((y, m))
        y, m = (y, m - 1) if m > 1 else (y - 1, 12)
    months.reverse()
    totals = {}
    for t in fuel_trips:
        ym = t["trip_date"].strftime("%Y-%m")
        totals[ym] = totals.get(ym, 0.0) + float(t["actual_fuel_consumption"])
    has_fuel_records = bool(fuel_trips)
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

    model_summary = get_metrics() if is_admin else None   # model monitoring is the GSO's

    return {
        "stats": {"total_vehicles": total_vehicles, "total_trips": total_trips,
                  "total_predictions": total_predictions, "avg_fuel": avg_fuel, **requests_summary},
        "recent_predictions": recent_predictions,
        "fuel_trend_labels": fuel_trend_labels, "fuel_trend_values": fuel_trend_values,
        "fuel_trend_months": fuel_trend_months,
        "avp_labels": avp_labels, "avp_actual": avp_actual, "avp_predicted": avp_predicted, "avp_missing": avp_missing,
        "avp_urls": avp_urls,
        "model_summary": model_summary,
    }


@app.route("/dashboard")
@login_required
def dashboard():
    ensure_model_current()
    ctx = build_dashboard_context()
    hour = now_local().hour
    greeting = "Good morning" if hour < 12 else ("Good afternoon" if hour < 18 else "Good evening")
    return render_template("dashboard.html", active="dashboard",
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
    return sorted(db.records("vehicles"), key=lambda v: v["plate_number"])


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
        errors.append(f"{vehicle['plate_number']} has no engine power (kW) in its vehicle record yet. " +
                      ("Please add it in Vehicle Management first." if session.get("role") == "admin"
                       else "Please ask the administrator to add it."))
    if vehicle["fuel_type"] not in FUEL_TYPES:
        errors.append(f"{vehicle['plate_number']} has no valid fuel type in its vehicle record." +
                      ("" if session.get("role") == "admin" else " Please ask the administrator to correct it."))
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

    pred_id = db.insert("predictions", {
        "user_id": session["user_id"], "vehicle_id": vehicle["id"], "distance_km": values["distance_km"],
        "engine_power_kw": values["engine_power_kw"], "fuel_type": values["fuel_type"],
        "predicted_fuel": predicted_fuel})
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
    pred = db.get("predictions", prediction_id)
    if pred:
        v = db.get("vehicles", pred["vehicle_id"])
        pred.update(plate_number=v["plate_number"] if v else None, brand_model=v["brand_model"] if v else None)
    if not pred or not can_see_prediction(pred):
        flash("Prediction record not found.", "danger")
        return redirect(url_for("prediction"))
    clamped = float(pred["predicted_fuel"]) <= 0.1  # model output was at/below the 0.1 L floor
    warnings = prediction_warnings(pred, get_metrics(), raw_prediction=0 if clamped else None)
    if pred["vehicle_id"] is not None and not db.find("trip_records", vehicle_id=pred["vehicle_id"]):
        # Scope and Limitations: only the vehicles with records in the Monthly
        # Report of Official Travel are included, so other vehicles are not validated.
        warnings.insert(0, f"{pred['plate_number']} has no trip records in the Monthly Report of Official Travel yet, "
                           "so this prediction for it is not validated against its own trips.")
    reviewer = db.get("users", pred["reviewed_by"])
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
    p = db.get("predictions", prediction_id)
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
    status = args.get("status", "")
    try:
        page = max(int(args.get("page") or 1), 1)
    except ValueError:
        page = 1
    per_page = 15

    vehicles_by_id = {v["id"]: v for v in db.records("vehicles")}
    users_by_id = {u["id"]: u for u in db.records("users")}
    everything = sorted(db.records("predictions"), key=lambda p: (p["created_at"], p["id"]))
    # First come, first served: requests are listed in the order they were made,
    # and each keeps its request number (1 = the first request ever made) even
    # when the list is filtered or paged, so "No." always names the same request.
    for i, p in enumerate(everything, 1):
        v, u, r = (vehicles_by_id.get(p["vehicle_id"]), users_by_id.get(p["user_id"]),
                   users_by_id.get(p["reviewed_by"]))
        p.update(request_no=i, plate_number=v["plate_number"] if v else None,
                 brand_model=v["brand_model"] if v else None,
                 full_name=u["full_name"] if u else None, reviewer_name=r["full_name"] if r else None)
    # Staff see only the fuel requests they made; the administrator sees all.
    mine = args.get("mine") == "1" or session.get("role") != "admin"
    needle = q.lower()

    def keep(p):
        if needle:
            label = [p["plate_number"] or "", p["brand_model"] or ""] if p["vehicle_id"] is not None and p["plate_number"] \
                else ["Vehicle deleted"]
            if not any(needle in part.lower() for part in label):
                return False
        if status in ("pending", "approved", "rejected") and p["approval_status"] != status:
            return False
        return not mine or p["user_id"] == session.get("user_id")
    matching = [p for p in everything if keep(p)]
    # "Predicted range" = predicted fuel ± the model's RMSE (its typical error in liters).
    tolerance = float((get_metrics() or {}).get("rmse") or 2.0)

    errors_l = [abs(float(p["predicted_fuel"]) - float(p["actual_fuel"])) for p in matching if p["actual_fuel"] is not None]
    stats = {"total": len(matching), "with_actual": len(errors_l),
             "pending": sum(p["approval_status"] == "pending" for p in matching),
             "outside": sum(e > tolerance for e in errors_l)}
    total = int(stats["total"] or 0)
    total_pages = max((total + per_page - 1) // per_page, 1)
    page = min(page, total_pages)
    offset = (page - 1) * per_page
    rows = matching[offset:offset + per_page]

    records = []
    for p in rows:
        actual = float(p["actual_fuel"]) if p["actual_fuel"] is not None else None
        predicted = float(p["predicted_fuel"])
        diff = round(predicted - actual, 2) if actual is not None else None
        records.append({
            "id": p["id"], "num": int(p["request_no"]),
            "created_at": p["created_at"].strftime("%b %d, %Y %I:%M %p"),
            "created_at_long": p["created_at"].strftime("%B %d, %Y %I:%M %p"),
            "vehicle": p["plate_number"] or "Vehicle deleted", "vehicle_model": p["brand_model"] or "",
            "vehicle_label": f"{p['plate_number']} ({p['brand_model']})" if p["plate_number"] else "Vehicle deleted",
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
        "pending": int(stats["pending"] or 0),
        "outside": int(stats["outside"] or 0),
        "tolerance": f"{tolerance:.2f}",
    }
    return {"predictions": records, "page": page, "total_pages": total_pages, "summary": summary,
            "q": q,
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
    pred = db.get("predictions", prediction_id)
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
        # Typed in by hand: never changed by the automatic matching from trips.
        db.update("predictions", prediction_id, actual_fuel=value,
                  actual_source="manual" if value is not None else None,
                  trip_record_id=pred["trip_record_id"] if value is not None else None)
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
    pred = db.get("predictions", prediction_id)
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
    db.update("predictions", prediction_id, approval_status=decision, approved_fuel=approved_fuel,
              reviewed_by=session["user_id"], reviewed_at=now_local(), review_note=note)
    flash(f"Fuel request #{prediction_id} {decision}" + (f": {approved_fuel:.2f} L to release." if approved_fuel else "."), "success")
    _link_actuals_quietly()  # a rejection frees its trip for another request
    return back_to_list("prediction_history")


@app.route("/prediction-history/<int:prediction_id>/delete", methods=["POST"])
@admin_required
def delete_prediction(prediction_id):
    if not db.get("predictions", prediction_id):
        flash("That prediction no longer exists.", "danger")
        return back_to_list("prediction_history")
    db.delete("predictions", prediction_id)
    flash("Prediction record deleted.", "success")
    return back_to_list("prediction_history")


# Engine power (kW) from published manufacturer specifications matched to each
# fleet vehicle's model and fuel type (Scope and Limitations). Filled in only
# where a vehicle has none yet; corrected values are edited in Vehicle Management.
PUBLISHED_ENGINE_POWER_KW = {
    "SFA 4712": 95, "SFA 4713": 95, "SFA 4714": 95,  # Nissan NV350 Urvan 2.5 diesel, 129 PS
    "SFA 1172": 130,  # Toyota HiAce GL Grandia 2.8 diesel (1GD-FTV), 174 hp
    "SFA 1173": 128,  # Toyota Innova 2.8 diesel (1GD-FTV), 174 PS
    "SEF 535": 51,    # Mitsubishi L300 2.5 diesel (4D56), 70 hp
    "SJC 955": 62,    # Isuzu Crosswind 2.5 diesel (4JA1-L), 85 PS
    "SGF 810": 63,    # Toyota Revo 2.4 diesel (2L-II), 85 PS
    # Hino bus: the exact model is not on record; Hino's FG midi bus (J08E-WF,
    # 237 hp), the bus line commonly bought by Philippine universities, is assumed.
    "SFA 1741": 177,
}
_VEHICLE_COLUMNS_READY = {"ok": False}


def _ensure_vehicle_columns():
    """Once per server start: fill in the published engine power of the fleet
    vehicles that have none yet (corrected values are kept)."""
    if _VEHICLE_COLUMNS_READY["ok"]:
        return
    for v in db.records("vehicles"):
        kw = PUBLISHED_ENGINE_POWER_KW.get(v["plate_number"])
        if kw is not None and v["engine_power_kw"] is None:
            db.update("vehicles", v["id"], engine_power_kw=float(kw))
    _VEHICLE_COLUMNS_READY["ok"] = True



def query_vehicles():
    """Vehicles with how many trip records depend on each one and its last trip."""
    _ensure_vehicle_columns()
    trips = db.records("trip_records")
    rows = sorted(db.records("vehicles"), key=lambda v: v["plate_number"])
    for v in rows:
        mine = [t["trip_date"] for t in trips if t["vehicle_id"] == v["id"]]
        v.update(trip_count=len(mine), last_trip_date=max(mine) if mine else None)
    return rows



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
    elif any(v["plate_number"] == plate and v["id"] != vehicle_id for v in db.records("vehicles")):
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
    return {"plate_number": f["plate_number"].strip().upper(), "brand_model": f["brand_model"].strip(),
            "fuel_type": f["fuel_type"], "engine_power_kw": round(float(f["engine_power_kw"]), 2)}



def render_vehicles_page(reopen=None):
    """`reopen` (after a rejected save) opens the same form again with what the
    user typed, instead of losing it."""
    rows = [vehicle_record(v, i) for i, v in enumerate(query_vehicles(), 1)]
    return render_template("vehicles.html", active="vehicles", vehicles=rows, reopen=reopen)


@app.route("/vehicles")
@admin_required
def vehicles():
    return render_vehicles_page()


@app.route("/api/vehicles")
@admin_required
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
        db.insert("vehicles", _vehicle_values(request.form))
        flash("Vehicle added successfully.", "success")
    except Exception:
        app.logger.exception("Adding vehicle failed")
        flash("Could not add vehicle due to a database error. Please try again.", "danger")
    return redirect(url_for("vehicles"))


@app.route("/vehicles/<int:vehicle_id>/edit", methods=["POST"])
@admin_required
def edit_vehicle(vehicle_id):
    if not db.get("vehicles", vehicle_id):
        flash("That vehicle no longer exists.", "danger")
        return redirect(url_for("vehicles"))
    errors = validate_vehicle_form(request.form, vehicle_id)
    if errors:
        flash("Could not update vehicle: " + " ".join(errors), "danger")
        return render_vehicles_page({"modal": "editVehicleModal", "vehicle_id": vehicle_id,
                                     "values": request.form.to_dict()})
    try:
        _ensure_vehicle_columns()
        db.update("vehicles", vehicle_id, **_vehicle_values(request.form))
        flash("Vehicle updated successfully.", "success")
    except Exception:
        app.logger.exception("Updating vehicle failed")
        flash("Could not update vehicle due to a database error. Please try again.", "danger")
    return redirect(url_for("vehicles"))


@app.route("/vehicles/<int:vehicle_id>/delete", methods=["POST"])
@admin_required
def delete_vehicle(vehicle_id):
    v = db.get("vehicles", vehicle_id)
    if not v:
        flash("That vehicle no longer exists.", "danger")
        return redirect(url_for("vehicles"))
    try:
        # The vehicle's trip records are deleted with it; its fuel requests stay
        # in the prediction history (as "Vehicle deleted"), and a request whose
        # actual fuel came from one of those trips loses it.
        trip_ids = {t["id"] for t in db.find("trip_records", vehicle_id=vehicle_id)}
        for p in db.records("predictions"):
            fields = {}
            if p["vehicle_id"] == vehicle_id:
                fields["vehicle_id"] = None
            if p["trip_record_id"] in trip_ids:
                fields["trip_record_id"] = None
                if p["actual_source"] == "trip":
                    fields.update(actual_fuel=None, actual_source=None)
            if fields:
                db.update("predictions", p["id"], **fields)
        for tid in trip_ids:
            db.delete("trip_records", tid)
        db.delete("vehicles", vehicle_id)
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
        # Staff edit only the trips they encoded; the collected records stay with the administrator.
        "can_edit": session.get("role") == "admin" or t.get("created_by") == session.get("user_id"),
    }


def query_trips():
    _ensure_vehicle_columns()
    vehicles_by_id = {v["id"]: v for v in db.records("vehicles")}
    rows = []
    for t in sorted(db.records("trip_records"), key=lambda t: (t["trip_date"], t["id"])):
        v = vehicles_by_id.get(t["vehicle_id"])
        if v:
            t.update(plate_number=v["plate_number"], brand_model=v["brand_model"])
            rows.append(t)
    # Oldest first (January to December, like the Monthly Report of Official
    # Travel); a newly added or edited trip lands in its date's place automatically.
    return [trip_record(r, i) for i, r in enumerate(rows, 1)]


def validate_trip_form(f, trip_id=None):
    """Monthly Report of Official Travel: date of travel, vehicle, distance
    traveled (km) and fuel consumed (L). Returns (errors, warnings). Errors
    block saving; warnings are shown but the trip is still saved."""
    errors, warnings = [], []
    vid = (f.get("vehicle_id") or "").strip()
    if not (vid.isdigit() and db.get("vehicles", int(vid))):
        errors.append("Please choose a valid vehicle.")
    try:
        trip_date = date.fromisoformat((f.get("trip_date") or "").strip())
        if not date(2000, 1, 1) <= trip_date <= today_local():
            errors.append(f"Date of travel must be between 2000-01-01 and today ({today_local().isoformat()}).")
    except ValueError:
        errors.append("Date of travel must be a valid date.")
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


ACTUAL_MATCH_DISTANCE_TOLERANCE = 0.20   # trip distance within ±20% of the requested distance
ACTUAL_MATCH_DAYS_BEFORE, ACTUAL_MATCH_DAYS_AFTER = 1, 7


def link_predictions_to_trips():
    """Record the actual fuel of fuel requests automatically from Trip Records.

    1. A request already filled from a trip follows that trip (its liters are
       kept in step when the trip is edited, cleared if the trip lost them).
    2. A request with no actual fuel yet is matched to the trip ticket of the
       same vehicle dated from 1 day before to 7 days after the request, whose
       distance is within ±20% of the requested distance (closest first), and
       that is not already matched to another request.
    Manually recorded actual fuel is never changed. Returns the request ids filled."""
    trips = {t["id"]: t for t in db.records("trip_records")}
    preds = sorted(db.records("predictions"), key=lambda p: (p["created_at"], p["id"]))

    def change(p, **fields):
        if any(p[k] != v for k, v in fields.items()):
            db.update("predictions", p["id"], **fields)
            p.update(fields)

    for p in preds:
        if p["actual_source"] != "trip":
            continue
        t = trips.get(p["trip_record_id"])
        if t is not None and p["actual_fuel"] != t["actual_fuel_consumption"]:
            change(p, actual_fuel=t["actual_fuel_consumption"])
        if p["actual_fuel"] is None:
            change(p, trip_record_id=None, actual_source=None)
        # A rejected request released no fuel: it never takes a trip's actual fuel,
        # and frees any trip it was matched to before it was rejected.
        if p["approval_status"] == "rejected":
            change(p, actual_fuel=None, trip_record_id=None, actual_source=None)
    used = {p["trip_record_id"] for p in preds if p["trip_record_id"] is not None}
    filled = []
    for p in preds:
        if (p["actual_fuel"] is not None or p["vehicle_id"] is None or p["trip_record_id"] is not None
                or p["approval_status"] == "rejected"):
            continue
        d, day = float(p["distance_km"]), p["created_at"].date()
        lo, hi = day - timedelta(days=ACTUAL_MATCH_DAYS_BEFORE), day + timedelta(days=ACTUAL_MATCH_DAYS_AFTER)
        candidates = [t for t in trips.values()
                      if t["vehicle_id"] == p["vehicle_id"] and t["actual_fuel_consumption"] is not None
                      and lo <= t["trip_date"] <= hi and t["id"] not in used
                      and abs(float(t["distance_km"]) - d) <= d * ACTUAL_MATCH_DISTANCE_TOLERANCE]
        if candidates:
            trip = min(candidates, key=lambda t: (abs(float(t["distance_km"]) - d), abs((t["trip_date"] - day).days), t["id"]))
            change(p, actual_fuel=trip["actual_fuel_consumption"], trip_record_id=trip["id"], actual_source="trip")
            used.add(trip["id"])
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
    return {
        "vehicle_id": int(f["vehicle_id"]), "trip_date": date.fromisoformat(f["trip_date"].strip()),
        "distance_km": round(float(f["distance_km"].strip().replace(",", "")), 2),
        "actual_fuel_consumption": round(float(f["actual_fuel_consumption"].strip().replace(",", "")), 2),
    }



def render_trips_page(reopen=None, status=200):
    vehicles_list = sorted(db.records("vehicles"), key=lambda v: v["plate_number"])
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
        db.insert("trip_records", dict(_trip_payload(request.form), created_by=session["user_id"]))
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
    trip = db.get("trip_records", trip_id)
    if not trip:
        flash("That trip record no longer exists.", "danger")
        return redirect(url_for("trips"))
    if session.get("role") != "admin" and trip.get("created_by") != session.get("user_id"):
        flash("You can only edit the trip records you encoded.", "danger")
        return redirect(url_for("trips"))
    _ensure_vehicle_columns()
    errors, warnings = validate_trip_form(request.form, trip_id)
    if errors:
        flash("Could not update trip record: " + " ".join(errors), "danger")
        return render_trips_page({"modal": "editTripModal", "trip_id": trip_id,
                                  "values": request.form.to_dict()})
    try:
        db.update("trip_records", trip_id, **_trip_payload(request.form))
        flash("Trip record updated successfully.", "success")
        for w in warnings:
            flash(w, "warning")
        _link_actuals_quietly()
    except Exception:
        app.logger.exception("Updating trip failed")
        flash("Could not update trip record due to a database error. Please try again.", "danger")
    return redirect(url_for("trips"))


@app.route("/trips/<int:trip_id>/delete", methods=["POST"])
@admin_required
def delete_trip(trip_id):
    if not db.get("trip_records", trip_id):
        flash("That trip record no longer exists.", "danger")
        return redirect(url_for("trips"))
    try:
        # A fuel request whose actual fuel came from this trip loses it (and may
        # be matched again to another trip below); manual entries are kept.
        for p in db.find("predictions", trip_record_id=trip_id):
            if p["actual_source"] == "trip":
                db.update("predictions", p["id"], actual_fuel=None, trip_record_id=None, actual_source=None)
            else:
                db.update("predictions", p["id"], trip_record_id=None)
        db.delete("trip_records", trip_id)
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

def _system_trips():
    """Trips with fuel consumed, joined to their vehicle, oldest first."""
    vehicles_by_id = {v["id"]: v for v in db.records("vehicles")}
    rows = []
    for t in sorted(db.records("trip_records"), key=lambda t: (t["trip_date"], t["id"])):
        v = vehicles_by_id.get(t["vehicle_id"])
        if v and t["actual_fuel_consumption"] is not None:
            rows.append((t, v))
    return rows


def load_system_trip_records():
    """The trips in the system (Monthly Report of Official Travel: date,
    plate number, distance, fuel consumed) merged with the vehicle records
    (engine power and fuel type) using the plate number."""
    from model.preprocess import merge_trips_and_vehicles
    _ensure_vehicle_columns()
    trips = pd.DataFrame([{"trip_date": t["trip_date"], "plate_number": v["plate_number"],
                           "distance_km": t["distance_km"], "actual_fuel_consumption": t["actual_fuel_consumption"]}
                          for t, v in _system_trips()])
    if trips.empty:
        return trips
    vehicles = pd.DataFrame([{k: v[k] for k in ("plate_number", "brand_model", "fuel_type", "engine_power_kw")}
                             for v in db.records("vehicles")])
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
    import zlib
    _ensure_vehicle_columns()
    # Every value the model trains on from a trip and its vehicle, so adding,
    # editing or deleting a trip record (or editing a vehicle) changes the fingerprint.
    rows = _system_trips()
    crc = sum(zlib.crc32("|".join(str(x) for x in (
        t["id"], t["trip_date"], f"{float(t['distance_km']):.2f}", f"{float(t['actual_fuel_consumption']):.2f}",
        v["plate_number"], v["fuel_type"], "" if v["engine_power_kw"] is None else f"{float(v['engine_power_kw']):.2f}"))
        .encode()) for t, v in rows)
    mtimes = [os.path.getmtime(app.config[k]) for k in ("HISTORICAL_DATA_PATH", "SUPPLEMENTARY_DATA_PATH")]
    return f"{mtimes[0]:.0f}-{mtimes[1]:.0f}-{len(rows)}-{crc}"


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
    "add_trip", "edit_trip", "delete_trip",
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
            if db.reconnect():  # was running from a backup while Firestore reads were blocked
                print(" * Firebase Firestore can be read again (real-time sync on).")
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
    from backup_database import BACKUP_DIR, PREFIX
    try:
        files = [os.path.join(BACKUP_DIR, f) for f in os.listdir(BACKUP_DIR)
                 if f.startswith(PREFIX) and f.endswith(".json")]
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
    (colab/fuel_consumption_linear_regression.ipynb), as the three CSV files
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
        data = pd.DataFrame([{k: v[k] for k in VEHICLE_COLUMNS} for v in
                             sorted(db.records("vehicles"), key=lambda v: v["plate_number"])], columns=VEHICLE_COLUMNS)
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
        # "backup" while Firestore reads are blocked and the server runs from its newest backup
        "database": "backup" if db.offline_backup() else "live",
    }


@app.route("/api/model-performance-data")
@admin_required
def api_model_performance_data():
    ensure_model_current()
    return {"metrics": get_metrics(), "charts": build_model_charts()}


# ------------------------------------------------------------------
# SETTINGS
# ------------------------------------------------------------------
EMAIL_RE = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")


def render_settings(form=None, status=200):
    user = db.get("users", session["user_id"])
    return render_template("settings.html", active="settings", user=user, form=form or {},
                           admin_account=ADMIN_ACCOUNT), status


@app.route("/settings")
@login_required
def settings():
    return render_settings()


@app.route("/api/me")
@login_required
def api_me():
    """Current account details, polled by every page so the name in the
    top bar (and the settings form) stay in sync across tabs."""
    user = db.get("users", session["user_id"])
    return {
        "username": user["username"], "full_name": user["full_name"], "email": user["email"] or "",
        "role": user["role"].capitalize(), "initial": (user["full_name"] or "U")[0].upper(),
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
        elif email_taken(email, session["user_id"]):
            errors.append("That email address is already used by another account.")
    if errors:
        flash("Could not save profile: " + " ".join(errors), "danger")
        return render_settings({"full_name": request.form.get("full_name", ""), "email": email})
    db.update("users", session["user_id"], full_name=full_name, email=email or None)
    session["full_name"] = full_name
    flash("Profile updated successfully.", "success")
    return redirect(url_for("settings"))


@app.route("/settings/password", methods=["POST"])
@login_required
def change_password():
    user = db.get("users", session["user_id"])
    if user["username"] == ADMIN_ACCOUNT:
        flash("The administrator account's password is fixed and cannot be changed.", "danger")
        return redirect(url_for("settings"))
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
        db.update("users", session["user_id"], password_hash=new_hash)
        session["pw_sig"] = password_signature(new_hash)  # stay logged in here; other sessions are signed out
        session.pop("must_change_pw", None)
        flash("Password updated successfully. You were signed out on your other devices.", "success")
    return redirect(url_for("settings"))


# ------------------------------------------------------------------
# USER ACCOUNTS (admin only)
# ------------------------------------------------------------------
USER_ROLES = ["staff"]  # the only administrator is ADMIN_ACCOUNT
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
            "email": u["email"] or "", "role": effective_role(u), "status": u["status"],
            "locked": u["username"] == ADMIN_ACCOUNT,
            "created_at": u["created_at"].strftime("%b %d, %Y") if u["created_at"] else "",
            "is_self": u["id"] == session.get("user_id")}


def query_users():
    rows = sorted(db.records("users"), key=lambda u: (u["status"] != "pending", u["role"] != "admin", u["full_name"] or ""))
    return [user_record(u, i) for i, u in enumerate(rows, 1)]



def validate_user_form(f, user_id=None):
    errors = []
    full_name = " ".join((f.get("full_name") or "").split())
    email = (f.get("email") or "").strip()
    if user_id is None:
        username = (f.get("username") or "").strip()
        if not USERNAME_RE.fullmatch(username):
            errors.append("Username must be 3-50 characters: letters, numbers, dot, dash or underscore.")
        elif username_taken(username):
            errors.append(f"Username {username} is already taken.")
    if not 2 <= len(full_name) <= 100:
        errors.append("Full name must be 2 to 100 characters.")
    if email:
        if len(email) > 120 or not EMAIL_RE.fullmatch(email):
            errors.append("Please enter a valid email address.")
        elif email_taken(email, user_id):
            errors.append("That email address is already used by another account.")
    if f.get("role") not in USER_ROLES:
        errors.append("Please choose a valid role.")
    return errors, full_name, email


@app.route("/users")
@admin_required
def users():
    return render_template("users.html", active="users", users=query_users())


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
    db.insert("users", {"username": f["username"].strip(), "password_hash": generate_password_hash(f["password"]),
                        "full_name": full_name, "email": email or None, "role": f["role"], "status": "active"})
    flash(f"Account {f['username'].strip()} created. Share the username and password with the user.", "success")
    return redirect(url_for("users"))


@app.route("/users/<int:user_id>/edit", methods=["POST"])
@admin_required
def edit_user(user_id):
    target = db.get("users", user_id)
    if not target:
        flash("That account no longer exists.", "danger")
        return redirect(url_for("users"))
    if target["username"] == ADMIN_ACCOUNT:
        flash("The administrator account is fixed and cannot be changed here.", "danger")
        return redirect(url_for("users"))
    f = request.form
    errors, full_name, email = validate_user_form(f, user_id)
    if errors:
        flash("Could not update account: " + " ".join(errors), "danger")
        return redirect(url_for("users"))
    db.update("users", user_id, full_name=full_name, email=email or None, role=f["role"])
    flash(f"Account {target['username']} updated.", "success")
    return redirect(url_for("users"))


@app.route("/users/<int:user_id>/approve", methods=["POST"])
@admin_required
def approve_user(user_id):
    target = db.get("users", user_id)
    if not target or target["status"] != "pending":
        flash("That sign-up request no longer exists or was already handled.", "danger")
        return redirect(url_for("users"))
    db.update("users", user_id, status="active")
    flash(f"Account {target['username']} approved. The user can now log in.", "success")
    return redirect(url_for("users"))


@app.route("/users/<int:user_id>/reject", methods=["POST"])
@admin_required
def reject_user(user_id):
    target = db.get("users", user_id)
    if not target or target["status"] != "pending":
        flash("That sign-up request no longer exists or was already handled.", "danger")
        return redirect(url_for("users"))
    db.delete("users", user_id)
    for d in db.find("notification_dismissals", user_id=user_id):
        db.delete("notification_dismissals", d["id"])
    flash(f"Sign-up request from {target['username']} was rejected and removed.", "success")
    return redirect(url_for("users"))


@app.route("/users/<int:user_id>/reset-password", methods=["POST"])
@admin_required
def reset_user_password(user_id):
    target = db.get("users", user_id)
    if not target:
        flash("That account no longer exists.", "danger")
        return redirect(url_for("users"))
    if target["username"] == ADMIN_ACCOUNT:
        flash("The administrator account's password is fixed and cannot be reset.", "danger")
        return redirect(url_for("users"))
    password = request.form.get("password", "")
    problem = password_problem(password, target["username"])
    if not problem and password != request.form.get("confirm_password"):
        problem = "Password and confirmation do not match."
    if problem:
        flash("Could not reset password: " + problem, "danger")
        return redirect(url_for("users"))
    new_hash = generate_password_hash(password)
    db.update("users", user_id, password_hash=new_hash)
    if user_id == session["user_id"]:
        session["pw_sig"] = password_signature(new_hash)
    flash(f"Password for {target['username']} was reset and the user was signed out of any open sessions. "
          "Give the new password to the user.", "success")
    return redirect(url_for("users"))


# ------------------------------------------------------------------
# ERROR HANDLING
# ------------------------------------------------------------------
from flask_wtf.csrf import CSRFError


def _wants_json():
    return request.path.startswith("/api/") or request.accept_mimetypes.best == "application/json"


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
    # Firebase Firestore cannot be reached (no internet, missing key): say so plainly.
    original = getattr(e, "original_exception", None)
    if isinstance(original, db.DatabaseUnavailable):
        if _wants_json():
            return {"error": "database_unavailable"}, 503
        message = ("The Firebase Firestore database cannot be reached right now. Check the internet connection "
                   "and try again in a few minutes; if it keeps happening, contact the system administrator.")
        if not app.config["ONLINE"] and "key not found" in str(original):
            message = str(original)
        return render_template("error.html", code=503, title="Database cannot be reached", message=message), 503
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
            with app.app_context():
                try:
                    db.warm_up()
                except db.DatabaseUnavailable as e:
                    print(f" * WARNING: Firebase Firestore is not reachable yet: {e}")
            start_model_watcher()
        app.run(debug=True, host="0.0.0.0", port=5000, threaded=True)
    else:
        from waitress import serve
        with app.app_context():
            try:
                db.warm_up()
                print(" * Connected to Firebase Firestore (real-time sync on).")
            except db.DatabaseUnavailable as e:
                print(f" * WARNING: Firebase Firestore is not reachable yet: {e}")
        start_model_watcher()
        start_backup_scheduler()
        port = int(os.environ.get("PORT", 5000))  # hosting providers choose the port
        print(f" * Serving on http://127.0.0.1:{port} (Waitress)")
        serve(app, host="0.0.0.0", port=port, threads=8)
