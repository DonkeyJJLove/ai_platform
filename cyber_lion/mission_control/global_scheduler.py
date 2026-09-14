from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

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
  created_at TEXT NOT NULL,
  claimed_at TEXT,
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
    turn_cols={r[1] for r in conn.execute('PRAGMA table_info(mission_scheduler_turns)')}
    if 'last_dispatch_order' not in turn_cols:
        conn.execute('ALTER TABLE mission_scheduler_turns ADD COLUMN last_dispatch_order INTEGER NOT NULL DEFAULT 0')
    stamp = now_fn()
    conn.execute(
        "INSERT OR IGNORE INTO mission_scheduler_state(scheduler_id,generation,state,heartbeat_at,queue_depth,active_run_count) VALUES(?,?,?,?,?,?)",
        (SCHEDULER_ID, 1, "ACTIVE", stamp, 0, 0),
    )
    conn.execute('INSERT OR IGNORE INTO mission_scheduler_migrations VALUES(1,?,?)',
                 ('lion.scheduler-storage-reconciliation/v1',stamp))
    if [r[0] for r in conn.execute('PRAGMA integrity_check')] != ['ok']:
        conn.rollback()
        raise ValueError('scheduler database integrity after migration')
    conn.commit()


def scheduler_snapshot(conn):
    row = conn.execute("SELECT * FROM mission_scheduler_state WHERE scheduler_id=?", (SCHEDULER_ID,)).fetchone()
    return dict(row) if row else None


def heartbeat(conn, now_fn, *, queue_depth, active_run_count, last_error=None, dispatched=False):
    stamp = now_fn()
    conn.execute(
        "UPDATE mission_scheduler_state SET state='ACTIVE',heartbeat_at=?,last_dispatch_at=CASE WHEN ? THEN ? ELSE last_dispatch_at END,queue_depth=?,active_run_count=?,last_error=? WHERE scheduler_id=?",
        (stamp, 1 if dispatched else 0, stamp, int(queue_depth), int(active_run_count), last_error, SCHEDULER_ID),
    )
    conn.commit()
    return scheduler_snapshot(conn)


def resolve_phase_execution_spec(phase_id, handlers, *, default_timeout=300):
    """Pure phase-spec resolution. Unknown phases are fail-closed and effect-free."""
    pid = str(phase_id)
    configured = handlers.get(pid)
    if configured is None:
        return {
            "handler_id": "PHASE_HANDLER_NOT_REGISTERED",
            "handler_version": "1",
            "effect_class": "NONE",
            "gate_class": "WAITING",
            "timeout_seconds": int(default_timeout),
            "retry_policy": "NO_AUTOMATIC_RETRY",
            "authority_class": "NONE",
        }
    spec = dict(configured)
    if not spec.get("handler_id"):
        raise ValueError("phase handler id")
    spec.setdefault("handler_version", "1")
    spec.setdefault("effect_class", "NONE")
    spec.setdefault("gate_class", "NONE")
    spec.setdefault("timeout_seconds", int(default_timeout))
    spec.setdefault("retry_policy", "NO_AUTOMATIC_RETRY")
    spec.setdefault("authority_class", "NONE")
    spec["timeout_seconds"] = int(spec["timeout_seconds"])
    return spec


def compile_phase_specs(conn, mission_id, handlers, *, default_timeout=300):
    rows = conn.execute(
        "SELECT phase_id FROM mission_phases WHERE mission_id=? ORDER BY ordinal", (mission_id,)
    ).fetchall()
    out = []
    for row in rows:
        pid = str(row["phase_id"])
        spec = resolve_phase_execution_spec(pid, handlers, default_timeout=default_timeout)
        conn.execute(
            "INSERT INTO mission_phase_execution_specs VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(mission_id,phase_id) DO UPDATE SET handler_id=excluded.handler_id,handler_version=excluded.handler_version,effect_class=excluded.effect_class,gate_class=excluded.gate_class,timeout_seconds=excluded.timeout_seconds,retry_policy=excluded.retry_policy,authority_class=excluded.authority_class",
            (
                mission_id, pid, spec["handler_id"], spec["handler_version"],
                spec["effect_class"], spec["gate_class"],
                spec["timeout_seconds"], spec["retry_policy"], spec["authority_class"],
            ),
        )
        out.append({"phase_id": pid, **spec})
    conn.commit()
    return out


def _parse_range(value, prefix):
    left, right = str(value).split("-", 1)
    if not left.startswith(prefix) or not right.startswith(prefix):
        raise ValueError("logical/material range prefix")
    a, b = int(left[len(prefix):]), int(right[len(prefix):])
    if a > b:
        raise ValueError("descending range")
    return tuple(f"{prefix}{i:03d}" for i in range(a, b + 1))


