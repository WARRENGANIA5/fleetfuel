import ssl
import threading
import time

import pymysql
import pymysql.cursors
from flask import current_app, g


def ssl_options(use_ssl):
    """Encrypted connection (verified against the system's CA certificates)
    for cloud MySQL services; none for the local XAMPP MySQL."""
    return {"ssl": ssl.create_default_context()} if use_ssl else {}


# One open connection per worker thread, reused across requests: opening an
# encrypted connection to the cloud database takes most of a second, while a
# query on an open connection takes about a tenth.
_local = threading.local()
IDLE_CHECK_SECONDS = 30  # after this long unused, check the connection is still alive


def _connect():
    cfg = current_app.config
    return pymysql.connect(
        host=cfg["MYSQL_HOST"],
        port=cfg["MYSQL_PORT"],
        user=cfg["MYSQL_USER"],
        password=cfg["MYSQL_PASSWORD"],
        database=cfg["MYSQL_DB"],
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True,
        init_command=f"SET time_zone = '{cfg['DB_TIME_ZONE']}'",
        **ssl_options(cfg["MYSQL_SSL"]),
    )


def get_db():
    if "db" not in g:
        conn = getattr(_local, "conn", None)
        if conn is None or not conn.open:
            conn = _connect()
        elif time.monotonic() - _local.used > IDLE_CHECK_SECONDS:
            try:
                conn.ping(reconnect=False)
            except pymysql.err.Error:
                conn = _connect()
        _local.conn = conn
        g.db = conn
    _local.used = time.monotonic()
    return g.db


def close_db(e=None):
    """End of request: keep the connection open for the next request on this
    thread, unless the request failed (then start fresh next time)."""
    conn = g.pop("db", None)
    if conn is not None and e is not None:
        _local.conn = None
        try:
            conn.close()
        except pymysql.err.Error:
            pass


# The server dropped the connection (idle timeout, network change, restart).
_CONNECTION_LOST = (2006, 2013, 2055)


def _drop_connection():
    conn = g.pop("db", None)
    _local.conn = None
    if conn is not None:
        try:
            conn.close()
        except pymysql.err.Error:
            pass


def _read(sql, params, fetch):
    """Run a read; if the reused connection turns out to be dead, reconnect and
    run it once more (a read is safe to repeat)."""
    for attempt in (1, 2):
        try:
            with get_db().cursor() as cur:
                cur.execute(sql, params or ())
                return fetch(cur)
        except pymysql.err.OperationalError as e:
            if attempt == 2 or not e.args or e.args[0] not in _CONNECTION_LOST:
                raise
            _drop_connection()


def query_all(sql, params=None):
    return _read(sql, params, lambda cur: cur.fetchall())


def query_one(sql, params=None):
    return _read(sql, params, lambda cur: cur.fetchone())


def execute(sql, params=None):
    # Writes are not repeated automatically (it might run twice); a lost
    # connection is dropped so the next request starts with a fresh one.
    try:
        with get_db().cursor() as cur:
            cur.execute(sql, params or ())
            return cur.lastrowid
    except pymysql.err.OperationalError as e:
        if e.args and e.args[0] in _CONNECTION_LOST:
            _drop_connection()
        raise


def init_app(app):
    app.teardown_appcontext(close_db)
