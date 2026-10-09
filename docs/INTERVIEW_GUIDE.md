# Explain the project accurately

Use the first-person examples only for work you actually performed and can explain. See [career preparation](CAREER_READINESS.md) for contribution wording and practical exercises.

## A 60-second explanation

“I built a real-time fraud decisioning reference platform. Transactions arrive through a Kafka-compatible stream or a FastAPI endpoint. Shared feature code calculates recent account activity without using future events. An XGBoost classifier and an Isolation Forest percentile produce a risk score; a threshold and review rules return approve, review or block. Each transaction commits its history, decision and event outbox atomically, so retries cannot double-count activity. I added supervised SHAP reasons, reviewer feedback, PSI and labelled performance reports, versioned training, validation gates and model rollback. I used synthetic data to test the pipeline and clearly separated those results from production fraud claims.”

## Likely interview questions

**Why two models?** The classifier learns labelled patterns; the anomaly model can contribute novelty information. Here the fixed 95/5 blend is a transparent demo choice, not empirically proven best. A real evaluation should ablate it and consider calibrated score fusion.

**Why not accuracy?** The synthetic fraud rate is about 3.5%; a majority-class baseline would have high accuracy. PR-AUC, fraud recall at a specified false-positive budget, review precision/capacity and financial loss are more meaningful.

**What is the exactly-once guarantee?** There is none end-to-end. Atomic SQL idempotency ensures one durable decision/state update for each ID. Kafka output is at-least-once because a publish acknowledgement can precede a process crash before delivery marking. Downstream deduplication is required.

**Why SQLite instead of Redis as a feature store?** SQLite lets this reference atomically persist history, ledger and outbox. Redis is an optional decision cache; making it authoritative would require multi-store coordination or a different transactional design. SQLite is a known scale limit.

**What happens to out-of-order events?** Strict per-account watermark rejection and a DLQ. Historical reconstruction uses isolated state. Real late-event tolerance needs event-time windows and correction policy.

**How do you avoid leakage?** Features only inspect prior account activity. Model fit uses the earliest chronological 60%; threshold selection uses validation and final reporting uses holdout. Labels never enter online features.

**What do explanations mean?** Positive Tree SHAP contributions to XGBoost log-odds, not causes. The blended anomaly component has no SHAP explanation; policy rules get explicit reason codes.

**What triggers retraining?** A supplied CLI inspects PSI and creates a candidate from a separately curated mature-label dataset. It never auto-promotes. An external scheduler can invoke it; the repository does not claim to schedule it.

**Can it scale on Kubernetes?** The provided manifest deliberately uses one replica. Production scale requires transactional shared state, partition-aware account updates, publisher ownership and load testing.

## Honest resume version

**Real-Time Fraud Detection & Risk Decisioning Platform** — Python, XGBoost, Isolation Forest, Kafka, FastAPI, Redis, Docker, Kubernetes

- Built a streaming fraud reference platform with account velocity features, supervised/anomaly risk scoring, review rules and native Tree SHAP explanations.
- Implemented durable idempotency, an event outbox, manual Kafka offset commits, feedback capture, drift monitoring, chronological evaluation and versioned model rollback.
- Added an operations dashboard, automated correctness checks, Docker Compose and a Kubernetes deployment reference; evaluated using synthetic transactions.

Add measured latency or business impact only when you can provide hardware, workload, dataset, baseline and evaluation conditions. Do not reuse “35% fewer false positives,” “2 weeks to 1 day” or “92% recall” from a proposed resume draft as if these were measured results.
