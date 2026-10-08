'use strict';
const test=require('node:test');
const assert=require('node:assert/strict');
const {createHash}=require('node:crypto');
const {CanonicalConversationSaaSConsumer}=require('../src/canonical-conversation-consumer.cjs');

class FakeStore{
 constructor(){this.values=new Map()}
 setting(k){return this.values.get(k)}
 setSetting(k,v){this.values.set(k,String(v))}
}

const baseCandidate={
 request_id:'saas-abc123',
 conversation_id:'conv-canonical-1',
 binding_epoch:1,
 lane_id:'lane-saas-1',
 request_message_id:'msg-user-1',
 causation_id:'cause-1',
 correlation_id:'corr-1',
 context_digest:'a'.repeat(64),
 shared_context_digest:'c'.repeat(64),
 binding_context_digest:'b'.repeat(64),
 mission_id:null,
 provider_session_ref:'ps-1',
};
const brokerQuestion=c=>[
 'LION MODEL CHAT — immutable context snapshot.',
 'Treat the transcript below as conversation context only; authority_effect=NONE.',
 'conversation_id='+c.conversation_id,
 'binding_epoch='+c.binding_epoch,
 'lane_id='+c.lane_id,
 'request_message_id='+c.request_message_id,
 'causation_id='+c.causation_id,
 'correlation_id='+c.correlation_id,
 'context_digest='+c.context_digest,
 'shared_context_digest='+c.shared_context_digest,
 'USER: hello',
].join('\n');
const candidate={...baseCandidate,projection_digest:createHash('sha256').update(brokerQuestion(baseCandidate)).digest('hex')};

function turnInput(c=candidate){
 return [
  'LION Mission Control SaaS request.',
  'Broker request id: '+c.request_id,
  'Question: '+brokerQuestion(c),
 ].join('\n');
}

function fixture({bridges=[]}={}){
 const store=new FakeStore();
 const calls={panel:[],browser:[],bridgeBodies:[],dispatchBodies:[]};
 let conversation={conversation_id:candidate.conversation_id,state:'UNBOUND',current_binding:{binding_epoch:1,mission_id:null,context_digest:'b'.repeat(64)},external_bridges:[...bridges]};
 const turn={
  turn_id:'turn_1',command_id:'MC-'+candidate.request_id,thread_id:null,session_id:'CHATGPT-SAAS',status:'PENDING',
  parent_event_id:'saas_request:'+candidate.request_id,input:turnInput(),request_hash:'e'.repeat(64),
 };
 const panel=async(path,method='GET',body)=>{
  calls.panel.push([path,method,body]);
  if(path==='/api/conversations/saas/pending?limit=128')return {candidates:[candidate],authority_effect:'NONE'};
  if(path==='/api/conversations/'+candidate.conversation_id&&method==='GET')return conversation;
  if(path==='/api/conversations/'+candidate.conversation_id+'/bridges'&&method==='POST'){
   calls.bridgeBodies.push(body);
   const row={bridge_id:'bridge-new',conversation_id:candidate.conversation_id,external_thread_ref:body.external_thread_ref,external_system:body.external_system,created_at:1,provenance_json:JSON.stringify({supplied:body.provenance}),context_snapshot_digest:body.context_snapshot_digest,authority_effect:'NONE'};
   conversation={...conversation,external_bridges:[...conversation.external_bridges,row]};
   return row;
  }
  if(path==='/api/conversations/saas/dispatch'&&method==='POST'){
   calls.dispatchBodies.push(body);
   return {dispatch_evidence:body,authority_effect:'NONE'};
  }
  throw new Error('panel '+method+' '+path);
 };
 const mc=async path=>{
  assert.equal(path,'/api/v3/saas-broker/requests/'+candidate.request_id);
  const question=brokerQuestion(candidate);
  return {request_id:candidate.request_id,status:'WAITING_SUPERVISOR',scope_type:'CONTROL_PLANE',thread_id:null,mission_id:null,authority_effect:'NONE',transport:'CHATGPT_SENTINELX_MCP',question,question_digest:createHash('sha256').update(question).digest('hex')};
 };
 const ingress=async path=>{
  if(path==='/v1/events?after=0')return {events:[{seq:1,type:'turn.pending',data:{turn_id:turn.turn_id,command_id:turn.command_id}}]};
  if(path==='/v1/events?after=1')return {events:[]};
  if(path==='/v1/turns/'+turn.turn_id)return {turn};
  throw new Error('ingress '+path);
 };
 const browser={
  async createProjectConversationWithPrompt(prompt,admitted){
   assert.equal(admitted(),true);calls.browser.push(['create',prompt]);
   return {conversation_url:'https://chatgpt.com/g/g-p-6a91cabd3f208191a37f295819e9f75b-lion-evolusion/c/native-1',external_thread_ref:'native-1',route:'PROJECT_CONVERSATION',project_membership:'URL_PROJECT_ID_MATCH'};
  },
  async sendToConversation(url,prompt,admitted){
   assert.equal(admitted(),true);calls.browser.push(['send',url,prompt]);return {url,id:'native-existing'};
  },
  async navigateExact(url){calls.browser.push(['navigate',url]);return {url}},
 };
 const consumer=new CanonicalConversationSaaSConsumer({store,panel,mc,ingress,browser,projectUrl:'https://chatgpt.com/g/g-p-6a91cabd3f208191a37f295819e9f75b-lion-evolusion/project',now:()=>1000});
 return {consumer,store,calls,conversation:()=>conversation,turn};
}

