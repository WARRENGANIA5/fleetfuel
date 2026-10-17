# Supplementary dataset — source

`supplementary_data.csv` holds 6,000 real-world trips taken from this open online dataset:

> Fan, P., & Song, G. (2022). *Which factor contributes more to the fuel consumption gap between
> in-laboratory vs. real-world driving conditions? An independent component analysis* (Version 2)
> [Dataset]. Mendeley Data. https://doi.org/10.17632/jzjxcdn6k4.2

- **License:** CC BY 4.0 (free to use with citation).
- **Original data:** 385,158 trips of 395 gasoline passenger vehicles (15 models) in Beijing, China
  (file `Vehicle fuel consumption.csv`, SHA-256 `7ef46102c29d04ae83f382b37e6ee181e6a2ed003c89a801afc72a67cc2a9590`).
- **Sample:** 150 trips per vehicle model in each of four distance bands — 1–10, 10–30, 30–100 and
  100–1000 km — (fixed random seed 42), keeping only complete trips with 1–1000 km, 1–1440 min,
  5–130 km/h and 3–40 L/100 km. The bands make the training data cover the long inter-campus and
  provincial trips the fleet makes; a plain random sample is almost all short city trips (about 20 km).
  Result: 1,500 trips per band; 3,600 sedan, 1,200 SUV and 1,200 van trips; 1.5–690 km.
- **Vehicles:** Sedan (Audi A6L, Honda Accord, Nissan Teana, Nissan Tiida, Volkswagen Magotan,
  Volkswagen Passat), SUV (Chevrolet Captiva, Hyundai ix35), Van (Buick GL8, Honda Odyssey);
  engine 1.6–2.5 L, model years 2011–2017, all gasoline.

## Variables

The file has the same variables as the local trip records merged with the vehicle records:

| Study variable | From the online dataset |
|---|---|
| distance_km | `tirp_distance` (m) ÷ 1000 |
| engine_power_kw | rated power of the vehicle's engine code, from `Vehicle information.xlsx` of the same dataset |
| fuel_type | Gasoline (all online vehicles; encoded 1) |
| actual_fuel_consumption (L) | `fuel consumption (L)` |

`brand_model` and `engine_code` are kept for reference only.

During cleaning, records with missing values or zero distance are dropped, and outliers are removed with
the IQR rule on **fuel used per 100 km within each engine-power group**, so a large vehicle is compared
only with vehicles of similar size. Fuel per 100 km rather than total liters, because a long trip
naturally uses more fuel and is not an outlier.

## Rebuild

Download `Vehicle fuel consumption.csv` from the DOI above, then:

```
venv\Scripts\python.exe data\build_supplementary_dataset.py "Vehicle fuel consumption.csv" data\supplementary_data.csv
```
