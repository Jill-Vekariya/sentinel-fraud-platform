"""Crash windows use real SQLite; broker failures use deterministic adapters."""

import json
from unittest.mock import Mock

import httpx
import pytest

from fraud.schema import Transaction
from fraud.store import Store
from fraud.worker import drain_outbox, process_message, run_loop


def setup(tmp_path):
    store = Store(tmp_path / "stream.db")
    tx = Transaction.model_validate(
        {
            "transaction_id": "replay-one",
            "account_id": "a",
            "timestamp": "2025-01-01T00:00:00Z",
            "amount": 10,
            "device_id": "d",
            "country": "US",
            "home_country": "US",
        }
    )
    manager = Mock()
    manager.score.return_value = {"decision": "APPROVE"}
    return store, tx, manager


def counts(store):
    with store.connect() as db:
        return [
            db.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            for t in ("decisions", "accounts", "outbox")
        ]


def test_replay_after_consumer_commit_failure_preserves_one_decision(tmp_path):
    store, tx, manager = setup(tmp_path)
    msg = Mock()
    msg.error.return_value = None
    msg.key.return_value = b"a"
    msg.value.return_value = json.dumps(tx.model_dump(mode="json")).encode()
    client = Mock()
    results = []

    def post(*args, **kwargs):
        result = store.score(Transaction.model_validate(kwargs["json"]), manager)
        results.append(result)
        return httpx.Response(200, json=result, request=httpx.Request("POST", "http://local"))

    client.post.side_effect = post
    consumer = Mock()
    consumer.commit.side_effect = RuntimeError("lost commit acknowledgement")
    with pytest.raises(RuntimeError):
        process_message(consumer, Mock(), client, msg)
    # New consumer, same delivery. The first durable decision is reused.
    process_message(Mock(), Mock(), client, msg)
    assert [r["replayed"] for r in results] == [False, True]
    assert counts(store) == [1, 1, 1]
    manager.score.assert_called_once()


def test_disconnect_and_restart_retain_attempts_and_event_identity(tmp_path):
    store, tx, manager = setup(tmp_path)
    store.score(tx, manager)
    producer = Mock()
    producer.flush.return_value = 1
    with pytest.raises(RuntimeError):
        drain_outbox(store, producer)
    assert len(store.pending()) == 1
    # Simulate a crash after broker acceptance but before SQL acknowledgement.
    store.begin_delivery(tx.transaction_id)
    restarted = Store(store.path)
    producer.flush.return_value = 0
    drain_outbox(restarted, producer)
    assert not restarted.pending()
    with store.connect() as db:
        attempts = db.execute(
            "SELECT event_id,status FROM outbox_attempts ORDER BY attempt_id"
        ).fetchall()
    assert [r["status"] for r in attempts] == ["unconfirmed", "publishing", "confirmed"]
    assert {r["event_id"] for r in attempts} == {tx.transaction_id}
    assert counts(store) == [1, 1, 1]


def test_worker_survives_disconnection_with_bounded_backoff():
    consumer, producer, client, store = Mock(), Mock(), Mock(), Mock()
    store.pending.return_value = []
    consumer.poll.side_effect = [RuntimeError("broker unavailable")] * 7 + [None]
    delays = []
    run_loop(
        consumer,
        producer,
        client,
        store,
        stopped=lambda: consumer.poll.call_count >= 8,
        wait=delays.append,
    )
    assert delays == [0.5, 1, 2, 4, 5, 5, 5]
    consumer.commit.assert_not_called()


def test_delivery_attempt_cannot_ack_another_event(tmp_path):
    store, tx, manager = setup(tmp_path)
    store.score(tx, manager)
    attempt = store.begin_delivery(tx.transaction_id)
    with pytest.raises(ValueError, match="identity/state"):
        store.finish_delivery(attempt, "other-event")
    assert len(store.pending()) == 1
