# Final integration verification

Executed on 2026-10-09 on Windows with Docker Desktop/WSL2, Python 3.12.15 and CPU XGBoost 3.0.0. These are bounded portfolio checks, including a short concurrent HTTP workload; they do not establish production certification or a capacity SLA.

A later [fresh-checkout checklist](FINAL_CHECKLIST.md) repeated startup with new model/data volumes, all 18 tests, standard producer and full broker audits, restart replay, benchmark reproduction, 300 successful load requests and 27 security checks. The repeat run measured 10-client p95 1,269 ms; the original run below measured 987 ms. Both are retained with their conditions.

| Check | Evidence |
|---|---|
| Complete Compose startup | `docker compose up --build -d` succeeded; API, broker and Redis healthy, worker running |
| Python regression checks | 18 passed in the rebuilt image and local Python environment |
| Live Kafka pipeline | 20 unique synthetic inputs across four accounts; all 20 durable decisions and corresponding output IDs observed |
| API and persistence | Authentication, invalid input, identical replay, conflicting payload and feedback passed |
| Stream failure handling | A deliberately late account event reached the DLQ; all 20 audit outbox rows were marked delivered |
| Redis and monitoring | Decision mirror, monitoring endpoint and Prometheus metrics present |
| API restart | Saved transaction replayed with exactly the same risk score and one decision row |
| Dashboard connected to Docker API | Connection, model display, scoring, recent decisions and feedback passed in jsdom with no JavaScript errors |
| Public browser demo | Desktop rendering and guided scoring, explanations, feedback, batch simulation and threshold/cost controls inspected in Chrome |
| Browser benchmark default policy | Every default table row matches the published minimum-cost policy; regression check added |
| Real benchmark reproduced on CPU | All 284,807 CSV rows and five approaches rerun; 17,147 numeric comparisons passed at absolute tolerance 1e-8 |
| Concurrent HTTP load | 300/300 successful requests across 1, 5 and 10 clients; p95 41.61 / 486.10 / 987.48 ms respectively |
| Concurrent replay | 20 requests returned one new decision and 19 replays; exactly one ledger row and one outbox row |
| Basic security | 27 checks passed after fixing non-ASCII key and overflowing-number errors |
| Recorded demonstration | 48-second captioned visualization of captured Docker API requests, decisions and classifier explanations |
| Feature freeze | Scope and remaining limitations recorded in [RELEASE_FREEZE.md](RELEASE_FREEZE.md) |

The maximum benchmark difference was 6.776263578034403e-21. Dataset SHA-256: `76274b691b16a6c49d3f159c883398e03ccd6d1ee12d9d8ee38f4b4b98551a89`. The original aggregate benchmark remains unchanged. Reports: [live](live-verification.json), [restart](restart-verification.json), [benchmark reproduction](benchmark-reproduction-check.json), [Docker dashboard](dashboard-test.json), [browser DOM checks](hosted-demo-test.json) and [load/security with captured demo responses](load-security.json).

After the security fixes, the rebuilt image passed the complete 18-test suite, the 27-check security audit, the bounded load workload, the live Kafka audit, the actual API restart/replay check and the connected dashboard check again. Benchmark model code and data were unchanged by those API fixes.

## Fixes verified

- Successful-request timing now includes the DB commit and optional Redis write. Stored core-scoring latency remains a separate measurement.
- The browser uses the exact published validation threshold at the default costs. An equally optimal validation quantile previously added one holdout false positive, showing EUR 2,645.78 rather than EUR 2,639.78 for XGBoost. No holdout information selects the threshold.
- Linux x86_64 installs the official CPU XGBoost package at the same version, avoiding unused GPU dependencies after an incomplete GPU dependency download failed checksum validation. Checksum validation was retained. Tests and the complete real benchmark passed with the CPU package.
- Invalid non-ASCII API keys now return 401 through a constant-time byte comparison. Previously the string comparison could raise a server error.
- Overflowing JSON numbers now return 422 field diagnostics. Invalid inputs and arbitrary validation contexts are omitted from error responses so non-finite values cannot break JSON serialization.

## Reproduce the bounded checks

```bash
docker compose up --build -d
docker compose run --rm --no-deps -e REDIS_URL= api python -m pytest -q
docker compose exec -T api python -m scripts.verify_live
docker compose restart api
docker compose exec -T api python -m scripts.verify_restart
npm ci
npm run test:dashboard
npm run test:hosted
```

The live helper creates synthetic audit events and consumer groups in the running demo, then saves a checkpoint in its data volume. The restart helper must follow that successful live run and an actual API restart. The Node dashboard check uses the local demo API key; adapt it if your `.env` overrides that key. See [benchmark protocol](REAL_BENCHMARK.md) to obtain the excluded raw CSV and rerun it, then compare reports with `python -m scripts.verify_benchmark expected.json reproduced.json`.

See [LOAD_SECURITY.md](LOAD_SECURITY.md) for the isolated load/security command sequence, measured percentiles and workload limits. [DEMO_TRANSCRIPT.md](DEMO_TRANSCRIPT.md) identifies the captured API values used in the video.

## Scope limits

The public browser demo performs browser inference and stores local history; it does not host the Python/Kafka backend. The Docker dashboard was checked against the actual backend through jsdom; its visual layout on the user's computer was not inspected. The short load workload used one isolated API without Redis or Kafka; it does not establish sustained throughput or distributed capacity. No comprehensive penetration test, mobile/accessibility audit, host reboot, crash-injection campaign, multi-replica correctness, Kubernetes/Azure deployment or optional MLflow exercise was performed. Passing replay after an API restart does not establish end-to-end exactly-once Kafka delivery. Upstream Starlette/AnyIO and SciPy solver-option warnings were observed; the checks and numeric reproduction passed.
