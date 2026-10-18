"""Firebase Firestore data layer (Chapter III: Firebase Firestore stores the
vehicle records and the prediction history of the web application).

Collections (one document per record):
    users, vehicles, trip_records, predictions, notification_dismissals

Records keep whole-number IDs (1, 2, 3 ...), like the record numbers the pages
and links use; the next ID of each collection is kept in the `_counters`
collection and taken inside a Firestore transaction, so two users saving at
the same moment never get the same number.

Real-time sync: while the server runs, a Firestore snapshot listener per
collection keeps an up-to-date copy of the records in memory. Pages read that
copy (instant, and the pages that refresh every few seconds cost no Firestore
reads); every change, from this server or another one, arrives within a moment.
Writes go to Firestore first and are applied to the copy right away.

Values: dates of travel are stored as "YYYY-MM-DD" text and returned as dates;
times are stored as Firestore timestamps and returned in Philippine time.
"""
import copy
import json
import os
import threading
from datetime import date, datetime

from timeutil import LOCAL_TZ, now_local

COLLECTIONS = ("users", "vehicles", "trip_records", "predictions", "notification_dismissals")
COUNTERS = "_counters"
DATE_FIELDS = {"trip_date"}

# Every field of each record, with its default, so a page never meets a
# missing key (Firestore documents have no fixed columns).
FIELDS = {
    "users": {"username": None, "password_hash": None, "full_name": None, "email": None,
              "role": "staff", "status": "active", "notif_seen_at": None, "created_at": None},
    "vehicles": {"plate_number": None, "brand_model": None, "fuel_type": None, "engine_power_kw": None,
                 "created_at": None, "updated_at": None},
    "trip_records": {"vehicle_id": None, "trip_date": None, "distance_km": None,
                     "actual_fuel_consumption": None, "remarks": None, "created_at": None},
    "predictions": {"user_id": None, "vehicle_id": None, "distance_km": None, "engine_power_kw": None,
                    "fuel_type": None, "predicted_fuel": None, "actual_fuel": None, "trip_record_id": None,
                    "actual_source": None, "created_at": None, "approval_status": "pending",
                    "approved_fuel": None, "reviewed_by": None, "reviewed_at": None, "review_note": None},
    "notification_dismissals": {"user_id": None, "notif_key": None, "dismissed_at": None},
}


class DatabaseUnavailable(Exception):
    """Firestore could not be reached (no internet, wrong key, project missing)."""


# ------------------------------------------------------------------
# value conversion
# ------------------------------------------------------------------
def _plain_datetime(v):
    """A plain datetime: Firestore hands back its own datetime subclass, which
    the library cannot write again once it has been copied or changed."""
    return datetime(v.year, v.month, v.day, v.hour, v.minute, v.second, v.microsecond, v.tzinfo)


def _encode(data):
    out = {}
    for k, v in data.items():
        if isinstance(v, datetime):
            v = _plain_datetime(v)
            v = v if v.tzinfo else v.replace(tzinfo=LOCAL_TZ)
        elif isinstance(v, date):
            v = v.isoformat()
        elif hasattr(v, "is_finite") and not isinstance(v, (int, float)):  # Decimal
            v = float(v)
        out[k] = v
    return out


def _decode(coll, data):
    row = dict(FIELDS.get(coll, {}))
    for k, v in data.items():
        if isinstance(v, datetime):
            v = _plain_datetime(v.astimezone(LOCAL_TZ) if v.tzinfo else v).replace(tzinfo=None, microsecond=0)
        elif k in DATE_FIELDS and isinstance(v, str):
            try:
                v = date.fromisoformat(v[:10])
            except ValueError:
                pass
        row[k] = v
    return row


def _key(doc_id):
    return int(doc_id) if str(doc_id).isdigit() else str(doc_id)


