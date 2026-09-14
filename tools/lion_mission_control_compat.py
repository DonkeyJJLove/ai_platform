from __future__ import annotations
import hashlib,json,sqlite3,time,threading
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import unquote
LEGACY_DB=Path('/var/lib/sentinelx/uploads/lion-mission-control/mission-control.db')
VKT_DB=Path('/var/lib/sentinelx/uploads/vkt-r3-mission-control/mission-control.db')
VKT_FINAL_DB=Path('/var/lib/sentinelx/uploads/vkt-r3-lpcl-v2-final/mission-control.db')
STATIC=Path('/var/lib/sentinelx/uploads/lion-mission-control-v3/static')
V3_DB=Path('/var/lib/sentinelx/uploads/lion-mission-control-v3/mission-control-v3.db')
CURRENT_ID='LION-R4-PREFLIGHT-L12-M64-MISSION-CONTROL-V3'
V3_READ_LOCK=threading.Lock()

def ro(path):
 c=sqlite3.connect('file:'+str(path)+'?mode=ro',uri=True,timeout=5);c.row_factory=sqlite3.Row;return c

def _json(v,default=None):
 try:return json.loads(v)
 except Exception:return default

def generic_runs():
 if not LEGACY_DB.is_file():return []
 c=ro(LEGACY_DB);rows=c.execute('SELECT payload FROM runs ORDER BY updated_at DESC,run_id').fetchall();c.close();return [_json(r[0],{}) for r in rows]

def current_run(s):
 org={x['logical_id']:int(x.get('material_target') or 0) for x in s.get('logical',[])}
 active={x['logical_id']:int(x.get('ready') or 0) for x in s.get('logical',[])}
 pods=[{'fleet':x.get('logical_id'),'name':x.get('pod_name'),'uid':x.get('pod_uid'),'phase':x.get('phase'),'ready':bool(x.get('ready')),'restarts':int(x.get('restarts') or 0),'pod_ip':x.get('pod_ip')} for x in s.get('workers',[])]
 parts={x['logical_id']:{'participant_id':x['logical_id'],'role':x.get('role'),'fleet':x['logical_id'],'logical_identity':x['logical_id'],'material_identity':f"{x.get('materialized',0)} Kubernetes Pods",'host':'LION-AUTH-LAB','runtime':'K3S','state':'RUNNING' if x.get('ready')==x.get('material_target') else 'PARTIAL','observation_state':'OBSERVED'} for x in s.get('logical',[])}
 val=next((c for c in s.get('commands',[]) if c.get('action')=='VALIDATE' and c.get('status')=='PASS'),None)
 return {'run_id':CURRENT_ID,'process_language':'LPCL/1.1','process_class':'R4_PREFLIGHT_L12_M64_MISSION','adapter_type':'MISSION64_K3S','status':s.get('state','UNKNOWN'),'verification_status':'VERIFIED' if val else 'OBSERVED','phase':'RUNTIME','started_at':s.get('authorized_at') or s.get('created_at'),'finished_at':None,'duration':None,'host':'LION-AUTH-LAB','runtime':'K3S','namespace':s.get('namespace'),'source':{'repository':'DonkeyJJLove/ai_platform','head':s.get('source_head'),'tree':s.get('source_tree')},'target':{'kind':'MISSION64_K3S_FLEET','mission_id':CURRENT_ID},'workload':{'kind':'KubernetesFleet','pods':s.get('material_target',64)},'authority':{'class':'EXPLICIT_USER_AUTHORIZED_MISSION','mission_control':'BOUNDED_MISSION_CONTROL','model_authority':'NONE'},'participants':parts,'metrics':{'pods':int(s.get('materialized') or 0),'fresh_drones':int(s.get('ready') or 0),'fleet_organizations':org,'active_by_organization':active,'drone_pods':pods,'unique_uid_count':len({p['uid'] for p in pods if p.get('uid')})},'artifacts':[],'receipts':[],'cleanup':{},'evidence':{'class':'KUBERNETES_RUNTIME','spec_digest':s.get('spec_digest'),'control_authority':s.get('control_authority'),'last_validation':'PASS' if val else 'UNKNOWN'}}


