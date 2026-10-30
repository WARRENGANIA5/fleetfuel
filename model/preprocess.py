"""
Shared preprocessing for the fuel-consumption Linear Regression model
(Chapter III, How the Project Will Work). Imported by BOTH train_model.py and
app.py, so the exact same features and encoding are used when the model is
trained and when it serves a live prediction.

Predictors (Scope): distance traveled (km), engine power (kW) and fuel type;
the predicted value is the fuel consumed per trip in liters. The model is

    y^ = b0 + b1(Distance) + b2(Engine Power) + b3(Fuel Type) + b4(Distance x Engine Power)

with fuel type encoded as 1 = Gasoline, 0 = Diesel.
"""
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin

FUEL_TYPES = ("Diesel", "Gasoline")
FUEL_TYPE_CODES = {"Diesel": 0, "Gasoline": 1}  # Encoding: 1 represents gasoline and 0 represents diesel

# The three inputs a prediction needs (from the trip and the selected vehicle's record).
FEATURE_COLUMNS = ["distance_km", "engine_power_kw", "fuel_type"]
# The four terms of the regression equation, after encoding and the interaction term.
MODEL_TERMS = ["distance_km", "engine_power_kw", "fuel_type_code", "distance_x_power"]
TERM_LABELS = {
    "distance_km": "Distance (km)",
    "engine_power_kw": "Engine Power (kW)",
    "fuel_type_code": "Fuel Type (1 = Gasoline)",
    "distance_x_power": "Distance × Engine Power",
    "actual_fuel_consumption": "Fuel Consumed (L)",
}
TARGET_COLUMN = "actual_fuel_consumption"

# Kept for code that still asks for them: every model term is numeric now.
NUMERIC_FEATURES = MODEL_TERMS
CATEGORICAL_FEATURES = []

# The local Monthly Report of Official Travel export (one row per trip) and the
# vehicle records it is merged with on the plate number.
TRIP_COLUMNS = ["trip_date", "plate_number", "distance_km", TARGET_COLUMN]
VEHICLE_COLUMNS = ["plate_number", "brand_model", "fuel_type", "engine_power_kw"]


def encode_features(frame, centers=None):
    """Encoding and interaction term: fuel type as 1 (Gasoline) / 0 (Diesel),
    plus Distance x Engine Power for the higher fuel use per kilometre of
    larger engines. Returns the four model terms in a fixed order.

    With `centers` (mean distance, mean engine power of the training set),
    distance and power are mean-centered before the interaction is formed.
    Centering removes the collinearity between a predictor and an interaction
    built from it (high VIF) without changing any prediction."""
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
    """Pipeline step: learns the mean distance and mean engine power of the
    training data (fit) and builds the four centered terms (transform)."""

    def fit(self, X, y=None):
        X = pd.DataFrame(X)
        self.distance_mean_ = float(pd.to_numeric(X["distance_km"], errors="coerce").mean())
        self.power_mean_ = float(pd.to_numeric(X["engine_power_kw"], errors="coerce").mean())
        return self

    def transform(self, X):
        return encode_features(X, centers=(self.distance_mean_, self.power_mean_))


def build_feature_encoder():
    """The encoding step bundled into the saved joblib pipeline in front of the
    regression, so a prediction is always encoded exactly like the training data."""
    return TermEncoder()


def raw_equation(intercept, coefficients, centers):
    """The fitted centered equation written back in the original units:
    y = b0 + b1(D - d) + b2(P - p) + b3 F + b4(D - d)(P - p)
      = [b0 - b1 d - b2 p + b4 d p] + (b1 - b4 p) D + (b2 - b4 d) P + b3 F + b4 D P."""
    b1, b2, b3, b4 = (coefficients[t] for t in MODEL_TERMS)
    d, p = centers
    return (intercept - b1 * d - b2 * p + b4 * d * p,
            {"distance_km": b1 - b4 * p, "engine_power_kw": b2 - b4 * d, "fuel_type_code": b3, "distance_x_power": b4})


def merge_trips_and_vehicles(trips, vehicles):
    """The trip records and the vehicle records are stored separately, so they are
    merged using the plate number (each trip gets its vehicle's engine power and
    fuel type)."""
    vehicles = vehicles[["plate_number", "fuel_type", "engine_power_kw"]].drop_duplicates("plate_number")
    trips = trips.drop(columns=[c for c in ("fuel_type", "engine_power_kw") if c in trips.columns])
    return trips.merge(vehicles, on="plate_number", how="left")


def supplementary_info(supplementary_path):
    """Describe the supplementary dataset: online trip records with the same
    variables (distance, engine power, fuel type, fuel consumed)."""
    columns = list(pd.read_csv(supplementary_path, nrows=0).columns)
    missing = [c for c in FEATURE_COLUMNS + [TARGET_COLUMN] if c not in columns]
    return {"kind": "trips", "dropped_features": [], "missing_columns": missing, "columns": columns}


def load_and_merge_datasets(historical_path, supplementary_path, extra_df=None, exclude_supplementary_rows=()):
    """Combine the local trips (the historical CSV plus the trip records in the
    system, already merged with their vehicles) and the supplementary dataset on
    their shared variables. Each record is labeled with its source
    (`data_source`), so the local trips can be identified after merging: the
    trip records keep a `data_source` they already have (the online records
    shown as trip records), the others are "system". The supplementary rows in
    `exclude_supplementary_rows` are already among the trip records, so they
    are left out (no record is counted twice)."""
    frames = []
    historical = pd.read_csv(historical_path)
    if not historical.empty:
        frames.append(historical.assign(data_source="historical"))
    if extra_df is not None and not extra_df.empty:
        label = extra_df["data_source"].fillna("system") if "data_source" in extra_df else "system"
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
    """Remove records with missing values or zero distance, then extreme
    outliers with the IQR rule on the fuel used per 100 km, within each group
    of vehicles with the same engine power (large vehicles are compared only
    with vehicles of similar size)."""
    df = df.copy()
    for col in ("distance_km", "engine_power_kw", TARGET_COLUMN):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df["fuel_type"] = df["fuel_type"].astype("string").str.strip().str.title()
    df = df.dropna(subset=["distance_km", "engine_power_kw", "fuel_type", TARGET_COLUMN])
    df = df[df["fuel_type"].isin(FUEL_TYPES)]
    df = df[(df["distance_km"] > 0) & (df["engine_power_kw"] > 0) & (df[TARGET_COLUMN] > 0)]

    # IQR = Q3 - Q1; lower bound = Q1 - 1.5(IQR); upper bound = Q3 + 1.5(IQR).
    def within_iqr(per_100km):
        q1, q3 = per_100km.quantile(0.25), per_100km.quantile(0.75)
        iqr = q3 - q1
        return per_100km.between(q1 - 1.5 * iqr, q3 + 1.5 * iqr)

    per_100km = df[TARGET_COLUMN] / df["distance_km"] * 100
    keep = per_100km.groupby(df["engine_power_kw"], group_keys=False).apply(within_iqr)
    df = df[keep.reindex(df.index).fillna(False).astype(bool)]
    return df.reset_index(drop=True)


def build_prediction_frame(values):
    """A single-row frame from the trip distance and the selected vehicle's
    engine power and fuel type, in the schema the pipeline expects."""
    return pd.DataFrame([{
        "distance_km": float(values["distance_km"]),
        "engine_power_kw": float(values["engine_power_kw"]),
        "fuel_type": str(values["fuel_type"]),
    }])
