"""Build data/supplementary_data.csv from the open online dataset

  Fan, P., & Song, G. (2022). Which factor contributes more to the fuel consumption
  gap between in-laboratory vs. real-world driving conditions? An independent
  component analysis (Version 2) [Dataset]. Mendeley Data.
  https://doi.org/10.17632/jzjxcdn6k4.2  (license CC BY 4.0)

385,158 real-world trips of 395 gasoline passenger vehicles (15 models) in Beijing.
Each trip is reduced to the study's variables and units. Variables the online
dataset does not have (odometer, trip type, load, route, road type, terrain) are
left out, so the web application drops them during merging (Scope and Limitations).

Usage: python build_supplementary.py <Vehicle fuel consumption.csv> <output.csv>
"""
import sys

import pandas as pd

SRC, OUT = sys.argv[1], sys.argv[2]
# Trips are sampled per vehicle model AND per distance band, so the training data
# covers short city trips as well as the long inter-campus / provincial trips the
# fleet makes (a plain random sample is almost all short city trips).
DISTANCE_BANDS = [(1, 10), (10, 30), (30, 100), (100, 1000)]   # km
# Trips to take in all. With the 49,390 EEA diesel vans (add_eea_diesel_vans.py) the
# supplementary dataset has 99,898 records; with the 93 local trips and 9 fleet
# vehicles the study has 100,000 records.
TOTAL_TRIPS = 50_508
SEED = 42


def balanced_quotas(sizes, total):
    """Split `total` as evenly as possible over the groups: every group gets the same
    number, and a group with fewer trips than that gives all of them (the rest is
    shared by the larger groups)."""
    quotas, left, open_groups = {}, total, sorted(sizes, key=sizes.get)
    while open_groups:
        share = left // len(open_groups)
        key = open_groups[0]
        if sizes[key] <= share:
            quotas[key] = sizes[key]
            left -= sizes[key]
            open_groups.pop(0)
        else:
            for i, key in enumerate(open_groups):
                quotas[key] = share + (1 if i < left - share * len(open_groups) else 0)
            break
    return quotas

# Vehicle model -> the web application's vehicle types (body style of each model).
VEHICLE_TYPES = {
    "Audi-A6L": "Sedan", "Honda-Accord": "Sedan", "Nissan-Teana": "Sedan", "Nissan-Tiida": "Sedan",
    "Volkswagen-Magotan": "Sedan", "Volkswagen-Passat": "Sedan",
    "Chevrolet-Captiva": "SUV", "Hyundai-Beijingix35": "SUV",
    "Buick-GL8": "Van", "Honda-Odyssey": "Van",
}
# Engine power (Max Power, kW) of every engine code, from the dataset's own
# "Vehicle information.xlsx" (same Mendeley record, SHA-256 3d5b80eb...7339293).
# The study's predictors are distance traveled, engine power and fuel type.
ENGINE_POWER_KW = {
    "0230320": 132,  # Audi A6L 2.0T (2014)
    "0B2020W": 123,  # Buick GL8 2.4L (2014)
    "0B2021Y": 147,  # Buick GL8 2.5L (2017)
    "3K10409": 123,  # Chevrolet Captiva 2.4L (2014)
    "0H3082Y": 114,  # Honda Accord 2.0L (2015)
    "0H3011H": 137,  # Honda Odyssey 2.4L (2015)
    "3J1020O": 121,  # Hyundai ix35 2.0L (2013)
    "2X1080Q": 104,  # Nissan Teana 2.0L (2013)
    "2X10829": 110,  # Nissan Teana 2.0L (2016)
    "2X10608": 140,  # Nissan Tiida 1.6L (2011), as published in the dataset
    "0X3050M": 118,  # Volkswagen Magotan 1.8T (2012)
    "0X3050X": 118,  # Volkswagen Magotan 1.8T (2013)
    "0X2072R": 118,  # Volkswagen Passat 1.8T (2015)
    "0X2072S": 118,  # Volkswagen Passat 1.8T (2015)
    "0X2072T": 118,  # Volkswagen Passat 1.8T (2015)
}
# Spellings used in the dataset's English Model column -> the model's proper name
# (as listed in the dataset's Vehicle information.xlsx).
NAME_FIXES = {"Chevrolet-Capaci": "Chevrolet-Captiva", "Volkswagen-Maotan": "Volkswagen-Magotan"}


