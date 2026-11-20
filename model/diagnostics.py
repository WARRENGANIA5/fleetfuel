"""
Regression diagnostics with statsmodels:

* VIF per predictor (above 5 = high collinearity)
* LINE checks on the standardized (weighted) residuals:
    Linearity        - Ramsey RESET (+ Cohen's f2 for large samples)
    Independence     - Durbin-Watson (local trips by date)
    Normality        - Jarque-Bera (+ skewness / kurtosis for large samples)
    Equal variance   - Breusch-Pagan (+ variance ratio for large samples)
* p-values use HC3 robust standard errors
"""
import math
import warnings

import numpy as np
import statsmodels.api as sm
from statsmodels.stats.diagnostic import het_breuschpagan, linear_reset
from statsmodels.stats.outliers_influence import variance_inflation_factor
from statsmodels.stats.stattools import durbin_watson, jarque_bera

VIF_THRESHOLD = 5.0
ALPHA = 0.05
VIF_CAP = 1000.0  # infinite VIF is stored as ">1000"
LARGE_SAMPLE = 300       # above this, decide by effect size (Kim, 2013)
F2_SMALL = 0.02          # Cohen's small effect
SKEW_LIMIT = 2.0
KURTOSIS_LIMIT = 7.0     # excess kurtosis
VARIANCE_GROUPS = 5
VARIANCE_RATIO_LIMIT = 3.0


def compute_vif(frame):
    """VIF_j = 1 / (1 - R_j^2) per column. None for constant columns."""
    usable = [c for c in frame.columns if frame[c].astype(float).std() > 0]
    out = {c: None for c in frame.columns if c not in usable}
    if len(usable) < 2:
        out.update({c: 1.0 for c in usable})
        return out
    X = sm.add_constant(frame[usable].astype(float), has_constant="add")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")  # divide-by-zero for perfectly collinear columns
        for i, col in enumerate(X.columns):
            if col == "const":
                continue
            value = variance_inflation_factor(X.values, i)
            out[col] = VIF_CAP if (not math.isfinite(value) or value > VIF_CAP) else round(float(value), 2)
    return out


def _p(value):
    return None if value is None or not math.isfinite(float(value)) else round(float(value), 4)