# ------------------------------------------------------------------
# storage backends
# ------------------------------------------------------------------
class FirestoreBackend:
    def __init__(self, config):
        import firebase_admin
        from firebase_admin import credentials, firestore
        raw = config.get("FIREBASE_CREDENTIALS_JSON")
        path = config.get("FIREBASE_CREDENTIALS")
        if raw:
            cred = credentials.Certificate(json.loads(raw))
        elif path and os.path.exists(path):
            cred = credentials.Certificate(path)
        else:
            raise DatabaseUnavailable(
                "Firebase key not found. Download the service account key of your Firebase project "
                f"(Project settings > Service accounts > Generate new private key) and save it as {path}.")
        try:
            fb_app = firebase_admin.get_app()
        except ValueError:
            fb_app = firebase_admin.initialize_app(cred)
        self._firestore = firestore
        self.client = firestore.client(fb_app)

    def load(self, coll):
        return {_key(d.id): d.to_dict() for d in self.client.collection(coll).stream()}

    def set(self, coll, doc_id, data):
        self.client.collection(coll).document(str(doc_id)).set(data)

    def update(self, coll, doc_id, fields):
        self.client.collection(coll).document(str(doc_id)).update(fields)

    def delete(self, coll, doc_id):
        self.client.collection(coll).document(str(doc_id)).delete()

    def next_id(self, coll, at_least):
        ref = self.client.collection(COUNTERS).document(coll)

        @self._firestore.transactional
        def take(transaction):
            snap = ref.get(transaction=transaction)
            last = (snap.to_dict() or {}).get("last", 0) if snap.exists else 0
            new = max(int(last), at_least) + 1
            transaction.set(ref, {"last": new})
            return new
        return take(self.client.transaction())

    def set_counter(self, coll, last):
        self.client.collection(COUNTERS).document(coll).set({"last": int(last)})

    def watch(self, coll, on_change):
        """Snapshot listener: on_change(kind, doc_id, data) for every change."""
        def callback(_docs, changes, _read_time):
            for ch in changes:
                kind = ch.type.name  # ADDED / MODIFIED / REMOVED
                on_change(kind, _key(ch.document.id), ch.document.to_dict() if kind != "REMOVED" else None)
        return self.client.collection(coll).on_snapshot(callback)


class MemoryBackend:
    """Same interface, kept in memory: for automated tests only (DB_BACKEND=memory)."""

    def __init__(self, config=None):
        self.data = {c: {} for c in COLLECTIONS}
        self.counters = {}
        self.lock = threading.Lock()

    def load(self, coll):
        return copy.deepcopy(self.data.setdefault(coll, {}))

    def set(self, coll, doc_id, data):
        self.data.setdefault(coll, {})[_key(doc_id)] = copy.deepcopy(data)

    def update(self, coll, doc_id, fields):
        self.data[coll][_key(doc_id)].update(copy.deepcopy(fields))

    def delete(self, coll, doc_id):
        self.data.setdefault(coll, {}).pop(_key(doc_id), None)

    def next_id(self, coll, at_least):
        with self.lock:
            new = max(self.counters.get(coll, 0), at_least) + 1
            self.counters[coll] = new
            return new

    def set_counter(self, coll, last):
        self.counters[coll] = int(last)

    def watch(self, coll, on_change):
        return None


# ------------------------------------------------------------------
# in-memory copy kept in sync with Firestore
# ------------------------------------------------------------------
class Store:
    def __init__(self, backend, live):
        self.backend = backend
        self.live = live          # keep listeners open (long-running server)
        self.rows = {}            # coll -> {id: decoded row}
        self.loaded = {}          # coll -> threading.Event
        self.watches = {}
        self.lock = threading.RLock()

    def _apply(self, coll, kind, doc_id, data):
        with self.lock:
            table = self.rows.setdefault(coll, {})
            if kind == "REMOVED":
                table.pop(doc_id, None)
            else:
                row = _decode(coll, data or {})
                row["id"] = doc_id
                table[doc_id] = row

    def ensure(self, coll, fresh=False):
        with self.lock:
            ready = self.loaded.get(coll)
            if ready is not None and not fresh:
                return
            self.loaded[coll] = threading.Event()
        try:
            raw = self.backend.load(coll)
        except Exception as e:
            with self.lock:
                self.loaded.pop(coll, None)
            raise DatabaseUnavailable(str(e)) from e
        with self.lock:
            self.rows[coll] = {}
            for doc_id, data in raw.items():
                self._apply(coll, "ADDED", doc_id, data)
            self.loaded[coll].set()
        if self.live and coll not in self.watches:
            try:
                self.watches[coll] = self.backend.watch(
                    coll, lambda kind, doc_id, data: self._apply(coll, kind, doc_id, data))
            except Exception:
                pass  # no listener: the copy is still updated by this server's own writes

    def table(self, coll):
        self.ensure(coll)
        return self.rows.get(coll, {})


_STORE = {"store": None}
_STORE_LOCK = threading.Lock()


def _store():
    if _STORE["store"] is None:
        with _STORE_LOCK:
            if _STORE["store"] is None:
                from flask import current_app
                cfg = current_app.config
                if cfg.get("DB_BACKEND") == "memory":
                    backend, live = MemoryBackend(), False
                else:
                    try:
                        backend = FirestoreBackend(cfg)
                    except DatabaseUnavailable:
                        raise
                    except Exception as e:
                        raise DatabaseUnavailable(str(e)) from e
                    # Listeners are opened by the running server (warm_up); a
                    # short script reads fresh data instead and exits cleanly.
                    live = False
                _STORE["store"] = Store(backend, live)
    store = _STORE["store"]
    if not store.live:
        _refresh_per_request(store)
    return store


