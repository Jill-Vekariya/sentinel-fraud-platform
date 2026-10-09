export function averagePath(n){if(n<=1)return 0;if(n===2)return 1;return 2*(Math.log(n-1)+0.5772156649015329)-2*(n-1)/n}
export function predict(model,features){
 const x=model.features.map(f=>Math.fround(features[f]));let margin=Math.log(model.base_score/(1-model.base_score));
 for(const t of model.trees){let i=0;while(t.left_children[i]!==-1)i=x[t.split_indices[i]]<Math.fround(t.split_conditions[i])?t.left_children[i]:t.right_children[i];margin+=t.split_conditions[i]}
 const probability=1/(1+Math.exp(-margin));let depth=0;
 for(const t of model.forest){let i=0,n=0;while(t.left[i]!==-1){i=x[t.feature[i]]<=t.threshold[i]?t.left[i]:t.right[i];n++}depth+=n+averagePath(t.count[i])}
 const anomaly=Math.pow(2,-depth/(model.forest.length*averagePath(model.max_samples)));let lo=0,hi=model.reference.length;
 while(lo<hi){const mid=(lo+hi)>>1;if(model.reference[mid]<anomaly)lo=mid+1;else hi=mid}
 const percentile=lo/model.reference.length;const risk=.95*probability+.05*percentile;
 const reasons=[];if(features.count_5m>=12)reasons.push('HIGH_VELOCITY');if(features.amount_ratio>=10&&features.foreign)reasons.push('FOREIGN_AMOUNT_SPIKE');
 let decision=risk>=model.threshold?'BLOCK':risk>=model.threshold*.65?'REVIEW':'APPROVE';if(reasons.length&&decision==='APPROVE')decision='REVIEW';
 return {risk_score:risk,fraud_probability:probability,anomaly_percentile:percentile,decision,reason_codes:reasons,model_version:model.version}
}
export function extract(tx,history=[]){const ts=Date.parse(tx.timestamp)/1000;const past=history.filter(h=>0<=ts-h.ts&&ts-h.ts<=86400);const recent=past.filter(h=>ts-h.ts<=300);const mean=past.length?past.reduce((s,h)=>s+h.amount,0)/past.length:100;const date=new Date(tx.timestamp);const hour=date.getUTCHours()+date.getUTCMinutes()/60;return {log_amount:Math.log1p(tx.amount),count_5m:recent.length,sum_5m:Math.log1p(recent.reduce((s,h)=>s+h.amount,0)),amount_ratio:Math.min(tx.amount/Math.max(mean,1),100),new_device:+!past.some(h=>h.device_id===tx.device_id),foreign:+(tx.country!==tx.home_country),hour_sin:Math.sin(hour*Math.PI/12),hour_cos:Math.cos(hour*Math.PI/12)}}
export function advance(tx,history=[]){const ts=Date.parse(tx.timestamp)/1000;return [...history.filter(h=>ts-h.ts<=86400),{ts,amount:tx.amount,device_id:tx.device_id}].sort((a,b)=>a.ts-b.ts).slice(-1000)}
