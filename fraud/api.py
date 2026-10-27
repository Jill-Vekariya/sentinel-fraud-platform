import os
import json
import time
import secrets
import logging
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Depends, HTTPException, Header, Response, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.exceptions import RequestValidationError
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from .config import DATA, MODELS, API_KEY, REDIS_URL
from .schema import Transaction, Feedback
from .store import Store, Conflict, LateEvent
from .middleware import BodyLimitMiddleware
from .model import ModelManager
from .monitor import report

log = logging.getLogger(__name__)
REQUESTS = Counter("fraud_decisions_total", "New durable decisions", ["decision"])
LATENCY = Histogram(
    "fraud_request_seconds",
    "Successful scoring handler including DB commit and optional cache",
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 5),
)

HTTP_REQUESTS = Counter(
    "fraud_http_requests_total",
    "HTTP requests including rejected and failed requests",
    ["method", "route", "status"],
)
HTTP_LATENCY = Histogram(
    "fraud_http_request_seconds",
    "Application request duration including validation and auth",
    ["method", "route"],
)


def auth(x_api_key: str = Header(default="")):
    if not secrets.compare_digest(x_api_key.encode("utf-8"), API_KEY.encode("utf-8")):
        raise HTTPException(401, "invalid API key")


def create_app(data_dir=DATA, model_dir=MODELS):
    if os.getenv("FRAUD_ENV", "local") == "production" and (
        len(API_KEY) < 24 or API_KEY == "local-demo-change-me"
    ):
        raise ValueError("Production requires a non-demo API key of at least 24 characters")

    @asynccontextmanager
    async def lifespan(app):
        app.state.store = Store(Path(data_dir) / "fraud.db")
        app.state.manager = ModelManager(Path(model_dir))
        app.state.manager.load()
        app.state.cache = None
        if REDIS_URL:
            import redis

            app.state.cache = redis.Redis.from_url(
                REDIS_URL, socket_connect_timeout=0.2, socket_timeout=0.2
            )
        yield
        if app.state.cache:
            app.state.cache.close()

    app = FastAPI(title="Fraud Risk Decisioning API", version="1.0.0", lifespan=lifespan)
    app.add_middleware(BodyLimitMiddleware, max_bytes=65_536)

    @app.middleware("http")
    async def request_telemetry(request: Request, call_next):
        request_id, start, status = uuid.uuid4().hex, time.perf_counter(), 500
        try:
            response = await call_next(request)
            status = response.status_code
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            # Use route templates, never submitted IDs, payloads, credentials or raw URLs.
            route = getattr(request.scope.get("route"), "path", "<unmatched>")
            method = (
                request.method if request.method in {"GET", "POST", "HEAD", "OPTIONS"} else "OTHER"
            )
            elapsed = time.perf_counter() - start
            HTTP_REQUESTS.labels(method, route, str(status)).inc()
            HTTP_LATENCY.labels(method, route).observe(elapsed)
            log.info(
                json.dumps(
                    {
                        "event": "http_request",
                        "request_id": request_id,
                        "method": method,
                        "route": route,
                        "status": status,
                        "duration_ms": round(elapsed * 1000, 3),
                    }
                )
            )

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request, exc):
        # Invalid JSON numbers can become inf/NaN, which cannot be serialized.
        # Return field diagnostics without echoing arbitrary inputs or contexts.
        detail = [{key: error[key] for key in ("loc", "msg", "type")} for error in exc.errors()]
        return JSONResponse(status_code=422, content={"detail": detail})

    @app.get("/", include_in_schema=False)
    def home():
        return FileResponse(Path(__file__).parent.parent / "web/index.html")

    @app.get("/health/live")
    def live():
        return {"status": "alive"}

    @app.get("/health/ready")
    def ready():
        try:
            app.state.manager.load()
            with app.state.store.connect() as db:
                db.execute("SELECT 1")
            return {"status": "ready", "model_version": app.state.manager.version}
        except Exception:
            raise HTTPException(503, "model or database unavailable")

    @app.post("/v1/score", dependencies=[Depends(auth)])
    def score(tx: Transaction):
        start = time.perf_counter()
        try:
            result = app.state.store.score(tx, app.state.manager)
        except (Conflict, LateEvent) as e:
            raise HTTPException(409, str(e))
        except Exception:
            log.exception("Scoring failed")
            raise HTTPException(503, "scoring unavailable; retry same transaction_id")
        if not result["replayed"]:
            REQUESTS.labels(result["decision"]).inc()
        # Cache is an optional read mirror, never the source of correctness.
        if app.state.cache:
            try:
                app.state.cache.setex("decision:" + tx.transaction_id, 3600, json.dumps(result))
            except Exception:
                log.warning("Redis unavailable; durable SQL result remains valid")
        LATENCY.observe(time.perf_counter() - start)
        return result

    @app.get("/v1/decisions", dependencies=[Depends(auth)])
    def decisions():
        return app.state.store.recent()

    @app.get("/v1/decisions/{tid}", dependencies=[Depends(auth)])
    def decision(tid: str):
        if app.state.cache:
            try:
                hit = app.state.cache.get("decision:" + tid)
                if hit:
                    return json.loads(hit)
            except Exception:
                pass
        with app.state.store.connect() as db:
            row = db.execute("SELECT result FROM decisions WHERE id=?", (tid,)).fetchone()
        if not row:
            raise HTTPException(404, "unknown transaction")
        return json.loads(row["result"])

    @app.post("/v1/feedback/{tid}", dependencies=[Depends(auth)])
    def feedback(tid: str, body: Feedback):
        try:
            app.state.store.feedback(tid, body.is_fraud, body.source)
        except KeyError:
            raise HTTPException(404, "unknown transaction")
        return {"status": "recorded"}

    @app.get("/v1/monitor", dependencies=[Depends(auth)])
    def monitor():
        return report(app.state.store, app.state.manager)

    @app.get("/v1/model", dependencies=[Depends(auth)])
    def model():
        app.state.manager.load()
        return {
            k: v
            for k, v in app.state.manager.meta.items()
            if k not in ("anomaly_reference", "baseline")
        }

    @app.get("/metrics", dependencies=[Depends(auth)])
    def metrics():
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    return app


app = create_app()
