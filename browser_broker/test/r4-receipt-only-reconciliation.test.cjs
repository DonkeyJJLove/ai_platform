'use strict';
const test=require('node:test');
const assert=require('node:assert/strict');
const {CanonicalConversationSaaSConsumer}=require('../src/canonical-conversation-consumer.cjs');
const SHA=prefix=>prefix.repeat(64);
class Store{
 constructor(){this.data=new Map([['canonical_consumer_enabled','false']]);this.writes=[]}
 setting(key){return this.data.get(key)}
 setSetting(key,value){this.writes.push({key,value});this.data.set(key,String(value))}
}
const mk=(n)=>'saas-receipt-r'+String(n);
const states=Array.from({length:10},(_,i)=>i===9?'SEND_COMMITTED':'RESULT_OBSERVED');
function fixture(opts={}){
 const store=new Store(),calls={mc:[],panel:[],ingress:[],browser:[]};
 const dispatch={};
 for(let i=0;i<10;i++)dispatch[mk(i)]={state:states[i],started_at:1000+i,bridge_id:'bridge-'+i};
 store.data.set('canonical_dispatch_map',JSON.stringify(dispatch));
 let waiting;
 const gate=new Promise(r=>{waiting=r});
 const browser=new Proxy({}, {get(t,k){return async()=>{calls.browser.push(k);throw Error('BROWSER_MUST_NEVER_SEND')}}});
 const panel=async(...args)=>{calls.panel.push(args);throw Error('PANEL_MUTATION_PROHIBITED')};
 const ingress=async(...args)=>{calls.ingress.push(args);throw Error('INGRESS_MUTATION_PROHIBITED')};
 const mc=async url=>{
  calls.mc.push(url);
  if(opts.block)await gate;
  if(opts.failAt!==undefined && url.endsWith(mk(opts.failAt)))throw Error('REMOTE_UNAVAILABLE');
  const rid=url.split('/').at(-1);
  const b={request_id:rid,status:'RESPONDED',authority_effect:'NONE',
   response_digest:SHA('a'),receipt_digest:SHA('b')};
  if(opts.badAt!==undefined&&rid===mk(opts.badAt))b.receipt_digest='malformed';
  if(opts.conflictAt!==undefined&&rid===mk(opts.conflictAt))b.receipt_digest=SHA('c');
  return b;
 };
 const consumer=new CanonicalConversationSaaSConsumer({
  store,panel,ingress,mc,browser,projectUrl:'https://chatgpt.com/g/g-p-lion-example/project',
  now:()=>1700000000,
 });
 if(opts.conflictAt!==undefined)consumer.dispatchMap[mk(opts.conflictAt)].receipt_digest=SHA('b');
 return {consumer,store,calls,release:waiting};
}
test('ten verified prior SaaS receipts reconcile with one LOCAL settings write and no external sends',async()=>{
 const x=fixture();
 assert.equal(x.consumer.enabled,false);
 const result=await x.consumer.reconcileReceiptsOnly();
 assert.equal(result.result,'PASS_RECEIPT_ONLY_RECONCILED');
 assert.equal(result.reconciled,10);assert.equal(result.unresolved,0);
 assert.equal(result.external_send_count,0);assert.equal(result.authority_effect,'NONE');
 assert.equal(x.calls.mc.length,10);
 assert.deepEqual(x.calls.browser,[]);assert.deepEqual(x.calls.panel,[]);assert.deepEqual(x.calls.ingress,[]);
 assert.equal(x.store.writes.length,1);
 assert.equal(x.store.writes[0].key,'canonical_dispatch_map');
 assert.equal(x.store.setting('canonical_consumer_enabled'),'false');
 assert.equal(x.consumer.state,'STOPPED');
 const persisted=JSON.parse(x.store.setting('canonical_dispatch_map'));
 assert.equal(Object.values(persisted).filter(v=>v.state==='RECONCILED').length,10);
 assert(Object.values(persisted).every(v=>v.receipt_reconciliation==='EXACT_CANONICAL_BROKER_READBACK_NO_SEND'));
 const repeated=await x.consumer.reconcileReceiptsOnly();
 assert.equal(repeated.result,'PASS_ALREADY_RECONCILED');
 assert.equal(x.store.writes.length,1);
 assert.equal(x.calls.mc.length,10);
});
test('bad final response digest rejects entire batch atomically without partial persistence',async()=>{
 const x=fixture({badAt:9});
 const before=JSON.stringify(x.consumer.dispatchMap);
 const outcome=await x.consumer.reconcileReceiptsOnly();
 assert.equal(outcome.result,'BLOCKED_RECEIPT_ONLY_UNVERIFIED_RESPONSE');
 assert.equal(outcome.reconciled,0);
 assert.equal(x.store.writes.length,0);
 assert.equal(JSON.stringify(x.consumer.dispatchMap),before);
 assert.equal(x.consumer.enabled,false);
});
test('digest conflicts fail closed without overwriting historical local receipts',async()=>{
 const x=fixture({conflictAt:2});
 const prior=JSON.stringify(x.consumer.dispatchMap);
 const result=await x.consumer.reconcileReceiptsOnly();
 assert.equal(result.result,'BLOCKED_RECEIPT_ONLY_DIGEST_CONFLICT');
 assert.equal(result.reconciled,0);
 assert.equal(JSON.stringify(x.consumer.dispatchMap),prior);
 assert.equal(x.store.writes.length,0);
});
test('remote transport error is UNKNOWN; never replay or mark success',async()=>{
 const x=fixture({failAt:5});
 await assert.rejects(()=>x.consumer.reconcileReceiptsOnly(),/REMOTE_UNAVAILABLE/);
 assert.equal(x.store.writes.length,0);
 assert.equal(x.consumer.running,false);
 assert.equal(x.consumer.enabled,false);
 assert.equal(x.calls.browser.length,0);
});
test('paused-only invariant denies receipt reconciliation when automatic sender active',async()=>{
 const x=fixture();x.consumer.enabled=true;
 await assert.rejects(()=>x.consumer.reconcileReceiptsOnly(),/PAUSED_EXCLUSIVE/);
 assert.equal(x.calls.mc.length,0);
 assert.equal(x.store.writes.length,0);
});
test('single in-flight reconciliation prevents concurrent mutation',async()=>{
 const x=fixture({block:true});
 const promise=x.consumer.reconcileReceiptsOnly();
 await assert.rejects(()=>x.consumer.reconcileReceiptsOnly(),/PAUSED_EXCLUSIVE/);
 x.release();
 const v=await promise;
 assert.equal(v.reconciled,10);
 assert.equal(x.store.writes.length,1);
});
test('bounded manual batch refuses more outstanding than explicit limit',async()=>{
 const x=fixture();
 const v=await x.consumer.reconcileReceiptsOnly({limit:9});
 assert.equal(v.result,'BLOCKED_RECEIPT_ONLY_BATCH_LIMIT');
 assert.equal(v.unresolved,10);
 assert.equal(x.calls.mc.length,0);
 assert.equal(x.store.writes.length,0);
});
test('untrusted response cannot become verified with only a declared status',async()=>{
 const x=fixture();
 x.consumer.mc=async rid=>({request_id:rid.split('/').at(-1),status:'RESPONDED',
  authority_effect:'NONE',response_digest:SHA('a')});
 const v=await x.consumer.reconcileReceiptsOnly();
 assert.equal(v.result,'BLOCKED_RECEIPT_ONLY_UNVERIFIED_RESPONSE');
 assert.equal(x.store.writes.length,0);
});