def _v3_focus_id():
 if not V3_DB.is_file():return CURRENT_ID
 c=ro(V3_DB)
 try:
  row=c.execute("SELECT value FROM mission_meta WHERE key='focus_mission_id'").fetchone()
  if row and row[0] and c.execute('SELECT 1 FROM missions WHERE mission_id=?',(row[0],)).fetchone():return str(row[0])
  first=c.execute('SELECT mission_id FROM missions ORDER BY updated_at DESC,mission_id LIMIT 1').fetchone()
  return first[0] if first else None
 except Exception:return CURRENT_ID
 finally:c.close()

def _v3_has_run(run_id):
 if not V3_DB.is_file():return False
 c=ro(V3_DB)
 try:return c.execute('SELECT 1 FROM missions WHERE mission_id=?',(run_id,)).fetchone() is not None
 except Exception:return False
 finally:c.close()

def _mission_run_from_db(c,m,*,focus_id=None):
 if focus_id is None:
  focus=c.execute("SELECT value FROM mission_meta WHERE key='focus_mission_id'").fetchone();focus_id=str(focus[0]) if focus and focus[0] else CURRENT_ID
 mid=m['mission_id'];ps=c.execute('SELECT * FROM mission_process_specs WHERE mission_id=?',(mid,)).fetchone()
 logical=c.execute('SELECT * FROM logical_drones WHERE mission_id=? ORDER BY logical_id',(mid,)).fetchall()
 workers=c.execute('SELECT * FROM material_workers WHERE mission_id=? ORDER BY logical_id,pod_name',(mid,)).fetchall()
 org={r['logical_id']:int(r['material_target'] or 0) for r in logical};active={r['logical_id']:int(r['ready'] or 0) for r in logical}
 pods=[{'fleet':r['logical_id'],'name':r['pod_name'],'uid':r['pod_uid'],'phase':r['phase'],'ready':bool(r['ready']),'restarts':int(r['restarts'] or 0),'pod_ip':r['pod_ip']} for r in workers]
 parts={r['logical_id']:{'participant_id':r['logical_id'],'role':r['role'],'fleet':r['logical_id'],'logical_identity':r['logical_id'],'material_identity':f"{int(r['materialized'] or 0)} Kubernetes Pods",'host':'LION-AUTH-LAB','runtime':'K3S' if int(m['materialized'] or 0)>0 else 'MISSION_CONTROL','state':'RUNNING' if int(r['ready'] or 0)==int(r['material_target'] or 0) and int(r['material_target'] or 0)>0 else 'PARTIAL_OR_UNKNOWN','observation_state':'OBSERVED' if mid==focus_id else 'RECORDED_PROCESS'} for r in logical}
 current_phase=ps['current_phase'] if ps else None;authority_state=ps['authority_state'] if ps else 'UNKNOWN'
 phases=c.execute('SELECT status,finished_at FROM mission_phases WHERE mission_id=? ORDER BY ordinal',(mid,)).fetchall() if ps else []
 terminal=bool(phases) and all(str(r['status']) in {'PASS','COMPLETE','SKIPPED','CANCELLED'} for r in phases)
 finished=max((r['finished_at'] for r in phases if r['finished_at']),default=None) if terminal else None
 process_class='LION_LPCL_MISSION_PROCESS' if ps else 'MISSION_CORE_RECORD'
 runtime='K3S' if int(m['materialized'] or 0)>0 else 'MISSION_CONTROL'
 state=str(m['state'] or 'UNKNOWN')
 verification='SUPERSEDED' if state=='SUPERSEDED' else ('OBSERVED' if mid==focus_id and state in {'RUNNING','WAITING','BLOCKED'} else 'SCHEMA_AWARE_RECORDED')
 return {'run_id':mid,'process_language':'LPCL/1.1' if ps else 'UNKNOWN','process_class':process_class,'adapter_type':m['adapter'],'status':state,'verification_status':verification,'phase':current_phase or m['runtime_state'] or 'UNKNOWN','started_at':m['authorized_at'] or m['created_at'],'finished_at':finished,'duration':None,'host':'LION-AUTH-LAB','runtime':runtime,'namespace':m['namespace'],'source':{'repository':'DonkeyJJLove/ai_platform','head':m['source_head'],'tree':m['source_tree']},'target':{'kind':'MISSION_PROCESS','mission_id':mid},'workload':{'kind':'KubernetesFleet' if int(m['material_target'] or 0)>0 else 'MissionProcess','pods':int(m['material_target'] or 0)},'authority':{'class':authority_state,'mission_control':'BOUNDED_LPCL_EXECUTION_ADAPTER' if m['adapter']=='LPCL_REBOUND_EPOCH3_64' else 'MISSION_PROCESS_CONTROL','model_authority':'NONE'},'participants':parts,'metrics':{'pods':int(m['materialized'] or 0),'fresh_drones':int(m['ready'] or 0),'fleet_organizations':org,'active_by_organization':active,'drone_pods':pods,'unique_uid_count':len({p['uid'] for p in pods if p.get('uid')})},'artifacts':[],'receipts':[],'cleanup':{},'objective':ps['objective'] if ps else None,'evidence':{'class':'MISSION_PROCESS_DB','record_class':'CURRENT_PROCESS_RECORD' if ps else 'CURRENT_CORE_ONLY','authority_state':authority_state,'spec_digest':m['spec_digest'],'runtime_state':m['runtime_state'],'current_phase':current_phase,'progress':float(ps['progress']) if ps else None,'database_schema':'lion.mission-control.lifecycle-db/v2'}}

