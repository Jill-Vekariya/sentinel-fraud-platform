# Real-dataset benchmark and cost policy

Completed on 2026-10-09 using the public ULB/Worldline credit-card dataset: 284,807 transactions and 492 fraud labels. [OpenML 1597](https://www.openml.org/d/1597) documents its provenance. The compressed CSV mirror is the download source referenced by [River's credit-card dataset implementation](https://github.com/online-ml/river/blob/main/river/datasets/credit_card.py). The report records the actual CSV SHA-256 and MD5; raw data is excluded from Git.

## Protocol

Stable chronological Time sort; equal Time values never cross split boundaries. Train: 170,882 rows / 360 frauds. Validation: 56,963 / 57. Holdout: 56,962 / 75. All approaches use identical rows and 30 provided numeric features. StandardScaler is fitted only on training for logistic regression. Isolation Forest is trained only on legitimate training rows and percentile references come from training. No oversampling, tuning on holdout or account-feature fabrication.

Models: prior baseline, logistic regression, XGBoost, Isolation Forest and the fixed 95/5 classifier/anomaly blend. Settings and seed 42 are in the reproducible script. This is a fixed-settings comparison, not a claim that all approaches were optimally tuned.

Each model chooses two operating thresholds on validation only: lowest threshold within a 1% FPR budget, and minimum assumed financial cost. Holdout metrics are reported at these fixed thresholds. Curves in the browser are exploratory; scenario choices use validation curves, then display their holdout outcomes.

## Holdout results at validation-selected minimum-cost thresholds

Default hypothetical EUR costs: missed fraud loss = transaction Amount; false-positive friction = €5; review per flagged event = €1. All flagged fraud is assumed prevented.

| Approach | PR-AUC | Recall | FPR | Flagged | Assumed cost |
|---|---:|---:|---:|---:|---:|
| Prior baseline | 0.0013 | 0.0% | 0.0000% | 0 | €7,729.26 |
| Logistic regression | 0.6926 | 74.7% | 0.0492% | 84 | €2,974.50 |
| XGBoost | 0.7639 | 76.0% | 0.0527% | 87 | €2,639.78 |
| Isolation Forest | 0.0330 | 29.3% | 0.7612% | 455 | €6,958.71 |
| XGBoost + anomaly (95/5) | 0.7663 | 76.0% | 0.0527% | 87 | €2,639.78 |

Approve-all assumed holdout loss: €7,729.26. This is a counterfactual scenario, not measured business savings. Both the classifier and blend choose the same holdout decisions under the default minimum-cost policy; the small PR-AUC difference does not establish statistical superiority.

## Reproduce

Download the compressed public CSV and extract it into `data/benchmarks/` (never commit raw data):

```bash
curl -L --fail https://maxhalford.github.io/files/datasets/creditcardfraud.zip -o data/benchmarks/creditcard.zip
# Extract creditcard.csv with your ZIP utility.
python -m scripts.benchmark_real --dataset data/benchmarks/creditcard.csv --output docs/real-benchmark.json
```

Create the destination directory first. Install requirements using Python 3.12. The recorded run used Docker/Python 3.12.15, NumPy 2.2.5, pandas 2.2.3, scikit-learn 1.6.1, XGBoost 3.0.0 and SciPy 1.18.1. Copy the report to `hosted-demo/benchmark.json` for the browser. JSON includes split counts, raw file checksum, both policy outcomes and validation/holdout threshold curves. A verified OpenML ARFF can also be supplied; its expected MD5 is checked.

## Interpretation and limits

The data covers two days in 2013, only 75 holdout frauds, and anonymized PCA components whose upstream fitting provenance is unavailable. One chronological split cannot demonstrate statistical superiority or production generalization. Costs and perfect interception are assumed. Scores are not calibrated probabilities. No customer IDs, device identities or countries are supplied; these models cannot be substituted into the synthetic streaming feature schema.

The live demo uses the original synthetic model. Its exact browser classifier Tree SHAP calculations were checked against native XGBoost on 20 deterministic cases, maximum log-odds difference below 0.000001. The anomaly component and review rules remain separately identified; feature contributions are not causal explanations.

Reference requested by dataset authors: Dal Pozzolo, Caelen, Johnson and Bontempi, *Calibrating Probability with Undersampling for Unbalanced Classification*, CIDM, 2015.
