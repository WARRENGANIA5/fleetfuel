# Supplementary dataset — source

`supplementary_data.csv` holds 2,000 real-world trips taken from this open online dataset:

> Fan, P., & Song, G. (2022). *Which factor contributes more to the fuel consumption gap between
> in-laboratory vs. real-world driving conditions? An independent component analysis* (Version 2)
> [Dataset]. Mendeley Data. https://doi.org/10.17632/jzjxcdn6k4.2

- **License:** CC BY 4.0 (free to use with citation).
- **Original data:** 385,158 trips of 395 gasoline passenger vehicles (15 models) in Beijing, China
  (file `Vehicle fuel consumption.csv`, SHA-256 `7ef46102c29d04ae83f382b37e6ee181e6a2ed003c89a801afc72a67cc2a9590`).
- **Sample:** 200 trips per vehicle model (fixed random seed 42), keeping only complete trips with
  1–1000 km, 1–1440 min, 5–130 km/h and 3–40 L/100 km.
- **Vehicles:** Sedan (Audi A6L, Honda Accord, Nissan Teana, Nissan Tiida, Volkswagen Magotan,
  Volkswagen Passat), SUV (Chevrolet Captiva, Hyundai ix35), Van (Buick GL8, Honda Odyssey);
  engine 1.6–2.5 L, model years 2011–2017, all gasoline.

## Variables

| Study variable | From the online dataset |
|---|---|
| distance_km | `tirp_distance` (m) ÷ 1000 |
| duration_minutes | `tirp_time` (s) ÷ 60 |
| avg_speed_kmh | distance ÷ duration |
| departure_time / departure_period | `tirp_start_time` |
| engine_displacement, year_model | `Model` (e.g. `…-2015-1.8T`) |
| vehicle_type | body style of the model |
| fuel_type | Gasoline |
| actual_fuel_consumption (L) | `fuel consumption (L)` |

Odometer, trip type, passenger/cargo load, route, road type and terrain are **not** in the online
dataset, so they are dropped during merging (Chapter I, Scope and Limitations).

During cleaning, outliers are removed with the IQR rule **within each source** (fleet records and
online trips separately), because the fleet's inter-campus trips and the online city trips have very
different typical fuel use.

## Rebuild

Download `Vehicle fuel consumption.csv` from the DOI above, then:

```
venv\Scripts\python.exe data\build_supplementary_dataset.py "Vehicle fuel consumption.csv" data\supplementary_data.csv
```

The previous made-up lookup table is kept as `supplementary_data.synthetic_lookup.csv`.
