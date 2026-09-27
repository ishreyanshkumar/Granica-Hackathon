"""Model definitions shared by training, evaluation, prediction and the dashboard."""
import numpy as np
import pandas as pd
from sklearn.neural_network import MLPRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from xgboost import XGBRegressor

from .config import HORIZONS, INTERVAL_MIN, RANDOM_SEED
from .features import FEATURES

XGB_DEFAULT = dict(n_estimators=400, learning_rate=0.05, max_depth=4, min_child_weight=3,
                   subsample=0.9, colsample_bytree=0.9, reg_lambda=1.0)


def make_xgb(params=None, objective="reg:absoluteerror", alpha=None):
    p = dict(XGB_DEFAULT, **(params or {}))
    kw = dict(objective=objective, random_state=RANDOM_SEED, n_jobs=-1, tree_method="hist")
    if alpha is not None:
        kw["quantile_alpha"] = alpha
    return XGBRegressor(**p, **kw)


def make_mlp():
    return make_pipeline(StandardScaler(), MLPRegressor(
        hidden_layer_sizes=(64, 32), alpha=1e-3, learning_rate_init=1e-3, max_iter=3000,
        early_stopping=True, validation_fraction=0.15, n_iter_no_change=30,
        random_state=RANDOM_SEED))


# ------------------------------------------------------------------ baselines
def baseline_predictions(f: pd.DataFrame, priors: dict, h: int) -> dict:
    qprof = priors["queue_profile"]
    seasonal = np.array([qprof.get((m, w, s + h), np.nan) for m, w, s in
                         zip(f["meal"], f["weekday"], f["slot_idx"])], float)
    seasonal = np.where(np.isnan(seasonal), f["queue_now"], seasonal)
    exp_in = f[[f"prof_in_{k}" for k in range(1, h + 1)]].sum(axis=1)       # expected arrivals
    physics = (f["queue_now"] + exp_in - f["mu"] * INTERVAL_MIN * h).clip(lower=0)
    return {"persistence": f["queue_now"].values,
            "seasonal_profile": seasonal,
            "physics_profile": physics.values,
            "experimental_formula": f["queue_heur"].values}


# ------------------------------------------------------------------ fit / predict bundle
def fit_bundle(train_f: pd.DataFrame, priors: dict, kind="xgb", params=None, quantiles=True):
    """One model per horizon, trained on the change in queue (y_d{h})."""
    bundle = {"kind": kind, "priors": priors, "models": {}, "lo": {}, "hi": {}, "features": FEATURES}
    for h in HORIZONS:
        d = train_f.dropna(subset=[f"y_d{h}"])
        X, y = d[FEATURES].values, d[f"y_d{h}"].values
        m = make_xgb(params) if kind == "xgb" else make_mlp()
        m.fit(X, y)
        bundle["models"][h] = m
        if quantiles and kind == "xgb":
            bundle["lo"][h] = make_xgb(params, "reg:quantileerror", 0.1).fit(X, y)
            bundle["hi"][h] = make_xgb(params, "reg:quantileerror", 0.9).fit(X, y)
    return bundle


def predict_bundle(f: pd.DataFrame, bundle) -> pd.DataFrame:
    out = f.copy()
    X = out[bundle["features"]].values
    for h in HORIZONS:
        base = out["queue_now"].values
        out[f"q_pred{h}"] = np.clip(base + bundle["models"][h].predict(X), 0, None)
        if h in bundle["lo"]:
            lo = np.clip(base + bundle["lo"][h].predict(X), 0, None)
            hi = np.clip(base + bundle["hi"][h].predict(X), 0, None)
            out[f"q_lo{h}"] = np.minimum(lo, out[f"q_pred{h}"])
            out[f"q_hi{h}"] = np.maximum(hi, out[f"q_pred{h}"])
    return out
