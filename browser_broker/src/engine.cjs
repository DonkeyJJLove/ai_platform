'use strict';
const {matches,prompt}=require('./contract.cjs');
class Engine{
 constructor({store,browser,getTurn,admit=async()=>false,now=Date.now}){this.store=store;this.browser=browser;this.getTurn=getTurn;this.admit=admit;this.now=now;this.running=false;this.lastError=null;this.lastTickAt=null;this.lastDecision=null}
 async tick(){
  if(this.running)return;this.running=true;this.lastTickAt=this.now();this.lastDecision={stage:'TICK_START',at:this.lastTickAt};
  try{
   // Readback remains permissible after STOP, but never triggers another send.
   for(const r of this.store.rows().filter(r=>['AWAITING_RESULT','SEND_UNKNOWN'].includes(r.state)||(r.state==='OPERATOR_REQUIRED'&&r.reason==='EXTERNAL_OUTCOME_UNRESOLVED'))){
    if(r.envelope.deadline_at<=this.now()&&r.state!=='OPERATOR_REQUIRED'){this.store.transition(r.request_id,['AWAITING_RESULT','SEND_UNKNOWN'],'OPERATOR_REQUIRED','EXTERNAL_OUTCOME_UNRESOLVED');continue}
    try{const turn=await this.getTurn(r.envelope.turn_id);if(!matches(r.envelope,turn)){this.store.transition(r.request_id,['AWAITING_RESULT','SEND_UNKNOWN'],'OPERATOR_REQUIRED','TURN_IDENTITY_MISMATCH');continue}
     if(turn.status==='COMPLETED'&&typeof (typeof turn.response==='string'?turn.response:turn.response?.text)==='string'&&(typeof turn.response==='string'?turn.response:turn.response.text).trim())this.store.transition(r.request_id,['AWAITING_RESULT','SEND_UNKNOWN','OPERATOR_REQUIRED'],'RESULT_OBSERVED',r.state==='OPERATOR_REQUIRED'?'LATE_MCP_COMPLETION_READBACK_ONLY':'MCP_READBACK_ONLY_NOT_PANEL_DELIVERY');
    }catch{this.lastError='READBACK_UNAVAILABLE'}
   }
   if(this.store.stopped()||this.store.rows().some(r=>r.state==='OPERATOR_REQUIRED')){this.lastDecision={stage:'STOP_OR_OPERATOR_REQUIRED'};return;}
   const next=this.store.rows().find(r=>r.state==='QUEUED');if(!next){this.lastDecision={stage:'NO_QUEUED'};return;}this.lastDecision={stage:'QUEUED_FOUND',request_id:next.request_id};
   if(next.envelope.deadline_at<=this.now()){this.lastDecision={stage:'DEADLINE_EXPIRED',request_id:next.request_id};this.store.transition(next.request_id,['QUEUED'],'TIMED_OUT','BEFORE_SEND');return}
   if(!(await this.admit(next.envelope))){this.lastDecision={stage:'ADMIT_1_FALSE',request_id:next.request_id};return;}this.lastDecision={stage:'ADMIT_1_TRUE',request_id:next.request_id};
   if(!(await this.browser.ready(next.envelope))){this.lastDecision={stage:'BROWSER_READY_FALSE',request_id:next.request_id,browser_state:this.browser.state};return;}this.lastDecision={stage:'BROWSER_READY_TRUE',request_id:next.request_id};
   const before=await this.getTurn(next.envelope.turn_id);
   if(!matches(next.envelope,before)||before.status!=='PENDING'){this.lastDecision={stage:'TURN_MATCH_FALSE',request_id:next.request_id,turn_status:before&&before.status};this.store.transition(next.request_id,['QUEUED'],'FAILED','TURN_NOT_PENDING_OR_IDENTITY_MISMATCH');return}this.lastDecision={stage:'TURN_MATCH_TRUE',request_id:next.request_id};
   if(!(await this.admit(next.envelope))){this.lastDecision={stage:'ADMIT_2_FALSE',request_id:next.request_id};return;}this.lastDecision={stage:'ADMIT_2_TRUE',request_id:next.request_id};
   if(this.store.stopped())return;
   const job=this.store.claim(next.request_id);if(!job){this.lastDecision={stage:'CLAIM_FALSE',request_id:next.request_id};return;}this.lastDecision={stage:'CLAIMED',request_id:next.request_id};
   try{
    // Persist DISPATCHING before any external action. The adapter rechecks STOP.
    if(this.store.stopped())return;
    await this.browser.send(job.envelope,prompt(job.envelope),()=>!this.store.stopped());
    this.store.transition(job.request_id,['DISPATCHING'],'AWAITING_RESULT');this.lastDecision={stage:'SENT',request_id:job.request_id};
   }catch{this.store.transition(job.request_id,['DISPATCHING'],'SEND_UNKNOWN','SEND_OUTCOME_UNCERTAIN')}
  }catch(e){this.lastError='DEPENDENCY_UNAVAILABLE:'+(e&&e.name?e.name:'Error')+':'+String(e&&e.message?e.message:e).slice(0,500);this.lastDecision={stage:'EXCEPTION',error:this.lastError}}finally{this.running=false}
 }
}
module.exports={Engine};
