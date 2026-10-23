# Current status

Updated 2026-10-23 for the cleanup review. The public browser demo runs exported synthetic scoring and classifier explanations; its real-data cost explorer displays recorded offline results. Python/Docker provides the separate API, durable state, broker worker and optional Redis mirror.

## Reproduce

Use Python 3.12. On Linux x86_64, install `requirements-linux-py312.lock` with `--require-hashes`; other platforms retain the pinned direct requirements in `requirements.txt`. Install `requirements-dev.txt` for the Ruff lint/format tools. The Linux lock describes one supported environment, not all operating systems.

After `npm ci`, run `npm run test:hosted` for the DOM/model checks and `npm run test:dashboard` for a newly trained isolated local API and real dashboard requests. The latter requires the active Python environment. It uses temporary model/data directories, a random local key and an available loopback port, and shuts down its own server. `npm run test:dashboard:attached` targets an explicitly selected running API using `SENTINEL_TEST_URL` and `SENTINEL_TEST_API_KEY`.

New DOM reports go under ignored `reports/local/` paths and refuse to overwrite an existing output. `SENTINEL_TEST_OUTPUT` selects a new explicit output path. Benchmark reproduction also requires a new `--output`; published reports are preserved. `python scripts/check_links.py` checks local Markdown paths/anchors; add `--online` for external reachability.

## Remaining limits

The 95/5 risk score is not a calibrated fraud probability. Measured synthetic results, historical real-data metrics and assumed business costs have different scopes. The local demo key is publicly documented. Distributed state, automatic online canary routing, scheduled retraining, managed Azure endpoints and production readiness are not claimed. Existing Kubernetes/Azure files remain reference material.

Personal coding/review/reproduction must be recorded truthfully in [ownership](OWNERSHIP.md); study [the interview guide](INTERVIEW_GUIDE.md) and [career readiness](CAREER_READINESS.md).
