"""Trip records from the online datasets (data/trip_records_dataset.csv, built
by data/build_trip_records_dataset.py), shown on the Trip Records page next to
the trips saved in Firestore.

They are kept in a file, not in Firestore: about 100,000 documents would take
5 days of the free plan's daily writes (20,000) and every start of the server
would read twice the daily read limit (50,000). The administrator edits and
deletes them like the other trips (update() / delete() rewrite the file); their
ids on the page are "d" + row_id. They are not part of the "system" trips the
model is trained with (the model uses the same records from
supplementary_data.csv instead).

Each record is linked to its vehicle by the plate number, like the local trips
and the vehicle records are merged for training.
"""
import os
import threading
from datetime import date

import pandas as pd

PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "trip_records_dataset.csv")

_lock = threading.Lock()
_write_lock = threading.Lock()   # one edit or delete of the file at a time
_cache = {"mtime": None, "frame": None, "listing": (None, None), "summary": (None, None)}


def _num(v):
    return str(float(v))


def frame():
    """The dataset trips, oldest first (empty if the file is missing)."""
    try:
        mtime = os.path.getmtime(PATH)
    except OSError:
        mtime = None
    with _lock:
        if _cache["mtime"] == mtime and _cache["frame"] is not None:
            return _cache["frame"]
        if mtime is None:
            df = pd.DataFrame(columns=["row_id", "trip_date", "plate_number", "distance_km",
                                       "actual_fuel_consumption", "source", "source_vehicle"])
        else:
            df = pd.read_csv(PATH, dtype={"trip_date": str, "plate_number": str})
        df = df.sort_values(["trip_date", "row_id"], kind="mergesort").reset_index(drop=True)
        _cache.update(mtime=mtime, frame=df, listing=(None, None), summary=(None, None))
        return df


def listing(own_trips, vehicles_by_plate):
    """Every trip record of the Trip Records page, oldest first, numbered:
    `own_trips` (the Firestore trips, already joined to their vehicle, as
    dicts) plus the dataset trips of the vehicles that exist. Returns a
    DataFrame with the columns of the page's rows plus `search` text."""
    ds = frame()
    key = (_cache["mtime"], tuple(sorted((k, v["id"], v["brand_model"]) for k, v in vehicles_by_plate.items())),
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
        if _cache["summary"][0] == (_cache["mtime"], plates):
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
        _cache["summary"] = ((_cache["mtime"], plates), result)
    return result


def get(row_id):
    """One dataset trip as a dict, or None."""
    ds = frame()
    hit = ds[ds["row_id"] == row_id]
    return hit.iloc[0].to_dict() if len(hit) else None


def _save(df):
    """Write the file (to a temporary file first, so a failed write never
    leaves half a file) and drop the cached copies."""
    df = df.sort_values("row_id")
    tmp = PATH + ".tmp"
    df.to_csv(tmp, index=False)
    os.replace(tmp, PATH)
    with _lock:
        _cache.update(mtime=None, frame=None)


def update(row_id, trip_date, plate_number, distance_km, actual_fuel_consumption):
    """Change one dataset trip (Edit on the Trip Records page). False if it no longer exists."""
    with _write_lock:
        df = frame().copy()
        hit = df["row_id"] == row_id
        if not hit.any():
            return False
        df.loc[hit, ["trip_date", "plate_number", "distance_km", "actual_fuel_consumption"]] = [
            trip_date.isoformat(), plate_number, distance_km, actual_fuel_consumption]
        _save(df)
        return True


def delete(row_id):
    """Remove one dataset trip (Delete on the Trip Records page). False if it no longer exists."""
    with _write_lock:
        df = frame()
        hit = df["row_id"] == row_id
        if not hit.any():
            return False
        _save(df[~hit])
        return True


def rename_plate(old, new):
    """A vehicle's plate number was changed: its dataset trips follow it."""
    with _write_lock:
        df = frame()
        hit = df["plate_number"] == old
        if hit.any():
            df = df.copy()
            df.loc[hit, "plate_number"] = new
            _save(df)


def delete_plate(plate):
    """A vehicle was deleted: its dataset trips are deleted with it."""
    with _write_lock:
        df = frame()
        hit = df["plate_number"] == plate
        if hit.any():
            _save(df[~hit])
