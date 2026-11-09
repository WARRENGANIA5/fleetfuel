# Chapter III — code for the 14 [CODE] placeholders

Chapter III ("How the Project will work") has 14 `[CODE]` placeholders. Below is the code for each, in the same
order as they appear in the manuscript. The snippets are shortened from the Google Colab notebook used to train
the model (`colab/fuel_consumption_linear_regression.ipynb`) and `model/preprocess.py`, `model/diagnostics.py`.

## 1. Merging the trip and vehicle records, labeling the source

*After: "...each record is labeled according to its source to identify the local trips after merging."*

```python
import pandas as pd

trips = pd.read_csv("trip_records.csv")
vehicles = pd.read_csv("vehicle_records.csv")
supplementary = pd.read_csv("supplementary_data.csv")

# Merge the trip records and vehicle records using the plate number
vehicles = vehicles[["plate_number", "fuel_type", "engine_power_kw"]]
local = trips.merge(vehicles, on="plate_number", how="left")

# Label each record by its source, then combine on the shared variables
local["data_source"] = local["source"].map(lambda s: "local" if pd.isna(s) else "trip_records_online")
supplementary["data_source"] = "supplementary"
df = pd.concat([local, supplementary], ignore_index=True)
```

## 2. Removing missing values and zero distance

*After: "The records with missing values or zero distance are removed."*

```python
df = df.dropna(subset=["distance_km", "engine_power_kw", "fuel_type", "actual_fuel_consumption"])
df = df[df["distance_km"] > 0]
```

## 3. Removing outliers with the IQR method

*After the lower and upper bound formulas.*

```python
def within_iqr(per_100km):
    q1, q3 = per_100km.quantile(0.25), per_100km.quantile(0.75)
    iqr = q3 - q1
    return per_100km.between(q1 - 1.5 * iqr, q3 + 1.5 * iqr)

# Fuel used per 100 km, compared within each group of the same engine power
per_100km = df["actual_fuel_consumption"] / df["distance_km"] * 100
keep = per_100km.groupby(df["engine_power_kw"], group_keys=False).apply(within_iqr)
df = df[keep]
```

## 4. Encoding the fuel type

*After: "...where 1 represents gasoline and 0 represents diesel."*

```python
df["fuel_type_code"] = df["fuel_type"].map({"Gasoline": 1, "Diesel": 0})
```

## 5. 80/20 train-test split

*After: "...so the same split is reproduced in every run."*

```python
from sklearn.model_selection import train_test_split

predictors = ["distance_km", "engine_power_kw", "fuel_type_code"]
X = df[predictors]
y = df["actual_fuel_consumption"]
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
```

## 6. Centering and the interaction term

*After the Interaction formula.*

```python
def add_terms(frame, distance_mean, power_mean):
    out = frame.copy()
    out["distance_km"] = out["distance_km"] - distance_mean
    out["engine_power_kw"] = out["engine_power_kw"] - power_mean
    out["distance_x_power"] = out["distance_km"] * out["engine_power_kw"]
    return out

# The means come from the training set and are saved with the model
distance_mean = X_train["distance_km"].mean()
power_mean = X_train["engine_power_kw"].mean()
terms_train = add_terms(X_train, distance_mean, power_mean)
terms_test = add_terms(X_test, distance_mean, power_mean)
```

## 7. Correlation heatmap

*After: "...the strength of the relationship between each pair of variables."*

```python
import seaborn as sns
import matplotlib.pyplot as plt

terms_all = add_terms(X, distance_mean, power_mean)
corr = terms_all.assign(actual_fuel_consumption=y).corr()
sns.heatmap(corr, annot=True, fmt=".2f", cmap="coolwarm", vmin=-1, vmax=1)
plt.title("Correlation Heatmap of the Terms")
plt.show()
```

## 8. Variance Inflation Factor

*After: "...regressing predictor j on all the other predictors."*

```python
import statsmodels.api as sm
from statsmodels.stats.outliers_influence import variance_inflation_factor

X_vif = sm.add_constant(terms_all)
for i, term in enumerate(X_vif.columns):
    if term != "const":
        print(term, round(variance_inflation_factor(X_vif.values, i), 2))  # above 5 = high collinearity
```

## 9. Training the Linear Regression model

*After: "...and the subscript c marks a centered variable."*

```python
from sklearn.linear_model import LinearRegression

model = LinearRegression()
model.fit(terms_train, y_train)
print("Intercept (β0):", model.intercept_)
print("Coefficients (β1 to β4):", dict(zip(terms_train.columns, model.coef_)))
```

