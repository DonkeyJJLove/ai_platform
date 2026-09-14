from __future__ import annotations

import hashlib
import json
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from cyber_lion.mission_control.supervisor_projection import supervisor_projection

SCHEMA_VERSION = 5
SCHEMA_ID = "lion.saas-session-bridge/v2"
TRANSPORT = "CHATGPT_SENTINELX_SESSION_MEDIATED"
ATTESTATION_CLASS = "OPERATOR_SESSION_PLUS_CONNECTOR_ROUNDTRIP"

DDL = r"""
CREATE TABLE IF NOT EXISTS saas_session_bindings(
  binding_id TEXT PRIMARY KEY,
  mission_id TEXT NOT NULL,
  lpcl_digest TEXT NOT NULL,
  supervisor_role TEXT NOT NULL,
  model_identity TEXT NOT NULL,
  transport TEXT NOT NULL,
  attestation_class TEXT NOT NULL,
  authority_effect TEXT NOT NULL,
  status TEXT NOT NULL,
  created_at TEXT NOT NULL,
  bound_at TEXT NOT NULL,
  expires_at TEXT NOT NULL,
  last_request_id TEXT,
  attestation_json TEXT NOT NULL,
  attestation_digest TEXT NOT NULL,
  binding_scope TEXT NOT NULL DEFAULT 'MISSION'
);
CREATE INDEX IF NOT EXISTS idx_saas_binding_mission ON saas_session_bindings(mission_id,status,expires_at);
CREATE TABLE IF NOT EXISTS saas_handoff_requests(
  request_id TEXT PRIMARY KEY,
  mission_id TEXT NOT NULL,
  lpcl_digest TEXT NOT NULL,
  request_code TEXT NOT NULL UNIQUE,
  response_token TEXT NOT NULL,
  question TEXT NOT NULL,
  question_digest TEXT NOT NULL,
  status TEXT NOT NULL,
  created_at TEXT NOT NULL,
  expires_at TEXT NOT NULL,
  responded_at TEXT,
  response_text TEXT,
  response_digest TEXT,
  binding_id TEXT,
  response_meta_json TEXT,
  receipt_digest TEXT,
  progress_state TEXT,
  deadline_elapsed_at TEXT,
  retry_of_request_id TEXT
);
CREATE INDEX IF NOT EXISTS idx_saas_request_mission ON saas_handoff_requests(mission_id,status,created_at);
"""


def _canon(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def _digest(value):
    return hashlib.sha256(_canon(value).encode("utf-8")).hexdigest()


def _parse_ts(value):
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def _future(stamp, seconds):
    return (_parse_ts(stamp) + timedelta(seconds=int(seconds))).astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _columns(conn, table):
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def _ensure_column(conn, table, name, ddl):
    if name not in _columns(conn, table):
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}")


def migrate(conn, now_fn, *, source_head, source_tree):
    conn.executescript(DDL)
    # Forward-only compatibility for live databases created by schema v1.
    _ensure_column(conn, "saas_session_bindings", "binding_scope", "TEXT NOT NULL DEFAULT 'MISSION'")
    _ensure_column(conn, "saas_handoff_requests", "progress_state", "TEXT")
    _ensure_column(conn, "saas_handoff_requests", "deadline_elapsed_at", "TEXT")
    _ensure_column(conn, "saas_handoff_requests", "retry_of_request_id", "TEXT")
    stamp = now_fn()
    digest = hashlib.sha256(DDL.encode("utf-8")).hexdigest()
    conn.execute(
        "INSERT OR IGNORE INTO schema_migrations(version,schema_id,applied_at,source_head,source_tree,migration_digest,note) VALUES(?,?,?,?,?,?,?)",
        (SCHEMA_VERSION, SCHEMA_ID, stamp, source_head, source_tree, digest,
         "Epoch 3 SaaS supervisor v2: durable overdue handoffs, independent session lease, global supervisor-channel binding; authority effect NONE."),
    )
    conn.commit()


