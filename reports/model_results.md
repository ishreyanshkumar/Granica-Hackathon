# Model results (Forward Split)

Evaluated strictly on Forward Split: trained on past dates (12 days), tested on held-out future dates (5 days, 15 sessions, including real weekend meals).

- Chosen model: **XGB** (lowest congested-interval MAE averaged over horizons on forward out-of-sample: xgb 13.60, mlp 14.27)
- XGB hyper-parameters (grouped inner CV): `{'max_depth': 3, 'n_estimators': 300, 'min_child_weight': 5}`
- Most important inputs (10-min horizon): served_l0, prof_in_2, prof_in_sum3, mu, in_r3

## Out-of-Sample Forward Split Metrics

### MAE (people, all intervals)

| model                |   5 min |   10 min |   15 min |
|:---------------------|--------:|---------:|---------:|
| xgb                  |    4.45 |     7.79 |    10.98 |
| mlp                  |    5.26 |     8.88 |    12.44 |
| physics_profile      |    8.85 |    16.48 |    23.91 |
| seasonal_profile     |   10.33 |    12.68 |    15.01 |
| persistence          |    5.05 |     9.39 |    13.62 |
| experimental_formula |   24.09 |    24.87 |    25.71 |

### MAE on congested intervals (true queue >= 10), people

| model                |   5 min |   10 min |   15 min |
|:---------------------|--------:|---------:|---------:|
| xgb                  |    8.23 |    13.74 |    18.83 |
| mlp                  |    9.09 |    14.39 |    19.32 |
| physics_profile      |   12.9  |    23.83 |    33.81 |
| seasonal_profile     |   17.41 |    21.34 |    24.89 |
| persistence          |    9.43 |    16.59 |    23.16 |
| experimental_formula |   49.58 |    49.58 |    49.57 |

### Wait-time MAE (minutes: predicted queue / service rate vs actual)

| model                |   5 min |   10 min |   15 min |
|:---------------------|--------:|---------:|---------:|
| xgb                  |    2.4  |     4.59 |     6.69 |
| mlp                  |    2.61 |     4.92 |     7.26 |
| physics_profile      |    4.28 |     8.24 |    12.32 |
| seasonal_profile     |    4.62 |     6.02 |     7.47 |
| persistence          |    2.44 |     4.69 |     6.88 |
| experimental_formula |    9.07 |     9.36 |     9.7  |

### RED alert (wait >= 8 min): recall, then precision (309 RED intervals across horizons in test set)

| model                |   5 min |   10 min |   15 min |
|:---------------------|--------:|---------:|---------:|
| xgb                  |    0.81 |     0.62 |     0.5  |
| mlp                  |    0.79 |     0.61 |     0.48 |
| physics_profile      |    0.72 |     0.55 |     0.48 |
| seasonal_profile     |    0.65 |     0.54 |     0.46 |
| persistence          |    0.8  |     0.62 |     0.47 |
| experimental_formula |    0.01 |     0.01 |     0    |

| model                |   5 min |   10 min |   15 min |
|:---------------------|--------:|---------:|---------:|
| xgb                  |    0.88 |     0.74 |     0.67 |
| mlp                  |    0.87 |     0.72 |     0.63 |
| physics_profile      |    0.72 |     0.46 |     0.34 |
| seasonal_profile     |    0.81 |     0.72 |     0.66 |
| persistence          |    0.87 |     0.75 |     0.63 |
| experimental_formula |    1    |     1    |     0    |

### 80% prediction band coverage (XGB quantiles; target 0.80)

| model   |   5 min |   10 min |   15 min |
|:--------|--------:|---------:|---------:|
| xgb     |    0.71 |     0.69 |     0.68 |

## Figures

![mae](figures/model_1_mae.png)

![example](figures/model_2_example.png)

![importance](figures/model_3_importance.png)
