# Chapter IV — Results and Discussion (draft, November 9, 2026)

Draft text for Chapter IV. Every figure comes from the trained model (`model/metrics.json`), the cleaned dataset
(`data/cleaned_merged_dataset.csv`) and the charts in `reports/figures/`. The sections follow the specific
objectives of the study.

## 1. Data Collection

The researchers gathered three sources of data.

**Table 1. Collected records per source**

| Source | Records | Description |
|---|---|---|
| Monthly Report of Official Travel (GSO) | 93 | Official trips of SFA 4714, January–June 2026 |
| Vehicle records of the university fleet | 9 vehicles | Plate number, vehicle model, fuel type and engine power (kW) |
| Trip records from online datasets | 7,496 | Diesel van trips from the European Environment Agency (2025), matched to the fleet vehicles |
| Other online records (supplementary dataset) | 92,402 | 50,508 gasoline records (Fan & Song) and the other 41,894 diesel van records (EEA) |
| **Total trip records** | **99,991** | Each online record is used only once |

The 93 local trips cover distances of 32 to 372 km (mean 176 km) with a mean fuel consumption of 17.6 liters per
trip. Because the local records cover a single vehicle over six months, the online records widen the range of
distances and engine powers available to the model.

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
| Other online records (supplementary dataset) | 92,402 | 27,184 | 65,218 |
| **Total** | **99,991** | **34,471** | **65,520 (65.5%)** |

The IQR method removed 3,857 records. The other 61,663 records were outside the operating range of the university
fleet (diesel, 30 to 400 km, 51 to 177 kW), including every gasoline record. All 93 GSO records were kept. The final
modelling-ready dataset holds 34,471 diesel records. Fuel type was encoded as 0 for diesel, so it is the same in
every record, and the interaction term Distance × Engine Power was added.

**Table 3. Descriptive statistics of the final dataset**

| Variable | Mean | Std. Dev. | Minimum | Maximum |
|---|---|---|---|---|
| Distance traveled (km) | 151.36 | 92.17 | 30.00 | 400.00 |
| Engine power (kW) | 95.35 | 22.28 | 51.00 | 177.00 |
| Fuel consumed (L) | 14.24 | 8.73 | 1.90 | 96.10 |

## 3. Variable Selection

**Figure 2. Correlation heatmap** (`reports/figures/correlation_heatmap.png`)

Distance traveled has a strong positive correlation with fuel consumed (r = 0.88), confirming it as the main
predictor. Engine power has a weak positive correlation (r = 0.15). Fuel type has no correlation to report because
every record in the final dataset is diesel.

**Table 4. Variance Inflation Factor (VIF)** (`reports/figures/vif.png`)

| Predictor | VIF |
|---|---|
| Distance traveled | 1.03 |
| Engine power | 1.03 |
| Distance × Engine Power | 1.01 |

All VIF values are below the threshold of 5, so the predictors do not carry overlapping information. Distance and
engine power were mean-centered before forming the interaction term; this removes the collinearity between the
interaction and the predictors it is built from without changing any prediction.

## 4. Model Development

The dataset was split into 80 percent training (27,576 records) and 20 percent testing (6,895 records). The
Linear Regression model trained on the training set produced the following equation:

> ŷ = −1.7904 + 0.03263(Distance) + 0.03167(Engine Power) + 0.000573(Distance × Engine Power)

where ŷ is the predicted fuel consumed in liters, Distance is in kilometers and Engine Power is in kilowatts. Since
every record is diesel, the coefficient of Fuel Type is 0 and the term does not appear.

**Table 5. Regression coefficients** (standard errors are heteroskedasticity-robust, HC3)

| Term | Coefficient (centered) | Std. Error | p-value |
|---|---|---|---|
| Intercept | 14.46 | 0.0192 | < 0.001 |
| Distance traveled | 0.0873 | 0.00028 | < 0.001 |
| Engine power | 0.1186 | 0.00101 | < 0.001 |
| Distance × Engine Power | 0.000573 | 0.0000144 | < 0.001 |

