"""Firebase Firestore data layer (Chapter III: Firebase Firestore stores the
vehicle records and the prediction history of the web application).

Collections (one document per record):
    users, vehicles, trip_records, predictions, notification_dismissals,
    trip_dataset_changes (changes to the online-dataset trips, see trip_dataset.py)

Records keep whole-number IDs (1, 2, 3 ...), like the record numbers the pages
and links use. A new record takes the next number above the highest one in use
and is saved with Firestore's create(), which refuses a number that is already
taken (two users saving at the same moment), so the next one is tried.

Real-time sync: while the server runs, a Firestore snapshot listener per
collection keeps an up-to-date copy of the records in memory. Pages read that
copy (instant, and the pages that refresh every few seconds cost no Firestore
reads); every change, from this server or another one, arrives within a moment.
Writes go to Firestore first and are applied to the copy right away.

Without listeners (serverless hosting, short scripts) every write also adds 1
to a change counter (`_counters/_changes`); a request reads that one document
and loads the records again only when it changed, so the pages that refresh
every few seconds cost 1 read each instead of reading every record.

Values: dates of travel are stored as "YYYY-MM-DD" text and returned as dates;
times are stored as Firestore timestamps and returned in Philippine time.
"""
import copy
import json
import os
import threading
import time
from datetime import date, datetime

from timeutil import LOCAL_TZ, now_local

COLLECTIONS = ("users", "vehicles", "trip_records", "predictions", "notification_dismissals",
               "trip_dataset_changes")
COUNTERS = "_counters"
CHANGES = "_changes"   # document in COUNTERS: how many writes so far (see module doc)
BACKUP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backups")
RECONNECT_SECONDS = 60
DATE_FIELDS = {"trip_date"}

