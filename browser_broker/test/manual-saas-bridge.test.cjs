'use strict';
const test=require('node:test');
const assert=require('node:assert/strict');
const {CanonicalConversationSaaSConsumer}=require('../src/canonical-conversation-consumer.cjs');
const {conversationReport}=require('../src/conversation.cjs');

const PROJECT='https://chatgpt.com/g/g-p-6a91cabd3f208191a37f295819e9f75b-lion-evolusion/project';
const CHAT='https://chatgpt.com/g/g-p-6a91cabd3f208191a37f295819e9f75b-lion-evolusion/c/manual-thread-001';
const CONVERSATION='conv-manual-1';

function fixture(){
 let state={conversation_id:CONVERSATION,state:'UNBOUND',
  current_binding:{mission_id:null,binding_epoch:1,context_digest:'a'.repeat(64)},
  external_bridges:[],lanes:[]};
 let url=CHAT;
 let postCount=0,sendCount=0,reads=0,postReadFails=false;
 const values=new Map();
 const store={setting:k=>values.get(k),setSetting:(k,v)=>values.set(k,String(v))};
 const browser={
  bindingReport:()=>conversationReport(url,PROJECT),
  async createProjectConversationWithPrompt(){sendCount++;throw Error('SEND_FORBIDDEN_IN_MANUAL_LINK_TEST')},
  async sendToConversation(){sendCount++;throw Error('SEND_FORBIDDEN_IN_MANUAL_LINK_TEST')},
 };
 const panel=async(route,method='GET',body)=>{
  assert.equal(route,'/api/conversations/'+CONVERSATION+(method==='POST'?'/bridges':''));
  if(method==='GET'){
   reads++;if(postReadFails&&postCount>0)throw Error('READBACK_UNAVAILABLE');
   return state;
  }
  postCount++;
  assert.equal(method,'POST');
  const row={
   bridge_id:'bridge-manual-001',conversation_id:CONVERSATION,
   external_thread_ref:body.external_thread_ref,external_system:body.external_system,
   context_snapshot_digest:body.context_snapshot_digest,authority_effect:'NONE',
   provenance_json:JSON.stringify({supplied:body.provenance}),
  };
  state={...state,external_bridges:[...state.external_bridges,row]};
  return row;
 };
 const consumer=new CanonicalConversationSaaSConsumer({
  store,panel,mc:async()=>{throw Error('MC_NOT_USED')},
  ingress:async()=>{throw Error('INGRESS_NOT_USED')},
  browser,projectUrl:PROJECT,
 });
 consumer.stop('MANUAL_BIND_UNIT_TEST');
 return {
  consumer,setUrl:value=>{url=value},setState:value=>{state=value},
  state:()=>state,get postCount(){return postCount},get sendCount(){return sendCount},
  get reads(){return reads},set postReadFails(value){postReadFails=value},
 };
}