test('first canonical SaaS request auto-creates a dedicated native thread and persists exact bridge',async()=>{
 const f=fixture();f.consumer.resume('test');await f.consumer.tick();
 assert.equal(f.calls.browser.filter(x=>x[0]==='create').length,1);
 assert.equal(f.calls.bridgeBodies.length,1);
 const body=f.calls.bridgeBodies[0];
 assert.equal(body.external_thread_ref,'native-1');
 assert.equal(body.external_system,'CHATGPT_SAAS');
 assert.equal(body.context_snapshot_digest,candidate.context_digest);
 assert.equal(body.provenance.creation_mode,'AUTO');
 assert.equal(body.provenance.broker_request_id,candidate.request_id);
 assert.match(body.provenance.creation_receipt_digest,/^[a-f0-9]{64}$/);
 const state=JSON.parse(f.store.setting('canonical_dispatch_map'));
 assert.equal(state[candidate.request_id].state,'BOUND_SENT');
 assert.equal(state[candidate.request_id].bridge_id,'bridge-new');
 assert.equal(state[candidate.request_id].shared_context_digest,candidate.shared_context_digest);
 assert.equal(state[candidate.request_id].projection_digest,candidate.projection_digest);
 assert.match(state[candidate.request_id].actual_payload_bytes_digest,/^[a-f0-9]{64}$/);
 assert.equal(state[candidate.request_id].turn_request_hash,f.turn.request_hash);
 assert.match(String(state[candidate.request_id].dispatch_evidence_recorded_at),/^1000$/);
 assert.equal(f.calls.dispatchBodies.length,1);
 assert.equal(f.calls.dispatchBodies[0].bridge_id,'bridge-new');
 assert.equal(f.calls.dispatchBodies[0].external_thread_ref,'native-1');
 assert.equal(f.calls.dispatchBodies[0].actual_payload_bytes_digest,state[candidate.request_id].actual_payload_bytes_digest);
 assert.equal(f.calls.dispatchBodies[0].attachment_payload_bytes_digest,createHash('sha256').update(f.turn.input).digest('hex'));
 assert.equal(state[candidate.request_id].attachment_payload_bytes_digest,f.calls.dispatchBodies[0].attachment_payload_bytes_digest);
});

test('existing canonical bridge wins over current browser state and exact bound URL is used',async()=>{
 const provenance={supplied:{conversation_url:'https://chatgpt.com/c/native-existing',creation_mode:'AUTO'}};
 const bridge={bridge_id:'bridge-existing',conversation_id:candidate.conversation_id,external_thread_ref:'native-existing',external_system:'CHATGPT_SAAS',created_at:1,provenance_json:JSON.stringify(provenance),context_snapshot_digest:candidate.context_digest,authority_effect:'NONE'};
 const f=fixture({bridges:[bridge]});f.consumer.resume('test');await f.consumer.tick();
 assert.equal(f.calls.browser.filter(x=>x[0]==='create').length,0);
 const sends=f.calls.browser.filter(x=>x[0]==='send');assert.equal(sends.length,1);
 assert.equal(sends[0][1],'https://chatgpt.com/c/native-existing');
 assert.equal(f.calls.bridgeBodies.length,0);
 assert.equal(f.calls.dispatchBodies.length,1);
 assert.equal(f.calls.dispatchBodies[0].bridge_id,'bridge-existing');
 assert.equal(f.calls.dispatchBodies[0].external_thread_ref,'native-existing');
});

