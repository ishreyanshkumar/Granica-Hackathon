"""
Smart Mess dashboard (Streamlit).

  streamlit run dashboard/app.py

Replays a meal interval by interval using OUT-OF-SAMPLE forecasts
(reports/predictions_dashboard.parquet, made by `python -m src.predict`).
URL parameters (used for the recorded demo):  ?session=<id>&slot=<n>&reveal=1
"""
import json
import sys
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from src.config import ALERT_AMBER_MAX, ALERT_GREEN_MAX, HORIZONS, INTERVAL_MIN, TARGET_WAIT_MIN  # noqa: E402

st.set_page_config(page_title="Smart Mess", page_icon=":stew:", layout="wide")
COL = {"GREEN": "#2b8a3e", "AMBER": "#e67700", "RED": "#c92a2a"}
st.markdown("""<style>
.block-container{padding-top:3.2rem;padding-bottom:0.5rem}
header[data-testid="stHeader"]{background:transparent}
.card{border-radius:10px;padding:14px 18px;border:1px solid #dee2e6;background:#fff}
.big{font-size:2.6rem;font-weight:700;line-height:1.1}
.lbl{font-size:.8rem;color:#495057;text-transform:uppercase;letter-spacing:.04em}
.msg{font-family:ui-monospace,Menlo,monospace;font-size:.95rem;white-space:pre-wrap;line-height:1.5}
.banner{background:#fff4e6;border:1px solid #ffc078;border-radius:8px;padding:6px 12px;font-size:.85rem}
</style>""", unsafe_allow_html=True)


@st.cache_data
def load():
    p = pd.read_parquet(ROOT / "reports" / "predictions_dashboard.parquet")
    summ = json.loads((ROOT / "reports" / "model_summary.json").read_text())
    return p, summ


pred, summ = load()
sessions = list(pred.session_id.unique())
qp = st.query_params
default_sid = qp.get("session", pred.groupby("session_id").queue_now.max().idxmax())
if default_sid not in sessions:
    default_sid = sessions[0]

