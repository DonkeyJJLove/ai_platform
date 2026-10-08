'use strict';
const fs = require('node:fs');
const path = require('node:path');

const MC = 'http://127.0.0.1:8766';
const PANEL = 'http://127.0.0.1:8780';
const MODEL = 'http://127.0.0.1:8772';
const MAX_FILE = 1024*1024;
function compactError(error){return String(error && error.name || 'UNAVAILABLE').slice(0,64)}
async function jsonGet(fetcher,url,timeoutMs=2800){
 const controller=new AbortController();
 const timer=setTimeout(()=>controller.abort(),timeoutMs);
 try {
  const r=await fetcher(url,{method:'GET',signal:controller.signal,redirect:'error',headers:{accept:'application/json'}});
  if(!r.ok)throw Error('UPSTREAM_HTTP_'+r.status);
  const length=Number(r.headers && r.headers.get('content-length')||0);
  if(length>128*1024)throw Error('UPSTREAM_BODY_TOO_LARGE');
  const txt=await r.text();
  if(txt.length>128*1024)throw Error('UPSTREAM_BODY_TOO_LARGE');
  return JSON.parse(txt);
 }finally{clearTimeout(timer)}
}
function safeFile(readFs,file,max=MAX_FILE){
 try{
  const st=readFs.lstatSync(file);
  if(!st.isFile()||st.isSymbolicLink()||st.size>max)return null;
  return readFs.readFileSync(file,'utf8');
 }catch{return null}
}
function redact(line){
 const x=String(line||'').slice(0,420);
 if(/token|password|authorization:|secret|bearer |private.key/i.test(x))return '[REDACTED_SECRET_BEARING_LINE]';
 return x;
}
function tail(text,limit=24){
 return (text||'').split(/\r?\n/).slice(-limit).map(redact);
}
function createReadModel({root,fetcher=fetch,readFs=fs,now=()=>new Date()}){
 if(typeof root!=='string'||!path.isAbsolute(root))throw Error('ROOT_REQUIRED');
 const originalSnapshot=path.join(root,'desktop','observability-preview','LION_OBSERVABILITY_SNAPSHOT_20261008.json');
 async function observe(scope){
  if(!['cluster','system'].includes(scope))throw Error('UNKNOWN_READ_SCOPE');
  const targets=[
   ['mission',MC+'/health'],['missions',MC+'/api/v3/missions/recent?view=operational'],
   ['broker',MC+'/api/v3/saas-broker/status'],['panel',PANEL+'/health'],
   ['model',MODEL+'/health'],['models',MODEL+'/v1/models'],
  ];
  const results=await Promise.allSettled(targets.map(([,u])=>jsonGet(fetcher,u)));
  const live={};
  for(let i=0;i<targets.length;i++){
   const x=results[i],name=targets[i][0];
   if(x.status==='fulfilled')live[name]=x.value;
   else live[name]={observation_error:compactError(x.reason)};
  }
  let stored={};
  try{
   const s=safeFile(readFs,originalSnapshot,512*1024);
   if(s){const j=JSON.parse(s);if(j.schema==='lion.desktop-observability-preview/v1')stored=j}
  }catch{}
  const preferred=path.join(root,'staging','recovery-e0r3-20261008','desktop-launcher.log');
  const alternate=path.join(root,'staging','recovery-e0r4-20261008','desktop-launcher.log');
  const text=safeFile(readFs,alternate,180*1024)||safeFile(readFs,preferred,180*1024)||'';
  const current=live.missions||{};
  const recent=Array.isArray(current.missions)?current.missions.slice(0,20).map(m=>({
   mission_id:String(m.mission_id||'').slice(0,180),
   state:String(m.state||'UNKNOWN').slice(0,60),
   runtime_state:String(m.runtime_state||'UNKNOWN').slice(0,120),
   materialized:Number.isSafeInteger(m.materialized)?m.materialized:null,
   ready:Number.isSafeInteger(m.ready)?m.ready:null,
  })):[];
  const workerSnapshot=Array.isArray(stored.cluster?.workers)?stored.cluster.workers.slice(0,32):[];
  const repoSnapshot=Array.isArray(stored.federation?.repositories)?stored.federation.repositories.slice(0,20):[];
  const modelData=Array.isArray(live.models?.data)?live.models.data.slice(0,2).map(x=>({
   label:path.win32.basename(String(x.id||'unknown')).slice(0,120),
  })):[];
  return {
   schema:'lion.operator-read-model/v1',scope,
   observed_at:now().toISOString(),
   authority_effect:'NONE',execution_effect:'NONE',data_class:'READ_ONLY_MIXED_CURRENTNESS',
   endpoints:{
    mission_control:live.mission?.status==='ok'?'HEALTHY':String(live.mission?.observation_error||'UNKNOWN'),
    panel:live.panel?.status==='ok'?'HEALTHY':String(live.panel?.observation_error||'UNKNOWN'),
    model:live.model?.status==='ok'?'HEALTHY':String(live.model?.observation_error||'UNKNOWN'),
    broker_state:String(live.broker?.state||live.broker?.observation_error||'UNKNOWN').slice(0,70),
    broker_pending:Number.isInteger(live.broker?.pending_count)?live.broker.pending_count:null,
   },
   missions:recent,
   material_workers:{source:'STORED_SNAPSHOT_NOT_LIVE_DOCKER',snapshot_at:stored.generated_at||null,workers:workerSnapshot},
   repos:{source:'STORED_GITHUB_HEADS_NOT_LIVE',snapshot_at:stored.generated_at||null,repositories:repoSnapshot},
   artifacts:{source:'STORED_LEDGER_METADATA_NOT_BYTES',snapshot_at:stored.generated_at||null,
    types:stored.cluster?.historical_artifact_metadata?.type_counts||{},
    total:stored.cluster?.historical_artifact_metadata?.count||0,
    download:'NOT_EXPOSED_BY_THIS_READ_MODEL'},
   model_names:modelData,
   logs:{source:'ALLOWLISTED_DESKTOP_LAUNCHER',lines:tail(text)},
  };
 }
 return {observe};
}
module.exports={createReadModel,jsonGet,redact,tail};
