# Chapter III — code for the 12 [code] placeholders (October 30, 2026)

Chapter III ("How the Project Will Work") has 12 `[code]` placeholders. Below is the code for each, in the same
order as they appear in the manuscript. The snippets are shortened from the Google Colab notebook used to train
the model (`colab/fuel_consumption_linear_regression.ipynb`) and `model/preprocess.py`, `model/diagnostics.py`.

## 1. Merging the trip and vehicle records, labeling the source

*After: "...the local and supplementary data are combined using their shared variables."*

```python
import pandas as pd

trips = pd.read_csv("trip_records.csv")
vehicles = pd.read_csv("vehicle_records.csv")
supplementary = pd.read_csv("supplementary_data.csv")

# Merge the trip records and vehicle records using the plate number
vehicles = vehicles[["plate_number", "fuel_type", "engine_power_kw"]]
local = trips.merge(vehicles, on="plate_number", how="left")

# Label each record by its source, then combine on the shared variables
local["data_source"] = "local"
supplementary["data_source"] = "supplementary"
df = pd.concat([local, supplementary], ignore_index=True)
```

## 2. Removing missing values and zero distance; correlation heatmap

*After: "...the correlation heatmap shows the strength of the relationship between the variables."*

```python
import seaborn as sns
import matplotlib.pyplot as plt

df = df.dropna(subset=["distance_km", "engine_power_kw", "fuel_type", "actual_fuel_consumption"])
df = df[df["distance_km"] > 0]

corr = df[["distance_km", "engine_power_kw", "actual_fuel_consumption"]].corr()
sns.heatmap(corr, annot=True, fmt=".2f", cmap="coolwarm", vmin=-1, vmax=1)
plt.title("Correlation Heatmap")
plt.show()
```

## 3. Removing outliers with the IQR method

*After: "Values below the lower bound or above the upper bound are removed."*

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

## 5. Interaction term

*After: "Distance × Engine Power"*

```python
# Distance and engine power are mean-centered first, so the interaction term does not
# repeat the information of the two predictors (keeps every VIF below 5)
df["distance_km"] = df["distance_km"] - df["distance_km"].mean()
df["engine_power_kw"] = df["engine_power_kw"] - df["engine_power_kw"].mean()
df["distance_x_power"] = df["distance_km"] * df["engine_power_kw"]
```

## 6. Variance Inflation Factor

*After the VIF formula.*

```python
import statsmodels.api as sm
from statsmodels.stats.outliers_influence import variance_inflation_factor

terms = ["distance_km", "engine_power_kw", "fuel_type_code", "distance_x_power"]
X_vif = sm.add_constant(df[terms])
for i, term in enumerate(X_vif.columns):
    if term != "const":
        print(term, round(variance_inflation_factor(X_vif.values, i), 2))  # above 5 = high collinearity
```

## 7. 80/20 split and training the Linear Regression model

*After: "...and β1 to β4 are the coefficients of the predictors."*

```python
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LinearRegression

X = df[terms]
y = df["actual_fuel_consumption"]
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

model = LinearRegression()
model.fit(X_train, y_train)
print("Intercept (β0):", model.intercept_)
print("Coefficients (β1 to β4):", dict(zip(terms, model.coef_)))
```

## 8. Residual plot and histogram

*After: "...the histogram checks whether the errors follow a normal distribution."*

```python
y_pred = model.predict(X_test)
residuals = y_test - y_pred

fig, ax = plt.subplots(1, 2, figsize=(12, 5))
ax[0].scatter(y_pred, residuals, alpha=0.4)
ax[0].axhline(0, linestyle="--")
ax[0].set(xlabel="Predicted Fuel Consumed (L)", ylabel="Residual (L)", title="Residual Plot")
sns.histplot(residuals, kde=True, ax=ax[1])
ax[1].set(xlabel="Residual (L)", title="Histogram of Residuals")
plt.show()
```

## 9. Durbin-Watson test on the local trips

*After: "A value close to 2 indicates that the errors are independent."*

```python
from statsmodels.stats.stattools import durbin_watson

local_trips = df[df["data_source"] == "local"].sort_values("trip_date")
local_residuals = local_trips["actual_fuel_consumption"] - model.predict(local_trips[terms])
print("Durbin-Watson:", round(durbin_watson(local_residuals), 3))
```

## 10. R-Squared, MAE and RMSE

*After the RMSE formula.*

```python
import numpy as np
from sklearn.metrics import r2_score, mean_absolute_error, mean_squared_error

r2 = r2_score(y_test, y_pred)
mae = mean_absolute_error(y_test, y_pred)
rmse = np.sqrt(mean_squared_error(y_test, y_pred))
print(f"R² = {r2:.4f}   MAE = {mae:.4f} L   RMSE = {rmse:.4f} L")
```

## 11. 5-fold cross-validation

*After: "...repeating the process for all the five iterations."*

```python
from sklearn.model_selection import KFold, cross_val_score

kfold = KFold(n_splits=5, shuffle=True, random_state=42)
cv_r2 = cross_val_score(LinearRegression(), X, y, cv=kfold, scoring="r2")
print("R² per fold:", cv_r2.round(4))
print(f"Mean R² = {cv_r2.mean():.4f}   Std = {cv_r2.std():.4f}")
```

## 12. Actual versus predicted plot

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

The trained model in the system takes the means from the training set only (76,907 records) and bundles the
encoding and centering into the saved pipeline, so a prediction is encoded exactly like the training data:

```python
import joblib
joblib.dump(pipeline, "linear_regression_pipeline.joblib")  # loaded by the Flask backend
```

If the panel asks, the full code is in the Colab notebook. The shortened snippets above show each step as it is
described in Chapter III.
