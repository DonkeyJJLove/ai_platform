'use strict';
const test=require('node:test');const assert=require('node:assert/strict');
const fs=require('node:fs'),os=require('node:os'),path=require('node:path');
const {Store}=require('../src/store.cjs');const {Relay,TRANSPORT}=require('../src/relay.cjs');
const {Engine}=require('../src/engine.cjs');const {hash,brokerAllows}=require('../src/contract.cjs');
const PROJECT='https://chatgpt.com/g/g-p-test/project';
const SCOPE={mission_id:'LION-R19-test',thread_id:'thread-test',conversation_url:'https://chatgpt.com/g/g-p-test/c/test'};
function fixture(t){
 const dir=fs.mkdtempSync(path.join(os.tmpdir(),'lion-relay-'));const file=path.join(dir,'queue.db');const clock=Date.now();
 const store=new Store(file,PROJECT,()=>clock);store.resume();t.after(()=>{store.close();fs.rmSync(dir,{recursive:true,force:true})});
 const row={request_id:'saas-test',mission_id:SCOPE.mission_id,thread_id:SCOPE.thread_id,transport:TRANSPORT,status:'WAITING_SUPERVISOR',created_at:new Date(clock).toISOString(),deadline_at:new Date(clock+600000).toISOString(),question:'Fixture cognitive request',question_digest:hash('Fixture cognitive request')};
 const writes=[];let turn,sends=0,failClaim=false,loseResponse=false,onClaim=()=>{};
 const mc=async(route,method='GET',body)=>{
  if(method==='POST')writes.push({route,body});
  if(route.endsWith('/process'))return {mission_id:SCOPE.mission_id,state:'AUTHORIZED',execution_preflight:{mission_readiness:'READY_BOUND'}};
  if(route.endsWith('/pending'))return {requests:[{...row}]};
  if(route.endsWith('/claim')){onClaim();row.status='CLAIMED';row.claim_generation=1;row.claim_expires_at=new Date(clock+300000).toISOString();if(failClaim)throw Error('lost claim');return {...row,response_token:'test-secret-'.repeat(8)}}
  if(route.endsWith('/respond')){row.status='RESPONDED';row.response_digest=hash(body.answer);row.receipt_digest='b'.repeat(64);if(loseResponse)throw Error('lost response');return {receipt:{receipt_digest:row.receipt_digest}}}
  return {...row};
 };
 const ingress=async(route,method='GET',body)=>{if(method==='POST'){writes.push({route,body});turn={...body,turn_id:'turn_test',request_hash:'a'.repeat(64),status:'PENDING'}}return {turn}};
 const browser={ready:async()=>true,send:async()=>{sends++}};
 const relay=new Relay({store,browser,mc,ingress,scope:SCOPE,now:()=>clock});
 const engine=new Engine({store,browser,getTurn:async()=>turn,admit:async v=>brokerAllows(v,row,clock),now:()=>clock});
 return {store,relay,engine,row,writes,clock,dir,file,get turn(){return turn},get sends(){return sends},set failClaim(v){failClaim=v},set loseResponse(v){loseResponse=v},set onClaim(v){onClaim=v},async enqueue(){await relay.tick();await relay.tick();await relay.tick()},complete(){turn.status='COMPLETED';turn.response={text:'A real response in the test fixture'}}};
}
test('relay binds an existing request through one send and independently reads back its receipt',async t=>{
 const f=fixture(t);await f.enqueue();assert.equal(f.store.row('saas-test').state,'QUEUED');await f.engine.tick();assert.equal(f.sends,1);
 f.complete();await f.engine.tick();await f.relay.tick();assert.equal(f.store.handoffs()[0].state,'RESPOND_INTENT');await f.relay.tick();
 const r=f.store.handoffs()[0];assert.equal(r.state,'RECONCILED');assert.equal(r.receipt_digest,'b'.repeat(64));assert.equal(r.claim,undefined);
 assert.equal(f.relay.status().panel_delivery,'NOT_PROVEN');assert.equal(f.writes.length,3);
 assert.ok(!JSON.stringify(f.relay.status()).includes('test-secret'));
});
test('lost respond ACK is reconciled without another POST or SaaS send',async t=>{
 const f=fixture(t);await f.enqueue();await f.engine.tick();f.complete();await f.engine.tick();f.loseResponse=true;
 await f.relay.tick();await f.relay.tick();assert.equal(f.store.handoffs()[0].state,'RECONCILED');assert.equal(f.writes.filter(w=>w.route.endsWith('/respond')).length,1);assert.equal(f.sends,1);
});
test('lost claim ACK blocks instead of repeating an upstream mutation',async t=>{
 const f=fixture(t);f.failClaim=true;await f.relay.tick();await f.relay.tick();await f.relay.tick();assert.equal(f.store.handoffs()[0].state,'OPERATOR_REQUIRED');assert.equal(f.writes.length,1);assert.equal(f.store.rows().length,0);
});
test('STOP during claim prevents turn creation and browser work',async t=>{
 const f=fixture(t);f.onClaim=()=>f.store.stop();await f.relay.tick();await f.relay.tick();assert.equal(f.writes.length,1);assert.equal(f.store.rows().length,0);
});
test('cancellation before enqueue blocks work without importing a cancelled turn',async t=>{
 const f=fixture(t);await f.relay.tick();await f.relay.tick();f.row.status='CANCELLED';await f.relay.tick();assert.equal(f.store.handoffs()[0].state,'CANCELLED');assert.equal(f.store.rows().length,0);assert.equal(f.sends,0);
});
test('claim rollover blocks a queued send',async t=>{
 const f=fixture(t);await f.enqueue();f.row.claim_generation=2;await f.relay.tick();await f.engine.tick();assert.equal(f.store.handoffs()[0].state,'OPERATOR_REQUIRED');assert.equal(f.sends,0);
});
test('old requests and unrelated panel threads are excluded before claim',async t=>{
 const f=fixture(t);f.row.created_at=new Date(f.clock-1).toISOString();await f.relay.tick();assert.equal(f.writes.length,0);
 f.row.created_at=new Date(f.clock).toISOString();f.row.thread_id='another-thread';await f.relay.tick();assert.equal(f.writes.length,0);
});
test('receipt hash mismatch cannot become reconciled',async t=>{
 const f=fixture(t);await f.enqueue();await f.engine.tick();f.complete();await f.engine.tick();await f.relay.tick();f.row.response_digest='c'.repeat(64);await f.relay.tick();assert.equal(f.store.handoffs()[0].state,'RESPOND_INTENT');assert.equal(f.relay.lastError,'RELAY_DEPENDENCY_OR_BINDING_ERROR');
});
test('expired claim never sends or fabricates a completion',async t=>{
 const f=fixture(t);await f.enqueue();f.row.claim_expires_at=new Date(f.clock-1).toISOString();await f.engine.tick();await f.relay.tick();assert.equal(f.sends,0);assert.equal(f.store.handoffs()[0].state,'OPERATOR_REQUIRED');
});
test('conversation survives reopening and rejected auth URLs cannot replace it',t=>{
 const f=fixture(t);f.store.rememberConversation(SCOPE.conversation_url);assert.throws(()=>f.store.rememberConversation('https://auth.openai.com/'));const other=new Store(f.file,PROJECT);try{assert.equal(other.restoreConversation(),SCOPE.conversation_url)}finally{other.close()}
});
test('claimed broker admission requires exact generation and live lease',t=>{
 const f=fixture(t);const v={request_id:f.row.request_id,mission_id:f.row.mission_id,panel_thread_id:f.row.thread_id,deadline_at:f.clock+600000,claim_generation:2};
 Object.assign(f.row,{status:'CLAIMED',claim_generation:2,claim_expires_at:new Date(f.clock+300000).toISOString()});
 assert.equal(brokerAllows(v,f.row,f.clock),true);assert.equal(brokerAllows({...v,claim_generation:1},f.row,f.clock),false);assert.equal(brokerAllows({...v,claim_generation:undefined},f.row,f.clock),false);
});
