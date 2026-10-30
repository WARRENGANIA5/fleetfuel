# Chapter IV — Results and Discussion (draft, October 30, 2026)

Draft text for Chapter IV. Every figure comes from the trained model (`model/metrics.json`, model version
v20261030104247), the cleaned dataset (`data/cleaned_merged_dataset.csv`) and the charts in `reports/figures/`.
The sections follow the specific objectives of the study.

## 1. Data Collection

The researchers gathered three sources of data.

**Table 1. Collected records per source**

| Source | Records | Description |
|---|---|---|
| Monthly Report of Official Travel (GSO) | 93 | Official trips of SFA 4714, January–June 2026 |
| Vehicle records of the university fleet | 9 vehicles | Plate number, vehicle model, fuel type and engine power (kW) |
| Trip records from online datasets | 7,496 | Diesel van trips from the European Environment Agency (2025), matched to the fleet vehicles |
| Supplementary dataset | 99,898 | 50,508 gasoline records (Fan & Song) and 49,390 diesel van records (EEA) |
| **Total trip records** | **107,487** | |

The 93 local trips cover distances of 32 to 372 km (mean 176 km) with a mean fuel consumption of 17.6 liters per
trip. Because the local records cover a single vehicle over six months, the supplementary records widen the
range of distances, engine powers and fuel types available to the model.

## 2. Data Preprocessing

The trip records and vehicle records were merged using the plate number, then combined with the supplementary
dataset using their shared variables. Each record kept a label of its source. Records with missing values or zero
distance were removed, followed by extreme outliers using the Interquartile Range (IQR) method on the fuel used
per 100 km within each engine-power group.

**Table 2. Records before and after preprocessing**

| Source | Before | After | Removed |
|---|---|---|---|
| Local trips (GSO) | 93 | 93 | 0 |
| Online trip records | 7,496 | 7,194 | 302 |
| Supplementary dataset | 99,898 | 88,847 | 11,051 |
| **Total** | **107,487** | **96,134** | **11,353 (10.6%)** |

None of the local trips fell outside the IQR bounds, so all 93 GSO records were kept. The final
modelling-ready dataset holds 96,134 records: 46,937 diesel and 49,197 gasoline. Fuel type was encoded as
1 for gasoline and 0 for diesel, and the interaction term Distance × Engine Power was added.

**Table 3. Descriptive statistics of the final dataset**

| Variable | Mean | Std. Dev. | Minimum | Maximum |
|---|---|---|---|---|
| Distance traveled (km) | 166.79 | 226.01 | 1.50 | 1,000.00 |
| Engine power (kW) | 110.67 | 22.63 | 51.00 | 221.00 |
| Fuel type (1 = Gasoline) | 0.51 | 0.50 | 0 | 1 |
| Fuel consumed (L) | 15.42 | 21.73 | 0.10 | 210.70 |

## 3. Variable Selection

**Figure 2. Correlation heatmap** (`reports/figures/correlation_heatmap.png`)

Distance traveled has a very strong positive correlation with fuel consumed (r = 0.96), confirming it as the main
predictor. Fuel type has a moderate negative correlation (r = −0.54), and engine power a weak negative
correlation (r = −0.22). The negative sign of engine power does not mean that stronger engines use less fuel.
It comes from the composition of the data: the gasoline records have higher engine power (104–147 kW) but mostly
shorter distances, while the diesel records include the long trips. Once distance and fuel type are held
constant in the regression, engine power has a positive effect (Section 4).

**Table 4. Variance Inflation Factor (VIF)** (`reports/figures/vif.png`)

| Predictor | VIF |
|---|---|
| Distance traveled | 1.64 |
| Engine power | 1.76 |
| Fuel type | 2.28 |
| Distance × Engine Power | 1.25 |

All VIF values are below the threshold of 5, so the predictors do not carry overlapping information. Distance and
engine power were mean-centered before forming the interaction term; this removes the collinearity between the
interaction and the predictors it is built from without changing any prediction.

## 4. Model Development

The dataset was split into 80 percent training (76,907 records) and 20 percent testing (19,227 records). The
Linear Regression model trained on the training set produced the following equation:

> ŷ = −1.8174 + 0.04036(Distance) + 0.03258(Engine Power) − 3.0161(Fuel Type) + 0.000503(Distance × Engine Power)

where ŷ is the predicted fuel consumed in liters, Distance is in kilometers, Engine Power is in kilowatts and Fuel
Type is 1 for gasoline and 0 for diesel.

**Table 5. Regression coefficients** (standard errors are heteroskedasticity-robust, HC3)

| Term | Coefficient (centered) | Std. Error | p-value |
|---|---|---|---|
| Intercept | 17.82 | 0.0252 | < 0.001 |
| Distance traveled | 0.09602 | 0.00025 | < 0.001 |
| Engine power | 0.1166 | 0.00083 | < 0.001 |
| Fuel type | −3.016 | 0.0433 | < 0.001 |
| Distance × Engine Power | 0.000503 | 0.0000086 | < 0.001 |

