"""Build trip_records_dataset.csv: the supplementary online records shown as
trip records (Trip Records page) of the fleet vehicles.

Distance traveled (km) and fuel consumed (L) of every record come unchanged
(rounded to 0.01) from supplementary_data.csv - Fan & Song (2022) on Mendeley
Data and the European Environment Agency (2025), both found through Google
Dataset Search; see SUPPLEMENTARY_DATASET_SOURCE.md. The date of travel and
the vehicle are assigned:

* from 2019-03-05 (the fleet's earliest acquisition date, ACQUIRED) to
  2026-10-29, each vehicle GSU already had travels at most once a day, as often
  as the GSO's own trips show for that day of the week (scaled down for the
  less-used vehicles, FLEET_SHARE);
* no trips on Philippine regular holidays;
* each trip takes an unused diesel record (EEA vans, fixed random seed 42) with
  an engine power close to the vehicle's (VEHICLE_KW), so its fuel use fits the
  vehicle, and a distance drawn like the GSO trips' distances (30-400 km). The
  records left over are not used.

`source`, `source_vehicle` and `source_row` (its row in supplementary_data.csv)
keep where each record came from. The
administrator can edit and delete these trips on the Trip Records page; that
changes this file, so running this script again undoes those changes. The model is
still trained on supplementary_data.csv itself (with each record's own engine
power and fuel type), not on this file.

Run:  python data/build_trip_records_dataset.py
"""
import os
from datetime import date, timedelta

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
SOURCE = os.path.join(HERE, "supplementary_data.csv")
OUTPUT = os.path.join(HERE, "trip_records_dataset.csv")

# The fleet vehicles of Vehicle Management (plate numbers) and the share of the
# trips each one gets: the vans and the Innova travel most, the bus least, so
# the vehicles do not all have the same number of trips.
FLEET_SHARE = {"SFA 4714": 16, "SFA 1173": 15, "SFA 4713": 14, "SFA 1172": 13, "SFA 4712": 12,
               "SGF 810": 10, "SJC 955": 9, "SEF 535": 7, "SFA 1741": 4}
SEED = 42

# When GSU got each vehicle: it has no trips before this date. Published dates
# where GSU posted them; otherwise ESTIMATED as the earliest date the vehicle
# could be GSU's, from its model (engine power in Vehicle Management) and its
# plate number. Replace an estimate with the GSO property record's "date acquired".
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
# The trips run from the day the fleet above was complete to yesterday;
# SFA 4714's trips from 2026 are the GSO's own Monthly Reports of Official
# Travel, so its dataset trips stop before 2026.
FIRST_DAY, LAST_DAY = min(ACQUIRED.values()), date(2026, 10, 29)
LAST_TRIP = {"SFA 4714": date(2025, 12, 31)}

# How the fleet travels, from the GSO's own trips (data/gso_monthly_travel_SFA4714_2026.csv,
# SFA 4714, Jan-Jun 2026): at most one trip a day, on about half of the days,
# mostly Monday to Thursday; 32-372 km a trip (176 km on average).
GSO_TRIPS = os.path.join(HERE, "gso_monthly_travel_SFA4714_2026.csv")
DISTANCE_BINS = [30, 80, 130, 180, 230, 280, 330, 400]   # km; the records are drawn to match the GSO trips

# Engine power (kW) of each vehicle in Vehicle Management. All 9 are diesel, so
# a vehicle's trips are diesel records (EEA vans) whose engine power is within
# KW_WINDOW of its own: their fuel use then fits the vehicle's size.
VEHICLE_KW = {"SEF 535": 51, "SFA 1172": 130, "SFA 1173": 128, "SFA 1741": 177, "SFA 4712": 95,
              "SFA 4713": 95, "SFA 4714": 95, "SGF 810": 63, "SJC 955": 62}
KW_WINDOW = 10


def holidays(year):
    """Philippine regular holidays (offices closed, no official travel):
    New Year, Maundy Thursday, Good Friday, Araw ng Kagitingan, Labor Day,
    Independence Day, National Heroes Day (last Monday of August), Bonifacio
    Day, Christmas and Rizal Day."""
    from dateutil.easter import easter
    e = easter(year)
    heroes = max(date(year, 8, d) for d in range(25, 32) if date(year, 8, d).weekday() == 0)
    return {date(year, 1, 1), e - timedelta(days=3), e - timedelta(days=2), date(year, 4, 9),
            date(year, 5, 1), date(year, 6, 12), heroes, date(year, 11, 30), date(year, 12, 25),
            date(year, 12, 30)}


def gso_pattern():
    """From the GSO trips: the chance of a trip on each day of the week
    (Monday = 0) and the share of trips in each distance bin."""
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
    src["source_row"] = src.index   # row of supplementary_data.csv: training leaves it out there (no double count)
    src = src[src["distance_km"].between(DISTANCE_BINS[0], DISTANCE_BINS[-1]) & (src["fuel_type"] == "Diesel")]
    src = src.sample(frac=1, random_state=SEED).reset_index(drop=True)
    # For each vehicle and distance bin: the unused records it may take.
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
    # Each day, each vehicle GSU had travels once or not at all: the busiest
    # vehicle (SFA 4714, share 16) as often as in the GSO reports for that day
    # of the week, the others less (FLEET_SHARE). Its trip is the next unused
    # online record of a distance drawn like the GSO trips' distances.
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
        "row_id": np.arange(1, len(rows) + 1),   # permanent key: edits and deletes on the Trip Records page use it
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
