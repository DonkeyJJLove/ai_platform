#!/usr/bin/env node
'use strict';
const {jsonRequest}=require('../src/http-json');
const {id}=require('../src/canonical');
function args(){const a={writeCanary:false};for(let i=2;i<process.argv.length;i++){if(process.argv[i]==='--write-canary')a.writeCanary=true;else if(process.argv[i]==='--panel')a.panel=process.argv[++i];}return a;}
async function probe(base,path='/health'){try{const v=await jsonRequest(base,path,{timeoutMs:1500});return {reachable:true,response:v};}catch(e){return {reachable:false,error:e.message};}}
async function main(){const a=args(),panel=a.panel||'http://127.0.0.1:8780',targets={mission_control:'http://127.0.0.1:8766',operator_control:'http://127.0.0.1:8767',local_model:'http://127.0.0.1:8772',panel,turn_ingress:'http://127.0.0.1:8791',mcp_transport:'http://127.0.0.1:8792'},out={schema:'lion.r18.live-compat/v1',mode:a.writeCanary?'ISOLATED_AUTHORITY_NONE_CANARY':'READ_ONLY',authority_effect:'NONE',targets:{}};for(const [k,b] of Object.entries(targets))out.targets[k]=await probe(b,k==='panel'?'/health':'/health');
  if(a.writeCanary){const thread=await jsonRequest(panel,'/api/threads',{method:'POST',body:{title:'R18 compatibility canary '+id().slice(0,8)}});try{out.canary={thread_id:thread.thread_id,state:'CREATED',authority_effect:'NONE'};}finally{try{await jsonRequest(panel,'/api/threads/'+encodeURIComponent(thread.thread_id),{method:'DELETE',body:{authority_effect:'NONE'}});out.canary.cleanup='DELETED';}catch(e){out.canary.cleanup='UNKNOWN:'+e.message;}}}
  process.stdout.write(JSON.stringify(out,null,2)+'\n');
}
main().catch(e=>{console.error(JSON.stringify({status:'FAIL',error:e.message,authority_effect:'NONE'}));process.exitCode=1});
