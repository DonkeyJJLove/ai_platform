from __future__ import annotations

import hashlib
import json
import uuid

SCHEMA_VERSION = 2
SCHEMA_ID = "lion.mission-control.lifecycle-db/v2"
PRE_PROCESS_STAGE = "PRE_MISSION_PROCESS_SCHEMA"
CURRENT_STAGE = "MISSION_PROCESS_SCHEMA_V1"

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
    migration = conn.execute("SELECT * FROM schema_migrations WHERE version=?", (SCHEMA_VERSION,)).fetchone()
    gaps = [dict(x) for x in conn.execute("SELECT field_name,reason_class,source_stage,source_schema,detail FROM mission_data_gaps WHERE mission_id=? ORDER BY field_name", (mission_id,))]
    return {
        "current_schema": SCHEMA_ID,
        "current_schema_version": SCHEMA_VERSION,
        **profile,
        "missing_fields": gaps,
        "migration": dict(migration) if migration else None,
    }


def capabilities(conn, mission_id, *, current_mission_id, rebound_adapter="LPCL_REBOUND_EPOCH3_64"):
    row = conn.execute("SELECT adapter,state FROM missions WHERE mission_id=?", (mission_id,)).fetchone()
    if row is None:
        raise ValueError("mission not found")
    adapter = str(row["adapter"] or "")
    historical = adapter.startswith("LEGACY_OBSERVATION:")
    current = mission_id == current_mission_id and adapter == "MISSION64_K3S"
    epoch3 = mission_id == "EPOCH3-CLOSURE-DOCS-FEDERATION-GITHUB-R1"
    rebound = adapter == rebound_adapter
    return {
        "REFRESH": {"state": "SUPPORTED", "effect": "READ_ONLY_CURRENTNESS" if not historical else "HISTORICAL_SOURCE_REINDEX"},
        "AUDIT": {"state": "SUPPORTED", "effect": "CONTROL_DB_METADATA_ONLY"},
        "RESTART": {"state": "SUPPORTED_BOUNDED_EFFECT" if (current or epoch3) else ("REVISION_DRAFT_ONLY" if historical or rebound else "ADAPTER_REQUIRED"), "effect": "MATERIAL" if (current or epoch3) else "NONE"},
        "START_COMPONENT": {"state": "ADAPTER_REQUIRED", "effect": "NONE", "reason": "No exact per-component material effect adapter is installed in Epoch 3. The control contract is present and fails closed."},
        "ADD_COMPONENT": {"state": "DRAFT_REVISION_SUPPORTED", "effect": "NONE"},
        "REDESIGN": {"state": "DRAFT_REVISION_SUPPORTED", "effect": "NONE"},
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


def rollback_plan(conn, mission_id, rollback_id, now_fn):
    row = conn.execute("SELECT * FROM mission_rollback_points WHERE rollback_id=? AND mission_id=?", (rollback_id, mission_id)).fetchone()
    if row is None:
        raise ValueError("rollback point not found")
    request = {"rollback_id": rollback_id, "rollback_class": row["rollback_class"], "state_digest": row["state_digest"], "restorable": bool(row["restorable"]), "blocker": row["blocker"]}
    return create_design_revision(conn, mission_id, "ROLLBACK", request, now_fn, state="ROLLBACK_PLAN_REQUIRES_EXACT_RUNTIME_ADAPTER")


def decorate_snapshot(conn, snapshot, *, current_mission_id, rebound_adapter="LPCL_REBOUND_EPOCH3_64"):
    mid = snapshot["mission_id"]
    snapshot["schema_context"] = schema_context(conn, mid)
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