All terms are statistically significant at α = 0.05. At the average engine power, each additional kilometer
adds about 0.096 liters (around 9.6 L per 100 km). Each additional kilowatt adds about 0.117 liters at the average
distance. The positive interaction term shows that larger engines use more fuel per kilometer, so the gap between
small and large vehicles grows on longer trips. Holding distance and engine power constant, gasoline trips use
about 3.02 liters less than diesel trips in this dataset.

For example, a 176 km trip of SFA 4714 (diesel, 95 kW) gives:
ŷ = −1.8174 + 0.04036(176) + 0.03258(95) − 3.0161(0) + 0.000503(176 × 95) ≈ **16.79 liters**,
close to the 17.6-liter average of its recorded trips.

## 5. Model Evaluation

**Table 6. Performance on the testing set**

| Metric | Value |
|---|---|
| R-Squared (R²) | 0.9502 |
| Mean Absolute Error (MAE) | 2.5137 L |
| Root Mean Squared Error (RMSE) | 4.8378 L |

The model explains 95.02 percent of the variation in fuel consumed. On average, a prediction differs from the
actual fuel consumed by 2.51 liters. The RMSE of 4.84 liters is almost twice the MAE, which shows that a small
number of trips, mostly the long trips and the larger vehicles, have larger errors than the typical trip.

**Table 7. 5-fold cross-validation**

| Metric | Mean | Std. Dev. |
|---|---|---|
| R² | 0.9510 | 0.0008 |
| MAE | 2.503 L | 0.018 |
| RMSE | 4.810 L | 0.035 |

**Figure 3. Cross-validation R² per fold** (`reports/figures/cv_r2_scores.png`)

The cross-validation results are almost identical to the testing-set results, with very small standard
deviations. The model gives the same level of accuracy on every partition of the data, so the result does not
depend on a lucky train-test split.

**Figure 4. Actual versus predicted fuel consumption** (`reports/figures/actual_vs_predicted.png`)

The points lie close to the line of perfect prediction for most trips, and spread out more for the high fuel
values.

## 6. Assumption Checks

**Figure 5. Residual plot** (`reports/figures/residual_plot.png`)
**Figure 6. Histogram of residuals** (`reports/figures/residual_histogram.png`)
**Figure 7. Q-Q plot of residuals** (`reports/figures/residual_qq_plot.png`)

**Table 8. Assumption tests**

| Assumption | Test | Result | Rule | Met? |
|---|---|---|---|---|
| Linearity | Ramsey RESET | F = 1,024.35, p < 0.001 | p > 0.05 | No |
| Independence of errors | Durbin-Watson (93 local trips by date) | 0.936 | 1.5 to 2.5 | No |
| Normality of errors | Jarque-Bera | skew 2.21, kurtosis 28.70, p < 0.001 | p > 0.05 | No |
| Equal variance | Breusch-Pagan | 13,776.99, p < 0.001 | p > 0.05 | No |
| No multicollinearity | VIF | highest 2.28 | ≤ 5 | Yes |

The residuals are centered on zero, but their spread grows with the predicted fuel, and the distribution has a
sharp peak with long tails. With 96,134 records, these formal tests detect even small departures, so the
rejections partly reflect the sample size. Still, the residual plot confirms unequal variance, so
heteroskedasticity-robust (HC3) standard errors were used for the coefficients in Table 5. The RESET result
agrees with the limitation stated in Chapter I that a Linear Regression model cannot fully capture nonlinear
patterns. The Durbin-Watson value of 0.936 shows positive autocorrelation among the local trips: consecutive
trips of SFA 4714 tend to be over- or under-predicted together, likely because of routes and conditions the
records do not capture (speed, load, road condition). These departures affect the confidence intervals of the
coefficients more than the predictions themselves, and the stable cross-validation results show that the
predictive accuracy holds.

## 7. Integration and Implementation of the Web Application

The trained model was saved with Joblib and integrated into the Flask web application, the GSU FleetFuel Fuel
Consumption Prediction System. The staff log in, select a vehicle and enter the trip distance. The system retrieves
the engine power and fuel type of the selected vehicle from its records in Firebase Firestore, passes the values
to the model and displays the predicted fuel consumption in liters. Each prediction is stored in the Prediction
History, where the administrator compares the predicted figure with the fuel request before approving it and
later records the actual fuel consumed. The Model Performance page shows the metrics, coefficients and charts
reported in this chapter. The application is deployed online at https://gsu-fleetfuel.vercel.app.

## 8. Summary of Results

- The final dataset holds 96,134 records after removing 11,353 records (10.6%) with missing values, zero distance or
  extreme fuel use; all 93 local trips were kept.
- Distance traveled is the strongest predictor of fuel consumed (r = 0.96); all VIF values are below 5.
- The Linear Regression model reached R² = 0.9502, MAE = 2.51 L and RMSE = 4.84 L on the testing set.
- 5-fold cross-validation gave a mean R² of 0.951 (standard deviation 0.0008), confirming a stable model.
- The residuals show unequal variance, non-normality and autocorrelation among the local trips, so robust
  standard errors were used; multicollinearity is not a problem.
- The model is integrated into a web application that gives the General Services Office and motorpool staff a
  per-trip fuel estimate before approving a fuel request.
