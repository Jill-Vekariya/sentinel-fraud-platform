"""Bounded real-broker probe against a disposable, explicitly named local container.

Scoring uses a deterministic adapter and real SQLite. No live model or payments.
The broker must be owned by this probe; existing project brokers are refused.
"""

import argparse
import json
import subprocess
import time
from pathlib import Path
from uuid import uuid4

import httpx
from confluent_kafka import Consumer, Producer
from confluent_kafka.admin import AdminClient, NewTopic

from fraud.schema import Transaction
from fraud.store import Store
from fraud.worker import drain_outbox, process_message, publish


class Manager:
    def load(self):
        pass

    def score(self, features):
        return {"decision": "APPROVE", "adapter": "synthetic"}


class Client:
    def __init__(self, store):
        self.store, self.results = store, []

    def post(self, path, *, json):
        result = self.store.score(Transaction.model_validate(json), Manager())
        self.results.append(result)
        return httpx.Response(200, json=result, request=httpx.Request("POST", "http://fixture"))


def receive(consumer, count=1):
    rows, deadline = [], time.monotonic() + 30
    while len(rows) < count and time.monotonic() < deadline:
        msg = consumer.poll(0.5)
        if msg is not None:
            if msg.error():
                raise RuntimeError(str(msg.error()))
            rows.append(msg)
    if len(rows) != count:
        raise RuntimeError("Bounded broker receive timed out")
    return rows


def run(bootstrap, container, folder):
    if not container.startswith("sentinel-stage4-") or not bootstrap.startswith("127.0.0.1:"):
        raise ValueError("Only a task-owned loopback broker is permitted")
    inspection = subprocess.run(
        ["docker", "inspect", container], check=True, capture_output=True, text=True, timeout=15
    )
    labels = json.loads(inspection.stdout)[0]["Config"].get("Labels") or {}
    if labels.get("stage4.owner") != "portfolio-recovery-probe":
        raise ValueError("Disposable broker ownership label required before fault injection")
    folder.mkdir(parents=True, exist_ok=False)
    cfg = {"bootstrap.servers": bootstrap, "enable.idempotence": True, "message.timeout.ms": 1500}
    # Keep the client alive until its asynchronous topic futures complete.
    admin = AdminClient({"bootstrap.servers": bootstrap})
    for result in admin.create_topics(
        [NewTopic(t, 1, 1) for t in ("transactions", "decisions", "transactions.dlq")],
        request_timeout=10,
    ).values():
        result.result(timeout=15)
    group = "stage4-" + uuid4().hex

    def consumer(topics, suffix=""):
        c = Consumer(
            {
                "bootstrap.servers": bootstrap,
                "group.id": group + suffix,
                "auto.offset.reset": "earliest",
                "enable.auto.commit": False,
                "enable.auto.offset.store": False,
            }
        )
        c.subscribe(topics)
        return c

    store = Store(folder / "probe.sqlite")
    client = Client(store)
    tx = {
        "transaction_id": "stage4-one",
        "account_id": "a",
        "timestamp": "2025-01-01T00:00:00Z",
        "amount": 10,
        "device_id": "d",
        "country": "US",
        "home_country": "US",
    }
    producer = Producer(cfg)
    publish(producer, "transactions", "a", tx)
    c = consumer(["transactions"])
    first = receive(c)[0]

    class LostConsumer:
        def commit(self, **kwargs):
            raise RuntimeError("injected consumer loss after durable scoring before offset commit")

    try:
        process_message(LostConsumer(), producer, client, first)
        raise AssertionError("Failure injection did not occur")
    except RuntimeError as exc:
        if not str(exc).startswith("injected consumer loss"):
            raise
    finally:
        c.close()
    c = consumer(["transactions"])
    try:
        replay = receive(c)[0]
        assert (first.topic(), first.partition(), first.offset()) == (
            replay.topic(),
            replay.partition(),
            replay.offset(),
        )
        process_message(c, producer, client, replay)
    finally:
        c.close()
    paused = False
    try:
        subprocess.run(["docker", "pause", container], check=True, capture_output=True, timeout=15)
        paused = True
        try:
            drain_outbox(store, producer)
            raise AssertionError("Paused broker unexpectedly confirmed delivery")
        except RuntimeError:
            assert len(store.pending()) == 1
    finally:
        if paused:
            subprocess.run(
                ["docker", "unpause", container], check=True, capture_output=True, timeout=15
            )
    # Restart publisher; the first acknowledgement is deliberately not recorded
    # to exercise the broker-ack/SQL-commit crash window.
    producer = Producer(cfg)
    store.begin_delivery(tx["transaction_id"])
    publish(producer, "decisions", tx["transaction_id"], client.results[0])
    restarted = Store(store.path)
    drain_outbox(restarted, producer)
    c = consumer(["decisions"], "-outputs")
    try:
        outputs = receive(c, 2)
    finally:
        c.close()
    with store.connect() as db:
        counts = {
            t: db.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            for t in ("accounts", "decisions", "outbox")
        }
        attempts = [
            dict(r) for r in db.execute("SELECT * FROM outbox_attempts ORDER BY attempt_id")
        ]
    assert counts == {"accounts": 1, "decisions": 1, "outbox": 1}
    assert [r["replayed"] for r in client.results] == [False, True]
    assert all(m.key() == b"stage4-one" for m in outputs)
    assert not store.pending()
    result = {
        "label": "VERIFIED",
        "mode": "real broker; synthetic scoring adapter",
        "input_identity": [first.topic(), first.partition(), first.offset()],
        "counts": counts,
        "replayed": [r["replayed"] for r in client.results],
        "attempts": attempts,
        "observed_output_messages": len(outputs),
        "distinct_output_event_keys": len({m.key() for m in outputs}),
        "guarantee": "At-least-once publication; durable decision idempotency. "
        "Consumers must deduplicate decision events by Kafka key.",
        "limits": "One partition, one account, one transaction; injected crash window, "
        "not a killed OS process. No throughput or production claim.",
    }
    (folder / "result.json").write_text(json.dumps(result, indent=2))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bootstrap", required=True)
    parser.add_argument("--container", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.bootstrap, args.container, args.output), indent=2))


if __name__ == "__main__":
    main()