def _refresh_per_request(store):
    """Without listeners (serverless hosting) read each collection again once
    per request, so a page never shows data older than the request."""
    try:
        from flask import g, has_app_context
        if not has_app_context() or isinstance(store.backend, MemoryBackend):
            return
        seen = g.setdefault("_db_fresh", set())
    except RuntimeError:
        return
    for coll in list(store.loaded):
        if coll not in seen:
            seen.add(coll)
            store.ensure(coll, fresh=True)


# ------------------------------------------------------------------
# public API used by the app
# ------------------------------------------------------------------
def records(coll):
    """Every record of a collection (copies, safe to change)."""
    store = _store()
    with store.lock:
        return [dict(r) for r in store.table(coll).values()]


def get(coll, doc_id):
    if doc_id is None:
        return None
    store = _store()
    with store.lock:
        row = store.table(coll).get(_key(doc_id))
        return dict(row) if row else None


def find(coll, **equal):
    return [r for r in records(coll) if all_match(r, equal)]


def find_one(coll, **equal):
    rows = find(coll, **equal)
    return min(rows, key=lambda r: str(r["id"]).zfill(12)) if rows else None


def all_match(row, equal):
    return not any(row.get(k) != v for k, v in equal.items())


def insert(coll, data):
    """Add a record; returns its new ID."""
    store = _store()
    store.ensure(coll)
    with store.lock:
        highest = max((k for k in store.rows.get(coll, {}) if isinstance(k, int)), default=0)
    record = {k: v for k, v in FIELDS[coll].items()}
    record.update(data)
    if "created_at" in record and record["created_at"] is None:
        record["created_at"] = now_local()
    if coll == "vehicles" and record.get("updated_at") is None:
        record["updated_at"] = record["created_at"]
    try:
        new_id = store.backend.next_id(coll, highest)
        encoded = _encode(record)
        store.backend.set(coll, new_id, encoded)
    except DatabaseUnavailable:
        raise
    except Exception as e:
        raise DatabaseUnavailable(str(e)) from e
    store._apply(coll, "ADDED", new_id, encoded)
    return new_id


def put(coll, doc_id, data):
    """Create or replace a record under a chosen ID (e.g. notification dismissals)."""
    store = _store()
    store.ensure(coll)
    record = dict(FIELDS.get(coll, {}))
    record.update(data)
    encoded = _encode(record)
    try:
        store.backend.set(coll, doc_id, encoded)
    except Exception as e:
        raise DatabaseUnavailable(str(e)) from e
    store._apply(coll, "ADDED", _key(doc_id), encoded)


def update(coll, doc_id, **fields):
    if not fields:
        return
    store = _store()
    current = get(coll, doc_id)
    if current is None:
        return
    if coll == "vehicles":
        fields.setdefault("updated_at", now_local())
    encoded = _encode(fields)
    try:
        store.backend.update(coll, doc_id, encoded)
    except Exception as e:
        raise DatabaseUnavailable(str(e)) from e
    with store.lock:
        raw = _encode({k: v for k, v in current.items() if k != "id"})
        raw.update(encoded)
        store._apply(coll, "MODIFIED", _key(doc_id), raw)


def delete(coll, doc_id):
    store = _store()
    try:
        store.backend.delete(coll, doc_id)
    except Exception as e:
        raise DatabaseUnavailable(str(e)) from e
    store._apply(coll, "REMOVED", _key(doc_id), None)


def reset_counter(coll):
    """After a delete, the next ID continues from the highest ID still in use,
    so deleting the newest record leaves no gap."""
    store = _store()
    with store.lock:
        highest = max((k for k in store.table(coll) if isinstance(k, int)), default=0)
    try:
        store.backend.set_counter(coll, highest)
    except Exception as e:
        raise DatabaseUnavailable(str(e)) from e


def warm_up():
    """Server start: load every collection and open its real-time listener."""
    store = _store()
    if not isinstance(store.backend, MemoryBackend):
        store.live = True
    for coll in COLLECTIONS:
        store.ensure(coll)
        if store.live and coll not in store.watches:
            try:
                store.watches[coll] = store.backend.watch(
                    coll, lambda kind, doc_id, data, coll=coll: store._apply(coll, kind, doc_id, data))
            except Exception:
                pass


def init_app(app):
    pass
