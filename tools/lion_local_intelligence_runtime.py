#!/usr/bin/env python3
"""R10 R2 canonical user-level runtime.

All live repository/currentness/web reads cross the MAT12 file-mailbox boundary.
The raw model remains proposal-only at loopback :8772.
"""
from __future__ import annotations
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from dataclasses import dataclass
import argparse,hashlib,json,os,threading,time,urllib.request,urllib.error,urllib.parse,uuid,sqlite3,re,sys,inspect
from datetime import datetime,timezone
from cyber_lion.app_coordination.local_intelligence_gateway import Gateway,serve_gateway,UI
from cyber_lion.app_coordination.hybrid_gateway_extension import apply_hybrid_gateway_extension
apply_hybrid_gateway_extension(Gateway)
from cyber_lion.app_coordination.saas_handoff_extension import apply_saas_handoff_extension
apply_saas_handoff_extension(Gateway)
from cyber_lion.app_coordination.web_research_broker import WebEvidence
from cyber_lion.app_coordination import ui_runtime_events
from cyber_lion.contracts.phase_execution_contract import compile_panel_phase_contracts, preflight_execution_contracts, PhaseExecutionContractError

DRONE_ROLES={
'MAT01':'LOCAL_REPOSITORY_CURRENTNESS','MAT02':'LOCAL_REPOSITORY_CONTENT','MAT03':'LOCAL_CLONE_INVENTORY','MAT04':'FEDERATION_CURRENTNESS',
'MAT05':'PUBLIC_WEB_SEARCH','MAT06':'PUBLIC_WEB_FETCH','MAT07':'WEB_SECURITY_FALSIFIER','MAT08':'SOURCE_PROVENANCE_VALIDATOR',
'MAT09':'MODEL_GPU_OBSERVER','MAT10':'RESULT_VALIDATOR','MAT11':'MATERIAL_COORDINATOR','MAT12':'FINAL_RECONCILER'}

def canon(v):return json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False,default=str).encode('utf-8')
def digest(v):return hashlib.sha256(canon(v)).hexdigest()
def _assignment_lease_valid(assignment,observed_at):
    expires=(assignment or {}).get('lease_expires_at') if isinstance(assignment,dict) else None
    if not expires:return False
    now_dt=datetime.fromisoformat(str(observed_at).replace('Z','+00:00'));exp_dt=datetime.fromisoformat(str(expires).replace('Z','+00:00'))
    if now_dt.tzinfo is None:now_dt=now_dt.replace(tzinfo=timezone.utc)
    if exp_dt.tzinfo is None:exp_dt=exp_dt.replace(tzinfo=timezone.utc)
    return now_dt<exp_dt
