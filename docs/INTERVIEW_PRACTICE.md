# Sentinel — interview practice

## Five-sentence technical summary

Sentinel turns transactions into inspectable approve, review or block decisions. It combines account-history features, XGBoost scoring and an anomaly percentile. The local platform stores durable decisions and sends broker outputs through an outbox. The engineering purpose is to connect model scoring with replay handling, monitoring and guarded model changes. The default serving data is synthetic, and real-data offline comparisons and hypothetical costs do not prove real fraud reduction.

This explains the project’s engineering purpose. Describe your own motivation and role using actual experience; this document does not invent either.

## Ten questions and simple answers

1. **What enters the score?** Amount and rolling account/device/time features feed the supervised model and anomaly detector. The documented policy blends classifier output at 95% and anomaly percentile at 5%.

2. **Is the risk score a probability?** No. It is a ranking score used by the decision policy. Calibration on a representative population would require separate evidence.

3. **Why split data chronologically?** Future transactions should not train a model that is evaluated on earlier decisions. Thresholds are selected on validation, not on final holdout outcomes.

4. **What does the SQL outbox do?** It stores a decision and its pending output in the same transaction. The worker can retry delivery without losing the durable decision.

5. **Is delivery exactly once?** Do not claim end-to-end exactly-once delivery. Retries and replay handling limit the effects of duplicates, but broker delivery and SQL state have distinct boundaries.

6. **Why key streaming events by account?** Account history affects rolling features, so per-account ordering matters. Late or conflicting inputs need explicit handling.

7. **What if Redis fails?** Redis is an optional read mirror. Durable SQL state remains responsible for scoring correctness.

8. **What do SHAP contributions explain?** They explain the supervised classifier’s log-odds output. They are not causal explanations and do not fully explain the separate anomaly score or policy rules.

9. **How is promotion guarded?** Candidates face validation gates and a champion comparison before explicit promotion. The gates are demo criteria, not a bank’s accepted business policy.

10. **What is actually deployed?** The public static demo performs browser inference and recorded cost exploration. Kafka/Redis/Python run separately, and the Kubernetes/Azure files are references rather than proof of a managed production deployment.

## Study before an interview

- Trace a transaction through features, model, SQLite transaction and outbox.
- Explain idempotent replay versus an ID with conflicting content.
- Study PR-AUC, recall, false-positive budgets, calibration and label bias.
- Understand threshold selection, mature labels, drift and explicit promotion.
- Run the isolated dashboard check, then explain a failure and recovery yourself.

See [current status](CURRENT_STATUS.md) and the existing project-specific interview and ownership material. These answers are practice aids, not completed personal contributions.
