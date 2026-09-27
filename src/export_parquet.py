"""
Open-format export (the PS prefers Parquet).

Writes every table of the dataset - raw logs, per-5-minute slot tables, the modelling table and
the stopwatch samples - to data/parquet/, one file per table. Each file carries its schema inside:
  * typed columns (timestamps are real timestamps, counts are integers, missing counts are nulls)
  * a description on every column (Parquet field metadata, key "description")
  * table metadata: title, grain, source, observed/inferred/synthetic tags, generator + version
It also writes data/parquet/schema.json (the same information, human-readable) and verifies that
every file reads back with the expected row count and column types.

Run:  python -m src.export_parquet
Read: pandas.read_parquet("data/parquet/intervals.parquet")  or  pyarrow.parquet.read_schema(...)
"""
import json

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from .config import DATA, INTERVAL_MIN, PROCESSED, REAL, SYNTHETIC
from .ingest import load_source

OUT = DATA / "parquet"
DATASET = "smartmess-mess-a"
VERSION = "1.0"

DESCR = {
    "inout": ("One row per person crossing the dining-hall door.", "event", {
        "session_id": "meal session id <MESS>_<meal>_<YYYY-MM-DD>; SYN_ prefix = synthetic",
        "ts": "tap time, IST, second precision",
        "event": "IN = entered the hall, OUT = left the hall",
        "is_synthetic": "1 = simulated row, 0 = counted in the mess"}),
    "intervals": ("One row per 5-minute interval at the main-dish counter.", "5 min", {
        "session_id": "meal session id",
        "interval_start": "start of the 5-minute window, IST",
        "interval_end": "end of the window, IST; the line is counted at this moment",
        "queue_len": "people standing in the main-dish line at interval_end (null = count missed)",
        "items_made": "main-dish units made in the window, e.g. dosas (null = count missed)",
        "is_synthetic": "1 = simulated row, 0 = counted in the mess"}),
    "waits": ("One row per stopwatch sample: one person timed from joining the line to getting the dish.", "person", {
        "session_id": "meal session id", "tag": "anonymous label (S01, S02...)",
        "join_ts": "person joined the main-dish line, IST", "served_ts": "person received the main dish, IST",
        "wait_min": "served_ts - join_ts in minutes (inferred)", "is_synthetic": "1 = simulated, 0 = measured"}),
    "sessions_meta": ("One row per meal session.", "meal", {
        "session_id": "meal session id", "date": "calendar date", "weekday": "day name", "meal": "breakfast / lunch / dinner",
        "mess": "mess code", "open_time": "official opening HH:MM", "close_time": "official closing HH:MM",
        "main_dish": "the meal's main (bottleneck) dish", "items_per_person": "units of the main dish per plate",
        "interval_min": "counter-count cadence in minutes", "observers": "initials + roles (real sessions)",
        "is_synthetic": "1 = simulated session", "notes": "anything unusual; provenance for synthetic sessions"}),
    "slot_tables": ("Per-5-minute view of each meal: in, out, running totals, queue, sitting, serving rate.", "5 min", {
        "session_id": "meal session id", "day": "day name", "meal": "meal", "time_slot": "HH:MM-HH:MM",
        "people_in": "people entering in the slot", "people_out": "people leaving in the slot",
        "cumulative_in": "running total of people_in", "cumulative_out": "running total of people_out",
        "queue_total": "people in the main-dish line at slot end (null = missed)",
        "avg_queue_per_counter": "queue_total over 3 counters, averaged; 1 when 0 < people_in < 4",
        "longest_counter_queue": "longest of the 3 counters",
        "sitting": "cumulative_in - cumulative_out - queue_total (in the hall, not in line)",
        "main_dish": "main dish", "items_made_5min": "main-dish units made in the slot",
        "serving_rate_items_per_min": "items_made_5min / 5", "serving_rate_people_per_min": "/ items_per_person",
        "formula_estimate_per_counter": "team's first formula (in - served)/3 without carry-over, for comparison",
        "is_synthetic": "1 = simulated row"}),
    "sessions_5min": ("Modelling table built by src/ingest.py: door counts joined onto the 5-minute counter log.", "5 min", {
        "session_id": "meal session id", "interval_start": "window start, IST", "interval_end": "window end, IST",
        "in_count": "IN taps in the window (observed)", "out_count": "OUT taps in the window (observed)",
        "queue_len": "line at interval_end (observed; null = missed)", "items_made": "units made (observed; null = missed)",
        "service_rate_items_per_min": "items_made / 5 (inferred)",
        "service_rate_people_per_min": "/ items_per_person (inferred)", "main_dish": "from meta (observed)",
        "items_per_person": "from meta (observed)", "meal": "from meta", "weekday": "from meta",
        "slot_idx": "interval index since opening (inferred)", "tod_min": "minutes since midnight (inferred)",
        "after_close": "1 = window starts after closing time (inferred)",
        "queue_missing": "1 = line count missed (inferred)", "items_missing": "1 = item count missed (inferred)",
        "is_synthetic": "1 = simulated row"}),
}


