"""
Stage 1 - ingest and validate raw logs (real and synthetic use the same code).

Raw layout per source folder (data/real or data/synthetic):
  sessions_meta.csv          one row per meal
  inout/<session_id>.csv     ts,event            (event = IN / OUT)
  intervals/<session_id>.csv interval_start,interval_end,queue_len,items_made
  waits/<session_id>.csv     tag,join_ts,served_ts   (optional stopwatch samples)

Outputs
  data/processed/sessions_5min.parquet   modelling table, one row per session per 5-min interval
  data/processed/waits.parquet           stopwatch samples with measured wait
  reports/data_quality.md                every check, per session

Run:  python -m src.ingest
"""
import numpy as np
import pandas as pd

from .config import INTERVAL_MIN, PROCESSED, REAL, REPORTS, SYNTHETIC

META_COLS = ["session_id", "date", "weekday", "meal", "mess", "open_time", "close_time",
             "main_dish", "items_per_person", "interval_min", "observers", "is_synthetic", "notes"]
TABLE_COLS = ["session_id", "interval_start", "interval_end", "in_count", "out_count", "queue_len",
              "items_made", "service_rate_items_per_min", "service_rate_people_per_min", "main_dish",
              "items_per_person", "meal", "weekday", "slot_idx", "tod_min", "after_close",
              "queue_missing", "items_missing", "is_synthetic"]


class DataError(ValueError):
    pass


def _check(cond, msg, problems):
    if not cond:
        problems.append(msg)


def load_source(folder):
    """Yield (meta_row, inout, intervals, waits, problems) for every session in a source folder."""
    meta_path = folder / "sessions_meta.csv"
    if not meta_path.exists():
        return
    meta = pd.read_csv(meta_path)
    missing = set(META_COLS) - set(meta.columns)
    if missing:
        raise DataError(f"{meta_path}: missing columns {sorted(missing)}")
    for _, m in meta.iterrows():
        sid = m["session_id"]
        p_io, p_iv, p_w = (folder / "inout" / f"{sid}.csv", folder / "intervals" / f"{sid}.csv",
                           folder / "waits" / f"{sid}.csv")
        problems = []
        if not p_io.exists() or not p_iv.exists():
            problems.append("missing inout or intervals file -> session skipped")
            yield m, None, None, None, problems
            continue
        io = pd.read_csv(p_io, parse_dates=["ts"])
        iv = pd.read_csv(p_iv, parse_dates=["interval_start", "interval_end"])
        w = pd.read_csv(p_w, parse_dates=["join_ts", "served_ts"]) if p_w.exists() else None

        _check(set(io["event"].unique()) <= {"IN", "OUT"}, f"unknown events {set(io['event'].unique()) - {'IN', 'OUT'}}", problems)
        io = io[io["event"].isin(["IN", "OUT"])]
        _check(io["ts"].notna().all(), "unparseable timestamps in inout", problems)
        step = (iv["interval_end"] - iv["interval_start"]).dt.total_seconds() / 60
        _check((step == INTERVAL_MIN).all(), f"interval width not {INTERVAL_MIN} min everywhere", problems)
        gaps = (iv["interval_start"].iloc[1:].values != iv["interval_end"].iloc[:-1].values).sum()
        _check(gaps == 0, f"{gaps} gaps/overlaps between intervals", problems)
        for c in ("queue_len", "items_made"):
            _check((iv[c].dropna() >= 0).all(), f"negative {c}", problems)
        n_in, n_out = (io["event"] == "IN").sum(), (io["event"] == "OUT").sum()
        _check(abs(n_in - n_out) <= max(5, 0.05 * n_in),
               f"IN ({n_in}) and OUT ({n_out}) differ by more than 5% - door count drift", problems)
        outside = ((io["ts"] < iv["interval_start"].min()) | (io["ts"] >= iv["interval_end"].max())).sum()
        _check(outside == 0, f"{outside} in/out taps fall outside the interval log (dropped)", problems)
        if w is not None:
            bad = (w["served_ts"] < w["join_ts"]).sum()
            _check(bad == 0, f"{bad} stopwatch rows with served before join (dropped)", problems)
            w = w[w["served_ts"] >= w["join_ts"]]
        yield m, io, iv, w, problems


