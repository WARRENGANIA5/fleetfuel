"""
Preprocessing shared by train_model.py and app.py so training and prediction
use the same features.

    y^ = b0 + b1(Distance) + b2(Engine Power) + b3(Fuel Type) + b4(Distance x Engine Power)

Fuel type: 1 = Gasoline, 0 = Diesel. Output is liters per trip.

The coefficients are fitted by weighted least squares (WLS): the error of a
trip grows with the fuel it uses, so each record is weighted by 1 / its
estimated error variance (feasible GLS), which gives equal-variance errors.
"""
import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.linear_model import LinearRegression

FUEL_TYPES = ("Diesel", "Gasoline")
FUEL_TYPE_CODES = {"Diesel": 0, "Gasoline": 1}

# model inputs
FEATURE_COLUMNS = ["distance_km", "engine_power_kw", "fuel_type"]
# regression terms after encoding
MODEL_TERMS = ["distance_km", "engine_power_kw", "fuel_type_code", "distance_x_power"]
TERM_LABELS = {
    "distance_km": "Distance (km)",
    "engine_power_kw": "Engine Power (kW)",
    "fuel_type_code": "Fuel Type (1 = Gasoline)",
    "distance_x_power": "Distance × Engine Power",
    "actual_fuel_consumption": "Fuel Consumed (L)",
}
TARGET_COLUMN = "actual_fuel_consumption"

# kept for older code; all terms are numeric now
NUMERIC_FEATURES = MODEL_TERMS
CATEGORICAL_FEATURES = []

# operating range of the university fleet (all diesel; local trips 32-372 km)
FLEET_FUEL_TYPE = "Diesel"
FLEET_DISTANCE_KM = (30, 400)
FLEET_POWER_KW = (51, 177)

# local trip export and vehicle records (joined on plate number)
TRIP_COLUMNS = ["trip_date", "plate_number", "distance_km", TARGET_COLUMN]
VEHICLE_COLUMNS = ["plate_number", "brand_model", "fuel_type", "engine_power_kw"]


def encode_features(frame, centers=None):
    """Encode fuel type and add the Distance x Engine Power term.

    With `centers` (training means), distance and power are centered first,
    which lowers the VIF without changing predictions."""
    frame = pd.DataFrame(frame)
    distance = pd.to_numeric(frame["distance_km"], errors="coerce").astype(float)
    power = pd.to_numeric(frame["engine_power_kw"], errors="coerce").astype(float)
    fuel = frame["fuel_type"].map(lambda v: FUEL_TYPE_CODES.get(str(v).strip().title(), float("nan"))).astype(float)
    if centers is not None:
        distance, power = distance - centers[0], power - centers[1]
    return pd.DataFrame({
        "distance_km": distance,
        "engine_power_kw": power,
        "fuel_type_code": fuel,
        "distance_x_power": distance * power,
    }, index=frame.index)


class TermEncoder(BaseEstimator, TransformerMixin):
    """Pipeline step: fit stores the training means, transform builds the terms."""

    def fit(self, X, y=None):
        X = pd.DataFrame(X)
        self.distance_mean_ = float(pd.to_numeric(X["distance_km"], errors="coerce").mean())
        self.power_mean_ = float(pd.to_numeric(X["engine_power_kw"], errors="coerce").mean())
        return self

    def transform(self, X):
        return encode_features(X, centers=(self.distance_mean_, self.power_mean_))


def build_feature_encoder():
    """Encoding step saved inside the joblib pipeline."""
    return TermEncoder()


class WeightedLinearRegression(LinearRegression):
    """Linear regression fitted by feasible weighted least squares.

    1. ordinary least squares fit;
    2. error variance modeled as  log(e^2) = g0 + g1 log(y^)  (the error grows
       with the fuel a trip uses);
    3. refit with weights 1 / variance.
    Predictions use the same linear equation as LinearRegression."""

    MIN_FITTED = 0.5  # liters; keeps log(y^) defined for very short trips

    def fit(self, X, y, sample_weight=None):
        y = np.asarray(y, dtype=float)
        LinearRegression.fit(self, X, y)
        self.first_coef_, self.first_intercept_ = self.coef_.copy(), float(self.intercept_)
        fitted = self._first_stage(X)
        log_sq = np.log((y - fitted) ** 2 + 1e-6)
        design = np.column_stack([np.ones(len(fitted)), np.log(fitted)])
        self.variance_params_ = np.linalg.lstsq(design, log_sq, rcond=None)[0]
        LinearRegression.fit(self, X, y, sample_weight=self.weights(X))
        return self

    def _first_stage(self, X):
        return np.clip(np.asarray(pd.DataFrame(X), dtype=float) @ self.first_coef_ + self.first_intercept_,
                       self.MIN_FITTED, None)

    def weights(self, X):
        """1 / estimated error variance of each record."""
        g0, g1 = self.variance_params_
        return 1.0 / np.exp(g0 + g1 * np.log(self._first_stage(X)))


