#!/usr/bin/env python3
from __future__ import annotations
import argparse,hashlib,json,os,socket,sqlite3,threading,uuid
from datetime import datetime,timezone
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse,unquote
from mission_control_compat import compat_get, STATIC
try:
 from lion_mission_lifecycle_db import migrate as lifecycle_migrate, decorate_snapshot as lifecycle_decorate, sync_components as lifecycle_sync_components, create_audit as lifecycle_create_audit, create_design_revision as lifecycle_create_design_revision, create_action_receipt as lifecycle_create_action_receipt, rollback_plan as lifecycle_rollback_plan
except ImportError:
 from tools.lion_mission_lifecycle_db import migrate as lifecycle_migrate, decorate_snapshot as lifecycle_decorate, sync_components as lifecycle_sync_components, create_audit as lifecycle_create_audit, create_design_revision as lifecycle_create_design_revision, create_action_receipt as lifecycle_create_action_receipt, rollback_plan as lifecycle_rollback_plan

DB=Path('/var/lib/sentinelx/uploads/lion-mission-control-v3/mission-control-v3.db')
LEGACY_DB=Path('/var/lib/sentinelx/uploads/lion-mission-control/mission-control.db')
SOCKET='/run/lion-effect-admission.sock'
MISSION='LION-R4-PREFLIGHT-L12-M64-MISSION-CONTROL-V3'
HEAD='849db8f5ea6434f5647ee072cd4835fd2264e078'
TREE='fccec66a96e8d914dff8b835ccbbadd9dca0a608'
SPEC='c9f8d0b9c94e881636d33601f79da5b99e93e79461bf495fa8b20a2ecdfe178e'
NAMESPACE='lion-mission64-r4-preflight'
LOGICAL=(('LD01','MISSION_PLANNER',6),('LD02','AUTHORITY_CURRENTNESS',6),('LD03','REPOSITORY_CURRENTNESS',6),('LD04','LOCAL_MODEL_ROUTER',6),('LD05','SAAS_DELEGATION',5),('LD06','DETERMINISTIC_EXECUTION',5),('LD07','WEB_EVIDENCE',5),('LD08','MATERIAL_SCHEDULER',5),('LD09','SECURITY_FALSIFIER',5),('LD10','VALIDATION',5),('LD11','RECOVERY',5),('LD12','RECONCILIATION',5))
ACTIONS={'START':'MISSION64_START','PAUSE':'MISSION64_PAUSE','RESUME':'MISSION64_RESUME','RESTART_ONE':'MISSION64_RESTART_ONE','VALIDATE':'MISSION64_VALIDATE','STOP':'MISSION64_STOP'}
LOCK=threading.Lock();STOP_EVENT=threading.Event()

def now():return datetime.now(timezone.utc).isoformat().replace('+00:00','Z')
def connect():
 DB.parent.mkdir(parents=True,exist_ok=True);c=sqlite3.connect(DB,timeout=10);c.row_factory=sqlite3.Row;c.execute('PRAGMA journal_mode=WAL');c.execute('PRAGMA foreign_keys=ON');return c

