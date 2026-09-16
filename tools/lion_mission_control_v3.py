#!/usr/bin/env python3
from __future__ import annotations
import argparse,hashlib,json,os,socket,sqlite3,threading,uuid,subprocess,sys,tempfile,shutil
import time, urllib.request, urllib.error
from concurrent.futures import Future
from copy import deepcopy
from datetime import datetime,timezone
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse,unquote,parse_qs
from cyber_lion.mission_control.runtime_projection import normalize_snapshot, validate_registration, SCHEMA_VERSION as RUNTIME_SCHEMA_VERSION
from cyber_lion.mission_control.phase_control import apply_phase_action, fence_phase_action
from cyber_lion.contracts.phase_execution_contract import (
 PhaseExecutionContract, PhaseExecutionContractError, compile_panel_phase_contracts,
 preflight_execution_contracts, migrated_explicit_contract, SCHEMA_ID as PHASE_CONTRACT_SCHEMA,
 COMPILER_VERSION as PHASE_CONTRACT_COMPILER_VERSION,
)
from cyber_lion.contracts.mission_contract_profiles import migrated_contract_for, GENERIC_ADAPTER_REPAIR_MISSION, SAAS_AUTOMATIC_MEDIATOR_MISSION, FIREFOX_PROJECT_MEDIATOR_SUCCESSOR_MISSION
from cyber_lion.mission_control.mission_reconciliation import evaluate_completion_predicates
from cyber_lion.mission_control import control_plane_reconnaissance as control_recon
from cyber_lion.contracts.action_ir import CanonicalActionIR
from mission_control_compat import compat_get, STATIC
try:
 from lion_mission_lifecycle_db import migrate as lifecycle_migrate, decorate_snapshot as lifecycle_decorate, sync_components as lifecycle_sync_components, create_audit as lifecycle_create_audit, create_design_revision as lifecycle_create_design_revision, create_action_receipt as lifecycle_create_action_receipt, rollback_plan as lifecycle_rollback_plan, mission_delete_preview, delete_mission_records, mission_lifecycle_classification, normalize_epoch3_terminal_lifecycle
except ImportError:
 from tools.lion_mission_lifecycle_db import migrate as lifecycle_migrate, decorate_snapshot as lifecycle_decorate, sync_components as lifecycle_sync_components, create_audit as lifecycle_create_audit, create_design_revision as lifecycle_create_design_revision, create_action_receipt as lifecycle_create_action_receipt, rollback_plan as lifecycle_rollback_plan, mission_delete_preview, delete_mission_records, mission_lifecycle_classification, normalize_epoch3_terminal_lifecycle
try:
 from lion_saas_session_bridge import migrate as saas_migrate, create_request as saas_create, pending_request as saas_pending, request_status as saas_request_status, cancel_request as saas_cancel, bridge_status as saas_bridge_status, respond as saas_respond, TRANSPORT as SAAS_TRANSPORT, ATTESTATION_CLASS as SAAS_ATTESTATION_CLASS
except ImportError:
 from tools.lion_saas_session_bridge import migrate as saas_migrate, create_request as saas_create, pending_request as saas_pending, request_status as saas_request_status, cancel_request as saas_cancel, bridge_status as saas_bridge_status, respond as saas_respond, TRANSPORT as SAAS_TRANSPORT, ATTESTATION_CLASS as SAAS_ATTESTATION_CLASS
try:
 from cyber_lion.mission_control.execution_driver import migrate as driver_migrate, ensure_driver, activate as driver_activate, heartbeat as driver_heartbeat, begin_attempt as driver_begin_attempt, finish_attempt as driver_finish_attempt, observe_gate as driver_observe_gate, snapshot as driver_snapshot, transition as driver_transition, reconcile_complete as driver_reconcile_complete, adaptive_worker_plan as driver_adaptive_worker_plan, wait_for_execution_binding as driver_wait_for_execution_binding
except ImportError:
 from execution_driver import migrate as driver_migrate, ensure_driver, activate as driver_activate, heartbeat as driver_heartbeat, begin_attempt as driver_begin_attempt, finish_attempt as driver_finish_attempt, observe_gate as driver_observe_gate, snapshot as driver_snapshot, transition as driver_transition, reconcile_complete as driver_reconcile_complete, adaptive_worker_plan as driver_adaptive_worker_plan, wait_for_execution_binding as driver_wait_for_execution_binding
try:
 from cyber_lion.mission_control.dual_result_join import create_dual as dual_create, link_saas_request as dual_link_saas, record_response as dual_record_response, join_result as dual_join_result, LOCAL_PROVIDER as DUAL_LOCAL_PROVIDER, SAAS_PROVIDER as DUAL_SAAS_PROVIDER
except ImportError:
 from dual_result_join import create_dual as dual_create, link_saas_request as dual_link_saas, record_response as dual_record_response, join_result as dual_join_result, LOCAL_PROVIDER as DUAL_LOCAL_PROVIDER, SAAS_PROVIDER as DUAL_SAAS_PROVIDER
try:
 from cyber_lion.mission_control import global_scheduler as global_sched
except ImportError:
 import global_scheduler as global_sched

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

FIREFOX_RELAY_IPC=DB.parent/'firefox-mediator-ipc'
FIREFOX_RELAY_STATE=DB.parent/'firefox-mediator-relay'
FIREFOX_RELAY_KEY=DB.parent/'saas-mediator.key'

def _start_firefox_broker_relay(port):
    relay=Path(__file__).with_name('lion_firefox_broker_relay.py')
    if not relay.is_file():
        return None
    FIREFOX_RELAY_IPC.mkdir(parents=True,exist_ok=True)
    for name in ('inbox','outbox','journal','receipts','archive'):
        q=FIREFOX_RELAY_IPC/name;q.mkdir(parents=True,exist_ok=True);os.chmod(q,0o777)
    os.chmod(FIREFOX_RELAY_IPC,0o777)
    FIREFOX_RELAY_STATE.mkdir(parents=True,exist_ok=True)
    return subprocess.Popen([sys.executable,str(relay),'--broker',f'http://127.0.0.1:{int(port)}','--key-file',str(FIREFOX_RELAY_KEY),'--state-dir',str(FIREFOX_RELAY_STATE),'--ipc-dir',str(FIREFOX_RELAY_IPC)],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,close_fds=True)


try:
 import lion_saas_broker as saas_broker
except ModuleNotFoundError:
 from tools import lion_saas_broker as saas_broker


def saas_broker_api(method,path,payload=None):
 c=connect()
 try:
  prefix='/api/v3/saas-broker';tail=path[len(prefix):];x=payload or {}
  if method=='GET':
   if tail in {'/status','/session'}:return saas_broker.bridge_status(c,None,now)
   if tail=='/pending':return saas_broker.broker_pending(c,now)
   if tail.startswith('/requests/'):return saas_broker.request_status(c,tail[len('/requests/'):],now)
  if method=='POST' and tail=='/requests':
   if type(x) is not dict or not {'scope_type','question','authority_effect'}<=set(x) or set(x)-{'scope_type','scope_id','thread_id','mission_id','question','authority_effect'}:raise ValueError('broker request schema')
   return saas_broker.create_request(c,x.get('mission_id'),x['question'],now,scope_type=x['scope_type'],scope_id=x.get('scope_id'),thread_id=x.get('thread_id'),authority_effect=x['authority_effect'])
  if method=='POST' and tail=='/mediator/heartbeat':
   return saas_broker.record_mediator_heartbeat(c,x,now)
  if method=='POST' and tail=='/session/attest':
   if set(x)!={'request_id','receipt_digest'}:raise ValueError('attestation receipt schema')
   row=saas_broker.request_status(c,x['request_id'],now);status=saas_broker.bridge_status(c,None,now);binding=status.get('binding')
   if row['receipt_digest']!=x['receipt_digest'] or not binding or binding['binding_id']!=row['binding_id']:raise ValueError('fresh roundtrip receipt required')
   return {'binding':binding,'authority_effect':'NONE'}
  if method=='POST' and tail.startswith('/requests/'):
   parts=tail.split('/')
   if len(parts)!=4:raise ValueError('broker path')
   rid,action=parts[2:]
   if action=='claim':
    if x:raise ValueError('claim schema')
    return saas_broker.claim(c,rid,now)
   if action=='cancel':
    if x:raise ValueError('cancel schema')
    return saas_broker.cancel_request(c,rid,now)
   if action=='respond':
    if set(x)!={'response_token','claim_generation','answer','model_identity','transport','attestation_class'}:raise ValueError('response schema')
    row=c.execute('SELECT claim_generation FROM saas_handoff_requests WHERE request_id=?',(rid,)).fetchone()
    if row is None or type(x['claim_generation']) is not int or row[0]!=x['claim_generation']:raise ValueError('stale claim')
    return saas_broker.respond(c,rid,x['response_token'],x['answer'],now,model_identity=x['model_identity'],transport=x['transport'],attestation_class=x['attestation_class'],claim_generation=x['claim_generation'])
  raise ValueError('broker endpoint')
 finally:c.close()


def mediator_authorized(headers):
 # The key is available only to the local mediator/host connector, never to UI GETs.
 path=DB.parent/'saas-mediator.key'
 try:key=path.read_text(encoding='utf-8').strip()
 except OSError:return False
 return len(key)>=64 and __import__('secrets').compare_digest(headers.get('X-LION-Mediator-Key',''),key)


def now():return datetime.now(timezone.utc).isoformat().replace('+00:00','Z')
def connect():
 DB.parent.mkdir(parents=True,exist_ok=True);c=sqlite3.connect(DB,timeout=10);c.row_factory=sqlite3.Row;c.execute('PRAGMA journal_mode=WAL');c.execute('PRAGMA foreign_keys=ON');return c

