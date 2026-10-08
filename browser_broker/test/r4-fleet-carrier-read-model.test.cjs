'use strict';
const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const os=require('node:os');
const path=require('node:path');
const {observeFleetCarrier,digest,CARRIER_SCHEMA}=require('../src/fleet-carrier-read-model.cjs');
const NOW='2026-10-08T18:59:30.000Z';
function fixture(){
 const root=fs.mkdtempSync(path.join(os.tmpdir(),'lion-fleet-carrier-'));
 const file=path.join(root,'r23-autonomy','fleet-currentness.json');
 fs.mkdirSync(path.dirname(file),{recursive:true});
 const value={
  schema:CARRIER_SCHEMA,observed_at:'2026-10-08T18:59:20.000Z',
  physical_host:'MOON',source_head:'a'.repeat(40),source_tree:'b'.repeat(40),
  materialized:32,ready:0,state:'DEGRADED',
  workers:Array.from({length:32},(_,i)=>({
   material_worker_id:'MD'+String(i+1).padStart(3,'0'),
   container_id:(i+1).toString(16).padStart(64,'0'),
   container_state:'exited',ready:false,
   heartbeat_observed_at:'2026-10-08T18:57:00.000Z',
  }))
 };
 const save=()=>fs.writeFileSync(file,JSON.stringify({...value,currentness_digest:digest(value)}));
 const read=(time=NOW)=>observeFleetCarrier({root,now:()=>new Date(time)});
 save();
 return {root,file,value,save,read,close:()=>fs.rmSync(root,{recursive:true,force:true})};
}
test('32 parked carrier workers are identity checked and current, never execution-ready',()=>{
 const f=fixture();
 try{
  const v=f.read();
  assert.equal(v.currentness,'FRESH');
  assert.equal(v.carrier_digest_verified,true);
  assert.equal(v.observed_runtime_state,'PARKED_OBSERVED');
  assert.equal(v.materialized,32);assert.equal(v.ready,0);
  assert.equal(v.provider_ready,false);
  assert.equal(v.authority_effect,'NONE');
  assert.equal(v.deployment_binding,'NOT_ATTESTED');
  assert.equal(v.workers.length,32);
  assert.deepEqual(v.workers.map(w=>w.worker_id).slice(0,2),['MD001','MD002']);
  assert.equal(v.workers[0].container_id_prefix,'000000000000');
  assert(!('runtime_contract_sha256' in v.workers[0]));
 }finally{f.close()}
});
test('READY carrier observation is not mission admission or verified provider',()=>{
 const f=fixture();
 try{
  f.value.ready=32;f.value.state='READY';
  for(const w of f.value.workers){w.ready=true;w.container_state='running'}
  f.save();
  const v=f.read();
  assert.equal(v.observed_runtime_state,'READY_OBSERVED');
  assert.equal(v.provider_ready,false);
  assert.equal(v.deployment_binding,'NOT_ATTESTED');
 }finally{f.close()}
});
test('tampered worker state and digest substitution are rejected',()=>{
 const f=fixture();
 try{
  const data=JSON.parse(fs.readFileSync(f.file,'utf8'));
  data.workers[0].container_state='running';
  fs.writeFileSync(f.file,JSON.stringify(data));
  const v=f.read();
  assert.equal(v.currentness,'INVALID');
  assert.equal(v.reason,'CARRIER_DIGEST_MISMATCH');
  assert.equal(v.workers.length,0);
 }finally{f.close()}
});
test('validly rehashed duplicate worker identity and duplicate container fail',()=>{
 const f=fixture();
 try{
  f.value.workers[31].material_worker_id='MD001';f.save();
  assert.equal(f.read().reason,'CARRIER_WORKER_IDENTITY_INVALID');
  f.value.workers[31].material_worker_id='MD032';
  f.value.workers[31].container_id=f.value.workers[0].container_id;f.save();
  assert.equal(f.read().reason,'CARRIER_WORKER_IDENTITY_INVALID');
 }finally{f.close()}
});
test('stale and future carrier timestamps are explicit, never fresh',()=>{
 const f=fixture();
 try{
  assert.equal(f.read('2026-10-08T19:04:30.000Z').currentness,'STALE');
  assert.equal(f.read('2026-10-08T18:58:50.000Z').currentness,'FUTURE');
  assert.equal(f.read('2026-10-08T19:04:30.000Z').provider_ready,false);
 }finally{f.close()}
});
test('missing carrier is not fabricated into ready workers',()=>{
 const f=fixture();
 try{
  fs.unlinkSync(f.file);
  const v=f.read();
  assert.equal(v.currentness,'UNAVAILABLE');
  assert.equal(v.workers.length,0);
  assert.equal(v.provider_ready,false);
 }finally{f.close()}
});
test('reported filesystem symlink is denied before content read on every platform',()=>{
 const f=fixture();
 try{
  const fakeFs={
   lstatSync:()=>({isFile:()=>true,isSymbolicLink:()=>true,size:100}),
   readFileSync:()=>{throw Error('FILE_BYTES_MUST_NEVER_BE_READ')}
  };
  const v=observeFleetCarrier({root:f.root,readFs:fakeFs,now:()=>new Date(NOW)});
  assert.equal(v.currentness,'INVALID');
  assert.equal(v.reason,'CARRIER_FILE_TYPE_OR_SIZE_INVALID');
  if(process.platform!=='win32'){
   const target=f.file+'.real';
   fs.renameSync(f.file,target);fs.symlinkSync(target,f.file);
   const actual=f.read();
   assert.equal(actual.currentness,'INVALID');
   assert.equal(actual.reason,'CARRIER_FILE_TYPE_OR_SIZE_INVALID');
  }
 }finally{f.close()}
});
test('oversized carrier is denied without reading bytes',()=>{
 const f=fixture();
 try{
  fs.writeFileSync(f.file,'x'.repeat(300000));
  const v=f.read();
  assert.equal(v.currentness,'INVALID');
  assert.equal(v.reason,'CARRIER_FILE_TYPE_OR_SIZE_INVALID');
 }finally{f.close()}
});
test('carrier shape and source hashes are exact even with a rehashed payload',()=>{
 const f=fixture();
 try{
  f.value.source_head='not-git-hash';f.save();
  assert.equal(f.read().reason,'CARRIER_IDENTITY_OR_SHAPE_INVALID');
  f.value.source_head='a'.repeat(40);
  f.value.workers[0].container_id='short-id';f.save();
  assert.equal(f.read().reason,'CARRIER_WORKER_IDENTITY_INVALID');
 }finally{f.close()}
});
test('no shell/Docker/Mission Control mutations are present in the reader',()=>{
 const source=fs.readFileSync(require.resolve('../src/fleet-carrier-read-model.cjs'),'utf8');
 for(const needle of ['child_process','spawn(','execFile','docker ps','docker stop','http.request','fetch('])
  assert(!source.includes(needle),needle);
 assert(source.includes("CARRIER_REL=path.join('r23-autonomy','fleet-currentness.json')"));
});