# Every field of each record, with its default, so a page never meets a
# missing key (Firestore documents have no fixed columns).
FIELDS = {
    "users": {"username": None, "password_hash": None, "full_name": None, "position": None,
              "email": None, "role": "staff", "status": "active", "notif_seen_at": None, "created_at": None},
    "vehicles": {"plate_number": None, "brand_model": None, "fuel_type": None, "engine_power_kw": None,
                 "created_at": None, "updated_at": None},
    "trip_records": {"vehicle_id": None, "trip_date": None, "distance_km": None,
                     "actual_fuel_consumption": None, "remarks": None, "created_by": None, "created_at": None,
                     "prediction_id": None},   # the fuel request (prediction) that added the trip
    "predictions": {"user_id": None, "vehicle_id": None, "distance_km": None, "engine_power_kw": None,
                    "fuel_type": None, "predicted_fuel": None, "actual_fuel": None, "trip_record_id": None,
                    "actual_source": None, "created_at": None, "approval_status": "pending",
                    "approved_fuel": None, "reviewed_by": None, "reviewed_at": None, "review_note": None},
    "notification_dismissals": {"user_id": None, "notif_key": None, "dismissed_at": None},
    # Changes to the online-dataset trips of Trip Records (see trip_dataset.py):
    # kind = edit / delete (row_id) or rename_plate / delete_plate (plate numbers).
    "trip_dataset_changes": {"kind": None, "row_id": None, "trip_date": None, "plate_number": None,
                             "old_plate": None, "distance_km": None, "actual_fuel_consumption": None,
                             "created_at": None},
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

    def create(self, coll, after, data):
        """Save a new record under the next free ID above `after` (the highest ID
        in the copy). Firestore's create() refuses an ID that is taken (another
        computer saved first), so the next one is tried. Needs no read, so new
        records can be saved even when the daily read quota is used up."""
        from google.api_core.exceptions import AlreadyExists, Conflict
        new = int(after) + 1
        for _ in range(200):
            try:
                self.client.collection(coll).document(str(new)).create(data)
                return new
            except (AlreadyExists, Conflict):
                new += 1
        raise DatabaseUnavailable(f"No free record number found in {coll}.")

    def bump(self):
        self.client.collection(COUNTERS).document(CHANGES).set({"n": self._firestore.Increment(1)}, merge=True)

    def change_mark(self):
        snap = self.client.collection(COUNTERS).document(CHANGES).get()
        return (snap.to_dict() or {}).get("n", 0) if snap.exists else 0

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
        self.changes = 0
        self.lock = threading.Lock()

    def bump(self):
        self.changes += 1

    def change_mark(self):
        return self.changes

    def load(self, coll):
        return copy.deepcopy(self.data.setdefault(coll, {}))

    def set(self, coll, doc_id, data):
        self.data.setdefault(coll, {})[_key(doc_id)] = copy.deepcopy(data)

    def update(self, coll, doc_id, fields):
        self.data[coll][_key(doc_id)].update(copy.deepcopy(fields))

    def delete(self, coll, doc_id):
        self.data.setdefault(coll, {}).pop(_key(doc_id), None)

    def create(self, coll, after, data):
        with self.lock:
            table = self.data.setdefault(coll, {})
            new = int(after) + 1
            while new in table:
                new += 1
            table[new] = copy.deepcopy(data)
            return new


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
        self.mark = None          # change counter when the copy was last loaded (no listeners)
        self.offline = None       # backup file the copy came from while Firestore reads are blocked
        self.last_try = 0.0
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


def _store(refresh=True):
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
    if refresh and not store.live:
        _refresh_per_request(store)
    return store


def _refresh_per_request(store):
    """Without listeners (serverless hosting, short scripts): once per request,
    read the change counter (1 read) and load the records again only when a
    write happened since the copy was loaded. (Edits typed straight into the
    Firebase console, which skip the counter, show after the next app write.)"""
    try:
        from flask import g, has_app_context
        if not has_app_context() or isinstance(store.backend, MemoryBackend):
            return
        seen = g.setdefault("_db_fresh", set())
    except RuntimeError:
        return
    if seen:
        return
    seen.add("_checked")
    try:
        mark = store.backend.change_mark()
    except Exception as e:
        raise DatabaseUnavailable(str(e)) from e
    if mark == store.mark:
        return
    store.mark = mark
    for coll in list(store.loaded):
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
        encoded = _encode(record)
        new_id = store.backend.create(coll, highest, encoded)
    except DatabaseUnavailable:
        raise
    except Exception as e:
        raise DatabaseUnavailable(str(e)) from e
    store._apply(coll, "ADDED", new_id, encoded)
    _changed(store)
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
    _changed(store)


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
    _changed(store)


def delete(coll, doc_id):
    store = _store()
    try:
        store.backend.delete(coll, doc_id)
    except Exception as e:
        raise DatabaseUnavailable(str(e)) from e
    store._apply(coll, "REMOVED", _key(doc_id), None)
    _changed(store)


def _changed(store):
    """Tell servers without listeners that the records changed (1 small write)."""
    try:
        store.backend.bump()
    except Exception:
        pass  # the record itself is saved; other servers notice at their next change


def warm_up():
    """Server start: load every collection and open its real-time listener.
    If Firestore cannot be read (e.g. the free daily read quota is used up),
    start from the newest backup in backups/ instead; saving still goes to
    Firestore, and reconnect() switches back once it can be read again."""
    store = _store(refresh=False)  # the server keeps its copy current with listeners instead
    if not isinstance(store.backend, MemoryBackend):
        store.live = True
    try:
        for coll in COLLECTIONS:
            store.ensure(coll)
    except DatabaseUnavailable as e:
        path = _newest_backup() if store.live else None
        if not path:
            raise
        _load_backup(store, path)
        raise DatabaseUnavailable(f"{e} -- running from the backup {os.path.basename(path)} until Firestore "
                                  f"can be read again (new records are still saved to Firestore)") from e
    _open_listeners(store)


def _open_listeners(store):
    for coll in COLLECTIONS:
        if store.live and coll not in store.watches:
            try:
                store.watches[coll] = store.backend.watch(
                    coll, lambda kind, doc_id, data, coll=coll: store._apply(coll, kind, doc_id, data))
            except Exception:
                pass


def _newest_backup():
    if not os.path.isdir(BACKUP_DIR):
        return None
    files = sorted(f for f in os.listdir(BACKUP_DIR) if f.startswith("firestore_") and f.endswith(".json"))
    return os.path.join(BACKUP_DIR, files[-1]) if files else None


def _from_backup(value):
    if isinstance(value, dict) and "$datetime" in value:
        return datetime.fromisoformat(value["$datetime"])
    if isinstance(value, dict) and "$date" in value:
        return date.fromisoformat(value["$date"])
    return value


def _load_backup(store, path):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    with store.lock:
        for coll in COLLECTIONS:
            store.rows[coll] = {}
            for r in data.get(coll, []):
                r = dict(r)
                doc_id = _key(r.pop("id"))
                store._apply(coll, "ADDED", doc_id, _encode({k: _from_backup(v) for k, v in r.items()}))
            store.loaded[coll] = threading.Event()
            store.loaded[coll].set()
        store.offline = path
        store.last_try = time.time()


def offline_backup():
    """The backup file the server is running from, or None when Firestore is read normally."""
    store = _STORE["store"]
    return store.offline if store else None


def reconnect():
    """Called by the server's background loop: while running from a backup, try
    Firestore again (once a minute); when it answers, load the real records and
    open the listeners. Returns True when it switched back."""
    store = _STORE["store"]
    if not store or not store.offline or time.time() - store.last_try < RECONNECT_SECONDS:
        return False
    store.last_try = time.time()
    try:
        fresh = {coll: store.backend.load(coll) for coll in COLLECTIONS}
    except Exception:
        return False
    with store.lock:
        for coll, raw in fresh.items():
            store.rows[coll] = {}
            for doc_id, data in raw.items():
                store._apply(coll, "ADDED", doc_id, data)
        store.offline = None
    _open_listeners(store)
    return True



def init_app(app):
    pass
