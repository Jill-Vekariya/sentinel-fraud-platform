import argparse,csv
from fraud.data import generate
p=argparse.ArgumentParser();p.add_argument('--output',default='data/labelled.csv');p.add_argument('--count',type=int,default=12000);p.add_argument('--seed',type=int,default=51);a=p.parse_args()
from pathlib import Path
Path(a.output).parent.mkdir(parents=True,exist_ok=True)
with open(a.output,'w',newline='') as f:
    writer=None
    for tx,label in generate(a.count,a.seed):
        row=tx.model_dump(mode='json');row['is_fraud']=label
        if writer is None:writer=csv.DictWriter(f,fieldnames=row.keys());writer.writeheader()
        writer.writerow(row)
print(a.output)
