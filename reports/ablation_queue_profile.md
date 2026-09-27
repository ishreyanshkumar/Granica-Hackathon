# Ablation: historical queue-profile features

XGBoost, congested-interval MAE (people, true line >= 10), forward out-of-sample split (last 5 days held out). Lower is better.

| features        |   5 min |   10 min |   15 min |
|:----------------|--------:|---------:|---------:|
| + queue profile |   10.03 |    15.24 |    21.81 |
| model features  |    9.4  |    14.12 |    19.32 |

Mean over horizons: + queue profile **15.69**, model features **14.28**

Decision: the queue-profile features are **left out** of the model (they fit past queues too closely and forecast worse on unseen days).
