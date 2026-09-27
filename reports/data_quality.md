# Data quality report

- Sessions: 6 real, 45 synthetic
- 5-minute rows: 1616 (197 real)

NOTE: All physical inputs are timestamped taps (IN, OUT, SERVED) in bronze inout/ files.
5-minute intervals and queues are derived automatically in data/processed/.

Checks per session: known event names (IN, OUT, SERVED), IN vs OUT within 5% (door drift).

| session | source | rows | taps | status |
| --- | --- | --- | --- | --- |
| SYN_breakfast_2026-09-07 | synthetic | 32 | 2159 taps | OK |
| SYN_lunch_2026-09-07 | synthetic | 30 | 2366 taps | OK |
| SYN_dinner_2026-09-07 | synthetic | 32 | 2195 taps | OK |
| SYN_breakfast_2026-09-08 | synthetic | 31 | 1992 taps | OK |
| SYN_lunch_2026-09-08 | synthetic | 30 | 2493 taps | OK |
| SYN_dinner_2026-09-08 | synthetic | 32 | 2503 taps | OK |
| SYN_breakfast_2026-09-09 | synthetic | 31 | 2055 taps | OK |
| SYN_lunch_2026-09-09 | synthetic | 30 | 2657 taps | OK |
| SYN_dinner_2026-09-09 | synthetic | 33 | 2295 taps | OK |
| SYN_breakfast_2026-09-10 | synthetic | 31 | 2297 taps | OK |
| SYN_lunch_2026-09-10 | synthetic | 30 | 2698 taps | OK |
| SYN_dinner_2026-09-10 | synthetic | 33 | 2413 taps | OK |
| SYN_breakfast_2026-09-11 | synthetic | 32 | 1996 taps | OK |
| SYN_lunch_2026-09-11 | synthetic | 30 | 2665 taps | OK |
| SYN_dinner_2026-09-11 | synthetic | 34 | 2505 taps | OK |
| SYN_breakfast_2026-09-14 | synthetic | 32 | 1947 taps | OK |
| SYN_lunch_2026-09-14 | synthetic | 30 | 2718 taps | OK |
| SYN_dinner_2026-09-14 | synthetic | 33 | 2482 taps | OK |
| SYN_breakfast_2026-09-15 | synthetic | 33 | 2232 taps | OK |
| SYN_lunch_2026-09-15 | synthetic | 30 | 2468 taps | OK |
| SYN_dinner_2026-09-15 | synthetic | 33 | 2524 taps | OK |
| SYN_breakfast_2026-09-16 | synthetic | 33 | 2038 taps | OK |
| SYN_lunch_2026-09-16 | synthetic | 29 | 2365 taps | OK |
| SYN_dinner_2026-09-16 | synthetic | 32 | 2452 taps | OK |
| SYN_breakfast_2026-09-17 | synthetic | 31 | 2222 taps | OK |
| SYN_lunch_2026-09-17 | synthetic | 30 | 2842 taps | OK |
| SYN_dinner_2026-09-17 | synthetic | 32 | 2763 taps | OK |
| SYN_breakfast_2026-09-18 | synthetic | 32 | 1802 taps | OK |
| SYN_lunch_2026-09-18 | synthetic | 31 | 2688 taps | OK |
| SYN_dinner_2026-09-18 | synthetic | 34 | 2292 taps | OK |
| SYN_breakfast_2026-09-21 | synthetic | 31 | 2201 taps | OK |
| SYN_lunch_2026-09-21 | synthetic | 30 | 2587 taps | OK |
| SYN_dinner_2026-09-21 | synthetic | 33 | 2257 taps | OK |
| SYN_breakfast_2026-09-22 | synthetic | 32 | 2345 taps | OK |
| SYN_lunch_2026-09-22 | synthetic | 31 | 2466 taps | OK |
| SYN_dinner_2026-09-22 | synthetic | 32 | 2209 taps | OK |
| SYN_breakfast_2026-09-23 | synthetic | 31 | 2161 taps | OK |
| SYN_lunch_2026-09-23 | synthetic | 30 | 2530 taps | OK |
| SYN_dinner_2026-09-23 | synthetic | 32 | 2370 taps | OK |
| SYN_breakfast_2026-09-24 | synthetic | 30 | 2197 taps | OK |
| SYN_lunch_2026-09-24 | synthetic | 31 | 2776 taps | OK |
| SYN_dinner_2026-09-24 | synthetic | 33 | 2466 taps | OK |
| SYN_breakfast_2026-09-25 | synthetic | 32 | 2330 taps | OK |
| SYN_lunch_2026-09-25 | synthetic | 30 | 2424 taps | OK |
| SYN_dinner_2026-09-25 | synthetic | 35 | 2734 taps | OK |
| MESSA_breakfast_2026-09-26 | real | 37 | 2388 taps | OK |
| MESSA_lunch_2026-09-26 | real | 32 | 2518 taps | OK |
| MESSA_dinner_2026-09-26 | real | 30 | 2754 taps | OK |
| MESSA_breakfast_2026-09-27 | real | 37 | 2481 taps | OK |
| MESSA_lunch_2026-09-27 | real | 32 | 2600 taps | OK |
| MESSA_dinner_2026-09-27 | real | 29 | 2674 taps | OK |
