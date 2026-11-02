"""Build trip_records_dataset.csv: online records assigned to the fleet
vehicles so they show up as trips on the Trip Records page.

Distance and fuel come from supplementary_data.csv as-is (see
SUPPLEMENTARY_DATASET_SOURCE.md). Dates and vehicles are assigned:

* 2019-03-05 to 2026-10-29, at most one trip per vehicle per day, following
  the GSO's weekday pattern, scaled by FLEET_SHARE
* no trips on regular holidays
* each trip uses an unused EEA diesel record with engine power close to the
  vehicle's (VEHICLE_KW), distance drawn like the GSO trips (seed 42)

`source`, `source_vehicle` and `source_row` point back to the original row.
Re-running this resets any edits made on the Trip Records page. Training
still uses supplementary_data.csv, not this file.

Run:  python data/build_trip_records_dataset.py
"""
import os
from datetime import date, timedelta

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
SOURCE = os.path.join(HERE, "supplementary_data.csv")
OUTPUT = os.path.join(HERE, "trip_records_dataset.csv")

# relative trip share per vehicle (vans/Innova most, bus least)
FLEET_SHARE = {"SFA 4714": 16, "SFA 1173": 15, "SFA 4713": 14, "SFA 1172": 13, "SFA 4712": 12,
               "SGF 810": 10, "SJC 955": 9, "SEF 535": 7, "SFA 1741": 4}
SEED = 42

# Date GSU got each vehicle (no trips before it). ESTIMATED ones should be
# replaced with the "date acquired" from the GSO property records.
ACQUIRED = {
    # ESTIMATED - Toyota Hiace GL Grandia, 130 kW: only the new 2.8 1GD Hiace has
    # this power; it went on sale in the Philippines on March 5, 2019.
    "SFA 1172": date(2019, 3, 5),
    # ESTIMATED - Toyota Innova 2.8 (2nd generation, launched Feb 2016); its plate
    # SFA 1173 follows the Grandia's SFA 1172, so both were registered together.
    "SFA 1173": date(2019, 3, 5),
    # ESTIMATED - Nissan NV350 Urvan, 95 kW (129 PS, launched June 15, 2015); plates
    # SFA 4712-4714 come after SFA 1172/1173 in the same series, so not before them.
    "SFA 4712": date(2019, 3, 5),
    "SFA 4713": date(2019, 3, 5),
    "SFA 4714": date(2019, 3, 5),
    # ESTIMATED - Mitsubishi L300, 51 kW: the old non-turbo 2.5 4D56, sold until
    # the Euro 4 rule (the 2019 L300 has a 2.2 engine), so GSU had it before 2019.
    "SEF 535": date(2019, 3, 5),
    # Isuzu Crosswind XL 2.5, donated by NTC Region VI on May 12, 2023
    # (https://www.gsu.edu.ph/?p=8017)
    "SJC 955": date(2023, 5, 12),
    # Toyota Revo, donated by BFAR 6; announced May 25, 2023 (same post, no donation date given)
    "SGF 810": date(2023, 5, 25),
    # New university bus, blessed May 7, 2025 (procured as "Motor Vehicle (Mini-Bus)", March 2025)
    # (https://www.gsu.edu.ph/2025/05/07/gsu-welcomes-new-university-bus-with-blessing-ceremony-to-boost-campus-mobility/)
    "SFA 1741": date(2025, 5, 7),
}
# SFA 4714 stops at 2025 since its 2026 trips are the real GSO records
FIRST_DAY, LAST_DAY = min(ACQUIRED.values()), date(2026, 10, 29)
LAST_TRIP = {"SFA 4714": date(2025, 12, 31)}

# Travel pattern from the real GSO trips (SFA 4714, Jan-Jun 2026): about every
# other day, mostly Mon-Thu, 32-372 km (avg 176 km).
GSO_TRIPS = os.path.join(HERE, "gso_monthly_travel_SFA4714_2026.csv")
DISTANCE_BINS = [30, 80, 130, 180, 230, 280, 330, 400]   # km

# Engine power (kW) per vehicle; trips use EEA vans within KW_WINDOW of it.
VEHICLE_KW = {"SEF 535": 51, "SFA 1172": 130, "SFA 1173": 128, "SFA 1741": 177, "SFA 4712": 95,
              "SFA 4713": 95, "SFA 4714": 95, "SGF 810": 63, "SJC 955": 62}
