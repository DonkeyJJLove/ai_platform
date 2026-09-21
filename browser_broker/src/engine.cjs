'use strict';
const {matches,prompt}=require('./contract.cjs');
class Engine{
 constructor({store,browser,getTurn,admit=async()=>false,now=Date.now}){this.store=store;this.browser=browser;this.getTurn=getTurn;this.admit=admit;this.now=now;this.running=false;this.lastError=null}
 async tick(){
  if(this.running)return;this.running=true;
  try{
   // Readback remains permissible after STOP, but never triggers another send.
   for(const r of this.store.rows().filter(r=>['AWAITING_RESULT','SEND_UNKNOWN'].includes(r.state))){
    if(r.envelope.deadline_at<=this.now()){this.store.transition(r.request_id,['AWAITING_RESULT','SEND_UNKNOWN'],'OPERATOR_REQUIRED','EXTERNAL_OUTCOME_UNRESOLVED');continue}
    try{const turn=await this.getTurn(r.envelope.turn_id);if(!matches(r.envelope,turn)){this.store.transition(r.request_id,['AWAITING_RESULT','SEND_UNKNOWN'],'OPERATOR_REQUIRED','TURN_IDENTITY_MISMATCH');continue}
     if(turn.status==='COMPLETED'&&typeof (typeof turn.response==='string'?turn.response:turn.response?.text)==='string'&&(typeof turn.response==='string'?turn.response:turn.response.text).trim())this.store.transition(r.request_id,['AWAITING_RESULT','SEND_UNKNOWN'],'RESULT_OBSERVED','MCP_READBACK_ONLY_NOT_PANEL_DELIVERY');
    }catch{this.lastError='READBACK_UNAVAILABLE'}
   }
   if(this.store.stopped()||this.store.rows().some(r=>r.state==='OPERATOR_REQUIRED'))return;
   const next=this.store.rows().find(r=>r.state==='QUEUED');if(!next)return;
   if(next.envelope.deadline_at<=this.now()){this.store.transition(next.request_id,['QUEUED'],'TIMED_OUT','BEFORE_SEND');return}
   if(!(await this.admit(next.envelope)))return;
   if(!(await this.browser.ready(next.envelope)))return;
   const before=await this.getTurn(next.envelope.turn_id);
   if(!matches(next.envelope,before)||before.status!=='PENDING'){this.store.transition(next.request_id,['QUEUED'],'FAILED','TURN_NOT_PENDING_OR_IDENTITY_MISMATCH');return}
   if(this.store.stopped())return;
   const job=this.store.claim(next.request_id);if(!job)return;
   try{
    // Persist DISPATCHING before any external action. The adapter rechecks STOP.
    if(this.store.stopped())return;
    await this.browser.send(job.envelope,prompt(job.envelope),()=>!this.store.stopped());
    this.store.transition(job.request_id,['DISPATCHING'],'AWAITING_RESULT');
   }catch{this.store.transition(job.request_id,['DISPATCHING'],'SEND_UNKNOWN','SEND_OUTCOME_UNCERTAIN')}
  }catch{this.lastError='DEPENDENCY_UNAVAILABLE'}finally{this.running=false}
 }
}
module.exports={Engine};
