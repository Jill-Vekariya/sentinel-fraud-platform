import json
from unittest.mock import Mock

import httpx
import pytest

from fraud.worker import publish, run_loop


def test_empty_producer_queue_is_not_a_delivery_acknowledgement():
    producer = Mock()
    producer.flush.return_value = 0
    # A missing callback must leave delivery uncertain, even with no queued work.
    with pytest.raises(RuntimeError, match="unconfirmed"):
        publish(producer, "decisions", "event", {"decision": "APPROVE"})


def test_failed_input_is_retried_before_polling_and_committing_later_offset(monkeypatch):
    monkeypatch.setattr("fraud.worker.time.sleep", lambda _: None)
    consumer, producer, client, store = Mock(), Mock(), Mock(), Mock()
    store.pending.return_value = []
    messages = []
    for offset in (5, 6):
        msg = Mock()
        msg.error.return_value = None
        msg.key.return_value = b"a"
        msg.offset.return_value = offset
        msg.value.return_value = json.dumps(
            {
                "transaction_id": "event-" + str(offset),
                "account_id": "a",
                "timestamp": "2025-01-01T00:00:00Z",
                "amount": 100,
                "device_id": "d",
                "country": "US",
                "home_country": "US",
            }
        ).encode()
        messages.append(msg)
    consumer.poll.side_effect = messages
    attempts, commits = [], []

    def post(path, *, json):
        attempts.append(json["transaction_id"])
        if json["transaction_id"] == "event-5" and attempts.count("event-5") <= 3:
            raise httpx.ConnectError("temporary scoring outage")
        return httpx.Response(200, json={}, request=httpx.Request("POST", "http://fixture"))

    client.post.side_effect = post
    consumer.commit.side_effect = lambda *, message, asynchronous: commits.append(message.offset())
    waits = []
    run_loop(
        consumer,
        producer,
        client,
        store,
        stopped=lambda: 6 in commits,
        wait=waits.append,
    )
    assert attempts == ["event-5"] * 4 + ["event-6"]
    assert commits == [5, 6]
    assert consumer.poll.call_count == 2
    assert waits == [0.5]
