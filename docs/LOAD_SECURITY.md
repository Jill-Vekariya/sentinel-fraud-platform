# Bounded load and basic security record

Executed on 2026-10-09 after rebuilding the Docker image with the final API fixes. Raw measurements and captured demonstration responses are in [load-security.json](load-security.json). All traffic used generated synthetic data and an isolated audit database.

## Workload and measurements

One API container, CPU model scoring, SQLite WAL, no Redis or Kafka in this particular workload. The client ran inside that container over loopback. Python 3.12.15; Linux x86_64 on Docker Desktop/WSL2; 12 CPUs visible to the process, without a dedicated CPU allocation. Other processes shared the computer.

Each stage sent 100 new transactions with unique accounts. A semaphore limited outstanding requests to 1, 5 or 10. Latency is measured from immediately before the HTTP call until receipt of its response; time waiting for the semaphore is excluded. Requests include database persistence. This is a closed-loop workload: slower responses reduce the offered request rate.

| Concurrent clients | HTTP 200 / requests | Duration, s | Achieved requests/s | p50, ms | p95, ms | p99, ms |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 100 / 100 | 2.63 | 37.99 | 23.51 | 41.61 | 46.79 |
| 5 | 100 / 100 | 2.46 | 40.59 | 50.98 | 486.10 | 780.52 |
| 10 | 100 / 100 | 2.82 | 35.46 | 71.25 | 987.48 | 1,649.87 |

All 300 requests succeeded and returned the correct new transaction ID without a replay marker. A separate 20-request concurrent retry of the same payload returned one new decision and 19 identical replays, with exactly one decision row and one outbox row.

## Repeat from a clean checkout

A second run used a fresh Git clone, new Compose model/data volumes and a separately isolated audit API. All 300 new requests, 20 concurrent retries and 27 security checks passed again. [Full second report](final-checklist-load-security.json); [checkout conditions](FINAL_CHECKLIST.md).

| Concurrent clients | HTTP 200 / requests | Achieved requests/s | p50, ms | p95, ms | p99, ms |
|---:|---:|---:|---:|---:|---:|
| 1 | 100 / 100 | 23.57 | 40.13 | 64.24 | 73.43 |
| 5 | 100 / 100 | 24.97 | 82.85 | 887.02 | 1,795.67 |
| 10 | 100 / 100 | 35.51 | 59.53 | 1,269.14 | 2,709.34 |

The earlier measurements remain above with their original conditions. Runtime contention and short samples cause variation; neither run is a guaranteed performance target.

These short samples are not a steady-state capacity, soak or availability test. They do not include network distance, Kafka lag, a Redis outage, realistic repeated-account skew or growing production history. The p95 increase under concurrency is consistent with the deliberate single SQLite writer and serialized model scoring; the project makes no guaranteed sub-100 ms claim. Broker/Redis integration was checked separately in [FINAL_VERIFICATION.md](FINAL_VERIFICATION.md).

## Security results and fixes

All 27 basic checks passed:

- Missing and incorrect keys returned 401 on seven protected endpoints, including metrics (14 checks).
- An invalid non-ASCII key returned 401.
- Negative/excessive amounts, naive timestamps, SQL-like transaction IDs, HTML device IDs, an overflowing JSON number and malformed JSON returned 422 (seven checks).
- SQL-like lookup and encoded path traversal returned 404; a changed payload for an existing transaction returned 409 (three checks).
- An untrusted origin received no CORS permission, and the rejected requests added no decision rows (two checks).

The first audit exposed two reproducible server errors. The API key comparison rejected non-ASCII strings with a Python exception; it now compares UTF-8 bytes in constant time. A valid JSON number such as `1e999` overflowed to infinity, and the default validation response could not serialize that invalid value; a custom handler now returns only the error location, message and type. Both cases have a regression test in the complete 18-test suite. The full live integration and restart checks also passed after the fixes.

These checks cover selected failure cases. They are not a comprehensive penetration test, dependency vulnerability assessment or proof against all SQL injection, XSS or file traversal variants. The local API uses one shared key rather than per-user roles; application rate limits, request-size limits and an internet-facing TLS/authentication deployment have not been validated. Compose binds the API to loopback. Replace the documented demo key before any network exposure and define a deployment threat model before treating this as a real service.

## Reproduce in an isolated container

Start the normal stack first so a trained model exists. Use the current image and a fresh `/tmp` database; do not point this helper at the primary demo database. The helper reads the same database as the API to verify durable row counts.

```bash
docker compose up --build -d
docker compose run --rm --no-deps -d --name sentinel-load-audit \
  -e DATA_DIR=/tmp/sentinel-audit -e REDIS_URL= \
  -e API_KEY=verification-demo-only api
docker exec sentinel-load-audit python -m scripts.check_load_security \
  --count 100 --output /tmp/load-security.json
docker cp sentinel-load-audit:/tmp/load-security.json docs/load-security.json
docker stop sentinel-load-audit
```

The helper waits for readiness, prints each stage, writes its report and exits nonzero on failed checks. Stop the audit container even if a check fails; `--rm` removes this isolated container. It does not publish a host port or delete the primary model/data volumes. A fresh run generates new audit IDs and its own timing values. The two scored demonstration events are captured at the end of the report.
