"""Reproducible OpenML 1597 comparison; never promotes the streaming demo model."""
import argparse, hashlib, json, time, platform
from importlib.metadata import version
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.io import arff
from sklearn.dummy import DummyClassifier
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import IsolationForest
from sklearn.metrics import average_precision_score, roc_auc_score
from xgboost import XGBClassifier, __version__ as xgboost_version

SOURCE='https://www.openml.org/d/1597'
EXPECTED_MD5='178bcf9bb1f31a3dfe12d0e577884add'

def threshold_table(y, scores, amounts, thresholds):
    order=np.argsort(scores,kind='stable'); s=np.asarray(scores)[order]
    truth=np.asarray(y,dtype=int)[order]; money=np.asarray(amounts,dtype=float)[order]
    prefix_fraud=np.r_[0,np.cumsum(truth)]
    prefix_money=np.r_[0.,np.cumsum(money*truth)]
    fraud=int(truth.sum()); legitimate=len(truth)-fraud
    indexes=np.searchsorted(s,thresholds,side='left')
    fn=prefix_fraud[indexes]; tn=indexes-fn; tp=fraud-fn; fp=legitimate-tn
    return [{'threshold':float(t),'tp':int(a),'fp':int(b),'tn':int(c),'fn':int(d),
             'missed_fraud_amount':float(e),'flagged':int(a+b)}
            for t,a,b,c,d,e in zip(thresholds,tp,fp,tn,fn,prefix_money[indexes])]

def scenario_cost(row, loss_multiplier=1., fp_cost=5., review_cost=1.):
    return row['missed_fraud_amount']*loss_multiplier+row['fp']*fp_cost+row['flagged']*review_cost

def select_thresholds(y, scores, amounts):
    thresholds=np.unique(np.r_[scores,np.nextafter(float(np.max(scores)),np.inf)])
    table=threshold_table(y,scores,amounts,thresholds)
    negative=int((y==0).sum())
    budget=[r for r in table if r['fp']/max(negative,1)<=.01]
    # Lowest eligible threshold maximizes flagged recall under the FPR budget.
    fpr=min(budget,key=lambda r:r['threshold'])
    # Ties favor fewer flags; all candidate choices are on validation only.
    cost=min(table,key=lambda r:(scenario_cost(r),r['flagged']))
    return fpr['threshold'],cost['threshold']

def enrich(row):
    r=dict(row);r.update(precision=r['tp']/max(r['tp']+r['fp'],1),
                        recall=r['tp']/max(r['tp']+r['fn'],1),
                        false_positive_rate=r['fp']/max(r['fp']+r['tn'],1),
                        scenario_cost=scenario_cost(r))
    return r

