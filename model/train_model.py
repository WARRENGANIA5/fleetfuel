"""
Train the linear regression model and save the pipeline (Joblib) and
model/metrics.json.

Run:  python model/train_model.py
"""
import json
import os
import sys

import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression
from sklearn.model_selection import KFold, cross_validate, train_test_split
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.pipeline import Pipeline

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from model.diagnostics import VIF_THRESHOLD, compute_vif, regression_diagnostics
from timeutil import now_local
from model.preprocess import (
    FEATURE_COLUMNS,
    MODEL_TERMS,
    TARGET_COLUMN,
    build_feature_encoder,
    clean_data,
    raw_equation,
    load_and_merge_datasets,
    supplementary_info,
)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HISTORICAL_PATH = os.path.join(BASE_DIR, "data", "historical_fleet_data.csv")
SUPPLEMENTARY_PATH = os.path.join(BASE_DIR, "data", "supplementary_data.csv")
MODEL_PATH = os.path.join(BASE_DIR, "model", "linear_regression_pipeline.joblib")
# cleaned + merged training data
CLEANED_PATH = os.path.join(BASE_DIR, "data", "cleaned_merged_dataset.csv")
METRICS_PATH = os.path.join(BASE_DIR, "model", "metrics.json")

CV_FOLDS = 5
RANDOM_STATE = 42


def _replace_with_retry(src, dst, attempts=40, delay=0.05):
    """os.replace with retries (Windows/OneDrive may have the file open)."""
    import time
    for i in range(attempts):
        try:
            return os.replace(src, dst)
        except PermissionError:
            if i == attempts - 1:
                raise
            time.sleep(delay)


