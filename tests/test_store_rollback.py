import json
import sqlite3
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

import pytest

from fraud.schema import Transaction
from fraud.store import Store


TABLES = ("decisions", "accounts", "outbox")


def transaction(tid, seconds=0):
    return Transaction(
        transaction_id=tid,
        account_id="account-one",
        timestamp=datetime(2025, 1, 1, tzinfo=timezone.utc) + timedelta(seconds=seconds),
        amount=100,
        device_id="device-one",
        country="US",
        home_country="US",
    )


def snapshot(store):
    with store.connect() as db:
        return {
            table: [dict(row) for row in db.execute(f"SELECT * FROM {table} ORDER BY id")]
            for table in TABLES
        }


@pytest.mark.parametrize("table", TABLES)
@pytest.mark.parametrize("existing_account", [False, True])
def test_database_write_failure_rolls_back_and_retry_is_idempotent(
    tmp_path, table, existing_account
):
    store = Store(tmp_path / "fraud.db")
    manager = Mock()
    manager.score.side_effect = lambda features: {
        "decision": "APPROVE",
        "model_version": "test-version",
    }
    if existing_account:
        store.score(transaction("seed"), manager)
    before = snapshot(store)
    candidate = transaction("candidate", seconds=60)
    with store.connect() as db:
        db.execute(
            f"CREATE TRIGGER reject_write BEFORE INSERT ON {table} "
            "BEGIN SELECT RAISE(ABORT, 'injected database write failure'); END"
        )

    with pytest.raises(sqlite3.IntegrityError, match="injected database write failure"):
        store.score(candidate, manager)

    restarted = Store(store.path)
    assert snapshot(restarted) == before
    with restarted.connect() as db:
        db.execute("DROP TRIGGER reject_write")

    result = restarted.score(candidate, manager)
    assert result["replayed"] is False
    calls = manager.score.call_count
    replay = restarted.score(candidate, manager)
    assert replay == {**result, "replayed": True}
    assert manager.score.call_count == calls
    after = snapshot(restarted)
    expected_decisions = 2 if existing_account else 1
    assert len(after["decisions"]) == len(after["outbox"]) == expected_decisions
    assert len(after["accounts"]) == 1
    account = after["accounts"][0]
    assert account["last_ts"] == candidate.timestamp.timestamp()
    assert len(json.loads(account["history"])) == expected_decisions
    decision = next(row for row in after["decisions"] if row["id"] == "candidate")
    event = next(row for row in after["outbox"] if row["id"] == "candidate")
    assert json.loads(decision["features"])["count_5m"] == int(existing_account)
    assert json.loads(decision["result"]) == json.loads(event["payload"]) == result
    assert event["delivered"] == 0
