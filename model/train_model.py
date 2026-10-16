"""
Trains the Linear Regression fuel-consumption model for the Government
Fleet Fuel Consumption Prediction System and saves the fitted
preprocessing + regression Pipeline via Joblib, together with its
evaluation metrics (model/metrics.json).

Run:  python model/train_model.py
"""
import json
import os
import sys
from datetime import datetime

import joblib
import numpy as np
from sklearn.linear_model import LinearRegression
from sklearn.model_selection import KFold, cross_val_score, train_test_split
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.pipeline import Pipeline

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from model.diagnostics import CORR_THRESHOLD, VIF_THRESHOLD, regression_diagnostics, select_features
from timeutil import now_local
from model.preprocess import (
    CATEGORICAL_FEATURES,
    FEATURE_COLUMNS,
    NUMERIC_FEATURES,
    TARGET_COLUMN,
    build_preprocessing_pipeline,
    clean_data,
    load_and_merge_datasets,
    supplementary_info,
)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HISTORICAL_PATH = os.path.join(BASE_DIR, "data", "historical_fleet_data.csv")
SUPPLEMENTARY_PATH = os.path.join(BASE_DIR, "data", "supplementary_data.csv")
MODEL_PATH = os.path.join(BASE_DIR, "model", "linear_regression_pipeline.joblib")
METRICS_PATH = os.path.join(BASE_DIR, "model", "metrics.json")

CV_FOLDS = 5
RANDOM_STATE = 42


def _replace_with_retry(src, dst, attempts=40, delay=0.05):
    """os.replace, retried briefly: on Windows the swap fails while another
    thread (a page reading metrics) or OneDrive sync has the file open."""
    import time
    for i in range(attempts):
        try:
            return os.replace(src, dst)
        except PermissionError:
            if i == attempts - 1:
                raise
            time.sleep(delay)


