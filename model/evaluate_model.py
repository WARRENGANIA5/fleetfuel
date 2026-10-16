"""
Generates the evaluation figures for the paper (Chapter IV) with
Matplotlib/Seaborn, from exactly the data, predictors and 80/20 split the
current model was trained on:

  actual_vs_predicted.png   residual_plot.png      residual_qq_plot.png
  fuel_distribution.png     correlation_heatmap.png vif_before_after.png
  cv_r2_scores.png

Saved to reports/figures/. The web app draws the same charts live; these
PNGs are the print-ready versions.

Run:  python model/evaluate_model.py   (after train_model.py)
"""
import json
import os
import sys

import joblib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import seaborn as sns
import statsmodels.api as sm
from sklearn.model_selection import KFold, cross_val_score, train_test_split

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from model.preprocess import (FEATURE_COLUMNS, NUMERIC_FEATURES, TARGET_COLUMN,
                              clean_data, load_and_merge_datasets)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HISTORICAL_PATH = os.path.join(BASE_DIR, "data", "historical_fleet_data.csv")
SUPPLEMENTARY_PATH = os.path.join(BASE_DIR, "data", "supplementary_data.csv")
MODEL_PATH = os.path.join(BASE_DIR, "model", "linear_regression_pipeline.joblib")
METRICS_PATH = os.path.join(BASE_DIR, "model", "metrics.json")
FIGURES_DIR = os.path.join(BASE_DIR, "reports", "figures")

LABELS = {
    "odometer_reading": "Odometer (km)", "distance_km": "Distance (km)", "duration_minutes": "Duration (min)",
    "avg_speed_kmh": "Avg Speed (km/h)", "passenger_cargo_load_kg": "Load (kg)",
    "engine_displacement": "Engine Size (L)", "year_model": "Year Model",
    "rated_efficiency_l_per_100km": "Rated Eff. (L/100km)", "actual_fuel_consumption": "Fuel Used (L)",
}
sns.set_theme(style="whitegrid")
BLUE, NAVY, TEAL = "#1d6fd6", "#0b2545", "#1aa38c"


def load_training_frame():
    """Same data the model trains on: the web app's loader (CSV + system trip
    records from MySQL), or the CSV files alone if the database is offline."""
    try:
        from app import app, load_training_frame as app_loader
        with app.app_context():
            return app_loader(), "historical CSV + system trip records"
    except Exception as exc:  # database unavailable
        print(f"(Database unavailable: {exc}; using the CSV files only)")
        return load_and_merge_datasets(HISTORICAL_PATH, SUPPLEMENTARY_PATH), "historical CSV"


def save(fig, name):
    path = os.path.join(FIGURES_DIR, name)
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)
    print(f"  saved {os.path.relpath(path, BASE_DIR)}")