def v3_mission_runs():
 with V3_READ_LOCK:return _v3_mission_runs()

def _v3_mission_runs():
 if not V3_DB.is_file():return []
 c=ro(V3_DB);out=[]
 try:
  focus=c.execute("SELECT value FROM mission_meta WHERE key='focus_mission_id'").fetchone();focus_id=str(focus[0]) if focus and focus[0] else CURRENT_ID
  for m in c.execute("SELECT * FROM missions WHERE mission_id<>? AND adapter NOT LIKE 'LEGACY_OBSERVATION:%' ORDER BY updated_at DESC,mission_id",(CURRENT_ID,)).fetchall():out.append(_mission_run_from_db(c,m,focus_id=focus_id))
 finally:c.close()
 return out

def v3_events(run_id):
 if not V3_DB.is_file():return []
 c=ro(V3_DB);out=[]
 try:
  for r in c.execute('SELECT id,observed_at,protocol,from_id,to_id,phase,direction,payload_json FROM protocol_messages WHERE mission_id=? ORDER BY id',(run_id,)).fetchall():
   out.append({'schema_version':'lion.protocol-event/v1','event_id':'protocol-'+str(r['id']),'run_id':run_id,'timestamp':r['observed_at'],'event_type':'PROTOCOL_'+str(r['protocol']),'adapter_type':'MISSION_PROCESS','phase':r['phase'],'source':str(r['from_id'])+'→'+str(r['to_id']),'payload':_json(r['payload_json'],{})})
  for r in c.execute('SELECT id,observed_at,event_type,payload_json FROM mission_events WHERE mission_id=? ORDER BY id',(run_id,)).fetchall():
   out.append({'schema_version':'lion.observation-event/v1','event_id':'mission-'+str(r['id']),'run_id':run_id,'timestamp':r['observed_at'],'event_type':r['event_type'],'adapter_type':'MISSION_PROCESS','phase':None,'payload':_json(r['payload_json'],{})})
 finally:c.close()
 return sorted(out,key=lambda x:str(x.get('timestamp')))

def v3_receipts(run_id):
 if not V3_DB.is_file():return []
 c=ro(V3_DB);out=[]
 try:
  try:
   for r in c.execute('SELECT receipt_id,action,effect_class,status,receipt_digest,created_at,result_json FROM mission_action_receipts WHERE mission_id=? ORDER BY created_at',(run_id,)).fetchall():out.append({'receipt_id':r['receipt_id'],'run_id':run_id,'operation':r['action'],'status':r['status'],'timestamp':r['created_at'],'effect_observed':r['effect_class']!='NONE' and r['status']=='PASS','reconciliation_complete':r['status']=='PASS','digest':r['receipt_digest'],'payload':_json(r['result_json'],{})})
  except Exception:pass
  try:
   for r in c.execute("SELECT request_id,status,responded_at,receipt_digest,response_digest FROM saas_handoff_requests WHERE mission_id=? AND receipt_digest IS NOT NULL ORDER BY responded_at",(run_id,)).fetchall():out.append({'receipt_id':r['receipt_digest'],'run_id':run_id,'operation':'SAAS_HANDOFF','status':r['status'],'timestamp':r['responded_at'],'effect_observed':False,'reconciliation_complete':r['status']=='RESPONDED','digest':r['response_digest'],'payload':{'request_id':r['request_id'],'authority_effect':'NONE'}})
  except Exception:pass
 finally:c.close()
 return out