def atomic_json(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_suffix(path.suffix+'.tmp');tmp.write_text(json.dumps(value,sort_keys=True,ensure_ascii=False),encoding='utf-8');os.replace(tmp,path)
def _json_request(url,*,body=None,timeout=8):
    headers={'User-Agent':'LION-R10-R2-runtime/1'};method='GET'
    if body is not None:body=json.dumps(body).encode();headers['Content-Type']='application/json';method='POST'
    req=urllib.request.Request(url,data=body,headers=headers,method=method)
    with urllib.request.urlopen(req,timeout=timeout) as res:return json.load(res)


class ThreadStore:
    """Persistent local conversation store. Not exposed as model authority."""
    ID_RE=re.compile(r"^[0-9a-f]{32}$")
    BUS_TARGET_RE=re.compile(r"^(?:mission|drone|swarm|group|operator):[A-Za-z0-9][A-Za-z0-9._:-]{0,191}$")
    def __init__(self,path):
        self.path=Path(path).resolve();self.path.parent.mkdir(parents=True,exist_ok=True);self.lock=threading.RLock();self._init()
    def _conn(self):
        c=sqlite3.connect(self.path,timeout=10);c.row_factory=sqlite3.Row;c.execute('PRAGMA journal_mode=WAL');c.execute('PRAGMA foreign_keys=ON');return c
    def _init(self):
        with self.lock:
            c=self._conn();c.executescript("""
            CREATE TABLE IF NOT EXISTS threads(thread_id TEXT PRIMARY KEY,title TEXT NOT NULL,created_at REAL NOT NULL,updated_at REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS messages(message_id TEXT PRIMARY KEY,thread_id TEXT NOT NULL,seq INTEGER NOT NULL,role TEXT NOT NULL,content TEXT NOT NULL,created_at REAL NOT NULL,meta_json TEXT NOT NULL,FOREIGN KEY(thread_id) REFERENCES threads(thread_id) ON DELETE CASCADE,UNIQUE(thread_id,seq));
            CREATE TABLE IF NOT EXISTS thread_bindings(thread_id TEXT PRIMARY KEY,mission_id TEXT,target TEXT NOT NULL,channel TEXT NOT NULL,binding_revision INTEGER NOT NULL,binding_state TEXT NOT NULL,created_at REAL NOT NULL,updated_at REAL NOT NULL,FOREIGN KEY(thread_id) REFERENCES threads(thread_id) ON DELETE CASCADE);
            CREATE TABLE IF NOT EXISTS thread_model_routes(thread_id TEXT PRIMARY KEY,model_route TEXT NOT NULL,route_revision INTEGER NOT NULL,created_at REAL NOT NULL,updated_at REAL NOT NULL,FOREIGN KEY(thread_id) REFERENCES threads(thread_id) ON DELETE CASCADE);
            CREATE INDEX IF NOT EXISTS idx_threads_updated ON threads(updated_at DESC);
            CREATE INDEX IF NOT EXISTS idx_messages_thread_seq ON messages(thread_id,seq);
            """);c.execute("INSERT OR IGNORE INTO thread_model_routes(thread_id,model_route,route_revision,created_at,updated_at) SELECT thread_id,'LOCAL',1,created_at,updated_at FROM threads");c.commit();ui_runtime_events.migrate(c);c.close()
    def _id(self,v):
        if not isinstance(v,str) or not self.ID_RE.fullmatch(v):raise ValueError('thread_id')
        return v
    def __call__(self,op,args):
        args=args or {}
        with self.lock:
            c=self._conn()
            try:
                if op=='ui_runtime_event':
                    return ui_runtime_events.record(c,args)
                if op=='list':
                    rows=[]
                    for x in c.execute("SELECT t.thread_id,t.title,t.created_at,t.updated_at,b.mission_id,b.target,b.channel,b.binding_revision,b.binding_state,COALESCE(r.model_route,'LOCAL') model_route,COALESCE(r.route_revision,1) route_revision FROM threads t LEFT JOIN thread_bindings b ON b.thread_id=t.thread_id LEFT JOIN thread_model_routes r ON r.thread_id=t.thread_id ORDER BY t.created_at DESC LIMIT 500"):
                        d=dict(x);d['context']={'mission_id':d.pop('mission_id'),'target':d.pop('target'),'channel':d.pop('channel'),'binding_revision':d.pop('binding_revision'),'binding_state':d.pop('binding_state')} if d.get('channel') else None;rows.append(d)
                    return {'threads':rows}
                if op=='create':
                    tid=uuid.uuid4().hex;title=str(args.get('title') or 'Nowa rozmowa').strip()[:120] or 'Nowa rozmowa';t=time.time();c.execute('INSERT INTO threads VALUES(?,?,?,?)',(tid,title,t,t));c.execute("INSERT INTO thread_model_routes VALUES(?,?,?,?,?)",(tid,'LOCAL',1,t,t));c.commit();return {'thread_id':tid,'title':title,'created_at':t,'updated_at':t,'messages':[],'context':None,'model_route':'LOCAL','route_revision':1}
                if op=='saas_delivery_candidates':
                    result=[]
                    for row in c.execute("SELECT thread_id,meta_json FROM messages ORDER BY created_at DESC"):
                        meta=json.loads(row['meta_json'] or '{}');rid=meta.get('saas_request_id')
                        if rid and not meta.get('external_receipt_key'):
                            if not c.execute("SELECT 1 FROM messages WHERE thread_id=? AND json_extract(meta_json,'$.external_receipt_key')=?",(row['thread_id'],'saas:'+rid)).fetchone():result.append({'thread_id':row['thread_id'],'request_id':rid,'dual_request_id':meta.get('dual_request_id')})
                        if len(result)>=64:break
                    return result
                if op=='import':
                    rows=args.get('messages')
                    if type(rows) is not list or not 1<=len(rows)<=16:raise ValueError('import messages')
                    clean=[]
                    for row in rows:
                        if type(row) is not dict or set(row)!={'role','content'} or row.get('role') not in {'user','assistant'} or not isinstance(row.get('content'),str):raise ValueError('import message')
                        content=row['content'][:24000] if row['role']=='assistant' else row['content'][:8000]
                        if not content:continue
                        clean.append((row['role'],content))
                    if not clean:raise ValueError('import empty')
                    first=next((content for role,content in clean if role=='user'),clean[0][1]);title=' '.join(first.split())[:64] or 'Zaimportowana rozmowa';tid=uuid.uuid4().hex;t=time.time();c.execute('INSERT INTO threads VALUES(?,?,?,?)',(tid,title,t,t));c.execute("INSERT INTO thread_model_routes VALUES(?,?,?,?,?)",(tid,'LOCAL',1,t,t))
                    for seq,(role,content) in enumerate(clean,1):c.execute('INSERT INTO messages VALUES(?,?,?,?,?,?,?)',(uuid.uuid4().hex,tid,seq,role,content,t,json.dumps({'legacy_local_storage_import':True},sort_keys=True)))
                    c.commit();return {'thread_id':tid,'title':title,'created_at':t,'updated_at':t,'imported_messages':len(clean)}
                tid=self._id(args.get('thread_id'))
                if op=='get':
                    row=c.execute('SELECT * FROM threads WHERE thread_id=?',(tid,)).fetchone();
                    if row is None:raise KeyError('thread not found')
                    msgs=[]
                    for m in c.execute('SELECT message_id,seq,role,content,created_at,meta_json FROM messages WHERE thread_id=? ORDER BY seq',(tid,)):
                        d=dict(m);d['meta']=json.loads(d.pop('meta_json') or '{}');msgs.append(d)
                    binding=c.execute('SELECT mission_id,target,channel,binding_revision,binding_state,created_at,updated_at FROM thread_bindings WHERE thread_id=?',(tid,)).fetchone();route=c.execute("SELECT model_route,route_revision FROM thread_model_routes WHERE thread_id=?",(tid,)).fetchone()
                    return {**dict(row),'messages':msgs,'context':dict(binding) if binding else None,'model_route':str(route['model_route'] if route else 'LOCAL'),'route_revision':int(route['route_revision'] if route else 1)}
                if op=='bind':
                    if c.execute('SELECT 1 FROM threads WHERE thread_id=?',(tid,)).fetchone() is None:raise KeyError('thread not found')
                    mid=str(args.get('mission_id') or '').strip();target=str(args.get('target') or ('mission:'+mid)).strip()
                    if not mid or len(mid)>128 or not self.BUS_TARGET_RE.fullmatch(target):raise ValueError('thread binding')
                    if target.startswith('mission:') and target!='mission:'+mid:raise ValueError('thread target mission mismatch')
                    prior=c.execute('SELECT binding_revision FROM thread_bindings WHERE thread_id=?',(tid,)).fetchone();revision=int(prior['binding_revision'] if prior else 0)+1;t=time.time()
                    c.execute("INSERT INTO thread_bindings(thread_id,mission_id,target,channel,binding_revision,binding_state,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(thread_id) DO UPDATE SET mission_id=excluded.mission_id,target=excluded.target,channel=excluded.channel,binding_revision=excluded.binding_revision,binding_state=excluded.binding_state,updated_at=excluded.updated_at",(tid,mid,target,'LION_BUS',revision,'MISSION_BOUND',t,t));c.commit();return {'thread_id':tid,'mission_id':mid,'target':target,'channel':'LION_BUS','binding_revision':revision,'binding_state':'MISSION_BOUND'}
                if op=='unbind':
                    if c.execute('SELECT 1 FROM threads WHERE thread_id=?',(tid,)).fetchone() is None:raise KeyError('thread not found')
                    prior=c.execute('SELECT binding_revision FROM thread_bindings WHERE thread_id=?',(tid,)).fetchone();revision=int(prior['binding_revision'] if prior else 0)+1;t=time.time()
                    c.execute("INSERT INTO thread_bindings(thread_id,mission_id,target,channel,binding_revision,binding_state,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(thread_id) DO UPDATE SET mission_id=NULL,target='',channel=excluded.channel,binding_revision=excluded.binding_revision,binding_state=excluded.binding_state,updated_at=excluded.updated_at",(tid,None,'','LION_BUS',revision,'MISSION_UNBOUND',t,t));c.commit();return {'thread_id':tid,'mission_id':None,'target':'','channel':'LION_BUS','binding_revision':revision,'binding_state':'MISSION_UNBOUND'}
                if op=='set_model_route':
                    route=str(args.get('model_route') or '').upper()
                    if route not in {'LOCAL','SAAS','DUAL'}:raise ValueError('model_route')
                    if c.execute('SELECT 1 FROM threads WHERE thread_id=?',(tid,)).fetchone() is None:raise KeyError('thread not found')
                    prior=c.execute('SELECT route_revision,created_at FROM thread_model_routes WHERE thread_id=?',(tid,)).fetchone();revision=int(prior['route_revision'] if prior else 0)+1;t=time.time();created=float(prior['created_at'] if prior else t)
                    c.execute("INSERT INTO thread_model_routes(thread_id,model_route,route_revision,created_at,updated_at) VALUES(?,?,?,?,?) ON CONFLICT(thread_id) DO UPDATE SET model_route=excluded.model_route,route_revision=excluded.route_revision,updated_at=excluded.updated_at",(tid,route,revision,created,t));c.execute('UPDATE threads SET updated_at=? WHERE thread_id=?',(t,tid));c.commit();return {'thread_id':tid,'model_route':route,'route_revision':revision}
                if op=='rename':
                    title=str(args.get('title') or '').strip()[:120]
                    if not title:raise ValueError('title')
                    if c.execute('SELECT 1 FROM threads WHERE thread_id=?',(tid,)).fetchone() is None:raise KeyError('thread not found')
                    c.execute('UPDATE threads SET title=?,updated_at=? WHERE thread_id=?',(title,time.time(),tid));c.commit();return {'thread_id':tid,'title':title}
                if op=='delete':
                    requests=set()
                    for row in c.execute('SELECT meta_json FROM messages WHERE thread_id=?',(tid,)):
                        rid=json.loads(row['meta_json'] or '{}').get('saas_request_id')
                        if isinstance(rid,str) and rid:requests.add(rid)
                    cancel=args.get('cancel_handoff')
                    if requests and not callable(cancel):raise RuntimeError('handoff cancellation unavailable; thread preserved')
                    cancelled=[cancel(rid) for rid in sorted(requests)]
                    cur=c.execute('DELETE FROM threads WHERE thread_id=?',(tid,));c.commit();return {'thread_id':tid,'deleted':cur.rowcount==1,'handoffs':cancelled}
                if op=='append_pair':
                    row=c.execute('SELECT title FROM threads WHERE thread_id=?',(tid,)).fetchone()
                    if row is None:raise KeyError('thread not found')
                    user=str(args.get('user') or '')[:8000];assistant=str(args.get('assistant') or '')[:24000]
                    if not user or not assistant:raise ValueError('message')
                    seq=int(c.execute('SELECT COALESCE(MAX(seq),0) FROM messages WHERE thread_id=?',(tid,)).fetchone()[0]);t=time.time();meta=args.get('meta') if isinstance(args.get('meta'),dict) else {}
                    c.execute('INSERT INTO messages VALUES(?,?,?,?,?,?,?)',(uuid.uuid4().hex,tid,seq+1,'user',user,t,'{}'))
                    c.execute('INSERT INTO messages VALUES(?,?,?,?,?,?,?)',(uuid.uuid4().hex,tid,seq+2,'assistant',assistant,t,json.dumps(meta,ensure_ascii=False,sort_keys=True)))
                    title=row['title']
                    if title=='Nowa rozmowa':title=' '.join(user.split())[:64] or title
                    c.execute('UPDATE threads SET title=?,updated_at=? WHERE thread_id=?',(title,t,tid));c.commit();return {'thread_id':tid,'title':title,'updated_at':t}
                if op=='append_assistant_once':
                    c.execute('BEGIN IMMEDIATE')
                    row=c.execute('SELECT title FROM threads WHERE thread_id=?',(tid,)).fetchone()
                    if row is None:raise KeyError('thread not found')
                    assistant=str(args.get('assistant') or '')[:24000];dedupe_key=str(args.get('dedupe_key') or '')[:200]
                    if not assistant or not dedupe_key:raise ValueError('assistant/dedupe_key')
                    for m in c.execute("SELECT message_id,meta_json FROM messages WHERE thread_id=? AND role='assistant' ORDER BY seq",(tid,)):
                        try:meta_existing=json.loads(m['meta_json'] or '{}')
                        except Exception:meta_existing={}
                        if meta_existing.get('external_receipt_key')==dedupe_key:return {'thread_id':tid,'inserted':False,'message_id':m['message_id'],'dedupe_key':dedupe_key}
                    seq=int(c.execute('SELECT COALESCE(MAX(seq),0) FROM messages WHERE thread_id=?',(tid,)).fetchone()[0]);t=time.time();meta=args.get('meta') if isinstance(args.get('meta'),dict) else {};meta={**meta,'external_receipt_key':dedupe_key}
                    message_id=uuid.uuid4().hex;c.execute('INSERT INTO messages VALUES(?,?,?,?,?,?,?)',(message_id,tid,seq+1,'assistant',assistant,t,json.dumps(meta,ensure_ascii=False,sort_keys=True)));c.execute('UPDATE threads SET updated_at=? WHERE thread_id=?',(t,tid));c.commit();return {'thread_id':tid,'inserted':True,'message_id':message_id,'dedupe_key':dedupe_key,'updated_at':t}
                raise ValueError('thread operation denied')
            finally:c.close()

class LpclControlBridge:
    """Loopback-only LPCL intake/control bridge. It never grants model authority."""
    KEY_RE=re.compile(r'^([A-Z][A-Z0-9_]*)\s*=\s*(.*)$')
    MID_RE=re.compile(r'^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$')
    ALLOWED_PROTOCOLS=('LPCL','AUTHORITY','CURRENTNESS','ASSIGNMENT','HEARTBEAT','EVIDENCE','VALIDATION','RECEIPT','RECOVERY','GITHUB','HUMAN','CONTROL','LIFECYCLE','HISTORY','LINEAGE','TRANSPORT','BROKER','MEDIATOR','THREAD')
    def __init__(self,broker,base='http://127.0.0.1:8766'):
        self.broker=broker;self.base=base.rstrip('/')
    def _get(self,path,timeout=8):
        req=urllib.request.Request(self.base+path,headers={'User-Agent':'LION-LPCL-PANEL/1'},method='GET')
        with urllib.request.urlopen(req,timeout=timeout) as res:return json.load(res)
    def _post(self,path,body,timeout=10):
        data=json.dumps(body,ensure_ascii=False).encode('utf-8');req=urllib.request.Request(self.base+path,data=data,headers={'Content-Type':'application/json','User-Agent':'LION-LPCL-PANEL/1'},method='POST')
        try:
            with urllib.request.urlopen(req,timeout=timeout) as res:return json.load(res)
        except urllib.error.HTTPError as error:
            try:detail=json.loads(error.read(4096)).get('error','backend request rejected')
            except (ValueError,AttributeError):detail='backend request rejected'
            raise ValueError('Mission Control '+str(error.code)+': '+str(detail)[:600]) from error
    @classmethod
    def _parse_pairs(cls,text):
        lines=text.replace('\r\n','\n').replace('\r','\n').split('\n');out={};i=0
        while i<len(lines):
            m=cls.KEY_RE.match(lines[i].strip())
            if not m:i+=1;continue
            key,val=m.group(1),m.group(2).strip();i+=1
            if not val:
                buf=[]
                while i<len(lines):
                    s=lines[i].strip()
                    if cls.KEY_RE.match(s):break
                    if s and not s.startswith('#'):buf.append(s)
                    i+=1
                val=' '.join(buf).strip()
            out[key]=val
        return out
    def validate(self,text):
        if not isinstance(text,str) or not 20<=len(text)<=200000:raise ValueError('lpcl text')
        kv=self._parse_pairs(text)
        # Authoring normalization: preserve a strict canonical backend while accepting
        # semantically equivalent LPCL/1.1 surface forms at intake.
        if not kv.get('MISSION_DESCRIPTION') and kv.get('MISSION_OBJECTIVE'):kv['MISSION_DESCRIPTION']=kv['MISSION_OBJECTIVE']
        if not kv.get('LOGICAL_DRONE_COUNT') and kv.get('LOGICAL_DRONES'):kv['LOGICAL_DRONE_COUNT']=kv['LOGICAL_DRONES']
        if not kv.get('MATERIAL_DRONE_COUNT') and kv.get('MATERIAL_FLEET_TARGET'):kv['MATERIAL_DRONE_COUNT']=kv['MATERIAL_FLEET_TARGET']
        required=('PROJECT','MODE','CONTROL_LANGUAGE','MISSION_ID','MISSION_TITLE','MISSION_OBJECTIVE','MISSION_DESCRIPTION','LOGICAL_DRONE_COUNT','MATERIAL_DRONE_COUNT','PROTOCOLS')
        missing=[k for k in required if not kv.get(k)]
        if missing:raise ValueError('LPCL_MISSING_REQUIRED:'+','.join(missing))
        if kv['PROJECT']!='LION_EVOLUSION' or kv['MODE']!='AUTONOMOUS_EXECUTE' or kv['CONTROL_LANGUAGE'] not in {'LPCL/1.1','LPCL/1.2'}:raise ValueError('lpcl envelope')
        mid=kv['MISSION_ID']
        if not self.MID_RE.fullmatch(mid):raise ValueError('mission_id')
        logical=int(kv['LOGICAL_DRONE_COUNT']);material=int(kv['MATERIAL_DRONE_COUNT'])
        if not 1<=logical<=512 or not 0<=material<=4096:raise ValueError('fleet cardinality')
        prot=[x for x in re.split(r'[,;\s]+',kv['PROTOCOLS'].strip()) if x]
        if not prot or any(x not in self.ALLOWED_PROTOCOLS for x in prot):raise ValueError('protocols')
        phases=[]
        for key in sorted(k for k in kv if re.fullmatch(r'PHASE_[0-9]{2}',k)):
            val=kv[key]
            if '|' in val:pid,title=[x.strip() for x in val.split('|',1)]
            else:
                pid=val.strip();title=' '.join(w.capitalize() for w in pid.split('_'))
            if not self.MID_RE.fullmatch(pid) or not title:raise ValueError('LPCL_PHASE_INVALID:'+key)
            phases.append({'id':pid,'title':title[:180]})
        if not phases:raise ValueError('no phases')
        try:
            contracts=compile_panel_phase_contracts(kv,mid,phases,kv['CONTROL_LANGUAGE'])
            try:
                registry_snapshot=self._get('/api/v3/capabilities/process-contracts')
                runtime_registry=registry_snapshot.get('capabilities') if isinstance(registry_snapshot,dict) else None
                if not isinstance(runtime_registry,dict):raise ValueError('runtime capability registry malformed')
                registry_state='LIVE_RUNTIME_REGISTRY'
            except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError):
                # Backward compatibility with older Mission Control: language
                # validation remains available, but readiness is fail-safe UNBOUND.
                registry_snapshot={'schema':'UNAVAILABLE_LEGACY_MISSION_CONTROL','capabilities':{},'authority_effect':'NONE'}
                runtime_registry={};registry_state='UNAVAILABLE_FALLBACK_EMPTY'
            preflight=preflight_execution_contracts(contracts,runtime_registry)
        except PhaseExecutionContractError as exc:
            raise ValueError('LPCL_PHASE_EXECUTION_CONTRACT:'+str(exc)) from exc
        cur=self.broker.call('MAT04','github_branch',{'repository':'DonkeyJJLove/ai_platform','branch':'master'})['result']
        dg=hashlib.sha256(text.encode('utf-8')).hexdigest()
        spec={'mission_id':mid,'title':kv['MISSION_TITLE'][:180],'objective':kv['MISSION_OBJECTIVE'][:4000],'description':kv['MISSION_DESCRIPTION'][:8000],'lpcl_digest':dg,'lpcl_text':text,'source_head':cur['head'],'source_tree':cur['tree'],'logical_count':logical,'material_target':material,'phases':phases,'protocols':prot}
        return {'valid':True,'lpcl_digest':dg,'source_currentness':cur,'spec':spec,'execution_preflight':preflight.as_dict(),'capability_registry_state':registry_state,'capability_registry_digest':registry_snapshot.get('registry_digest') if isinstance(registry_snapshot,dict) else None,'phase_execution_contracts':[x.as_dict() for x in contracts],'parsed':{'run':kv.get('RUN'),'project':kv['PROJECT'],'mode':kv['MODE'],'control_language':kv['CONTROL_LANGUAGE'],'phase_count':len(phases)}}
    def __call__(self,op,args):
        args=args or {}
        if op=='recent':
            view=str(args.get('view') or 'operational').lower()
            if view not in {'operational','history','all'}:raise ValueError('mission view')
            return self._get('/api/v3/missions/recent?view='+view)
        if op=='capability_registry':return self._get('/api/v3/capabilities/process-contracts')
        if op in {'mission_delete_preview','mission_delete'}:
            mid=args.get('mission_id')
            if not isinstance(mid,str) or not self.MID_RE.fullmatch(mid):raise ValueError('mission_id')
            if op=='mission_delete_preview':return self._get('/api/v3/missions/'+mid+'/delete-preview')
            dg=args.get('spec_digest')
            if not isinstance(dg,str) or not re.fullmatch('[0-9a-f]{64}',dg):raise ValueError('spec_digest')
            return self._post('/api/v3/missions/'+mid+'/delete',{'spec_digest':dg})
        if op=='phase_action':
            if type(args) is not dict or set(args)!={'mission_id','phase_id','action','control_token'}:raise ValueError('phase action schema')
            mid=args['mission_id'];pid=args['phase_id'];action=args['action'];token=args['control_token']
            if not isinstance(mid,str) or not self.MID_RE.fullmatch(mid) or not isinstance(pid,str) or not self.MID_RE.fullmatch(pid):raise ValueError('phase identity')
            if action not in {'PAUSE','STOP'} or not isinstance(token,str) or not re.fullmatch('[0-9a-f]{64}',token):raise ValueError('phase containment action/token')
            return self._post('/api/v3/missions/'+mid+'/phase-actions',{'phase_id':pid,'action':action,'control_token':token})
        if op=='saas_request':
            if args.get('scope_type'):
                return self._post('/api/v3/saas-broker/requests',args)
            mid=args.get('mission_id');question=args.get('question')
            if not isinstance(mid,str) or not self.MID_RE.fullmatch(mid) or not isinstance(question,str) or not question.strip() or len(question)>8000:raise ValueError('saas request')
            return self._post('/api/v3/saas/request',{'mission_id':mid,'question':question})
        if op=='saas_status':return self._get('/api/v3/saas-broker/status')
        if op=='saas_request_status':
            rid=args.get('request_id')
            if not isinstance(rid,str) or not self.MID_RE.fullmatch(rid):raise ValueError('saas request id')
            return self._get('/api/v3/saas-broker/requests/'+rid)
        if op=='saas_request_cancel':
            rid=args.get('request_id')
            if set(args)!={'request_id'} or not isinstance(rid,str) or not self.MID_RE.fullmatch(rid):raise ValueError('saas request id')
            return self._post('/api/v3/saas/cancel',{'request_id':rid})
        if op=='mission_action':
            mid=args.get('mission_id');action=args.get('action');payload=args.get('payload') or {}
            if not isinstance(mid,str) or not self.MID_RE.fullmatch(mid):raise ValueError('mission_id')
            if not isinstance(action,str):raise ValueError('action')
            return self._post('/api/v3/missions/'+mid+'/actions',{'action':action,**payload},timeout=240)
        if op=='dual_create':
            mid=args.get('mission_id');req=args.get('original_request');cur=args.get('currentness')
            if not isinstance(mid,str) or not self.MID_RE.fullmatch(mid) or not isinstance(req,str) or not isinstance(cur,dict):raise ValueError('dual create')
            return self._post('/api/v3/dual/create',{'mission_id':mid,'original_request':req,'currentness':cur})
        if op=='dual_link_saas':
            return self._post('/api/v3/dual/link-saas',{'request_id':args.get('request_id'),'saas_request_id':args.get('saas_request_id')})
        if op=='dual_response':
            return self._post('/api/v3/dual/response',{'request_id':args.get('request_id'),'provider':args.get('provider'),'response_text':args.get('response_text'),'transport':args.get('transport')})
        if op=='dual_result':
            rid=args.get('request_id')
            if not isinstance(rid,str) or not self.MID_RE.fullmatch(rid):raise ValueError('dual request id')
            return self._get('/api/v3/dual/'+rid)
        if op=='local_assignments':
            mid=args.get('mission_id');limit=int(args.get('limit',16))
            q=('?mission_id='+mid if isinstance(mid,str) and mid else '')+('&' if isinstance(mid,str) and mid else '?')+'limit='+str(limit)
            return self._get('/api/v3/local/assignments'+q)
        if op=='local_assignment_claim':
            return self._post('/api/v3/local/assignments/claim',{'assignment_id':args.get('assignment_id'),'material_drone_id':args.get('material_drone_id')})
        if op=='local_assignment_receipt':
            return self._post('/api/v3/local/assignments/receipt',{'assignment_id':args.get('assignment_id'),'material_drone_id':args.get('material_drone_id'),'lease_generation':args.get('lease_generation'),'status':args.get('status'),'result':args.get('result'),'effect_receipt_digest':args.get('effect_receipt_digest'),'authority_effect':'NONE'})
        if op=='model_call_intent':
            return self._post('/api/v3/model-calls',args)
        if op=='model_call_transition':
            model_call_id=args.get('model_call_id');payload={k:v for k,v in args.items() if k!='model_call_id'}
            if not isinstance(model_call_id,str) or not self.MID_RE.fullmatch(model_call_id):raise ValueError('model_call_id')
            return self._post('/api/v3/model-calls/'+model_call_id+'/transition',payload)
        if op=='model_call_get':
            model_call_id=args.get('model_call_id')
            if not isinstance(model_call_id,str) or not self.MID_RE.fullmatch(model_call_id):raise ValueError('model_call_id')
            return self._get('/api/v3/model-calls/'+model_call_id)
        if op=='model_call_list':
            q=[]
            if isinstance(args.get('mission_id'),str):q.append(('mission_id',args['mission_id']))
            if isinstance(args.get('assignment_id'),str):q.append(('assignment_id',args['assignment_id']))
            q.append(('limit',str(int(args.get('limit',200)))))
            return self._get('/api/v3/model-calls?'+urllib.parse.urlencode(q))
        if op=='process':
            mid=args.get('mission_id')
            if not isinstance(mid,str) or not self.MID_RE.fullmatch(mid):raise ValueError('mission_id')
            return self._get('/api/v3/missions/'+mid+'/process')
        if op=='post_message':
            mid=args.get('mission_id');protocol=args.get('protocol');phase=args.get('phase');payload=args.get('payload');from_id=args.get('from_id') or 'LPCL_PANEL';to_id=args.get('to_id') or 'MISSION_CONTROL'
            if not isinstance(mid,str) or not self.MID_RE.fullmatch(mid):raise ValueError('mission_id')
            if protocol not in self.ALLOWED_PROTOCOLS or not isinstance(payload,dict):raise ValueError('protocol message')
            return self._post('/api/v3/missions/'+mid+'/messages',{'protocol':protocol,'from_id':from_id,'to_id':to_id,'phase':phase,'payload':payload})
        if op=='validate_lpcl':return self.validate(args.get('lpcl_text'))
        if op=='register_lpcl':
            source=args.get('lpcl_text');v=self.validate(source);out=self._post('/api/v3/missions/register-lpcl',v['spec'])
            mission=out.get('mission') if isinstance(out,dict) else None
            if not isinstance(mission,dict):raise ValueError('REGISTERED_SOURCE_DRIFT:missing mission readback')
            backend_mid=mission.get('mission_id') or (mission.get('process') or {}).get('mission_id')
            backend_digest=mission.get('spec_digest') or (mission.get('process') or {}).get('lpcl_digest')
            if backend_mid!=v['spec']['mission_id'] or backend_digest!=v['lpcl_digest']:raise ValueError('REGISTERED_SOURCE_DRIFT')
            return {**out,'registration_confirmation':{'mission_id':backend_mid,'lpcl_digest':backend_digest,'source_length':len(source),'authority_effect':'NONE'}}
        if op=='activate_lpcl':
            mid=args.get('mission_id');dg=args.get('lpcl_digest')
            if not isinstance(mid,str) or not self.MID_RE.fullmatch(mid) or not isinstance(dg,str) or not re.fullmatch('[0-9a-f]{64}',dg):raise ValueError('activation')
            out=self._post('/api/v3/missions/'+mid+'/activate',{'lpcl_digest':dg,'activation_event':'EXPLICIT_UI_ACTIVATION'})
            if not isinstance(out,dict) or out.get('mission_id')!=mid:raise ValueError('ACTIVATION_SOURCE_DRIFT')
            return {**out,'activation_confirmation':{'mission_id':mid,'lpcl_digest':dg,'authority_effect':'EXPLICIT_USER_ACTIVATION'}}
        if op=='current_action':
            action=args.get('action');pod=args.get('pod_name')
            if action not in {'START','PAUSE','RESUME','VALIDATE','STOP','RESTART_ONE'}:raise ValueError('action')
            body={'action':action}
            if action=='RESTART_ONE':
                if not isinstance(pod,str) or len(pod)>180:raise ValueError('pod')
                body['pod_name']=pod
            return self._post('/api/v3/missions/current/actions',body,timeout=240)
        raise ValueError('control operation denied')

