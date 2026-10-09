from datetime import datetime,timezone
import argparse,time,json,statistics
import httpx
from fraud.data import generate
from fraud.config import API_KEY
p=argparse.ArgumentParser();p.add_argument('--count',type=int,default=200);p.add_argument('--url',default='http://localhost:8000');a=p.parse_args()
lat=[];decisions={};seed=int(time.time())
with httpx.Client(base_url=a.url,headers={'X-API-Key':API_KEY},timeout=20,trust_env=False) as client:
    for tx,label in generate(a.count,seed):
        tx.timestamp=datetime.now(timezone.utc)
        begin=time.perf_counter();r=client.post('/v1/score',json=tx.model_dump(mode='json'));r.raise_for_status()
        lat.append((time.perf_counter()-begin)*1000);result=r.json()
        decisions[result['decision']]=decisions.get(result['decision'],0)+1
        client.post('/v1/feedback/'+tx.transaction_id,json={'is_fraud':bool(label),'source':'synthetic-generator'}).raise_for_status()
    # Explicitly a serial HTTP benchmark, not a concurrent throughput claim.
    import numpy as np
    measured={'n':len(lat),'p50_http_ms':float(np.percentile(lat,50)),'p95_http_ms':float(np.percentile(lat,95)),
              'p99_http_ms':float(np.percentile(lat,99)),'decisions':decisions,'synthetic':True,'concurrency':1}
    print(json.dumps(measured,indent=2))