test('operator rotation provisions a fresh thread and preserves supersession provenance',async()=>{
 const provenance={supplied:{conversation_url:'https://chatgpt.com/c/native-old',creation_mode:'AUTO'}};
 const bridge={bridge_id:'bridge-old',conversation_id:candidate.conversation_id,external_thread_ref:'native-old',external_system:'CHATGPT_SAAS',created_at:1,provenance_json:JSON.stringify(provenance),context_snapshot_digest:candidate.context_digest,authority_effect:'NONE'};
 const f=fixture({bridges:[bridge]});f.consumer.resume('test');f.consumer.requestRotate(candidate.conversation_id);await f.consumer.tick();
 assert.equal(f.calls.browser.filter(x=>x[0]==='create').length,1);
 assert.equal(f.calls.bridgeBodies[0].provenance.supersedes_bridge_id,'bridge-old');
});

test('canonical identity mismatch fails closed before browser send',async()=>{
 const f=fixture();f.turn.input=f.turn.input.replace('correlation_id=corr-1','correlation_id=corr-wrong');
 f.consumer.resume('test');await f.consumer.tick();
 assert.equal(f.calls.browser.length,0);
 assert.match(f.consumer.lastError,/CANONICAL_TURN_IDENTITY_MISMATCH_CORRELATION_ID/);
});


test('autonomous SaaS consumer dispatches at most one candidate per tick and preserves fair cursor',async()=>{
 const f=fixture();
 const ids=['saas-first','saas-second','saas-third'];
 const seen=[];
 f.consumer._discoverTurns=async()=>{};
 f.consumer.panel=async(path)=>{
  assert.equal(path,'/api/conversations/saas/pending?limit=128');
  return {candidates:ids.map(request_id=>({request_id})),authority_effect:'NONE'};
 };
 f.consumer._dispatch=async(candidate)=>seen.push(candidate.request_id);
 f.consumer.resume('test');
 await f.consumer.tick();
 assert.deepEqual(seen,['saas-first']);
 assert.equal(f.consumer.status().max_dispatches_per_tick,1);
 assert.equal(f.consumer.status().pending_candidates_last_tick,3);
 assert.equal(f.consumer.status().dispatch_scan_cursor,1);
 assert.equal(f.store.setting('canonical_dispatch_scan_cursor'),'1');
 await f.consumer.tick();
 await f.consumer.tick();
 await f.consumer.tick();
 assert.deepEqual(seen,['saas-first','saas-second','saas-third','saas-first']);
 assert.equal(f.store.setting('canonical_dispatch_scan_cursor'),'1');
});

test('durable dispatch cursor survives consumer process re-instantiation',async()=>{
 const f=fixture();
 f.consumer.scanCursor=5;
 f.consumer._persist();
 const current=f.consumer;
 const resumed=new CanonicalConversationSaaSConsumer({
  store:f.store,panel:current.panel,mc:current.mc,
  ingress:current.ingress,browser:current.browser,
  projectUrl:current.projectUrl,now:()=>1000,
 });
 assert.equal(resumed.scanCursor,5);
 assert.equal(resumed.status().authority_effect,'NONE');
});

test('create-project timeout after uncertain UI send is SEND_UNKNOWN and never replayed',async()=>{
 const f=fixture();
 let externalAttempts=0;
 f.consumer.browser.createProjectConversationWithPrompt=async(prompt,admitted)=>{
  assert.equal(admitted(),true);
  externalAttempts++;
  throw Error('BROWSER_WAIT_TIMEOUT');
 };
 f.consumer.resume('test');
 await f.consumer.tick();
 let state=JSON.parse(f.store.setting('canonical_dispatch_map'))[candidate.request_id];
 assert.equal(state.state,'SEND_UNKNOWN');
 assert.equal(state.uncertainty_reason,'PROVISIONING_SEND_OUTCOME_UNKNOWN');
 assert.equal(f.consumer.status().state,'OPERATOR_REQUIRED');
 assert.equal(externalAttempts,1);
 await f.consumer.tick();
 state=JSON.parse(f.store.setting('canonical_dispatch_map'))[candidate.request_id];
 assert.equal(state.state,'SEND_UNKNOWN');
 assert.equal(externalAttempts,1);
 assert.equal(f.consumer.lastDecision.stage,'SEND_UNKNOWN_RECONCILE_FIRST');
});

test('stale PROVISIONING intent from interrupted process cannot re-send SaaS message',async()=>{
 const f=fixture();
 f.consumer.dispatchMap[candidate.request_id]={state:'PROVISIONING',started_at:123};
 f.consumer._persist();
 f.consumer.resume('test');
 await f.consumer.tick();
 const state=JSON.parse(f.store.setting('canonical_dispatch_map'))[candidate.request_id];
 assert.equal(state.state,'SEND_UNKNOWN');
 assert.equal(state.uncertainty_reason,'UNACKNOWLEDGED_EXTERNAL_SEND');
 assert.equal(f.calls.browser.length,0);
 assert.equal(f.consumer.status().state,'OPERATOR_REQUIRED');
});

