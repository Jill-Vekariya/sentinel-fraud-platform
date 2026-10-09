import math
from .config import FEATURES

def extract(tx, history):
    # Strictly preceding event times; equal timestamps have a stable arrival order.
    ts = tx.timestamp.timestamp()
    past = [h for h in history if 0 <= ts-h['ts'] <= 86400]
    recent = [h for h in past if ts - h['ts'] <= 300]
    mean = sum(h['amount'] for h in past) / len(past) if past else 100.0
    hour = tx.timestamp.hour + tx.timestamp.minute / 60
    values = [math.log1p(tx.amount), len(recent), math.log1p(sum(h['amount'] for h in recent)),
              min(tx.amount / max(mean, 1), 100),
              int(not any(h['device_id'] == tx.device_id for h in past)),
              int(tx.country != tx.home_country), math.sin(hour*math.pi/12), math.cos(hour*math.pi/12)]
    return dict(zip(FEATURES, values))

def record(tx):
    return {'ts': tx.timestamp.timestamp(), 'amount': tx.amount, 'device_id': tx.device_id}

def advance(history, tx):
    # Shared bounded history for offline and online parity; 24h + 1000 most recent events.
    ts=tx.timestamp.timestamp()
    return sorted([h for h in history if ts-h['ts'] <= 86400] + [record(tx)], key=lambda h:h['ts'])[-1000:]
