// Exact subset Shapley values for the tree-path-dependent cover-weighted game.
export function explain(model,features){
 const n=model.features.length;if(n>10)throw Error('Exact browser explanations support at most 10 features');
 const x=model.features.map(f=>Math.fround(features[f]));const size=1<<n;const values=new Float64Array(size);
 const base=Math.log(model.base_score/(1-model.base_score));
 function expected(t,i,mask){const left=t.left_children[i];if(left===-1)return t.split_conditions[i];
  const right=t.right_children[i],feature=t.split_indices[i];
  if(mask&(1<<feature))return expected(t,x[feature]<Math.fround(t.split_conditions[i])?left:right,mask);
  const lc=t.sum_hessian[left],rc=t.sum_hessian[right],total=lc+rc;
  return total>0?(lc*expected(t,left,mask)+rc*expected(t,right,mask))/total:(expected(t,left,mask)+expected(t,right,mask))/2;
 }
 for(let mask=0;mask<size;mask++){let value=base;for(const t of model.trees)value+=expected(t,0,mask);values[mask]=value;}
 const choose=(a,b)=>{let v=1;for(let k=1;k<=b;k++)v=v*(a-k+1)/k;return v;};
 const contributions=model.features.map((feature,i)=>{let value=0;for(let mask=0;mask<size;mask++){if(mask&(1<<i))continue;let count=0;for(let m=mask;m;m>>>=1)count+=m&1;value+=(values[mask|(1<<i)]-values[mask])/(n*choose(n-1,count));}return {feature,contribution_log_odds:value};});
 return {baseline_log_odds:values[0],margin_log_odds:values[size-1],contributions};
}
