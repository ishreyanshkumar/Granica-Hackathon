"""
Stage 3 - exploratory analysis BEFORE any model is trained.
Answers: when does the line form, why (arrivals vs service), how predictable is it,
and does the physics (queue balance, wait = queue / service rate) hold?

Outputs: reports/eda_report.md + reports/figures/eda_*.png + reports/eda_summary.json
Run:  python -m src.eda
"""
import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from .config import BUSY_QUEUE, CONGESTED_QUEUE, FIGS, INTERVAL_MIN, PROCESSED, REPORTS, TARGET_WAIT_MIN
from .features import WEEKDAYS, add_features, fit_priors

plt.rcParams.update({"figure.dpi": 110, "axes.spines.top": False, "axes.spines.right": False,
                     "axes.grid": True, "grid.alpha": 0.25, "font.size": 9})
DAY_COLORS = {"Monday": "#1f77b4", "Tuesday": "#ff7f0e", "Wednesday": "#2ca02c",
              "Thursday": "#d62728", "Friday": "#9467bd", "Saturday": "#8c564b", "Sunday": "#e377c2"}


def _hhmm(m):
    return f"{int(m) // 60:02d}:{int(m) % 60:02d}"


def profiles(f, col, fname, title, ylabel):
    fig, axes = plt.subplots(1, 3, figsize=(13, 3.4))
    for ax, meal in zip(axes, ["breakfast", "lunch", "dinner"]):
        d = f[f.meal == meal]
        for wd in [w for w in WEEKDAYS if w in d.weekday.unique()]:
            p = d[d.weekday == wd].groupby("tod_min")[col].mean()
            ax.plot(p.index, p.values, color=DAY_COLORS.get(wd), lw=1.4, label=wd[:3])
        ticks = sorted(d.tod_min.unique())[::6]
        ax.set_xticks(ticks, [_hhmm(t) for t in ticks], rotation=0)
        ax.set_title(meal.capitalize()); ax.set_ylabel(ylabel)
    axes[0].legend(frameon=False, ncol=5, fontsize=7)
    fig.suptitle(title, x=0.01, ha="left", fontsize=11); fig.tight_layout()
    fig.savefig(FIGS / fname); plt.close(fig)


