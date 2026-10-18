"""Add real-world DIESEL vehicles to data/supplementary_data.csv from the open dataset

  European Environment Agency (2025). 2024 real-world CO2 emissions from cars and vans
  [Dataset]. https://doi.org/10.2909/13e6fad9-149c-4b86-9d83-cdf3569ccfee  (license CC BY 4.0)
  File: 2024_Vans_Raw.csv

Each row of that file is one van in circulation in the EU, read from its on-board fuel
consumption meter (OBFCM): total distance travelled (km), total fuel consumed (L),
fuel type and engine power Ep (kW) - the study's variables. The Fan & Song (2022)
trips already in supplementary_data.csv are all gasoline (104-147 kW), and the local
trips come from one diesel van (95 kW), so without these records the model cannot
learn how engine power changes the fuel use of diesel vehicles.

Kept: diesel vans with 40-250 kW whose recorded distance is within the trip range of
the fleet (30-1,000 km; the local trips are 32-372 km) and 3-40 L/100 km. Shorter
records are left out: they are brand-new vans whose few kilometres are mostly
warm-up and idling (median about 20 L/100 km), not trips. The same number of vans is taken from every
engine-power band and distance band (fixed seed), so small and large engines and
short and long distances are equally represented. Re-running replaces the EEA rows.

Usage: python data/add_eea_diesel_vans.py <2024_Vans_Raw.csv> data/supplementary_data.csv
"""
import hashlib
import sys

import pandas as pd

SRC, OUT = sys.argv[1], sys.argv[2]
SOURCE = "EEA 2024 (OBFCM)"
POWER_BANDS = [40, 60, 80, 100, 120, 140, 160, 250]      # kW
DISTANCE_BANDS = [30, 100, 300, 1000]                     # km
PER_CELL = 60                                             # vans per power band x distance band
SEED = 42

with open(SRC, "rb") as f:
    print("source SHA-256:", hashlib.sha256(f.read()).hexdigest())

raw = pd.read_csv(SRC, encoding="utf-8-sig", low_memory=False,
                  usecols=["Total fuel consumed (lifetime) (l)", "Total distance travelled (lifetime) (km)",
                           "Mk", "Cn", "Ft", "Ep (KW)"])
raw.columns = ["fuel", "distance", "make", "model", "fuel_type", "power"]
print(f"vans in the online file: {len(raw):,}")
for c in ("fuel", "distance", "power"):
    raw[c] = pd.to_numeric(raw[c], errors="coerce")
df = raw[raw["fuel_type"].astype(str).str.strip().str.lower().eq("diesel")].dropna(subset=["fuel", "distance", "power"])
df = df[df["distance"].between(DISTANCE_BANDS[0], DISTANCE_BANDS[-1]) & (df["fuel"] > 0) & df["power"].between(POWER_BANDS[0], POWER_BANDS[-1])]
df = df[(df["fuel"] / df["distance"] * 100).between(3, 40)]
print(f"diesel vans with 30-1,000 km, 40-250 kW and 3-40 L/100 km: {len(df):,}")

df["power_band"] = pd.cut(df["power"], POWER_BANDS, include_lowest=True)
df["distance_band"] = pd.cut(df["distance"], DISTANCE_BANDS, include_lowest=True)
sample = (df.groupby(["power_band", "distance_band"], observed=True, group_keys=False)
          .apply(lambda g: g.sample(min(PER_CELL, len(g)), random_state=SEED)))

eea = pd.DataFrame({
    "brand_model": (sample["make"].astype(str).str.split().str.join(" ") + " "
                    + sample["model"].astype(str).str.split().str.join(" ")).str.title(),
    "engine_code": "",
    "distance_km": sample["distance"].round(2),
    "engine_power_kw": sample["power"].round(0).astype(int),
    "fuel_type": "Diesel",
    "actual_fuel_consumption": sample["fuel"].round(4),
    "source": SOURCE,
}).sort_values(["engine_power_kw", "distance_km"])

current = pd.read_csv(OUT, dtype={"engine_code": str})
if "source" not in current.columns:
    current["source"] = "Fan & Song 2022"
current = current[current["source"] != SOURCE]
out = pd.concat([current, eea], ignore_index=True)
out.to_csv(OUT, index=False)
print(f"written {OUT}: {len(current):,} earlier records + {len(eea):,} EEA diesel vans = {len(out):,}")
print(eea.groupby(pd.cut(eea["engine_power_kw"], POWER_BANDS, include_lowest=True), observed=True).size().to_string())
