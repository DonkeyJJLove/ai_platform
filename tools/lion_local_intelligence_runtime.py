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
import argparse,hashlib,json,os,threading,time,urllib.request,uuid,sqlite3,re
from datetime import datetime,timezone
from cyber_lion.app_coordination.local_intelligence_gateway import Gateway,serve_gateway
from cyber_lion.app_coordination.hybrid_gateway_extension import apply_hybrid_gateway_extension
apply_hybrid_gateway_extension(Gateway)
from cyber_lion.app_coordination.saas_handoff_extension import apply_saas_handoff_extension
apply_saas_handoff_extension(Gateway)
from cyber_lion.app_coordination.web_research_broker import WebEvidence

DRONE_ROLES={
'MAT01':'LOCAL_REPOSITORY_CURRENTNESS','MAT02':'LOCAL_REPOSITORY_CONTENT','MAT03':'LOCAL_CLONE_INVENTORY','MAT04':'FEDERATION_CURRENTNESS',
'MAT05':'PUBLIC_WEB_SEARCH','MAT06':'PUBLIC_WEB_FETCH','MAT07':'WEB_SECURITY_FALSIFIER','MAT08':'SOURCE_PROVENANCE_VALIDATOR',
'MAT09':'MODEL_GPU_OBSERVER','MAT10':'RESULT_VALIDATOR','MAT11':'MATERIAL_COORDINATOR','MAT12':'FINAL_RECONCILER'}

