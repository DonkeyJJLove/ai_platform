'use strict';
const {createHash}=require('node:crypto');
const {conversationInfo}=require('./conversation.cjs');

const TRANSPORT='CHATGPT_SENTINELX_MCP';
const EXTERNAL_SYSTEM='CHATGPT_SAAS';
// The UI delivery acknowledgement may outlive one broker tick. Never send
// an entire pending batch in one async turn; advance a durable fair cursor.
const MAX_DISPATCHES_PER_TICK=1;
const UNRESOLVED_SEND_STATES=new Set([
 'PROVISIONING','DISPATCHING','SEND_COMMITTED','BOUND_SENT','SEND_UNKNOWN','RESULT_OBSERVED',
]);
const receiptConfirmed=(broker,rid)=>
 broker?.request_id===rid&&broker.status==='RESPONDED'&&broker.authority_effect==='NONE'
 &&/^[a-f0-9]{64}$/.test(broker.response_digest||'')
 &&/^[a-f0-9]{64}$/.test(broker.receipt_digest||'');
// Contract markers: AUTO_CREATE · CANONICAL_BRIDGE_WINS · EXPLICIT_BRIDGE_ONLY.
// Durable bridge owner is conversation_external_bridges. Historical bridges are
// SUPERSEDED by provenance, never rewritten. BIND/DETACH enforce
// NO_HIDDEN_SUCCESSOR_INHERITANCE because the successor conversation_id has no bridge.

const digest=value=>createHash('sha256').update(typeof value==='string'?value:JSON.stringify(value)).digest('hex');
const requiredString=(value,name)=>{
 if(typeof value!=='string'||!value)throw Error('CANONICAL_'+name.toUpperCase()+'_REQUIRED');
 return value;
};
const loadJson=(store,key,fallback)=>{
 try{const raw=store.setting(key);return raw?JSON.parse(raw):fallback}catch{return fallback}
};
const saveJson=(store,key,value)=>store.setSetting(key,JSON.stringify(value));

function canonicalPrompt(turn,candidate){
 const ids=[
  ['conversation_id',candidate.conversation_id],
  ['binding_epoch',String(candidate.binding_epoch)],
  ['lane_id',candidate.lane_id],
  ['request_message_id',candidate.request_message_id],
  ['causation_id',candidate.causation_id],
  ['correlation_id',candidate.correlation_id],
  ['context_digest',candidate.context_digest],
  ['shared_context_digest',candidate.shared_context_digest],
  ['projection_digest',candidate.projection_digest],
  ...(candidate.synchronization_checkpoint_digest?[['synchronization_checkpoint_digest',candidate.synchronization_checkpoint_digest]]:[]),
  ['broker_request_id',candidate.request_id],
 ];
 return [
  'Use the SentinelX connector only. Do not use LION-MCP-R2 or OpenAI Secure MCP Tunnel.',
  'Target host: MOON.',
  'Canonical Model Chat identity is frozen for this request:',
  ...ids.map(([k,v])=>k+'='+v),
  '1. Call SentinelX sentinel_exec on MOON with command exactly:',
  '/usr/local/bin/lion-sentinelx-turn get '+turn.turn_id,
  '2. Read the returned JSON input field and answer that cognitive request.',
  '3. Call SentinelX sentinel_exec on MOON again with command:',
  '/usr/local/bin/lion-sentinelx-turn complete '+turn.turn_id+' chatgpt-saas-sentinelx \'{"text":"<your answer>"}\'',
  'The final argument must be one valid shell-quoted JSON object with exactly one key: text.',
  'Do not call any other write tool.',
  'Do not infer canonical identity from the currently visible ChatGPT thread.',
  'Broker request id: '+candidate.request_id,
 ].join('\n');
}

