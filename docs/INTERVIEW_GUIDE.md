# Explain the project accurately

Use the first-person examples only for work you actually performed and can explain. See [career preparation](CAREER_READINESS.md) for contribution wording and practical exercises.

## A 60-second explanation

“I built a real-time fraud decisioning reference platform. Transactions arrive through a Kafka-compatible stream or a FastAPI endpoint. Shared feature code calculates recent account activity without using future events. An XGBoost classifier and an Isolation Forest percentile produce a risk score; a threshold and review rules return approve, review or block. Each transaction commits its history, decision and event outbox atomically, so retries cannot double-count activity. I added supervised SHAP reasons, reviewer feedback, PSI and labelled performance reports, versioned training, validation gates and model rollback. I used synthetic data to test the pipeline and clearly separated those results from production fraud claims.”

## Ten implementation-specific answers

Use these as preparation notes, then explain them without reading. Source references identify where to inspect the behavior rather than asking you to memorize technology names.

**1. Why XGBoost and Isolation Forest?** XGBoost learns nonlinear patterns and interactions in labelled tabular features. Isolation Forest contributes an unsupervised anomaly ranking learned from legitimate training rows. Sentinel fixes the blend at 95% classifier output and 5% empirical anomaly percentile. That is a demonstrable design choice, not proof that the blend is superior: in the real benchmark its PR-AUC was 0.7663 versus 0.7639 for XGBoost, but both selected the same default-cost holdout decisions. Inspect `fraud/train.py`, `fraud/model.py` and `scripts/benchmark_real.py`. Be ready to propose an ablation and score calibration on fresh data.

**2. Why is fraud classification imbalanced?** The real dataset has 492 frauds among 284,807 transactions, about 0.173%. Predicting every event legitimate would achieve about 99.83% accuracy while catching no fraud. Use PR-AUC to assess ranking, and recall/precision/FPR, review volume and assumed financial cost to assess an operating policy. The synthetic serving dataset is different, with about 3.5% fraud, so do not transfer its metrics to real customers.

**3. How are APPROVE, REVIEW and BLOCK chosen?** `fraud/model.py` computes a blended ranking score. BLOCK begins at the validation-selected threshold; REVIEW begins at 65% of that threshold; lower scores initially APPROVE. At least 12 prior events in five minutes or a foreign event with amount ratio at least 10 adds an explicit reason and raises APPROVE to REVIEW. Rules do not lower BLOCK. Synthetic training picks the lowest validation threshold within a 1% BLOCK FPR budget. The separate real-data cost explorer minimizes assumed validation loss, false-positive friction and review cost; it does not choose thresholds using holdout. Explain those two policies separately.

**4. How does the Kafka-compatible stream work?** The producer keys transactions by account ID so one account follows its partition ordering. Redpanda implements the broker interface. The worker requests a durable API decision and manually commits the input offset afterward; malformed, conflicting or late events require confirmed DLQ publication before offset commit. The SQL transaction also creates an output outbox row. Publishing and marking delivery cannot be one atomic Kafka/SQLite operation, so output is at least once and downstream consumers must deduplicate by transaction ID. Inspect `fraud/produce.py`, `fraud/worker.py` and `fraud/store.py`.

**5. How is leakage prevented?** The serving feature code uses only preceding account events and never the label. Training carries prior history forward as an online system would, fits models on the earliest 60%, selects thresholds on validation, and reports the final 20% separately. The real benchmark keeps equal `Time` groups together, fits StandardScaler only on training and builds the anomaly reference from legitimate training rows. Its supplied PCA transformation has unknown provenance; do not claim that all upstream leakage is ruled out. Champion comparisons also require a fresh validation window not previously used to train the champion. Inspect `fraud/features.py`, `fraud/data.py` and the [verified split boundaries](FINAL_CHECKLIST.md).

**6. What does SHAP explain, and what are its limits?** Native XGBoost Tree SHAP decomposes the classifier margin into a baseline plus feature contributions in log-odds. The API returns its top positive contributions; the browser displays positive and negative contributions and their sum. It does not explain the Isolation Forest component or policy rules, establish causation, or make uncalibrated scores into probabilities. Correlated features and the reference distribution affect attribution. Browser/classifier explanation parity was checked on deterministic cases; that is an implementation check, not proof of model validity. Inspect `fraud/model.py` and `hosted-demo/explain.js`.