def import_legacy(c):
 if not LEGACY_DB.is_file():return
 try:lc=sqlite3.connect('file:'+str(LEGACY_DB)+'?mode=ro',uri=True);rows=lc.execute('SELECT run_id,payload FROM runs').fetchall();lc.close()
 except Exception:return
 for run_id,raw in rows:
  try:p=json.loads(raw);mid='legacy::'+str(run_id);src=p.get('source') or {};metrics=p.get('metrics') or {};work=p.get('workload') or {};status=str(p.get('status') or 'UNKNOWN');mat=int(work.get('pods') or metrics.get('ready') or 0);ready=int(metrics.get('ready') or (mat if status=='PASS' else 0));t=now();spec_digest=hashlib.sha256(json.dumps(p,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest();c.execute('INSERT OR IGNORE INTO missions VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(mid,str(p.get('process_class') or run_id),'LEGACY_OBSERVATION:'+str(p.get('adapter_type') or 'UNKNOWN'),spec_digest,src.get('head'),src.get('tree'),p.get('namespace'),'RECORDED_'+status,str((p.get('evidence') or {}).get('class') or 'HISTORICAL'),0,mat,mat,ready,t,None,t,None,json.dumps(p,sort_keys=True,ensure_ascii=False)))
  except Exception:continue

def migrate():
 c=connect();c.executescript('''
 CREATE TABLE IF NOT EXISTS missions(mission_id TEXT PRIMARY KEY,title TEXT NOT NULL,adapter TEXT NOT NULL,spec_digest TEXT NOT NULL,source_head TEXT,source_tree TEXT,namespace TEXT,state TEXT NOT NULL,runtime_state TEXT,logical_count INTEGER NOT NULL,material_target INTEGER NOT NULL,materialized INTEGER NOT NULL DEFAULT 0,ready INTEGER NOT NULL DEFAULT 0,created_at TEXT NOT NULL,authorized_at TEXT,updated_at TEXT NOT NULL,last_error TEXT,spec_json TEXT NOT NULL);
 CREATE TABLE IF NOT EXISTS logical_drones(mission_id TEXT NOT NULL,logical_id TEXT NOT NULL,role TEXT NOT NULL,material_target INTEGER NOT NULL,materialized INTEGER NOT NULL DEFAULT 0,ready INTEGER NOT NULL DEFAULT 0,PRIMARY KEY(mission_id,logical_id));
 CREATE TABLE IF NOT EXISTS material_workers(mission_id TEXT NOT NULL,pod_name TEXT NOT NULL,pod_uid TEXT,logical_id TEXT,phase TEXT,ready INTEGER NOT NULL,restarts INTEGER NOT NULL,pod_ip TEXT,observed_at TEXT NOT NULL,PRIMARY KEY(mission_id,pod_name));
 CREATE TABLE IF NOT EXISTS commands(command_id TEXT PRIMARY KEY,mission_id TEXT NOT NULL,action TEXT NOT NULL,pod_name TEXT,requested_at TEXT NOT NULL,started_at TEXT,finished_at TEXT,status TEXT NOT NULL,request_id TEXT,result_json TEXT,receipt_json TEXT,error TEXT);
 CREATE TABLE IF NOT EXISTS mission_events(id INTEGER PRIMARY KEY AUTOINCREMENT,mission_id TEXT NOT NULL,observed_at TEXT NOT NULL,event_type TEXT NOT NULL,payload_json TEXT NOT NULL);
 CREATE TABLE IF NOT EXISTS mission_meta(key TEXT PRIMARY KEY,value TEXT NOT NULL,updated_at TEXT NOT NULL);
 ''')
 spec={'mission_id':MISSION,'spec_digest':SPEC,'source_head':HEAD,'source_tree':TREE,'namespace':NAMESPACE,'logical_drones':[{'id':i,'role':r,'replicas':n} for i,r,n in LOGICAL],'logical_count':12,'material_target':64,'authority':'EXPLICIT_USER_AUTHORIZED_MISSION'}
 t=now();c.execute('INSERT OR IGNORE INTO missions VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(MISSION,'R4 Preflight · 12 Logical / 64 Material','MISSION64_K3S',SPEC,HEAD,TREE,NAMESPACE,'AUTHORIZED','UNKNOWN',12,64,0,0,t,t,t,None,json.dumps(spec,sort_keys=True)))
 for i,r,n in LOGICAL:c.execute('INSERT OR IGNORE INTO logical_drones VALUES(?,?,?,?,?,?)',(MISSION,i,r,n,0,0))
 import_legacy(c)
 process_migrate(c)
 lifecycle_migrate(c,now,current_mission_id=MISSION,source_head=HEAD,source_tree=TREE)
 c.commit();c.close()

def broker(op,pod=None):
 req={'schema_version':'1.0.0','request_id':hashlib.sha256(os.urandom(32)).hexdigest(),'operation':op,'mission_id':MISSION,'source_head':HEAD,'source_tree':TREE,'spec_digest':SPEC}
 if op=='MISSION64_RESTART_ONE':req['pod_name']=pod
 s=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM);s.settimeout(240);s.connect(SOCKET);s.sendall(json.dumps(req,sort_keys=True,separators=(',',':')).encode()+b'\n');s.shutdown(socket.SHUT_WR);data=bytearray()
 while True:
  b=s.recv(65536)
  if not b:break
  data.extend(b)
  if len(data)>16*1024*1024:raise RuntimeError('broker response too large')
 s.close();v=json.loads(bytes(data).decode())
 if not isinstance(v,dict) or v.get('ok') is not True:raise RuntimeError('broker denied:'+str(v.get('error') if isinstance(v,dict) else 'malformed'))
 return v['result'],req['request_id']

def event(c,etype,payload):c.execute('INSERT INTO mission_events(mission_id,observed_at,event_type,payload_json) VALUES(?,?,?,?)',(MISSION,now(),etype,json.dumps(payload,sort_keys=True,ensure_ascii=False)))
def apply_runtime(c,r):
 state=r.get('state','UNKNOWN');mat=int(r.get('materialized',0) or 0);ready=int(r.get('ready',0) or 0);t=now();m=c.execute('SELECT state FROM missions WHERE mission_id=?',(MISSION,)).fetchone();cur=m['state'] if m else 'UNKNOWN'
 if state=='RUNNING':life='RUNNING'
 elif state=='PAUSED':life='PAUSED'
 elif state=='ABSENT' and cur in {'STOPPING','STOPPED'}:life='STOPPED'
 elif state=='K3S_NOT_RUNNING' and cur=='AUTHORIZED':life='AUTHORIZED'
 elif state=='CONVERGING' and cur in {'STARTING','RESUMING','RESTARTING','PAUSING'}:life=cur
 else:life=cur
 c.execute('UPDATE missions SET state=?,runtime_state=?,materialized=?,ready=?,updated_at=? WHERE mission_id=?',(life,state,mat,ready,t,MISSION));c.execute('DELETE FROM material_workers WHERE mission_id=?',(MISSION,));by={}
 for p in r.get('pods',[]):
  lid=(p.get('logical_drone') or '').upper();by.setdefault(lid,[0,0]);by[lid][0]+=1;by[lid][1]+=1 if p.get('ready') else 0;c.execute('INSERT INTO material_workers VALUES(?,?,?,?,?,?,?,?,?)',(MISSION,p.get('name'),p.get('uid'),lid,p.get('phase'),1 if p.get('ready') else 0,int(p.get('restarts',0) or 0),p.get('pod_ip'),t))
 for i,_,_ in LOGICAL:
  vals=by.get(i,[0,0]);c.execute('UPDATE logical_drones SET materialized=?,ready=? WHERE mission_id=? AND logical_id=?',(vals[0],vals[1],MISSION,i))

def observe_once():
 try:r,_=broker('MISSION64_READ')
 except Exception as e:
  c=connect();c.execute('UPDATE missions SET runtime_state=?,updated_at=?,last_error=? WHERE mission_id=?',('UNKNOWN',now(),type(e).__name__+':'+str(e)[:1000],MISSION));c.commit();c.close();return
 c=connect();apply_runtime(c,r);c.execute('UPDATE missions SET last_error=NULL WHERE mission_id=?',(MISSION,));c.commit();c.close()
def observer():
 while not STOP_EVENT.is_set():observe_once();STOP_EVENT.wait(5)

def command(action,pod=None):
 if action not in ACTIONS:raise ValueError('action denied')
 cid=uuid.uuid4().hex;c=connect();state=c.execute('SELECT state FROM missions WHERE mission_id=?',(MISSION,)).fetchone()['state'];allowed={'START':{'AUTHORIZED','STOPPED','FAILED'},'PAUSE':{'RUNNING'},'RESUME':{'PAUSED'},'RESTART_ONE':{'RUNNING'},'VALIDATE':{'RUNNING'},'STOP':{'RUNNING','PAUSED','FAILED','STARTING','CONVERGING'}}
 if state not in allowed[action]:c.close();raise ValueError('action denied from state '+state)
 if action=='RESTART_ONE' and (not isinstance(pod,str) or not c.execute('SELECT 1 FROM material_workers WHERE mission_id=? AND pod_name=?',(MISSION,pod)).fetchone()):c.close();raise ValueError('pod not in current mission')
 transitional={'START':'STARTING','PAUSE':'PAUSING','RESUME':'RESUMING','RESTART_ONE':'RESTARTING','VALIDATE':'VALIDATING','STOP':'STOPPING'}[action];t=now();c.execute('INSERT INTO commands(command_id,mission_id,action,pod_name,requested_at,started_at,status) VALUES(?,?,?,?,?,?,?)',(cid,MISSION,action,pod,t,t,'RUNNING'));c.execute('UPDATE missions SET state=?,updated_at=? WHERE mission_id=?',(transitional,t,MISSION));event(c,'COMMAND_ACCEPTED',{'command_id':cid,'action':action,'pod_name':pod});c.commit();c.close()
 try:
  result,rid=broker(ACTIONS[action],pod);receipt=result.get('control_receipt');runtime_result=(broker('MISSION64_READ')[0] if action=='VALIDATE' else result);c=connect();apply_runtime(c,runtime_result);final={'START':'RUNNING','PAUSE':'PAUSED','RESUME':'RUNNING','RESTART_ONE':'RUNNING','VALIDATE':'RUNNING','STOP':'STOPPED'}[action];c.execute('UPDATE missions SET state=?,updated_at=?,last_error=NULL WHERE mission_id=?',(final,now(),MISSION));c.execute('UPDATE commands SET finished_at=?,status=?,request_id=?,result_json=?,receipt_json=? WHERE command_id=?',(now(),'PASS',rid,json.dumps(result,sort_keys=True),json.dumps(receipt,sort_keys=True),cid));event(c,'COMMAND_PASS',{'command_id':cid,'action':action,'request_id':rid,'receipt_digest':(receipt or {}).get('receipt_digest')});c.commit();c.close();return {'command_id':cid,'status':'PASS','action':action,'result':result}
 except Exception as e:
  c=connect();c.execute('UPDATE missions SET state=?,updated_at=?,last_error=? WHERE mission_id=?',('FAILED',now(),type(e).__name__+':'+str(e)[:1000],MISSION));c.execute('UPDATE commands SET finished_at=?,status=?,error=? WHERE command_id=?',(now(),'FAIL',type(e).__name__+':'+str(e)[:2000],cid));event(c,'COMMAND_FAIL',{'command_id':cid,'action':action,'error':str(e)[:1000]});c.commit();c.close();raise

def legacy_count():
 if not LEGACY_DB.is_file():return 0
 try:
  c=sqlite3.connect('file:'+str(LEGACY_DB)+'?mode=ro',uri=True);n=c.execute('SELECT COUNT(*) FROM runs').fetchone()[0];c.close();return int(n)
 except Exception:return 0

def mission_summaries():
 c=connect();rows=[]
 for r in c.execute('SELECT mission_id,title,adapter,state,runtime_state,logical_count,material_target,materialized,ready,updated_at FROM missions ORDER BY CASE WHEN mission_id=? THEN 0 ELSE 1 END, updated_at DESC',(MISSION,)):
  d=dict(r);d['controllable']=d['mission_id']==MISSION and d['adapter']=='MISSION64_K3S';rows.append(d)
 c.close();return rows

def register_observation(x):
 expected={'mission_id','title','spec_digest','source_head','source_tree','logical_count','material_target'}
 if type(x) is not dict or set(x)!=expected:raise ValueError('registration schema')
 mid=x['mission_id'];title=x['title']
 if not isinstance(mid,str) or not __import__('re').fullmatch(r'[A-Za-z0-9][A-Za-z0-9._:-]{0,127}',mid) or mid==MISSION:raise ValueError('mission_id')
 if not isinstance(title,str) or not 1<=len(title)<=160:raise ValueError('title')
 for key,n in [('spec_digest',64),('source_head',40),('source_tree',40)]:
  if not isinstance(x[key],str) or not __import__('re').fullmatch(r'[0-9a-f]{'+str(n)+'}',x[key]):raise ValueError(key)
 for key in ('logical_count','material_target'):
  if type(x[key]) is not int or not 0<=x[key]<=4096:raise ValueError(key)
 t=now();spec={**x,'adapter':'OBSERVATION_ONLY','registered_via':'MISSION_CONTROL_V3'};c=connect();c.execute('INSERT INTO missions VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(mid,title,'OBSERVATION_ONLY',x['spec_digest'],x['source_head'],x['source_tree'],None,'REGISTERED','UNKNOWN',x['logical_count'],x['material_target'],0,0,t,None,t,None,json.dumps(spec,sort_keys=True)));event(c,'MISSION_REGISTERED',{'mission_id':mid,'adapter':'OBSERVATION_ONLY'});c.commit();c.close();return {'mission_id':mid,'state':'REGISTERED','control_authority':'NONE'}

def snapshot():
 c=connect();m=dict(c.execute('SELECT * FROM missions WHERE mission_id=?',(MISSION,)).fetchone());m['spec']=json.loads(m.pop('spec_json'));m['logical']=[dict(x) for x in c.execute('SELECT * FROM logical_drones WHERE mission_id=? ORDER BY logical_id',(MISSION,))];m['workers']=[dict(x) for x in c.execute('SELECT * FROM material_workers WHERE mission_id=? ORDER BY logical_id,pod_name',(MISSION,))];m['commands']=[dict(x) for x in c.execute('SELECT command_id,action,pod_name,requested_at,finished_at,status,request_id,error FROM commands WHERE mission_id=? ORDER BY requested_at DESC LIMIT 30',(MISSION,))];m['events']=[dict(x) for x in c.execute('SELECT observed_at,event_type,payload_json FROM mission_events WHERE mission_id=? ORDER BY id DESC LIMIT 30',(MISSION,))];c.close();m['legacy_recorded_runs']=legacy_count();m['control_authority']='BOUNDED_MISSION_CONTROL';m['registry']=mission_summaries();return m


# ---- LPCL mission process extension v1 -----------------------------------
PROTOCOLS=('LPCL','AUTHORITY','CURRENTNESS','ASSIGNMENT','HEARTBEAT','EVIDENCE','VALIDATION','RECEIPT','RECOVERY','GITHUB','HUMAN','CONTROL')
PHASE_STATES=('PENDING','READY','RUNNING','WAITING','BLOCKED','PASS','FAIL','SKIPPED','COMPLETE','CANCELLED')
LPCL_REBIND_SOURCE='EPOCH3-CLOSURE-DOCS-FEDERATION-GITHUB-R1'
LPCL_REBIND_ADAPTER='LPCL_REBOUND_EPOCH3_64'
LPCL_REBIND_DISTRIBUTION=(6,6,6,6,5,5,5,5,5,5,5,5)


def _lpcl_pairs(text):
    import re
    lines=str(text or '').replace('\r\n','\n').replace('\r','\n').split('\n');out={};i=0
    while i<len(lines):
      m=re.match(r'^([A-Z][A-Z0-9_]*)\s*=\s*(.*)$',lines[i].strip())
      if not m:i+=1;continue
      key,val=m.group(1),m.group(2).strip();i+=1
      if not val:
       buf=[]
       while i<len(lines):
        row=lines[i].strip()
        if re.match(r'^([A-Z][A-Z0-9_]*)\s*=\s*(.*)$',row):break
        if row and not row.startswith('#'):buf.append(row)
        i+=1
       val=' '.join(buf).strip()
      out[key]=val
    return out


def bind_lpcl_execution(mid):
    c=connect()
    try:
      m=c.execute('SELECT mission_id,state,spec_digest,source_head,source_tree,logical_count,material_target,adapter FROM missions WHERE mission_id=?',(mid,)).fetchone()
      ps=c.execute('SELECT lpcl_text,authority_state,current_phase FROM mission_process_specs WHERE mission_id=?',(mid,)).fetchone()
      if not m or not ps:return None
      if m['adapter']==LPCL_REBIND_ADAPTER:return process_snapshot(mid)
      if m['state']!='AUTHORIZED' or ps['authority_state']!='EXPLICIT_USER_ACTIVATION':return None
      if m['logical_count']!=12 or m['material_target']!=64:raise ValueError('lpcl execution adapter cardinality')
      kv=_lpcl_pairs(ps['lpcl_text'])
      if kv.get('CONTINUE_EXISTING_EPOCH3_MISSION')!='TRUE' or kv.get('CREATE_PARALLEL_COMPETING_EPOCH3_MISSION')!='FALSE':raise ValueError('lpcl continuation contract')
      reuse=kv.get('REUSE_EXISTING_HEALTHY_MATERIAL_FLEET','')
      if 'ALLOWED' not in reuse:raise ValueError('lpcl material rebind not allowed')
      src=c.execute('SELECT state,runtime_state,materialized,ready,source_head,source_tree FROM missions WHERE mission_id=?',(LPCL_REBIND_SOURCE,)).fetchone()
      if not src or src['state'] not in {'RUNNING','AUTHORIZED'} or src['materialized']!=64 or src['ready']!=64:raise ValueError('lpcl source fleet not healthy')
      workers=c.execute('SELECT pod_name,pod_uid,logical_id,phase,ready,restarts,pod_ip,observed_at FROM material_workers WHERE mission_id=? ORDER BY logical_id,pod_name',(LPCL_REBIND_SOURCE,)).fetchall()
      if len(workers)!=64 or len({r['pod_uid'] for r in workers if r['pod_uid']})!=64 or any(int(r['ready'])!=1 for r in workers):raise ValueError('lpcl source fleet identity')
      roles=[]
      for i,target in enumerate(LPCL_REBIND_DISTRIBUTION,1):
       lid=f'LD{i:02d}';role=kv.get(lid)
       if not role:raise ValueError('lpcl logical role '+lid)
       roles.append((lid,role,target))
      by={lid:[0,0] for lid,_,_ in roles}
      for r in workers:
       lid=str(r['logical_id']).upper()
       if lid not in by:raise ValueError('lpcl worker logical id')
       by[lid][0]+=1;by[lid][1]+=int(r['ready'])
      for lid,_,target in roles:
       if by[lid] != [target,target]:raise ValueError('lpcl worker distribution '+lid)
      first=c.execute('SELECT phase_id FROM mission_phases WHERE mission_id=? ORDER BY ordinal LIMIT 1',(mid,)).fetchone()
      if not first:raise ValueError('lpcl first phase missing')
      t=now();c.execute('DELETE FROM logical_drones WHERE mission_id=?',(mid,));c.execute('DELETE FROM material_workers WHERE mission_id=?',(mid,))
      for lid,role,target in roles:c.execute('INSERT INTO logical_drones VALUES(?,?,?,?,?,?)',(mid,lid,role,target,target,target))
      for r in workers:c.execute('INSERT INTO material_workers VALUES(?,?,?,?,?,?,?,?,?)',(mid,r['pod_name'],r['pod_uid'],str(r['logical_id']).upper(),r['phase'],r['ready'],r['restarts'],r['pod_ip'],t))
      c.execute('UPDATE missions SET adapter=?,state=?,runtime_state=?,materialized=64,ready=64,updated_at=?,last_error=NULL WHERE mission_id=?',(LPCL_REBIND_ADAPTER,'RUNNING','REBOUND_EXISTING_HEALTHY_FLEET',t,mid))
      c.execute('UPDATE mission_process_specs SET current_phase=?,updated_at=? WHERE mission_id=?',(first['phase_id'],t,mid))
      c.execute('UPDATE mission_phases SET status=?,progress=?,detail=?,started_at=COALESCE(started_at,?),updated_at=? WHERE mission_id=? AND phase_id=?',('RUNNING',0.0,'64/64 healthy material workers rebound from '+LPCL_REBIND_SOURCE+'; currentness reacquisition started',t,t,mid,first['phase_id']))
      c.execute('UPDATE missions SET state=?,runtime_state=?,updated_at=? WHERE mission_id=?',('SUPERSEDED','REBOUND_TO:'+mid,t,LPCL_REBIND_SOURCE))
      c.execute('UPDATE mission_process_specs SET current_phase=NULL,authority_state=?,updated_at=? WHERE mission_id=?',('SUPERSEDED_BY_EXACT_LPCL',t,LPCL_REBIND_SOURCE))
      uid_digest=_payload_digest({'uids':sorted(r['pod_uid'] for r in workers)})
      _process_message(c,mid,'ASSIGNMENT','MISSION_CONTROL','MATERIAL_FLEET',first['phase_id'],{'event':'EXISTING_HEALTHY_FLEET_REBOUND','source_mission_id':LPCL_REBIND_SOURCE,'worker_count':64,'unique_uid_count':64,'worker_uid_digest':uid_digest,'binding_class':'CONTROL_PLANE_REBIND','pod_role_environment_rewritten':False,'authority_effect':'MISSION_SCOPED_CONTROL_BINDING'},'INTERNAL')
      _process_message(c,mid,'CURRENTNESS','MISSION_CONTROL','LD02',first['phase_id'],{'event':'CURRENTNESS_REACQUIRE_STARTED','source_head':m['source_head'],'source_tree':m['source_tree'],'material_ready':64,'material_target':64},'INTERNAL')
      _process_message(c,mid,'RECEIPT','MISSION_CONTROL','OPERATOR',first['phase_id'],{'event':'LPCL_EXECUTION_ADAPTER_BOUND','adapter':LPCL_REBIND_ADAPTER,'source_mission_id':LPCL_REBIND_SOURCE,'lpcl_digest':m['spec_digest'],'worker_uid_digest':uid_digest},'OUT')
      c.commit()
    finally:c.close()
    return process_snapshot(mid)


def reconcile_lpcl_execution_bindings():
    c=connect()
    try:rows=[r['mission_id'] for r in c.execute("SELECT mission_id FROM missions WHERE adapter='LPCL_MISSION' AND state='AUTHORIZED' ORDER BY updated_at DESC").fetchall()]
    finally:c.close()
    for mid in rows:
      try:bind_lpcl_execution(mid)
      except Exception:
       c=connect();c.execute('UPDATE missions SET last_error=?,updated_at=? WHERE mission_id=?',('LPCL_EXECUTION_BIND:'+__import__('traceback').format_exc(limit=1)[-900:],now(),mid));c.commit();c.close()

def process_migrate(c):
    c.executescript('''
    CREATE TABLE IF NOT EXISTS mission_process_specs(
      mission_id TEXT PRIMARY KEY,title TEXT NOT NULL,objective TEXT NOT NULL,description TEXT NOT NULL,
      lpcl_digest TEXT,lpcl_text TEXT,protocols_json TEXT NOT NULL,authority_state TEXT NOT NULL,
      current_phase TEXT,progress REAL NOT NULL DEFAULT 0,created_at TEXT NOT NULL,updated_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS mission_phases(
      mission_id TEXT NOT NULL,phase_id TEXT NOT NULL,ordinal INTEGER NOT NULL,title TEXT NOT NULL,
      status TEXT NOT NULL,progress REAL NOT NULL DEFAULT 0,detail TEXT,started_at TEXT,finished_at TEXT,updated_at TEXT NOT NULL,
      PRIMARY KEY(mission_id,phase_id)
    );
    CREATE TABLE IF NOT EXISTS protocol_messages(
      id INTEGER PRIMARY KEY AUTOINCREMENT,mission_id TEXT NOT NULL,observed_at TEXT NOT NULL,protocol TEXT NOT NULL,
      from_id TEXT NOT NULL,to_id TEXT NOT NULL,phase TEXT,direction TEXT NOT NULL,payload_json TEXT NOT NULL,payload_digest TEXT NOT NULL
    );
    ''')
    t=now()
    objective='Validate the integrated LION control plane: 12 logical roles, 64 material Kubernetes Pods, lifecycle control, execution validation, receipts and Mission Control observability.'
    desc='R4 preflight mission used to prove bounded Mission Control lifecycle and material execution before the next evolution phase.'
    c.execute('INSERT OR IGNORE INTO mission_process_specs VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',
      (MISSION,'R4 Preflight · 12 Logical / 64 Material',objective,desc,None,None,json.dumps(PROTOCOLS), 'AUTHORIZED','LIVE',100.0,t,t))
    c.execute('INSERT OR IGNORE INTO mission_phases VALUES(?,?,?,?,?,?,?,?,?,?)',
      (MISSION,'LIVE',1,'Live controlled material fleet','RUNNING',100.0,'64/64 material Pods under bounded Mission Control',t,None,t))
    c.execute('INSERT OR IGNORE INTO mission_meta(key,value,updated_at) VALUES(?,?,?)',('focus_mission_id',MISSION,t))
    for r in c.execute('SELECT command_id,action,pod_name,requested_at,finished_at,status,request_id,error FROM commands WHERE mission_id=? ORDER BY requested_at',(MISSION,)).fetchall():
      payload=dict(r);dg=hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(',',':'),default=str).encode()).hexdigest()
      exists=c.execute('SELECT 1 FROM protocol_messages WHERE mission_id=? AND payload_digest=?',(MISSION,dg)).fetchone()
      if not exists:
       c.execute('INSERT INTO protocol_messages(mission_id,observed_at,protocol,from_id,to_id,phase,direction,payload_json,payload_digest) VALUES(?,?,?,?,?,?,?,?,?)',
        (MISSION,r['finished_at'] or r['requested_at'],'CONTROL','MISSION_CONTROL','MATERIAL_FLEET',r['action'],'OUT',json.dumps(payload,sort_keys=True,default=str),dg))

def _hex(v,n):
    return isinstance(v,str) and len(v)==n and all(ch in '0123456789abcdef' for ch in v)

def _safe_id(v,maxlen=128):
    import re
    return isinstance(v,str) and 1<=len(v)<=maxlen and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._:-]*',v) is not None

def _payload_digest(v):
    return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False,default=str).encode()).hexdigest()