test('stale DISPATCHING intent from interrupted process cannot re-send SaaS message',async()=>{
 const provenance={supplied:{conversation_url:'https://chatgpt.com/c/native-existing',creation_mode:'AUTO'}};
 const bridge={bridge_id:'bridge-existing',conversation_id:candidate.conversation_id,
  external_thread_ref:'native-existing',external_system:'CHATGPT_SAAS',created_at:1,
  provenance_json:JSON.stringify(provenance),context_snapshot_digest:candidate.context_digest,
  authority_effect:'NONE'};
 const f=fixture({bridges:[bridge]});
 f.consumer.dispatchMap[candidate.request_id]={
  state:'DISPATCHING',bridge_id:bridge.bridge_id,
  external_thread_ref:bridge.external_thread_ref,started_at:123,
 };
 f.consumer._persist();
 f.consumer.resume('test');
 await f.consumer.tick();
 const state=JSON.parse(f.store.setting('canonical_dispatch_map'))[candidate.request_id];
 assert.equal(state.state,'SEND_UNKNOWN');
 assert.equal(f.calls.browser.length,0);
 assert.equal(f.calls.dispatchBodies.length,0);
 await f.consumer.tick();
 assert.equal(f.calls.browser.length,0);
});

test('a candidate error yields next fair candidate rather than starving the queue',async()=>{
 const f=fixture();
 const seen=[];
 f.consumer._discoverTurns=async()=>{};
 f.consumer.panel=async()=>({
  candidates:[{request_id:'saas-bad'},{request_id:'saas-good'}],
  authority_effect:'NONE',
 });
 f.consumer._dispatch=async candidate=>{
  seen.push(candidate.request_id);
  if(candidate.request_id==='saas-bad')throw Error('INDEPENDENT_BAD_CANDIDATE');
 };
 f.consumer.resume('test');
 await f.consumer.tick();
 assert.equal(f.consumer.status().state,'DEGRADED');
 assert.equal(f.store.setting('canonical_dispatch_scan_cursor'),'1');
 await f.consumer.tick();
 assert.deepEqual(seen,['saas-bad','saas-good']);
 assert.equal(f.store.setting('canonical_dispatch_scan_cursor'),'0');
});


test('one unresolved external send blocks subsequent candidate until canonical receipt',async()=>{
 const f=fixture();
 const second={...candidate,request_id:'saas-second'};
 const sent=[];
 f.consumer._discoverTurns=async()=>{};
 f.consumer.panel=async()=>({candidates:[candidate,second]});
 f.consumer._dispatch=async c=>{
  sent.push(c.request_id);
  if(c.request_id===candidate.request_id){
   f.consumer.dispatchMap[c.request_id]={state:'BOUND_SENT',sent_at:1000};
   f.consumer._persist();
  }
 };
 f.consumer.resume('test');
 await f.consumer.tick();
 assert.deepEqual(sent,[candidate.request_id]);
 await f.consumer.tick();
 assert.deepEqual(sent,[candidate.request_id,candidate.request_id]);
 assert.equal(f.consumer.scanCursor,1);
 f.consumer.dispatchMap[candidate.request_id]={state:'RECONCILED',observed_at:2000};
 f.consumer._persist();
 await f.consumer.tick();
 assert.deepEqual(sent,[candidate.request_id,candidate.request_id,'saas-second']);
});

test('resolved request absent from pending is released only by exact response and receipt digests',async()=>{
 const f=fixture();
 const old='saas-old-before-restart';
 const sent=[];
 f.consumer._discoverTurns=async()=>{};
 f.consumer.panel=async()=>({candidates:[candidate]});
 f.consumer.mc=async path=>{
  assert.equal(path,'/api/v3/saas-broker/requests/'+old);
  return {request_id:old,status:'RESPONDED',authority_effect:'NONE',
    response_digest:'b'.repeat(64),receipt_digest:'c'.repeat(64)};
 };
 f.consumer._dispatch=async row=>sent.push(row.request_id);
 f.consumer.dispatchMap[old]={state:'BOUND_SENT'};
 f.consumer._persist();
 f.consumer.resume('test');
 await f.consumer.tick();
 assert.equal(f.consumer.dispatchMap[old].state,'RECONCILED');
 assert.deepEqual(sent,[]);
 await f.consumer.tick();
 assert.deepEqual(sent,[candidate.request_id]);
});

