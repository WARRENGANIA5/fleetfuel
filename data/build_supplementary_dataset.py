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
PER_MODEL = 200          # trips sampled per vehicle model (15 models -> 3,000 trips)
SEED = 42

# Vehicle model -> the web application's vehicle types (body style of each model).
VEHICLE_TYPES = {
    "Audi-A6L": "Sedan", "Honda-Accord": "Sedan", "Nissan-Teana": "Sedan", "Nissan-Tiida": "Sedan",
    "Volkswagen-Magotan": "Sedan", "Volkswagen-Passat": "Sedan",
    "Chevrolet-Captiva": "SUV", "Hyundai-Beijingix35": "SUV",
    "Buick-GL8": "Van", "Honda-Odyssey": "Van",
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

# Same number of trips from every vehicle model (fixed seed, reproducible).
key = df["model_key"] + "-" + df["engine_code"] + "-" + df["year_model"].astype(int).astype(str)
sample = (df.assign(_k=key).groupby("model_key", group_keys=False)
          .apply(lambda g: g.sample(min(PER_MODEL, len(g)), random_state=SEED)))
sample = sample.sort_values(["model_key", "start"]).reset_index(drop=True)

columns = ["vehicle_type", "brand_model", "engine_displacement", "fuel_type", "year_model",
           "distance_km", "duration_minutes", "avg_speed_kmh", "departure_time", "departure_period",
           "actual_fuel_consumption"]
out = sample[columns].copy()
out["year_model"] = out["year_model"].astype(int)
for c, n in (("distance_km", 2), ("duration_minutes", 2), ("avg_speed_kmh", 1), ("actual_fuel_consumption", 4)):
    out[c] = out[c].round(n)
out.to_csv(OUT, index=False)
print(f"written {OUT}: {len(out):,} trips")
print(out.groupby("vehicle_type").size().to_dict())
print(out[["distance_km", "duration_minutes", "avg_speed_kmh", "actual_fuel_consumption"]].describe().round(2).to_string())
