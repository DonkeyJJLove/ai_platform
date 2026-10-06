'use strict';
const {createHash}=require('node:crypto');
const {conversationInfo}=require('./conversation.cjs');

const TRANSPORT='CHATGPT_SENTINELX_MCP';
const EXTERNAL_SYSTEM='CHATGPT_SAAS';
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
 for(const key of ['conversation_id','binding_epoch','lane_id','request_message_id','causation_id','correlation_id','context_digest','shared_context_digest','projection_digest','broker_request_id']){
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
   authority_effect:'NONE',
  };
 }
 stop(reason='OPERATOR_STOP'){this.enabled=false;this.store.setSetting('canonical_consumer_enabled','false');this.state='STOPPED';this.lastDecision={stage:'STOPPED',reason}}
 resume(reason='OPERATOR_RESUME'){this.enabled=true;this.store.setSetting('canonical_consumer_enabled','true');this.state='WAITING_CANONICAL_REQUEST';this.lastDecision={stage:'RESUMED',reason}}
 _persist(){
  this.store.setSetting('canonical_ingress_cursor',String(this.cursor));
  saveJson(this.store,'canonical_turn_map',this.turnMap);
  saveJson(this.store,'canonical_dispatch_map',this.dispatchMap);
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
   broker_request_id:candidate.request_id,
  };
  for(const key of ['conversation_id','binding_epoch','lane_id','request_message_id','causation_id','correlation_id','context_digest','shared_context_digest','projection_digest'])if(embedded[key]!==exact[key])throw Error('CANONICAL_TURN_IDENTITY_MISMATCH_'+key.toUpperCase());
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
 async _dispatch(candidate){
  const rid=candidate.request_id;
  if(this.inFlight.has(rid))return;
  this.inFlight.add(rid);
  try{
   const broker=await this.mc('/api/v3/saas-broker/requests/'+encodeURIComponent(rid));
   if(broker.status==='RESPONDED'){this.dispatchMap[rid]={...(this.dispatchMap[rid]||{}),state:'RECONCILED',observed_at:this.now()};this._persist();return}
   if(!['WAITING_SUPERVISOR','PENDING','CREATED','QUEUED','CLAIMED'].includes(broker.status))return;
   const turn=await this._turnFor(rid);if(!turn){this.state='WAITING_TURN';return}
   const exact=this._validate(candidate,turn,broker);
   const prior=this.dispatchMap[rid];
   if(prior&&['SEND_COMMITTED','BOUND_SENT','SEND_UNKNOWN','RESULT_OBSERVED'].includes(prior.state)){
    if(turn.status==='COMPLETED'){this.dispatchMap[rid]={...prior,state:'RESULT_OBSERVED',observed_at:this.now()};this._persist()}
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
   const dispatchEvidence={shared_context_digest:candidate.shared_context_digest,projection_digest:candidate.projection_digest,actual_payload_bytes_digest:actualPayloadBytesDigest,turn_request_hash:turn.request_hash,turn_id:turn.turn_id};
   if(!bridge||rotate){
    this.state='PROVISIONING';this.lastDecision={stage:'AUTO_CREATE',request_id:rid,conversation_id:candidate.conversation_id};
    this.dispatchMap[rid]={state:'PROVISIONING',exact,...dispatchEvidence,started_at:this.now()};this._persist();
    const created=await this.browser.createProjectConversationWithPrompt(prompt,()=>this.dispatchMap[rid]?.state==='PROVISIONING');
    this.dispatchMap[rid]={...this.dispatchMap[rid],state:'SEND_COMMITTED',conversation_url:created.conversation_url,external_thread_ref:created.external_thread_ref,sent_at:this.now()};this._persist();
    const persisted=await this._persistBridge(candidate,created,rotate?bridge:null);
    bridge={...persisted,provenance:{conversation_url:created.conversation_url,creation_receipt_digest:persisted.creation_receipt_digest}};
    if(rotate){delete forceNew[candidate.conversation_id];saveJson(this.store,'canonical_force_new_bridge',forceNew)}
    this.dispatchMap[rid]={...this.dispatchMap[rid],state:'BOUND_SENT',bridge_id:persisted.bridge_id,creation_receipt_digest:persisted.creation_receipt_digest,bound_at:this.now()};this._persist();
   }else{
    const url=this._conversationUrl(bridge);
    this.state='DISPATCHING';this.lastDecision={stage:'EXACT_BRIDGE_SEND',request_id:rid,bridge_id:bridge.bridge_id,conversation_id:candidate.conversation_id};
    this.dispatchMap[rid]={state:'DISPATCHING',exact,...dispatchEvidence,bridge_id:bridge.bridge_id,conversation_url:url,started_at:this.now()};this._persist();
    try{
     await this.browser.sendToConversation(url,prompt,()=>this.dispatchMap[rid]?.state==='DISPATCHING');
     this.dispatchMap[rid]={...this.dispatchMap[rid],state:'SEND_COMMITTED',sent_at:this.now()};this._persist();
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
   for(const candidate of rows){
    await this._dispatch(candidate);
   }
   this.lastError=null;
   if(!rows.length)this.state='WAITING_CANONICAL_REQUEST';
   else if(this.state==='STARTING')this.state='WAITING_CANONICAL_REQUEST';
  }catch(error){
   this.lastError=String(error?.message||error).slice(0,500);
   this.state=/SEND_UNKNOWN/.test(this.lastError)?'OPERATOR_REQUIRED':'DEGRADED';
   this.lastDecision={stage:'ERROR',error:this.lastError};
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
