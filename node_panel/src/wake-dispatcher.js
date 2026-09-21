'use strict';
const {id}=require('./canonical');
const TERMINAL=new Set(['CANCELLED','SUPERSEDED','FAILED','REJECTED','RESPONDED','RECONCILED','FAILED_CLOSED','ORPHANED_THREAD']);
class WakeDispatcher {
  constructor({store,missionControl,relay,trigger,now=Date.now,maxAttempts=3}){
    this.store=store;this.mc=missionControl;this.relay=relay;this.trigger=trigger;this.now=now;this.maxAttempts=maxAttempts;
  }
  async dispatch(binding,turnBinding){
    const db=this.store.db,now=this.now();
    let job=db.prepare('SELECT * FROM saas_wake_outbox WHERE request_id=?').get(binding.request_id);
    // Only new requests enrolled by this runtime can trigger. No historic queue drain.
    if(!job)return {state:'NOT_ENROLLED'};
    if(['ACCEPTED','CANCELLED','REJECTED','EXHAUSTED','COMPLETED'].includes(job.state))return {state:job.state};
    if(!this.trigger?.configured())return {state:'NOT_CONFIGURED'};
    if(job.next_attempt_at>now||job.lease_until>now)return {state:'DEFERRED'};
    const current=this.store.requestBinding(binding.request_id);
    if(!current||TERMINAL.has(current.state)||!this.store._threadExists(current.thread_id)){this.finish(binding.request_id,'CANCELLED');return {state:'CANCELLED'};}
    // Read broker and exact turn before every attempt, including after restart.
    const broker=await this.mc.requestStatus(binding.request_id);
    if(TERMINAL.has(broker.status)){this.finish(binding.request_id,'CANCELLED');return {state:'CANCELLED'};}
    const turn=await this.relay.getTurn(turnBinding.turn_id);
    if(turn.status==='COMPLETED'){this.finish(binding.request_id,'COMPLETED');return {state:'COMPLETED'};}
    if(turn.status!=='PENDING')return {state:'WAITING_TURN'};
    if(turn.turn_id!==turnBinding.turn_id||turn.thread_id!==current.thread_id||turn.command_id!=='MC-'+current.request_id||
      (turn.mission_id||null)!==(current.mission_id||null)||!turnBinding.turn_request_hash||turn.request_hash!==turnBinding.turn_request_hash)throw Error('WAKE_TURN_IDENTITY_MISMATCH');
    if(current.mission_id){
      const mission=await this.mc.missionProcess(current.mission_id);
      if(mission.mission_id!==current.mission_id||!['RUNNING','AUTHORIZED'].includes(mission.state))return {state:'MISSION_NOT_ACTIVE'};
    }
    const event=this.trigger.event(current,turnBinding),owner=id();
    const leased=this.store._tx(()=>{
      job=db.prepare('SELECT * FROM saas_wake_outbox WHERE request_id=?').get(current.request_id);
      if(job.lease_until>now||job.next_attempt_at>now||['ACCEPTED','CANCELLED','REJECTED','EXHAUSTED','COMPLETED'].includes(job.state))return false;
      if(job.event_json&&job.event_json!==JSON.stringify(event))throw Error('WAKE_BINDING_CONFLICT');
      if(job.attempts>=this.maxAttempts){this.finish(current.request_id,'EXHAUSTED');return false;}
      db.prepare("UPDATE saas_wake_outbox SET state='SEND_UNKNOWN',event_json=?,attempts=attempts+1,lease_owner=?,lease_until=?,updated_at=? WHERE request_id=?").run(JSON.stringify(event),owner,now+60000,now,current.request_id);return true;
    });
    if(!leased)return {state:'DEFERRED'};
    try{
      // Recheck local cancellation after acquiring the durable lease.
      if(!this.store._threadExists(current.thread_id)||TERMINAL.has(this.store.requestBinding(current.request_id)?.state)){this.finish(current.request_id,'CANCELLED');return {state:'CANCELLED'};}
      const result=await this.trigger.send(event);
      db.prepare("UPDATE saas_wake_outbox SET state='ACCEPTED',result_json=?,lease_until=0,updated_at=? WHERE request_id=? AND lease_owner=?").run(JSON.stringify(result),this.now(),current.request_id,owner);
      return {state:'ACCEPTED'};
    }catch(e){
      const state=e.terminal?'REJECTED':'SEND_UNKNOWN';
      // Persist only our bounded error codes; never arbitrary provider/credential text.
      const code=/^(WAKE_[A-Z0-9_]+|WORKSPACE_TOKEN_UNAVAILABLE)$/.test(e.message)?e.message:'WAKE_ERROR';
      db.prepare('UPDATE saas_wake_outbox SET state=?,last_error=?,next_attempt_at=?,lease_until=0,updated_at=? WHERE request_id=? AND lease_owner=?').run(state,code,this.now()+60000*Math.min(4,job.attempts+1),this.now(),current.request_id,owner);
      return {state,error:code};
    }
  }
  finish(requestId,state){this.store.db.prepare('UPDATE saas_wake_outbox SET state=?,lease_until=0,updated_at=? WHERE request_id=?').run(state,this.now(),requestId);}
}
module.exports={WakeDispatcher};
