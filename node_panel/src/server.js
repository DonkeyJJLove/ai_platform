#!/usr/bin/env node
'use strict';
const path=require('node:path'),fs=require('node:fs');
const express=require('express');
const {ThreadStore}=require('./thread-store');
const {ProviderRegistry}=require('./provider-registry');
const {ProviderRouter}=require('./provider-router');
const {LocalModelClient}=require('./local-model');
const {MissionControlClient}=require('./mission-control');
const {OperatorControlClient}=require('./operator-control');
const {SecureMcpRelay}=require('./secure-mcp-relay');
const {SaasDelivery}=require('./saas-delivery');
const {TurnReconciler}=require('./turn-reconciler');
const {RelevanceEngine}=require('./relevance-engine');
const {buildContextEnvelope}=require('./context-envelope');
const {ReadinessProbe}=require('./readiness');
const {sha256,id,canonicalJson}=require('./canonical');

function argvMap(argv){const out={};for(let i=2;i<argv.length;i++){if(!argv[i].startsWith('--'))continue;const k=argv[i].slice(2);const v=argv[i+1]&&!argv[i+1].startsWith('--')?argv[++i]:true;out[k]=v;}return out;}
function statusError(res,e){const status=Number(e.status)||(/NOT_FOUND/.test(e.message)?404:400);res.status(status).json({error:e.message,authority_effect:'NONE'});}
function sourceItems(body){return Array.isArray(body.sources)?body.sources:[];}
function buildRelevance(engine,thread,message,body,requestLineage=[]){return engine.evaluate({query:message,thread,messages:thread.messages,sources:sourceItems(body),observations:Array.isArray(body.observations)?body.observations:[],currentness:body.currentness||{},entities:Array.isArray(body.entities)?body.entities:[],requestLineage,evaluation_time:body.evaluation_time||null});}

