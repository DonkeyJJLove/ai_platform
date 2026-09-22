#!/usr/bin/env python3
from __future__ import annotations
import hashlib,json,subprocess,os
from datetime import datetime,timezone
from pathlib import Path

STATUS_DIR=Path('/srv/lion-e4-candidate-r1/r20-mission/r23-autonomy/status')
OUT=Path('/mnt/c/Users/d2j3/AppData/Local/LION/r23-autonomy/fleet-currentness.json')
LABEL='LION_ROLE=MATERIAL_LOCAL_MODEL_WORKER'
MODEL='gpt-oss-20b-MXFP4'
EXPECTED=32

def now():
    return datetime.now(timezone.utc).isoformat().replace('+00:00','Z')
def parse_time(s):
    try:return datetime.fromisoformat(str(s).replace('Z','+00:00'))
    except Exception:return None

names=subprocess.check_output(['docker','ps','-a','--filter','label='+LABEL,'--format','{{.Names}}'],text=True).splitlines()
rows=[]
observed=datetime.now(timezone.utc)
for name in sorted(x for x in names if x.startswith('lion-r23-md')):
    info=json.loads(subprocess.check_output(['docker','inspect',name],text=True))[0]
    labels=((info.get('Config') or {}).get('Labels') or {})
    wid=labels.get('LION_MATERIAL_WORKER_ID')
    status_path=STATUS_DIR/(str(wid)+'.json')
    heartbeat=None
    if status_path.is_file():
        try:heartbeat=json.loads(status_path.read_text())
        except Exception:heartbeat=None
    hb_time=parse_time((heartbeat or {}).get('observed_at'))
    age=None if hb_time is None else max(0.0,(observed-hb_time).total_seconds())
    state=((info.get('State') or {}).get('Status') or '').lower()
    ready=bool(
        wid and state=='running' and heartbeat and heartbeat.get('state')=='READY'
        and heartbeat.get('model')==MODEL and age is not None and age<=20
    )
    rows.append({
        'material_worker_id':wid,
        'container_name':name,
        'container_id':info.get('Id'),
        'image_id':info.get('Image'),
        'container_state':state,
        'started_at':(info.get('State') or {}).get('StartedAt'),
        'heartbeat_observed_at':(heartbeat or {}).get('observed_at'),
        'heartbeat_age_seconds':age,
        'model':(heartbeat or {}).get('model'),
        'mission_control':(heartbeat or {}).get('mission_control'),
        'model_endpoint':(heartbeat or {}).get('model_endpoint'),
        'ready':ready,
    })

ids=[r.get('material_worker_id') for r in rows]
containers=[r.get('container_id') for r in rows]
healthy=(
    len(rows)==EXPECTED and len(set(ids))==EXPECTED and None not in ids
    and len(set(containers))==EXPECTED and None not in containers
    and all(r['ready'] for r in rows)
)
body={
    'schema':'lion.docker-local-model-fleet-currentness/v1',
    'observed_at':now(),
    'physical_host':'MOON',
    'physical_failure_domains':1,
    'expected_material_workers':EXPECTED,
    'materialized':len(rows),
    'ready':sum(1 for r in rows if r['ready']),
    'unique_worker_ids':len(set(x for x in ids if x)),
    'unique_container_ids':len(set(x for x in containers if x)),
    'model':MODEL,
    'state':'READY' if healthy else 'DEGRADED',
    'workers':rows,
}
canon=json.dumps(body,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
body['currentness_digest']=hashlib.sha256(canon).hexdigest()
OUT.parent.mkdir(parents=True,exist_ok=True)
tmp=OUT.with_suffix('.tmp')
tmp.write_text(json.dumps(body,indent=2,ensure_ascii=False)+chr(10),encoding='utf-8')
os.replace(tmp,OUT)
print(json.dumps({'state':body['state'],'materialized':body['materialized'],'ready':body['ready'],'digest':body['currentness_digest']}))