test('manual exact project thread binds only with operator confirmation and independent post-write readback',async()=>{
 const f=fixture();
 let confirmation;
 const result=await f.consumer.bindExistingProjectThread(CONVERSATION,async input=>{
  confirmation=input;return true;
 });
 assert.equal(result.state,'BRIDGE_RECORDED_SAAS_E2E_UNVERIFIED');
 assert.equal(result.external_send_count,0);
 assert.equal(result.authority_effect,'NONE');
 assert.equal(confirmation.conversation_id,CONVERSATION);
 assert.equal(confirmation.external_thread_ref,'manual-thread-001');
 assert.equal(confirmation.binding_epoch,1);
 assert.equal(f.postCount,1);
 assert.equal(f.sendCount,0);
 assert.equal(f.state().external_bridges.length,1);
 const bridge=f.state().external_bridges[0];
 const provenance=JSON.parse(bridge.provenance_json).supplied;
 assert.equal(provenance.creation_mode,'EXPLICIT_NATIVE_OPERATOR_EXISTING_THREAD');
 assert.equal(provenance.bridge_state,'RECORDED_UNVERIFIED_E2E');
 assert.equal(provenance.external_send_count,0);
 assert.equal(bridge.context_snapshot_digest,'a'.repeat(64));
 await assert.rejects(
  f.consumer.bindExistingProjectThread(CONVERSATION,async()=>true),
  /CANONICAL_BIND_EXISTING_BRIDGE_REQUIRES_RECONCILIATION/);
 assert.equal(f.postCount,1);
});
test('operator decline leaves all canonical and browser objects unchanged',async()=>{
 const f=fixture();
 const out=await f.consumer.bindExistingProjectThread(CONVERSATION,async()=>false);
 assert.equal(out.state,'OPERATOR_DECLINED');assert.equal(f.postCount,0);
 assert.equal(f.sendCount,0);
});
test('cannot bind a project landing page, cross-project thread, or direct c route',async()=>{
 for(const url of [
  PROJECT,
  'https://chatgpt.com/g/g-p-other-project/c/unknown',
  'https://chatgpt.com/c/unverified-manual',
 ]){
  const f=fixture();f.setUrl(url);
  await assert.rejects(
   f.consumer.bindExistingProjectThread(CONVERSATION,async()=>true),
   /CANONICAL_BIND_PROJECT_THREAD_NOT_OBSERVED/);
  assert.equal(f.postCount,0);
 }
});
test('no binding when canonical mission epoch or browser URL changes during native confirmation',async()=>{
 {
  const f=fixture();
  await assert.rejects(f.consumer.bindExistingProjectThread(CONVERSATION,async()=>{
   f.setUrl(CHAT.replace('manual-thread-001','different-thread'));return true;
  }),/CANONICAL_BIND_BROWSER_NAVIGATED_DURING_CONFIRMATION/);
  assert.equal(f.postCount,0);
 }
 {
  const f=fixture();
  await assert.rejects(f.consumer.bindExistingProjectThread(CONVERSATION,async()=>{
   f.setState({...f.state(),current_binding:{...f.state().current_binding,binding_epoch:2}});
   return true;
  }),/CANONICAL_BIND_EPOCH_OR_CONTEXT_DRIFT/);
  assert.equal(f.postCount,0);
 }
});
test('no silent binding when any previous SaaS lane exists, including an expired request',async()=>{
 for(const state of ['ACTIVE','CLOSED','FAILED']){
  const f=fixture();
  f.setState({...f.state(),lanes:[{provider:'SAAS',state}]});
  await assert.rejects(f.consumer.bindExistingProjectThread(CONVERSATION,async()=>true),
   /CANONICAL_BIND_PRIOR_SAAS_LANE_REQUIRES_RECONCILIATION/);
  assert.equal(f.postCount,0);
 }
});
test('consumer must be stopped; native binding never serves as a broker resume',async()=>{
 const f=fixture();f.consumer.resume('NEGATIVE_ONLY');
 await assert.rejects(f.consumer.bindExistingProjectThread(CONVERSATION,async()=>true),
  /CANONICAL_BIND_REQUIRES_PAUSED_CONSUMER/);
 assert.equal(f.postCount,0);assert.equal(f.sendCount,0);
});
test('readback uncertainty after a possible commit is explicit, never blindly retried',async()=>{
 const f=fixture();f.postReadFails=true;
 await assert.rejects(f.consumer.bindExistingProjectThread(CONVERSATION,async()=>true),
  /CANONICAL_BIND_EFFECT_UNKNOWN_READBACK_REQUIRED/);
 assert.equal(f.postCount,1);assert.equal(f.state().external_bridges.length,1);
 assert.equal(f.sendCount,0);
});
test('concurrent operator confirmations cannot create split bindings',async()=>{
 const f=fixture();let proceed;
 const pending=f.consumer.bindExistingProjectThread(CONVERSATION,()=>new Promise(resolve=>{proceed=resolve}));
 await new Promise(resolve=>setImmediate(resolve));
 await assert.rejects(f.consumer.bindExistingProjectThread(CONVERSATION,async()=>true),
  /CANONICAL_BIND_ALREADY_IN_FLIGHT/);
 proceed(false);
 const out=await pending;assert.equal(out.state,'OPERATOR_DECLINED');
 assert.equal(f.postCount,0);
});
