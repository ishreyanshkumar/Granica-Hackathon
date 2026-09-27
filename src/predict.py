"""
Stage 5 - forecasts + decisions for the dashboard and for live use.

  python -m src.predict                 # out-of-sample predictions for the dashboard / demo
                                        #   forward split: last 5 days held out, model trained on earlier days.
                                        #   includes both synthetic weekday and real weekend sessions in test window.
  python -m src.predict --session ID    # live-style forecast for one session with the final model

Output: reports/predictions_dashboard.parquet (+ .csv)
"""
import argparse
import json

import joblib
import pandas as pd

from .config import MODELS, PROCESSED, REPORTS
from .features import add_features, fit_priors
from .model import fit_bundle, predict_bundle
from .recommend import apply


def _bundle(train_raw, kind, params):
    pri = fit_priors(train_raw)
    tr_f = add_features(train_raw, pri)
    b = fit_bundle(tr_f, pri, kind, params if kind == "xgb" else None)
    if kind != "xgb":
        q = fit_bundle(tr_f, pri, "xgb", params)
        b["lo"], b["hi"] = q["lo"], q["hi"]
    return b, pri


def out_of_sample():
    """
    Forward-split out-of-sample predictions for the dashboard.
    Train on all days before the chronological cutoff (last 5 unique dates held out).
    Both synthetic weekday sessions and real weekend sessions in the test window are predicted
    by a single model that has never seen those dates - strictly no leakage.
    """
    raw = pd.read_parquet(PROCESSED / "sessions_5min.parquet")
    raw["date"] = raw["interval_start"].dt.normalize()
    summ = json.loads((REPORTS / "model_summary.json").read_text())
    kind, params = summ["chosen_model"], summ["xgb_params"]

    # Forward split: chronological cutoff — last 5 unique operational dates are held out
    cut = raw["date"].sort_values().unique()[-5] if raw["date"].nunique() > 5 else raw["date"].max()
    train_raw = raw[raw.date < cut]
    test_raw = raw[raw.date >= cut]

    b, pri = _bundle(train_raw, kind, params)
    te = add_features(test_raw, pri)
    out = apply(predict_bundle(te, b))

    out.to_parquet(REPORTS / "predictions_dashboard.parquet", index=False)
    keep = ["session_id", "interval_end", "main_dish", "meal", "weekday", "in_count", "out_count",
            "queue_len", "queue_now", "mu", "wait_now",
            "q_pred1", "q_pred2", "q_pred3", "q_lo3", "q_hi3",
            "wait_pred1", "wait_pred2", "wait_pred3",
            "alert", "service_rate_required", "items_rate_required", "service_gap_pct",
            "student_advice", "is_synthetic"]
    available = [c for c in keep if c in out.columns]
    csv = out[available].copy()
    num = csv.select_dtypes("number").columns
    csv[num] = csv[num].round(2)
    csv.to_csv(REPORTS / "predictions_dashboard.csv", index=False)
    n_real = int((out.is_synthetic == 0).sum() > 0)
    print(f"predict: {out.session_id.nunique()} sessions ({n_real} real), {len(out)} rows "
          f"-> reports/predictions_dashboard.parquet  [forward split, cutoff {cut.date()}]")
    return out


def live(session_id):
    b = joblib.load(MODELS / "queue_forecaster.joblib")
    raw = pd.read_parquet(PROCESSED / "sessions_5min.parquet")
    g = raw[raw.session_id == session_id]
    if g.empty:
        raise SystemExit(f"Session '{session_id}' not found - available sessions: {list(raw.session_id.unique())[:5]}...")
    res = apply(predict_bundle(add_features(g, b["priors"]), b))
    last = res.iloc[-1]
    print(f"\n=== Live Prediction: {session_id} ===")
    print(f"Time: {last['interval_end']:%H:%M} | Dish: {last['main_dish']} | Line Now: {int(last['queue_now'])} people")
    print(f"Forecast (+5m / +10m / +15m): {last['q_pred1']:.1f} / {last['q_pred2']:.1f} / {last['q_pred3']:.1f} people")
    print(f"Estimated Wait: {last['wait_pred1']:.1f} min (Alert: {last['alert']})")
    print(f"Manager: {last['manager_message']}")
    print(f"Student: {last['student_advice']}\n")
    return res


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Smart Mess Queue Forecaster")
    ap.add_argument("pos_session", nargs="?", default=None, help="Session ID (optional positional argument)")
    ap.add_argument("--session", default=None, help="Session ID (optional flag)")
    a = ap.parse_args()
    sid = a.session or a.pos_session
    live(sid) if sid else out_of_sample()
