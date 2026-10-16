"""
Synthetic historical fleet dataset generator.

Guimaras State University's General Services Office does not yet have a
digitized historical trip/fuel logbook, so this script produces a
realistic, physically-consistent CORPUS OF TRAINING RECORDS that stands
in for that collection until real logbook data is digitized and
substituted (simply replace data/historical_fleet_data.csv with the real
export -- the column names must match).

IMPORTANT: this script only builds training DATA. It does not compute
fuel consumption at prediction time -- that job belongs entirely to the
Linear Regression model trained in model/train_model.py. The formula
below is used solely to make the synthetic rows internally consistent
(e.g. a mountainous, heavily loaded, old diesel truck should plausibly
consume more fuel than a light sedan on a flat paved road), the same way
a thesis writer would describe expected relationships in Chapter 3.
"""
import numpy as np
import pandas as pd
import os

RNG = np.random.default_rng(42)

VEHICLES = [
    # vehicle_type, brand_model, engine_displacement(L), fuel_type, baseline L/100km, year range
    ("Sedan", "Toyota Vios", 1.5, "Gasoline", 6.5),
    ("Sedan", "Honda City", 1.5, "Gasoline", 6.3),
    ("SUV", "Toyota Fortuner", 2.4, "Diesel", 8.5),
    ("SUV", "Mitsubishi Montero Sport", 2.4, "Diesel", 8.7),
    ("Van", "Toyota Hiace", 2.8, "Diesel", 9.8),
    ("Van", "Nissan Urvan", 2.5, "Diesel", 9.5),
    ("Pickup Truck", "Toyota Hilux", 2.4, "Diesel", 8.9),
    ("Pickup Truck", "Ford Ranger", 2.2, "Diesel", 8.6),
    ("Service Bus", "Isuzu Forward", 5.2, "Diesel", 16.5),
    ("Dump Truck", "Isuzu Elf", 4.6, "Diesel", 15.2),
    ("Motorcycle", "Honda XRM 125", 0.125, "Gasoline", 2.1),
]

ROUTES = [
    "Jordan - San Miguel", "Buenavista - Jordan", "Jordan - Nueva Valencia",
    "San Lorenzo - Jordan", "Jordan - Sibunag", "Capitol - Buenavista Port",
    "Jordan - Iloilo City (via ferry landing)", "Jordan - San Lorenzo Circumferential",
    "Buenavista - Nueva Valencia", "Jordan - Alaguisoc", "Campus - Jordan Port",
    "Campus - Buenavista Campus", "Jordan - Sibunag Terminal", "Nueva Valencia - Sibunag",
]

TRIP_TYPES = ["Official Business", "Errand", "Hauling", "Airport Transfer", "Field Visit", "Other"]
ROAD_TYPES = ["Paved", "Unpaved", "Mixed"]
TERRAINS = ["Flat", "Hilly", "Mountainous"]

TERRAIN_FACTOR = {"Flat": 1.00, "Hilly": 1.18, "Mountainous": 1.38}
ROAD_FACTOR = {"Paved": 1.00, "Mixed": 1.10, "Unpaved": 1.25}
TRIP_TYPE_FACTOR = {
    "Official Business": 1.00, "Errand": 0.95, "Hauling": 1.25,
    "Airport Transfer": 1.05, "Field Visit": 1.10, "Other": 1.00,
}


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


def speed_factor(avg_speed):
    # U-shaped: inefficient at very low (idling/traffic) and very high (aero drag) speeds
    optimal = 55.0
    return 1.0 + 0.00035 * (avg_speed - optimal) ** 2


def age_factor(year_model, current_year=2026):
    age = max(0, current_year - year_model)
    return 1.0 + min(age, 20) * 0.012


def load_factor(load_kg, vehicle_type):
    capacity = {"Motorcycle": 150, "Sedan": 400, "SUV": 500, "Pickup Truck": 800,
                "Van": 1200, "Service Bus": 2500, "Dump Truck": 4000}[vehicle_type]
    ratio = min(load_kg / capacity, 1.5)
    return 1.0 + ratio * 0.22


