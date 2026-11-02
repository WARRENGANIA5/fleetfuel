"""Add diesel vans to data/supplementary_data.csv from

  European Environment Agency (2025). 2024 real-world CO2 emissions from cars and vans
  [Dataset]. https://doi.org/10.2909/13e6fad9-149c-4b86-9d83-cdf3569ccfee  (license CC BY 4.0)
  File: 2024_Vans_Raw.csv

Each row is one EU van's OBFCM reading: distance (km), fuel (L), fuel type and
engine power (kW). The Fan & Song data is all gasoline, so these add diesel.

Filter: diesel, 40-250 kW, 30-1,000 km, 3-40 L/100 km (49,390 rows). Shorter
distances are mostly new vans idling, so they're dropped. Re-running replaces
the EEA rows.

Usage: python data/add_eea_diesel_vans.py <2024_Vans_Raw.csv> data/supplementary_data.csv
"""
import hashlib
import sys

import pandas as pd

SRC, OUT = sys.argv[1], sys.argv[2]
SOURCE = "EEA 2024 (OBFCM)"
POWER_BANDS = [40, 60, 80, 100, 120, 140, 160, 250]      # kW
DISTANCE_BANDS = [30, 100, 300, 1000]                     # km

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

sample = df

# Clean up inconsistent make/model labels ("VOLKSWAGEN, VW", "FIAT DUCATO").
MAKES = ["Alfa Romeo", "Audi", "Citroen", "Dacia", "DS", "Fiat", "Ford", "Hyundai", "Ineos", "Isuzu",
         "Iveco", "Jeep", "Kia", "Land Rover", "MAN", "Mazda", "Mercedes-Benz", "Nissan", "Opel", "Peugeot",
         "Renault", "Seat", "Skoda", "SsangYong", "Toyota", "Volkswagen", "Volvo"]
UPPER_WORDS = {"MAN", "TGE", "DS", "HVM", "STX", "XL", "N1", "S&S", "4X4", "4WD", "AWD"}
TEXT_FIXES = {"\xa0": " ", "DOBLÃ’": "DOBLO", "FURG?N": "FURGON", "DI?SEL": "DIESEL"}


def tidy_text(text):
    text = str(text)
    for bad, good in TEXT_FIXES.items():
        text = text.replace(bad, good)
    return " ".join(text.replace(",", " ").replace(".", " ").split()).upper()


def make_name(raw):
    text = tidy_text(raw)
    if text.startswith("VW"):
        return "Volkswagen"
    for make in MAKES:
        if text.startswith(make.upper()):
            return make
    if not text or text[0].isdigit():
        return "Unknown"
    return " ".join(w.capitalize() for w in text.split("/")[0].replace("GMBH", "").replace("LTD", "")
                    .replace("COMMERCIALS", "").split())


def model_name(raw, make):
    if pd.isna(raw):
        return ""
    words = tidy_text(raw).split()
    for prefix in (make.upper().split(), ["VW"], ["VOLKSWAGEN"]):   # "FIAT DUCATO" -> "DUCATO"
        if words[:len(prefix)] == prefix and len(words) > len(prefix):
            words = words[len(prefix):]
    return " ".join(w if w in UPPER_WORDS or any(ch.isdigit() for ch in w) else w.capitalize() for w in words)


makes = sample["make"].map(make_name)
models = [model_name(m, mk) for m, mk in zip(sample["model"], makes)]

eea = pd.DataFrame({
    "brand_model": [f"{mk} {m}".strip() for mk, m in zip(makes, models)],
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
