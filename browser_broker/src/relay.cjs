'use strict';
const {TASK,hash,conversation,matches,brokerAllows}=require('./contract.cjs');
const TRANSPORT='CHATGPT_OPENAI_SECURE_MCP_TUNNEL';
const TERMINAL=new Set(['RECONCILED','CANCELLED']);

// This adapter consumes only newly created requests in an explicitly bound scope.
// It never imports the old filesystem inbox or completes a model turn itself.
class Relay{
 constructor({store,browser,mc,ingress,scope,now=Date.now}){
  if(!scope||!/^LION-R19-[A-Za-z0-9_-]+$/.test(scope.mission_id)||!/^[A-Za-z0-9_-]{1,160}$/.test(scope.thread_id))throw Error('RELAY_SCOPE_REQUIRED');
  this.scope={...scope,conversation_url:conversation(scope.conversation_url,store.projectUrl)};
  this.store=store;this.browser=browser;this.mc=mc;this.ingress=ingress;this.now=now;
  this.since=now();this.running=false;this.state='STOPPED';this.lastError=null;
  // A restarted process never blindly repeats an interrupted external mutation.
  for(const r of store.handoffs())if(['CLAIM_INTENT','TURN_INTENT'].includes(r.state)){r.state='OPERATOR_REQUIRED';r.reason='INTERRUPTED_UPSTREAM_MUTATION';store.saveHandoff(r)}
 }
 save(r,state,extra={}){Object.assign(r,extra,{state,updated_at:this.now()});this.store.saveHandoff(r);this.state=state}
 sameScope(row){return row?.mission_id===this.scope.mission_id&&row.thread_id===this.scope.thread_id&&row.transport===TRANSPORT}
 async authorized(){
  if(this.store.stopped())return false;
  const m=await this.mc('/api/v3/missions/'+encodeURIComponent(this.scope.mission_id)+'/process');
  return !this.store.stopped()&&m.mission_id===this.scope.mission_id&&['AUTHORIZED','RUNNING'].includes(m.state)&&m.execution_preflight?.mission_readiness==='READY_BOUND';
 }
 async current(r){const row=await this.mc('/api/v3/saas-broker/requests/'+encodeURIComponent(r.request_id));if(!this.sameScope(row)||row.question_digest!==r.question_digest)throw Error('BROKER_IDENTITY_MISMATCH');return row}
 payload(row){return {command_id:'MC-'+row.request_id,mission_id:row.mission_id,session_id:'CHATGPT-SAAS',thread_id:row.thread_id,cursor:0,
  input:'LION Mission Control cognitive request. Authority effect: NONE.\nBroker request id: '+row.request_id+'\nQuestion: '+row.question+'\n\nAnswer the question and complete this exact LION turn with response.text and actor chatgpt-saas-mcp. Do not call any other write tool.',
  metadata:{source:'LION_MISSION_CONTROL',broker_request_id:row.request_id,thread_id:row.thread_id,transport:TRANSPORT,authority_effect:'NONE',task_sha256:TASK}}}
 async start(){
  if(!(await this.authorized())||!(await this.browser.ready({conversation_url:this.scope.conversation_url})))return;
  const records=this.store.handoffs();if(records.length>=18||records.filter(r=>r.mission_id===this.scope.mission_id).length>=6){this.state='TURN_LIMIT';return}
  const pending=await this.mc('/api/v3/saas-broker/pending');
  const row=(pending.requests||[]).find(x=>this.sameScope(x)&&['WAITING_SUPERVISOR','QUEUED'].includes(x.status)&&Date.parse(x.created_at)>=this.since&&Date.parse(x.deadline_at||x.expires_at)>this.now()&&!records.some(r=>r.request_id===x.request_id));
  if(!row){this.state='WAITING_NEW_SCOPED_REQUEST';return}
  if(!/^saas-[A-Za-z0-9-]+$/.test(row.request_id)||typeof row.question!=='string'||!row.question.trim()||hash(row.question)!==row.question_digest)throw Error('REQUEST_INTEGRITY_REQUIRED');
  if(!(await this.authorized()))return;
  const r={request_id:row.request_id,mission_id:row.mission_id,thread_id:row.thread_id,conversation_url:this.scope.conversation_url,question_digest:row.question_digest,deadline_at:Math.min(Date.parse(row.deadline_at||row.expires_at),this.now()+1200000)};
  this.save(r,'CLAIM_INTENT');
  try{
   const claim=await this.mc('/api/v3/saas-broker/requests/'+row.request_id+'/claim','POST',{});
   if(claim.request_id!==r.request_id||claim.question_digest!==r.question_digest||!Number.isSafeInteger(claim.claim_generation)||claim.claim_generation<1||typeof claim.response_token!=='string'||claim.response_token.length<32)throw Error('INVALID_CLAIM');
   this.save(r,'CLAIMED',{claim,turn_payload:this.payload(row)});
  }catch{this.save(r,'OPERATOR_REQUIRED',{reason:'CLAIM_OUTCOME_UNKNOWN'})}
 }
 async advance(r){
  if(r.mission_id!==this.scope.mission_id||r.thread_id!==this.scope.thread_id||r.conversation_url!==this.scope.conversation_url){this.state='PRIOR_SCOPE_RECONCILIATION_REQUIRED';return}
  const row=await this.current(r);
  if(['CANCELLED','SUPERSEDED','FAILED','REJECTED'].includes(row.status)){
   this.store.transition(r.request_id,['QUEUED'],'CANCELLED','UPSTREAM_TERMINAL');
   const local=this.store.row(r.request_id);
   this.save(r,local&&local.sends>0?'OPERATOR_REQUIRED':'CANCELLED',{reason:'UPSTREAM_'+row.status});return;
  }
  if(row.status==='RESPONDED'){
   if(!r.response_digest||row.response_digest!==r.response_digest||typeof row.receipt_digest!=='string'||!/^[a-f0-9]{64}$/.test(row.receipt_digest))throw Error('RECEIPT_BINDING_MISMATCH');
   this.save(r,'RECONCILED',{receipt_digest:row.receipt_digest,claim:undefined,reason:'BROKER_RECEIPT_BOUND_PANEL_DELIVERY_UNVERIFIED'});return;
  }
  if(['OPERATOR_REQUIRED','RESPOND_INTENT'].includes(r.state)){this.state='OPERATOR_REQUIRED';return}
  if(r.deadline_at<=this.now()){this.save(r,'OPERATOR_REQUIRED',{reason:'DEADLINE_EXPIRED'});return}
  const binding={request_id:r.request_id,mission_id:r.mission_id,panel_thread_id:r.thread_id,deadline_at:r.deadline_at,claim_generation:r.claim?.claim_generation};
  if(!brokerAllows(binding,row,this.now())){this.save(r,'OPERATOR_REQUIRED',{reason:'CLAIM_EXPIRED_OR_CHANGED'});return}
  if(!(await this.authorized()))return;
  if(r.state==='CLAIMED'){
   this.save(r,'TURN_INTENT');
   try{
    const result=await this.ingress('/v1/turns','POST',r.turn_payload);const turn=result.turn;
    const v={...binding,turn_id:turn?.turn_id,turn_request_hash:turn?.request_hash,conversation_url:r.conversation_url,task_sha256:TASK};
    if(!matches(v,turn)||turn.status!=='PENDING')throw Error('TURN_BINDING_MISMATCH');
    this.save(r,'TURN_CREATED',{envelope:v,turn_payload:undefined});
   }catch{this.save(r,'OPERATOR_REQUIRED',{reason:'TURN_CREATION_OUTCOME_UNKNOWN'})}
   return;
  }
  if(r.state==='TURN_CREATED'){
   // Rechecking after asynchronous observations covers STOP and cancellation.
   if(!brokerAllows(r.envelope,await this.current(r),this.now())||this.store.stopped())return;
   this.store.enqueue(r.envelope);this.save(r,'ENQUEUED');return;
  }
  if(r.state==='ENQUEUED'){
   const job=this.store.row(r.request_id);
   if(!job)throw Error('LOCAL_QUEUE_RECORD_MISSING');
   if(['CANCELLED','FAILED','TIMED_OUT','OPERATOR_REQUIRED'].includes(job.state)){this.save(r,'OPERATOR_REQUIRED',{reason:'LOCAL_'+job.state});return}
   if(job.state!=='RESULT_OBSERVED')return;
   const turn=(await this.ingress('/v1/turns/'+encodeURIComponent(r.envelope.turn_id))).turn;
   const answer=(typeof turn?.response==='string'?turn.response:turn?.response?.text)?.trim();
   if(!matches(r.envelope,turn)||turn.status!=='COMPLETED'||!answer||answer.length>24000)throw Error('COMPLETION_IDENTITY_MISMATCH');
   if(!(await this.authorized())||!brokerAllows(r.envelope,await this.current(r),this.now())||this.store.stopped())return;
   this.save(r,'RESPOND_INTENT',{response_digest:hash(answer)});
   // A lost response is resolved by GET on the next tick, never a repeated POST.
   await this.mc('/api/v3/saas-broker/requests/'+r.request_id+'/respond','POST',{
    response_token:r.claim.response_token,claim_generation:r.claim.claim_generation,answer,
    model_identity:'ChatGPT SaaS / model UNKNOWN / embedded browser + MCP',transport:TRANSPORT,attestation_class:'OPENAI_SECURE_MCP_TUNNEL_TOOL_ROUNDTRIP'
   });
  }
 }
 async tick(){
  if(this.running)return;this.running=true;
  try{
   const active=this.store.handoffs().filter(r=>!TERMINAL.has(r.state));
   if(active.length>1){this.state='MULTIPLE_ACTIVE_HANDOFFS';return}
   if(active.length)await this.advance(active[0]);
   else if(!this.store.stopped())await this.start();else this.state='STOPPED';
   this.lastError=null;
  }catch{this.lastError='RELAY_DEPENDENCY_OR_BINDING_ERROR'}finally{this.running=false}
 }
 status(){return {state:this.state,error:this.lastError,scope:this.scope,handoffs:this.store.handoffs().map(r=>({request_id:r.request_id,state:r.state,reason:r.reason,receipt_digest:r.receipt_digest})),panel_delivery:'NOT_PROVEN'}}
}
module.exports={Relay,TRANSPORT};
