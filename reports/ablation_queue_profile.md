# Ablation: historical queue-profile features

XGBoost, congested-interval MAE (people, true line >= 10), forward out-of-sample split (last 5 days held out). Lower is better.

| features        |   5 min |   10 min |   15 min |
|:----------------|--------:|---------:|---------:|
| + queue profile |    8.63 |    14.5  |    20.15 |
| model features  |    8.23 |    13.74 |    18.83 |

Mean over horizons: + queue profile **14.43**, model features **13.6**

Decision: the queue-profile features are **left out** of the model (they fit past queues too closely and forecast worse on unseen days).
