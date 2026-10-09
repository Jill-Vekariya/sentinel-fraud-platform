# Operations runbook

## Starting and checking

1. Start Compose; trainer must finish successfully before API readiness succeeds.
2. Inspect `docker compose ps` and `docker compose logs api worker trainer`.
3. GET `/health/live` checks process responsiveness; GET `/health/ready` checks model and SQL access.
4. Use the dashboard to score a transaction, inspect its model/reasons and submit known feedback.
5. Produce Kafka transactions; consume `decisions` to verify the outbox loop.

## Failure cases

| Symptom | Meaning and recovery |
|---|---|
| HTTP 401 | Send the configured X-API-Key; dashboard keys remain in browser memory only |
| HTTP 422 | Invalid input; correct schema/timezone/finite positive amount |
| HTTP 409, conflicting payload | ID already represents another transaction; investigate upstream reuse |
| HTTP 409, late event | Account watermark passed event time; offline replay into isolated state required |
| HTTP 503 | No decision confirmed; retry the identical ID/payload, investigate DB/model |
| Redis unavailable | Scoring stays durable; cached reads fall back to SQL |
| Kafka unavailable | Worker fails/restarts; uncommitted input and undelivered outbox are retried |
| Duplicate decision event | At-least-once output; deduplicate downstream by transaction ID |
| PSI alert | Investigate missing values, population changes, feature parity and label-backed performance |
| Retraining gate fails | Candidate is retained; active model is unchanged |
| Bad model release | Run rollback from the same mounted model directory; verify model endpoint |

## Model actions in Docker

Candidate from a labelled CSV mounted into the container:

```bash
docker compose run --rm -v "$PWD/data/labelled.csv:/tmp/labelled.csv:ro" trainer python -m fraud.train --dataset /tmp/labelled.csv
```

Inspect its report in the model volume. Append `--promote` only after evaluating a representative validation window and agreeing business criteria. Roll back with:

```bash
docker compose run --rm trainer python -m fraud.train --rollback
```

Only one training/promoting process should run at a time. The first release has no prior pointer; rollback requires a previous model version. Corrupt artifacts cause readiness/scoring failure, not silent fallback.

## Data and privacy

SQLite retains normalized inputs, model features, decisions, labels and event outbox. No automatic retention/deletion policy is enabled. Back up database and model volumes consistently; test restore before using important data. Never load arbitrary pickle files. The artifact checksum detects accidental corruption, not malicious artifacts (there is no signing infrastructure). The API key is a local demo credential, not user-level identity or authorization. Exposing public services requires TLS, managed secrets, access control, rate limiting and PII minimization.

## Release checklist

Use mature labels; freeze a data snapshot; validate feature parity; compare champion/challenger on a non-overlapping evaluation period; select thresholds against fraud cost and review capacity; evaluate customer segments; run concurrent load and crash/replay tests; keep a reversible artifact release. These actions are required to turn the portfolio reference into an operational payment system.
