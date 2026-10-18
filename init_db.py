"""Prepare an empty Firebase Firestore database for a new installation (used by
the online deployment on every start; safe to run again and again):

1. Checks that the Firebase project can be reached with the service account key.
2. If there are no user accounts yet, creates the administrator account
   admin1114 with the password in ADMIN_PASSWORD (and ADMIN_FULL_NAME).

Firestore needs no tables: each collection (users, vehicles, trip_records,
predictions, notification_dismissals) appears with its first record.
It adds no sample vehicles, trips or default passwords, so a new office
starts with an empty, private system.

Run:  python init_db.py
"""
import os
import re
import sys

from werkzeug.security import generate_password_hash


def main():
    from app import app, ADMIN_ACCOUNT
    import db
    with app.app_context():
        try:
            users = db.records("users")
        except db.DatabaseUnavailable as e:
            print(" * Firebase Firestore cannot be reached: " + str(e))
            return 1
        print(" * Firebase Firestore is ready.")
        if users:
            return 0
        username = ADMIN_ACCOUNT  # the only administrator account
        password = os.environ.get("ADMIN_PASSWORD") or ""
        full_name = (os.environ.get("ADMIN_FULL_NAME") or "System Administrator").strip()
        if not username or len(password) < 8 or not (re.search(r"[A-Za-z]", password) and re.search(r"\d", password)):
            print(f" * No accounts yet. Set ADMIN_PASSWORD (8+ characters with a letter and a number) "
                  f"and restart to create the administrator account {ADMIN_ACCOUNT}.")
            return 0
        db.insert("users", {"username": username, "password_hash": generate_password_hash(password),
                            "full_name": full_name, "role": "admin", "status": "active"})
        print(f" * Administrator account '{username}' created. Remove ADMIN_PASSWORD from the settings now.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