function parseCanonicalIdentity(input){
 const out={};
 for(const key of ['conversation_id','binding_epoch','lane_id','request_message_id','causation_id','correlation_id','context_digest','shared_context_digest','synchronization_checkpoint_digest','broker_request_id']){
  const m=String(input||'').match(new RegExp('(?:^|\\n)'+key+'=([^\\n]+)'));
  if(m)out[key]=m[1].trim();
 }
 if(out.binding_epoch!==undefined)out.binding_epoch=Number(out.binding_epoch);
 if(!out.broker_request_id){const m=String(input||'').match(/(?:^|\n)Broker request id:\s*(saas-[A-Za-z0-9-]+)/);if(m)out.broker_request_id=m[1]}
 return out;
}

class CanonicalConversationSaaSConsumer{
 constructor({store,panel,mc,ingress,browser,projectUrl,conversationFilter=null,now=Date.now}){
  if(!store||typeof panel!=='function'||typeof mc!=='function'||typeof ingress!=='function'||!browser||typeof projectUrl!=='string')throw Error('CANONICAL_CONSUMER_CONFIG_REQUIRED');
  Object.assign(this,{store,panel,mc,ingress,browser,projectUrl,conversationFilter,now});
  this.running=false;this.state='STARTING';this.lastError=null;this.lastDecision=null;
  this.inFlight=new Set();
  this.enabled=store.setting('canonical_consumer_enabled')==='true';
  this.turnMap=loadJson(store,'canonical_turn_map',{});
  this.dispatchMap=loadJson(store,'canonical_dispatch_map',{});
  this.cursor=Math.max(0,Number(store.setting('canonical_ingress_cursor')||0)||0);
  const savedScan=Number(store.setting('canonical_dispatch_scan_cursor')||0);
  this.scanCursor=Number.isSafeInteger(savedScan)&&savedScan>=0?savedScan:0;
  this.lastPendingCount=0;
 }
 status(){
  return {
   state:this.state,error:this.lastError,cursor:this.cursor,
   mapped_turns:Object.keys(this.turnMap).length,
   tracked_dispatches:Object.keys(this.dispatchMap).length,
   mode:'CANONICAL_CONVERSATION_SAAS_CONSUMER',
   identity_source:'CANONICAL_CONVERSATION_DB',
   external_saas_semantics:'EXPLICIT_BRIDGE_ONLY',
   bridge_precedence:'CANONICAL_BRIDGE_WINS',
   auto_provision:'AUTO_CREATE',
   conversation_filter:this.conversationFilter,
   writes_legacy_threads:false,
   enabled:this.enabled,
   max_dispatches_per_tick:MAX_DISPATCHES_PER_TICK,
   dispatch_scan_cursor:this.scanCursor,
   pending_candidates_last_tick:this.lastPendingCount,
   authority_effect:'NONE',
  };
 }
 stop(reason='OPERATOR_STOP'){this.enabled=false;this.store.setSetting('canonical_consumer_enabled','false');this.state='STOPPED';this.lastDecision={stage:'STOPPED',reason}}
 resume(reason='OPERATOR_RESUME'){this.enabled=true;this.store.setSetting('canonical_consumer_enabled','true');this.state='WAITING_CANONICAL_REQUEST';this.lastDecision={stage:'RESUMED',reason}}
 _persist(){
  this.store.setSetting('canonical_ingress_cursor',String(this.cursor));
  saveJson(this.store,'canonical_turn_map',this.turnMap);
  saveJson(this.store,'canonical_dispatch_map',this.dispatchMap);
  this.store.setSetting('canonical_dispatch_scan_cursor',String(this.scanCursor));
 }
 async _discoverTurns(){
  const batch=await this.ingress('/v1/events?after='+this.cursor);
  if(!Array.isArray(batch.events))throw Error('CANONICAL_INGRESS_EVENTS_REQUIRED');
  for(const event of batch.events){
   if(!Number.isSafeInteger(event.seq)||event.seq<=this.cursor)continue;
   if(event.type==='turn.pending'&&/^turn_[A-Za-z0-9-]+$/.test(event.data?.turn_id||'')){
    const response=await this.ingress('/v1/turns/'+encodeURIComponent(event.data.turn_id));
    const turn=response.turn;
    const rid=turn?.metadata?.broker_request_id;
    if(typeof rid==='string'&&/^saas-[A-Za-z0-9-]+$/.test(rid)&&turn.command_id==='MC-'+rid){
     this.turnMap[rid]={
      turn_id:turn.turn_id,
      request_hash:turn.request_hash,
      parent_event_id:turn.parent_event_id,
      seq:event.seq,
     };
    }
   }
   this.cursor=event.seq;
  }
  // Bound local cache growth without losing mappings for currently relevant recent turns.
  const entries=Object.entries(this.turnMap).sort((a,b)=>(a[1].seq||0)-(b[1].seq||0));
  if(entries.length>512)this.turnMap=Object.fromEntries(entries.slice(-512));
  this._persist();
 }
 async _turnFor(requestId){
  let mapped=this.turnMap[requestId];
  if(!mapped){
   // First startup after historical pending requests must be able to recover them.
   const all=await this.ingress('/v1/events?after=0');
   if(!Array.isArray(all.events))throw Error('CANONICAL_INGRESS_EVENTS_REQUIRED');
   for(const event of all.events){
    if(event.type!=='turn.pending'||!/^turn_[A-Za-z0-9-]+$/.test(event.data?.turn_id||''))continue;
    const command=event.data?.command_id;
    if(command==='MC-'+requestId){
     mapped={turn_id:event.data.turn_id,seq:event.seq};
     this.turnMap[requestId]=mapped;this._persist();break;
    }
   }
  }
  if(!mapped)return null;
  return (await this.ingress('/v1/turns/'+encodeURIComponent(mapped.turn_id))).turn;
 }
 _validate(candidate,turn,broker){
  for(const key of ['request_id','conversation_id','lane_id','request_message_id','causation_id','correlation_id','context_digest','shared_context_digest','projection_digest'])requiredString(candidate[key],key);
  if(!/^[a-f0-9]{64}$/.test(candidate.shared_context_digest)||!/^[a-f0-9]{64}$/.test(candidate.projection_digest))throw Error('CANONICAL_DIGEST_REQUIRED');
  if(!Number.isSafeInteger(Number(candidate.binding_epoch))||Number(candidate.binding_epoch)<1)throw Error('CANONICAL_BINDING_EPOCH_REQUIRED');
  if(!turn||turn.command_id!=='MC-'+candidate.request_id||turn.parent_event_id!=='saas_request:'+candidate.request_id)throw Error('CANONICAL_TURN_REQUEST_MISMATCH');
  if(turn.thread_id!==null)throw Error('CANONICAL_TURN_LEGACY_THREAD_DENIED');
  if(turn.session_id!==null&&turn.session_id!=='CHATGPT-SAAS')throw Error('CANONICAL_TURN_SESSION_MISMATCH');
  if(!broker||broker.request_id!==candidate.request_id||broker.scope_type!=='CONTROL_PLANE'||broker.thread_id!==null||broker.authority_effect!=='NONE'||broker.transport!==TRANSPORT)throw Error('CANONICAL_BROKER_MISMATCH');
  if(typeof broker.question!=='string'||digest(broker.question)!==candidate.projection_digest||broker.question_digest!==candidate.projection_digest)throw Error('CANONICAL_PROJECTION_DIGEST_MISMATCH');
  const embedded=parseCanonicalIdentity(turn.input);
  if(embedded.broker_request_id!==candidate.request_id)throw Error('CANONICAL_TURN_BROKER_ID_MISMATCH');
  const exact={
   conversation_id:candidate.conversation_id,
   binding_epoch:Number(candidate.binding_epoch),
   lane_id:candidate.lane_id,
   request_message_id:candidate.request_message_id,
   causation_id:candidate.causation_id,
   correlation_id:candidate.correlation_id,
   context_digest:candidate.context_digest,
   shared_context_digest:candidate.shared_context_digest,
   projection_digest:candidate.projection_digest,
   synchronization_checkpoint_digest:candidate.synchronization_checkpoint_digest||null,
   broker_request_id:candidate.request_id,
  };
  for(const key of ['conversation_id','binding_epoch','lane_id','request_message_id','causation_id','correlation_id','context_digest','shared_context_digest'])if(embedded[key]!==exact[key])throw Error('CANONICAL_TURN_IDENTITY_MISMATCH_'+key.toUpperCase());
  if(exact.synchronization_checkpoint_digest&&embedded.synchronization_checkpoint_digest!==exact.synchronization_checkpoint_digest)throw Error('CANONICAL_TURN_IDENTITY_MISMATCH_SYNCHRONIZATION_CHECKPOINT_DIGEST');
  return exact;
 }
 _bridgeFor(conversation){
  const rows=(conversation.external_bridges||[]).filter(b=>b.external_system===EXTERNAL_SYSTEM);
  if(!rows.length)return null;
  const superseded=new Set();
  for(const row of rows){
   try{
    const p=JSON.parse(row.provenance_json||'{}');
    const supplied=p.supplied||{};
    if(typeof supplied.supersedes_bridge_id==='string')superseded.add(supplied.supersedes_bridge_id);
   }catch{}
  }
  const active=rows.filter(r=>!superseded.has(r.bridge_id)).sort((a,b)=>Number(a.created_at||0)-Number(b.created_at||0)).at(-1);
  if(!active)return null;
  let provenance={};try{provenance=JSON.parse(active.provenance_json||'{}').supplied||{}}catch{}
  return {...active,provenance};
 }
 _conversationUrl(bridge){
  const stored=bridge?.provenance?.conversation_url;
  if(typeof stored==='string'){
   const info=conversationInfo(stored,this.projectUrl);
   if(info.id!==bridge.external_thread_ref)throw Error('CANONICAL_BRIDGE_URL_REF_MISMATCH');
   return info.url;
  }
  // Auto-created bridge normally stores the URL. This fallback is deterministic and
  // never consults the currently visible tab.
  return 'https://chatgpt.com/c/'+encodeURIComponent(requiredString(bridge.external_thread_ref,'external_thread_ref'));
 }
 async _persistBridge(candidate,created,supersedes=null){
  const creationReceiptDigest=digest({
   schema:'lion.canonical-saas-bridge-creation/v1',
   conversation_id:candidate.conversation_id,
   binding_epoch:candidate.binding_epoch,
   lane_id:candidate.lane_id,
   request_message_id:candidate.request_message_id,
   broker_request_id:candidate.request_id,
   external_thread_ref:created.external_thread_ref,
   conversation_url:created.conversation_url,
  });
  const body={
   external_thread_ref:created.external_thread_ref,
   external_system:EXTERNAL_SYSTEM,
   context_snapshot_digest:candidate.context_digest,
   provenance:{
    surface:'CANONICAL_CONVERSATION_SAAS_CONSUMER',
    creation_mode:'AUTO',
    bridge_state:'BOUND',
    conversation_url:created.conversation_url,
    creation_receipt_digest:creationReceiptDigest,
    broker_request_id:candidate.request_id,
    request_message_id:candidate.request_message_id,
    lane_id:candidate.lane_id,
    correlation_id:candidate.correlation_id,
    causation_id:candidate.causation_id,
    ...(supersedes?{supersedes_bridge_id:supersedes.bridge_id}:{}),
    authority_effect:'NONE',
   },
  };
  const result=await this.panel('/api/conversations/'+encodeURIComponent(candidate.conversation_id)+'/bridges','POST',body);
  return {...result,creation_receipt_digest:creationReceiptDigest};
 }
 async _recordDispatchEvidence(candidate,bridge,dispatchEvidence,dispatchState){
  const body={
   conversation_id:candidate.conversation_id,
   request_message_id:candidate.request_message_id,
   request_id:candidate.request_id,
   binding_epoch:Number(candidate.binding_epoch),
   lane_id:candidate.lane_id,
   shared_context_digest:dispatchEvidence.shared_context_digest,
   projection_digest:dispatchEvidence.projection_digest,
   actual_payload_bytes_digest:dispatchEvidence.actual_payload_bytes_digest,
   attachment_payload_bytes_digest:dispatchEvidence.attachment_payload_bytes_digest,
   turn_request_hash:dispatchEvidence.turn_request_hash,
   turn_id:dispatchEvidence.turn_id,
   bridge_id:requiredString(bridge.bridge_id,'bridge_id'),
   external_thread_ref:requiredString(bridge.external_thread_ref,'external_thread_ref'),
   dispatch_state:dispatchState,
  };
  return this.panel('/api/conversations/saas/dispatch','POST',body);
 }
 async _dispatch(candidate){
  const rid=candidate.request_id;
  if(this.inFlight.has(rid))return;
  this.inFlight.add(rid);
  try{
   const broker=await this.mc('/api/v3/saas-broker/requests/'+encodeURIComponent(rid));
   if(broker.status==='RESPONDED'){
    if(!receiptConfirmed(broker,rid)){
     this.state='OPERATOR_REQUIRED';
     this.lastDecision={stage:'RESPONSE_RECEIPT_UNVERIFIED',request_id:rid,authority_effect:'NONE'};
     return;
    }
    this.dispatchMap[rid]={...(this.dispatchMap[rid]||{}),state:'RECONCILED',observed_at:this.now()};this._persist();return;
   }
   if(!['WAITING_SUPERVISOR','PENDING','CREATED','QUEUED','CLAIMED'].includes(broker.status))return;
   const turn=await this._turnFor(rid);if(!turn){this.state='WAITING_TURN';return}
   const exact=this._validate(candidate,turn,broker);
   const prior=this.dispatchMap[rid];
   if(prior&&['PROVISIONING','DISPATCHING'].includes(prior.state)){
    // After an interrupted send, the actual SaaS UI outcome is unknown.
    // Never auto-replay a request that may already have been submitted.
    this.dispatchMap[rid]={...prior,state:'SEND_UNKNOWN',
      uncertainty_reason:'UNACKNOWLEDGED_EXTERNAL_SEND',observed_at:this.now()};this._persist();
    this.state='OPERATOR_REQUIRED';
    this.lastDecision={stage:'SEND_UNKNOWN_RECONCILE_FIRST',request_id:rid,authority_effect:'NONE'};
    return;
   }
   if(prior&&['SEND_COMMITTED','BOUND_SENT','SEND_UNKNOWN','RESULT_OBSERVED'].includes(prior.state)){
    if(prior.state==='SEND_UNKNOWN'){
     this.state='OPERATOR_REQUIRED';
     this.lastDecision={stage:'SEND_UNKNOWN_RECONCILE_FIRST',request_id:rid,authority_effect:'NONE'};
     return;
    }
    if(
     !prior.dispatch_evidence_recorded_at &&
     ['SEND_COMMITTED','BOUND_SENT'].includes(prior.state) &&
     prior.bridge_id && prior.external_thread_ref
    ){
     await this._recordDispatchEvidence(candidate,{bridge_id:prior.bridge_id,external_thread_ref:prior.external_thread_ref},prior,prior.state);
     this.dispatchMap[rid]={...prior,dispatch_evidence_recorded_at:this.now()};this._persist();
    }
    if(turn.status==='COMPLETED'){this.dispatchMap[rid]={...this.dispatchMap[rid],state:'RESULT_OBSERVED',observed_at:this.now()};this._persist()}
    return;
   }
   if(turn.status!=='PENDING')return;
   const conversation=await this.panel('/api/conversations/'+encodeURIComponent(candidate.conversation_id));
   if(conversation.state==='FROZEN')throw Error('CANONICAL_CONVERSATION_FROZEN');
   if(Number(conversation.current_binding?.binding_epoch)!==Number(candidate.binding_epoch))throw Error('CANONICAL_BINDING_EPOCH_STALE');
   let bridge=this._bridgeFor(conversation);
   const forceNew=loadJson(this.store,'canonical_force_new_bridge',{});
   const rotate=forceNew[candidate.conversation_id]===true;
   const prompt=canonicalPrompt(turn,candidate);
   const actualPayloadBytesDigest=digest(prompt);
   const attachmentPayloadBytesDigest=digest(String(turn.input||''));
   const dispatchEvidence={shared_context_digest:candidate.shared_context_digest,projection_digest:candidate.projection_digest,actual_payload_bytes_digest:actualPayloadBytesDigest,attachment_payload_bytes_digest:attachmentPayloadBytesDigest,turn_request_hash:turn.request_hash,turn_id:turn.turn_id};
   if(!bridge||rotate){
    this.state='PROVISIONING';this.lastDecision={stage:'AUTO_CREATE',request_id:rid,conversation_id:candidate.conversation_id};
    this.dispatchMap[rid]={state:'PROVISIONING',exact,...dispatchEvidence,started_at:this.now()};this._persist();
    let created;
    try{
     created=await this.browser.createProjectConversationWithPrompt(
      prompt,()=>this.dispatchMap[rid]?.state==='PROVISIONING');
    }catch(error){
     // A browser timeout can happen after the external send was committed.
     this.dispatchMap[rid]={...this.dispatchMap[rid],state:'SEND_UNKNOWN',
      uncertainty_reason:'PROVISIONING_SEND_OUTCOME_UNKNOWN',
      error:String(error?.message||error).slice(0,200),observed_at:this.now()};this._persist();
     this.state='OPERATOR_REQUIRED';
     this.lastDecision={stage:'SEND_UNKNOWN_RECONCILE_FIRST',request_id:rid,authority_effect:'NONE'};
     throw error;
    }
    this.dispatchMap[rid]={...this.dispatchMap[rid],state:'SEND_COMMITTED',conversation_url:created.conversation_url,external_thread_ref:created.external_thread_ref,sent_at:this.now()};this._persist();
    const persisted=await this._persistBridge(candidate,created,rotate?bridge:null);
    bridge={...persisted,provenance:{conversation_url:created.conversation_url,creation_receipt_digest:persisted.creation_receipt_digest}};
    if(rotate){delete forceNew[candidate.conversation_id];saveJson(this.store,'canonical_force_new_bridge',forceNew)}
    this.dispatchMap[rid]={...this.dispatchMap[rid],state:'BOUND_SENT',bridge_id:persisted.bridge_id,external_thread_ref:created.external_thread_ref,creation_receipt_digest:persisted.creation_receipt_digest,bound_at:this.now()};this._persist();
    await this._recordDispatchEvidence(candidate,{bridge_id:persisted.bridge_id,external_thread_ref:created.external_thread_ref},dispatchEvidence,'BOUND_SENT');
    this.dispatchMap[rid]={...this.dispatchMap[rid],dispatch_evidence_recorded_at:this.now()};this._persist();
   }else{
    const url=this._conversationUrl(bridge);
    this.state='DISPATCHING';this.lastDecision={stage:'EXACT_BRIDGE_SEND',request_id:rid,bridge_id:bridge.bridge_id,conversation_id:candidate.conversation_id};
    this.dispatchMap[rid]={state:'DISPATCHING',exact,...dispatchEvidence,bridge_id:bridge.bridge_id,external_thread_ref:bridge.external_thread_ref,conversation_url:url,started_at:this.now()};this._persist();
    try{
     await this.browser.sendToConversation(url,prompt,()=>this.dispatchMap[rid]?.state==='DISPATCHING');
     this.dispatchMap[rid]={...this.dispatchMap[rid],state:'SEND_COMMITTED',sent_at:this.now()};this._persist();
     await this._recordDispatchEvidence(candidate,bridge,dispatchEvidence,'SEND_COMMITTED');
     this.dispatchMap[rid]={...this.dispatchMap[rid],dispatch_evidence_recorded_at:this.now()};this._persist();
    }catch(error){
     this.dispatchMap[rid]={...this.dispatchMap[rid],state:'SEND_UNKNOWN',error:String(error?.message||error),observed_at:this.now()};this._persist();throw error;
    }
   }
   this.state='AWAITING_MCP_RESULT';
  }finally{this.inFlight.delete(rid)}
 }
 async openBridgeForConversation(conversationId){
  const conversation=await this.panel('/api/conversations/'+encodeURIComponent(conversationId));
  const bridge=this._bridgeFor(conversation);if(!bridge)throw Error('CANONICAL_BRIDGE_REQUIRED');
  const url=this._conversationUrl(bridge);
  await this.browser.navigateExact(url);
  return {conversation_id:conversationId,bridge_id:bridge.bridge_id,external_thread_ref:bridge.external_thread_ref,conversation_url:url,authority_effect:'NONE'};
 }
 requestRotate(conversationId){
  const value=loadJson(this.store,'canonical_force_new_bridge',{});value[conversationId]=true;saveJson(this.store,'canonical_force_new_bridge',value);
  return {conversation_id:conversationId,state:'ROTATE_ON_NEXT_SAAS',authority_effect:'NONE'};
 }
 async tick(){
  if(this.running||!this.enabled){if(!this.enabled)this.state='STOPPED';return}this.running=true;
  try{
   await this._discoverTurns();
   const pending=await this.panel('/api/conversations/saas/pending?limit=128');
   const allRows=Array.isArray(pending.candidates)?pending.candidates:[];
   const rows=this.conversationFilter?allRows.filter(x=>x.conversation_id===this.conversationFilter):allRows;
   this.lastPendingCount=rows.length;
   const unresolved=Object.entries(this.dispatchMap)
     .filter(([,value])=>value&&UNRESOLVED_SEND_STATES.has(value.state));
   if(unresolved.length>1){
    this.state='OPERATOR_REQUIRED';
    this.lastDecision={stage:'MULTIPLE_UNRESOLVED_EXTERNAL_SENDS',
     count:unresolved.length,authority_effect:'NONE'};
   }else if(unresolved.length===1){
    const [requestId]=unresolved[0];
    const owned=rows.find(candidate=>candidate.request_id===requestId);
    if(owned){
     // Reconcile exactly the same request; do not begin another send.
     await this._dispatch(owned);
    }else{
     // A responded request may disappear from the pending projection.
     // Only verified canonical response/receipt readback frees the gate.
     const broker=await this.mc('/api/v3/saas-broker/requests/'+encodeURIComponent(requestId));
     if(receiptConfirmed(broker,requestId)){
      this.dispatchMap[requestId]={...this.dispatchMap[requestId],
       state:'RECONCILED',observed_at:this.now()};this._persist();
      this.lastDecision={stage:'RECONCILED_BY_EXACT_BROKER_READBACK',
       request_id:requestId,authority_effect:'NONE'};
     }else{
      this.state=broker?.status==='RESPONDED'?'OPERATOR_REQUIRED':'WAITING_PRIOR_READBACK';
      this.lastDecision={stage:'PRIOR_EXTERNAL_SEND_NOT_RECONCILED',
       request_id:requestId,authority_effect:'NONE'};
     }
    }
   }else if(rows.length){
    // Advance and persist the fair scan cursor before an external send.
    const index=this.scanCursor%rows.length;
    this.scanCursor=(index+MAX_DISPATCHES_PER_TICK)%rows.length;
    this._persist();
    await this._dispatch(rows[index]);
   }
   this.lastError=null;
   if(!rows.length&&!['WAITING_PRIOR_READBACK','OPERATOR_REQUIRED'].includes(this.state))this.state='WAITING_CANONICAL_REQUEST';
   else if(this.state==='STARTING')this.state='WAITING_CANONICAL_REQUEST';
  }catch(error){
   this.lastError=String(error?.message||error).slice(0,500);
   const uncertain=Object.values(this.dispatchMap).some(x=>x?.state==='SEND_UNKNOWN');
   this.state=uncertain||this.state==='OPERATOR_REQUIRED'||/SEND_UNKNOWN/.test(this.lastError)
     ?'OPERATOR_REQUIRED':'DEGRADED';
   this.lastDecision=uncertain
    ?{stage:'SEND_UNKNOWN_RECONCILE_FIRST',error:this.lastError,authority_effect:'NONE'}
    :{stage:'ERROR',error:this.lastError};
  }finally{this.running=false}
 }
}

module.exports={
 CanonicalConversationSaaSConsumer,
 canonicalPrompt,
 parseCanonicalIdentity,
 EXTERNAL_SYSTEM,
 TRANSPORT,
};
