'use strict';
const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),os=require('node:os'),path=require('node:path');
const {ThreadStore}=require('../src/thread-store');
const {ProviderRegistry}=require('../src/provider-registry');
const {ProviderRouter}=require('../src/provider-router');
const {createRuntime}=require('../src/server');
const {TurnReconciler}=require('../src/turn-reconciler');
const {SaasDelivery}=require('../src/saas-delivery');
const {sha256}=require('../src/canonical');

async function listen(t,runtime){const server=runtime.app.listen(0,'127.0.0.1');await new Promise((ok,fail)=>{server.once('listening',ok);server.once('error',fail)});t.after(()=>new Promise(r=>server.close(r)));const a=server.address();return 'http://127.0.0.1:'+a.port;}
async function call(base,p,opt={}){const r=await fetch(base+p,{headers:{'content-type':'application/json'},...opt});const j=await r.json();return {status:r.status,body:j};}
function fixture(t,{relayReady=true,mcCreateWorks=true}={}){
  const dir=fs.mkdtempSync(path.join(os.tmpdir(),'lion-r18-http-')),db=path.join(dir,'threads.db'),store=new ThreadStore(db);t.after(()=>{try{store.close()}catch{}fs.rmSync(dir,{recursive:true,force:true})});
  let localCalls=0,swarmCalls=0,saas=0;
  const mc={mediatorKey:'fixture',ready:async()=>true,createSaasRequest:async({thread_id})=>{if(!mcCreateWorks)throw Error('CHATGPT_DOWN');return {request_id:'saas-'+(++saas),thread_id}},requestStatus:async()=>({status:'WAITING_SUPERVISOR'}),cancelRequest:async()=>({status:'CANCELLED'}),recentMissions:async()=>({missions:[]}),missionProcess:async()=>({})};
  const local={ready:async()=>true,complete:async()=>{localCalls++;return {text:'LOCAL_ANSWER',response_digest:sha256('LOCAL_ANSWER'),authority_effect:'NONE'}}};
  const relay={ready:async()=>relayReady,dispatch:async({binding})=>store.bindTurn({request_id:binding.request_id,turn_id:'turn-'+binding.request_id,turn_request_hash:'h',state:'PENDING'})};
  const readiness={probe:async()=>({control_plane_ready:true,operator_control_ready:false,panel_runtime_ready:true,panel_runtime:'NODE_EXPRESS_R18',local_model_ready:true,turn_ingress_ready:relayReady,mcp_transport_ready:relayReady,durable_turn_dispatch_ready:relayReady,chatgpt_external_completion_ready:false,chatgpt_autonomous_execution_ready:false,browser_automation:'DISABLED_BY_POLICY',authority_effect:'NONE'}),snapshot(){return {local_model_ready:true,panel_runtime_ready:true,turn_ingress_ready:relayReady,mcp_transport_ready:relayReady,browser_automation:'DISABLED_BY_POLICY'}}};
  const registry=new ProviderRegistry(),router=new ProviderRouter({registry,readiness:()=>readiness.snapshot(),swarmHandler:async()=>{swarmCalls++;}});
  const runtime=createRuntime({store,local,missionControl:mc,operatorControl:{ready:async()=>false,state:async()=>({})},relay,readiness,router,reconciler:{start(){},stop(){}}});
  return {runtime,store,mc,local,relay,readiness,counts:()=>({localCalls,swarmCalls,saas})};
}
test('T01 Express boots on an isolated listener',async t=>{const f=fixture(t),base=await listen(t,f.runtime),r=await call(base,'/health');assert.equal(r.status,200);assert.equal(r.body.ok,true);});
test('T02 /health reports Node runtime',async t=>{const f=fixture(t),base=await listen(t,f.runtime),r=await call(base,'/health');assert.equal(r.body.runtime,'NODE_EXPRESS_R18');assert.equal(r.body.browser_automation,'DISABLED_BY_POLICY');});
test('T05 LOCAL result returns to exact originating thread',async t=>{const f=fixture(t),base=await listen(t,f.runtime),a=(await call(base,'/api/threads',{method:'POST',body:JSON.stringify({title:'A'})})).body,b=(await call(base,'/api/threads',{method:'POST',body:JSON.stringify({title:'B'})})).body;const r=await call(base,'/api/threads/'+a.thread_id+'/chat',{method:'POST',body:JSON.stringify({route:'LOCAL',message:'hello'})});assert.equal(r.status,200);assert.equal(r.body.thread_id,a.thread_id);assert.equal(f.store.getThread(a.thread_id).messages.at(-1).content,'LOCAL_ANSWER');assert.equal(f.store.getThread(b.thread_id).messages.length,0);});
test('T06 CHATGPT creates durable request and exact turn handoff',async t=>{const f=fixture(t),base=await listen(t,f.runtime),a=(await call(base,'/api/threads',{method:'POST',body:JSON.stringify({title:'A'})})).body,r=await call(base,'/api/threads/'+a.thread_id+'/chat',{method:'POST',body:JSON.stringify({route:'CHATGPT',message:'q'})});assert.equal(r.status,202);assert.equal(r.body.provider_id,'CHATGPT_SAAS');assert.equal(f.store.requestBinding(r.body.request_id).thread_id,a.thread_id);assert.equal(f.store.turnForRequest(r.body.request_id).turn_id,r.body.turn_id);});
test('T07 CHATGPT routing does not call SWARM',async t=>{const f=fixture(t),base=await listen(t,f.runtime),a=(await call(base,'/api/threads',{method:'POST',body:JSON.stringify({})})).body;await call(base,'/api/threads/'+a.thread_id+'/chat',{method:'POST',body:JSON.stringify({route:'CHATGPT',message:'q'})});assert.equal(f.counts().swarmCalls,0);});
test('T08 CHATGPT routing does not call local model',async t=>{const f=fixture(t),base=await listen(t,f.runtime),a=(await call(base,'/api/threads',{method:'POST',body:JSON.stringify({})})).body;await call(base,'/api/threads/'+a.thread_id+'/chat',{method:'POST',body:JSON.stringify({route:'CHATGPT',message:'q'})});assert.equal(f.counts().localCalls,0);});
test('T21 MCP/Turn Ingress down does not kill panel',async t=>{const f=fixture(t,{relayReady:false}),base=await listen(t,f.runtime),h=await call(base,'/health'),a=(await call(base,'/api/threads',{method:'POST',body:JSON.stringify({})})).body,r=await call(base,'/api/threads/'+a.thread_id+'/chat',{method:'POST',body:JSON.stringify({route:'CHATGPT',message:'q'})});assert.equal(h.status,200);assert.equal(r.status,202);assert.equal(r.body.state,'PENDING');});
test('T22 ChatGPT broker down does not kill LOCAL provider',async t=>{const f=fixture(t,{mcCreateWorks:false}),base=await listen(t,f.runtime),a=(await call(base,'/api/threads',{method:'POST',body:JSON.stringify({})})).body,r=await call(base,'/api/threads/'+a.thread_id+'/chat',{method:'POST',body:JSON.stringify({route:'LOCAL',message:'q'})});assert.equal(r.status,200);assert.equal(r.body.state,'RECONCILED');});

