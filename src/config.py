"""Shared paths and constants. Change operating targets here, nowhere else."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
SYNTHETIC = DATA / "synthetic"
REAL = DATA / "real"
PROCESSED = DATA / "processed"
MODELS = ROOT / "models"
REPORTS = ROOT / "reports"
FIGS = REPORTS / "figures"

INTERVAL_MIN = 5                 # queue and items are counted every 5 minutes
HORIZONS = [1, 2, 3]             # forecast steps ahead (x 5 min = 5, 10, 15 min)

# Operating targets (agree these with the mess manager)
TARGET_WAIT_MIN = 5.0            # acceptable wait at the main-dish counter
ALERT_GREEN_MAX = 3.0            # predicted wait < 3 min  -> GREEN
ALERT_AMBER_MAX = 8.0            # 3 <= wait < 8           -> AMBER, >= 8 -> RED
STUDENT_MIN_SAVING = 2.0         # only advise "come later" if it saves >= 2 min
CONGESTED_QUEUE = 10             # queue length that counts as "congested" in metrics
BUSY_QUEUE = 3                   # a line of >= 3 people means the counter is working at capacity
MU_FLOOR = 0.5                   # people/min, avoids divide-by-zero in wait time

RANDOM_SEED = 2026

for d in (PROCESSED, MODELS, REPORTS, FIGS):
    d.mkdir(parents=True, exist_ok=True)