def departure_period(hour):
    if 5 <= hour < 9:
        return "Early Morning"
    if 9 <= hour < 12:
        return "Morning"
    if 12 <= hour < 17:
        return "Afternoon"
    if 17 <= hour < 20:
        return "Evening"
    return "Night"


raw = pd.read_csv(SRC, encoding="gbk", encoding_errors="replace",
                  usecols=["vid", "Model", "tirp_start_time", "tirp_time", "tirp_distance", "fuel consumption (L)"])
print(f"online trips: {len(raw):,} | vehicles: {raw['vid'].nunique()} | models: {raw['Model'].nunique()}")

parts = raw["Model"].str.split("-", expand=True)        # e.g. Volkswagen-Passat-0X2072R-2015-1.8T
model_key = (parts[0] + "-" + parts[1]).replace(NAME_FIXES)
df = pd.DataFrame({
    "model_key": model_key,
    "brand_model": model_key.str.replace("-", " ", n=1).str.replace("Beijingix35", "ix35"),
    "engine_code": parts[2],
    "year_model": pd.to_numeric(parts[3], errors="coerce"),
    "engine_displacement": pd.to_numeric(parts[4].str.rstrip("LT"), errors="coerce"),
    "start": pd.to_datetime(raw["tirp_start_time"], format="%Y/%m/%d %H:%M", errors="coerce"),
    "duration_minutes": raw["tirp_time"] / 60.0,             # seconds -> minutes
    "distance_km": raw["tirp_distance"] / 1000.0,            # metres -> km
    "actual_fuel_consumption": raw["fuel consumption (L)"],  # liters per trip
})
df["vehicle_type"] = df["model_key"].map(VEHICLE_TYPES)
df["engine_power_kw"] = df["engine_code"].map(ENGINE_POWER_KW)
unmatched = sorted(df.loc[df["engine_power_kw"].isna(), "engine_code"].unique())
assert not unmatched, f"engine codes without a published power: {unmatched}"
unknown = sorted(df.loc[df["vehicle_type"].isna(), "model_key"].unique())
assert not unknown, f"vehicle models without a type: {unknown}"
df["fuel_type"] = "Gasoline"
df["avg_speed_kmh"] = df["distance_km"] / (df["duration_minutes"] / 60.0)
df["departure_time"] = df["start"].dt.strftime("%H:%M")
df["departure_period"] = df["start"].dt.hour.map(departure_period)

# Complete, physically plausible trips only (the app's cleaning step then removes outliers).
ok = (df[["year_model", "engine_displacement", "start"]].notna().all(axis=1)
      & df["distance_km"].between(1, 1000) & df["duration_minutes"].between(1, 1440)
      & df["avg_speed_kmh"].between(5, 130) & (df["actual_fuel_consumption"] > 0))
df = df[ok]
l_per_100 = df["actual_fuel_consumption"] / df["distance_km"] * 100
df = df[l_per_100.between(3, 40)]
print(f"complete, plausible trips: {len(df):,}")

# Same number of trips from every vehicle model in every distance band, or all of them when
# fewer (fixed seed, reproducible).
df["band"] = pd.cut(df["distance_km"], [b[0] for b in DISTANCE_BANDS] + [DISTANCE_BANDS[-1][1]],
                    labels=[f"{a}-{b} km" for a, b in DISTANCE_BANDS], include_lowest=True)
groups = df.dropna(subset=["band"]).groupby(["model_key", "band"], observed=True)
quotas = balanced_quotas(groups.size().to_dict(), TOTAL_TRIPS)
sample = pd.concat([g.sample(quotas[key], random_state=SEED) for key, g in groups])
print("trips per distance band:", sample.groupby("band", observed=True).size().to_dict())
sample = sample.sort_values(["model_key", "start"]).reset_index(drop=True)

# The study's shared variables (distance, engine power, fuel type, fuel consumed),
# plus the vehicle model and engine code so every row can be traced to its source.
columns = ["brand_model", "engine_code", "distance_km", "engine_power_kw", "fuel_type", "actual_fuel_consumption"]
out = sample[columns].copy()
out["engine_power_kw"] = out["engine_power_kw"].astype(int)
for c, n in (("distance_km", 2), ("actual_fuel_consumption", 4)):
    out[c] = out[c].round(n)
out.to_csv(OUT, index=False)
print(f"written {OUT}: {len(out):,} trips")
print(out.groupby("engine_power_kw").size().to_dict())
print(out[["distance_km", "engine_power_kw", "actual_fuel_consumption"]].describe().round(2).to_string())