with st.sidebar:
    st.header("Smart Mess")
    sid = st.selectbox("Meal session", sessions, index=sessions.index(default_sid))
    g = pred[pred.session_id == sid].sort_values("slot_idx").reset_index(drop=True)
    slot = st.slider("Replay time (5-min steps)", 0, len(g) - 1,
                     min(int(qp.get("slot", len(g) // 2)), len(g) - 1))
    reveal = st.toggle("Show what actually happened (replay only)", value=qp.get("reveal", "1") == "1")
    st.caption(f"Model: {summ['chosen_model'].upper()}")

r = g.iloc[slot]
now = r["interval_end"]

st.markdown(f"### {r['meal'].capitalize()} · {r['weekday']} · main dish **{r['main_dish']}**")
st.markdown(f"<span style='font-size:1.3rem'>Time now: <b>{now:%H:%M}</b></span>", unsafe_allow_html=True)

tab_live, tab_report, tab_model = st.tabs(["Live", "Post-meal report", "Model & data"])

with tab_live:
    c1, c2, c3, c4 = st.columns(4)
    worst = max(HORIZONS, key=lambda h: r[f"wait_pred{h}"])
    for c, lbl, val, sub in (
            (c1, "In line now", f"{r['queue_now']:.0f}", "people"),
            (c2, "Wait now", f"{r['wait_now']:.0f} min", f"serving {r['mu']:.1f} people/min"),
            (c3, f"Line in {worst * INTERVAL_MIN} min", f"{r[f'q_pred{worst}']:.0f}",
             f"80% band {r[f'q_lo{worst}']:.0f}-{r[f'q_hi{worst}']:.0f}"),
            (c4, "Alert", r["alert"], f"worst predicted wait {r[f'wait_pred{worst}']:.0f} min")):
        color = COL.get(val, "#212529")
        c.markdown(f"<div class='card'><div class='lbl'>{lbl}</div><div class='big' style='color:{color}'>{val}</div>"
                   f"<div class='lbl' style='text-transform:none'>{sub}</div></div>", unsafe_allow_html=True)

    left, right = st.columns([3, 2])
    with left:
        past = g.iloc[: slot + 1][["interval_end", "queue_now"]].rename(columns={"queue_now": "people"})
        past["series"] = "counted queue"
        fut = pd.DataFrame({"interval_end": [now + pd.Timedelta(minutes=INTERVAL_MIN * h) for h in [0] + HORIZONS],
                            "people": [r["queue_now"]] + [r[f"q_pred{h}"] for h in HORIZONS],
                            "lo": [r["queue_now"]] + [r[f"q_lo{h}"] for h in HORIZONS],
                            "hi": [r["queue_now"]] + [r[f"q_hi{h}"] for h in HORIZONS]})
        fut["series"] = "forecast"
        layers = []
        base_x = alt.X("interval_end:T", title=None, axis=alt.Axis(format="%H:%M"),
                       scale=alt.Scale(domain=[g.interval_end.min(), g.interval_end.max()]))
        if reveal:
            act = g.iloc[slot:][["interval_end", "queue_now"]].rename(columns={"queue_now": "queue_actual"})
            layers.append(alt.Chart(act).mark_line(color="#adb5bd", strokeDash=[4, 3]).encode(
                x=base_x, y="queue_actual:Q"))
        layers += [
            alt.Chart(fut).mark_area(color="#d9480f", opacity=.15).encode(x=base_x, y="lo:Q", y2="hi:Q"),
            alt.Chart(past).mark_line(color="#212529", point=alt.OverlayMarkDef(color="#212529")).encode(
                x=base_x, y=alt.Y("people:Q", title="people in main-dish line")),
            alt.Chart(fut).mark_line(color="#d9480f", point=alt.OverlayMarkDef(color="#d9480f"), strokeWidth=3).encode(x=base_x, y="people:Q"),
            alt.Chart(pd.DataFrame({"t": [now]})).mark_rule(color="#495057").encode(x="t:T")]
        st.altair_chart(alt.layer(*layers).properties(height=300), width="stretch")
        st.caption("Black: counted every 5 min. Orange: forecast for the next 15 min with 80% band."
                   + (" Grey dashed: what actually happened (hidden in live use)." if reveal else ""))
    with right:
        st.markdown("<div class='lbl'>Mess manager</div>", unsafe_allow_html=True)
        st.markdown(f"<div class='card msg' style='border-left:6px solid {COL[r['alert']]}'>{r['manager_message']}</div>",
                    unsafe_allow_html=True)
        st.write("")
        st.markdown("<div class='lbl'>Students</div>", unsafe_allow_html=True)
        adv_col = "#2b8a3e" if r["student_advice"] == "Go now" else "#e67700"
        st.markdown(
            f"<div class='card'><div class='big' style='color:{adv_col}'>{r['student_advice']}</div>"
            f"<div>Wait now ~{r['wait_now']:.0f} min · in 15 min ~{r['wait_pred3']:.0f} min</div></div>",
            unsafe_allow_html=True)

with tab_report:
    over = int((g.wait_now >= TARGET_WAIT_MIN).sum() * INTERVAL_MIN)
    pk = g.loc[g.queue_now.idxmax()]
    first_red = g[g.alert == "RED"]
    lead = None
    if len(first_red):
        cong = g[g.queue_now >= 10]
        if len(cong):
            lead = (cong.interval_end.iloc[0] - first_red.interval_end.iloc[0]).total_seconds() / 60
    a, b, c, d = st.columns(4)
    a.metric("Peak line", f"{pk.queue_now:.0f}", f"at {pk.interval_end:%H:%M}", delta_color="off")
    b.metric("Minutes with wait over target", f"{over}", f"target {TARGET_WAIT_MIN:.0f} min", delta_color="off")
    c.metric("Peak service needed", f"{g.service_rate_required.max():.1f} /min",
             f"vs {g.mu.median():.1f} typical", delta_color="off")
    d.metric("First RED alert", f"{first_red.interval_end.iloc[0]:%H:%M}" if len(first_red) else "none",
             f"{lead:.0f} min before line hit 10" if lead is not None and lead > 0 else "", delta_color="off")
    tl = g[["interval_end", "in_count", "queue_now", "wait_now", "alert"]].copy()
    ch = alt.Chart(tl).mark_bar().encode(
        x=alt.X("interval_end:T", axis=alt.Axis(format="%H:%M"), title=None), y=alt.Y("in_count:Q", title="people in / 5 min"),
        color=alt.Color("alert:N", scale=alt.Scale(domain=list(COL), range=list(COL.values())), title="alert"))
    st.altair_chart(ch.properties(height=220), width="stretch")
    st.caption("Arrivals per 5 minutes, coloured by the alert shown at that time.")

with tab_model:
    st.markdown(f"**Chosen model:** {summ['chosen_model'].upper()} · **Data:** {summ['data']}")

    with st.expander("📊 Validation methodology — Forward Out-of-Sample Split", expanded=True):
        st.markdown("""
**How we validate (no data leakage):**

We use a **strictly chronological forward split**:
- **Train set**: all operational days *before* the cutoff (first 12 of 17 dates).
- **Test set**: the held-out last **5 days** — the model never sees these sessions during training.

Every forecast shown in the dashboard was made by a model that had never seen that date.
        """)

    fw = summ.get("forward", {})
    if fw:
        train_days = summ.get("train_days_count", "?")
        test_days = summ.get("test_days_count", "?")
        test_sess = summ.get("test_sessions_count", "?")
        st.caption(f"Train: {train_days} days · Test (held-out): {test_days} days, {test_sess} sessions")
        t = pd.DataFrame({m: {f"{h} min": fw[m][str(h)]["mae_congested"] for h in (5, 10, 15)}
                          for m in fw}).T
        st.markdown("**MAE on congested intervals (queue ≥ 10 people) — people, forward test set:**")
        st.dataframe(t.round(1), use_container_width=True)
        t2 = pd.DataFrame({m: {f"{h} min": fw[m][str(h)]["mae"] for h in (5, 10, 15)}
                           for m in fw}).T
        st.markdown("**MAE, all intervals — people:**")
        st.dataframe(t2.round(1), use_container_width=True)
    else:
        st.info("Run `python run_all.py` to generate model metrics.")