def import_legacy(c):
 if c.execute("SELECT 1 FROM mission_meta WHERE key='runtime_mission_reset' AND value='1'").fetchone():return
 if not LEGACY_DB.is_file():return
 try:lc=sqlite3.connect('file:'+str(LEGACY_DB)+'?mode=ro',uri=True);rows=lc.execute('SELECT run_id,payload FROM runs').fetchall();lc.close()
 except Exception:return
 for run_id,raw in rows:
  if c.execute("SELECT 1 FROM mission_meta WHERE key=?",("deleted_mission:legacy::"+str(run_id),)).fetchone():continue
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
 if not c.execute("SELECT 1 FROM mission_meta WHERE key='runtime_mission_reset' AND value='1'").fetchone():
  spec={'mission_id':MISSION,'spec_digest':SPEC,'source_head':HEAD,'source_tree':TREE,'namespace':NAMESPACE,'logical_drones':[{'id':i,'role':r,'replicas':n} for i,r,n in LOGICAL],'logical_count':12,'material_target':64,'authority':'EXPLICIT_USER_AUTHORIZED_MISSION'}
  t=now();c.execute('INSERT OR IGNORE INTO missions VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(MISSION,'R4 Preflight · 12 Logical / 64 Material','MISSION64_K3S',SPEC,HEAD,TREE,NAMESPACE,'AUTHORIZED','UNKNOWN',12,64,0,0,t,t,t,None,json.dumps(spec,sort_keys=True)))
  for i,r,n in LOGICAL:c.execute('INSERT OR IGNORE INTO logical_drones VALUES(?,?,?,?,?,?)',(MISSION,i,r,n,0,0))
  import_legacy(c)
 process_migrate(c)
 lifecycle_migrate(c,now,current_mission_id=MISSION,source_head=HEAD,source_tree=TREE)
 saas_migrate(c,now,source_head=HEAD,source_tree=TREE)
 driver_migrate(c,now,source_head=HEAD,source_tree=TREE)
 global_sched.migrate(c,now)
 # Capture the pre-capability execution preflight before startup reconciliation
 # recomputes it against the current capability registry.
 control_recon.capture_pre_recon_baselines(c,now)
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
 if not c.execute('SELECT 1 FROM missions WHERE mission_id=?',(MISSION,)).fetchone():return
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
 c=connect()
 try:present=c.execute('SELECT 1 FROM missions WHERE mission_id=?',(MISSION,)).fetchone()
 finally:c.close()
 if not present:return
 try:r,_=broker('MISSION64_READ')
 except Exception as e:
  c=connect();c.execute('UPDATE missions SET runtime_state=?,updated_at=?,last_error=? WHERE mission_id=?',('UNKNOWN',now(),type(e).__name__+':'+str(e)[:1000],MISSION));c.commit();c.close();return
 c=connect();apply_runtime(c,r);c.execute('UPDATE missions SET last_error=NULL WHERE mission_id=?',(MISSION,));c.commit();c.close()
def observer():
 while not STOP_EVENT.is_set():observe_once();STOP_EVENT.wait(5)

def command(action,pod=None):
 if action not in ACTIONS:raise ValueError('action denied')
 cid=uuid.uuid4().hex;c=connect();row=c.execute('SELECT state FROM missions WHERE mission_id=?',(MISSION,)).fetchone()
 if row is None:c.close();raise ValueError('no active mission')
 state=row['state'];allowed={'START':{'AUTHORIZED','STOPPED','FAILED'},'PAUSE':{'RUNNING'},'RESUME':{'PAUSED'},'RESTART_ONE':{'RUNNING'},'VALIDATE':{'RUNNING'},'STOP':{'RUNNING','PAUSED','FAILED','STARTING','CONVERGING'}}
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
 c=connect();row=c.execute('SELECT * FROM missions WHERE mission_id=?',(MISSION,)).fetchone()
 if row is None:
  c.close();return {'mission_id':None,'state':'NO_ACTIVE_MISSIONS','runtime_state':'NOT_STARTED','logical':[],'workers':[],'commands':[],'events':[],'registry':mission_summaries(),'material_target':0,'materialized':0,'ready':0,'logical_count':0,'legacy_recorded_runs':0,'control_authority':'NONE'}
 m=dict(row);m['spec']=json.loads(m.pop('spec_json'));m['logical']=[dict(x) for x in c.execute('SELECT * FROM logical_drones WHERE mission_id=? ORDER BY logical_id',(MISSION,))];m['workers']=[dict(x) for x in c.execute('SELECT * FROM material_workers WHERE mission_id=? ORDER BY logical_id,pod_name',(MISSION,))];m['commands']=[dict(x) for x in c.execute('SELECT command_id,action,pod_name,requested_at,finished_at,status,request_id,error FROM commands WHERE mission_id=? ORDER BY requested_at DESC LIMIT 30',(MISSION,))];m['events']=[dict(x) for x in c.execute('SELECT observed_at,event_type,payload_json FROM mission_events WHERE mission_id=? ORDER BY id DESC LIMIT 30',(MISSION,))];c.close();m['legacy_recorded_runs']=legacy_count();m['control_authority']='BOUNDED_MISSION_CONTROL';m['registry']=mission_summaries();return m


# ---- LPCL mission process extension v1 -----------------------------------
PROTOCOLS=('LPCL','AUTHORITY','CURRENTNESS','ASSIGNMENT','HEARTBEAT','EVIDENCE','VALIDATION','RECEIPT','RECOVERY','GITHUB','HUMAN','CONTROL','LIFECYCLE','HISTORY','LINEAGE','TRANSPORT','BROKER','MEDIATOR','THREAD')
PHASE_STATES=('PENDING','READY','RUNNING','WAITING','BLOCKED','PASS','FAIL','SKIPPED','COMPLETE','CANCELLED')
EPOCH3_LIFECYCLE_TASK='LION-EPOCH3-MISSION-LIFECYCLE-NORMALIZATION-LEGACY-HISTORY-AND-EPOCH4-SCOPE-EXTRACTION-R2'
EPOCH3_LIFECYCLE_TASK_DIGEST='67a90c3826fa3f4f45bcad54685f15d2a53da3d09cd01bf2434a83718c6f094c'
EPOCH3_LIFECYCLE_TARGET_1='LION-EPOCH3-FULL-CONTROL-PLANE-PANEL-AND-AUTONOMOUS-RUN-DISPATCHER-128L64M-R1'
EPOCH3_LIFECYCLE_TARGET_1_DIGEST='d974b7562bfae99c7a061c1e38494ef3208e79d088630ac52b46ce8b53de39c0'
EPOCH3_LIFECYCLE_TARGET_2='EPOCH3-GLOBAL-UPGRADE-AUTHORITY-SYNC-EVERYWHERE-R1'
EPOCH3_LIFECYCLE_TARGET_2_DIGEST='cfe4ddd9f24588a4a91d06a2a36eecbc17acf6cc87c690570949fabdb3e4fc8e'
EPOCH3_LIFECYCLE_SUCCESSOR='LION-CONTROL-PLANE-PANEL-BROKER-REPAIR-SUCCESSOR-R1'
LPCL_REBIND_SOURCE='EPOCH3-CLOSURE-DOCS-FEDERATION-GITHUB-R1'
EPOCH3_MATERIAL_CARRIER_ID=LPCL_REBIND_SOURCE
EPOCH3_MATERIAL_CARRIER_SPEC_DIGEST='be0c4204b0aeffa5db61019128f70b092db5d62ed4c4e6936b41d430a1b67951'
LPCL_REBIND_ADAPTER='LPCL_REBOUND_EPOCH3_64'
LPCL_GENERIC_ADAPTER='LPCL_GENERIC_128L64M'
PROCESS_CONTRACT_TARGET_MISSION=GENERIC_ADAPTER_REPAIR_MISSION
PROCESS_CAPABILITY_REGISTRY={
 'REPOSITORY_AND_RUNTIME_RECONCILIATION':(
  {'capability_id':'GENERIC_EXECUTION_BINDER_RECONCILIATION','executor_id':'MISSION_CONTROL_PROCESS_CONTRACT_RECONCILER','effect_ceiling':'NONE','mode':'READ_ONLY_VERIFY'},
 ),
 'MISSION_RUNTIME_RECONCILIATION':(
  {'capability_id':'GENERIC_MISSION_CONTRACT_RECONCILIATION','executor_id':'MISSION_CONTROL_PROCESS_CONTRACT_RECONCILER','effect_ceiling':'NONE','mode':'READ_ONLY_VERIFY'},
 ),
 'CONTROL_PLANE_RECONNAISSANCE':(
  {'capability_id':'CONTROL_PLANE_RECONNAISSANCE_V1','executor_id':'MISSION_CONTROL_CONTROL_PLANE_RECONCILER','effect_ceiling':'NONE','mode':'READ_ONLY_RECON'},
 ),
 'REPOSITORY_CANDIDATE_PREPARE':(
  {'capability_id':'GENERIC_MISSION_CONTRACT_RECONCILIATION','executor_id':'MISSION_CONTROL_PROCESS_CONTRACT_RECONCILER','effect_ceiling':'NONE','mode':'VERIFY_BEFORE_REPAIR_RECONCILIATION'},
 ),
 'CONTROL_PLANE_REPAIR':(
  {'capability_id':'GENERIC_MISSION_CONTRACT_RECONCILIATION','executor_id':'MISSION_CONTROL_PROCESS_CONTRACT_RECONCILER','effect_ceiling':'NONE','mode':'VERIFY_BEFORE_REPAIR_RECONCILIATION'},
 ),
 'BROKER_RECONCILIATION':(
  {'capability_id':'GENERIC_MISSION_CONTRACT_RECONCILIATION','executor_id':'MISSION_CONTROL_PROCESS_CONTRACT_RECONCILER','effect_ceiling':'NONE','mode':'VERIFY_BEFORE_REPAIR_RECONCILIATION'},
 ),
 'PANEL_ACCEPTANCE':(
  {'capability_id':'GENERIC_MISSION_CONTRACT_RECONCILIATION','executor_id':'MISSION_CONTROL_PROCESS_CONTRACT_RECONCILER','effect_ceiling':'NONE','mode':'READ_ONLY_ACCEPTANCE'},
 ),
}
def process_capability_registry_snapshot():
    capabilities={}
    for cls,rows in sorted(PROCESS_CAPABILITY_REGISTRY.items()):
      capabilities[cls]=[{
        'capability_id':str(item.get('capability_id')),
        'executor_id':str(item.get('executor_id')) if item.get('executor_id') is not None else None,
        'effect_ceiling':str(item.get('effect_ceiling') or 'NONE'),
        'mode':str(item.get('mode') or 'UNKNOWN'),
      } for item in rows]
    value={'schema':'lion.process-capability-registry/v1','capabilities':capabilities,'authority_effect':'NONE'}
    value['registry_digest']=hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    return value


MISSION_DRIVER_LOOP_INTERVAL_SECONDS=2.0
LIVENESS_FRESH_MULTIPLIER=3
LIVENESS_STALE_MULTIPLIER=10
CAPABILITY_RECHECK_BLOCKERS=frozenset({'CAPABILITY_NOT_AVAILABLE','CURRENTNESS_REQUIRED','EXECUTOR_NOT_AVAILABLE','EXTERNAL_DEPENDENCY_WAIT'})
LPCL_REBIND_DISTRIBUTION=(6,6,6,6,5,5,5,5,5,5,5,5)


def _phase_lifecycle_state(rows,current_phase=None):
    statuses=[str(r['status']) for r in rows]
    current_status=None
    if current_phase:
      current_status=next((str(r['status']) for r in rows if r['phase_id']==current_phase),None)
    if current_status=='BLOCKED':return 'BLOCKED'
    if current_status=='WAITING':return 'WAITING'
    if current_status=='RUNNING':return 'RUNNING'
    if 'RUNNING' in statuses:return 'RUNNING'
    if 'WAITING' in statuses:return 'WAITING'
    if 'BLOCKED' in statuses:return 'BLOCKED'
    if 'FAIL' in statuses:return 'FAILED'
    if statuses and all(s in {'PASS','COMPLETE','SKIPPED'} for s in statuses):return 'COMPLETE'
    return 'AUTHORIZED'


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


def _lpcl_rebind_source(kv):
    parent=str(kv.get('PARENT_MISSION_ID') or '').strip()
    return parent if parent else LPCL_REBIND_SOURCE



def _compile_and_store_phase_contracts(c,mid,lpcl_text,phase_rows,*,allow_current_migration=True):
    kv=_lpcl_pairs(lpcl_text);language=str(kv.get('CONTROL_LANGUAGE') or 'LPCL/1.1').strip()
    phases=[{'id':row[0] if not isinstance(row,dict) else row['id']} for row in phase_rows]
    contracts=list(compile_panel_phase_contracts(kv,mid,phases,language))
    if allow_current_migration:
      contracts=[migrated_contract_for(mid,contract.phase_id,contract.ordinal) or contract for contract in contracts]
    global_sched.store_phase_execution_contracts(c,mid,contracts,now)
    preflight=preflight_execution_contracts(contracts,PROCESS_CAPABILITY_REGISTRY)
    global_sched.store_execution_preflight(c,mid,preflight,now)
    return contracts,preflight


def reconcile_phase_execution_contracts():
    c=connect()
    try:
      rows=c.execute("SELECT mission_id,lpcl_text FROM mission_process_specs WHERE lpcl_text IS NOT NULL AND lpcl_text!=''").fetchall()
      for row in rows:
       phase_rows=[{'id':r['phase_id']} for r in c.execute('SELECT phase_id FROM mission_phases WHERE mission_id=? ORDER BY ordinal',(row['mission_id'],)).fetchall()]
       if not phase_rows:continue
       try:_compile_and_store_phase_contracts(c,row['mission_id'],row['lpcl_text'],phase_rows)
       except PhaseExecutionContractError as exc:
        # Existing LPCL/1.1 must remain readable; invalid declared 1.2 is recorded by registration/preflight, not promoted.
        _process_message(c,row['mission_id'],'VALIDATION','PROCESS_CONTRACT_COMPILER','MISSION_CONTROL',None,{'event':'PROCESS_CONTRACT_RECONCILIATION_BLOCKED','error':str(exc),'authority_effect':'NONE'},'INTERNAL')
      artifact_changes=control_recon.reconcile_terminal_artifacts(c,now)
      for change in artifact_changes:
       _process_message(c,change['mission_id'],'RECEIPT','TERMINAL_ARTIFACT_RECONCILER','MISSION_CONTROL',None,{'event':'TERMINAL_ARTIFACT_RECONCILED','language_gap_digest':change['language_gap_digest'],'intelligence_digest':change['intelligence_digest'],'successor_digest':change['successor_digest'],'successor_proposal_digest':change['successor_proposal_digest'],'successor_contract_count':change['successor_contract_count'],'authority_effect':'NONE'},'INTERNAL')
      c.commit()
    finally:c.close()


def _phase_contract_capability(c,mid,pid):
    contract=global_sched.phase_execution_contract(c,mid,pid)
    if not contract:return None,None
    for cls in contract.get('capability_classes',[]):
      candidates=PROCESS_CAPABILITY_REGISTRY.get(cls,())
      if not candidates:continue
      capability=dict(candidates[0]);binding=global_sched.bind_phase_capability(c,mid,pid,cls,capability,now)
      return contract,{**capability,'binding':binding,'capability_class':cls}
    return contract,None


CURRENT_MASTER_IDENTITY_RESOLVER=None

def _current_master_identity():
    if callable(CURRENT_MASTER_IDENTITY_RESOLVER):
      head,tree=CURRENT_MASTER_IDENTITY_RESOLVER()
      if not _hex(head,40) or not _hex(tree,40):raise RuntimeError('injected master currentness malformed')
      return head,tree
    td=Path(tempfile.mkdtemp(prefix='lion-mc-current-master-'))
    try:
      subprocess.run(['/usr/bin/git','init',str(td)],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,check=True,timeout=30)
      subprocess.run(['/usr/bin/git','-C',str(td),'remote','add','origin','https://github.com/DonkeyJJLove/ai_platform.git'],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,check=True,timeout=30)
      subprocess.run(['/usr/bin/git','-C',str(td),'fetch','--no-tags','--depth=1','origin','refs/heads/master'],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,check=True,timeout=180)
      head=subprocess.run(['/usr/bin/git','-C',str(td),'rev-parse','FETCH_HEAD'],stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,check=True,timeout=30).stdout.strip()
      tree=subprocess.run(['/usr/bin/git','-C',str(td),'rev-parse','FETCH_HEAD^{tree}'],stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,check=True,timeout=30).stdout.strip()
      if not _hex(head,40) or not _hex(tree,40):raise RuntimeError('git master currentness malformed')
      return head,tree
    except Exception as exc:
      raise RuntimeError('github master currentness unavailable:'+type(exc).__name__) from exc
    finally:shutil.rmtree(td,ignore_errors=True)


def bind_lpcl_execution(mid):
    c=connect()
    try:
      m=c.execute('SELECT mission_id,state,spec_digest,source_head,source_tree,logical_count,material_target,adapter FROM missions WHERE mission_id=?',(mid,)).fetchone()
      ps=c.execute('SELECT lpcl_text,authority_state,current_phase,progress FROM mission_process_specs WHERE mission_id=?',(mid,)).fetchone()
      if not m or not ps:return None
      if m['state'] not in {'AUTHORIZED','RUNNING','WAITING','BLOCKED'} or ps['authority_state']!='EXPLICIT_USER_ACTIVATION':return None
      if m['material_target']!=64 or m['logical_count'] not in {12,128}:raise ValueError('lpcl execution adapter cardinality')
      kv=_lpcl_pairs(ps['lpcl_text'])
      continuation_ok=(kv.get('CONTINUE_EXISTING_EPOCH3_MISSION')=='TRUE' or kv.get('CONTINUE_EXISTING_EPOCH3_LINEAGE')=='TRUE')
      explicit_parent=str(kv.get('PARENT_MISSION_ID') or '').strip()
      fresh_ok=(not continuation_ok and not explicit_parent)
      if not continuation_ok and not fresh_ok:raise ValueError('lpcl lineage mode')
      if continuation_ok:
       if kv.get('CREATE_PARALLEL_COMPETING_EPOCH3_MISSION')!='FALSE':raise ValueError('lpcl continuation contract')
       reuse=kv.get('REUSE_EXISTING_HEALTHY_MATERIAL_FLEET','')
       legacy_reuse=kv.get('MATERIAL_REUSE_POLICY','')
       reuse_ok=('ALLOWED' in reuse or legacy_reuse=='REUSE_EXISTING_HEALTHY_EPOCH3_M64_AFTER_EXACT_IDENTITY_READBACK')
       if not reuse_ok:raise ValueError('lpcl material rebind not allowed')
       source_mid=_lpcl_rebind_source(kv)
       if source_mid==mid:raise ValueError('lpcl parent self-reference')
      else:
       source_mid=None
      # A bound mission owns its durable logical/material snapshot. Preserve a
      # complete snapshot across process restarts; otherwise reacquire the exact
      # physical carrier read-only and rebuild the binding.
      if m['adapter']==LPCL_REBIND_ADAPTER:
       own=c.execute('SELECT pod_name,pod_uid,logical_id,phase,ready,restarts,pod_ip,observed_at FROM material_workers WHERE mission_id=? ORDER BY logical_id,pod_name',(mid,)).fetchall()
       own_by={f'LD{i:02d}':[0,0] for i in range(1,13)}
       for r in own:
        lid=str(r['logical_id'] or '').upper()
        if lid in own_by:
         own_by[lid][0]+=1;own_by[lid][1]+=int(r['ready'] or 0)
       own_distribution_ok=all(own_by[f'LD{i:02d}']==[target,target] for i,target in enumerate(LPCL_REBIND_DISTRIBUTION,1))
       if len(own)==64 and len({r['pod_uid'] for r in own if r['pod_uid']})==64 and all(int(r['ready'])==1 for r in own) and own_distribution_ok:
        c.execute('UPDATE missions SET last_error=NULL,updated_at=? WHERE mission_id=?',(now(),mid));c.commit();return process_snapshot(mid)
      if m['adapter']==LPCL_GENERIC_ADAPTER:
       own=c.execute('SELECT pod_uid,ready FROM material_workers WHERE mission_id=?',(mid,)).fetchall()
       logical_total=c.execute('SELECT COUNT(*) FROM logical_drones WHERE mission_id=?',(mid,)).fetchone()[0]
       topo_total=c.execute("SELECT COUNT(*) FROM mission_execution_assignments WHERE mission_id=? AND phase_id='__TOPOLOGY__'",(mid,)).fetchone()[0]
       if len(own)==64 and len({r['pod_uid'] for r in own if r['pod_uid']})==64 and all(int(r['ready'])==1 for r in own) and logical_total==128 and topo_total==128:
        c.execute('UPDATE missions SET last_error=NULL,updated_at=? WHERE mission_id=?',(now(),mid));c.commit();return process_snapshot(mid)
      if continuation_ok:
       src=c.execute('SELECT mission_id,state,runtime_state,source_head,source_tree FROM missions WHERE mission_id=?',(source_mid,)).fetchone()
       if not src:raise ValueError('lpcl source mission missing:'+source_mid)
      current_head,current_tree=_current_master_identity()
      runtime,material_request_id=epoch3_broker('EPOCH3_M64_READ',source_mission_id=source_mid,current_head=current_head,current_tree=current_tree)
      live_pods=runtime.get('pods') or []
      if runtime.get('state')!='RUNNING' or int(runtime.get('materialized',0) or 0)!=64 or int(runtime.get('ready',0) or 0)!=64 or int(runtime.get('unique_uid_count',0) or 0)!=64 or len(live_pods)!=64:
       raise ValueError('lpcl live material fleet not healthy')
      workers=[]
      for pod in live_pods:
       workers.append({'pod_name':pod.get('name'),'pod_uid':pod.get('uid'),'logical_id':str(pod.get('logical_drone') or '').upper(),'phase':pod.get('phase'),'ready':1 if pod.get('ready') else 0,'restarts':int(pod.get('restarts',0) or 0),'pod_ip':pod.get('pod_ip')})
      if len({r['pod_uid'] for r in workers if r['pod_uid']})!=64 or any(int(r['ready'])!=1 for r in workers):raise ValueError('lpcl live material fleet identity')
      if int(m['logical_count'])==128:
       fresh=not continuation_ok
       has_explicit_topology=any(__import__('re').fullmatch(r'COHORT_[0-9]{2}',k) for k in kv)
       topology_text=ps['lpcl_text'] if (continuation_ok or has_explicit_topology) else global_sched.default_128l64m_topology_text()
       adapter=LPCL_REBIND_ADAPTER.replace('_64','_128L64M') if continuation_ok else LPCL_GENERIC_ADAPTER
       runtime_state='REBOUND_EXISTING_HEALTHY_FLEET_128L64M' if continuation_ok else 'GENERIC_SHARED_HEALTHY_FLEET_128L64M'
       bound=global_sched.bind_128l64m(c,mid,topology_text,workers,now,adapter=adapter,runtime_state=runtime_state)
       handlers={
        'EXACT_128L64M_TOPOLOGY_BIND':{'handler_id':'VERIFY_128L64M_BIND','effect_class':'NONE','gate_class':'EVIDENCE','retry_policy':'IDEMPOTENT','authority_class':'NONE'},
        'DATABASE_AND_SCHEDULER_SCHEMA_MIGRATION':{'handler_id':'VERIFY_SCHEDULER_SCHEMA','effect_class':'INTERNAL_DB','gate_class':'EVIDENCE','retry_policy':'IDEMPOTENT','authority_class':'MISSION_CONTROL'},
        'GLOBAL_MULTI_RUN_DISPATCHER':{'handler_id':'GLOBAL_MULTI_RUN_DISPATCH','effect_class':'CONTROL_STATE','gate_class':'EVIDENCE','retry_policy':'IDEMPOTENT','authority_class':'MISSION_CONTROL'},
        'PER_MISSION_LEASE_AND_FAIRNESS':{'handler_id':'VERIFY_LEASE_FAIRNESS','effect_class':'NONE','gate_class':'EVIDENCE','retry_policy':'IDEMPOTENT','authority_class':'NONE'},
        'PHASE_EXECUTION_PLAN_COMPILER':{'handler_id':'VERIFY_PHASE_PLAN','effect_class':'NONE','gate_class':'EVIDENCE','retry_policy':'IDEMPOTENT','authority_class':'NONE'},
        'DRIVER_LIFECYCLE_NORMALIZATION':{'handler_id':'VERIFY_DRIVER_LIFECYCLE','effect_class':'CONTROL_STATE','gate_class':'EVIDENCE','retry_policy':'IDEMPOTENT','authority_class':'MISSION_CONTROL'},
        'UNKNOWN_HANDLER_FAIL_CLOSED':{'handler_id':'VERIFY_UNKNOWN_HANDLER_WAIT','effect_class':'NONE','gate_class':'EVIDENCE','retry_policy':'IDEMPOTENT','authority_class':'NONE'},
       }
       if fresh:
        generic={'handler_id':'GENERIC_LPCL_PHASE','effect_class':'NONE','gate_class':'COGNITIVE_PLAN','retry_policy':'IDEMPOTENT','authority_class':'NONE'}
        for prow in c.execute('SELECT phase_id FROM mission_phases WHERE mission_id=?',(mid,)).fetchall():handlers.setdefault(prow['phase_id'],generic)
       global_sched.compile_phase_specs(c,mid,handlers)
       nxt=c.execute("SELECT phase_id FROM mission_phases WHERE mission_id=? AND status NOT IN ('PASS','COMPLETE','SKIPPED','CANCELLED') ORDER BY ordinal LIMIT 1",(mid,)).fetchone()
       current=nxt['phase_id'] if nxt else None;t=now()
       c.execute('UPDATE mission_process_specs SET current_phase=?,updated_at=? WHERE mission_id=?',(current,t,mid))
       if current:c.execute("UPDATE mission_phases SET status=CASE WHEN status='PENDING' THEN 'RUNNING' ELSE status END,started_at=COALESCE(started_at,?),updated_at=? WHERE mission_id=? AND phase_id=?",(t,t,mid,current))
       ensure_driver(c,mid,now,initial_state='BOOTSTRAP_PAUSED')
       prior=driver_snapshot(c,mid)
       if prior and prior['state']=='ACTIVE' and prior.get('lease_owner')!=DRIVER_PROCESS_ID:
        driver_wait_for_execution_binding(c,mid,now,blocking_gate='EXECUTION_REBIND_HANDOFF',waiting_reason='Fresh execution binding superseded an orphan active driver',next_action='EXECUTION_BINDING_READY')
       driver_activate(c,mid,now,next_action='GLOBAL_SCHEDULER_DISPATCH',owner_id=DRIVER_PROCESS_ID,lease_seconds=30)
       event_name='EXACT_128L64M_BOUND' if continuation_ok else 'GENERIC_SHARED_128L64M_BOUND'
       _process_message(c,mid,'ASSIGNMENT','MISSION_CONTROL','GLOBAL_SCHEDULER',current,{'event':event_name,'logical_count':128,'material_count':64,'assignments':128,'ratio':'2:1','unique_uid_count':64,'material_request_id':material_request_id,'binding_class':'LINEAGE_REBIND' if continuation_ok else 'FRESH_SHARED_CAPACITY','authority_effect':'MISSION_SCOPED_CONTROL_BINDING'},'INTERNAL')
       c.commit();return process_snapshot(mid)
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
      old_uids=sorted(r['pod_uid'] for r in c.execute('SELECT pod_uid FROM material_workers WHERE mission_id=? AND pod_uid IS NOT NULL',(mid,)).fetchall())
      new_uids=sorted(r['pod_uid'] for r in workers)
      t=now()
      c.execute('DELETE FROM logical_drones WHERE mission_id=?',(mid,));c.execute('DELETE FROM material_workers WHERE mission_id=?',(mid,))
      for lid,role,target in roles:c.execute('INSERT INTO logical_drones VALUES(?,?,?,?,?,?)',(mid,lid,role,target,target,target))
      for r in workers:c.execute('INSERT INTO material_workers VALUES(?,?,?,?,?,?,?,?,?)',(mid,r['pod_name'],r['pod_uid'],str(r['logical_id']).upper(),r['phase'],r['ready'],r['restarts'],r['pod_ip'],t))
      # First unfinished phase is the execution cursor. Never rewind completed evidence.
      nxt=c.execute("SELECT phase_id FROM mission_phases WHERE mission_id=? AND status NOT IN ('PASS','COMPLETE','SKIPPED','CANCELLED') ORDER BY ordinal LIMIT 1",(mid,)).fetchone()
      current=nxt['phase_id'] if nxt else None
      c.execute('UPDATE missions SET adapter=?,state=?,runtime_state=?,materialized=64,ready=64,updated_at=?,last_error=NULL WHERE mission_id=?',(LPCL_REBIND_ADAPTER,'RUNNING','REBOUND_EXISTING_HEALTHY_FLEET',t,mid))
      c.execute('UPDATE mission_process_specs SET current_phase=?,updated_at=? WHERE mission_id=?',(current,t,mid))
      if current:
       c.execute("UPDATE mission_phases SET status=CASE WHEN status='PENDING' THEN 'RUNNING' ELSE status END,started_at=COALESCE(started_at,?),updated_at=? WHERE mission_id=? AND phase_id=?",(t,t,mid,current))
      phase_rows=c.execute('SELECT phase_id,status FROM mission_phases WHERE mission_id=? ORDER BY ordinal',(mid,)).fetchall();life=_phase_lifecycle_state(phase_rows,current)
      c.execute('UPDATE missions SET state=?,updated_at=? WHERE mission_id=?',(life,t,mid))
      # Preserve the parent until explicit self-hosting/lineage reconciliation.
      keep_parent=kv.get('PARENT_MISSION_REMAINS_AUTHORITY_CARRIER_UNTIL_SELF_HOSTING_TAKEOVER')=='TRUE'
      if not keep_parent and source_mid==LPCL_REBIND_SOURCE:
       c.execute('UPDATE missions SET state=?,runtime_state=?,updated_at=? WHERE mission_id=?',('SUPERSEDED','REBOUND_TO:'+mid,t,source_mid))
       c.execute('UPDATE mission_process_specs SET current_phase=NULL,authority_state=?,updated_at=? WHERE mission_id=?',('SUPERSEDED_BY_EXACT_LPCL',t,source_mid))
      # lineage is metadata only; authority remains exact LPCL.
      try:
       c.execute("INSERT INTO mission_lineage(mission_id,root_mission_id,parent_mission_id,revision,relation,source_epoch,source_stage,source_schema,created_at) VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(mission_id) DO UPDATE SET parent_mission_id=excluded.parent_mission_id,relation=excluded.relation",(mid,source_mid,source_mid,1,'COMPLEMENTARY_CONTROL_PLANE_REPAIR_CHILD','EPOCH3_CLOSURE','MISSION_PROCESS_SCHEMA_V1','lion.mission-process/v1',t))
      except sqlite3.OperationalError:pass
      uid_digest=_payload_digest({'uids':new_uids})
      changed=old_uids!=new_uids
      _process_message(c,mid,'ASSIGNMENT','MISSION_CONTROL','MATERIAL_FLEET',current,{'event':'EXISTING_HEALTHY_FLEET_REBOUND','source_mission_id':source_mid,'worker_count':64,'unique_uid_count':64,'worker_uid_digest':uid_digest,'previous_binding_changed':changed,'binding_class':'CONTROL_PLANE_REBIND','material_currentness_source':'EPOCH3_M64_READ','material_request_id':material_request_id,'pod_role_environment_rewritten':False,'authority_effect':'MISSION_SCOPED_CONTROL_BINDING'},'INTERNAL')
      _process_message(c,mid,'CURRENTNESS','MISSION_CONTROL','LD02',current,{'event':'CURRENTNESS_REACQUIRED','registered_source_head':m['source_head'],'registered_source_tree':m['source_tree'],'runtime_source_head':current_head,'runtime_source_tree':current_tree,'material_ready':64,'material_target':64,'parent_mission_id':source_mid,'material_currentness_source':'GITHUB_MASTER_PLUS_EPOCH3_M64_READ','material_request_id':material_request_id},'INTERNAL')
      _process_message(c,mid,'RECEIPT','MISSION_CONTROL','OPERATOR',current,{'event':'LPCL_EXECUTION_ADAPTER_BOUND','adapter':LPCL_REBIND_ADAPTER,'source_mission_id':source_mid,'lpcl_digest':m['spec_digest'],'worker_uid_digest':uid_digest,'parent_preserved':keep_parent},'OUT')
      ensure_driver(c,mid,now,initial_state='BOOTSTRAP_PAUSED')
      c.commit()
    finally:c.close()
    return process_snapshot(mid)


def reconcile_lpcl_execution_bindings():
    c=connect()
    try:
      rows=[r['mission_id'] for r in c.execute("SELECT m.mission_id FROM missions m JOIN mission_process_specs p ON p.mission_id=m.mission_id WHERE p.authority_state='EXPLICIT_USER_ACTIVATION' AND m.state IN ('AUTHORIZED','RUNNING','WAITING','BLOCKED') AND m.adapter IN ('LPCL_MISSION','LPCL_REBOUND_EPOCH3_64','LPCL_GENERIC_128L64M') ORDER BY m.updated_at DESC").fetchall()]
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
    validate_registration(x)
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
    spec['schema_version']=RUNTIME_SCHEMA_VERSION
    spec['mission_class']='LPCL_MISSION'
    c.execute('INSERT INTO missions VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(mid,x['title'],'LPCL_MISSION',x['lpcl_digest'],x['source_head'],x['source_tree'],None,'REGISTERED','NOT_STARTED',x['logical_count'],x['material_target'],0,0,t,None,t,None,json.dumps(spec,sort_keys=True,ensure_ascii=False)))
    c.execute('INSERT INTO mission_process_specs VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(mid,x['title'],x['objective'],x['description'],x['lpcl_digest'],x['lpcl_text'],json.dumps(x['protocols']), 'NONE',None,0.0,t,t))
    for i,(pid,title) in enumerate(phase_rows,1):c.execute('INSERT INTO mission_phases VALUES(?,?,?,?,?,?,?,?,?,?)',(mid,pid,i,title,'PENDING',0.0,None,None,None,t))
    contracts,preflight=_compile_and_store_phase_contracts(c,mid,x['lpcl_text'],[{'id':pid} for pid,_ in phase_rows],allow_current_migration=(mid in {SAAS_AUTOMATIC_MEDIATOR_MISSION,FIREFOX_PROJECT_MEDIATOR_SUCCESSOR_MISSION}))
    _process_message(c,mid,'LPCL','LPCL_PANEL','MISSION_CONTROL',None,{'event':'MISSION_REGISTERED','lpcl_digest':x['lpcl_digest'],'phase_count':len(phase_rows),'phase_contract_schema':PHASE_CONTRACT_SCHEMA,'phase_contract_compiler':PHASE_CONTRACT_COMPILER_VERSION,'preflight':preflight.as_dict()},'IN')
    c.execute('INSERT INTO mission_meta(key,value,updated_at) VALUES(?,?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value,updated_at=excluded.updated_at',('focus_mission_id',mid,t))
    c.commit();c.close();return {'idempotent':False,'mission':process_snapshot(mid)}

def activate_lpcl_mission(mid,x):
    if type(x) is not dict or set(x)!={'lpcl_digest','activation_event'} or x.get('activation_event')!='EXPLICIT_UI_ACTIVATION' or not _hex(x.get('lpcl_digest'),64):raise ValueError('activation schema')
    c=connect();m=c.execute('SELECT state,spec_digest FROM missions WHERE mission_id=?',(mid,)).fetchone()
    if not m: c.close();raise ValueError('mission not found')
    if m['spec_digest']!=x['lpcl_digest']:c.close();raise ValueError('activation digest drift')
    if m['state'] not in {'REGISTERED','AUTHORIZED'}:c.close();raise ValueError('activation state')
    preflight=global_sched.execution_preflight(c,mid)
    if preflight is None:raise ValueError('phase execution preflight missing')
    if preflight.get('mission_readiness')=='INVALID':raise ValueError('phase execution preflight invalid')
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
    c=connect()
    life=c.execute('SELECT m.state AS mission_state,p.authority_state FROM missions m LEFT JOIN mission_process_specs p ON p.mission_id=m.mission_id WHERE m.mission_id=?',(mid,)).fetchone()
    if not life:c.close();raise ValueError('mission not found')
    if str(life['mission_state']).upper()=='SUPERSEDED' or str(life['authority_state'] or '').upper().startswith('SUPERSEDED'):
      c.close();raise ValueError('mission superseded')
    row=c.execute('SELECT status,started_at FROM mission_phases WHERE mission_id=? AND phase_id=?',(mid,x['phase_id'])).fetchone()
    if not row:c.close();raise ValueError('phase not found')
    t=now();started=row['started_at'];finished=None
    if x['status']=='RUNNING' and not started:started=t
    if x['status'] in {'PASS','FAIL','SKIPPED','COMPLETE','CANCELLED'}:finished=t
    c.execute('UPDATE mission_phases SET status=?,progress=?,detail=?,started_at=?,finished_at=?,updated_at=? WHERE mission_id=? AND phase_id=?',(x['status'],float(x['progress']),str(x['detail'])[:4000],started,finished,t,mid,x['phase_id']))
    rows=c.execute('SELECT status,progress,phase_id FROM mission_phases WHERE mission_id=? ORDER BY ordinal',(mid,)).fetchall();overall=sum(float(r['progress']) for r in rows)/max(1,len(rows));current=next((r['phase_id'] for r in rows if r['status'] in {'RUNNING','WAITING','BLOCKED'}),None)
    life=_phase_lifecycle_state(rows,current)
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


def epoch3_broker(operation,pod=None,source_mission_id=None,current_head=None,current_tree=None):
    # Logical lineage and material-carrier authority are distinct identities.
    # Continuations validate their explicit logical parent. Fresh missions may
    # acquire the same bounded shared carrier without inventing a parent.
    source=None
    if source_mission_id is not None:
     source_mid=str(source_mission_id).strip()
     c=connect();source=c.execute('SELECT mission_id,source_head,source_tree FROM missions WHERE mission_id=?',(source_mid,)).fetchone();c.close()
     if not source:raise ValueError('epoch3 source mission missing:'+source_mid)
    elif current_head is None or current_tree is None:
     source_mid=LPCL_REBIND_SOURCE
     c=connect();source=c.execute('SELECT mission_id,source_head,source_tree FROM missions WHERE mission_id=?',(source_mid,)).fetchone();c.close()
     if not source:raise ValueError('epoch3 source mission missing:'+source_mid)
    head=str(current_head or (source['source_head'] if source else '') or '').strip();tree=str(current_tree or (source['source_tree'] if source else '') or '').strip()
    if not _hex(head,40) or not _hex(tree,40):raise ValueError('epoch3 currentness identity')
    req={'schema_version':'1.0.0','request_id':hashlib.sha256(os.urandom(32)).hexdigest(),'operation':operation,'mission_id':EPOCH3_MATERIAL_CARRIER_ID,'source_head':head,'source_tree':tree,'spec_digest':EPOCH3_MATERIAL_CARRIER_SPEC_DIGEST}
    if pod is not None:req['pod_name']=pod
    return _send_broker_request(req)


def epoch3_component_broker(operation,logical_id):
    c=connect();row=c.execute('SELECT mission_id,spec_digest,source_head,source_tree FROM missions WHERE mission_id=?',(LPCL_REBIND_SOURCE,)).fetchone();c.close()
    if not row:raise ValueError('epoch3 material adapter identity missing')
    req={'schema_version':'1.0.0','request_id':hashlib.sha256(os.urandom(32)).hexdigest(),'operation':operation,'mission_id':LPCL_REBIND_SOURCE,'source_head':row['source_head'],'source_tree':row['source_tree'],'spec_digest':row['spec_digest'],'logical_id':str(logical_id).upper()}
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


def _replace_lpcl_key(text,key,value):
    import re
    pat=re.compile(r'^'+re.escape(key)+r'=.*$',re.MULTILINE)
    line=f'{key}={value}'
    return pat.sub(line,text,count=1) if pat.search(text) else text.rstrip()+'\n'+line+'\n'


def compile_design_revision(mid,revision_id):
    c=connect()
    try:
      rev=c.execute('SELECT revision_id,mission_id,revision_no,action,state,request_json,request_digest FROM mission_design_revisions WHERE revision_id=? AND mission_id=?',(revision_id,mid)).fetchone()
      ps=c.execute('SELECT lpcl_text FROM mission_process_specs WHERE mission_id=?',(mid,)).fetchone()
      m=c.execute('SELECT source_head,source_tree FROM missions WHERE mission_id=?',(mid,)).fetchone()
      if not rev or not ps or not ps['lpcl_text'] or not m:raise ValueError('revision compilation source missing')
      existing=c.execute('SELECT * FROM mission_revision_compilations WHERE revision_id=?',(revision_id,)).fetchone()
      if existing:return dict(existing)
      suffix=f"-REV{int(rev['revision_no']):02d}"
      successor=(mid+suffix)[:127]
      if successor==mid or len(mid+suffix)>127:
       successor=(mid[:110]+'-R'+hashlib.sha256((mid+suffix).encode()).hexdigest()[:12])
      text=str(ps['lpcl_text'])
      text=_replace_lpcl_key(text,'MISSION_ID',successor)
      text=_replace_lpcl_key(text,'RUN','THE-BEAN-FACTORY-LION-EVOLUTION-V1_4-DESIGN-REVISION-'+hashlib.sha256(successor.encode()).hexdigest()[:16].upper())
      text=_replace_lpcl_key(text,'PARENT_MISSION_ID',mid)
      text=_replace_lpcl_key(text,'MISSION_RELATION','DESIGN_REVISION_SUCCESSOR')
      text=_replace_lpcl_key(text,'REVISION_SOURCE_ID',revision_id)
      text=_replace_lpcl_key(text,'REVISION_ACTION',rev['action'])
      text=_replace_lpcl_key(text,'REVISION_REQUEST_DIGEST',rev['request_digest'])
      dg=hashlib.sha256(text.encode('utf-8')).hexdigest();stamp=now()
      c.execute('INSERT INTO mission_revision_compilations(revision_id,mission_id,successor_mission_id,lpcl_digest,lpcl_text,state,created_at,activated_at) VALUES(?,?,?,?,?,?,?,NULL)',(revision_id,mid,successor,dg,text,'COMPILED_AWAITING_EXPLICIT_ACTIVATION',stamp));c.commit()
      return dict(c.execute('SELECT * FROM mission_revision_compilations WHERE revision_id=?',(revision_id,)).fetchone())
    finally:c.close()


def register_compiled_revision(mid,revision_id):
    comp=compile_design_revision(mid,revision_id)
    kv=_lpcl_pairs(comp['lpcl_text'])
    phases=[]
    for key,val in sorted(((k,v) for k,v in kv.items() if __import__('re').fullmatch(r'PHASE_[0-9]{2}',k))):
      if '|' not in val:raise ValueError('compiled phase format')
      pid,title=val.split('|',1);phases.append({'id':pid.strip(),'title':title.strip()[:180]})
    protocols=[x.strip() for x in kv.get('PROTOCOLS','').split(',') if x.strip()]
    c=connect();m=c.execute('SELECT source_head,source_tree FROM missions WHERE mission_id=?',(mid,)).fetchone();c.close()
    payload={'mission_id':comp['successor_mission_id'],'title':kv.get('MISSION_TITLE','Design revision successor')[:180],'objective':kv.get('MISSION_OBJECTIVE','Design revision successor')[:4000],'description':kv.get('MISSION_DESCRIPTION','')[:8000],'lpcl_digest':comp['lpcl_digest'],'lpcl_text':comp['lpcl_text'],'source_head':m['source_head'],'source_tree':m['source_tree'],'logical_count':int(kv.get('LOGICAL_DRONE_COUNT') or 12),'material_target':int(kv.get('MATERIAL_DRONE_COUNT') or 64),'phases':phases,'protocols':protocols}
    registered=register_lpcl_mission(payload)
    c=connect();c.execute("UPDATE mission_design_revisions SET state='SUCCESSOR_COMPILED_REGISTERED' WHERE revision_id=?",(revision_id,));c.execute("UPDATE mission_revision_compilations SET state='REGISTERED_AWAITING_EXPLICIT_ACTIVATION' WHERE revision_id=?",(revision_id,));c.commit();c.close()
    return {'revision_id':revision_id,'successor_mission_id':comp['successor_mission_id'],'lpcl_digest':comp['lpcl_digest'],'state':'REGISTERED_AWAITING_EXPLICIT_ACTIVATION','authority_effect':'NONE','registered':registered.get('idempotent') is not None}


def maybe_register_compiled_revision(mid,revision_id):
    c=connect();row=c.execute('SELECT lpcl_text FROM mission_process_specs WHERE mission_id=?',(mid,)).fetchone();c.close()
    if not row or not row['lpcl_text']:
        return {'state':'NO_CANONICAL_LPCL_SOURCE','authority_effect':'NONE'}
    return register_compiled_revision(mid,revision_id)


def activate_compiled_revision(mid,revision_id,lpcl_digest):
    c=connect();row=c.execute('SELECT successor_mission_id,lpcl_digest,state FROM mission_revision_compilations WHERE revision_id=? AND mission_id=?',(revision_id,mid)).fetchone();c.close()
    if not row:raise ValueError('compiled revision not found')
    if row['lpcl_digest']!=lpcl_digest:raise ValueError('revision activation digest drift')
    result=activate_lpcl_mission(row['successor_mission_id'],{'lpcl_digest':lpcl_digest,'activation_event':'EXPLICIT_UI_ACTIVATION'})
    c=connect();stamp=now();c.execute("UPDATE mission_revision_compilations SET state='ACTIVATED',activated_at=? WHERE revision_id=?",(stamp,revision_id));c.execute("UPDATE mission_design_revisions SET state='ACTIVATED',activated_at=? WHERE revision_id=?",(stamp,revision_id));c.commit();c.close()
    return {'revision_id':revision_id,'successor_mission_id':row['successor_mission_id'],'lpcl_digest':lpcl_digest,'state':'ACTIVATED','mission':result,'authority_effect':'EXPLICIT_USER_ACTIVATION'}


def mission_action(mid,x,*,phase_guard=None):
    if type(x) is not dict or 'action' not in x or not isinstance(x['action'],str):raise ValueError('action schema')
    action=x['action'].upper();allowed={'REFRESH','RESTART','START_COMPONENT','ADD_COMPONENT','REDESIGN','ACTIVATE_REVISION','AUDIT','ROLLBACK','PAUSE','PAUSE_AUTO_RESUME','REACQUIRE_CAPABILITIES','RESUME','VALIDATE','STOP','DRIVER_START'}
    if action not in allowed:raise ValueError('action denied')
    request={k:v for k,v in x.items() if k!='action'}
    c=connect();row=c.execute('SELECT mission_id,adapter,state FROM missions WHERE mission_id=?',(mid,)).fetchone();classification=mission_lifecycle_classification(c,mid) if row else None;c.close()
    if not row:raise ValueError('mission not found')
    if classification['lifecycle_class']=='LEGACY_HISTORY' and action not in {'REFRESH','AUDIT','VALIDATE'}:raise ValueError('LEGACY_HISTORY_READ_ONLY')
    if (classification['lifecycle_class']=='SUPERSEDED' or mid in {EPOCH3_LIFECYCLE_TARGET_1,EPOCH3_LIFECYCLE_TARGET_2}) and action not in {'REFRESH','AUDIT','VALIDATE'}:raise ValueError('MISSION_SUPERSEDED_READ_ONLY' if classification['lifecycle_class']=='SUPERSEDED' else 'EPOCH3_TARGET_PENDING_SUPERSESSION_READ_ONLY')
    guarded_connection=None
    if phase_guard is not None:
      if action not in {'PAUSE','STOP'} or phase_guard.get('action')!=action:raise ValueError('phase guard action mismatch')
      guarded_connection=connect()
      try:fence_phase_action(guarded_connection,mid,phase_guard)
      except Exception:guarded_connection.close();raise
    effect='NONE';status='PASS';result=None
    try:
      if action=='REFRESH':
        if mid==MISSION:
          observe_once();result={'mission_id':mid,'source':'MISSION64_READ','effect':'READ_ONLY_CURRENTNESS'}
        elif mid==LPCL_REBIND_SOURCE or row['adapter']==LPCL_REBIND_ADAPTER:
          runtime,rid=epoch3_broker('EPOCH3_M64_READ');c=connect();apply_runtime_for(c,mid,runtime);c.commit();c.close();result={'mission_id':mid,'source':'EPOCH3_M64_READ','request_id':rid,'runtime':{k:runtime.get(k) for k in ('state','materialized','ready','unique_uid_count')},'effect':'READ_ONLY_CURRENTNESS','adapter_binding':'LPCL_REBOUND_SOURCE_RUNTIME' if row['adapter']==LPCL_REBIND_ADAPTER else 'DIRECT'}
        elif mid.startswith('legacy::'):result=refresh_legacy(mid)
        else:result={'mission_id':mid,'effect':'CONTROL_DB_READBACK','state':'NO_MATERIAL_CURRENTNESS_ADAPTER'}
      elif action=='AUDIT':
        c=connect();result=lifecycle_create_audit(c,mid,now);c.close()
      elif action in {'RESUME','DRIVER_START'}:
        c=connect();ds=driver_snapshot(c,mid)
        if not ds:raise ValueError('driver missing')
        if action=='RESUME' and ds['state'] not in {'BOOTSTRAP_PAUSED','PAUSED','STOPPED','FAILED'}:raise ValueError('driver not resumable from '+str(ds['state']))
        result=driver_activate(c,mid,now,next_action='SELECT_NEXT_PHASE',owner_id=DRIVER_PROCESS_ID);c.close();effect='CONTROL_STATE'
      elif action=='PAUSE':
        c=guarded_connection if guarded_connection is not None else connect();ds=driver_snapshot(c,mid)
        if not ds:raise ValueError('driver missing')
        if ds['state'] not in {'ACTIVE','BLOCKED'}:raise ValueError('driver not pausable from '+str(ds['state'])+'; WAITING requires PAUSE_AUTO_RESUME')
        result=driver_transition(c,mid,'PAUSED',now,next_action='OPERATOR_RESUME',current_phase=ds.get('current_phase'),commit=guarded_connection is None)
        if guarded_connection is None:c.close()
        effect='CONTROL_STATE'
      elif action=='PAUSE_AUTO_RESUME':
        c=connect();ds=driver_snapshot(c,mid)
        if not ds or ds['state']!='WAITING':raise ValueError('pause auto-resume requires WAITING driver')
        result=driver_transition(c,mid,'PAUSED',now,next_action='OPERATOR_RESUME',current_phase=ds.get('current_phase'));c.close();effect='CONTROL_STATE'
      elif action=='REACQUIRE_CAPABILITIES':
        c=connect();ds=driver_snapshot(c,mid)
        if not ds or ds['state'] not in {'WAITING','BLOCKED'}:c.close();raise ValueError('capability recheck requires WAITING/BLOCKED driver')
        gate=str(ds.get('blocking_gate') or '')
        if gate not in CAPABILITY_RECHECK_BLOCKERS:c.close();raise ValueError('blocking gate is not capability-recheckable: '+gate)
        pid=ds.get('current_phase');before_assign=int(c.execute("SELECT COUNT(*) FROM mission_execution_assignments WHERE mission_id=? AND phase_id=? AND phase_id!='__TOPOLOGY__'",(mid,pid)).fetchone()[0]);before_receipts=int(c.execute('SELECT COUNT(*) FROM mission_execution_receipts WHERE mission_id=? AND phase_id=?',(mid,pid)).fetchone()[0]);before_plans=int(c.execute('SELECT COUNT(*) FROM mission_generic_phase_plans WHERE mission_id=? AND phase_id=?',(mid,pid)).fetchone()[0]);_process_message(c,mid,'CONTROL','OPERATOR','GLOBAL_SCHEDULER',pid,{'event':'CAPABILITY_RECHECK_REQUESTED','blocking_gate':gate,'authority_effect':'CONTROL_STATE'},'IN');c.commit();c.close()
        drive_generic_once(mid)
        c=connect();after=driver_snapshot(c,mid);after_assign=int(c.execute("SELECT COUNT(*) FROM mission_execution_assignments WHERE mission_id=? AND phase_id=? AND phase_id!='__TOPOLOGY__'",(mid,pid)).fetchone()[0]);after_receipts=int(c.execute('SELECT COUNT(*) FROM mission_execution_receipts WHERE mission_id=? AND phase_id=?',(mid,pid)).fetchone()[0]);after_plans=int(c.execute('SELECT COUNT(*) FROM mission_generic_phase_plans WHERE mission_id=? AND phase_id=?',(mid,pid)).fetchone()[0]);still=bool(after and after.get('state') in {'WAITING','BLOCKED'} and after.get('blocking_gate')==gate);_process_message(c,mid,'CONTROL','GLOBAL_SCHEDULER','OPERATOR',pid,{'event':'CAPABILITY_RECHECK_RESULT','state':after.get('state') if after else None,'blocking_gate':after.get('blocking_gate') if after else None,'next_action':after.get('next_action') if after else None,'still_unavailable':still,'authority_effect':'CONTROL_STATE'},'OUT');c.commit();c.close()
        if after_assign!=before_assign or after_receipts!=before_receipts:raise ValueError('capability recheck duplicated planning work')
        result={'driver':after,'phase_id':pid,'still_unavailable':still,'planning_assignments_delta':after_assign-before_assign,'planning_receipts_delta':after_receipts-before_receipts,'action_ir_delta':after_plans-before_plans};effect='CONTROL_STATE'
      elif action=='STOP':
        c=guarded_connection if guarded_connection is not None else connect();ds=driver_snapshot(c,mid)
        if not ds:raise ValueError('driver missing')
        if ds['state'] in {'COMPLETE','STOPPED'}:result=ds
        else:result=driver_transition(c,mid,'STOPPED',now,next_action='EXPLICIT_RESUME_REQUIRED',commit=guarded_connection is None)
        if guarded_connection is None:c.close()
        effect='CONTROL_STATE'
      elif action=='VALIDATE':
        c=connect();ds=driver_snapshot(c,mid);mrow=c.execute('SELECT materialized,ready FROM missions WHERE mission_id=?',(mid,)).fetchone();integrity=c.execute('PRAGMA integrity_check').fetchone()[0]
        result={'driver':ds,'materialized':mrow['materialized'],'ready':mrow['ready'],'database_integrity':integrity,'validated':bool(ds and mrow['ready']==64 and integrity=='ok'),'authority_effect':'NONE'};c.close();effect='NONE'
      elif action=='RESTART':
        if mid==MISSION:
          effect='BOUNDED_MATERIAL';with_lock=LOCK
          with with_lock:
            first=command('STOP');second=command('START')
          result={'mission_id':mid,'restart_class':'STOP_THEN_START','stop':first,'start':second}
        elif mid==LPCL_REBIND_SOURCE or row['adapter']==LPCL_REBIND_ADAPTER:
          effect='BOUNDED_MATERIAL'
          stop,sid=epoch3_broker('EPOCH3_M64_STOP');start,stid=epoch3_broker('EPOCH3_M64_START');c=connect();apply_runtime_for(c,mid,start)
          if row['adapter']==LPCL_REBIND_ADAPTER:
            phase=c.execute('SELECT current_phase FROM mission_process_specs WHERE mission_id=?',(mid,)).fetchone();pid=phase['current_phase'] if phase else None
            if pid:
              c.execute("UPDATE mission_phases SET status='RUNNING',started_at=COALESCE(started_at,?),finished_at=NULL,updated_at=?,detail=? WHERE mission_id=? AND phase_id=?",(now(),now(),'Mission material runtime restarted under exact rebound adapter; autonomous phase execution resumed',mid,pid))
              _process_message(c,mid,'RECOVERY','MISSION_CONTROL','MATERIAL_FLEET',pid,{'event':'MISSION_RESTARTED_AND_RESUMED','stop_request_id':sid,'start_request_id':stid,'materialized':int(start.get('materialized',0) or 0),'ready':int(start.get('ready',0) or 0),'authority_effect':'MISSION_SCOPED'},'OUT')
          c.commit();c.close();result={'mission_id':mid,'restart_class':'EPOCH3_STOP_THEN_START','stop_request_id':sid,'start_request_id':stid,'runtime':{k:start.get(k) for k in ('state','materialized','ready','unique_uid_count')},'autonomous_resume':row['adapter']==LPCL_REBIND_ADAPTER}
        else:
          c=connect();result=lifecycle_create_design_revision(c,mid,'RESTART',request or {'reason':'operator requested restart/replay'},now,state='AWAITING_EXACT_LPCL_ACTIVATION');c.close()
      elif action=='START_COMPONENT':
        component=str(request.get('component_id') or '').strip().upper()
        if not component:raise ValueError('component_id required')
        c=connect();exists=c.execute('SELECT 1 FROM mission_components WHERE mission_id=? AND UPPER(component_id)=?',(mid,component)).fetchone();auth=c.execute('SELECT p.authority_state,m.adapter FROM missions m JOIN mission_process_specs p ON p.mission_id=m.mission_id WHERE m.mission_id=?',(mid,)).fetchone();c.close()
        if not exists:raise ValueError('component not found')
        if not auth or auth['authority_state']!='EXPLICIT_USER_ACTIVATION' or auth['adapter']!=LPCL_REBIND_ADAPTER:
          c=connect();result=lifecycle_create_design_revision(c,mid,'START_COMPONENT',{'component_id':component,'reason':request.get('reason') or 'bounded component start requested'},now,state='BLOCKED_EXACT_COMPONENT_ADAPTER_REQUIRED');c.close()
        else:
          effect='BOUNDED_MATERIAL';before,_=epoch3_component_broker('EPOCH3_M64_VALIDATE_LOGICAL',component);started,rid=epoch3_component_broker('EPOCH3_M64_START_LOGICAL',component);after,_=epoch3_component_broker('EPOCH3_M64_VALIDATE_LOGICAL',component)
          result={'mission_id':mid,'component_id':component,'pre':{k:before.get(k) for k in ('materialized','ready','uids')},'effect':{k:started.get(k) for k in ('materialized','ready','uids')},'post':{k:after.get(k) for k in ('materialized','ready','uids')},'material_request_id':rid,'authority_effect':'MISSION_SCOPED'}
      elif action=='ADD_COMPONENT':
        component=request.get('component')
        if type(component) is not dict or not str(component.get('component_id') or '').strip():raise ValueError('component object with component_id required')
        c=connect();rev=lifecycle_create_design_revision(c,mid,'ADD_COMPONENT',request,now);c.close();result={**rev,'successor':maybe_register_compiled_revision(mid,rev['revision_id'])}
      elif action=='REDESIGN':
        if not request:raise ValueError('redesign request required')
        c=connect();rev=lifecycle_create_design_revision(c,mid,'REDESIGN',request,now);c.close();result={**rev,'successor':maybe_register_compiled_revision(mid,rev['revision_id'])}
      elif action=='ACTIVATE_REVISION':
        revision_id=str(request.get('revision_id') or '').strip();lpcl_digest=str(request.get('lpcl_digest') or '').strip()
        if not revision_id or not _hex(lpcl_digest,64):raise ValueError('revision_id and exact lpcl_digest required')
        result=activate_compiled_revision(mid,revision_id,lpcl_digest);effect='CONTROL_STATE'
      elif action=='ROLLBACK':
        rollback_id=str(request.get('rollback_id') or '').strip()
        if not rollback_id:raise ValueError('rollback_id required')
        c=connect();result=lifecycle_rollback_plan(c,mid,rollback_id,now);c.close()
      c=guarded_connection if guarded_connection is not None else connect();receipt=lifecycle_create_action_receipt(c,mid,action,effect,status,request,result,now);c.close();return {'mission_id':mid,'action':action,'status':status,'effect_class':effect,'result':result,'receipt':receipt}
    except Exception as e:
      if guarded_connection is not None:
       try:guarded_connection.rollback();guarded_connection.close()
       except Exception:pass
      try:
        c=connect();receipt=lifecycle_create_action_receipt(c,mid,action,effect,'FAIL',request,{'error':type(e).__name__+':'+str(e)[:1000]},now);c.close()
      except Exception:receipt=None
      raise ValueError(type(e).__name__+':'+str(e)+((' receipt='+str(receipt.get('receipt_id'))) if receipt else ''))


def _parse_utc(value):
    if not value:return None
    try:
      dt=datetime.fromisoformat(str(value).replace('Z','+00:00'))
      if dt.tzinfo is None:dt=dt.replace(tzinfo=timezone.utc)
      return dt.astimezone(timezone.utc)
    except Exception:return None


def _age_ms(value,observed_dt):
    dt=_parse_utc(value)
    if dt is None:return None
    return max(0,int((observed_dt-dt).total_seconds()*1000))


def _heartbeat_freshness(age_ms,interval_ms):
    if age_ms is None:return 'UNKNOWN'
    if age_ms<=int(interval_ms*LIVENESS_FRESH_MULTIPLIER):return 'FRESH'
    if age_ms<=int(interval_ms*LIVENESS_STALE_MULTIPLIER):return 'AGING'
    return 'STALE'


def _derive_liveness_state(*,mission_state,driver_state,blocking_gate,current_phase,scheduler_age_ms,driver_age_ms,interval_ms):
    stale=int(interval_ms*LIVENESS_STALE_MULTIPLIER)
    if mission_state=='COMPLETE' or driver_state=='COMPLETE':return ('COMPLETE','Mission and driver are terminal.')
    if mission_state=='FAILED' or driver_state=='FAILED':return ('FAILED','Mission or driver is failed.')
    if driver_state in {'PAUSED','BOOTSTRAP_PAUSED','STOPPED'}:return ('PAUSED','Driver is operator-contained and will not auto-resume.')
    if scheduler_age_ms is None or scheduler_age_ms>stale:return ('STALE','Global scheduler heartbeat is stale or unavailable.')
    if driver_state=='ACTIVE':
      if driver_age_ms is None or driver_age_ms>stale:return ('STALE','Active driver heartbeat is stale or unavailable.')
      if current_phase:return ('EXECUTING','Scheduler and active driver heartbeats are fresh.')
      return ('IDLE_HEALTHY','Scheduler and driver are live but no executable phase is active.')
    if driver_state=='WAITING':
      return ('WAITING_HEALTHY','Control plane is live and the driver is intentionally waiting on an explicit gate.' if blocking_gate else 'Control plane is live and the driver is waiting.')
    if driver_state=='BLOCKED':
      return ('BLOCKED_HEALTHY','Control plane is live and the driver is blocked on an explicit gate.' if blocking_gate else 'Control plane is live and the driver is blocked.')
    return ('IDLE_HEALTHY','Control plane heartbeat is fresh; no active execution is observed.')


def _project_driver_controls(driver):
    d=driver or {};state=str(d.get('state') or 'UNKNOWN');gate=str(d.get('blocking_gate') or '')
    def item(supported,reason,label,effect='CONTROL_STATE'):
      return {'supported':bool(supported),'reason':None if supported else reason,'label':label,'effect':effect}
    recheck=state in {'WAITING','BLOCKED'} and gate in CAPABILITY_RECHECK_BLOCKERS
    return {
      'REACQUIRE_CAPABILITIES':item(recheck,'Available only for WAITING/BLOCKED drivers on a re-evaluable dependency gate.','Recheck capability'),
      'PAUSE_AUTO_RESUME':item(state=='WAITING','Available only while the driver is WAITING.','Pause auto-resume'),
      'PAUSE':item(state in {'ACTIVE','BLOCKED'},'WAITING uses Pause auto-resume; Resume is reserved for explicit PAUSED states.','Pause driver'),
      'RESUME':item(state in {'BOOTSTRAP_PAUSED','PAUSED','STOPPED','FAILED'},'Driver is not explicitly paused/stopped/failed.','Resume driver'),
      'STOP':item(bool(state and state not in {'COMPLETE','STOPPED','UNKNOWN'}),'Driver is already terminal/stopped or unavailable.','Stop driver'),
    }


def _project_mission_liveness(c,mid,mission,process,driver,scheduler):
    observed_dt=datetime.now(timezone.utc);observed_at=observed_dt.isoformat().replace('+00:00','Z')
    interval_ms=int(MISSION_DRIVER_LOOP_INTERVAL_SECONDS*1000)
    dh=(driver or {}).get('heartbeat_at');sh=(scheduler or {}).get('heartbeat_at')
    da=_age_ms(dh,observed_dt);sa=_age_ms(sh,observed_dt)
    scheduler_freshness=_heartbeat_freshness(sa,interval_ms);driver_freshness=_heartbeat_freshness(da,interval_ms)
    state,reason=_derive_liveness_state(mission_state=str((mission or {}).get('state') or 'UNKNOWN'),driver_state=str((driver or {}).get('state') or 'UNKNOWN'),blocking_gate=(driver or {}).get('blocking_gate'),current_phase=(process or {}).get('current_phase'),scheduler_age_ms=sa,driver_age_ms=da,interval_ms=interval_ms)
    def one(sql):
      try:
       r=c.execute(sql,(mid,)).fetchone();return r[0] if r and r[0] else None
      except sqlite3.OperationalError:return None
    last_assignment=one("SELECT MAX(created_at) FROM mission_execution_assignments WHERE mission_id=? AND phase_id!='__TOPOLOGY__'")
    last_receipt=one('SELECT MAX(observed_at) FROM mission_execution_receipts WHERE mission_id=?')
    last_event=one('SELECT MAX(observed_at) FROM protocol_messages WHERE mission_id=?')
    last_phase=one('SELECT MAX(updated_at) FROM mission_phases WHERE mission_id=?')
    current_phase=(process or {}).get('current_phase')
    wait_started=None
    if current_phase:
      try:
       r=c.execute("SELECT updated_at FROM mission_phases WHERE mission_id=? AND phase_id=? AND status IN ('WAITING','BLOCKED')",(mid,current_phase)).fetchone();wait_started=r[0] if r else None
      except sqlite3.OperationalError:pass
    ages=[x for x in (sa,da) if x is not None]
    freshness='STALE' if state=='STALE' else ('AGING' if scheduler_freshness=='AGING' or (state=='EXECUTING' and driver_freshness=='AGING') else 'FRESH')
    return {
      'state':state,'reason':reason,'observed_at':observed_at,
      'driver_heartbeat_at':dh,'driver_heartbeat_age_ms':da,'driver_heartbeat_freshness':driver_freshness,
      'scheduler_heartbeat_at':sh,'scheduler_heartbeat_age_ms':sa,'scheduler_heartbeat_freshness':scheduler_freshness,
      'heartbeat_interval_ms':interval_ms,'freshness':freshness,
      'last_assignment_at':last_assignment,'last_receipt_at':last_receipt,'last_event_at':last_event,
      'last_phase_transition_at':last_phase,'last_progress_change_at':(process or {}).get('updated_at'),
      'wait_started_at':wait_started,'auto_resume_armed':str((driver or {}).get('state') or '') in {'WAITING','BLOCKED'},
      'blocking_gate':(driver or {}).get('blocking_gate'),'next_action':(driver or {}).get('next_action'),
      'current_phase':current_phase,'source_revision':None,
    }


def process_snapshot(mid, *, read_only=False, _connection=None):
    if _connection is not None and not read_only:raise ValueError('shared snapshot must be read only')
    c=_connection if _connection is not None else connect()
    if not read_only:
      lifecycle_sync_components(c,mid,now)
      c.commit()
    if _connection is None:c.execute('BEGIN')
    m=c.execute('SELECT * FROM missions WHERE mission_id=?',(mid,)).fetchone()
    if not m:
      if _connection is None:c.close()
      raise ValueError('mission not found')
    d=dict(m);s=c.execute('SELECT * FROM mission_process_specs WHERE mission_id=?',(mid,)).fetchone();d['process']=dict(s) if s else None
    if d['process']:
      try:d['process']['protocols']=json.loads(d['process'].pop('protocols_json'))
      except Exception:d['process']['protocols']=[]
      d['process'].pop('lpcl_text',None)
    d['phases']=[dict(r) for r in c.execute('SELECT * FROM mission_phases WHERE mission_id=? ORDER BY ordinal',(mid,))]
    d['phase_execution_specs']=[dict(r) for r in c.execute('SELECT * FROM mission_phase_execution_specs WHERE mission_id=? ORDER BY phase_id',(mid,))]
    d['phase_execution_contracts']=[global_sched.phase_execution_contract(c,mid,r['phase_id']) for r in c.execute('SELECT phase_id FROM mission_phases WHERE mission_id=? ORDER BY ordinal',(mid,)).fetchall() if global_sched.phase_execution_contract(c,mid,r['phase_id'])]
    d['phase_capability_bindings']=global_sched.phase_capability_bindings(c,mid)
    d['execution_preflight']=global_sched.execution_preflight(c,mid)
    d['phase_evidence_counts']={r['phase']:r['total'] for r in c.execute("SELECT phase,COUNT(*) AS total FROM protocol_messages WHERE mission_id=? AND protocol IN ('EVIDENCE','VALIDATION','RECEIPT') GROUP BY phase",(mid,))}
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
    elif d.get('adapter')==LPCL_GENERIC_ADAPTER:d['control_authority']='BOUNDED_GENERIC_LPCL_EXECUTION_ADAPTER'
    elif mid==LPCL_REBIND_SOURCE:d['control_authority']='BOUNDED_EPOCH3_MATERIAL_ADAPTER'
    else:d['control_authority']='ACTIVATED_NO_EFFECT_ADAPTER' if d['state'] in {'AUTHORIZED','RUNNING'} else 'NONE'
    d=lifecycle_decorate(c,d,current_mission_id=MISSION,rebound_adapter=LPCL_REBIND_ADAPTER)
    d['execution_driver']=driver_snapshot(c,mid)
    d['scheduler']=global_sched.scheduler_snapshot(c)
    d['execution_assignments']=[dict(r) for r in c.execute('SELECT assignment_id,mission_id,phase_id,logical_drone_id,material_drone_id,input_digest,state,lease_generation,created_at,claimed_at,finished_at FROM mission_execution_assignments WHERE mission_id=? ORDER BY created_at DESC,assignment_id LIMIT 100',(mid,))]
    d['execution_receipts']=[dict(r) for r in c.execute('SELECT r.*,a.material_drone_id,a.logical_drone_id FROM mission_execution_receipts r JOIN mission_execution_assignments a ON a.assignment_id=r.assignment_id WHERE r.mission_id=? ORDER BY r.observed_at DESC,r.receipt_id LIMIT 100',(mid,))]
    d['execution_history_window']={'assignments':100,'receipts':100,'order':'NEWEST_FIRST','payloads':'DIGEST_PLUS_BOUNDED_RESULT_STORE'}
    try:d['generic_phase_plans']=[dict(r) for r in c.execute('SELECT * FROM mission_generic_phase_plans WHERE mission_id=? ORDER BY created_at,plan_id',(mid,))]
    except sqlite3.OperationalError:d['generic_phase_plans']=[]
    try:d['generic_action_receipts']=[dict(r) for r in c.execute('SELECT * FROM mission_generic_action_receipts WHERE mission_id=? ORDER BY observed_at,receipt_id',(mid,))]
    except sqlite3.OperationalError:d['generic_action_receipts']=[]
    try:d['mission_artifacts']=[{k:v for k,v in art.items() if k!='content_json' and k!='content'} for art in global_sched.list_artifacts(c,mid)]
    except sqlite3.OperationalError:d['mission_artifacts']=[]
    try:d['recon_material_leases']=[dict(r) for r in c.execute('SELECT * FROM mission_recon_material_leases WHERE mission_id=? ORDER BY acquired_at,material_drone_id',(mid,))]
    except sqlite3.OperationalError:d['recon_material_leases']=[]
    try:d['recon_trajectories']=[dict(r) for r in c.execute('SELECT * FROM mission_recon_trajectories WHERE mission_id=? ORDER BY created_at,trajectory_role',(mid,))]
    except sqlite3.OperationalError:d['recon_trajectories']=[]
    try:d['recon_saas_advisories']=[dict(r) for r in c.execute('SELECT * FROM mission_recon_saas_advisories WHERE mission_id=? ORDER BY created_at,advisory_id',(mid,))]
    except sqlite3.OperationalError:d['recon_saas_advisories']=[]
    try:d['execution_assignment_count']=int(c.execute('SELECT COUNT(*) FROM mission_execution_assignments WHERE mission_id=?',(mid,)).fetchone()[0]);d['execution_receipt_count']=int(c.execute('SELECT COUNT(*) FROM mission_execution_receipts WHERE mission_id=?',(mid,)).fetchone()[0])
    except sqlite3.OperationalError:d['execution_assignment_count']=0;d['execution_receipt_count']=0
    try:d['revision_compilations']=[dict(x) for x in c.execute('SELECT revision_id,successor_mission_id,lpcl_digest,state,created_at,activated_at FROM mission_revision_compilations WHERE mission_id=? ORDER BY created_at DESC LIMIT 20',(mid,))]
    except sqlite3.OperationalError:d['revision_compilations']=[]
    try:d['adaptive_worker_plan']=driver_adaptive_worker_plan(c,mid,preferred_roles=('LD01','LD02','LD10','LD11'),limit=16) if int(d.get('ready') or 0)==64 else None
    except Exception:d['adaptive_worker_plan']=None
    liveness=_project_mission_liveness(c,mid,d,d.get('process') or {},d.get('execution_driver') or {},d.get('scheduler') or {})
    controls=_project_driver_controls(d.get('execution_driver'))
    if _connection is None:c.commit()
    out=normalize_snapshot(d);liveness['source_revision']=out.get('projection_revision');out['liveness']=liveness;out['driver_controls']=controls
    if _connection is None:c.close()
    return out

def set_focus_mission(mid, request):
    if type(request) is not dict or request:raise ValueError('focus request must be empty object')
    if not isinstance(mid,str) or not mid or '/' in mid:raise ValueError('mission id')
    c=connect()
    try:
      c.execute('BEGIN IMMEDIATE')
      if not c.execute('SELECT 1 FROM missions WHERE mission_id=?',(mid,)).fetchone():raise ValueError('mission not found')
      previous=c.execute("SELECT value FROM mission_meta WHERE key='focus_mission_id'").fetchone()
      changed=previous is None or previous['value']!=mid
      receipt=None
      if changed:
        stamp=now();rid='action-'+uuid.uuid4().hex
        result={'previous_focus_mission_id':previous['value'] if previous else None,'focus_mission_id':mid,'authority_effect':'NONE','metadata_only':True}
        payload={'receipt_id':rid,'mission_id':mid,'action':'FOCUS','effect_class':'CONTROL_DB_METADATA_ONLY','status':'PASS','request':{},'result':result,'created_at':stamp}
        dg=_payload_digest(payload)
        c.execute('INSERT INTO mission_meta(key,value,updated_at) VALUES(?,?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value,updated_at=excluded.updated_at',('focus_mission_id',mid,stamp))
        c.execute('INSERT INTO mission_events(mission_id,observed_at,event_type,payload_json) VALUES(?,?,?,?)',(mid,stamp,'FOCUS_CHANGED',json.dumps(result,sort_keys=True)))
        c.execute('INSERT INTO mission_action_receipts VALUES(?,?,?,?,?,?,?,?,?)',(rid,mid,'FOCUS','CONTROL_DB_METADATA_ONLY','PASS','{}',json.dumps(result,sort_keys=True),dg,stamp))
        receipt={'receipt_id':rid,'receipt_digest':dg}
      focus=c.execute("SELECT value FROM mission_meta WHERE key='focus_mission_id'").fetchone()['value']
      readback=process_snapshot(focus,read_only=True,_connection=c)
      c.commit()
      return {'focus_mission_id':focus,'changed':changed,'authority_effect':'NONE','receipt':receipt,'readback':readback}
    except Exception:
      c.rollback();raise
    finally:c.close()

def _view_name(value):
    view=str(value or 'operational').lower()
    if view not in {'operational','history','all'}:raise ValueError('mission view')
    return view


def _classification_matches_view(classification, view):
    if view=='all':return True
    if view=='operational':return bool(classification.get('operational'))
    return bool(classification.get('historical'))


def focus_mission_id(view='operational'):
    view=_view_name(view);c=connect()
    try:
      r=c.execute("SELECT m.mission_id FROM missions m JOIN mission_meta f ON f.value=m.mission_id WHERE f.key='focus_mission_id'").fetchone()
      if r is not None:
        try:
          if _classification_matches_view(mission_lifecycle_classification(c,r[0]),view):return r[0]
        except ValueError:pass
      for candidate in c.execute('SELECT mission_id FROM missions ORDER BY updated_at DESC,mission_id'):
        try:
          if _classification_matches_view(mission_lifecycle_classification(c,candidate['mission_id']),view):return candidate['mission_id']
        except ValueError:continue
      return None
    finally:c.close()

RECENT_PROJECTION_LOCK=threading.Lock()
RECENT_PROJECTION_PENDING={}


def recent_process_missions(view='operational'):
    view=_view_name(view)
    global RECENT_PROJECTION_PENDING
    with RECENT_PROJECTION_LOCK:
      leader=view not in RECENT_PROJECTION_PENDING
      if leader:RECENT_PROJECTION_PENDING[view]=Future()
      pending=RECENT_PROJECTION_PENDING[view]
    if leader:
      try:pending.set_result(_read_recent_process_missions(view))
      except BaseException as error:pending.set_exception(error)
      finally:
        with RECENT_PROJECTION_LOCK:RECENT_PROJECTION_PENDING.pop(view,None)
    return deepcopy(pending.result())


def _read_recent_process_missions(view='operational'):
    view=_view_name(view);c=connect()
    try:mids=[r['mission_id'] for r in c.execute('SELECT mission_id FROM missions ORDER BY updated_at DESC LIMIT 60')]
    finally:c.close()
    rows=[]
    for mid in mids:
      try:
        snap=process_snapshot(mid,read_only=True);classification=snap.get('lifecycle') or {}
        if not _classification_matches_view(classification,view):continue
        summary=dict(snap['mission_summary']);summary.update({k:classification.get(k) for k in ('lifecycle_class','record_class','operational','historical','legacy','execution_controls_allowed','history_reason')});rows.append(summary)
      except ValueError as error:
        if str(error)!='mission not found':raise
    return rows


def execute_epoch3_lifecycle_normalization(x):
    if type(x) is not dict or set(x)!={'task_mission_id','task_lpcl_digest','source_head','source_tree'}:raise ValueError('lifecycle normalization schema')
    if x['task_mission_id']!=EPOCH3_LIFECYCLE_TASK or x['task_lpcl_digest']!=EPOCH3_LIFECYCLE_TASK_DIGEST:raise ValueError('lifecycle normalization authority identity')
    if not _hex(x['source_head'],40) or not _hex(x['source_tree'],40):raise ValueError('source identity')
    c=connect()
    try:
      task=c.execute('SELECT state,spec_digest FROM missions WHERE mission_id=?',(EPOCH3_LIFECYCLE_TASK,)).fetchone();process=c.execute('SELECT authority_state FROM mission_process_specs WHERE mission_id=?',(EPOCH3_LIFECYCLE_TASK,)).fetchone()
      if task is None or task['spec_digest']!=EPOCH3_LIFECYCLE_TASK_DIGEST or task['state'] not in {'AUTHORIZED','RUNNING','WAITING','BLOCKED'} or process is None or process['authority_state']!='EXPLICIT_USER_ACTIVATION':raise ValueError('lifecycle task not explicitly activated')
      return normalize_epoch3_terminal_lifecycle(c,target_1_mission_id=EPOCH3_LIFECYCLE_TARGET_1,target_1_expected_spec_digest=EPOCH3_LIFECYCLE_TARGET_1_DIGEST,target_2_mission_id=EPOCH3_LIFECYCLE_TARGET_2,target_2_expected_spec_digest=EPOCH3_LIFECYCLE_TARGET_2_DIGEST,successor_mission_id=EPOCH3_LIFECYCLE_SUCCESSOR,expected_current_head=x['source_head'],expected_current_tree=x['source_tree'],now_fn=now)
    finally:c.close()

# ---- end LPCL mission process extension v1 -------------------------------




SELF_HOSTING_MISSION='EPOCH3-CONTROL-PLANE-AUTONOMY-RECOVERY-SELF-HOSTING-R1'
SELF_HOSTED_PHASES=('SELF_HOSTING_TAKEOVER','LIVE_AUTONOMY_CANARY','PARENT_MISSION_RECONCILIATION','PR337_FAST_FORWARD_AND_GREEN_EXACT_HEAD_CI','READY_FOR_SYSTEM_ACCEPTANCE_TESTS')
PHASE_HANDLER_REGISTRY={
 'SELF_HOSTING_TAKEOVER':'SELF_HOSTING_TAKEOVER',
 'LIVE_AUTONOMY_CANARY':'LIVE_AUTONOMY_CANARY',
 'PARENT_MISSION_RECONCILIATION':'PARENT_MISSION_RECONCILIATION',
 'PR337_FAST_FORWARD_AND_GREEN_EXACT_HEAD_CI':'GITHUB_EXACT_HEAD_GATE',
 'READY_FOR_SYSTEM_ACCEPTANCE_TESTS':'TERMINAL_READINESS',
}
PHASE_HANDLER_AUTHORITY={k:'BOUNDED_EXACT_HANDLER' for k in PHASE_HANDLER_REGISTRY}
DRIVER_STOP=threading.Event()
DRIVER_PROCESS_ID=f'{socket.gethostname()}:{os.getpid()}:{uuid.uuid4().hex}'


def _mission_lpcl_kv(c,mid):
    r=c.execute('SELECT lpcl_text FROM mission_process_specs WHERE mission_id=?',(mid,)).fetchone()
    return _lpcl_pairs(r['lpcl_text']) if r and r['lpcl_text'] else {}


def _recompute_process(c,mid):
    rows=c.execute('SELECT ordinal,phase_id,status,progress FROM mission_phases WHERE mission_id=? ORDER BY ordinal',(mid,)).fetchall()
    overall=sum(float(r['progress']) for r in rows)/max(1,len(rows))
    current=next((r['phase_id'] for r in rows if r['status'] in {'RUNNING','WAITING','BLOCKED'}),None)
    if current is None:
      nxt=next((r['phase_id'] for r in rows if r['status'] in {'PENDING','READY'}),None)
      current=nxt
      if nxt:
       c.execute("UPDATE mission_phases SET status='RUNNING',started_at=COALESCE(started_at,?),updated_at=? WHERE mission_id=? AND phase_id=?",(now(),now(),mid,nxt))
    c.execute('UPDATE mission_process_specs SET current_phase=?,progress=?,updated_at=? WHERE mission_id=?',(current,overall,now(),mid))
    return current,overall


def _driver_phase_result(c,mid,pid,status,detail,payload,protocol='VALIDATION'):
    t=now();progress=100.0 if status in {'PASS','COMPLETE','SKIPPED'} else 0.0
    finished=t if status in {'PASS','COMPLETE','SKIPPED','FAIL','CANCELLED'} else None
    c.execute('UPDATE mission_phases SET status=?,progress=?,detail=?,started_at=COALESCE(started_at,?),finished_at=?,updated_at=? WHERE mission_id=? AND phase_id=?',(status,progress,str(detail)[:4000],t,finished,t,mid,pid))
    _process_message(c,mid,protocol,'MISSION_EXECUTION_DRIVER','MISSION_CONTROL',pid,payload,'INTERNAL')
    current,overall=_recompute_process(c,mid)
    life='COMPLETE' if current is None and status in {'PASS','COMPLETE','SKIPPED'} else ('FAILED' if status=='FAIL' else ('WAITING' if status=='WAITING' else ('BLOCKED' if status=='BLOCKED' else 'RUNNING')))
    c.execute('UPDATE missions SET state=?,runtime_state=?,updated_at=? WHERE mission_id=?',(life,'DRIVER_'+life,t,mid))
    # Phase advancement is part of the durable driver transaction. Without this
    # commit the attempt receipt can be durable while mission_phases rolls back,
    # causing an infinite replay of an already-PASS attempt.
    c.commit()
    return current,overall


def _http_json(url,timeout=10):
    req=urllib.request.Request(url,headers={'User-Agent':'LION-MISSION-DRIVER/1','Accept':'application/vnd.github+json'})
    with urllib.request.urlopen(req,timeout=timeout) as r:return json.load(r)


def _github_pr_state():
    pr=_http_json('https://api.github.com/repos/DonkeyJJLove/ai_platform/pulls/337')
    head=((pr.get('head') or {}).get('sha'));base=((pr.get('base') or {}).get('sha'))
    if not _hex(head,40) or not _hex(base,40):raise ValueError('GitHub PR identity is not an exact SHA-1')
    # Keep the outbound request target fully static.  The PR head is external
    # observation data and is used only for local exact-head filtering, never
    # interpolated back into a network URL (SSRF/target-substitution boundary).
    runs=_http_json('https://api.github.com/repos/DonkeyJJLove/ai_platform/actions/runs?event=pull_request&per_page=50')
    rr=[{'name':x.get('name'),'status':x.get('status'),'conclusion':x.get('conclusion'),'head_sha':x.get('head_sha'),'id':x.get('id')} for x in runs.get('workflow_runs',[]) if x.get('head_sha')==head]
    return {'state':pr.get('state'),'merged':pr.get('merged'),'head':head,'base':base,'mergeable':pr.get('mergeable'),'runs':rr}


def _all_required_ci_green(v):
    names={r['name']:r for r in v.get('runs',[]) if r.get('head_sha')==v.get('head')}
    required=('Bandit Security Scan','LION R22C Full Symbol Census','Cyber-Lion Core')
    return all(names.get(n,{}).get('status')=='completed' and names.get(n,{}).get('conclusion')=='success' for n in required),names


def _connector_github_gate(c,mid,pid,max_age_seconds=900):
    required=('Bandit Security Scan','LION R22C Full Symbol Census','Cyber-Lion Core')
    rows=c.execute("SELECT observed_at,payload_json,payload_digest FROM protocol_messages WHERE mission_id=? AND protocol='GITHUB' AND from_id='CHATGPT_SAAS_SUPERVISOR' AND phase=? ORDER BY id DESC LIMIT 20",(mid,pid)).fetchall()
    stamp=datetime.now(timezone.utc)
    for row in rows:
      try: payload=json.loads(row['payload_json'])
      except Exception: continue
      if payload.get('event')!='GITHUB_EXACT_HEAD_CI_RECEIPT' or payload.get('authority_effect')!='NONE' or payload.get('source')!='GITHUB_CONNECTOR': continue
      head=str(payload.get('head') or '')
      if not _hex(head,40): continue
      try:
       observed=datetime.fromisoformat(str(row['observed_at']).replace('Z','+00:00'))
       if (stamp-observed).total_seconds()>max_age_seconds: continue
      except Exception: continue
      workflows=payload.get('workflows') or {}
      if set(workflows)!=set(required): continue
      runs=[]
      valid=True
      for name in required:
       item=workflows.get(name) or {}
       if item.get('head_sha')!=head or item.get('status')!='completed' or item.get('conclusion')!='success': valid=False
       runs.append({'name':name,'status':item.get('status'),'conclusion':item.get('conclusion'),'head_sha':item.get('head_sha'),'id':item.get('run_id')})
      if valid:
       return {'state':'open','merged':False,'head':head,'base':payload.get('base'),'mergeable':payload.get('mergeable'),'runs':runs,'connector_payload_digest':row['payload_digest'],'connector_observed_at':row['observed_at']}
    return None


def _terminal_github_state(c,mid):
    receipt=_connector_github_gate(c,mid,'PR337_FAST_FORWARD_AND_GREEN_EXACT_HEAD_CI',max_age_seconds=3600)
    return receipt if receipt is not None else _github_pr_state()


def _local_health(port,path='/health'):
    try:
      with urllib.request.urlopen(f'http://127.0.0.1:{port}{path}',timeout=3) as r:return {'ok':r.status==200,'status':r.status}
    except Exception as e:return {'ok':False,'error':type(e).__name__+':'+str(e)[:300]}


def drive_self_hosted_once(mid=SELF_HOSTING_MISSION):
    c=connect()
    try:
      ds=driver_snapshot(c,mid)
      if not ds or ds['state'] not in {'ACTIVE','WAITING','BLOCKED'}:return
      row=c.execute("SELECT phase_id,status FROM mission_phases WHERE mission_id=? AND status NOT IN ('PASS','COMPLETE','SKIPPED','CANCELLED') ORDER BY ordinal LIMIT 1",(mid,)).fetchone()
      if not row:
       driver_transition(c,mid,'COMPLETE',now,next_action='SYSTEM_ACCEPTANCE_TESTS');c.execute("UPDATE missions SET state='COMPLETE',runtime_state='DRIVER_COMPLETE',updated_at=? WHERE mission_id=?",(now(),mid));c.commit();return
      pid=row['phase_id']
      if pid not in SELF_HOSTED_PHASES:
       driver_heartbeat(c,mid,now,phase=pid,next_action='BOOTSTRAP_PHASE_NOT_DRIVER_OWNED',owner_id=DRIVER_PROCESS_ID);return
      if ds['state'] in {'WAITING','BLOCKED'}:
       # Gate phases are re-evaluated on each loop; legal transition back to ACTIVE.
       driver_transition(c,mid,'ACTIVE',now,current_phase=pid,next_action='REEVALUATE_GATE')
      driver_heartbeat(c,mid,now,phase=pid,next_action='EXECUTE_'+pid,owner_id=DRIVER_PROCESS_ID)
      attempt=driver_begin_attempt(c,mid,pid,now,preconditions={'mission_id':mid,'phase':pid},owner_id=DRIVER_PROCESS_ID)
      if pid=='SELF_HOSTING_TAKEOVER':
       kv=_mission_lpcl_kv(c,mid);parent=kv.get('PARENT_MISSION_ID')
       p=c.execute('SELECT state,materialized,ready FROM missions WHERE mission_id=?',(parent,)).fetchone()
       cu=sorted(r['pod_uid'] for r in c.execute('SELECT pod_uid FROM material_workers WHERE mission_id=? AND pod_uid IS NOT NULL',(mid,)))
       pu=sorted(r['pod_uid'] for r in c.execute('SELECT pod_uid FROM material_workers WHERE mission_id=? AND pod_uid IS NOT NULL',(parent,))) if parent else []
       evidence={'parent':parent,'parent_state':dict(p) if p else None,'child_uid_count':len(cu),'parent_uid_count':len(pu),'uids_equal':cu==pu,'driver_generation':driver_snapshot(c,mid)['generation']}
       if not p or p['ready']!=64 or len(cu)!=64 or cu!=pu:
        driver_finish_attempt(c,attempt,now,state='BLOCKED',evidence=evidence,detail='Parent/child material identity not reconciled')
        _driver_phase_result(c,mid,pid,'BLOCKED','Self-hosting blocked: exact parent 64-worker identities do not match child binding.',evidence,'RECOVERY')
        driver_transition(c,mid,'BLOCKED',now,blocking_gate='M64_PARENT_CHILD_IDENTITY',waiting_reason='Exact 64-worker parent/child binding mismatch',next_action='RECONCILE_DYNAMIC_PARENT_REBIND',current_phase=pid);return
       driver_finish_attempt(c,attempt,now,state='PASS',evidence=evidence,detail='Self-hosting takeover proved')
       _driver_phase_result(c,mid,pid,'PASS','Durable driver is active and child binding matches the exact current parent 64-worker identity set.',{'event':'SELF_HOSTING_TAKEOVER_COMPLETE',**evidence},'RECEIPT')
       return
      if pid=='LIVE_AUTONOMY_CANARY':
       # Durable canary waits for one real SaaS response. Create once.
       existing=c.execute("SELECT request_id,status FROM saas_handoff_requests WHERE mission_id=? AND question_digest=? ORDER BY created_at DESC LIMIT 1",(mid,hashlib.sha256(b'LION SELF HOSTING CANARY: respond with SAAS_CANARY_OK and no authority effect.').hexdigest())).fetchone()
       if not existing:
        out=saas_create(c,mid,'LION SELF HOSTING CANARY: respond with SAAS_CANARY_OK and no authority effect.',now,ttl_seconds=3600)
        _process_message(c,mid,'ASSIGNMENT','MISSION_EXECUTION_DRIVER','CHATGPT_SAAS_SUPERVISOR',pid,{'event':'SELF_HOSTING_SAAS_CANARY_REQUESTED','request_id':out['request_id'],'request_code':out['request_code'],'authority_effect':'NONE'},'OUT');c.commit();existing={'request_id':out['request_id'],'status':'PENDING'}
       sr=c.execute('SELECT status,response_digest,receipt_digest FROM saas_handoff_requests WHERE request_id=?',(existing['request_id'],)).fetchone()
       # The local model is Windows-loopback scoped. WSL Mission Control must not
       # infer 127.0.0.1:8772 reachability. The Windows LPCL runtime performs the
       # actual LOCAL canary and posts a digest-bound EVIDENCE receipt here.
       lr=None
       for msg in c.execute("SELECT observed_at,payload_json,payload_digest FROM protocol_messages WHERE mission_id=? AND protocol='EVIDENCE' AND from_id='LPCL_PANEL' AND phase=? ORDER BY id DESC LIMIT 20",(mid,pid)).fetchall():
        try:
         payload=json.loads(msg['payload_json'])
        except Exception:
         payload={}
        if payload.get('event')=='LOCAL_MODEL_CANARY_PASS' and payload.get('model')=='gpt-oss-20b-MXFP4' and payload.get('authority_effect')=='NONE':
         lr={'observed_at':msg['observed_at'],'payload_digest':msg['payload_digest'],'response_digest':payload.get('response_digest')}
         break
       local_ok=bool(lr and lr.get('response_digest'))
       evidence={'request_id':existing['request_id'],'saas_status':sr['status'] if sr else 'UNKNOWN','local_ok':local_ok,'local_receipt':lr}
       if not sr or sr['status']!='RESPONDED' or not local_ok:
        driver_finish_attempt(c,attempt,now,state='WAITING',evidence=evidence,detail='Waiting for real SaaS and Windows-local model receipts')
        _driver_phase_result(c,mid,pid,'WAITING','Live autonomy canary waiting for real SaaS receipt and Windows-local model receipt.',evidence,'HEARTBEAT')
        missing=[]
        if not sr or sr['status']!='RESPONDED': missing.append('SAAS_RESPONSE_RECEIPT')
        if not local_ok: missing.append('LOCAL_MODEL_RECEIPT')
        driver_transition(c,mid,'WAITING',now,blocking_gate='+'.join(missing),waiting_reason='Waiting for '+', '.join(missing),next_action='WAIT_FOR_CANARY_RECEIPTS',current_phase=pid);return
       evidence.update({'saas_response_digest':sr['response_digest'],'saas_receipt_digest':sr['receipt_digest']})
       driver_finish_attempt(c,attempt,now,state='PASS',evidence=evidence,detail='Live autonomy canary passed')
       _driver_phase_result(c,mid,pid,'PASS','LOCAL canary and operator-mediated SaaS receipt both observed by durable driver.',{'event':'LIVE_AUTONOMY_CANARY_PASS',**evidence},'VALIDATION');return
      if pid=='PARENT_MISSION_RECONCILIATION':
       kv=_mission_lpcl_kv(c,mid);parent=kv.get('PARENT_MISSION_ID');ds2=driver_snapshot(c,mid)
       if not parent or not ds2 or not ds2.get('heartbeat_at'):
        raise ValueError('parent/driver evidence missing')
       t=now();c.execute("UPDATE missions SET state='SUPERSEDED',runtime_state=?,updated_at=? WHERE mission_id=?",('REBOUND_TO:'+mid,t,parent));c.execute("UPDATE mission_process_specs SET current_phase=NULL,authority_state='SUPERSEDED_BY_EXACT_LPCL',updated_at=? WHERE mission_id=?",(t,parent))
       evidence={'parent':parent,'child':mid,'driver_generation':ds2['generation'],'heartbeat_at':ds2['heartbeat_at']}
       driver_finish_attempt(c,attempt,now,state='PASS',evidence=evidence,detail='Parent lineage reconciled')
       _driver_phase_result(c,mid,pid,'PASS','Parent mission reconciled only after live child driver heartbeat and exact material rebind.',{'event':'PARENT_MISSION_RECONCILED',**evidence},'RECOVERY');return
      if pid=='PR337_FAST_FORWARD_AND_GREEN_EXACT_HEAD_CI':
       g=_connector_github_gate(c,mid,pid)
       if g is None:
        try:
         g=_github_pr_state()
        except urllib.error.HTTPError as exc:
         if exc.code==403:
          evidence={'source':'GITHUB_PUBLIC_API','http_status':403,'rate_limited':True,'connector_receipt':False}
          driver_finish_attempt(c,attempt,now,state='WAITING',evidence=evidence,detail='GitHub public API rate limited; waiting for connector receipt or rate reset')
          _driver_phase_result(c,mid,pid,'WAITING','GitHub currentness rate-limited; exact connector receipt is accepted as bounded read-only fallback.',evidence,'GITHUB')
          driver_transition(c,mid,'WAITING',now,blocking_gate='GITHUB_CONNECTOR_OR_RATE_RESET',waiting_reason='GitHub public API rate limit exhausted',next_action='WAIT_FOR_EXACT_GITHUB_RECEIPT',current_phase=pid);return
         raise
       green,names=_all_required_ci_green(g);driver_observe_gate(c,mid,pid,'GITHUB_PR337_EXACT_HEAD_CI','PASS' if green else 'WAITING',g,now)
       evidence={'head':g['head'],'base':g['base'],'mergeable':g['mergeable'],'required':{k:{'status':v.get('status'),'conclusion':v.get('conclusion')} for k,v in names.items()}}
       if not green:
        driver_finish_attempt(c,attempt,now,state='WAITING',evidence=evidence,detail='Exact-head CI not green')
        _driver_phase_result(c,mid,pid,'WAITING','Waiting for all required GitHub workflows to be green on exact PR337 head.',evidence,'GITHUB')
        driver_transition(c,mid,'WAITING',now,blocking_gate='GITHUB_PR337_EXACT_HEAD_CI',waiting_reason='Required exact-head CI is not yet all green',next_action='POLL_GITHUB_CI',current_phase=pid);return
       driver_finish_attempt(c,attempt,now,state='PASS',evidence=evidence,detail='Exact-head CI green')
       _driver_phase_result(c,mid,pid,'PASS','All required workflows green on exact current PR337 head; no merge performed.',{'event':'PR337_EXACT_HEAD_CI_GREEN',**evidence},'GITHUB');return
      if pid=='READY_FOR_SYSTEM_ACCEPTANCE_TESTS':
       # Reuse the fresh, exact-head, read-only connector receipt accepted by
       # the immediately preceding GitHub gate.  This keeps terminal readiness
       # restart-safe when the unauthenticated public API is rate-limited.
       try:g=_terminal_github_state(c,mid)
       except urllib.error.HTTPError as exc:
        if exc.code==403:
         evidence={'source':'GITHUB_PUBLIC_API','http_status':403,'rate_limited':True,'connector_receipt':False}
         driver_finish_attempt(c,attempt,now,state='WAITING',evidence=evidence,detail='Terminal currentness waiting for connector receipt or GitHub rate reset')
         _driver_phase_result(c,mid,pid,'WAITING','Terminal readiness currentness is rate-limited; waiting for bounded exact-head connector evidence.',evidence,'GITHUB')
         driver_transition(c,mid,'WAITING',now,blocking_gate='GITHUB_CONNECTOR_OR_RATE_RESET',waiting_reason='GitHub public API rate limit exhausted',next_action='WAIT_FOR_EXACT_GITHUB_RECEIPT',current_phase=pid);return
        raise
       green,_=_all_required_ci_green(g);m=c.execute('SELECT materialized,ready FROM missions WHERE mission_id=?',(mid,)).fetchone();integrity=c.execute('PRAGMA integrity_check').fetchone()[0]
       health={'8766':_local_health(8766)}
       win=None
       for msg in c.execute("SELECT payload_json,payload_digest,observed_at FROM protocol_messages WHERE mission_id=? AND protocol='EVIDENCE' AND from_id='LPCL_PANEL' AND phase=? ORDER BY id DESC LIMIT 20",(mid,pid)).fetchall():
        try: payload=json.loads(msg['payload_json'])
        except Exception: payload={}
        if payload.get('event')=='WINDOWS_CONTROL_SURFACE_READBACK' and payload.get('authority_effect')=='NONE':
         win={'payload':payload,'payload_digest':msg['payload_digest'],'observed_at':msg['observed_at']};break
       windows_ok=bool(win and win['payload'].get('panel_http')==200 and win['payload'].get('model_http')==200 and int(win['payload'].get('model_count') or 0)>=1)
       evidence={'materialized':m['materialized'],'ready':m['ready'],'db_integrity':integrity,'github_head':g['head'],'github_green':green,'health':health,'windows_control_surface_readback':win,'driver_heartbeat':driver_snapshot(c,mid).get('heartbeat_at')}
       if m['ready']!=64 or integrity!='ok' or not green or not health['8766']['ok'] or not windows_ok:
        driver_finish_attempt(c,attempt,now,state='BLOCKED',evidence=evidence,detail='Terminal readback incomplete')
        _driver_phase_result(c,mid,pid,'BLOCKED','Terminal readiness evidence incomplete.',evidence,'VALIDATION');driver_transition(c,mid,'BLOCKED',now,blocking_gate='SYSTEM_ACCEPTANCE_START_VECTOR',waiting_reason='Terminal system readback incomplete',next_action='REACQUIRE_TERMINAL_CURRENTNESS',current_phase=pid);return
       driver_finish_attempt(c,attempt,now,state='PASS',evidence=evidence,detail='Ready for system acceptance tests')
       _driver_phase_result(c,mid,pid,'PASS','Control plane, durable driver, M64, DB and exact-head CI are ready for system acceptance tests.',{'event':'READY_FOR_SYSTEM_ACCEPTANCE_TESTS',**evidence},'RECEIPT')
       driver_transition(c,mid,'COMPLETE',now,next_action='RUN_FULL_LION_SYSTEM_ACCEPTANCE_AND_AUTONOMY_TEST_CAMPAIGN',current_phase=pid)
       c.execute("UPDATE missions SET state='COMPLETE',runtime_state='DRIVER_COMPLETE',updated_at=? WHERE mission_id=?",(now(),mid));c.commit();return
    except Exception as e:
      try:
       _process_message(c,mid,'RECOVERY','MISSION_EXECUTION_DRIVER','MISSION_CONTROL',locals().get('pid'),{'event':'DRIVER_ITERATION_ERROR','error':type(e).__name__+':'+str(e)[:1200]},'INTERNAL');c.commit()
      except Exception:pass
    finally:c.close()


CONTROL_PLANE_MISSION='LION-EPOCH3-FULL-CONTROL-PLANE-PANEL-AND-AUTONOMOUS-RUN-DISPATCHER-128L64M-R1'
CONTROL_PLANE_EARLY_HANDLERS={
 'EXACT_128L64M_TOPOLOGY_BIND',
 'DATABASE_AND_SCHEDULER_SCHEMA_MIGRATION',
 'GLOBAL_MULTI_RUN_DISPATCHER',
 'PER_MISSION_LEASE_AND_FAIRNESS',
 'PHASE_EXECUTION_PLAN_COMPILER',
 'DRIVER_LIFECYCLE_NORMALIZATION',
 'UNKNOWN_HANDLER_FAIL_CLOSED',
}


def _phase_exec_spec(c,mid,pid):
    try:
      row=c.execute('SELECT * FROM mission_phase_execution_specs WHERE mission_id=? AND phase_id=?',(mid,pid)).fetchone()
      return dict(row) if row else None
    except sqlite3.OperationalError:return None


def _normalize_complete_driver(c,mid):
    m=c.execute('SELECT state FROM missions WHERE mission_id=?',(mid,)).fetchone()
    d=driver_snapshot(c,mid)
    if not m or not d or m['state']!='COMPLETE':return False
    terminal_next_action=d.get('next_action') if d.get('state')=='COMPLETE' and d.get('next_action') else 'TERMINAL_RECONCILED'
    result=driver_reconcile_complete(c,mid,now,next_action=terminal_next_action,commit=False)
    if result.get('idempotent'):
      c.commit();return False
    _process_message(c,mid,'RECOVERY','GLOBAL_SCHEDULER','MISSION_CONTROL',None,{'event':'MISSION_COMPLETE_DRIVER_NORMALIZED','previous_driver_state':result.get('previous_state'),'checkpoint_id':result.get('checkpoint_id'),'checkpoint_digest':result.get('checkpoint_digest'),'last_phase_id':result.get('last_phase_id'),'last_attempt_id':result.get('last_attempt_id'),'authority_effect':'CONTROL_STATE'},'INTERNAL')
    c.commit();return True


def drive_control_plane_once(mid=CONTROL_PLANE_MISSION):
    c=connect()
    try:
      m=c.execute('SELECT state,ready,materialized FROM missions WHERE mission_id=?',(mid,)).fetchone()
      ps=c.execute('SELECT authority_state,current_phase FROM mission_process_specs WHERE mission_id=?',(mid,)).fetchone()
      if not m or not ps or ps['authority_state']!='EXPLICIT_USER_ACTIVATION':return
      d=driver_snapshot(c,mid)
      if not d:return
      if d['state']=='BOOTSTRAP_PAUSED':
       d=driver_activate(c,mid,now,next_action='GLOBAL_SCHEDULER_DISPATCH',owner_id=DRIVER_PROCESS_ID,lease_seconds=30)
      elif d['state'] in {'ACTIVE','WAITING','BLOCKED'}:
       try:driver_heartbeat(c,mid,now,phase=ps['current_phase'],next_action='GLOBAL_SCHEDULER_DISPATCH',owner_id=DRIVER_PROCESS_ID,lease_seconds=30)
       except ValueError:return
      else:return
      row=c.execute("SELECT phase_id,status FROM mission_phases WHERE mission_id=? AND status NOT IN ('PASS','COMPLETE','SKIPPED','CANCELLED') ORDER BY ordinal LIMIT 1",(mid,)).fetchone()
      if not row:
       if driver_snapshot(c,mid)['state']!='COMPLETE':driver_transition(c,mid,'COMPLETE',now,next_action='TERMINAL_RECONCILED')
       c.execute("UPDATE missions SET state='COMPLETE',runtime_state='DRIVER_COMPLETE',updated_at=? WHERE mission_id=?",(now(),mid));c.commit();return
      pid=row['phase_id'];spec=_phase_exec_spec(c,mid,pid)
      if not spec or spec['handler_id']=='PHASE_HANDLER_NOT_REGISTERED':
       evidence={'phase_id':pid,'handler':None if not spec else spec['handler_id'],'gate':'PHASE_HANDLER_NOT_REGISTERED'}
       if row['status']!='WAITING':_driver_phase_result(c,mid,pid,'WAITING','No registered phase handler; fail closed without progress.',evidence,'CONTROL')
       cur=driver_snapshot(c,mid)
       if cur and cur['state']!='WAITING':driver_transition(c,mid,'WAITING',now,blocking_gate='PHASE_HANDLER_NOT_REGISTERED',waiting_reason='No exact handler registered for '+pid,next_action='WAIT_FOR_HANDLER_REGISTRATION',current_phase=pid)
       return
      # Early repair phases are evidence-verification handlers.  They never
      # mutate external systems and may only close after their exact invariant exists.
      if pid=='EXACT_128L64M_TOPOLOGY_BIND':
       logical=c.execute('SELECT COUNT(*) FROM logical_drones WHERE mission_id=?',(mid,)).fetchone()[0]
       material=c.execute('SELECT COUNT(*) FROM material_workers WHERE mission_id=?',(mid,)).fetchone()[0]
       uids=c.execute('SELECT COUNT(DISTINCT pod_uid) FROM material_workers WHERE mission_id=? AND pod_uid IS NOT NULL',(mid,)).fetchone()[0]
       assignments=c.execute("SELECT COUNT(*) FROM mission_execution_assignments WHERE mission_id=? AND phase_id='__TOPOLOGY__'",(mid,)).fetchone()[0]
       evidence={'logical_count':logical,'material_count':material,'unique_uid_count':uids,'topology_assignments':assignments,'ratio':'2:1'}
       ok=(logical,material,uids,assignments)==(128,64,64,128)
      elif pid=='DATABASE_AND_SCHEDULER_SCHEMA_MIGRATION':
       tables={r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
       required={'mission_scheduler_state','mission_phase_execution_specs','mission_execution_assignments','mission_execution_receipts'}
       evidence={'required_tables':sorted(required),'present':sorted(required & tables),'integrity':c.execute('PRAGMA integrity_check').fetchone()[0]};ok=required<=tables and evidence['integrity']=='ok'
      elif pid=='GLOBAL_MULTI_RUN_DISPATCHER':
       sched=global_sched.scheduler_snapshot(c);eligible=global_sched.eligible_missions(c)
       evidence={'scheduler':sched,'eligible_missions':[r['mission_id'] for r in eligible],'dispatcher':'DB_DRIVEN_MULTI_MISSION'};ok=bool(sched and sched['state']=='ACTIVE')
      elif pid=='PER_MISSION_LEASE_AND_FAIRNESS':
       sched=global_sched.scheduler_snapshot(c);evidence={'scheduler':sched,'policy':'BOUNDED_ROUND_ROBIN_ACTIVE_BEFORE_WAITING','lease_owner':driver_snapshot(c,mid).get('lease_owner')};ok=bool(evidence['lease_owner'])
      elif pid=='PHASE_EXECUTION_PLAN_COMPILER':
       total=c.execute('SELECT COUNT(*) FROM mission_phases WHERE mission_id=?',(mid,)).fetchone()[0]
       compiled=c.execute('SELECT COUNT(*) FROM mission_phase_execution_specs WHERE mission_id=?',(mid,)).fetchone()[0]
       unknown=c.execute("SELECT COUNT(*) FROM mission_phase_execution_specs WHERE mission_id=? AND handler_id='PHASE_HANDLER_NOT_REGISTERED'",(mid,)).fetchone()[0]
       evidence={'phase_count':total,'compiled_count':compiled,'unknown_handler_count':unknown};ok=compiled==total and total>0
      elif pid=='DRIVER_LIFECYCLE_NORMALIZATION':
       normalized=[]
       for r in c.execute("SELECT mission_id FROM missions WHERE state='COMPLETE'").fetchall():
        if _normalize_complete_driver(c,r['mission_id']):normalized.append(r['mission_id'])
       evidence={'normalized':normalized,'rule':'MISSION_COMPLETE_IMPLIES_DRIVER_COMPLETE'}
       bad=c.execute("SELECT COUNT(*) FROM missions m JOIN mission_execution_drivers d ON d.mission_id=m.mission_id WHERE m.state='COMPLETE' AND d.state!='COMPLETE'").fetchone()[0];evidence['remaining_mismatch']=bad;ok=bad==0
      elif pid=='UNKNOWN_HANDLER_FAIL_CLOSED':
       canary_phase_id='__LION_UNKNOWN_HANDLER_CANARY__'
       resolved=global_sched.resolve_phase_execution_spec(canary_phase_id,{})
       expected={
        'handler_id':'PHASE_HANDLER_NOT_REGISTERED',
        'gate_class':'WAITING',
        'retry_policy':'NO_AUTOMATIC_RETRY',
        'effect_class':'NONE',
        'authority_class':'NONE',
       }
       ok=all(resolved.get(k)==v for k,v in expected.items())
       evidence={
        'canary_phase_id':canary_phase_id,
        'resolved_handler':resolved.get('handler_id'),
        'gate_class':resolved.get('gate_class'),
        'retry_policy':resolved.get('retry_policy'),
        'effect_class':resolved.get('effect_class'),
        'authority_class':resolved.get('authority_class'),
        'pass':ok,
        'behavior':'WAITING_NO_PROGRESS',
       }
      else:return
      aid=driver_begin_attempt(c,mid,pid,now,preconditions={'handler_id':spec['handler_id']},owner_id=DRIVER_PROCESS_ID)
      driver_finish_attempt(c,aid,now,state='PASS' if ok else 'BLOCKED',evidence=evidence,detail=pid)
      if ok:
       _driver_phase_result(c,mid,pid,'PASS','Verified by global scheduler repair handler.',{'event':'PHASE_HANDLER_PASS',**evidence},'VALIDATION')
       if driver_snapshot(c,mid)['state'] in {'WAITING','BLOCKED'}:driver_transition(c,mid,'ACTIVE',now,current_phase=pid,next_action='SELECT_NEXT_PHASE')
      else:
       _driver_phase_result(c,mid,pid,'BLOCKED','Exact invariant not satisfied.',{'event':'PHASE_HANDLER_BLOCKED',**evidence},'VALIDATION')
       if driver_snapshot(c,mid)['state']!='BLOCKED':driver_transition(c,mid,'BLOCKED',now,blocking_gate=pid,waiting_reason='Exact invariant not satisfied',next_action='REACQUIRE',current_phase=pid)
    finally:c.close()


GENERIC_PHASE_HANDLER='GENERIC_LPCL_PHASE'


def _registered_generic_driver(mid):
    c=connect()
    try:
      row=c.execute("SELECT phase_id FROM mission_phases WHERE mission_id=? AND status NOT IN ('PASS','COMPLETE','SKIPPED','CANCELLED') ORDER BY ordinal LIMIT 1",(mid,)).fetchone()
      if not row:return False
      spec=_phase_exec_spec(c,mid,row['phase_id'])
      return bool(spec and spec.get('handler_id')==GENERIC_PHASE_HANDLER)
    finally:c.close()


def _generic_wait(c,mid,pid,*,gate,reason,next_action,status='WAITING',detail=None):
    d=driver_snapshot(c,mid)
    target_state='BLOCKED' if status=='BLOCKED' else 'WAITING'
    if d and d.get('state')==target_state and d.get('blocking_gate')==gate and d.get('next_action')==next_action and d.get('current_phase')==pid and d.get('lease_owner') is None:
     return False
    if detail is not None:
     c.execute('UPDATE mission_phases SET status=?,detail=?,updated_at=? WHERE mission_id=? AND phase_id=?',(status,str(detail)[:4000],now(),mid,pid))
    driver_transition(c,mid,target_state,now,blocking_gate=gate,waiting_reason=reason,next_action=next_action,current_phase=pid,commit=False)
    c.execute('UPDATE mission_execution_drivers SET lease_owner=NULL,lease_expires_at=NULL WHERE mission_id=?',(mid,))
    c.commit();return True



GENERIC_BOUNDED_CAPABILITIES={
 'REPRODUCE_BIND_FAILURE':'MISSION_HISTORY_READ',
 'SEPARATE_NEW_AND_CONTINUATION_LINEAGE':'MISSION_STATE_READ',
}


def _file_sha256(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
      while True:
       b=f.read(1024*1024)
       if not b:break
       h.update(b)
    return h.hexdigest()


def _find_historical_bind_failure(mid):
    root=DB.parent/'backups';candidates=[]
    if root.is_dir():
      for p in root.glob('**/*.db'):
       try:candidates.append((p.stat().st_mtime,p))
       except OSError:pass
    for _,path in sorted(candidates,reverse=True)[:192]:
      try:
       rc=sqlite3.connect('file:'+str(path)+'?mode=ro',uri=True);rc.row_factory=sqlite3.Row
       integrity=rc.execute('PRAGMA integrity_check').fetchone()[0]
       row=rc.execute('SELECT mission_id,state,runtime_state,materialized,ready,last_error,updated_at FROM missions WHERE mission_id=?',(mid,)).fetchone()
       rc.close()
       if integrity=='ok' and row and 'lpcl continuation contract' in str(row['last_error'] or ''):
        return {'path':str(path),'sha256':_file_sha256(path),'integrity':integrity,'record':dict(row)}
      except Exception:continue
    return None


def _generic_action_ir(mid,pid,capability,target,currentness_requirements,evidence_requirements):
    action_id='generic:'+hashlib.sha256((mid+'|'+pid+'|'+capability).encode()).hexdigest()[:40]
    recon=(capability==control_recon.CAPABILITY_ID)
    air={
      'schema_version':'1.0.0','action_id':action_id,'kind':'repository.observe' if recon else 'filesystem.read',
      'intent_ref':mid+':'+pid,'mission_ref':mid,'autonomy_ref':'GENERIC_LPCL_PHASE',
      'bean_ref':'CONTROL_PLANE_RECONNAISSANCE' if recon else 'GENERIC_EFFECT_EVIDENCE_EXECUTOR',
      'target':{'host':'LION-AUTH-LAB','environment':'MISSION_CONTROL_V3','runtime':'CONTROL_PLANE_RECON' if recon else 'SQLITE_READ_ONLY'},
      'authority_request':{'domain':'mission_control','capability':capability,'grant_ref':None},
      'boundary':{'shell':False,'network':'READ_ONLY_PINNED' if recon else 'DENY','filesystem_read':[str(target)],'filesystem_write':[],
                  'process_children':[],'timeout_ms':60000 if recon else 10000,'max_processes':1,'memory_limit_bytes':134217728 if recon else 67108864},
      'preconditions':list(currentness_requirements),'expected_effects':['READ_ONLY_EVIDENCE'],
      'forbidden_effects':['FILESYSTEM_WRITE','PROCESS_EXEC','NETWORK_WRITE','AUTHORITY_MUTATION','REPOSITORY_WRITE','BROKER_RESPONSE_INJECTION'],
      'observation':{'observer_class':'deterministic_independent','required_events':list(evidence_requirements)},
      'reconciliation':{'mode':'EXACT','receipt':'REQUIRED'},
    }
    CanonicalActionIR.from_mapping(air)
    return air



def _find_restart_durability_evidence(mid,pid,assignment_id,receipt_id):
    root=DB.parent/'backups';current=connect()
    try:
      cur_a=current.execute('SELECT input_digest,state FROM mission_execution_assignments WHERE assignment_id=? AND mission_id=? AND phase_id=?',(assignment_id,mid,pid)).fetchone()
      cur_r=current.execute('SELECT result_digest,status,authority_effect FROM mission_execution_receipts WHERE receipt_id=? AND assignment_id=?',(receipt_id,assignment_id)).fetchone()
    finally:current.close()
    if not cur_a or not cur_r:return None
    candidates=[]
    if root.is_dir():
      for path in root.glob('**/*.db'):
       try:candidates.append((path.stat().st_mtime,path))
       except OSError:pass
    for _,path in sorted(candidates,reverse=True)[:256]:
      try:
       rc=sqlite3.connect('file:'+str(path)+'?mode=ro',uri=True);rc.row_factory=sqlite3.Row
       integrity=rc.execute('PRAGMA integrity_check').fetchone()[0]
       a=rc.execute('SELECT input_digest,state FROM mission_execution_assignments WHERE assignment_id=? AND mission_id=? AND phase_id=?',(assignment_id,mid,pid)).fetchone()
       r=rc.execute('SELECT result_digest,status,authority_effect FROM mission_execution_receipts WHERE receipt_id=? AND assignment_id=?',(receipt_id,assignment_id)).fetchone();rc.close()
       if integrity=='ok' and a and r and a['input_digest']==cur_a['input_digest'] and r['result_digest']==cur_r['result_digest'] and r['status']==cur_r['status'] and r['authority_effect']==cur_r['authority_effect']:
        return {'backup_path':str(path),'backup_sha256':_file_sha256(path),'backup_integrity':integrity,'assignment_id':assignment_id,'receipt_id':receipt_id,'assignment_input_digest':a['input_digest'],'receipt_result_digest':r['result_digest'],'durable_across_snapshot_boundary':True}
      except Exception:continue
    return None


def _execution_binder_postconditions(c,mid,pid,assignment,receipt):
    ps=c.execute('SELECT lpcl_text FROM mission_process_specs WHERE mission_id=?',(mid,)).fetchone();kv=_lpcl_pairs(ps['lpcl_text'] if ps else '')
    m=c.execute('SELECT adapter,state,runtime_state,logical_count,materialized,ready FROM missions WHERE mission_id=?',(mid,)).fetchone()
    logical_count=c.execute('SELECT COUNT(*) FROM logical_drones WHERE mission_id=?',(mid,)).fetchone()[0]
    material_rows=c.execute('SELECT pod_uid,ready FROM material_workers WHERE mission_id=?',(mid,)).fetchall()
    unique_material=len({r['pod_uid'] for r in material_rows if r['pod_uid']})
    specs=c.execute('SELECT phase_id,handler_id FROM mission_phase_execution_specs WHERE mission_id=?',(mid,)).fetchall()
    generic_specs=[r for r in specs if r['handler_id']==GENERIC_PHASE_HANDLER]
    driver=driver_snapshot(c,mid);sched=global_sched.scheduler_snapshot(c)
    local_receipt=bool(receipt and receipt['status']=='PASS' and receipt['authority_effect']=='NONE')
    fail_closed=bool(c.execute("SELECT 1 FROM protocol_messages WHERE mission_id=? AND phase=? AND protocol='CONTROL' AND payload_json LIKE '%GENERIC_PHASE_CAPABILITY_UNAVAILABLE%' LIMIT 1",(mid,pid)).fetchone())
    restart=_find_restart_durability_evidence(mid,pid,assignment['assignment_id'],receipt['receipt_id']) if receipt else None
    fresh_no_parent=not any(k in kv for k in ('CONTINUE_EXISTING_EPOCH3_MISSION','CONTINUE_EXISTING_EPOCH3_LINEAGE','PARENT_MISSION_ID'))
    checks={
      'FRESH_LPCL_WITHOUT_PARENT':fresh_no_parent,
      'GENERIC_ADAPTER_BOUND':bool(m and m['adapter']==LPCL_GENERIC_ADAPTER),
      'LOGICAL_COUNT_128':bool(m and int(m['logical_count'])==128 and logical_count==128),
      'MATERIAL_READY_64':bool(m and int(m['materialized'])==64 and int(m['ready'])==64 and len(material_rows)==64 and all(int(r['ready'])==1 for r in material_rows)),
      'UNIQUE_MATERIAL_64':unique_material==64,
      'GENERIC_PHASE_COMPILER':len(specs)==c.execute('SELECT COUNT(*) FROM mission_phases WHERE mission_id=?',(mid,)).fetchone()[0],
      'GENERIC_PHASE_HANDLER':len(generic_specs)>=1 and any(r['phase_id']==pid for r in generic_specs),
      'DURABLE_DRIVER':bool(driver and driver.get('state') in {'ACTIVE','WAITING','BLOCKED','PAUSED'}),
      'GLOBAL_SCHEDULER_DISPATCH':bool(sched and sched.get('state')=='ACTIVE' and sched.get('heartbeat_at')),
      'LOCAL_PLANNING_RECEIPT':local_receipt,
      'FAIL_CLOSED_MISSING_CAPABILITY':fail_closed,
      'RESTART_DURABILITY':bool(restart),
      'DB_INTEGRITY':c.execute('PRAGMA integrity_check').fetchone()[0]=='ok',
    }
    evidence={'checks':{k:'PASS' if v else 'FAIL' for k,v in checks.items()},'restart_durability':restart,'adapter':m['adapter'] if m else None,'mission_state':m['state'] if m else None,'runtime_state':m['runtime_state'] if m else None,'logical_count':logical_count,'material_count':len(material_rows),'unique_material_count':unique_material,'generic_spec_count':len(generic_specs),'driver_state':driver.get('state') if driver else None,'scheduler':sched,'assignment_id':assignment['assignment_id'],'planning_receipt_id':receipt['receipt_id'] if receipt else None,'authority_effect':'NONE'}
    return all(checks.values()),evidence


def _generic_plan_definition(c,mid,pid,assignment,receipt):
    payload=global_sched.assignment_payload(c,assignment['assignment_id'])
    payload_state='RETAINED' if payload else 'LEGACY_DIGEST_ONLY'
    deps=[receipt['receipt_id']]
    executor_id='MISSION_CONTROL_READ_ONLY_EVIDENCE'
    if pid=='REPRODUCE_BIND_FAILURE':
      hist=_find_historical_bind_failure(mid)
      if not hist:return None
      capability='MISSION_HISTORY_READ';target=hist['path'];operation='READ_HISTORICAL_BIND_FAILURE'
      required={'mission_id':mid,'error_fragment':'lpcl continuation contract','backup_sha256':hist['sha256']}
      expected={'state':'AUTHORIZED','runtime_state':'NOT_STARTED','bind_error':'lpcl continuation contract'}
      currentness=['HISTORICAL_SNAPSHOT_SHA256_BOUND','MISSION_ID_MATCH']
      evidence=['SQLITE_INTEGRITY_OK','HISTORICAL_BIND_FAILURE_MATCH']
    elif pid=='SEPARATE_NEW_AND_CONTINUATION_LINEAGE':
      capability='MISSION_STATE_READ';target=str(DB);operation='VERIFY_FRESH_LINEAGE_SEPARATION'
      required={'mission_id':mid,'expected_adapter':LPCL_GENERIC_ADAPTER}
      expected={'fresh_mission':True,'continuation_required':False,'parent_required':False}
      currentness=['LIVE_DB_INTEGRITY_OK','CURRENT_MISSION_RECORD']
      evidence=['GENERIC_ADAPTER_ACTIVE','NO_CONTINUATION_FLAGS','NO_PARENT_REQUIRED']
    else:
      contract,bound=_phase_contract_capability(c,mid,pid)
      if not contract or not bound:return None
      capability=bound['capability_id'];target=str(DB);executor_id=bound.get('executor_id') or executor_id
      operation='CONTROL_PLANE_RECONNAISSANCE' if capability==control_recon.CAPABILITY_ID else 'RECONCILE_PHASE_COMPLETION_POSTCONDITIONS'
      required={'mission_id':mid,'phase_id':pid,'contract_digest':contract['contract_digest'],'capability_class':bound['capability_class']}
      expected={'completion_predicates':contract['completion_predicates'],'verify_before_mutate':bool(contract['verify_before_mutate'])}
      currentness=list(contract['currentness_requirements']);evidence=list(contract['evidence_requirements'])
    air=_generic_action_ir(mid,pid,capability,target,currentness,evidence)
    return {
      'mission_id':mid,'phase_id':pid,'planning_assignment_id':assignment['assignment_id'],
      'planning_receipt_id':receipt['receipt_id'],'planning_result_digest':receipt['result_digest'],
      'planning_payload_state':payload_state,'state':'CAPABILITY_RESOLUTION','capability':capability,
      'target':target,'operation':operation,'required_inputs':required,'expected_output':expected,
      'authority_class':'NONE','currentness_requirements':currentness,'evidence_requirements':evidence,
      'rollback_class':'NONE','dependencies':deps,'action_ir':air,'action_ir_digest':global_sched.digest(air),
      'executor_id':executor_id,
    }


def _generic_execute_read_plan(c,plan):
    capability=plan['capability'];pid=plan['phase_id'];mid=plan['mission_id'];executor_id=plan.get('executor_id') or 'MISSION_CONTROL_READ_ONLY_EVIDENCE'
    if plan['authority_class']!='NONE':
      global_sched.update_generic_plan_state(c,plan['plan_id'],'WAITING_AUTHORITY',now,executor_id=executor_id)
      return {'state':'WAITING_AUTHORITY','gate':'AUTHORITY_REQUIRED','reason':'Explicit admitted authority is required'}
    global_sched.update_generic_plan_state(c,plan['plan_id'],'WAITING_CURRENTNESS',now,executor_id=executor_id)
    if capability=='MISSION_HISTORY_READ':
      try:
       expected=json.loads(plan['required_inputs_json']);path=Path(plan['target'])
       if not path.is_file() or _file_sha256(path)!=expected['backup_sha256']:
        return {'state':'WAITING_CURRENTNESS','gate':'CURRENTNESS_REQUIRED','reason':'Historical evidence file identity changed'}
       rc=sqlite3.connect('file:'+str(path)+'?mode=ro',uri=True);rc.row_factory=sqlite3.Row
       integrity=rc.execute('PRAGMA integrity_check').fetchone()[0]
       row=rc.execute('SELECT state,runtime_state,materialized,ready,last_error,updated_at FROM missions WHERE mission_id=?',(mid,)).fetchone();rc.close()
       ok=bool(integrity=='ok' and row and row['state']=='AUTHORIZED' and row['runtime_state']=='NOT_STARTED' and 'lpcl continuation contract' in str(row['last_error'] or ''))
       evidence={'capability':capability,'source_path':str(path),'source_sha256':expected['backup_sha256'],'sqlite_integrity':integrity,
                 'mission_id':mid,'historical_record':dict(row) if row else None,'bind_failure_match':ok,'authority_effect':'NONE'}
      except Exception as exc:
       return {'state':'WAITING_CURRENTNESS','gate':'CURRENTNESS_REQUIRED','reason':type(exc).__name__+':'+str(exc)[:500]}
    elif capability=='MISSION_STATE_READ':
      integrity=c.execute('PRAGMA integrity_check').fetchone()[0]
      m=c.execute('SELECT adapter,state,runtime_state,materialized,ready,source_head,source_tree FROM missions WHERE mission_id=?',(mid,)).fetchone()
      ps=c.execute('SELECT lpcl_text FROM mission_process_specs WHERE mission_id=?',(mid,)).fetchone();kv=_lpcl_pairs(ps['lpcl_text'] if ps else '')
      continuation=any(k in kv for k in ('CONTINUE_EXISTING_EPOCH3_MISSION','CONTINUE_EXISTING_EPOCH3_LINEAGE','PARENT_MISSION_ID'))
      ok=bool(integrity=='ok' and m and m['adapter']==LPCL_GENERIC_ADAPTER and not continuation)
      evidence={'capability':capability,'sqlite_integrity':integrity,'mission_id':mid,'adapter':m['adapter'] if m else None,
                'state':m['state'] if m else None,'runtime_state':m['runtime_state'] if m else None,
                'materialized':m['materialized'] if m else None,'ready':m['ready'] if m else None,
                'continuation_keys_present':sorted(k for k in ('CONTINUE_EXISTING_EPOCH3_MISSION','CONTINUE_EXISTING_EPOCH3_LINEAGE','PARENT_MISSION_ID') if k in kv),
                'fresh_mission_separation':ok,'authority_effect':'NONE'}
    elif capability=='GENERIC_EXECUTION_BINDER_RECONCILIATION':
      assignment=c.execute("SELECT assignment_id,state FROM mission_execution_assignments WHERE mission_id=? AND phase_id=? AND phase_id!='__TOPOLOGY__' ORDER BY created_at DESC LIMIT 1",(mid,pid)).fetchone()
      receipt=c.execute('SELECT * FROM mission_execution_receipts WHERE mission_id=? AND phase_id=? ORDER BY observed_at DESC LIMIT 1',(mid,pid)).fetchone()
      ok,evidence=_execution_binder_postconditions(c,mid,pid,assignment,receipt) if assignment and receipt else (False,{'missing':'planning assignment or receipt','authority_effect':'NONE'})
      evidence={'capability':capability,**evidence}
    elif capability==control_recon.CAPABILITY_ID:
      contract=global_sched.phase_execution_contract(c,mid,pid)
      if not contract:return {'state':'BLOCKED','gate':'PROCESS_CONTRACT_MISSING','reason':'Phase execution contract is not materialized'}
      driver=driver_snapshot(c,mid)
      def _create_recon_saas(mission_id,question):
       return saas_broker.create_request(c,mission_id,question,now,scope_type='MISSION',scope_id=mission_id,authority_effect='NONE')
      def _recon_saas_status(request_id):
       return saas_broker.request_status(c,request_id,now)
      recon_result=control_recon.execute_phase(c,mid,pid,contract,db_path=DB,driver_generation=int((driver or {}).get('generation') or 1),now_fn=now,create_saas_request=_create_recon_saas,saas_request_status=_recon_saas_status)
      if recon_result.get('state')=='REACQUIRE_REQUIRED':
       current=driver_snapshot(c,mid)
       if not current or current.get('state') not in {'WAITING','BLOCKED'}:
        return {'state':'WAITING','gate':'EVIDENCE_REACQUISITION_REQUIRED','reason':'Evidence reacquisition requires a parked driver','evidence':recon_result.get('evidence') or {'authority_effect':'NONE'}}
       activated=driver_activate(c,mid,now,next_action='REACQUIRE_EVIDENCE',owner_id=DRIVER_PROCESS_ID,lease_seconds=30)
       _process_message(c,mid,'CURRENTNESS','GLOBAL_SCHEDULER','GENERIC_EFFECT_EVIDENCE_EXECUTOR',pid,{'event':'RECON_EVIDENCE_REACQUISITION_OPENED','previous_driver_generation':int(current.get('generation') or 0),'driver_generation':int(activated.get('generation') or 0),'reacquisition':recon_result.get('reacquisition'),'authority_effect':'NONE'},'INTERNAL');c.commit()
       recon_result=control_recon.execute_phase(c,mid,pid,contract,db_path=DB,driver_generation=int(activated.get('generation') or 1),now_fn=now,create_saas_request=_create_recon_saas,saas_request_status=_recon_saas_status,allow_reacquire=True)
      if recon_result.get('state')!='PASS':
       global_sched.update_generic_plan_state(c,plan['plan_id'],'WAITING_CURRENTNESS',now,executor_id=executor_id,evidence=recon_result.get('evidence') or {'authority_effect':'NONE'})
       return recon_result
      ok=True;evidence={'capability':capability,**(recon_result.get('evidence') or {})}
    elif capability=='GENERIC_MISSION_CONTRACT_RECONCILIATION':
      contract=global_sched.phase_execution_contract(c,mid,pid)
      if not contract:return {'state':'BLOCKED','gate':'PROCESS_CONTRACT_MISSING','reason':'Phase execution contract is not materialized'}
      ok,evidence=evaluate_completion_predicates(c,mid,pid,contract['completion_predicates'],db_path=DB)
      evidence={'capability':capability,'contract_digest':contract['contract_digest'],**evidence}
    else:return {'state':'BLOCKED','gate':'CAPABILITY_NOT_AVAILABLE','reason':'Capability is not in the bounded generic executor registry'}
    global_sched.update_generic_plan_state(c,plan['plan_id'],'READY_TO_EXECUTE',now,executor_id=executor_id)
    global_sched.update_generic_plan_state(c,plan['plan_id'],'EXECUTING',now,executor_id=executor_id)
    global_sched.update_generic_plan_state(c,plan['plan_id'],'VALIDATING',now,executor_id=executor_id,evidence=evidence)
    if not ok:
      global_sched.update_generic_plan_state(c,plan['plan_id'],'BLOCKED',now,executor_id=executor_id,evidence=evidence)
      return {'state':'BLOCKED','gate':'EVIDENCE_REQUIREMENTS_NOT_SATISFIED','reason':'Independent read-only evidence did not satisfy the phase completion contract','evidence':evidence}
    receipt=global_sched.record_generic_action_receipt(c,plan['plan_id'],now,status='PASS',evidence=evidence,authority_effect='NONE')
    return {'state':'PASS','receipt':receipt,'evidence':evidence}


def _generic_existing_action_receipt(c,plan_id):
    row=c.execute('SELECT * FROM mission_generic_action_receipts WHERE plan_id=?',(plan_id,)).fetchone()
    return dict(row) if row else None

def drive_generic_once(mid):
    c=connect()
    try:
      m=c.execute('SELECT state,title FROM missions WHERE mission_id=?',(mid,)).fetchone()
      ps=c.execute('SELECT authority_state,current_phase,objective,description FROM mission_process_specs WHERE mission_id=?',(mid,)).fetchone()
      if not m or not ps or ps['authority_state']!='EXPLICIT_USER_ACTIVATION':return
      d=driver_snapshot(c,mid)
      if not d or d['state'] not in {'ACTIVE','WAITING','BLOCKED'}:return
      row=c.execute("SELECT phase_id,title,status FROM mission_phases WHERE mission_id=? AND status NOT IN ('PASS','COMPLETE','SKIPPED','CANCELLED') ORDER BY ordinal LIMIT 1",(mid,)).fetchone()
      if not row:
       driver_reconcile_complete(c,mid,now,next_action='TERMINAL_RECONCILED',commit=False)
       c.execute("UPDATE missions SET state='COMPLETE',runtime_state='DRIVER_COMPLETE',updated_at=? WHERE mission_id=?",(now(),mid));c.commit();return
      pid=row['phase_id'];spec=_phase_exec_spec(c,mid,pid)
      if not spec or spec.get('handler_id')!=GENERIC_PHASE_HANDLER:return
      assignment=c.execute("SELECT assignment_id,state,lease_generation FROM mission_execution_assignments WHERE mission_id=? AND phase_id=? AND phase_id!='__TOPOLOGY__' ORDER BY created_at DESC,assignment_id DESC LIMIT 1",(mid,pid)).fetchone()
      if assignment is None:
       if d['state']!='ACTIVE':
        d=driver_activate(c,mid,now,next_action='GENERIC_PHASE_PLAN',owner_id=DRIVER_PROCESS_ID,lease_seconds=30)
       else:
        driver_heartbeat(c,mid,now,phase=pid,next_action='GENERIC_PHASE_PLAN',owner_id=DRIVER_PROCESS_ID,lease_seconds=30)
        d=driver_snapshot(c,mid)
       prompt=(
        'LION generic LPCL phase planning. You are proposal-only and have authority_effect=NONE. '
        'Do not claim that any effect was executed. Produce a bounded execution plan, required capabilities, evidence, '
        'authority/currentness prerequisites, delegation candidates, and a clear completion test.\n\n'
        f'Mission: {m["title"]}\nObjective: {ps["objective"]}\nPhase: {pid} — {row["title"]}\nDescription: {ps["description"]}'
       )
       payload={'kind':'LOCAL_MODEL_INFERENCE','messages':[{'role':'user','content':prompt}], 'max_tokens':768, 'mission_id':mid, 'phase_id':pid, 'authority_effect':'NONE'}
       aid=global_sched.create_assignment(c,mid,pid,'LD001','MD025',payload,now,lease_generation=int(d['generation']))
       _process_message(c,mid,'ASSIGNMENT','GLOBAL_SCHEDULER','LOCAL_MODEL',pid,{'event':'GENERIC_PHASE_LOCAL_PLAN_REQUESTED','assignment_id':aid,'material_drone_id':'MD025','authority_effect':'NONE'},'OUT')
       _generic_wait(c,mid,pid,gate='GENERIC_PHASE_LOCAL_PLAN_RECEIPT',reason='Waiting for proposal-only LOCAL planning receipt',next_action='WAIT_FOR_LOCAL_PLAN',detail='Generic phase started; waiting for proposal-only LOCAL planning receipt.')
       return
      astate=str(assignment['state'])
      if astate in {'READY','CLAIMED'}:
       _generic_wait(c,mid,pid,gate='GENERIC_PHASE_LOCAL_PLAN_RECEIPT',reason='Waiting for proposal-only LOCAL planning receipt',next_action='WAIT_FOR_LOCAL_PLAN',detail='Generic phase started; waiting for proposal-only LOCAL planning receipt.')
       return
      receipt=c.execute('SELECT receipt_id,result_digest,status,observed_at FROM mission_execution_receipts WHERE assignment_id=? ORDER BY observed_at DESC,receipt_id DESC LIMIT 1',(assignment['assignment_id'],)).fetchone()
      if astate=='PASS' and receipt:
       planrow=c.execute('SELECT * FROM mission_generic_phase_plans WHERE mission_id=? AND phase_id=?',(mid,pid)).fetchone()
       if planrow is None:
        definition=_generic_plan_definition(c,mid,pid,assignment,receipt)
        if definition is None:
         changed=_generic_wait(c,mid,pid,gate='CAPABILITY_NOT_AVAILABLE',reason='No bounded capability is registered for this generic phase',next_action='WAIT_FOR_CAPABILITY',detail='LOCAL planning receipt observed. No bounded effect/evidence capability is registered for this phase.')
         if changed:_process_message(c,mid,'CONTROL','GLOBAL_SCHEDULER','MISSION_CONTROL',pid,{'event':'GENERIC_PHASE_CAPABILITY_UNAVAILABLE','assignment_id':assignment['assignment_id'],'receipt_id':receipt['receipt_id'],'authority_effect':'NONE'},'INTERNAL');c.commit()
         return
        planrow=global_sched.put_generic_phase_plan(c,now_fn=now,**definition)
        _process_message(c,mid,'ASSIGNMENT','GLOBAL_SCHEDULER','GENERIC_EFFECT_EVIDENCE_EXECUTOR',pid,{'event':'GENERIC_ACTION_IR_MATERIALIZED','plan_id':planrow['plan_id'],'capability':planrow['capability'],'operation':planrow['operation'],'action_ir_digest':planrow['action_ir_digest'],'planning_receipt_id':receipt['receipt_id'],'planning_payload_state':planrow['planning_payload_state'],'authority_effect':'NONE'},'INTERNAL');c.commit()
       else:planrow=dict(planrow)
       action_receipt=_generic_existing_action_receipt(c,planrow['plan_id'])
       if action_receipt and action_receipt.get('status')=='PASS':
        evidence=json.loads(planrow['evidence_json'] or '{}')
        current,overall=_driver_phase_result(c,mid,pid,'PASS','Bounded generic effect/evidence executor satisfied the phase contract.',{'event':'GENERIC_PHASE_EXECUTION_PASS','plan_id':planrow['plan_id'],'action_receipt_id':action_receipt['receipt_id'],'action_ir_digest':planrow['action_ir_digest'],'evidence_digest':action_receipt['evidence_digest'],'authority_effect':'NONE',**evidence},'VALIDATION')
        if current and driver_snapshot(c,mid)['state'] in {'WAITING','BLOCKED'}:driver_transition(c,mid,'ACTIVE',now,current_phase=current,next_action='SELECT_NEXT_PHASE')
        return
       result=_generic_execute_read_plan(c,planrow)
       if result['state']=='PASS':
        ar=result['receipt']
        _process_message(c,mid,'EVIDENCE','GENERIC_EFFECT_EVIDENCE_EXECUTOR','MISSION_CONTROL',pid,{'event':'GENERIC_ACTION_EVIDENCE_OBSERVED','plan_id':planrow['plan_id'],'action_ir_digest':planrow['action_ir_digest'],'evidence_digest':ar['evidence_digest'],'authority_effect':'NONE'},'INTERNAL')
        _process_message(c,mid,'RECEIPT','GENERIC_EFFECT_EVIDENCE_EXECUTOR','MISSION_CONTROL',pid,{'event':'GENERIC_ACTION_RECEIPT','plan_id':planrow['plan_id'],'receipt_id':ar['receipt_id'],'action_ir_digest':planrow['action_ir_digest'],'evidence_digest':ar['evidence_digest'],'authority_effect':'NONE'},'INTERNAL');c.commit()
        current,overall=_driver_phase_result(c,mid,pid,'PASS','Bounded generic effect/evidence executor satisfied the phase contract.',{'event':'GENERIC_PHASE_EXECUTION_PASS','plan_id':planrow['plan_id'],'action_receipt_id':ar['receipt_id'],'action_ir_digest':planrow['action_ir_digest'],'evidence_digest':ar['evidence_digest'],'authority_effect':'NONE',**result['evidence']},'VALIDATION')
        if current and driver_snapshot(c,mid)['state'] in {'WAITING','BLOCKED'}:driver_transition(c,mid,'ACTIVE',now,current_phase=current,next_action='SELECT_NEXT_PHASE')
        return
       gate=result.get('gate') or ('AUTHORITY_REQUIRED' if result['state']=='WAITING_AUTHORITY' else 'CURRENTNESS_REQUIRED' if result['state']=='WAITING_CURRENTNESS' else 'GENERIC_EXECUTION_BLOCKED')
       changed=_generic_wait(c,mid,pid,gate=gate,reason=result.get('reason') or 'Generic executor waiting',next_action='WAIT_FOR_'+gate,status='BLOCKED' if result['state'] in {'BLOCKED','FAILED'} else 'WAITING',detail=result.get('reason') or 'Generic executor waiting')
       if changed:_process_message(c,mid,'CONTROL','GENERIC_EFFECT_EVIDENCE_EXECUTOR','MISSION_CONTROL',pid,{'event':'GENERIC_EXECUTOR_WAIT','plan_id':planrow['plan_id'],'state':result['state'],'gate':gate,'authority_effect':'NONE'},'INTERNAL');c.commit()
       return
      if astate=='FAIL':
       changed=_generic_wait(c,mid,pid,gate='GENERIC_PHASE_LOCAL_PLAN_FAILED',reason='LOCAL proposal worker failed; no automatic effect retry',next_action='REPLAN_OR_OPERATOR_REVIEW',status='BLOCKED',detail='LOCAL proposal worker failed; generic phase blocked without effect.')
       if changed:_process_message(c,mid,'RECOVERY','GLOBAL_SCHEDULER','MISSION_CONTROL',pid,{'event':'GENERIC_PHASE_LOCAL_PLAN_FAILED','assignment_id':assignment['assignment_id'],'authority_effect':'NONE'},'INTERNAL');c.commit()
    finally:c.close()


def _registered_control_plane_early_driver(mid):
    c=connect()
    try:
      row=c.execute("SELECT phase_id FROM mission_phases WHERE mission_id=? AND status NOT IN ('PASS','COMPLETE','SKIPPED','CANCELLED') ORDER BY ordinal LIMIT 1",(mid,)).fetchone()
      if not row or row['phase_id'] not in CONTROL_PLANE_EARLY_HANDLERS:return False
      spec=_phase_exec_spec(c,mid,row['phase_id'])
      return bool(spec and spec.get('handler_id')!='PHASE_HANDLER_NOT_REGISTERED')
    finally:c.close()


def reconcile_control_plane_late_saas():
    c=connect()
    try:
      changes=control_recon.late_saas_reconcile(c,now,request_status=lambda rid:saas_broker.request_status(c,rid,now))
      for item in changes:
       _process_message(c,item['mission_id'],'EVIDENCE','CHATGPT_SAAS_SUPERVISOR','MISSION_CONTROL',item['phase_id'],{'event':'RECON_LATE_SAAS_RECEIPT','request_id':item['request_id'],'response_digest':item.get('response_digest'),'receipt_digest':item.get('receipt_digest'),'authority_effect':'NONE'},'INTERNAL')
      if changes:c.commit()
    finally:c.close()


def global_scheduler_once():
    try:reconcile_control_plane_late_saas()
    except Exception:pass
    c=connect()
    try:
      if c.execute("SELECT 1 FROM mission_meta WHERE key='mission_dispatch_paused' AND value='1'").fetchone():return
      # Terminal state reconciliation is orthogonal to dispatch and prevents
      # historical COMPLETE missions from presenting a PAUSED driver.
      for row in c.execute("SELECT mission_id FROM missions WHERE state='COMPLETE'").fetchall():
       _normalize_complete_driver(c,row['mission_id'])
      pick=global_sched.next_dispatch(c,now)
    finally:c.close()
    if not pick:return
    mid=pick['mission_id']
    if mid==SELF_HOSTING_MISSION:drive_self_hosted_once(mid)
    elif mid==CONTROL_PLANE_MISSION or _registered_control_plane_early_driver(mid):drive_control_plane_once(mid)
    elif _registered_generic_driver(mid):drive_generic_once(mid)
    else:
      # A generic driver without an executable registration is not running.
      # Park it durably instead of replaying a persisted lease_owner and
      # manufacturing an ACTIVE heartbeat from an obsolete process identity.
      c=connect()
      try:
       d=driver_snapshot(c,mid)
       if d and d['state']=='ACTIVE':
        mrow=c.execute('SELECT last_error FROM missions WHERE mission_id=?',(mid,)).fetchone()
        bind_failed=bool(mrow and str(mrow['last_error'] or '').startswith('LPCL_EXECUTION_BIND:'))
        reason='No executable global driver is registered for the mission'
        if bind_failed:reason+='; execution binding failed (see mission.last_error)'
        parked=driver_wait_for_execution_binding(c,mid,now,blocking_gate='GLOBAL_DRIVER_NOT_REGISTERED',waiting_reason=reason,next_action='WAIT_FOR_EXECUTION_BINDING')
        if not parked.get('idempotent'):
         _process_message(c,mid,'RECOVERY','GLOBAL_SCHEDULER','MISSION_CONTROL',None,{'event':'ORPHAN_ACTIVE_DRIVER_PARKED','blocking_gate':'GLOBAL_DRIVER_NOT_REGISTERED','execution_bind_failed':bind_failed,'authority_effect':'CONTROL_STATE'},'INTERNAL');c.commit()
      finally:c.close()


def mission_driver_loop():
    while not DRIVER_STOP.is_set():
      try:global_scheduler_once()
      except Exception as exc:
       try:
        c=connect();global_sched.heartbeat(c,now,queue_depth=len(global_sched.eligible_missions(c)),active_run_count=sum(1 for x in global_sched.eligible_missions(c) if x['state']=='ACTIVE'),last_error=type(exc).__name__+':'+str(exc)[:900]);c.close()
       except Exception:pass
      DRIVER_STOP.wait(MISSION_DRIVER_LOOP_INTERVAL_SECONDS)


def create_dual_evaluation(x):
    required={'mission_id','original_request','currentness'}
    if type(x) is not dict or set(x)!=required:raise ValueError('dual request schema')
    mid=x['mission_id'];c=connect()
    try:
      ps=c.execute('SELECT current_phase FROM mission_process_specs WHERE mission_id=?',(mid,)).fetchone()
      if not ps:raise ValueError('mission not found')
      out=dual_create(c,mid,ps['current_phase'],x['original_request'],x['currentness'],now);return out
    finally:c.close()


def link_dual_saas(x):
    if type(x) is not dict or set(x)!={'request_id','saas_request_id'}:raise ValueError('dual link schema')
    c=connect()
    try:dual_link_saas(c,x['request_id'],x['saas_request_id'],now);return {'ok':True}
    finally:c.close()


def record_dual_response(x):
    required={'request_id','provider','response_text','transport'}
    if type(x) is not dict or set(x)!=required:raise ValueError('dual response schema')
    c=connect()
    try:return dual_record_response(c,x['request_id'],x['provider'],x['response_text'],now,transport=x.get('transport'),authority_effect='NONE')
    finally:c.close()


def get_dual_result(rid):
    c=connect()
    try:return dual_join_result(c,rid)
    finally:c.close()
def create_saas_handoff(x):
    if type(x) is not dict or set(x)!={'mission_id','question'}:raise ValueError('saas request schema')
    mid=x.get('mission_id');question=x.get('question')
    if not _safe_id(mid,127):raise ValueError('mission_id')
    c=connect()
    try:
      out=saas_create(c,mid,question,now)
      phase=c.execute('SELECT current_phase FROM mission_process_specs WHERE mission_id=?',(mid,)).fetchone()
      _process_message(c,mid,'ASSIGNMENT','LPCL_PANEL','CHATGPT_SAAS_SUPERVISOR',(phase['current_phase'] if phase else None),{'event':'SAAS_HANDOFF_REQUESTED','request_id':out['request_id'],'request_code':out['request_code'],'question_digest':out['question_digest'],'transport':out['transport'],'authority_effect':'NONE'},'OUT')
      c.commit();return out
    finally:c.close()


def get_saas_pending(code=None,mission_id=None):
    c=connect()
    try:return saas_pending(c,now,request_code=code,mission_id=mission_id)
    finally:c.close()


def get_saas_request_status(request_id):
    c=connect()
    try:return saas_request_status(c,request_id,now)
    finally:c.close()


def get_saas_bridge_status(mission_id):
    c=connect()
    try:return saas_bridge_status(c,mission_id,now)
    finally:c.close()


def respond_saas_handoff(x):
    required={'request_id','response_token','answer','model_identity','transport','attestation_class'}
    if type(x) is not dict or set(x)!=required:raise ValueError('saas response schema')
    if x['transport']!=SAAS_TRANSPORT or x['attestation_class']!=SAAS_ATTESTATION_CLASS:raise ValueError('saas transport binding')
    c=connect()
    try:
      out=saas_respond(c,x['request_id'],x['response_token'],x['answer'],now,model_identity=x['model_identity'],transport=x['transport'],attestation_class=x['attestation_class'])
      mid=out['receipt']['mission_id'];phase=c.execute('SELECT current_phase FROM mission_process_specs WHERE mission_id=?',(mid,)).fetchone()
      _process_message(c,mid,'RECEIPT','CHATGPT_SAAS_SUPERVISOR','MISSION_CONTROL',(phase['current_phase'] if phase else None),{'event':'SAAS_HANDOFF_RESPONSE','request_id':x['request_id'],'binding_id':out['receipt']['binding_id'],'model_identity':x['model_identity'],'transport':x['transport'],'response_digest':out['receipt']['response_digest'],'attestation_digest':out['receipt']['attestation_digest'],'receipt_digest':out['receipt']['receipt_digest'],'authority_effect':'NONE'},'IN')
      # Browser-independent join: the SaaS ingress is the authoritative moment
      # at which the durable SaaS receipt exists.  If this request belongs to a
      # dual evaluation, persist that receipt and compute the join here, not in JS.
      dual=c.execute('SELECT request_id FROM mission_dual_evaluations WHERE saas_request_id=? ORDER BY updated_at DESC LIMIT 1',(x['request_id'],)).fetchone()
      if dual:
       drid=dual['request_id'];dual_record_response(c,drid,DUAL_SAAS_PROVIDER,x['answer'],now,transport=x['transport'],authority_effect='NONE');joined=dual_join_result(c,drid);out['dual_result']=joined
       _process_message(c,mid,'RECEIPT','MISSION_CONTROL','DUAL_RESULT_JOIN',(phase['current_phase'] if phase else None),{'event':'SAAS_RECEIPT_AUTO_JOINED','dual_request_id':drid,'dual_state':joined.get('state'),'saas_response_digest':out['receipt']['response_digest'],'authority_effect':'NONE'},'INTERNAL')
      c.commit();return out
    finally:c.close()


def local_assignment_list(mission_id=None,limit=16):
    c=connect()
    try:return {'assignments':global_sched.pending_local_assignments(c,mission_id=mission_id,limit=limit),'authority_effect':'NONE'}
    finally:c.close()


def local_assignment_claim(x):
    if type(x) is not dict or set(x)!={'assignment_id','material_drone_id'}:raise ValueError('local assignment claim schema')
    c=connect()
    try:return global_sched.claim_assignment(c,x['assignment_id'],now,expected_material_drone_id=x['material_drone_id'])
    finally:c.close()


def local_assignment_receipt(x):
    required={'assignment_id','status','result','effect_receipt_digest','authority_effect','material_drone_id','lease_generation'}
    if type(x) is not dict or set(x)!=required:raise ValueError('local assignment receipt schema')
    if x['status'] not in {'PASS','FAIL'} or x['authority_effect']!='NONE':raise ValueError('local assignment receipt status/authority')
    if type(x['result']) is not dict:raise ValueError('local assignment result')
    c=connect()
    try:
      out=global_sched.record_receipt(c,x['assignment_id'],x['result'],now,material_drone_id=x['material_drone_id'],lease_generation=x['lease_generation'],status=x['status'],effect_receipt_digest=x['effect_receipt_digest'],authority_effect='NONE')
      payload_store=global_sched.store_assignment_payload(c,x['assignment_id'],out['receipt_id'],x['result'],now)
      row=c.execute('SELECT mission_id,phase_id FROM mission_execution_assignments WHERE assignment_id=?',(x['assignment_id'],)).fetchone()
      if row:_process_message(c,row['mission_id'],'RECEIPT','LOCAL_ASSIGNMENT_WORKER','GLOBAL_SCHEDULER',row['phase_id'],{'event':'LOCAL_ASSIGNMENT_RECEIPT','assignment_id':x['assignment_id'],'receipt_id':out['receipt_id'],'result_digest':out['result_digest'],'payload_retained':True,'status':x['status'],'authority_effect':'NONE'},'IN')
      out['payload_store']=payload_store
      c.commit();return out
    finally:c.close()

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
  if path=='/health':return self.json({'status':'ok','mission_id':focus_mission_id(),'mission_count':len(mission_summaries()),'control':'BOUNDED','authority_effect':'NONE','broker_schema':saas_broker.SCHEMA_ID,'collector':'MULTI_SQLITE_READ_MODEL'})
  if path.startswith('/api/v3/saas-broker/'):
   try:return self.json(saas_broker_api('GET',path))
   except ValueError as e:return self.json({'error':str(e)},404)
  current=snapshot()
  compat=compat_get(path,current)
  if compat is not None:
   code,ctype,body=compat
   if isinstance(body,(dict,list)):return self.json(body,code)
   return self.send_content(body,ctype,code)
  if path in {'/api/v3/missions/current','/api/v3/missions/'+MISSION}:return self.json(current)
  if path=='/api/v3/missions':return self.json({'missions':mission_summaries(),'process_missions':recent_process_missions(),'legacy_recorded_runs':legacy_count()})
  if path=='/api/v3/missions/recent':
   try:
    q=parse_qs(urlparse(self.path).query);view=_view_name((q.get('view') or ['operational'])[0]);return self.json({'missions':recent_process_missions(view),'focus_mission_id':focus_mission_id(view),'view':view})
   except ValueError as e:return self.json({'error':str(e)},400)
  if path=='/api/v3/capabilities/process-contracts':return self.json(process_capability_registry_snapshot())
  if path.startswith('/api/v3/missions/') and path.endswith('/delete-preview'):
   mid=path[len('/api/v3/missions/'):-len('/delete-preview')].strip('/');c=connect()
   try:return self.json(mission_delete_preview(c,mid,MISSION))
   finally:c.close()
  if path.startswith('/api/v3/missions/') and path.endswith('/process'):
   mid=path[len('/api/v3/missions/'):-len('/process')].strip('/')
   try:return self.json(process_snapshot(mid))
   except ValueError as e:return self.json({'error':str(e)},404)
  if path.startswith('/api/v3/missions/') and path.endswith('/messages'):
   mid=path[len('/api/v3/missions/'):-len('/messages')].strip('/')
   try:return self.json({'mission_id':mid,'messages':process_snapshot(mid)['protocol_messages']})
   except ValueError as e:return self.json({'error':str(e)},404)
  if path=='/api/v3/saas/pending':
   q=parse_qs(urlparse(self.path).query);return self.json({'pending':get_saas_pending((q.get('code') or [None])[0],(q.get('mission_id') or [None])[0])})
  if path=='/api/v3/saas/status':
   q=parse_qs(urlparse(self.path).query);mid=(q.get('mission_id') or [focus_mission_id()])[0];return self.json(get_saas_bridge_status(mid))
  if path.startswith('/api/v3/saas/requests/'):
   rid=path[len('/api/v3/saas/requests/'):].strip('/')
   try:return self.json(get_saas_request_status(rid))
   except ValueError as e:return self.json({'error':str(e)},404)
  if path.startswith('/api/v3/dual/'):
   rid=path[len('/api/v3/dual/'):].strip('/')
   try:return self.json(get_dual_result(rid))
   except ValueError as e:return self.json({'error':str(e)},404)
  if path=='/api/v3/local/assignments':
   q=parse_qs(urlparse(self.path).query);mid=(q.get('mission_id') or [None])[0];limit=int((q.get('limit') or ['16'])[0]);return self.json(local_assignment_list(mid,limit))
  return self.json({'error':'not found'},404)
 def do_POST(self):
  path=unquote(urlparse(self.path).path)
  if path.startswith('/api/v3/saas-broker/'):
   controlled=path.endswith(('/claim','/respond','/session/attest','/mediator/heartbeat'))
   if controlled and not mediator_authorized(self.headers):return self.json({'error':'mediator authentication required'},403)
   try:
    n=int(self.headers.get('Content-Length','0'))
    if not 2<=n<=40000 or 'application/json' not in self.headers.get('Content-Type',''):raise ValueError('broker JSON body')
    return self.json(saas_broker_api('POST',path,json.loads(self.rfile.read(n))),201 if path.endswith('/requests') else 200)
   except Exception as e:return self.json({'error':type(e).__name__+':'+str(e)},409)

  if path.startswith('/api/v3/missions/') and path.endswith('/delete'):
   try:
    mid=path[len('/api/v3/missions/'):-len('/delete')].strip('/');n=int(self.headers.get('Content-Length','0'))
    if n<2 or n>4096 or 'application/json' not in self.headers.get('Content-Type',''):raise ValueError('request')
    x=json.loads(self.rfile.read(n))
    if type(x) is not dict or set(x)!={'spec_digest'} or not _hex(x['spec_digest'],64):raise ValueError('delete schema')
    c=connect()
    try:out=delete_mission_records(c,mid,x['spec_digest'],MISSION,now)
    finally:c.close()
    return self.json(out)
   except Exception as e:return self.json({'error':type(e).__name__+':'+str(e)},409)
  if path.startswith('/api/v3/missions/') and path.endswith('/focus'):
   try:
    mid=path[len('/api/v3/missions/'):-len('/focus')];n=int(self.headers.get('Content-Length','0'))
    if n<2 or n>4096 or 'application/json' not in self.headers.get('Content-Type',''):raise ValueError('request')
    return self.json(set_focus_mission(mid,json.loads(self.rfile.read(n))))
   except Exception as e:return self.json({'error':type(e).__name__+':'+str(e)},409)
  if path.startswith('/api/v3/missions/') and path.endswith('/phase-actions'):
   try:
    mid=path[len('/api/v3/missions/'):-len('/phase-actions')].strip('/');n=int(self.headers.get('Content-Length','0'))
    if n<2 or n>4096 or 'application/json' not in self.headers.get('Content-Type',''):raise ValueError('request')
    x=json.loads(self.rfile.read(n));return self.json(apply_phase_action(mid,x,lambda identity:process_snapshot(identity,read_only=True),mission_action))
   except Exception as e:return self.json({'error':type(e).__name__+':'+str(e)},409)
  if path in {'/api/v3/local/assignments/claim','/api/v3/local/assignments/receipt'}:
   try:
    n=int(self.headers.get('Content-Length','0'))
    if n<2 or n>100000 or 'application/json' not in self.headers.get('Content-Type',''):raise ValueError('request')
    x=json.loads(self.rfile.read(n));out=local_assignment_claim(x) if path.endswith('/claim') else local_assignment_receipt(x);return self.json(out)
   except Exception as e:return self.json({'error':type(e).__name__+':'+str(e)},409)
  if path in {'/api/v3/dual/create','/api/v3/dual/link-saas','/api/v3/dual/response'}:
   try:
    n=int(self.headers.get('Content-Length','0'))
    if n<2 or n>100000 or 'application/json' not in self.headers.get('Content-Type',''):raise ValueError('request')
    x=json.loads(self.rfile.read(n))
    if path.endswith('/create'):out=create_dual_evaluation(x)
    elif path.endswith('/link-saas'):out=link_dual_saas(x)
    else:out=record_dual_response(x)
    return self.json(out,201 if path.endswith('/create') else 200)
   except Exception as e:return self.json({'error':type(e).__name__+':'+str(e)},400)
  if path=='/api/v3/saas/request':
   try:
    n=int(self.headers.get('Content-Length','0'))
    if n<2 or n>20000 or 'application/json' not in self.headers.get('Content-Type',''):raise ValueError('request')
    return self.json(create_saas_handoff(json.loads(self.rfile.read(n))),201)
   except Exception as e:return self.json({'error':type(e).__name__+':'+str(e)},400)
  if path=='/api/v3/saas/cancel':
   try:
    n=int(self.headers.get('Content-Length','0'))
    if n<2 or n>4096 or 'application/json' not in self.headers.get('Content-Type',''):raise ValueError('request')
    x=json.loads(self.rfile.read(n))
    if type(x) is not dict or set(x)!={'request_id'} or not _safe_id(x['request_id'],127):raise ValueError('cancel schema')
    c=connect()
    try:out=saas_cancel(c,x['request_id'],now)
    finally:c.close()
    return self.json(out)
   except Exception as e:return self.json({'error':type(e).__name__+':'+str(e)},409)
  if path=='/api/v3/saas/respond':
   try:
    n=int(self.headers.get('Content-Length','0'))
    if n<2 or n>40000 or 'application/json' not in self.headers.get('Content-Type',''):raise ValueError('request')
    return self.json(respond_saas_handoff(json.loads(self.rfile.read(n))),200)
   except Exception as e:return self.json({'error':type(e).__name__+':'+str(e)},409)
  if path=='/api/v3/lifecycle/normalize-epoch3':
   try:
    n=int(self.headers.get('Content-Length','0'))
    if n<2 or n>8192 or 'application/json' not in self.headers.get('Content-Type',''):raise ValueError('request')
    return self.json(execute_epoch3_lifecycle_normalization(json.loads(self.rfile.read(n))),200)
   except Exception as e:return self.json({'error':type(e).__name__+':'+str(e)},409)
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
 ap=argparse.ArgumentParser();ap.add_argument('--host',default='127.0.0.1');ap.add_argument('--port',type=int,default=8767);ap.add_argument('--listen-state',default='/run/lion-mission-control/listen.json');ap.add_argument('--legacy-listen-state',default='/run/lion-vkt-mission-control/listen.json');a=ap.parse_args();migrate();reconcile_phase_execution_contracts();reconcile_lpcl_execution_bindings();observe_once();threading.Thread(target=observer,daemon=True).start();threading.Thread(target=mission_driver_loop,daemon=True).start();srv=ThreadingHTTPServer((a.host,a.port),H);relay=_start_firefox_broker_relay(a.port);loc={'status':'LISTENING','host':a.host,'port':a.port,'pid':os.getpid(),'generation':'MISSION_CONTROL_V3','mission_id':MISSION};
 for lp in (a.listen_state,a.legacy_listen_state):
  q=Path(lp);q.parent.mkdir(parents=True,exist_ok=True);tmp=q.with_name(q.name+'.tmp-'+uuid.uuid4().hex[:8]);tmp.write_text(json.dumps(loc,sort_keys=True),encoding='utf-8');os.replace(tmp,q)
 print(json.dumps(loc),flush=True)
 try:srv.serve_forever()
 finally:
  STOP_EVENT.set();DRIVER_STOP.set();srv.server_close()
  if relay is not None and relay.poll() is None:
   relay.terminate()
   try:relay.wait(timeout=5)
   except subprocess.TimeoutExpired:relay.kill()
if __name__=='__main__':main()
