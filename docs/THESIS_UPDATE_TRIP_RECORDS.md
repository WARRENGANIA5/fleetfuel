# Thesis update — Trip Records, automatic trip recording and the retrained model (October 30, 2026)

Text for Chapter III (Data and How the Project Will Work) and Scope and Limitations. It describes the
system as it now works; the figures come from the system and the trained model (`model/metrics.json`).

## 1. Trip Records data

The Trip Records module holds **7,589 trip records**:

| Part | Records | Source |
|---|---|---|
| Local trips (GSO Monthly Report of Official Travel, SFA 4714, January–June 2026) | 93 | Data gathering |
| Trips built from online datasets | 7,496 | European Environment Agency (2025), *2024 real-world CO2 emissions from cars and vans*, https://doi.org/10.2909/13e6fad9-149c-4b86-9d83-cdf3569ccfee (CC BY 4.0) |

For the 7,496 online trips, the **distance traveled (km)** and **fuel consumed (L)** are the values recorded by
the vehicles' on-board fuel consumption meters (OBFCM) in the EEA dataset, unchanged. The **vehicle** and the
**date of travel** were assigned by a fixed procedure (`data/build_trip_records_dataset.py`, random seed 42) that
follows the local trips:

1. **Vehicle match.** All nine fleet vehicles use diesel, so only diesel records are used. Each fleet vehicle
   receives records of vans whose engine power is within ±10 kW of its own (Vehicle Management), so the fuel use
   fits the vehicle's size (median L/100 km: L300 7.2; Revo and Crosswind 7.1–7.2; Nissan NV350 vans 9.7–9.8;
   Innova and Grandia 11.4; Hino bus 16.3).
2. **How often a vehicle travels.** As in the GSO report, a vehicle makes at most one trip a day. SFA 4714
   travels on 53% of days, as in its GSO report (0.53 trips a day). The other vehicles travel proportionally
   less, and the bus least. The share of trips by day of the week follows the GSO trips (Monday to Sunday:
   22, 20, 18, 15, 13, 9 and 3%). There are no trips on Philippine regular holidays.
3. **Distance.** Records of 30–400 km are drawn so their distances follow the GSO trips (GSO: 32–372 km, mean
   176 km; online trips: 30–400 km, mean 172 km).
4. **Dates.** Trips run in order from March 5, 2019 to October 29, 2026, and no vehicle has a trip before GSU
   acquired it. SFA 4714's online trips stop at December 31, 2025, because its 2026 trips are the GSO's own records.

**Acquisition dates of the fleet vehicles**

| Vehicle | Acquired | Basis |
|---|---|---|
| SJC 955 Isuzu Crosswind | May 12, 2023 | Donated by NTC Region VI (GSU news post, May 25, 2023, https://www.gsu.edu.ph/?p=8017) |
| SGF 810 Toyota Revo | May 25, 2023 | Donated by BFAR 6 (same post; the donation date is not given, so the posting date is used) |
| SFA 1741 Hino bus | May 7, 2025 | New university bus blessed (GSU news post, May 7, 2025) |
| SFA 1172 Toyota Hiace GL Grandia | March 5, 2019 (estimated) | 130 kW matches only the 2.8 L Hiace, sold in the Philippines from March 5, 2019 |
| SFA 1173 Toyota Innova | March 5, 2019 (estimated) | Plate number follows SFA 1172, so both were registered together |
| SFA 4712, 4713, 4714 Nissan NV350 Urvan | March 5, 2019 (estimated) | Plates come after SFA 1172/1173 in the same series |
| SEF 535 Mitsubishi L300 | before March 5, 2019 (estimated) | 51 kW is the 2.5 L non-turbo engine, sold before the 2019 Euro 4 model |

## 2. Automatic trip recording from fuel requests

Every Fuel Consumption Prediction (fuel request) adds its trip to Trip Records at once. The new trip has the
vehicle, the date of the request and the distance, and its fuel consumed is marked *Pending*. When the actual
fuel is recorded, either in Prediction History or by editing the trip, both records show the same value. If a
request is rejected, its pending trip is removed, because no trip took place. All users see these records
within seconds, on the office computer and online, because they share one Firebase Firestore database.

A trip is used for training only after its actual fuel is recorded. The model therefore never learns from its
own predictions.

## 3. Model training data and results

The model is trained on every trip record joined with its vehicle record by plate number, plus the other online
records (supplementary dataset: 50,508 gasoline trips from Fan & Song, 2022, https://doi.org/10.17632/jzjxcdn6k4.2,
and the remaining EEA diesel vans). Each online record is used only once.

| Data | Records after cleaning |
|---|---|
| Local GSO trips | 93 |
| Online trips in Trip Records | 7,194 |
| Other online records | 88,847 |
| **Total** (80% training / 20% testing) | **96,134** (76,907 / 19,227) |

Fitted equation (Fuel Type: 1 = gasoline, 0 = diesel):

**Fuel (L) = −1.8174 + 0.04036(Distance) + 0.03258(Engine Power) − 3.0161(Fuel Type) + 0.000503(Distance × Engine Power)**

| Measure | Value |
|---|---|
| R² (testing set) | 0.9502 |
| MAE | 2.51 L |
| RMSE | 4.84 L |
| 5-fold cross-validation R² | 0.951 ± 0.001 |
| R² / MAE on the 93 local GSO trips | 0.975 / 0.96 L |
| Highest VIF | 2.28 (no multicollinearity) |

## 4. Additions to Scope and Limitations

- **Online trips are not GSU trips.** In the 7,496 online trips, the distance and fuel consumed are real
  measurements of European diesel vans. Only the vehicle and the date were assigned, by the procedure in
  Section 1, so they show the model's behavior on realistic data, not the fleet's actual history.
- **Estimated acquisition dates.** Six vehicles' acquisition dates are estimates, the earliest dates the
  evidence allows. They should be replaced with the "date acquired" in the GSO property records (PPE Ledger
  Card or Property Acknowledgment Receipt) when available.
- **Local fuel figures follow an allocation rule.** The GSO report's fuel consumed is computed as distance
  ÷ 10 km/L, not measured.
- **Regression assumptions.** The Ramsey RESET (linearity), Durbin–Watson on the local trips (0.94,
  independence), Jarque–Bera (normality) and Breusch–Pagan (equal variance) tests are not passed. Standard
  errors are therefore reported as heteroskedasticity-robust (HC3), and the estimates should be read as an
  approximation.
- **Training environment.** The model was trained by running the project's Google Colab notebook
  (`colab/fuel_consumption_linear_regression_AUTO.ipynb`) with the same code and data.
