"""Verify the live audit's saved transaction survives an API restart."""
import json
import sqlite3
import time

import httpx

from fraud.config import API_KEY, DATA


def run():
    audit = DATA / 'audit'
    checkpoint = json.loads((audit / 'restart-input.json').read_text())
    transaction = checkpoint['transaction']
    with httpx.Client(base_url='http://127.0.0.1:8000',
                      headers={'X-API-Key': API_KEY},
                      trust_env=False, timeout=10) as client:
        deadline = time.monotonic() + 60
        while True:
            try:
                response = client.get('/health/ready')
                if response.status_code == 200:
                    break
            except httpx.TransportError:
                pass
            if time.monotonic() >= deadline:
                raise RuntimeError('API did not become ready after restart')
            time.sleep(1)
        response = client.post('/v1/score', json=transaction)
        response.raise_for_status()
        decision = response.json()
        if not decision['replayed'] or decision['risk_score'] != checkpoint['risk_score']:
            raise AssertionError('Restart changed the persisted decision')
    with sqlite3.connect(DATA / 'fraud.db') as db:
        count = db.execute('SELECT count(*) FROM decisions WHERE id=?',
                           (transaction['transaction_id'],)).fetchone()[0]
        if count != 1:
            raise AssertionError('Restart replay duplicated the decision')
    result = {'passed': True, 'persisted_replay': True,
              'identical_risk_score': True, 'decision_rows': count}
    (audit / 'restart-verification.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))


if __name__ == '__main__':
    run()
