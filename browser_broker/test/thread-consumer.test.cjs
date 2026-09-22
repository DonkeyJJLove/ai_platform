'use strict';
const test=require('node:test'),assert=require('node:assert/strict');
const fs=require('node:fs'),os=require('node:os'),path=require('node:path');
const {ThreadConsumer}=require('../src/thread-consumer.cjs');const {Store}=require('../src/store.cjs');
const {Engine}=require('../src/engine.cjs');const {TASK,hash,brokerAllows}=require('../src/contract.cjs');
const PROJECT='https://chatgpt.com/g/g-p-test/project';
function fixture(t){
 const dir=fs.mkdtempSync(path.join(os.tmpdir(),'lion-thread-')),store=new Store(path.join(dir,'broker.db'),PROJECT);
 t.after(()=>{store.close();fs.rmSync(dir,{recursive:true,force:true})});
 const scope={mode:'THREAD_CONSUMER',mission_id:null,thread_id:'panel-thread',conversation_url:'https://chatgpt.com/g/g-p-test/c/saas-thread',task_sha256:TASK};
 const row={request_id:'saas-1',mission_id:null,thread_id:scope.thread_id,scope_type:'THREAD',scope_id:scope.thread_id,authority_effect:'NONE',transport:'CHATGPT_SENTINELX_MCP',status:'CLAIMED',claim_generation:1,claim_expires_at:new Date(Date.now()+300000).toISOString(),deadline_at:new Date(Date.now()+600000).toISOString()};
 const turn={turn_id:'turn_1',command_id:'MC-saas-1',mission_id:null,thread_id:scope.thread_id,request_hash:'a'.repeat(64),parent_event_id:'saas_request:saas-1',status:'PENDING',response:null};
 let events=[{seq:101,type:'turn.pending',data:{turn_id:turn.turn_id,command_id:turn.command_id}}],sends=0,onRead=()=>{};const calls=[];
 const ingress=async(route,method='GET')=>{assert.equal(method,'GET');calls.push(route);if(route==='/v1/state')return {seq:100};if(route.startsWith('/v1/events?'))return {events};onRead();return {turn}};
 const mc=async(route,method='GET')=>{assert.equal(method,'GET');calls.push(route);assert.ok(!route.includes('/missions/'));return {...row}};
 const consumer=new ThreadConsumer({store,scope,mc,ingress});
 const engine=new Engine({store,getTurn:async()=>turn,admit:v=>consumer.admits(v),browser:{ready:async()=>true,send:async()=>{sends++}}});
 return {store,scope,row,turn,calls,consumer,engine,get sends(){return sends},set events(v){events=v},set onRead(v){onRead=v},async start(){await consumer.prime();store.resume();await consumer.tick()}};
}
test('THREAD request with null mission uses existing turn and no upstream writes',async t=>{
 const f=fixture(t);await f.start();assert.equal(f.store.row('saas-1').envelope.mission_id,null);assert.equal(f.store.row('saas-1').mission_id,'THREAD:panel-thread');
 await f.engine.tick();assert.equal(f.sends,1);assert.equal(f.store.row('saas-1').state,'AWAITING_RESULT');
 f.turn.status='COMPLETED';f.turn.response={text:'fixture answer'};await f.engine.tick();assert.equal(f.store.row('saas-1').state,'RESULT_OBSERVED');
 Object.assign(f.row,{status:'RESPONDED',receipt_digest:'b'.repeat(64),response_digest:hash('fixture answer')});await f.consumer.tick();
 assert.equal(f.store.row('saas-1').state,'RECONCILED');assert.equal(f.sends,1);assert.equal(f.consumer.status().writes_responses,false);
});
test('starting and status observation cannot replay pending historical turns',async t=>{
 const f=fixture(t);f.events=[{seq:99,type:'turn.pending',data:{turn_id:'turn_1'}}];await f.consumer.tick();assert.equal(f.calls.length,0);
 await f.start();assert.equal(f.store.rows().length,0);assert.equal(f.consumer.cursor,100);assert.equal(f.sends,0);
});
test('wrong thread, non-cognitive scope and cancelled requests never enqueue',async t=>{
 for(const patch of [{scope_id:'other'},{authority_effect:'BOUNDED_MATERIAL'},{scope_type:'MISSION'},{status:'CANCELLED'},{mission_id:'LION-R19-other'}]){
  const f=fixture(t);Object.assign(f.row,patch);await f.start();assert.equal(f.store.rows().length,0);
 }
});
test('producer claim rollover blocks dispatch of a stale observed envelope',async t=>{
 const f=fixture(t);await f.start();f.row.claim_generation=2;await f.engine.tick();assert.equal(f.sends,0);
});
test('event cannot substitute another pending turn identity',async t=>{
 const f=fixture(t);f.turn.turn_id='turn_other';await f.start();assert.equal(f.store.rows().length,0);
});
test('STOP while a turn is read prevents enqueue',async t=>{
 const f=fixture(t);f.onRead=()=>f.store.stop();await f.start();assert.equal(f.store.rows().length,0);assert.equal(f.sends,0);
});
test('duplicate event cannot duplicate a send',async t=>{
 const f=fixture(t);await f.start();await f.engine.tick();f.events=[{seq:102,type:'turn.pending',data:{turn_id:'turn_1'}}];await f.consumer.tick();await f.engine.tick();assert.equal(f.store.rows().length,1);assert.equal(f.sends,1);
});
test('receipt for another response is not reconciled',async t=>{
 const f=fixture(t);await f.start();await f.engine.tick();f.turn.status='COMPLETED';f.turn.response={text:'fixture answer'};await f.engine.tick();
 Object.assign(f.row,{status:'RESPONDED',receipt_digest:'b'.repeat(64),response_digest:hash('wrong answer')});await f.consumer.tick();assert.equal(f.store.row('saas-1').state,'RESULT_OBSERVED');
});
test('unbound thread consumer cannot admit external HTTP envelopes',async t=>{
 const f=fixture(t);await f.start();const v=f.store.row('saas-1').envelope;
 assert.equal(await f.consumer.admits({...v,panel_thread_id:'other'}),false);
 assert.equal(await f.consumer.admits({...v,conversation_url:'https://chatgpt.com/g/g-p-test/c/other'}),false);
 assert.equal(brokerAllows(v,{...f.row,authority_effect:'BOUNDED_MATERIAL'}),false);
});
test('STOP revision changes independently from resume',t=>{
 const f=fixture(t);const before=f.store.stopRevision();f.store.stop();assert.ok(f.store.stopRevision()>before);const after=f.store.stopRevision();f.store.resume();assert.equal(f.store.stopRevision(),after);
});

test('malformed causal-lineage event advances cursor without enqueuing',async t=>{
 const f=fixture(t);f.turn.parent_event_id=null;await f.start();
 assert.equal(f.store.rows().length,0);assert.equal(f.consumer.cursor,101);assert.equal(f.sends,0);
});