def _read_operator_local_secret(path):
    p=Path(path).resolve();raw=p.read_bytes()
    if os.name!='nt' or p.suffix.lower()!='.dpapi':
        value=raw.decode('utf-8').strip()
        if len(value)<64:raise ValueError('operator local secret malformed')
        return value
    import ctypes
    from ctypes import wintypes
    class DATA_BLOB(ctypes.Structure):
        _fields_=[('cbData',wintypes.DWORD),('pbData',ctypes.POINTER(ctypes.c_byte))]
    buf=ctypes.create_string_buffer(raw);src=DATA_BLOB(len(raw),ctypes.cast(buf,ctypes.POINTER(ctypes.c_byte)));dst=DATA_BLOB()
    crypt32=ctypes.windll.crypt32;kernel32=ctypes.windll.kernel32
    if not crypt32.CryptUnprotectData(ctypes.byref(src),None,None,None,None,0,ctypes.byref(dst)):
        raise OSError(ctypes.get_last_error(),'DPAPI CryptUnprotectData failed')
    try:value=ctypes.string_at(dst.pbData,dst.cbData).decode('utf-8').strip()
    finally:kernel32.LocalFree(dst.pbData)
    if len(value)<64:raise ValueError('operator local secret malformed')
    return value


class OperatorControlBridge:
    """Bounded 8780 transport proxy; human authority requires a gateway session."""
    def __init__(self,base,key_file,pairing_file=None):
        self.base=str(base).rstrip('/');self.key=_read_operator_local_secret(key_file);self.pairing_file=str(pairing_file) if pairing_file else None
        if len(self.key)<64:raise ValueError('operator panel proxy key unavailable')
    def _request(self,path,body=None,timeout=8,session_token=None):
        data=None;headers={'Accept':'application/json','User-Agent':'LION-8780-Operator-Proxy/1','X-LION-Panel-Proxy-Key':self.key};method='GET'
        if session_token:headers['X-LION-Operator-Session']=session_token
        if body is not None:data=json.dumps(body,ensure_ascii=False,separators=(',',':')).encode();headers['Content-Type']='application/json';method='POST'
        req=urllib.request.Request(self.base+path,data=data,headers=headers,method=method)
        try:
            with urllib.request.urlopen(req,timeout=timeout) as res:return json.load(res)
        except urllib.error.HTTPError as error:
            try:detail=json.loads(error.read(4096)).get('error','operator gateway rejected')
            except Exception:detail='operator gateway rejected'
            raise ValueError('Operator Control '+str(error.code)+': '+str(detail)[:600]) from error
    def __call__(self,op,args):
        args=dict(args or {})
        if op=='pair':
            pairing_code=args.get('pairing_code')
            if pairing_code:
                return self._request('/v1/session/pair',{'pairing_code':pairing_code},10)
            challenge=self._request('/v1/session/pair/challenge',{},10)
            challenge_id=challenge.get('challenge_id');code=challenge.get('pairing_code')
            if not isinstance(challenge_id,str) or not isinstance(code,str):raise ValueError('operator pairing challenge unavailable')
            return self._request('/v1/session/pair',{'challenge_id':challenge_id,'pairing_code':code},10)
        if op=='session':return self._request('/v1/session',session_token=args.get('session_token'))
        if op=='unpair':return self._request('/v1/session/revoke',{},10,session_token=args.get('session_token'))
        if op=='state':
            mid=args.get('mission_id');return self._request('/v1/state?'+urllib.parse.urlencode({'mission_id':mid}),session_token=args.get('session_token'))
        if op=='thread':
            correlation_id=args.get('correlation_id');limit=int(args.get('limit',500))
            return self._request('/v1/thread?'+urllib.parse.urlencode({'correlation_id':correlation_id,'limit':limit}),session_token=args.get('session_token'))
        if op=='participants':return self._request('/v1/participants',session_token=args.get('session_token'))
        if op=='events':
            return self._request('/v1/events?'+urllib.parse.urlencode({'mission_id':args.get('mission_id'),'after':int(args.get('after',0)),'limit':int(args.get('limit',200))}),session_token=args.get('session_token'))
        if op=='swarm_active':
            return self._request('/v1/swarm/session/active',session_token=args.get('session_token'))
        if op=='swarm_open':
            body={'mission_id':args.get('mission_id')}
            if args.get('duration_seconds') is not None:body['duration_seconds']=int(args['duration_seconds'])
            if args.get('workers') is not None:body['workers']=list(args['workers'])
            if args.get('mode') is not None:body['mode']=str(args['mode'])
            return self._request('/v1/swarm/sessions',body,15,session_token=args.get('session_token'))
        if op=='swarm_snapshot':
            sid=urllib.parse.quote(str(args.get('session_id')),safe='')
            return self._request('/v1/swarm/sessions/'+sid+'/snapshot',session_token=args.get('session_token'))
        if op=='swarm_stream':
            sid=urllib.parse.quote(str(args.get('session_id')),safe='')
            query=urllib.parse.urlencode({'after':int(args.get('after',0)),'limit':int(args.get('limit',25))})
            return self._request('/v1/swarm/sessions/'+sid+'?'+query,timeout=15,session_token=args.get('session_token'))
        session_token=args.pop('__session_token',None)
        if op=='swarm_send':
            sid=urllib.parse.quote(str(args.pop('session_id')),safe='')
            return self._request('/v1/swarm/sessions/'+sid+'/messages',args,20,session_token=session_token)
        if op=='command':return self._request('/v1/commands',args,15,session_token=session_token)
        if op=='command_status':return self._request('/v1/commands/'+urllib.parse.quote(str(args.get('command_id')),safe=''),session_token=session_token)
        if op=='ack':return self._request('/v1/events/ack',args,session_token=session_token)
        raise ValueError('operator operation denied')


