# Streaming recovery and delivery evidence

The previous worker exited when broker publication or polling failed. It now
retries transient broker, HTTP and SQLite availability errors with delays bounded
at five seconds. It never commits an input offset on an unconfirmed scoring/DLQ
operation. Draining pending outbox records precedes polling new work; prolonged
outages can therefore cause consumer-group rebalances and input replay.

`outbox_attempts` records intent before publication and confirms delivery in the
same SQL transaction that marks the event delivered. A crash after broker
acknowledgement and before that transaction leaves a `publishing` attempt and a
pending event. Retries retain the same `transaction_id` as the Kafka key.
Known publication failures are `unconfirmed`, never erased or called delivered.

Decision/history/outbox creation remains one existing SQLite transaction.
Input replay reuses its decision and does not advance account history twice.
The guarantee is at-least-once Kafka publication with durable decision
idempotency. Broker acknowledgement and SQL acknowledgement are not atomic.
Downstream consumers must deduplicate by event key; no exactly-once external
effect guarantee is made. Attempt history needs a deliberate production retention
policy and adds writes during outages; this stage does not purge failed evidence.

```bash
python -m pytest tests/test_stream.py tests/test_stream_recovery.py -q
```

The real-broker probe requires a disposable, task-owned Redpanda container with a
name beginning `sentinel-stage4-` and the exact label
`stage4.owner=portfolio-recovery-probe`. Its advertised broker address must be
loopback, for example `127.0.0.1:19092`. Do not use an existing project broker.
Create it from the repository's Redpanda v24.3.5 image, one CPU, 768 MiB container
limit and 512 MiB broker memory, exposing only the loopback Kafka port.

```bash
docker run -d --pull never --name sentinel-stage4-20261029 --label stage4.owner=portfolio-recovery-probe --cpus 1 --memory 768m -p 127.0.0.1:19092:19092 redpandadata/redpanda:v24.3.5 redpanda start --overprovisioned --smp 1 --memory 512M --reserve-memory 0M --node-id 0 --check=false --kafka-addr PLAINTEXT://0.0.0.0:19092 --advertise-kafka-addr PLAINTEXT://127.0.0.1:19092
# Wait for: docker exec sentinel-stage4-20261029 rpk cluster info -X brokers=127.0.0.1:19092
python -m scripts.stream_recovery_probe --bootstrap 127.0.0.1:19092 --container sentinel-stage4-20261029 --output reports/local/stage4-001
```

The bounded probe creates three topics on that disposable broker, restarts a real
consumer after injected loss before offset commit, pauses/unpauses the broker,
restarts the publisher and exposes the broker-ack/SQL-commit crash window. It
retains SQLite decisions, attempt records and duplicate output identities.
Scoring uses a deterministic synthetic adapter. The crash window is injected;
it is not an OS-killed worker or a trained-model experiment. Receive deadlines
are 30 seconds. Always remove only this task's disposable container and its
anonymous data volume after exporting evidence; leave existing services alone.

**VERIFIED:** local full suite 31 passed, including replay, retry, uncertain
delivery and event-identity checks; lint/format passed. The real Redpanda probe
also passed: one input offset replayed after consumer restart, one durable
account/decision/outbox row, retained `unconfirmed`, `publishing`, and `confirmed`
attempts, and two observed output records with one event key. The task-owned
broker and its anonymous volume were removed successfully. The first broker
probe failed before outage injection because a temporary Kafka admin client was
destroyed while topic futures were pending; retaining that client fixed the
driver. That failed trial and its broker teardown are retained separately.
Existing ownership and AI-assistance disclosures remain unchanged.
