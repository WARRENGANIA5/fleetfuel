"""Back up the Firebase Firestore database to backups/ (one .json file per run).

Runs automatically from scripts/start_server.bat every time the system is started
(and every 24 hours while the server runs), and can be run by hand:
    venv\\Scripts\\python.exe backup_database.py
Keeps the newest KEEP backups and deletes older ones.

To restore a backup (this REPLACES the records with the same IDs):
    venv\\Scripts\\python.exe backup_database.py --restore backups\\<file>.json
"""
import json
import os
import sys
from datetime import date, datetime

from timeutil import now_local

KEEP = 30
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BACKUP_DIR = os.path.join(BASE_DIR, "backups")
PREFIX = "firestore_"


def _plain(value):
    if isinstance(value, datetime):
        return {"$datetime": value.isoformat()}
    if isinstance(value, date):
        return {"$date": value.isoformat()}
    return value


def _restore_value(value):
    if isinstance(value, dict) and "$datetime" in value:
        return datetime.fromisoformat(value["$datetime"])
    if isinstance(value, dict) and "$date" in value:
        return date.fromisoformat(value["$date"])
    return value


def main():
    from app import app
    import db
    os.makedirs(BACKUP_DIR, exist_ok=True)
    with app.app_context():
        try:
            data = {coll: [{k: _plain(v) for k, v in r.items()} for r in db.records(coll)]
                    for coll in db.COLLECTIONS}
        except db.DatabaseUnavailable as e:
            print(" * Backup FAILED: " + str(e))
            return 1
    target = os.path.join(BACKUP_DIR, f"{PREFIX}{now_local():%Y-%m-%d_%H%M%S}.json")
    partial = target + ".partial"
    with open(partial, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    os.replace(partial, target)
    backups = sorted(f for f in os.listdir(BACKUP_DIR) if f.startswith(PREFIX) and f.endswith(".json"))
    for old in backups[:-KEEP]:
        os.remove(os.path.join(BACKUP_DIR, old))
    total = sum(len(v) for v in data.values())
    print(f" * Database backed up to backups\\{os.path.basename(target)} "
          f"({total} records; keeping the newest {KEEP}).")
    return 0


def restore(path):
    from app import app
    import db
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    with app.app_context():
        for coll, rows in data.items():
            for r in rows:
                doc_id = r.pop("id")
                db.put(coll, doc_id, {k: _restore_value(v) for k, v in r.items()})
    print(f" * Restored {sum(len(v) for v in data.values())} records from {path}.")
    return 0


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--restore":
        sys.exit(restore(sys.argv[2]))
    sys.exit(main())
