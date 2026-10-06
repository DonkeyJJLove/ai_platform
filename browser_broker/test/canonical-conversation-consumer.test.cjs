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