def deleted_mission_ids():
 if not V3_DB.is_file():return set()
 c=ro(V3_DB)
 try:return {r[0][len('deleted_mission:'):] for r in c.execute("SELECT key FROM mission_meta WHERE key LIKE 'deleted_mission:%'")}
 except sqlite3.OperationalError:return set()
 finally:c.close()

def mission_registry_reset():
 if not V3_DB.is_file():return False
 c=ro(V3_DB)
 try:return c.execute("SELECT 1 FROM mission_meta WHERE key='runtime_mission_reset' AND value='1'").fetchone() is not None
 except sqlite3.OperationalError:return False
 finally:c.close()


def all_runs(s):
 deleted=deleted_mission_ids();focus=_v3_focus_id();rows=([current_run(s)] if s.get('mission_id') or (not mission_registry_reset() and s.get('state')!='NO_ACTIVE_MISSIONS') else [])+v3_mission_runs();seen={r.get('run_id') for r in rows}
 for r in ([] if mission_registry_reset() else generic_runs()):
  if r.get('run_id') not in seen:rows.append(r);seen.add(r.get('run_id'))
 rows=[r for r in rows if r.get('run_id') not in deleted and 'legacy::'+str(r.get('run_id')) not in deleted]
 rows.sort(key=lambda r:(0 if r.get('run_id')==focus else 1,0 if str(r.get('status')).upper() in {'RUNNING','WAITING','BLOCKED','AUTHORIZED'} else 1,str(r.get('started_at') or r.get('finished_at') or '')),reverse=False)
 return rows

def _status_counts(runs):
 active={'RUNNING','STARTING','CLEANING'};complete={'PASS','CLEANED','STOPPED','COMPLETE'}
 vals=[str(r.get('status')).upper() for r in runs]
 return {'recorded_active_runs':sum(v in active for v in vals),'observed_active_runs':0,'authorized_runs':vals.count('AUTHORIZED'),'waiting_runs':vals.count('WAITING'),'blocked_runs':vals.count('BLOCKED'),'paused_runs':vals.count('PAUSED'),'registered_runs':vals.count('REGISTERED'),'completed_runs':sum(v in complete for v in vals),'superseded_runs':sum(v=='SUPERSEDED' for v in vals),'failed_runs':sum(v in {'FAIL','FAILED','ERROR'} for v in vals),'deferred_runs':sum(v=='DEFER' for v in vals)}

def table_count(path,table):
 try:c=ro(path);n=c.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0];c.close();return int(n)
 except Exception:return 0

def source_inventory():
 specs=[('mission_control_v3',V3_DB),('generic_mission_control',LEGACY_DB),('vkt_runtime_history',VKT_DB),('vkt_lpcl_final',VKT_FINAL_DB)]
 out=[]
 for name,path in specs:
  d={'name':name,'path':str(path),'available':path.is_file(),'mode':'READ_ONLY_SOURCE' if name!='mission_control_v3' else 'CONTROL_STATE_RW','currentness':'LIVE' if name=='mission_control_v3' else 'HISTORICAL_EVIDENCE','tables':{}}
  if path.is_file():
   try:
    c=ro(path);tabs=[r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
    for t in tabs:d['tables'][t]=int(c.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0])
    d['data_version']=c.execute('PRAGMA data_version').fetchone()[0];d['page_count']=c.execute('PRAGMA page_count').fetchone()[0];c.close();d['size_bytes']=path.stat().st_size;d['mtime']=path.stat().st_mtime
   except Exception as e:d['error']=type(e).__name__+':'+str(e)[:200]
  out.append(d)
 return {'sources':out,'collector':'MULTI_SQLITE_READ_MODEL','source_count':len(out)}

def _runtime_observation(s, polled_at):
 # Worker observation timestamps are evidence; a fresh API read or mission edit is not.
 stamps=[]
 for worker in s.get('workers',[]):
  try:stamp=datetime.fromisoformat(str(worker['observed_at']).replace('Z','+00:00')).timestamp()
  except (KeyError,TypeError,ValueError):return None,None,False
  stamps.append(stamp)
 observed_at=min(stamps) if stamps else None
 age=polled_at-observed_at if observed_at is not None else None
 fresh=age is not None and 0<=age<=15
 return observed_at,age,fresh


