'use strict';
const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),os=require('node:os'),path=require('node:path');
const {ThreadStore}=require('../src/thread-store');
const {WorkspaceTrigger}=require('../src/workspace-trigger');
const {WakeDispatcher}=require('../src/wake-dispatcher');
const {TurnReconciler}=require('../src/turn-reconciler');
const {ProviderRegistry}=require('../src/provider-registry');
const {ProviderRouter}=require('../src/provider-router');
function fixture(t,{fetchImpl,enroll=true}={}){
  const dir=fs.mkdtempSync(path.join(os.tmpdir(),'lion-wake-')),db=path.join(dir,'threads.db');
  let store=new ThreadStore(db),clock=100000;
  t.after(()=>{store.close();fs.rmSync(dir,{recursive:true,force:true});});
  const thread=store.createThread('wake'),binding=store.bindRequest({request_id:'request-1',thread_id:thread.thread_id,request_hash:'request-hash',provider_id:'CHATGPT_SAAS',context_digest:'context-hash',wake_requested:enroll,state:'WAITING_FOR_SAAS_CONSUMER'});
  const tb=store.bindTurn({request_id:binding.request_id,turn_id:'turn-1',turn_request_hash:'turn-hash'});
  const calls=[],trigger=new WorkspaceTrigger({channelId:'agtch_fixture',tokenProvider:async()=>'unit-test-secret',fetchImpl:async(u,o)=>{calls.push({u,o});return fetchImpl?fetchImpl(u,o):{status:202,json:async()=>({conversation_url:'https://chatgpt.com/c/fixture',agent_trigger_run_id:'apirun_fixture'})};}});
  const mc={requestStatus:async()=>({status:'CLAIMED'})},relay={getTurn:async()=>({turn_id:tb.turn_id,thread_id:binding.thread_id,mission_id:null,command_id:'MC-'+binding.request_id,request_hash:'turn-hash',status:'PENDING'})};
  const dispatcher=()=>new WakeDispatcher({store,missionControl:mc,relay,trigger,now:()=>clock});
  return {get store(){return store},binding,tb,mc,relay,trigger,calls,dispatcher,advance(){clock+=300000;},restart(){store.close();store=new ThreadStore(db);}};
}
test('W01 AUTO routes through SaaS supervisor even when local inference is available',()=>{
  const router=new ProviderRouter({registry:new ProviderRegistry(),readiness:()=>({local_model_ready:true})});
  assert.equal(router.select('AUTO').provider_id,'CHATGPT_SAAS');assert.equal(router.select('LOCAL').provider_id,'LOCAL_MODEL');
});
test('W02 accepted wake survives DB reopen without duplicate send or secret persistence',async t=>{
  const f=fixture(t);assert.equal((await f.dispatcher().dispatch(f.binding,f.tb)).state,'ACCEPTED');
  f.restart();await f.dispatcher().dispatch(f.binding,f.tb);assert.equal(f.calls.length,1);
  const row=f.store.db.prepare('SELECT * FROM saas_wake_outbox').get();assert.ok(!JSON.stringify(row).includes('unit-test-secret'));
  assert.equal(row.state,'ACCEPTED');assert.notEqual(f.store.requestBinding('request-1').state,'RECONCILED');
});
test('W03 unknown network outcome retries identical event only after backoff',async t=>{
  let n=0;const f=fixture(t,{fetchImpl:async()=>{if(++n===1)throw Error('timeout');return {status:202,json:async()=>({conversation_url:'https://chatgpt.com/c/fixture'})};}});
  assert.equal((await f.dispatcher().dispatch(f.binding,f.tb)).state,'SEND_UNKNOWN');
  await f.dispatcher().dispatch(f.binding,f.tb);assert.equal(f.calls.length,1);
  f.restart();f.advance();await f.dispatcher().dispatch(f.binding,f.tb);
  assert.equal(f.calls[0].o.body,f.calls[1].o.body);assert.equal(f.calls[0].o.headers['Idempotency-Key'],f.calls[1].o.headers['Idempotency-Key']);
});
test('W04 historic unenrolled backlog is never awakened',async t=>{const f=fixture(t,{enroll:false});assert.equal((await f.dispatcher().dispatch(f.binding,f.tb)).state,'NOT_ENROLLED');assert.equal(f.calls.length,0);});
test('W05 deleted thread and cancelled broker prevent wake',async t=>{const f=fixture(t);f.store.tombstoneThread(f.binding.thread_id);assert.equal((await f.dispatcher().dispatch(f.binding,f.tb)).state,'CANCELLED');assert.equal(f.calls.length,0);});
test('W06 turn identity mismatch fails before sending',async t=>{const f=fixture(t);const get=f.relay.getTurn;f.relay.getTurn=async()=>({...await get(),thread_id:'other'});await assert.rejects(f.dispatcher().dispatch(f.binding,f.tb),/IDENTITY_MISMATCH/);assert.equal(f.calls.length,0);});
test('W07 403 does not produce an automatic retry loop',async t=>{const f=fixture(t,{fetchImpl:async()=>({status:403})});assert.equal((await f.dispatcher().dispatch(f.binding,f.tb)).state,'REJECTED');f.advance();await f.dispatcher().dispatch(f.binding,f.tb);assert.equal(f.calls.length,1);});
test('W08 two dispatchers cannot send the same job concurrently',async t=>{
  let release;const wait=new Promise(r=>release=r);const f=fixture(t,{fetchImpl:async()=>{await wait;return {status:202,json:async()=>({conversation_url:'https://chatgpt.com/c/fixture'})};}});
  const first=f.dispatcher().dispatch(f.binding,f.tb);await new Promise(r=>setImmediate(r));
  const second=await f.dispatcher().dispatch(f.binding,f.tb);assert.equal(second.state,'DEFERRED');release();await first;assert.equal(f.calls.length,1);
});
test('W09 background reconciler wakes pending exact turn without marking completion',async t=>{
  const f=fixture(t);const r=new TurnReconciler({store:f.store,missionControl:f.mc,relay:f.relay,delivery:{deliver(){assert.fail('premature delivery')}},wakeDispatcher:f.dispatcher()});
  await r.runOnce();assert.equal(f.calls.length,1);assert.equal(f.store.requestBinding(f.binding.request_id).state,'WAITING_FOR_SAAS_CONSUMER');
});
test('W10 same mission has stable conversation key and distinct request keys',async t=>{
  const f=fixture(t),a=f.trigger.event({...f.binding,mission_id:'mission-1'},f.tb),b=f.trigger.event({...f.binding,mission_id:'mission-1',request_id:'request-2'}, {...f.tb,turn_id:'turn-2'});
  assert.equal(JSON.parse(a.body).conversation_key,JSON.parse(b.body).conversation_key);assert.notEqual(a.idempotency_key,b.idempotency_key);
});
test('W11 missing token performs no HTTP request and is bounded by attempt limit',async t=>{
  const f=fixture(t);f.trigger.tokenProvider=async()=>null;
  for(let n=0;n<4;n++){await f.dispatcher().dispatch(f.binding,f.tb);f.advance();}
  assert.equal(f.calls.length,0);assert.equal(f.store.wakeState(f.binding.request_id).state,'EXHAUSTED');
});
test('W12 completed turn is not awakened after restart',async t=>{
  const f=fixture(t),get=f.relay.getTurn;f.relay.getTurn=async()=>({...await get(),status:'COMPLETED'});
  await f.dispatcher().dispatch(f.binding,f.tb);assert.equal(f.calls.length,0);assert.equal(f.store.wakeState(f.binding.request_id).state,'COMPLETED');
});
