# ---- 1. Merge the records ----
import pandas as pd

trips = pd.read_csv("trip_records.csv")
vehicles = pd.read_csv("vehicle_records.csv")
supplementary = pd.read_csv("supplementary_data.csv")

vehicles = vehicles[["plate_number", "fuel_type", "engine_power_kw"]]
local = trips.merge(vehicles, on="plate_number", how="left")

local["data_source"] = local["source"].map(lambda s: "local" if pd.isna(s) else "trip_records_online")
supplementary["data_source"] = "supplementary"
df = pd.concat([local, supplementary], ignore_index=True)

# ---- 2. Remove missing values and zero distance ----
df = df.dropna(subset=["distance_km", "engine_power_kw", "fuel_type", "actual_fuel_consumption"])
df = df[df["distance_km"] > 0]

# ---- 3. IQR outliers and operating range ----
def within_iqr(per_100km):
    q1, q3 = per_100km.quantile(0.25), per_100km.quantile(0.75)
    iqr = q3 - q1
    return per_100km.between(q1 - 1.5 * iqr, q3 + 1.5 * iqr)

per_100km = df["actual_fuel_consumption"] / df["distance_km"] * 100
keep = per_100km.groupby(df["engine_power_kw"], group_keys=False).apply(within_iqr)
df = df[keep]

df = df[(df["fuel_type"] == "Diesel") & df["distance_km"].between(30, 400) & df["engine_power_kw"].between(51, 177)]

# ---- 4. Encoding ----
df["fuel_type_code"] = df["fuel_type"].map({"Gasoline": 1, "Diesel": 0})

# ---- 5. Train-test split ----
from sklearn.model_selection import train_test_split

predictors = ["distance_km", "engine_power_kw"]
X = df[predictors]
y = df["actual_fuel_consumption"]
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

# ---- 6. Centering and interaction term ----
def add_terms(frame, distance_mean, power_mean):
    out = frame.copy()
    out["distance_km"] = out["distance_km"] - distance_mean
    out["engine_power_kw"] = out["engine_power_kw"] - power_mean
    out["distance_x_power"] = out["distance_km"] * out["engine_power_kw"]
    return out

distance_mean = X_train["distance_km"].mean()
power_mean = X_train["engine_power_kw"].mean()
terms_train = add_terms(X_train, distance_mean, power_mean)
terms_test = add_terms(X_test, distance_mean, power_mean)

# ---- 7. Correlation heatmap ----
import seaborn as sns
import matplotlib.pyplot as plt

terms_all = add_terms(X, distance_mean, power_mean)
corr = terms_all.assign(actual_fuel_consumption=y).corr()
sns.heatmap(corr, annot=True, fmt=".2f", cmap="coolwarm", vmin=-1, vmax=1)
plt.title("Correlation Heatmap of the Terms")
plt.show()

# ---- 8. Variance Inflation Factor ----
import statsmodels.api as sm
from statsmodels.stats.outliers_influence import variance_inflation_factor

X_vif = sm.add_constant(terms_all)
for i, term in enumerate(X_vif.columns):
    if term != "const":
        print(term, round(variance_inflation_factor(X_vif.values, i), 2))

# ---- 9. Train the model ----
from sklearn.linear_model import LinearRegression

model = LinearRegression()
model.fit(terms_train, y_train)
print("Intercept (β0):", model.intercept_)
print("Coefficients (β1 to β4):", dict(zip(terms_train.columns, model.coef_)))

# ---- 10. Residual plots and Breusch-Pagan test ----
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

# ---- 11. Durbin-Watson test ----
from statsmodels.stats.stattools import durbin_watson

local_trips = df[df["data_source"] == "local"].sort_values("trip_date")
local_terms = terms_all.loc[local_trips.index]
local_residuals = local_trips["actual_fuel_consumption"] - model.predict(local_terms)
print("Durbin-Watson:", round(durbin_watson(local_residuals), 3))

# ---- 12. R-Squared, MAE and RMSE ----
import numpy as np
from sklearn.metrics import r2_score, mean_absolute_error, mean_squared_error

r2 = r2_score(y_test, y_pred)
mae = mean_absolute_error(y_test, y_pred)
rmse = np.sqrt(mean_squared_error(y_test, y_pred))
print(f"R² = {r2:.4f}   MAE = {mae:.4f} L   RMSE = {rmse:.4f} L")

# ---- 13. 5-fold cross-validation ----
from sklearn.model_selection import KFold

scores = []
for train_i, test_i in KFold(n_splits=5, shuffle=True, random_state=42).split(X):
    X_a, X_b, y_a, y_b = X.iloc[train_i], X.iloc[test_i], y.iloc[train_i], y.iloc[test_i]
    means = X_a["distance_km"].mean(), X_a["engine_power_kw"].mean()
    fold_model = LinearRegression().fit(add_terms(X_a, *means), y_a)
    scores.append(r2_score(y_b, fold_model.predict(add_terms(X_b, *means))))
print("R² per fold:", np.round(scores, 4))
print(f"Mean R² = {np.mean(scores):.4f}   Std = {np.std(scores):.4f}")

# ---- 14. Actual vs predicted plot ----
plt.scatter(y_test, y_pred, alpha=0.4)
limits = [min(y_test.min(), y_pred.min()), max(y_test.max(), y_pred.max())]
plt.plot(limits, limits, "--")
plt.xlabel("Actual Fuel Consumed (L)")
plt.ylabel("Predicted Fuel Consumed (L)")
plt.title("Actual vs Predicted Fuel Consumption")
plt.show()
