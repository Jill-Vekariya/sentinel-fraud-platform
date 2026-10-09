import argparse, json, pickle, hashlib, time, csv
from pathlib import Path
import numpy as np
import xgboost as xgb
from sklearn.ensemble import IsolationForest
from sklearn.metrics import average_precision_score, precision_score, recall_score, confusion_matrix
from .data import generate,matrix
from .config import MODELS,FEATURES
from .model import point_to, ModelManager
from .schema import Transaction

def metrics(y,scores,threshold):
    pred=scores>=threshold;tn,fp,fn,tp=confusion_matrix(y,pred,labels=[0,1]).ravel()
    return {'pr_auc':float(average_precision_score(y,scores)), 'precision':float(precision_score(y,pred,zero_division=0)),
            'recall':float(recall_score(y,pred,zero_division=0)), 'false_positive_rate':float(fp/max(tn+fp,1)),
            'tp':int(tp),'fp':int(fp),'tn':int(tn),'fn':int(fn),'n':len(y)}

def risk(clf,anomaly,reference,X):
    return .95*clf.predict_proba(X)[:,1]+.05*np.searchsorted(reference,-anomaly.score_samples(X))/len(reference)

def fit(directory=MODELS,n=12000,seed=42,dataset=None,promote=False):
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
    if dataset:
        with open(dataset,newline='') as f: rows=list(csv.DictReader(f))
        if any(r['is_fraud'] not in ('0','1') for r in rows): raise ValueError('labels must be 0 or 1')
        events=sorted([(Transaction.model_validate(r),int(r['is_fraud'])) for r in rows],key=lambda e:e[0].timestamp)
    else: events=list(generate(n,seed))
    ids=[tx.transaction_id for tx,_ in events]
    if len(ids)!=len(set(ids)): raise ValueError('duplicate transaction IDs in training dataset')
    X,y,payloads=matrix(events)
    a=int(len(y)*.6);b=int(len(y)*.8)
    if min(a,b-a,len(y)-b)<100 or any(len(np.unique(v))!=2 for v in [y[:a],y[a:b],y[b:]]):
        raise ValueError('need >=100 events and both classes in each chronological split')
    clf=xgb.XGBClassifier(n_estimators=120,max_depth=4,learning_rate=.06,subsample=.9,colsample_bytree=.9,
                          eval_metric='logloss',n_jobs=2,random_state=seed)
    clf.fit(X[:a],y[:a])
    anomaly=IsolationForest(n_estimators=80,random_state=seed,n_jobs=2).fit(X[:a][y[:a]==0])
    reference=np.sort(-anomaly.score_samples(X[:a][y[:a]==0]))
    val=risk(clf,anomaly,reference,X[a:b])
    # Select threshold on validation only. FPR applies to model BLOCK, not rule-driven REVIEW.
    thresholds=np.unique(np.r_[val,1.01])
    negatives=np.sort(val[y[a:b]==0])
    fpr=(len(negatives)-np.searchsorted(negatives,thresholds,side='left'))/len(negatives)
    threshold=float(thresholds[np.flatnonzero(fpr<=.01)[0]])
    validation=metrics(y[a:b],val,threshold)
    test=metrics(y[b:],risk(clf,anomaly,reference,X[b:]),threshold)
    baseline={}
    for i,name in enumerate(FEATURES):
        edges=np.unique(np.quantile(X[:a,i],np.linspace(0,1,11)))
        if len(edges)<2: edges=np.array([X[:a,i].min()-1,X[:a,i].max()+1])
        edges[0]=-1e12;edges[-1]=1e12
        counts=np.histogram(X[:a,i],edges)[0]; baseline[name]={'edges':edges.tolist(),'probabilities':(counts/counts.sum()).tolist()}
    digest=hashlib.sha256(json.dumps(payloads,sort_keys=True).encode()+y.tobytes()).hexdigest()
    version=f'v{time.time_ns()}';folder=directory/version;folder.mkdir()
    clf.save_model(folder/'classifier.json');raw=pickle.dumps(anomaly);(folder/'anomaly.pkl').write_bytes(raw)
    gate=validation['pr_auc']>=.15 and validation['recall']>=.1 and validation['false_positive_rate']<=.01
    champion_validation=None
    if (directory/'current.json').exists():
        champion=ModelManager(directory).load()
        cv=risk(champion.clf,champion.anomaly,np.array(champion.meta['anomaly_reference']),X[a:b])
        champion_validation=metrics(y[a:b],cv,champion.meta['threshold'])
        gate=gate and validation['pr_auc']>=champion_validation['pr_auc']-.02
    meta={'version':version,'features':FEATURES,'threshold':threshold,'validation':validation,'test':test,
          'champion_validation':champion_validation,'promotion_gate_passed':gate,'baseline':baseline,
          'anomaly_reference':reference.tolist(),'anomaly_sha256':hashlib.sha256(raw).hexdigest(),
          'classifier_sha256':hashlib.sha256((folder/'classifier.json').read_bytes()).hexdigest(),
          'dataset_sha256':digest,'synthetic':dataset is None,'seed':seed,'split':'chronological 60/20/20',
          'note':'Synthetic metrics demonstrate pipeline only; no real-world claims.'}
    (folder/'metadata.json').write_text(json.dumps(meta,indent=2))
    (folder/'report.json').write_text(json.dumps({k:v for k,v in meta.items() if k not in ('anomaly_reference','baseline')},indent=2))
    if promote:
        if not gate: raise ValueError(f'promotion gate failed; candidate retained at {folder}')
        point_to(directory,version)
    # Optional experiment logging. Tracking failures do not invalidate local artifacts.
    import os
    if os.getenv('MLFLOW_TRACKING_URI'):
        import mlflow
        mlflow.set_experiment('fraud-platform')
        with mlflow.start_run():
            mlflow.log_params({'version':version,'seed':seed,'synthetic':dataset is None,'dataset_sha256':digest})
            mlflow.log_metrics({f'test_{k}':v for k,v in test.items()})
            mlflow.log_artifacts(str(folder),artifact_path='model')
    return {k:v for k,v in meta.items() if k not in ('anomaly_reference','baseline')}
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--n',type=int,default=12000);p.add_argument('--seed',type=int,default=42)
    p.add_argument('--dataset');p.add_argument('--promote',action='store_true');p.add_argument('--rollback',action='store_true')
    args=p.parse_args()
    if args.rollback:
        pointer=json.loads((MODELS/'current.json').read_text());point_to(MODELS,pointer['previous']);print('Rolled back')
    else: print(json.dumps(fit(n=args.n,seed=args.seed,dataset=args.dataset,promote=args.promote),indent=2))