function createRuntime(options={}){
  const config={port:Number(options.port||8780),host:options.host||'127.0.0.1',threadDb:options.threadDb||path.resolve('.lion-r18/threads.db'),modelBase:options.modelBase||'http://127.0.0.1:8772',missionControlBase:options.missionControlBase||'http://127.0.0.1:8766',operatorControlBase:options.operatorControlBase||'http://127.0.0.1:8767',ingressBase:options.ingressBase||'http://127.0.0.1:8791',mcpTransportBase:options.mcpTransportBase||'http://127.0.0.1:8792',journalDir:options.journalDir||path.resolve('.lion-r18/relay'),mediatorKey:options.mediatorKey||MissionControlClient.keyFromFile(options.mediatorKeyFile),ingressToken:options.ingressToken||MissionControlClient.keyFromFile(options.ingressTokenFile)};
  const store=options.store||new ThreadStore(config.threadDb),registry=options.registry||new ProviderRegistry(),local=options.local||new LocalModelClient({base:config.modelBase}),mc=options.missionControl||new MissionControlClient({base:config.missionControlBase,mediatorKey:config.mediatorKey}),operator=options.operatorControl||new OperatorControlClient({base:config.operatorControlBase}),relevance=options.relevance||new RelevanceEngine();
  let readiness;
  const router=options.router||new ProviderRouter({registry,readiness:()=>readiness?.snapshot?.()||{}});
  const relay=options.relay||new SecureMcpRelay({store,missionControl:mc,ingressBase:config.ingressBase,tunnelBase:config.mcpTransportBase,ingressToken:config.ingressToken,journalDir:config.journalDir});
  const delivery=options.delivery||new SaasDelivery({store});
  const reconciler=options.reconciler||new TurnReconciler({store,missionControl:mc,relay,delivery});
  readiness=options.readiness||new ReadinessProbe({missionControl:mc,operatorControl:operator,localModel:local,relay,panelRuntime:'NODE_EXPRESS_R18',externalConsumerReady:()=>false});
  const app=express();app.disable('x-powered-by');app.use(express.json({limit:'256kb'}));app.use(express.static(path.resolve(__dirname,'../static')));
  app.get('/health',(req,res)=>res.json({ok:true,status:'ok',runtime:'NODE_EXPRESS_R18',port:config.port,browser_automation:'DISABLED_BY_POLICY',authority_effect:'NONE'}));
  app.get('/api/state',async(req,res)=>{const state=await readiness.probe();res.json({...state,providers:registry.list(),semantic_context_entropy_metrics:'AVAILABLE_PER_CONTEXT',model_internal_latent_state:'UNOBSERVABLE',latent_proxy_state:'OBSERVABLE_DERIVED_STATE'});});
  app.get('/api/debug/fabric',(req,res)=>res.json({...store.debugState(),readiness:readiness.snapshot(),authority_effect:'NONE'}));
  app.get('/api/threads',(req,res)=>res.json({threads:store.listThreads()}));
  app.post('/api/threads',(req,res)=>{try{res.status(201).json(store.createThread(req.body?.title));}catch(e){statusError(res,e);}});
  app.get('/api/threads/:thread_id',(req,res)=>{try{res.json(store.getThread(req.params.thread_id));}catch(e){statusError(res,e);}});
  app.patch('/api/threads/:thread_id',(req,res)=>{try{res.json(store.renameThread(req.params.thread_id,req.body?.title));}catch(e){statusError(res,e);}});
  app.delete('/api/threads/:thread_id',async(req,res)=>{try{const threadId=req.params.thread_id,bindings=store.pendingBindings().filter(x=>x.thread_id===threadId);for(const b of bindings){try{await mc.cancelRequest(b.request_id);store.markReconciliation(b.request_id,'CANCELLED','thread deleted; broker cancellation observed');}catch{store.markReconciliation(b.request_id,'ORPHANED_THREAD','thread deleted; cancellation unavailable or unknown');}}res.json(store.tombstoneThread(threadId));}catch(e){statusError(res,e);}});
  app.post('/api/threads/:thread_id/user',(req,res)=>{try{const key=String(req.body?.dedupe_key||'user:'+id());res.status(201).json(store.appendUserOnce(req.params.thread_id,req.body?.content,key,req.body?.meta||{}));}catch(e){statusError(res,e);}});
  app.post('/api/threads/:thread_id/assistant',(req,res)=>{try{if(req.body?.authority_effect&&req.body.authority_effect!=='NONE')throw new Error('ASSISTANT_AUTHORITY_DENIED');const key=String(req.body?.dedupe_key||'assistant:'+id());res.status(201).json(store.appendAssistantOnce(req.params.thread_id,req.body?.content,key,req.body?.meta||{}));}catch(e){statusError(res,e);}});
  app.get('/api/missions/recent',async(req,res)=>{try{res.json(await mc.recentMissions(req.query.view||'operational'));}catch(e){statusError(res,e);}});
  app.get('/api/missions/:mission_id/process',async(req,res)=>{try{res.json(await mc.missionProcess(req.params.mission_id));}catch(e){statusError(res,e);}});
  app.get('/api/operator/state',async(req,res)=>{try{res.json(await operator.state(req.query.mission_id||''));}catch(e){statusError(res,e);}});
  app.post('/api/threads/:thread_id/chat',async(req,res)=>{
    const threadId=req.params.thread_id,message=String(req.body?.message||req.body?.content||'').trim();if(!message)return res.status(400).json({error:'MESSAGE_REQUIRED'});
    try{
      const thread=store.getThread(threadId),rel=buildRelevance(relevance,thread,message,req.body||[]),provider=router.select(req.body?.route||'AUTO',{relevance:rel});if(provider.authority_effect!=='NONE')throw new Error('PROVIDER_AUTHORITY_WIDENING');
      if(provider.provider_id==='SWARM')return res.status(409).json({error:'SWARM_REQUIRES_EXPLICIT_MISSION_SCOPED_PATH',authority_effect:'NONE'});
      if(provider.provider_id==='LOCAL_MODEL'){
        const requestId='local-'+id(),env=buildContextEnvelope({thread,requestId,intent:message,relevance:rel,messages:thread.messages,sources:sourceItems(req.body||{}),observations:req.body?.observations||[],currentness:req.body?.currentness||{},providerRequirements:{provider_id:'LOCAL_MODEL'},selectedProvider:'LOCAL_MODEL'}),requestHash=sha256(canonicalJson({thread_id:threadId,message,context_digest:env.context_digest,provider_id:'LOCAL_MODEL'}));
        store.bindRequest({thread_id:threadId,request_id:requestId,request_hash:requestHash,provider_id:'LOCAL_MODEL',context_digest:env.context_digest,question:message,context_json:canonicalJson(env),state:'PENDING'});store.appendUserOnce(threadId,message,'local-user:'+requestId,{provider_id:'LOCAL_MODEL',request_id:requestId,context_digest:env.context_digest,authority_effect:'NONE'});
        const result=await local.complete({contextEnvelope:env,message});const saved=store.appendAssistantOnce(threadId,result.text,'local:'+requestId,{provider_id:'LOCAL_MODEL',request_id:requestId,context_digest:env.context_digest,response_digest:result.response_digest,authority_effect:'NONE'});store.markDelivery({request_id:requestId,thread_id:threadId,state:'DELIVERED',message_id:saved.message_id,dedupe_key:'local:'+requestId});store.markReconciliation(requestId,'RECONCILED','direct local model response appended to exact originating thread');return res.json({request_id:requestId,provider_id:'LOCAL_MODEL',thread_id:threadId,message_id:saved.message_id,context_digest:env.context_digest,response_digest:result.response_digest,state:'RECONCILED',authority_effect:'NONE'});
      }
      const broker=await mc.createSaasRequest({thread_id:threadId,question:message});const requestId=broker.request_id;if(!requestId)throw new Error('BROKER_REQUEST_ID_MISSING');
      const env=buildContextEnvelope({thread,requestId,intent:message,relevance:rel,messages:thread.messages,sources:sourceItems(req.body||{}),observations:req.body?.observations||[],currentness:req.body?.currentness||{},providerRequirements:{provider_id:'CHATGPT_SAAS',transport:'MCP',completion_owner:'ACTIVE_CHATGPT_SAAS_SESSION'},selectedProvider:'CHATGPT_SAAS'}),requestHash=sha256(canonicalJson({thread_id:threadId,request_id:requestId,message,context_digest:env.context_digest,provider_id:'CHATGPT_SAAS'}));
      const binding=store.bindRequest({thread_id:threadId,request_id:requestId,request_hash:requestHash,provider_id:'CHATGPT_SAAS',context_digest:env.context_digest,question:message,context_json:canonicalJson(env),state:'CREATED'});store.appendUserOnce(threadId,message,'saas-user:'+requestId,{provider_id:'CHATGPT_SAAS',saas_request_id:requestId,context_digest:env.context_digest,authority_effect:'NONE'});
      let turn=null,state='PENDING';if(await relay.ready()){try{turn=await relay.dispatch({binding,question:message,contextEnvelope:env});state='WAITING_FOR_SAAS_CONSUMER';}catch(e){store.markReconciliation(requestId,'SEND_UNKNOWN','turn dispatch outcome unknown: '+e.message);state='SEND_UNKNOWN';}}else store.updateRequestState(requestId,'PENDING');
      return res.status(202).json({request_id:requestId,turn_id:turn?.turn_id||null,thread_id:threadId,provider_id:'CHATGPT_SAAS',state,context_digest:env.context_digest,activation_owner:'ACTIVE_CHATGPT_SAAS_SESSION',chatgpt_host_triggered_autonomous_inference:'NOT_MATERIALIZED',authority_effect:'NONE'});
    }catch(e){statusError(res,e);}
  });
  return {app,config,store,registry,router,local,mc,operator,relay,delivery,reconciler,readiness};
}
function main(){
  const a=argvMap(process.argv),runtime=createRuntime({port:a.port,host:a.host,threadDb:a['thread-db'],modelBase:a.model,missionControlBase:a['mission-control-url'],operatorControlBase:a['operator-control-url'],ingressBase:a['turn-ingress-url'],mcpTransportBase:a['mcp-transport-url'],journalDir:a['relay-state-dir'],mediatorKeyFile:a['mediator-key-file'],ingressTokenFile:a['ingress-token-file']});
  runtime.reconciler.start();const server=runtime.app.listen(runtime.config.port,runtime.config.host,()=>console.log(JSON.stringify({status:'LISTENING',runtime:'NODE_EXPRESS_R18',host:runtime.config.host,port:runtime.config.port,pid:process.pid,browser_automation:'DISABLED_BY_POLICY',authority_effect:'NONE'})));
  const stop=()=>{runtime.reconciler.stop();server.close(()=>{runtime.store.close();process.exit(0)});};process.on('SIGINT',stop);process.on('SIGTERM',stop);
}
if(require.main===module)main();
module.exports={createRuntime,argvMap};
