from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from . import operator_control

SCHEDULER_ID = "GLOBAL_MISSION_SCHEDULER_V1"
ELIGIBLE_DRIVER_STATES = ("ACTIVE", "WAITING", "BLOCKED")
EXCLUDED_DRIVER_STATES = ("PAUSED", "STOPPED", "FAILED", "COMPLETE", "BOOTSTRAP_PAUSED")

DDL = r"""
CREATE TABLE IF NOT EXISTS mission_scheduler_state(
  scheduler_id TEXT PRIMARY KEY,
  generation INTEGER NOT NULL,
  state TEXT NOT NULL,
  heartbeat_at TEXT,
  last_dispatch_at TEXT,
  queue_depth INTEGER NOT NULL DEFAULT 0,
  active_run_count INTEGER NOT NULL DEFAULT 0,
  last_error TEXT
);
CREATE TABLE IF NOT EXISTS mission_phase_execution_specs(
  mission_id TEXT NOT NULL,
  phase_id TEXT NOT NULL,
  handler_id TEXT NOT NULL,
  handler_version TEXT NOT NULL,
  effect_class TEXT NOT NULL,
  gate_class TEXT NOT NULL,
  timeout_seconds INTEGER NOT NULL,
  retry_policy TEXT NOT NULL,
  authority_class TEXT NOT NULL,
  PRIMARY KEY(mission_id, phase_id)
);
CREATE TABLE IF NOT EXISTS mission_phase_execution_contracts(
  mission_id TEXT NOT NULL,
  phase_id TEXT NOT NULL,
  ordinal INTEGER NOT NULL,
  contract_version TEXT NOT NULL,
  execution_class TEXT NOT NULL,
  capability_classes_json TEXT NOT NULL,
  effect_ceiling TEXT NOT NULL,
  binding_mode TEXT NOT NULL,
  on_missing_capability TEXT NOT NULL,
  auto_resume INTEGER NOT NULL,
  verify_before_mutate INTEGER NOT NULL,
  currentness_requirements_json TEXT NOT NULL,
  evidence_requirements_json TEXT NOT NULL,
  completion_predicates_json TEXT NOT NULL,
  contract_source TEXT NOT NULL,
  contract_digest TEXT NOT NULL,
  compiler_version TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  PRIMARY KEY(mission_id, phase_id)
);
CREATE TABLE IF NOT EXISTS mission_execution_preflights(
  mission_id TEXT PRIMARY KEY,
  preflight_json TEXT NOT NULL,
  preflight_digest TEXT NOT NULL,
  generated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS mission_phase_capability_bindings(
  mission_id TEXT NOT NULL,
  phase_id TEXT NOT NULL,
  capability_class TEXT NOT NULL,
  capability_id TEXT NOT NULL,
  state TEXT NOT NULL,
  executor_id TEXT,
  binding_digest TEXT NOT NULL,
  bound_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  PRIMARY KEY(mission_id, phase_id, capability_class)
);
CREATE TABLE IF NOT EXISTS mission_execution_assignments(
  assignment_id TEXT PRIMARY KEY,
  mission_id TEXT NOT NULL,
  phase_id TEXT NOT NULL,
  logical_drone_id TEXT NOT NULL,
  material_drone_id TEXT NOT NULL,
  input_digest TEXT NOT NULL,
  input_json TEXT NOT NULL DEFAULT '{}',
  state TEXT NOT NULL,
  lease_generation INTEGER NOT NULL,
  control_epoch INTEGER NOT NULL DEFAULT 0,
  context_revision INTEGER NOT NULL DEFAULT 0,
  plan_revision INTEGER NOT NULL DEFAULT 0,
  dispatch_authority TEXT NOT NULL DEFAULT 'AUTONOMOUS',
  created_at TEXT NOT NULL,
  claimed_at TEXT,
  lease_expires_at TEXT,
  finished_at TEXT,
  UNIQUE(mission_id, phase_id, logical_drone_id, lease_generation)
);
CREATE TABLE IF NOT EXISTS mission_execution_receipts(
  receipt_id TEXT PRIMARY KEY,
  assignment_id TEXT NOT NULL,
  mission_id TEXT NOT NULL,
  phase_id TEXT NOT NULL,
  result_digest TEXT NOT NULL,
  effect_receipt_digest TEXT,
  authority_effect TEXT NOT NULL,
  status TEXT NOT NULL,
  observed_at TEXT NOT NULL,
  UNIQUE(assignment_id, result_digest)
);
CREATE TABLE IF NOT EXISTS mission_stale_assignment_results(
  stale_result_id TEXT PRIMARY KEY,
  assignment_id TEXT NOT NULL,
  mission_id TEXT NOT NULL,
  phase_id TEXT NOT NULL,
  result_digest TEXT NOT NULL,
  result_json TEXT NOT NULL,
  material_drone_id TEXT,
  lease_generation INTEGER,
  assignment_control_epoch INTEGER,
  observed_control_epoch INTEGER,
  reason TEXT NOT NULL,
  observed_at TEXT NOT NULL,
  UNIQUE(assignment_id,result_digest,reason)
);
CREATE INDEX IF NOT EXISTS idx_stale_assignment_result_mission
  ON mission_stale_assignment_results(mission_id,observed_at,assignment_id);
CREATE INDEX IF NOT EXISTS idx_assignment_mission_state
  ON mission_execution_assignments(mission_id, state, created_at);
CREATE INDEX IF NOT EXISTS idx_receipt_mission_phase
  ON mission_execution_receipts(mission_id, phase_id, observed_at);
CREATE TABLE IF NOT EXISTS mission_scheduler_turns(
  mission_id TEXT PRIMARY KEY,
  last_dispatch_order INTEGER NOT NULL DEFAULT 0,
  dispatch_count INTEGER NOT NULL DEFAULT 0,
  last_dispatched_at TEXT
);
CREATE TABLE IF NOT EXISTS mission_assignment_payloads(
  assignment_id TEXT PRIMARY KEY,
  receipt_id TEXT NOT NULL,
  mission_id TEXT NOT NULL,
  phase_id TEXT NOT NULL,
  result_digest TEXT NOT NULL,
  result_json TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS mission_generic_phase_plans(
  plan_id TEXT PRIMARY KEY,
  mission_id TEXT NOT NULL,
  phase_id TEXT NOT NULL,
  planning_assignment_id TEXT NOT NULL,
  planning_receipt_id TEXT NOT NULL,
  planning_result_digest TEXT NOT NULL,
  planning_payload_state TEXT NOT NULL,
  state TEXT NOT NULL,
  capability TEXT NOT NULL,
  target TEXT NOT NULL,
  operation TEXT NOT NULL,
  required_inputs_json TEXT NOT NULL,
  expected_output_json TEXT NOT NULL,
  authority_class TEXT NOT NULL,
  currentness_requirements_json TEXT NOT NULL,
  evidence_requirements_json TEXT NOT NULL,
  rollback_class TEXT NOT NULL,
  dependencies_json TEXT NOT NULL,
  action_ir_json TEXT NOT NULL,
  action_ir_digest TEXT NOT NULL,
  executor_id TEXT,
  evidence_json TEXT,
  evidence_digest TEXT,
  effect_receipt_digest TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE(mission_id,phase_id)
);
CREATE TABLE IF NOT EXISTS mission_generic_action_receipts(
  receipt_id TEXT PRIMARY KEY,
  plan_id TEXT NOT NULL UNIQUE,
  mission_id TEXT NOT NULL,
  phase_id TEXT NOT NULL,
  action_ir_digest TEXT NOT NULL,
  evidence_digest TEXT NOT NULL,
  authority_effect TEXT NOT NULL,
  status TEXT NOT NULL,
  observed_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS mission_artifacts(
  artifact_id TEXT PRIMARY KEY,
  mission_id TEXT NOT NULL,
  phase_id TEXT,
  artifact_type TEXT NOT NULL,
  schema_id TEXT NOT NULL,
  revision INTEGER NOT NULL DEFAULT 1,
  content_digest TEXT NOT NULL,
  content_json TEXT NOT NULL,
  authority_effect TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE(mission_id,artifact_type,phase_id)
);
CREATE INDEX IF NOT EXISTS idx_mission_artifacts_type
  ON mission_artifacts(mission_id,artifact_type,updated_at);
CREATE TABLE IF NOT EXISTS mission_recon_material_leases(
  lease_id TEXT PRIMARY KEY,
  mission_id TEXT NOT NULL,
  phase_id TEXT NOT NULL,
  logical_drone_id TEXT NOT NULL,
  material_drone_id TEXT NOT NULL,
  purpose TEXT NOT NULL,
  execution_mode TEXT NOT NULL,
  state TEXT NOT NULL,
  acquired_at TEXT NOT NULL,
  released_at TEXT,
  UNIQUE(mission_id,phase_id,material_drone_id)
);
CREATE TABLE IF NOT EXISTS mission_recon_trajectories(
  trajectory_id TEXT PRIMARY KEY,
  mission_id TEXT NOT NULL,
  phase_id TEXT NOT NULL,
  trajectory_role TEXT NOT NULL,
  evidence_bundle_digest TEXT NOT NULL,
  assignment_id TEXT,
  result_digest TEXT,
  response_digest TEXT,
  state TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE(mission_id,phase_id,trajectory_role,evidence_bundle_digest)
);
CREATE TABLE IF NOT EXISTS mission_recon_saas_advisories(
  advisory_id TEXT PRIMARY KEY,
  mission_id TEXT NOT NULL,
  phase_id TEXT NOT NULL,
  evidence_bundle_digest TEXT NOT NULL,
  advisory_role TEXT NOT NULL,
  request_id TEXT,
  state TEXT NOT NULL,
  response_digest TEXT,
  receipt_digest TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE(mission_id,phase_id,evidence_bundle_digest,advisory_role)
);
CREATE TABLE IF NOT EXISTS mission_recon_evidence_generations(
  generation_id TEXT PRIMARY KEY,
  mission_id TEXT NOT NULL,
  phase_id TEXT NOT NULL,
  generation INTEGER NOT NULL,
  source_fingerprint TEXT,
  evidence_bundle_digest TEXT NOT NULL,
  content_json TEXT NOT NULL,
  trigger TEXT NOT NULL,
  created_at TEXT NOT NULL,
  UNIQUE(mission_id,phase_id,generation),
  UNIQUE(mission_id,phase_id,source_fingerprint)
);
CREATE INDEX IF NOT EXISTS idx_recon_evidence_generation
  ON mission_recon_evidence_generations(mission_id,phase_id,generation);
CREATE TABLE IF NOT EXISTS mission_scheduler_migrations(
  version INTEGER PRIMARY KEY,
  schema_id TEXT NOT NULL,
  applied_at TEXT NOT NULL
);
"""