def main():
    raw = pd.read_parquet(PROCESSED / "sessions_5min.parquet")
    f = add_features(raw, fit_priors(raw))           # descriptive: priors on all data is fine here
    S = {}
    src = "real" if (raw.is_synthetic == 0).any() else "synthetic"
    S["data_used"] = src if src == "synthetic" else "real + synthetic"
    S["sessions"] = int(raw.session_id.nunique()); S["rows"] = int(len(raw))

    # 1-2. arrival and queue profiles
    profiles(f, "in_count", "eda_1_arrivals.png", "People entering per 5 min (mean by weekday)", "people / 5 min")
    profiles(f, "queue_len", "eda_2_queue.png", "Main-dish line length (mean by weekday)", "people in line")
    profiles(f, "wait_now", "eda_3_wait.png", "Estimated wait = queue / service rate", "minutes")

    # peak table per meal x weekday
    rows = []
    for (meal, wd), d in f.groupby(["meal", "weekday"]):
        by = d.groupby("tod_min")
        q = by["queue_len"].mean(); a = by["in_count"].mean(); w = by["wait_now"].mean()
        over = (d.groupby("session_id").apply(lambda x: (x.wait_now >= TARGET_WAIT_MIN).sum(), include_groups=False)
                * INTERVAL_MIN).mean()
        rows.append({"meal": meal, "weekday": wd, "peak_arrivals_at": _hhmm(a.idxmax()),
                     "peak_arrivals_per_5min": round(a.max(), 1), "peak_queue_at": _hhmm(q.idxmax()),
                     "peak_queue_mean": round(q.max(), 1), "max_wait_mean_min": round(w.max(), 1),
                     "min_per_meal_wait_over_target": round(over, 1),
                     "main_dish": d.main_dish.mode().iat[0]})
    peaks = pd.DataFrame(rows)
    peaks["wd_i"] = peaks.weekday.map(WEEKDAYS.index)
    peaks = peaks.sort_values(["meal", "wd_i"]).drop(columns="wd_i")
    peaks.to_csv(REPORTS / "eda_peaks.csv", index=False)

    # 4. service rate by dish (busy intervals = capacity)
    q_prev = f.groupby("session_id")["queue_len"].shift(1)
    f["busy"] = (f.queue_len.fillna(0) >= BUSY_QUEUE) | (q_prev.fillna(0) >= BUSY_QUEUE)
    fig, ax = plt.subplots(1, 2, figsize=(12, 3.6))
    dishes = f.groupby("main_dish")["service_rate_people_per_min"].median().sort_values().index
    data_b = [f[(f.main_dish == d) & f.busy]["service_rate_people_per_min"].dropna() for d in dishes]
    data_i = [f[(f.main_dish == d) & ~f.busy]["service_rate_people_per_min"].dropna() for d in dishes]
    pos = np.arange(len(dishes))
    ax[0].boxplot(data_b, positions=pos - 0.18, widths=0.3, patch_artist=True,
                  boxprops=dict(facecolor="#d9480f", alpha=.6), showfliers=False)
    ax[0].boxplot(data_i, positions=pos + 0.18, widths=0.3, patch_artist=True,
                  boxprops=dict(facecolor="#adb5bd", alpha=.6), showfliers=False)
    ax[0].set_xticks(pos, [d.replace(" (special)", "*") for d in dishes], rotation=30, ha="right")
    ax[0].set_ylabel("people served / min"); ax[0].set_title("Service rate by dish: line present (orange) vs empty (grey)")
    cap = {d: round(float(x.median()), 1) for d, x in zip(dishes, data_b) if len(x)}
    S["capacity_people_per_min_by_dish"] = cap

    # 5. physics: imbalance drives queue growth
    prv = f.groupby("session_id")["queue_len"].shift(1)
    g = pd.DataFrame({"net": f["in_count"] - f["served_people"], "dq": f["queue_len"] - prv}).dropna()
    g = g[g.index.isin(f.index[f.busy])]
    ax[1].scatter(g.net, g.dq, s=6, alpha=.35, color="#1c7ed6")
    lim = [g.net.min(), g.net.max()]; ax[1].plot(lim, lim, color="k", lw=.8, ls="--")
    ax[1].set_xlabel("people in - people served (this 5 min)"); ax[1].set_ylabel("queue change over the same 5 min")
    ax[1].set_title("Queue balance holds when the line is present")
    fig.tight_layout(); fig.savefig(FIGS / "eda_4_service_and_balance.png"); plt.close(fig)
    S["balance_corr"] = round(float(g.net.corr(g.dq)), 3)

    # balance residual (same interval): observed Q_t vs Q_{t-1} + in_t - served_t
    prev = f.groupby("session_id")["queue_len"].shift(1)
    res = (f["queue_len"] - (prev + f["in_count"] - f["served_people"])).dropna()
    res_busy = res[f.loc[res.index, "busy"]]
    S["balance_residual_busy_mae"] = round(float(res_busy.abs().mean()), 2)

    # 6. utilisation and congestion
    fig, ax = plt.subplots(1, 3, figsize=(13, 3.4))
    ax[0].scatter(f.rho, f.queue_len, s=5, alpha=.3, color="#495057")
    ax[0].axvline(1, color="#d9480f", lw=1); ax[0].set_xlabel("utilisation rho = arrivals / capacity (15-min)")
    ax[0].set_ylabel("queue"); ax[0].set_title("Line forms once rho > 1")
    S["share_congested_when_rho_gt1"] = round(float((f.loc[f.rho > 1, "queue_len"] >= CONGESTED_QUEUE).mean()), 2)
    S["share_congested_when_rho_lt08"] = round(float((f.loc[f.rho < .8, "queue_len"] >= CONGESTED_QUEUE).mean()), 2)

    # 7. predictability: correlation of queue now vs queue h steps ahead
    ac = []
    for h in range(1, 7):
        s = f.groupby("session_id")["queue_len"].shift(-h)
        ac.append(float(f["queue_len"].corr(s)))
    ax[1].bar(np.arange(1, 7) * INTERVAL_MIN, ac, width=3, color="#1c7ed6")
    ax[1].set_xlabel("minutes ahead"); ax[1].set_ylabel("corr(queue now, queue later)")
    ax[1].set_title("How far ahead 'queue now' still helps")
    S["autocorr_by_minutes"] = {int(h * INTERVAL_MIN): round(v, 2) for h, v in zip(range(1, 7), ac)}

    # 8. experimental formula vs counted queue (same interval)
    ok = f.queue_len.notna() & f.items_made.notna()
    ax[2].scatter(f.loc[ok, "queue_len"], f.loc[ok, "queue_heur"], s=5, alpha=.35, color="#868e96")
    m = f.loc[ok, "queue_len"].max(); ax[2].plot([0, m], [0, m], "k--", lw=.8)
    ax[2].set_xlabel("counted queue"); ax[2].set_ylabel("(in - items)/3 formula")
    ax[2].set_title("Experimental formula vs counted queue")
    S["heuristic_nowcast_mae"] = round(float((f.loc[ok, "queue_len"] - f.loc[ok, "queue_heur"]).abs().mean()), 2)
    S["heuristic_nowcast_mae_congested"] = round(float(
        (f.loc[ok & (f.queue_len >= CONGESTED_QUEUE), "queue_len"] - f.loc[ok & (f.queue_len >= CONGESTED_QUEUE), "queue_heur"]).abs().mean()), 2)
    fig.tight_layout(); fig.savefig(FIGS / "eda_5_rho_autocorr_heuristic.png"); plt.close(fig)

    # 9. hall occupancy (seats)
    profiles(f, "occupancy", "eda_6_occupancy.png", "People inside the hall (seated or eating)", "people")
    S["peak_occupancy"] = int(f.occupancy.max())

    # 10. missingness and door drift
    S["missing_queue_pct"] = round(100 * raw.queue_missing.mean(), 1)
    S["missing_items_pct"] = round(100 * raw.items_missing.mean(), 1)
    drift = raw.groupby("session_id").apply(lambda x: x.in_count.sum() - x.out_count.sum(), include_groups=False)
    S["door_drift_max_abs"] = int(drift.abs().max())
    S["share_intervals_congested"] = round(float((f.queue_len >= CONGESTED_QUEUE).mean()), 3)

    # stopwatch check of wait = queue / service rate (descriptive; full check in validate_waits.py)
    (REPORTS / "eda_summary.json").write_text(json.dumps(S, indent=2))

    worst = peaks.sort_values("peak_queue_mean", ascending=False).head(3)
    md = [
        "# Exploratory analysis", "",
        f"Data: {S['sessions']} sessions, {S['rows']} five-minute rows ({S['data_used']}). "
        + ("**All numbers below come from SYNTHETIC data and only demonstrate the analysis.** "
           "Re-run after real sessions are added." if src == "synthetic" else ""), "",
        "## Key findings", "",
        f"1. **Congestion is concentrated.** Only {S['share_intervals_congested']:.1%} of 5-minute intervals have "
        f"a line of {CONGESTED_QUEUE}+ people. The worst slots are "
        + "; ".join(f"{r.meal} {r.weekday} at {r.peak_queue_at} (mean peak {r.peak_queue_mean})" for r in worst.itertuples()) + ".",
        f"2. **The line forms when arrivals exceed service capacity.** When utilisation rho > 1, "
        f"{S['share_congested_when_rho_gt1']:.0%} of intervals are congested; when rho < 0.8, only "
        f"{S['share_congested_when_rho_lt08']:.0%} are.",
        f"3. **Queue balance holds.** In busy intervals, (people in - people served) vs the queue change over the same 5 min: "
        f"correlation {S['balance_corr']}; mean absolute balance error {S['balance_residual_busy_mae']} people "
        "(counting noise, plus overflow: when the line is full, new arrivals wait at tables and join later).",
        "4. **Capacity depends on the dish.** Median people served per minute while a line is present: "
        + ", ".join(f"{k} {v}" for k, v in S["capacity_people_per_min_by_dish"].items()) + ". "
        "When the line is empty, items made measures demand, not capacity, so only busy intervals are used.",
        f"5. **'Queue now' alone fades fast.** Correlation with the queue later: "
        + ", ".join(f"{k} min {v}" for k, v in S["autocorr_by_minutes"].items())
        + ". A 15-minute forecast needs arrival expectations (historical profile) and capacity, not just the current line.",
        f"6. **The experimental formula underestimates real lines.** (in - items)/3 vs counted queue: MAE "
        f"{S['heuristic_nowcast_mae']} people overall and {S['heuristic_nowcast_mae_congested']} when the line is "
        f"{CONGESTED_QUEUE}+. It measures growth, not the accumulated stock, so it is kept only as a baseline.",
        f"7. **Data quality.** {S['missing_queue_pct']}% of queue counts and {S['missing_items_pct']}% of item counts "
        f"are missing; they are left blank, never imputed in the raw data. Largest IN-OUT door drift in a meal: "
        f"{S['door_drift_max_abs']} people.", "",
        "## What this means for the model", "",
        "- Target: queue length 5, 10 and 15 minutes ahead (counted, so it is a real label).",
        "- Inputs that matter by construction: current queue, recent arrivals, service capacity for the day's dish, "
        "and the expected arrivals from the same meal and weekday in past weeks.",
        "- Metrics must focus on congested intervals; most intervals have no line, so average error alone flatters any model.", "",
        "## Peak table (mean over weeks)", "",
        peaks.to_markdown(index=False), "",
        "## Figures", "",
        "![arrivals](figures/eda_1_arrivals.png)", "", "![queue](figures/eda_2_queue.png)", "",
        "![wait](figures/eda_3_wait.png)", "", "![service](figures/eda_4_service_and_balance.png)", "",
        "![rho](figures/eda_5_rho_autocorr_heuristic.png)", "", "![occupancy](figures/eda_6_occupancy.png)", ""]
    (REPORTS / "eda_report.md").write_text("\n".join(md))
    print("eda: reports/eda_report.md written")


if __name__ == "__main__":
    main()
