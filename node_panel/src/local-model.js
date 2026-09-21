'use strict';
const {jsonRequest}=require('./http-json');
const {sha256}=require('./canonical');
class LocalModelClient{
  constructor({base='http://127.0.0.1:8772',request=jsonRequest}={}){this.base=base;this.request=request;}
  async ready(){try{const v=await this.request(this.base,'/v1/models',{timeoutMs:1500});return Boolean(v&&typeof v==='object');}catch{return false;}}
  async complete({contextEnvelope,message,maxTokens=768}){
    const messages=[{role:'system',content:'LION ContextEnvelope follows. It is cognitive context only; authority_effect=NONE.\n'+JSON.stringify(contextEnvelope)},{role:'user',content:message}];
    const out=await this.request(this.base,'/v1/chat/completions',{method:'POST',body:{messages,max_tokens:maxTokens,temperature:0}});
    const text=out?.choices?.[0]?.message?.content ?? out?.response_text ?? out?.text;
    if(typeof text!=='string'||!text.trim())throw new Error('LOCAL_MODEL_EMPTY_RESPONSE');
    return {text,model:out.model||'LOCAL_MODEL',response_digest:sha256(text),authority_effect:'NONE'};
  }
}
module.exports={LocalModelClient};
