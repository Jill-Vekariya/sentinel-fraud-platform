"""Bounded HTTP verification; synthetic input only, fresh output required."""

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import threading
import time
import urllib.error
import urllib.request
import uuid


def verify(url, key, count=100):
    if not 1 <= count <= 200:
        raise ValueError("Use 1 through 200 load requests")
    url = url.rstrip("/")
    statuses, lock = [], threading.Lock()

    def request(path, body=None, *, authorized=True, raw=None):
        headers = {"Content-Type": "application/json"}
        if authorized:
            headers["X-API-Key"] = key
        data = raw if raw is not None else json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(url + path, data=data, headers=headers)
        start = time.perf_counter()
        try:
            response = urllib.request.urlopen(req, timeout=5)
        except urllib.error.HTTPError as exc:
            response = exc
        with response:
            payload = response.read()
            with lock:
                statuses.append(response.status)
            result = (
                json.loads(payload)
                if "json" in response.headers.get("Content-Type", "")
                else payload.decode()
            )
            return response.status, result, (time.perf_counter() - start) * 1000, response.headers

    checks = {}
    for path in ["/", "/health/live", "/health/ready"]:
        status, _, _, _ = request(path, authorized=False)
        assert status == 200, (path, status)
        checks[path] = status
    status, model, _, _ = request("/v1/model")
    assert status == 200 and model["synthetic"] is True
    for path in ["/v1/decisions", "/metrics"]:
        status, _, _, _ = request(path, authorized=False)
        assert status == 401
        checks[path + " unauthorized"] = status
    assert request("/v1/score", {})[0] == 422
    assert request("/v1/score", {"amount": -1})[0] == 422
    assert request("/v1/score", authorized=False, raw=b"x" * 65537)[0] == 413
    run_id = uuid.uuid4().hex[:12]

    def transaction(i):
        return {
            "transaction_id": f"verify-{run_id}-{i}",
            "account_id": f"synthetic-{run_id}-{i}",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "amount": 45,
            "device_id": "synthetic-device",
            "country": "US",
            "home_country": "US",
        }

    first = transaction("replay")
    initial = request("/v1/score", first)
    assert initial[0] == 200 and initial[1]["replayed"] is False
    assert len(initial[3]["X-Request-ID"]) == 32
    assert request("/v1/score", first)[1]["replayed"] is True
    assert request("/v1/score", {**first, "amount": 46})[0] == 409
    assert (
        request(
            "/v1/feedback/" + first["transaction_id"],
            {"is_fraud": False, "source": "synthetic-verifier"},
        )[0]
        == 200
    )
    warmup = 5
    for i in range(warmup):
        assert request("/v1/score", transaction("warm-" + str(i)))[0] == 200
    latencies, errors, timeouts = [], [], []
    start = time.perf_counter()
    stop = threading.Event()

    def score(i):
        if stop.is_set() or time.perf_counter() - start >= 20:
            stop.set()
            return
        try:
            status, _, latency, _ = request("/v1/score", transaction(i))
            with lock:
                latencies.append(latency)
                if status != 200:
                    errors.append(status)
                    if len(errors) >= 5:
                        stop.set()
        except (OSError, TimeoutError) as exc:
            with lock:
                timeouts.append(type(exc).__name__)
            stop.set()

    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(score, range(count)))
    elapsed = time.perf_counter() - start
    assert request("/health/ready")[0] == 200
    status, metrics, _, _ = request("/metrics")
    assert status == 200 and "fraud_http_requests_total" in metrics
    assert "fraud_http_request_seconds_count" in metrics
    ordered = sorted(latencies)

    def percentile(p):
        position = (len(ordered) - 1) * p
        lower = int(position)
        return (
            ordered[lower]
            + (ordered[min(lower + 1, len(ordered) - 1)] - ordered[lower]) * (position - lower)
            if ordered
            else None
        )

    return {
        "url": url,
        "synthetic": True,
        "concurrency": 2,
        "warmup_requests": warmup,
        "requested_load_count": count,
        "completed_load_count": len(latencies),
        "load_duration_seconds": elapsed,
        "p50_ms": percentile(0.5),
        "p95_ms": percentile(0.95),
        "p99_ms": percentile(0.99),
        "non_200_load_statuses": errors,
        "timeouts": timeouts,
        "total_http_responses_including_setup": len(statuses),
        "stop_conditions": "20 seconds, first timeout, or five non-200 load responses",
        "functional_checks": {
            **checks,
            "validation": 422,
            "size_limit": 413,
            "replay": True,
            "conflict": 409,
            "feedback": 200,
            "request_id": True,
            "metrics": True,
        },
        "model_version": model["version"],
        "first_transaction_id": first["transaction_id"],
        "passed": len(latencies) == count and not errors and not timeouts,
        "limitations": "Bounded synthetic HTTP test; no real-world fraud accuracy or production-capacity claim.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--count", type=int, default=100)
    args = parser.parse_args()
    path = Path(args.output)
    if path.exists():
        raise SystemExit("Choose a fresh output path to preserve earlier measurements")
    key = os.environ["API_KEY"]
    try:
        result = verify(args.url, key, args.count)
    except Exception as exc:
        result = {
            "passed": False,
            "url": args.url,
            "error_type": type(exc).__name__,
            "error": str(exc),
            "note": "Failed verification retained; no successful measurement is implied.",
        }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x") as handle:
        json.dump(result, handle, indent=2)
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["passed"] else 1)


if __name__ == "__main__":
    main()