def main():
    if not (os.path.exists(MODEL_PATH) and os.path.exists(METRICS_PATH)):
        print("Trained model not found. Run model/train_model.py first.")
        sys.exit(1)
    os.makedirs(FIGURES_DIR, exist_ok=True)
    pipeline = joblib.load(MODEL_PATH)
    with open(METRICS_PATH, encoding="utf-8") as f:
        metrics = json.load(f)

    frame, source = load_training_frame()
    df = clean_data(frame)
    print(f"Evaluating model {metrics.get('model_version')} on {len(df)} records ({source})")
    X, y = df[FEATURE_COLUMNS], df[TARGET_COLUMN]
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    y_pred = pipeline.predict(X_test)
    residuals = y_test.values - y_pred

    # 1. Actual vs Predicted
    fig, ax = plt.subplots(figsize=(6.4, 5.2))
    ax.scatter(y_test, y_pred, alpha=0.55, color=BLUE, edgecolor="white", linewidth=0.3, label="Test records")
    lims = [min(y_test.min(), y_pred.min()), max(y_test.max(), y_pred.max())]
    ax.plot(lims, lims, color=NAVY, linestyle="--", linewidth=1.5, label="Perfect prediction")
    ax.set(xlabel="Actual Fuel Consumption (L)", ylabel="Predicted Fuel Consumption (L)",
           title=f"Actual vs Predicted (R² = {metrics['r2_score']})")
    ax.legend()
    save(fig, "actual_vs_predicted.png")

    # 2. Residuals vs fitted
    fig, ax = plt.subplots(figsize=(6.4, 5.2))
    ax.scatter(y_pred, residuals, alpha=0.55, color=BLUE, edgecolor="white", linewidth=0.3)
    ax.axhline(0, color=NAVY, linestyle="--", linewidth=1.5)
    ax.set(xlabel="Predicted Fuel Consumption (L)", ylabel="Residual (Actual − Predicted, L)", title="Residual Plot")
    save(fig, "residual_plot.png")

    # 3. Q-Q plot of residuals (normality check)
    fig = sm.qqplot(residuals, line="s", markerfacecolor=BLUE, markeredgecolor="white", alpha=0.7)
    fig.set_size_inches(6.4, 5.2)
    fig.axes[0].set_title("Normal Q-Q Plot of Residuals")
    save(fig, "residual_qq_plot.png")

    # 4. Fuel consumption distribution
    fig, ax = plt.subplots(figsize=(6.4, 5.2))
    sns.histplot(df[TARGET_COLUMN], kde=True, color=BLUE, binwidth=2.5, ax=ax)
    ax.set(xlabel="Fuel Used per Trip (L)", ylabel="Number of Trips", title="Fuel Consumption Distribution")
    save(fig, "fuel_distribution.png")

    # 5. Correlation heatmap (variable selection)
    corr = df[NUMERIC_FEATURES + [TARGET_COLUMN]].corr().rename(index=LABELS, columns=LABELS)
    fig, ax = plt.subplots(figsize=(8.2, 6.8))
    sns.heatmap(corr, annot=True, fmt=".2f", cmap="RdBu_r", vmin=-1, vmax=1, square=True, cbar=True, ax=ax,
                annot_kws={"size": 8})
    ax.set_title("Feature Correlation Heatmap")
    save(fig, "correlation_heatmap.png")

    # 6. VIF before and after variable selection
    vif_initial = metrics.get("vif_initial") or {}
    vif_final = metrics.get("vif_final") or {}
    if vif_initial:
        names = list(vif_initial)
        fig, ax = plt.subplots(figsize=(8.2, 4.8))
        pos = np.arange(len(names))
        ax.barh(pos + 0.2, [min(vif_initial[n], 50) for n in names], height=0.4, color="#c9d6e8", label="Before selection")
        ax.barh(pos - 0.2, [min(vif_final.get(n, 0), 50) for n in names], height=0.4, color=BLUE, label="After selection")
        ax.axvline(metrics.get("vif_threshold", 5), color="#d9534f", linestyle="--", label="Threshold (VIF = 5)")
        ax.set_yticks(pos, [LABELS.get(n, n) for n in names])
        ax.set(xlabel="Variance Inflation Factor (capped at 50 for display)", title="Multicollinearity Check (VIF)")
        ax.legend(loc="lower right")
        save(fig, "vif_before_after.png")

    # 7. k-fold cross-validation scores
    scores = cross_val_score(pipeline, X, y, cv=KFold(n_splits=metrics.get("cv_folds", 5), shuffle=True, random_state=42),
                             scoring="r2")
    fig, ax = plt.subplots(figsize=(6.4, 4.4))
    ax.bar([f"Fold {i}" for i in range(1, len(scores) + 1)], scores, color=TEAL)
    ax.axhline(scores.mean(), color=NAVY, linestyle="--", label=f"Mean R² = {scores.mean():.4f}")
    ax.set(ylim=(0, 1), ylabel="R²", title=f"{len(scores)}-Fold Cross-Validation")
    ax.legend()
    save(fig, "cv_r2_scores.png")

    print(f"Saved evaluation figures to {os.path.relpath(FIGURES_DIR, BASE_DIR)}")


if __name__ == "__main__":
    main()
