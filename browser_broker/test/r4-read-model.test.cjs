'use strict';
const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const os=require('node:os');
const path=require('node:path');
const {createReadModel,redact,tail}=require('../src/desktop-read-model.cjs');
const response=v=>({ok:true,headers:{get:()=>null},text:async()=>JSON.stringify(v)});
function fixture(overrides={}){
 const root=fs.mkdtempSync(path.join(os.tmpdir(),'lion-readmodel-r4-'));
 const snapshot=path.join(root,'desktop','observability-preview','LION_OBSERVABILITY_SNAPSHOT_20261008.json');
 fs.mkdirSync(path.dirname(snapshot),{recursive:true});
 fs.writeFileSync(snapshot,JSON.stringify({
  schema:'lion.desktop-observability-preview/v1',generated_at:'2026-10-08T16:54:01Z',
  cluster:{workers:[{name:'lion-r24-md001',state:'exited'}],
   historical_artifact_metadata:{count:95,type_counts:{RECON_PHASE_SUMMARY:22}}},
  federation:{repositories:[{name:'ai_platform',branch:'master',head_sha:'e'.repeat(40)}]}
 }));
 const dir=path.join(root,'staging','recovery-e0r3-20261008');
 fs.mkdirSync(dir,{recursive:true});
 fs.writeFileSync(path.join(dir,'desktop-launcher.log'),
  '2026-10-08T17:01Z ELECTRON_READY\nBearer hidden-token\n');
 const fetcher=overrides.fetcher||(async url=>{
  if(url.endsWith('/api/v3/missions/recent?view=operational'))return response({missions:[{mission_id:'LION-MISSION',state:'RUNNING',runtime_state:'AWAIT_PROVIDER',materialized:0,ready:0}]});
  if(url.endsWith('/api/v3/saas-broker/status'))return response({state:'PENDING_HANDOFF',pending_count:4});
  if(url.endsWith('/v1/models'))return response({data:[{id:'C:\\private\\model\\gpt-oss-20b.gguf'}]});
  return response({status:'ok',authority_effect:'NONE'});
 });
 const model=createReadModel({root,fetcher,now:()=>new Date('2026-10-08T17:50:00Z')});
 return {root,model,cleanup:()=>fs.rmSync(root,{force:true,recursive:true})};
}
test('live model sanitizes Mission Control, broker and model observations',async()=>{
 const f=fixture();
 try{
  const d=await f.model.observe('cluster');
  assert.equal(d.schema,'lion.operator-read-model/v1');
  assert.equal(d.authority_effect,'NONE');assert.equal(d.execution_effect,'NONE');
  assert.equal(d.endpoints.mission_control,'HEALTHY');
  assert.equal(d.endpoints.panel,'HEALTHY');
  assert.equal(d.endpoints.model,'HEALTHY');
  assert.equal(d.endpoints.broker_pending,4);
  assert.equal(d.missions.length,1);assert.equal(d.missions[0].state,'RUNNING');
  assert.equal(d.model_names[0].label,'gpt-oss-20b.gguf');
  assert.equal(d.material_workers.source,'STORED_SNAPSHOT_NOT_LIVE_DOCKER');
  assert.equal(d.artifacts.download,'NOT_EXPOSED_BY_THIS_READ_MODEL');
  assert(d.logs.lines.some(line=>line==='[REDACTED_SECRET_BEARING_LINE]'));
 }finally{f.cleanup()}
});
test('system repo SHA remains stored, not falsely live after refresh',async()=>{
 const f=fixture();
 try{
  const d=await f.model.observe('system');
  assert.equal(d.repos.source,'STORED_GITHUB_HEADS_NOT_LIVE');
  assert.equal(d.repos.repositories[0].head_sha,'e'.repeat(40));
  assert.equal(d.repos.snapshot_at,'2026-10-08T16:54:01Z');
 }finally{f.cleanup()}
});
test('read model cannot perform writes or arbitrary route construction',async()=>{
 const f=fixture();
 try{
  await assert.rejects(()=>f.model.observe('/api/v3/admin'),/UNKNOWN_READ_SCOPE/);
  const d=await f.model.observe('cluster');assert.equal(d.authority_effect,'NONE');
 }finally{f.cleanup()}
});
test('temporary downstream failure is visible as UNKNOWN not fabricated healthy',async()=>{
 const f=fixture({fetcher:async()=>{throw Error('UNREACHABLE')}});
 try{
  const d=await f.model.observe('cluster');
  assert.equal(d.endpoints.model,'Error');
  assert.equal(d.endpoints.mission_control,'Error');
  assert.equal(d.missions.length,0);
 }finally{f.cleanup()}
});
test('secrets and overly long lines are redacted in bounded log projections',()=>{
 assert.equal(redact('Authorization: Bearer AAA'),'[REDACTED_SECRET_BEARING_LINE]');
 assert.equal(redact('token=hidden'),'[REDACTED_SECRET_BEARING_LINE]');
 assert(redact('A'.repeat(900)).length<=420);
 assert.equal(tail('a\nb\nc',2).length,2);
});
test('oversized or missing file never escapes the read model',async()=>{
 const f=fixture();
 try{
  const p=path.join(f.root,'desktop','observability-preview','LION_OBSERVABILITY_SNAPSHOT_20261008.json');
  fs.writeFileSync(p,'x'.repeat(600000));
  const d=await f.model.observe('system');
  assert.equal(d.repos.repositories.length,0);
  assert.equal(d.repos.source,'STORED_GITHUB_HEADS_NOT_LIVE');
 }finally{f.cleanup()}
});
