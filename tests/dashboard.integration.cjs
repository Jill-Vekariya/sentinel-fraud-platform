const {JSDOM,VirtualConsole}=require('jsdom');
const fs=require('fs');
const {writeReport}=require('./report.cjs');
const baseURL=process.env.SENTINEL_TEST_URL || 'http://127.0.0.1:8000';
const apiKey=process.env.SENTINEL_TEST_API_KEY || 'local-demo-change-me';
(async()=>{
 const errors=[];const virtual=new VirtualConsole();virtual.on('jsdomError',e=>errors.push(e.message));
 const dom=new JSDOM(fs.readFileSync('web/index.html','utf8'),{url:baseURL,runScripts:'dangerously',virtualConsole:virtual,beforeParse(window){window.fetch=(path,opts)=>fetch(new URL(path,baseURL),opts);}});
 const d=dom.window.document;
 async function until(test){for(let i=0;i<200;i++){if(test())return;await new Promise(r=>setTimeout(r,25))}throw Error('Timed out: '+d.getElementById('error').textContent)}
 d.getElementById('key').value=apiKey;d.getElementById('connect').click();
 await until(()=>d.getElementById('count').textContent!=='—');
 d.getElementById('form').dispatchEvent(new dom.window.Event('submit',{bubbles:true,cancelable:true}));
 await until(()=>d.getElementById('result').textContent.includes('model_version'));
 const scored=JSON.parse(d.getElementById('result').textContent).transaction_id;
 await until(()=>d.getElementById('rows').firstElementChild?.textContent.includes(scored));
 const n=Number(d.getElementById('labels').textContent);
 const first=d.getElementById('rows').firstElementChild; first.querySelector('button').click();
 await until(()=>Number(d.getElementById('labels').textContent)>n);
 if(errors.length)throw Error(errors.join('\n'));
 const report={connection:true,model_display:true,scoring:true,recent_decisions:true,feedback:true,js_errors:errors,visual_rendering_verified:false};
 writeReport('dashboard',report);dom.window.close();
})().catch(e=>{console.error(e);process.exit(1)});