test('response status without matching receipt cannot release prior send gate',async()=>{
 const f=fixture();
 const old='saas-unverified-prior';
 let sends=0;
 f.consumer._discoverTurns=async()=>{};
 f.consumer.panel=async()=>({candidates:[candidate]});
 f.consumer.mc=async()=>({request_id:old,status:'RESPONDED',authority_effect:'NONE'});
 f.consumer._dispatch=async()=>{sends++};
 f.consumer.dispatchMap[old]={state:'SEND_COMMITTED'};
 f.consumer._persist();
 f.consumer.resume('test');
 await f.consumer.tick();
 assert.equal(f.consumer.dispatchMap[old].state,'SEND_COMMITTED');
 assert.equal(f.consumer.status().state,'OPERATOR_REQUIRED');
 assert.equal(f.consumer.lastDecision.stage,'PRIOR_EXTERNAL_SEND_NOT_RECONCILED');
 assert.equal(sends,0);
});

test('missing prior broker receipt persists WAITING_PRIOR_READBACK instead of claiming empty queue',async()=>{
 const f=fixture();
 const old='saas-prior-no-receipt';
 f.consumer._discoverTurns=async()=>{};
 f.consumer.panel=async()=>({candidates:[]});
 f.consumer.mc=async()=>({request_id:old,status:'WAITING_SUPERVISOR',authority_effect:'NONE'});
 f.consumer.dispatchMap[old]={state:'RESULT_OBSERVED'};
 f.consumer._persist();
 f.consumer.resume('test');
 await f.consumer.tick();
 assert.equal(f.consumer.status().state,'WAITING_PRIOR_READBACK');
 assert.equal(f.consumer.lastDecision.stage,'PRIOR_EXTERNAL_SEND_NOT_RECONCILED');
});

test('multiple unresolved external sends require operator and forbid new send',async()=>{
 const f=fixture();
 let sends=0;
 f.consumer._discoverTurns=async()=>{};
 f.consumer.panel=async()=>({candidates:[candidate]});
 f.consumer._dispatch=async()=>{sends++};
 f.consumer.dispatchMap['saas-old-1']={state:'PROVISIONING'};
 f.consumer.dispatchMap['saas-old-2']={state:'SEND_UNKNOWN'};
 f.consumer._persist();
 f.consumer.resume('test');
 await f.consumer.tick();
 assert.equal(sends,0);
 assert.equal(f.consumer.status().state,'OPERATOR_REQUIRED');
 assert.equal(f.consumer.lastDecision.stage,'MULTIPLE_UNRESOLVED_EXTERNAL_SENDS');
 assert.equal(f.consumer.lastDecision.count,2);
});

test('already RESPONDED broker status must contain both verified digests',async()=>{
 const f=fixture();
 let sends=0;
 f.consumer.mc=async()=>({request_id:candidate.request_id,status:'RESPONDED',
  authority_effect:'NONE',response_digest:'d'.repeat(64)});
 f.consumer.browser.createProjectConversationWithPrompt=async()=>{sends++};
 f.consumer.resume('test');
 await f.consumer.tick();
 assert.equal(f.consumer.dispatchMap[candidate.request_id],undefined);
 assert.equal(sends,0);
 assert.equal(f.consumer.status().state,'OPERATOR_REQUIRED');
 assert.equal(f.consumer.lastDecision.stage,'RESPONSE_RECEIPT_UNVERIFIED');
});


test('existing exact-bridge send timeout is SEND_UNKNOWN and requires operator before retry',async()=>{
 const provenance={supplied:{conversation_url:'https://chatgpt.com/c/native-existing',creation_mode:'AUTO'}};
 const bridge={bridge_id:'bridge-existing',conversation_id:candidate.conversation_id,
  external_thread_ref:'native-existing',external_system:'CHATGPT_SAAS',created_at:1,
  provenance_json:JSON.stringify(provenance),context_snapshot_digest:candidate.context_digest,
  authority_effect:'NONE'};
 const f=fixture({bridges:[bridge]});
 let attempts=0;
 f.consumer.browser.sendToConversation=async()=>{
  attempts++;
  throw Error('BROWSER_WAIT_TIMEOUT');
 };
 f.consumer.resume('test');
 await f.consumer.tick();
 const row=JSON.parse(f.store.setting('canonical_dispatch_map'))[candidate.request_id];
 assert.equal(row.state,'SEND_UNKNOWN');
 assert.equal(f.consumer.status().state,'OPERATOR_REQUIRED');
 assert.equal(f.consumer.lastDecision.stage,'SEND_UNKNOWN_RECONCILE_FIRST');
 assert.equal(attempts,1);
 await f.consumer.tick();
 assert.equal(attempts,1);
});
