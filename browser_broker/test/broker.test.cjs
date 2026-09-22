'use strict';
const test=require('node:test');const assert=require('node:assert/strict');const fs=require('node:fs');const os=require('node:os');const path=require('node:path');
const {Store}=require('../src/store.cjs');const {Engine}=require('../src/engine.cjs');const {createHttp}=require('../src/http.cjs');const {TASK,webPreferences,conversation}=require('../src/contract.cjs');
const PROJECT='https://chatgpt.com/g/g-p-test/project';
const make=(id='1')=>({request_id:'saas-'+id,mission_id:'test-mission',panel_thread_id:'thread-test',turn_id:'turn_'+id,turn_request_hash:'a'.repeat(64),conversation_url:'https://chatgpt.com/g/g-p-test/c/conversation-one',task_sha256:TASK,deadline_at:Date.now()+600000});
const turn=v=>({turn_id:v.turn_id,thread_id:v.panel_thread_id,mission_id:v.mission_id,request_hash:v.turn_request_hash,command_id:'MC-'+v.request_id,status:'PENDING'});
function setup(t){const dir=fs.mkdtempSync(path.join(os.tmpdir(),'lion-r19-'));let store=new Store(path.join(dir,'queue.db'),PROJECT);store.resume();t.after(()=>{store.close();fs.rmSync(dir,{recursive:true,force:true})});return {dir,get store(){return store},reopen(){store.close();store=new Store(path.join(dir,'queue.db'),PROJECT);store.recover();return store}}}
test('queue survives restart without resending an uncertain effect',t=>{const x=setup(t);const v=make();x.store.enqueue(v);x.store.claim();x.reopen();assert.equal(x.store.stopped(),true);assert.equal(x.store.row(v.request_id).state,'SEND_UNKNOWN');x.store.resume();assert.equal(x.store.claim(),null);assert.equal(x.store.row(v.request_id).sends,1)});
test('authorized idle restart preserves automatic dispatch authorization',t=>{
 const x=setup(t);assert.equal(x.store.authorized(),true);x.store.shutdown();x.reopen();
 assert.equal(x.store.stopped(),false);assert.equal(x.store.authorized(),true);
 const last=x.store.db.prepare("SELECT state,reason FROM events ORDER BY seq DESC LIMIT 1").get();
 assert.equal(last.state,'RESUMED');assert.equal(last.reason,'PROCESS_START_AUTHORIZATION_RESTORED');
});
test('explicit STOP survives restart and clears automatic authorization',t=>{
 const x=setup(t);x.store.stop();x.reopen();assert.equal(x.store.stopped(),true);assert.equal(x.store.authorized(),false);
});
test('duplicate is idempotent but any binding change is rejected',t=>{const {store}=setup(t);const v=make();store.enqueue(v);store.enqueue({...v});assert.equal(store.rows().length,1);assert.throws(()=>store.enqueue({...v,panel_thread_id:'other'}),/BINDING_CONFLICT/)});
test('one mission and bounded turns; cross-thread mission reuse rejected',t=>{const {store}=setup(t);store.enqueue(make());assert.throws(()=>store.enqueue({...make('2'),mission_id:'other'}),/MISSION_LIMIT/);assert.throws(()=>store.enqueue({...make('2'),panel_thread_id:'other'}),/MISSION_BINDING_CONFLICT/);for(let i=2;i<=6;i++)store.enqueue(make(String(i)));assert.throws(()=>store.enqueue(make('7')),/TURN_LIMIT/)});
test('STOP cancels queued jobs and freezes uncertain external work',t=>{const {store}=setup(t);store.enqueue(make());store.claim();store.enqueue(make('2'));store.stop();assert.equal(store.row('saas-1').state,'SEND_UNKNOWN');assert.equal(store.row('saas-2').state,'CANCELLED');assert.equal(store.claim(),null)});
test('time bound rejects work before send',t=>{const {store}=setup(t);store.enqueue(make());store.now=()=>Date.now()+1200001;assert.equal(store.claim(),null);assert.equal(store.row('saas-1').state,'TIMED_OUT')});
test('mismatched live turn never reaches browser',async t=>{const {store}=setup(t);const v=make();store.enqueue(v);let sends=0;const e=new Engine({store,admit:async()=>true,browser:{ready:async()=>true,send:async()=>sends++},getTurn:async()=>({...turn(v),thread_id:'wrong'})});await e.tick();assert.equal(sends,0);assert.equal(store.row(v.request_id).state,'FAILED')});
test('one send then receipt readback; no model answer is synthesized',async t=>{const {store}=setup(t);const v=make();store.enqueue(v);let live=turn(v),sends=0;const e=new Engine({store,admit:async()=>true,browser:{ready:async()=>true,send:async()=>sends++},getTurn:async()=>live});await Promise.all([e.tick(),e.tick()]);assert.equal(sends,1);assert.equal(store.row(v.request_id).state,'AWAITING_RESULT');live={...live,status:'COMPLETED',response:{text:'genuine upstream value for this fixture'}};await e.tick();assert.equal(store.row(v.request_id).state,'RESULT_OBSERVED');assert.equal(sends,1)});
test('send exception never triggers blind retry',async t=>{const {store}=setup(t);const v=make();store.enqueue(v);let sends=0;const e=new Engine({store,admit:async()=>true,browser:{ready:async()=>true,send:async()=>{sends++;throw Error('unknown')}},getTurn:async()=>turn(v)});await e.tick();await e.tick();assert.equal(sends,1);assert.equal(store.row(v.request_id).state,'SEND_UNKNOWN')});
test('STOP during asynchronous admission prevents send',async t=>{const {store}=setup(t);const v=make();store.enqueue(v);let sends=0;const e=new Engine({store,admit:async()=>true,browser:{ready:async()=>true,send:async()=>sends++},getTurn:async()=>{store.stop();return turn(v)}});await e.tick();assert.equal(sends,0)});
test('wrong origins and fabricated project conversations rejected',()=>{for(const u of ['http://chatgpt.com/g/g-p-test/c/a','https://chatgpt.com.evil.test/g/g-p-test/c/a','https://chatgpt.com/g/g-p-other/c/a','https://chatgpt.com/g/g-p-test/c/a?token=x'])assert.throws(()=>conversation(u,PROJECT));const p=webPreferences('persist:test');assert.equal(p.sandbox,true);assert.equal(p.nodeIntegration,false);assert.equal(p.contextIsolation,true);assert.equal(p.webSecurity,true)});
test('HTTP requires broker token, rejects browser origins, accepts durable envelope',async t=>{const {store}=setup(t);const token='test-control-key-'.repeat(4);const server=createHttp({store,token,status:()=>({browser:'NOT_PROVEN'})}).listen(0,'127.0.0.1');await new Promise(r=>server.once('listening',r));t.after(()=>new Promise(r=>server.close(r)));const base='http://127.0.0.1:'+server.address().port;assert.equal((await fetch(base+'/v1/status')).status,401);const headers={authorization:'Bearer '+token,'content-type':'application/json'};assert.equal((await fetch(base+'/v1/status',{headers:{...headers,origin:'https://chatgpt.com'}})).status,403);assert.equal((await fetch(base+'/v1/wakes',{method:'POST',headers,body:JSON.stringify(make())})).status,202);const s=await (await fetch(base+'/v1/status',{headers})).json();assert.equal(s.live_e2e,'NOT_PROVEN');assert.equal(s.wakes.length,1)});
test('missing mission admission does not spend a send',async t=>{const {store}=setup(t);const v=make();store.enqueue(v);let sends=0;const e=new Engine({store,browser:{ready:async()=>true,send:async()=>sends++},getTurn:async()=>turn(v)});await e.tick();assert.equal(sends,0);assert.equal(store.row(v.request_id).sends,0)});
test('fresh mismatched completion requires operator reconciliation',async t=>{const {store}=setup(t);const v=make();store.enqueue(v);store.claim();store.transition(v.request_id,['DISPATCHING'],'AWAITING_RESULT');const e=new Engine({store,admit:async()=>true,browser:{ready:async()=>true},getTurn:async()=>({...turn(v),status:'COMPLETED',mission_id:'other',response:{text:'wrong'}})});await e.tick();assert.equal(store.row(v.request_id).state,'OPERATOR_REQUIRED')});
test('expiry during readback cannot dispatch an unverified next request',async t=>{
 const {store}=setup(t);const v=make(),later={...make('2'),deadline_at:v.deadline_at+1000};store.enqueue(v);store.enqueue(later);let sends=0;
 const e=new Engine({store,admit:async()=>true,browser:{ready:async()=>true,send:async()=>sends++},getTurn:async()=>{store.now=()=>v.deadline_at+1;return turn(v)}});
 await e.tick();assert.equal(sends,0);assert.equal(store.row(v.request_id).state,'TIMED_OUT');assert.equal(store.row(later.request_id).state,'QUEUED');assert.equal(store.row(later.request_id).sends,0);
});
test('broker cancellation, foreign scope, expired deadline and other consumer claim reject dispatch',()=>{
 const {brokerAllows}=require('../src/contract.cjs');const v=make();const request={request_id:v.request_id,mission_id:v.mission_id,thread_id:v.panel_thread_id,status:'WAITING_SUPERVISOR',deadline_at:new Date(v.deadline_at).toISOString()};
 assert.equal(brokerAllows(v,request),true);
 for(const status of ['CANCELLED','COMPLETED','CLAIMED','WAITING_OPERATOR_OVERDUE','SUPERSEDED'])assert.equal(brokerAllows(v,{...request,status}),false);
 assert.equal(brokerAllows(v,{...request,mission_id:'other'}),false);
 assert.equal(brokerAllows(v,{...request,thread_id:'other'}),false);
 assert.equal(brokerAllows(v,{...request,deadline_at:new Date(Date.now()-1).toISOString()}),false);
});
test('cancellation while ingress is read prevents external send',async t=>{
 const {store}=setup(t);const v=make();store.enqueue(v);let allowed=true,sends=0;
 const e=new Engine({store,admit:async()=>allowed,browser:{ready:async()=>true,send:async()=>sends++},getTurn:async()=>{allowed=false;return turn(v)}});
 await e.tick();assert.equal(sends,0);assert.equal(store.row(v.request_id).sends,0);
});
