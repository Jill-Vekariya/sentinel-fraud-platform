"""At-least-once Kafka input/output backed by durable SQL decision idempotency."""

import os
import json
import time
import logging
import sqlite3
import httpx
from confluent_kafka import Consumer, Producer, KafkaException
from .config import API_KEY, DATA
from .store import Store
from .schema import Transaction
from pydantic import ValidationError

log = logging.getLogger(__name__)


def publish(producer, topic, key, payload):
    errors = []
    producer.produce(
        topic,
        key=key,
        value=json.dumps(payload),
        on_delivery=lambda err, msg: errors.append(err) if err else None,
    )
    remaining = producer.flush(10)
    if remaining or errors:
        raise RuntimeError("Kafka delivery unconfirmed; retry without committing offset")


def drain_outbox(store, producer):
    for row in store.pending():
        attempt = store.begin_delivery(row["id"])
        try:
            publish(producer, "decisions", row["id"], json.loads(row["payload"]))
        except (RuntimeError, KafkaException, BufferError) as exc:
            store.finish_delivery(attempt, row["id"], type(exc).__name__)
            raise
        # Broker acknowledgement and SQL commit cannot be atomic. A crash here
        # permits another publication with the same event key after restart.
        store.finish_delivery(attempt, row["id"])


def process_message(consumer, producer, client, msg):
    if msg.error():
        raise RuntimeError(msg.error())
    try:
        body = json.loads(msg.value())
        tx = Transaction.model_validate(body)
        if msg.key() != tx.account_id.encode():
            raise ValueError("Kafka key must equal account_id")
    except (ValueError, TypeError, ValidationError):
        publish(
            producer,
            "transactions.dlq",
            str(msg.offset()),
            {
                "reason": "invalid schema/key",
                "topic": msg.topic(),
                "partition": msg.partition(),
                "offset": msg.offset(),
            },
        )
        consumer.commit(message=msg, asynchronous=False)
        return
    for attempt in range(3):
        try:
            response = client.post("/v1/score", json=body)
            if response.status_code == 409:
                publish(
                    producer,
                    "transactions.dlq",
                    tx.transaction_id,
                    {
                        "reason": response.json(),
                        "transaction_id": tx.transaction_id,
                        "partition": msg.partition(),
                        "offset": msg.offset(),
                    },
                )
                break
            response.raise_for_status()
            break
        except (httpx.HTTPError, RuntimeError):
            if attempt == 2:
                raise
            time.sleep(0.5 * (attempt + 1))
    consumer.commit(message=msg, asynchronous=False)


def run_loop(consumer, producer, client, store, *, stopped=lambda: False, wait=time.sleep):
    failures = 0
    while not stopped():
        try:
            drain_outbox(store, producer)
            msg = consumer.poll(1)
            if msg is not None:
                process_message(consumer, producer, client, msg)
            failures = 0
        except (
            KafkaException,
            BufferError,
            RuntimeError,
            httpx.HTTPError,
            sqlite3.OperationalError,
        ) as exc:
            failures += 1
            delay = min(5.0, 0.5 * 2 ** min(failures - 1, 4))
            log.warning(
                "stream_retry error_type=%s failures=%s delay_seconds=%s",
                type(exc).__name__,
                failures,
                delay,
            )
            wait(delay)


def main():
    logging.basicConfig(level=logging.INFO)
    bootstrap = os.getenv("KAFKA_BOOTSTRAP", "localhost:9092")
    consumer = Consumer(
        {
            "bootstrap.servers": bootstrap,
            "group.id": "fraud-scorer-v1",
            "enable.auto.commit": False,
            "enable.auto.offset.store": False,
            "auto.offset.reset": "earliest",
        }
    )
    producer = Producer({"bootstrap.servers": bootstrap, "enable.idempotence": True})
    consumer.subscribe(["transactions"])
    store = Store(DATA / "fraud.db")
    try:
        with httpx.Client(
            base_url=os.getenv("API_URL", "http://localhost:8000"),
            headers={"X-API-Key": API_KEY},
            timeout=10,
            trust_env=False,
        ) as client:
            run_loop(consumer, producer, client, store)
    finally:
        consumer.close()


if __name__ == "__main__":
    main()
