'use strict';
const {jsonRequest}=require('./http-json');
class OperatorControlClient{
  constructor({base='http://127.0.0.1:8767',request=jsonRequest}={}){this.base=base;this.request=request;}
  async ready(){try{await this.request(this.base,'/v1/session',{timeoutMs:1500});return true}catch(e){return e.status===403;}}
  async state(missionId){return this.request(this.base,'/v1/state?mission_id='+encodeURIComponent(missionId||''));}
}
module.exports={OperatorControlClient};
