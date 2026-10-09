# A three-minute internship demo

1. Open the [public demo](https://jill-vekariya.github.io/sentinel-fraud-platform/). Explain that it runs an exported synthetic model in the browser, while the complete backend runs in Docker.
2. Select **Normal payment**, then **Foreign amount spike**. Show the decisions, prior account features, explicit rule reasons and classifier contributions. Explain that contributions describe the classifier in log-odds, not causation or the anomaly component.
3. Change the demo block threshold and score a new transaction. Explain the tradeoff between missed fraud, false positives and review capacity. Previous decisions retain their original policy context.
4. Show the real-data comparison: 284,807 rows, the same chronological split for five approaches, and XGBoost holdout PR-AUC 0.7639. Increase false-positive friction in the cost explorer. Explain that thresholds are chosen on validation and displayed financial outcomes are hypothetical assumptions.
5. Show the [verification record](FINAL_VERIFICATION.md). For a backend demonstration, start Compose, open its dashboard, enter the configured API key and score a transaction. Run the live and restart helpers to demonstrate durable replay, output and DLQ behavior.

Finish with one design tradeoff you can explain: SQLite provides atomic local state but limits horizontal scale, Redis is a mirror, and Kafka output may be duplicated after a crash. Describe your own contribution accurately, and be ready to reproduce the commands without assistance.
