"""
Stage 6 - check the wait-time formula against stopwatch measurements.

Each stopwatch sample = one person timed from joining the main-dish line (join_ts) to receiving
the dish (served_ts). The formula predicts their wait from data available when they joined:

    queue at join  = linear interpolation between the two 5-minute queue counts around join_ts
    service rate   = mu of that interval (people/min, busy-interval capacity, see features.py)
    predicted wait = queue at join / service rate

Outputs: reports/wait_validation.md, reports/wait_validation.csv, reports/figures/wait_validation.png
Run:  python -m src.validate_waits
"""
import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from .config import FIGS, MU_FLOOR, PROCESSED, REPORTS
from .features import add_features, fit_priors


def main():
    raw = pd.read_parquet(PROCESSED / "sessions_5min.parquet")
    waits = pd.read_parquet(PROCESSED / "waits.parquet")
    if waits.empty:
        (REPORTS / "wait_validation.md").write_text("# Wait validation\n\nNo stopwatch samples yet.\n")
        print("validate_waits: no samples"); return
    f = add_features(raw, fit_priors(raw))
    rows = []
    for sid, w in waits.groupby("session_id"):
        g = f[f.session_id == sid].sort_values("slot_idx")
        q_end = g["queue_now"].values
        q_start = np.r_[0.0, q_end[:-1]]
        for _, r in w.iterrows():
            k = np.searchsorted(g["interval_end"].values, np.datetime64(r["join_ts"]), side="right")
            if k >= len(g):
                continue
            a, b = g["interval_start"].iloc[k], g["interval_end"].iloc[k]
            frac = (r["join_ts"] - a) / (b - a)
            q = q_start[k] + frac * (q_end[k] - q_start[k])
            mu = max(float(g["mu"].iloc[k]), MU_FLOOR)
            rows.append({"session_id": sid, "tag": r["tag"], "is_synthetic": int(r["is_synthetic"]),
                         "join_ts": r["join_ts"], "queue_at_join": round(q, 1), "service_rate": round(mu, 2),
                         "wait_measured_min": round(r["wait_min"], 2), "wait_predicted_min": round(q / mu, 2)})
    v = pd.DataFrame(rows)
    v["error_min"] = v.wait_predicted_min - v.wait_measured_min
    v.to_csv(REPORTS / "wait_validation.csv", index=False)

    def stats(d):
        return {"n": int(len(d)), "mae_min": round(float(d.error_min.abs().mean()), 2),
                "bias_min": round(float(d.error_min.mean()), 2),
                "within_2min": round(float((d.error_min.abs() <= 2).mean()), 3),
                "corr": round(float(d.wait_measured_min.corr(d.wait_predicted_min)), 3),
                "mae_when_wait_over_3min": round(float(d[d.wait_measured_min > 3].error_min.abs().mean()), 2)
                if (d.wait_measured_min > 3).any() else None,
                "naive_mean_wait_mae": round(float((d.wait_measured_min - d.wait_measured_min.mean()).abs().mean()), 2)}
    out = {}
    for name, d in (("real", v[v.is_synthetic == 0]), ("synthetic", v[v.is_synthetic == 1])):
        if len(d):
            out[name] = stats(d)
    (REPORTS / "wait_validation.json").write_text(json.dumps(out, indent=2))

    fig, ax = plt.subplots(figsize=(4.6, 4.2))
    for name, d, c in (("synthetic", v[v.is_synthetic == 1], "#adb5bd"), ("real", v[v.is_synthetic == 0], "#d9480f")):
        if len(d):
            ax.scatter(d.wait_measured_min, d.wait_predicted_min, s=10, alpha=.6, color=c, label=name)
    m = max(v.wait_measured_min.max(), v.wait_predicted_min.max()) * 1.05
    ax.plot([0, m], [0, m], "k--", lw=.8)
    ax.set_xlabel("measured wait (stopwatch), min"); ax.set_ylabel("queue / service rate, min")
    ax.set_title("Wait formula vs stopwatch"); ax.legend(frameon=False)
    fig.tight_layout(); fig.savefig(FIGS / "wait_validation.png"); plt.close(fig)

    lines = ["# Wait-time validation (stopwatch)", "",
             "Formula: predicted wait = queue at join / service rate. Queue at join is interpolated between the "
             "5-minute counts; service rate is the busy-interval capacity.", ""]
    if "real" not in out:
        lines += ["**No real stopwatch samples yet.** The synthetic check below only shows the procedure works. "
                  "Time 10 or more people per real meal and put them in `data/real/waits/`.", ""]
    for name, s in out.items():
        lines += [f"## {name.capitalize()} samples", "",
                  f"- n = {s['n']}; MAE = {s['mae_min']} min; bias = {s['bias_min']} min; "
                  f"within +/-2 min: {s['within_2min']:.0%}; correlation {s['corr']}",
                  f"- MAE when the measured wait is over 3 min: {s['mae_when_wait_over_3min']} min",
                  f"- Naive guess (always the average wait) MAE: {s['naive_mean_wait_mae']} min", ""]
    lines += ["![wait](figures/wait_validation.png)", ""]
    (REPORTS / "wait_validation.md").write_text("\n".join(lines))
    print("validate_waits:", out)


if __name__ == "__main__":
    main()