def to_table(m, io, iv):
    """Count IN/OUT timestamps into the 5-minute grid and attach derived columns."""
    df = iv.copy().sort_values("interval_start").reset_index(drop=True)
    edges = list(df["interval_start"]) + [df["interval_end"].iloc[-1]]
    for ev, col in (("IN", "in_count"), ("OUT", "out_count")):
        ts = io.loc[io["event"] == ev, "ts"]
        df[col] = pd.cut(ts, bins=edges, right=False).value_counts(sort=False).values.astype(int)
    ipp = float(m["items_per_person"])
    df["session_id"] = m["session_id"]
    df["queue_len"] = df["queue_len"].astype(float)
    df["items_made"] = df["items_made"].astype(float)
    df["service_rate_items_per_min"] = df["items_made"] / INTERVAL_MIN
    df["service_rate_people_per_min"] = df["service_rate_items_per_min"] / ipp
    df["main_dish"] = m["main_dish"]
    df["items_per_person"] = ipp
    df["meal"] = m["meal"]
    df["weekday"] = m["weekday"]
    df["slot_idx"] = np.arange(len(df))
    df["tod_min"] = df["interval_start"].dt.hour * 60 + df["interval_start"].dt.minute
    close = pd.Timestamp(f"{m['date']} {m['close_time']}")
    df["after_close"] = (df["interval_start"] >= close).astype(int)
    df["queue_missing"] = df["queue_len"].isna().astype(int)
    df["items_missing"] = df["items_made"].isna().astype(int)
    df["is_synthetic"] = int(m["is_synthetic"])
    return df[TABLE_COLS]


def build():
    tables, waits, lines = [], [], []
    for folder in (SYNTHETIC, REAL):
        for m, io, iv, w, problems in load_source(folder):
            sid = m["session_id"]
            status = "OK" if not problems else "; ".join(problems)
            if io is None:
                lines.append(f"| {sid} | {folder.name} | 0 | skipped | {status} |")
                continue
            t = to_table(m, io, iv)
            tables.append(t)
            if w is not None and len(w):
                w = w.assign(session_id=sid, is_synthetic=int(m["is_synthetic"]),
                             wait_min=(w["served_ts"] - w["join_ts"]).dt.total_seconds() / 60)
                waits.append(w)
            lines.append(f"| {sid} | {folder.name} | {len(t)} | "
                         f"{int(t.queue_missing.sum())} q / {int(t.items_missing.sum())} items | {status} |")
    if not tables:
        raise DataError("no sessions found in data/synthetic or data/real")
    tab = pd.concat(tables, ignore_index=True)
    tab.to_parquet(PROCESSED / "sessions_5min.parquet", index=False)
    tab.head(60).to_csv(PROCESSED / "sessions_5min_sample.csv", index=False)      # quick-look sample
    wt = pd.concat(waits, ignore_index=True) if waits else pd.DataFrame(
        columns=["tag", "join_ts", "served_ts", "session_id", "is_synthetic", "wait_min"])
    wt.to_parquet(PROCESSED / "waits.parquet", index=False)

    n_real = tab.loc[tab.is_synthetic == 0, "session_id"].nunique()
    n_syn = tab.loc[tab.is_synthetic == 1, "session_id"].nunique()
    rep = [
        "# Data quality report", "",
        f"- Sessions: {n_real} real, {n_syn} synthetic",
        f"- 5-minute rows: {len(tab)} ({int((tab.is_synthetic == 0).sum())} real)",
        f"- Stopwatch samples: {len(wt)} ({int((wt.is_synthetic == 0).sum()) if len(wt) else 0} real)",
        f"- Missing queue counts: {int(tab.queue_missing.sum())} ({tab.queue_missing.mean():.1%})",
        f"- Missing item counts: {int(tab.items_missing.sum())} ({tab.items_missing.mean():.1%})",
        "", "Checks per session: known event names, 5-minute interval width, no gaps between intervals,",
        "non-negative counts, IN vs OUT within 5% (door-count drift), taps inside the interval log,",
        "stopwatch served >= join.", "",
        "| session | source | rows | missing counts | status |", "| --- | --- | --- | --- | --- |", *lines]
    (REPORTS / "data_quality.md").write_text("\n".join(rep) + "\n")
    print(f"ingest: {n_real} real + {n_syn} synthetic sessions, {len(tab)} rows, {len(wt)} stopwatch samples")
    return tab, wt


if __name__ == "__main__":
    build()