class MaterialDroneBroker:
    def __init__(self,runtime_dir):
        self.root=Path(runtime_dir).resolve();self.local=threading.local()
    def begin(self):self.local.receipts=[]
    def _remember(self,r):
        if not hasattr(self.local,'receipts'):self.local.receipts=[]
        self.local.receipts.append({k:r.get(k) for k in ('task_id','drone_id','runtime_identity','role','status','receipt_digest','authority_effect')})
    def receipts(self):return list(getattr(self.local,'receipts',[]))
    def fleet_state(self):
        rows=[];now=datetime.now(timezone.utc)
        for drone,role in DRONE_ROLES.items():
            p=self.root/'health'/f'{drone}.json'
            try:
                h=json.loads(p.read_text(encoding='utf-8'));stamp=h.get('observed_at') or h.get('started_at');age=(now-datetime.fromisoformat(stamp)).total_seconds();h['heartbeat_age_seconds']=round(age,3);h['live']=h.get('status')=='READY' and age<3;rows.append(h)
            except Exception:rows.append({'drone_id':drone,'role':role,'status':'UNKNOWN','live':False,'authority_effect':'NONE'})
        return {'requested':12,'healthy':sum(1 for x in rows if x.get('live')),'rows':rows,'authority_effect':'NONE'}
    def _intrinsic(self,r):
        if type(r) is not dict or r.get('authority_effect')!='NONE':raise ValueError('material receipt authority')
        rd=r.get('receipt_digest');payload={k:r[k] for k in r if k!='receipt_digest'}
        if not isinstance(rd,str) or digest(payload)!=rd or digest(r.get('result'))!=r.get('result_digest'):raise ValueError('material receipt digest')
        return r
    @staticmethod
    def _read_json_transient(path,deadline):
        path=Path(path);last=None
        while time.time()<deadline:
            try:return json.loads(path.read_text(encoding='utf-8'))
            except (PermissionError,OSError,json.JSONDecodeError) as e:
                last=e;time.sleep(.02)
        if last:raise last
        raise TimeoutError(f'material json read timeout:{path.name}')
    def _call_raw(self,drone,operation,args,timeout=30):
        if drone not in DRONE_ROLES:raise ValueError('unknown material drone')
        task_id=uuid.uuid4().hex;task={'task_id':task_id,'drone_id':drone,'operation':operation,'args':args,'created_at':time.time_ns()}
        out=self.root/'outbox'/drone/f'{task_id}.json';atomic_json(self.root/'inbox'/drone/f'{task_id}.json',task)
        end=time.time()+timeout
        while time.time()<end:
            if out.exists():
                try:
                    r=self._intrinsic(self._read_json_transient(out,min(end,time.time()+1.0)))
                    hp=self.root/'health'/f'{drone}.json';h=self._read_json_transient(hp,min(end,time.time()+1.0))
                except (PermissionError,OSError,json.JSONDecodeError):
                    time.sleep(.04);continue
                if r.get('runtime_identity')!=h.get('runtime_identity'):raise ValueError('material runtime identity drift')
                try:out.unlink()
                except OSError:pass
                self._remember(r);return r
            time.sleep(.04)
        raise TimeoutError(f'material drone timeout:{drone}')
    def call(self,drone,operation,args,timeout=30,validate=True):
        r=self._call_raw(drone,operation,args,timeout)
        if r.get('status')!='PASS':raise ValueError(f"material drone denied:{r.get('result')}")
        if validate and drone not in {'MAT08','MAT10'}:
            for v in ('MAT08','MAT10'):
                vr=self._call_raw(v,'validate_receipt',{'receipt':r},10)
                if vr.get('status')!='PASS' or not vr.get('result',{}).get('valid'):raise ValueError('material receipt validation failed')
        return r
    def aggregate(self):
        ds=[x.get('receipt_digest') for x in self.receipts() if isinstance(x.get('receipt_digest'),str)]
        if not ds:return None
        c=self.call('MAT11','coordinate',{'receipt_digests':ds},validate=True)
        all_ds=[x.get('receipt_digest') for x in self.receipts() if isinstance(x.get('receipt_digest'),str)]
        f=self.call('MAT12','reconcile',{'receipt_digests':all_ds},validate=True)
        return {'coordinator':c['result'],'reconciler':f['result']}

