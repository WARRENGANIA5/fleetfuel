"""Back up the MySQL database to backups/ (one .sql file per run).

Runs automatically from start_server.bat every time the system is started,
and can be run by hand:  venv\\Scripts\\python.exe backup_database.py
Keeps the newest KEEP backups and deletes older ones.

To restore a backup (this REPLACES the current data):
    C:\\xampp\\mysql\\bin\\mysql.exe -u root government_fleet_fuel_prediction < backups\\<file>.sql
"""
import os
import shutil
import subprocess
import sys

from config import Config
from timeutil import now_local

KEEP = 30
TIMEOUT_SECONDS = 10 * 60
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BACKUP_DIR = os.path.join(BASE_DIR, "backups")


def _dump_completed(path):
    """mysqldump writes '-- Dump completed' as its last line only on success."""
    size = os.path.getsize(path)
    if size == 0:
        return False
    with open(path, "rb") as f:
        f.seek(max(0, size - 200))
        return b"-- Dump completed" in f.read()


def find_mysqldump():
    for path in (r"C:\xampp\mysql\bin\mysqldump.exe", shutil.which("mysqldump")):
        if path and os.path.exists(path):
            return path
    return None


def main():
    dump = find_mysqldump()
    if not dump:
        print(" * Backup skipped: mysqldump was not found (install XAMPP or add MySQL to PATH).")
        return 1
    os.makedirs(BACKUP_DIR, exist_ok=True)
    target = os.path.join(BACKUP_DIR, f"{Config.MYSQL_DB}_{now_local():%Y-%m-%d_%H%M%S}.sql")
    cmd = [dump, f"--host={Config.MYSQL_HOST}", f"--port={Config.MYSQL_PORT}", f"--user={Config.MYSQL_USER}",
           "--single-transaction", "--routines", "--default-character-set=utf8mb4", Config.MYSQL_DB]
    env = dict(os.environ)
    if Config.MYSQL_PASSWORD:
        env["MYSQL_PWD"] = Config.MYSQL_PASSWORD  # keeps the password off the command line
    # Dump to a .partial file and rename it only once the dump is complete, so a
    # hung or killed dump never leaves an empty .sql that counts as a backup.
    partial = target + ".partial"
    try:
        with open(partial, "wb") as out:
            result = subprocess.run(cmd, stdout=out, stderr=subprocess.PIPE, env=env, timeout=TIMEOUT_SECONDS)
        error = result.stderr.decode(errors="replace").strip()
        if result.returncode == 0 and not _dump_completed(partial):
            error = "the dump file is empty or incomplete."
        elif result.returncode == 0:
            error = None
    except subprocess.TimeoutExpired:
        error = f"mysqldump did not finish within {TIMEOUT_SECONDS // 60} minutes (is MySQL responding?)."
    if error is not None:
        os.remove(partial)
        print(" * Backup FAILED: " + error)
        return 1
    os.replace(partial, target)
    backups = sorted(f for f in os.listdir(BACKUP_DIR) if f.startswith(Config.MYSQL_DB + "_") and f.endswith(".sql"))
    for old in backups[:-KEEP]:
        os.remove(os.path.join(BACKUP_DIR, old))
    print(f" * Database backed up to backups\\{os.path.basename(target)} "
          f"({os.path.getsize(target) // 1024} KB; keeping the newest {KEEP}).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
