"""
Stage 1 - ingest and validate raw logs (real and synthetic use the same code).

Bronze physical layout per source folder (data/real or data/synthetic):
  sessions_meta.csv          one row per meal (operating times, dish, items per person)
  inout/<session_id>.csv     ts,event (event = IN / OUT / SERVED)

Everything else (5-minute grids, service rates, queue lengths) is derived
deterministically in data/processed/.

Outputs
  data/processed/sessions_5min.parquet   modelling table, one row per session per 5-min interval
  reports/data_quality.md                every check, per session

Run:  python -m src.ingest
"""
import numpy as np
import pandas as pd

from .config import INTERVAL_MIN, PROCESSED, REAL, REPORTS, SYNTHETIC

META_COLS = ["session_id", "date", "weekday", "meal", "mess", "open_time", "close_time",
             "main_dish", "items_per_person", "interval_min", "observers", "is_synthetic", "notes"]
TABLE_COLS = ["session_id", "interval_start", "interval_end", "in_count", "out_count", "served_count",
              "items_made", "service_rate_items_per_min", "service_rate_people_per_min", "main_dish",
              "items_per_person", "meal", "weekday", "slot_idx", "tod_min", "after_close",
              "items_missing", "is_synthetic"]
VALID_EVENTS = {"IN", "OUT", "SERVED"}


class DataError(ValueError):
    pass


def _check(cond, msg, problems):
    if not cond:
        problems.append(msg)


def load_source(folder):
    """Yield (meta_row, inout, problems) for every session in a source folder."""
    meta_path = folder / "sessions_meta.csv"
    if not meta_path.exists():
        return
    meta = pd.read_csv(meta_path)
    missing = set(META_COLS) - set(meta.columns)
    if missing:
        raise DataError(f"{meta_path}: missing columns {sorted(missing)}")
    for _, m in meta.iterrows():
        sid = m["session_id"]
        p_io = folder / "inout" / f"{sid}.csv"
        problems = []
        if not p_io.exists():
            problems.append("missing inout file -> session skipped")
            yield m, None, problems
            continue
        io = pd.read_csv(p_io, parse_dates=["ts"])

        _check(set(io["event"].unique()) <= VALID_EVENTS, f"unknown events {set(io['event'].unique()) - VALID_EVENTS}", problems)
        io = io[io["event"].isin(VALID_EVENTS)]
        _check(io["ts"].notna().all(), "unparseable timestamps in inout", problems)
        n_in, n_out = (io["event"] == "IN").sum(), (io["event"] == "OUT").sum()
        _check(abs(n_in - n_out) <= max(5, 0.05 * n_in),
               f"IN ({n_in}) and OUT ({n_out}) differ by more than 5% - door count drift", problems)
        yield m, io, problems


def to_table(m, io):
    """Bin timestamped taps into 5-minute intervals and compute service rates and counts."""
    d, op, cl = m["date"], m["open_time"], m["close_time"]
    t_start = pd.Timestamp(f"{d} {op}")
    last_tap = io["ts"].max()
    t_end = max(pd.Timestamp(f"{d} {cl}"), last_tap).ceil(f"{INTERVAL_MIN}min")
    edges = pd.date_range(t_start, t_end, freq=f"{INTERVAL_MIN}min")

    df = pd.DataFrame({
        "interval_start": edges[:-1],
        "interval_end": edges[1:]
    })
    for ev, col in (("IN", "in_count"), ("OUT", "out_count"), ("SERVED", "served_count")):
        ts = io.loc[io["event"] == ev, "ts"]
        df[col] = pd.cut(ts, bins=edges, right=False).value_counts(sort=False).values.astype(int)

    ipp = float(m["items_per_person"])
    df["session_id"] = m["session_id"]
    df["items_made"] = (df["served_count"] * ipp).astype(float)
    df["service_rate_people_per_min"] = df["served_count"] / INTERVAL_MIN
    df["service_rate_items_per_min"] = df["items_made"] / INTERVAL_MIN
    df["main_dish"] = m["main_dish"]
    df["items_per_person"] = ipp
    df["meal"] = m["meal"]
    df["weekday"] = m["weekday"]
    df["slot_idx"] = np.arange(len(df))
    df["tod_min"] = df["interval_start"].dt.hour * 60 + df["interval_start"].dt.minute
    close = pd.Timestamp(f"{m['date']} {m['close_time']}")
    df["after_close"] = (df["interval_start"] >= close).astype(int)
    df["items_missing"] = 0
    df["is_synthetic"] = int(m["is_synthetic"])
    return df[TABLE_COLS]


def build():
    tables, lines = [], []
    for folder in (SYNTHETIC, REAL):
        for m, io, problems in load_source(folder):
            sid = m["session_id"]
            status = "OK" if not problems else "; ".join(problems)
            if io is None:
                lines.append(f"| {sid} | {folder.name} | 0 | skipped | {status} |")
                continue
            t = to_table(m, io)
            tables.append(t)
            lines.append(f"| {sid} | {folder.name} | {len(t)} | {len(io)} taps | {status} |")
    if not tables:
        raise DataError("no sessions found in data/synthetic or data/real")
    tab = pd.concat(tables, ignore_index=True)
    tab.to_parquet(PROCESSED / "sessions_5min.parquet", index=False)
    tab.head(60).to_csv(PROCESSED / "sessions_5min_sample.csv", index=False)      # quick-look sample

    n_real = tab.loc[tab.is_synthetic == 0, "session_id"].nunique()
    n_syn = tab.loc[tab.is_synthetic == 1, "session_id"].nunique()
    rep = [
        "# Data quality report", "",
        f"- Sessions: {n_real} real, {n_syn} synthetic",
        f"- 5-minute rows: {len(tab)} ({int((tab.is_synthetic == 0).sum())} real)",
        "", "NOTE: All physical inputs are timestamped taps (IN, OUT, SERVED) in bronze inout/ files.",
        "5-minute intervals and queues are derived automatically in data/processed/.", "",
        "Checks per session: known event names (IN, OUT, SERVED), IN vs OUT within 5% (door drift).", "",
        "| session | source | rows | taps | status |", "| --- | --- | --- | --- | --- |", *lines]
    (REPORTS / "data_quality.md").write_text("\n".join(rep) + "\n")
    print(f"ingest: {n_real} real + {n_syn} synthetic sessions, {len(tab)} rows")
    return tab


if __name__ == "__main__":
    build()