def _mission_binding(conn, mission_id):
    mission = conn.execute("SELECT mission_id,state,spec_digest FROM missions WHERE mission_id=?", (mission_id,)).fetchone()
    process = conn.execute("SELECT authority_state,current_phase FROM mission_process_specs WHERE mission_id=?", (mission_id,)).fetchone()
    if mission is None or process is None:
        raise ValueError("mission process unavailable")
    if process["authority_state"] != "EXPLICIT_USER_ACTIVATION":
        raise ValueError("exact LPCL not activated")
    if mission["state"] not in {"AUTHORIZED", "RUNNING", "WAITING", "BLOCKED"}:
        raise ValueError("mission state not eligible")
    return mission, process


def create_request(conn, mission_id, question, now_fn, *, ttl_seconds=900):
    if not isinstance(question, str) or not question.strip() or len(question) > 8000:
        raise ValueError("saas question")
    mission, process = _mission_binding(conn, mission_id)
    stamp = now_fn()
    # Queue semantics: multiple independent handoffs may coexist for one mission.
    # The panel polls exact request_id, while operator mediation consumes the oldest pending
    # request (FIFO). Never destroy a still-pending answer merely because a newer query arrived.
    request_id = "saas-" + uuid.uuid4().hex
    request_code = secrets.token_hex(4).upper()
    token = secrets.token_hex(32)
    question = question.strip()
    qdigest = hashlib.sha256(question.encode("utf-8")).hexdigest()
    expires = _future(stamp, ttl_seconds)
    conn.execute(
        "INSERT INTO saas_handoff_requests(request_id,mission_id,lpcl_digest,request_code,response_token,question,question_digest,status,created_at,expires_at,progress_state) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
        (request_id, mission_id, mission["spec_digest"], request_code, token, question, qdigest, "PENDING", stamp, expires, "WAITING_OPERATOR"),
    )
    conn.commit()
    return {
        "request_id": request_id,
        "request_code": request_code,
        "mission_id": mission_id,
        "lpcl_digest": mission["spec_digest"],
        "question_digest": qdigest,
        "status": "PENDING",
        "expires_at": expires,
        "transport": TRANSPORT,
        "operator_trigger": "LION SaaS",
        "authority_effect": "NONE",
    }


def _expire(conn, now_value):
    # Request deadlines are advisory progress deadlines, not destructive TTLs.
    # A handoff remains answerable until it is explicitly responded/rejected/superseded.
    conn.execute(
        "UPDATE saas_handoff_requests SET progress_state='WAITING_OPERATOR_OVERDUE', "
        "deadline_elapsed_at=COALESCE(deadline_elapsed_at,?) "
        "WHERE status='PENDING' AND expires_at<=?",
        (now_value, now_value),
    )
    # Session attestation is an independent freshness lease and may truthfully expire.
    conn.execute("UPDATE saas_session_bindings SET status='EXPIRED' WHERE status='BOUND' AND expires_at<=?", (now_value,))


def pending_request(conn, now_fn, *, request_code=None, mission_id=None):
    stamp = now_fn(); _expire(conn, stamp); conn.commit()
    where = ["status='PENDING'"]; args = []
    if request_code:
        where.append("request_code=?"); args.append(str(request_code).upper())
    if mission_id:
        where.append("mission_id=?"); args.append(mission_id)
    row = conn.execute(
        "SELECT * FROM saas_handoff_requests WHERE " + " AND ".join(where) + " ORDER BY created_at ASC LIMIT 1",
        tuple(args),
    ).fetchone()
    if row is None:
        return None
    out = dict(row)
    out["transport"] = TRANSPORT
    out["supervisor_role"] = "CHATGPT_SAAS_SUPERVISOR"
    out["dual_request_id"] = _dual_request_id(conn, out["request_id"]) if "mission_dual_evaluations" in {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()} else None
    out["authority_effect"] = "NONE"
    return out


