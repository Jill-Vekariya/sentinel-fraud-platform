"""Drift-triggered candidate training; promotion always remains explicit."""
import argparse,json,csv
from pathlib import Path
from .config import DATA,MODELS
from .store import Store
from .model import ModelManager
from .monitor import report
from .train import fit
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--dataset',required=True,help='Mature labelled chronological CSV')
    p.add_argument('--force',action='store_true');args=p.parse_args()
    monitoring=report(Store(DATA/'fraud.db'),ModelManager(MODELS))
    if monitoring['retraining_recommended'] or args.force:
        # Train on a separately curated mature-label export, not selective reviewer feedback alone.
        print(json.dumps(fit(dataset=args.dataset,promote=False),indent=2))
    else:print('No drift trigger; no candidate trained')
