"""
Variable selection and regression-assumption diagnostics (Chapter II,
Theoretical Background), computed with statsmodels:

* Correlation filter - numeric predictors with |r| < 0.10 against fuel
  consumption have no measurable link to fuel use and are removed.
* Variance Inflation Factor (VIF) - predictors above 5 are treated as highly
  collinear and removed one at a time (highest first) before training.
* LINE conditions on the training residuals of an OLS fit:
    Linearity           - Ramsey RESET test
    Independence        - Durbin-Watson statistic
    Normality           - Jarque-Bera test
    Equal variance      - Breusch-Pagan test
"""
import math
import warnings

import numpy as np
import pandas as pd
import statsmodels.api as sm
from statsmodels.stats.diagnostic import het_breuschpagan, linear_reset
from statsmodels.stats.outliers_influence import variance_inflation_factor
from statsmodels.stats.stattools import durbin_watson, jarque_bera

VIF_THRESHOLD = 5.0
CORR_THRESHOLD = 0.10  # |r| below this = no measurable (only negligible) link to fuel use
# Never removed for a high VIF: the study's primary predictor (Chapter II).
PRIMARY_PREDICTORS = ("distance_km",)
ALPHA = 0.05
VIF_CAP = 1000.0  # perfect collinearity gives an infinite VIF; stored as ">1000"


def compute_vif(frame):
    """VIF of every column in `frame` (numeric predictors), with an intercept."""
    X = sm.add_constant(frame.astype(float), has_constant="add")
    out = {}
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")  # divide-by-zero for perfectly collinear columns
        for i, col in enumerate(X.columns):
            if col == "const":
                continue
            value = variance_inflation_factor(X.values, i)
            out[col] = VIF_CAP if (not math.isfinite(value) or value > VIF_CAP) else round(float(value), 2)
    return out


def select_features_by_vif(frame, numeric_features, threshold=VIF_THRESHOLD):
    """Drop the numeric predictor with the highest VIF until every remaining
    VIF is at or below `threshold`. Returns (kept, initial_vif, final_vif, removed)."""
    kept = [c for c in numeric_features if frame[c].astype(float).std() > 0]
    removed = [{"feature": c, "vif": None, "reason": "constant value"} for c in numeric_features if c not in kept]
    initial = compute_vif(frame[kept])
    while len(kept) > 1:
        vif = compute_vif(frame[kept])
        worst = max(vif, key=vif.get)
        if vif[worst] <= threshold:
            break
        removed.append({"feature": worst, "vif": vif[worst], "reason": f"VIF above {threshold:g}"})
        kept.remove(worst)
    return kept, initial, compute_vif(frame[kept]), removed


def select_features(frame, target, numeric_features, corr_threshold=CORR_THRESHOLD, vif_threshold=VIF_THRESHOLD):
    """Two-step variable selection (Chapter I, Process: "keeps the predictors
    with a measurable link to fuel use and removes the ones carrying the same
    information"):

    1. correlation filter - drop numeric predictors whose |Pearson r| with
       fuel consumption is below `corr_threshold` (no measurable link);
    2. VIF - drop the remaining predictor with the highest VIF until every
       VIF is at or below `vif_threshold` (same information).

    Returns (kept, initial_vif, final_vif, removed, correlations)."""
    y = target.astype(float)
    candidates = [c for c in numeric_features if frame[c].astype(float).std() > 0]
    removed = [{"feature": c, "vif": None, "r": None, "reason": "constant value"}
               for c in numeric_features if c not in candidates]
    correlations = {c: round(float(frame[c].astype(float).corr(y)), 3) for c in candidates}
    initial_vif = compute_vif(frame[candidates]) if len(candidates) > 1 else {c: 1.0 for c in candidates}
    kept = []
    for c in candidates:
        if abs(correlations[c]) < corr_threshold:
            removed.append({"feature": c, "vif": initial_vif.get(c), "r": correlations[c],
                            "reason": f"weak link to fuel use (|r| < {corr_threshold:g})"})
        else:
            kept.append(c)
    while len(kept) > 1:
        vif = compute_vif(frame[kept])
        # Distance traveled is the study's primary predictor (Chapter II, [5]), so
        # when it shares information with another predictor (e.g. trip duration),
        # the other one is removed. Among the rest, the highest VIF goes first; on
        # a tie, the one with the weaker link to fuel use, then the later one.
        candidates_to_drop = [c for c in kept if c not in PRIMARY_PREDICTORS] or kept
        worst = max(candidates_to_drop, key=lambda c: (vif[c], -abs(correlations[c]), kept.index(c)))
        if max(vif.values()) <= vif_threshold or vif[worst] <= vif_threshold:
            break
        removed.append({"feature": worst, "vif": vif[worst], "r": correlations[worst],
                        "reason": f"VIF above {vif_threshold:g}"})
        kept.remove(worst)
    final_vif = compute_vif(frame[kept]) if len(kept) > 1 else {c: 1.0 for c in kept}
    return kept, initial_vif, final_vif, removed, correlations


