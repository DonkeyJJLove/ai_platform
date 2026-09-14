from __future__ import annotations

import hashlib
import json
import os
import socket
import uuid
from datetime import datetime, timezone

from .execution_driver_contract import DRIVER_SCHEMA, DRIVER_STATES, legal_driver_transition

SCHEMA_VERSION = 4  # migration-ledger ordinal; schema semantic version remains v3
SCHEMA_ID = "lion.mission-control.lifecycle-db/v3"

DDL = r"""
CREATE TABLE IF NOT EXISTS mission_execution_drivers(
  mission_id TEXT PRIMARY KEY,
  driver_id TEXT NOT NULL,
  generation INTEGER NOT NULL,
  state TEXT NOT NULL,
  lease_token TEXT NOT NULL,
  lease_owner TEXT,
  lease_expires_at TEXT,
  heartbeat_at TEXT,
  current_phase TEXT,
  current_attempt_id TEXT,
  waiting_reason TEXT,
  blocking_gate TEXT,
  next_action TEXT,
  last_currentness_at TEXT,
  last_effect TEXT,
  last_effect_receipt TEXT,
  checkpoint_digest TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS mission_execution_checkpoints(
  checkpoint_id TEXT PRIMARY KEY,
  mission_id TEXT NOT NULL,
  driver_generation INTEGER NOT NULL,
  phase_id TEXT,
  attempt_id TEXT,
  state TEXT NOT NULL,
  cursor_json TEXT NOT NULL,
  cursor_digest TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS mission_phase_attempts(
  attempt_id TEXT PRIMARY KEY,
  mission_id TEXT NOT NULL,
  phase_id TEXT NOT NULL,
  driver_generation INTEGER NOT NULL,
  attempt_no INTEGER NOT NULL,
  state TEXT NOT NULL,
  started_at TEXT NOT NULL,
  finished_at TEXT,
  precondition_digest TEXT,
  evidence_digest TEXT,
  effect_receipt_digest TEXT,
  detail TEXT,
  UNIQUE(mission_id,phase_id,attempt_no)
);
CREATE TABLE IF NOT EXISTS mission_gate_observations(
  observation_id TEXT PRIMARY KEY,
  mission_id TEXT NOT NULL,
  phase_id TEXT,
  gate_id TEXT NOT NULL,
  state TEXT NOT NULL,
  observed_value_json TEXT NOT NULL,
  observed_digest TEXT NOT NULL,
  observed_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS mission_dual_evaluations(
  request_id TEXT PRIMARY KEY,
  mission_id TEXT NOT NULL,
  phase_id TEXT,
  context_digest TEXT NOT NULL,
  currentness_digest TEXT NOT NULL,
  original_request TEXT NOT NULL,
  local_prompt TEXT NOT NULL,
  saas_prompt TEXT NOT NULL,
  state TEXT NOT NULL,
  saas_request_id TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS mission_dual_receipts(
  receipt_id TEXT PRIMARY KEY,
  request_id TEXT NOT NULL,
  provider TEXT NOT NULL,
  response_digest TEXT NOT NULL,
  response_text TEXT NOT NULL,
  transport TEXT,
  authority_effect TEXT NOT NULL,
  created_at TEXT NOT NULL,
  UNIQUE(request_id,provider)
);
CREATE TABLE IF NOT EXISTS mission_revision_compilations(
  revision_id TEXT PRIMARY KEY,
  mission_id TEXT NOT NULL,
  successor_mission_id TEXT NOT NULL UNIQUE,
  lpcl_digest TEXT NOT NULL UNIQUE,
  lpcl_text TEXT NOT NULL,
  state TEXT NOT NULL,
  created_at TEXT NOT NULL,
  activated_at TEXT
);
"""


