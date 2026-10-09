# Sentinel — Real-Time Fraud Detection & Risk Decisioning

A runnable portfolio reference: synthetic transaction generation → shared streaming features → XGBoost + Isolation Forest risk score → APPROVE / REVIEW / BLOCK → durable audit ledger → feedback and monitoring → candidate retraining and guarded model promotion.

**Status:** implemented and tested locally. Synthetic data only by default. No claim of production readiness, a 35% false-positive reduction, real fraud capture, or guaranteed sub-100 ms latency. Docker and cloud deployment configurations are included; check `docs/VALIDATION.md` for what was actually exercised.

## Online demo and evidence

[Open the hosted browser demo](https://sentinel-fraud-demo-girish.amneal-9162.chatgpt.site) — **private; authorized access required**. It stays hosted independently of the local computer. This browser demo runs exported model inference and stores demo history locally in the browser. The full Python/Kafka platform below runs separately through Docker.

| Evidence | Recorded result | Scope |
|---|---|---|
| Correctness tests | 15 passed | Python API, features, model lifecycle and failure behavior |
| Actual broker integration | 100 transactions scored; decision output consumed | Local Docker Desktop, Redis and Redpanda |
| Model holdout | PR-AUC 0.7426; recall 0.6203; FPR 0.6463% | 2,400 synthetic chronological holdout events |
| Serial HTTP latency | p50 25.12 ms; p95 64.08 ms; p99 136.86 ms | 200 loopback requests, one client |
| Browser model parity | 200 cases within 0.00001 | Python versus JavaScript synthetic scores |

See [validation conditions](docs/VALIDATION.md), [architecture](docs/ARCHITECTURE.md), [interview guide](docs/INTERVIEW_GUIDE.md) and [career preparation](docs/CAREER_READINESS.md). GitHub Actions passed Python regression tests, Docker image build, Kafka streaming smoke checks and browser model parity on 2026-10-09. [View the successful CI run](https://github.com/Jill-Vekariya/sentinel-fraud-platform/actions/runs/37929026019).

## Start with Docker (recommended)

Install Docker Desktop with Compose v2 and allocate about 4 GB memory.

```bash
cp .env.example .env
docker compose up --build -d
docker compose logs -f trainer api worker
```

The one-shot trainer builds a model before the API starts. Open **http://localhost:8000** for the dashboard and **http://localhost:8000/docs** for the API explorer. Enter the API key from `.env`; the local demo default is `local-demo-change-me`.

Produce a Kafka stream:

```bash
docker compose run --rm --no-deps producer
```

Redpanda is a Kafka-compatible broker. The producer keys events by account ID; the consumer scores them through the API and publishes durable outbox results to `decisions`. The dashboard refreshes on demand. To inspect output:

```bash
docker compose exec broker rpk topic consume decisions -n 5
```

Stop with `docker compose down`. Add `-v` only when intentionally deleting all demo state. The producer uses the current epoch as its default seed, giving new IDs on later runs. An explicit reused seed produces reused IDs with changed timestamps and therefore conflicts; use a fresh seed for each new stream. The live producer stamps current UTC time so subsequent new streams respect account watermarks. Live simulation runs faster than the training event clock; interpret its drift and metrics as demo observations.

## Start with Python (no broker required)

Use Python 3.12. Windows users can activate `.venv\Scripts\activate`; macOS/Linux use the command below.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m fraud.train --promote
uvicorn fraud.api:app --host 127.0.0.1 --port 8000
```

In a second terminal, activate the same environment and run:

```bash
python -m scripts.demo --count 200
python -m pytest -q
```

The demo sends serial HTTP transactions and synthetic ground-truth feedback. It prints measured HTTP p50/p95/p99; it does not establish concurrent throughput. `models/` and `data/` are created locally. The downloadable package includes a pre-trained synthetic model. Git clones exclude generated Python model artifacts; run the training command first.

## Example request

```bash
curl http://localhost:8000/v1/score \
  -H 'X-API-Key: local-demo-change-me' \
  -H 'Content-Type: application/json' \
  -d '{"transaction_id":"example_1","account_id":"demo_1","timestamp":"2026-10-09T10:00:00Z","amount":850,"device_id":"device_1","country":"GB","home_country":"US"}'
```

Inputs use timezone-aware timestamps and a single currency assumption (USD). Do not mix currencies without upstream normalization. The response contains the blended risk score, supervised probability, anomaly percentile, decision, reason codes, model version, threshold and supervised Tree SHAP contributions. `risk_score` is a ranking score, **not a calibrated fraud probability**; the supervised probability is also uncalibrated on real data.

## What is implemented

| Component | Implementation |
|---|---|
| Features | 5-minute velocity/count and amount sum, 24-hour rolling amount ratio/device history, foreign flag, cyclical hour |
| Models | XGBoost classifier, Isolation Forest fitted on legitimate training rows |
| Decision policy | 95% classifier probability + 5% anomaly percentile; validation-selected BLOCK threshold; lower REVIEW threshold; transparent review rules |
| Explanations | Native XGBoost Tree SHAP, top positive supervised log-odds contributions |
| API | FastAPI, validation, API key, readiness, replay and conflict handling |
| Streaming | Kafka-compatible broker, account-keyed producer, manual offsets, malformed/late/conflicting-event DLQ |
| State | SQLite WAL ledger + account history + decision outbox in one transaction |
| Cache | Optional Redis decision-read mirror; cache outages do not change scoring correctness |
| Monitoring | Prometheus counters and full request histogram, PSI, feedback PR-AUC/precision/recall/FPR, dashboard |
| Model lifecycle | Immutable artifact versions, checksum, atomic pointer, validation gates, champion comparison, rollback |
| Retraining | Drift-triggered candidate CLI against supplied mature-label CSV; explicit promotion |
| Experiment tracking | Optional MLflow logging of params, metrics and artifacts |
| Delivery | Docker Compose, GitHub Actions tests/image build, single-replica Kubernetes reference, AKS guide |

**Intentionally excluded:** distributed feature-store architecture, automatic online canary traffic routing, Evidently integration, automatic scheduling of retraining, cloud provisioning and a managed Azure ML endpoint. The simpler implemented components are named accurately.

## Train using your own labelled dataset

CSV columns:

`transaction_id,account_id,timestamp,amount,device_id,country,home_country,is_fraud`

Use `is_fraud` equal to `0` or `1`; sort order is enforced by timestamp. Include only mature labels and a representative population of legitimate transactions. Review-only labels create selection bias.

```bash
python -m scripts.generate_csv --output data/labelled.csv --seed 51
python -m fraud.train --dataset data/labelled.csv
```

This retains a candidate without affecting the current model. Inspect `models/<version>/report.json`. To train and promote when gates pass:

```bash
python -m fraud.train --dataset data/labelled.csv --promote
python -m fraud.train --rollback
```

Promotion checks validation PR-AUC ≥ 0.15, recall ≥ 0.10, model BLOCK FPR ≤ 1%, and PR-AUC no more than 0.02 below the current champion on the same validation rows. These are **demo gates**, not business acceptance criteria. No threshold/gate uses the test holdout. A champion previously trained on the comparison data would invalidate that comparison; supply a fresh non-overlapping validation window for a defensible real release. Retraining and promotion commands must be single-writer operations.

Drift-triggered candidate training:

```bash
python -m fraud.retrain --dataset data/labelled.csv
```

No drift → no candidate. `--force` overrides the trigger. Schedule this command externally only after defining label-maturity and evaluation policy; it never promotes automatically.

## Optional MLflow

```bash
docker compose --profile tracking up -d mlflow
pip install mlflow==2.22.0
export MLFLOW_TRACKING_URI=http://localhost:5000
python -m fraud.train --dataset data/labelled.csv
```

Open http://localhost:5000. MLflow is an experiment log; the local immutable-artifact registry owns serving. MLflow is optional and its service is not tested in this environment.

## Repository guide

- `fraud/`: training, feature code, model lifecycle, scoring API, SQL state, streaming, monitoring and retraining
- `web/index.html`: operations dashboard with scoring, explanations and reviewer feedback
- `scripts/`: labelled CSV generator, serial HTTP benchmark/demo, browser model export and parity verification
- `hosted-demo/`: static browser inference demo, separate from the Docker backend
- `tests/`: correctness and API regression checks
- `deploy/`: Kubernetes reference manifest and Azure deployment guide
- `docs/ARCHITECTURE.md`: dataflow, design decisions, guarantees and tradeoffs
- `docs/RUNBOOK.md`: failure recovery, model rollback and monitoring interpretation
- `docs/INTERVIEW_GUIDE.md`: architecture explanation and honest resume wording
- `docs/VALIDATION.md`: measured validation and limitations

Technical references: [FastAPI lifespan tests](https://fastapi.tiangolo.com/advanced/testing-events/), [Confluent Python consumer](https://docs.confluent.io/kafka-clients/python/current/overview.html), [Redis transactions](https://redis.io/docs/latest/develop/using-commands/transactions/). Dependencies are pinned for this project, not asserted to be the latest versions.
