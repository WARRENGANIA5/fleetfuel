import ssl

import pymysql
import pymysql.cursors
from flask import current_app, g


def ssl_options(use_ssl):
    """Encrypted connection (verified against the system's CA certificates)
    for cloud MySQL services; none for the local XAMPP MySQL."""
    return {"ssl": ssl.create_default_context()} if use_ssl else {}


def get_db():
    if "db" not in g:
        g.db = pymysql.connect(
            host=current_app.config["MYSQL_HOST"],
            port=current_app.config["MYSQL_PORT"],
            user=current_app.config["MYSQL_USER"],
            password=current_app.config["MYSQL_PASSWORD"],
            database=current_app.config["MYSQL_DB"],
            cursorclass=pymysql.cursors.DictCursor,
            autocommit=True,
            init_command=f"SET time_zone = '{current_app.config['DB_TIME_ZONE']}'",
            **ssl_options(current_app.config["MYSQL_SSL"]),
        )
    return g.db


def close_db(e=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def query_all(sql, params=None):
    db = get_db()
    with db.cursor() as cur:
        cur.execute(sql, params or ())
        return cur.fetchall()


def query_one(sql, params=None):
    db = get_db()
    with db.cursor() as cur:
        cur.execute(sql, params or ())
        return cur.fetchone()


def execute(sql, params=None):
    db = get_db()
    with db.cursor() as cur:
        cur.execute(sql, params or ())
        return cur.lastrowid


def init_app(app):
    app.teardown_appcontext(close_db)
