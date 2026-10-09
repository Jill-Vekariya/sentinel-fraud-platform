"""Verify exact browser explanations against native Tree SHAP."""
import json, subprocess
from pathlib import Path
import numpy as np
import xgboost as xgb
from fraud.model import ModelManager
from fraud.config import FEATURES

def main():
    manager=ModelManager().load(); model=json.loads(Path('hosted-demo/model.json').read_text())
    rng=np.random.default_rng(57); X=np.column_stack([rng.uniform(0,10,20),rng.integers(0,25,20),
      rng.uniform(0,12,20),rng.uniform(0,30,20),rng.integers(0,2,20),rng.integers(0,2,20),
      rng.uniform(-1,1,20),rng.uniform(-1,1,20)]).astype(float)
    rows=[dict(zip(FEATURES,row)) for row in X]
    code="import fs from 'node:fs';import {explain} from './hosted-demo/explain.js';const x=JSON.parse(fs.readFileSync(0,'utf8'));console.log(JSON.stringify(x.rows.map(r=>explain(x.model,r))));"
    output=json.loads(subprocess.run(['node','--input-type=module','-e',code],input=json.dumps({'model':model,'rows':rows}),text=True,capture_output=True,check=True).stdout)
    expected=manager.clf.get_booster().predict(xgb.DMatrix(X),pred_contribs=True)
    actual=np.array([[c['contribution_log_odds'] for c in r['contributions']]+[r['baseline_log_odds']] for r in output])
    error=float(np.max(np.abs(expected-actual)))
    report={'cases':len(rows),'max_log_odds_difference':error,'tolerance':1e-5,'passed':error<1e-5}
    Path('docs/browser-explanations-parity.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
    if not report['passed']:raise AssertionError('Browser SHAP parity failed')

if __name__=='__main__':main()