All terms are statistically significant at α = 0.05. At the average engine power, each additional kilometer
adds about 0.087 liters (around 8.7 L per 100 km). Each additional kilowatt adds about 0.119 liters at the average
distance. The positive interaction term shows that larger engines use more fuel per kilometer, so the gap between
small and large vehicles grows on longer trips.

For example, a 176 km trip of SFA 4714 (diesel, 95 kW) gives:
ŷ = −1.7904 + 0.03263(176) + 0.03167(95) + 0.000573(176 × 95) ≈ **16.55 liters**,
close to the 17.6-liter average of its recorded trips.

## 5. Model Evaluation

**Table 6. Performance on the testing set**

| Metric | Value |
|---|---|
| R-Squared (R²) | 0.8877 |
| Mean Absolute Error (MAE) | 1.9759 L |
| Root Mean Squared Error (RMSE) | 2.8900 L |

The model explains 88.77 percent of the variation in fuel consumed. On average, a prediction differs from the
actual fuel consumed by 1.98 liters. The RMSE of 2.89 liters is higher than the MAE, which shows that some trips
have larger errors than the typical trip.

**Table 7. 5-fold cross-validation**

| Metric | Mean | Std. Dev. |
|---|---|---|
| R² | 0.8879 | 0.0015 |
| MAE | 1.993 L | 0.012 |
| RMSE | 2.922 L | 0.030 |

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
| Linearity | Ramsey RESET | F = 38.99, p < 0.001 | p > 0.05 | No |
| Independence of errors | Durbin-Watson (93 local trips by date) | 0.784 | 1.5 to 2.5 | No |
| Normality of errors | Jarque-Bera | skew 1.17, kurtosis 12.23, p < 0.001 | p > 0.05 | No |
| Equal variance | Breusch-Pagan | 3,074.54, p < 0.001 | p > 0.05 | No |
| No multicollinearity | VIF | highest 1.03 | ≤ 5 | Yes |

The residuals are centered on zero, but their spread grows with the predicted fuel, and the distribution has a
sharp peak with long tails. With 34,471 records, these formal tests detect even small departures, so the
rejections partly reflect the sample size. Still, the residual plot confirms unequal variance, so
heteroskedasticity-robust (HC3) standard errors were used for the coefficients in Table 5. The RESET result
agrees with the limitation stated in Chapter I that a Linear Regression model cannot fully capture nonlinear
patterns. The Durbin-Watson value of 0.784 shows positive autocorrelation among the local trips: consecutive
trips of SFA 4714 tend to be over- or under-predicted together. Since the local fuel figures follow a fixed rule of
one liter per 10 kilometers, these residuals depend only on the trip distance, so the statistic reflects the order of the distances traveled. These departures
affect the confidence intervals of the coefficients more than the predictions themselves, and the stable
cross-validation results show that the predictive accuracy holds.

## 7. Integration and Implementation of the Web Application

The trained model was saved with Joblib and integrated into the Flask web application, the GSU FleetFuel Fuel
Consumption Prediction System. The staff log in, select a vehicle and enter the trip distance. The system retrieves
the engine power and fuel type of the selected vehicle from its records in Firebase Firestore, passes the values
to the model and displays the predicted fuel consumption in liters. A trip outside 30 to 400 km receives a warning
that the estimate is outside the range the model was trained on. Each prediction is stored in the
Prediction History, where the administrator compares the predicted figure with the fuel request before approving it, and the actual fuel consumed is
recorded after the trip. The Model Performance page shows the metrics, coefficients and charts
reported in this chapter. The application is deployed online at https://gsu-fleetfuel.vercel.app.

## 8. Summary of Results

- The final dataset holds 34,471 diesel records within the fleet's operating range; all 93 local trips were kept.
- Distance traveled is the strongest predictor of fuel consumed (r = 0.88); all VIF values are below 5.
- The Linear Regression model reached R² = 0.8877, MAE = 1.98 L and RMSE = 2.89 L on the testing set.
- 5-fold cross-validation gave a mean R² of 0.8879 (standard deviation 0.0015), confirming a stable model.
- The residuals show unequal variance, non-normality and autocorrelation among the local trips, so robust
  standard errors were used; multicollinearity is not a problem.
- The model is integrated into a web application that gives the General Services Office and motorpool staff a
  per-trip fuel estimate before approving a fuel request.
