'use strict';
const {randomUUID,createHash}=require('node:crypto');
const ENDPOINT='http://127.0.0.1:8772';
const sha=x=>createHash('sha256').update(x).digest('hex');
const limitText=(s,n)=>typeof s==='string' && s.trim() && s.length<=n && !s.includes('\u0000');
function safeMessages(value){
 if(!Array.isArray(value)||value.length>10)throw Error('LOCAL_CONTEXT_BOUND_EXCEEDED');
 return value.map(item=>{
  if(!item||!['user','assistant'].includes(item.role)||!limitText(item.content,5000))
   throw Error('LOCAL_HISTORY_INVALID');
  return {role:item.role,content:item.content};
 });
}
function createLocalAdvisory({fetcher=fetch,now=()=>new Date()}={}){
 let inFlight=false;
 async function requestJson(url,body,ms){
  const controller=new AbortController();
  const timer=setTimeout(()=>controller.abort(),ms);
  try{
   const response=await fetcher(url,{method:body?'POST':'GET',
    headers:{'Content-Type':'application/json',accept:'application/json'},
    body:body?JSON.stringify(body):undefined,redirect:'error',signal:controller.signal});
   if(!response.ok)throw Error('LOCAL_MODEL_HTTP_'+response.status);
   const data=await response.text();
   if(data.length>192*1024)throw Error('LOCAL_MODEL_RESPONSE_TOO_LARGE');
   return JSON.parse(data);
  }finally{clearTimeout(timer)}
 }
 async function status(){
  try{
   const [health,models]=await Promise.all([
    requestJson(ENDPOINT+'/health',null,4500),
    requestJson(ENDPOINT+'/v1/models',null,4500),
   ]);
   const id=String(models?.data?.[0]?.id||'');
   if(!id)throw Error('MODEL_ID_MISSING');
   return {state:'READY',model_label:id.split(/[\\/]/).pop().slice(0,120),
    observed_at:now().toISOString(),authority_effect:'NONE',
    binding:'UNBOUND_LOCAL_ADVISORY'};
  }catch(error){
   return {state:'UNREACHABLE_OR_UNVERIFIED',reason:String(error.name||'ERROR').slice(0,55),
    observed_at:now().toISOString(),authority_effect:'NONE',
    binding:'UNBOUND_LOCAL_ADVISORY'};
  }
 }
 async function ask(args){
  if(inFlight)throw Error('LOCAL_MODEL_REQUEST_IN_FLIGHT');
  if(!args||!limitText(args.prompt,8000))throw Error('LOCAL_PROMPT_INVALID');
  const previous=safeMessages(args.history||[]);
  if(previous.length && previous[previous.length-1].role!=='assistant')throw Error('LOCAL_HISTORY_ORDER_INVALID');
  inFlight=true;
  const id=randomUUID();
  const requestHash=sha(JSON.stringify({prompt:args.prompt,history:previous}));
  try{
   const catalog=await requestJson(ENDPOINT+'/v1/models',null,5000);
   const modelId=catalog?.data?.[0]?.id;
   if(typeof modelId!=='string'||modelId.length>600||!modelId)throw Error('MODEL_ID_UNVERIFIED');
   const messages=[
    {role:'system',content:'You are an independent LOCAL advisory model. You have no tools, authority, mission binding, or access to hidden system context. Do not claim an action occurred.'},
    ...previous,{role:'user',content:args.prompt}
   ];
   const body={model:modelId,messages,stream:false,max_tokens:384,temperature:0.35};
   const result=await requestJson(ENDPOINT+'/v1/chat/completions',body,110000);
   const reply=result?.choices?.[0]?.message?.content;
   if(typeof reply!=='string'||reply.length>48000)throw Error('LOCAL_MODEL_INVALID_RESPONSE');
   return {
    schema:'lion.local-advisory-response/v1',request_id:id,
    request_digest:requestHash,response_digest:sha(reply),message:reply,
    model_label:modelId.split(/[\\/]/).pop().slice(0,120),
    observed_at:now().toISOString(),model_transport:'HTTP_127_0_0_1_8772',
    conversation_id:null,mission_id:null,context_projection_digest:null,
    origin:'OPERATOR_UNBOUND_LOCAL_CHAT',authority_effect:'NONE',
    runtime_effect:'MODEL_INFERENCE_ONLY',mission_binding:'NOT_BOUND',
    durable_mission_receipt:'NOT_CREATED'
   };
  }finally{inFlight=false}
 }
 return {ask,status,isBusy:()=>inFlight};
}
module.exports={createLocalAdvisory,safeMessages};