## 10. Residual plot, histogram and Breusch-Pagan test

*After: "...where a p-value above 0.05 indicates equal variance of the errors."*

```python
from statsmodels.stats.diagnostic import het_breuschpagan

y_pred = model.predict(terms_test)
residuals = y_test - y_pred

fig, ax = plt.subplots(1, 2, figsize=(12, 5))
ax[0].scatter(y_pred, residuals, alpha=0.4)
ax[0].axhline(0, linestyle="--")
ax[0].set(xlabel="Predicted Fuel Consumed (L)", ylabel="Residual (L)", title="Residual Plot")
sns.histplot(residuals, kde=True, ax=ax[1])
ax[1].set(xlabel="Residual (L)", title="Histogram of Residuals")
plt.show()

ols = sm.OLS(y_train, sm.add_constant(terms_train)).fit()
lm, p_value, _, _ = het_breuschpagan(ols.resid, ols.model.exog)
print("Breusch-Pagan p-value:", round(p_value, 4))
```

## 11. Durbin-Watson test on the local trips

*After: "A value close to 2 indicates independent errors."*

```python
from statsmodels.stats.stattools import durbin_watson

local_trips = df[df["data_source"] == "local"].sort_values("trip_date")
local_terms = terms_all.loc[local_trips.index]
local_residuals = local_trips["actual_fuel_consumption"] - model.predict(local_terms)
print("Durbin-Watson:", round(durbin_watson(local_residuals), 3))
```

## 12. R-Squared, MAE and RMSE

*After: "...which reflect the vehicles and trips of the university fleet."*

```python
import numpy as np
from sklearn.metrics import r2_score, mean_absolute_error, mean_squared_error

r2 = r2_score(y_test, y_pred)
mae = mean_absolute_error(y_test, y_pred)
rmse = np.sqrt(mean_squared_error(y_test, y_pred))
print(f"R² = {r2:.4f}   MAE = {mae:.4f} L   RMSE = {rmse:.4f} L")

# Records within the fleet's operating range: diesel, 30-400 km, 51-177 kW
in_range = (X_test["fuel_type_code"] == 0) & X_test["distance_km"].between(30, 400) & X_test["engine_power_kw"].between(51, 177)
fleet_pred = y_pred[in_range.to_numpy()]
print("Fleet range R²:", round(r2_score(y_test[in_range], fleet_pred), 4),
      "MAE:", round(mean_absolute_error(y_test[in_range], fleet_pred), 4),
      "RMSE:", round(np.sqrt(mean_squared_error(y_test[in_range], fleet_pred)), 4))
```

## 13. 5-fold cross-validation

*After: "The mean and standard deviation of the scores across the five folds are reported."*

```python
from sklearn.model_selection import KFold

scores = []
for train_i, test_i in KFold(n_splits=5, shuffle=True, random_state=42).split(X):
    X_a, X_b, y_a, y_b = X.iloc[train_i], X.iloc[test_i], y.iloc[train_i], y.iloc[test_i]
    # centering is repeated inside each fold, so the test fold stays unseen
    means = X_a["distance_km"].mean(), X_a["engine_power_kw"].mean()
    fold_model = LinearRegression().fit(add_terms(X_a, *means), y_a)
    scores.append(r2_score(y_b, fold_model.predict(add_terms(X_b, *means))))
print("R² per fold:", np.round(scores, 4))
print(f"Mean R² = {np.mean(scores):.4f}   Std = {np.std(scores):.4f}")
```

## 14. Actual versus predicted plot

*After: "The actual and predicted values are plotted to show how closely the predictions follow the recorded fuel
consumption."*

```python
plt.scatter(y_test, y_pred, alpha=0.4)
limits = [min(y_test.min(), y_pred.min()), max(y_test.max(), y_pred.max())]
plt.plot(limits, limits, "--")  # line of perfect prediction
plt.xlabel("Actual Fuel Consumed (L)")
plt.ylabel("Predicted Fuel Consumed (L)")
plt.title("Actual vs Predicted Fuel Consumption")
plt.show()
```

## Note

The trained model in the system bundles the encoding and centering into the saved pipeline, so a prediction is
encoded exactly like the training data:

```python
import joblib
joblib.dump(pipeline, "linear_regression_pipeline.joblib")  # loaded by the Flask backend
```

If the panel asks, the full code is in the Colab notebook. The shortened snippets above show each step as it is
described in Chapter III.
