import numpy as np
from scripts.benchmark_real import threshold_table,select_thresholds,scenario_cost

def test_threshold_counts_ties_and_amounts():
    rows=threshold_table(np.array([0,1,0,1]),np.array([.1,.2,.2,.9]),np.array([2,100,4,50]),[.2,.91])
    assert rows[0]=={'threshold':.2,'tp':2,'fp':1,'tn':1,'fn':0,'missed_fraud_amount':0.,'flagged':3}
    assert rows[1]['missed_fraud_amount']==150 and rows[1]['fn']==2 and rows[1]['flagged']==0
    assert scenario_cost(rows[0])==8

def test_cost_threshold_uses_validation_loss_and_has_approve_all_option():
    y=np.array([0,1]);s=np.array([.9,.1]);a=np.array([1,100])
    fpr,cost=select_thresholds(y,s,a)
    assert fpr>.9
    assert cost==.1
