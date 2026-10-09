import os,json,time,secrets,logging
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI,Depends,HTTPException,Header,Response
from fastapi.responses import FileResponse
from prometheus_client import Counter, Histogram,generate_latest,CONTENT_TYPE_LATEST
from .config import DATA,MODELS,API_KEY,REDIS_URL
from .schema import Transaction,Feedback
from .store import Store,Conflict,LateEvent
from .model import ModelManager
from .monitor import report
log=logging.getLogger(__name__)
REQUESTS=Counter('fraud_decisions_total','New durable decisions',['decision'])
LATENCY=Histogram('fraud_request_seconds','Full scoring request including DB commit',buckets=(.01,.025,.05,.1,.25,.5,1,5))

def auth(x_api_key: str=Header(default='')):
    if not secrets.compare_digest(x_api_key,API_KEY): raise HTTPException(401,'invalid API key')

def create_app(data_dir=DATA,model_dir=MODELS):
    @asynccontextmanager
    async def lifespan(app):
        app.state.store=Store(Path(data_dir)/'fraud.db')
        app.state.manager=ModelManager(Path(model_dir));app.state.manager.load()
        app.state.cache=None
        if REDIS_URL:
            import redis
            app.state.cache=redis.Redis.from_url(REDIS_URL,socket_connect_timeout=.2,socket_timeout=.2)
        yield
        if app.state.cache: app.state.cache.close()
    app=FastAPI(title='Fraud Risk Decisioning API',version='1.0.0',lifespan=lifespan)
    @app.get('/',include_in_schema=False)
    def home(): return FileResponse(Path(__file__).parent.parent/'web/index.html')
    @app.get('/health/live')
    def live(): return {'status':'alive'}
    @app.get('/health/ready')
    def ready():
        try:
            app.state.manager.load()
            with app.state.store.connect() as db: db.execute('SELECT 1')
            return {'status':'ready','model_version':app.state.manager.version}
        except Exception: raise HTTPException(503,'model or database unavailable')
    @app.post('/v1/score',dependencies=[Depends(auth)])
    def score(tx:Transaction):
        start=time.perf_counter()
        try: result=app.state.store.score(tx,app.state.manager)
        except (Conflict,LateEvent) as e: raise HTTPException(409,str(e))
        except Exception:
            log.exception('Scoring failed');raise HTTPException(503,'scoring unavailable; retry same transaction_id')
        LATENCY.observe(time.perf_counter()-start)
        if not result['replayed']: REQUESTS.labels(result['decision']).inc()
        # Cache is an optional read mirror, never the source of correctness.
        if app.state.cache:
            try: app.state.cache.setex('decision:'+tx.transaction_id,3600,json.dumps(result))
            except Exception: log.warning('Redis unavailable; durable SQL result remains valid')
        return result
    @app.get('/v1/decisions',dependencies=[Depends(auth)])
    def decisions(): return app.state.store.recent()
    @app.get('/v1/decisions/{tid}',dependencies=[Depends(auth)])
    def decision(tid:str):
        if app.state.cache:
            try:
                hit=app.state.cache.get('decision:'+tid)
                if hit:return json.loads(hit)
            except Exception: pass
        with app.state.store.connect() as db:
            row=db.execute('SELECT result FROM decisions WHERE id=?',(tid,)).fetchone()
        if not row: raise HTTPException(404,'unknown transaction')
        return json.loads(row['result'])
    @app.post('/v1/feedback/{tid}',dependencies=[Depends(auth)])
    def feedback(tid:str,body:Feedback):
        try: app.state.store.feedback(tid,body.is_fraud,body.source)
        except KeyError:raise HTTPException(404,'unknown transaction')
        return {'status':'recorded'}
    @app.get('/v1/monitor',dependencies=[Depends(auth)])
    def monitor():return report(app.state.store,app.state.manager)
    @app.get('/v1/model',dependencies=[Depends(auth)])
    def model():
        app.state.manager.load()
        return {k:v for k,v in app.state.manager.meta.items() if k not in ('anomaly_reference','baseline')}
    @app.get('/metrics',dependencies=[Depends(auth)])
    def metrics():return Response(generate_latest(),media_type=CONTENT_TYPE_LATEST)
    return app
app=create_app()
