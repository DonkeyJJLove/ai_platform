from __future__ import annotations

import hashlib
import json
import uuid

SCHEMA_VERSION = 2
SCHEMA_ID = "lion.mission-control.lifecycle-db/v2"
PRE_PROCESS_STAGE = "PRE_MISSION_PROCESS_SCHEMA"
CURRENT_STAGE = "MISSION_PROCESS_SCHEMA_V1"


def mission_lifecycle_classification(conn, mission_id):
    """Derive lifecycle semantics from recorded state without granting authority."""
    row=conn.execute('SELECT mission_id,adapter,state FROM missions WHERE mission_id=?',(mission_id,)).fetchone()
    if row is None:raise ValueError('mission not found')
    process=conn.execute('SELECT authority_state FROM mission_process_specs WHERE mission_id=?',(mission_id,)).fetchone()
    tables={r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    driver=conn.execute('SELECT state FROM mission_execution_drivers WHERE mission_id=?',(mission_id,)).fetchone() if 'mission_execution_drivers' in tables else None
    adapter=str(row['adapter'] or '')
    state=str(row['state'] or 'UNKNOWN').upper()
    authority=str(process['authority_state'] if process else '')
    driver_state=str(driver['state'] if driver else '')
    has_process=process is not None
    profile=_source_profile(row,has_process)
    legacy=adapter.startswith('LEGACY_OBSERVATION:')
    superseded=state=='SUPERSEDED' or authority.upper().startswith('SUPERSEDED')
    current_authority=authority in {'EXPLICIT_USER_ACTIVATION','EXPLICIT_EXACT_DIGEST_ACTIVATION'}
    active_driver=driver_state in {'ACTIVE','WAITING','BLOCKED'}
    terminal_state=state in {'COMPLETE','COMPLETED','STOPPED','FAILED','FAIL','CANCELLED'}
    if legacy:
        lifecycle_class='LEGACY_HISTORY';record_class='RECORDED_OBSERVATION';reason='LEGACY_OBSERVATION_SOURCE_STAGE'
    elif superseded:
        lifecycle_class='SUPERSEDED';record_class=profile['record_class'];reason='MISSION_OR_PROCESS_AUTHORITY_SUPERSEDED'
    elif current_authority and active_driver:
        lifecycle_class='CURRENT_EXECUTABLE';record_class=profile['record_class'];reason='CURRENT_AUTHORITY_AND_ACTIVE_DRIVER'
    elif terminal_state:
        lifecycle_class='CURRENT_TERMINAL';record_class=profile['record_class'];reason='CURRENT_TERMINAL_RECORDED_STATE'
    elif state in {'REGISTERED','AUTHORIZED','RUNNING','WAITING','BLOCKED','PAUSED','CONVERGING'}:
        lifecycle_class='CURRENT_NONEXECUTING';record_class=profile['record_class'];reason='CURRENT_RECORD_WITHOUT_ACTIVE_EXECUTION_PROOF'
    else:
        lifecycle_class='UNKNOWN';record_class=profile['record_class'];reason='LIFECYCLE_COMBINATION_UNKNOWN'
    historical=lifecycle_class in {'LEGACY_HISTORY','SUPERSEDED'} or record_class=='RECORDED_OBSERVATION'
    operational=lifecycle_class in {'CURRENT_EXECUTABLE','CURRENT_NONEXECUTING','CURRENT_TERMINAL'}
    return {
        'mission_id':mission_id,'lifecycle_class':lifecycle_class,'record_class':record_class,
        'operational':operational,'historical':historical,'legacy':legacy,
        'execution_controls_allowed':operational and not legacy and not superseded,
        'history_reason':reason,'authority_state':authority or None,'driver_state':driver_state or None,
        'recorded_state':row['state'],'adapter':row['adapter'],'authority_effect':'NONE',
    }


def mission_delete_preview(conn, mission_id, protected_id):
    row=conn.execute('SELECT mission_id,state,spec_digest FROM missions WHERE mission_id=?',(mission_id,)).fetchone()
    if row is None:return {'mission_id':mission_id,'allowed':False,'reason':'MISSION_NOT_FOUND'}
    lifecycle=mission_lifecycle_classification(conn,mission_id)
    reasons=[]
    if mission_id==protected_id:reasons.append('SHARED_RUNTIME_OWNER')
    if lifecycle['lifecycle_class']=='LEGACY_HISTORY':
        reasons.append('LEGACY_HISTORY_PRESERVATION_POLICY')
    elif row['state'] not in {'COMPLETE','COMPLETED','SUPERSEDED','CANCELLED','STOPPED','FAILED','FAIL','REGISTERED','AUTHORIZED','BLOCKED','RECORDED_PASS','RECORDED_CLEANED','RECORDED_FAIL'}:
        reasons.append('MISSION_STILL_ACTIVE')
    tables={r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if 'mission_execution_drivers' in tables:
        driver=conn.execute('SELECT state FROM mission_execution_drivers WHERE mission_id=?',(mission_id,)).fetchone()
        if driver and driver['state'] not in {'COMPLETE','COMPLETED','STOPPED','CANCELLED','FAILED','SUPERSEDED'}:reasons.append('DRIVER_MUST_BE_STOPPED')
    if 'mission_execution_assignments' in tables and conn.execute("SELECT 1 FROM mission_execution_assignments WHERE mission_id=? AND state='CLAIMED' LIMIT 1",(mission_id,)).fetchone():reasons.append('WORKER_ASSIGNMENT_IN_FLIGHT')
    if 'commands' in tables and conn.execute("SELECT 1 FROM commands WHERE mission_id=? AND status IN ('RUNNING','PENDING') LIMIT 1",(mission_id,)).fetchone():reasons.append('COMMAND_IN_FLIGHT')
    return {'mission_id':mission_id,'spec_digest':row['spec_digest'],'state':row['state'],'allowed':not reasons,'reason':'; '.join(reasons) or 'RECORDS_ONLY_NO_RUNTIME_STOP','lifecycle':lifecycle,'authority_effect':'NONE'}

def delete_mission_records(conn, mission_id, expected_digest, protected_id, now_fn):
    """Permanent local record deletion; never dispatches or stops external resources."""
    conn.execute('BEGIN IMMEDIATE')
    try:
        preview=mission_delete_preview(conn,mission_id,protected_id)
        if not preview['allowed']:raise ValueError(preview['reason'])
        if preview['spec_digest']!=expected_digest:raise ValueError('MISSION_CHANGED_REFRESH_REQUIRED')
        tables={r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        removed={}
        if 'mission_dual_receipts' in tables and 'mission_dual_evaluations' in tables:
            removed['mission_dual_receipts']=conn.execute('DELETE FROM mission_dual_receipts WHERE request_id IN (SELECT request_id FROM mission_dual_evaluations WHERE mission_id=?)',(mission_id,)).rowcount
        # Identifiers come only from the local schema and are quoted, never from request data.
        for table in sorted(tables-{'missions','mission_meta','saas_session_bindings','sqlite_sequence'}):
            ident='"'+table.replace('"','""')+'"'
            columns={r[1] for r in conn.execute('PRAGMA table_info('+ident+')')}
            if 'mission_id' in columns:removed[table]=conn.execute('DELETE FROM '+ident+' WHERE mission_id=?',(mission_id,)).rowcount
        # A global session is independent of the deleted mission; its attestation stays intact.
        if 'saas_session_bindings' in tables:removed['saas_session_bindings']=conn.execute("DELETE FROM saas_session_bindings WHERE mission_id=? AND binding_scope!='GLOBAL_SUPERVISOR_CHANNEL'",(mission_id,)).rowcount
        removed['missions']=conn.execute('DELETE FROM missions WHERE mission_id=?',(mission_id,)).rowcount
        # ID-only suppression prevents historical source import from resurrecting deleted records.
        conn.execute('INSERT OR REPLACE INTO mission_meta(key,value,updated_at) VALUES(?,?,?)',('deleted_mission:'+mission_id,'1',now_fn()))
        conn.execute("UPDATE mission_meta SET value=?,updated_at=? WHERE key='focus_mission_id' AND value=?",(protected_id,now_fn(),mission_id))
        conn.commit()
        return {'mission_id':mission_id,'deleted':True,'removed_rows':removed,'runtime_resources_changed':False,'authority_effect':'NONE'}
    except Exception:
        conn.rollback();raise

DDL = r"""
CREATE TABLE IF NOT EXISTS schema_migrations(
  version INTEGER PRIMARY KEY,
  schema_id TEXT NOT NULL UNIQUE,
  applied_at TEXT NOT NULL,
  source_head TEXT,
  source_tree TEXT,
  migration_digest TEXT NOT NULL,
  note TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS mission_lineage(
  mission_id TEXT PRIMARY KEY,
  root_mission_id TEXT NOT NULL,
  parent_mission_id TEXT,
  revision INTEGER NOT NULL,
  relation TEXT NOT NULL,
  source_epoch TEXT NOT NULL,
  source_stage TEXT NOT NULL,
  source_schema TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS mission_data_gaps(
  mission_id TEXT NOT NULL,
  field_name TEXT NOT NULL,
  reason_class TEXT NOT NULL,
  source_stage TEXT NOT NULL,
  source_schema TEXT NOT NULL,
  detail TEXT NOT NULL,
  PRIMARY KEY(mission_id,field_name)
);
CREATE TABLE IF NOT EXISTS mission_components(
  mission_id TEXT NOT NULL,
  component_id TEXT NOT NULL,
  component_class TEXT NOT NULL,
  desired_state TEXT NOT NULL,
  observed_state TEXT,
  adapter TEXT,
  authority_class TEXT NOT NULL,
  spec_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  PRIMARY KEY(mission_id,component_id)
);
CREATE TABLE IF NOT EXISTS mission_design_revisions(
  revision_id TEXT PRIMARY KEY,
  mission_id TEXT NOT NULL,
  revision_no INTEGER NOT NULL,
  action TEXT NOT NULL,
  state TEXT NOT NULL,
  request_json TEXT NOT NULL,
  request_digest TEXT NOT NULL,
  created_at TEXT NOT NULL,
  activated_at TEXT,
  UNIQUE(mission_id,revision_no)
);
CREATE TABLE IF NOT EXISTS mission_audits(
  audit_id TEXT PRIMARY KEY,
  mission_id TEXT NOT NULL,
  status TEXT NOT NULL,
  snapshot_json TEXT NOT NULL,
  snapshot_digest TEXT NOT NULL,
  findings_json TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS mission_rollback_points(
  rollback_id TEXT PRIMARY KEY,
  mission_id TEXT NOT NULL,
  rollback_class TEXT NOT NULL,
  state_json TEXT NOT NULL,
  state_digest TEXT NOT NULL,
  restorable INTEGER NOT NULL,
  blocker TEXT,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS mission_action_receipts(
  receipt_id TEXT PRIMARY KEY,
  mission_id TEXT NOT NULL,
  action TEXT NOT NULL,
  effect_class TEXT NOT NULL,
  status TEXT NOT NULL,
  request_json TEXT NOT NULL,
  result_json TEXT NOT NULL,
  receipt_digest TEXT NOT NULL,
  created_at TEXT NOT NULL
);
"""

PROCESS_FIELDS = (
    "objective",
    "description",
    "current_phase",
    "progress",
    "authority_state",
    "protocols",
    "phase_plan",
    "protocol_messages",
)


def _canon(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def _digest(value):
    return hashlib.sha256(_canon(value).encode("utf-8")).hexdigest()


def _source_profile(row, has_process):
    adapter = str(row["adapter"] or "UNKNOWN")
    if adapter.startswith("LEGACY_OBSERVATION:"):
        legacy_adapter = adapter.split(":", 1)[1] or "UNKNOWN"
        return {
            "record_class": "HISTORICAL_PRE_SCHEMA",
            "source_epoch": "UNKNOWN_HISTORICAL_EPOCH",
            "source_stage": f"{PRE_PROCESS_STAGE}:{legacy_adapter}",
            "source_schema": "legacy.run.payload/v1",
            "compatibility_note": "Mission was recorded before the canonical mission-process schema existed. Missing process fields are historical absence, not refresh failure.",
        }
    if has_process:
        return {
            "record_class": "CURRENT_PROCESS_RECORD",
            "source_epoch": "EPOCH3_CLOSURE",
            "source_stage": CURRENT_STAGE,
            "source_schema": "lion.mission-process/v1",
            "compatibility_note": "Mission has canonical process metadata.",
        }
    return {
        "record_class": "CURRENT_CORE_ONLY",
        "source_epoch": "EPOCH3_CLOSURE",
        "source_stage": "MISSION_CORE_SCHEMA_WITHOUT_PROCESS_RECORD",
        "source_schema": "lion.mission-core/v1",
        "compatibility_note": "Core mission identity exists, but no process record was materialized for this mission.",
    }


def migrate(conn, now_fn, *, current_mission_id, source_head, source_tree):
    conn.executescript(DDL)
    stamp = now_fn()
    md = hashlib.sha256(DDL.encode("utf-8")).hexdigest()
    conn.execute(
        "INSERT OR IGNORE INTO schema_migrations(version,schema_id,applied_at,source_head,source_tree,migration_digest,note) VALUES(?,?,?,?,?,?,?)",
        (SCHEMA_VERSION, SCHEMA_ID, stamp, source_head, source_tree, md, "Epoch 3 closure: mission lineage, historical schema compatibility, audit/design/rollback metadata."),
    )
    missions = conn.execute("SELECT mission_id,adapter,created_at FROM missions ORDER BY created_at").fetchall()
    for row in missions:
        mid = row["mission_id"]
        has_process = conn.execute("SELECT 1 FROM mission_process_specs WHERE mission_id=?", (mid,)).fetchone() is not None
        profile = _source_profile(row, has_process)
        conn.execute(
            "INSERT OR IGNORE INTO mission_lineage(mission_id,root_mission_id,parent_mission_id,revision,relation,source_epoch,source_stage,source_schema,created_at) VALUES(?,?,?,?,?,?,?,?,?)",
            (mid, mid, None, 1, "ORIGINAL_OR_IMPORTED", profile["source_epoch"], profile["source_stage"], profile["source_schema"], row["created_at"] or stamp),
        )
        if not has_process:
            for field in PROCESS_FIELDS:
                conn.execute(
                    "INSERT OR IGNORE INTO mission_data_gaps(mission_id,field_name,reason_class,source_stage,source_schema,detail) VALUES(?,?,?,?,?,?)",
                    (mid, field, "NOT_RECORDED_AT_SOURCE_STAGE", profile["source_stage"], profile["source_schema"], "The field did not exist in the mission record available at this historical stage; UNKNOWN is preserved rather than synthesized."),
                )
        logical = conn.execute("SELECT logical_id,role,material_target,materialized,ready FROM logical_drones WHERE mission_id=? ORDER BY logical_id", (mid,)).fetchall()
        for item in logical:
            desired = "RUNNING" if int(item["material_target"] or 0) else "DECLARED"
            observed = "READY" if int(item["ready"] or 0) == int(item["material_target"] or 0) and int(item["material_target"] or 0) > 0 else "PARTIAL_OR_UNKNOWN"
            spec = {"role": item["role"], "material_target": item["material_target"], "materialized": item["materialized"], "ready": item["ready"]}
            conn.execute(
                "INSERT OR IGNORE INTO mission_components(mission_id,component_id,component_class,desired_state,observed_state,adapter,authority_class,spec_json,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
                (mid, item["logical_id"], "LOGICAL_DRONE", desired, observed, row["adapter"], "MISSION_SCOPED_OR_NONE", _canon(spec), stamp, stamp),
            )
    conn.commit()


def schema_context(conn, mission_id):
    row = conn.execute("SELECT mission_id,adapter FROM missions WHERE mission_id=?", (mission_id,)).fetchone()
    if row is None:
        raise ValueError("mission not found")
    has_process = conn.execute("SELECT 1 FROM mission_process_specs WHERE mission_id=?", (mission_id,)).fetchone() is not None
    profile = _source_profile(row, has_process)
    migration = conn.execute("SELECT * FROM schema_migrations ORDER BY version DESC LIMIT 1").fetchone()
    gaps = [dict(x) for x in conn.execute("SELECT field_name,reason_class,source_stage,source_schema,detail FROM mission_data_gaps WHERE mission_id=? ORDER BY field_name", (mission_id,))]
    return {
        "current_schema": (migration["schema_id"] if migration else SCHEMA_ID),
        "current_schema_version": (migration["version"] if migration else SCHEMA_VERSION),
        **profile,
        "missing_fields": gaps,
        "migration": dict(migration) if migration else None,
    }


def capabilities(conn, mission_id, *, current_mission_id, rebound_adapter="LPCL_REBOUND_EPOCH3_64"):
    row = conn.execute("SELECT adapter,state FROM missions WHERE mission_id=?", (mission_id,)).fetchone()
    if row is None:
        raise ValueError("mission not found")
    classification=mission_lifecycle_classification(conn,mission_id)
    adapter = str(row["adapter"] or "")
    historical = classification['lifecycle_class']=='LEGACY_HISTORY'
    superseded = classification['lifecycle_class']=='SUPERSEDED'
    if historical or superseded:
        denied='DENIED_LEGACY_HISTORY_READ_ONLY' if historical else 'DENIED_SUPERSEDED_READ_ONLY'
        reason='Historical records are read-only and do not carry current execution authority.' if historical else 'Superseded missions are read-only execution history.'
        return {
            "REFRESH": {"state": "SUPPORTED", "effect": "HISTORICAL_SOURCE_REINDEX" if historical else "READ_ONLY_CURRENTNESS"},
            "AUDIT": {"state": "SUPPORTED", "effect": "CONTROL_DB_METADATA_ONLY"},
            "VALIDATE": {"state": "SUPPORTED", "effect": "NONE"},
            "RESTART": {"state": denied, "effect": "NONE", "reason": reason},
            "PAUSE": {"state": denied, "effect": "NONE", "reason": reason},
            "RESUME": {"state": denied, "effect": "NONE", "reason": reason},
            "STOP": {"state": denied, "effect": "NONE", "reason": reason},
            "START_COMPONENT": {"state": denied, "effect": "NONE", "reason": reason},
            "ADD_COMPONENT": {"state": denied, "effect": "NONE", "reason": reason},
            "REDESIGN": {"state": denied, "effect": "NONE", "reason": reason},
            "ACTIVATE_REVISION": {"state": denied, "effect": "NONE", "reason": reason},
            "ROLLBACK": {"state": denied, "effect": "NONE", "reason": reason},
        }
    current = mission_id == current_mission_id and adapter == "MISSION64_K3S"
    epoch3 = mission_id == "EPOCH3-CLOSURE-DOCS-FEDERATION-GITHUB-R1"
    rebound = adapter == rebound_adapter
    driver_capable = rebound
    return {
        "REFRESH": {"state": "SUPPORTED", "effect": "READ_ONLY_CURRENTNESS"},
        "AUDIT": {"state": "SUPPORTED", "effect": "CONTROL_DB_METADATA_ONLY"},
        "RESTART": {"state": "SUPPORTED_BOUNDED_EFFECT" if (current or epoch3 or rebound) else "ADAPTER_REQUIRED", "effect": "MATERIAL" if (current or epoch3 or rebound) else "NONE"},
        "PAUSE": {"state": "SUPPORTED_DRIVER_CONTROL" if driver_capable else "ADAPTER_REQUIRED", "effect": "CONTROL_STATE" if driver_capable else "NONE"},
        "RESUME": {"state": "SUPPORTED_DRIVER_CONTROL" if driver_capable else "ADAPTER_REQUIRED", "effect": "CONTROL_STATE" if driver_capable else "NONE"},
        "VALIDATE": {"state": "SUPPORTED", "effect": "NONE"},
        "STOP": {"state": "SUPPORTED_DRIVER_CONTROL" if driver_capable else "ADAPTER_REQUIRED", "effect": "CONTROL_STATE" if driver_capable else "NONE"},
        "START_COMPONENT": {"state": "SUPPORTED_BOUNDED_EFFECT" if rebound else "ADAPTER_REQUIRED", "effect": "MATERIAL" if rebound else "NONE", "reason": None if rebound else "Exact per-component material adapter is available only for an exact activated rebound mission."},
        "ADD_COMPONENT": {"state": "DRAFT_REVISION_SUPPORTED", "effect": "NONE"},
        "REDESIGN": {"state": "DRAFT_REVISION_SUPPORTED", "effect": "NONE"},
        "ACTIVATE_REVISION": {"state": "EXPLICIT_EXACT_DIGEST_ACTIVATION_REQUIRED", "effect": "CONTROL_STATE"},
        "ROLLBACK": {"state": "CONTROL_PLANE_PLAN_SUPPORTED", "effect": "NONE", "reason": "Material rollback requires an exact rollback point plus bounded runtime adapter; metadata rollback is represented as a new revision, never database time-travel."},
    }

def sync_components(conn, mission_id, now_fn):
    stamp = now_fn()
    row = conn.execute("SELECT adapter FROM missions WHERE mission_id=?", (mission_id,)).fetchone()
    if row is None:
        raise ValueError("mission not found")
    logical = conn.execute("SELECT logical_id,role,material_target,materialized,ready FROM logical_drones WHERE mission_id=? ORDER BY logical_id", (mission_id,)).fetchall()
    for item in logical:
        observed = "READY" if int(item["ready"] or 0) == int(item["material_target"] or 0) and int(item["material_target"] or 0) > 0 else "PARTIAL_OR_UNKNOWN"
        spec = {"role": item["role"], "material_target": item["material_target"], "materialized": item["materialized"], "ready": item["ready"]}
        conn.execute(
            "INSERT INTO mission_components(mission_id,component_id,component_class,desired_state,observed_state,adapter,authority_class,spec_json,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(mission_id,component_id) DO UPDATE SET observed_state=excluded.observed_state,adapter=excluded.adapter,spec_json=excluded.spec_json,updated_at=excluded.updated_at",
            (mission_id, item["logical_id"], "LOGICAL_DRONE", "RUNNING", observed, row["adapter"], "MISSION_SCOPED_OR_NONE", _canon(spec), stamp, stamp),
        )


def create_design_revision(conn, mission_id, action, request, now_fn, *, state="AWAITING_EXACT_LPCL_ACTIVATION"):
    if conn.execute("SELECT 1 FROM missions WHERE mission_id=?", (mission_id,)).fetchone() is None:
        raise ValueError("mission not found")
    rev = int(conn.execute("SELECT COALESCE(MAX(revision_no),0)+1 FROM mission_design_revisions WHERE mission_id=?", (mission_id,)).fetchone()[0])
    stamp = now_fn(); rid = "rev-" + uuid.uuid4().hex
    payload = {"mission_id": mission_id, "action": action, "request": request, "revision_no": rev, "created_at": stamp}
    dg = _digest(payload)
    conn.execute("INSERT INTO mission_design_revisions VALUES(?,?,?,?,?,?,?,?,?)", (rid, mission_id, rev, action, state, _canon(request), dg, stamp, None))
    conn.commit()
    return {"revision_id": rid, "revision_no": rev, "state": state, "request_digest": dg, "authority_effect": "NONE", "runtime_effect": "NONE"}


def create_audit(conn, mission_id, now_fn):
    mission = conn.execute("SELECT mission_id,title,adapter,state,runtime_state,logical_count,material_target,materialized,ready,source_head,source_tree,updated_at,last_error FROM missions WHERE mission_id=?", (mission_id,)).fetchone()
    if mission is None:
        raise ValueError("mission not found")
    process = conn.execute("SELECT objective,current_phase,progress,authority_state,updated_at FROM mission_process_specs WHERE mission_id=?", (mission_id,)).fetchone()
    logical = [dict(x) for x in conn.execute("SELECT logical_id,role,material_target,materialized,ready FROM logical_drones WHERE mission_id=? ORDER BY logical_id", (mission_id,))]
    workers = int(conn.execute("SELECT COUNT(*) FROM material_workers WHERE mission_id=?", (mission_id,)).fetchone()[0])
    gaps = [dict(x) for x in conn.execute("SELECT field_name,reason_class,source_stage FROM mission_data_gaps WHERE mission_id=? ORDER BY field_name", (mission_id,))]
    stamp = now_fn()
    snapshot = {"mission": dict(mission), "process": dict(process) if process else None, "logical": logical, "worker_count": workers, "data_gaps": gaps, "captured_at": stamp}
    findings = []
    if gaps:
        findings.append({"class": "HISTORICAL_SCHEMA_GAPS", "count": len(gaps), "severity": "INFO"})
    if int(mission["material_target"] or 0) and int(mission["ready"] or 0) < int(mission["material_target"] or 0):
        findings.append({"class": "MATERIAL_NOT_FULLY_READY", "ready": mission["ready"], "target": mission["material_target"], "severity": "WARN"})
    if mission["last_error"]:
        findings.append({"class": "LAST_ERROR_PRESENT", "severity": "WARN", "detail": str(mission["last_error"])[:500]})
    status = "PASS_WITH_INFORMATIONAL_GAPS" if gaps and not any(x["severity"] == "WARN" for x in findings) else ("ATTENTION" if any(x["severity"] == "WARN" for x in findings) else "PASS")
    aid = "audit-" + uuid.uuid4().hex; sd = _digest(snapshot)
    conn.execute("INSERT INTO mission_audits VALUES(?,?,?,?,?,?,?)", (aid, mission_id, status, _canon(snapshot), sd, _canon(findings), stamp))
    rollback_state = {"mission": dict(mission), "process": dict(process) if process else None, "components": [dict(x) for x in conn.execute("SELECT * FROM mission_components WHERE mission_id=? ORDER BY component_id", (mission_id,))]}
    rbid = "rollback-" + uuid.uuid4().hex; rd = _digest(rollback_state)
    conn.execute("INSERT INTO mission_rollback_points VALUES(?,?,?,?,?,?,?,?)", (rbid, mission_id, "CONTROL_METADATA_SNAPSHOT", _canon(rollback_state), rd, 0, "Material/runtime rollback requires exact adapter and independent rollback identity; this point is evidence and redesign input only.", stamp))
    conn.commit()
    return {"audit_id": aid, "status": status, "snapshot_digest": sd, "findings": findings, "rollback_point": {"rollback_id": rbid, "restorable": False, "blocker": "MATERIAL_ROLLBACK_ADAPTER_REQUIRED"}, "authority_effect": "NONE"}


def create_action_receipt(conn, mission_id, action, effect_class, status, request, result, now_fn):
    stamp = now_fn(); rid = "action-" + uuid.uuid4().hex
    payload = {"receipt_id": rid, "mission_id": mission_id, "action": action, "effect_class": effect_class, "status": status, "request": request, "result": result, "created_at": stamp}
    dg = _digest(payload)
    conn.execute("INSERT INTO mission_action_receipts VALUES(?,?,?,?,?,?,?,?,?)", (rid, mission_id, action, effect_class, status, _canon(request), _canon(result), dg, stamp))
    conn.commit()
    return {"receipt_id": rid, "receipt_digest": dg}


def _normalization_receipt(conn, mission_id, before, after, successor_mission_id, source_head, source_tree, reason, now_fn):
    stamp=now_fn();rid='action-'+uuid.uuid4().hex
    result={'before':before,'after':after,'successor_mission_id':successor_mission_id,'source_head':source_head,'source_tree':source_tree,'normalization_reason':reason,'timestamp':stamp,'authority_effect':'CONTROL_STATE'}
    request={'operation':'EPOCH3_TERMINAL_LIFECYCLE_NORMALIZATION','successor_mission_id':successor_mission_id,'source_head':source_head,'source_tree':source_tree}
    payload={'receipt_id':rid,'mission_id':mission_id,'action':'EPOCH3_LIFECYCLE_NORMALIZE','effect_class':'CONTROL_STATE','status':'PASS','request':request,'result':result,'created_at':stamp}
    dg=_digest(payload)
    conn.execute('INSERT INTO mission_action_receipts VALUES(?,?,?,?,?,?,?,?,?)',(rid,mission_id,'EPOCH3_LIFECYCLE_NORMALIZE','CONTROL_STATE','PASS',_canon(request),_canon(result),dg,stamp))
    return {'receipt_id':rid,'receipt_digest':dg,'mission_id':mission_id,'result':result}


def normalize_epoch3_terminal_lifecycle(conn, *, target_1_mission_id, target_1_expected_spec_digest, target_2_mission_id, target_2_expected_spec_digest, successor_mission_id, expected_current_head, expected_current_tree, now_fn):
    """Atomically supersede two obsolete Epoch-3 execution lineages; never mutates legacy observations."""
    conn.execute('BEGIN IMMEDIATE')
    try:
        integrity=conn.execute('PRAGMA integrity_check').fetchone()[0]
        if integrity!='ok':raise ValueError('DATABASE_INTEGRITY_NOT_OK')
        successor=conn.execute('SELECT state,runtime_state FROM missions WHERE mission_id=?',(successor_mission_id,)).fetchone()
        if successor is None or successor['state']!='COMPLETE' or successor['runtime_state']!='DRIVER_COMPLETE':raise ValueError('SUCCESSOR_NOT_COMPLETE')
        sdriver=conn.execute('SELECT state FROM mission_execution_drivers WHERE mission_id=?',(successor_mission_id,)).fetchone()
        if sdriver is None or sdriver['state']!='COMPLETE':raise ValueError('SUCCESSOR_DRIVER_NOT_COMPLETE')
        currentness=False
        for row in conn.execute("SELECT payload_json FROM protocol_messages WHERE mission_id=? AND protocol='CURRENTNESS' ORDER BY id DESC LIMIT 80",(successor_mission_id,)):
            try:payload=json.loads(row['payload_json'])
            except Exception:continue
            if payload.get('event')=='SUCCESSOR_SOURCE_CURRENTNESS_REBOUND' and payload.get('current_source_head')==expected_current_head and payload.get('current_source_tree')==expected_current_tree and payload.get('ancestry_verified') is True:
                currentness=True;break
        if not currentness:raise ValueError('SUCCESSOR_SOURCE_CURRENTNESS_NOT_EXACT')
        targets=((target_1_mission_id,target_1_expected_spec_digest),(target_2_mission_id,target_2_expected_spec_digest))
        rows={}
        for mid,digest in targets:
            m=conn.execute('SELECT mission_id,state,runtime_state,spec_digest,last_error FROM missions WHERE mission_id=?',(mid,)).fetchone()
            if m is None:raise ValueError('TARGET_NOT_FOUND:'+mid)
            if m['spec_digest']!=digest:raise ValueError('SPEC_DIGEST_DRIFT:'+mid)
            rows[mid]=m
            if conn.execute("SELECT 1 FROM mission_execution_assignments WHERE mission_id=? AND state='CLAIMED' LIMIT 1",(mid,)).fetchone():raise ValueError('CLAIMED_ASSIGNMENT:'+mid)
            if conn.execute("SELECT 1 FROM commands WHERE mission_id=? AND status IN ('RUNNING','PENDING') LIMIT 1",(mid,)).fetchone():raise ValueError('COMMAND_IN_FLIGHT:'+mid)
            if conn.execute("SELECT 1 FROM mission_recon_material_leases WHERE mission_id=? AND state='ACTIVE' LIMIT 1",(mid,)).fetchone():raise ValueError('ACTIVE_RECON_LEASE:'+mid)
            if conn.execute("SELECT 1 FROM mission_phase_attempts WHERE mission_id=? AND state='RUNNING' LIMIT 1",(mid,)).fetchone():raise ValueError('RUNNING_PHASE_ATTEMPT:'+mid)
        d1=conn.execute('SELECT * FROM mission_execution_drivers WHERE mission_id=?',(target_1_mission_id,)).fetchone()
        if d1 is None or d1['state'] not in {'STOPPED','SUPERSEDED'}:raise ValueError('TARGET1_DRIVER_NOT_TERMINAL')
        d2=conn.execute('SELECT * FROM mission_execution_drivers WHERE mission_id=?',(target_2_mission_id,)).fetchone()
        if d2 is not None:raise ValueError('TARGET2_DRIVER_MUST_BE_ABSENT')
        p1=conn.execute('SELECT authority_state,current_phase,progress FROM mission_process_specs WHERE mission_id=?',(target_1_mission_id,)).fetchone()
        p2=conn.execute('SELECT authority_state,current_phase,progress FROM mission_process_specs WHERE mission_id=?',(target_2_mission_id,)).fetchone()
        if p1 is None or p2 is None:raise ValueError('TARGET_PROCESS_SPEC_MISSING')
        already=(rows[target_1_mission_id]['state']=='SUPERSEDED' and str(p1['authority_state']).startswith('SUPERSEDED') and d1['state']=='SUPERSEDED' and rows[target_2_mission_id]['state']=='SUPERSEDED' and str(p2['authority_state']).startswith('SUPERSEDED'))
        if already:
            receipts=[dict(r) for r in conn.execute("SELECT receipt_id,mission_id,receipt_digest,created_at FROM mission_action_receipts WHERE mission_id IN (?,?) AND action='EPOCH3_LIFECYCLE_NORMALIZE' ORDER BY created_at",(target_1_mission_id,target_2_mission_id))]
            conn.rollback();return {'already_normalized':True,'receipts':receipts,'authority_effect':'NONE'}
        if rows[target_1_mission_id]['state']!='WAITING' or d1['state']!='STOPPED':raise ValueError('TARGET1_PRECONDITION_DRIFT')
        if str(p2['authority_state'])!='SUPERSEDED_BY_EXACT_LPCL' or rows[target_2_mission_id]['state']!='RUNNING':raise ValueError('TARGET2_PRECONDITION_DRIFT')
        stamp=now_fn()
        before1={'state':rows[target_1_mission_id]['state'],'runtime_state':rows[target_1_mission_id]['runtime_state'],'authority_state':p1['authority_state'],'driver_state':d1['state'],'progress':p1['progress'],'current_phase':p1['current_phase']}
        conn.execute('UPDATE missions SET state=?,runtime_state=?,updated_at=? WHERE mission_id=?',('SUPERSEDED','SUPERSEDED_BY:'+successor_mission_id,stamp,target_1_mission_id))
        conn.execute('UPDATE mission_process_specs SET authority_state=?,current_phase=NULL,updated_at=? WHERE mission_id=?',('SUPERSEDED_BY_CURRENT_CONTROL_PLANE',stamp,target_1_mission_id))
        conn.execute("UPDATE mission_execution_drivers SET state='SUPERSEDED',lease_owner=NULL,lease_expires_at=NULL,current_phase=NULL,current_attempt_id=NULL,waiting_reason=?,blocking_gate=NULL,next_action='NONE_SUPERSEDED',updated_at=? WHERE mission_id=?",('SUPERSEDED_BY_CURRENT_CONTROL_PLANE_FIXED_POINT',stamp,target_1_mission_id))
        after1={'state':'SUPERSEDED','runtime_state':'SUPERSEDED_BY:'+successor_mission_id,'authority_state':'SUPERSEDED_BY_CURRENT_CONTROL_PLANE','driver_state':'SUPERSEDED','progress':p1['progress'],'current_phase':None}
        r1=_normalization_receipt(conn,target_1_mission_id,before1,after1,successor_mission_id,expected_current_head,expected_current_tree,'NEWER_CANONICAL_CONTROL_PLANE_FIXED_POINT',now_fn)
        before2={'state':rows[target_2_mission_id]['state'],'runtime_state':rows[target_2_mission_id]['runtime_state'],'authority_state':p2['authority_state'],'driver_state':None,'progress':p2['progress'],'current_phase':p2['current_phase'],'last_error':rows[target_2_mission_id]['last_error']}
        conn.execute('UPDATE missions SET state=?,runtime_state=?,updated_at=? WHERE mission_id=?',('SUPERSEDED','HISTORICAL_SUPERSEDED',stamp,target_2_mission_id))
        conn.execute('UPDATE mission_process_specs SET current_phase=NULL,updated_at=? WHERE mission_id=?',(stamp,target_2_mission_id))
        after2={'state':'SUPERSEDED','runtime_state':'HISTORICAL_SUPERSEDED','authority_state':p2['authority_state'],'driver_state':None,'progress':p2['progress'],'current_phase':None,'last_error':rows[target_2_mission_id]['last_error']}
        r2=_normalization_receipt(conn,target_2_mission_id,before2,after2,successor_mission_id,expected_current_head,expected_current_tree,'PROCESS_AUTHORITY_ALREADY_SUPERSEDED_AND_DRIVER_ABSENT',now_fn)
        conn.commit()
        return {'already_normalized':False,'target_1':after1,'target_2':after2,'receipts':[r1,r2],'authority_effect':'CONTROL_STATE'}
    except Exception:
        conn.rollback();raise


def rollback_plan(conn, mission_id, rollback_id, now_fn):
    row = conn.execute("SELECT * FROM mission_rollback_points WHERE rollback_id=? AND mission_id=?", (rollback_id, mission_id)).fetchone()
    if row is None:
        raise ValueError("rollback point not found")
    request = {"rollback_id": rollback_id, "rollback_class": row["rollback_class"], "state_digest": row["state_digest"], "restorable": bool(row["restorable"]), "blocker": row["blocker"]}
    return create_design_revision(conn, mission_id, "ROLLBACK", request, now_fn, state="ROLLBACK_PLAN_REQUIRES_EXACT_RUNTIME_ADAPTER")


def decorate_snapshot(conn, snapshot, *, current_mission_id, rebound_adapter="LPCL_REBOUND_EPOCH3_64"):
    mid = snapshot["mission_id"]
    snapshot["schema_context"] = schema_context(conn, mid)
    snapshot["lifecycle"] = mission_lifecycle_classification(conn, mid)
    snapshot["lineage"] = [dict(x) for x in conn.execute("SELECT * FROM mission_lineage WHERE mission_id=? OR parent_mission_id=? ORDER BY revision", (mid, mid))]
    snapshot["components"] = [dict(x) for x in conn.execute("SELECT mission_id,component_id,component_class,desired_state,observed_state,adapter,authority_class,spec_json,updated_at FROM mission_components WHERE mission_id=? ORDER BY component_id", (mid,))]
    for item in snapshot["components"]:
        try: item["spec"] = json.loads(item.pop("spec_json"))
        except Exception: item["spec"] = {}
    snapshot["capabilities"] = capabilities(conn, mid, current_mission_id=current_mission_id, rebound_adapter=rebound_adapter)
    snapshot["design_revisions"] = [dict(x) for x in conn.execute("SELECT revision_id,revision_no,action,state,request_digest,created_at,activated_at FROM mission_design_revisions WHERE mission_id=? ORDER BY revision_no DESC LIMIT 20", (mid,))]
    snapshot["audits"] = [dict(x) for x in conn.execute("SELECT audit_id,status,snapshot_digest,findings_json,created_at FROM mission_audits WHERE mission_id=? ORDER BY created_at DESC LIMIT 20", (mid,))]
    for item in snapshot["audits"]:
        try:item["findings"] = json.loads(item.pop("findings_json"))
        except Exception:item["findings"] = []
    snapshot["rollback_points"] = [dict(x) for x in conn.execute("SELECT rollback_id,rollback_class,state_digest,restorable,blocker,created_at FROM mission_rollback_points WHERE mission_id=? ORDER BY created_at DESC LIMIT 20", (mid,))]
    snapshot["action_receipts"] = [dict(x) for x in conn.execute("SELECT receipt_id,action,effect_class,status,receipt_digest,created_at FROM mission_action_receipts WHERE mission_id=? ORDER BY created_at DESC LIMIT 30", (mid,))]
    return snapshot
