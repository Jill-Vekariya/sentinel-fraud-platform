# Portfolio feature freeze

Frozen on 2026-10-09 after the following six release checks. A later [clean-checkout repeat](FINAL_CHECKLIST.md) reproduced the core results, and a small dashboard input-display bug was fixed and checked. This is the student portfolio scope, with bug fixes and documentation corrections allowed; no additional platform components are required for this release.

| Release step | Completion evidence |
|---|---|
| Clean environment run | Pinned dependencies installed in a clean Python environment; rebuilt CPU Docker image and Compose startup passed; GitHub Actions starts from a clean checkout on hosted runners |
| Complete automated suite | 18 Python regression tests passed locally and in the rebuilt image; connected dashboard and browser parity/interaction checks passed |
| Real-data reproduction | Full 284,807-row CSV and five approaches rerun; 17,147 numeric comparisons passed at tolerance 1e-8 |
| Concurrent load and basic security | 300/300 new HTTP requests, 20 concurrent retries with one durable decision, 27 basic security checks passed after two fixes |
| Short demonstration | [48-second captioned captured API walkthrough](sentinel-demo.mp4), with [transcript and provenance](DEMO_TRANSCRIPT.md) |
| Feature freeze and limitations | This release record plus [final integration verification](FINAL_VERIFICATION.md), [load/security scope](LOAD_SECURITY.md) and [benchmark protocol](REAL_BENCHMARK.md) |

The immutable benchmark/integration source checkpoint `dcb046a0cf0f7a20214ae4100f1e9640b1be24de` passed [all four CI jobs](https://github.com/Jill-Vekariya/sentinel-fraud-platform/actions/runs/37939745257). The final security fixes and release evidence are committed after that checkpoint; their exact commit and CI status are available in the [workflow history](https://github.com/Jill-Vekariya/sentinel-fraud-platform/actions/workflows/ci.yml). No benchmark model or dataset changed during the API security fixes.

## Included scope

Synthetic streaming feature computation, XGBoost/Isolation Forest inference, cost-sensitive threshold exploration, classifier explanations, durable SQLite decisions/history/outbox, Kafka input/output and DLQ, optional Redis read mirror, feedback/monitoring, guarded offline model lifecycle, Docker startup, reproducible real-data benchmarking and the free public browser demo.

## Remaining limitations

- The public GitHub Pages demo performs browser inference and stores local history. The Python/Kafka platform runs separately in Docker; a publicly hosted, continuously available backend has not been deployed.
- One API replica, one SQLite writer and serialized scoring limit concurrency. Two bounded load runs reached p95 987 ms and 1,269 ms at ten clients. There is no sustained throughput, availability or low-latency SLA.
- Kafka output is at least once. Consumers must deduplicate transaction IDs. Restart replay checks do not prove end-to-end exactly-once delivery; crash injection, host reboot and multi-replica behavior remain untested.
- The serving model learns synthetic data. The separate real benchmark uses supplied anonymized PCA features and one chronological split from two days in 2013, with only 75 holdout frauds. It does not validate the synthetic model on real transactions or establish future generalization.
- Scores are uncalibrated. Threshold cost assumptions include perfect interception and hypothetical friction/review costs; measured benchmark savings are not realized business savings. Review-only labels and immature labels can bias retraining.
- Basic selected security checks passed. A comprehensive penetration test, dependency security review, rate/body limits and internet-facing TLS/access control are outside this validation.
- Public desktop interactions were inspected. The Docker dashboard passed API-connected DOM tests; its visual layout, mobile behavior and accessibility were not independently audited.
- Optional MLflow and Kubernetes/Azure reference configurations were not exercised. Distributed feature storage, canary routing, automatic retraining scheduling and managed cloud ML endpoints remain intentionally excluded.

Use this as an evaluated B.Tech portfolio project. Resume claims should describe implementation and measured conditions accurately; interview preparation should cover the data split, threshold selection, idempotency/outbox behavior, explanation limits and observed concurrency tradeoff. See [INTERVIEW_GUIDE.md](INTERVIEW_GUIDE.md).
