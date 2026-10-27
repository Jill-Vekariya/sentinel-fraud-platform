# Synthetic API deployment review

Status: **prepared locally; public deployment not authorized or claimed**.

## Choice

Use Sentinel's single-process HTTP scoring API for this stage. It provides a browser dashboard, model explanations, idempotent durable decisions, feedback and monitoring with fewer runtime dependencies than Atlas. The deployed demo deliberately excludes the Kafka worker, broker, Redis mirror and MLflow server. Its SQLite ledger/outbox is local and temporary; this deployment does not prove streaming delivery or preserve transactions across restarts.

A same-host native observation with one BLAS/OpenMP thread measured peak RSS of 189,224 KiB for Sentinel and 254,812 KiB for Atlas. Installed environment files totaled 446,117,773 and 1,826,871,058 bytes respectively. Readiness was about 1.63 seconds for each. These are observations with different application workloads, not matched benchmarks or container capacity guarantees. Both applications retain useful demonstrations; Sentinel is selected for the smaller dependency and service footprint.

## Exact source and image

`deploy/image-source.json` records the reviewed base commit and SHA-256 of every Docker input. The input fingerprint covers the pinned base reference, lockfile, API, model/feature/storage modules, dashboard, server entry point and HTTP verifier. It is a review artifact, not a newly published Git revision. The image contains the same manifest at `/app/image-source.json`.

After intentionally changing any input, inspect the changes and run:

```sh
python scripts/freeze_demo_source.py --write
python scripts/freeze_demo_source.py
```

The first command refreshes the review fingerprint; it is not a substitute for rerunning affected checks. A future publication must record the resulting actual Git commit and deployed image ID/digest separately. Building again may produce a different image because model version identifiers use build time and OS packages are not snapshot-pinned. Keep the verified image digest rather than claiming bit-for-bit rebuilds.

## Build and bounded local verification

Requires Docker with Linux amd64 support and access to Docker Hub, Debian mirrors and PyPI. Run from a fresh checkout with the reviewed patches applied:

```sh
python scripts/freeze_demo_source.py
python -m ruff check fraud scripts tests
python -m ruff format --check fraud scripts tests
python -m pytest -q

docker build --platform linux/amd64 -f Dockerfile.demo -t sentinel-demo:review .
python scripts/check_demo_container.py --image sentinel-demo:review --output reports/local/demo-review-001.json
```

Use a fresh report name on every attempt. Container verification creates a uniquely named owned container, a random private key and an automatically allocated loopback port. It checks UID 10001, read-only root, source-manifest agreement, a 512 MiB RAM cap, 0.5 CPU cap, 128 PID limit, dropped capabilities, no privilege escalation and a 64 MiB writable tmpfs. It terminates only its own container and does not prune images, delete volumes or alter existing services. The CPU cap is a local test setting, not a claim about Render Free's fractional CPU entitlement.

Docker may allocate a different random host port after restart. The verifier resolves the current mapping again, records both endpoints and then checks readiness and ephemeral-ledger loss. Three synthetic regression cases cover stable mapping, changed mapping and an unhealthy restarted server; these unit fixtures are not live container measurements. The initial failed CI run remains available at https://github.com/Jill-Vekariya/sentinel-fraud-platform/actions/runs/40516215959.

The reviewed Docker-input files use LF through `.gitattributes`, including on Windows. A pre-existing CRLF checkout can legitimately fail the byte fingerprint; use a fresh checkout or canonical Git archive rather than refreshing the manifest merely to conceal line-ending conversion. Source hashes remain byte checks, not a claim of bit-for-bit identical image builds.

The image trains a fixed 12,000-row, seed-42 synthetic model at build time. Trusted model artifacts are baked into the image; startup does not train, download weights, connect to Kafka/Redis or call an external model provider. No API key is baked into the image.

The HTTP protocol performs functional checks, five warm-up scoring requests and up to 200 measured scoring requests at concurrency 2. It stops scheduling after 20 seconds, the first timeout, or five non-200 load responses. Each request has a five-second timeout. Reports separate setup requests from the measured load, preserve errors/timeouts, and report p50/p95/p99. They do not establish production throughput or real-world fraud accuracy. The container check then restarts its owned instance and checks readiness and loss of temporary ledger data.

