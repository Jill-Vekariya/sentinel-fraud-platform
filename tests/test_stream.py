import json
from unittest.mock import Mock
import httpx
import pytest
from fraud.worker import process_message,drain_outbox
from fraud.store import Store
from fraud.schema import Transaction
from datetime import datetime,timezone

def message(body=None):
    msg=Mock();msg.error.return_value=None;msg.key.return_value=b'a'
    msg.value.return_value=json.dumps(body or {'transaction_id':'stream_1','account_id':'a','timestamp':'2025-01-01T00:00:00Z',
        'amount':100,'device_id':'d','country':'US','home_country':'US'}).encode()
    msg.offset.return_value=5;msg.partition.return_value=0;msg.topic.return_value='transactions';return msg

def producer(fail=False):
    p=Mock();p.flush.return_value=int(fail);return p

def test_success_commits_after_durable_api():
    consumer=Mock();p=producer();client=Mock()
    client.post.return_value=httpx.Response(200,json={'decision':'APPROVE'},request=httpx.Request('POST','http://api/v1/score'))
    process_message(consumer,p,client,message())
    client.post.assert_called_once();consumer.commit.assert_called_once()

def test_api_failure_does_not_commit(monkeypatch):
    monkeypatch.setattr('fraud.worker.time.sleep',lambda _:None)
    consumer=Mock();client=Mock();client.post.side_effect=httpx.ConnectError('unavailable')
    with pytest.raises(httpx.ConnectError):process_message(consumer,producer(),client,message())
    assert client.post.call_count==3;consumer.commit.assert_not_called()

def test_invalid_schema_dlq_before_commit():
    consumer=Mock();p=producer();client=Mock()
    process_message(consumer,p,client,message({'amount':-1}))
    assert p.produce.call_args.args[0]=='transactions.dlq';consumer.commit.assert_called_once();client.post.assert_not_called()

def test_dlq_failure_does_not_commit():
    consumer=Mock()
    with pytest.raises(RuntimeError):process_message(consumer,producer(True),Mock(),message({'amount':-1}))
    consumer.commit.assert_not_called()

def test_outbox_delivery_failure_retains_pending(tmp_path):
    store=Store(tmp_path/'db');payload='{"transaction_id":"one"}'
    with store.connect() as db:
        db.execute('INSERT INTO decisions VALUES(?,?,?,?,?,?)',('one','digest','{}','{}',payload,1))
        db.execute('INSERT INTO outbox(id,payload) VALUES(?,?)',('one',payload))
    with pytest.raises(RuntimeError):drain_outbox(store,producer(True))
    assert len(store.pending())==1
    drain_outbox(store,producer());assert not store.pending()
