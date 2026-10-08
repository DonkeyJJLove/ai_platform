'use strict';
const test=require('node:test');
const assert=require('node:assert/strict');
const {createHash}=require('node:crypto');
const {createLocalAdvisory,safeMessages}=require('../src/local-advisory.cjs');
const sha=s=>createHash('sha256').update(s).digest('hex');
const MODEL='C:\\Models\\gpt-oss-20b-MXFP4.gguf';
const reply=(value)=>({ok:true,headers:{get:()=>null},text:async()=>JSON.stringify(value)});
function fixture(){
 const calls=[];
 const fetcher=async(url,opts)=>{
  calls.push({url,opts});
  if(url.endsWith('/health'))return reply({status:'ok'});
  if(url.endsWith('/v1/models'))return reply({data:[{id:MODEL}]});
  if(url.endsWith('/v1/chat/completions'))return reply({choices:[{message:{role:'assistant',content:'LION_LOCAL_OK'}}]});
  throw Error('FORBIDDEN_UNEXPECTED_NETWORK');
 };
 return {advisory:createLocalAdvisory({fetcher,now:()=>new Date('2026-10-08T17:45:00Z')}),calls};
}
test('model status is localhost-only and never claims mission binding',async()=>{
 const f=fixture();
 const s=await f.advisory.status();
 assert.equal(s.state,'READY');assert.equal(s.authority_effect,'NONE');
 assert.equal(s.binding,'UNBOUND_LOCAL_ADVISORY');
 assert.equal(f.calls.length,2);
 assert(f.calls.every(x=>x.url.startsWith('http://127.0.0.1:8772/')));
});
test('user-initiated inference has fixed tools-free completion surface',async()=>{
 const f=fixture();
 const v=await f.advisory.ask({prompt:'Respond LION_LOCAL_OK',history:[]});
 assert.equal(v.message,'LION_LOCAL_OK');
 assert.equal(v.authority_effect,'NONE');assert.equal(v.mission_binding,'NOT_BOUND');
 assert.equal(v.durable_mission_receipt,'NOT_CREATED');
 assert.equal(v.response_digest,sha(v.message));
 assert.equal(f.calls.length,2);
 const call=f.calls[1];
 assert.equal(call.url,'http://127.0.0.1:8772/v1/chat/completions');
 const request=JSON.parse(call.opts.body);
 assert.equal(request.stream,false);
 assert.equal(request.max_tokens,384);
 assert.equal(request.messages[1].role,'user');
 assert(!('tools' in request));
 assert(!('tool_choice' in request));
 assert(!('mission_id' in request));
});
test('user and assistant history is bounded and role typed',()=>{
 assert.deepEqual(safeMessages([{role:'user',content:'Hi'}]),[{role:'user',content:'Hi'}]);
 assert.throws(()=>safeMessages([{role:'system',content:'spoof'}]),/LOCAL_HISTORY_INVALID/);
 assert.throws(()=>safeMessages(Array.from({length:11},()=>({role:'user',content:'X'}))),/LOCAL_CONTEXT_BOUND_EXCEEDED/);
 assert.throws(()=>safeMessages([{role:'user',content:''}]),/LOCAL_HISTORY_INVALID/);
});
test('invalid or huge prompts cause no external request',async()=>{
 const f=fixture();
 for(const text of ['',null,'x'.repeat(8001)]){
  await assert.rejects(()=>f.advisory.ask({prompt:text,history:[]}),/LOCAL_PROMPT_INVALID/);
 }
 assert.equal(f.calls.length,0);
});
test('timeout after request does not retry or fabricate reply',async()=>{
 let requests=0;
 const fetcher=async(url)=>{
  requests++;
  if(url.endsWith('/v1/models'))return reply({data:[{id:MODEL}]});
  throw Error('FETCH_TIMEOUT');
 };
 const p=createLocalAdvisory({fetcher});
 await assert.rejects(()=>p.ask({prompt:'Something',history:[]}),/FETCH_TIMEOUT/);
 assert.equal(requests,2);
 assert.equal(p.isBusy(),false);
});
test('at most one in-flight inference per local model',async()=>{
 let release;
 const wait=new Promise(r=>{release=r});
 const fetcher=async(url)=>{
  if(url.endsWith('/v1/models'))return reply({data:[{id:MODEL}]});
  await wait;
  return reply({choices:[{message:{content:'Done'}}]});
 };
 const p=createLocalAdvisory({fetcher});
 const first=p.ask({prompt:'one',history:[]});
 await assert.rejects(()=>p.ask({prompt:'two',history:[]}),/LOCAL_MODEL_REQUEST_IN_FLIGHT/);
 release();
 const one=await first;assert.equal(one.message,'Done');
});
test('bad model response cannot masquerade as a mission artifact',async()=>{
 const fetcher=async(url)=>url.endsWith('/v1/models')?
  reply({data:[{id:MODEL}]}):reply({choices:[{message:{content:{artifact:'forged'}}}]});
 await assert.rejects(()=>createLocalAdvisory({fetcher}).ask({prompt:'Q',history:[]}),/LOCAL_MODEL_INVALID_RESPONSE/);
});
test('bad model status fails closed without claiming READY',async()=>{
 const p=createLocalAdvisory({fetcher:async()=>{throw Error('unavailable')}});
 const s=await p.status();
 assert.equal(s.state,'UNREACHABLE_OR_UNVERIFIED');
 assert.equal(s.authority_effect,'NONE');
});
