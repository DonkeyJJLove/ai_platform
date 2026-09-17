#!/usr/bin/env python3
"""Browserless cognition-only OpenAI Responses consumer for the LION SaaS broker."""
from __future__ import annotations
import argparse, hashlib, json, os, sqlite3, threading, time, urllib.error, urllib.parse, urllib.request
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

DIRECT_TRANSPORT='OPENAI_RESPONSES_API_MEDIATED'
DIRECT_ATTESTATION='OPENAI_RESPONSES_API_RECEIPT'
CONTROL_TRANSPORT='SENTINELX_OPERATOR_CONTROL'
PROVIDER='OPENAI'
BRIDGE_ID='LION_DIRECT_SUPERVISOR_BRIDGE_R1'
DEFAULT_MODEL='gpt-5.6-sol'
WAITING={'WAITING_PROVIDER','WAITING_PROVIDER_OVERDUE'}
MAX_INPUT_SIZE=8000
MAX_OUTPUT_TOKENS=2048
MAX_INFLIGHT=1
REQUEST_TIMEOUT=120
RETRY_MAX=0
ALLOWED_PROVIDER_HOSTS={'api.openai.com'}

def utcnow():return datetime.now(timezone.utc).isoformat().replace('+00:00','Z')
def canon(v):return json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False,default=str)
def digest(v):return hashlib.sha256(canon(v).encode()).hexdigest()

def http_json(base,path,method='GET',body=None,headers=None,timeout=15):
    data=None;h={'Accept':'application/json','User-Agent':'LION-Direct-Supervisor/1'};h.update(headers or {})
    if body is not None:data=canon(body).encode();h['Content-Type']='application/json'
    req=urllib.request.Request(base.rstrip('/')+path,data=data,headers=h,method=method)
    try:
        with urllib.request.urlopen(req,timeout=timeout) as r:return json.loads(r.read().decode('utf-8'))
    except urllib.error.HTTPError as exc:
        raw=exc.read().decode('utf-8','replace')
        raise RuntimeError(f'HTTP {exc.code} {raw[:800]}') from exc

def provider_base(value):
    raw=str(value or 'https://api.openai.com/v1').rstrip('/');u=urllib.parse.urlparse(raw)
    if u.scheme!='https' or u.hostname not in ALLOWED_PROVIDER_HOSTS or u.username or u.password or u.query or u.fragment:
        raise ValueError('provider base URL not allowlisted')
    return raw

def output_text(response):
    chunks=[]
    for item in response.get('output') or []:
        if not isinstance(item,dict) or item.get('type')!='message':continue
        for part in item.get('content') or []:
            if isinstance(part,dict) and part.get('type') in {'output_text','text'} and isinstance(part.get('text'),str):chunks.append(part['text'])
    text='\n'.join(x.strip() for x in chunks if x.strip()).strip()
    if not text and isinstance(response.get('output_text'),str):text=response['output_text'].strip()
    if not text:raise RuntimeError('provider response contains no output text')
    return text[:24000]

