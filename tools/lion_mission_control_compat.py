from __future__ import annotations
import hashlib,json,sqlite3,time
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import unquote
LEGACY_DB=Path('/var/lib/sentinelx/uploads/lion-mission-control/mission-control.db')
VKT_DB=Path('/var/lib/sentinelx/uploads/vkt-r3-mission-control/mission-control.db')
VKT_FINAL_DB=Path('/var/lib/sentinelx/uploads/vkt-r3-lpcl-v2-final/mission-control.db')
STATIC=Path('/var/lib/sentinelx/uploads/lion-mission-control-v3/static')
CURRENT_ID='LION-R4-PREFLIGHT-L12-M64-MISSION-CONTROL-V3'

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

def all_runs(s):
 runs=generic_runs();cur=current_run(s);return [cur]+[r for r in runs if r.get('run_id')!=CURRENT_ID]

def _status_counts(runs):
 active={'RUNNING','STARTING','CLEANING','AUTHORIZED','PAUSED'};complete={'PASS','CLEANED','STOPPED'}
 return {'recorded_active_runs':sum(str(r.get('status')).upper() in active for r in runs),'observed_active_runs':1 if runs and runs[0].get('status') in {'RUNNING','PAUSED'} else 0,'completed_runs':sum(str(r.get('status')).upper() in complete for r in runs),'failed_runs':sum(str(r.get('status')).upper()=='FAIL' for r in runs),'deferred_runs':sum(str(r.get('status')).upper()=='DEFER' for r in runs)}

def table_count(path,table):
 try:c=ro(path);n=c.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0];c.close();return int(n)
 except Exception:return 0

def source_inventory():
 specs=[('mission_control_v3',Path('/var/lib/sentinelx/uploads/lion-mission-control-v3/mission-control-v3.db')),('generic_mission_control',LEGACY_DB),('vkt_runtime_history',VKT_DB),('vkt_lpcl_final',VKT_FINAL_DB)]
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

def summary(s):
 runs=all_runs(s);counts=_status_counts(runs);cur=current_run(s);m=cur['metrics'];org={k:{'total':v,'active':m['active_by_organization'].get(k,0),'idle':max(0,v-m['active_by_organization'].get(k,0))} for k,v in m['fleet_organizations'].items()};events=sum(x['tables'].get('events',0) for x in source_inventory()['sources']);arts=table_count(LEGACY_DB,'artifacts')
 sm={**counts,'active_runs':counts['recorded_active_runs'],'hosts':len({r.get('host') for r in runs if r.get('host')}),'workloads':sum(bool(r.get('workload')) for r in runs),'events':events,'artifacts':arts,'run_count':len(runs)}
 obs={r.get('run_id'):{'recorded_status':r.get('status'),'observation_status':'OBSERVED' if r.get('run_id')==CURRENT_ID else 'RECORDED_HISTORY','heartbeat_status':'FRESH_REPORTED' if r.get('run_id')==CURRENT_ID and s.get('ready') else 'UNKNOWN'} for r in runs}
 return {'ok':True,'error':None,'summary':sm,'fleet':{'currentness':'OBSERVED','fleet_total':m['pods'],'working_drones':m['fresh_drones'],'idle_drones':max(0,m['pods']-m['fresh_drones']),'organization_count':len(org),'organizations':org,'run_ids':[CURRENT_ID],'pod_observations':[{'run_id':CURRENT_ID,'pods':m['drone_pods']}]},'run_observations':obs,'observation':{'reason':'OBSERVED','attempt_at':time.time(),'completed_at':time.time(),'success_at':time.time(),'age_seconds':0,'success_age_seconds':0,'threshold_seconds':15,'in_progress':False,'adapters':{'MISSION64_K3S':{'reason':'OBSERVED'},'MULTI_SQLITE_COLLECTOR':{'reason':'OBSERVED'}}}}

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
 return {'ok':True,'adapters':[{'adapter_id':'MISSION64_K3S','supported_process_classes':['R4_PREFLIGHT_L12_M64_MISSION'],'control_authority':'BOUNDED_MISSION_CONTROL'},{'adapter_id':'LPCL_EVENT_STREAM','supported_process_classes':['*'],'control_authority':'OBSERVATION_ONLY'},{'adapter_id':'OSS_REPOSITORY_TEST','supported_process_classes':['AUTONOMOUS_LOCAL_K3S_OSS_REPOSITORY_TEST'],'control_authority':'HISTORICAL'},{'adapter_id':'VKT_R3','supported_process_classes':['VKT_R3_384_DRONE_TEST'],'control_authority':'HISTORICAL'},{'adapter_id':'MULTI_SQLITE_COLLECTOR','supported_process_classes':['DATABASE_EVIDENCE'],'control_authority':'NONE'}]}

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
  if kind=='events':vals=current_events(s) if run_id==CURRENT_ID else generic_table(run_id,'events')+vkt_deep_events(run_id);return 200,'application/json; charset=utf-8',{'ok':True,'events':vals}
  if kind=='metrics':vals=r.get('metrics',{}) if run_id==CURRENT_ID else generic_table(run_id,'metrics');return 200,'application/json; charset=utf-8',{'ok':True,'metrics':vals}
  if kind=='participants':vals=r.get('participants',{}) if run_id==CURRENT_ID else generic_table(run_id,'participants');return 200,'application/json; charset=utf-8',{'ok':True,'participants':vals}
  if kind=='artifacts':vals=current_artifacts() if run_id==CURRENT_ID else generic_table(run_id,'artifacts');return 200,'application/json; charset=utf-8',{'ok':True,'artifacts':vals}
  if kind=='receipts':vals=current_receipts(s) if run_id==CURRENT_ID else generic_table(run_id,'receipts');return 200,'application/json; charset=utf-8',{'ok':True,'receipts':vals}
 if p.startswith('/api/export/'):
  rid=p[len('/api/export/'):];r=find_run(rid,s);return (200,'application/json; charset=utf-8',{'ok':True,'export':{'run':r,'events':current_events(s) if rid==CURRENT_ID else generic_table(rid,'events'),'metrics':r.get('metrics',{}) if r else {},'participants':r.get('participants',{}) if r else {},'artifacts':current_artifacts() if rid==CURRENT_ID else generic_table(rid,'artifacts'),'receipts':current_receipts(s) if rid==CURRENT_ID else generic_table(rid,'receipts')}}) if r else (404,'application/json; charset=utf-8',{'ok':False,'error':'run-not-found'})
 return None