def providers(broker,model):
    def cur(kind,args):
        if kind=='github_branch':
            r=broker.call('MAT04','github_branch',{'repository':args['repository'],'branch':args['branch']});x=r['result'];return {'head':x['head'],'tree':x['tree']}
        if kind=='local_model':return broker.call('MAT09','model_health',{})['result']
        raise ValueError('provider kind denied')
    def gitprov(op,args):
        if op not in {'head_tree','status'}:raise ValueError('git op denied')
        return broker.call('MAT01',op,{})['result']
    def content(op,args):
        if op not in {'read_file','search'}:raise ValueError('content op denied')
        return broker.call('MAT02',op,args)['result']
    def source(op,args):
        if op=='local_clones':return broker.call('MAT03','local_clones',{})['result']
        if op=='federation':return broker.call('MAT04','federation',{})['result']
        if op=='branch_state':return broker.call('MAT04','github_branch',{'repository':args['repository'],'branch':args['branch']})['result']
        raise ValueError('source op denied')
    def mission(op,args):
        if op=='recent':return broker.call('MAT04','mission_recent',{})['result']
        if op=='process':return broker.call('MAT04','mission_process',{'mission_id':args['mission_id']})['result']
        raise ValueError('mission op denied')
    class MaterialWeb:
        def search(self,query,limit=5):
            r=broker.call('MAT05','web_search',{'query':query,'limit':limit});rows=r['result']
            for row in rows:broker.call('MAT07','validate_web',{'url':row['url']})
            return tuple(rows)
        def fetch(self,url):
            broker.call('MAT07','validate_web',{'url':url});d=broker.call('MAT06','web_fetch',{'url':url})['result'];return WebEvidence(**d)
    def modelprov(messages,max_tokens=384):
        broker.call('MAT09','model_health',{})
        d=_json_request(model.rstrip('/')+'/v1/chat/completions',body={'messages':messages,'max_tokens':max_tokens,'temperature':0.1,'stream':False},timeout=90)
        return d['choices'][0]['message']['content']
    return cur,gitprov,content,source,mission,MaterialWeb(),modelprov



