"""Create a developer account, or change its password. Safe to run again.

A developer sees Prediction Accuracy and the technical Model Diagnostics
page (coefficients, assumption tests, residual plots, Colab CSV downloads,
model upload and rollback). Otherwise it works like a staff account. The
administrator cannot edit it on the User Accounts page.

Run (on the GSO computer, in the project folder):
    python create_developer.py                     -> username "developer", asks for the password
    python create_developer.py myname              -> another username
    python create_developer.py myname --generate   -> makes and prints a random password
The password can also come from the DEVELOPER_PASSWORD environment variable.
Run it again with the same username to change the password.
"""
import getpass
import os
import secrets
import sys

from werkzeug.security import generate_password_hash


def main(argv):
    from app import USERNAME_RE, app, password_problem
    import db
    args = [a for a in argv if not a.startswith("--")]
    username = (args[0] if args else "developer").strip()
    if not USERNAME_RE.fullmatch(username):
        print(" * Username must be 3-50 characters: letters, numbers, dot, dash or underscore.")
        return 1
    if "--generate" in argv:
        password = secrets.token_urlsafe(12) + "7a"  # always has a letter and a digit
    else:
        password = os.environ.get("DEVELOPER_PASSWORD") or ""
        if not password:
            password = getpass.getpass(f"Password for {username}: ")
            if password != getpass.getpass("Type it again: "):
                print(" * The passwords do not match. Nothing was changed.")
                return 1
    with app.app_context():
        problem = password_problem(password, username)
        if problem:
            print(" * " + problem + " Nothing was changed.")
            return 1
        existing = next((u for u in db.records("users") if (u["username"] or "").lower() == username.lower()), None)
        if existing and existing["role"] != "developer":
            print(f" * {username} is already a {existing['role']} account. Choose another username.")
            return 1
        password_hash = generate_password_hash(password)
        if existing:
            db.update("users", existing["id"], password_hash=password_hash, status="active")
            print(f" * Password of developer account '{existing['username']}' changed.")
        else:
            db.insert("users", {"username": username, "password_hash": password_hash, "full_name": "System Developer",
                                "position": "System Developer", "role": "developer", "status": "active"})
            print(f" * Developer account '{username}' created.")
        if "--generate" in argv:
            print(f"   Password: {password}")
            print("   Keep it somewhere safe; change it any time under Settings or by running this again.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