DATA_THROUGH = ""   # last session date, set in main(); keeps files byte-reproducible (no wall-clock time)


def write(name, df):
    title, grain, cols = DESCR[name]
    missing = [c for c in df.columns if c not in cols]
    if missing:
        raise ValueError(f"{name}: undocumented columns {missing}")
    table = pa.Table.from_pandas(df.reset_index(drop=True), preserve_index=False)
    fields = [f.with_metadata({"description": cols[f.name]}) for f in table.schema]
    n_syn = int((df["is_synthetic"] == 1).sum()) if "is_synthetic" in df else None
    meta = {"title": title, "grain": grain, "dataset": DATASET, "version": VERSION,
            "data_through": DATA_THROUGH,
            "rows_synthetic": str(n_syn), "rows_real": str(len(df) - n_syn if n_syn is not None else ""),
            "provenance": "real rows: tap logger (collection_kit/tap_logger.html); synthetic rows: "
                          "data/provenance/generate_dataset.py, assumptions in data/synthetic/generation_assumptions.json"}
    schema = pa.schema(fields, metadata={f"smartmess.{k}": v for k, v in meta.items()})
    table = table.cast(schema)
    pq.write_table(table, OUT / f"{name}.parquet", compression="zstd")
    return {"file": f"data/parquet/{name}.parquet", "rows": len(df), "title": title, "grain": grain,
            "columns": [{"name": f.name, "type": str(f.type), "description": cols[f.name]} for f in fields]}


def build_raw():
    io, iv, wt, meta = [], [], [], []
    for folder in (SYNTHETIC, REAL):
        for m, i, v, w, _ in load_source(folder):
            if i is None:
                continue
            flag = int(m["is_synthetic"])
            io.append(i.assign(session_id=m["session_id"], is_synthetic=flag)[["session_id", "ts", "event", "is_synthetic"]])
            v = v.assign(session_id=m["session_id"], is_synthetic=flag)
            v["queue_len"] = v["queue_len"].astype("Int64"); v["items_made"] = v["items_made"].astype("Int64")
            iv.append(v[["session_id", "interval_start", "interval_end", "queue_len", "items_made", "is_synthetic"]])
            if w is not None and len(w):
                w = w.assign(session_id=m["session_id"], is_synthetic=flag,
                             wait_min=(w["served_ts"] - w["join_ts"]).dt.total_seconds() / 60)
                wt.append(w[["session_id", "tag", "join_ts", "served_ts", "wait_min", "is_synthetic"]])
            meta.append(m.to_frame().T)
    ms = pd.concat(meta, ignore_index=True)
    ms["date"] = pd.to_datetime(ms["date"]).dt.date
    for c in ("items_per_person", "interval_min", "is_synthetic"):
        ms[c] = pd.to_numeric(ms[c]).astype("int64")
    for c in ("observers", "notes", "main_dish", "mess", "weekday", "meal", "open_time", "close_time", "session_id"):
        ms[c] = ms[c].astype(str)
    return (pd.concat(io, ignore_index=True), pd.concat(iv, ignore_index=True),
            pd.concat(wt, ignore_index=True), ms)


