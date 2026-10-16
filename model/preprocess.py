"""
Shared preprocessing definition for the fuel-consumption Linear Regression
model. This module is imported by BOTH train_model.py and app.py so that
the exact same feature list, encoding, and scaling are applied whether the
model is being trained or used to serve a live prediction. This avoids the
classic train/predict mismatch bug.
"""
import os
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

NUMERIC_FEATURES = [
    "odometer_reading",
    "distance_km",
    "duration_minutes",
    "avg_speed_kmh",
    "passenger_cargo_load_kg",
    "engine_displacement",
    "year_model",
    "rated_efficiency_l_per_100km",
]

CATEGORICAL_FEATURES = [
    "trip_type",
    "departure_period",
    "route",
    "road_type",
    "terrain_classification",
    "vehicle_type",
    "fuel_type",
]

FEATURE_COLUMNS = NUMERIC_FEATURES + CATEGORICAL_FEATURES
TARGET_COLUMN = "actual_fuel_consumption"


def departure_period_from_time(time_str):
    """Bucket a HH:MM(:SS) string into the same periods used in training."""
    try:
        hour = int(str(time_str).split(":")[0])
    except (ValueError, IndexError):
        hour = 8
    if 5 <= hour < 9:
        return "Early Morning"
    if 9 <= hour < 12:
        return "Morning"
    if 12 <= hour < 17:
        return "Afternoon"
    if 17 <= hour < 20:
        return "Evening"
    return "Night"


def supplementary_info(supplementary_path):
    """Describe the supplementary dataset.

    * "trips"  - trip-level records from open online sources (has the target
                 column). They are merged into the training data, and every
                 predictor the online dataset does not have is dropped from the
                 model ("variables absent from the online dataset are dropped
                 during merging" - Scope and Limitations).
    * "lookup" - a per-vehicle-type table of manufacturer-rated efficiency,
                 joined on vehicle_type as an extra predictor.
    """
    columns = list(pd.read_csv(supplementary_path, nrows=0).columns)
    if TARGET_COLUMN in columns:
        dropped = [c for c in FEATURE_COLUMNS if c not in columns and c != "departure_period"]
        if "departure_period" not in columns and "departure_time" not in columns:
            dropped.append("departure_period")
        return {"kind": "trips", "dropped_features": dropped, "columns": columns}
    return {"kind": "lookup", "dropped_features": [], "columns": columns}


def load_and_merge_datasets(historical_path, supplementary_path, extra_df=None):
    """Load the historical trip/fuel dataset (plus any extra records, e.g.
    trip records entered in the system) and merge the supplementary dataset
    (trip records appended, or a rated-efficiency lookup joined on vehicle_type).
    A `data_source` column records where each row came from."""
    df = pd.read_csv(historical_path)
    df["data_source"] = "historical"
    if extra_df is not None and not extra_df.empty:
        df = pd.concat([df, extra_df.assign(data_source="system")], ignore_index=True)
    supp = pd.read_csv(supplementary_path)
    if TARGET_COLUMN in supp.columns:
        supp = supp.copy()
        if "departure_period" not in supp.columns and "departure_time" in supp.columns:
            supp["departure_period"] = supp["departure_time"].map(departure_period_from_time)
        df = pd.concat([df, supp.assign(data_source="supplementary")], ignore_index=True)
    else:
        df = df.merge(supp[["vehicle_type", "rated_efficiency_l_per_100km"]], on="vehicle_type", how="left")
        df["rated_efficiency_l_per_100km"] = df["rated_efficiency_l_per_100km"].fillna(
            df["rated_efficiency_l_per_100km"].median()
        )
    # Every feature column exists (NaN where a source lacks it) so downstream
    # code can always select FEATURE_COLUMNS; dropped predictors are simply
    # not used by the model.
    for col in FEATURE_COLUMNS:
        if col not in df.columns:
            df[col] = pd.NA
    return df