def _canon(v):
    return json.dumps(v, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def digest(v):
    return hashlib.sha256(_canon(v).encode("utf-8")).hexdigest()


def _plus_seconds(stamp, seconds):
    value=str(stamp).replace('Z','+00:00')
    dt=datetime.fromisoformat(value)
    return (dt + __import__('datetime').timedelta(seconds=int(seconds))).astimezone(timezone.utc).isoformat().replace('+00:00','Z')


def _lease_held_by_other(row, stamp, owner_id):
    owner=row['lease_owner'] if 'lease_owner' in row.keys() else None
    expires=row['lease_expires_at']
    return bool(owner and owner_id and owner != owner_id and expires and str(expires) > str(stamp))


def migrate(conn, now_fn, *, source_head=None, source_tree=None):
    conn.executescript(DDL)
    cols={r[1] for r in conn.execute("PRAGMA table_info(mission_execution_drivers)").fetchall()}
    if "lease_owner" not in cols:
        conn.execute("ALTER TABLE mission_execution_drivers ADD COLUMN lease_owner TEXT")
    stamp = now_fn()
    dg = hashlib.sha256(DDL.encode("utf-8")).hexdigest()
    conn.execute(
        "INSERT OR IGNORE INTO schema_migrations(version,schema_id,applied_at,source_head,source_tree,migration_digest,note) VALUES(?,?,?,?,?,?,?)",
        (SCHEMA_VERSION, SCHEMA_ID, stamp, source_head, source_tree, dg,
         "Durable fenced mission execution driver, checkpoints, attempts, gates and dual-result receipts."),
    )
    conn.commit()


def ensure_driver(conn, mission_id, now_fn, *, initial_state="BOOTSTRAP_PAUSED"):
    if initial_state not in DRIVER_STATES:
        raise ValueError("driver state")
    row = conn.execute("SELECT * FROM mission_execution_drivers WHERE mission_id=?", (mission_id,)).fetchone()
    if row:
        return dict(row)
    stamp = now_fn(); did = "driver-" + uuid.uuid4().hex; token = uuid.uuid4().hex
    conn.execute(
        "INSERT INTO mission_execution_drivers(mission_id,driver_id,generation,state,lease_token,created_at,updated_at) VALUES(?,?,?,?,?,?,?)",
        (mission_id, did, 1, initial_state, token, stamp, stamp),
    )
    conn.commit()
    return dict(conn.execute("SELECT * FROM mission_execution_drivers WHERE mission_id=?", (mission_id,)).fetchone())


def _checkpoint(conn, mission_id, now_fn, cursor):
    row = conn.execute("SELECT generation,current_phase,current_attempt_id FROM mission_execution_drivers WHERE mission_id=?", (mission_id,)).fetchone()
    if not row:
        raise ValueError("driver missing")
    stamp=now_fn(); cid="checkpoint-"+uuid.uuid4().hex; dg=digest(cursor)
    conn.execute("INSERT INTO mission_execution_checkpoints VALUES(?,?,?,?,?,?,?,?,?)",
        (cid,mission_id,row["generation"],row["current_phase"],row["current_attempt_id"],str(cursor.get("state") or "UNKNOWN"),_canon(cursor),dg,stamp))
    conn.execute("UPDATE mission_execution_drivers SET checkpoint_digest=?,updated_at=? WHERE mission_id=?",(dg,stamp,mission_id))
    return {"checkpoint_id":cid,"checkpoint_digest":dg}


def _terminalize(conn, mission_id, now_fn, *, next_action="TERMINAL_RECONCILED", last_effect=None, last_effect_receipt=None, reconcile=False, commit=True):
    row=conn.execute("SELECT * FROM mission_execution_drivers WHERE mission_id=?",(mission_id,)).fetchone()
    if not row: raise ValueError("driver missing")
    old=row["state"]
    if old != "COMPLETE" and not reconcile and not legal_driver_transition(old,"COMPLETE"):
        raise ValueError(f"illegal driver transition {old}->COMPLETE")
    latest=conn.execute("SELECT checkpoint_id,state,cursor_digest,created_at FROM mission_execution_checkpoints WHERE mission_id=? ORDER BY created_at DESC,rowid DESC LIMIT 1",(mission_id,)).fetchone()
    clean=(old=="COMPLETE" and row["lease_owner"] is None and row["lease_expires_at"] is None and row["current_phase"] is None and row["current_attempt_id"] is None and row["waiting_reason"] is None and row["blocking_gate"] is None and row["next_action"]==next_action and latest is not None and latest["state"]=="COMPLETE" and row["checkpoint_digest"]==latest["cursor_digest"])
    if clean:
        return {"checkpoint_id":latest["checkpoint_id"],"checkpoint_digest":latest["cursor_digest"],"idempotent":True,"previous_state":old}
    last_phase=row["current_phase"]; last_attempt=row["current_attempt_id"]; stamp=now_fn()
    conn.execute("UPDATE mission_execution_drivers SET state='COMPLETE',lease_owner=NULL,lease_expires_at=NULL,waiting_reason=NULL,blocking_gate=NULL,next_action=?,last_effect=COALESCE(?,last_effect),last_effect_receipt=COALESCE(?,last_effect_receipt),current_phase=NULL,current_attempt_id=NULL,updated_at=? WHERE mission_id=?",
        (next_action,last_effect,last_effect_receipt,stamp,mission_id))
    event="DRIVER_TERMINAL_RECONCILED" if reconcile else "DRIVER_COMPLETED"
    cp=_checkpoint(conn,mission_id,now_fn,{"state":"COMPLETE","event":event,"previous_state":old,"next_action":next_action,"last_phase_id":last_phase,"last_attempt_id":last_attempt,"lease_released":True})
    if commit:conn.commit()
    return {**cp,"idempotent":False,"previous_state":old,"last_phase_id":last_phase,"last_attempt_id":last_attempt}


def reconcile_complete(conn, mission_id, now_fn, *, next_action="TERMINAL_RECONCILED", commit=True):
    return _terminalize(conn,mission_id,now_fn,next_action=next_action,reconcile=True,commit=commit)


def transition(conn, mission_id, new_state, now_fn, *, waiting_reason=None, blocking_gate=None, next_action=None, last_effect=None, last_effect_receipt=None, current_phase=None, commit=True):
    row=conn.execute("SELECT state FROM mission_execution_drivers WHERE mission_id=?",(mission_id,)).fetchone()
    if not row: raise ValueError("driver missing")
    old=row["state"]
    if new_state not in DRIVER_STATES or not legal_driver_transition(old,new_state):
        raise ValueError(f"illegal driver transition {old}->{new_state}")
    if new_state=="COMPLETE":
        return _terminalize(conn,mission_id,now_fn,next_action=next_action or "TERMINAL_RECONCILED",last_effect=last_effect,last_effect_receipt=last_effect_receipt,reconcile=False,commit=commit)
    stamp=now_fn()
    conn.execute("UPDATE mission_execution_drivers SET state=?,waiting_reason=?,blocking_gate=?,next_action=?,last_effect=COALESCE(?,last_effect),last_effect_receipt=COALESCE(?,last_effect_receipt),current_phase=COALESCE(?,current_phase),updated_at=? WHERE mission_id=?",
        (new_state,waiting_reason,blocking_gate,next_action,last_effect,last_effect_receipt,current_phase,stamp,mission_id))
    cp=_checkpoint(conn,mission_id,now_fn,{"state":new_state,"waiting_reason":waiting_reason,"blocking_gate":blocking_gate,"next_action":next_action,"current_phase":current_phase})
    if commit:conn.commit()
    return cp


def activate(conn, mission_id, now_fn, *, next_action="SELECT_NEXT_PHASE", owner_id=None, lease_seconds=20):
    ensure_driver(conn,mission_id,now_fn)
    row=conn.execute("SELECT * FROM mission_execution_drivers WHERE mission_id=?",(mission_id,)).fetchone()
    if row["state"] == "COMPLETE": raise ValueError("driver complete")
    stamp=now_fn(); owner_id=str(owner_id or ("process:"+str(os.getpid())))
    if _lease_held_by_other(row,stamp,owner_id):
        raise ValueError("driver lease held by another owner")
    if row["state"] == "ACTIVE" and row["lease_owner"] == owner_id:
        heartbeat(conn,mission_id,now_fn,next_action=next_action,owner_id=owner_id,lease_seconds=lease_seconds)
        return snapshot(conn,mission_id)
    gen=int(row["generation"])+1; token=uuid.uuid4().hex; expires=_plus_seconds(stamp,lease_seconds)
    conn.execute("UPDATE mission_execution_drivers SET generation=?,state='ACTIVE',lease_token=?,lease_owner=?,lease_expires_at=?,heartbeat_at=?,last_currentness_at=?,waiting_reason=NULL,blocking_gate=NULL,next_action=?,updated_at=? WHERE mission_id=?",
        (gen,token,owner_id,expires,stamp,stamp,next_action,stamp,mission_id))
    _checkpoint(conn,mission_id,now_fn,{"state":"ACTIVE","event":"DRIVER_ACTIVATED","generation":gen,"owner_id":owner_id,"lease_expires_at":expires,"next_action":next_action})
    conn.commit(); return snapshot(conn,mission_id)

def heartbeat(conn, mission_id, now_fn, *, phase=None, next_action=None, owner_id=None, lease_seconds=20):
    row=conn.execute("SELECT * FROM mission_execution_drivers WHERE mission_id=?",(mission_id,)).fetchone()
    if not row or row["state"] not in {"ACTIVE","WAITING","BLOCKED"}: return None
    stamp=now_fn(); owner_id=str(owner_id or row["lease_owner"] or ("process:"+str(os.getpid())))
    if _lease_held_by_other(row,stamp,owner_id): raise ValueError("driver heartbeat fenced")
    expires=_plus_seconds(stamp,lease_seconds)
    conn.execute("UPDATE mission_execution_drivers SET lease_owner=?,lease_expires_at=?,heartbeat_at=?,last_currentness_at=?,current_phase=COALESCE(?,current_phase),next_action=COALESCE(?,next_action),updated_at=? WHERE mission_id=?",(owner_id,expires,stamp,stamp,phase,next_action,stamp,mission_id));conn.commit();return stamp

def begin_attempt(conn, mission_id, phase_id, now_fn, *, preconditions=None, owner_id=None):
    d=conn.execute("SELECT generation,state FROM mission_execution_drivers WHERE mission_id=?",(mission_id,)).fetchone()
    if not d or d["state"]!="ACTIVE": raise ValueError("driver not active")
    if owner_id:
        lease=conn.execute("SELECT lease_owner,lease_expires_at FROM mission_execution_drivers WHERE mission_id=?",(mission_id,)).fetchone();stamp0=now_fn()
        if not lease or lease["lease_owner"]!=owner_id or not lease["lease_expires_at"] or str(lease["lease_expires_at"])<=str(stamp0):raise ValueError("driver attempt lease not owned")
    no=int(conn.execute("SELECT COALESCE(MAX(attempt_no),0)+1 FROM mission_phase_attempts WHERE mission_id=? AND phase_id=?",(mission_id,phase_id)).fetchone()[0])
    aid="attempt-"+uuid.uuid4().hex; stamp=now_fn(); pd=digest(preconditions or {})
    conn.execute("INSERT INTO mission_phase_attempts(attempt_id,mission_id,phase_id,driver_generation,attempt_no,state,started_at,precondition_digest) VALUES(?,?,?,?,?,?,?,?)",(aid,mission_id,phase_id,d["generation"],no,"RUNNING",stamp,pd))
    conn.execute("UPDATE mission_execution_drivers SET current_phase=?,current_attempt_id=?,heartbeat_at=?,next_action=?,updated_at=? WHERE mission_id=?",(phase_id,aid,stamp,"EXECUTE_PHASE",stamp,mission_id));conn.commit();return aid


def finish_attempt(conn, attempt_id, now_fn, *, state, evidence=None, effect_receipt=None, detail=None):
    if state not in {"PASS","WAITING","BLOCKED","FAIL"}: raise ValueError("attempt state")
    stamp=now_fn(); ed=digest(evidence or {}) if evidence is not None else None
    conn.execute("UPDATE mission_phase_attempts SET state=?,finished_at=?,evidence_digest=?,effect_receipt_digest=?,detail=? WHERE attempt_id=?",(state,stamp,ed,effect_receipt,str(detail or '')[:4000],attempt_id))
    conn.commit();return {"attempt_id":attempt_id,"state":state,"evidence_digest":ed,"effect_receipt_digest":effect_receipt}


def observe_gate(conn, mission_id, phase_id, gate_id, state, value, now_fn):
    oid="gate-"+uuid.uuid4().hex; stamp=now_fn(); dg=digest(value)
    conn.execute("INSERT INTO mission_gate_observations VALUES(?,?,?,?,?,?,?,?)",(oid,mission_id,phase_id,gate_id,state,_canon(value),dg,stamp));conn.commit();return {"observation_id":oid,"digest":dg}


def adaptive_worker_plan(conn, mission_id, *, preferred_roles=(), limit=16):
    """Return a deterministic, read-only allocation plan inside the existing M64 pool.

    This never scales or mutates Kubernetes.  It selects already-bound READY workers
    while preserving logical/material identity and caps active concurrency.
    """
    if type(limit) is not int or not 1 <= limit <= 16:
        raise ValueError("adaptive concurrency limit")
    roles=tuple(str(x).upper() for x in preferred_roles if str(x).strip())
    rows=conn.execute("SELECT pod_name,pod_uid,logical_id,ready FROM material_workers WHERE mission_id=? ORDER BY logical_id,pod_name",(mission_id,)).fetchall()
    ready=[dict(r) for r in rows if int(r["ready"] or 0)==1 and r["pod_uid"]]
    if len(ready) != 64 or len({r["pod_uid"] for r in ready}) != 64:
        raise ValueError("adaptive scheduler requires exact ready M64 identity")
    rank={role:i for i,role in enumerate(roles)}
    ready.sort(key=lambda r:(rank.get(str(r["logical_id"]).upper(),len(rank)),str(r["logical_id"]),str(r["pod_name"])))
    selected=ready[:limit]
    return {
        "mission_id":mission_id,
        "policy":"BOUNDED_EXISTING_M64_READ_ONLY_ALLOCATION",
        "limit":limit,
        "selected":[{"pod_name":r["pod_name"],"pod_uid":r["pod_uid"],"logical_id":r["logical_id"]} for r in selected],
        "selected_count":len(selected),
        "pool_ready":64,
        "unique_uid_count":64,
        "authority_effect":"NONE",
    }


def snapshot(conn, mission_id):
    row=conn.execute("SELECT * FROM mission_execution_drivers WHERE mission_id=?",(mission_id,)).fetchone()
    if not row:return None
    d=dict(row)
    d["latest_checkpoint"] = dict(conn.execute("SELECT checkpoint_id,driver_generation,phase_id,attempt_id,state,cursor_digest,created_at FROM mission_execution_checkpoints WHERE mission_id=? ORDER BY created_at DESC,rowid DESC LIMIT 1",(mission_id,)).fetchone() or {})
    d["latest_attempt"] = dict(conn.execute("SELECT attempt_id,phase_id,driver_generation,attempt_no,state,started_at,finished_at,precondition_digest,evidence_digest,effect_receipt_digest,detail FROM mission_phase_attempts WHERE mission_id=? ORDER BY started_at DESC LIMIT 1",(mission_id,)).fetchone() or {})
    d["latest_gate"] = dict(conn.execute("SELECT observation_id,phase_id,gate_id,state,observed_digest,observed_at FROM mission_gate_observations WHERE mission_id=? ORDER BY observed_at DESC LIMIT 1",(mission_id,)).fetchone() or {})
    return d
