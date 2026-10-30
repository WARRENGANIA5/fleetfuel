"""Trip records from the online datasets (data/trip_records_dataset.csv, built
by data/build_trip_records_dataset.py), shown on the Trip Records page next to
the trips saved in Firestore.

The trips themselves are kept in the file (read-only), not in Firestore, to
save the free plan's daily reads and writes. What the administrator changes -
editing or deleting a trip, changing a vehicle's plate number, deleting a
vehicle - is saved in Firestore (collection CHANGES, one small record per
change) and applied on top of the file, so the changes last and show the same
everywhere: on the office computer and online (Vercel's files are read-only,
and Render's are lost on every restart). Their ids on the page are "d" + row_id.

Each record is linked to its vehicle by the plate number, like the local trips
and the vehicle records are merged for training. Rebuilding the file starts
over from the online data, so the change records must then be cleared.
"""
import os
import threading
from datetime import date

import pandas as pd

import db

PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "trip_records_dataset.csv")
CHANGES = "trip_dataset_changes"
EDITED = ["trip_date", "plate_number", "distance_km", "actual_fuel_consumption"]

_lock = threading.Lock()
_cache = {"mtime": None, "base": None, "key": None, "frame": None, "listing": (None, None), "summary": (None, None)}


def _num(v):
    return str(float(v))


def _base():
    """The file as built (cached until it changes on disk)."""
    try:
        mtime = os.path.getmtime(PATH)
    except OSError:
        mtime = None
    with _lock:
        if _cache["mtime"] == mtime and _cache["base"] is not None:
            return _cache["base"], mtime
    if mtime is None:
        df = pd.DataFrame(columns=["row_id", "trip_date", "plate_number", "distance_km",
                                   "actual_fuel_consumption", "source", "source_vehicle", "source_row"])
    else:
        df = pd.read_csv(PATH, dtype={"trip_date": str, "plate_number": str})
    with _lock:
        _cache.update(mtime=mtime, base=df)
    return df, mtime


def _changes():
    """The administrator's changes, oldest first (none outside a request or script)."""
    try:
        return sorted(db.records(CHANGES), key=lambda c: c["id"])
    except RuntimeError:   # no application context
        return []


def frame():
    """The dataset trips with the administrator's changes applied, oldest first."""
    base, mtime = _base()
    changes = _changes()
    key = (mtime, tuple((c["id"], c["kind"], c["row_id"], str(c["trip_date"]), c["plate_number"], c["old_plate"],
                         c["distance_km"], c["actual_fuel_consumption"]) for c in changes))
    with _lock:
        if _cache["key"] == key:
            return _cache["frame"]
    df = base.copy()
    for c in changes:
        if c["kind"] == "edit":
            hit = df["row_id"] == c["row_id"]
            df.loc[hit, EDITED] = [str(c["trip_date"]), c["plate_number"], float(c["distance_km"]),
                                   float(c["actual_fuel_consumption"])]
        elif c["kind"] == "delete":
            df = df[df["row_id"] != c["row_id"]]
        elif c["kind"] == "rename_plate":
            df.loc[df["plate_number"] == c["old_plate"], "plate_number"] = c["plate_number"]
        elif c["kind"] == "delete_plate":
            df = df[df["plate_number"] != c["plate_number"]]
    df = df.sort_values(["trip_date", "row_id"], kind="mergesort").reset_index(drop=True)
    with _lock:
        _cache.update(key=key, frame=df, listing=(None, None), summary=(None, None))
    return df