def generate(n_rows=1500):
    rows = []
    for i in range(n_rows):
        v_type, brand, disp, fuel, base_rate = VEHICLES[RNG.integers(0, len(VEHICLES))]
        year_model = int(RNG.integers(2008, 2026))
        distance_km = float(np.round(RNG.uniform(3, 180), 1))
        avg_speed = float(np.round(RNG.uniform(18, 95), 1))
        duration_minutes = float(np.round((distance_km / avg_speed) * 60 * RNG.uniform(0.95, 1.15), 1))
        trip_type = TRIP_TYPES[RNG.integers(0, len(TRIP_TYPES))]
        road_type = ROAD_TYPES[RNG.integers(0, len(ROAD_TYPES))]
        terrain = TERRAINS[RNG.integers(0, len(TERRAINS))]
        route = ROUTES[RNG.integers(0, len(ROUTES))]
        hour = int(RNG.integers(5, 22))
        departure_time = f"{hour:02d}:{int(RNG.integers(0,60)):02d}:00"

        max_load = {"Motorcycle": 150, "Sedan": 400, "SUV": 500, "Pickup Truck": 800,
                    "Van": 1200, "Service Bus": 2500, "Dump Truck": 4000}[v_type]
        load_kg = float(np.round(RNG.uniform(0, max_load), 1))

        odometer_reading = float(np.round(RNG.uniform(5000, 180000), 1))

        rate_per_100km = (
            base_rate
            * TERRAIN_FACTOR[terrain]
            * ROAD_FACTOR[road_type]
            * TRIP_TYPE_FACTOR[trip_type]
            * speed_factor(avg_speed)
            * age_factor(year_model)
            * load_factor(load_kg, v_type)
        )
        noise = RNG.normal(1.0, 0.05)
        actual_fuel_consumption = max(0.3, round((distance_km / 100.0) * rate_per_100km * noise, 2))

        rows.append({
            "vehicle_type": v_type,
            "brand_model": brand,
            "engine_displacement": disp,
            "fuel_type": fuel,
            "year_model": year_model,
            "odometer_reading": odometer_reading,
            "distance_km": distance_km,
            "duration_minutes": duration_minutes,
            "avg_speed_kmh": avg_speed,
            "trip_type": trip_type,
            "departure_time": departure_time,
            "departure_period": departure_period(hour),
            "passenger_cargo_load_kg": load_kg,
            "route": route,
            "road_type": road_type,
            "terrain_classification": terrain,
            "actual_fuel_consumption": actual_fuel_consumption,
        })

    return pd.DataFrame(rows)


def generate_supplementary():
    """Manufacturer-rated baseline fuel efficiency lookup (Supplementary Dataset)."""
    seen = {}
    for v_type, brand, disp, fuel, base_rate in VEHICLES:
        seen[v_type] = (fuel, base_rate)
    supp_rows = [
        {"vehicle_type": v_type, "rated_fuel_type": fuel, "rated_efficiency_l_per_100km": rate}
        for v_type, (fuel, rate) in seen.items()
    ]
    return pd.DataFrame(supp_rows)


if __name__ == "__main__":
    out_dir = os.path.dirname(os.path.abspath(__file__))
    df = generate(1500)
    df.to_csv(os.path.join(out_dir, "historical_fleet_data.csv"), index=False)
    supp = generate_supplementary()
    supp.to_csv(os.path.join(out_dir, "supplementary_data.csv"), index=False)
    # Fingerprint the synthetic files so the web app can label results as demo data.
    import hashlib, json
    def _sha(name):
        with open(os.path.join(out_dir, name), "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()
    with open(os.path.join(out_dir, "dataset_info.json"), "w", encoding="utf-8") as f:
        json.dump({"note": "SHA-256 fingerprints of the SYNTHETIC demo datasets; the app labels results as demo data "
                           "while the CSV files still match them.",
                   "synthetic_sha256": {n: _sha(n) for n in ("historical_fleet_data.csv", "supplementary_data.csv")}},
                  f, indent=2)
    print(f"Generated {len(df)} historical trip/fuel records -> historical_fleet_data.csv")
    print(f"Generated {len(supp)} supplementary vehicle efficiency ratings -> supplementary_data.csv")