def local_assignment_worker_once(control, modelprov, *, material_drone_id='MD025', pending=None):
    if pending is None:
        pending=control('local_assignments',{'limit':16}).get('assignments') or []
    for row in pending:
        if row.get('material_drone_id')!=material_drone_id:continue
        aid=row.get('assignment_id')
        try:claimed=control('local_assignment_claim',{'assignment_id':aid,'material_drone_id':material_drone_id})
        except Exception:continue
        model_call_id=None;model_state=None
        try:
            payload=json.loads(claimed.get('input_json') or '{}')
            if payload.get('kind')!='LOCAL_MODEL_INFERENCE':raise ValueError('unsupported local assignment kind')
            messages=payload.get('messages')
            if not isinstance(messages,list) or not messages:raise ValueError('local assignment messages')
            messages=[dict(m) for m in messages if isinstance(m,dict) and m.get('role') in {'system','user','assistant'} and isinstance(m.get('content'),str)]
            trusted_participant_context=payload.get('trusted_participant_context')
            trusted_source_context=payload.get('trusted_source_context')
            evidence_classes=payload.get('evidence_classes') or []
            if trusted_participant_context is not None and type(trusted_participant_context) is not dict:raise ValueError('trusted participant context')
            if trusted_source_context is not None and type(trusted_source_context) is not dict:raise ValueError('trusted source context')
            if type(evidence_classes) is not list or any(x not in {'TRUSTED_TOPOLOGY_CONTEXT','OPERATOR_MESSAGE','MODEL_CLAIM'} for x in evidence_classes):raise ValueError('communication evidence classes')
            conversation_mode=payload.get('purpose')=='OPERATOR_BUS_CONVERSATION_R1'
            communication_context={
                'schema':'lion.cognitive-participant-context/v1',
                'mission_id':claimed.get('mission_id'),
                'phase_id':claimed.get('phase_id'),
                'logical_drone_id':claimed.get('logical_drone_id') if payload.get('conversation_context_class')!='OPERATOR_BUS' else None,
                'logical_context':payload.get('logical_context') or ('drone:'+str(claimed.get('logical_drone_id') or 'UNKNOWN')),
                'conversation_context_class':payload.get('conversation_context_class'),
                'conversation_binding_mode':payload.get('conversation_binding_mode'),
                'material_worker_id':claimed.get('material_drone_id'),
                'cognitive_executor':'model:local',
                'model':'gpt-oss-20b-MXFP4',
                'direct_effect_authority':'NONE',
                'mediated_system_communication':'AVAILABLE',
                'mediated_channels':['mission_control','operator_bus','logical_drone_context','material_worker_receipt','chatgpt_saas_via_control_plane'],
                'reply_path':['model:local','worker:'+str(claimed.get('material_drone_id') or 'UNKNOWN'),'mission_control'],
                'effect_rule':'MODEL_OUTPUT_IS_ADVISORY; EFFECTS_REQUIRE_ADMITTED_CAPABILITY_AND_AUTHORITY',
            }
            communication_guidance=(
                'LION COMMUNICATION CONTEXT. PARTICIPANT ONTOLOGY IS STRICT. '
                'You are model:local (gpt-oss-20b-MXFP4), the shared proposal-only cognitive executor. '
                'You are NOT worker:'+str(claimed.get('material_drone_id') or 'UNKNOWN')+' and you are NOT drone:'+str(claimed.get('logical_drone_id') or 'UNKNOWN')+'. '
                'worker:MDxxx is the bounded material runtime that invokes you and carries the assignment/receipt. '
                'drone:LDxxx is a logical role/context bound by Mission Control to a worker; it is not a physical agent and not a model. '
                'operator:primary is the human operator. model:saas is the remote cognitive supervisor. Mission Control is the control plane. '
                'You have no direct OS/tool/effect authority, but you DO have mediated communication through LION: your answer returns through the bound worker, is persisted as a receipt, and can be routed by Mission Control to logical drones, the operator, or ChatGPT SaaS. '
                'Never collapse "no direct authority" into "I cannot communicate with the system". '
                'If asked who you are, identify yourself as model:local and separately name the current worker and logical context. '
                'Do not claim that a worker or logical drone has thoughts, knowledge, sensors, physical embodiment, or model identity. '
                'When asked to help the system, reason substantively and emit the bounded request/handoff that LION can route. '
                'Never claim an effect occurred unless a matching receipt is supplied. Current participant context follows: '
                +json.dumps(communication_context,ensure_ascii=False,sort_keys=True)
            )
            if conversation_mode:
                communication_guidance=(
                    'LION OPERATOR BUS CONVERSATION. Answer the human operator latest message directly and substantively. '
                    'Do not begin by reciting your identity, worker id, logical context, mission id, or transport unless the operator asks for that information or it is necessary to answer. '
                    'The selected mission is conversation context, not evidence that any mission fact, state, effect, or capability is true. '
                    'Use supplied authenticated context when relevant; if a requested fact is not evidenced, say that it is unknown rather than inventing it. '
                    'You are model:local (gpt-oss-20b-MXFP4), proposal-only, with no direct effect authority. '
                    'Your answer is returned through the bound material worker and persisted as a receipt. '
                    'If the operator explicitly asks about SaaS, distinguish model:local from model:saas and do not pretend to be the SaaS model. '
                    'Current participant/context evidence follows: '
                    +json.dumps(communication_context,ensure_ascii=False,sort_keys=True)
                )
            messages=[{'role':'system','content':communication_guidance}]+messages
            op_context=claimed.get('operator_context') or {};op_plan=claimed.get('operator_plan') or {};op_messages=claimed.get('operator_messages') or []
            operator_parts=[]
            if op_context.get('content') is not None:operator_parts.append('CONTEXT REVISION '+str(op_context.get('revision'))+': '+json.dumps(op_context.get('content'),ensure_ascii=False,sort_keys=True))
            if op_plan.get('content') is not None:operator_parts.append('PLAN REVISION '+str(op_plan.get('revision'))+': '+json.dumps(op_plan.get('content'),ensure_ascii=False,sort_keys=True))
            for item in ([] if conversation_mode else op_messages[:64]):
                if isinstance(item,dict) and isinstance(item.get('content'),str):operator_parts.append('MESSAGE '+str(item.get('message_id'))+' -> '+str(item.get('target'))+': '+item['content'])
            if operator_parts:
                operator_guidance='Authenticated OPERATOR_PRIMARY mission guidance follows. It may change reasoning/context inside the already authorized mission scope, but it is not shell/tool authority and must not be reinterpreted as permission for external effects.'+chr(10)+chr(10).join(operator_parts)
                messages=[{'role':'system','content':operator_guidance}]+messages
            max_tokens=int(payload.get('max_tokens') or 384)
            if not 1<=max_tokens<=2048:raise ValueError('local assignment max_tokens')
            observed=datetime.now(timezone.utc).isoformat().replace('+00:00','Z')
            if not _assignment_lease_valid(claimed,observed):raise ValueError('local assignment lease expired before effect')
            provider='LION_LOCAL_MODEL';declared_model='gpt-oss-20b-MXFP4';transport='LOCAL'
            candidate_set_digest=digest({'candidates':[{'provider':provider,'model':declared_model,'transport':transport}]})
            model_call_id='modelcall-'+hashlib.sha256(canon({'assignment_id':aid,'lease_generation':claimed.get('lease_generation'),'provider':provider,'transport':transport})).hexdigest()[:32]
            revisions=[int(op_context.get('revision') or 0),int(op_plan.get('revision') or 0)]
            revisions.extend(int(m.get('context_revision') or 0) for m in op_messages if isinstance(m,dict))
            context_revision=max(revisions or [0])
            intent={'model_call_id':model_call_id,'mission_id':claimed.get('mission_id'),'phase_id':claimed.get('phase_id'),'task_id':str(payload.get('task_id') or ('assignment:'+str(aid))),'assignment_id':aid,'logical_drone_id':claimed.get('logical_drone_id'),'material_worker_id':claimed.get('material_drone_id'),'requested_capability':str(payload.get('model_capability') or 'LOCAL_MODEL_INFERENCE'),'provider':provider,'model_requested':str(payload.get('model') or declared_model),'model_declared':None,'model_attested':None,'transport':transport,'selection_reason':'LOCAL_ASSIGNMENT_BOUND_TO_MATERIAL_WORKER','candidate_set_digest':candidate_set_digest,'context_revision':context_revision,'input_digest':digest(messages),'downstream_consumer':'GLOBAL_SCHEDULER','authority_effect':'NONE'}
            control('model_call_intent',intent);model_state='INTENT_DURABLE'
            transition_base={'result_digest':None,'model_declared':None,'model_attested':None,'downstream_consumer':'GLOBAL_SCHEDULER','authority_effect':'NONE'}
            control('model_call_transition',{'model_call_id':model_call_id,'state':'SEND_ATTEMPT',**transition_base});model_state='SEND_ATTEMPT'
            try:
                raw_answer=modelprov(messages,max_tokens)
            except Exception:
                try:control('model_call_transition',{'model_call_id':model_call_id,'state':'SEND_UNKNOWN',**transition_base});model_state='SEND_UNKNOWN'
                except Exception:pass
                raise
            answer=str(raw_answer).strip();answer_digest=hashlib.sha256(answer.encode('utf-8')).hexdigest()
            control('model_call_transition',{'model_call_id':model_call_id,'state':'SEND_CONFIRMED','result_digest':answer_digest,'model_declared':declared_model,'model_attested':None,'downstream_consumer':'GLOBAL_SCHEDULER','authority_effect':'NONE'});model_state='SEND_CONFIRMED'
            if not answer:
                control('model_call_transition',{'model_call_id':model_call_id,'state':'FAILED','result_digest':answer_digest,'model_declared':declared_model,'model_attested':None,'downstream_consumer':'GLOBAL_SCHEDULER','authority_effect':'NONE'});model_state='FAILED'
                raise ValueError('empty local model result')
            payload_message_ids=payload.get('operator_message_ids') if conversation_mode else None
            if conversation_mode and not (isinstance(payload_message_ids,list) and payload_message_ids and all(isinstance(x,str) and x for x in payload_message_ids)):raise ValueError('conversation operator_message_ids')
            result_message_ids=list(payload_message_ids) if conversation_mode else [m.get('message_id') for m in op_messages if isinstance(m,dict) and isinstance(m.get('message_id'),str)]
            result={'kind':'LOCAL_MODEL_INFERENCE','model':declared_model,'model_call_id':model_call_id,'transport':transport,'response_text':answer,'response_digest':answer_digest,'trajectory_role':payload.get('trajectory_role'),'evidence_bundle_digest':payload.get('evidence_bundle_digest'),'purpose':payload.get('purpose'),'operator_context_revision':op_context.get('revision'),'operator_plan_revision':op_plan.get('revision'),'operator_message_ids':result_message_ids,'participant_context':communication_context,'trusted_participant_context':trusted_participant_context,'trusted_source_context':trusted_source_context,'evidence_classes':list(evidence_classes),'source_participant':'model:local','reply_via':'worker:'+str(claimed.get('material_drone_id') or 'UNKNOWN'),'logical_context':payload.get('logical_context') or ('drone:'+str(claimed.get('logical_drone_id') or 'UNKNOWN')),'authority_effect':'NONE'}
            dual_id=payload.get('dual_request_id')
            if dual_id:control('dual_response',{'request_id':dual_id,'provider':declared_model,'response_text':answer,'transport':'WINDOWS_LOCAL_MODEL_LOOPBACK'})
            receipt=control('local_assignment_receipt',{'assignment_id':aid,'material_drone_id':claimed.get('material_drone_id'),'lease_generation':claimed.get('lease_generation'),'status':'PASS','result':result,'effect_receipt_digest':None})
            control('model_call_transition',{'model_call_id':model_call_id,'state':'RESPONSE_RECONCILED','result_digest':answer_digest,'model_declared':declared_model,'model_attested':None,'downstream_consumer':'GLOBAL_SCHEDULER','authority_effect':'NONE'});model_state='RESPONSE_RECONCILED'
            return receipt
        except Exception as exc:
            if model_call_id and model_state in {'INTENT_DURABLE','SEND_CONFIRMED'}:
                try:
                    fail_digest=hashlib.sha256((type(exc).__name__+':'+str(exc)[:600]).encode('utf-8')).hexdigest()
                    control('model_call_transition',{'model_call_id':model_call_id,'state':'FAILED','result_digest':fail_digest,'model_declared':None,'model_attested':None,'downstream_consumer':'GLOBAL_SCHEDULER','authority_effect':'NONE'})
                except Exception:pass
            result={'kind':'LOCAL_MODEL_INFERENCE','model_call_id':model_call_id,'model_call_state':model_state,'error':type(exc).__name__+':'+str(exc)[:600],'authority_effect':'NONE'}
            return control('local_assignment_receipt',{'assignment_id':aid,'material_drone_id':claimed.get('material_drone_id'),'lease_generation':claimed.get('lease_generation'),'status':'FAIL','result':result,'effect_receipt_digest':None})
    return None


