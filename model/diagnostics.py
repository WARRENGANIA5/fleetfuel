"""
Regression diagnostics (Chapter II, Theoretical Background; Chapter III, How
the Project Will Work), computed with statsmodels:

* Variance Inflation Factor (VIF) of each predictor - a value above 5
  indicates high collinearity (reported; the equation's four terms are kept).
* LINE conditions on the residuals of an OLS fit of the same equation:
    Linearity        - Ramsey RESET test
    Independence     - Durbin-Watson statistic on the residuals of the LOCAL
                       trips arranged by the date of travel
    Normality        - Jarque-Bera test (with the residual histogram)
    Equal variance   - Breusch-Pagan test
* Coefficient standard errors and p-values use heteroskedasticity-robust
  (HC3) standard errors, which stay valid when the equal-variance condition
  is not met (larger errors on longer trips).
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
VIF_CAP = 1000.0  # perfect collinearity gives an infinite VIF; stored as ">1000"


def compute_vif(frame):
    """VIF_j = 1 / (1 - R_j^2) for every column of `frame`, with an intercept.
    A column with the same value in every record has no VIF (None)."""
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


def regression_diagnostics(terms_train, y_train, vif, local_residuals_by_date=None):
    """Fit OLS on the training split with the model's terms and test the LINE
    conditions. `local_residuals_by_date` are the residuals of the local trips
    in date order (for the Durbin-Watson test); without local trips the test
    falls back to the training residuals."""
    usable = [c for c in terms_train.columns if terms_train[c].astype(float).std() > 0]
    design = sm.add_constant(terms_train[usable].astype(float), has_constant="add")
    y = np.asarray(y_train, dtype=float)
    result = sm.OLS(y, design).fit()
    resid = np.asarray(result.resid)

    reset = linear_reset(result, power=2, use_f=True)
    if local_residuals_by_date is not None and len(local_residuals_by_date) >= 3:
        dw = float(durbin_watson(np.asarray(local_residuals_by_date, dtype=float)))
        dw_note = f"Residuals of the {len(local_residuals_by_date)} local trips arranged by date of travel."
    else:
        dw = float(durbin_watson(resid))
        dw_note = "No dated local trips yet: computed on the training residuals."
    jb_stat, jb_p, skew, kurtosis = jarque_bera(resid)
    bp_lm, bp_p, _, _ = het_breuschpagan(resid, design)
    vif_values = [v for v in vif.values() if v is not None]
    max_vif = max(vif_values) if vif_values else 0.0

    tests = [
        {"key": "linearity", "assumption": "Linearity", "test": "Ramsey RESET test",
         "statistic": round(float(reset.fvalue), 3), "p_value": _p(reset.pvalue),
         "passed": bool(reset.pvalue > ALPHA), "rule": f"p > {ALPHA}",
         "meaning": "Fuel consumed is a straight-line function of the predictors."},
        {"key": "independence", "assumption": "Independence of errors", "test": "Durbin-Watson statistic",
         "statistic": round(dw, 3), "p_value": None,
         "passed": bool(1.5 <= dw <= 2.5), "rule": "1.5 to 2.5 (close to 2 = independent)",
         "meaning": dw_note},
        {"key": "normality", "assumption": "Normality of errors", "test": "Jarque-Bera test",
         "statistic": round(float(jb_stat), 3), "p_value": _p(jb_p),
         "passed": bool(jb_p > ALPHA), "rule": f"p > {ALPHA}",
         "meaning": f"Residuals follow a normal distribution (skew {float(skew):.2f}, kurtosis {float(kurtosis):.2f})."},
        {"key": "equal_variance", "assumption": "Equal variance of errors", "test": "Breusch-Pagan test",
         "statistic": round(float(bp_lm), 3), "p_value": _p(bp_p),
         "passed": bool(bp_p > ALPHA), "rule": f"p > {ALPHA}",
         "meaning": "The spread of errors is the same for short and long trips."},
        {"key": "multicollinearity", "assumption": "No multicollinearity", "test": "Variance Inflation Factor",
         "statistic": round(float(max_vif), 2), "p_value": None,
         "passed": bool(max_vif <= VIF_THRESHOLD), "rule": f"every VIF ≤ {VIF_THRESHOLD:g}",
         "meaning": "Predictors do not carry the same information (an interaction term usually shares "
                    "information with the predictors it is built from)."},
    ]
    # Same coefficients; HC3 robust standard errors for the significance tests.
    robust = sm.OLS(y, design).fit(cov_type="HC3")
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
        "alpha": ALPHA,
        "std_err_type": "HC3 (heteroskedasticity-robust)",
    }
