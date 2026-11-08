# Design decisions

Each entry names a decision visible in the code, the alternative it rejects, and the cost accepted. [ARCHITECTURE.md](ARCHITECTURE.md) describes the resulting system; this page explains why it looks that way.

## 1. One transaction for idempotency, features, decision and outbox

**Decision.** `fraud/store.py` opens `BEGIN IMMEDIATE`, checks the stored fingerprint for the transaction ID, updates account history, scores, writes the decision and inserts the outbox row, then commits. If scoring raises, nothing is persisted.

**Rejected.** Score first, persist later. A crash between the two produces a decision the system cannot explain or replay.

**Cost.** Model inference runs under the write lock, which caps throughput; measured p95 at ten clients was about 1 s ([LOAD_SECURITY.md](LOAD_SECURITY.md)).

## 2. Idempotency means "same ID, same content"

**Decision.** A retry with an identical payload returns the original decision and model version. The same ID with different content returns HTTP 409 instead of silently re-scoring.

**Rejected.** Last-write-wins, which lets a client overwrite the evidence for a past decision.

**Cost.** Clients that mutate payloads on retry must generate a new ID; this is documented as part of the API contract.

## 3. A per-account watermark instead of general out-of-order handling

**Decision.** Events older than an account's most recent accepted timestamp are rejected (`LateEvent`). Equal timestamps follow ingestion order.

**Rejected.** Accepting late events and recomputing features retroactively.

**Cost.** Late events need a separate offline replay path; the online service refuses them rather than producing features that differ from what training saw.

## 4. Transactional outbox with at-least-once delivery

**Decision.** Decisions are published from an `outbox` table by a worker that marks rows delivered only after broker confirmation. Kafka offsets for inputs are committed only after a durable decision (or confirmed DLQ publication).

**Rejected.** Publishing from the request handler, or claiming exactly-once delivery.

**Cost.** A crash between send and mark duplicates an output message; consumers of `decisions` must deduplicate by transaction ID. The README states this plainly.

## 5. One feature function for training and serving

**Decision.** `fraud/features.py` exposes `extract` and `advance`, used by both the training CLI and the API. History is bounded to 24 hours and the 1000 most recent events, using only preceding events.

**Rejected.** A separate batch feature pipeline for training.

**Cost.** `new_device` means "unseen in retained history", not "never seen". The bounded window is a deliberate approximation and is called out in the architecture notes.

## 6. Chronological 60/20/20 split with carried-forward state

**Decision.** `fraud/train.py` splits by time and carries account history across split boundaries, as the online service would.

**Rejected.** Random splits, which leak future behaviour into features.

**Cost.** Lower, more honest metrics: holdout PR-AUC 0.764 on the real anonymised dataset ([REAL_BENCHMARK.md](REAL_BENCHMARK.md)).

## 7. Threshold chosen for FPR ≤ 1 % on validation, not on test

**Decision.** The BLOCK threshold is the one maximising recall subject to validation FPR ≤ 1 %; REVIEW starts at 65 % of that threshold. Promotion gates re-check the FPR budget.

**Rejected.** Picking a threshold on the holdout set, or hard-coding 0.5.

**Cost.** The FPR budget covers BLOCK only; review workload is measured separately and is not bounded by this choice.

## 8. A fixed 95/5 classifier–anomaly blend

**Decision.** Risk = 0.95 × XGBoost probability + 0.05 × Isolation Forest percentile, with the anomaly model trained on legitimate rows only.

**Rejected.** A tuned stacking model, for which there was no second dataset to validate on.

**Cost.** The weight is a demonstration constant. The architecture notes say to compare classifier-only, anomaly-only and blended baselines before defending it.

## 9. Native Tree SHAP for reasons, with explicit scope

**Decision.** Reasons are the top positive SHAP contributions in log-odds, which sum with the bias to the classifier margin. Rule reasons are listed separately.

**Rejected.** Post-hoc text explanations or surrogate models.

**Cost.** Explanations cover only the XGBoost component, not the anomaly score or rules, and are not causal.

## 10. PSI drift monitoring with a stated minimum sample

**Decision.** `fraud/monitor.py` computes PSI against training histograms over the latest 1000 decisions and flags above 0.2 only after 100 samples.

**Rejected.** Alerting on any shift.

**Cost.** Discrete features and seasonal traffic can trip PSI; the flag is a prompt to investigate, not proof of degradation.

## 11. Model promotion is an atomic pointer swap

**Decision.** Training writes a new version directory; promotion replaces the active pointer atomically and keeps the prior version for rollback. Rollback changes future decisions only.

**Rejected.** Overwriting the model file in place.

**Cost.** Concurrent trainers or promoters are unsupported; the reference deployment runs one.

## 12. SQLite as the reference store, with the ceiling written down

**Decision.** A single API process and a shared SQLite file provide a durable, reproducible reference implementation. Redis is only a read cache for decisions.

**Rejected.** Starting with Postgres and a distributed lock before correctness was established.

**Cost.** No horizontal scaling. The architecture notes list exactly what a scaled version needs (shared transaction store, account-state concurrency, separate publisher ownership, remote model artifacts) and tell operators not to add replicas to the provided manifest.