def local_assignment_worker_loop(control,modelprov,stop_event,material_drone_id='MD025'):
    while not stop_event.is_set():
        try:local_assignment_worker_once(control,modelprov,material_drone_id=material_drone_id)
        except Exception:pass
        stop_event.wait(1)

RUNTIME_STARTED_AT=datetime.now(timezone.utc).isoformat()
RECON_CAPABILITY_CLASS='CONTROL_PLANE_RECONNAISSANCE'
RECON_WINDOWS_SCHEMA='lion.control-plane-windows-observation/v1'


def _recon_sha(path):
    try:
        h=hashlib.sha256()
        with Path(path).open('rb') as f:
            while True:
                b=f.read(1024*1024)
                if not b:break
                h.update(b)
        return h.hexdigest()
    except OSError:return None


RUNTIME_LOADED_SOURCE_SHA=_recon_sha(Path(__file__).resolve())
GATEWAY_LOADED_SOURCE_SHA=_recon_sha(Path(sys.modules[Gateway.__module__].__file__).resolve())


def _recon_observation_fingerprint(*,phase,runtime_loaded_sha,gateway_loaded_sha,features,local,github,thread_identity):
    feature_digest=hashlib.sha256(json.dumps(features,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    value={'phase':phase,'runtime_loaded':runtime_loaded_sha,'gateway_loaded':gateway_loaded_sha,'feature_digest':feature_digest,'local':local,'github':github,'thread':thread_identity}
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest(),feature_digest


def _recon_text(path):
    try:return Path(path).read_text(encoding='utf-8',errors='replace')
    except OSError:return ''


def _recon_thread_db(path):
    path=Path(path)
    try:
        uri='file:'+path.as_posix()+'?mode=ro';c=sqlite3.connect(uri,uri=True);integrity=c.execute('PRAGMA integrity_check').fetchone()[0];schema=c.execute('PRAGMA schema_version').fetchone()[0];threads=c.execute('SELECT COUNT(*) FROM threads').fetchone()[0];messages=c.execute('SELECT COUNT(*) FROM messages').fetchone()[0];c.close();value={'path':str(path),'integrity':integrity,'schema_version':schema,'thread_count':threads,'message_count':messages,'size_bytes':path.stat().st_size};value['identity_digest']=hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest();return value
    except Exception as exc:return {'path':str(path),'integrity':'UNKNOWN','error_class':type(exc).__name__,'identity_digest':None}


def _recon_source_snapshot(repo):
    repo=Path(repo).resolve();rels=(
      'tools/lion_local_intelligence_runtime.py','cyber_lion/app_coordination/local_intelligence_gateway.py','tools/lion_saas_broker.py',
      'cyber_lion/app_coordination/saas_thread_delivery.py','cyber_lion/app_coordination/saas_handoff_extension.py',
      'cyber_lion/process_language/lpcl.py','cyber_lion/contracts/phase_execution_contract.py','tools/lion_mission_control_v3.py',
    )
    return {rel:_recon_sha(repo/rel) for rel in rels if (repo/rel).is_file()}


def _recon_source_features(repo):
    repo=Path(repo).resolve();gateway=_recon_text(repo/'cyber_lion/app_coordination/local_intelligence_gateway.py');delivery=_recon_text(repo/'cyber_lion/app_coordination/saas_thread_delivery.py');ext=_recon_text(repo/'cyber_lion/app_coordination/saas_handoff_extension.py');broker=_recon_text(repo/'tools/lion_saas_broker.py');dual_join_source=_recon_text(repo/'cyber_lion/mission_control/dual_result_join.py')
    try:parser=inspect.getsource(LpclControlBridge._parse_pairs)
    except Exception:parser=''
    return {
      'lpcl_parser_sha256':hashlib.sha256(parser.encode()).hexdigest(),
      'panel_exact_source_state_machine':all(x in gateway for x in ('validated_source','REGISTERED_SOURCE_DRIFT','ACTIVATION_DIGEST_DRIFT')),
      'panel_backward_compatibility':all(x in Path(__file__).read_text(encoding='utf-8',errors='replace') for x in ('LOGICAL_DRONES','MATERIAL_FLEET_TARGET')),
      'thread_delivery_exact_once':bool("append_assistant_once" in delivery and re.search(r"[\"']dedupe_key[\"']\s*:\s*[\"']saas:",delivery)),
      'thread_request_linkage':'saas_request_id' in delivery and 'thread_id' in delivery,
      'thread_delivery_receipt_gate':'receipt_digest' in delivery and "status')!='RESPONDED'" in delivery,
      'thread_delete_safety':'concurrently deleted conversation' in delivery,
      'dual_create':'dual_create' in ext,'dual_local_result':'dual_response' in ext,'dual_saas_link':'dual_link_saas' in ext,
      'dual_join':bool('dual_result' in gateway and 'dual_result' in delivery and 'JOINED' in dual_join_source),
      'broker_request_state_machine':'saas_handoff_requests' in broker and 'WAITING_SUPERVISOR' in broker,
      'broker_claim_fencing':'claim_generation' in broker and 'claim_expires_at' in broker,
      'broker_session_binding':'saas_session_bindings' in broker,
    }


def control_plane_recon_observer_once(control,broker,gitprov,thread_db,repo,model_url):
    recent=control('recent',{});mid=recent.get('focus_mission_id')
    if not mid:return None
    snap=control('process',{'mission_id':mid});phase=(snap.get('process') or {}).get('current_phase')
    if not phase:return None
    contract=next((x for x in (snap.get('phase_execution_contracts') or []) if x.get('phase_id')==phase),None)
    if not contract or RECON_CAPABILITY_CLASS not in (contract.get('capability_classes') or []):return None
    repo=Path(repo).resolve();runtime_path=Path(__file__).resolve();gateway_path=Path(sys.modules[Gateway.__module__].__file__).resolve();runtime_file_sha=_recon_sha(runtime_path);gateway_file_sha=_recon_sha(gateway_path);frontend=hashlib.sha256(UI.encode()).hexdigest()
    local=gitprov('head_tree',{});status=gitprov('status',{});gh=broker.call('MAT04','github_branch',{'repository':'DonkeyJJLove/ai_platform','branch':'master'})['result'];model=broker.call('MAT09','model_health',{})['result'];thread=_recon_thread_db(thread_db);sources=_recon_source_snapshot(repo);features=_recon_source_features(repo);saas=control('saas_status',{})
    fingerprint,feature_digest=_recon_observation_fingerprint(phase=phase,runtime_loaded_sha=RUNTIME_LOADED_SOURCE_SHA,gateway_loaded_sha=GATEWAY_LOADED_SOURCE_SHA,features=features,local=local,github={'head':gh.get('head'),'tree':gh.get('tree')},thread_identity=thread.get('identity_digest'))
    for msg in snap.get('protocol_messages') or []:
        payload=msg.get('payload') or {}
        if msg.get('phase')==phase and payload.get('event')=='CONTROL_PLANE_WINDOWS_OBSERVATION' and payload.get('source_fingerprint')==fingerprint:return {'idempotent':True,'source_fingerprint':fingerprint}
    health=model.get('health') if isinstance(model,dict) else None;health_state=(health or {}).get('status') if isinstance(health,dict) else None
    payload={'event':'CONTROL_PLANE_WINDOWS_OBSERVATION','schema':RECON_WINDOWS_SCHEMA,'source_fingerprint':fingerprint,'snapshot':{
      'runtime':{'pid':os.getpid(),'runtime_started_at':RUNTIME_STARTED_AT,'python_runtime':sys.version.split()[0],'argv':[str(x) for x in sys.argv],'runtime_source_sha256':RUNTIME_LOADED_SOURCE_SHA,'runtime_file_sha256':runtime_file_sha,'gateway_source_sha256':GATEWAY_LOADED_SOURCE_SHA,'gateway_file_sha256':gateway_file_sha,'feature_vector_digest':feature_digest,'frontend_revision':frontend,'mission_control_url':getattr(control,'base',None),'model_endpoint':model_url},
      'repo':{'local_head':local.get('head'),'local_tree':local.get('tree'),'status_count':len(status) if isinstance(status,list) else None,'github_master':{'head':gh.get('head'),'tree':gh.get('tree')}},
      'thread_db':thread,
      'model':{'endpoint':model_url,'health':health_state or model.get('status') if isinstance(model,dict) else 'UNKNOWN','model_count':len(model.get('models') or []) if isinstance(model,dict) else None,'model_ids':[x.get('id') for x in (model.get('models') or []) if isinstance(x,dict)] if isinstance(model,dict) else []},
      'sources':sources,'source_features':features,
      'provider_graph':['MAT01_LOCAL_REPOSITORY_CURRENTNESS','MAT02_LOCAL_REPOSITORY_CONTENT','MAT04_FEDERATION_CURRENTNESS','MAT09_MODEL_GPU_OBSERVER','MISSION_CONTROL_8766','THREAD_DB'],
      'saas_projection':(saas.get('supervisor_projection') if isinstance(saas,dict) else None) or saas,
    },'authority_effect':'NONE'}
    return control('post_message',{'mission_id':mid,'protocol':'EVIDENCE','from_id':'LPCL_PANEL','to_id':'MISSION_EXECUTION_DRIVER','phase':phase,'payload':payload})


def control_plane_recon_observer_loop(control,broker,gitprov,thread_db,repo,model_url,stop_event):
    while not stop_event.is_set():
        try:control_plane_recon_observer_once(control,broker,gitprov,thread_db,repo,model_url)
        except Exception:pass
        stop_event.wait(2)


def local_canary_loop(control, modelprov, stop_event, panel_port, model_url):
    """Windows-side LOCAL canary producer for the self-hosting gate.

    Mission Control runs in WSL and must not probe Windows 127.0.0.1:8772.
    This loop executes the proposal-only local model in its own namespace and
    posts evidence only; it never advances a phase or grants authority.
    """
    while not stop_event.is_set():
        try:
            recent=control('recent',{})
            mid=recent.get('focus_mission_id')
            if mid:
                snap=control('process',{'mission_id':mid})
                phase=(snap.get('process') or {}).get('current_phase')
                if phase=='LIVE_AUTONOMY_CANARY':
                    exists=False
                    for msg in snap.get('protocol_messages') or []:
                        payload=msg.get('payload') or {}
                        if msg.get('protocol')=='EVIDENCE' and msg.get('from_id')=='LPCL_PANEL' and msg.get('phase')==phase and payload.get('event')=='LOCAL_MODEL_CANARY_PASS':
                            exists=True;break
                    if not exists:
                        prompt='LOCAL self-hosting inference canary: return any concise non-empty response.'
                        answer=str(modelprov([{'role':'system','content':'You are the proposal-only local LION cognitive executor. Return a concise response.'},{'role':'user','content':prompt}],64)).strip()
                        rd=hashlib.sha256(answer.encode('utf-8')).hexdigest()
                        pd=hashlib.sha256(prompt.encode('utf-8')).hexdigest()
                        if answer:
                            control('post_message',{'mission_id':mid,'protocol':'EVIDENCE','from_id':'LPCL_PANEL','to_id':'MISSION_EXECUTION_DRIVER','phase':phase,'payload':{'event':'LOCAL_MODEL_CANARY_PASS','model':'gpt-oss-20b-MXFP4','prompt_digest':pd,'response_digest':rd,'response_bytes':len(answer.encode('utf-8')),'transport':'WINDOWS_LOCAL_MODEL_LOOPBACK','authority_effect':'NONE'}})
                        else:
                            control('post_message',{'mission_id':mid,'protocol':'EVIDENCE','from_id':'LPCL_PANEL','to_id':'MISSION_EXECUTION_DRIVER','phase':phase,'payload':{'event':'LOCAL_MODEL_CANARY_EMPTY','model':'gpt-oss-20b-MXFP4','prompt_digest':pd,'response_digest':rd,'authority_effect':'NONE'}})
                elif phase=='READY_FOR_SYSTEM_ACCEPTANCE_TESTS':
                    exists=False
                    for msg in snap.get('protocol_messages') or []:
                        payload=msg.get('payload') or {}
                        if msg.get('protocol')=='EVIDENCE' and msg.get('from_id')=='LPCL_PANEL' and msg.get('phase')==phase and payload.get('event')=='WINDOWS_CONTROL_SURFACE_READBACK':
                            exists=True;break
                    if not exists:
                        panel=_json_request(f'http://127.0.0.1:{panel_port}/health',timeout=3)
                        models=_json_request(model_url.rstrip('/')+'/v1/models',timeout=5)
                        model_count=len(models.get('data') or []) if isinstance(models,dict) else 0
                        control('post_message',{'mission_id':mid,'protocol':'EVIDENCE','from_id':'LPCL_PANEL','to_id':'MISSION_EXECUTION_DRIVER','phase':phase,'payload':{'event':'WINDOWS_CONTROL_SURFACE_READBACK','panel_http':200 if panel.get('status')=='ok' else 0,'panel_authority_effect':panel.get('authority_effect'),'model_http':200,'model_count':model_count,'model_id':'gpt-oss-20b-MXFP4','authority_effect':'NONE'}})
        except Exception:
            pass
        stop_event.wait(5)

def main():
    p=argparse.ArgumentParser();p.add_argument('--repo',required=True);p.add_argument('--material-runtime-dir',required=True);p.add_argument('--rag');p.add_argument('--rag-sha');p.add_argument('--release');p.add_argument('--model',default='http://127.0.0.1:8772');p.add_argument('--model-sha',required=True);p.add_argument('--mission-control-url',default='http://127.0.0.1:8766');p.add_argument('--operator-control-url',default='http://127.0.0.1:8767');p.add_argument('--operator-key-file');p.add_argument('--operator-panel-proxy-key-file');p.add_argument('--operator-pairing-key-file');p.add_argument('--port',type=int,default=8780);p.add_argument('--thread-db');a=p.parse_args()
    if bool(a.rag)!=bool(a.rag_sha) or bool(a.rag)!=bool(a.release):raise SystemExit('rag, rag-sha and release must be supplied together')
    b=MaterialDroneBroker(a.material_runtime_dir);cur,gp,cp,sp,mission,web,mp=providers(b,a.model);thread_db=Path(a.thread_db).resolve() if a.thread_db else Path(a.material_runtime_dir).resolve().parent/'threads'/'lion-local-model.db';threads=ThreadStore(thread_db);control=LpclControlBridge(b,a.mission_control_url)
    operator_key_file=a.operator_panel_proxy_key_file or a.operator_key_file
    operator=OperatorControlBridge(a.operator_control_url,operator_key_file,a.operator_pairing_key_file) if operator_key_file else None
    g=Gateway(a.repo,a.rag,a.rag_sha,a.release,a.model,a.model_sha,mp,cur,gp,web=web,content_provider=cp,source_provider=sp,mission_provider=mission,control_provider=control,material_begin=b.begin,material_receipts=b.receipts,material_state=b.fleet_state,material_reconcile=b.aggregate,thread_provider=threads,operator_provider=operator)
    canary_stop=threading.Event();threading.Thread(target=local_canary_loop,args=(control,mp,canary_stop,a.port,a.model),daemon=True).start()
    for material_id in ('MD025','MD026','MD027'):
        threading.Thread(target=local_assignment_worker_loop,args=(control,mp,canary_stop,material_id),daemon=True,name='local-model-'+material_id).start()
    threading.Thread(target=control_plane_recon_observer_loop,args=(control,b,gp,thread_db,a.repo,a.model,canary_stop),daemon=True,name='control-plane-recon-observer').start()
    from cyber_lion.app_coordination.saas_thread_delivery import delivery_loop
    threading.Thread(target=delivery_loop,args=(threads,control,canary_stop),daemon=True,name='saas-thread-delivery').start()
    try: serve_gateway(g,a.port)
    finally: canary_stop.set()
if __name__=='__main__':main()