def _dual_request_id(conn, request_id):
    try:
        row = conn.execute(
            "SELECT request_id FROM mission_dual_evaluations WHERE saas_request_id=? ORDER BY updated_at DESC LIMIT 1",
            (request_id,),
        ).fetchone()
    except Exception:
        return None
    if row is None:
        return None
    try:
        return row["request_id"]
    except Exception:
        return row[0]


def request_status(conn, request_id, now_fn):
    stamp = now_fn(); _expire(conn, stamp); conn.commit()
    row = conn.execute("SELECT * FROM saas_handoff_requests WHERE request_id=?", (request_id,)).fetchone()
    if row is None:
        raise ValueError("saas request not found")
    out = dict(row)
    out.pop("response_token", None)
    out["dual_request_id"] = _dual_request_id(conn, request_id)
    return out


def bridge_status(conn, mission_id, now_fn):
    stamp = now_fn(); _expire(conn, stamp); conn.commit()
    # The ChatGPT supervisor session is a control-plane channel, not a mission-local object.
    # Prefer a current global channel attestation and retain legacy mission-scoped fallback.
    binding = conn.execute(
        "SELECT * FROM saas_session_bindings WHERE binding_scope='GLOBAL_SUPERVISOR_CHANNEL' AND status='BOUND' ORDER BY bound_at DESC LIMIT 1"
    ).fetchone()
    if binding is None:
        binding = conn.execute(
            "SELECT * FROM saas_session_bindings WHERE mission_id=? AND status='BOUND' ORDER BY bound_at DESC LIMIT 1",
            (mission_id,),
        ).fetchone()
    last_binding = None
    if binding is None:
        # Preserve historical lease evidence without treating it as active binding.
        last_binding = conn.execute(
            "SELECT binding_id,mission_id,model_identity,transport,status,expires_at,binding_scope,authority_effect "
            "FROM saas_session_bindings WHERE binding_scope='GLOBAL_SUPERVISOR_CHANNEL' OR mission_id=? "
            "ORDER BY bound_at DESC LIMIT 1", (mission_id,),
        ).fetchone()
    pending = conn.execute(
        "SELECT request_id,request_code,status,created_at,expires_at,question_digest,progress_state,deadline_elapsed_at,retry_of_request_id FROM saas_handoff_requests WHERE mission_id=? AND status='PENDING' ORDER BY created_at ASC LIMIT 1",
        (mission_id,),
    ).fetchone()
    pending_count = int(conn.execute("SELECT COUNT(*) FROM saas_handoff_requests WHERE mission_id=? AND status='PENDING'", (mission_id,)).fetchone()[0])
    pending_value = dict(pending) if pending else None
    if pending_value is not None:
        pending_value["dual_request_id"] = _dual_request_id(conn, pending_value["request_id"])
    last_response = conn.execute(
        "SELECT request_id,responded_at,response_digest,receipt_digest,binding_id FROM saas_handoff_requests WHERE mission_id=? AND status='RESPONDED' ORDER BY responded_at DESC LIMIT 1",
        (mission_id,),
    ).fetchone()
    out = {
        "mission_id": mission_id,
        "state": "BOUND" if binding else ("PENDING_HANDOFF" if pending else "UNBOUND"),
        "channel_state": "READY_FOR_HANDOFF",
        "session_attestation_state": "BOUND" if binding else "NOT_ATTESTED",
        "session_scope": (binding["binding_scope"] if binding else None),
        "binding": dict(binding) if binding else None,
        "last_binding": dict(last_binding) if last_binding else None,
        "pending": pending_value,
        "pending_count": pending_count,
        "last_response": dict(last_response) if last_response else None,
        "queue_policy": "FIFO_MULTI_PENDING",
        "transport": TRANSPORT,
        "automatic_local_to_saas_hop": False,
        "operator_mediation_required": True,
        "cryptographic_provider_attestation": False,
        "authority_effect": "NONE",
    }
    out["supervisor_projection"] = supervisor_projection(out, now=stamp, observed_at=stamp)
    return out


