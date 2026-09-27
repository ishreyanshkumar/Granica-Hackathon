# Exploratory analysis

Data: 51 sessions, 1616 five-minute rows (real + synthetic). 

## Key findings

1. **Congestion is concentrated.** Only 39.2% of 5-minute intervals have a line of 10+ people. The worst slots are breakfast Sunday at 10:05 (mean peak 220.0); breakfast Saturday at 10:10 (mean peak 199.0); lunch Thursday at 12:55 (mean peak 114.3).
2. **The line forms when arrivals exceed service capacity.** When utilisation rho > 1, 55% of intervals are congested; when rho < 0.8, only 36% are.
3. **Queue balance holds.** In busy intervals, (people in - people served) vs the queue change over the same 5 min: correlation 1.0; mean absolute balance error 0.01 people (counting noise, plus overflow: when the line is full, new arrivals wait at tables and join later).
4. **Capacity depends on the dish.** Median people served per minute while a line is present: Dosa 5.6, Aloo Paratha 7.7, Idli/Vada 9.2, Poha 4.6, Veg Biryani (special) 6.0, Rice/Dal/Roti 8.4, Paneer + Roti (special) 7.0, Roti/Sabzi 7.6. When the line is empty, items made measures demand, not capacity, so only busy intervals are used.
5. **'Queue now' alone fades fast.** Correlation with the queue later: 5 min 0.94, 10 min 0.84, 15 min 0.72, 20 min 0.6, 25 min 0.49, 30 min 0.39. A 15-minute forecast needs arrival expectations (historical profile) and capacity, not just the current line.
6. **The experimental formula underestimates real lines.** (in - items)/3 vs counted queue: MAE 18.52 people overall and 44.75 when the line is 10+. It measures growth, not the accumulated stock, so it is kept only as a baseline.
7. **Data quality.** 0.0% of item counts are missing; they are left blank, never imputed in the raw data. Largest IN-OUT door drift in a meal: 0 people. Queue length is physics-derived (no observer count).

## What this means for the model

- Target: queue length 5, 10 and 15 minutes ahead (physics-derived from in/out and service rate conservation law).
- Inputs that matter by construction: current queue, recent arrivals, service capacity for the day's dish, and the expected arrivals from the same meal and weekday in past weeks.
- Metrics must focus on congested intervals; most intervals have no line, so average error alone flatters any model.

## Peak table (mean over weeks)

| meal      | weekday   | peak_arrivals_at   |   peak_arrivals_per_5min | peak_queue_at   |   peak_queue_mean |   max_wait_mean_min |   min_per_meal_wait_over_target | main_dish               |
|:----------|:----------|:-------------------|-------------------------:|:----------------|------------------:|--------------------:|--------------------------------:|:------------------------|
| breakfast | Monday    | 08:50              |                     82.7 | 08:50           |              53.3 |                19   |                            18.3 | Idli/Vada               |
| breakfast | Tuesday   | 08:50              |                     89   | 09:00           |              97.3 |                10.1 |                            36.7 | Aloo Paratha            |
| breakfast | Wednesday | 08:50              |                     69.7 | 09:00           |              70.3 |                50.7 |                            38.3 | Dosa                    |
| breakfast | Thursday  | 08:50              |                     87.7 | 08:50           |              53.3 |                26   |                            48.3 | Poha                    |
| breakfast | Friday    | 08:50              |                     73.7 | 08:50           |              81.3 |                82   |                            48.3 | Dosa                    |
| breakfast | Saturday  | 09:40              |                    104   | 10:10           |             199   |               110   |                           100   | Dosa                    |
| breakfast | Sunday    | 09:40              |                    110   | 10:05           |             220   |                70   |                            90   | Dosa                    |
| dinner    | Monday    | 21:15              |                     52.3 | 21:15           |              23.7 |                23.3 |                            33.3 | Roti/Sabzi              |
| dinner    | Tuesday   | 21:10              |                     52.3 | 22:10           |              76   |               152   |                            41.7 | Roti/Sabzi              |
| dinner    | Wednesday | 21:30              |                     45.3 | 21:30           |              52.3 |                87.3 |                            91.7 | Veg Biryani (special)   |
| dinner    | Thursday  | 21:15              |                     56.7 | 21:30           |              39.7 |                49   |                            26.7 | Roti/Sabzi              |
| dinner    | Friday    | 21:25              |                     45.7 | 21:35           |              51.3 |                 7.3 |                            16.7 | Paneer + Roti (special) |
| dinner    | Saturday  | 20:40              |                     69   | 20:45           |              52   |                 5.1 |                             5   | Roti/Sabzi              |
| dinner    | Sunday    | 20:30              |                     69   | 20:45           |              37   |                 3.5 |                             0   | Roti/Sabzi              |
| lunch     | Monday    | 13:50              |                     56.3 | 13:55           |              37.3 |                28.7 |                            30   | Rice/Dal/Roti           |
| lunch     | Tuesday   | 13:50              |                     57.3 | 14:30           |              60   |               120   |                            35   | Rice/Dal/Roti           |
| lunch     | Wednesday | 12:50              |                     78.3 | 12:55           |              58.7 |                 5.9 |                            20   | Rice/Dal/Roti           |
| lunch     | Thursday  | 12:50              |                     90.7 | 12:55           |             114.3 |               100   |                            96.7 | Rice/Dal/Roti           |
| lunch     | Friday    | 12:55              |                     86   | 12:55           |              74.7 |               114   |                            48.3 | Rice/Dal/Roti           |
| lunch     | Saturday  | 13:00              |                     56   | 13:00           |              12   |                 1.4 |                             0   | Rice/Dal/Roti           |
| lunch     | Sunday    | 13:10              |                     59   | 13:10           |              32   |                 3.6 |                             0   | Rice/Dal/Roti           |

## Figures

![arrivals](figures/eda_1_arrivals.png)

![queue](figures/eda_2_queue.png)

![wait](figures/eda_3_wait.png)

![service](figures/eda_4_service_and_balance.png)

![rho](figures/eda_5_rho_autocorr_heuristic.png)

![occupancy](figures/eda_6_occupancy.png)
