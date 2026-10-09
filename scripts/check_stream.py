"""CI smoke check after publishing --seed 99 --count 20 into a fresh Compose stack."""
import time
import httpx
from fraud.config import API_KEY
with httpx.Client(base_url='http://127.0.0.1:8000',headers={'X-API-Key':API_KEY},trust_env=False) as client:
    for _ in range(120):
        response=client.get('/v1/decisions');response.raise_for_status()
        ids={r['transaction_id'] for r in response.json()}
        if all(f'tx_99_{i}' in ids for i in range(20)):
            print('20 streamed transactions durably scored');break
        time.sleep(.5)
    else:raise SystemExit('Kafka scoring timed out')
