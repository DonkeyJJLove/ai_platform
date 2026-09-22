'use strict';
const {TASK,brokerAllows,matches,hash}=require('./contract.cjs');
const {boundConversation}=require('./conversation.cjs');
const TRANSPORT='CHATGPT_SENTINELX_MCP';
class ThreadConsumer{
 constructor({store,scope,mc,ingress,now=Date.now}){
  if(scope?.mode!=='THREAD_CONSUMER'||scope.task_sha256!==TASK||scope.mission_id!==null||!/^[A-Za-z0-9_-]{1,160}$/.test(scope.thread_id))throw Error('THREAD_SCOPE_REQUIRED');
  this.scope={...scope,conversation_url:boundConversation(scope,store.projectUrl)};
  Object.assign(this,{store,mc,ingress,now});this.cursor=null;this.running=false;this.state='STOPPED';this.lastError=null;
 }
 async prime(){
  const s=await this.ingress('/v1/state');if(!Number.isSafeInteger(s.seq)||s.seq<0)throw Error('INGRESS_CURSOR_REQUIRED');
  this.cursor=s.seq;this.state='WAITING_NEW_PANEL_TURN';return s.seq;
 }
 async admits(v){
  if(v.mission_id!==null||v.panel_thread_id!==this.scope.thread_id||v.conversation_url!==this.scope.conversation_url||v.task_sha256!==TASK)return false;
  const row=await this.mc('/api/v3/saas-broker/requests/'+encodeURIComponent(v.request_id));
  return row.transport===TRANSPORT&&brokerAllows(v,row,this.now());
 }
 async reconcile(){
  // Receipt creation and panel insertion belong to the existing panel producer.
  for(const job of this.store.rows().filter(j=>j.state==='RESULT_OBSERVED'&&j.envelope.mission_id===null&&j.envelope.panel_thread_id===this.scope.thread_id)){
   const v=job.envelope,row=await this.mc('/api/v3/saas-broker/requests/'+encodeURIComponent(v.request_id));
   if(row.request_id!==v.request_id||row.thread_id!==v.panel_thread_id||row.mission_id!==null||row.scope_type!=='THREAD'||row.scope_id!==v.panel_thread_id)continue;
   if(row.status==='RESPONDED'&&/^[a-f0-9]{64}$/.test(row.receipt_digest||'')){
    const turn=(await this.ingress('/v1/turns/'+encodeURIComponent(v.turn_id))).turn;
    const answer=typeof turn?.response==='string'?turn.response:turn?.response?.text;
    if(matches(v,turn)&&turn.status==='COMPLETED'&&typeof answer==='string'&&hash(answer.trim())===row.response_digest)this.store.transition(v.request_id,['RESULT_OBSERVED'],'RECONCILED','UPSTREAM_RECEIPT_OBSERVED_PANEL_DELIVERY_UNVERIFIED');
   }
  }
 }
 async tick(){
  if(this.running)return;this.running=true;
  try{
   await this.reconcile();
   if(this.store.stopped()){this.state='STOPPED';return}
   if(this.cursor===null){await this.prime();return}
   const batch=await this.ingress('/v1/events?after='+this.cursor);
   if(!Array.isArray(batch.events))throw Error('EVENTS_REQUIRED');
   for(const event of batch.events){
    if(!Number.isSafeInteger(event.seq)||event.seq<=this.cursor)continue;
    if(this.store.stopped())return;
    if(event.type==='turn.pending'&&/^turn_[A-Za-z0-9-]+$/.test(event.data?.turn_id||'')){
     const turn=(await this.ingress('/v1/turns/'+encodeURIComponent(event.data.turn_id))).turn;
     if(turn?.turn_id===event.data.turn_id&&turn.status==='PENDING'&&turn.mission_id===null&&turn.thread_id===this.scope.thread_id&&/^MC-saas-[A-Za-z0-9-]+$/.test(turn.command_id||'')){
      const rid=turn.command_id.slice(3),row=await this.mc('/api/v3/saas-broker/requests/'+encodeURIComponent(rid));
      const v={request_id:rid,mission_id:null,panel_thread_id:this.scope.thread_id,turn_id:turn.turn_id,turn_request_hash:turn.request_hash,parent_event_id:turn.parent_event_id,conversation_url:this.scope.conversation_url,task_sha256:TASK,deadline_at:Math.min(Date.parse(row.deadline_at||row.expires_at),this.now()+1200000)};
      if(v.parent_event_id!=='saas_request:'+rid){this.cursor=event.seq;continue;}
      if(row.status==='CLAIMED')v.claim_generation=row.claim_generation;
      if(row.transport===TRANSPORT&&brokerAllows(v,row,this.now())){
       if(this.store.stopped())return;
       this.store.enqueue(v);this.state='PANEL_TURN_QUEUED';
      }
     }
    }
    this.cursor=event.seq;
   }
   this.lastError=null;
  }catch(e){this.lastError=/^[A-Z_]+$/.test(e.message)?e.message:'THREAD_DEPENDENCY_UNAVAILABLE'}finally{this.running=false}
 }
 status(){return {state:this.state,error:this.lastError,mode:'THREAD_CONSUMER',scope:this.scope,cursor:this.cursor,creates_turns:false,claims_requests:false,writes_responses:false,panel_delivery:'NOT_PROVEN'}}
}
module.exports={ThreadConsumer};
