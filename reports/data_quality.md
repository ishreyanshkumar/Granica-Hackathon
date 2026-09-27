# Data quality report

- Sessions: 6 real, 45 synthetic
- 5-minute rows: 1616 (197 real)
- Stopwatch samples: 849 (97 real)
- Missing queue counts: 58 (3.6%)
- Missing item counts: 41 (2.5%)

Checks per session: known event names, 5-minute interval width, no gaps between intervals,
non-negative counts, IN vs OUT within 5% (door-count drift), taps inside the interval log,
stopwatch served >= join.

| session | source | rows | missing counts | status |
| --- | --- | --- | --- | --- |
| SYN_breakfast_2026-09-07 | synthetic | 32 | 1 q / 0 items | OK |
| SYN_lunch_2026-09-07 | synthetic | 30 | 2 q / 1 items | OK |
| SYN_dinner_2026-09-07 | synthetic | 32 | 3 q / 1 items | OK |
| SYN_breakfast_2026-09-08 | synthetic | 31 | 0 q / 1 items | OK |
| SYN_lunch_2026-09-08 | synthetic | 30 | 1 q / 0 items | OK |
| SYN_dinner_2026-09-08 | synthetic | 32 | 3 q / 0 items | OK |
| SYN_breakfast_2026-09-09 | synthetic | 31 | 2 q / 2 items | OK |
| SYN_lunch_2026-09-09 | synthetic | 30 | 2 q / 0 items | OK |
| SYN_dinner_2026-09-09 | synthetic | 33 | 1 q / 1 items | OK |
| SYN_breakfast_2026-09-10 | synthetic | 31 | 0 q / 0 items | OK |
| SYN_lunch_2026-09-10 | synthetic | 30 | 1 q / 2 items | OK |
| SYN_dinner_2026-09-10 | synthetic | 33 | 4 q / 1 items | OK |
| SYN_breakfast_2026-09-11 | synthetic | 32 | 1 q / 0 items | OK |
| SYN_lunch_2026-09-11 | synthetic | 30 | 1 q / 0 items | OK |
| SYN_dinner_2026-09-11 | synthetic | 34 | 2 q / 0 items | OK |
| SYN_breakfast_2026-09-14 | synthetic | 32 | 0 q / 1 items | OK |
| SYN_lunch_2026-09-14 | synthetic | 30 | 1 q / 0 items | OK |
| SYN_dinner_2026-09-14 | synthetic | 33 | 1 q / 1 items | OK |
| SYN_breakfast_2026-09-15 | synthetic | 33 | 0 q / 0 items | OK |
| SYN_lunch_2026-09-15 | synthetic | 30 | 3 q / 1 items | OK |
| SYN_dinner_2026-09-15 | synthetic | 33 | 1 q / 3 items | OK |
| SYN_breakfast_2026-09-16 | synthetic | 33 | 0 q / 0 items | OK |
| SYN_lunch_2026-09-16 | synthetic | 29 | 2 q / 0 items | OK |
| SYN_dinner_2026-09-16 | synthetic | 32 | 1 q / 1 items | OK |
| SYN_breakfast_2026-09-17 | synthetic | 31 | 1 q / 2 items | OK |
| SYN_lunch_2026-09-17 | synthetic | 30 | 2 q / 1 items | OK |
| SYN_dinner_2026-09-17 | synthetic | 32 | 1 q / 0 items | OK |
| SYN_breakfast_2026-09-18 | synthetic | 32 | 0 q / 2 items | OK |
| SYN_lunch_2026-09-18 | synthetic | 31 | 1 q / 1 items | OK |
| SYN_dinner_2026-09-18 | synthetic | 34 | 1 q / 0 items | OK |
| SYN_breakfast_2026-09-21 | synthetic | 31 | 0 q / 0 items | OK |
| SYN_lunch_2026-09-21 | synthetic | 30 | 0 q / 0 items | OK |
| SYN_dinner_2026-09-21 | synthetic | 33 | 2 q / 1 items | OK |
| SYN_breakfast_2026-09-22 | synthetic | 32 | 0 q / 0 items | OK |
| SYN_lunch_2026-09-22 | synthetic | 31 | 1 q / 2 items | OK |
| SYN_dinner_2026-09-22 | synthetic | 32 | 0 q / 2 items | OK |
| SYN_breakfast_2026-09-23 | synthetic | 31 | 0 q / 1 items | OK |
| SYN_lunch_2026-09-23 | synthetic | 30 | 2 q / 0 items | OK |
| SYN_dinner_2026-09-23 | synthetic | 32 | 2 q / 2 items | OK |
| SYN_breakfast_2026-09-24 | synthetic | 30 | 1 q / 1 items | OK |
| SYN_lunch_2026-09-24 | synthetic | 31 | 2 q / 1 items | OK |
| SYN_dinner_2026-09-24 | synthetic | 33 | 1 q / 2 items | OK |
| SYN_breakfast_2026-09-25 | synthetic | 32 | 1 q / 2 items | OK |
| SYN_lunch_2026-09-25 | synthetic | 30 | 1 q / 1 items | OK |
| SYN_dinner_2026-09-25 | synthetic | 35 | 1 q / 0 items | OK |
| MESSA_breakfast_2026-09-26 | real | 37 | 1 q / 2 items | OK |
| MESSA_lunch_2026-09-26 | real | 32 | 1 q / 0 items | OK |
| MESSA_dinner_2026-09-26 | real | 30 | 1 q / 0 items | OK |
| MESSA_breakfast_2026-09-27 | real | 37 | 1 q / 1 items | OK |
| MESSA_lunch_2026-09-27 | real | 32 | 0 q / 0 items | OK |
| MESSA_dinner_2026-09-27 | real | 29 | 1 q / 1 items | OK |