class ConversationStore:
    def __init__(self,path):self.path=Path(path);self.path.parent.mkdir(parents=True,exist_ok=True);self.lock=threading.RLock();self._init()
    def _conn(self):c=sqlite3.connect(self.path,timeout=10);c.row_factory=sqlite3.Row;c.execute('PRAGMA journal_mode=WAL');return c
    def _init(self):
        with self.lock:
            c=self._conn();c.executescript("""
CREATE TABLE IF NOT EXISTS provider_conversations(
  binding_key TEXT PRIMARY KEY, thread_id TEXT, scope_type TEXT NOT NULL, scope_id TEXT,
  mission_id TEXT, provider TEXT NOT NULL, model_id TEXT NOT NULL,
  conversation_id TEXT NOT NULL, conversation_id_digest TEXT NOT NULL,
  created_at TEXT NOT NULL, updated_at TEXT NOT NULL, last_response_id TEXT,
  state TEXT NOT NULL, currentness_digest TEXT);
CREATE TABLE IF NOT EXISTS provider_attempts(
  request_id TEXT PRIMARY KEY, claim_generation INTEGER NOT NULL, binding_key TEXT NOT NULL,
  started_at TEXT NOT NULL, completed_at TEXT, provider_response_id TEXT,
  state TEXT NOT NULL, error_class TEXT, authority_effect TEXT NOT NULL);
""");c.commit();c.close()
    def key(self,row):return row.get('thread_id') or f"{row.get('scope_type')}:{row.get('scope_id') or 'GLOBAL'}"
    def get(self,key):
        with self.lock:
            c=self._conn();r=c.execute('SELECT * FROM provider_conversations WHERE binding_key=?',(key,)).fetchone();c.close();return dict(r) if r else None
    def bind(self,key,row,conversation_id,model):
        stamp=utcnow();dg=hashlib.sha256(conversation_id.encode()).hexdigest()
        with self.lock:
            c=self._conn();c.execute('INSERT INTO provider_conversations(binding_key,thread_id,scope_type,scope_id,mission_id,provider,model_id,conversation_id,conversation_id_digest,created_at,updated_at,state,currentness_digest) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(binding_key) DO UPDATE SET thread_id=excluded.thread_id,scope_type=excluded.scope_type,scope_id=excluded.scope_id,mission_id=excluded.mission_id,provider=excluded.provider,model_id=excluded.model_id,conversation_id=excluded.conversation_id,conversation_id_digest=excluded.conversation_id_digest,updated_at=excluded.updated_at,state=excluded.state,currentness_digest=excluded.currentness_digest',(key,row.get('thread_id'),row.get('scope_type'),row.get('scope_id'),row.get('mission_id'),PROVIDER,model,conversation_id,dg,stamp,stamp,'BOUND',digest({'mission_id':row.get('mission_id'),'thread_id':row.get('thread_id'),'scope_type':row.get('scope_type'),'scope_id':row.get('scope_id')})));c.commit();c.close()
        return conversation_id
    def refresh_binding(self,key,row,model):
        stamp=utcnow();currentness=digest({'mission_id':row.get('mission_id'),'thread_id':row.get('thread_id'),'scope_type':row.get('scope_type'),'scope_id':row.get('scope_id')})
        with self.lock:
            c=self._conn();c.execute('UPDATE provider_conversations SET thread_id=?,scope_type=?,scope_id=?,mission_id=?,provider=?,model_id=?,updated_at=?,currentness_digest=? WHERE binding_key=?',(row.get('thread_id'),row.get('scope_type'),row.get('scope_id'),row.get('mission_id'),PROVIDER,model,stamp,currentness,key));c.commit();c.close()
    def prepare_attempt(self,rid,generation,key):
        with self.lock:
            c=self._conn();old=c.execute('SELECT * FROM provider_attempts WHERE request_id=?',(rid,)).fetchone()
            if old:
                c.execute("UPDATE provider_attempts SET claim_generation=?,state=CASE WHEN state='COMPLETED' THEN state ELSE 'STARTED' END,error_class=NULL WHERE request_id=?",(generation,rid));c.commit();out=dict(c.execute('SELECT * FROM provider_attempts WHERE request_id=?',(rid,)).fetchone());c.close();return out
            c.execute('INSERT INTO provider_attempts VALUES(?,?,?,?,?,?,?,?,?)',(rid,generation,key,utcnow(),None,None,'STARTED',None,'NONE'));c.commit();out=dict(c.execute('SELECT * FROM provider_attempts WHERE request_id=?',(rid,)).fetchone());c.close();return out
    def finish_attempt(self,rid,response_id):
        with self.lock:
            c=self._conn();c.execute("UPDATE provider_attempts SET state='COMPLETED',completed_at=?,provider_response_id=? WHERE request_id=?",(utcnow(),response_id,rid));c.execute('UPDATE provider_conversations SET updated_at=?,last_response_id=? WHERE binding_key=(SELECT binding_key FROM provider_attempts WHERE request_id=?)',(utcnow(),response_id,rid));c.commit();c.close()
    def fail_attempt(self,rid,error_class):
        with self.lock:
            c=self._conn();c.execute("UPDATE provider_attempts SET state='FAILED',completed_at=?,error_class=? WHERE request_id=?",(utcnow(),str(error_class)[:160],rid));c.commit();c.close()
    def snapshot(self):
        with self.lock:
            c=self._conn();n=c.execute("SELECT COUNT(*) FROM provider_conversations WHERE state='BOUND'").fetchone()[0];last=c.execute('SELECT provider,model_id,conversation_id_digest,last_response_id,updated_at,state FROM provider_conversations ORDER BY updated_at DESC LIMIT 1').fetchone();c.close();return {'bound_conversations':n,'last':dict(last) if last else None}

