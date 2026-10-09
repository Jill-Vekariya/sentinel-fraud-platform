# Validation record

Validated on 2026-10-09, Python 3.12.14, Linux x86_64, CPU inference. Training seed 42, 12,000 synthetic events, chronological 60/20/20 split. Reports are synthetic demonstrations, not production fraud results.

| Check | Result |
|---|---|
| Python regression suite | 15 passed; one upstream Starlette/AnyIO deprecation warning |
| Feature parity, 24h expiry and idempotency | Passed |
| Concurrent replay and failed-scoring atomicity | Passed |
| API authentication, validation, feedback and health | Passed |
| Model reload, rollback and artifact checksum | Passed |
| Kafka commit/DLQ/outbox failures using test doubles | Passed |
| Live FastAPI HTTP demo | 200 transactions and synthetic feedback accepted |
| Dashboard connection, scoring, decision list and feedback | Passed with jsdom; no JavaScript errors |
| JavaScript syntax | Passed via Node |
| Python compilation | Passed |
| Compose / CI / Kubernetes YAML parsing | Passed |
| Browser visual rendering | Not verified: Chromium download failed |
| Docker image and actual Kafka broker execution | Passed on connected Windows/WSL2 Docker Desktop; 100 streamed transactions scored and decision output consumed |
| Redis service integration | Passed: a scored decision was present in Redis |
| Kubernetes, Azure and optional MLflow | Not deployed/exercised |

## Measured HTTP latency

One sequential client, loopback transport, 200 synthetic transactions, existing synthetic account state:

- p50: 25.12 ms
- p95: 64.08 ms
- p99: 136.86 ms

These are measurements on this runtime only; there is no concurrent-load throughput or availability claim. The live stream uses current timestamps and runs faster than the training clock. Hardware/process contention can affect measurements.

## Synthetic holdout results

2,400 chronologically held-out events, model threshold 0.339396:

- PR-AUC: 0.7426
- Precision: 0.7656
- Recall: 0.6203
- False-positive rate: 0.6463%

The threshold was selected on validation, not this holdout. These metrics cover the model BLOCK threshold, not review rules/capacity. Synthetic patterns were intentionally learnable. No comparison supporting a real-world 35% reduction has been performed.

## Reproduce

```bash
pip install -r requirements.txt
python -m pytest -q
python -m fraud.train --promote
uvicorn fraud.api:app --host 127.0.0.1 --port 8000
# Second terminal:
python -m scripts.demo --count 200
# Optional dashboard DOM integration test, Node >=22.12; use a fresh test database:
npm install
npm run test:dashboard
```

GitHub Actions includes a streaming job that starts Compose, generates 20 Kafka events, checks their durable API decisions and consumes a decision event. That job passed on GitHub Actions on 2026-10-09, along with the Python tests, Docker image build and browser model export/parity check. [CI evidence](https://github.com/Jill-Vekariya/sentinel-fraud-platform/actions/runs/37929026019) covers source commit f887961.

## Connected-computer verification

On 2026-10-09 the project was installed on the authorized Windows computer using Docker Desktop. Readiness, durable replay, feedback, Redis decision caching, all 15 regression tests, 100 Kafka inputs, API scoring and Kafka decision output passed. A repeated topic-init bug was fixed with idempotent topic checks. Model bootstrap now retains an existing active model, and producer instructions use `--no-deps` after the stack starts. Desktop launch/demo shortcuts were created. Visual browser rendering remains unverified.

## Portfolio browser export

The GitHub package includes the hosted browser source and reproducible Python model export. `python -m scripts.check_browser_parity` checks 200 deterministic synthetic feature cases and compares decisions plus classifier, anomaly and blended scores. The recorded maximum score difference is 0.000000571, below tolerance 0.00001. This checks inference parity; it does not establish production model validity. The hosted deployment remains private as requested.