def summary(s):
 polled_at=time.time();runs=all_runs(s);counts=_status_counts(runs);focus=_v3_focus_id()
 cur=next((r for r in runs if r.get('run_id')==focus),None) or current_run(s)
 fleet_run=current_run(s);m=fleet_run.get('metrics') or {}
 observed_at,age,fresh=_runtime_observation(s,polled_at)
 observed=fresh and s.get('state')=='RUNNING' and bool(m.get('drone_pods'))
 counts['observed_active_runs']=int(observed)
 inventory=source_inventory()['sources']
 live=next((x['tables'] for x in inventory if x['name']=='mission_control_v3'),{})
 events=sum(live.get(t,0) for t in ('mission_events','protocol_messages'))
 historical_events=sum(x['tables'].get('events',0) for x in inventory if x['name']!='mission_control_v3')
 arts=table_count(LEGACY_DB,'artifacts')
 sm={**counts,'active_runs':counts['recorded_active_runs'],'hosts':len({r.get('host') for r in runs if r.get('host')}),'workloads':sum(bool(r.get('workload')) for r in runs),'events':events,'historical_events':historical_events,'artifacts':arts,'run_count':len(runs),'focus_mission_id':focus}
 obs={}
 for r in runs:
  rid=r.get('run_id');st=str(r.get('status') or 'UNKNOWN')
  oc='OBSERVED' if rid==CURRENT_ID and observed else ('SUPERSEDED_HISTORY' if st=='SUPERSEDED' else 'RECORDED_PROCESS')
  obs[rid]={'recorded_status':st,'observation_status':oc,'heartbeat_status':'FRESH_REPORTED' if oc=='OBSERVED' else 'UNKNOWN'}
 org={k:{'total':v,'active':(m.get('active_by_organization') or {}).get(k,0),'idle':max(0,v-(m.get('active_by_organization') or {}).get(k,0))} for k,v in (m.get('fleet_organizations') or {}).items()}
 ready=int(m.get('fresh_drones') or 0);fm=cur.get('metrics') or {};target=int((cur.get('workload') or {}).get('pods') or 0)
 focus_observed=focus==CURRENT_ID and observed
 readiness='READY' if focus_observed and target>0 and ready==target else ('DEGRADED' if focus_observed else 'UNKNOWN')
 reason='WORKER_OBSERVATIONS_FRESH' if fresh else ('WORKER_OBSERVATIONS_STALE' if age is not None else 'WORKER_OBSERVATIONS_MISSING')
 return {'ok':True,'error':None,'summary':sm,'readiness':{'status':readiness,'focus_mission_id':focus,'ready':int(fm.get('fresh_drones') or 0),'target':target},'fleet':{'currentness':'OBSERVED' if observed else ('STALE' if age is not None and not fresh else 'RECORDED'),'fleet_total':int(m.get('pods') or 0),'working_drones':ready if observed else None,'idle_drones':max(0,int(m.get('pods') or 0)-ready) if observed else None,'organization_count':len(org),'organizations':org,'run_ids':[CURRENT_ID] if s.get('state')!='NO_ACTIVE_MISSIONS' else [],'pod_observations':[{'run_id':CURRENT_ID,'pods':m.get('drone_pods') or []}] if s.get('state')!='NO_ACTIVE_MISSIONS' else []},'run_observations':obs,'observation':{'reason':reason,'attempt_at':polled_at,'completed_at':polled_at,'success_at':observed_at,'age_seconds':age,'success_age_seconds':age,'threshold_seconds':15,'in_progress':False,'scope':'CURRENT_KUBERNETES_COLLECTOR; OTHER_MISSIONS_RECORDED','adapters':{'MISSION_PROCESS_DB':{'reason':'RECORDED'},'MULTI_SQLITE_COLLECTOR':{'reason':reason}}}}


def find_run(run_id,s):
 for r in all_runs(s):
  if r.get('run_id')==run_id:return r
 return None

def generic_table(run_id,table):
 if not LEGACY_DB.is_file():return [] if table in {'events','artifacts','receipts'} else {}
 c=ro(LEGACY_DB)
 if table=='events':rows=c.execute('SELECT payload FROM events WHERE run_id=? ORDER BY ts,event_id',(run_id,)).fetchall();out=[_json(r[0],{}) for r in rows]
 elif table in {'artifacts','receipts'}:rows=c.execute(f'SELECT payload FROM {table} WHERE run_id=? ORDER BY rowid',(run_id,)).fetchall();out=[_json(r[0],{}) for r in rows]
 elif table in {'metrics','participants'}:rows=c.execute(f'SELECT name,payload FROM {table} WHERE run_id=? ORDER BY name',(run_id,)).fetchall();out={r[0]:_json(r[1]) for r in rows}
 else:out=[]
 c.close();return out