def clean_data(df):
    """Handle missing values and remove clearly invalid / outlier rows."""
    df = df.copy()
    df = df.dropna(subset=[TARGET_COLUMN])

    for col in NUMERIC_FEATURES:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
            median = df[col].median() if df[col].notna().any() else 0
            df[col] = df[col].fillna(median)

    for col in CATEGORICAL_FEATURES:
        if col in df.columns:
            df[col] = df[col].fillna("Unknown")

    # Basic sanity filters
    df = df[(df["distance_km"] > 0) & (df["distance_km"] < 1000)]
    df = df[(df["duration_minutes"] > 0) & (df["duration_minutes"] < 1440)]
    df = df[(df["avg_speed_kmh"] > 0) & (df["avg_speed_kmh"] < 160)]
    df = df[df[TARGET_COLUMN] > 0]

    # Outlier removal via IQR on the target variable, within each data source:
    # the fleet's inter-campus trips and the online dataset's city trips have
    # very different typical fuel use, so one range for the merged data would
    # discard a whole source as "outliers" instead of the extreme trips in each.
    def within_iqr(target):
        q1, q3 = target.quantile(0.25), target.quantile(0.75)
        iqr = q3 - q1
        return target.between(q1 - 1.5 * iqr, q3 + 1.5 * iqr)

    if "data_source" in df.columns:
        keep = df.groupby("data_source", group_keys=False)[TARGET_COLUMN].apply(within_iqr)
        df = df[keep.reindex(df.index).fillna(False).astype(bool)]
    else:
        df = df[within_iqr(df[TARGET_COLUMN])]

    return df.reset_index(drop=True)


def build_preprocessing_pipeline(numeric_features=None, categorical_features=None):
    """ColumnTransformer: scale numeric features, one-hot encode categoricals.
    Bundled into the saved joblib pipeline together with the regressor so
    training-time and prediction-time preprocessing can never drift apart.
    `numeric_features` is the VIF-selected subset (default: all)."""
    transformer = ColumnTransformer(
        transformers=[
            ("numeric", StandardScaler(), list(numeric_features or NUMERIC_FEATURES)),
            ("categorical", OneHotEncoder(handle_unknown="ignore"), list(categorical_features or CATEGORICAL_FEATURES)),
        ]
    )
    return transformer


def build_prediction_frame(form):
    """Build a single-row DataFrame from a Flask form / dict of raw user
    input, in exactly the schema the pipeline expects."""
    row = {
        "odometer_reading": float(form["odometer_reading"]),
        "distance_km": float(form["distance_km"]),
        "duration_minutes": float(form["duration_minutes"]),
        "avg_speed_kmh": float(form["avg_speed_kmh"]),
        "passenger_cargo_load_kg": float(form.get("passenger_cargo_load_kg", 0) or 0),
        "engine_displacement": float(form["engine_displacement"]),
        "year_model": int(form["year_model"]),
        "trip_type": form["trip_type"],
        "departure_period": departure_period_from_time(form["departure_time"]),
        "route": form["route"],
        "road_type": form["road_type"],
        "terrain_classification": form["terrain_classification"],
        "vehicle_type": form["vehicle_type"],
        "fuel_type": form["fuel_type"],
        "rated_efficiency_l_per_100km": float(form.get("rated_efficiency_l_per_100km", 0) or 0),
    }
    return pd.DataFrame([row])


def attach_rated_efficiency(df_row, supplementary_path):
    """Look up the supplementary manufacturer-rated efficiency for a single
    prediction row based on its vehicle_type."""
    supp = pd.read_csv(supplementary_path)
    if "rated_efficiency_l_per_100km" not in supp.columns:
        # A trip-level supplementary dataset has no rated-efficiency lookup; the
        # predictor is then dropped during merging, so the model never uses it.
        df_row.loc[0, "rated_efficiency_l_per_100km"] = float("nan")
        return df_row
    match = supp[supp["vehicle_type"] == df_row.loc[0, "vehicle_type"]]
    if not match.empty:
        df_row.loc[0, "rated_efficiency_l_per_100km"] = float(match.iloc[0]["rated_efficiency_l_per_100km"])
    else:
        df_row.loc[0, "rated_efficiency_l_per_100km"] = float(supp["rated_efficiency_l_per_100km"].median())
    return df_row
