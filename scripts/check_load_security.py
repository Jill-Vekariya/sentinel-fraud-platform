"""Bounded checks for an isolated API container; synthetic data only."""
import argparse
import asyncio
import json
import os
import platform
import sqlite3
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import httpx
import numpy as np

from fraud.config import API_KEY, DATA


def transaction(name, amount=100):
    return dict(transaction_id=name, account_id=name, timestamp=datetime.now(timezone.utc).isoformat(),
                amount=amount, device_id='usual', country='US', home_country='US')


async def run(url, count, output):
    prefix = 'load_' + uuid.uuid4().hex[:12]
    limits = httpx.Limits(max_connections=10, max_keepalive_connections=10)
    async with httpx.AsyncClient(base_url=url, headers={'X-API-Key': API_KEY},
                                trust_env=False, timeout=30, limits=limits) as client:
        deadline = time.monotonic() + 45
        while True:
            try:
                ready = await client.get('/health/ready')
                if ready.status_code == 200:
                    break
            except httpx.TransportError:
                pass
            if time.monotonic() >= deadline:
                raise RuntimeError('Isolated API did not become ready')
            await asyncio.sleep(.5)
        stages = []
        for concurrency in (1, 5, 10):
            semaphore = asyncio.Semaphore(concurrency)
            latencies = []
            statuses = {}

            async def score(index):
                async with semaphore:
                    tx = transaction(f'{prefix}_c{concurrency}_{index}')
                    start = time.perf_counter()
                    response = await client.post('/v1/score', json=tx)
                    latencies.append((time.perf_counter() - start) * 1000)
                    statuses[response.status_code] = statuses.get(response.status_code, 0) + 1
                    if response.status_code == 200:
                        body = response.json()
                        if body['transaction_id'] != tx['transaction_id'] or body['replayed']:
                            raise AssertionError('A new transaction returned the wrong decision')

            start = time.perf_counter()
            await asyncio.gather(*(score(i) for i in range(count)))
            duration = time.perf_counter() - start
            stages.append(dict(concurrency=concurrency, requests=count, status_counts=statuses,
                               duration_seconds=duration, achieved_requests_per_second=count / duration,
                               p50_http_ms=float(np.percentile(latencies, 50)),
                               p95_http_ms=float(np.percentile(latencies, 95)),
                               p99_http_ms=float(np.percentile(latencies, 99))))
            print(json.dumps(stages[-1]), flush=True)

        replay_tx = transaction(prefix + '_replay')
        replay_responses = await asyncio.gather(*(client.post('/v1/score', json=replay_tx) for _ in range(20)))
        if any(r.status_code != 200 for r in replay_responses):
            raise AssertionError('Concurrent replay failed')
        decisions = [r.json() for r in replay_responses]
        if sum(not r['replayed'] for r in decisions) != 1 or len({r['risk_score'] for r in decisions}) != 1:
            raise AssertionError('Concurrent replay was not idempotent')
        with sqlite3.connect(DATA / 'fraud.db') as db:
            for table in ('decisions', 'outbox'):
                if db.execute(f'SELECT count(*) FROM {table} WHERE id=?', (replay_tx['transaction_id'],)).fetchone()[0] != 1:
                    raise AssertionError('Concurrent replay duplicated persistent state')
            before = db.execute('SELECT count(*) FROM decisions').fetchone()[0]
        security = []

        async def check(name, method, path, expected, **kwargs):
            async with httpx.AsyncClient(base_url=url, headers={'X-API-Key': API_KEY},
                                        trust_env=False, timeout=10) as isolated:
                response = await isolated.request(method, path, **kwargs)
            security.append(dict(check=name, expected_status=expected, actual_status=response.status_code,
                                 passed=response.status_code == expected))
            return response

        tx = transaction(prefix + '_security')
        endpoints = [('POST', '/v1/score', {'json': tx}), ('GET', '/v1/decisions', {}),
                     ('GET', '/v1/decisions/' + replay_tx['transaction_id'], {}),
                     ('POST', '/v1/feedback/' + replay_tx['transaction_id'], {'json': {'is_fraud': False, 'source': 'audit'}}),
                     ('GET', '/v1/monitor', {}), ('GET', '/v1/model', {}), ('GET', '/metrics', {})]
        for method, path, kwargs in endpoints:
            for key in ('', 'incorrect-demo-key'):
                await check(f'{method} {path.split("/")[-1]} auth {"missing" if not key else "wrong"}',
                            method, path, 401, headers={'X-API-Key': key}, **kwargs)
        await check('non-ASCII invalid key', 'POST', '/v1/score', 401,
                    headers={b'X-API-Key': b'\xe9'}, json=tx)
        for name, changes in [('negative amount', {'amount': -1}), ('excess amount', {'amount': 10000001}),
                              ('naive timestamp', {'timestamp': '2026-10-09T12:00:00'}),
                              ('SQL identifier', {'transaction_id': "'; DROP TABLE decisions; --"}),
                              ('HTML device identifier', {'device_id': '<script>alert(1)</script>'})]:
            await check(name, 'POST', '/v1/score', 422, json={**tx, **changes})
        await check('overflow JSON number', 'POST', '/v1/score', 422,
                    content=json.dumps(tx).replace('"amount": 100', '"amount": 1e999'),
                    headers={'Content-Type': 'application/json'})
        await check('malformed JSON', 'POST', '/v1/score', 422, content='{',
                    headers={'Content-Type': 'application/json'})
        await check('SQL lookup remains unknown', 'GET', "/v1/decisions/'%20OR%201=1--", 404)
        await check('path traversal does not expose files', 'GET', '/%2e%2e/.env', 404)
        await check('changed payload conflicts', 'POST', '/v1/score', 409, json={**replay_tx, 'amount': 200})
        response = await client.options('/v1/score', headers={'Origin': 'https://attacker.invalid',
                          'Access-Control-Request-Method': 'POST', 'Access-Control-Request-Headers': 'x-api-key'})
        security.append(dict(check='untrusted origin not granted CORS',
                             passed='access-control-allow-origin' not in response.headers))
        with sqlite3.connect(DATA / 'fraud.db') as db:
            after = db.execute('SELECT count(*) FROM decisions').fetchone()[0]
        security.append(dict(check='rejected requests do not mutate ledger', passed=before == after))
        demo = []
        account = prefix + '_demo_account'
        for name, amount, device, country in [('normal', 45, 'usual', 'US'), ('foreign_spike', 6000, 'new', 'GB')]:
            body = {**transaction(prefix + '_' + name, amount), 'account_id': account,
                    'device_id': device, 'country': country}
            response = await client.post('/v1/score', json=body)
            response.raise_for_status()
            with sqlite3.connect(DATA / 'fraud.db') as db:
                features = json.loads(db.execute('SELECT features FROM decisions WHERE id=?',
                                     (body['transaction_id'],)).fetchone()[0])
            demo.append(dict(scenario=name, request=body, response=response.json(), stored_features=features))
        result = dict(passed=all(s['status_counts'] == {200: count} for s in stages) and all(s['passed'] for s in security),
                      recorded_at=datetime.now(timezone.utc).isoformat(),
                      environment=dict(python=platform.python_version(), platform=platform.platform(), visible_cpus=os.cpu_count()),
                      scope='Isolated single API, no Redis/Kafka; closed-loop HTTP clients; synthetic unique accounts; not a capacity SLA',
                      stages=stages, concurrent_replay=dict(requests=20, new_decisions=1, replays=19, ledger_rows=1, outbox_rows=1),
                      security_checks=security, recorded_demo=demo)
        Path(output).write_text(json.dumps(result, indent=2) + '\n')
        print(json.dumps({'passed': result['passed'], 'security_checks': len(security), 'output': output}), flush=True)
        if not result['passed']:
            raise SystemExit(1)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--url', default='http://127.0.0.1:8000')
    parser.add_argument('--count', type=int, default=100)
    parser.add_argument('--output', default='/tmp/load-security.json')
    args = parser.parse_args()
    if not 10 <= args.count <= 200:
        parser.error('Use 10 to 200 requests per stage')
    asyncio.run(run(args.url, args.count, args.output))
