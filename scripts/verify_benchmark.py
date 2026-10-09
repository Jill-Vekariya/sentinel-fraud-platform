"""Compare a freshly reproduced benchmark with the published aggregate report."""
import argparse,json,math
from pathlib import Path

def compare(expected_path,actual_path):
    expected=json.loads(Path(expected_path).read_text()); actual=json.loads(Path(actual_path).read_text())
    for key in ['rows','fraud_rows','sha256','splits']:
        if expected['dataset'][key]!=actual['dataset'][key]:raise AssertionError(f'Dataset differs: {key}')
    if expected['software']!=actual['software']:raise AssertionError('Benchmark software versions differ')
    worst=0.;checks=0
    for e,a in zip(expected['models'],actual['models'],strict=True):
        if e['name']!=a['name']:raise AssertionError('Model order differs')
        for key in ['validation_pr_auc','test_pr_auc','test_roc_auc']:
            delta=abs(e[key]-a[key]);worst=max(worst,delta);checks+=1
            if not math.isclose(e[key],a[key],rel_tol=0,abs_tol=1e-8):raise AssertionError(f'{e["name"]}: {key}')
        for policy in ['fpr_budget','minimum_cost']:
            for split in ['validation','test']:
                for key,value in e['policies'][policy][split].items():
                    other=a['policies'][policy][split][key];delta=abs(value-other);worst=max(worst,delta);checks+=1
                    if not math.isclose(value,other,rel_tol=0,abs_tol=1e-8):raise AssertionError(f'{e["name"]}: {policy}/{split}/{key}')
        for split in ['validation_curve','test_curve']:
            if len(e[split])!=len(a[split]):raise AssertionError('Threshold grid differs')
            for er,ar in zip(e[split],a[split],strict=True):
                for key,value in er.items():
                    other=ar[key];delta=abs(value-other);worst=max(worst,delta);checks+=1
                    if not math.isclose(value,other,rel_tol=0,abs_tol=1e-8):raise AssertionError(f'Threshold curve differs: {key}')
    return {'passed':True,'dataset_rows':actual['dataset']['rows'],'models':len(actual['models']),
            'numeric_comparisons':checks,'max_numeric_difference':worst,'tolerance':1e-8,
            'dataset_sha256':actual['dataset']['sha256']}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('expected');p.add_argument('actual');p.add_argument('--output');a=p.parse_args()
    result=compare(a.expected,a.actual); text=json.dumps(result,indent=2);print(text)
    if a.output:Path(a.output).write_text(text+'\n')