def _process_message(c,mid,protocol,from_id,to_id,phase,payload,direction='INTERNAL'):
    if protocol not in PROTOCOLS:raise ValueError('protocol')
    if not _safe_id(from_id,96) or not _safe_id(to_id,96):raise ValueError('message endpoint')
    if phase is not None and (not isinstance(phase,str) or len(phase)>96):raise ValueError('phase')
    if type(payload) is not dict or len(json.dumps(payload,ensure_ascii=False))>16384:raise ValueError('payload')
    dg=_payload_digest(payload);ts=now()
    c.execute('INSERT INTO protocol_messages(mission_id,observed_at,protocol,from_id,to_id,phase,direction,payload_json,payload_digest) VALUES(?,?,?,?,?,?,?,?,?)',
      (mid,ts,protocol,from_id,to_id,phase,direction,json.dumps(payload,sort_keys=True,ensure_ascii=False),dg))
    return {'observed_at':ts,'protocol':protocol,'payload_digest':dg}

def register_lpcl_mission(x):
    required={'mission_id','title','objective','description','lpcl_digest','lpcl_text','source_head','source_tree','logical_count','material_target','phases','protocols'}
    if type(x) is not dict or set(x)!=required:raise ValueError('lpcl registration schema')
    mid=x['mission_id']
    if not _safe_id(mid) or mid==MISSION:raise ValueError('mission_id')
    if not isinstance(x['title'],str) or not 1<=len(x['title'])<=180:raise ValueError('title')
    if not isinstance(x['objective'],str) or not 1<=len(x['objective'])<=4000:raise ValueError('objective')
    if not isinstance(x['description'],str) or len(x['description'])>8000:raise ValueError('description')
    if not _hex(x['lpcl_digest'],64) or not _hex(x['source_head'],40) or not _hex(x['source_tree'],40):raise ValueError('identity')
    if not isinstance(x['lpcl_text'],str) or not 1<=len(x['lpcl_text'])<=200000:raise ValueError('lpcl_text')
    if type(x['logical_count']) is not int or not 1<=x['logical_count']<=512:raise ValueError('logical_count')
    if type(x['material_target']) is not int or not 0<=x['material_target']<=4096:raise ValueError('material_target')
    if type(x['protocols']) is not list or not x['protocols'] or any(p not in PROTOCOLS for p in x['protocols']):raise ValueError('protocols')
    if type(x['phases']) is not list or not 1<=len(x['phases'])<=64:raise ValueError('phases')
    phase_rows=[];seen=set()
    for i,row in enumerate(x['phases'],1):
      if type(row) is not dict or set(row)!={'id','title'} or not _safe_id(row['id'],64) or row['id'] in seen or not isinstance(row['title'],str) or not 1<=len(row['title'])<=180:raise ValueError('phase row')
      seen.add(row['id']);phase_rows.append((row['id'],row['title']))
    if hashlib.sha256(x['lpcl_text'].encode('utf-8')).hexdigest()!=x['lpcl_digest']:raise ValueError('lpcl digest mismatch')
    t=now();c=connect();existing=c.execute('SELECT spec_digest,state FROM missions WHERE mission_id=?',(mid,)).fetchone()
    if existing:
      if existing['spec_digest']==x['lpcl_digest']:
       c.close();return {'idempotent':True,'mission':process_snapshot(mid)}
      c.close();raise ValueError('mission_id already bound')
    spec={'mission_id':mid,'title':x['title'],'objective':x['objective'],'description':x['description'],'lpcl_digest':x['lpcl_digest'],'protocols':x['protocols'],'phases':x['phases'],'logical_count':x['logical_count'],'material_target':x['material_target'],'source_head':x['source_head'],'source_tree':x['source_tree']}
    c.execute('INSERT INTO missions VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(mid,x['title'],'LPCL_MISSION',x['lpcl_digest'],x['source_head'],x['source_tree'],None,'REGISTERED','NOT_STARTED',x['logical_count'],x['material_target'],0,0,t,None,t,None,json.dumps(spec,sort_keys=True,ensure_ascii=False)))
    c.execute('INSERT INTO mission_process_specs VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(mid,x['title'],x['objective'],x['description'],x['lpcl_digest'],x['lpcl_text'],json.dumps(x['protocols']), 'NONE',None,0.0,t,t))
    for i,(pid,title) in enumerate(phase_rows,1):c.execute('INSERT INTO mission_phases VALUES(?,?,?,?,?,?,?,?,?,?)',(mid,pid,i,title,'PENDING',0.0,None,None,None,t))
    _process_message(c,mid,'LPCL','LPCL_PANEL','MISSION_CONTROL',None,{'event':'MISSION_REGISTERED','lpcl_digest':x['lpcl_digest'],'phase_count':len(phase_rows)},'IN')
    c.execute('INSERT INTO mission_meta(key,value,updated_at) VALUES(?,?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value,updated_at=excluded.updated_at',('focus_mission_id',mid,t))
    c.commit();c.close();return {'idempotent':False,'mission':process_snapshot(mid)}

def activate_lpcl_mission(mid,x):
    if type(x) is not dict or set(x)!={'lpcl_digest','activation_event'} or x.get('activation_event')!='EXPLICIT_UI_ACTIVATION' or not _hex(x.get('lpcl_digest'),64):raise ValueError('activation schema')
    c=connect();m=c.execute('SELECT state,spec_digest FROM missions WHERE mission_id=?',(mid,)).fetchone()
    if not m: c.close();raise ValueError('mission not found')
    if m['spec_digest']!=x['lpcl_digest']:c.close();raise ValueError('activation digest drift')
    if m['state'] not in {'REGISTERED','AUTHORIZED'}:c.close();raise ValueError('activation state')
    t=now();c.execute('UPDATE missions SET state=?,authorized_at=?,updated_at=? WHERE mission_id=?',('AUTHORIZED',t,t,mid));c.execute('UPDATE mission_process_specs SET authority_state=?,updated_at=? WHERE mission_id=?',('EXPLICIT_USER_ACTIVATION',t,mid))
    _process_message(c,mid,'AUTHORITY','OPERATOR','MISSION_CONTROL',None,{'event':'MISSION_AUTHORIZED','lpcl_digest':x['lpcl_digest']},'IN')
    c.execute('INSERT INTO mission_meta(key,value,updated_at) VALUES(?,?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value,updated_at=excluded.updated_at',('focus_mission_id',mid,t))
    c.commit();c.close()
    try:return bind_lpcl_execution(mid) or process_snapshot(mid)
    except Exception as e:
      c=connect();c.execute('UPDATE missions SET last_error=?,updated_at=? WHERE mission_id=?',('LPCL_EXECUTION_BIND:'+type(e).__name__+':'+str(e)[:800],now(),mid));c.commit();c.close();return process_snapshot(mid)

def update_lpcl_phase(mid,x):
    required={'phase_id','status','progress','protocol','from_id','to_id','detail','payload'}
    if type(x) is not dict or set(x)!=required:raise ValueError('phase update schema')
    if x['status'] not in PHASE_STATES or type(x['progress']) not in (int,float) or not 0<=float(x['progress'])<=100 or x['protocol'] not in PROTOCOLS:raise ValueError('phase update')
    c=connect();row=c.execute('SELECT status,started_at FROM mission_phases WHERE mission_id=? AND phase_id=?',(mid,x['phase_id'])).fetchone()
    if not row:c.close();raise ValueError('phase not found')
    t=now();started=row['started_at'];finished=None
    if x['status']=='RUNNING' and not started:started=t
    if x['status'] in {'PASS','FAIL','SKIPPED','COMPLETE','CANCELLED'}:finished=t
    c.execute('UPDATE mission_phases SET status=?,progress=?,detail=?,started_at=?,finished_at=?,updated_at=? WHERE mission_id=? AND phase_id=?',(x['status'],float(x['progress']),str(x['detail'])[:4000],started,finished,t,mid,x['phase_id']))
    rows=c.execute('SELECT status,progress,phase_id FROM mission_phases WHERE mission_id=? ORDER BY ordinal',(mid,)).fetchall();overall=sum(float(r['progress']) for r in rows)/max(1,len(rows));current=next((r['phase_id'] for r in rows if r['status'] in {'RUNNING','WAITING','BLOCKED'}),None)
    states={r['status'] for r in rows};life='RUNNING' if any(s in states for s in ('RUNNING','WAITING','BLOCKED')) else ('COMPLETE' if states and states.issubset({'PASS','COMPLETE','SKIPPED'}) else 'AUTHORIZED')
    c.execute('UPDATE mission_process_specs SET current_phase=?,progress=?,updated_at=? WHERE mission_id=?',(current,overall,t,mid));c.execute('UPDATE missions SET state=?,updated_at=? WHERE mission_id=?',(life,t,mid))
    _process_message(c,mid,x['protocol'],x['from_id'],x['to_id'],x['phase_id'],x['payload'],'INTERNAL')
    c.commit();c.close();return process_snapshot(mid)

def post_protocol_message(mid,x):
    required={'protocol','from_id','to_id','phase','payload'}
    if type(x) is not dict or set(x)!=required:raise ValueError('protocol schema')
    c=connect()
    if not c.execute('SELECT 1 FROM missions WHERE mission_id=?',(mid,)).fetchone():c.close();raise ValueError('mission not found')
    out=_process_message(c,mid,x['protocol'],x['from_id'],x['to_id'],x['phase'],x['payload'],'INTERNAL');c.commit();c.close();return out

def _send_broker_request(req):
    s=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM);s.settimeout(240);s.connect(SOCKET);s.sendall(json.dumps(req,sort_keys=True,separators=(',',':')).encode()+b'\n');s.shutdown(socket.SHUT_WR);data=bytearray()
    while True:
      b=s.recv(65536)
      if not b:break
      data.extend(b)
      if len(data)>16*1024*1024:raise RuntimeError('broker response too large')
    s.close();value=json.loads(bytes(data).decode())
    if not isinstance(value,dict) or value.get('ok') is not True:raise RuntimeError('broker denied:'+str(value.get('error') if isinstance(value,dict) else 'malformed'))
    return value['result'],req['request_id']


def epoch3_broker(operation,pod=None):
    c=connect();row=c.execute('SELECT mission_id,spec_digest,source_head,source_tree FROM missions WHERE mission_id=?',(LPCL_REBIND_SOURCE,)).fetchone();c.close()
    if not row:raise ValueError('epoch3 source mission missing')
    req={'schema_version':'1.0.0','request_id':hashlib.sha256(os.urandom(32)).hexdigest(),'operation':operation,'mission_id':LPCL_REBIND_SOURCE,'source_head':row['source_head'],'source_tree':row['source_tree'],'spec_digest':row['spec_digest']}
    if pod is not None:req['pod_name']=pod
    return _send_broker_request(req)


def apply_runtime_for(c,mid,r):
    state=str(r.get('state') or 'UNKNOWN');mat=int(r.get('materialized',0) or 0);ready=int(r.get('ready',0) or 0);t=now();row=c.execute('SELECT state FROM missions WHERE mission_id=?',(mid,)).fetchone();cur=row['state'] if row else 'UNKNOWN'
    if state=='RUNNING':life='RUNNING'
    elif state=='PAUSED':life='PAUSED'
    elif state in {'ABSENT','K3S_NOT_RUNNING'}:life='STOPPED' if cur not in {'AUTHORIZED'} else cur
    elif state=='CONVERGING':life='CONVERGING'
    else:life=cur
    c.execute('UPDATE missions SET state=?,runtime_state=?,materialized=?,ready=?,updated_at=? WHERE mission_id=?',(life,state,mat,ready,t,mid));c.execute('DELETE FROM material_workers WHERE mission_id=?',(mid,));by={}
    for pod in r.get('pods',[]) or []:
      lid=str(pod.get('logical_drone') or '').upper();by.setdefault(lid,[0,0]);by[lid][0]+=1;by[lid][1]+=1 if pod.get('ready') else 0
      c.execute('INSERT INTO material_workers VALUES(?,?,?,?,?,?,?,?,?)',(mid,pod.get('name'),pod.get('uid'),lid,pod.get('phase'),1 if pod.get('ready') else 0,int(pod.get('restarts',0) or 0),pod.get('pod_ip'),t))
    for logical in c.execute('SELECT logical_id FROM logical_drones WHERE mission_id=?',(mid,)).fetchall():
      vals=by.get(str(logical['logical_id']).upper(),[0,0]);c.execute('UPDATE logical_drones SET materialized=?,ready=? WHERE mission_id=? AND logical_id=?',(vals[0],vals[1],mid,logical['logical_id']))
    lifecycle_sync_components(c,mid,now)


def refresh_legacy(mid):
    if not mid.startswith('legacy::'):raise ValueError('not legacy mission')
    run_id=mid[len('legacy::'):]
    if not LEGACY_DB.is_file():raise ValueError('legacy source unavailable')
    lc=sqlite3.connect('file:'+str(LEGACY_DB)+'?mode=ro',uri=True);row=lc.execute('SELECT payload FROM runs WHERE run_id=?',(run_id,)).fetchone();lc.close()
    if not row:raise ValueError('legacy source record unavailable')
    payload=json.loads(row[0]);src=payload.get('source') or {};metrics=payload.get('metrics') or {};work=payload.get('workload') or {};status=str(payload.get('status') or 'UNKNOWN');mat=int(work.get('pods') or metrics.get('ready') or 0);ready=int(metrics.get('ready') or (mat if status=='PASS' else 0));runtime=str((payload.get('evidence') or {}).get('class') or 'HISTORICAL_IMPORTED_EVIDENCE');t=now();dg=hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest();c=connect();c.execute('UPDATE missions SET state=?,runtime_state=?,material_target=?,materialized=?,ready=?,source_head=?,source_tree=?,spec_digest=?,spec_json=?,updated_at=?,last_error=NULL WHERE mission_id=?',('RECORDED_'+status,runtime,mat,mat,ready,src.get('head'),src.get('tree'),dg,json.dumps(payload,sort_keys=True,ensure_ascii=False),t,mid));c.commit();c.close();return {'mission_id':mid,'source':'generic_mission_control','recorded_status':status,'materialized':mat,'ready':ready,'effect':'READ_ONLY_REINDEX'}


def mission_action(mid,x):
    if type(x) is not dict or 'action' not in x or not isinstance(x['action'],str):raise ValueError('action schema')
    action=x['action'].upper();allowed={'REFRESH','RESTART','START_COMPONENT','ADD_COMPONENT','REDESIGN','AUDIT','ROLLBACK'}
    if action not in allowed:raise ValueError('action denied')
    request={k:v for k,v in x.items() if k!='action'}
    c=connect();row=c.execute('SELECT mission_id,adapter,state FROM missions WHERE mission_id=?',(mid,)).fetchone();c.close()
    if not row:raise ValueError('mission not found')
    effect='NONE';status='PASS';result=None
    try:
      if action=='REFRESH':
        if mid==MISSION:
          observe_once();result={'mission_id':mid,'source':'MISSION64_READ','effect':'READ_ONLY_CURRENTNESS'}
        elif mid==LPCL_REBIND_SOURCE:
          runtime,rid=epoch3_broker('EPOCH3_M64_READ');c=connect();apply_runtime_for(c,mid,runtime);c.commit();c.close();result={'mission_id':mid,'source':'EPOCH3_M64_READ','request_id':rid,'runtime':{k:runtime.get(k) for k in ('state','materialized','ready','unique_uid_count')},'effect':'READ_ONLY_CURRENTNESS'}
        elif mid.startswith('legacy::'):result=refresh_legacy(mid)
        else:result={'mission_id':mid,'effect':'CONTROL_DB_READBACK','state':'NO_MATERIAL_CURRENTNESS_ADAPTER'}
      elif action=='AUDIT':
        c=connect();result=lifecycle_create_audit(c,mid,now);c.close()
      elif action=='RESTART':
        if mid==MISSION:
          effect='BOUNDED_MATERIAL';with_lock=LOCK
          with with_lock:
            first=command('STOP');second=command('START')
          result={'mission_id':mid,'restart_class':'STOP_THEN_START','stop':first,'start':second}
        elif mid==LPCL_REBIND_SOURCE:
          effect='BOUNDED_MATERIAL'
          stop,sid=epoch3_broker('EPOCH3_M64_STOP');start,stid=epoch3_broker('EPOCH3_M64_START');c=connect();apply_runtime_for(c,mid,start);c.commit();c.close();result={'mission_id':mid,'restart_class':'EPOCH3_STOP_THEN_START','stop_request_id':sid,'start_request_id':stid,'runtime':{k:start.get(k) for k in ('state','materialized','ready','unique_uid_count')}}
        else:
          c=connect();result=lifecycle_create_design_revision(c,mid,'RESTART',request or {'reason':'operator requested restart/replay'},now,state='AWAITING_EXACT_LPCL_ACTIVATION');c.close()
      elif action=='START_COMPONENT':
        component=str(request.get('component_id') or '').strip()
        if not component:raise ValueError('component_id required')
        c=connect();exists=c.execute('SELECT 1 FROM mission_components WHERE mission_id=? AND component_id=?',(mid,component)).fetchone()
        if not exists:c.close();raise ValueError('component not found')
        result=lifecycle_create_design_revision(c,mid,'START_COMPONENT',{'component_id':component,'reason':request.get('reason') or 'bounded component start requested'},now,state='BLOCKED_EXACT_COMPONENT_ADAPTER_REQUIRED');c.close()
      elif action=='ADD_COMPONENT':
        component=request.get('component')
        if type(component) is not dict or not str(component.get('component_id') or '').strip():raise ValueError('component object with component_id required')
        c=connect();result=lifecycle_create_design_revision(c,mid,'ADD_COMPONENT',request,now);c.close()
      elif action=='REDESIGN':
        if not request:raise ValueError('redesign request required')
        c=connect();result=lifecycle_create_design_revision(c,mid,'REDESIGN',request,now);c.close()
      elif action=='ROLLBACK':
        rollback_id=str(request.get('rollback_id') or '').strip()
        if not rollback_id:raise ValueError('rollback_id required')
        c=connect();result=lifecycle_rollback_plan(c,mid,rollback_id,now);c.close()
      c=connect();receipt=lifecycle_create_action_receipt(c,mid,action,effect,status,request,result,now);c.close();return {'mission_id':mid,'action':action,'status':status,'effect_class':effect,'result':result,'receipt':receipt}
    except Exception as e:
      try:
        c=connect();receipt=lifecycle_create_action_receipt(c,mid,action,effect,'FAIL',request,{'error':type(e).__name__+':'+str(e)[:1000]},now);c.close()
      except Exception:receipt=None
      raise ValueError(type(e).__name__+':'+str(e)+((' receipt='+str(receipt.get('receipt_id'))) if receipt else ''))


def process_snapshot(mid):
    c=connect();m=c.execute('SELECT * FROM missions WHERE mission_id=?',(mid,)).fetchone()
    if not m:c.close();raise ValueError('mission not found')
    d=dict(m);s=c.execute('SELECT * FROM mission_process_specs WHERE mission_id=?',(mid,)).fetchone();d['process']=dict(s) if s else None
    if d['process']:
      try:d['process']['protocols']=json.loads(d['process'].pop('protocols_json'))
      except Exception:d['process']['protocols']=[]
      d['process'].pop('lpcl_text',None)
    d['phases']=[dict(r) for r in c.execute('SELECT * FROM mission_phases WHERE mission_id=? ORDER BY ordinal',(mid,))]
    d['logical']=[dict(r) for r in c.execute('SELECT * FROM logical_drones WHERE mission_id=? ORDER BY logical_id',(mid,))]
    d['workers']=[dict(r) for r in c.execute('SELECT * FROM material_workers WHERE mission_id=? ORDER BY logical_id,pod_name',(mid,))]
    d['commands']=[dict(r) for r in c.execute('SELECT command_id,action,pod_name,requested_at,finished_at,status,request_id,error FROM commands WHERE mission_id=? ORDER BY requested_at DESC LIMIT 40',(mid,))]
    msgs=[]
    for r in c.execute('SELECT id,observed_at,protocol,from_id,to_id,phase,direction,payload_json,payload_digest FROM protocol_messages WHERE mission_id=? ORDER BY id DESC LIMIT 120',(mid,)):
      q=dict(r)
      try:q['payload']=json.loads(q.pop('payload_json'))
      except Exception:q['payload']={}
      msgs.append(q)
    d['protocol_messages']=msgs
    if mid==MISSION:d['control_authority']='BOUNDED_MISSION_CONTROL'
    elif d.get('adapter')==LPCL_REBIND_ADAPTER:d['control_authority']='BOUNDED_LPCL_EXECUTION_ADAPTER'
    elif mid==LPCL_REBIND_SOURCE:d['control_authority']='BOUNDED_EPOCH3_MATERIAL_ADAPTER'
    else:d['control_authority']='ACTIVATED_NO_EFFECT_ADAPTER' if d['state'] in {'AUTHORIZED','RUNNING'} else 'NONE'
    lifecycle_sync_components(c,mid,now)
    d=lifecycle_decorate(c,d,current_mission_id=MISSION,rebound_adapter=LPCL_REBIND_ADAPTER)
    c.commit();c.close();return d

def focus_mission_id():
    c=connect();r=c.execute("SELECT value FROM mission_meta WHERE key='focus_mission_id'").fetchone();c.close();return r['value'] if r else MISSION

def recent_process_missions():
    c=connect();rows=[]
    for r in c.execute('SELECT m.mission_id,m.title,m.adapter,m.state,m.runtime_state,m.logical_count,m.material_target,m.materialized,m.ready,m.updated_at,p.objective,p.current_phase,p.progress,p.authority_state FROM missions m LEFT JOIN mission_process_specs p ON p.mission_id=m.mission_id ORDER BY m.updated_at DESC LIMIT 30'):
      d=dict(r);d['controllable']=d['mission_id']==MISSION and d['adapter']=='MISSION64_K3S';rows.append(d)
    c.close();return rows
# ---- end LPCL mission process extension v1 -------------------------------

UI=r'''<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>LION Mission Control</title><style>:root{color-scheme:dark;--b:#080d12;--p:#111820;--l:#293744;--t:#edf5fa;--m:#91a7b7;--g:#55d99d;--y:#e5bd68;--r:#ff7580}*{box-sizing:border-box}body{margin:0;background:var(--b);color:var(--t);font:14px/1.45 Inter,Segoe UI,system-ui}.app{max-width:1500px;margin:auto;padding:18px}h1{margin:0;font-size:24px}.sub{color:var(--m)}.top{display:flex;justify-content:space-between;gap:12px}.pill,.card,.panel{border:1px solid var(--l);background:var(--p);border-radius:10px}.pill{padding:8px 12px}.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:8px;margin:14px 0}.card{padding:10px}.k{font-size:10px;color:#7fa7bb}.v{font-size:18px;font-weight:700}.grid{display:grid;grid-template-columns:1.35fr .65fr;gap:10px}.panel{padding:14px;margin-bottom:10px}.logical{display:grid;grid-template-columns:repeat(3,1fr);gap:8px}.ld{border:1px solid var(--l);border-radius:8px;padding:9px}.bar{height:7px;background:#22303a;border-radius:9px;overflow:hidden}.bar i{display:block;height:100%;background:var(--g)}button{background:#173743;color:white;border:1px solid #3c6575;border-radius:7px;padding:8px 12px;margin:2px}button.danger{border-color:#7a3d45;background:#3a2025}.workers{max-height:440px;overflow:auto}table{width:100%;border-collapse:collapse;font-size:12px}th,td{padding:6px;border-bottom:1px solid #202c35;text-align:left}.ok{color:var(--g)}.warn{color:var(--y)}.bad{color:var(--r)}.cmd{font-family:Consolas,monospace;font-size:11px}.legacy{color:var(--m)}@media(max-width:950px){.grid{grid-template-columns:1fr}.logical{grid-template-columns:1fr 1fr}}</style></head><body><div class="app"><div class="top"><div><h1>LION MISSION CONTROL</h1><div class="sub">Mission registry · bounded control · live material execution · receipts</div></div><div id="authority" class="pill">loading</div></div><div id="cards" class="cards"></div><div class="grid"><div><div class="panel"><h2 id="title"></h2><div id="meta" class="sub"></div><div id="actions"></div><h3>Logical control plane · 12 drones</h3><div id="logical" class="logical"></div></div><div class="panel"><h3>Material plane · 64 Kubernetes Pods</h3><div class="workers"><table><thead><tr><th>Pod</th><th>Logical</th><th>Phase</th><th>Ready</th><th>Restarts</th><th>UID</th><th></th></tr></thead><tbody id="workers"></tbody></table></div></div></div><div><div class="panel"><h3>Mission registry</h3><div id="registry"></div></div><div class="panel"><h3>Command / receipt ledger</h3><div id="commands"></div></div><div class="panel"><h3>Mission events</h3><div id="events"></div></div><div class="panel legacy"><b>Legacy recorded runs:</b> <span id="legacy"></span><br>Legacy history remains evidence, not live state.</div></div></div></div><script>const $=x=>document.getElementById(x);let S=null;function esc(x){return String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}async function get(){let r=await fetch('/api/v3/missions/current',{cache:'no-store'});S=await r.json();render()}function btn(a,label,cls=''){return '<button class="'+cls+'" onclick="act(\''+a+'\')">'+label+'</button>'}async function act(a,pod){if(!confirm(a+(pod?' '+pod:'')))return;let r=await fetch('/api/v3/missions/current/actions',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action:a,...(pod?{pod_name:pod}:{})})});let x=await r.json();if(!r.ok)alert(x.error||'control failed');await get()}function render(){let s=S;$('authority').innerHTML='CONTROL: <b>'+esc(s.control_authority)+'</b>';$('title').textContent=s.title;$('meta').textContent=s.mission_id+' · state '+s.state+' · runtime '+s.runtime_state+' · spec '+s.spec_digest.slice(0,16);let cs=[['STATE',s.state],['RUNTIME',s.runtime_state],['LOGICAL',s.logical_count],['MATERIAL',s.materialized+'/'+s.material_target],['READY',s.ready+'/'+s.material_target],['SOURCE',s.source_head.slice(0,8)],['LEGACY',s.legacy_recorded_runs]];$('cards').innerHTML=cs.map(x=>'<div class="card"><div class="k">'+x[0]+'</div><div class="v">'+esc(x[1])+'</div></div>').join('');let a='';if(['AUTHORIZED','STOPPED','FAILED'].includes(s.state))a+=btn('START','Start mission');if(s.state==='RUNNING'){a+=btn('PAUSE','Pause');a+=btn('VALIDATE','Validate fleet');}if(s.state==='PAUSED')a+=btn('RESUME','Resume');if(['RUNNING','PAUSED','FAILED','CONVERGING'].includes(s.state))a+=btn('STOP','Stop','danger');$('actions').innerHTML=a;$('logical').innerHTML=s.logical.map(x=>'<div class="ld"><b>'+x.logical_id+' · '+esc(x.role)+'</b><div>'+x.ready+'/'+x.material_target+' ready</div><div class="bar"><i style="width:'+(100*x.ready/Math.max(1,x.material_target))+'%"></i></div></div>').join('');$('workers').innerHTML=s.workers.map(x=>'<tr><td>'+esc(x.pod_name)+'</td><td>'+esc(x.logical_id)+'</td><td>'+esc(x.phase)+'</td><td class="'+(x.ready?'ok':'warn')+'">'+(x.ready?'YES':'NO')+'</td><td>'+x.restarts+'</td><td>'+esc((x.pod_uid||'').slice(0,12))+'</td><td>'+(s.state==='RUNNING'?'<button onclick="act(\'RESTART_ONE\',\''+esc(x.pod_name)+'\')">restart</button>':'')+'</td></tr>').join('');$('registry').innerHTML=(s.registry||[]).map(x=>'<div class="cmd">'+(x.controllable?'● ':'○ ')+esc(x.mission_id)+' · '+esc(x.state)+' · '+esc(x.adapter)+'</div>').join('');$('commands').innerHTML=s.commands.map(x=>'<div class="cmd">'+esc(x.requested_at)+' '+esc(x.action)+' <b class="'+(x.status==='PASS'?'ok':x.status==='FAIL'?'bad':'warn')+'">'+x.status+'</b>'+(x.pod_name?' '+esc(x.pod_name):'')+'</div>').join('')||'none';$('events').innerHTML=s.events.map(x=>'<div class="cmd">'+esc(x.observed_at)+' '+esc(x.event_type)+'</div>').join('')||'none';$('legacy').textContent=s.legacy_recorded_runs}get();setInterval(get,3000)</script></body></html>'''

class H(BaseHTTPRequestHandler):
 def log_message(self,*a):return
 def json(self,x,status=200):b=json.dumps(x,ensure_ascii=False).encode();self.send_response(status);self.send_header('Content-Type','application/json; charset=utf-8');self.send_header('Content-Length',str(len(b)));self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(b)
 def send_content(self,body,content_type='application/octet-stream',status=200):
  if isinstance(body,str):body=body.encode('utf-8')
  self.send_response(status);self.send_header('Content-Type',content_type);self.send_header('Content-Length',str(len(body)));self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(body)
 def do_GET(self):
  path=unquote(urlparse(self.path).path)
  static_map={'/':('index.html','text/html; charset=utf-8'),'/index.html':('index.html','text/html; charset=utf-8'),'/app.css':('app.css','text/css; charset=utf-8'),'/app.js':('app.js','text/javascript; charset=utf-8'),'/passive.js':('passive.js','text/javascript; charset=utf-8'),'/control-v3.js':('control-v3.js','text/javascript; charset=utf-8')}
  if path in static_map:
   name,ctype=static_map[path];target=STATIC/name
   if not target.is_file():return self.json({'error':'static-not-found'},404)
   return self.send_content(target.read_bytes(),ctype)
  if path=='/health':return self.json({'status':'ok','mission_id':MISSION,'control':'BOUNDED','authority_effect':'MISSION_SCOPED','ui':'HISTORICAL_OBSERVER_PLUS_V3_CONTROL','collector':'MULTI_SQLITE_READ_MODEL'})
  current=snapshot()
  compat=compat_get(path,current)
  if compat is not None:
   code,ctype,body=compat
   if isinstance(body,(dict,list)):return self.json(body,code)
   return self.send_content(body,ctype,code)
  if path in {'/api/v3/missions/current','/api/v3/missions/'+MISSION}:return self.json(current)
  if path=='/api/v3/missions':return self.json({'missions':mission_summaries(),'process_missions':recent_process_missions(),'legacy_recorded_runs':legacy_count()})
  if path=='/api/v3/missions/recent':return self.json({'missions':recent_process_missions(),'focus_mission_id':focus_mission_id()})
  if path.startswith('/api/v3/missions/') and path.endswith('/process'):
   mid=path[len('/api/v3/missions/'):-len('/process')].strip('/')
   try:return self.json(process_snapshot(mid))
   except ValueError as e:return self.json({'error':str(e)},404)
  if path.startswith('/api/v3/missions/') and path.endswith('/messages'):
   mid=path[len('/api/v3/missions/'):-len('/messages')].strip('/')
   try:return self.json({'mission_id':mid,'messages':process_snapshot(mid)['protocol_messages']})
   except ValueError as e:return self.json({'error':str(e)},404)
  return self.json({'error':'not found'},404)
 def do_POST(self):
  path=unquote(urlparse(self.path).path)
  if path.startswith('/api/v3/missions/') and path.endswith('/actions') and path!='/api/v3/missions/current/actions':
   try:
    mid=path[len('/api/v3/missions/'):-len('/actions')].strip('/');n=int(self.headers.get('Content-Length','0'))
    if n<2 or n>65536 or 'application/json' not in self.headers.get('Content-Type',''):raise ValueError('request')
    x=json.loads(self.rfile.read(n));return self.json(mission_action(mid,x),200)
   except ValueError as e:return self.json({'error':str(e)},409)
   except Exception as e:return self.json({'error':type(e).__name__+':'+str(e)},500)
  if path=='/api/v3/missions/register-lpcl':
   try:
    n=int(self.headers.get('Content-Length','0'));
    if n<2 or n>220000:raise ValueError('body size')
    x=json.loads(self.rfile.read(n));return self.json(register_lpcl_mission(x),201)
   except Exception as e:return self.json({'error':type(e).__name__+':'+str(e)},400)
  if path.startswith('/api/v3/missions/') and path.endswith('/activate'):
   try:
    mid=path[len('/api/v3/missions/'):-len('/activate')].strip('/');n=int(self.headers.get('Content-Length','0'));x=json.loads(self.rfile.read(n));return self.json(activate_lpcl_mission(mid,x))
   except Exception as e:return self.json({'error':type(e).__name__+':'+str(e)},409)
  if path.startswith('/api/v3/missions/') and path.endswith('/phase'):
   try:
    mid=path[len('/api/v3/missions/'):-len('/phase')].strip('/');n=int(self.headers.get('Content-Length','0'));x=json.loads(self.rfile.read(n));return self.json(update_lpcl_phase(mid,x))
   except Exception as e:return self.json({'error':type(e).__name__+':'+str(e)},409)
  if path.startswith('/api/v3/missions/') and path.endswith('/messages'):
   try:
    mid=path[len('/api/v3/missions/'):-len('/messages')].strip('/');n=int(self.headers.get('Content-Length','0'));x=json.loads(self.rfile.read(n));return self.json(post_protocol_message(mid,x),201)
   except Exception as e:return self.json({'error':type(e).__name__+':'+str(e)},400)
  if path=='/api/v3/missions/register':
   try:
    n=int(self.headers.get('Content-Length','0'));x=json.loads(self.rfile.read(n));return self.json(register_observation(x),201)
   except Exception as e:return self.json({'error':type(e).__name__+':'+str(e)},400)
  if path not in {'/api/v3/missions/current/actions','/api/v3/missions/'+MISSION+'/actions'}:return self.json({'error':'not found'},404)
  try:
   n=int(self.headers.get('Content-Length','0'))
   if n<2 or n>4096 or 'application/json' not in self.headers.get('Content-Type',''):raise ValueError('request')
   x=json.loads(self.rfile.read(n));allowed={'action','pod_name'}
   if type(x) is not dict or not set(x).issubset(allowed) or x.get('action') not in ACTIONS:raise ValueError('action schema')
   if x.get('action')!='RESTART_ONE' and 'pod_name' in x:raise ValueError('pod_name denied')
   with LOCK:out=command(x['action'],x.get('pod_name'))
   return self.json(out)
  except ValueError as e:return self.json({'error':str(e)},409)
  except Exception as e:return self.json({'error':type(e).__name__+':'+str(e)},500)
 def do_PUT(self):self.json({'error':'method denied'},405)
 def do_PATCH(self):self.json({'error':'method denied'},405)
 def do_DELETE(self):self.json({'error':'method denied'},405)

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--host',default='127.0.0.1');ap.add_argument('--port',type=int,default=8767);ap.add_argument('--listen-state',default='/run/lion-mission-control/listen.json');ap.add_argument('--legacy-listen-state',default='/run/lion-vkt-mission-control/listen.json');a=ap.parse_args();migrate();reconcile_lpcl_execution_bindings();observe_once();threading.Thread(target=observer,daemon=True).start();srv=ThreadingHTTPServer((a.host,a.port),H);loc={'status':'LISTENING','host':a.host,'port':a.port,'pid':os.getpid(),'generation':'MISSION_CONTROL_V3','mission_id':MISSION};
 for lp in (a.listen_state,a.legacy_listen_state):
  q=Path(lp);q.parent.mkdir(parents=True,exist_ok=True);tmp=q.with_name(q.name+'.tmp-'+uuid.uuid4().hex[:8]);tmp.write_text(json.dumps(loc,sort_keys=True),encoding='utf-8');os.replace(tmp,q)
 print(json.dumps(loc),flush=True)
 try:srv.serve_forever()
 finally:STOP_EVENT.set();srv.server_close()
if __name__=='__main__':main()