def respond(conn, request_id, response_token, answer, now_fn, *, model_identity, transport=TRANSPORT, attestation_class=ATTESTATION_CLASS, lease_seconds=7200):
    if not isinstance(answer, str) or not answer.strip() or len(answer) > 24000:
        raise ValueError("saas answer")
    if not isinstance(model_identity, str) or not model_identity.strip() or len(model_identity) > 120:
        raise ValueError("model identity")
    stamp = now_fn(); _expire(conn, stamp)
    row = conn.execute("SELECT * FROM saas_handoff_requests WHERE request_id=?", (request_id,)).fetchone()
    if row is None:
        raise ValueError("saas request not found")
    if row["status"] != "PENDING":
        raise ValueError("saas request not pending")
    if not isinstance(response_token, str) or not secrets.compare_digest(response_token, row["response_token"]):
        raise ValueError("saas response token")
    mission, process = _mission_binding(conn, row["mission_id"])
    if mission["spec_digest"] != row["lpcl_digest"]:
        raise ValueError("saas lpcl digest drift")
    answer = answer.strip()
    rdigest = hashlib.sha256(answer.encode("utf-8")).hexdigest()
    binding_id = "saas-binding-" + uuid.uuid4().hex
    expires = _future(stamp, lease_seconds)
    attestation = {
        "binding_id": binding_id,
        "mission_id": row["mission_id"],
        "lpcl_digest": row["lpcl_digest"],
        "supervisor_role": "CHATGPT_SAAS_SUPERVISOR",
        "model_identity": model_identity.strip(),
        "transport": transport,
        "attestation_class": attestation_class,
        "authority_effect": "NONE",
        "request_id": request_id,
        "question_digest": row["question_digest"],
        "response_digest": rdigest,
        "bound_at": stamp,
        "expires_at": expires,
        "cryptographic_provider_attestation": False,
        "binding_scope": "GLOBAL_SUPERVISOR_CHANNEL",
    }
    adigest = _digest(attestation)
    conn.execute(
        "UPDATE saas_session_bindings SET status='SUPERSEDED' "
        "WHERE status='BOUND' AND (binding_scope='GLOBAL_SUPERVISOR_CHANNEL' OR mission_id=?)",
        (row["mission_id"],),
    )
    conn.execute(
        "INSERT INTO saas_session_bindings(binding_id,mission_id,lpcl_digest,supervisor_role,model_identity,transport,attestation_class,authority_effect,status,created_at,bound_at,expires_at,last_request_id,attestation_json,attestation_digest,binding_scope) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (binding_id,row["mission_id"],row["lpcl_digest"],"CHATGPT_SAAS_SUPERVISOR",model_identity.strip(),transport,attestation_class,"NONE","BOUND",stamp,stamp,expires,request_id,_canon(attestation),adigest,"GLOBAL_SUPERVISOR_CHANNEL"),
    )
    meta = {"model_identity": model_identity.strip(), "transport": transport, "attestation_class": attestation_class, "authority_effect": "NONE", "binding_scope": "GLOBAL_SUPERVISOR_CHANNEL"}
    receipt = {
        "request_id": request_id,
        "request_code": row["request_code"],
        "mission_id": row["mission_id"],
        "lpcl_digest": row["lpcl_digest"],
        "question_digest": row["question_digest"],
        "response_digest": rdigest,
        "binding_id": binding_id,
        "attestation_digest": adigest,
        "responded_at": stamp,
        "authority_effect": "NONE",
    }
    receipt_digest = _digest(receipt)
    conn.execute(
        "UPDATE saas_handoff_requests SET status='RESPONDED',progress_state='RECEIPT_BOUND',responded_at=?,response_text=?,response_digest=?,binding_id=?,response_meta_json=?,receipt_digest=? WHERE request_id=?",
        (stamp,answer,rdigest,binding_id,_canon(meta),receipt_digest,request_id),
    )
    conn.commit()
    return {"status":"RESPONDED","answer":answer,"binding":attestation,"receipt":{**receipt,"receipt_digest":receipt_digest}}