**7. How is drift detected?** `fraud/monitor.py` compares the latest 1,000 decision feature vectors with training histograms using Population Stability Index. At least 100 decisions are required; any PSI above 0.2 flags investigation and recommends retraining. It is a heuristic and can react to seasonality or discrete features. Performance metrics require at least 100 observed labels and both classes; selective review feedback is not a representative mature-label evaluation. `fraud/retrain.py` creates a candidate only when drift is flagged or `--force` is supplied. There is no built-in automatic scheduler or promotion.

**8. How do promotion and rollback work?** Each candidate gets an immutable version directory, model files, checksums and a report. Explicit `--promote` requires validation PR-AUC at least 0.15, recall at least 0.10, BLOCK FPR at most 1%, and no PR-AUC drop greater than 0.02 against the champion on the same validation rows. These are demo gates. Atomic pointer replacement records the previous version; the serving manager reloads the new version. Rollback changes the pointer for future scores without rewriting prior decisions or feature history. Only trusted locally built pickle artifacts may be loaded; checksums detect accidental corruption but do not authenticate an attacker-controlled model plus metadata. Inspect `fraud/train.py` and `fraud/model.py`; concurrent promoters are unsupported.

**9. Why SQLite and Redis?** SQLite WAL provides one local transaction for account history, decision, fingerprint and output outbox. A scoring failure rolls the transaction back; the same ID/payload replays its original decision while changed payloads return 409. Redis mirrors decision reads with a TTL and never owns correctness. This makes the student project runnable without coordinating two authoritative stores. The cost is serialized writes/model scoring and no high availability. Ten-client p95 was 987 ms and 1,269 ms in two bounded runs. Inspect `fraud/store.py`, `fraud/api.py` and [load conditions](LOAD_SECURITY.md).

**10. What would change before a real financial institution deployed it?** First define representative mature-label data, customer/currency semantics, label delay, leakage checks, calibration and threshold/review-capacity economics. Establish security/access controls, TLS, rate/body limits, secrets handling, artifact trust and privacy/audit retention. Replace single-node state only when scale and availability requirements demand shared transactional state, account concurrency control and owned outbox publishing. Test sustained load, failure recovery, backups, late-event correction and version-specific monitoring. Those are deployment requirements to justify and validate, not features currently claimed. No portfolio check certifies banking production readiness.

## Practice the explanation

1. Start from a fresh checkout and explain why the trainer runs before API readiness. Trace one transaction through features, policy, ledger and Kafka output using the [architecture diagram](ARCHITECTURE.md).
2. Demonstrate a normal payment, a foreign spike and classifier contributions. Say which model and policy each explanation covers.
3. Replay an identical transaction, then change its amount while retaining its ID. Predict the result before issuing the request, and show the unchanged decision count.
4. Explain the real-data train/validation/holdout boundaries and change a cost assumption. Identify which data selects the threshold and why the displayed financial outcome is hypothetical.
5. Explain one measured limitation without guessing a benefit: serialized writes, selected feedback labels, short load tests or the unknown upstream PCA fitting procedure.

Rehearse a three-minute demonstration and a one-minute architecture explanation. You have prepared evidence and notes; being able to defend them requires your own practice.

## Additional follow-up questions

**What happens to out-of-order events?** Strict per-account watermark rejection and a DLQ. Historical reconstruction uses isolated state. Real late-event tolerance needs event-time windows and correction policy.

**Can it scale on Kubernetes?** The provided manifest deliberately uses one replica. Production scale requires transactional shared state, partition-aware account updates, publisher ownership and load testing.

## Honest resume version

**Real-Time Fraud Detection & Risk Decisioning Platform** — Python, XGBoost, Isolation Forest, Kafka, FastAPI, Redis, Docker

- Built a streaming fraud reference platform with account velocity features, supervised/anomaly risk scoring, review rules and native Tree SHAP explanations.
- Implemented durable idempotency, an event outbox, manual Kafka offset commits, feedback capture, drift monitoring, chronological evaluation and versioned model rollback.
- Compared five approaches on 284,807 anonymized credit-card transactions using chronological splits and validation-selected thresholds; XGBoost achieved 0.7639 holdout PR-AUC.
- Added an operations dashboard, automated checks and a public browser demo with classifier explanations and hypothetical cost scenarios.

Add measured latency or business impact only when you can provide hardware, workload, dataset, baseline and evaluation conditions. Do not reuse “35% fewer false positives,” “2 weeks to 1 day” or “92% recall” from a proposed resume draft as if these were measured results.
