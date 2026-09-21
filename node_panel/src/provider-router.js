'use strict';
class ProviderRouter{
  constructor({registry, readiness=()=>({}), swarmHandler=null}){this.registry=registry;this.readiness=readiness;this.swarmHandler=swarmHandler;}
  select(route,{relevance}={}){
    const requested=String(route||'AUTO').toUpperCase();
    if(requested==='LOCAL')return this.registry.get('LOCAL_MODEL');
    if(requested==='CHATGPT')return this.registry.get('CHATGPT_SAAS');
    if(requested==='SWARM')return {provider_id:'SWARM',provider_class:'MISSION_SCOPED_SWARM',execution_mode:'MISSION_SCOPED',transport_mode:'LION_BUS',completion_owner:'MISSION_CONTROL',autonomous_capable:false,authority_effect:'NONE'};
    if(requested!=='AUTO')throw new Error('ROUTE_INVALID');
    const state=this.readiness()||{};
    const externalHint=(relevance?.semantic_anchors||[]).some(x=>['latest','current','web','internet','saas','chatgpt'].includes(String(x).toLowerCase()));
    if(state.local_model_ready===true&&!externalHint)return this.registry.get('LOCAL_MODEL');
    return this.registry.get('CHATGPT_SAAS');
  }
  async dispatchSwarm(input){if(!this.swarmHandler)throw new Error('SWARM_PATH_NOT_CONFIGURED');return this.swarmHandler(input);}
}
module.exports={ProviderRouter};