def current_events(s):
 p=Path('/var/lib/sentinelx/uploads/lion-mission-control-v3/mission-control-v3.db');c=ro(p);rows=c.execute('SELECT id,observed_at,event_type,payload_json FROM mission_events WHERE mission_id=? ORDER BY id',(CURRENT_ID,)).fetchall();c.close();out=[]
 for r in rows:out.append({'schema_version':'lion.observation-event/v1','event_id':'mcv3-'+str(r['id']),'run_id':CURRENT_ID,'timestamp':r['observed_at'],'event_type':r['event_type'],'process_language':'LPCL/1.1','process_class':'R4_PREFLIGHT_L12_M64_MISSION','adapter_type':'MISSION64_K3S','host':'LION-AUTH-LAB','runtime':'K3S','phase':'RUNTIME','status':s.get('state'),'source':{'repository':'DonkeyJJLove/ai_platform','head':s.get('source_head'),'tree':s.get('source_tree')},'target':{'mission_id':CURRENT_ID},'authority':{'class':'BOUNDED_MISSION_CONTROL'},'payload':_json(r['payload_json'],{})})
 return out

def vkt_deep_events(run_id):
 # Attach deep channel/event history to the canonical historical 384-pod run only.
 if run_id!='LION-LPCL-1_0-VKT-R3-SUPERVISED-LOCAL-384-DRONE-TEST-v2' or not VKT_DB.is_file():return []
 c=ro(VKT_DB);events=[]
 for r in c.execute('SELECT * FROM events ORDER BY ts DESC LIMIT 400').fetchall():
  p=_json(r['payload'],{});events.append({'event_id':r['event_id'],'run_id':run_id,'timestamp':r['ts'],'event_type':r['event_type'],'adapter_type':'VKT_R3','phase':r['phase'],'payload':p})
 for r in c.execute('SELECT * FROM messages ORDER BY ts DESC LIMIT 600').fetchall():
  p=_json(r['payload'],{});events.append({'event_id':'msg-'+r['message_id'],'run_id':run_id,'timestamp':r['ts'],'event_type':'CHANNEL_MESSAGE','adapter_type':'VKT_R3','phase':r['phase'],'payload':p})
 c.close();return sorted(events,key=lambda x:str(x.get('timestamp')))

def current_receipts(s):
 p=Path('/var/lib/sentinelx/uploads/lion-mission-control-v3/mission-control-v3.db');c=ro(p);rows=c.execute('SELECT action,status,finished_at,receipt_json,result_json,command_id FROM commands WHERE mission_id=? ORDER BY requested_at',(CURRENT_ID,)).fetchall();c.close();out=[]
 for r in rows:
  rec=_json(r['receipt_json'],{}) or {}; rid=rec.get('receipt_digest') or ('command:'+r['command_id']);out.append({'receipt_id':rid,'run_id':CURRENT_ID,'operation':r['action'],'status':r['status'],'timestamp':r['finished_at'],'effect_observed':True if r['status']=='PASS' else False,'reconciliation_complete':r['status']=='PASS','payload':rec})
 return out

def current_artifacts():
 out=[]
 for path in [Path('/var/lib/sentinelx/uploads/lion-mission-control-v3/LION_R4_PREFLIGHT_MISSION_FINAL_EVIDENCE.json'),Path('/var/lib/sentinelx/uploads/lion-mission-control-v3/LION_R4_PREFLIGHT_MISSION_FINAL_REPORT.md')]:
  if path.is_file():
   h=hashlib.sha256(path.read_bytes()).hexdigest();out.append({'artifact_id':CURRENT_ID+':'+path.name,'run_id':CURRENT_ID,'type':'MISSION_EVIDENCE','origin':'MISSION_CONTROL_V3','path':str(path),'sha256':h,'size':path.stat().st_size,'verification_state':'LOCAL_HASHED'})
 return out

