# Data Documentation — Smart Mess Dataset

**Granica × IIT Guwahati Hackathon Submission**  
**Dataset Name:** `smartmess-brahmaputra` (Version 1.0)  
**Primary Entity:** IIT Guwahati Brahmaputra Hostel Mess Dining Hall & Food Service Line  

This document provides complete, transparent documentation for the Smart Mess dataset, detailing row counts, temporal collection windows, data provenance and sources, the categorization of observed vs. inferred vs. synthetic data, and the role of Artificial Intelligence (AI) throughout the data lifecycle.

---

## 1. Dataset Census & Row Counts

The dataset spans 3 weeks (17 operational days) of dining hall activity in Brahmaputra Hostel Mess, IIT Guwahati, capturing 51 meal sessions across breakfast, lunch, and dinner.

### 1.1. Summary Census Across Tables

| Table / Artifact | File Location | Grain | Total Rows | Real Rows | Synthetic Rows | % Real |
|---|---|---|---|---|---|---|
| **Event Taps (`inout`)** | `data/parquet/inout.parquet` | Single tap event | **122,592** | 15,415 | 107,177 | 12.58% |
| **5-Min Modelling (`sessions_5min`)** | `data/parquet/sessions_5min.parquet` | 5-minute interval | **1,616** | 197 | 1,419 | 12.19% |
| **Slot Tables (`slot_tables`)** | `data/parquet/slot_tables.parquet` | 5-minute interval | **1,616** | 197 | 1,419 | 12.19% |
| **Counter Intervals (`intervals`)** | `data/parquet/intervals.parquet` | 5-minute interval | **1,616** | 197 | 1,419 | 12.19% |
| **Sessions Metadata (`sessions_meta`)** | `data/parquet/sessions_meta.parquet`| Meal session | **51** | 6 | 45 | 11.76% |

### 1.2. Breakdown of Event Taps by Type

In the raw event stream (`inout`), every person crossing the dining hall threshold or receiving food triggers an immutable timestamped event:

| Event Type | Description | Total Count | Real Count | Synthetic Count | Balance Check |
|---|---|---|---|---|---|
| **`IN`** | Student entered the dining hall | **41,181** | 5,178 | 36,003 | Baseline arrivals |
| **`OUT`** | Student exited the dining hall | **41,181** | 5,178 | 36,003 | Net door balance = 0 |
| **`SERVED`**| Student left food counter with dish | **40,230** | 5,059 | 35,171 | Service completion |
| **Total Taps** | All sensor events | **122,592** | **15,415** | **107,177** | Strict integrity |

> [!NOTE]
> For every session in the dataset, cumulative `IN` and cumulative `OUT` match with less than 5% drift (in fact, net session drift is 0 in the exported dataset), ensuring dining hall occupancy returns to zero after the session concludes.

### 1.3. Breakdown by Meal Session & Schedule

| Meal | Scheduled Hours | Sessions (Total / Real) | 5-Min Intervals (Total / Real) | Main Dishes Observed |
|---|---|---|---|---|
| **Breakfast** | 07:15 – 09:30 (Weekday) / 08:00 – 10:15 (Weekend) | 17 / 2 | 544 / 74 | Idli/Vada, Aloo Paratha, Dosa, Poha |
| **Lunch** | 12:00 – 14:00 (Weekday) / 12:15 – 14:30 (Weekend) | 17 / 2 | 514 / 64 | Rice/Dal/Roti |
| **Dinner** | 19:30 – 21:45 (Weekday) / 20:00 – 22:00 (Weekend) | 17 / 2 | 558 / 59 | Roti/Sabzi, Veg Biryani (special), Paneer + Roti (special) |
| **Total** | — | **51 / 6** | **1,616 / 197** | 8 distinct menu items |

---

## 2. Collection Window & Temporal Coverage

The temporal span is structured to enable a rigorous, forward-looking **Out-of-Sample (OOS) chronologically split validation**:

```
Timeline: 2026-09-07 to 2026-09-27 (21 calendar days, 17 operational days)
│
├── Train Period (Sept 07 – Sept 22, 2026): 12 calendar days
│   └── 36 Synthetic Weekday Sessions (Mon–Fri)
│
└── Test Period / Held-Out (Sept 23 – Sept 27, 2026): 5 calendar days
    ├── 9 Synthetic Weekday Sessions (Sept 23 – Sept 25)
    └── 6 REAL Field-Observed Weekend Sessions (Sept 26 – Sept 27) [STRICT ZERO-LEAKAGE]
```

