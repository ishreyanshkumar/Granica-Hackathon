"""
Stage 4 - train and evaluate forecasting models.

Target: physics-derived queue length 5 / 10 / 15 min ahead (model learns the change from now).
Queue is never observed directly — it is the conservation-law estimate (cum_in − cum_served).
Models compared:
  persistence           queue in h = queue now
  seasonal_profile      mean queue for the same meal, weekday and time slot in training weeks
  physics_profile       queue now + expected arrivals (profile) - capacity x time
  experimental_formula  (in - items)/3, the team's first hypothesis
  xgb                   gradient-boosted trees (tuned with grouped inner CV), + 10/90% quantile models
  mlp                   small neural network (64-32), standardised inputs

Evaluation (no leakage: priors and models fitted on training sessions only):
  forward   strictly chronological out-of-sample: trained on past operational days,
            evaluated on held-out future days (last 5 days, including real weekend meals).
Metrics: MAE, RMSE, MAE on congested intervals (true queue >= 10), wait-time MAE,
         RED-alert precision / recall, 80% interval coverage.

Run:  python -m src.train
"""
import itertools
import json

import joblib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.model_selection import GroupKFold

from .config import (ALERT_AMBER_MAX, CONGESTED_QUEUE, FIGS, HORIZONS, INTERVAL_MIN, MODELS,
                     MU_FLOOR, PROCESSED, RANDOM_SEED, REPORTS)
from .features import FEATURES, add_features, fit_priors
from .model import baseline_predictions, fit_bundle, predict_bundle, make_xgb

GRID = [dict(max_depth=d, n_estimators=n, min_child_weight=c)
        for d, n, c in itertools.product([3, 5], [300, 600], [1, 5])]
MODEL_ORDER = ["xgb", "mlp", "physics_profile", "seasonal_profile", "persistence", "experimental_formula"]


def prep(train_raw, test_raw):
    pri = fit_priors(train_raw)
    return add_features(train_raw, pri), add_features(test_raw, pri), pri


def tune_xgb(train_f):
    """Pick XGB hyper-parameters by grouped inner CV on congested-weighted MAE (10-min horizon)."""
    d = train_f.dropna(subset=["y_d2"])
    gkf = GroupKFold(n_splits=3)
    best, best_score = None, np.inf
    for p in GRID:
        errs = []
        for tr, va in gkf.split(d, groups=d["session_id"]):
            m = make_xgb(p).fit(d.iloc[tr][FEATURES], d.iloc[tr]["y_d2"])
            pred = np.clip(d.iloc[va]["queue_now"] + m.predict(d.iloc[va][FEATURES]), 0, None)
            true = d.iloc[va]["y_q2"]
            w = np.where(true >= CONGESTED_QUEUE, 3.0, 1.0)             # congestion matters more
            errs.append(np.average(np.abs(pred - true), weights=w))
        s = float(np.mean(errs))
        if s < best_score:
            best, best_score = p, s
    return best


def score(test_f, preds, h, lo=None, hi=None):
    true = test_f[f"y_q{h}"].values
    ok = ~np.isnan(true)
    t, p = true[ok], np.asarray(preds, float)[ok]
    mu_now = np.maximum(test_f["mu"].values[ok], MU_FLOOR)
    mu_fut = np.maximum(test_f[f"mu_fut{h}"].values[ok], MU_FLOOR)
    w_true, w_pred = t / mu_fut, p / mu_now
    cong = t >= CONGESTED_QUEUE
    red_t, red_p = w_true >= ALERT_AMBER_MAX, w_pred >= ALERT_AMBER_MAX
    tp = int((red_t & red_p).sum())
    r = {"n": int(ok.sum()), "mae": np.abs(p - t).mean(), "rmse": np.sqrt(((p - t) ** 2).mean()),
         "mae_congested": np.abs(p[cong] - t[cong]).mean() if cong.any() else np.nan,
         "n_congested": int(cong.sum()), "wait_mae_min": np.abs(w_pred - w_true).mean(),
         "red_precision": tp / red_p.sum() if red_p.sum() else np.nan, "n_red": int(red_t.sum()),
         "red_recall": tp / red_t.sum() if red_t.sum() else np.nan}
    if lo is not None:
        l, u = np.asarray(lo)[ok], np.asarray(hi)[ok]
        r["coverage_80"] = float(((t >= l) & (t <= u)).mean())
    return r


def evaluate_split(train_raw, test_raw, params, split_name, fold=0):
    tr_f, te_f, pri = prep(train_raw, test_raw)
    rows = []
    xgb = fit_bundle(tr_f, pri, "xgb", params)
    mlp = fit_bundle(tr_f, pri, "mlp", quantiles=False)
    px, pm = predict_bundle(te_f, xgb), predict_bundle(te_f, mlp)
    for h in HORIZONS:
        preds = {"xgb": px[f"q_pred{h}"], "mlp": pm[f"q_pred{h}"], **baseline_predictions(te_f, pri, h)}
        for name, p in preds.items():
            extra = (px[f"q_lo{h}"], px[f"q_hi{h}"]) if name == "xgb" else (None, None)
            rows.append({"split": split_name, "fold": fold, "horizon_min": h * INTERVAL_MIN,
                         "model": name, **score(te_f, p, h, *extra)})
    return rows, px, xgb


