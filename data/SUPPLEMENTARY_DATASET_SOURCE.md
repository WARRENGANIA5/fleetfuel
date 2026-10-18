# Supplementary dataset — sources

`supplementary_data.csv` combines two open online datasets (column `source`).

## 1. Gasoline trips — Fan & Song (2022)

6,000 real-world trips taken from:

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

## 2. Diesel vans — European Environment Agency (2024)

> European Environment Agency (2025). *2024 real-world CO2 emissions from cars and vans* [Dataset].
> https://doi.org/10.2909/13e6fad9-149c-4b86-9d83-cdf3569ccfee — file `2024_Vans_Raw.csv`

- **License:** CC BY 4.0 (free to use with citation).
- **Original data:** one row per van in circulation in the EU, read from the vehicle's on-board fuel
  consumption meter (OBFCM): total distance travelled (km), total fuel consumed (L), fuel type and
  engine power Ep (kW).
- **Why:** the Fan & Song trips are all gasoline (104–147 kW) and the local trips come from one diesel
  van (95 kW), so without diesel records of other engine sizes the model cannot learn how engine power
  changes the fuel use of the fleet's diesel vehicles (51–177 kW).
- **Sample:** diesel vans with 40–250 kW whose recorded distance is within the fleet's trip range
  (30–1,000 km; the local trips are 32–372 km) and 3–40 L/100 km; 60 vans from every engine-power band
  (40–60, 60–80, …, 160–250 kW) and distance band (30–100, 100–300, 300–1,000 km), fixed random seed 42.
- **Why not shorter distances:** vans with under 30 km are brand new; their few kilometres are mostly
  warm-up and idling (median about 20 L/100 km), not trips. Including them made the model under-predict
  the local trips.

## Variables

The file has the same variables as the local trip records merged with the vehicle records:

| Study variable | From the online dataset |
|---|---|
| distance_km | Fan & Song: `tirp_distance` (m) ÷ 1000 · EEA: `Total distance travelled (lifetime) (km)` |
| engine_power_kw | Fan & Song: rated power of the engine code (`Vehicle information.xlsx`) · EEA: `Ep (KW)` |
| fuel_type | Fan & Song: Gasoline (encoded 1) · EEA: Diesel (encoded 0) |
| actual_fuel_consumption (L) | Fan & Song: `fuel consumption (L)` · EEA: `Total fuel consumed (lifetime) (l)` |

`brand_model`, `engine_code` and `source` are kept for reference only.

During cleaning, records with missing values or zero distance are dropped, and outliers are removed with
the IQR rule on **fuel used per 100 km within each engine-power group**, so a large vehicle is compared
only with vehicles of similar size. Fuel per 100 km rather than total liters, because a long trip
naturally uses more fuel and is not an outlier.

## Rebuild

Download `Vehicle fuel consumption.csv` (Fan & Song DOI) and `2024_Vans_Raw.csv` (EEA DOI), then:

```
venv\Scripts\python.exe data\build_supplementary_dataset.py "Vehicle fuel consumption.csv" data\supplementary_data.csv
venv\Scripts\python.exe data\add_eea_diesel_vans.py 2024_Vans_Raw.csv data\supplementary_data.csv
```
