from datetime import datetime,timezone
import os,json,time,argparse
from confluent_kafka import Producer
from .data import generate
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--count',type=int,default=300);p.add_argument('--delay',type=float,default=.05)
    p.add_argument('--seed',type=int,default=int(time.time()));a=p.parse_args()
    producer=Producer({'bootstrap.servers':os.getenv('KAFKA_BOOTSTRAP','localhost:9092'),'enable.idempotence':True})
    failed=[]
    for tx,_ in generate(a.count,a.seed):
        tx.timestamp=datetime.now(timezone.utc)
        producer.produce('transactions',key=tx.account_id,value=json.dumps(tx.model_dump(mode='json')),
            on_delivery=lambda err,msg:failed.append(str(err)) if err else None)
        producer.poll(0);time.sleep(a.delay)
    if producer.flush(15) or failed:raise SystemExit('Delivery failed')
    print(f'Published {a.count} synthetic transactions (labels never sent to scorer)')
