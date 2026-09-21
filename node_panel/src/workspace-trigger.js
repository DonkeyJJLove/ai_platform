'use strict';
const {sha256,canonicalJson}=require('./canonical');

class WorkspaceTrigger {
  constructor({channelId,tokenProvider,fetchImpl=globalThis.fetch}={}) {
    this.channelId=channelId;this.tokenProvider=tokenProvider;this.fetch=fetchImpl;
  }
  configured(){return /^agtch_[A-Za-z0-9_-]+$/.test(this.channelId||'')&&typeof this.tokenProvider==='function';}
  event(binding,turn){
    if(!this.configured())throw Error('WORKSPACE_TRIGGER_NOT_CONFIGURED');
    const identity={request_id:binding.request_id,thread_id:binding.thread_id,mission_id:binding.mission_id||null,turn_id:turn.turn_id,context_digest:binding.context_digest};
    for(const key of ['request_id','thread_id','turn_id','context_digest'])if(typeof identity[key]!=='string'||!identity[key])throw Error('WAKE_IDENTITY_MISSING');
    const scope=identity.mission_id?'mission:'+identity.mission_id:'thread:'+identity.thread_id;
    const body=canonicalJson({conversation_key:'lion-'+sha256(scope),input:[
      'LION SaaS supervisor: consume exactly the bound LION-MCP-R2 turn with lion_get_turn.',
      'Check request, thread, mission and context identity; stop on mismatch. Do not consume the global queue.',
      'Perform semantic/heuristic reasoning according to the published agent contract.',
      'Return response.text through lion_complete_turn for this exact turn_id; actor chatgpt-saas-mcp.',
      'Local model and fleet actions remain subject to their existing mission contracts and admission; this message grants no authority.',
      'Binding: '+canonicalJson(identity)
    ].join('\n')});
    return {channel_id:this.channelId,body,idempotency_key:'lion-'+sha256(this.channelId+'\n'+binding.request_id),digest:sha256(body)};
  }
  async send(event){
    if(!this.configured()||event.channel_id!==this.channelId)throw Error('WAKE_CHANNEL_CHANGED');
    const token=await this.tokenProvider();if(typeof token!=='string'||!token.trim())throw Error('WORKSPACE_TOKEN_UNAVAILABLE');
    let r;try{r=await this.fetch('https://api.chatgpt.com/v1/workspace_agents/'+this.channelId+'/trigger',{
      method:'POST',redirect:'error',signal:AbortSignal.timeout(15000),headers:{Authorization:'Bearer '+token,'Content-Type':'application/json','Idempotency-Key':event.idempotency_key,'OpenAI-Beta':'workspace_agent_runs=v1'},body:event.body
    });}catch{throw Error('WAKE_SEND_UNKNOWN');}
    if(r.status!==202)throw Object.assign(Error('WAKE_HTTP_'+r.status),{terminal:[400,401,403,404,409,422].includes(r.status)});
    let data,url;try{data=await r.json();url=new URL(data.conversation_url);}catch{throw Error('WAKE_ACCEPTANCE_UNKNOWN');}
    if(url.origin!=='https://chatgpt.com'||!url.pathname.startsWith('/c/')||url.username||url.password)throw Error('WAKE_ACCEPTANCE_UNKNOWN');
    return {conversation_url:url.href,run_id:/^apirun_[A-Za-z0-9_-]+$/.test(data.agent_trigger_run_id||'')?data.agent_trigger_run_id:null};
  }
}
module.exports={WorkspaceTrigger};
