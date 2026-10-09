import random, math
from datetime import datetime, timedelta, timezone
from .schema import Transaction
from .features import extract, advance
from .config import FEATURES
import numpy as np

def generate(n=12000,seed=42):
    rng=random.Random(seed);start=datetime(2025,1,1,tzinfo=timezone.utc)
    for i in range(n):
        account=rng.randrange(120); fraud=rng.random()<.035
        # Overlapping distributions, with deliberately learnable synthetic patterns.
        amount=math.exp(rng.gauss(4.4+1.4*fraud,1.05))
        foreign=rng.random() < (.65 if fraud else .08)
        new=rng.random() < (.7 if fraud else .04)
        yield Transaction(transaction_id=f'tx_{seed}_{i}',account_id=f'a_{account}',
            timestamp=start+timedelta(seconds=i*3),amount=round(amount,2),
            device_id=f'd_{account}_{i if new else 0}',country='GB' if foreign else 'US',home_country='US'),int(fraud)

def matrix(events):
    histories={};X=[];y=[];payloads=[]
    for tx,label in events:
        h=histories.get(tx.account_id,[])
        X.append(list(extract(tx,h).values()));y.append(label);payloads.append(tx.model_dump(mode='json'))
        histories[tx.account_id]=advance(h,tx)
    return np.array(X), np.array(y), payloads