def remove_residual_outliers(df, limit=3.0, max_rounds=20):
    """Drop records whose standardized (weighted) residual is beyond +/- `limit`,
    refitting until none is left: trips the equation cannot represent
    (recording errors, unusual driving)."""
    df = df.copy()
    for _ in range(max_rounds):
        if len(df) < 10:
            break
        terms = encode_features(df[FEATURE_COLUMNS], centers=(df["distance_km"].mean(), df["engine_power_kw"].mean()))
        y = df[TARGET_COLUMN].to_numpy(dtype=float)
        model = WeightedLinearRegression().fit(terms, y)
        w = model.weights(terms)
        z = (y - model.predict(terms)) * np.sqrt(w)
        z = z / np.sqrt(np.sum(z ** 2) / max(len(z) - terms.shape[1] - 1, 1))
        outlier = np.abs(z) > limit
        if not outlier.any():
            break
        df = df[~outlier]
    return df


def raw_equation(intercept, coefficients, centers):
    """Convert the centered coefficients back to original units:
    y = b0 + b1(D - d) + b2(P - p) + b3 F + b4(D - d)(P - p)
      = [b0 - b1 d - b2 p + b4 d p] + (b1 - b4 p) D + (b2 - b4 d) P + b3 F + b4 D P."""
    b1, b2, b3, b4 = (coefficients[t] for t in MODEL_TERMS)
    d, p = centers
    return (intercept - b1 * d - b2 * p + b4 * d * p,
            {"distance_km": b1 - b4 * p, "engine_power_kw": b2 - b4 * d, "fuel_type_code": b3, "distance_x_power": b4})


def fleet_range_mask(frame):
    """Records of the same kind as the fleet's: diesel, its trip distances and engine powers."""
    frame = pd.DataFrame(frame)
    return ((frame["fuel_type"].astype(str).str.strip().str.title() == FLEET_FUEL_TYPE)
            & frame["distance_km"].between(*FLEET_DISTANCE_KM)
            & frame["engine_power_kw"].between(*FLEET_POWER_KW))


def merge_trips_and_vehicles(trips, vehicles):
    """Join trips with their vehicle's engine power and fuel type by plate number."""
    vehicles = vehicles[["plate_number", "fuel_type", "engine_power_kw"]].drop_duplicates("plate_number")
    trips = trips.drop(columns=[c for c in ("fuel_type", "engine_power_kw") if c in trips.columns])
    return trips.merge(vehicles, on="plate_number", how="left")


def supplementary_info(supplementary_path):
    """Supplementary dataset with the same columns as the trip records."""
    columns = list(pd.read_csv(supplementary_path, nrows=0).columns)
    missing = [c for c in FEATURE_COLUMNS + [TARGET_COLUMN] if c not in columns]
    return {"kind": "trips", "dropped_features": [], "missing_columns": missing, "columns": columns}


def load_and_merge_datasets(historical_path, supplementary_path, extra_df=None, exclude_supplementary_rows=()):
    """Merge local trips with the supplementary dataset, tagging each row's
    `data_source`. Rows in `exclude_supplementary_rows` are already trip
    records and are skipped so nothing is counted twice."""
    frames = []
    historical = pd.read_csv(historical_path)
    if not historical.empty:
        frames.append(historical.assign(data_source="historical"))
    if extra_df is not None and not extra_df.empty:
        label = extra_df["data_source"].fillna("local") if "data_source" in extra_df else "local"
        frames.append(extra_df.assign(data_source=label))
    supplementary = pd.read_csv(supplementary_path)
    supplementary = supplementary.drop(index=[i for i in exclude_supplementary_rows if i in supplementary.index])
    frames.append(supplementary.assign(data_source="supplementary"))
    df = pd.concat(frames, ignore_index=True)
    for col in FEATURE_COLUMNS + [TARGET_COLUMN, "trip_date", "plate_number"]:
        if col not in df.columns:
            df[col] = pd.NA
    return df


def clean_data(df):
    """Drop missing/zero-distance rows, then IQR outliers on L/100 km per
    engine-power group, keep the fleet's operating range, then drop records
    with a standardized residual beyond +/- 3."""
    df = df.copy()
    for col in ("distance_km", "engine_power_kw", TARGET_COLUMN):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df["fuel_type"] = df["fuel_type"].astype("string").str.strip().str.title()
    df = df.dropna(subset=["distance_km", "engine_power_kw", "fuel_type", TARGET_COLUMN])
    df = df[df["fuel_type"].isin(FUEL_TYPES)]
    df = df[(df["distance_km"] > 0) & (df["engine_power_kw"] > 0) & (df[TARGET_COLUMN] > 0)]

    # bounds: Q1 - 1.5*IQR, Q3 + 1.5*IQR
    def within_iqr(per_100km):
        q1, q3 = per_100km.quantile(0.25), per_100km.quantile(0.75)
        iqr = q3 - q1
        return per_100km.between(q1 - 1.5 * iqr, q3 + 1.5 * iqr)

    per_100km = df[TARGET_COLUMN] / df["distance_km"] * 100
    keep = per_100km.groupby(df["engine_power_kw"], group_keys=False).apply(within_iqr)
    df = df[keep.reindex(df.index).fillna(False).astype(bool)]
    df = df[fleet_range_mask(df)]
    df = remove_residual_outliers(df)
    return df.reset_index(drop=True)


def build_prediction_frame(values):
    """One-row input frame for a prediction."""
    return pd.DataFrame([{
        "distance_km": float(values["distance_km"]),
        "engine_power_kw": float(values["engine_power_kw"]),
        "fuel_type": str(values["fuel_type"]),
    }])