def _canon(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def digest(value):
    return hashlib.sha256(_canon(value).encode("utf-8")).hexdigest()


def migrate(conn, now_fn):
    if [r[0] for r in conn.execute('PRAGMA integrity_check')] != ['ok']:
        raise ValueError('scheduler database integrity before migration')
    conn.executescript(DDL)
    cols={r[1] for r in conn.execute('PRAGMA table_info(mission_execution_assignments)').fetchall()}
    if 'input_json' not in cols:
        conn.execute("ALTER TABLE mission_execution_assignments ADD COLUMN input_json TEXT NOT NULL DEFAULT '{}'")
    if 'lease_expires_at' not in cols:
        conn.execute("ALTER TABLE mission_execution_assignments ADD COLUMN lease_expires_at TEXT")
    for name,ddl in (
        ('control_epoch','INTEGER NOT NULL DEFAULT 0'),('context_revision','INTEGER NOT NULL DEFAULT 0'),('plan_revision','INTEGER NOT NULL DEFAULT 0'),('dispatch_authority',"TEXT NOT NULL DEFAULT 'AUTONOMOUS'"),):
        if name not in cols: conn.execute(f'ALTER TABLE mission_execution_assignments ADD COLUMN {name} {ddl}')
    turn_cols={r[1] for r in conn.execute('PRAGMA table_info(mission_scheduler_turns)')}
    if 'last_dispatch_order' not in turn_cols: conn.execute('ALTER TABLE mission_scheduler_turns ADD COLUMN last_dispatch_order INTEGER NOT NULL DEFAULT 0')
    stamp = now_fn()
    conn.execute("INSERT OR IGNORE INTO mission_scheduler_state(scheduler_id,generation,state,heartbeat_at,queue_depth,active_run_count) VALUES(?,?,?,?,?,?)",(SCHEDULER_ID,1,"ACTIVE",stamp,0,0))
    for version,schema in ((1,'lion.scheduler-storage-reconciliation/v1'),(2,'lion.generic-effect-evidence-executor/v1'),(3,'lion.process-contract-plane/v1'),(4,'lion.control-plane-reconnaissance/v1'),(5,'lion.recon-evidence-reacquisition/v1'),(6,'lion.operator-stale-result-evidence/v1')):
        conn.execute('INSERT OR IGNORE INTO mission_scheduler_migrations VALUES(?,?,?)',(version,schema,stamp))
    if [r[0] for r in conn.execute('PRAGMA integrity_check')] != ['ok']: conn.rollback(); raise ValueError('scheduler database integrity after migration')
    conn.commit()


def put_artifact(conn, mission_id, artifact_type, content, now_fn, *, phase_id=None, schema_id='lion.mission-artifact/v1', authority_effect='NONE'):
    if authority_effect != 'NONE': raise ValueError('mission artifacts are non-authoritative')
    if not isinstance(mission_id,str) or not mission_id or not isinstance(artifact_type,str) or not artifact_type: raise ValueError('artifact identity')
    raw=_canon(content);dg=hashlib.sha256(raw.encode('utf-8')).hexdigest();stamp=now_fn();row=conn.execute('SELECT * FROM mission_artifacts WHERE mission_id=? AND artifact_type=? AND phase_id IS ?',(mission_id,artifact_type,phase_id)).fetchone()
    if row:
        value=dict(row)
        if value['content_digest']==dg:return value
        revision=int(value['revision'])+1;conn.execute('UPDATE mission_artifacts SET schema_id=?,revision=?,content_digest=?,content_json=?,authority_effect=?,updated_at=? WHERE artifact_id=?',(schema_id,revision,dg,raw,authority_effect,stamp,value['artifact_id']));conn.commit();return dict(conn.execute('SELECT * FROM mission_artifacts WHERE artifact_id=?',(value['artifact_id'],)).fetchone())
    artifact_id='artifact-'+uuid.uuid4().hex;conn.execute('INSERT INTO mission_artifacts VALUES(?,?,?,?,?,?,?,?,?,?,?)',(artifact_id,mission_id,phase_id,artifact_type,schema_id,1,dg,raw,authority_effect,stamp,stamp));conn.commit();return dict(conn.execute('SELECT * FROM mission_artifacts WHERE artifact_id=?',(artifact_id,)).fetchone())


def artifact(conn, mission_id, artifact_type, *, phase_id=None):
    row=conn.execute('SELECT * FROM mission_artifacts WHERE mission_id=? AND artifact_type=? AND phase_id IS ?',(mission_id,artifact_type,phase_id)).fetchone()
    if not row:return None
    value=dict(row);value['content']=json.loads(value['content_json'] or '{}');return value


def list_artifacts(conn, mission_id):
    out=[]
    for row in conn.execute('SELECT * FROM mission_artifacts WHERE mission_id=? ORDER BY created_at,artifact_id',(mission_id,)):
        value=dict(row);value['content']=json.loads(value['content_json'] or '{}');out.append(value)
    return out


def record_recon_evidence_generation(conn, mission_id, phase_id, generation, source_fingerprint, evidence_bundle_digest, content, trigger, now_fn):
    if type(generation) is not int or generation < 1:raise ValueError('recon evidence generation')
    if source_fingerprint is not None and (not isinstance(source_fingerprint,str) or len(source_fingerprint)!=64 or any(ch not in '0123456789abcdef' for ch in source_fingerprint)):raise ValueError('recon source fingerprint')
    if not isinstance(evidence_bundle_digest,str) or len(evidence_bundle_digest)!=64:raise ValueError('recon evidence digest')
    if type(content) is not dict or not isinstance(trigger,str) or not trigger:raise ValueError('recon evidence generation content')
    raw=_canon(content);stamp=now_fn();bygen=conn.execute('SELECT * FROM mission_recon_evidence_generations WHERE mission_id=? AND phase_id=? AND generation=?',(mission_id,phase_id,generation)).fetchone()
    if bygen:
        value=dict(bygen)
        if (value['source_fingerprint'],value['evidence_bundle_digest'],value['content_json'],value['trigger']) != (source_fingerprint,evidence_bundle_digest,raw,trigger):raise ValueError('recon evidence generation conflict')
        return value
    if source_fingerprint is not None:
        byfp=conn.execute('SELECT * FROM mission_recon_evidence_generations WHERE mission_id=? AND phase_id=? AND source_fingerprint=?',(mission_id,phase_id,source_fingerprint)).fetchone()
        if byfp:
            value=dict(byfp)
            if value['evidence_bundle_digest']!=evidence_bundle_digest or value['content_json']!=raw:raise ValueError('recon evidence fingerprint conflict')
            return value
    gid='recon-evidence-'+hashlib.sha256(f'{mission_id}|{phase_id}|{generation}|{source_fingerprint or "NONE"}'.encode()).hexdigest()[:32];conn.execute('INSERT INTO mission_recon_evidence_generations VALUES(?,?,?,?,?,?,?,?,?)',(gid,mission_id,phase_id,generation,source_fingerprint,evidence_bundle_digest,raw,trigger,stamp));conn.commit();return dict(conn.execute('SELECT * FROM mission_recon_evidence_generations WHERE generation_id=?',(gid,)).fetchone())


def recon_evidence_generations(conn, mission_id, phase_id):
    out=[]
    for row in conn.execute('SELECT * FROM mission_recon_evidence_generations WHERE mission_id=? AND phase_id=? ORDER BY generation',(mission_id,phase_id)):
        value=dict(row);value['content']=json.loads(value['content_json'] or '{}');out.append(value)
    return out


def scheduler_snapshot(conn):
    row=conn.execute("SELECT * FROM mission_scheduler_state WHERE scheduler_id=?",(SCHEDULER_ID,)).fetchone();return dict(row) if row else None


def heartbeat(conn, now_fn, *, queue_depth, active_run_count, last_error=None, dispatched=False):
    stamp=now_fn();conn.execute("UPDATE mission_scheduler_state SET state='ACTIVE',heartbeat_at=?,last_dispatch_at=CASE WHEN ? THEN ? ELSE last_dispatch_at END,queue_depth=?,active_run_count=?,last_error=? WHERE scheduler_id=?",(stamp,1 if dispatched else 0,stamp,int(queue_depth),int(active_run_count),last_error,SCHEDULER_ID));conn.commit();return scheduler_snapshot(conn)


def store_phase_execution_contracts(conn, mission_id, contracts, now_fn):
    stamp=now_fn();out=[]
    for contract in contracts:
        value=contract.as_dict()
        if value['mission_id']!=mission_id:raise ValueError('phase contract mission mismatch')
        conn.execute("""INSERT INTO mission_phase_execution_contracts(mission_id,phase_id,ordinal,contract_version,execution_class,capability_classes_json,effect_ceiling,binding_mode,on_missing_capability,auto_resume,verify_before_mutate,currentness_requirements_json,evidence_requirements_json,completion_predicates_json,contract_source,contract_digest,compiler_version,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(mission_id,phase_id) DO UPDATE SET ordinal=excluded.ordinal,contract_version=excluded.contract_version,execution_class=excluded.execution_class,capability_classes_json=excluded.capability_classes_json,effect_ceiling=excluded.effect_ceiling,binding_mode=excluded.binding_mode,on_missing_capability=excluded.on_missing_capability,auto_resume=excluded.auto_resume,verify_before_mutate=excluded.verify_before_mutate,currentness_requirements_json=excluded.currentness_requirements_json,evidence_requirements_json=excluded.evidence_requirements_json,completion_predicates_json=excluded.completion_predicates_json,contract_source=excluded.contract_source,contract_digest=excluded.contract_digest,compiler_version=excluded.compiler_version,updated_at=excluded.updated_at""",(mission_id,value['phase_id'],value['ordinal'],value['contract_version'],value['execution_class'],_canon(value['capability_classes']),value['effect_ceiling'],value['binding_mode'],value['on_missing_capability'],1 if value['auto_resume'] else 0,1 if value['verify_before_mutate'] else 0,_canon(value['currentness_requirements']),_canon(value['evidence_requirements']),_canon(value['completion_predicates']),value['contract_source'],value['contract_digest'],value['compiler_version'],stamp,stamp));out.append(value)
    conn.commit();return out


def phase_execution_contract(conn, mission_id, phase_id):
    row=conn.execute('SELECT * FROM mission_phase_execution_contracts WHERE mission_id=? AND phase_id=?',(mission_id,phase_id)).fetchone()
    if not row:return None
    value=dict(row)
    for key in ('capability_classes_json','currentness_requirements_json','evidence_requirements_json','completion_predicates_json'):value[key.removesuffix('_json')]=json.loads(value.pop(key) or '[]')
    value['auto_resume']=bool(value['auto_resume']);value['verify_before_mutate']=bool(value['verify_before_mutate']);return value


def store_execution_preflight(conn, mission_id, preflight, now_fn):
    value=preflight.as_dict() if hasattr(preflight,'as_dict') else dict(preflight);digest_value=str(value.get('preflight_digest') or digest({k:v for k,v in value.items() if k!='preflight_digest'}));stamp=now_fn();conn.execute("INSERT INTO mission_execution_preflights VALUES(?,?,?,?) ON CONFLICT(mission_id) DO UPDATE SET preflight_json=excluded.preflight_json,preflight_digest=excluded.preflight_digest,generated_at=excluded.generated_at",(mission_id,_canon(value),digest_value,stamp));conn.commit();return value


def execution_preflight(conn, mission_id):
    row=conn.execute('SELECT preflight_json FROM mission_execution_preflights WHERE mission_id=?',(mission_id,)).fetchone();return json.loads(row[0]) if row else None


def bind_phase_capability(conn, mission_id, phase_id, capability_class, capability, now_fn):
    cid=str(capability['capability_id']);executor=str(capability.get('executor_id') or '') or None;payload={'mission_id':mission_id,'phase_id':phase_id,'capability_class':capability_class,'capability_id':cid,'executor_id':executor,'effect_ceiling':capability.get('effect_ceiling')};dg=digest(payload);stamp=now_fn();conn.execute("""INSERT INTO mission_phase_capability_bindings VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(mission_id,phase_id,capability_class) DO UPDATE SET capability_id=excluded.capability_id,state=excluded.state,executor_id=excluded.executor_id,binding_digest=excluded.binding_digest,updated_at=excluded.updated_at""",(mission_id,phase_id,capability_class,cid,'BOUND',executor,dg,stamp,stamp));conn.commit();return {**payload,'state':'BOUND','binding_digest':dg,'bound_at':stamp}


def phase_capability_bindings(conn, mission_id, phase_id=None):
    rows=conn.execute('SELECT * FROM mission_phase_capability_bindings WHERE mission_id=? ORDER BY phase_id,capability_class',(mission_id,)).fetchall() if phase_id is None else conn.execute('SELECT * FROM mission_phase_capability_bindings WHERE mission_id=? AND phase_id=? ORDER BY capability_class',(mission_id,phase_id)).fetchall();return [dict(r) for r in rows]


def resolve_phase_execution_spec(phase_id, handlers, *, default_timeout=300):
    pid=str(phase_id);configured=handlers.get(pid)
    if configured is None:return {"handler_id":"PHASE_HANDLER_NOT_REGISTERED","handler_version":"1","effect_class":"NONE","gate_class":"WAITING","timeout_seconds":int(default_timeout),"retry_policy":"NO_AUTOMATIC_RETRY","authority_class":"NONE"}
    spec=dict(configured)
    if not spec.get("handler_id"):raise ValueError("phase handler id")
    spec.setdefault("handler_version","1");spec.setdefault("effect_class","NONE");spec.setdefault("gate_class","NONE");spec.setdefault("timeout_seconds",int(default_timeout));spec.setdefault("retry_policy","NO_AUTOMATIC_RETRY");spec.setdefault("authority_class","NONE");spec["timeout_seconds"]=int(spec["timeout_seconds"]);return spec


def compile_phase_specs(conn, mission_id, handlers, *, default_timeout=300):
    rows=conn.execute("SELECT phase_id FROM mission_phases WHERE mission_id=? ORDER BY ordinal",(mission_id,)).fetchall();out=[]
    for row in rows:
        pid=str(row["phase_id"]);spec=resolve_phase_execution_spec(pid,handlers,default_timeout=default_timeout);conn.execute("INSERT INTO mission_phase_execution_specs VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(mission_id,phase_id) DO UPDATE SET handler_id=excluded.handler_id,handler_version=excluded.handler_version,effect_class=excluded.effect_class,gate_class=excluded.gate_class,timeout_seconds=excluded.timeout_seconds,retry_policy=excluded.retry_policy,authority_class=excluded.authority_class",(mission_id,pid,spec["handler_id"],spec["handler_version"],spec["effect_class"],spec["gate_class"],spec["timeout_seconds"],spec["retry_policy"],spec["authority_class"]));out.append({"phase_id":pid,**spec})
    conn.commit();return out


def _parse_range(value,prefix):
    left,right=str(value).split("-",1)
    if not left.startswith(prefix) or not right.startswith(prefix):raise ValueError("logical/material range prefix")
    a,b=int(left[len(prefix):]),int(right[len(prefix):])
    if a>b:raise ValueError("descending range")
    return tuple(f"{prefix}{i:03d}" for i in range(a,b+1))


def parse_128l64m_topology(lpcl_text):
    lines=[x.strip() for x in str(lpcl_text).replace("\r","").split("\n")];cohorts=[];i=0
    while i<len(lines):
        line=lines[i]
        if line.startswith("COHORT_") and "=" in line:
            key,value=line.split("=",1)
            if not value:
                i+=1
                while i<len(lines) and not lines[i]:i+=1
                value=lines[i] if i<len(lines) else ""
            range_value,separator,inline_role=value.partition("|");range_value=range_value.strip();inline_role=inline_role.strip() if separator else "";logical=_parse_range(range_value,"LD");role=inline_role or None;material=None
            if inline_role:
                suffix=key[len("COHORT_"):]
                if len(suffix)!=2 or not suffix.isdigit():raise ValueError("invalid compact cohort key")
                cohort_index=int(suffix)
                if not 1<=cohort_index<=16:raise ValueError("compact cohort ordinal out of range")
                first_material=(cohort_index-1)*4+1;material=tuple(f"MD{x:03d}" for x in range(first_material,first_material+4))
            j=i+1
            while j<len(lines) and not lines[j].startswith("COHORT_"):
                if lines[j]=="ROLE=" or lines[j].startswith("ROLE="):
                    rv=lines[j].split("=",1)[1]
                    if not rv:
                        j+=1
                        while j<len(lines) and not lines[j]:j+=1
                        rv=lines[j] if j<len(lines) else ""
                    role=rv
                if lines[j]=="MATERIAL=" or lines[j].startswith("MATERIAL="):
                    mv=lines[j].split("=",1)[1]
                    if not mv:
                        j+=1
                        while j<len(lines) and not lines[j]:j+=1
                        mv=lines[j] if j<len(lines) else ""
                    material=_parse_range(mv,"MD")
                j+=1
            if len(logical)!=8 or not role or material is None or len(material)!=4:raise ValueError("invalid 128L64M cohort")
            cohorts.append((key,logical,role,material));i=j;continue
        i+=1
    if len(cohorts)!=16:raise ValueError("expected 16 cohorts")
    logical_ids=[lid for _,ids,_,_ in cohorts for lid in ids];material_ids=[mid for _,_,_,ids in cohorts for mid in ids]
    if logical_ids != [f"LD{i:03d}" for i in range(1,129)]:raise ValueError("logical topology not exact LD001-LD128")
    if material_ids != [f"MD{i:03d}" for i in range(1,65)]:raise ValueError("material topology not exact MD001-MD064")
    return cohorts


def default_128l64m_topology_text(role_prefix="GENERIC_EXECUTION_POOL"):
    lines=[]
    for i in range(1,17):
        la=(i-1)*8+1;lb=i*8;ma=(i-1)*4+1;mb=i*4;lines.extend([f"COHORT_{i:02d}=LD{la:03d}-LD{lb:03d}",f"ROLE={role_prefix}_{i:02d}",f"MATERIAL=MD{ma:03d}-MD{mb:03d}"])
    return "\n".join(lines)+"\n"


def bind_128l64m(conn,mission_id,lpcl_text,workers,now_fn,*,adapter="LPCL_REBOUND_EPOCH3_128L64M",runtime_state="REBOUND_EXISTING_HEALTHY_FLEET_128L64M"):
    cohorts=parse_128l64m_topology(lpcl_text)
    if len(workers)!=64:raise ValueError("material worker count must be 64")
    uids=[str(w.get("pod_uid") or w.get("uid") or "") for w in workers]
    if any(not x for x in uids) or len(set(uids))!=64:raise ValueError("material worker UIDs must be 64 unique non-empty values")
    if any(int(w.get("ready",0) or 0)!=1 for w in workers):raise ValueError("all material workers must be ready")
    ordered=sorted(workers,key=lambda w:(str(w.get("pod_name") or w.get("name") or ""),str(w.get("pod_uid") or w.get("uid") or "")));stamp=now_fn();conn.execute("DELETE FROM logical_drones WHERE mission_id=?",(mission_id,));conn.execute("DELETE FROM material_workers WHERE mission_id=?",(mission_id,));conn.execute("DELETE FROM mission_execution_assignments WHERE mission_id=? AND phase_id='__TOPOLOGY__'",(mission_id,));logical=[]
    for _,ids,role,_ in cohorts:
        for lid in ids:conn.execute("INSERT INTO logical_drones VALUES(?,?,?,?,?,?)",(mission_id,lid,role,0,0,0));logical.append((lid,role))
    for idx,worker in enumerate(ordered,1):
        material_id=f"MD{idx:03d}";pod_name=str(worker.get("pod_name") or worker.get("name") or material_id);pod_uid=str(worker.get("pod_uid") or worker.get("uid"));conn.execute("INSERT INTO material_workers VALUES(?,?,?,?,?,?,?,?,?)",(mission_id,pod_name,pod_uid,material_id,str(worker.get("phase") or "RUNNING"),1,int(worker.get("restarts",0) or 0),worker.get("pod_ip"),stamp))
        for logical_index in (2*idx-2,2*idx-1):
            lid,_=logical[logical_index];assignment_id="topology-"+uuid.uuid4().hex;input_digest=digest({"mission_id":mission_id,"logical_drone_id":lid,"material_drone_id":material_id,"pod_uid":pod_uid});conn.execute("INSERT INTO mission_execution_assignments(assignment_id,mission_id,phase_id,logical_drone_id,material_drone_id,input_digest,input_json,state,lease_generation,created_at,claimed_at,finished_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",(assignment_id,mission_id,"__TOPOLOGY__",lid,material_id,input_digest,_canon({"pod_uid":pod_uid}),"BOUND",1,stamp,stamp,stamp))
    conn.execute("UPDATE missions SET adapter=?,state='RUNNING',runtime_state=?,materialized=64,ready=64,updated_at=?,last_error=NULL WHERE mission_id=?",(str(adapter),str(runtime_state),stamp,mission_id));conn.commit();return {"mission_id":mission_id,"logical_count":128,"material_count":64,"unique_uid_count":64,"assignments":128,"ratio":"2:1","authority_effect":"MISSION_SCOPED_CONTROL_BINDING"}



def bind_dynamic_local_model_fleet(conn,mission_id,logical_count,workers,now_fn,*,adapter="LPCL_DOCKER_LOCAL_MODEL",runtime_state="DOCKER_LOCAL_MODEL_FLEET_BOUND",role_prefix="AUTONOMOUS_LOGICAL",currentness_digest=None):
    if type(logical_count) is not int or not 1<=logical_count<=512:raise ValueError("logical count")
    if not isinstance(workers,list) or not 1<=len(workers)<=32:raise ValueError("material worker count must be 1..32")
    ordered=sorted(workers,key=lambda w:str(w.get("material_worker_id") or ""))
    material_count=len(ordered)
    mids=[str(w.get("material_worker_id") or "") for w in ordered]
    expected=[f"MD{i:03d}" for i in range(1,material_count+1)]
    if mids!=expected:raise ValueError("material worker identity set")
    uids=[str(w.get("pod_uid") or w.get("container_id") or "") for w in ordered]
    if any(not x for x in uids) or len(set(uids))!=material_count:raise ValueError("material worker UIDs")
    if any(int(w.get("ready",0) or 0)!=1 for w in ordered):raise ValueError("all material workers must be ready")
    stamp=now_fn()
    conn.execute("DELETE FROM logical_drones WHERE mission_id=?",(mission_id,))
    conn.execute("DELETE FROM material_workers WHERE mission_id=?",(mission_id,))
    conn.execute("DELETE FROM mission_execution_assignments WHERE mission_id=? AND phase_id='__TOPOLOGY__'",(mission_id,))
    logical=[f"LD{i:03d}" for i in range(1,logical_count+1)]
    distribution={mid:[] for mid in mids}
    for idx,lid in enumerate(logical):
        mid=mids[idx%material_count];distribution[mid].append(lid)
        conn.execute("INSERT INTO logical_drones VALUES(?,?,?,?,?,?)",(mission_id,lid,f"{role_prefix}_{idx+1:03d}",1,1,1))
    by={str(w["material_worker_id"]):w for w in ordered}
    for mid in mids:
        w=by[mid];mapped=distribution[mid]
        pod_name=str(w.get("pod_name") or w.get("container_name") or mid)
        pod_uid=str(w.get("pod_uid") or w.get("container_id"))
        primary=mid
        conn.execute("INSERT INTO material_workers VALUES(?,?,?,?,?,?,?,?,?)",(mission_id,pod_name,pod_uid,primary,"DOCKER_LOCAL_MODEL",1,int(w.get("restarts",0) or 0),w.get("pod_ip"),stamp))
        for lid in mapped:
            aid="topology-"+uuid.uuid4().hex
            value={"material_worker_id":mid,"container_id":pod_uid,"container_name":pod_name,"model":w.get("model"),"currentness_digest":currentness_digest,"binding_class":"DOCKER_LOCAL_MODEL"}
            conn.execute("INSERT INTO mission_execution_assignments(assignment_id,mission_id,phase_id,logical_drone_id,material_drone_id,input_digest,input_json,state,lease_generation,created_at,claimed_at,finished_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",(aid,mission_id,"__TOPOLOGY__",lid,mid,digest(value),_canon(value),"BOUND",1,stamp,stamp,stamp))
    conn.execute("UPDATE missions SET adapter=?,state='RUNNING',runtime_state=?,materialized=?,ready=?,updated_at=?,last_error=NULL WHERE mission_id=?",(str(adapter),str(runtime_state),material_count,material_count,stamp,mission_id))
    conn.commit()
    return {"mission_id":mission_id,"logical_count":logical_count,"material_count":material_count,"unique_uid_count":material_count,"assignments":logical_count,"distribution":sorted((mid,len(distribution[mid])) for mid in mids),"authority_effect":"MISSION_SCOPED_CONTROL_BINDING"}


def eligible_missions(conn):
    rows=conn.execute("SELECT d.mission_id,d.state,d.heartbeat_at,d.current_phase,m.updated_at FROM mission_execution_drivers d JOIN missions m ON m.mission_id=d.mission_id WHERE d.state IN ('ACTIVE','WAITING','BLOCKED') AND m.state NOT IN ('SUPERSEDED','FAILED') ORDER BY CASE d.state WHEN 'ACTIVE' THEN 0 WHEN 'WAITING' THEN 1 ELSE 2 END, COALESCE(d.heartbeat_at,m.updated_at), d.mission_id").fetchall();return [dict(r) for r in rows if operator_control.autonomy_allowed(conn,r['mission_id'])]


def next_dispatch(conn,now_fn):
    conn.execute('SAVEPOINT scheduler_select_turn')
    try:
        conn.execute('UPDATE mission_scheduler_state SET generation=generation WHERE scheduler_id=?',(SCHEDULER_ID,));rows=eligible_missions(conn);turns={r['mission_id']:r['last_dispatch_order'] for r in conn.execute('SELECT mission_id,last_dispatch_order FROM mission_scheduler_turns')};rows.sort(key=lambda r:turns.get(r['mission_id'],0))
        if rows:
            order=conn.execute('SELECT COALESCE(MAX(last_dispatch_order),0)+1 FROM mission_scheduler_turns').fetchone()[0];conn.execute('INSERT INTO mission_scheduler_turns(mission_id,last_dispatch_order,dispatch_count,last_dispatched_at) VALUES(?,?,1,?) ON CONFLICT(mission_id) DO UPDATE SET last_dispatch_order=excluded.last_dispatch_order,dispatch_count=mission_scheduler_turns.dispatch_count+1,last_dispatched_at=excluded.last_dispatched_at',(rows[0]['mission_id'],order,now_fn()))
    except Exception:conn.execute('ROLLBACK TO scheduler_select_turn');conn.execute('RELEASE scheduler_select_turn');raise
    conn.execute('RELEASE scheduler_select_turn');active=sum(1 for r in rows if r["state"]=="ACTIVE");heartbeat(conn,now_fn,queue_depth=len(rows),active_run_count=active,dispatched=bool(rows));return rows[0] if rows else None


def create_assignment(conn,mission_id,phase_id,logical_drone_id,material_drone_id,input_value,now_fn,*,lease_generation,dispatch_authority="AUTONOMOUS"):
    if dispatch_authority not in {"AUTONOMOUS",operator_control.PRIMARY_OPERATOR}:raise ValueError("dispatch authority")
    control=operator_control.control_state(conn,mission_id,now_fn)
    if not operator_control.assignment_allowed(conn,mission_id,dispatch_authority,int(control["control_epoch"])):raise ValueError("operator control fence")
    capability=input_value.get("capability") if isinstance(input_value,dict) else None
    if isinstance(capability,str) and operator_control.is_capability_revoked(conn,mission_id,capability):raise ValueError("capability revoked by operator")
    aid="assignment-"+uuid.uuid4().hex;stamp=now_fn();conn.execute("INSERT INTO mission_execution_assignments(assignment_id,mission_id,phase_id,logical_drone_id,material_drone_id,input_digest,input_json,state,lease_generation,control_epoch,context_revision,plan_revision,dispatch_authority,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(aid,mission_id,phase_id,logical_drone_id,material_drone_id,digest(input_value),_canon(input_value),"READY",int(lease_generation),int(control["control_epoch"]),int(control["context_revision"]),int(control["plan_revision"]),dispatch_authority,stamp));conn.commit();return aid


def record_receipt(conn,assignment_id,result,now_fn,*,material_drone_id,lease_generation,status="PASS",effect_receipt_digest=None,authority_effect="NONE"):
    if not isinstance(material_drone_id,str) or not material_drone_id:raise ValueError('material identity required')
    if type(lease_generation) is not int or lease_generation<1:raise ValueError('lease generation required')
    if status not in {'PASS','FAIL'} or authority_effect!='NONE':raise ValueError('assignment receipt status/authority')
    return _record_receipt(conn,assignment_id,result,now_fn,status=status,effect_receipt_digest=effect_receipt_digest,authority_effect=authority_effect,worker_binding=(material_drone_id,lease_generation))


def record_internal_receipt(conn,assignment_id,result,now_fn,*,status="PASS",effect_receipt_digest=None,authority_effect="NONE"):
    return _record_receipt(conn,assignment_id,result,now_fn,status=status,effect_receipt_digest=effect_receipt_digest,authority_effect=authority_effect)


class StaleAssignmentResult(ValueError):pass

def _store_stale_result(conn,row,result,result_digest,now_fn,*,material_drone_id,lease_generation,reason):
    if "mission_stale_assignment_results" not in {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}:raise ValueError(reason)
    control=operator_control.control_state(conn,row["mission_id"],None) or {};sid="stale-result-"+uuid.uuid4().hex;raw=_canon(result);stamp=now_fn();conn.execute("INSERT OR IGNORE INTO mission_stale_assignment_results VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",(sid,row["assignment_id"],row["mission_id"],row["phase_id"],result_digest,raw,material_drone_id,lease_generation,int(row["control_epoch"] or 0),int(control.get("control_epoch") or 0),reason,stamp));conn.execute("UPDATE mission_execution_assignments SET state='STALE_RESULT',finished_at=COALESCE(finished_at,?) WHERE assignment_id=?",(stamp,row["assignment_id"]));return sid


def _record_receipt(conn,assignment_id,result,now_fn,*,status,effect_receipt_digest,authority_effect,worker_binding=None):
    result_digest=digest(result);rid="receipt-"+uuid.uuid4().hex;stamp=now_fn();conn.execute('SAVEPOINT scheduler_receipt_ingress')
    try:
        conn.execute('UPDATE mission_execution_assignments SET state=state WHERE assignment_id=?',(assignment_id,));row=conn.execute("SELECT assignment_id,mission_id,phase_id,state,material_drone_id,lease_generation,control_epoch,dispatch_authority FROM mission_execution_assignments WHERE assignment_id=?",(assignment_id,)).fetchone()
        if not row:raise ValueError("assignment missing")
        if worker_binding is not None:
            material_drone_id,lease_generation=worker_binding
            if row['material_drone_id']!=material_drone_id:raise ValueError('material identity mismatch')
            if not operator_control.assignment_allowed(conn,row['mission_id'],row['dispatch_authority'],int(row['control_epoch'])):
                if "mission_operator_control" in {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}:
                    sid=_store_stale_result(conn,row,result,result_digest,now_fn,material_drone_id=material_drone_id,lease_generation=lease_generation,reason='STALE_CONTROL_EPOCH');conn.execute('RELEASE scheduler_receipt_ingress');conn.commit();raise StaleAssignmentResult('stale assignment control epoch; historical_result='+sid)
                raise ValueError('stale assignment control epoch')
            driver=conn.execute('SELECT generation FROM mission_execution_drivers WHERE mission_id=?',(row['mission_id'],)).fetchone()
            if row['lease_generation']!=lease_generation or not driver or driver['generation']!=lease_generation:
                tables={r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                if 'mission_operator_control' in tables and row['state']=='CANCEL_REQUESTED':
                    sid=_store_stale_result(conn,row,result,result_digest,now_fn,material_drone_id=material_drone_id,lease_generation=lease_generation,reason='STALE_DRIVER_GENERATION');conn.execute('RELEASE scheduler_receipt_ingress');conn.commit();raise StaleAssignmentResult('stale assignment generation; historical_result='+sid)
                raise ValueError('stale assignment generation')
        existing=conn.execute("SELECT result_digest,effect_receipt_digest,authority_effect,status FROM mission_execution_receipts WHERE assignment_id=? ORDER BY observed_at,receipt_id",(assignment_id,)).fetchall()
        if existing:
            identical=len(existing)==1 and tuple(existing[0])==(result_digest,effect_receipt_digest,authority_effect,status);raise ValueError('assignment receipt duplicate' if identical else 'assignment receipt conflict')
        if worker_binding is not None and row['state']!='CLAIMED':raise ValueError('assignment not claimed')
        conn.execute("INSERT INTO mission_execution_receipts VALUES(?,?,?,?,?,?,?,?,?)",(rid,assignment_id,row["mission_id"],row["phase_id"],result_digest,effect_receipt_digest,authority_effect,status,stamp));conn.execute("UPDATE mission_execution_assignments SET state=?,finished_at=? WHERE assignment_id=?",(status,stamp,assignment_id))
    except StaleAssignmentResult:raise
    except Exception:conn.execute('ROLLBACK TO scheduler_receipt_ingress');conn.execute('RELEASE scheduler_receipt_ingress');raise
    conn.execute('RELEASE scheduler_receipt_ingress');conn.commit();return {"receipt_id":rid,"duplicate":False,"result_digest":result_digest}


def pending_local_assignments(conn,*,mission_id=None,limit=16):
    if type(limit) is not int or not 1<=limit<=64:raise ValueError("assignment limit")
    rows=conn.execute("SELECT * FROM mission_execution_assignments WHERE state='READY' AND mission_id=? ORDER BY created_at,assignment_id LIMIT ?",(mission_id,max(limit*4,limit))).fetchall() if mission_id else conn.execute("SELECT * FROM mission_execution_assignments WHERE state='READY' ORDER BY created_at,assignment_id LIMIT ?",(max(limit*4,limit),)).fetchall();allowed=[]
    driver_cols={r[1] for r in conn.execute("PRAGMA table_info(mission_execution_drivers)")}
    generation_cache={}
    for row in rows:
        if 'generation' in driver_cols:
            mid=row['mission_id']
            if mid not in generation_cache:
                driver=conn.execute("SELECT generation FROM mission_execution_drivers WHERE mission_id=?",(mid,)).fetchone()
                generation_cache[mid]=int(driver['generation']) if driver and driver['generation'] is not None else None
            current_generation=generation_cache[mid]
            if current_generation is not None and int(row['lease_generation'])!=current_generation:continue
        if operator_control.assignment_allowed(conn,row['mission_id'],row['dispatch_authority'],int(row['control_epoch'])):allowed.append(dict(row))
        if len(allowed)>=limit:break
    return allowed


def _assignment_lease_deadline(stamp,seconds=120):
    dt=datetime.fromisoformat(str(stamp).replace('Z','+00:00'))
    if dt.tzinfo is None:dt=dt.replace(tzinfo=timezone.utc)
    return (dt+timedelta(seconds=int(seconds))).astimezone(timezone.utc).isoformat().replace('+00:00','Z')

def assignment_lease_valid(assignment,observed_at):
    expires=(assignment or {}).get('lease_expires_at') if isinstance(assignment,dict) else None
    if not expires:return False
    now_dt=datetime.fromisoformat(str(observed_at).replace('Z','+00:00'));exp_dt=datetime.fromisoformat(str(expires).replace('Z','+00:00'))
    if now_dt.tzinfo is None:now_dt=now_dt.replace(tzinfo=timezone.utc)
    if exp_dt.tzinfo is None:exp_dt=exp_dt.replace(tzinfo=timezone.utc)
    return now_dt<exp_dt

def claim_assignment(conn,assignment_id,now_fn,*,expected_material_drone_id=None,lease_seconds=120):
    conn.execute('SAVEPOINT assignment_claim_fence')
    try:
        conn.execute('UPDATE mission_execution_assignments SET state=state WHERE assignment_id=?',(assignment_id,));row=conn.execute("SELECT * FROM mission_execution_assignments WHERE assignment_id=?",(assignment_id,)).fetchone()
        if not row:raise ValueError("assignment missing")
        if row['state']!='READY':raise ValueError("assignment not ready")
        if expected_material_drone_id and row['material_drone_id']!=expected_material_drone_id:raise ValueError("material identity mismatch")
        if not operator_control.assignment_allowed(conn,row['mission_id'],row['dispatch_authority'],int(row['control_epoch'])):raise ValueError('operator control fence')
        driver_cols={r[1] for r in conn.execute('PRAGMA table_info(mission_execution_drivers)')}
        if 'generation' in driver_cols:
            driver=conn.execute('SELECT generation FROM mission_execution_drivers WHERE mission_id=?',(row['mission_id'],)).fetchone()
            if not driver or int(driver['generation'])!=int(row['lease_generation']):raise ValueError('stale assignment generation')
        stamp=now_fn();expires=_assignment_lease_deadline(stamp,lease_seconds);cur=conn.execute("UPDATE mission_execution_assignments SET state='CLAIMED',claimed_at=?,lease_expires_at=? WHERE assignment_id=? AND state='READY'",(stamp,expires,assignment_id))
        if cur.rowcount!=1:raise ValueError("assignment claim race")
    except Exception:conn.execute('ROLLBACK TO assignment_claim_fence');conn.execute('RELEASE assignment_claim_fence');raise
    conn.execute('RELEASE assignment_claim_fence');conn.commit();out=dict(row);out['state']='CLAIMED';out['claimed_at']=stamp;out['lease_expires_at']=expires;return out


GENERIC_EXECUTOR_STATES=frozenset({"PLANNING","CAPABILITY_RESOLUTION","WAITING_AUTHORITY","WAITING_CURRENTNESS","READY_TO_EXECUTE","EXECUTING","VALIDATING","PASS","BLOCKED","FAILED"})

def store_assignment_payload(conn,assignment_id,receipt_id,result,now_fn,*,max_bytes=131072):
    if type(result) is not dict:raise ValueError("assignment payload result")
    raw=_canon(result)
    if len(raw.encode("utf-8"))>int(max_bytes):raise ValueError("assignment payload too large")
    assignment=conn.execute("SELECT mission_id,phase_id FROM mission_execution_assignments WHERE assignment_id=?",(assignment_id,)).fetchone();receipt=conn.execute("SELECT receipt_id,result_digest FROM mission_execution_receipts WHERE assignment_id=? AND receipt_id=?",(assignment_id,receipt_id)).fetchone()
    if not assignment or not receipt:raise ValueError("assignment payload receipt missing")
    dg=digest(result)
    if dg!=receipt["result_digest"]:raise ValueError("assignment payload digest mismatch")
    existing=conn.execute("SELECT receipt_id,result_digest,result_json FROM mission_assignment_payloads WHERE assignment_id=?",(assignment_id,)).fetchone()
    if existing:
        if (existing["receipt_id"],existing["result_digest"],existing["result_json"])!=(receipt_id,dg,raw):raise ValueError("assignment payload conflict")
        return {"assignment_id":assignment_id,"receipt_id":receipt_id,"result_digest":dg,"idempotent":True}
    conn.execute("INSERT INTO mission_assignment_payloads VALUES(?,?,?,?,?,?,?)",(assignment_id,receipt_id,assignment["mission_id"],assignment["phase_id"],dg,raw,now_fn()));conn.commit();return {"assignment_id":assignment_id,"receipt_id":receipt_id,"result_digest":dg,"idempotent":False}

def assignment_payload(conn,assignment_id):
    row=conn.execute("SELECT * FROM mission_assignment_payloads WHERE assignment_id=?",(assignment_id,)).fetchone()
    if not row:return None
    out=dict(row)
    try:out["result"]=json.loads(out.pop("result_json"))
    except Exception:out["result"]={}
    return out

def put_generic_phase_plan(conn,*,mission_id,phase_id,planning_assignment_id,planning_receipt_id,planning_result_digest,planning_payload_state,state,capability,target,operation,required_inputs,expected_output,authority_class,currentness_requirements,evidence_requirements,rollback_class,dependencies,action_ir,action_ir_digest,now_fn,executor_id=None):
    if state not in GENERIC_EXECUTOR_STATES:raise ValueError("generic executor state")
    if planning_payload_state not in {"RETAINED","LEGACY_DIGEST_ONLY"}:raise ValueError("generic plan requirements")
    if type(required_inputs) is not dict or type(expected_output) is not dict:raise ValueError("generic plan io")
    if type(currentness_requirements) is not list or type(evidence_requirements) is not list or type(dependencies) is not list:raise ValueError("generic plan requirements")
    if type(action_ir) is not dict:raise ValueError("generic action ir")
    air=_canon(action_ir)
    if digest(action_ir)!=action_ir_digest:raise ValueError("generic action ir digest")
    stamp=now_fn();plan_id="generic-plan-"+hashlib.sha256((mission_id+"|"+phase_id).encode()).hexdigest()[:32];existing=conn.execute("SELECT * FROM mission_generic_phase_plans WHERE mission_id=? AND phase_id=?",(mission_id,phase_id)).fetchone();values=(plan_id,mission_id,phase_id,planning_assignment_id,planning_receipt_id,planning_result_digest,planning_payload_state,state,capability,target,operation,_canon(required_inputs),_canon(expected_output),authority_class,_canon(currentness_requirements),_canon(evidence_requirements),rollback_class,_canon(dependencies),air,action_ir_digest,executor_id,None,None,None,stamp,stamp)
    if existing:
        immutable=("planning_assignment_id","planning_receipt_id","planning_result_digest","capability","target","operation","authority_class","rollback_class","action_ir_digest");expected={"planning_assignment_id":planning_assignment_id,"planning_receipt_id":planning_receipt_id,"planning_result_digest":planning_result_digest,"capability":capability,"target":target,"operation":operation,"authority_class":authority_class,"rollback_class":rollback_class,"action_ir_digest":action_ir_digest}
        if any(existing[k]!=expected[k] for k in immutable):raise ValueError("generic plan immutable conflict")
        return dict(existing)
    conn.execute("INSERT INTO mission_generic_phase_plans VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",values);conn.commit();return dict(conn.execute("SELECT * FROM mission_generic_phase_plans WHERE plan_id=?",(plan_id,)).fetchone())

def update_generic_plan_state(conn,plan_id,state,now_fn,*,executor_id=None,evidence=None,effect_receipt_digest=None):
    if state not in GENERIC_EXECUTOR_STATES:raise ValueError("generic executor state")
    row=conn.execute("SELECT * FROM mission_generic_phase_plans WHERE plan_id=?",(plan_id,)).fetchone()
    if not row:raise ValueError("generic plan missing")
    evidence_json=None;evidence_digest=None
    if evidence is not None:
        if type(evidence) is not dict:raise ValueError("generic evidence")
        evidence_json=_canon(evidence);evidence_digest=digest(evidence)
    conn.execute("UPDATE mission_generic_phase_plans SET state=?,executor_id=COALESCE(?,executor_id),evidence_json=COALESCE(?,evidence_json),evidence_digest=COALESCE(?,evidence_digest),effect_receipt_digest=COALESCE(?,effect_receipt_digest),updated_at=? WHERE plan_id=?",(state,executor_id,evidence_json,evidence_digest,effect_receipt_digest,now_fn(),plan_id));conn.commit();return dict(conn.execute("SELECT * FROM mission_generic_phase_plans WHERE plan_id=?",(plan_id,)).fetchone())

def record_generic_action_receipt(conn,plan_id,now_fn,*,status,evidence,authority_effect="NONE"):
    if status not in {"PASS","FAIL"} or authority_effect!="NONE":raise ValueError("generic action receipt status/authority")
    plan=conn.execute("SELECT * FROM mission_generic_phase_plans WHERE plan_id=?",(plan_id,)).fetchone()
    if not plan:raise ValueError("generic plan missing")
    if type(evidence) is not dict:raise ValueError("generic action evidence")
    ed=digest(evidence);existing=conn.execute("SELECT * FROM mission_generic_action_receipts WHERE plan_id=?",(plan_id,)).fetchone()
    if existing:
        if (existing["action_ir_digest"],existing["evidence_digest"],existing["authority_effect"],existing["status"])!=(plan["action_ir_digest"],ed,authority_effect,status):raise ValueError("generic action receipt conflict")
        raise ValueError("generic action receipt duplicate")
    rid="generic-receipt-"+uuid.uuid4().hex;stamp=now_fn();conn.execute("INSERT INTO mission_generic_action_receipts VALUES(?,?,?,?,?,?,?,?,?)",(rid,plan_id,plan["mission_id"],plan["phase_id"],plan["action_ir_digest"],ed,authority_effect,status,stamp));conn.execute("UPDATE mission_generic_phase_plans SET state=?,evidence_json=?,evidence_digest=?,effect_receipt_digest=?,updated_at=? WHERE plan_id=?",("PASS" if status=="PASS" else "FAILED",_canon(evidence),ed,rid,stamp,plan_id));conn.commit();return {"receipt_id":rid,"plan_id":plan_id,"evidence_digest":ed,"status":status}
