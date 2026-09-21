'use strict';
const {DatabaseSync}=require('node:sqlite');
const {envelope,hash,conversation}=require('./contract.cjs');
const ACTIVE=['QUEUED','DISPATCHING','AWAITING_RESULT','SEND_UNKNOWN'];
class Store{
 constructor(file,projectUrl,now=Date.now){
  this.projectUrl=projectUrl;this.now=now;this.db=new DatabaseSync(file);
  this.db.exec("PRAGMA journal_mode=WAL; PRAGMA synchronous=FULL; PRAGMA busy_timeout=3000; CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY,value TEXT NOT NULL); CREATE TABLE IF NOT EXISTS wakes (request_id TEXT PRIMARY KEY, mission_id TEXT NOT NULL, turn_id TEXT NOT NULL UNIQUE, payload TEXT NOT NULL, digest TEXT NOT NULL, state TEXT NOT NULL, sends INTEGER NOT NULL DEFAULT 0, reason TEXT, updated_at INTEGER NOT NULL); CREATE TABLE IF NOT EXISTS events (seq INTEGER PRIMARY KEY AUTOINCREMENT,request_id TEXT,state TEXT NOT NULL,reason TEXT,at INTEGER NOT NULL)");
  this.db.prepare("INSERT OR IGNORE INTO settings VALUES ('stopped','true')").run();
  this.db.exec('CREATE TABLE IF NOT EXISTS handoffs (request_id TEXT PRIMARY KEY,payload TEXT NOT NULL)');
 }
 tx(fn){this.db.exec('BEGIN IMMEDIATE');try{const r=fn();this.db.exec('COMMIT');return r}catch(e){this.db.exec('ROLLBACK');throw e}}
 stopped(){return this.db.prepare("SELECT value FROM settings WHERE key='stopped'").get().value==='true'}
 rememberConversation(url){const valid=conversation(url,this.projectUrl);this.db.prepare("INSERT INTO settings VALUES ('conversation',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value").run(valid)}
 restoreConversation(){const value=this.db.prepare("SELECT value FROM settings WHERE key='conversation'").get()?.value;try{return conversation(value,this.projectUrl)}catch{return this.projectUrl}}
 handoffs(){return this.db.prepare('SELECT payload FROM handoffs ORDER BY rowid').all().map(r=>JSON.parse(r.payload))}
 saveHandoff(record){this.db.prepare('INSERT INTO handoffs VALUES (?,?) ON CONFLICT(request_id) DO UPDATE SET payload=excluded.payload').run(record.request_id,JSON.stringify(record))}
 record(id,state,reason=null){this.db.prepare('INSERT INTO events(request_id,state,reason,at) VALUES (?,?,?,?)').run(id,state,reason,this.now())}
 row(id){const r=this.db.prepare('SELECT * FROM wakes WHERE request_id=?').get(id);return r?{...r,envelope:JSON.parse(r.payload)}:null}
 rows(){return this.db.prepare('SELECT request_id FROM wakes ORDER BY rowid').all().map(r=>this.row(r.request_id))}
 setState(id,state,reason){this.db.prepare('UPDATE wakes SET state=?,reason=?,updated_at=? WHERE request_id=?').run(state,reason||null,this.now(),id);this.record(id,state,reason)}
 recover(){this.tx(()=>{for(const r of this.rows())if(r.state==='DISPATCHING')this.setState(r.request_id,'SEND_UNKNOWN','INTERRUPTED_DURING_SEND');this.db.prepare("UPDATE settings SET value='true' WHERE key='stopped'").run();this.record(null,'STOPPED','PROCESS_START_REQUIRES_OPERATOR_RESUME')})}
 enqueue(value){
  // Existing exact envelopes remain idempotent even after their original deadline.
  const old=value?.request_id?this.row(value.request_id):null;
  if(old){if(JSON.stringify(Object.keys(value).sort())!==JSON.stringify(Object.keys(old.envelope).sort())||Object.keys(old.envelope).some(k=>value[k]!==old.envelope[k]))throw Error('BINDING_CONFLICT');return old}
  const v=envelope(value,this.projectUrl,this.now()),payload=JSON.stringify(v),digest=hash(payload);
  return this.tx(()=>{
   if(this.stopped())throw Error('STOPPED');
   const existing=this.rows();
   if(existing.length>=18)throw Error('TASK_BUDGET_EXHAUSTED');
   if(existing.some(r=>ACTIVE.includes(r.state)&&r.mission_id!==v.mission_id))throw Error('MISSION_LIMIT');
   if(existing.filter(r=>r.mission_id===v.mission_id).length>=6)throw Error('TURN_LIMIT');
   if(existing.some(r=>r.mission_id===v.mission_id&&(r.envelope.conversation_url!==v.conversation_url||r.envelope.panel_thread_id!==v.panel_thread_id)))throw Error('MISSION_BINDING_CONFLICT');
   this.db.prepare('INSERT INTO wakes(request_id,mission_id,turn_id,payload,digest,state,updated_at) VALUES (?,?,?,?,?,?,?)').run(v.request_id,v.mission_id,v.turn_id,payload,digest,'QUEUED',this.now());this.record(v.request_id,'QUEUED');return this.row(v.request_id);
  });
 }
 claim(requestId=null){return this.tx(()=>{
  if(this.stopped())return null;
  const rows=this.rows();
  // Unknown external effect holds the queue until readback reconciliation.
  if(rows.some(r=>['DISPATCHING','AWAITING_RESULT','SEND_UNKNOWN'].includes(r.state)))return null;
  for(const r of rows.filter(r=>r.state==='QUEUED')){
   if(requestId!==null&&r.request_id!==requestId)continue;
   if(r.envelope.deadline_at<=this.now()){this.setState(r.request_id,'TIMED_OUT','BEFORE_SEND');continue}
   this.db.prepare('UPDATE wakes SET sends=sends+1 WHERE request_id=?').run(r.request_id);this.setState(r.request_id,'DISPATCHING');return this.row(r.request_id);
  }return null;
 })}
 transition(id,from,to,reason){return this.tx(()=>{const r=this.row(id);if(!r||!from.includes(r.state))return false;this.setState(id,to,reason);return true})}
 stop(){this.tx(()=>{this.db.prepare("UPDATE settings SET value='true' WHERE key='stopped'").run();for(const r of this.rows()){if(r.state==='QUEUED')this.setState(r.request_id,'CANCELLED','OPERATOR_STOP');else if(['DISPATCHING','AWAITING_RESULT'].includes(r.state))this.setState(r.request_id,'SEND_UNKNOWN','STOP_EXTERNAL_EFFECT_REQUIRES_READBACK')}this.record(null,'STOPPED','OPERATOR_STOP')})}
 resume(){this.tx(()=>{this.db.prepare("UPDATE settings SET value='false' WHERE key='stopped'").run();this.record(null,'RESUMED','LOCAL_OPERATOR_MENU')})}
 close(){this.db.close()}
}
module.exports={Store};