class Bridge:
    def __init__(self,broker,key_file,state_db,api_key,api_base,model,interval=0.5):
        self.broker=broker.rstrip('/');self.key=Path(key_file).read_text().strip();self.store=ConversationStore(state_db);self.api_key=api_key;self.api_base=provider_base(api_base);self.model=model;self.interval=max(0.2,float(interval));self.stop=threading.Event();self.last_error=None;self.last_request=None
        if len(self.key)<64:raise ValueError('mediator key unavailable')
    @property
    def credential_state(self):return 'PRESENT' if bool(self.api_key) else 'ABSENT'
    @property
    def state(self):return 'READY' if self.api_key else 'BLOCKED_CREDENTIAL'
    def broker_json(self,path,method='GET',body=None,timeout=15):return http_json(self.broker,path,method,body,{'X-LION-Mediator-Key':self.key} if method!='GET' else None,timeout)
    def heartbeat(self):
        body={'bridge_id':BRIDGE_ID,'state':self.state,'provider':PROVIDER,'model_id':self.model if self.api_key else None,'credential_state':self.credential_state,'authority_effect':'NONE'}
        return self.broker_json('/api/v3/saas-broker/direct/heartbeat','POST',body)
    def provider_json(self,path,body=None,timeout=REQUEST_TIMEOUT,request_key=None,method='POST'):
        if not self.api_key:raise RuntimeError('provider credential absent')
        headers={'Authorization':'Bearer '+self.api_key}
        if request_key:headers.update({'Idempotency-Key':request_key,'X-Client-Request-Id':request_key})
        return http_json(self.api_base,path,method,body,headers,timeout)
    def conversation(self,row):
        key=self.store.key(row);found=self.store.get(key)
        if found and found.get('provider')==PROVIDER and found.get('model_id')==self.model:
            self.store.refresh_binding(key,row,self.model);return key,found['conversation_id']
        binding_hash=hashlib.sha256(key.encode()).hexdigest();created=self.provider_json('/conversations',{'metadata':{'lion_binding':binding_hash[:32]}},request_key='lion-conv-'+binding_hash)
        cid=created.get('id')
        if not isinstance(cid,str) or not cid:raise RuntimeError('provider conversation id missing')
        return key,self.store.bind(key,row,cid,self.model)
    def process_one(self):
        if not self.api_key:return False
        pending=self.broker_json('/api/v3/saas-broker/pending').get('requests') or []
        row=next((r for r in pending if (r.get('inference_transport') or r.get('transport'))==DIRECT_TRANSPORT and r.get('status') in WAITING),None)
        if not row:return False
        rid=row['request_id'];claim=self.broker_json(f'/api/v3/saas-broker/requests/{rid}/claim','POST',{})
        key,cid=self.conversation(row);generation=int(claim['claim_generation']);attempt=self.store.prepare_attempt(rid,generation,key)
        self.last_request=rid
        try:
            response_key='lion-response-'+rid
            if attempt.get('state')=='COMPLETED' and attempt.get('provider_response_id'):
                response=self.provider_json('/responses/'+urllib.parse.quote(attempt['provider_response_id'],safe=''),None,REQUEST_TIMEOUT,method='GET')
            else:
                response=self.provider_json('/responses',{'model':self.model,'conversation':cid,'input':str(claim['question'])[:MAX_INPUT_SIZE],'instructions':'You are the remote cognition-only supervisor for LION. Return text only. You have no execution authority.','max_output_tokens':MAX_OUTPUT_TOKENS,'store':True},request_key=response_key)
            response_id=response.get('id')
            if not isinstance(response_id,str) or not response_id:raise RuntimeError('provider response id missing')
            answer=output_text(response);self.store.finish_attempt(rid,response_id)
            result=self.broker_json(f'/api/v3/saas-broker/requests/{rid}/respond','POST',{'response_token':claim['response_token'],'claim_generation':generation,'answer':answer,'model_identity':self.model,'transport':DIRECT_TRANSPORT,'attestation_class':DIRECT_ATTESTATION,'provider':PROVIDER,'provider_conversation_id':cid,'provider_response_id':response_id},30)
            self.last_error=None;return result
        except Exception as exc:
            self.store.fail_attempt(rid,type(exc).__name__);self.last_error=type(exc).__name__+':'+str(exc)[:500];raise
    def loop(self):
        last_hb=0.0
        while not self.stop.is_set():
            try:
                if time.time()-last_hb>=10:self.heartbeat();last_hb=time.time()
                if self.api_key:self.process_one()
            except Exception as exc:self.last_error=type(exc).__name__+':'+str(exc)[:500]
            self.stop.wait(self.interval)
    def status(self):return {'schema':'lion.direct-supervisor-bridge/v1','bridge_id':BRIDGE_ID,'state':self.state if not self.last_error else 'DEGRADED','credential_state':self.credential_state,'provider':PROVIDER,'model_id':self.model if self.api_key else None,'control_transport':CONTROL_TRANSPORT,'inference_transport':DIRECT_TRANSPORT,'max_inflight':MAX_INFLIGHT,'request_timeout_seconds':REQUEST_TIMEOUT,'max_input_size':MAX_INPUT_SIZE,'max_output_tokens':MAX_OUTPUT_TOKENS,'retry_max':RETRY_MAX,'provider_host':urllib.parse.urlparse(self.api_base).hostname,'last_request_id':self.last_request,'last_error':self.last_error,'conversations':self.store.snapshot(),'authority_effect':'NONE'}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--broker',default='http://127.0.0.1:8766');ap.add_argument('--mediator-key-file',default='/var/lib/sentinelx/uploads/lion-mission-control-v3/saas-mediator.key');ap.add_argument('--state-db',default='/var/lib/sentinelx/uploads/lion-mission-control-v3/direct-supervisor-bridge.db');ap.add_argument('--api-base',default=os.environ.get('OPENAI_BASE_URL','https://api.openai.com/v1'));ap.add_argument('--model',default=os.environ.get('LION_OPENAI_MODEL',DEFAULT_MODEL));ap.add_argument('--host',default='127.0.0.1');ap.add_argument('--port',type=int,default=8768);ap.add_argument('--interval',type=float,default=0.5);a=ap.parse_args()
    key=os.environ.get('OPENAI_API_KEY','').strip();bridge=Bridge(a.broker,a.mediator_key_file,a.state_db,key,a.api_base,a.model,a.interval)
    threading.Thread(target=bridge.loop,daemon=True,name='direct-provider-consumer').start()
    class H(BaseHTTPRequestHandler):
        def log_message(self,*args):return
        def out(self,x,status=200):b=canon(x).encode();self.send_response(status);self.send_header('Content-Type','application/json');self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(b)));self.end_headers();self.wfile.write(b)
        def do_GET(self):
            path=urllib.parse.urlparse(self.path).path
            if path in {'/healthz','/status'}:return self.out(bridge.status(),200 if path=='/status' or bridge.state in {'READY','BLOCKED_CREDENTIAL'} else 503)
            return self.out({'error':'not found'},404)
    server=ThreadingHTTPServer((a.host,a.port),H)
    try:server.serve_forever()
    finally:bridge.stop.set();server.server_close()
if __name__=='__main__':main()