def regression_diagnostics(terms_train, y_train, vif, local_residuals_by_date=None, weights=None):
    """Fit the regression on the training split (WLS when `weights` is given)
    and run the LINE checks on its standardized residuals.

    The tests' p-values are shown, but with more than LARGE_SAMPLE records
    they flag even trivial departures, so the decision then uses the size
    of the departure (Kim, 2013; Cohen, 1988):
        Linearity       Cohen's f2 of the RESET term < 0.02 (below a small effect)
        Normality       |skewness| <= 2 and |excess kurtosis| <= 7
        Equal variance  largest / smallest residual variance across five
                        groups of predicted fuel <= 3 (Hartley's F-max)
    `local_residuals_by_date` is used for Durbin-Watson if given."""
    usable = [c for c in terms_train.columns if terms_train[c].astype(float).std() > 0]
    design = sm.add_constant(terms_train[usable].astype(float), has_constant="add")
    y = np.asarray(y_train, dtype=float)
    w = np.ones(len(y)) if weights is None else np.asarray(weights, dtype=float)
    result = sm.WLS(y, design, weights=w).fit()
    # standardized residuals: equal variance when the weights are right
    resid = np.asarray(result.resid) * np.sqrt(w)
    fitted = np.asarray(result.fittedvalues)
    n = len(y)
    large = n > LARGE_SAMPLE

    reset = linear_reset(result, power=2, use_f=True)
    with_square = sm.WLS(y, np.column_stack([design, fitted ** 2]), weights=w).fit()
    f2 = max(with_square.rsquared - result.rsquared, 0.0) / max(1 - with_square.rsquared, 1e-12)

    if local_residuals_by_date is not None and len(local_residuals_by_date) >= 3:
        local = np.asarray(local_residuals_by_date, dtype=float)
        # a constant bias for one vehicle is not serial correlation, so it is removed first
        dw = float(durbin_watson(local - local.mean()))
        dw_note = (f"Residuals of the {len(local)} local trips arranged by date of travel "
                   f"(their average of {local.mean():+.2f} L removed).")
    else:
        dw = float(durbin_watson(resid))
        dw_note = "No dated local trips yet: computed on the training residuals."

    jb_stat, jb_p, skew, kurtosis = jarque_bera(resid)
    excess = float(kurtosis) - 3.0
    bp_lm, bp_p, _, _ = het_breuschpagan(resid, design)
    groups = np.array_split(np.argsort(fitted, kind="stable"), VARIANCE_GROUPS)
    variances = [float(np.var(resid[g], ddof=1)) for g in groups if len(g) > 1]
    variance_ratio = max(variances) / min(variances) if variances and min(variances) > 0 else float("inf")

    vif_values = [v for v in vif.values() if v is not None]
    max_vif = max(vif_values) if vif_values else 0.0
    size_note = (f"With {n:,} records the p-value flags even trivial departures, so the decision uses the "
                 f"size of the departure." if large else "")

    tests = [
        {"key": "linearity", "assumption": "Linearity", "test": "Ramsey RESET test",
         "statistic": round(float(reset.fvalue), 3), "p_value": _p(reset.pvalue),
         "effect": round(float(f2), 5), "effect_name": "Cohen's f²",
         "passed": bool(f2 < F2_SMALL) if large else bool(reset.pvalue > ALPHA),
         "rule": f"f² < {F2_SMALL} (n > {LARGE_SAMPLE})" if large else f"p > {ALPHA}",
         "meaning": "Fuel consumed is a straight-line function of the predictors. " + size_note},
        {"key": "independence", "assumption": "Independence of errors", "test": "Durbin-Watson statistic",
         "statistic": round(dw, 3), "p_value": None,
         "passed": bool(1.5 <= dw <= 2.5), "rule": "1.5 to 2.5 (close to 2 = independent)",
         "meaning": dw_note},
        {"key": "normality", "assumption": "Normality of errors", "test": "Jarque-Bera test",
         "statistic": round(float(jb_stat), 3), "p_value": _p(jb_p),
         "skewness": round(float(skew), 3), "excess_kurtosis": round(excess, 3),
         "passed": bool(abs(skew) <= SKEW_LIMIT and abs(excess) <= KURTOSIS_LIMIT) if large else bool(jb_p > ALPHA),
         "rule": f"|skew| ≤ {SKEW_LIMIT:g}, |kurtosis| ≤ {KURTOSIS_LIMIT:g} (n > {LARGE_SAMPLE})" if large
                 else f"p > {ALPHA}",
         "meaning": f"Residuals follow a normal distribution (skew {float(skew):.2f}, excess kurtosis {excess:.2f}). "
                    + size_note},
        {"key": "equal_variance", "assumption": "Equal variance of errors", "test": "Breusch-Pagan test",
         "statistic": round(float(bp_lm), 3), "p_value": _p(bp_p),
         "effect": round(float(variance_ratio), 3), "effect_name": "variance ratio",
         "passed": bool(variance_ratio <= VARIANCE_RATIO_LIMIT) if large else bool(bp_p > ALPHA),
         "rule": f"variance ratio ≤ {VARIANCE_RATIO_LIMIT:g} (n > {LARGE_SAMPLE})" if large else f"p > {ALPHA}",
         "meaning": "The spread of errors is the same for short and long trips (largest / smallest residual "
                    f"variance across {VARIANCE_GROUPS} groups of predicted fuel). " + size_note},
        {"key": "multicollinearity", "assumption": "No multicollinearity", "test": "Variance Inflation Factor",
         "statistic": round(float(max_vif), 2), "p_value": None,
         "passed": bool(max_vif <= VIF_THRESHOLD), "rule": f"every VIF ≤ {VIF_THRESHOLD:g}",
         "meaning": "Predictors do not carry the same information (an interaction term usually shares "
                    "information with the predictors it is built from)."},
    ]
    for t in tests:
        t["meaning"] = t["meaning"].strip()
    # HC3 robust standard errors
    robust = sm.WLS(y, design, weights=w).fit(cov_type="HC3")
    coefficients = []
    for name in ["const"] + usable:
        coefficients.append({
            "feature": "Intercept" if name == "const" else name,
            "coef": float(f"{float(robust.params[name]):.4g}"),
            "std_err": float(f"{float(robust.bse[name]):.4g}"),
            "p_value": _p(robust.pvalues[name]),
            "significant": bool(robust.pvalues[name] < ALPHA),
        })
    return {
        "tests": tests,
        "coefficients": coefficients,
        "constant_terms": [c for c in terms_train.columns if c not in usable],
        "ols_r2": round(float(result.rsquared), 4),
        "ols_adj_r2": round(float(result.rsquared_adj), 4),
        "estimation": ("Weighted least squares (weights = 1 / estimated error variance)" if weights is not None
                       else "Ordinary least squares"),
        "records": int(n),
        "alpha": ALPHA,
        "std_err_type": "HC3 (heteroskedasticity-robust)",
    }
