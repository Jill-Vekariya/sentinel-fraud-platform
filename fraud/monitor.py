import json
import numpy as np
from .config import FEATURES
from .train import metrics

def report(store, manager, minimum=100):
    rows=store.rows(1000); manager.load();features=[json.loads(r['features']) for r in rows]
    drift={}
    if len(rows)>=minimum:
        for name in FEATURES:
            base=manager.meta['baseline'][name]
            counts=np.histogram([f[name] for f in features],base['edges'])[0]
            current=np.maximum(counts/max(counts.sum(),1),1e-6)
            expected=np.maximum(base['probabilities'],1e-6)
            drift[name]=float(np.sum((current-expected)*np.log(current/expected)))
    labeled=[r for r in rows if r['label'] is not None]
    performance=None
    if len(labeled)>=minimum and len(set(r['label'] for r in labeled))==2:
        # Decision-level confusion matrix reflects original per-row model versions and rules.
        y=np.array([r['label'] for r in labeled]); results=[json.loads(r['result']) for r in labeled]
        pred=np.array([r['decision']=='BLOCK' for r in results]); scores=np.array([r['risk_score'] for r in results])
        performance=metrics(y,scores,.5)
        from sklearn.metrics import confusion_matrix,precision_score,recall_score
        tn,fp,fn,tp=confusion_matrix(y,pred,labels=[0,1]).ravel()
        performance.update(precision=float(precision_score(y,pred,zero_division=0)),recall=float(recall_score(y,pred,zero_division=0)),
                           false_positive_rate=float(fp/max(fp+tn,1)),tp=int(tp),fp=int(fp),tn=int(tn),fn=int(fn))
    latencies=[json.loads(r['result'])['latency_ms'] for r in rows]
    return {'sample_size':len(rows),'labeled_sample_size':len(labeled),'psi':drift,
            'drift_alert':any(p>.2 for p in drift.values()),'minimum_samples':minimum,
            'performance':performance,'p95_core_ms':float(np.percentile(latencies,95)) if latencies else None,
            'model_version':manager.version,'retraining_recommended':any(p>.2 for p in drift.values()),
            'note':'PSI is a heuristic; performance uses observed labels only. Core latency excludes HTTP and commit.'}
