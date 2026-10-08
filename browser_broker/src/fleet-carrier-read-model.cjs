'use strict';
// Projection of the existing Mission Control fleet carrier, not a Docker client,
// material runtime attestation or a source of worker execution authority.
const fs=require('node:fs');
const path=require('node:path');
const {createHash}=require('node:crypto');

const CARRIER_REL=path.join('r23-autonomy','fleet-currentness.json');
const CARRIER_SCHEMA='lion.docker-local-model-fleet-currentness/v1';
const MAX_BYTES=256*1024;
const MAX_AGE_MS=90*1000;
const MAX_FUTURE_SKEW_MS=3000;
const SHA40=/^[a-f0-9]{40}$/;
const SHA64=/^[a-f0-9]{64}$/;

function canonical(value){
 if(Array.isArray(value))return '['+value.map(canonical).join(',')+']';
 if(value!==null&&typeof value==='object'){
  return '{'+Object.keys(value).sort().map(k=>JSON.stringify(k)+':'+canonical(value[k])).join(',')+'}';
 }
 return JSON.stringify(value);
}
function digest(value){return createHash('sha256').update(canonical(value)).digest('hex')}
function fallback(reason,now,kind='UNAVAILABLE'){
 return {
  source:'MOON_CANONICAL_FLEET_CARRIER_READ_ONLY',
  currentness:kind,reason,observation_time:null,checked_at:now.toISOString(),
  carrier_digest_verified:false,provider_ready:false,authority_effect:'NONE',
  deployment_binding:'NOT_ATTESTED',workers:[],materialized:null,ready:null,
  observed_runtime_state:'UNKNOWN',source_head:null,source_tree:null,
 };
}
function observeFleetCarrier({root,readFs=fs,now=()=>new Date()}={}){
 if(typeof root!=='string'||!path.isAbsolute(root))throw Error('TRUSTED_LOCAL_ROOT_REQUIRED');
 const checked=now();
 if(!(checked instanceof Date)||!Number.isFinite(checked.getTime()))throw Error('OBSERVATION_CLOCK_INVALID');
 const filename=path.join(root,CARRIER_REL);
 let stat;
 try{stat=readFs.lstatSync(filename)}
 catch{return fallback('CARRIER_NOT_FOUND',checked)}
 if(!stat.isFile()||stat.isSymbolicLink()||stat.size<=0||stat.size>MAX_BYTES)
  return fallback('CARRIER_FILE_TYPE_OR_SIZE_INVALID',checked,'INVALID');
 let value;
 try{
  value=JSON.parse(readFs.readFileSync(filename,'utf8'));
 }catch{return fallback('CARRIER_NOT_VALID_JSON',checked,'INVALID')}
 if(value===null||Array.isArray(value)||typeof value!=='object'||value.schema!==CARRIER_SCHEMA)
  return fallback('CARRIER_SCHEMA_MISMATCH',checked,'INVALID');
 const signature=value.currentness_digest;
 if(typeof signature!=='string'||!SHA64.test(signature))
  return fallback('CARRIER_DIGEST_MISSING_OR_MALFORMED',checked,'INVALID');
 const unsigned={...value};delete unsigned.currentness_digest;
 if(digest(unsigned)!==signature)
  return fallback('CARRIER_DIGEST_MISMATCH',checked,'INVALID');
 const time=Date.parse(String(value.observed_at||''));
 const workers=value.workers;
 const head=value.source_head,tree=value.source_tree;
 const basic=(
  value.physical_host==='MOON' &&
  value.materialized===32 &&
  Number.isSafeInteger(value.ready)&&value.ready>=0&&value.ready<=32 &&
  Array.isArray(workers)&&workers.length===32 &&
  typeof head==='string'&&SHA40.test(head) &&
  typeof tree==='string'&&SHA40.test(tree) &&
  Number.isFinite(time)
 );
 if(!basic)return fallback('CARRIER_IDENTITY_OR_SHAPE_INVALID',checked,'INVALID');
 const expected=Array.from({length:32},(_,i)=>'MD'+String(i+1).padStart(3,'0'));
 const ids=workers.map(w=>w&&w.material_worker_id);
 const containers=workers.map(w=>w&&w.container_id);
 if(ids.some(x=>typeof x!=='string')||ids.slice().sort().join(',')!==expected.join(',')||
    containers.some(x=>typeof x!=='string'||!SHA64.test(x))||
    new Set(containers).size!==32)
  return fallback('CARRIER_WORKER_IDENTITY_INVALID',checked,'INVALID');
 const elapsed=checked.getTime()-time;
 const freshness=elapsed < -MAX_FUTURE_SKEW_MS?'FUTURE':
                 elapsed>MAX_AGE_MS?'STALE':'FRESH';
 const ready=(value.state==='READY'&&value.ready===32&&
   workers.every(w=>w.container_state==='running'&&w.ready===true));
 const parked=(value.state==='DEGRADED'&&value.ready===0&&
   workers.every(w=>w.container_state==='exited'&&w.ready===false));
 return {
  source:'MOON_CANONICAL_FLEET_CARRIER_READ_ONLY',
  currentness:freshness,reason:freshness==='FRESH'?null:'CARRIER_'+freshness,
  observation_time:new Date(time).toISOString(),
  checked_at:checked.toISOString(),
  age_seconds:Math.round(elapsed/1000),
  carrier_digest_verified:true,
  digest:signature,
  observed_runtime_state:ready?'READY_OBSERVED':parked?'PARKED_OBSERVED':'DEGRADED_OBSERVED',
  provider_ready:false,
  deployment_binding:'NOT_ATTESTED',
  authority_effect:'NONE',
  materialized:32,ready:value.ready,source_head:head,source_tree:tree,
  workers:workers.map(w=>({
   worker_id:w.material_worker_id,
   container_id_prefix:w.container_id.slice(0,12),
   container_state:String(w.container_state||'UNKNOWN').slice(0,36),
   ready:w.ready===true,
   heartbeat_observed_at:typeof w.heartbeat_observed_at==='string'?
    w.heartbeat_observed_at.slice(0,45):null,
  })),
 };
}
module.exports={observeFleetCarrier,canonical,digest,CARRIER_SCHEMA,MAX_AGE_MS};