def parse_128l64m_topology(lpcl_text):
    lines = [x.strip() for x in str(lpcl_text).replace("\r", "").split("\n")]
    cohorts = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("COHORT_") and "=" in line:
            key, value = line.split("=", 1)
            if not value:
                i += 1
                while i < len(lines) and not lines[i]:
                    i += 1
                value = lines[i] if i < len(lines) else ""
            logical = _parse_range(value, "LD")
            role = None
            material = None
            j = i + 1
            while j < len(lines) and not lines[j].startswith("COHORT_"):
                if lines[j] == "ROLE=" or lines[j].startswith("ROLE="):
                    rv = lines[j].split("=", 1)[1]
                    if not rv:
                        j += 1
                        while j < len(lines) and not lines[j]: j += 1
                        rv = lines[j] if j < len(lines) else ""
                    role = rv
                if lines[j] == "MATERIAL=" or lines[j].startswith("MATERIAL="):
                    mv = lines[j].split("=", 1)[1]
                    if not mv:
                        j += 1
                        while j < len(lines) and not lines[j]: j += 1
                        mv = lines[j] if j < len(lines) else ""
                    material = _parse_range(mv, "MD")
                j += 1
            if len(logical) != 8 or not role or material is None or len(material) != 4:
                raise ValueError("invalid 128L64M cohort")
            cohorts.append((key, logical, role, material))
            i = j
            continue
        i += 1
    if len(cohorts) != 16:
        raise ValueError("expected 16 cohorts")
    logical_ids = [lid for _, ids, _, _ in cohorts for lid in ids]
    material_ids = [mid for _, _, _, ids in cohorts for mid in ids]
    if logical_ids != [f"LD{i:03d}" for i in range(1, 129)]:
        raise ValueError("logical topology not exact LD001-LD128")
    if material_ids != [f"MD{i:03d}" for i in range(1, 65)]:
        raise ValueError("material topology not exact MD001-MD064")
    return cohorts


def bind_128l64m(conn, mission_id, lpcl_text, workers, now_fn):
    cohorts = parse_128l64m_topology(lpcl_text)
    if len(workers) != 64:
        raise ValueError("material worker count must be 64")
    uids = [str(w.get("pod_uid") or w.get("uid") or "") for w in workers]
    if any(not x for x in uids) or len(set(uids)) != 64:
        raise ValueError("material worker UIDs must be 64 unique non-empty values")
    if any(int(w.get("ready", 0) or 0) != 1 for w in workers):
        raise ValueError("all material workers must be ready")
    ordered = sorted(workers, key=lambda w: (str(w.get("pod_name") or w.get("name") or ""), str(w.get("pod_uid") or w.get("uid") or "")))
    stamp = now_fn()
    conn.execute("DELETE FROM logical_drones WHERE mission_id=?", (mission_id,))
    conn.execute("DELETE FROM material_workers WHERE mission_id=?", (mission_id,))
    conn.execute("DELETE FROM mission_execution_assignments WHERE mission_id=? AND phase_id='__TOPOLOGY__'", (mission_id,))
    logical = []
    for _, ids, role, _ in cohorts:
        for lid in ids:
            conn.execute("INSERT INTO logical_drones VALUES(?,?,?,?,?,?)", (mission_id, lid, role, 0, 0, 0))
            logical.append((lid, role))
    for idx, worker in enumerate(ordered, 1):
        material_id = f"MD{idx:03d}"
        pod_name = str(worker.get("pod_name") or worker.get("name") or material_id)
        pod_uid = str(worker.get("pod_uid") or worker.get("uid"))
        conn.execute(
            "INSERT INTO material_workers VALUES(?,?,?,?,?,?,?,?,?)",
            (mission_id, pod_name, pod_uid, material_id, str(worker.get("phase") or "RUNNING"), 1, int(worker.get("restarts", 0) or 0), worker.get("pod_ip"), stamp),
        )
        for logical_index in (2 * idx - 2, 2 * idx - 1):
            lid, _ = logical[logical_index]
            assignment_id = "topology-" + uuid.uuid4().hex
            input_digest = digest({"mission_id": mission_id, "logical_drone_id": lid, "material_drone_id": material_id, "pod_uid": pod_uid})
            conn.execute(
                "INSERT INTO mission_execution_assignments(assignment_id,mission_id,phase_id,logical_drone_id,material_drone_id,input_digest,input_json,state,lease_generation,created_at,claimed_at,finished_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                (assignment_id, mission_id, "__TOPOLOGY__", lid, material_id, input_digest, _canon({"pod_uid":pod_uid}), "BOUND", 1, stamp, stamp, stamp),
            )
    conn.execute(
        "UPDATE missions SET adapter='LPCL_REBOUND_EPOCH3_128L64M',state='RUNNING',runtime_state='REBOUND_EXISTING_HEALTHY_FLEET_128L64M',materialized=64,ready=64,updated_at=?,last_error=NULL WHERE mission_id=?",
        (stamp, mission_id),
    )
    conn.commit()
    return {
        "mission_id": mission_id,
        "logical_count": 128,
        "material_count": 64,
        "unique_uid_count": 64,
        "assignments": 128,
        "ratio": "2:1",
        "authority_effect": "MISSION_SCOPED_CONTROL_BINDING",
    }