def _p(value):
    return None if value is None or not math.isfinite(float(value)) else round(float(value), 4)


def regression_diagnostics(X_train, y_train, numeric_features, categorical_features, final_vif):
    """Fit an OLS model on the training split (same predictors as the
    scikit-learn pipeline, categoricals dummy-coded) and test the LINE
    conditions on its residuals."""
    numeric = X_train[numeric_features].astype(float)
    dummies = pd.get_dummies(X_train[categorical_features].astype(str), drop_first=True, dtype=float)
    design = sm.add_constant(pd.concat([numeric, dummies], axis=1), has_constant="add")
    y = np.asarray(y_train, dtype=float)
    result = sm.OLS(y, design).fit()
    resid = np.asarray(result.resid)

    reset = linear_reset(result, power=2, use_f=True)
    dw = float(durbin_watson(resid))
    jb_stat, jb_p, skew, kurtosis = jarque_bera(resid)
    bp_lm, bp_p, _, _ = het_breuschpagan(resid, design)
    max_vif = max(final_vif.values()) if final_vif else 0.0

    tests = [
        {"key": "linearity", "assumption": "Linearity", "test": "Ramsey RESET test",
         "statistic": round(float(reset.fvalue), 3), "p_value": _p(reset.pvalue),
         "passed": bool(reset.pvalue > ALPHA), "rule": f"p > {ALPHA}",
         "meaning": "Fuel use is a straight-line function of the predictors."},
        {"key": "independence", "assumption": "Independence of errors", "test": "Durbin-Watson statistic",
         "statistic": round(dw, 3), "p_value": None,
         "passed": bool(1.5 <= dw <= 2.5), "rule": "1.5 to 2.5 (2 = no autocorrelation)",
         "meaning": "One trip's error does not depend on another's."},
        {"key": "normality", "assumption": "Normality of errors", "test": "Jarque-Bera test",
         "statistic": round(float(jb_stat), 3), "p_value": _p(jb_p),
         "passed": bool(jb_p > ALPHA), "rule": f"p > {ALPHA}",
         "meaning": f"Residuals follow a normal distribution (skew {float(skew):.2f}, kurtosis {float(kurtosis):.2f})."},
        {"key": "equal_variance", "assumption": "Equal variance of errors", "test": "Breusch-Pagan test",
         "statistic": round(float(bp_lm), 3), "p_value": _p(bp_p),
         "passed": bool(bp_p > ALPHA), "rule": f"p > {ALPHA}",
         "meaning": "The spread of errors is the same for small and large trips."},
        {"key": "multicollinearity", "assumption": "No multicollinearity", "test": "Variance Inflation Factor",
         "statistic": round(float(max_vif), 2), "p_value": None,
         "passed": bool(max_vif <= VIF_THRESHOLD), "rule": f"every VIF ≤ {VIF_THRESHOLD:g}",
         "meaning": "Predictors do not carry the same information."},
    ]
    coefficients = []
    for name in ["const"] + list(numeric_features):
        coefficients.append({
            "feature": "Intercept" if name == "const" else name,
            "coef": float(f"{float(result.params[name]):.4g}"),
            "std_err": float(f"{float(result.bse[name]):.4g}"),
            "p_value": _p(result.pvalues[name]),
            "significant": bool(result.pvalues[name] < ALPHA),
        })
    return {
        "tests": tests,
        "coefficients": coefficients,
        "ols_r2": round(float(result.rsquared), 4),
        "ols_adj_r2": round(float(result.rsquared_adj), 4),
        "alpha": ALPHA,
    }
