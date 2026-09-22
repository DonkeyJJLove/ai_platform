'use strict';
const {createHash}=require('node:crypto');
const {conversation}=require('./conversation.cjs');
const TASK='908c81f467d245ac212540f47e5914b6cb114561e6970f83d80fc88618680512';
const hash=x=>createHash('sha256').update(x).digest('hex');
function envelope(v,projectUrl,now=Date.now()){
 const keys=['request_id','mission_id','panel_thread_id','turn_id','turn_request_hash','parent_event_id','conversation_url','task_sha256','deadline_at','claim_generation'];
 if(!v||typeof v!=='object'||Array.isArray(v)||Object.keys(v).some(k=>!keys.includes(k)))throw Error('INVALID_ENVELOPE');
 const out={};
 for(const k of ['request_id','mission_id','panel_thread_id','turn_id']){
  if(k==='mission_id'&&v[k]===null){out[k]=null;continue}
  if(typeof v[k]!=='string'||!/^[a-zA-Z0-9_-]{1,160}$/.test(v[k]))throw Error('INVALID_ID');out[k]=v[k];
 }
 if(!/^turn_[a-zA-Z0-9-]+$/.test(v.turn_id)||!/^saas-[a-zA-Z0-9-]+$/.test(v.request_id))throw Error('INVALID_ID');
 if(v.parent_event_id!==undefined){if(v.parent_event_id!=='saas_request:'+v.request_id)throw Error('INVALID_PARENT_EVENT');out.parent_event_id=v.parent_event_id}
 if(!/^[a-f0-9]{64}$/.test(v.turn_request_hash)||v.task_sha256!==TASK)throw Error('INVALID_BINDING');
 if(!Number.isSafeInteger(v.deadline_at)||v.deadline_at<=now||v.deadline_at>now+1200000)throw Error('INVALID_DEADLINE');
 if(v.claim_generation!==undefined){if(!Number.isSafeInteger(v.claim_generation)||v.claim_generation<1)throw Error('INVALID_CLAIM');out.claim_generation=v.claim_generation}
 return {...out,turn_request_hash:v.turn_request_hash,conversation_url:conversation(v.conversation_url,projectUrl),task_sha256:TASK,deadline_at:v.deadline_at};
}
function matches(v,turn){return !!turn&&turn.turn_id===v.turn_id&&turn.thread_id===v.panel_thread_id&&turn.mission_id===v.mission_id&&turn.command_id==='MC-'+v.request_id&&turn.request_hash===v.turn_request_hash&&(v.parent_event_id===undefined||turn.parent_event_id===v.parent_event_id);}
function brokerAllows(v,request,now=Date.now()){
 const deadline=Date.parse(request?.deadline_at||request?.expires_at||'');
 const state=v.claim_generation===undefined?['CREATED','QUEUED','WAITING_SUPERVISOR','PENDING'].includes(request?.status):request?.status==='CLAIMED'&&request.claim_generation===v.claim_generation&&Date.parse(request.claim_expires_at)>now;
 const scope=v.mission_id!==null||request?.scope_type==='THREAD'&&request.scope_id===v.panel_thread_id&&request.authority_effect==='NONE';
 return !!request&&scope&&request.request_id===v.request_id&&request.mission_id===v.mission_id&&request.thread_id===v.panel_thread_id&&state&&Number.isFinite(deadline)&&deadline>now&&v.deadline_at<=deadline;
}
const scopeKey=v=>v.mission_id===null?'THREAD:'+v.panel_thread_id:v.mission_id;
function prompt(v){return `Use the SentinelX connector only. Do not use LION-MCP-R2 or OpenAI Secure MCP Tunnel.\nTarget host: MOON.\n1. Call SentinelX sentinel_exec on MOON with command exactly:\n/usr/local/bin/lion-sentinelx-turn get ${v.turn_id}\n2. Read the returned JSON input field and answer that cognitive request.\n3. Call SentinelX sentinel_exec on MOON again with command:\n/usr/local/bin/lion-sentinelx-turn complete ${v.turn_id} chatgpt-saas-sentinelx '{"text":"<your answer>"}'\nThe final argument must be one valid shell-quoted JSON object with exactly one key: text.\nDo not call any other write tool.\nBroker request id: ${v.request_id}`;}
const webPreferences=partition=>({partition,nodeIntegration:false,nodeIntegrationInWorker:false,nodeIntegrationInSubFrames:false,contextIsolation:true,sandbox:true,webSecurity:true,allowRunningInsecureContent:false,webviewTag:false});
module.exports={TASK,hash,conversation,envelope,matches,brokerAllows,prompt,webPreferences,scopeKey};
