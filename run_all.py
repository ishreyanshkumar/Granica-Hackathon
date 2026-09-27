"""
One command rebuilds everything from the raw logs in data/:

    python run_all.py

Pipeline: ingest -> Parquet export -> EDA -> train/evaluate (forward split) -> feature ablation
          -> out-of-sample predictions -> wait-time validation

Add real sessions to data/real/ and run again: every table, figure and report updates.
"""
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
STEPS = [
    ("ingest + data quality",          [sys.executable, "-m", "src.ingest"]),
    ("Parquet export + schema check",  [sys.executable, "-m", "src.export_parquet"]),
    ("exploratory analysis",           [sys.executable, "-m", "src.eda"]),
    ("train + evaluate (forward split)",[sys.executable, "-m", "src.train"]),
    ("feature ablation",               [sys.executable, "-m", "src.ablation"]),
    ("out-of-sample predictions",      [sys.executable, "-m", "src.predict"]),
]


def main():
    for name, cmd in STEPS:
        t = time.time()
        print(f"==> {name}", flush=True)
        subprocess.run(cmd, cwd=ROOT, check=True)
        print(f"    done in {time.time() - t:.0f}s", flush=True)


if __name__ == "__main__":
    main()
