// Isolated rendering fixtures: these never enter the application or runtime DB.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const nodes = new Map();
const node = id => {
  if (!nodes.has(id)) nodes.set(id, {innerHTML:'',textContent:'',value:'',hidden:false,
    querySelectorAll:()=>[],scrollHeight:0,scrollTop:0,clientHeight:0});
  return nodes.get(id);
};
const source = fs.readFileSync(path.join(__dirname,'../mission_control/static/app.js'),'utf8');
const context = vm.createContext({document:{getElementById:node},navigator:{},
  AbortSignal,Date,console,setInterval:()=>{},fetch:()=>new Promise(()=>{})});
vm.runInContext(source,context);
const run = code => vm.runInContext(code,context);
async function main() {
  run('renderSummary({active_runs:0})');
  assert.match(node('summary').innerHTML,/Active runs.*>0</);
  assert.match(node('summary').innerHTML,/Deferred runs/);
  assert.match(node('summary').innerHTML,/Workloads/);
  assert.match(node('summary').innerHTML,/Artifacts/);
  assert.match(node('summary').innerHTML,/UNKNOWN/);
  assert.doesNotMatch(node('summary').innerHTML,/Working drones|Fleet total|Organizations/);
  run(`receipts([{receipt_id:'r',status:'PASS'}],'run')`);
  assert.match(node('receipts').innerHTML,/RECEIPT_PRESENT/);
  assert.match(node('receipts').innerHTML,/<td>UNKNOWN<\/td>/);
  assert.doesNotMatch(node('receipts').innerHTML,/VERIFIED|COMPLETE/);
  run(`participants({a:{state:'RUNNING',logical_id:'a'}},{host:'h'})`);
  assert.match(node('participants').innerHTML,/NONE OBSERVED/);
  assert.match(node('participants').innerHTML,/LOGICAL ONLY/);
  run(`artifacts([{artifact_id:'<img src=x>',path:'<script>bad()</script>'}],'r')`);
  assert.doesNotMatch(node('artifacts').innerHTML,/<img|<script>/);
  run(`allRuns=[{run_id:'r',adapter_type:'VKT_R3',process_class:'A',status:'PASS'}];$('processClass').value='B';renderRuns()`);
  assert.match(node('runs').innerHTML,/No runs match/);
  run(`$('processClass').value='A';renderRuns()`);
  assert.match(node('runs').innerHTML,/data-id="r"/);
  assert.notEqual(run("tone('UNKNOWN')"),run("tone('PASS')"));
  assert.notEqual(run("tone('CLEANED')"),run("tone('VERIFIED')"));
  assert.equal(run('stamp(null)'),'UNKNOWN');
  assert.equal(run('stamp(0)'),'1970-01-01T00:00:00.000Z');
  // An old request cannot replace a newer selection, even when it finishes last.
  const pending=[];
  context.fetch=url=>new Promise(resolve=>pending.push({url,resolve}));
  const old=run("detail('old')"),fresh=run("detail('new')");
  function answer(item){const id=item.url.split('/')[3];return {ok:true,run:{run_id:id,adapter_type:'OSS_REPOSITORY_TEST',status:'PASS',verification_status:'OBSERVED'},events:[],metrics:{},participants:{},artifacts:[],receipts:[]};}
  pending.slice(6).forEach(p=>p.resolve({ok:true,json:async()=>answer(p)}));
  await fresh;
  pending.slice(0,6).forEach(p=>p.resolve({ok:true,json:async()=>answer(p)}));
  await old;
  assert.match(node('identity').innerHTML,/>new</);
  assert.doesNotMatch(node('identity').innerHTML,/>old</);
  context.fetch=async()=>({ok:false,status:404});
  await run("detail('gone')");
  assert.equal(node('detail').hidden,true);
  assert.match(node('detailState').textContent,/UNKNOWN/);
  console.log('PASS: global cards, unknowns, evidence separation, logical identities, escaping, filters, selection race, failure state');
}
main().catch(e=>{console.error(e);process.exitCode=1});