## Production start and exposure

The Docker command is `python -m scripts.serve_demo`: one Uvicorn worker, `0.0.0.0:$PORT`, maximum configured concurrency 16, five-second keep-alive, proxy header trust disabled and access logs replaced by bounded application telemetry. `FRAUD_ENV=production` and a private, non-demo `API_KEY` of at least 24 characters are required. `PORT` defaults to 10000. Local native verification of this exact entry point passed; container-specific results must be read separately.

Public pages are the synthetic dashboard, API documentation and live/readiness checks. Scoring, decisions, feedback, model metadata, monitoring and Prometheus metrics require `X-API-Key`. Keep the key private; an authenticated dashboard user may read all decisions in this single-tenant demo. Do not distribute a shared key to unrestricted visitors. HTTPS is supplied by the host, not the application process.

Enter synthetic transaction/account/device identifiers only. Authorized requests, features, scores, decisions and feedback are stored in temporary SQLite files. Those files and the outbox are lost on restart, redeploy or free-service spin-down. There is no external transaction queue in this mode. Logs include request ID, method, route template, status and application duration; request bodies, query strings and API keys are excluded. The 65,536-byte body limit precedes JSON parsing. Metrics cover authentication/validation failures and oversize requests as well as successful handlers; they exclude network/proxy time.

## Proposed Render service — review required

`deploy/render-demo.yaml` proposes one new service named `sentinel-synthetic-demo`, Docker runtime, **Free** compute, Singapore region, one instance, manual deploys and `/health/ready` health checks. No database, disk, Redis service, background worker, autoscaling or paid plan is requested. The API key is generated by the provider. A free service's filesystem does not offer durable persistence; do not present this as a production fraud service.

Official sources checked 25 October 2026:

- [Pricing](https://render.com/pricing): Free web compute is advertised at $0/month with 512 MB RAM and fractional CPU. Workspace and usage charges are separate considerations.
- [Free service limits](https://render.com/docs/free): 750 shared free instance hours/workspace/month; idle spin-down after 15 minutes; cold wake-up about one minute; temporary files lost on restart/redeploy/spin-down. Bandwidth and build pipeline allowances also apply. Exceeding allowances can suspend services or cause supplementary charges depending on payment-method and spend-limit settings. A Free label is not a blanket $0 billing guarantee.
- [Blueprint reference](https://render.com/docs/blueprint-spec): manual deployment uses `autoDeployTrigger: "off"` and explicit `plan: free` avoids an unintended paid default.

An earlier Atlas attempt on this account received HTTP 402 and a payment-information requirement. That historical failure remains unresolved; account eligibility and current billing settings have not been revalidated. Do not add payment details, accept a paid upgrade, change existing workspace plans or create a service without the required authorization. No public URL or current hosted backend success is claimed.

Before an authorized public attempt: publish only the reviewed Sentinel patch at a recorded Git commit; verify account eligibility, workspace allowances and billing controls; confirm resource limits and synthetic-only data exposure; deploy that exact commit/image once; record provider deployment ID and image digest; run the same bounded protocol against the actual HTTPS endpoint after readiness, with its separately recorded permission. Stop on a payment/upgrade requirement. Public traffic can consume bandwidth and free hours even when only synthetic data is used.

## Rollback and teardown

Retain the previous verified image digest, source receipt and synthetic model report before replacement. Roll back only to a verified prior deployment; Render Free documents retention of only the two most recent previous deploys. Verify readiness and scoring after rollback. SQLite data is not recovered by an image rollback; export only synthetic records explicitly intended for retention beforehand. A first deployment has no prior production revision to restore.

For the local verifier, owned containers are removed automatically; keep its image and reports for review. For an authorized cloud service, disable auto-deploys (already off), stop/suspend or delete only the newly created service by its recorded provider ID, revoke its API key, and verify its endpoint is unavailable. Do not delete unrelated services or repositories. No persistent disks/databases are proposed, so teardown has no such resources to remove.
