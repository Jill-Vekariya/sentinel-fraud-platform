"""Bounded smoke verification of a running, synthetic-only Compose installation."""
import json,os,time,uuid,sqlite3
from datetime import datetime,timezone,timedelta
from pathlib import Path
import httpx,redis
from confluent_kafka import Producer,Consumer
from fraud.config import API_KEY,DATA

def run():
    prefix='audit_'+uuid.uuid4().hex[:12]; base=datetime.now(timezone.utc)
    events=[{'transaction_id':prefix+'_'+str(i),'account_id':prefix+'_a'+str(i%4),
      'timestamp':(base+timedelta(microseconds=i)).isoformat(),'amount':100+i,'device_id':'usual',
      'country':'US','home_country':'US'} for i in range(20)]
    with httpx.Client(base_url='http://127.0.0.1:8000',headers={'X-API-Key':API_KEY},trust_env=False,timeout=10) as client:
        client.get('/health/ready').raise_for_status()
        assert httpx.post('http://127.0.0.1:8000/v1/score',json=events[0],trust_env=False).status_code==401
        assert client.post('/v1/score',json={**events[0],'amount':-1}).status_code==422
        producer=Producer({'bootstrap.servers':os.getenv('KAFKA_BOOTSTRAP','broker:9092'),'enable.idempotence':True})
        errors=[]
        for tx in events:
            producer.produce('transactions',key=tx['account_id'],value=json.dumps(tx),
              on_delivery=lambda error,msg:errors.append(str(error)) if error else None)
        assert producer.flush(15)==0 and not errors
        deadline=time.monotonic()+90;found={}
        while len(found)<len(events) and time.monotonic()<deadline:
            for tx in events:
                if tx['transaction_id'] in found:continue
                r=client.get('/v1/decisions/'+tx['transaction_id'])
                if r.status_code==200:found[tx['transaction_id']]=r.json()
            time.sleep(.1)
        assert len(found)==20,'Stream scoring incomplete'
        replay=client.post('/v1/score',json=events[0]);replay.raise_for_status()
        assert replay.json()['replayed'] and replay.json()['risk_score']==found[events[0]['transaction_id']]['risk_score']
        assert client.post('/v1/score',json={**events[0],'amount':2000}).status_code==409
        client.post('/v1/feedback/'+events[0]['transaction_id'],json={'is_fraud':False,'source':'final-verification'}).raise_for_status()
        cache=redis.Redis.from_url(os.getenv('REDIS_URL','redis://redis:6379/0'))
        assert cache.get('decision:'+events[-1]['transaction_id']);cache.close()
        consumer=Consumer({'bootstrap.servers':'broker:9092','group.id':prefix+'_output',
           'auto.offset.reset':'earliest','enable.auto.commit':False})
        consumer.subscribe(['decisions']);outputs=set();deadline=time.monotonic()+90
        try:
            while len(outputs)<20 and time.monotonic()<deadline:
                msg=consumer.poll(.5)
                if msg is None:continue
                if msg.error():raise RuntimeError(msg.error())
                value=json.loads(msg.value());tid=value.get('transaction_id')
                if tid in found:outputs.add(tid)
        finally:consumer.close()
        assert len(outputs)==20,'Decision output incomplete'
        late={**events[0],'transaction_id':prefix+'_late','timestamp':(base-timedelta(seconds=1)).isoformat()}
        producer.produce('transactions',key=late['account_id'],value=json.dumps(late));assert producer.flush(15)==0
        dlq=Consumer({'bootstrap.servers':'broker:9092','group.id':prefix+'_dlq',
           'auto.offset.reset':'earliest','enable.auto.commit':False})
        dlq.subscribe(['transactions.dlq']);rejected=False;deadline=time.monotonic()+60
        try:
            while not rejected and time.monotonic()<deadline:
                msg=dlq.poll(.5)
                if msg is not None and not msg.error():rejected=json.loads(msg.value()).get('transaction_id')==late['transaction_id']
        finally:dlq.close()
        assert rejected,'Late event was not routed to DLQ'
        metrics=client.get('/metrics');metrics.raise_for_status();assert 'fraud_request_seconds_count' in metrics.text
        monitoring=client.get('/v1/monitor');monitoring.raise_for_status()
        with sqlite3.connect(DATA/'fraud.db') as db:
            assert db.execute('SELECT count(*) FROM decisions WHERE id LIKE ?',(prefix+'_%',)).fetchone()[0]==20
            assert db.execute('SELECT sum(delivered) FROM outbox WHERE id LIKE ?',(prefix+'_%',)).fetchone()[0]==20
            assert db.execute('SELECT label FROM feedback WHERE id=?',(events[0]['transaction_id'],)).fetchone()[0]==0
        audit=DATA/'audit';audit.mkdir(exist_ok=True)
        (audit/'restart-input.json').write_text(json.dumps({'transaction':events[0],'risk_score':found[events[0]['transaction_id']]['risk_score']}))
        result={'readiness':True,'authentication':True,'validation':True,'streamed':20,'decision_outputs':20,
           'durable_replay':True,'payload_conflict':True,'feedback':True,'redis_mirror':True,
           'late_event_dlq':True,'delivered_outbox':True,'monitoring':True,'prometheus':True}
        (audit/'live-verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))

if __name__=='__main__':run()