KW_WINDOW = 10


def holidays(year):
    """Philippine regular holidays (no official travel)."""
    from dateutil.easter import easter
    e = easter(year)
    heroes = max(date(year, 8, d) for d in range(25, 32) if date(year, 8, d).weekday() == 0)
    return {date(year, 1, 1), e - timedelta(days=3), e - timedelta(days=2), date(year, 4, 9),
            date(year, 5, 1), date(year, 6, 12), heroes, date(year, 11, 30), date(year, 12, 25),
            date(year, 12, 30)}


def gso_pattern():
    """Trip chance per weekday (Mon = 0) and distance bin shares from the GSO trips."""
    gso = pd.read_csv(GSO_TRIPS, parse_dates=["date"])
    span = pd.date_range(gso["date"].min(), gso["date"].max())
    per_weekday = gso["date"].dt.dayofweek.value_counts()
    weekday_chance = {d: per_weekday.get(d, 0) / (span.dayofweek == d).sum() for d in range(7)}
    bins = pd.cut(gso["distance_km"], DISTANCE_BINS).value_counts(normalize=True).sort_index()
    return weekday_chance, bins.values


def main():
    weekday_chance, bin_share = gso_pattern()
    rng = np.random.default_rng(SEED)
    src = pd.read_csv(SOURCE)
    src["source_row"] = src.index   # so training can skip it (no double count)
    src = src[src["distance_km"].between(DISTANCE_BINS[0], DISTANCE_BINS[-1]) & (src["fuel_type"] == "Diesel")]
    src = src.sample(frac=1, random_state=SEED).reset_index(drop=True)
    # unused records per vehicle and distance bin
    by_bin = {p: [list(src.index[(src["distance_km"] > lo) & (src["distance_km"] <= hi)
                                 & ((src["engine_power_kw"] - kw).abs() <= KW_WINDOW)])
                  for lo, hi in zip(DISTANCE_BINS, DISTANCE_BINS[1:])]
              for p, kw in VEHICLE_KW.items()}
    used = set()

    def take(p, k):
        """The next unused record of vehicle p in bin k (else the nearest bin)."""
        for j in sorted(range(len(DISTANCE_BINS) - 1), key=lambda j: abs(j - k)):
            cand = by_bin[p][j]
            while cand and cand[0] in used:
                cand.pop(0)
            if cand:
                used.add(cand[0])
                return cand.pop(0)
        return None
    # each day a vehicle makes 0 or 1 trip; SFA 4714 follows the GSO rate,
    # the rest are scaled down by FLEET_SHARE
    busiest = max(FLEET_SHARE.values())
    rows, day, closed = [], FIRST_DAY, set()
    for y in range(FIRST_DAY.year, LAST_DAY.year + 1):
        closed |= holidays(y)
    while day <= LAST_DAY:
        for p in FLEET_SHARE:
            if day in closed:
                break
            if not ACQUIRED[p] <= day <= LAST_TRIP.get(p, LAST_DAY):
                continue
            if rng.random() >= weekday_chance[day.weekday()] * FLEET_SHARE[p] / busiest:
                continue
            i = take(p, int(rng.choice(len(bin_share), p=bin_share)))
            if i is not None:
                rows.append((day.isoformat(), p, i))
        day += timedelta(days=1)
    pick = src.loc[[i for _, _, i in rows]].reset_index(drop=True)
    out = pd.DataFrame({
        "row_id": np.arange(1, len(rows) + 1),   # stable key for edits/deletes
        "trip_date": [d for d, _, _ in rows],
        "plate_number": [p for _, p, _ in rows],
        "distance_km": pick["distance_km"].round(2),
        "actual_fuel_consumption": pick["actual_fuel_consumption"].round(2),
        "source": pick["source"],
        "source_vehicle": pick["brand_model"],
        "source_row": pick["source_row"],
    })
    out = out[(out["distance_km"] > 0) & (out["actual_fuel_consumption"] > 0)]
    out.to_csv(OUTPUT, index=False)
    print(f"{len(out):,} trip records, {out['trip_date'].min()} to {out['trip_date'].max()} -> {OUTPUT}")
    print(out["plate_number"].value_counts().sort_index().to_string())
    print(out["source"].value_counts().to_string())


if __name__ == "__main__":
    main()
