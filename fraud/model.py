import json, pickle, hashlib, os, threading
import numpy as np
import xgboost as xgb
from .config import FEATURES, MODELS
class ModelManager:
    def __init__(self, directory=MODELS):
        self.directory=directory; self.lock=threading.RLock(); self.version=None
    def load(self):
        # The pointer changes atomically; immutable version folders permit safe reload/rollback.
        with self.lock:
            pointer=json.loads((self.directory/'current.json').read_text())
            version=pointer['version']
            if version != self.version:
                folder=self.directory/version
                if folder.parent != self.directory or '/' in version: raise ValueError('invalid model version')
                meta=json.loads((folder/'metadata.json').read_text())
                raw=(folder/'anomaly.pkl').read_bytes()
                if hashlib.sha256(raw).hexdigest()!=meta['anomaly_sha256']: raise ValueError('artifact checksum mismatch')
                if hashlib.sha256((folder/'classifier.json').read_bytes()).hexdigest()!=meta['classifier_sha256']: raise ValueError('classifier checksum mismatch')
                clf=xgb.XGBClassifier(); clf.load_model(folder/'classifier.json')
                self.clf=clf
                # Only load locally built trusted artifacts; pickle must never accept user uploads.
                self.anomaly=pickle.loads(raw); self.meta=meta; self.version=version
            return self
    def score(self, features):
        with self.lock:
            X=np.array([[features[f] for f in FEATURES]], dtype=float)
            probability=float(self.clf.predict_proba(X)[0,1])
            raw=-float(self.anomaly.score_samples(X)[0])
            percentile=float(np.searchsorted(self.meta['anomaly_reference'],raw)/len(self.meta['anomaly_reference']))
            risk=.95*probability+.05*percentile
            contributions=self.clf.get_booster().predict(xgb.DMatrix(X), pred_contribs=True)[0][:-1]
            reasons=[{'feature':FEATURES[int(i)],'contribution_log_odds':round(float(contributions[i]),5)}
                     for i in np.argsort(contributions)[::-1][:3] if contributions[i]>0]
            threshold=self.meta['threshold']
            decision='BLOCK' if risk>=threshold else ('REVIEW' if risk>=threshold*.65 else 'APPROVE')
            rules=[]
            if features['count_5m']>=12: rules.append('HIGH_VELOCITY')
            if features['amount_ratio']>=10 and features['foreign']: rules.append('FOREIGN_AMOUNT_SPIKE')
            if rules and decision=='APPROVE': decision='REVIEW'
            return {'risk_score':round(risk,6), 'fraud_probability':round(probability,6),
                    'anomaly_percentile':round(percentile,6), 'decision':decision,
                    'reason_codes':rules, 'explanations':reasons, 'model_version':self.version,
                    'threshold':threshold}

def point_to(directory, version):
    if not version or '/' in version or version in ('.','..'): raise ValueError('invalid model version')
    if not (directory/version/'metadata.json').is_file(): raise ValueError('unknown model version')
    current=json.loads((directory/'current.json').read_text()) if (directory/'current.json').exists() else {}
    tmp=directory/'pointer.tmp'
    tmp.write_text(json.dumps({'version':version,'previous':current.get('version')}))
    os.replace(tmp,directory/'current.json')
