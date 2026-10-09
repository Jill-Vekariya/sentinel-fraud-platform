import json
from datetime import datetime,timezone,timedelta
from concurrent.futures import ThreadPoolExecutor
import numpy as np
import pytest
from fastapi.testclient import TestClient
from fraud.train import fit
from fraud.model import ModelManager,point_to
from fraud.api import create_app
from fraud.store import Store,Conflict,LateEvent
from fraud.schema import Transaction
from fraud.features import extract,advance
from fraud.data import matrix
from fraud.monitor import report
from fraud.config import API_KEY
@pytest.fixture(scope='session')
def models(tmp_path_factory):
    path=tmp_path_factory.mktemp('models');fit(path,n=4000,seed=42,promote=True);return path
@pytest.fixture
def store(tmp_path):return Store(tmp_path/'fraud.db')
def tx(tid='one',seconds=0,amount=100):
    return Transaction(transaction_id=tid,account_id='a',timestamp=datetime(2025,1,1,tzinfo=timezone.utc)+timedelta(seconds=seconds),
                       amount=amount,device_id='d',country='US',home_country='US')
def test_duplicate_and_payload_conflict(store,models):
    manager=ModelManager(models);first=store.score(tx(),manager);again=store.score(tx(),manager)
    assert again['replayed'] and first['risk_score']==again['risk_score']
    with pytest.raises(Conflict):store.score(tx(amount=200),manager)
    store.score(tx('two',1),manager)
    row=store.rows()[0];assert json.loads(row['features'])['count_5m']==1
    assert len(store.pending())==2

def test_concurrent_idempotency(store,models):
    manager=ModelManager(models)
    with ThreadPoolExecutor(max_workers=6) as pool:results=list(pool.map(lambda _:store.score(tx(),manager),range(6)))
    assert sum(not r['replayed'] for r in results)==1
    assert len(store.rows())==1

def test_atomic_failure(store,models):
    class Broken:
        def load(self): pass
        def score(self,f):raise RuntimeError('model unavailable')
    with pytest.raises(RuntimeError):store.score(tx(),Broken())
    assert not store.rows() and not store.pending()
    result=store.score(tx(),ModelManager(models));assert not result['replayed']

def test_late_events(store,models):
    manager=ModelManager(models);store.score(tx('later',20),manager)
    with pytest.raises(LateEvent):store.score(tx('early',1),manager)
    assert len(store.rows())==1

def test_feature_parity():
    events=[(tx('one'),0),(tx('two',100,500),1),(tx('three',400,10),0)]
    X,_,_=matrix(events);history=[]
    for i,(event,_) in enumerate(events):
        assert np.allclose(X[i],list(extract(event,history).values()))
        history=advance(history,event)
    assert X[2,1]==1  # 5-minute window, first transaction expired

def test_auth_validation_feedback_and_health(tmp_path,models):
    with TestClient(create_app(tmp_path,models)) as client:
        assert client.get('/health/ready').status_code==200
        body=tx().model_dump(mode='json');headers={'X-API-Key':API_KEY}
        assert client.post('/v1/score',json=body).status_code==401
        assert client.post('/v1/score',json={**body,'amount':-1},headers=headers).status_code==422
        assert client.post('/v1/score',json={**body,'timestamp':'2025-01-01'},headers=headers).status_code==422
        result=client.post('/v1/score',json=body,headers=headers);assert result.status_code==200
        assert client.post('/v1/feedback/one',json={'is_fraud':True,'source':'test'},headers=headers).status_code==200
        assert client.post('/v1/feedback/missing',json={'is_fraud':True,'source':'test'},headers=headers).status_code==404
        monitoring=client.get('/v1/monitor',headers=headers).json()
        assert monitoring['labeled_sample_size']==1 and monitoring['performance'] is None
        assert client.get('/metrics',headers=headers).status_code==200
        assert client.get('/').status_code==200

def test_model_artifacts_and_monitor(store,models):
    manager=ModelManager(models).load();assert manager.meta['synthetic']
    assert manager.meta['validation']['false_positive_rate']<=.01
    result=store.score(tx(),manager)
    assert 0<=result['risk_score']<=1 and result['model_version']==manager.version
    assert isinstance(result['explanations'],list)
    assert report(store,manager)['psi']=={}

def test_invalid_header_and_overflow_are_client_errors(tmp_path,models):
    with TestClient(create_app(tmp_path,models)) as client:
        body=tx().model_dump(mode='json')
        assert client.post('/v1/score',json=body,headers={b'X-API-Key':b'\xe9'}).status_code==401
        raw=json.dumps(body).replace('"amount": 100.0','"amount": 1e999')
        assert '1e999' in raw
        response=client.post('/v1/score',content=raw,
            headers={'X-API-Key':API_KEY,'Content-Type':'application/json'})
        assert response.status_code==422 and response.json()['detail'][0]['loc']==['body','amount']
        assert client.get('/v1/decisions',headers={'X-API-Key':API_KEY}).json()==[]

def test_pointer_rollback_and_reload(tmp_path,models):
    import shutil
    target=tmp_path/'models';shutil.copytree(models,target)
    first=json.loads((target/'current.json').read_text())['version']
    second='second';shutil.copytree(target/first,target/second)
    point_to(target,second);manager=ModelManager(target).load();assert manager.version==second
    pointer=json.loads((target/'current.json').read_text());assert pointer['previous']==first
    point_to(target,pointer['previous']);manager.load();assert manager.version==first

def test_expired_account_history_is_not_used():
    first=tx('old',0,5000);later=tx('next',90000,100)
    features=extract(later,advance([],first))
    assert features['count_5m']==0 and features['amount_ratio']==1 and features['new_device']==1

def test_corrupt_artifact_rejected(tmp_path,models):
    import shutil
    target=tmp_path/'models';shutil.copytree(models,target)
    version=json.loads((target/'current.json').read_text())['version']
    (target/version/'classifier.json').write_text('{}')
    with pytest.raises(ValueError,match='checksum'):ModelManager(target).load()