def run(path, output):
    path=Path(path); raw=path.read_bytes(); digest=hashlib.md5(raw).hexdigest(); sha256=hashlib.sha256(raw).hexdigest()
    if path.suffix.lower()=='.csv':
        df=pd.read_csv(path); download_source='https://maxhalford.github.io/files/datasets/creditcardfraud.zip'
    else:
        if digest!=EXPECTED_MD5: raise ValueError('Dataset checksum differs from OpenML 1597 version 1')
        records,_=arff.loadarff(path); df=pd.DataFrame(records); download_source='https://openml.org/data/v1/download/1673544/creditcard.arff'
    df=df.sort_values('Time',kind='stable').reset_index(drop=True)
    y=df['Class'].map(lambda x:int(x.decode() if isinstance(x,bytes) else x)).to_numpy()
    if len(df)!=284807 or int(y.sum())!=492: raise ValueError('Unexpected dataset dimensions')
    features=['Time']+[f'V{i}' for i in range(1,29)]+['Amount']
    X=df[features].to_numpy(dtype=float); amounts=df.Amount.to_numpy(dtype=float)
    # Avoid equal elapsed-time values crossing split boundaries.
    a=int(len(y)*.6);b=int(len(y)*.8)
    a=int(np.searchsorted(df.Time.to_numpy(),df.Time.iloc[a],side='left'))
    b=int(np.searchsorted(df.Time.to_numpy(),df.Time.iloc[b],side='left'))
    train=slice(0,a);val=slice(a,b);test=slice(b,None)
    started=time.perf_counter()
    models={
      'Prior baseline':DummyClassifier(strategy='prior'),
      'Logistic regression':make_pipeline(StandardScaler(),LogisticRegression(max_iter=1000,random_state=42)),
      'XGBoost':XGBClassifier(n_estimators=120,max_depth=4,learning_rate=.06,subsample=.9,
                              colsample_bytree=.9,eval_metric='logloss',n_jobs=2,random_state=42),
    }
    scores={};timings={}
    for name,model in models.items():
        t=time.perf_counter();model.fit(X[train],y[train]);
        scores[name]=(model.predict_proba(X[val])[:,1],model.predict_proba(X[test])[:,1])
        timings[name]=time.perf_counter()-t;print(f'{name} completed',flush=True)
    t=time.perf_counter()
    anomaly=IsolationForest(n_estimators=80,n_jobs=2,random_state=42)
    anomaly.fit(X[train][y[train]==0])
    reference=np.sort(-anomaly.score_samples(X[train][y[train]==0]))
    av=np.searchsorted(reference,-anomaly.score_samples(X[val]))/len(reference)
    at=np.searchsorted(reference,-anomaly.score_samples(X[test]))/len(reference)
    scores['Isolation Forest']=(av,at);timings['Isolation Forest']=time.perf_counter()-t
    scores['XGBoost + anomaly (95/5)']=(.95*scores['XGBoost'][0]+.05*av,.95*scores['XGBoost'][1]+.05*at)
    timings['XGBoost + anomaly (95/5)']=timings['XGBoost']+timings['Isolation Forest']
    result={'dataset':{'name':'ULB/Worldline creditcard','openml_id':1597,'version':1,'source':SOURCE,
             'download_source':download_source,'md5':digest,'sha256':sha256,'rows':len(y),'fraud_rows':int(y.sum()),'features':features,
             'split':'Chronological 60/20/20, equal Time values kept together',
             'splits':{name:{'rows':len(y[s]),'fraud':int(y[s].sum()),'time_min':float(X[s,0].min()),
                            'time_max':float(X[s,0].max()),'fraud_amount':float(amounts[s][y[s]==1].sum())}
                       for name,s in [('train',train),('validation',val),('test',test)]}},
      'software':{'python':platform.python_version(),**{name:version(name) for name in ['numpy','pandas','scikit-learn','scipy']},'xgboost':xgboost_version},
      'protocol':{'seed':42,'preprocessing':'StandardScaler fitted only on training for logistic regression; no resampling',
        'threshold_selection':'Validation only: lowest threshold at <=1% FPR, and minimum assumed cost',
        'assumed_costs':{'loss_multiplier':1,'false_positive_friction':5,'review_per_flag':1,'currency':'EUR'},
        'cost_formula':'missed fraud Amount * loss multiplier + FP * friction + (TP + FP) * review',
        'limitations':['Only two days of old anonymized data; no customer IDs or account velocity features.',
          'Provided PCA transformation provenance is unknown; upstream leakage cannot be ruled out.',
          'One chronological holdout, fixed model settings; no statistical superiority claim or calibration.',
          'Assumes every flagged fraud is prevented; costs are hypothetical, not measured savings.',
          'Test curves are exploratory; reported operating thresholds were chosen on validation.',
          'Real benchmark models are separate from the synthetic live streaming model.']},'models':[]}
    for name,(vs,ts) in scores.items():
        fpr_threshold,cost_threshold=select_thresholds(y[val],vs,amounts[val])
        q=np.r_[np.linspace(0,.99,101),np.linspace(.99,1,201)]
        grid=np.unique(np.r_[np.quantile(vs,q),fpr_threshold,cost_threshold,np.nextafter(float(vs.max()),np.inf)])
        policies={}
        for policy,threshold in [('fpr_budget',fpr_threshold),('minimum_cost',cost_threshold)]:
            policies[policy]={'threshold':threshold,
              'validation':enrich(threshold_table(y[val],vs,amounts[val],[threshold])[0]),
              'test':enrich(threshold_table(y[test],ts,amounts[test],[threshold])[0])}
        result['models'].append({'name':name,'fit_and_score_seconds':timings[name],
          'validation_pr_auc':float(average_precision_score(y[val],vs)),
          'test_pr_auc':float(average_precision_score(y[test],ts)),'test_roc_auc':float(roc_auc_score(y[test],ts)),
          'policies':policies,'validation_curve':threshold_table(y[val],vs,amounts[val],grid),
          'test_curve':threshold_table(y[test],ts,amounts[test],grid)})
    result['runtime_seconds']=time.perf_counter()-started
    output=Path(output);output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'output':str(output),'rows':len(y),'models':[(m['name'],m['test_pr_auc']) for m in result['models']]}),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--dataset',default='data/benchmarks/creditcard.arff')
    p.add_argument('--output',default='docs/real-benchmark.json');args=p.parse_args();run(args.dataset,args.output)
