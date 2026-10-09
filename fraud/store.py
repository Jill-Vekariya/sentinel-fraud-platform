import sqlite3, json, hashlib, time
from contextlib import contextmanager
from pathlib import Path
from .features import extract, advance
class Conflict(Exception): pass
class LateEvent(Exception): pass
class Store:
    def __init__(self, path):
        self.path=Path(path); self.path.parent.mkdir(parents=True,exist_ok=True)
        with self.connect() as db:
            db.executescript("""
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS accounts(id TEXT PRIMARY KEY, history TEXT NOT NULL, last_ts REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS decisions(id TEXT PRIMARY KEY, fingerprint TEXT NOT NULL, payload TEXT NOT NULL,
                features TEXT NOT NULL, result TEXT NOT NULL, created REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS feedback(id TEXT PRIMARY KEY REFERENCES decisions(id), label INTEGER, source TEXT, updated REAL);
            CREATE TABLE IF NOT EXISTS outbox(id TEXT PRIMARY KEY REFERENCES decisions(id), payload TEXT, delivered INTEGER DEFAULT 0);
            CREATE INDEX IF NOT EXISTS decision_time ON decisions(created);
            """)
    @contextmanager
    def connect(self):
        db=sqlite3.connect(self.path,timeout=10);db.row_factory=sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        try:
            with db: yield db
        finally: db.close()
    def score(self, tx, manager):
        payload=tx.model_dump(mode='json'); canonical=json.dumps(payload,sort_keys=True)
        digest=hashlib.sha256(canonical.encode()).hexdigest()
        started=time.perf_counter()
        with self.connect() as db:
            # One durable transaction: idempotency, account features, decision and event outbox.
            db.execute('BEGIN IMMEDIATE')
            old=db.execute('SELECT fingerprint,result FROM decisions WHERE id=?',(tx.transaction_id,)).fetchone()
            if old:
                if old['fingerprint']!=digest: raise Conflict('transaction_id already used with another payload')
                result=json.loads(old['result']);result['replayed']=True;return result
            row=db.execute('SELECT history,last_ts FROM accounts WHERE id=?',(tx.account_id,)).fetchone()
            ts=tx.timestamp.timestamp()
            if row and ts<row['last_ts']: raise LateEvent('event precedes account watermark; use a separate offline replay')
            history=json.loads(row['history']) if row else []
            features=extract(tx,history)
            manager.load(); result=manager.score(features)
            result.update(transaction_id=tx.transaction_id, replayed=False,
                          latency_ms=round((time.perf_counter()-started)*1000,3))
            db.execute('INSERT INTO decisions VALUES(?,?,?,?,?,?)',
                       (tx.transaction_id,digest,canonical,json.dumps(features),json.dumps(result),time.time()))
            db.execute('INSERT OR REPLACE INTO accounts VALUES(?,?,?)',
                       (tx.account_id,json.dumps(advance(history,tx)),ts))
            db.execute('INSERT INTO outbox(id,payload) VALUES(?,?)',(tx.transaction_id,json.dumps(result)))
        return result
    def recent(self,limit=100):
        with self.connect() as db:
            return [json.loads(r['result']) for r in db.execute('SELECT result FROM decisions ORDER BY created DESC LIMIT ?',(limit,))]
    def feedback(self,tid,label,source):
        with self.connect() as db:
            if not db.execute('SELECT id FROM decisions WHERE id=?',(tid,)).fetchone(): raise KeyError(tid)
            db.execute('INSERT OR REPLACE INTO feedback VALUES(?,?,?,?)',(tid,int(label),source,time.time()))
    def rows(self,limit=1000):
        with self.connect() as db:
            return [dict(r) for r in db.execute('SELECT d.*,f.label FROM decisions d LEFT JOIN feedback f ON d.id=f.id ORDER BY d.created DESC LIMIT ?',(limit,))]
    def pending(self):
        with self.connect() as db:
            return [dict(r) for r in db.execute('SELECT * FROM outbox WHERE delivered=0 LIMIT 100')]
    def delivered(self,tid):
        with self.connect() as db: db.execute('UPDATE outbox SET delivered=1 WHERE id=?',(tid,))