def train_and_save(df, extra_metrics=None, log=print, excluded_features=()):
    """Clean `df`, fit and evaluate the pipeline, then save it with metrics.json."""
    log("[2/6] Removing records with missing values or zero distance, and IQR outliers per engine power...")
    df = clean_data(df)
    log(f"      Usable records after cleaning: {len(df)}")
    df.to_csv(CLEANED_PATH + ".tmp", index=False)
    _replace_with_retry(CLEANED_PATH + ".tmp", CLEANED_PATH)
    log(f"      Cleaned and merged dataset saved to {CLEANED_PATH}")

    X = df[FEATURE_COLUMNS]
    y = df[TARGET_COLUMN]

    log("[3/6] Splitting train/test sets (80/20)...")
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=RANDOM_STATE)

    # centered terms to keep VIF low
    encoder = build_feature_encoder().fit(X_train)
    centers = (encoder.distance_mean_, encoder.power_mean_)
    terms = encoder.transform(X)
    log(f"      Centering: mean distance {centers[0]:.4f} km, mean engine power {centers[1]:.4f} kW")
    log(f"      Variance Inflation Factor of each predictor (above {VIF_THRESHOLD:g} = high collinearity):")
    vif = compute_vif(terms)
    for term, value in vif.items():
        log(f"        {term:<18} {value}")
    correlations = {c: round(float(terms[c].corr(y)), 3) for c in MODEL_TERMS if terms[c].std() > 0}

    log("[4/6] Training Linear Regression: fuel = b0 + b1 Distance + b2 Engine Power + b3 Fuel Type + b4 Distance x Power")
    pipeline = Pipeline(steps=[
        ("encoder", build_feature_encoder()),
        ("regressor", LinearRegression()),
    ])
    pipeline.fit(X_train, y_train)

    log("[5/6] Evaluating on held-out test set...")
    y_pred = pipeline.predict(X_test)
    r2 = r2_score(y_test, y_pred)
    mae = mean_absolute_error(y_test, y_pred)
    rmse = float(np.sqrt(mean_squared_error(y_test, y_pred)))

    log(f"      R2 Score : {r2:.4f}")
    log(f"      MAE      : {mae:.4f} L")
    log(f"      RMSE     : {rmse:.4f} L")

    log(f"[6/6] Running {CV_FOLDS}-Fold Cross-Validation on full dataset...")
    kfold = KFold(n_splits=CV_FOLDS, shuffle=True, random_state=RANDOM_STATE)
    # sklearn returns the errors as negatives
    cv = cross_validate(pipeline, X, y, cv=kfold,
                        scoring=("r2", "neg_mean_absolute_error", "neg_root_mean_squared_error"))
    cv_scores = cv["test_r2"]
    cv_mae = -cv["test_neg_mean_absolute_error"]
    cv_rmse = -cv["test_neg_root_mean_squared_error"]
    log(f"      CV R2 scores: {np.round(cv_scores, 4)}")
    log(f"      CV mean R2  : {cv_scores.mean():.4f} (+/- {cv_scores.std():.4f})")
    log(f"      CV mean MAE : {cv_mae.mean():.4f} L (+/- {cv_mae.std():.4f})")
    log(f"      CV mean RMSE: {cv_rmse.mean():.4f} L (+/- {cv_rmse.std():.4f})")

    log("      Checking regression assumptions (statsmodels)...")
    # Durbin-Watson on local trips sorted by date
    local = df[df["data_source"].isin(["historical", "local"])] if "data_source" in df else df.iloc[0:0]
    local_resid = None
    if not local.empty:
        local = local.assign(_date=pd.to_datetime(local["trip_date"], errors="coerce")).sort_values(["_date"], kind="stable")
        local_resid = (local[TARGET_COLUMN] - pipeline.predict(local[FEATURE_COLUMNS])).to_numpy()
    diagnostics = regression_diagnostics(encoder.transform(X_train), y_train, vif, local_resid)
    for t in diagnostics["tests"]:
        log(f"        {t['assumption']:<26} {t['test']:<26} {'PASS' if t['passed'] else 'NOT MET'}")

    os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)
    # write to temp files then swap, so readers never see a partial file
    joblib.dump(pipeline, MODEL_PATH + ".tmp")
    _replace_with_retry(MODEL_PATH + ".tmp", MODEL_PATH)
    log(f"Model pipeline saved to {MODEL_PATH}")

    regressor = pipeline.named_steps["regressor"]
    coefficients = {t: float(c) for t, c in zip(MODEL_TERMS, regressor.coef_)}
    raw_b0, raw_coef = raw_equation(float(regressor.intercept_), coefficients, centers)
    metrics = {
        "model_version": now_local().strftime("v%Y%m%d%H%M%S"),
        "r2_score": round(float(r2), 4),
        "mae": round(float(mae), 4),
        "rmse": round(float(rmse), 4),
        "cv_folds": CV_FOLDS,
        "cv_mean_r2": round(float(cv_scores.mean()), 4),
        "cv_std_r2": round(float(cv_scores.std()), 4),
        "cv_r2_folds": [round(float(s), 4) for s in cv_scores],
        "cv_mean_mae": round(float(cv_mae.mean()), 4),
        "cv_std_mae": round(float(cv_mae.std()), 4),
        "cv_mean_rmse": round(float(cv_rmse.mean()), 4),
        "cv_std_rmse": round(float(cv_rmse.std()), 4),
        "train_size": len(X_train),
        "test_size": len(X_test),
        "total_records": len(df),
        "trained_at": now_local().isoformat(timespec="seconds"),
        "status": "active",
        "equation_terms": MODEL_TERMS,
        "intercept": float(f"{float(regressor.intercept_):.6g}"),
        "coefficients": {t: float(f"{c:.6g}") for t, c in coefficients.items()},
        "centering": {"distance_km": round(centers[0], 4), "engine_power_kw": round(centers[1], 4)},
        # equation in original units
        "raw_intercept": float(f"{raw_b0:.6g}"),
        "raw_coefficients": {t: float(f"{c:.6g}") for t, c in raw_coef.items()},
        "vif_threshold": VIF_THRESHOLD,
        "vif": vif,
        "correlations": correlations,
        "selected_numeric_features": list(MODEL_TERMS),
        "selected_categorical_features": [],
        "data_sources": {k: int(v) for k, v in df["data_source"].value_counts().items()} if "data_source" in df else {},
        "diagnostics": diagnostics,
        # input ranges for extrapolation warnings
        "feature_ranges": {col: [round(float(X[col].min()), 2), round(float(X[col].max()), 2)]
                           for col in ("distance_km", "engine_power_kw")},
        "category_values": {"fuel_type": sorted(X["fuel_type"].astype(str).unique().tolist())},
        # same, per fuel type
        "ranges_by_fuel": {fuel: {col: [round(float(g[col].min()), 2), round(float(g[col].max()), 2)]
                                  for col in ("distance_km", "engine_power_kw")} | {"records": int(len(g))}
                           for fuel, g in X.groupby(X["fuel_type"].astype(str))},
    }
    metrics.update(extra_metrics or {})
    with open(METRICS_PATH + ".tmp", "w") as f:
        json.dump(metrics, f, indent=2)
    _replace_with_retry(METRICS_PATH + ".tmp", METRICS_PATH)
    log(f"Metrics saved to {METRICS_PATH}")

    return metrics, pipeline, X_test, y_test, y_pred


def main():
    if not os.path.exists(HISTORICAL_PATH) or not os.path.exists(SUPPLEMENTARY_PATH):
        print("Historical/supplementary dataset not found. Put the supplementary dataset in data/supplementary_data.csv "
              "(see data/SUPPLEMENTARY_DATASET_SOURCE.md); historical_fleet_data.csv may hold only its header row.")
        sys.exit(1)

    # use the app's loader to include Firestore trips
    try:
        from app import app, retrain_model
        with app.app_context():
            print("[1/6] Loading historical CSV + system trip records...")
            return retrain_model(log=print)
    except Exception as exc:  # no database, CSV only
        print(f"      (System trip records unavailable: {exc}; training on CSV only)")

    print("[1/6] Loading and merging datasets...")
    info = supplementary_info(SUPPLEMENTARY_PATH)
    df = load_and_merge_datasets(HISTORICAL_PATH, SUPPLEMENTARY_PATH)
    if df[TARGET_COLUMN].dropna().empty:
        # the CSV is empty when all trips live in the database
        print("Nothing to train on: the historical CSV has no rows and the trip records in the database could "
              "not be loaded. Check the internet connection and firebase-key.json, then run this again.")
        sys.exit(1)
    return train_and_save(df, extra_metrics={"supplementary_kind": info["kind"]})


if __name__ == "__main__":
    main()
