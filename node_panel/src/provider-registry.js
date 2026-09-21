'use strict';
const PROVIDERS=Object.freeze({
  LOCAL_MODEL:Object.freeze({
    provider_id:'LOCAL_MODEL',provider_class:'MODEL',execution_mode:'DIRECT_MODEL_ENDPOINT',transport_mode:'LOCAL_HTTP',endpoint:'http://127.0.0.1:8772',completion_owner:'NODE_EXPRESS',autonomous_capable:true,readiness:'INDEPENDENT',authority_effect:'NONE'
  }),
  CHATGPT_SAAS:Object.freeze({
    provider_id:'CHATGPT_SAAS',provider_class:'EXTERNAL_MODEL_SESSION',execution_mode:'DURABLE_EXTERNAL_COMPLETION',transport_mode:'MCP',completion_owner:'CHATGPT_SAAS_CONSUMER',autonomous_capable:false,readiness:'EXTERNAL_CONSUMER_REQUIRED',authority_effect:'NONE'
  })
});
class ProviderRegistry{
  constructor(overrides={}){this.providers={...PROVIDERS,...overrides};}
  get(id){const p=this.providers[id];if(!p)throw new Error('UNKNOWN_PROVIDER');if(p.authority_effect!=='NONE')throw new Error('PROVIDER_AUTHORITY_INVALID');return {...p};}
  list(){return Object.values(this.providers).map(x=>({...x}));}
}
module.exports={ProviderRegistry,PROVIDERS};
