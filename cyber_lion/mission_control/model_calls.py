from __future__ import annotations

import hashlib
import json
import re

SCHEMA_ID="lion.model-call/v1"
AUTHORITY_EFFECT="NONE"
TRANSPORTS=frozenset({"LOCAL","CHATGPT_OPENAI_SECURE_MCP_TUNNEL","CHATGPT_FIREFOX_PROJECT_MEDIATED"})
STATES=frozenset({"INTENT_DURABLE","SEND_ATTEMPT","SEND_UNKNOWN","SEND_CONFIRMED","RESPONSE_RECONCILED","FAILED","CANCELLED"})
TRANSITIONS={
    "INTENT_DURABLE":frozenset({"SEND_ATTEMPT","CANCELLED"}),
    "SEND_ATTEMPT":frozenset({"SEND_UNKNOWN","SEND_CONFIRMED","FAILED"}),
    "SEND_UNKNOWN":frozenset({"SEND_CONFIRMED","FAILED","CANCELLED"}),
    "SEND_CONFIRMED":frozenset({"RESPONSE_RECONCILED","FAILED"}),
    "RESPONSE_RECONCILED":frozenset(),
    "FAILED":frozenset(),
    "CANCELLED":frozenset(),
}
ID_RE=re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,191}$")
HEX64=re.compile(r"^[0-9a-f]{64}$")