def real_slot_table(iv, io, m):
    """Slot table for real sessions (the generator makes them for synthetic ones)."""
    edges = list(iv["interval_start"]) + [iv["interval_end"].iloc[-1]]
    t = pd.DataFrame({"session_id": m["session_id"], "day": m["weekday"], "meal": m["meal"],
                      "time_slot": [f"{a:%H:%M}-{b:%H:%M}" for a, b in zip(iv.interval_start, iv.interval_end)]})
    for ev, col in (("IN", "people_in"), ("OUT", "people_out")):
        t[col] = pd.cut(io.loc[io.event == ev, "ts"], bins=edges, right=False).value_counts(sort=False).values
    t["cumulative_in"] = t.people_in.cumsum(); t["cumulative_out"] = t.people_out.cumsum()
    t["queue_total"] = iv["queue_len"].astype(float).values
    t["avg_queue_per_counter"] = np.round(t.queue_total / 3, 1)
    t["longest_counter_queue"] = np.nan
    floor = (t.people_in > 0) & (t.people_in < 4)
    t.loc[floor, "avg_queue_per_counter"] = np.maximum(t.loc[floor, "avg_queue_per_counter"].fillna(1), 1.0)
    t["sitting"] = t.cumulative_in - t.cumulative_out - t.queue_total
    t["main_dish"] = m["main_dish"]
    items = iv["items_made"].astype(float).values
    t["items_made_5min"] = items
    t["serving_rate_items_per_min"] = np.round(items / INTERVAL_MIN, 1)
    t["serving_rate_people_per_min"] = np.round(items / INTERVAL_MIN / float(m["items_per_person"]), 1)
    t["formula_estimate_per_counter"] = np.round(((t.people_in - items / float(m["items_per_person"])) / 3).clip(lower=0), 1)
    t.loc[floor, "formula_estimate_per_counter"] = 1.0
    t["is_synthetic"] = 0
    return t


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    global DATA_THROUGH
    io, iv, wt, ms = build_raw()
    DATA_THROUGH = str(max(ms["date"]))
    slots = [pd.read_csv(SYNTHETIC / "slot_tables_all.csv")] if (SYNTHETIC / "slot_tables_all.csv").exists() else []
    for m, i, v, _, _ in load_source(REAL):
        if i is not None:
            slots.append(real_slot_table(v, i, m))
    st = pd.concat(slots, ignore_index=True)
    for c in ("queue_total", "avg_queue_per_counter", "longest_counter_queue", "sitting", "items_made_5min",
              "serving_rate_items_per_min", "serving_rate_people_per_min", "formula_estimate_per_counter"):
        st[c] = st[c].astype(float)
    proc = pd.read_parquet(PROCESSED / "sessions_5min.parquet")
    catalog = [write("inout", io), write("intervals", iv), write("waits", wt),
               write("sessions_meta", ms), write("slot_tables", st), write("sessions_5min", proc)]

    # verify: every file reads back with the same rows, typed timestamps and documented columns
    for c in catalog:
        t = pq.read_table(OUT / c["file"].split("/")[-1])
        assert t.num_rows == c["rows"], c["file"]
        assert all(b"description" in (f.metadata or {}) for f in t.schema), c["file"]
        for f in t.schema:
            if f.name.endswith("_ts") or f.name in ("ts", "interval_start", "interval_end"):
                assert pa.types.is_timestamp(f.type), (c["file"], f.name, f.type)
    (OUT / "schema.json").write_text(json.dumps({"dataset": DATASET, "version": VERSION, "tables": catalog}, indent=2))
    print("export_parquet: " + ", ".join(f"{c['file'].split('/')[-1]} ({c['rows']})" for c in catalog))


if __name__ == "__main__":
    main()
