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
from cyber_lion.mission_control import operator_control
from cyber_lion.mission_control import model_calls as model_call_ledger

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

SECURE_MCP_RELAY_STATE=DB.parent/'secure-mcp-relay'
SECURE_MCP_INGRESS_TOKEN=DB.parent/'secure-mcp-ingress.token'

def _start_secure_mcp_broker_relay(port):
    if os.environ.get('LION_ENABLE_OPENAI_SECURE_MCP_TUNNEL')!='1':
        return None
    relay=Path(__file__).with_name('lion_secure_mcp_broker_relay.py')
    if not relay.is_file() or not FIREFOX_RELAY_KEY.is_file() or not SECURE_MCP_INGRESS_TOKEN.is_file():
        return None
    FIREFOX_RELAY_IPC.mkdir(parents=True,exist_ok=True)
    for name in ('inbox','outbox','journal','receipts','archive','mission-threads'):
        q=FIREFOX_RELAY_IPC/name;q.mkdir(parents=True,exist_ok=True)
    SECURE_MCP_RELAY_STATE.mkdir(parents=True,exist_ok=True)
    return subprocess.Popen([
        sys.executable,str(relay),'--broker',f'http://127.0.0.1:{int(port)}',
        '--mediator-key-file',str(FIREFOX_RELAY_KEY),
        '--ingress','http://127.0.0.1:8791',
        '--ingress-token-file',str(SECURE_MCP_INGRESS_TOKEN),
        '--state-dir',str(SECURE_MCP_RELAY_STATE),
        '--ipc-dir',str(FIREFOX_RELAY_IPC),
    ],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,close_fds=True)


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
   if type(x) is not dict or not {'scope_type','question','authority_effect'}<=set(x) or set(x)-{'scope_type','scope_id','thread_id','mission_id','question','authority_effect','transport'}:raise ValueError('broker request schema')
   return saas_broker.create_request(c,x.get('mission_id'),x['question'],now,scope_type=x['scope_type'],scope_id=x.get('scope_id'),thread_id=x.get('thread_id'),authority_effect=x['authority_effect'],transport=x.get('transport'))
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
    out=saas_broker.respond(c,rid,x['response_token'],x['answer'],now,model_identity=x['model_identity'],transport=x['transport'],attestation_class=x['attestation_class'],claim_generation=x['claim_generation'])
    dual=c.execute('SELECT request_id FROM mission_dual_evaluations WHERE saas_request_id=? ORDER BY updated_at DESC LIMIT 1',(rid,)).fetchone()
    if dual:
     drid=dual['request_id']
     prior=c.execute('SELECT response_digest FROM mission_dual_receipts WHERE request_id=? AND provider=?',(drid,DUAL_SAAS_PROVIDER)).fetchone()
     if prior is None:
      dual_record_response(c,drid,DUAL_SAAS_PROVIDER,x['answer'],now,transport=x['transport'],authority_effect='NONE')
     joined=dual_join_result(c,drid);out['dual_result']=joined
     row=c.execute('SELECT mission_id,phase_id FROM mission_dual_evaluations WHERE request_id=?',(drid,)).fetchone()
     if row:_process_message(c,row['mission_id'],'RECEIPT','CHATGPT_SAAS_SUPERVISOR','DUAL_RESULT_JOIN',row['phase_id'],{'event':'SAAS_BROKER_RECEIPT_AUTO_JOINED','dual_request_id':drid,'dual_state':joined.get('state'),'saas_request_id':rid,'authority_effect':'NONE'},'INTERNAL')
     c.commit()
    return out
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
 operator_control.migrate(c,now)
 model_call_ledger.migrate(c,now)
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
 if action in {'START','RESUME','RESTART_ONE'} and not operator_control.autonomy_allowed(c,MISSION):c.close();raise ValueError('operator control fence prevents material expansion')
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
LPCL_DOCKER_LOCAL_MODEL_ADAPTER='LPCL_DOCKER_LOCAL_MODEL'
DOCKER_LOCAL_MODEL_CURRENTNESS=Path('/mnt/c/Users/d2j3/AppData/Local/LION/r23-autonomy/fleet-currentness.json')
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
 'OPERATOR_INTERVENTION':(
  {'capability_id':'OPERATOR_CONTROL_R1','executor_id':'LION_OPERATOR_CONTROL_GATEWAY','effect_ceiling':'MISSION_SCOPED_CONTROL_STATE','mode':'AUTHENTICATED_FENCED_INTERVENTION'},
 ),
 'OPERATOR_CONTAINMENT':(
  {'capability_id':'OPERATOR_CONTAINMENT_R1','executor_id':'LION_OPERATOR_CONTROL_GATEWAY','effect_ceiling':'MISSION_SCOPED_CONTAINMENT','mode':'LATCH_FENCE_AND_CHECKPOINT'},
  {'capability_id':'OPERATOR_EMERGENCY_CONTAINMENT_R1','executor_id':'LION_OPERATOR_CONTAINMENT_HELPER','effect_ceiling':'PREPROVISIONED_PROCESS_STOP','mode':'EXACT_INVENTORY_ONLY'},
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



def _docker_local_model_currentness(expected_material):
    if type(expected_material) is not int or not 1<=expected_material<=32:raise ValueError("docker material target must be 1..32")
    try:value=json.loads(DOCKER_LOCAL_MODEL_CURRENTNESS.read_text(encoding="utf-8"))
    except Exception as exc:raise ValueError("docker fleet currentness unavailable:"+type(exc).__name__) from exc
    if value.get("schema")!="lion.docker-local-model-fleet-currentness/v1" or value.get("physical_host")!="MOON":raise ValueError("docker fleet currentness identity")
    dg=value.get("currentness_digest");body=dict(value);body.pop("currentness_digest",None)
    if not _hex(str(dg or ""),64) or _payload_digest(body)!=dg:raise ValueError("docker fleet currentness digest")
    from datetime import datetime as _dt,timezone as _tz
    try:observed=_dt.fromisoformat(str(value.get("observed_at")).replace("Z","+00:00"))
    except Exception as exc:raise ValueError("docker fleet currentness timestamp") from exc
    age=(_dt.now(_tz.utc)-observed).total_seconds()
    if age<0 or age>20:raise ValueError("docker fleet currentness stale")
    workers=value.get("workers") or []
    if value.get("state")!="READY" or int(value.get("materialized",0))!=32 or int(value.get("ready",0))!=32 or len(workers)!=32:raise ValueError("docker fleet not ready")
    expected_pool={f"MD{i:03d}" for i in range(1,33)}
    ids={str(w.get("material_worker_id") or "") for w in workers};cids={str(w.get("container_id") or "") for w in workers}
    if ids!=expected_pool or len(cids)!=32 or "" in cids:raise ValueError("docker fleet material identity")
    by={str(w.get("material_worker_id") or ""):w for w in workers}
    selected_ids=[f"MD{i:03d}" for i in range(1,expected_material+1)]
    normalized=[]
    for mid in selected_ids:
        w=by[mid]
        if not w.get("ready") or w.get("container_state")!="running" or w.get("model")!="gpt-oss-20b-MXFP4":raise ValueError("docker worker readiness")
        normalized.append({"material_worker_id":mid,"pod_name":w["container_name"],"pod_uid":w["container_id"],"container_id":w["container_id"],"ready":1,"phase":"DOCKER_LOCAL_MODEL","restarts":0,"pod_ip":None,"model":w["model"]})
    return {"digest":dg,"observed_at":value["observed_at"],"workers":normalized,"physical_failure_domains":int(value.get("physical_failure_domains") or 1),"pool_materialized":32,"pool_ready":32,"selected_material":expected_material}

def bind_lpcl_execution(mid):
    c=connect()
    try:
      m=c.execute('SELECT mission_id,state,spec_digest,source_head,source_tree,logical_count,material_target,adapter FROM missions WHERE mission_id=?',(mid,)).fetchone()
      ps=c.execute('SELECT lpcl_text,authority_state,current_phase,progress FROM mission_process_specs WHERE mission_id=?',(mid,)).fetchone()
      if not m or not ps:return None
      if m['state'] not in {'AUTHORIZED','RUNNING','WAITING','BLOCKED'} or ps['authority_state']!='EXPLICIT_USER_ACTIVATION':return None
      if not operator_control.autonomy_allowed(c,mid):return process_snapshot(mid)
      kv=_lpcl_pairs(ps['lpcl_text'])
      docker_mode=str(kv.get('MATERIAL_RUNTIME') or '').strip().upper()=='DOCKER_LOCAL_MODEL'
      if not docker_mode and (m['material_target']!=64 or m['logical_count'] not in {12,128}):raise ValueError('lpcl execution adapter cardinality')
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
      if docker_mode:
       if continuation_ok or source_mid is not None:raise ValueError('docker local model binding requires fresh mission')
       observed=_docker_local_model_currentness(int(m['material_target']))
       if m['adapter']==LPCL_DOCKER_LOCAL_MODEL_ADAPTER:
        own=c.execute('SELECT pod_uid,ready FROM material_workers WHERE mission_id=?',(mid,)).fetchall()
        logical_total=c.execute('SELECT COUNT(*) FROM logical_drones WHERE mission_id=?',(mid,)).fetchone()[0]
        topo_total=c.execute("SELECT COUNT(*) FROM mission_execution_assignments WHERE mission_id=? AND phase_id='__TOPOLOGY__'",(mid,)).fetchone()[0]
        own_uids={r['pod_uid'] for r in own if r['pod_uid']}
        observed_uids={str(w['pod_uid']) for w in observed['workers'] if w.get('pod_uid')}
        material_count=int(m['material_target'])
        if len(own)==material_count and len(own_uids)==material_count and own_uids==observed_uids and all(int(r['ready'])==1 for r in own) and logical_total==int(m['logical_count']) and topo_total==int(m['logical_count']):
         c.execute('UPDATE missions SET runtime_state=?,materialized=?,ready=?,last_error=NULL,updated_at=? WHERE mission_id=?',('DOCKER_LOCAL_MODEL_FLEET_BOUND',material_count,material_count,now(),mid));c.commit();return process_snapshot(mid)
       role_prefix=str(kv.get('LOGICAL_ROLE_PREFIX') or 'AUTONOMOUS_LOGICAL').strip().upper()[:48]
       bound=global_sched.bind_dynamic_local_model_fleet(c,mid,int(m['logical_count']),observed['workers'],now,adapter=LPCL_DOCKER_LOCAL_MODEL_ADAPTER,runtime_state='DOCKER_LOCAL_MODEL_FLEET_BOUND',role_prefix=role_prefix,currentness_digest=observed['digest'])
       generic={'handler_id':'GENERIC_LPCL_PHASE','effect_class':'NONE','gate_class':'COGNITIVE_PLAN','retry_policy':'IDEMPOTENT','authority_class':'NONE'}
       handlers={prow['phase_id']:generic for prow in c.execute('SELECT phase_id FROM mission_phases WHERE mission_id=?',(mid,)).fetchall()}
       global_sched.compile_phase_specs(c,mid,handlers)
       nxt=c.execute("SELECT phase_id FROM mission_phases WHERE mission_id=? AND status NOT IN ('PASS','COMPLETE','SKIPPED','CANCELLED') ORDER BY ordinal LIMIT 1",(mid,)).fetchone()
       current=nxt['phase_id'] if nxt else None;t=now()
       c.execute('UPDATE mission_process_specs SET current_phase=?,updated_at=? WHERE mission_id=?',(current,t,mid))
       if current:c.execute("UPDATE mission_phases SET status=CASE WHEN status='PENDING' THEN 'RUNNING' ELSE status END,started_at=COALESCE(started_at,?),updated_at=? WHERE mission_id=? AND phase_id=?",(t,t,mid,current))
       ensure_driver(c,mid,now,initial_state='BOOTSTRAP_PAUSED')
       prior=driver_snapshot(c,mid)
       if prior and prior['state']=='ACTIVE' and prior.get('lease_owner')!=DRIVER_PROCESS_ID:driver_wait_for_execution_binding(c,mid,now,blocking_gate='EXECUTION_REBIND_HANDOFF',waiting_reason='Dynamic Docker binding superseded an orphan active driver',next_action='EXECUTION_BINDING_READY')
       driver_activate(c,mid,now,next_action='GLOBAL_SCHEDULER_DISPATCH',owner_id=DRIVER_PROCESS_ID,lease_seconds=30)
       selected_material=int(m['material_target'])
       _process_message(c,mid,'CURRENTNESS','DOCKER_FLEET_CURRENTNESS','MISSION_CONTROL',current,{'event':'DOCKER_LOCAL_MODEL_FLEET_CURRENTNESS_BOUND','currentness_digest':observed['digest'],'observed_at':observed['observed_at'],'material_count':selected_material,'pool_materialized':observed.get('pool_materialized',32),'pool_ready':observed.get('pool_ready',32),'logical_count':int(m['logical_count']),'physical_failure_domains':observed['physical_failure_domains'],'model':'gpt-oss-20b-MXFP4','authority_effect':'NONE'},'INTERNAL')
       _process_message(c,mid,'ASSIGNMENT','MISSION_CONTROL','GLOBAL_SCHEDULER',current,{'event':'DYNAMIC_DOCKER_LOCAL_MODEL_BOUND','adapter':LPCL_DOCKER_LOCAL_MODEL_ADAPTER,'logical_count':int(m['logical_count']),'material_count':selected_material,'pool_materialized':observed.get('pool_materialized',32),'assignments':bound['assignments'],'distribution':bound['distribution'],'authority_effect':'MISSION_SCOPED_CONTROL_BINDING'},'INTERNAL')
       c.commit();return process_snapshot(mid)
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
      runtime,material_request_id=epoch3_broker('EPOCH3_M64_READ',source_mission_id=source_mid)
      execution_currentness=runtime.get('_execution_currentness') or {}
      execution_head=execution_currentness.get('source_head');execution_tree=execution_currentness.get('source_tree');currentness_request_id=execution_currentness.get('currentness_request_id')
      live_pods=runtime.get('pods') or []
      if runtime.get('state')!='RUNNING' or int(runtime.get('materialized',0) or 0)!=64 or int(runtime.get('ready',0) or 0)!=64 or int(runtime.get('unique_uid_count',0) or 0)!=64 or len(live_pods)!=64:
       raise ValueError('lpcl live material fleet not healthy')
      workers=[]
      for pod in live_pods:
       workers.append({'pod_name':pod.get('name'),'pod_uid':pod.get('uid'),'logical_id':str(pod.get('logical_drone') or '').upper(),'phase':pod.get('phase'),'ready':1 if pod.get('ready') else 0,'restarts':int(pod.get('restarts',0) or 0),'pod_ip':pod.get('pod_ip')})
      if len({r['pod_uid'] for r in workers if r['pod_uid']})!=64 or any(int(r['ready'])!=1 for r in workers):raise ValueError('lpcl live material fleet identity')
      if _hex(str(execution_head or ''),40) and _hex(str(execution_tree or ''),40):
       _process_message(c,mid,'CURRENTNESS','MISSION_CONTROL_CURRENTNESS_RECONCILER','LD02',None,{'event':'EXECUTION_CURRENTNESS_REACQUIRED','registered_source_head':m['source_head'],'registered_source_tree':m['source_tree'],'execution_source_head':execution_head,'execution_source_tree':execution_tree,'currentness_request_id':currentness_request_id,'material_request_id':material_request_id,'authority_effect':'NONE'},'INTERNAL')
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
      # Lineage is metadata only; authority remains exact LPCL. A fresh mission
      # is its own lineage root and has no parent.
      lineage_root=source_mid or mid
      lineage_parent=source_mid
      lineage_relation='COMPLEMENTARY_CONTROL_PLANE_REPAIR_CHILD' if source_mid else 'FRESH_SHARED_MATERIAL_BINDING'
      lineage_epoch='EPOCH3_CLOSURE' if source_mid else 'CURRENT'
      try:
       c.execute("INSERT INTO mission_lineage(mission_id,root_mission_id,parent_mission_id,revision,relation,source_epoch,source_stage,source_schema,created_at) VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(mission_id) DO UPDATE SET root_mission_id=excluded.root_mission_id,parent_mission_id=excluded.parent_mission_id,relation=excluded.relation",(mid,lineage_root,lineage_parent,1,lineage_relation,lineage_epoch,'MISSION_PROCESS_SCHEMA_V1','lion.mission-process/v1',t))
      except sqlite3.OperationalError:pass
      uid_digest=_payload_digest({'uids':new_uids})
      changed=old_uids!=new_uids
      _process_message(c,mid,'ASSIGNMENT','MISSION_CONTROL','MATERIAL_FLEET',current,{'event':'EXISTING_HEALTHY_FLEET_REBOUND','source_mission_id':source_mid,'worker_count':64,'unique_uid_count':64,'worker_uid_digest':uid_digest,'previous_binding_changed':changed,'binding_class':'CONTROL_PLANE_REBIND','material_currentness_source':'EPOCH3_M64_READ','material_request_id':material_request_id,'pod_role_environment_rewritten':False,'authority_effect':'MISSION_SCOPED_CONTROL_BINDING'},'INTERNAL')
      _process_message(c,mid,'CURRENTNESS','MISSION_CONTROL','LD02',current,{'event':'CURRENTNESS_REACQUIRED','registered_source_head':m['source_head'],'registered_source_tree':m['source_tree'],'runtime_source_head':execution_head,'runtime_source_tree':execution_tree,'material_ready':64,'material_target':64,'parent_mission_id':source_mid,'material_currentness_source':('GITHUB_MASTER_PLUS_EPOCH3_M64_READ' if _hex(str(execution_head or ''),40) and _hex(str(execution_tree or ''),40) else 'EPOCH3_M64_READ'),'material_request_id':material_request_id},'INTERNAL')
      _process_message(c,mid,'RECEIPT','MISSION_CONTROL','OPERATOR',current,{'event':'LPCL_EXECUTION_ADAPTER_BOUND','adapter':LPCL_REBIND_ADAPTER,'source_mission_id':source_mid,'lpcl_digest':m['spec_digest'],'worker_uid_digest':uid_digest,'parent_preserved':keep_parent},'OUT')
      if fresh_ok:
       generic={'handler_id':'GENERIC_LPCL_PHASE','effect_class':'NONE','gate_class':'COGNITIVE_PLAN','retry_policy':'IDEMPOTENT','authority_class':'NONE'}
       handlers={prow['phase_id']:generic for prow in c.execute('SELECT phase_id FROM mission_phases WHERE mission_id=?',(mid,)).fetchall()}
       global_sched.compile_phase_specs(c,mid,handlers)
      ensure_driver(c,mid,now,initial_state='BOOTSTRAP_PAUSED')
      c.commit()
    finally:c.close()
    return process_snapshot(mid)


def reconcile_lpcl_execution_bindings():
    c=connect()
    try:
      rows=[r['mission_id'] for r in c.execute("SELECT m.mission_id FROM missions m JOIN mission_process_specs p ON p.mission_id=m.mission_id WHERE p.authority_state='EXPLICIT_USER_ACTIVATION' AND m.state IN ('AUTHORIZED','RUNNING','WAITING','BLOCKED') AND m.adapter IN ('LPCL_MISSION','LPCL_REBOUND_EPOCH3_64','LPCL_GENERIC_128L64M','LPCL_DOCKER_LOCAL_MODEL') ORDER BY m.updated_at DESC").fetchall() if operator_control.autonomy_allowed(c,r['mission_id'])]
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
      c.close();raise ValueError('mission_id already bound