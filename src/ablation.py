"""
Feature ablation: does adding the historical queue profile (prof_q_*) help the XGB forecaster?

Runs XGB (point model only) on the forward out-of-sample split (same split used in src/train.py -
last 5 days held out, trained on earlier days) with and without the extra features, and writes
reports/ablation_queue_profile.md.

Run:  python -m src.ablation     (reads data/processed and reports/model_summary.json)
"""
import json

import numpy as np
import pandas as pd

from . import features as F
from .config import CONGESTED_QUEUE, HORIZONS, INTERVAL_MIN, PROCESSED, REPORTS
from .model import make_xgb


def score(tr_raw, te_raw, feats, params):
    pri = F.fit_priors(tr_raw)
    tr, te = F.add_features(tr_raw, pri), F.add_features(te_raw, pri)
    out = []
    for h in HORIZONS:
        a = tr.dropna(subset=[f"y_d{h}"]); b = te.dropna(subset=[f"y_d{h}"])
        m = make_xgb(params).fit(a[feats], a[f"y_d{h}"])
        p = np.clip(b["queue_now"] + m.predict(b[feats]), 0, None); t = b[f"y_q{h}"]
        c = t >= CONGESTED_QUEUE
        out.append({"h": h * INTERVAL_MIN, "mae": float(np.abs(p - t).mean()),
                    "mae_congested": float(np.abs(p[c] - t[c]).mean()) if c.any() else np.nan})
    return out


def main():
    raw = pd.read_parquet(PROCESSED / "sessions_5min.parquet")
    raw["date"] = raw["interval_start"].dt.normalize()
    params = json.loads((REPORTS / "model_summary.json").read_text())["xgb_params"]

    # Forward split: strictly out-of-sample (last 5 days held out)
    d = raw["date"]
    cut = d.sort_values().unique()[-5] if d.nunique() > 5 else d.max()
    tr_raw, te_raw = raw[d < cut], raw[d >= cut]

    sets = {"model features": F.FEATURES, "+ queue profile": F.FEATURES + F.QUEUE_PROFILE_FEATURES}
    rows = []
    for name, feats in sets.items():
        for r in score(tr_raw, te_raw, feats, params):
            rows.append({"split": "forward", "features": name, **r})

    df = pd.DataFrame(rows)
    t = df.groupby(["features", "h"])["mae_congested"].mean().unstack().round(2)
    t.columns = [f"{c} min" for c in t.columns]
    t = t.reset_index()
    overall = df.groupby("features")["mae_congested"].mean().round(2)
    md = ["# Ablation: historical queue-profile features", "",
          f"XGBoost, congested-interval MAE (people, true line >= {CONGESTED_QUEUE}), "
          f"forward out-of-sample split (last 5 days held out). Lower is better.", "",
          t.to_markdown(index=False), "",
          "Mean over horizons: " + ", ".join(f"{k} **{v}**" for k, v in overall.items()), "",
          "Decision: " + ("the queue-profile features are **left out** of the model (they fit past queues too closely "
                          "and forecast worse on unseen days)." if overall["+ queue profile"] > overall["model features"]
                          else "the queue-profile features **help** and should be added to FEATURES."), ""]
    (REPORTS / "ablation_queue_profile.md").write_text("\n".join(md))
    print("ablation:", overall.to_dict())


if __name__ == "__main__":
    main()