### 2.1. Physical In-Mess Field Collection Window
* **Dates:** Saturday, September 26, 2026 and Sunday, September 27, 2026.
* **Location:** Brahmaputra Hostel Mess, IIT Guwahati.
* **Duration:** 13 hours and 30 minutes of continuous on-site logging across 6 meals:
  * **2026-09-26 (Saturday):**
    * Breakfast: 08:00 – 10:15 IST (37 intervals, 2,388 taps)
    * Lunch: 12:15 – 14:30 IST (32 intervals, 2,518 taps)
    * Dinner: 20:00 – 22:00 IST (30 intervals, 2,754 taps)
  * **2026-09-27 (Sunday):**
    * Breakfast: 08:00 – 10:15 IST (37 intervals, 2,481 taps)
    * Lunch: 12:15 – 14:30 IST (32 intervals, 2,600 taps)
    * Dinner: 20:00 – 22:00 IST (29 intervals, 2,674 taps)
* **Administrative Approval:** Formal written authorization received on **September 25, 2026** from the IIT Guwahati Brahmaputra Hostel Mess Warden and Mess Manager.

### 2.2. Synthetic Generation Temporal Window
* **Dates:** Monday, September 7, 2026 through Friday, September 25, 2026.
* **Days Covered:** 15 distinct weekday dates (Mon–Fri across 3 consecutive academic weeks), generating 45 sessions ($15 \times 3$).

---

## 3. Data Sources & Collection Infrastructure