def listing(own_trips, vehicles_by_plate):
    """Every trip record of the Trip Records page, oldest first, numbered:
    `own_trips` (the Firestore trips, already joined to their vehicle, as
    dicts) plus the dataset trips of the vehicles that exist. Returns a
    DataFrame with the columns of the page's rows plus `search` text."""
    ds = frame()
    key = (_cache["key"], tuple(sorted((k, v["id"], v["brand_model"]) for k, v in vehicles_by_plate.items())),
           tuple((t["id"], str(t["trip_date"]), t["plate_number"], t["distance_km"], t["actual_fuel_consumption"],
                  t.get("prediction_id"))
                 for t in own_trips))
    with _lock:
        if _cache["listing"][0] == key:
            return _cache["listing"][1]
    ds = ds[ds["plate_number"].isin(list(vehicles_by_plate))]
    data = pd.DataFrame({
        "id": "d" + ds["row_id"].astype(str),
        "vehicle_id": ds["plate_number"].map(lambda p: vehicles_by_plate[p]["id"]),
        "trip_date": ds["trip_date"],
        "plate_number": ds["plate_number"],
        "brand_model": ds["plate_number"].map(lambda p: vehicles_by_plate[p]["brand_model"]),
        "distance_km": ds["distance_km"].map(_num),
        "actual_fuel_consumption": ds["actual_fuel_consumption"].map(_num),
        "source": ds["source"],
        "pending": False,
        "order": ds["row_id"].astype("int64"),
    })
    own = pd.DataFrame([{
        "id": t["id"], "vehicle_id": t["vehicle_id"], "trip_date": str(t["trip_date"]),
        "plate_number": t["plate_number"], "brand_model": t["brand_model"],
        "distance_km": str(t["distance_km"]),
        "actual_fuel_consumption": str(t["actual_fuel_consumption"]) if t["actual_fuel_consumption"] is not None else "",
        "source": "", "order": 10 ** 9 + int(t["id"]),
        # added by a fuel request, waiting for its actual fuel
        "pending": t["actual_fuel_consumption"] is None and t.get("prediction_id") is not None,
    } for t in own_trips], columns=data.columns)
    rows = pd.concat([data, own], ignore_index=True) if not own.empty else data
    rows = rows.sort_values(["trip_date", "order"], kind="mergesort").reset_index(drop=True)
    rows["num"] = rows.index + 1
    rows["search"] = (rows["trip_date"] + " " + rows["plate_number"] + " " + rows["distance_km"] + " "
                      + rows["actual_fuel_consumption"] + rows["pending"].map({True: " pending", False: ""})).str.lower()
    with _lock:
        _cache["listing"] = (key, rows)
    return rows


def summary(plates):
    """Totals of the dataset trips of the vehicles that exist (`plates`):
    count, liters, liters per month ("YYYY-MM") and per plate (count, last date)."""
    plates = tuple(sorted(plates))
    ds = frame()
    with _lock:
        if _cache["summary"][0] == (_cache["key"], plates):
            return _cache["summary"][1]
    ds = ds[ds["plate_number"].isin(plates)]
    per_plate = ds.groupby("plate_number")["trip_date"].agg(["count", "max"])
    result = {
        "count": int(len(ds)),
        "fuel_sum": float(ds["actual_fuel_consumption"].sum()),
        "monthly": {k: float(v) for k, v in ds.groupby(ds["trip_date"].str[:7])["actual_fuel_consumption"].sum().items()},
        "per_plate": {p: (int(r["count"]), date.fromisoformat(r["max"])) for p, r in per_plate.iterrows()},
    }
    with _lock:
        _cache["summary"] = ((_cache["key"], plates), result)
    return result


def get(row_id):
    """One dataset trip as a dict, or None."""
    ds = frame()
    hit = ds[ds["row_id"] == row_id]
    return hit.iloc[0].to_dict() if len(hit) else None


def update(row_id, trip_date, plate_number, distance_km, actual_fuel_consumption):
    """Change one dataset trip (Edit on the Trip Records page). False if it no longer exists."""
    if get(row_id) is None:
        return False
    db.insert(CHANGES, {"kind": "edit", "row_id": int(row_id), "trip_date": trip_date, "plate_number": plate_number,
                        "distance_km": float(distance_km), "actual_fuel_consumption": float(actual_fuel_consumption)})
    return True


def delete(row_id):
    """Remove one dataset trip (Delete on the Trip Records page). False if it no longer exists."""
    if get(row_id) is None:
        return False
    db.insert(CHANGES, {"kind": "delete", "row_id": int(row_id)})
    return True


def rename_plate(old, new):
    """A vehicle's plate number was changed: its dataset trips follow it."""
    if (frame()["plate_number"] == old).any():
        db.insert(CHANGES, {"kind": "rename_plate", "old_plate": old, "plate_number": new})


def delete_plate(plate):
    """A vehicle was deleted: its dataset trips are deleted with it."""
    if (frame()["plate_number"] == plate).any():
        db.insert(CHANGES, {"kind": "delete_plate", "plate_number": plate})
