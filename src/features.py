"""
Stage 2 - physics layer and feature engineering (5-minute grain).

Queue length is NOT an observed input.  It is derived entirely from the
conservation law at every interval:

    queue(t) = max(0, queue(t-1) + in_count(t) - served_people(t))

Only two sensor streams are used:
  - in_count / out_count   door tap counts per 5-min interval
  - items_made             service counter (5-min grouped)

Everything at row t uses only information available at interval_end of t (no look-ahead).
Anything learned across sessions (dish speed prior, arrival profile) is fitted on TRAINING
sessions only and passed in, so evaluation never leaks.
"""
import numpy as np
import pandas as pd

from .config import BUSY_QUEUE, HORIZONS, INTERVAL_MIN, MU_FLOOR

WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
MEALS = ["breakfast", "lunch", "dinner"]


def heuristic_queue(in_count, items_made):
    """Team's first (experimental) formula, kept as a baseline:
       Q = (people in - serving rate) / 3 ; Q = 1 when 0 < people in < 4.
       Applied to the per-interval counts. It estimates growth, not the stock."""
    in_count = np.asarray(in_count, float)
    items = np.nan_to_num(np.asarray(items_made, float))
    q = np.maximum(0.0, (in_count - items) / 3.0)
    return np.where((in_count > 0) & (in_count < 4), 1.0, q)


def derive_session_queue(g: pd.DataFrame, default_sp_cap: float = 40.0) -> list:
    """Conservation law: queue(t) = max(0, queue(t-1) + in_count(t) - served_people(t)).
    Only two sensor inputs are used: in_count and items_made."""
    ipp = g["items_per_person"].iloc[0] if "items_per_person" in g.columns else 1.0
    sp_col = (g["items_made"] / ipp) if "items_made" in g.columns else pd.Series(np.nan, index=g.index)
    q, qs = 0.0, []
    for inc, sp in zip(g["in_count"], sp_col):
        sp = sp if not (pd.isna(sp) or np.isnan(sp)) else min(q + inc, default_sp_cap)
        q = max(0.0, q + inc - sp)
        qs.append(q)
    return qs


# ---------------------------------------------------------------- priors fitted on train only
def fit_priors(train: pd.DataFrame) -> dict:
    """Dish service capacity (people/min, busy intervals only) and the historical arrival
    profile (mean in_count by meal x weekday x slot).

    Queue length is derived entirely from the conservation law across training sessions.
    """
    t = train.copy()
    if "queue_phys" not in t.columns:
        qs_all = {}
        for _, g in t.groupby("session_id", sort=False):
            g_sorted = g.sort_values("slot_idx")
            qs = derive_session_queue(g_sorted)
            for idx, q_val in zip(g_sorted.index, qs):
                qs_all[idx] = q_val
        t["queue_phys"] = pd.Series(qs_all)
    q_col = "queue_phys"

    q_prev = t.groupby("session_id")[q_col].shift(1)
    busy = (t[q_col].fillna(0) >= BUSY_QUEUE) | (q_prev.fillna(0) >= BUSY_QUEUE)
    cap = t.loc[busy, ["main_dish", "service_rate_people_per_min"]].dropna()
    dish = cap.groupby("main_dish")["service_rate_people_per_min"].median().to_dict()
    glob = float(cap["service_rate_people_per_min"].median()) if len(cap) else 8.0
    prof = t.groupby(["meal", "weekday", "slot_idx"])["in_count"].mean().to_dict()
    prof_meal = t.groupby(["meal", "slot_idx"])["in_count"].mean().to_dict()
    qprof = t.groupby(["meal", "weekday", "slot_idx"])[q_col].mean().to_dict()
    qprof_meal = t.groupby(["meal", "slot_idx"])[q_col].mean().to_dict()
    return {"dish_mu": dish, "global_mu": glob, "in_profile": prof, "in_profile_meal": prof_meal,
            "queue_profile": qprof, "queue_profile_meal": qprof_meal}


def _profile(p, meal, wd, slot):
    v = p["in_profile"].get((meal, wd, slot))
    if v is None or np.isnan(v):
        v = p["in_profile_meal"].get((meal, slot), 0.0)
    return float(v)


def _q_profile(p, meal, wd, slot):
    v = p["queue_profile"].get((meal, wd, slot))
    if v is None or np.isnan(v):
        v = p.get("queue_profile_meal", {}).get((meal, slot), 0.0)
    return float(v) if (v is not None and not np.isnan(v)) else 0.0


