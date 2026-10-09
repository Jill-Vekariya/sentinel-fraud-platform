# Final checklist: reproduced from a clean checkout

Executed on 2026-10-09 against source commit `14c4a3fb64e0281e27d94e62db0eab268423ed37`. [Machine-readable record](final-checklist.json); [full repeated load/security report](final-checklist-load-security.json). The verification cloned the public repository into a new directory and used a distinct Compose project with new volumes. No existing `.env`, model or database was present before startup. The API published no host port in this isolated run.

| Checklist item | Result and scope |
|---|---|
| Clean checkout | Passed clone, tracked example environment, image build, new synthetic model training and complete Compose startup |
| Automated tests | All 18 Python tests passed in the clean image; the browser interaction check also covers displayed-input consistency after the later UI fix |
| Real benchmark | All 284,807 rows and five approaches rerun; 17,147 numeric comparisons passed at 1e-8 tolerance |
| Complete Docker pipeline | Standard producer generated 20 events; all 20 decisions appeared. A separate live audit verified another 20 inputs and all 20 corresponding output IDs, SQL/outbox records, Redis mirror, feedback, monitoring and late-event DLQ |
| API security and replay | All 27 selected checks passed; 20 concurrent identical requests produced one decision and one outbox row. Actual API restart preserved the original decision and score |
| Tracked-file exposure review | No tracked `.env`, `data/` or `models/`; no selected private-key/provider-token signatures found in 83 tracked files. Public demo keys are examples; no complete secret-history or vulnerability audit is claimed |
| Demonstration | [Actual public dashboard walkthrough](sentinel-dashboard-demo.mp4), plus [captured Docker API walkthrough](sentinel-demo.mp4), each with separate provenance and limitations |
| README and interview material | Prominent real video/live/source links; setup and measured evidence; [architecture diagram](ARCHITECTURE.md) and [ten implementation-specific answers](INTERVIEW_GUIDE.md) |

## Leakage review and chronological boundaries

The real benchmark stably sorts `Time` and moves each split boundary to the beginning of its timestamp group. The fresh report confirms strict separation:

| Split | Rows | Frauds | Minimum Time | Maximum Time |
|---|---:|---:|---:|---:|
| Train | 170,882 | 360 | 0 | 120,395 |
| Validation | 56,963 | 57 | 120,396 | 145,247 |
| Holdout | 56,962 | 75 | 145,248 | 172,792 |

Code review confirmed that model fit and logistic-regression scaling use training rows only, Isolation Forest uses legitimate training rows, and its percentile reference is derived from those training rows. Thresholds and browser scenario choices use validation outcomes; fixed holdout metrics report the resulting decisions. No label or fabricated account feature enters the benchmark inputs. The benchmark's supplied PCA transformation has unknown upstream fitting provenance, so upstream leakage cannot be ruled out.

The excluded raw CSV was supplied explicitly as the benchmark input, with SHA-256 `76274b691b16a6c49d3f159c883398e03ccd6d1ee12d9d8ee38f4b4b98551a89` checked before copying it into the isolated container. It was not used to bootstrap the synthetic serving model, copied into the Git checkout or committed. Software versions matched the published report; the maximum numeric difference was 6.776263578034403e-21. The full aggregate reproduction remains outside Git to avoid duplicating the existing report.

## Repeated bounded load

Again, 100 requests per stage at 1, 5 and 10 clients all returned HTTP 200. The new p95 values were 64.24, 887.02 and 1,269.14 ms. The original run's 10-client p95 was 987.48 ms. Both remain recorded in [LOAD_SECURITY.md](LOAD_SECURITY.md); these short shared-runtime measurements do not establish a latency or capacity SLA.

## Reproduce without reusing demo state

Clone into a new directory and choose a new Compose project name:

```bash
git clone https://github.com/Jill-Vekariya/sentinel-fraud-platform.git sentinel-check
cd sentinel-check
cp .env.example .env
```

In that new directory, save the following as `compose-audit.yaml`. It removes the API host-port mapping so this test stack can run alongside an existing installation:

```yaml
# compose-audit.yaml; Compose must support !reset
services:
  api:
    ports: !reset []
```

```bash
docker compose -p sentinel-check -f compose.yaml -f compose-audit.yaml up --build -d
docker compose -p sentinel-check -f compose.yaml -f compose-audit.yaml run --rm --no-deps -e REDIS_URL= api python -m pytest -q
docker compose -p sentinel-check -f compose.yaml -f compose-audit.yaml run --rm --no-deps producer python -m fraud.produce --seed 99 --count 20 --delay 0.02
docker compose -p sentinel-check -f compose.yaml -f compose-audit.yaml exec -T api python -m scripts.check_stream
docker compose -p sentinel-check -f compose.yaml -f compose-audit.yaml exec -T api python -m scripts.verify_live
docker compose -p sentinel-check -f compose.yaml -f compose-audit.yaml restart api
docker compose -p sentinel-check -f compose.yaml -f compose-audit.yaml exec -T api python -m scripts.verify_restart
```

Use the [benchmark protocol](REAL_BENCHMARK.md) for the separately downloaded CSV and [isolated load commands](LOAD_SECURITY.md) for the second audit container; add the same project/override flags to its Compose commands. When finished, remove only this disposable test stack with `docker compose -p sentinel-check -f compose.yaml -f compose-audit.yaml down -v`. Keep your main demo's project and volumes separate. The actual verification used these steps with a distinct project name and removed its own test containers/volumes afterward.

The subsequent dashboard fix only synchronizes the form with the displayed transaction when selecting examples, simulation results or a previous decision. It changes no training, scoring, threshold or backend persistence code. Its interaction regression checks are included in the [CI workflow](https://github.com/Jill-Vekariya/sentinel-fraud-platform/actions/workflows/ci.yml).

Feature development remains frozen. A portfolio demonstration and a review of selected security cases do not certify a production banking service; [release limitations](RELEASE_FREEZE.md) remain applicable. Practising and explaining the project is the student's remaining preparation task.
