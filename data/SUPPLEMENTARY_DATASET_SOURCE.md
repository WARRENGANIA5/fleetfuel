# Supplementary dataset — sources

`supplementary_data.csv` combines two open online datasets (column `source`): 50,508 gasoline trips
and 49,390 diesel vans, **99,898 records**. With the 93 local trip records and the 9 fleet vehicles the
study has **100,000 records**.

## 1. Gasoline trips — Fan & Song (2022)

50,508 real-world trips taken from:

> Fan, P., & Song, G. (2022). *Which factor contributes more to the fuel consumption gap between
> in-laboratory vs. real-world driving conditions? An independent component analysis* (Version 2)
> [Dataset]. Mendeley Data. https://doi.org/10.17632/jzjxcdn6k4.2

- **License:** CC BY 4.0 (free to use with citation).
- **Original data:** 385,158 trips of 395 gasoline passenger vehicles (15 models) in Beijing, China
  (file `Vehicle fuel consumption.csv`, SHA-256 `7ef46102c29d04ae83f382b37e6ee181e6a2ed003c89a801afc72a67cc2a9590`).
- **Sample:** 50,508 trips spread evenly over the 10 vehicle models and four distance bands — 1–10,
  10–30, 30–100 and 100–1000 km — (fixed random seed 42), keeping only complete trips with 1–1000 km,
  1–1440 min, 5–130 km/h and 3–40 L/100 km. Every model × band gets the same number of trips (about
  1,440); where the dataset has fewer long trips than that, all of them are taken. The bands make the
  training data cover the long inter-campus and provincial trips the fleet makes; a plain random sample
  is almost all short city trips (about 20 km). Result: 14,412 / 14,417 / 13,692 / 7,987 trips per band;
  1.5–717 km.
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
- **File:** 1,139,902 vans, SHA-256 `4bf949848c065bd5b8ae9f551561856169be35faa8482e540d0e99d56fde0c81`.
- **Sample:** every diesel van with 40–250 kW whose recorded distance is within the fleet's trip range
  (30–1,000 km; the local trips are 32–372 km) and 3–40 L/100 km — 49,390 vans, so about half of the
  supplementary records are diesel, like the fleet.
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

## Trip Records page — `trip_records_dataset.csv`

Online records are also shown on the **Trip Records** page as trips of the fleet vehicles (built by
`build_trip_records_dataset.py`), used the way the GSO's own trips show the fleet travels, so with the
93 GSO trips the page lists **7,589 trip records** (7,496 online):

- **How often**: from the GSO trips of SFA 4714 (Jan–Jun 2026): at most one trip a vehicle a day, on
  about half of the days, mostly Monday to Thursday (by weekday: 22 / 20 / 18 / 15 / 13 / 9 / 3 %).
  SFA 4714 travels as often as in the GSO reports (0.53 trips a day); the less-used vehicles less often.
- **No trips on Philippine regular holidays** (New Year, Holy Thursday and Good Friday, April 9, May 1,
  June 12, National Heroes Day, November 30, December 25 and 30).
- **Distance Traveled (km) and Fuel Consumed (L)**: unchanged from the online datasets (rounded to
  0.01). All fleet vehicles are diesel, so only the EEA diesel vans are used, each vehicle getting vans
  whose engine power is within ±10 kW of its own (Vehicle Management), so the fuel use fits the vehicle
  (median L/100 km: L300 7.2, Revo/Crosswind 7.1–7.2, Nissan Vans 9.7–9.8, Innova/Grandia 11.4,
  Hino Bus 16.3). Distances of 30–400 km are drawn like the GSO trips' (GSO mean 176 km; online
  172 km). The other online records are not used on this page.
- **Date of Travel**: in order from 2019-03-05 to 2026-10-29; a vehicle has no trips before GSU acquired
  it, and SFA 4714's online trips stop before 2026 (its 2026 trips are the GSO reports).
- **Vehicle**: one of the 9 vehicles of Vehicle Management that GSU already had on that date, drawn at
  random (seed 42) with a different share per vehicle (vans and Innova most, bus least). Acquisition dates
  (`ACQUIRED` in the script):
  - published by GSU: Isuzu Crosswind SJC 955 donated by NTC Region VI on 2023-05-12, Toyota Revo SGF 810
    donated by BFAR 6, announced 2023-05-25 (https://www.gsu.edu.ph/?p=8017); new university bus SFA 1741,
    blessed 2025-05-07 (gsu.edu.ph news);
  - **estimated** (earliest possible date, to be replaced with the GSO property records' "date acquired"):
    Grandia SFA 1172 — 130 kW is the 2.8 Hiace sold in the Philippines from 2019-03-05; Innova SFA 1173 —
    plate follows SFA 1172, so registered with it; Nissan NV350 vans SFA 4712–4714 (launched 2015-06-15) —
    plates come after SFA 1172/1173; L300 SEF 535 — old 2.5 non-turbo, sold before the 2019 Euro 4 model,
    so already GSU's by 2019-03-05.
- `source` and `source_vehicle` keep where each record came from; the administrator edits and deletes
  them on the page like the other trips (this changes the file; rebuilding it undoes those changes).

They are kept in this file, not in Firestore (saves the free plan's daily reads and writes).

**Training (since 2026-10-30):** the model is trained on every trip of Trip Records, merged with the vehicle
records by plate number (`data_source` "system" = the 93 GSO trips, "trip_records_online" = the 7,496 online
trips, with their vehicle's engine power, at most 10 kW from the source van's), plus the 92,402 other online
records ("supplementary"). Each online record is used once (`source_row` links a trip to its row in
`supplementary_data.csv`, which training then leaves out): 99,991 records, 96,134 after cleaning.
The local-trip checks (Durbin-Watson, local R²) use only the GSO trips. `python colab/make_colab_files.py`
refreshes the Colab files.