def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode("utf-8")


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def migrate(conn,now_fn):
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS mission_model_calls(
      model_call_id TEXT PRIMARY KEY,
      schema_id TEXT NOT NULL,
      mission_id TEXT NOT NULL,
      phase_id TEXT NOT NULL,
      task_id TEXT NOT NULL,
      assignment_id TEXT NOT NULL,
      logical_drone_id TEXT NOT NULL,
      material_worker_id TEXT NOT NULL,
      requested_capability TEXT NOT NULL,
      provider TEXT NOT NULL,
      model_requested TEXT,
      model_declared TEXT,
      model_attested TEXT,
      transport TEXT NOT NULL,
      selection_reason TEXT NOT NULL,
      candidate_set_digest TEXT NOT NULL,
      context_revision INTEGER NOT NULL,
      state TEXT NOT NULL,
      input_digest TEXT,
      result_digest TEXT,
      downstream_consumer TEXT,
      created_at TEXT NOT NULL,
      started_at TEXT,
      finished_at TEXT,
      updated_at TEXT NOT NULL,
      authority_effect TEXT NOT NULL,
      intent_digest TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_model_calls_mission_state
      ON mission_model_calls(mission_id,state,created_at);
    CREATE INDEX IF NOT EXISTS idx_model_calls_assignment
      ON mission_model_calls(assignment_id,created_at);
    """)
    return {"schema":SCHEMA_ID,"state":"READY","authority_effect":"NONE"}


def _text(value,name,limit=512,allow_none=False):
    if value is None and allow_none:return None
    if not isinstance(value,str) or not value or len(value)>limit:raise ValueError(name)
    return value


def _id(value,name):
    value=_text(value,name,192)
    if not ID_RE.fullmatch(value):raise ValueError(name)
    return value


def _hex64(value,name,allow_none=False):
    if value is None and allow_none:return None
    if not isinstance(value,str) or not HEX64.fullmatch(value):raise ValueError(name)
    return value


def create_intent(conn,payload,now_fn):
    required={
      "model_call_id","mission_id","phase_id","task_id","assignment_id",
      "logical_drone_id","material_worker_id","requested_capability",
      "provider","model_requested","model_declared","model_attested",
      "transport","selection_reason","candidate_set_digest","context_revision",
      "input_digest","downstream_consumer","authority_effect"
    }
    if type(payload) is not dict or set(payload)!=required:raise ValueError("model call intent schema")
    if payload["authority_effect"]!="NONE":raise ValueError("model call authority")
    transport=payload["transport"]
    if transport not in TRANSPORTS:raise ValueError("model call transport")
    context_revision=payload["context_revision"]
    if type(context_revision) is not int or context_revision<0:raise ValueError("context revision")
    normalized={
      "model_call_id":_id(payload["model_call_id"],"model_call_id"),
      "mission_id":_id(payload["mission_id"],"mission_id"),
      "phase_id":_id(payload["phase_id"],"phase_id"),
      "task_id":_id(payload["task_id"],"task_id"),
      "assignment_id":_id(payload["assignment_id"],"assignment_id"),
      "logical_drone_id":_id(payload["logical_drone_id"],"logical_drone_id"),
      "material_worker_id":_id(payload["material_worker_id"],"material_worker_id"),
      "requested_capability":_text(payload["requested_capability"],"requested_capability",256),
      "provider":_text(payload["provider"],"provider",256),
      "model_requested":_text(payload["model_requested"],"model_requested",256,True),
      "model_declared":_text(payload["model_declared"],"model_declared",256,True),
      "model_attested":_text(payload["model_attested"],"model_attested",256,True),
      "transport":transport,
      "selection_reason":_text(payload["selection_reason"],"selection_reason",1024),
      "candidate_set_digest":_hex64(payload["candidate_set_digest"],"candidate_set_digest"),
      "context_revision":context_revision,
      "input_digest":_hex64(payload["input_digest"],"input_digest",True),
      "downstream_consumer":_text(payload["downstream_consumer"],"downstream_consumer",256,True),
      "authority_effect":"NONE",
    }
    intent_digest=digest(normalized);stamp=now_fn()
    prior=conn.execute("SELECT intent_digest FROM mission_model_calls WHERE model_call_id=?",(normalized["model_call_id"],)).fetchone()
    if prior:
      if prior["intent_digest"]!=intent_digest:raise ValueError("model call idempotency conflict")
      row=conn.execute("SELECT * FROM mission_model_calls WHERE model_call_id=?",(normalized["model_call_id"],)).fetchone()
      return dict(row)
    conn.execute("""INSERT INTO mission_model_calls(
      model_call_id,schema_id,mission_id,phase_id,task_id,assignment_id,
      logical_drone_id,material_worker_id,requested_capability,provider,
      model_requested,model_declared,model_attested,transport,selection_reason,
      candidate_set_digest,context_revision,state,input_digest,result_digest,
      downstream_consumer,created_at,started_at,finished_at,updated_at,
      authority_effect,intent_digest
    ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,'INTENT_DURABLE',?,NULL,?,?,NULL,NULL,?,'NONE',?)""",(
      normalized["model_call_id"],SCHEMA_ID,normalized["mission_id"],normalized["phase_id"],
      normalized["task_id"],normalized["assignment_id"],normalized["logical_drone_id"],
      normalized["material_worker_id"],normalized["requested_capability"],normalized["provider"],
      normalized["model_requested"],normalized["model_declared"],normalized["model_attested"],
      normalized["transport"],normalized["selection_reason"],normalized["candidate_set_digest"],
      normalized["context_revision"],normalized["input_digest"],normalized["downstream_consumer"],
      stamp,stamp,intent_digest
    ))
    conn.commit()
    row=conn.execute("SELECT * FROM mission_model_calls WHERE model_call_id=?",(normalized["model_call_id"],)).fetchone()
    return dict(row)


def transition(conn,model_call_id,payload,now_fn):
    model_call_id=_id(model_call_id,"model_call_id")
    required={"state","result_digest","model_declared","model_attested","downstream_consumer","authority_effect"}
    if type(payload) is not dict or set(payload)!=required:raise ValueError("model call transition schema")
    if payload["authority_effect"]!="NONE":raise ValueError("model call authority")
    target=payload["state"]
    if target not in STATES:raise ValueError("model call state")
    row=conn.execute("SELECT * FROM mission_model_calls WHERE model_call_id=?",(model_call_id,)).fetchone()
    if row is None:raise ValueError("model call not found")
    current=row["state"]
    if target==current:return dict(row)
    if target not in TRANSITIONS[current]:raise ValueError("model call transition")
    result_digest=_hex64(payload["result_digest"],"result_digest",True)
    model_declared=_text(payload["model_declared"],"model_declared",256,True)
    model_attested=_text(payload["model_attested"],"model_attested",256,True)
    consumer=_text(payload["downstream_consumer"],"downstream_consumer",256,True)
    stamp=now_fn()
    started=stamp if target=="SEND_ATTEMPT" and row["started_at"] is None else row["started_at"]
    finished=stamp if target in {"RESPONSE_RECONCILED","FAILED","CANCELLED"} else row["finished_at"]
    conn.execute("""UPDATE mission_model_calls
      SET state=?,result_digest=COALESCE(?,result_digest),
          model_declared=COALESCE(?,model_declared),
          model_attested=COALESCE(?,model_attested),
          downstream_consumer=COALESCE(?,downstream_consumer),
          started_at=?,finished_at=?,updated_at=?
      WHERE model_call_id=?""",(target,result_digest,model_declared,model_attested,consumer,started,finished,stamp,model_call_id))
    conn.commit()
    return dict(conn.execute("SELECT * FROM mission_model_calls WHERE model_call_id=?",(model_call_id,)).fetchone())


def list_calls(conn,mission_id=None,assignment_id=None,limit=200):
    limit=max(1,min(int(limit),1000))
    mid=_id(mission_id,"mission_id") if mission_id is not None else None
    aid=_id(assignment_id,"assignment_id") if assignment_id is not None else None
    if mid is not None and aid is not None:
      rows=conn.execute("SELECT * FROM mission_model_calls WHERE mission_id=? AND assignment_id=? ORDER BY created_at DESC,model_call_id DESC LIMIT ?",(mid,aid,limit))
    elif mid is not None:
      rows=conn.execute("SELECT * FROM mission_model_calls WHERE mission_id=? ORDER BY created_at DESC,model_call_id DESC LIMIT ?",(mid,limit))
    elif aid is not None:
      rows=conn.execute("SELECT * FROM mission_model_calls WHERE assignment_id=? ORDER BY created_at DESC,model_call_id DESC LIMIT ?",(aid,limit))
    else:
      rows=conn.execute("SELECT * FROM mission_model_calls ORDER BY created_at DESC,model_call_id DESC LIMIT ?",(limit,))
    return [dict(r) for r in rows]


def get_call(conn,model_call_id):
    row=conn.execute("SELECT * FROM mission_model_calls WHERE model_call_id=?",(_id(model_call_id,"model_call_id"),)).fetchone()
    return dict(row) if row else None
