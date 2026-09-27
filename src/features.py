"""
Stage 2 - physics layer and feature engineering (5-minute grain).

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


# ---------------------------------------------------------------- priors fitted on train only
def fit_priors(train: pd.DataFrame) -> dict:
    """Dish service capacity (people/min, busy intervals only) and the historical arrival
    profile (mean in_count by meal x weekday x slot)."""
    t = train.copy()
    q_prev = t.groupby("session_id")["queue_len"].shift(1)
    busy = (t["queue_len"].fillna(0) >= BUSY_QUEUE) | (q_prev.fillna(0) >= BUSY_QUEUE)
    cap = t.loc[busy, ["main_dish", "service_rate_people_per_min"]].dropna()
    dish = cap.groupby("main_dish")["service_rate_people_per_min"].median().to_dict()
    glob = float(cap["service_rate_people_per_min"].median()) if len(cap) else 8.0
    prof = t.groupby(["meal", "weekday", "slot_idx"])["in_count"].mean().to_dict()
    prof_meal = t.groupby(["meal", "slot_idx"])["in_count"].mean().to_dict()
    qprof = t.groupby(["meal", "weekday", "slot_idx"])["queue_len"].mean().to_dict()
    qprof_meal = t.groupby(["meal", "slot_idx"])["queue_len"].mean().to_dict()
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

        # service rate: measured capacity only in busy intervals (line >= BUSY_QUEUE at start or end)
        q_prev_obs = g["queue_len"].shift(1)
        busy = (g["queue_len"].fillna(0) >= BUSY_QUEUE) | (q_prev_obs.fillna(0) >= BUSY_QUEUE)
        cap = g["service_rate_people_per_min"].where(busy).rolling(3, min_periods=1).mean().ffill()
        dish_mu = priors["dish_mu"].get(dish, priors["global_mu"])
        g["dish_mu"] = dish_mu
        g["mu"] = cap.fillna(dish_mu).clip(lower=MU_FLOOR)                   # people/min
        g["served_people"] = (g["items_made"] / ipp)                          # people / 5 min
        g["lam"] = g["in_count"] / INTERVAL_MIN                                # people/min

        # conservation law, re-anchored to every counted queue
        q, qs = 0.0, []
        for inc, sp, obs in zip(g["in_count"], g["served_people"], g["queue_len"]):
            sp = sp if not np.isnan(sp) else min(q + inc, float(g["mu"].median()) * INTERVAL_MIN)
            q = max(0.0, q + inc - sp)
            if not np.isnan(obs):
                q = float(obs)
            qs.append(q)
        g["queue_phys"] = qs
        g["queue_now"] = g["queue_len"].fillna(g["queue_phys"])
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

        # targets: counted queue h steps ahead; the model learns the change
        for h in HORIZONS:
            g[f"y_q{h}"] = g["queue_len"].shift(-h)
            g[f"y_d{h}"] = g[f"y_q{h}"] - g["queue_now"]
            g[f"mu_fut{h}"] = g["mu"].shift(-h).fillna(g["mu"])                  # for true wait
        out.append(g)
    return pd.concat(out, ignore_index=True)


FEATURES = ["queue_now", "queue_d1", "in_count", "in_l1", "in_l2", "in_r3", "out_count", "out_r3",
            "served_l0", "mu", "dish_mu", "lam", "rho", "imbalance", "occupancy",
            "prof_in_1", "prof_in_2", "prof_in_3", "prof_in_sum3", "prof_gap",
            "slot_idx", "tod_min", "weekday_num", "meal_num", "min_to_close", "after_close"]

# Historical queue-profile features (computed above, available to the dashboard) were tested as model
# inputs and made the forecast worse on every split -> kept out of FEATURES. See src/ablation.py.
QUEUE_PROFILE_FEATURES = ["prof_q_1", "prof_q_2", "prof_q_3", "prof_q_gap"]