def adapters():
 return {'ok':True,'adapters':[{'adapter_id':'MISSION64_K3S','supported_process_classes':['R4_PREFLIGHT_L12_M64_MISSION'],'control_authority':'BOUNDED_MISSION_CONTROL'},{'adapter_id':'LPCL_REBOUND_EPOCH3_64','supported_process_classes':['LION_LPCL_MISSION_PROCESS'],'control_authority':'BOUNDED_LPCL_EXECUTION_ADAPTER'},{'adapter_id':'LPCL_MISSION','supported_process_classes':['LION_LPCL_MISSION_PROCESS'],'control_authority':'PROCESS_RECORD_OR_AUTHORIZED_PENDING'},{'adapter_id':'LPCL_EVENT_STREAM','supported_process_classes':['*'],'control_authority':'OBSERVATION_ONLY'},{'adapter_id':'OSS_REPOSITORY_TEST','supported_process_classes':['AUTONOMOUS_LOCAL_K3S_OSS_REPOSITORY_TEST'],'control_authority':'HISTORICAL'},{'adapter_id':'VKT_R3','supported_process_classes':['VKT_R3_384_DRONE_TEST'],'control_authority':'HISTORICAL'},{'adapter_id':'MULTI_SQLITE_COLLECTOR','supported_process_classes':['DATABASE_EVIDENCE'],'control_authority':'NONE'}]}

def compat_get(path,s):
 p=unquote(path)
 if p=='/api/summary':return 200,'application/json; charset=utf-8',summary(s)
 if p=='/api/adapters':return 200,'application/json; charset=utf-8',adapters()
 if p=='/api/runs':return 200,'application/json; charset=utf-8',{'ok':True,'runs':all_runs(s)}
 if p=='/api/export':return 200,'application/json; charset=utf-8',{'ok':True,'export':{'runs':all_runs(s),'evidence_sources':source_inventory()}}
 if p=='/api/v3/evidence-sources':return 200,'application/json; charset=utf-8',source_inventory()
 if p.startswith('/api/runs/'):
  tail=p[len('/api/runs/'):];parts=tail.split('/');run_id=parts[0];r=find_run(run_id,s)
  if r is None:return 404,'application/json; charset=utf-8',{'ok':False,'error':'run-not-found'}
  if len(parts)==1:return 200,'application/json; charset=utf-8',{'ok':True,'run':r}
  kind=parts[1]
  isv3=_v3_has_run(run_id)
  if kind=='events':vals=current_events(s) if run_id==CURRENT_ID else (v3_events(run_id) if isv3 else generic_table(run_id,'events')+vkt_deep_events(run_id));return 200,'application/json; charset=utf-8',{'ok':True,'events':vals}
  if kind=='metrics':vals=r.get('metrics',{}) if (run_id==CURRENT_ID or isv3) else generic_table(run_id,'metrics');return 200,'application/json; charset=utf-8',{'ok':True,'metrics':vals}
  if kind=='participants':vals=r.get('participants',{}) if (run_id==CURRENT_ID or isv3) else generic_table(run_id,'participants');return 200,'application/json; charset=utf-8',{'ok':True,'participants':vals}
  if kind=='artifacts':vals=current_artifacts() if run_id==CURRENT_ID else ([] if isv3 else generic_table(run_id,'artifacts'));return 200,'application/json; charset=utf-8',{'ok':True,'artifacts':vals}
  if kind=='receipts':vals=current_receipts(s) if run_id==CURRENT_ID else (v3_receipts(run_id) if isv3 else generic_table(run_id,'receipts'));return 200,'application/json; charset=utf-8',{'ok':True,'receipts':vals}
 if p.startswith('/api/export/'):
  rid=p[len('/api/export/'):];r=find_run(rid,s);isv3=_v3_has_run(rid);return (200,'application/json; charset=utf-8',{'ok':True,'export':{'run':r,'events':current_events(s) if rid==CURRENT_ID else (v3_events(rid) if isv3 else generic_table(rid,'events')),'metrics':r.get('metrics',{}) if r else {},'participants':r.get('participants',{}) if r else {},'artifacts':current_artifacts() if rid==CURRENT_ID else ([] if isv3 else generic_table(rid,'artifacts')),'receipts':current_receipts(s) if rid==CURRENT_ID else (v3_receipts(rid) if isv3 else generic_table(rid,'receipts'))}}) if r else (404,'application/json; charset=utf-8',{'ok':False,'error':'run-not-found'})
 return None
