"""
Generates the evaluation figures for the paper (Chapter IV) with
Matplotlib/Seaborn, from exactly the data, predictors and 80/20 split the
current model was trained on:

  actual_vs_predicted.png   residual_plot.png       residual_histogram.png
  residual_qq_plot.png      correlation_heatmap.png vif.png
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

from model.preprocess import (FEATURE_COLUMNS, MODEL_TERMS, TARGET_COLUMN, TERM_LABELS,
                              clean_data, load_and_merge_datasets)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HISTORICAL_PATH = os.path.join(BASE_DIR, "data", "historical_fleet_data.csv")
SUPPLEMENTARY_PATH = os.path.join(BASE_DIR, "data", "supplementary_data.csv")
MODEL_PATH = os.path.join(BASE_DIR, "model", "linear_regression_pipeline.joblib")
METRICS_PATH = os.path.join(BASE_DIR, "model", "metrics.json")
FIGURES_DIR = os.path.join(BASE_DIR, "reports", "figures")

LABELS = TERM_LABELS
sns.set_theme(style="whitegrid")
BLUE, NAVY, TEAL = "#1d6fd6", "#0b2545", "#1aa38c"


def load_training_frame():
    """Same data the model trains on: the web app's loader (CSV + system trip
    records from Firebase Firestore), or the CSV files alone if the database is offline."""
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

    # 4. Histogram of residuals (normality check), like the web app: bins over
    # 99% of the residuals, the few larger ones counted in the end bins.
    resid = np.asarray(residuals, dtype=float)
    half = max(float(np.ceil(np.percentile(np.abs(resid), 99))), 1.0)
    width = next(w for w in (0.1, 0.2, 0.25, 0.5, 1, 2, 2.5, 5, 10, 25, 50) if 2 * half / w <= 24)
    half = np.ceil(half / width) * width
    fig, ax = plt.subplots(figsize=(6.4, 5.2))
    sns.histplot(np.clip(resid, -half, half), bins=np.linspace(-half, half, int(round(2 * half / width)) + 1),
                 kde=True, color=BLUE, ax=ax)
    ax.axvline(0, color=NAVY, linestyle="--", linewidth=1.5)
    ax.set(xlabel="Residual (Actual − Predicted, L)", ylabel="Number of Test Trips", title="Histogram of Residuals")
    outside = int((np.abs(resid) > half).sum())
    if outside:
        ax.text(0.98, 0.97, f"{outside} residuals beyond ±{half:g} L\nare counted in the end bins",
                transform=ax.transAxes, ha="right", va="top", fontsize=8, color=NAVY)
    save(fig, "residual_histogram.png")

    # 5. Correlation heatmap of the equation's terms and the fuel consumed
    terms = pipeline.named_steps["encoder"].transform(X).assign(**{TARGET_COLUMN: y.astype(float)})
    cols = [c for c in MODEL_TERMS if terms[c].nunique() > 1] + [TARGET_COLUMN]
    corr = terms[cols].corr().rename(index=LABELS, columns=LABELS)
    fig, ax = plt.subplots(figsize=(8.2, 6.8))
    sns.heatmap(corr, annot=True, fmt=".2f", cmap="RdBu_r", vmin=-1, vmax=1, square=True, cbar=True, ax=ax,
                annot_kws={"size": 8})
    ax.set_title("Feature Correlation Heatmap")
    save(fig, "correlation_heatmap.png")

    # 6. Variance Inflation Factor of each term (above 5 = high collinearity)
    vif = {k: v for k, v in (metrics.get("vif") or {}).items() if v is not None}
    if vif:
        names = list(vif)
        fig, ax = plt.subplots(figsize=(8.2, 4.2))
        pos = np.arange(len(names))
        ax.barh(pos, [min(vif[n], 50) for n in names], height=0.5, color=BLUE)
        for i, n in enumerate(names):
            ax.text(min(vif[n], 50) + 0.5, i, f"{vif[n]:g}", va="center", fontsize=9)
        ax.axvline(metrics.get("vif_threshold", 5), color="#d9534f", linestyle="--", label="Threshold (VIF = 5)")
        ax.set_yticks(pos, [LABELS.get(n, n) for n in names])
        ax.set(xlabel="Variance Inflation Factor (capped at 50 for display)", title="Multicollinearity Check (VIF)")
        ax.legend(loc="lower right")
        save(fig, "vif.png")

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