# ---------------------------------------------------------------- per-session physics + features
def add_features(df: pd.DataFrame, priors: dict) -> pd.DataFrame:
    out = []
    for sid, g in df.groupby("session_id", sort=False):
        g = g.sort_values("slot_idx").copy()
        meal, wd, dish = g["meal"].iloc[0], g["weekday"].iloc[0], g["main_dish"].iloc[0]
        ipp = g["items_per_person"].iloc[0]

        # service rate: measured capacity only in busy intervals.
        cap_raw = g["service_rate_people_per_min"].rolling(3, min_periods=1).mean().ffill()
        dish_mu = priors["dish_mu"].get(dish, priors["global_mu"])
        g["dish_mu"] = dish_mu
        g["mu"] = cap_raw.fillna(dish_mu).clip(lower=MU_FLOOR)             # people/min
        g["served_people"] = (g["items_made"] / ipp)                        # people / 5 min
        g["lam"] = g["in_count"] / INTERVAL_MIN                              # people/min

        # conservation law — pure physics, no observer re-anchoring
        # queue(t) = max(0, queue(t-1) + in_count(t) - served_people(t))
        g["queue_phys"] = derive_session_queue(g, default_sp_cap=float(g["mu"].median()) * INTERVAL_MIN)
        g["queue_now"] = g["queue_phys"]   # queue_now IS queue_phys — no observed anchor
        g["queue_heur"] = heuristic_queue(g["in_count"], g["items_made"])
        g["cum_in"] = g["in_count"].cumsum()
        g["cum_out"] = g["out_count"].cumsum()
        g["occupancy"] = (g["cum_in"] - g["cum_out"] - g["queue_now"]).clip(lower=0)
        g["wait_now"] = g["queue_now"] / g["mu"]

        # lags / windows (all past or current)
        g["queue_d1"] = g["queue_now"].diff().fillna(0)
        g["in_l1"] = g["in_count"].shift(1).fillna(0)
        g["in_l2"] = g["in_count"].shift(2).fillna(0)
        g["in_r3"] = g["in_count"].rolling(3, min_periods=1).sum()
        g["out_r3"] = g["out_count"].rolling(3, min_periods=1).sum()
        g["served_l0"] = g["served_people"].fillna(g["mu"] * INTERVAL_MIN)
        g["rho"] = (g["in_r3"] / (3 * INTERVAL_MIN)) / g["mu"]
        g["imbalance"] = g["in_r3"] / (3 * INTERVAL_MIN) - g["mu"]            # people/min
        # expected arrivals and queues in the next intervals from the historical day-of-week profile
        for h in HORIZONS:
            g[f"prof_in_{h}"] = [_profile(priors, meal, wd, s + h) for s in g["slot_idx"]]
            g[f"prof_q_{h}"] = [_q_profile(priors, meal, wd, s + h) for s in g["slot_idx"]]
        g["prof_in_sum3"] = g[[f"prof_in_{h}" for h in HORIZONS]].sum(axis=1)
        g["prof_gap"] = g["in_count"] - [_profile(priors, meal, wd, s) for s in g["slot_idx"]]
        g["prof_q_gap"] = g["queue_now"] - [_q_profile(priors, meal, wd, s) for s in g["slot_idx"]]
        g["weekday_num"] = WEEKDAYS.index(wd) if wd in WEEKDAYS else -1
        g["meal_num"] = MEALS.index(meal) if meal in MEALS else -1
        close_slot = g.loc[g["after_close"] == 0, "slot_idx"].max()
        g["min_to_close"] = ((close_slot + 1 - g["slot_idx"]) * INTERVAL_MIN).clip(lower=0)

        # targets: physics-derived queue h steps ahead; the model learns the change
        for h in HORIZONS:
            g[f"y_q{h}"] = g["queue_phys"].shift(-h)   # physics queue, no observer
            g[f"y_d{h}"] = g[f"y_q{h}"] - g["queue_now"]
            g[f"mu_fut{h}"] = g["mu"].shift(-h).fillna(g["mu"])              # for wait MAE
        out.append(g)
    return pd.concat(out, ignore_index=True)


FEATURES = ["queue_now", "queue_d1", "in_count", "in_l1", "in_l2", "in_r3", "out_count", "out_r3",
            "served_l0", "mu", "dish_mu", "lam", "rho", "imbalance", "occupancy",
            "prof_in_1", "prof_in_2", "prof_in_3", "prof_in_sum3", "prof_gap",
            "slot_idx", "tod_min", "weekday_num", "meal_num", "min_to_close", "after_close"]

# Historical queue-profile features (computed above, available to the dashboard) were tested as model
# inputs and made the forecast worse on every split -> kept out of FEATURES. See src/ablation.py.
QUEUE_PROFILE_FEATURES = ["prof_q_1", "prof_q_2", "prof_q_3", "prof_q_gap"]
