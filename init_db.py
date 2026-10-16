"""Prepare an empty database for a new installation (used by the online
deployment on every start; safe to run again and again):

1. Creates the tables from database/government_fleet_fuel.sql if they are missing.
2. If there are no user accounts yet, creates the first administrator from the
   ADMIN_USERNAME / ADMIN_PASSWORD / ADMIN_FULL_NAME environment variables.

Unlike seed_data.py it adds no demo vehicles, trips or default passwords, so a
new office starts with an empty, private system.

Run:  python init_db.py
"""
import os
import re
import sys

import pymysql

from db import ssl_options
from werkzeug.security import generate_password_hash

from config import Config

SCHEMA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "database", "government_fleet_fuel.sql")


def schema_statements():
    sql = open(SCHEMA, encoding="utf-8").read()
    sql = re.sub(r"(?m)^\s*--.*$", "", sql)
    for stmt in sql.split(";"):
        stmt = stmt.strip()
        # The hosting provider gives us one database; skip creating/selecting our own.
        if stmt and not re.match(r"(?i)(CREATE DATABASE|USE)\b", stmt):
            yield stmt


def main():
    conn = pymysql.connect(host=Config.MYSQL_HOST, port=Config.MYSQL_PORT, user=Config.MYSQL_USER,
                           password=Config.MYSQL_PASSWORD, database=Config.MYSQL_DB, autocommit=True,
                           init_command=f"SET time_zone = '{Config.DB_TIME_ZONE}'",
                           **ssl_options(Config.MYSQL_SSL))
    with conn.cursor() as cur:
        for stmt in schema_statements():
            cur.execute(stmt)
        print(" * Database tables are ready.")

        cur.execute("SELECT COUNT(*) FROM users")
        if cur.fetchone()[0]:
            return 0
        username = (os.environ.get("ADMIN_USERNAME") or "").strip()
        password = os.environ.get("ADMIN_PASSWORD") or ""
        full_name = (os.environ.get("ADMIN_FULL_NAME") or "System Administrator").strip()
        if not username or len(password) < 8 or not (re.search(r"[A-Za-z]", password) and re.search(r"\d", password)):
            print(" * No accounts yet. Set ADMIN_USERNAME and ADMIN_PASSWORD (8+ characters with a letter "
                  "and a number) and restart to create the first administrator.")
            return 0
        cur.execute("""INSERT INTO users (username, password_hash, full_name, role, status)
                       VALUES (%s, %s, %s, 'admin', 'active')""",
                    (username, generate_password_hash(password), full_name))
        print(f" * Administrator account '{username}' created. Remove ADMIN_PASSWORD from the settings now.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
