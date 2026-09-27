"""
Stage 5 - turn queue forecasts into decisions.

  wait (min)            = queue / service rate (people/min)
  alert                 = worst predicted wait in the next 15 min: GREEN < 3, AMBER 3-8, RED >= 8
  service_rate_required = people/min needed so the predicted line drains to TARGET_WAIT while
                          absorbing expected arrivals:  max(lam_exp + (Q_hat - TARGET*mu)/T_h, Q_hat/TARGET)
  items_rate_required   = service_rate_required x items_per_person   (what the kitchen must produce)
  student_advice        = come later only if that saves >= STUDENT_MIN_SAVING minutes
"""
import numpy as np
import pandas as pd

from .config import (ALERT_AMBER_MAX, ALERT_GREEN_MAX, HORIZONS, INTERVAL_MIN, MU_FLOOR,
                     STUDENT_MIN_SAVING, TARGET_WAIT_MIN)


def level(w):
    return "GREEN" if w < ALERT_GREEN_MAX else "AMBER" if w < ALERT_AMBER_MAX else "RED"


def decide(row: pd.Series) -> dict:
    mu = max(float(row["mu"]), MU_FLOOR)
    waits = {h: float(row[f"q_pred{h}"]) / mu for h in HORIZONS}
    worst_h = max(HORIZONS, key=lambda h: waits[h])
    q_hat = float(row[f"q_pred{worst_h}"])
    t_h = worst_h * INTERVAL_MIN
    lam_exp = float(sum(row[f"prof_in_{k}"] for k in range(1, worst_h + 1))) / t_h
    mu_req = max(lam_exp + max(0.0, q_hat - TARGET_WAIT_MIN * mu) / t_h, q_hat / TARGET_WAIT_MIN)
    need_more = mu_req > mu * 1.02 and level(waits[worst_h]) != "GREEN"   # GREEN never asks for action
    best_h = min(HORIZONS, key=lambda h: waits[h])
    wait_now = float(row["wait_now"])
    advice = (f"Come in ~{best_h * INTERVAL_MIN} min" if wait_now - waits[best_h] >= STUDENT_MIN_SAVING
              else "Go now")
    out = {f"wait_pred{h}": round(waits[h], 2) for h in HORIZONS}
    out.update({
        "alert": level(waits[worst_h]),
        "alert_horizon_min": worst_h * INTERVAL_MIN,
        "service_rate_now": round(mu, 2),
        "service_rate_required": round(mu_req, 2),
        "items_rate_required": round(mu_req * float(row["items_per_person"]), 1),
        "service_gap_pct": round(100 * (mu_req / mu - 1), 0) if need_more else 0.0,
        "student_advice": advice,
    })
    return out


def manager_message(row: pd.Series, d: dict) -> str:
    h = d["alert_horizon_min"]
    q_now, q_h = row["queue_now"], row[f"q_pred{h // INTERVAL_MIN}"]
    lines = [f"{d['alert']}  {row['main_dish']} line: {q_now:.0f} now -> ~{q_h:.0f} in {h} min "
             f"(wait ~{d[f'wait_pred{h // INTERVAL_MIN}']:.0f} min)"]
    if d["service_gap_pct"] > 0:
        lines.append(f"Serving {d['service_rate_now']:.1f} people/min; need {d['service_rate_required']:.1f} "
                     f"(+{d['service_gap_pct']:.0f}%) = {d['items_rate_required']:.0f} {row['main_dish']} units/min")
        lines.append("Action: add a server / cooking station or start the next batch now")
    else:
        lines.append("Current output keeps the wait under target - no action")
    return "\n".join(lines)


def apply(pred: pd.DataFrame) -> pd.DataFrame:
    dec = pd.DataFrame([decide(r) for _, r in pred.iterrows()], index=pred.index)
    out = pd.concat([pred, dec], axis=1)
    out["manager_message"] = [manager_message(r, d) for (_, r), d in zip(out.iterrows(), dec.to_dict("records"))]
    return out