def eligible_missions(conn):
    rows = conn.execute(
        "SELECT d.mission_id,d.state,d.heartbeat_at,d.current_phase,m.updated_at FROM mission_execution_drivers d JOIN missions m ON m.mission_id=d.mission_id WHERE d.state IN ('ACTIVE','WAITING','BLOCKED') AND m.state NOT IN ('SUPERSEDED','FAILED') ORDER BY CASE d.state WHEN 'ACTIVE' THEN 0 WHEN 'WAITING' THEN 1 ELSE 2 END, COALESCE(d.heartbeat_at,m.updated_at), d.mission_id"
    ).fetchall()
    return [dict(r) for r in rows]


def next_dispatch(conn, now_fn):
    # Acquire the SQLite writer before selection: two schedulers must not
    # choose from the same stale turn history. This records selection only;
    # execution and its existing admission boundaries remain with the caller.
    conn.execute('SAVEPOINT scheduler_select_turn')
    try:
        conn.execute('UPDATE mission_scheduler_state SET generation=generation WHERE scheduler_id=?',(SCHEDULER_ID,))
        rows = eligible_missions(conn)
        turns={r['mission_id']:r['last_dispatch_order'] for r in conn.execute('SELECT mission_id,last_dispatch_order FROM mission_scheduler_turns')}
        # Stable sort retains existing ACTIVE-first order for never-dispatched
        # ties, then rotates fairly through all eligible driver states.
        rows.sort(key=lambda r:turns.get(r['mission_id'],0))
        if rows:
            order=conn.execute('SELECT COALESCE(MAX(last_dispatch_order),0)+1 FROM mission_scheduler_turns').fetchone()[0]
            conn.execute('INSERT INTO mission_scheduler_turns(mission_id,last_dispatch_order,dispatch_count,last_dispatched_at) VALUES(?,?,1,?) ON CONFLICT(mission_id) DO UPDATE SET last_dispatch_order=excluded.last_dispatch_order,dispatch_count=mission_scheduler_turns.dispatch_count+1,last_dispatched_at=excluded.last_dispatched_at',
                         (rows[0]['mission_id'],order,now_fn()))
    except Exception:
        conn.execute('ROLLBACK TO scheduler_select_turn')
        conn.execute('RELEASE scheduler_select_turn')
        raise
    conn.execute('RELEASE scheduler_select_turn')
    active = sum(1 for r in rows if r["state"] == "ACTIVE")
    heartbeat(conn, now_fn, queue_depth=len(rows), active_run_count=active, dispatched=bool(rows))
    return rows[0] if rows else None


def create_assignment(conn, mission_id, phase_id, logical_drone_id, material_drone_id, input_value, now_fn, *, lease_generation):
    aid = "assignment-" + uuid.uuid4().hex
    stamp = now_fn()
    conn.execute(
        "INSERT INTO mission_execution_assignments(assignment_id,mission_id,phase_id,logical_drone_id,material_drone_id,input_digest,input_json,state,lease_generation,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
        (aid, mission_id, phase_id, logical_drone_id, material_drone_id, digest(input_value), _canon(input_value), "READY", int(lease_generation), stamp),
    )
    conn.commit()
    return aid


def record_receipt(conn, assignment_id, result, now_fn, *, material_drone_id, lease_generation, status="PASS", effect_receipt_digest=None, authority_effect="NONE"):
    """Worker ingress: request identity is a binding check, not authentication."""
    if not isinstance(material_drone_id, str) or not material_drone_id:
        raise ValueError('material identity required')
    if type(lease_generation) is not int or lease_generation < 1:
        raise ValueError('lease generation required')
    if status not in {'PASS', 'FAIL'} or authority_effect != 'NONE':
        raise ValueError('assignment receipt status/authority')
    return _record_receipt(conn, assignment_id, result, now_fn, status=status,
        effect_receipt_digest=effect_receipt_digest, authority_effect=authority_effect,
        worker_binding=(material_drone_id, lease_generation))


