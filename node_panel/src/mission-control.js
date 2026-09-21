'use strict';
const fs=require('node:fs');
const {jsonRequest}=require('./http-json');
class MissionControlClient{
  constructor({base='http://127.0.0.1:8766',request=jsonRequest,mediatorKey=null}={}){this.base=base;this.request=request;this.mediatorKey=mediatorKey;}
  static keyFromFile(file){if(!file)return null;try{const v=fs.readFileSync(file,'utf8').trim();return v.length>=32?v:null}catch{return null}}
  async ready(){try{const v=await this.request(this.base,'/api/v3/saas-broker/status',{timeoutMs:1500});return Boolean(v&&typeof v==='object');}catch{return false;}}
  async recentMissions(view='operational'){return this.request(this.base,'/api/v3/missions/recent?view='+encodeURIComponent(view));}
  async missionProcess(id){return this.request(this.base,'/api/v3/missions/'+encodeURIComponent(id)+'/process');}
  async createSaasRequest({thread_id,question,transport='CHATGPT_OPENAI_SECURE_MCP_TUNNEL'}){return this.request(this.base,'/api/v3/saas-broker/requests',{method:'POST',body:{scope_type:'THREAD',scope_id:thread_id,thread_id,question,authority_effect:'NONE',transport}});}
  async requestStatus(requestId){return this.request(this.base,'/api/v3/saas-broker/requests/'+encodeURIComponent(requestId));}
  async cancelRequest(requestId){return this.request(this.base,'/api/v3/saas-broker/requests/'+encodeURIComponent(requestId)+'/cancel',{method:'POST',body:{},headers:this._mediatorHeaders()});}
  async claimRequest(requestId){return this.request(this.base,'/api/v3/saas-broker/requests/'+encodeURIComponent(requestId)+'/claim',{method:'POST',body:{},headers:this._mediatorHeaders()});}
  async respond({requestId,claim,answer}){return this.request(this.base,'/api/v3/saas-broker/requests/'+encodeURIComponent(requestId)+'/respond',{method:'POST',body:{response_token:claim.response_token,claim_generation:claim.claim_generation,answer,model_identity:'ChatGPT SaaS / ACTIVE_CHATGPT_SAAS_SESSION / LION-MCP-R2',transport:'CHATGPT_OPENAI_SECURE_MCP_TUNNEL',attestation_class:'OPENAI_SECURE_MCP_TUNNEL_TOOL_ROUNDTRIP'},headers:this._mediatorHeaders(),timeoutMs:30000});}
  _mediatorHeaders(){if(!this.mediatorKey)throw new Error('MEDIATOR_KEY_UNAVAILABLE');return {'X-LION-Mediator-Key':this.mediatorKey};}
}
module.exports={MissionControlClient};