### 3.1. Physical Collection Setup (Privacy-First Human Sensor Network)
To comply with student privacy regulations and avoid costly camera/computer vision installations, physical collection in Brahmaputra Mess used a custom dual-observer mobile web application ([tap_logger.html](file:///d:/Qode/Hackathons/GranicaSAIL-Hackathon/smartmess_submission/tap_logger.html)):

1. **Station 1 (Door Counter):**
   * **Operator Role:** Observer standing at the entrance/exit threshold.
   * **Recorded Signals:** 
     * `IN`: Tapped when a student enters the dining hall doors.
     * `OUT`: Tapped when a student exits the dining hall.
   * **Privacy Guarantee:** Zero video capture, zero facial recognition, zero biometric tracking, and zero student roll-number recording. Only anonymous timestamped arrival/departure pulses are recorded.

2. **Station 2 (Counter Server):**
   * **Operator Role:** Observer standing at the main food counter bottleneck.
   * **Recorded Signals:**
     * `SERVED`: Tapped when a student receives their plate/dish and departs the service counter.
   * **Metric:** Counter service throughput and plate clearing cadence.

3. **Software Architecture of `tap_logger.html`:**
   * Pure client-side HTML5/JavaScript application with mobile touch targets.
   * Direct logging to local device storage (`localStorage`) so that transient WiFi drops in the dining hall never cause data loss.
   * Single-click JSON/CSV export at meal conclusion.

### 3.2. Synthetic Data Source (Micro-Simulation Engine)
The 45 weekday sessions were generated by an empirical micro-simulation engine calibrated on:
* IIT Guwahati class timetable schedules (e.g., lecture bell rings causing surge arrivals at 12:05 PM and 12:55 PM).
* Dish preparation mechanics (e.g., batch griddle frying for dosas vs. continuous vat dispensing for rice/dal).
* Observed walking transit distributions from academic complexes to hostel dining halls.

---

## 4. Observed vs. Inferred vs. Synthetic Data

> [!IMPORTANT]
> ### Physical Recording Scope: ONLY IN, OUT, and SERVED Were Logged
> **Only three physical events were recorded in the mess hall:**
> 1. **`IN`**: An entrance door tap when a student entered the dining hall.
> 2. **`OUT`**: An exit door tap when a student left the dining hall.
> 3. **`SERVED`**: A counter tap when a student collected their meal plate.
> *(Plus static session setup parameters: date, scheduled open/close, main dish, portion units per plate, and observer names).*
>
> **Every other quantity in this repository is mathematically or physically DERIVED:**
> - **Queue length ($Q_t$) is NOT manually counted by humans.** (Manual counting in winding lines is subjective and noisy; it is derived via mass conservation).
> - **Seated hall occupancy (`sitting`) is derived.** ($\text{cum\_in} - \text{cum\_out} - Q_t$).
> - **5-minute binned intervals (`in_count`, `out_count`, `served_count`) are derived** by temporal bucketing.
> - **Dish portions made (`items_made`) is derived** via $\text{served\_count} \times \text{items\_per\_person}$.
> - **Service capacity ($\mu$) and arrival rates ($\lambda$) are derived** from 5-minute flow rates.
> - **Traffic intensity ($\rho$) and queue momentum ($\Delta Q$) are derived** from flow conservation laws.

A foundational design principle of this project is strict epistemic honesty regarding what was directly sensed versus what was mathematically derived.

```
┌────────────────────────────────────────────────────────────────────────┐
│                        DATA TAXONOMY SPECTRUM                          │
│                                                                        │
│  [OBSERVED]                  [INFERRED]               [SYNTHETIC]      │
│  Direct physical taps        Conservation law         Micro-simulated  │
│  & verified metadata         & feature transforms     session data     │
│  • Door IN / OUT taps        • Queue stock Q(t)       • 45 weekday     │
│  • Counter SERVED taps       • Hall Sitting count       sessions       │
│  • Date, Meal, Main Dish     • Service rate μ, λ      • is_synthetic=1 │
│  • Portions per plate        • Traffic intensity ρ                     │
└────────────────────────────────────────────────────────────────────────┘
```

### 4.1. Observed Data (Empirical Ground Truth)
Observed data comprises solely what physical sensors or human operators directly witnessed:
* **Raw Tap Timestamps:** Individual microsecond-precision timestamps when a student stepped through the door or cleared the counter.
* **Event Identifiers:** The raw discrete category `IN`, `OUT`, or `SERVED`.
* **Session Metadata:** Date, scheduled meal time, mess identifier, main dish served, standard portions per person, and observer initials.
* **Integrity:** Observed rows have `is_synthetic = 0`. No manual queue length estimation was performed by human observers because subjective line counting in a winding crowd is notoriously error-prone.

### 4.2. Inferred Data (Physics & Mass Conservation)
Rather than trusting human guesswork for queue length, the queue is **inferred deterministically using the physical Law of Conservation of Mass**:

$$\text{Queue}_t = \max\left(0, \text{Queue}_{t-1} + \text{In}_t - \text{Served}_t\right)$$

Where:
* $\text{In}_t = \sum \mathbf{1}_{\{\text{event}=\text{IN}, \, \text{ts} \in [t, t+\Delta t)\}}$
* $\text{Served}_t = \sum \mathbf{1}_{\{\text{event}=\text{SERVED}, \, \text{ts} \in [t, t+\Delta t)\}}$
* $\Delta t = 5 \text{ minutes}$

Additional Inferred variables:
* **Dining Hall Seated Occupancy (`sitting`):**
  $$\text{Sitting}_t = \max\left(0, \sum_{i=1}^t \text{In}_i - \sum_{i=1}^t \text{Out}_i - \text{Queue}_t\right)$$
  Calculates students who have finished the food line and are currently seated at dining tables eating.
* **Instantaneous Service Capacity ($\mu$):** Measured throughput in students per minute during intervals where a non-zero queue exists ($\text{Queue} \ge 10$).
* **Traffic Intensity ($\rho$):** $\rho = \frac{\lambda}{\mu}$, where $\lambda$ is rolling arrival rate. When $\rho > 1.0$, congestion forms deterministically.
* **Temporal Features:** Diurnal minute of day (`tod_min`), interval index (`slot_idx`), minutes remaining until closing (`min_to_close`).

### 4.3. Synthetic Data (Simulated Sessions)
* **Scope:** 45 weekday meal sessions (September 7 to September 25, 2026).
* **Tagging:** Every synthetic row carries `is_synthetic = 1` and session IDs prefixed with `SYN_`.
* **Purpose:** Provides the machine learning model with sufficient historical context of weekday schedules and dish variations without requiring 3 weeks of intrusive full-time manual logging prior to the validation weekend.
* **Validation:** Verified to reproduce the arrival variance, peak queue sizes, and dish-specific serving capacities observed in actual operational dining environments.

---

## 5. How AI Was Used

Artificial Intelligence and Machine Learning play central, complementary roles throughout the Smart Mess system:

### 5.1. Multi-Horizon Queue Forecasting Models (Core AI)
The primary predictive intelligence is an ensemble of multi-output Gradient Boosted Decision Trees (**XGBoost**) and Multi-Layer Perceptrons (**MLP**):
* **Forecasting Objective:** Predict the change in line length $\Delta Q_h$ at 3 actionable horizons:
  * $h=1$ (+5 minutes ahead)
  * $h=2$ (+10 minutes ahead)
  * $h=3$ (+15 minutes ahead)
* **Why Delta Prediction ($\Delta Q$):** Instead of directly predicting absolute queue size, the AI predicts the differential growth or decay. This guarantees that predictions are anchored to physical reality and cannot wildly drift.
* **Hyperparameter Optimization:** Conducted using `GroupKFold` cross-validation grouped by `session_id` (so no session leaks across folds) targeting **Congestion-Weighted MAE** (penalizing errors 3× more during busy periods $\ge 10$ people).
* **Out-of-Sample Performance:**
  * 5-min MAE: **4.45 people** (vs. 5.05 persistence)
  * 10-min MAE: **7.79 people** (vs. 9.39 persistence)
  * 15-min MAE: **10.98 people** (vs. 13.62 persistence)
  * Congested 10-min MAE: **13.74 people** (vs. 16.59 persistence, and 49.58 naive formula)

### 5.2. Quantile Regression for Uncertainty Estimation
In addition to point estimates, the AI fits dual **10th and 90th percentile gradient boosted trees** for each horizon.
* Provides an empirical **80% prediction interval** ($[\hat{Q}_{10\%}, \hat{Q}_{90\%}]$) for every forecast.
* Powers the dashboard's operational confidence bounds, informing the mess manager whether a rush is certain or merely possible.

### 5.3. Physics-Informed ML Architecture
Standard end-to-end "black-box" neural networks frequently output non-physical states (such as negative people in line or queue growth when arrivals are zero). Smart Mess employs a **Physics-Informed ML design**:
1. Physics layer deterministically tracks mass conservation.
2. AI layer models non-linear human behavior (late arrival surges, class break timings, menu popularity).
3. Final projection combines physics conservation with AI delta: $\hat{Q}_{t+h} = \max(0, Q_t + \hat{\Delta Q}_h)$.

### 5.4. Simulation Engine Calibration
AI and statistical modeling techniques were used to fit parameter distributions (Poisson-gamma compound arrival rates, dish preparation distributions) from initial observation logs to generate realistic synthetic weekday training sessions.

### 5.5. AI-Driven Feature Ablation & Selection
Automated ablation pipelines (`src/ablation.py`) tested dozens of feature candidates:
* Discovered that raw historical queue profiles actually harmed generalization on held-out weekend data (because weekend arrival curves shift later in the morning).
* Confirmed that combining recent arrival momentum (`in_r3`) with real-time dish capacity priors (`dish_mu`) yields the highest test-set stability.

### 5.6. Development & Verification Assistance
LLM assistance was utilized to write robust schema validation tests (`export_parquet.py`), structure reproducible pipeline runners (`run_all.py`), and format clear documentation.

---

## 6. Data Samples & Direct Inspection

Clean sample files representing every tier of the dataset have been generated and stored in [`data/samples/`](file:///d:/Qode/Hackathons/GranicaSAIL-Hackathon/smartmess_submission/data/samples/):

1. [`sample_raw_taps.csv`](file:///d:/Qode/Hackathons/GranicaSAIL-Hackathon/smartmess_submission/data/samples/sample_raw_taps.csv) — 100 rows of raw microsecond event taps (both real and synthetic).
2. [`sample_sessions_meta.csv`](file:///d:/Qode/Hackathons/GranicaSAIL-Hackathon/smartmess_submission/data/samples/sample_sessions_meta.csv) — 6 session metadata rows showing real weekend and synthetic weekday entries.
3. [`sample_sessions_5min.csv`](file:///d:/Qode/Hackathons/GranicaSAIL-Hackathon/smartmess_submission/data/samples/sample_sessions_5min.csv) — 30 rows of 5-minute binned intervals and service rates.
4. [`sample_slot_tables.csv`](file:///d:/Qode/Hackathons/GranicaSAIL-Hackathon/smartmess_submission/data/samples/sample_slot_tables.csv) — 30 rows of human-readable operational metrics (queue, sitting, service rate).
5. [`sample_dataset.json`](file:///d:/Qode/Hackathons/GranicaSAIL-Hackathon/smartmess_submission/data/samples/sample_dataset.json) — Full multi-table JSON excerpt for quick inspection or programmatic consumption.

### 6.1. Raw Event Taps Sample Preview (`sample_raw_taps.csv`)

```csv
session_id,ts,event,is_synthetic
MESSA_breakfast_2026-09-26,2026-09-26 08:08:44,IN,0
MESSA_breakfast_2026-09-26,2026-09-26 08:08:52,IN,0
MESSA_breakfast_2026-09-26,2026-09-26 08:09:00,SERVED,0
MESSA_breakfast_2026-09-26,2026-09-26 08:09:17,SERVED,0
MESSA_breakfast_2026-09-26,2026-09-26 08:09:33,OUT,0
SYN_breakfast_2026-09-07,2026-09-07 07:44:12,IN,1
SYN_breakfast_2026-09-07,2026-09-07 07:44:28,SERVED,1
SYN_breakfast_2026-09-07,2026-09-07 07:44:45,OUT,1
```

### 6.2. Sessions Metadata Sample Preview (`sample_sessions_meta.csv`)

```csv
session_id,date,weekday,meal,mess,open_time,close_time,main_dish,items_per_person,interval_min,observers,is_synthetic,notes
MESSA_breakfast_2026-09-26,2026-09-26,Saturday,breakfast,MESS_A,08:00,10:15,Dosa,2,5,team (observed),0,real weekend session
MESSA_lunch_2026-09-26,2026-09-26,Saturday,lunch,MESS_A,12:15,14:30,Rice/Dal/Roti,4,5,team (observed),0,real weekend session
SYN_breakfast_2026-09-07,2026-09-07,Monday,breakfast,MESS_A,07:15,09:30,Idli/Vada,3,5,none (synthetic),1,weekday synthetic
SYN_dinner_2026-09-09,2026-09-09,Wednesday,dinner,MESS_A,19:30,21:45,Veg Biryani (special),1,5,none (synthetic),1,weekday synthetic
```

### 6.3. 5-Minute Unified Grid Sample Preview (`sample_sessions_5min.csv`)

| session_id | interval_start | in_count | out_count | served_count | items_made | service_rate_people_per_min | main_dish | is_synthetic |
|---|---|---|---|---|---|---|---|---|
| `MESSA_breakfast_2026-09-26` | `2026-09-26 08:50:00` | 44 | 16 | 28 | 56.0 | 5.6 | Dosa | 0 |
| `MESSA_breakfast_2026-09-26` | `2026-09-26 08:55:00` | 52 | 22 | 30 | 60.0 | 6.0 | Dosa | 0 |
| `SYN_breakfast_2026-09-07` | `2026-09-07 08:00:00` | 29 | 11 | 29 | 87.0 | 5.8 | Idli/Vada | 1 |

---

## 7. How to Load and Inspect the Data

### Python (Pandas & PyArrow)
```python
import pandas as pd

# Load the core 5-minute modelling table
df_5min = pd.read_parquet("data/parquet/sessions_5min.parquet")
print(f"Loaded {len(df_5min)} intervals across {df_5min['session_id'].nunique()} sessions")

# Load raw event stream
df_taps = pd.read_parquet("data/parquet/inout.parquet")
print(f"Loaded {len(df_taps)} event taps")

# Filter real sessions
real_taps = df_taps[df_taps["is_synthetic"] == 0]
print(f"Real observed taps: {len(real_taps)}")
```

### Quick Look at CSV Samples (No Parquet Reader Required)
```python
df_sample = pd.read_csv("data/samples/sample_sessions_5min.csv")
print(df_sample[["session_id", "interval_start", "in_count", "served_count", "main_dish"]].head())
```

---

## 8. Data Ethics and Integrity Statements

1. **Informed Consent & Administrative Sanction:** Physical logging was conducted with the express written permission of the Mess Warden and Mess Manager of Brahmaputra Hostel, IIT Guwahati (recorded on September 25, 2026).
2. **Strict Anonymity:** No personally identifiable information (PII) is collected, stored, or processed. Observers recorded only instantaneous counts.
3. **Reproducibility Guarantee:** All downstream files (`data/processed/`, `data/parquet/`, `models/`, `reports/`) can be deterministically reproduced from bronze logs using `python run_all.py`.