def canon(v):return json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False,default=str).encode('utf-8')
def digest(v):return hashlib.sha256(canon(v)).hexdigest()
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
    def __init__(self,path):
        self.path=Path(path).resolve();self.path.parent.mkdir(parents=True,exist_ok=True);self.lock=threading.RLock();self._init()
    def _conn(self):
        c=sqlite3.connect(self.path,timeout=10);c.row_factory=sqlite3.Row;c.execute('PRAGMA journal_mode=WAL');c.execute('PRAGMA foreign_keys=ON');return c
    def _init(self):
        with self.lock:
            c=self._conn();c.executescript("""
            CREATE TABLE IF NOT EXISTS threads(thread_id TEXT PRIMARY KEY,title TEXT NOT NULL,created_at REAL NOT NULL,updated_at REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS messages(message_id TEXT PRIMARY KEY,thread_id TEXT NOT NULL,seq INTEGER NOT NULL,role TEXT NOT NULL,content TEXT NOT NULL,created_at REAL NOT NULL,meta_json TEXT NOT NULL,FOREIGN KEY(thread_id) REFERENCES threads(thread_id) ON DELETE CASCADE,UNIQUE(thread_id,seq));
            CREATE INDEX IF NOT EXISTS idx_threads_updated ON threads(updated_at DESC);
            CREATE INDEX IF NOT EXISTS idx_messages_thread_seq ON messages(thread_id,seq);
            """);c.commit();c.close()
    def _id(self,v):
        if not isinstance(v,str) or not self.ID_RE.fullmatch(v):raise ValueError('thread_id')
        return v
    def __call__(self,op,args):
        args=args or {}
        with self.lock:
            c=self._conn()
            try:
                if op=='list':
                    rows=[dict(x) for x in c.execute('SELECT thread_id,title,created_at,updated_at FROM threads ORDER BY updated_at DESC LIMIT 500')];return {'threads':rows}
                if op=='create':
                    tid=uuid.uuid4().hex;title=str(args.get('title') or 'Nowa rozmowa').strip()[:120] or 'Nowa rozmowa';t=time.time();c.execute('INSERT INTO threads VALUES(?,?,?,?)',(tid,title,t,t));c.commit();return {'thread_id':tid,'title':title,'created_at':t,'updated_at':t,'messages':[]}
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
                    first=next((content for role,content in clean if role=='user'),clean[0][1]);title=' '.join(first.split())[:64] or 'Zaimportowana rozmowa';tid=uuid.uuid4().hex;t=time.time();c.execute('INSERT INTO threads VALUES(?,?,?,?)',(tid,title,t,t))
                    for seq,(role,content) in enumerate(clean,1):c.execute('INSERT INTO messages VALUES(?,?,?,?,?,?,?)',(uuid.uuid4().hex,tid,seq,role,content,t,json.dumps({'legacy_local_storage_import':True},sort_keys=True)))
                    c.commit();return {'thread_id':tid,'title':title,'created_at':t,'updated_at':t,'imported_messages':len(clean)}
                tid=self._id(args.get('thread_id'))
                if op=='get':
                    row=c.execute('SELECT * FROM threads WHERE thread_id=?',(tid,)).fetchone();
                    if row is None:raise KeyError('thread not found')
                    msgs=[]
                    for m in c.execute('SELECT message_id,seq,role,content,created_at,meta_json FROM messages WHERE thread_id=? ORDER BY seq',(tid,)):
                        d=dict(m);d['meta']=json.loads(d.pop('meta_json') or '{}');msgs.append(d)
                    return {**dict(row),'messages':msgs}
                if op=='rename':
                    title=str(args.get('title') or '').strip()[:120]
                    if not title:raise ValueError('title')
                    if c.execute('SELECT 1 FROM threads WHERE thread_id=?',(tid,)).fetchone() is None:raise KeyError('thread not found')
                    c.execute('UPDATE threads SET title=?,updated_at=? WHERE thread_id=?',(title,time.time(),tid));c.commit();return {'thread_id':tid,'title':title}
                if op=='delete':
                    cur=c.execute('DELETE FROM threads WHERE thread_id=?',(tid,));c.commit();return {'thread_id':tid,'deleted':cur.rowcount==1}
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
    ALLOWED_PROTOCOLS=('LPCL','AUTHORITY','CURRENTNESS','ASSIGNMENT','HEARTBEAT','EVIDENCE','VALIDATION','RECEIPT','RECOVERY','GITHUB','HUMAN','CONTROL')
    def __init__(self,broker,base='http://127.0.0.1:8766'):
        self.broker=broker;self.base=base.rstrip('/')
    def _get(self,path,timeout=8):
        req=urllib.request.Request(self.base+path,headers={'User-Agent':'LION-LPCL-PANEL/1'},method='GET')
        with urllib.request.urlopen(req,timeout=timeout) as res:return json.load(res)
    def _post(self,path,body,timeout=10):
        data=json.dumps(body,ensure_ascii=False).encode('utf-8');req=urllib.request.Request(self.base+path,data=data,headers={'Content-Type':'application/json','User-Agent':'LION-LPCL-PANEL/1'},method='POST')
        with urllib.request.urlopen(req,timeout=timeout) as res:return json.load(res)
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
        if kv['PROJECT']!='LION_EVOLUSION' or kv['MODE']!='AUTONOMOUS_EXECUTE' or kv['CONTROL_LANGUAGE']!='LPCL/1.1':raise ValueError('lpcl envelope')
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
        cur=self.broker.call('MAT04','github_branch',{'repository':'DonkeyJJLove/ai_platform','branch':'master'})['result']
        dg=hashlib.sha256(text.encode('utf-8')).hexdigest()
        spec={'mission_id':mid,'title':kv['MISSION_TITLE'][:180],'objective':kv['MISSION_OBJECTIVE'][:4000],'description':kv['MISSION_DESCRIPTION'][:8000],'lpcl_digest':dg,'lpcl_text':text,'source_head':cur['head'],'source_tree':cur['tree'],'logical_count':logical,'material_target':material,'phases':phases,'protocols':prot}
        return {'valid':True,'lpcl_digest':dg,'source_currentness':cur,'spec':spec,'parsed':{'run':kv.get('RUN'),'project':kv['PROJECT'],'mode':kv['MODE'],'control_language':kv['CONTROL_LANGUAGE'],'phase_count':len(phases)}}
    def __call__(self,op,args):
        args=args or {}
        if op=='recent':return self._get('/api/v3/missions/recent')
        if op=='saas_request':
            mid=args.get('mission_id');question=args.get('question')
            if not isinstance(mid,str) or not self.MID_RE.fullmatch(mid) or not isinstance(question,str) or not question.strip() or len(question)>8000:raise ValueError('saas request')
            return self._post('/api/v3/saas/request',{'mission_id':mid,'question':question})
        if op=='saas_status':
            mid=args.get('mission_id')
            if not isinstance(mid,str) or not self.MID_RE.fullmatch(mid):raise ValueError('mission_id')
            return self._get('/api/v3/saas/status?mission_id='+mid)
        if op=='saas_request_status':
            rid=args.get('request_id')
            if not isinstance(rid,str) or not self.MID_RE.fullmatch(rid):raise ValueError('saas request id')
            return self._get('/api/v3/saas/requests/'+rid)
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
            v=self.validate(args.get('lpcl_text'));return self._post('/api/v3/missions/register-lpcl',v['spec'])
        if op=='activate_lpcl':
            mid=args.get('mission_id');dg=args.get('lpcl_digest')
            if not isinstance(mid,str) or not self.MID_RE.fullmatch(mid) or not isinstance(dg,str) or len(dg)!=64:raise ValueError('activation')
            return self._post('/api/v3/missions/'+mid+'/activate',{'lpcl_digest':dg,'activation_event':'EXPLICIT_UI_ACTIVATION'})
        if op=='current_action':
            action=args.get('action');pod=args.get('pod_name')
            if action not in {'START','PAUSE','RESUME','VALIDATE','STOP','RESTART_ONE'}:raise ValueError('action')
            body={'action':action}
            if action=='RESTART_ONE':
                if not isinstance(pod,str) or len(pod)>180:raise ValueError('pod')
                body['pod_name']=pod
            return self._post('/api/v3/missions/current/actions',body,timeout=240)
        raise ValueError('control operation denied')

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
    p=argparse.ArgumentParser();p.add_argument('--repo',required=True);p.add_argument('--material-runtime-dir',required=True);p.add_argument('--rag');p.add_argument('--rag-sha');p.add_argument('--release');p.add_argument('--model',default='http://127.0.0.1:8772');p.add_argument('--model-sha',required=True);p.add_argument('--mission-control-url',default='http://127.0.0.1:8766');p.add_argument('--port',type=int,default=8780);p.add_argument('--thread-db');a=p.parse_args()
    if bool(a.rag)!=bool(a.rag_sha) or bool(a.rag)!=bool(a.release):raise SystemExit('rag, rag-sha and release must be supplied together')
    b=MaterialDroneBroker(a.material_runtime_dir);cur,gp,cp,sp,mission,web,mp=providers(b,a.model);thread_db=Path(a.thread_db).resolve() if a.thread_db else Path(a.material_runtime_dir).resolve().parent/'threads'/'lion-local-model.db';threads=ThreadStore(thread_db);control=LpclControlBridge(b,a.mission_control_url)
    g=Gateway(a.repo,a.rag,a.rag_sha,a.release,a.model,a.model_sha,mp,cur,gp,web=web,content_provider=cp,source_provider=sp,mission_provider=mission,control_provider=control,material_begin=b.begin,material_receipts=b.receipts,material_state=b.fleet_state,material_reconcile=b.aggregate,thread_provider=threads)
    canary_stop=threading.Event();threading.Thread(target=local_canary_loop,args=(control,mp,canary_stop,a.port,a.model),daemon=True).start()
    try: serve_gateway(g,a.port)
    finally: canary_stop.set()
if __name__=='__main__':main()