def train_and_save(df, extra_metrics=None, log=print, excluded_features=()):
    """Clean `df`, fit the pipeline, evaluate it, and save both the pipeline
    and metrics.json. Shared by the CLI below and by the web app's automatic
    retraining (app.py), so both always train the exact same way."""
    log("[2/6] Cleaning data and removing outliers...")
    df = clean_data(df)
    log(f"      Usable records after cleaning: {len(df)}")

    X = df[FEATURE_COLUMNS]
    y = df[TARGET_COLUMN]

    log("[3/6] Splitting train/test sets (80/20)...")
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=RANDOM_STATE
    )

    log(f"      Variable selection: removing predictors with |r| < {CORR_THRESHOLD:g} or VIF > {VIF_THRESHOLD:g}...")
    excluded = list(excluded_features or [])
    if excluded:
        log(f"      Dropped during merging (absent from the supplementary dataset): {', '.join(excluded)}")
    numeric_candidates = [c for c in NUMERIC_FEATURES if c not in excluded]
    categorical = [c for c in CATEGORICAL_FEATURES if c not in excluded]
    selected_numeric, vif_initial, vif_final, removed, correlations = select_features(X_train, y_train, numeric_candidates)
    for r in removed:
        log(f"        - removed {r['feature']} ({r['reason']}; r = {r['r']}, VIF = {r['vif']})")
    log(f"      Kept numeric predictors: {', '.join(selected_numeric)}")

    log("[4/6] Building pipeline and training Linear Regression model...")
    preprocessor = build_preprocessing_pipeline(selected_numeric, categorical)
    pipeline = Pipeline(steps=[
        ("preprocessor", preprocessor),
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
    cv_scores = cross_val_score(pipeline, X, y, cv=kfold, scoring="r2")
    log(f"      CV R2 scores: {np.round(cv_scores, 4)}")
    log(f"      CV mean R2  : {cv_scores.mean():.4f} (+/- {cv_scores.std():.4f})")

    log("      Checking regression assumptions (statsmodels)...")
    diagnostics = regression_diagnostics(X_train, y_train, selected_numeric, categorical, vif_final)
    for t in diagnostics["tests"]:
        log(f"        {t['assumption']:<26} {t['test']:<26} {'PASS' if t['passed'] else 'NOT MET'}")

    os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)
    # Write to temp files and swap in, so a page reading mid-retrain never
    # sees a half-written model or metrics file.
    joblib.dump(pipeline, MODEL_PATH + ".tmp")
    _replace_with_retry(MODEL_PATH + ".tmp", MODEL_PATH)
    log(f"\nModel pipeline saved to {MODEL_PATH}")

    metrics = {
        "model_version": now_local().strftime("v%Y%m%d%H%M%S"),
        "r2_score": round(float(r2), 4),
        "mae": round(float(mae), 4),
        "rmse": round(float(rmse), 4),
        "cv_folds": CV_FOLDS,
        "cv_mean_r2": round(float(cv_scores.mean()), 4),
        "cv_std_r2": round(float(cv_scores.std()), 4),
        "train_size": len(X_train),
        "test_size": len(X_test),
        "total_records": len(df),
        "trained_at": now_local().isoformat(timespec="seconds"),
        "status": "active",
        "vif_threshold": VIF_THRESHOLD,
        "corr_threshold": CORR_THRESHOLD,
        "correlations": correlations,
        "vif_initial": vif_initial,
        "vif_final": vif_final,
        "removed_features": removed,
        "selected_numeric_features": selected_numeric,
        "selected_categorical_features": categorical,
        "dropped_in_merge": excluded,
        "data_sources": {k: int(v) for k, v in df["data_source"].value_counts().items()} if "data_source" in df else {},
        "diagnostics": diagnostics,
        # Min/max of every numeric feature the model saw, so the app can warn
        # when a prediction is asked for outside that range (extrapolation).
        "feature_ranges": {
            col: [round(float(X[col].min()), 2), round(float(X[col].max()), 2)]
            for col in X.columns if col in NUMERIC_FEATURES
        },
        # Every category the model saw, so the app can warn when a prediction
        # is asked for a vehicle type, fuel, road or terrain it has no trips for.
        "category_values": {
            col: sorted(X[col].dropna().astype(str).unique().tolist()) for col in categorical
        },
    }
    metrics.update(extra_metrics or {})
    with open(METRICS_PATH + ".tmp", "w") as f:
        json.dump(metrics, f, indent=2)
    _replace_with_retry(METRICS_PATH + ".tmp", METRICS_PATH)
    log(f"Metrics saved to {METRICS_PATH}")

    return metrics, pipeline, X_test, y_test, y_pred


def main():
    if not os.path.exists(HISTORICAL_PATH) or not os.path.exists(SUPPLEMENTARY_PATH):
        print("Historical/supplementary dataset not found. Run data/generate_dataset.py first "
              "(or replace it with the real GSU fleet dataset using the same column names).")
        sys.exit(1)

    # Prefer the web app's loader so the trip records entered in the system
    # (MySQL) are trained on together with the historical CSV.
    try:
        from app import app, retrain_model
        with app.app_context():
            print("[1/6] Loading historical CSV + system trip records...")
            return retrain_model(log=print)
    except Exception as exc:  # database unavailable -> CSV only
        print(f"      (System trip records unavailable: {exc}; training on CSV only)")

    print("[1/6] Loading and merging datasets...")
    info = supplementary_info(SUPPLEMENTARY_PATH)
    df = load_and_merge_datasets(HISTORICAL_PATH, SUPPLEMENTARY_PATH)
    if df[TARGET_COLUMN].dropna().empty:
        # The historical CSV holds only headers when the model trains on the
        # trip records in the database alone, so there is nothing to fall back on.
        print("Nothing to train on: the historical CSV has no rows and the trip records in the database could "
              "not be loaded. Start MySQL (start_server.bat) and run this again.")
        sys.exit(1)
    return train_and_save(df, extra_metrics={"supplementary_kind": info["kind"]},
                          excluded_features=info["dropped_features"])


if __name__ == "__main__":
    main()
