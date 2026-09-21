'use strict';
const path=require('node:path'),fs=require('node:fs');
const {DatabaseSync}=require('node:sqlite');
const {id,nowIso,canonicalJson}=require('./canonical');

class ThreadStore{
  constructor(dbPath){
    if(!dbPath)throw new Error('THREAD_DB_REQUIRED');
    this.path=path.resolve(dbPath);fs.mkdirSync(path.dirname(this.path),{recursive:true});
    this.db=new DatabaseSync(this.path);this.db.exec('PRAGMA journal_mode=WAL; PRAGMA foreign_keys=ON; PRAGMA busy_timeout=10000;');this._migrate();
  }
  _migrate(){
    this.db.exec(`
      CREATE TABLE IF NOT EXISTS threads(thread_id TEXT PRIMARY KEY,title TEXT NOT NULL,created_at REAL NOT NULL,updated_at REAL NOT NULL);
      CREATE TABLE IF NOT EXISTS messages(message_id TEXT PRIMARY KEY,thread_id TEXT NOT NULL,seq INTEGER NOT NULL,role TEXT NOT NULL,content TEXT NOT NULL,created_at REAL NOT NULL,meta_json TEXT NOT NULL,FOREIGN KEY(thread_id) REFERENCES threads(thread_id) ON DELETE CASCADE,UNIQUE(thread_id,seq));
      CREATE INDEX IF NOT EXISTS idx_threads_updated ON threads(updated_at DESC);
      CREATE INDEX IF NOT EXISTS idx_messages_thread_seq ON messages(thread_id,seq);
    `);
    const columns=this.db.prepare('PRAGMA table_info(threads)').all().map(x=>x.name);
    if(!columns.includes('deleted_at'))this.db.exec('ALTER TABLE threads ADD COLUMN deleted_at REAL');
    this.db.exec(`
      CREATE TABLE IF NOT EXISTS message_dedupe(
        thread_id TEXT NOT NULL,dedupe_key TEXT NOT NULL,message_id TEXT NOT NULL,
        PRIMARY KEY(thread_id,dedupe_key),UNIQUE(message_id),
        FOREIGN KEY(thread_id) REFERENCES threads(thread_id),FOREIGN KEY(message_id) REFERENCES messages(message_id)
      );
      CREATE TABLE IF NOT EXISTS saas_request_bindings(
        request_id TEXT PRIMARY KEY,thread_id TEXT NOT NULL,request_hash TEXT NOT NULL,provider_id TEXT NOT NULL,
        context_digest TEXT,question TEXT,context_json TEXT,created_at TEXT NOT NULL,state TEXT NOT NULL,
        FOREIGN KEY(thread_id) REFERENCES threads(thread_id)
      );
      CREATE INDEX IF NOT EXISTS idx_saas_request_thread ON saas_request_bindings(thread_id,state);
      CREATE TABLE IF NOT EXISTS turn_bindings(
        turn_id TEXT PRIMARY KEY,request_id TEXT NOT NULL UNIQUE,turn_request_hash TEXT,state TEXT NOT NULL,
        created_at TEXT NOT NULL,updated_at TEXT NOT NULL,FOREIGN KEY(request_id) REFERENCES saas_request_bindings(request_id)
      );
      CREATE TABLE IF NOT EXISTS receipt_bindings(
        request_id TEXT PRIMARY KEY,turn_id TEXT,receipt_digest TEXT NOT NULL,response_digest TEXT,observed_at TEXT NOT NULL,
        FOREIGN KEY(request_id) REFERENCES saas_request_bindings(request_id)
      );
      CREATE TABLE IF NOT EXISTS delivery_state(
        request_id TEXT PRIMARY KEY,thread_id TEXT NOT NULL,state TEXT NOT NULL,message_id TEXT,dedupe_key TEXT NOT NULL,updated_at TEXT NOT NULL,
        FOREIGN KEY(request_id) REFERENCES saas_request_bindings(request_id),FOREIGN KEY(thread_id) REFERENCES threads(thread_id)
      );
      CREATE TABLE IF NOT EXISTS reconciliation_state(
        request_id TEXT PRIMARY KEY,state TEXT NOT NULL,detail TEXT,updated_at TEXT NOT NULL,
        FOREIGN KEY(request_id) REFERENCES saas_request_bindings(request_id)
      );
      CREATE TABLE IF NOT EXISTS turn_claims(
        turn_id TEXT PRIMARY KEY,consumer_id TEXT NOT NULL,lease_id TEXT NOT NULL,lease_expiry TEXT NOT NULL,claim_epoch INTEGER NOT NULL,updated_at TEXT NOT NULL,
        FOREIGN KEY(turn_id) REFERENCES turn_bindings(turn_id)
      );
    `);
  }
  close(){this.db.close();}
  _tx(fn){this.db.exec('BEGIN IMMEDIATE');try{const v=fn();this.db.exec('COMMIT');return v}catch(e){try{this.db.exec('ROLLBACK')}catch{}throw e}}
  _threadExists(threadId,{includeDeleted=false}={}){const q=includeDeleted?'SELECT 1 FROM threads WHERE thread_id=?':'SELECT 1 FROM threads WHERE thread_id=? AND deleted_at IS NULL';return Boolean(this.db.prepare(q).get(threadId));}
  createThread(title='Nowa rozmowa'){const thread_id=id(),t=Date.now()/1000;this.db.prepare('INSERT INTO threads(thread_id,title,created_at,updated_at,deleted_at) VALUES(?,?,?,?,NULL)').run(thread_id,String(title||'Nowa rozmowa').trim().slice(0,120)||'Nowa rozmowa',t,t);return this.getThread(thread_id);}
  listThreads(){return this.db.prepare('SELECT thread_id,title,created_at,updated_at FROM threads WHERE deleted_at IS NULL ORDER BY updated_at DESC LIMIT 500').all();}
  getThread(threadId,{includeDeleted=false}={}){const q=includeDeleted?'SELECT * FROM threads WHERE thread_id=?':'SELECT * FROM threads WHERE thread_id=? AND deleted_at IS NULL';const t=this.db.prepare(q).get(threadId);if(!t)throw Object.assign(new Error('THREAD_NOT_FOUND'),{status:404});const rows=this.db.prepare('SELECT message_id,seq,role,content,created_at,meta_json FROM messages WHERE thread_id=? ORDER BY seq').all(threadId);return {...t,messages:rows.map(m=>({...m,meta:JSON.parse(m.meta_json||'{}')}))};}
  renameThread(threadId,title){if(!this._threadExists(threadId))throw Object.assign(new Error('THREAD_NOT_FOUND'),{status:404});const v=String(title||'').trim().slice(0,120);if(!v)throw new Error('TITLE_REQUIRED');this.db.prepare('UPDATE threads SET title=?,updated_at=? WHERE thread_id=?').run(v,Date.now()/1000,threadId);return this.getThread(threadId);}
  tombstoneThread(threadId){if(!this._threadExists(threadId))return {thread_id:threadId,deleted:false};const t=Date.now()/1000;this._tx(()=>{this.db.prepare('UPDATE threads SET deleted_at=?,updated_at=? WHERE thread_id=?').run(t,t,threadId);this.db.prepare("UPDATE saas_request_bindings SET state='ORPHANED_THREAD' WHERE thread_id=? AND state NOT IN ('RECONCILED','CANCELLED','FAILED_CLOSED')").run(threadId);});return {thread_id:threadId,deleted:true,deleted_at:t};}
  _appendOnce(threadId,role,content,dedupeKey,meta={}){
    if(!this._threadExists(threadId))throw Object.assign(new Error('THREAD_NOT_FOUND'),{status:404});
    if(!['user','assistant'].includes(role)||typeof content!=='string'||!content.trim()||!dedupeKey)throw new Error('MESSAGE_INVALID');
    return this._tx(()=>{const prior=this.db.prepare('SELECT message_id FROM message_dedupe WHERE thread_id=? AND dedupe_key=?').get(threadId,dedupeKey);if(prior)return {thread_id:threadId,message_id:prior.message_id,dedupe_key:dedupeKey,inserted:false};
      const seq=Number(this.db.prepare('SELECT COALESCE(MAX(seq),0) AS seq FROM messages WHERE thread_id=?').get(threadId).seq)+1,message_id=id(),t=Date.now()/1000;
      const tagged={...meta,external_receipt_key:dedupeKey};this.db.prepare('INSERT INTO messages(message_id,thread_id,seq,role,content,created_at,meta_json) VALUES(?,?,?,?,?,?,?)').run(message_id,threadId,seq,role,content, t,canonicalJson(tagged));
      this.db.prepare('INSERT INTO message_dedupe(thread_id,dedupe_key,message_id) VALUES(?,?,?)').run(threadId,dedupeKey,message_id);this.db.prepare('UPDATE threads SET updated_at=? WHERE thread_id=?').run(t,threadId);return {thread_id:threadId,message_id,dedupe_key:dedupeKey,inserted:true};});
  }
  appendUserOnce(threadId,content,dedupeKey,meta={}){return this._appendOnce(threadId,'user',String(content).slice(0,8000),dedupeKey,meta);}
  appendAssistantOnce(threadId,content,dedupeKey,meta={}){return this._appendOnce(threadId,'assistant',String(content).slice(0,24000),dedupeKey,meta);}
  bindRequest({thread_id,request_id,request_hash,provider_id,context_digest=null,question=null,context_json=null,state='CREATED'}){
    if(!this._threadExists(thread_id))throw Object.assign(new Error('THREAD_NOT_FOUND'),{status:404});
    const prior=this.db.prepare('SELECT * FROM saas_request_bindings WHERE request_id=?').get(request_id);if(prior){if(prior.thread_id!==thread_id||prior.request_hash!==request_hash||prior.provider_id!==provider_id)throw new Error('REQUEST_BINDING_CONFLICT');return prior;}
    this.db.prepare('INSERT INTO saas_request_bindings(request_id,thread_id,request_hash,provider_id,context_digest,question,context_json,created_at,state) VALUES(?,?,?,?,?,?,?,?,?)').run(request_id,thread_id,request_hash,provider_id,context_digest,question,context_json,nowIso(),state);
    return this.requestBinding(request_id);
  }
  requestBinding(requestId){return this.db.prepare('SELECT * FROM saas_request_bindings WHERE request_id=?').get(requestId)||null;}
  pendingBindings(){return this.db.prepare("SELECT * FROM saas_request_bindings WHERE state NOT IN ('RECONCILED','CANCELLED','FAILED_CLOSED') ORDER BY created_at,request_id").all();}
  updateRequestState(requestId,state){this.db.prepare('UPDATE saas_request_bindings SET state=? WHERE request_id=?').run(state,requestId);return this.requestBinding(requestId);}
  bindTurn({request_id,turn_id,turn_request_hash=null,state='PENDING'}){const p=this.db.prepare('SELECT * FROM turn_bindings WHERE request_id=?').get(request_id);if(p){if(p.turn_id!==turn_id)throw new Error('TURN_BINDING_CONFLICT');return p;}const stamp=nowIso();this.db.prepare('INSERT INTO turn_bindings(turn_id,request_id,turn_request_hash,state,created_at,updated_at) VALUES(?,?,?,?,?,?)').run(turn_id,request_id,turn_request_hash,state,stamp,stamp);return this.turnForRequest(request_id);}
  turnForRequest(requestId){return this.db.prepare('SELECT * FROM turn_bindings WHERE request_id=?').get(requestId)||null;}
  updateTurnState(turnId,state){this.db.prepare('UPDATE turn_bindings SET state=?,updated_at=? WHERE turn_id=?').run(state,nowIso(),turnId);}
  recordReceipt({request_id,turn_id=null,receipt_digest,response_digest=null}){const p=this.db.prepare('SELECT * FROM receipt_bindings WHERE request_id=?').get(request_id);if(p){if(p.receipt_digest!==receipt_digest||((p.response_digest||null)!==(response_digest||null)))throw new Error('RECEIPT_BINDING_CONFLICT');return p;}this.db.prepare('INSERT INTO receipt_bindings(request_id,turn_id,receipt_digest,response_digest,observed_at) VALUES(?,?,?,?,?)').run(request_id,turn_id,receipt_digest,response_digest,nowIso());return this.db.prepare('SELECT * FROM receipt_bindings WHERE request_id=?').get(request_id);}
  markDelivery({request_id,thread_id,state,message_id=null,dedupe_key}){this.db.prepare(`INSERT INTO delivery_state(request_id,thread_id,state,message_id,dedupe_key,updated_at) VALUES(?,?,?,?,?,?) ON CONFLICT(request_id) DO UPDATE SET state=excluded.state,message_id=COALESCE(delivery_state.message_id,excluded.message_id),dedupe_key=excluded.dedupe_key,updated_at=excluded.updated_at`).run(request_id,thread_id,state,message_id,dedupe_key,nowIso());}
  markReconciliation(requestId,state,detail=''){this.db.prepare(`INSERT INTO reconciliation_state(request_id,state,detail,updated_at) VALUES(?,?,?,?) ON CONFLICT(request_id) DO UPDATE SET state=excluded.state,detail=excluded.detail,updated_at=excluded.updated_at`).run(requestId,state,String(detail).slice(0,1000),nowIso());this.updateRequestState(requestId,state);return {request_id:requestId,state,detail};}
  reconciliation(requestId){return this.db.prepare('SELECT * FROM reconciliation_state WHERE request_id=?').get(requestId)||null;}
  claimTurn({turn_id,consumer_id,lease_id,lease_expiry}){
    return this._tx(()=>{const now=Date.now(),expiry=Date.parse(lease_expiry);if(!consumer_id||!lease_id||!Number.isFinite(expiry)||expiry<=now)throw new Error('TURN_CLAIM_INVALID');const prior=this.db.prepare('SELECT * FROM turn_claims WHERE turn_id=?').get(turn_id);
      if(prior&&Date.parse(prior.lease_expiry)>now){if(prior.consumer_id===consumer_id&&prior.lease_id===lease_id)return {...prior,idempotent:true};throw new Error('ALREADY_CLAIMED');}
      const epoch=Number(prior?.claim_epoch||0)+1;this.db.prepare(`INSERT INTO turn_claims(turn_id,consumer_id,lease_id,lease_expiry,claim_epoch,updated_at) VALUES(?,?,?,?,?,?) ON CONFLICT(turn_id) DO UPDATE SET consumer_id=excluded.consumer_id,lease_id=excluded.lease_id,lease_expiry=excluded.lease_expiry,claim_epoch=excluded.claim_epoch,updated_at=excluded.updated_at`).run(turn_id,consumer_id,lease_id,lease_expiry,epoch,nowIso());return {...this.db.prepare('SELECT * FROM turn_claims WHERE turn_id=?').get(turn_id),idempotent:false};});
  }
  debugState(){return {requests:this.db.prepare('SELECT * FROM saas_request_bindings ORDER BY created_at').all(),turns:this.db.prepare('SELECT * FROM turn_bindings ORDER BY created_at').all(),receipts:this.db.prepare('SELECT * FROM receipt_bindings ORDER BY observed_at').all(),deliveries:this.db.prepare('SELECT * FROM delivery_state ORDER BY updated_at').all(),reconciliation:this.db.prepare('SELECT * FROM reconciliation_state ORDER BY updated_at').all()};}
}
module.exports={ThreadStore};