def record_internal_receipt(conn, assignment_id, result, now_fn, *, status="PASS", effect_receipt_digest=None, authority_effect="NONE"):
    """Trusted in-process ledger import; never expose through worker/HTTP ingress."""
    return _record_receipt(conn, assignment_id, result, now_fn, status=status,
        effect_receipt_digest=effect_receipt_digest, authority_effect=authority_effect)


def _record_receipt(conn, assignment_id, result, now_fn, *, status, effect_receipt_digest, authority_effect, worker_binding=None):
    result_digest = digest(result)
    rid = "receipt-" + uuid.uuid4().hex
    stamp = now_fn()
    conn.execute('SAVEPOINT scheduler_receipt_ingress')
    try:
        # A no-op write serializes independent connections before the read.
        # Historical conflicting receipts remain untouched and fail closed.
        conn.execute('UPDATE mission_execution_assignments SET state=state WHERE assignment_id=?',(assignment_id,))
        row = conn.execute("SELECT mission_id,phase_id,state,material_drone_id,lease_generation FROM mission_execution_assignments WHERE assignment_id=?", (assignment_id,)).fetchone()
        if not row:
            raise ValueError("assignment missing")
        if worker_binding is not None:
            material_drone_id, lease_generation = worker_binding
            if row['material_drone_id'] != material_drone_id:
                raise ValueError('material identity mismatch')
            driver = conn.execute('SELECT generation FROM mission_execution_drivers WHERE mission_id=?', (row['mission_id'],)).fetchone()
            if row['lease_generation'] != lease_generation or not driver or driver['generation'] != lease_generation:
                raise ValueError('stale assignment generation')
        existing = conn.execute("SELECT result_digest,effect_receipt_digest,authority_effect,status FROM mission_execution_receipts WHERE assignment_id=? ORDER BY observed_at,receipt_id", (assignment_id,)).fetchall()
        if existing:
            identical=len(existing)==1 and tuple(existing[0])==(result_digest,effect_receipt_digest,authority_effect,status)
            raise ValueError('assignment receipt duplicate' if identical else 'assignment receipt conflict')
        if worker_binding is not None and row['state'] != 'CLAIMED':
            raise ValueError('assignment not claimed')
        conn.execute(
            "INSERT INTO mission_execution_receipts VALUES(?,?,?,?,?,?,?,?,?)",
            (rid, assignment_id, row["mission_id"], row["phase_id"], result_digest, effect_receipt_digest, authority_effect, status, stamp),
        )
        conn.execute("UPDATE mission_execution_assignments SET state=?,finished_at=? WHERE assignment_id=?", (status, stamp, assignment_id))
    except Exception:
        conn.execute('ROLLBACK TO scheduler_receipt_ingress')
        conn.execute('RELEASE scheduler_receipt_ingress')
        raise
    conn.execute('RELEASE scheduler_receipt_ingress')
    conn.commit()
    return {"receipt_id": rid, "duplicate": False, "result_digest": result_digest}


def pending_local_assignments(conn, *, mission_id=None, limit=16):
    if type(limit) is not int or not 1 <= limit <= 64:
        raise ValueError("assignment limit")
    if mission_id:
        rows=conn.execute(
            "SELECT * FROM mission_execution_assignments WHERE state='READY' AND mission_id=? ORDER BY created_at,assignment_id LIMIT ?",
            (mission_id, limit),
        ).fetchall()
    else:
        rows=conn.execute(
            "SELECT * FROM mission_execution_assignments WHERE state='READY' ORDER BY created_at,assignment_id LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


def claim_assignment(conn, assignment_id, now_fn, *, expected_material_drone_id=None):
    row=conn.execute("SELECT * FROM mission_execution_assignments WHERE assignment_id=?",(assignment_id,)).fetchone()
    if not row:raise ValueError("assignment missing")
    if row['state']!='READY':raise ValueError("assignment not ready")
    if expected_material_drone_id and row['material_drone_id']!=expected_material_drone_id:raise ValueError("material identity mismatch")
    stamp=now_fn();cur=conn.execute("UPDATE mission_execution_assignments SET state='CLAIMED',claimed_at=? WHERE assignment_id=? AND state='READY'",(stamp,assignment_id))
    if cur.rowcount!=1:raise ValueError("assignment claim race")
    conn.commit();out=dict(row);out['state']='CLAIMED';out['claimed_at']=stamp;return out