test('R18 integration A/B out-of-order completion and C deletion late receipt',async t=>{
  const dir=fs.mkdtempSync(path.join(os.tmpdir(),'lion-r18-abc-')),store=new ThreadStore(path.join(dir,'threads.db'));t.after(()=>{try{store.close()}catch{}fs.rmSync(dir,{recursive:true,force:true})});
  const A=store.createThread('A'),B=store.createThread('B'),C=store.createThread('C');
  for(const [tid,rid,turn] of [[A.thread_id,'ra','ta'],[B.thread_id,'rb','tb'],[C.thread_id,'rc','tc']]){store.bindRequest({thread_id:tid,request_id:rid,request_hash:'h'+rid,provider_id:'CHATGPT_SAAS',context_digest:'c',question:'q'+rid,context_json:'{}',state:'WAITING_FOR_SAAS_CONSUMER'});store.appendUserOnce(tid,'q'+rid,'saas-user:'+rid);store.bindTurn({request_id:rid,turn_id:turn,state:'PENDING'});}
  let phase=1;const answers={ra:'ANSWER_A',rb:'ANSWER_B',rc:'ANSWER_C'};
  const mc={requestStatus:async rid=>({status:'RESPONDED',receipt_digest:'receipt-'+rid})};
  const relay={getTurn:async turn=>{const rid={ta:'ra',tb:'rb',tc:'rc'}[turn];if(rid==='ra'&&phase===1)return {turn_id:turn,status:'PENDING'};return {turn_id:turn,status:'COMPLETED',response:{text:answers[rid]}};},completeBrokerFromTurn:async(binding,turn)=>({broker:{status:'RESPONDED',receipt_digest:'receipt-'+binding.request_id},answer:answers[binding.request_id],response_digest:sha256(answers[binding.request_id])})};
  const reconciler=new TurnReconciler({store,missionControl:mc,relay,delivery:new SaasDelivery({store})});
  await reconciler.runOnce();assert.equal(store.getThread(A.thread_id).messages.filter(x=>x.role==='assistant').length,0);assert.equal(store.getThread(B.thread_id).messages.filter(x=>x.role==='assistant')[0].content,'ANSWER_B');
  phase=2;await reconciler.runOnce();assert.equal(store.getThread(A.thread_id).messages.filter(x=>x.role==='assistant')[0].content,'ANSWER_A');assert.equal(store.getThread(B.thread_id).messages.filter(x=>x.role==='assistant').length,1);
  store.tombstoneThread(C.thread_id);await reconciler.runOnce();assert.throws(()=>store.getThread(C.thread_id),/THREAD_NOT_FOUND/);assert.equal(store.reconciliation('rc').state,'ORPHANED_THREAD');assert.equal(store.debugState().receipts.find(x=>x.request_id==='rc').receipt_digest,'receipt-rc');
});
