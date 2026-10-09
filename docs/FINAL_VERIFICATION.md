# Final integration verification

Executed on 2026-10-09 on Windows with Docker Desktop/WSL2, Python 3.12.15 and CPU XGBoost 3.0.0. These are bounded portfolio checks, not production certification or load testing.

| Check | Evidence |
|---|---|
| Complete Compose startup | `docker compose up --build -d` succeeded; API, broker and Redis healthy, worker running |
| Python regression checks | 17 passed in the rebuilt image |
| Live Kafka pipeline | 20 unique synthetic inputs across four accounts; all 20 durable decisions and corresponding output IDs observed |
| API and persistence | Authentication, invalid input, identical replay, conflicting payload and feedback passed |
| Stream failure handling | A deliberately late account event reached the DLQ; all 20 audit outbox rows were marked delivered |
| Redis and monitoring | Decision mirror, monitoring endpoint and Prometheus metrics present |
| API restart | Saved transaction replayed with exactly the same risk score and one decision row |
| Dashboard connected to Docker API | Connection, model display, scoring, recent decisions and feedback passed in jsdom with no JavaScript errors |
| Public browser demo | Desktop rendering and guided scoring, explanations, feedback, batch simulation and threshold/cost controls inspected in Chrome |
| Browser benchmark default policy | Every default table row matches the published minimum-cost policy; regression check added |
| Real benchmark reproduced on CPU | All 284,807 CSV rows and five approaches rerun; 17,147 numeric comparisons passed at absolute tolerance 1e-8 |

The maximum benchmark difference was 6.776263578034403e-21. Dataset SHA-256: `76274b691b16a6c49d3f159c883398e03ccd6d1ee12d9d8ee38f4b4b98551a89`. The original aggregate benchmark remains unchanged. Reports: [live](live-verification.json), [restart](restart-verification.json), [benchmark reproduction](benchmark-reproduction-check.json), [Docker dashboard](dashboard-test.json) and [browser DOM checks](hosted-demo-test.json).

## Fixes verified

- Successful-request timing now includes the DB commit and optional Redis write. Stored core-scoring latency remains a separate measurement.
- The browser uses the exact published validation threshold at the default costs. An equally optimal validation quantile previously added one holdout false positive, showing EUR 2,645.78 rather than EUR 2,639.78 for XGBoost. No holdout information selects the threshold.
- Linux x86_64 installs the official CPU XGBoost package at the same version, avoiding unused GPU dependencies after an incomplete GPU dependency download failed checksum validation. Checksum validation was retained. Tests and the complete real benchmark passed with the CPU package.

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

## Scope limits

The public browser demo performs browser inference and stores local history; it does not host the Python/Kafka backend. The Docker dashboard was checked against the actual backend through jsdom; its visual layout on the user's computer was not inspected. No mobile/accessibility audit, concurrent load, host reboot, crash-injection campaign, multi-replica correctness, Kubernetes/Azure deployment or optional MLflow exercise was performed. Passing replay after an API restart does not establish end-to-end exactly-once Kafka delivery. Upstream Starlette/AnyIO and SciPy solver-option warnings were observed; the checks and numeric reproduction passed.