def summarise(df):
    agg = df.groupby(["split", "model", "horizon_min"]).agg(
        mae=("mae", "mean"), rmse=("rmse", "mean"), mae_congested=("mae_congested", "mean"),
        wait_mae_min=("wait_mae_min", "mean"), red_precision=("red_precision", "mean"),
        red_recall=("red_recall", "mean"), coverage_80=("coverage_80", "mean"),
        n=("n", "sum"), n_congested=("n_congested", "sum"), n_red=("n_red", "sum")).reset_index()
    agg["model"] = pd.Categorical(agg["model"], MODEL_ORDER, ordered=True)
    return agg.sort_values(["split", "horizon_min", "model"]).round(3)


def pivot_md(agg, split, metric):
    t = agg[agg.split == split].pivot(index="model", columns="horizon_min", values=metric)
    t.columns = [f"{c} min" for c in t.columns]
    return t.round(2).to_markdown()


def main():
    raw = pd.read_parquet(PROCESSED / "sessions_5min.parquet")
    raw["date"] = raw["interval_start"].dt.normalize()
    syn, real = raw[raw.is_synthetic == 1], raw[raw.is_synthetic == 0]
    n_real = real.session_id.nunique()
    all_rows = []

    # ---------------- forward split: strictly out-of-sample forward in time
    # The model trains on earlier operational days and is evaluated on held-out future days (last 5 days)
    base = raw
    cut = base["date"].sort_values().unique()[-5] if base["date"].nunique() > 5 else base["date"].max()
    fwd_tr, fwd_te = base[base.date < cut], base[base.date >= cut]
    tr_f, _, _ = prep(fwd_tr, fwd_tr)
    params = tune_xgb(tr_f)
    rows, fwd_pred, _ = evaluate_split(fwd_tr, fwd_te, params, "forward")
    all_rows += rows

    res = pd.DataFrame(all_rows)
    res.to_csv(REPORTS / "model_metrics_by_fold.csv", index=False)
    agg = summarise(res)
    agg.to_csv(REPORTS / "model_metrics.csv", index=False)

    # model selection on forward out-of-sample congested MAE
    fw = agg[(agg.split == "forward") & agg.model.isin(["xgb", "mlp"])]
    sel = fw.groupby("model", observed=True)["mae_congested"].mean()
    if sel.isna().all():
        sel = fw.groupby("model", observed=True)["mae"].mean()
    chosen = sel.idxmin()

    # ---------------- final model on ALL sessions (real + synthetic)
    pri_all = fit_priors(raw)
    f_all = add_features(raw, pri_all)
    final = fit_bundle(f_all, pri_all, chosen, params if chosen == "xgb" else None,
                       quantiles=True)
    if chosen != "xgb":                                       # quantile bands always come from XGB
        q = fit_bundle(f_all, pri_all, "xgb", params)
        final["lo"], final["hi"] = q["lo"], q["hi"]
    final["params"] = params
    final["trained_on"] = {"real_sessions": int(n_real), "synthetic_sessions": int(syn.session_id.nunique())}
    joblib.dump(final, MODELS / "queue_forecaster.joblib")

    # ---------------- figures
    fwd = agg[agg.split == "forward"]
    fig, ax = plt.subplots(1, 2, figsize=(12, 3.6))
    colors = {"xgb": "#d9480f", "mlp": "#f08c00", "physics_profile": "#1c7ed6", "seasonal_profile": "#74c0fc",
              "persistence": "#868e96", "experimental_formula": "#ced4da"}
    for i, metric in enumerate(["mae", "mae_congested"]):
        for j, m in enumerate(MODEL_ORDER):
            d = fwd[fwd.model == m]
            ax[i].bar(d.horizon_min + (j - 2.5) * 0.7, d[metric], width=0.7, color=colors[m], label=m)
        ax[i].set_xticks([5, 10, 15], ["5 min", "10 min", "15 min"])
        ax[i].set_ylabel("people"); ax[i].set_title(
            "MAE, all intervals" if metric == "mae" else f"MAE, congested intervals (queue >= {CONGESTED_QUEUE})")
    ax[0].legend(frameon=False, fontsize=7)
    fig.suptitle("Forward Out-of-Sample Test (last 5 days held out)", x=0.01, ha="left")
    fig.tight_layout()
    fig.savefig(FIGS / "model_1_mae.png"); plt.close(fig)

    # example forecast on the most congested held-out session
    sid = fwd_pred.groupby("session_id")["queue_now"].max().idxmax()
    e = fwd_pred[fwd_pred.session_id == sid]
    fig, ax = plt.subplots(figsize=(10, 3.4))
    ax.plot(e.interval_end, e.queue_now, "ko-", ms=3, lw=1, label="physics queue (derived)")
    tgt = e.interval_end + pd.Timedelta(minutes=10)
    ax.plot(tgt, e.q_pred2, color="#d9480f", lw=1.6, label="forecast made 10 min earlier")
    ax.fill_between(tgt, e.q_lo2, e.q_hi2, color="#d9480f", alpha=.15, label="80% band")
    ax.set_ylabel("people in line"); ax.legend(frameon=False)
    ax.set_title(f"{sid}: 10-minute-ahead forecast (held-out out-of-sample)")
    fig.tight_layout(); fig.savefig(FIGS / "model_2_example.png"); plt.close(fig)

    # feature importance (gain) of the final 10-min XGB
    m10 = make_xgb(params).fit(f_all.dropna(subset=["y_d2"])[FEATURES], f_all.dropna(subset=["y_d2"])["y_d2"])
    imp = pd.Series(m10.get_booster().get_score(importance_type="gain")).rename(
        index=lambda k: FEATURES[int(k[1:])] if k.startswith("f") and k[1:].isdigit() else k)
    imp = (imp / imp.sum()).sort_values().tail(12)
    fig, ax = plt.subplots(figsize=(6, 3.8))
    ax.barh(imp.index, imp.values, color="#1c7ed6"); ax.set_xlabel("share of gain")
    ax.set_title("What drives the 10-min forecast"); fig.tight_layout()
    fig.savefig(FIGS / "model_3_importance.png"); plt.close(fig)

    # ---------------- report
    def row(model, h, col):
        v = fwd[(fwd.model == model) & (fwd.horizon_min == h)][col]
        return float(v.iloc[0]) if len(v) else float("nan")

    summary = {
        "split_method": "forward",
        "train_days_count": int(fwd_tr["date"].nunique()),
        "test_days_count": int(fwd_te["date"].nunique()),
        "test_sessions_count": int(fwd_te["session_id"].nunique()),
        "data": f"{n_real} real + {syn.session_id.nunique()} synthetic sessions",
        "n_real_sessions": int(n_real),
        "chosen_model": chosen,
        "xgb_params": params,
        "forward": {m: {h: {c: row(m, h, c) for c in ["mae", "mae_congested", "wait_mae_min",
                                                      "red_precision", "red_recall", "coverage_80"]}
                        for h in [5, 10, 15]} for m in MODEL_ORDER},
        "top_features": list(imp.sort_values(ascending=False).index[:5]),
    }
    (REPORTS / "model_summary.json").write_text(json.dumps(summary, indent=2, default=float))

    label = f"Evaluated strictly on Forward Split: trained on past dates ({fwd_tr['date'].nunique()} days), tested on held-out future dates ({fwd_te['date'].nunique()} days, {fwd_te['session_id'].nunique()} sessions, including real weekend meals)."
    md = [
        "# Model results (Forward Split)", "", label, "",
        f"- Chosen model: **{chosen.upper()}** (lowest congested-interval MAE averaged over horizons on forward out-of-sample: " + ", ".join(f"{k} {v:.2f}" for k, v in sel.items()) + ")",
        f"- XGB hyper-parameters (grouped inner CV): `{params}`",
        f"- Most important inputs (10-min horizon): {', '.join(summary['top_features'])}", "",
        "## Out-of-Sample Forward Split Metrics", "",
        "### MAE (people, all intervals)", "", pivot_md(agg, "forward", "mae"), "",
        f"### MAE on congested intervals (true queue >= {CONGESTED_QUEUE}), people", "",
        pivot_md(agg, "forward", "mae_congested"), "",
        "### Wait-time MAE (minutes: predicted queue / service rate vs actual)", "",
        pivot_md(agg, "forward", "wait_mae_min"), "",
        f"### RED alert (wait >= {ALERT_AMBER_MAX:.0f} min): recall, then precision "
        f"({int(fwd[fwd.model == 'xgb'].n_red.sum())} RED intervals across horizons in test set)", "",
        pivot_md(agg, "forward", "red_recall"), "", pivot_md(agg, "forward", "red_precision"), "",
        "### 80% prediction band coverage (XGB quantiles; target 0.80)", "",
        pivot_md(agg[agg.model == "xgb"], "forward", "coverage_80"), "",
        "## Figures", "", "![mae](figures/model_1_mae.png)", "", "![example](figures/model_2_example.png)", "",
        "![importance](figures/model_3_importance.png)", ""]
    (REPORTS / "model_results.md").write_text("\n".join(md))
    print(f"train: chosen={chosen}; forward congested MAE @10min xgb={row('xgb', 10, 'mae_congested'):.2f} "
          f"mlp={row('mlp', 10, 'mae_congested'):.2f} physics={row('physics_profile', 10, 'mae_congested'):.2f} "
          f"persistence={row('persistence', 10, 'mae_congested'):.2f}")


if __name__ == "__main__":
    main()
