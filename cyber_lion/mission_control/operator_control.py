"""Durable human-operator control plane for LION missions.

This module owns authority state, intervention receipts, participant mailboxes and
fencing metadata. It deliberately performs no model inference and no network I/O.
"""
from __future__ import annotations

import json
import secrets
import uuid
from typing import Any

from cyber_lion.contracts.operator_intervention import (
    ACTIONS, COMMUNICATION_ACTIONS, CONTEXT_ACTIONS, CONTROL_ACTIONS,
    PRIMARY_OPERATOR, PRIMARY_PARTICIPANT, OperatorCommand,
    action_effect, canonical, command_receipt_digest, digest,
)

SCHEMA_ID = "lion.operator-control/v1"
SCHEMA_VERSION = 7
GENERAL_CHANNEL_ID = "sentinelx:general"
AUTONOMOUS_OWNER = "AUTONOMOUS"
SENTINELX_PROXY_PRINCIPAL = "OPERATOR_SENTINELX_PROXY"
SENTINELX_PROXY_PARTICIPANT = "operator-proxy:sentinelx"
PANEL_PROXY_PRINCIPAL = "OPERATOR_PANEL_PROXY"
PANEL_PROXY_PARTICIPANT = "operator-proxy:panel8780"
DEFAULT_PROXY_ACTIONS = frozenset({"MESSAGE","REQUEST_STATUS","ANNOTATE","PAUSE_SCOPE","STOP_SCOPE","TAKE_CONTROL"})

DDL = r"""
CREATE TABLE IF NOT EXISTS operator_participants(
  participant_id TEXT PRIMARY KEY,
  principal_id TEXT NOT NULL UNIQUE,
  participant_kind TEXT NOT NULL,
  display_name TEXT NOT NULL,
  state TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS operator_grants(
  grant_id TEXT PRIMARY KEY,
  principal_id TEXT NOT NULL,
  mission_scope TEXT NOT NULL,
  actions_json TEXT NOT NULL,
  issued_at TEXT NOT NULL,
  expires_at TEXT,
  revoked_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_operator_grants_principal_scope ON operator_grants(principal_id,mission_scope,issued_at);
CREATE TABLE IF NOT EXISTS mission_operator_control(
  mission_id TEXT PRIMARY KEY,
  incarnation_id TEXT NOT NULL,
  control_epoch INTEGER NOT NULL,
  control_owner TEXT NOT NULL,
  pause_latch INTEGER NOT NULL,
  stop_latch INTEGER NOT NULL,
  context_revision INTEGER NOT NULL,
  plan_revision INTEGER NOT NULL,
  last_command_id TEXT,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS operator_commands(
  command_id TEXT PRIMARY KEY,
  command_digest TEXT NOT NULL,
  mission_id TEXT NOT NULL,
  action TEXT NOT NULL,
  target TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  principal_id TEXT NOT NULL,
  participant_id TEXT NOT NULL,
  grant_id TEXT NOT NULL,
  effective_priority INTEGER NOT NULL,
  admitted_control_epoch INTEGER NOT NULL,
  delivery_state TEXT NOT NULL,
  admission_state TEXT NOT NULL,
  execution_state TEXT NOT NULL,
  observation_state TEXT NOT NULL,
  created_at TEXT NOT NULL,
  admitted_at TEXT NOT NULL,
  completed_at TEXT,
  result_json TEXT
);
CREATE INDEX IF NOT EXISTS idx_operator_commands_mission
  ON operator_commands(mission_id,admitted_at,command_id);
CREATE TABLE IF NOT EXISTS operator_command_receipts(
  command_id TEXT PRIMARY KEY,
  receipt_digest TEXT NOT NULL UNIQUE,
  receipt_json TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE TRIGGER IF NOT EXISTS operator_command_receipt_immutable
BEFORE UPDATE ON operator_command_receipts
BEGIN SELECT RAISE(ABORT,'immutable operator receipt'); END;
CREATE TABLE IF NOT EXISTS operator_events(
  event_id INTEGER PRIMARY KEY AUTOINCREMENT,
  mission_id TEXT NOT NULL,
  command_id TEXT,
  event_type TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  payload_digest TEXT NOT NULL,
  observed_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_operator_events_mission
  ON operator_events(mission_id,event_id);
CREATE TABLE IF NOT EXISTS operator_messages(
  message_id TEXT PRIMARY KEY,
  mission_id TEXT NOT NULL,
  command_id TEXT NOT NULL,
  from_participant TEXT NOT NULL,
  target TEXT NOT NULL,
  kind TEXT NOT NULL,
  content TEXT NOT NULL,
  content_digest TEXT NOT NULL,
  context_revision INTEGER NOT NULL,
  plan_revision INTEGER NOT NULL,
  state TEXT NOT NULL,
  created_at TEXT NOT NULL,
  applied_at TEXT,
  applied_assignment_id TEXT,
  correlation_id TEXT,
  causation_id TEXT,
  fanout_id TEXT,
  recipient_set_digest TEXT
);
CREATE INDEX IF NOT EXISTS idx_operator_messages_target
  ON operator_messages(mission_id,target,state,created_at);
CREATE TABLE IF NOT EXISTS operator_message_deliveries(
  message_id TEXT NOT NULL,
  recipient TEXT NOT NULL,
  delivery_state TEXT NOT NULL,
  delivered_at TEXT,
  applied_at TEXT,
  applied_assignment_id TEXT,
  PRIMARY KEY(message_id,recipient)
);
CREATE INDEX IF NOT EXISTS idx_operator_message_deliveries_state
  ON operator_message_deliveries(delivery_state,message_id);
CREATE TABLE IF NOT EXISTS operator_protocol_recipient_routes(
  message_id TEXT NOT NULL,
  recipient TEXT NOT NULL,
  cognition_route TEXT NOT NULL,
  PRIMARY KEY(message_id,recipient)
);
CREATE TABLE IF NOT EXISTS protocol_cognitive_trajectories(
  trajectory_id TEXT PRIMARY KEY,
  message_id TEXT NOT NULL,
  mission_id TEXT NOT NULL,
  participant_id TEXT NOT NULL,
  cognition_route TEXT NOT NULL,
  local_assignment_id TEXT,
  local_model_call_id TEXT,
  saas_request_id TEXT,
  dual_request_id TEXT,
  state TEXT NOT NULL,
  result_digest TEXT,
  response_message_id TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  authority_effect TEXT NOT NULL,
  UNIQUE(message_id,participant_id)
);
CREATE INDEX IF NOT EXISTS idx_protocol_cognitive_trajectories_state
  ON protocol_cognitive_trajectories(state,mission_id,message_id);
CREATE TABLE IF NOT EXISTS mission_context_revisions(
  mission_id TEXT NOT NULL,
  revision INTEGER NOT NULL,
  command_id TEXT NOT NULL,
  content_json TEXT NOT NULL,
  content_digest TEXT NOT NULL,
  created_at TEXT NOT NULL,
  PRIMARY KEY(mission_id,revision)
);
CREATE TABLE IF NOT EXISTS mission_plan_revisions(
  mission_id TEXT NOT NULL,
  revision INTEGER NOT NULL,
  command_id TEXT NOT NULL,
  content_json TEXT NOT NULL,
  content_digest TEXT NOT NULL,
  created_at TEXT NOT NULL,
  PRIMARY KEY(mission_id,revision)
);
CREATE TABLE IF NOT EXISTS operator_pending_plan_amendments(
  proposal_id TEXT PRIMARY KEY,
  mission_id TEXT NOT NULL,
  command_id TEXT NOT NULL UNIQUE,
  content_json TEXT NOT NULL,
  content_digest TEXT NOT NULL,
  requested_scope_json TEXT NOT NULL,
  state TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_operator_pending_plan_mission
  ON operator_pending_plan_amendments(mission_id,state,created_at);
CREATE TABLE IF NOT EXISTS operator_capability_revocations(
  mission_id TEXT NOT NULL,
  capability TEXT NOT NULL,
  command_id TEXT NOT NULL,
  control_epoch INTEGER NOT NULL,
  revoked_at TEXT NOT NULL,
  released_at TEXT,
  PRIMARY KEY(mission_id,capability,command_id)
);
CREATE TABLE IF NOT EXISTS operator_approvals(
  mission_id TEXT NOT NULL,
  proposal_id TEXT NOT NULL,
  proposal_digest TEXT NOT NULL,
  command_id TEXT NOT NULL UNIQUE,
  approved_at TEXT NOT NULL,
  PRIMARY KEY(mission_id,proposal_id,proposal_digest)
);
CREATE TABLE IF NOT EXISTS operator_consumer_cursors(
  consumer_id TEXT NOT NULL,
  mission_id TEXT NOT NULL,
  event_id INTEGER NOT NULL,
  updated_at TEXT NOT NULL,
  PRIMARY KEY(consumer_id,mission_id)
);
CREATE TABLE IF NOT EXISTS operator_general_channels(
  channel_id TEXT PRIMARY KEY,
  display_name TEXT NOT NULL,
  state TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS operator_general_messages(
  sequence INTEGER PRIMARY KEY AUTOINCREMENT,
  message_id TEXT NOT NULL UNIQUE,
  channel_id TEXT NOT NULL,
  command_id TEXT NOT NULL UNIQUE,
  from_participant TEXT NOT NULL,
  to_participant TEXT NOT NULL,
  kind TEXT NOT NULL,
  content TEXT NOT NULL,
  content_digest TEXT NOT NULL,
  state TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_operator_general_messages_channel
  ON operator_general_messages(channel_id,sequence);
CREATE TABLE IF NOT EXISTS operator_general_deliveries(
  message_id TEXT NOT NULL,
  recipient TEXT NOT NULL,
  delivery_state TEXT NOT NULL,
  delivered_at TEXT,
  receipt_digest TEXT,
  PRIMARY KEY(message_id,recipient)
);
CREATE TABLE IF NOT EXISTS operator_general_message_receipts(
  message_id TEXT PRIMARY KEY,
  receipt_digest TEXT NOT NULL UNIQUE,
  receipt_json TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE TRIGGER IF NOT EXISTS operator_general_message_receipt_immutable
BEFORE UPDATE ON operator_general_message_receipts
BEGIN SELECT RAISE(ABORT,'immutable operator general message receipt'); END;
CREATE TABLE IF NOT EXISTS operator_general_delivery_receipts(
  message_id TEXT NOT NULL,
  recipient TEXT NOT NULL,
  receipt_digest TEXT NOT NULL UNIQUE,
  receipt_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  PRIMARY KEY(message_id,recipient)
);
CREATE TRIGGER IF NOT EXISTS operator_general_delivery_receipt_immutable
BEFORE UPDATE ON operator_general_delivery_receipts
BEGIN SELECT RAISE(ABORT,'immutable operator general delivery receipt'); END;
CREATE TABLE IF NOT EXISTS operator_schema_migrations(
  version INTEGER PRIMARY KEY,
  schema_id TEXT NOT NULL,
  applied_at TEXT NOT NULL
);
"""


def _tables(conn) -> set[str]:
    return {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}


def migrate(conn, now_fn) -> None:
    conn.executescript(DDL)
    grant_cols={r[1] for r in conn.execute("PRAGMA table_info(operator_grants)")}
    if "expires_at" not in grant_cols:conn.execute("ALTER TABLE operator_grants ADD COLUMN expires_at TEXT")
    message_cols={r[1] for r in conn.execute("PRAGMA table_info(operator_messages)")}
    if "correlation_id" not in message_cols:conn.execute("ALTER TABLE operator_messages ADD COLUMN correlation_id TEXT")
    if "causation_id" not in message_cols:conn.execute("ALTER TABLE operator_messages ADD COLUMN causation_id TEXT")
    if "fanout_id" not in message_cols:conn.execute("ALTER TABLE operator_messages ADD COLUMN fanout_id TEXT")
    if "recipient_set_digest" not in message_cols:conn.execute("ALTER TABLE operator_messages ADD COLUMN recipient_set_digest TEXT")
    stamp = now_fn()
    conn.execute("INSERT OR IGNORE INTO operator_general_channels(channel_id,display_name,state,created_at,updated_at) VALUES(?,?,?,?,?)",(GENERAL_CHANNEL_ID,"SentinelX general operator channel","ACTIVE",stamp,stamp))
    conn.execute("INSERT OR IGNORE INTO operator_schema_migrations(version,schema_id,applied_at) VALUES(?,?,?)",(SCHEMA_VERSION,SCHEMA_ID,stamp))
    conn.commit()


def ensure_primary_operator(conn, now_fn, *, mission_scope="*") -> dict[str, Any]:
    stamp=now_fn();conn.execute("INSERT OR IGNORE INTO operator_participants VALUES(?,?,?,?,?,?,?)",(PRIMARY_PARTICIPANT,PRIMARY_OPERATOR,"HUMAN","Primary operator","ACTIVE",stamp,stamp))
    row=conn.execute("SELECT * FROM operator_grants WHERE principal_id=? AND mission_scope=? AND revoked_at IS NULL AND (expires_at IS NULL OR expires_at>?) ORDER BY issued_at DESC LIMIT 1",(PRIMARY_OPERATOR,mission_scope,stamp)).fetchone()
    if row is None:conn.execute("INSERT INTO operator_grants(grant_id,principal_id,mission_scope,actions_json,issued_at,expires_at,revoked_at) VALUES(?,?,?,?,?,NULL,NULL)",("operator-grant-"+uuid.uuid4().hex,PRIMARY_OPERATOR,mission_scope,canonical(sorted(ACTIONS)),stamp))
    conn.commit();return participant_snapshot(conn,PRIMARY_OPERATOR)


def ensure_panel_proxy(conn,now_fn)->dict[str,Any]:
    stamp=now_fn();conn.execute("INSERT OR IGNORE INTO operator_participants VALUES(?,?,?,?,?,?,?)",(PANEL_PROXY_PARTICIPANT,PANEL_PROXY_PRINCIPAL,"TRANSPORT_PROXY","8780 browser-session proxy","ACTIVE",stamp,stamp));conn.commit();return participant_snapshot(conn,PANEL_PROXY_PRINCIPAL)


def ensure_operator_proxy(conn,now_fn,*,mission_scope="*",actions=None,expires_at=None)->dict[str,Any]:
    stamp=now_fn();allowed=sorted(set(actions or DEFAULT_PROXY_ACTIONS))
    if expires_at is not None and (not isinstance(expires_at,str) or expires_at<=stamp):raise ValueError("proxy grant expiry")
    if not set(allowed).issubset(ACTIONS):raise ValueError("proxy actions")
    conn.execute("INSERT OR IGNORE INTO operator_participants VALUES(?,?,?,?,?,?,?)",(SENTINELX_PROXY_PARTICIPANT,SENTINELX_PROXY_PRINCIPAL,"TRANSPORT_PROXY","SentinelX operator proxy","ACTIVE",stamp,stamp))
    row=conn.execute("SELECT * FROM operator_grants WHERE principal_id=? AND mission_scope=? AND revoked_at IS NULL AND (expires_at IS NULL OR expires_at>?) ORDER BY issued_at DESC LIMIT 1",(SENTINELX_PROXY_PRINCIPAL,mission_scope,stamp)).fetchone()
    if row is None:conn.execute("INSERT INTO operator_grants(grant_id,principal_id,mission_scope,actions_json,issued_at,expires_at,revoked_at) VALUES(?,?,?,?,?,?,NULL)",("operator-grant-"+uuid.uuid4().hex,SENTINELX_PROXY_PRINCIPAL,mission_scope,canonical(allowed),stamp,expires_at))
    conn.commit();return participant_snapshot(conn,SENTINELX_PROXY_PRINCIPAL)


def revoke_active_grants(conn,principal_id:str,now_fn,*,mission_scope=None)->int:
    stamp=now_fn();n=conn.execute("UPDATE operator_grants SET revoked_at=? WHERE principal_id=? AND revoked_at IS NULL",(stamp,principal_id)).rowcount if mission_scope is None else conn.execute("UPDATE operator_grants SET revoked_at=? WHERE principal_id=? AND mission_scope=? AND revoked_at IS NULL",(stamp,principal_id,mission_scope)).rowcount;conn.commit();return int(n)


def _participant_for_principal(conn,principal_id:str)->dict[str,Any]:
    row=conn.execute("SELECT * FROM operator_participants WHERE principal_id=? AND state='ACTIVE'",(principal_id,)).fetchone()
    if row is None:raise ValueError("operator principal unavailable")
    return dict(row)


def participant_snapshot(conn,principal_id:str=PRIMARY_OPERATOR)->dict[str,Any]:
    participant=conn.execute("SELECT * FROM operator_participants WHERE principal_id=?",(principal_id,)).fetchone();grants=conn.execute("SELECT * FROM operator_grants WHERE principal_id=? ORDER BY issued_at",(principal_id,)).fetchall();return {"participant":dict(participant) if participant else None,"grants":[dict(g) for g in grants],"authority_effect":"NONE"}


def _general_channel_participant(conn,principal_id:str)->dict[str,Any]:
    if principal_id not in {PRIMARY_OPERATOR,SENTINELX_PROXY_PRINCIPAL}:raise ValueError("general channel principal denied")
    return _participant_for_principal(conn,principal_id)


def _general_channel_grant(conn,principal_id:str,now_value:str)->dict[str,Any]:
    _general_channel_participant(conn,principal_id)
    for row in conn.execute("SELECT * FROM operator_grants WHERE principal_id=? AND mission_scope='*' AND revoked_at IS NULL AND (expires_at IS NULL OR expires_at>?) ORDER BY issued_at DESC",(principal_id,now_value)).fetchall():
        value=dict(row)
        try:actions=set(json.loads(value["actions_json"]))
        except Exception:actions=set()
        if actions.intersection({"MESSAGE","REQUEST_STATUS"}):return value
    raise ValueError("general channel not granted")


def _general_channel_peer(participant_id:str)->str:
    if participant_id==PRIMARY_PARTICIPANT:return SENTINELX_PROXY_PARTICIPANT
    if participant_id==SENTINELX_PROXY_PARTICIPANT:return PRIMARY_PARTICIPANT
    raise ValueError("general channel participant denied")


def _general_protocol_envelope(row:dict[str,Any],delivery_state:str|None=None)->dict[str,Any]:
    payload={"event":str(row.get("kind") or "MESSAGE"),"text":str(row.get("content") or "")}
    return {"id":row.get("message_id"),"sequence":int(row.get("sequence") or 0),"observed_at":row.get("created_at"),"protocol":"OPERATOR","from_id":row.get("from_participant"),"to_id":row.get("to_participant"),"phase":None,"direction":"INTERNAL","payload":payload,"payload_digest":digest(payload),"delivery_state":delivery_state or row.get("state") or "PERSISTED"}


def post_general_message(conn,principal_id:str,command_id:str,content:str,now_fn)->dict[str,Any]:
    if not isinstance(command_id,str) or not command_id.strip() or len(command_id)>200:raise ValueError("general channel command_id")
    if not isinstance(content,str) or not content.strip() or len(content)>16000:raise ValueError("general channel content")
    stamp=now_fn();grant=_general_channel_grant(conn,principal_id,stamp);participant=_general_channel_participant(conn,principal_id);sender=participant["participant_id"];recipient=_general_channel_peer(sender);command_id=command_id.strip();content=content.strip();content_digest=digest(content)
    existing=conn.execute("SELECT * FROM operator_general_messages WHERE command_id=?",(command_id,)).fetchone()
    if existing is not None:
        row=dict(existing)
        if row["from_participant"]!=sender or row["content_digest"]!=content_digest:raise ValueError("general channel command_id payload conflict")
        drow=conn.execute("SELECT delivery_state FROM operator_general_deliveries WHERE message_id=? AND recipient=?",(row["message_id"],row["to_participant"])).fetchone()
        receipt=conn.execute("SELECT receipt_digest FROM operator_general_message_receipts WHERE message_id=?",(row["message_id"],)).fetchone()
        return {"schema":"lion.protocol-message-ack/v1","channel_id":GENERAL_CHANNEL_ID,"message":_general_protocol_envelope(row,(drow["delivery_state"] if drow else None)),"receipt_digest":(receipt["receipt_digest"] if receipt else None),"idempotent":True,"authority_effect":"NONE"}
    conn.execute("BEGIN IMMEDIATE")
    try:
        message_id="opgen-"+digest({"principal_id":principal_id,"command_id":command_id})[:32]
        conn.execute("INSERT INTO operator_general_messages(message_id,channel_id,command_id,from_participant,to_participant,kind,content,content_digest,state,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)",(message_id,GENERAL_CHANNEL_ID,command_id,sender,recipient,"MESSAGE",content,content_digest,"PERSISTED",stamp))
        conn.execute("INSERT INTO operator_general_deliveries(message_id,recipient,delivery_state,delivered_at,receipt_digest) VALUES(?,?,?,NULL,NULL)",(message_id,recipient,"PERSISTED"))
        sequence=int(conn.execute("SELECT sequence FROM operator_general_messages WHERE message_id=?",(message_id,)).fetchone()[0])
        receipt={"schema":"lion.operator-general-message-receipt/v1","channel_id":GENERAL_CHANNEL_ID,"sequence":sequence,"message_id":message_id,"command_id":command_id,"from_participant":sender,"to_participant":recipient,"content_digest":content_digest,"delivery_state":"PERSISTED","grant_id":grant["grant_id"],"authority_effect":"NONE","created_at":stamp}
        receipt_digest=digest(receipt);receipt["receipt_digest"]=receipt_digest
        conn.execute("INSERT INTO operator_general_message_receipts(message_id,receipt_digest,receipt_json,created_at) VALUES(?,?,?,?)",(message_id,receipt_digest,canonical(receipt),stamp))
        conn.execute("UPDATE operator_general_channels SET updated_at=? WHERE channel_id=?",(stamp,GENERAL_CHANNEL_ID));conn.commit()
        row=dict(conn.execute("SELECT * FROM operator_general_messages WHERE message_id=?",(message_id,)).fetchone())
        return {"schema":"lion.protocol-message-ack/v1","channel_id":GENERAL_CHANNEL_ID,"message":_general_protocol_envelope(row,"PERSISTED"),"receipt_digest":receipt_digest,"idempotent":False,"authority_effect":"NONE"}
    except Exception:
        conn.rollback();raise


def general_channel_snapshot(conn,principal_id:str,now_fn,*,after=0,limit=200)->dict[str,Any]:
    if type(after) is not int or after<0 or type(limit) is not int or not 1<=limit<=500:raise ValueError("general channel cursor")
    stamp=now_fn();_general_channel_grant(conn,principal_id,stamp);participant=_general_channel_participant(conn,principal_id);participant_id=participant["participant_id"]
    rows=conn.execute("SELECT * FROM operator_general_messages WHERE channel_id=? AND sequence>? ORDER BY sequence LIMIT ?",(GENERAL_CHANNEL_ID,after,limit)).fetchall();messages=[];delivered=0
    for raw in rows:
        row=dict(raw);delivery=conn.execute("SELECT * FROM operator_general_deliveries WHERE message_id=? AND recipient=?",(row["message_id"],participant_id)).fetchone()
        if delivery is not None and delivery["delivery_state"]=="PERSISTED":
            receipt={"schema":"lion.operator-general-delivery-receipt/v1","channel_id":GENERAL_CHANNEL_ID,"sequence":row["sequence"],"message_id":row["message_id"],"recipient":participant_id,"content_digest":row["content_digest"],"delivery_state":"DELIVERED","authority_effect":"NONE","created_at":stamp}
            receipt_digest=digest(receipt);receipt["receipt_digest"]=receipt_digest
            conn.execute("INSERT OR IGNORE INTO operator_general_delivery_receipts(message_id,recipient,receipt_digest,receipt_json,created_at) VALUES(?,?,?,?,?)",(row["message_id"],participant_id,receipt_digest,canonical(receipt),stamp))
            stored=conn.execute("SELECT receipt_digest FROM operator_general_delivery_receipts WHERE message_id=? AND recipient=?",(row["message_id"],participant_id)).fetchone()[0]
            conn.execute("UPDATE operator_general_deliveries SET delivery_state='DELIVERED',delivered_at=COALESCE(delivered_at,?),receipt_digest=? WHERE message_id=? AND recipient=? AND delivery_state='PERSISTED'",(stamp,stored,row["message_id"],participant_id));delivered+=1
        drow=conn.execute("SELECT delivery_state FROM operator_general_deliveries WHERE message_id=? AND recipient=?",(row["message_id"],row["to_participant"])).fetchone()
        messages.append(_general_protocol_envelope(row,(drow["delivery_state"] if drow else None)))
    if delivered:conn.commit()
    channel=conn.execute("SELECT state FROM operator_general_channels WHERE channel_id=?",(GENERAL_CHANNEL_ID,)).fetchone()
    return {"schema":"lion.protocol-stream/v1","channel_id":GENERAL_CHANNEL_ID,"state":(channel["state"] if channel else "UNKNOWN"),"participant_id":participant_id,"protocol":"OPERATOR","messages":messages,"delivered_now":delivered,"next_cursor":messages[-1]["sequence"] if messages else after,"authority_effect":"NONE"}


def _mission_exists(conn,mission_id:str)->bool:return "missions" in _tables(conn) and conn.execute("SELECT 1 FROM missions WHERE mission_id=?",(mission_id,)).fetchone() is not None

TERMINAL_MISSION_STATES=frozenset({"COMPLETE","COMPLETED","SUPERSEDED","CANCELLED"})
def mission_terminal_state(conn,mission_id:str)->str|None:
    if "missions" not in _tables(conn):return None
    row=conn.execute("SELECT state FROM missions WHERE mission_id=?",(mission_id,)).fetchone()
    if row is None:return None
    state=str(row["state"] or "UNKNOWN").upper();return state if state in TERMINAL_MISSION_STATES or state.startswith("RECORDED_") else None

def _plan_scope_extension(payload:dict[str,Any])->dict[str,Any]|None:
    explicit=payload.get("scope_change")
    if isinstance(explicit,dict) and explicit:return explicit
    content=payload.get("content")
    if isinstance(content,dict):
        keys=("effect_ceiling","authority_scope","capability_grants","external_effects","scope_extension");found={k:content[k] for k in keys if k in content}
        if found:return found
    return None


def ensure_control_state(conn,mission_id:str,now_fn)->dict[str,Any]:
    if not _mission_exists(conn,mission_id):raise ValueError("mission not found")
    row=conn.execute("SELECT * FROM mission_operator_control WHERE mission_id=?",(mission_id,)).fetchone()
    if row is None:
        stamp=now_fn();conn.execute("INSERT INTO mission_operator_control VALUES(?,?,?,?,?,?,?,?,?,?)",(mission_id,"incarnation-"+uuid.uuid4().hex,1,AUTONOMOUS_OWNER,0,0,0,0,None,stamp));row=conn.execute("SELECT * FROM mission_operator_control WHERE mission_id=?",(mission_id,)).fetchone()
    return dict(row)

def _legacy_default_state(mission_id:str)->dict[str,Any]:return {"mission_id":mission_id,"incarnation_id":"LEGACY_UNMIGRATED","control_epoch":0,"control_owner":AUTONOMOUS_OWNER,"pause_latch":0,"stop_latch":0,"context_revision":0,"plan_revision":0,"last_command_id":None,"updated_at":None}
def control_state(conn,mission_id:str,now_fn=None)->dict[str,Any]|None:
    if "mission_operator_control" not in _tables(conn):return _legacy_default_state(mission_id) if now_fn is not None else None
    row=conn.execute("SELECT * FROM mission_operator_control WHERE mission_id=?",(mission_id,)).fetchone()
    if row is None and now_fn is not None:
        if _mission_exists(conn,mission_id):
            was=conn.in_transaction;value=ensure_control_state(conn,mission_id,now_fn)
            if not was and conn.in_transaction:conn.commit()
            return value
        return _legacy_default_state(mission_id)
    return dict(row) if row else None


def _grant_for(conn,principal_id:str,mission_id:str,action:str,now_value:str)->dict[str,Any]:
    if conn.execute("SELECT * FROM operator_participants WHERE principal_id=? AND state='ACTIVE'",(principal_id,)).fetchone() is None:raise ValueError("operator principal unavailable")
    for row in conn.execute("SELECT * FROM operator_grants WHERE principal_id=? AND revoked_at IS NULL AND (expires_at IS NULL OR expires_at>?) ORDER BY issued_at DESC",(principal_id,now_value)).fetchall():
        value=dict(row)
        if value["mission_scope"] not in {"*",mission_id}:continue
        try:actions=set(json.loads(value["actions_json"]))
        except Exception:actions=set()
        if action in actions:return value
    raise ValueError("operator action not granted")

def _event(conn,mission_id,event_type,payload,now_fn,*,command_id=None):
    raw=canonical(payload);cur=conn.execute("INSERT INTO operator_events(mission_id,command_id,event_type,payload_json,payload_digest,observed_at) VALUES(?,?,?,?,?,?)",(mission_id,command_id,event_type,raw,digest(payload),now_fn()));return int(cur.lastrowid)
def _driver_row(conn,mission_id):return None if "mission_execution_drivers" not in _tables(conn) else conn.execute("SELECT * FROM mission_execution_drivers WHERE mission_id=?",(mission_id,)).fetchone()

def _driver_fence(conn,mission_id,now_fn,*,state,reason):
    row=_driver_row(conn,mission_id)
    if row is None:return None
    old=dict(row);stamp=now_fn();generation=int(old.get("generation") or 0)+1;new_state=state or old.get("state") or "BOOTSTRAP_PAUSED";token=secrets.token_hex(16);conn.execute("UPDATE mission_execution_drivers SET generation=?,state=?,lease_token=?,lease_owner=NULL,lease_expires_at=NULL,current_attempt_id=NULL,waiting_reason=?,blocking_gate=?,next_action=?,updated_at=? WHERE mission_id=?",(generation,new_state,token,reason,"OPERATOR_CONTROL","OPERATOR_DECISION_REQUIRED",stamp,mission_id))
    if "mission_execution_checkpoints" in _tables(conn):
        cursor={"state":new_state,"event":"OPERATOR_FENCE","reason":reason,"previous_generation":old.get("generation"),"generation":generation,"current_phase":old.get("current_phase")};raw=canonical(cursor);dg=digest(cursor);checkpoint_id="checkpoint-"+uuid.uuid4().hex;conn.execute("INSERT INTO mission_execution_checkpoints(checkpoint_id,mission_id,driver_generation,phase_id,attempt_id,state,cursor_json,cursor_digest,created_at) VALUES(?,?,?,?,?,?,?,?,?)",(checkpoint_id,mission_id,generation,old.get("current_phase"),old.get("current_attempt_id"),new_state,raw,dg,stamp));conn.execute("UPDATE mission_execution_drivers SET checkpoint_digest=? WHERE mission_id=?",(dg,mission_id))
    return {"previous_generation":old.get("generation"),"generation":generation,"state":new_state}

def _fence_assignments(conn,mission_id,now_fn):
    if "mission_execution_assignments" not in _tables(conn):return {"cancelled_ready":0,"cancel_requested":0}
    stamp=now_fn();ready=conn.execute("UPDATE mission_execution_assignments SET state='CANCELLED',finished_at=? WHERE mission_id=? AND state='READY'",(stamp,mission_id)).rowcount;claimed=conn.execute("UPDATE mission_execution_assignments SET state='CANCEL_REQUESTED' WHERE mission_id=? AND state='CLAIMED'",(mission_id,)).rowcount;return {"cancelled_ready":int(ready),"cancel_requested":int(claimed)}

def rebind_ready_assignments(conn,mission_id,now_fn,*,authority_owner=AUTONOMOUS_OWNER,generation=None):
    if "mission_execution_assignments" not in _tables(conn):return {"rebound_ready":0}
    state=ensure_control_state(conn,mission_id,now_fn);cols={r[1] for r in conn.execute("PRAGMA table_info(mission_execution_assignments)")}
    if generation is None:
        driver=_driver_row(conn,mission_id);generation=int(driver["generation"]) if driver and "generation" in driver.keys() else None
    if generation is None:return {"rebound_ready":0}
    has_epoch="control_epoch" in cols;has_authority="dispatch_authority" in cols
    if has_epoch and has_authority:
        cur=conn.execute("UPDATE mission_execution_assignments SET lease_generation=?,control_epoch=?,dispatch_authority=? WHERE mission_id=? AND state='READY'",(int(generation),int(state["control_epoch"]),authority_owner,mission_id))
    elif has_epoch:
        cur=conn.execute("UPDATE mission_execution_assignments SET lease_generation=?,control_epoch=? WHERE mission_id=? AND state='READY'",(int(generation),int(state["control_epoch"]),mission_id))
    elif has_authority:
        cur=conn.execute("UPDATE mission_execution_assignments SET lease_generation=?,dispatch_authority=? WHERE mission_id=? AND state='READY'",(int(generation),authority_owner,mission_id))
    else:
        cur=conn.execute("UPDATE mission_execution_assignments SET lease_generation=? WHERE mission_id=? AND state='READY'",(int(generation),mission_id))
    return {"rebound_ready":int(cur.rowcount)}

def _release_assignment_handoff(conn,mission_id,now_fn,*,principal_id,generation,control_epoch):
    if "mission_execution_assignments" not in _tables(conn):return {"rebound_ready":0,"cancelled_ready":0,"cancel_requested":0}
    cols={r[1] for r in conn.execute("PRAGMA table_info(mission_execution_assignments)")};rebound=0;cancelled=0
    if "dispatch_authority" in cols and "control_epoch" in cols:
        cancelled=conn.execute("UPDATE mission_execution_assignments SET state='CANCELLED',finished_at=? WHERE mission_id=? AND state='READY' AND (dispatch_authority IS NULL OR dispatch_authority<>?)",(now_fn(),mission_id,principal_id)).rowcount;rebound=conn.execute("UPDATE mission_execution_assignments SET lease_generation=?,control_epoch=?,dispatch_authority=? WHERE mission_id=? AND state='READY' AND dispatch_authority=?",(int(generation),int(control_epoch),AUTONOMOUS_OWNER,mission_id,principal_id)).rowcount
    else:cancelled=conn.execute("UPDATE mission_execution_assignments SET state='CANCELLED',finished_at=? WHERE mission_id=? AND state='READY'",(now_fn(),mission_id)).rowcount
    claimed=conn.execute("UPDATE mission_execution_assignments SET state='CANCEL_REQUESTED' WHERE mission_id=? AND state='CLAIMED'",(mission_id,)).rowcount;return {"rebound_ready":int(rebound),"cancelled_ready":int(cancelled),"cancel_requested":int(claimed)}

def _bump_control(conn,mission_id,now_fn,*,owner=None,pause=None,stop=None,last_command_id=None):
    state=ensure_control_state(conn,mission_id,now_fn);values={"control_epoch":int(state["control_epoch"])+1,"control_owner":owner if owner is not None else state["control_owner"],"pause_latch":int(bool(pause)) if pause is not None else int(state["pause_latch"]),"stop_latch":int(bool(stop)) if stop is not None else int(state["stop_latch"]),"last_command_id":last_command_id or state.get("last_command_id"),"updated_at":now_fn()};conn.execute("UPDATE mission_operator_control SET control_epoch=?,control_owner=?,pause_latch=?,stop_latch=?,last_command_id=?,updated_at=? WHERE mission_id=?",(values["control_epoch"],values["control_owner"],values["pause_latch"],values["stop_latch"],values["last_command_id"],values["updated_at"],mission_id));return dict(conn.execute("SELECT * FROM mission_operator_control WHERE mission_id=?",(mission_id,)).fetchone())

def autonomy_allowed(conn,mission_id):
    if "mission_operator_control" not in _tables(conn):return True
    row=conn.execute("SELECT control_owner,pause_latch,stop_latch FROM mission_operator_control WHERE mission_id=?",(mission_id,)).fetchone();return True if row is None else row["control_owner"]==AUTONOMOUS_OWNER and not bool(row["pause_latch"]) and not bool(row["stop_latch"])
def assignment_allowed(conn,mission_id,authority_owner,control_epoch):
    if "mission_operator_control" not in _tables(conn):return authority_owner==AUTONOMOUS_OWNER and int(control_epoch)==0
    row=conn.execute("SELECT * FROM mission_operator_control WHERE mission_id=?",(mission_id,)).fetchone()
    if row is None:return authority_owner==AUTONOMOUS_OWNER
    if int(control_epoch)!=int(row["control_epoch"]) or bool(row["pause_latch"]) or bool(row["stop_latch"]):return False
    return row["control_owner"]==PRIMARY_OPERATOR if authority_owner==PRIMARY_OPERATOR else authority_owner==AUTONOMOUS_OWNER and row["control_owner"]==AUTONOMOUS_OWNER
def is_capability_revoked(conn,mission_id,capability):return False if "operator_capability_revocations" not in _tables(conn) else conn.execute("SELECT 1 FROM operator_capability_revocations WHERE mission_id=? AND capability=? AND released_at IS NULL LIMIT 1",(mission_id,capability)).fetchone() is not None


def _mission_drone_inventory(conn,mission_id):
    """Canonical protocol participants keyed by stable participant identity."""
    out={};tables=_tables(conn)
    if 'logical_drones' in tables:
        for row in conn.execute('SELECT logical_id,role FROM logical_drones WHERE mission_id=?',(mission_id,)):
            ident=str(row['logical_id'])
            if ident:out['drone:'+ident]={'recipient':'drone:'+ident,'kind':'LOGICAL_DRONE','role':str(row['role'] or '')}
    if 'material_workers' in tables:
        cols={r['name'] for r in conn.execute('PRAGMA table_info(material_workers)')}
        if 'ready' in cols:
            material_rows=conn.execute('SELECT pod_name,logical_id,ready FROM material_workers WHERE mission_id=?',(mission_id,))
        else:
            material_rows=conn.execute('SELECT pod_name,logical_id FROM material_workers WHERE mission_id=?',(mission_id,))
        for row in material_rows:
            logical_field=str(row['logical_id'] or '')
            pod=str(row['pod_name'] or '')
            # The material-worker registry carries the canonical MD identity.
            # Legacy rows that expose only an LD mapping are not promoted into a
            # worker identity; execution assignments are bindings, not a
            # participant registry.
            ident=logical_field if logical_field.upper().startswith('MD') else (pod if pod.upper().startswith('MD') else '')
            if not ident:continue
            if 'ready' in cols and not bool(row['ready']):continue
            out['worker:'+ident]={'recipient':'worker:'+ident,'kind':'MATERIAL_WORKER','role':'MATERIAL_EXECUTOR','pod_name':pod}
    return out

def resolve_target(conn,mission_id,target):
    if not _mission_exists(conn,mission_id):raise ValueError('mission not found')
    if not isinstance(target,str) or ':' not in target:raise ValueError('unresolved target')
    prefix,ident=target.split(':',1);inv=_mission_drone_inventory(conn,mission_id)
    if prefix in {'mission','swarm'}:
        if ident!=mission_id:raise ValueError('target mission mismatch' if prefix=='mission' else 'unresolved swarm target')
        return sorted(inv)
    if prefix=='drone':
        direct='drone:'+ident
        if direct in inv:return [direct]
        raise ValueError('unresolved drone target')
    if prefix=='worker':
        direct='worker:'+ident
        if direct not in inv:raise ValueError('unresolved worker target')
        return [direct]
    if prefix=='operator':
        row=conn.execute("SELECT participant_id FROM operator_participants WHERE participant_id=? AND state='ACTIVE'",('operator:'+ident,)).fetchone()
        if row is None:raise ValueError('unresolved operator target')
        return [target]
    if prefix=='group':
        if ident not in {'architecture','security','runtime'}:raise ValueError('unresolved group target')
        values=[]
        for item in inv.values():
            role=item['role'].upper()
            if ident=='runtime' or (ident=='security' and 'SECUR' in role) or (ident=='architecture' and any(x in role for x in ('ARCH','PLANNER','CONTROL'))):values.append(item['recipient'])
        return sorted(set(values))
    raise ValueError('unresolved target')

def _message_target_matches(target,mission_id,material_drone_id,logical_drone_id):
    if target in {'mission:'+mission_id,'swarm:'+mission_id}:return True
    if target.startswith('worker:'):return target.split(':',1)[1]==str(material_drone_id or '')
    if target.startswith('drone:'):
        ident=target.split(':',1)[1]
        return ident==str(logical_drone_id or '')
    return False

def assignment_context(conn,mission_id,material_drone_id,logical_drone_id):
    state=conn.execute("SELECT * FROM mission_operator_control WHERE mission_id=?",(mission_id,)).fetchone()
    if state is None:return {"control":None,"context":None,"plan":None,"messages":[]}
    context=conn.execute("SELECT * FROM mission_context_revisions WHERE mission_id=? ORDER BY revision DESC LIMIT 1",(mission_id,)).fetchone();plan=conn.execute("SELECT * FROM mission_plan_revisions WHERE mission_id=? ORDER BY revision DESC LIMIT 1",(mission_id,)).fetchone();messages=[]
    for row in conn.execute("SELECT * FROM operator_messages WHERE mission_id=? AND state IN ('PENDING','PARTIAL') ORDER BY created_at,message_id",(mission_id,)):
        value=dict(row);direct=_message_target_matches(value["target"],mission_id,material_drone_id,logical_drone_id);delivered=conn.execute("SELECT 1 FROM operator_message_deliveries WHERE message_id=? AND recipient IN (?,?,?) AND delivery_state NOT IN ('APPLIED','FAILED','CANCELLED') LIMIT 1",(value['message_id'],'worker:'+str(material_drone_id or ''),'drone:'+str(logical_drone_id or ''),'drone:'+str(material_drone_id or ''))).fetchone()
        if direct or delivered:messages.append(value)
    return {"control":dict(state),"context":dict(context) if context else None,"plan":dict(plan) if plan else None,"messages":messages[:64]}

def note_assignment_application(conn,assignment_id,result,now_fn):
    if "mission_execution_assignments" not in _tables(conn):return {"applied_messages":0,"partial_messages":0}
    row=conn.execute("SELECT mission_id,logical_drone_id,material_drone_id,input_json FROM mission_execution_assignments WHERE assignment_id=?",(assignment_id,)).fetchone()
    if row is None:raise ValueError("assignment missing")
    try:assignment_input=json.loads(row['input_json'] or '{}')
    except Exception:assignment_input={}
    ids=result.get("operator_message_ids") or []
    if not isinstance(ids,list) or any(not isinstance(x,str) for x in ids):ids=[]
    participant=result.get('responding_participant_id') or assignment_input.get('responding_participant_id')
    if participant is None:
        if assignment_input.get('purpose')=='PROTOCOL_FANOUT_R1':raise ValueError('protocol fanout responding participant missing')
        participant='worker:'+str(row['material_drone_id']) if row['material_drone_id'] else 'drone:'+str(row['logical_drone_id'])
    if not isinstance(participant,str) or not (participant.startswith('drone:') or participant.startswith('worker:')):
        raise ValueError('responding participant identity')
    protocol_fanout=assignment_input.get('purpose')=='PROTOCOL_FANOUT_R1'
    if protocol_fanout:
        expected_participant=assignment_input.get('responding_participant_id')
        if not isinstance(expected_participant,str) or participant!=expected_participant:
            raise ValueError('protocol fanout participant identity mismatch')
    cognition_route=str(assignment_input.get('cognition_route') or 'LOCAL').upper()
    stamp=now_fn();applied=0;partial=0;responses=[]
    if protocol_fanout and cognition_route=='DUAL':
        for message_id in ids[:64]:
            protocol_trajectory_update(conn,message_id,participant,now_fn,
                state='DUAL_LOCAL_RESPONSE_READY',
                local_assignment_id=assignment_id,
                local_model_call_id=result.get('model_call_id'),
                result_digest=result.get('response_digest'))
        return {"responding_participant_id":participant,"applied_messages":0,"partial_messages":0,"response_message_ids":[],"dual_local_leg_recorded":True}
    for message_id in ids[:64]:
        if protocol_fanout:
            response_text=result.get('response_text')
            if isinstance(response_text,str) and response_text.strip():
                protocol_trajectory_update(conn,message_id,participant,now_fn,
                    local_assignment_id=assignment_id,
                    local_model_call_id=result.get('model_call_id'),
                    state='LOCAL_RESPONSE_READY',
                    result_digest=result.get('response_digest'))
                recorded=record_protocol_model_response(conn,message_id,participant,response_text,now_fn,
                    result_digest=result.get('response_digest'),model_call_id=result.get('model_call_id'))
                responses.append(recorded['response_message_id'])
                applied+=1 if recorded['state']=='APPLIED' else 0
                partial+=1 if recorded['state']=='PARTIAL' else 0
            continue
        matched=conn.execute("UPDATE operator_message_deliveries SET delivery_state='APPLIED',delivered_at=COALESCE(delivered_at,?),applied_at=?,applied_assignment_id=? WHERE message_id=? AND recipient=? AND delivery_state!='APPLIED'",(stamp,stamp,assignment_id,message_id,participant)).rowcount
        counts=conn.execute("SELECT COUNT(*) total,SUM(CASE WHEN delivery_state='APPLIED' THEN 1 ELSE 0 END) applied FROM operator_message_deliveries WHERE message_id=?",(message_id,)).fetchone()
        if counts and int(counts['total'] or 0)>0:
            total=int(counts['total']);done=int(counts['applied'] or 0);state='APPLIED' if done==total else 'PARTIAL'
            conn.execute("UPDATE operator_messages SET state=?,applied_at=CASE WHEN ?='APPLIED' THEN ? ELSE applied_at END,applied_assignment_id=CASE WHEN ?='APPLIED' THEN ? ELSE applied_assignment_id END WHERE message_id=?",(state,state,stamp,state,assignment_id,message_id))
            applied+=1 if state=='APPLIED' else 0;partial+=1 if state=='PARTIAL' else 0
        response_text=result.get('response_text')
        if matched and isinstance(response_text,str) and response_text.strip():
            reply_id='opreply-'+digest({'assignment_id':assignment_id,'message_id':message_id,'participant':participant,'response':response_text})[:32]
            original=conn.execute('SELECT context_revision,plan_revision,correlation_id FROM operator_messages WHERE message_id=?',(message_id,)).fetchone()
            conn.execute("INSERT OR IGNORE INTO operator_messages(message_id,mission_id,command_id,from_participant,target,kind,content,content_digest,context_revision,plan_revision,state,created_at,applied_at,applied_assignment_id,correlation_id,causation_id,fanout_id,recipient_set_digest) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(reply_id,row['mission_id'],'assignment:'+assignment_id,participant,PRIMARY_PARTICIPANT,'RESPONSE',response_text.strip(),digest(response_text.strip()),int(original['context_revision'] if original else 0),int(original['plan_revision'] if original else 0),'DELIVERED',stamp,stamp,assignment_id,original['correlation_id'] if original else None,message_id,None,None));responses.append(reply_id)
    if applied or partial:_event(conn,row['mission_id'],'OPERATOR_MESSAGE_APPLIED',{'assignment_id':assignment_id,'responding_participant_id':participant,'message_ids':ids[:64],'applied_messages':applied,'partial_messages':partial,'response_message_ids':responses},now_fn)
    return {"responding_participant_id":participant,"applied_messages":applied,"partial_messages":partial,"response_message_ids":responses}

_PROTOCOL_COGNITION_ROUTES=frozenset({'LOCAL','SAAS','DUAL','DETERMINISTIC_ONLY'})

def _protocol_recipient_routes(payload,recipients):
    spec=payload.get('cognition_routes') if isinstance(payload,dict) else None
    if spec is None:spec={}
    if type(spec) is not dict or set(spec)-{'default','participants'}:raise ValueError('cognition_routes')
    configured_default=spec.get('default')
    if configured_default is not None:
        configured_default=str(configured_default).upper()
        if configured_default not in _PROTOCOL_COGNITION_ROUTES:raise ValueError('default cognition route')
    mapping=spec.get('participants') or {}
    if type(mapping) is not dict:raise ValueError('participant cognition routes')
    if set(mapping)-set(recipients):raise ValueError('cognition route recipient outside frozen target')
    out={}
    for recipient in recipients:
        fallback='LOCAL' if recipient.startswith('worker:') else 'SAAS'
        route=str(mapping.get(recipient) or configured_default or fallback).upper()
        if route not in _PROTOCOL_COGNITION_ROUTES:raise ValueError('participant cognition route')
        if recipient.startswith('worker:') and route!='LOCAL':raise ValueError('material worker cognition route must be LOCAL')
        if recipient.startswith('drone:') and route not in {'LOCAL','SAAS','DUAL'}:raise ValueError('logical drone cognition route')
        out[recipient]=route
    return out

def _store_message(conn,cmd,state,now_fn,*,kind,participant_id):
    content=cmd.payload.get("content")
    if not isinstance(content,str) or not content.strip() or len(content)>16000:raise ValueError("message content")
    content=content.strip();message_id="opmsg-"+digest({"command_id":cmd.command_id,"target":cmd.target})[:32]
    recipients=resolve_target(conn,cmd.mission_id,cmd.target)
    recipient_routes=_protocol_recipient_routes(cmd.payload,recipients) if kind=="MESSAGE" else {r:"DETERMINISTIC_ONLY" for r in recipients}
    recipient_set_digest=digest(sorted(recipients));fanout_id='fanout-'+digest({'message_id':message_id,'recipients':sorted(recipients)})[:32]
    message_state='PENDING' if recipients else 'PERSISTED_NO_CURRENT_RECIPIENT';created=now_fn()
    conn.execute("INSERT OR IGNORE INTO operator_messages(message_id,mission_id,command_id,from_participant,target,kind,content,content_digest,context_revision,plan_revision,state,created_at,applied_at,applied_assignment_id,correlation_id,causation_id,fanout_id,recipient_set_digest) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(message_id,cmd.mission_id,cmd.command_id,participant_id,cmd.target,kind,content,digest(content),int(state["context_revision"]),int(state["plan_revision"]),message_state,created,None,None,cmd.correlation_id,cmd.causation_id,fanout_id,recipient_set_digest))
    for recipient in recipients:
        conn.execute("INSERT OR IGNORE INTO operator_message_deliveries VALUES(?,?,?,NULL,NULL,NULL)",(message_id,recipient,'PERSISTED'))
        conn.execute("INSERT OR IGNORE INTO operator_protocol_recipient_routes(message_id,recipient,cognition_route) VALUES(?,?,?)",(message_id,recipient,recipient_routes[recipient]))
    return {"message_id":message_id,"target":cmd.target,"state":message_state,"recipients":recipients,"recipient_count":len(recipients),"recipient_routes":recipient_routes,"fanout_id":fanout_id,"recipient_set_digest":recipient_set_digest,"correlation_id":cmd.correlation_id,"causation_id":cmd.causation_id}


def ensure_protocol_trajectory(conn,message_id,mission_id,participant_id,cognition_route,now_fn):
    trajectory_id='trajectory-'+digest({'message_id':message_id,'participant_id':participant_id})[:32];stamp=now_fn()
    conn.execute("INSERT OR IGNORE INTO protocol_cognitive_trajectories(trajectory_id,message_id,mission_id,participant_id,cognition_route,local_assignment_id,local_model_call_id,saas_request_id,dual_request_id,state,result_digest,response_message_id,created_at,updated_at,authority_effect) VALUES(?,?,?,?,?,NULL,NULL,NULL,NULL,'INTENT_DURABLE',NULL,NULL,?,?,?)",(trajectory_id,message_id,mission_id,participant_id,cognition_route,stamp,stamp,'NONE'))
    row=conn.execute("SELECT * FROM protocol_cognitive_trajectories WHERE message_id=? AND participant_id=?",(message_id,participant_id)).fetchone()
    if row is None:raise RuntimeError('protocol trajectory persistence failed')
    if row['cognition_route']!=cognition_route:raise ValueError('protocol trajectory route conflict')
    return dict(row)

def protocol_trajectory_update(conn,message_id,participant_id,now_fn,**changes):
    allowed={'local_assignment_id','local_model_call_id','saas_request_id','dual_request_id','state','result_digest','response_message_id'}
    if set(changes)-allowed:raise ValueError('protocol trajectory update fields')
    row=conn.execute("SELECT * FROM protocol_cognitive_trajectories WHERE message_id=? AND participant_id=?",(message_id,participant_id)).fetchone()
    if row is None:raise ValueError('protocol trajectory missing')
    values=dict(row);values.update(changes);values['updated_at']=now_fn()
    conn.execute("UPDATE protocol_cognitive_trajectories SET local_assignment_id=?,local_model_call_id=?,saas_request_id=?,dual_request_id=?,state=?,result_digest=?,response_message_id=?,updated_at=? WHERE trajectory_id=?",(values['local_assignment_id'],values['local_model_call_id'],values['saas_request_id'],values['dual_request_id'],values['state'],values['result_digest'],values['response_message_id'],values['updated_at'],values['trajectory_id']))
    return dict(conn.execute("SELECT * FROM protocol_cognitive_trajectories WHERE trajectory_id=?",(values['trajectory_id'],)).fetchone())

def _reconcile_protocol_message_state(conn,message_id,stamp):
    counts=conn.execute("SELECT COUNT(*) total,SUM(CASE WHEN delivery_state='APPLIED' THEN 1 ELSE 0 END) applied,SUM(CASE WHEN delivery_state='FAILED' THEN 1 ELSE 0 END) failed,SUM(CASE WHEN delivery_state='CANCELLED' THEN 1 ELSE 0 END) cancelled FROM operator_message_deliveries WHERE message_id=?",(message_id,)).fetchone()
    total=int(counts['total'] or 0);applied=int(counts['applied'] or 0);failed=int(counts['failed'] or 0);cancelled=int(counts['cancelled'] or 0)
    terminal=applied+failed+cancelled
    state='APPLIED' if total and applied==total else 'FAILED' if total and failed==total else 'CANCELLED' if total and cancelled==total else 'PARTIAL' if terminal else 'PENDING'
    conn.execute("UPDATE operator_messages SET state=?,applied_at=CASE WHEN ?='APPLIED' THEN COALESCE(applied_at,?) ELSE applied_at END WHERE message_id=?",(state,state,stamp,message_id))
    return {'state':state,'total':total,'applied':applied,'failed':failed,'cancelled':cancelled,'pending':max(0,total-terminal)}

def record_protocol_model_response(conn,message_id,participant_id,response_text,now_fn,*,result_digest=None,model_call_id=None):
    if not isinstance(response_text,str) or not response_text.strip():raise ValueError('protocol response')
    source=conn.execute("SELECT mission_id,context_revision,plan_revision,correlation_id,fanout_id,recipient_set_digest FROM operator_messages WHERE message_id=?",(message_id,)).fetchone()
    trajectory=conn.execute("SELECT * FROM protocol_cognitive_trajectories WHERE message_id=? AND participant_id=?",(message_id,participant_id)).fetchone()
    delivery=conn.execute("SELECT delivery_state FROM operator_message_deliveries WHERE message_id=? AND recipient=?",(message_id,participant_id)).fetchone()
    if source is None or trajectory is None or delivery is None:raise ValueError('protocol response lineage missing')
    response_text=response_text.strip();stamp=now_fn()
    if trajectory['response_message_id']:
        prior=conn.execute("SELECT content_digest FROM operator_messages WHERE message_id=?",(trajectory['response_message_id'],)).fetchone()
        if prior and prior['content_digest']==digest(response_text):
            return {'idempotent':True,'response_message_id':trajectory['response_message_id'],**_reconcile_protocol_message_state(conn,message_id,stamp)}
        raise ValueError('protocol response conflict')
    reply_id='opreply-'+digest({'message_id':message_id,'participant_id':participant_id,'response':response_text})[:32]
    conn.execute("UPDATE operator_message_deliveries SET delivery_state='APPLIED',delivered_at=COALESCE(delivered_at,?),applied_at=?,applied_assignment_id=COALESCE(applied_assignment_id,?) WHERE message_id=? AND recipient=?",(stamp,stamp,trajectory['local_assignment_id'],message_id,participant_id))
    conn.execute("INSERT INTO operator_messages(message_id,mission_id,command_id,from_participant,target,kind,content,content_digest,context_revision,plan_revision,state,created_at,applied_at,applied_assignment_id,correlation_id,causation_id,fanout_id,recipient_set_digest) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(reply_id,source['mission_id'],'protocol:'+str(model_call_id or trajectory['trajectory_id']),participant_id,PRIMARY_PARTICIPANT,'RESPONSE',response_text,digest(response_text),int(source['context_revision']),int(source['plan_revision']),'DELIVERED',stamp,stamp,trajectory['local_assignment_id'],source['correlation_id'],message_id,source['fanout_id'],source['recipient_set_digest']))
    protocol_trajectory_update(conn,message_id,participant_id,now_fn,state='RESPONSE_RECONCILED',result_digest=result_digest or digest(response_text),response_message_id=reply_id,local_model_call_id=model_call_id or trajectory['local_model_call_id'])
    state=_reconcile_protocol_message_state(conn,message_id,stamp)
    _event(conn,source['mission_id'],'PROTOCOL_PARTICIPANT_RESPONSE',{'message_id':message_id,'participant_id':participant_id,'cognition_route':trajectory['cognition_route'],'response_message_id':reply_id,'authority_effect':'NONE'},now_fn)
    return {'idempotent':False,'response_message_id':reply_id,**state}

def fail_protocol_trajectory(conn,message_id,participant_id,reason,now_fn):
    stamp=now_fn();trajectory=conn.execute("SELECT * FROM protocol_cognitive_trajectories WHERE message_id=? AND participant_id=?",(message_id,participant_id)).fetchone()
    if trajectory is None:raise ValueError('protocol trajectory missing')
    if trajectory['state']=='RESPONSE_RECONCILED':return {'state':'RESPONSE_RECONCILED'}
    conn.execute("UPDATE operator_message_deliveries SET delivery_state='FAILED',delivered_at=COALESCE(delivered_at,?) WHERE message_id=? AND recipient=? AND delivery_state NOT IN ('APPLIED','CANCELLED')",(stamp,message_id,participant_id))
    protocol_trajectory_update(conn,message_id,participant_id,now_fn,state='FAILED',result_digest=digest(str(reason)))
    state=_reconcile_protocol_message_state(conn,message_id,stamp)
    return {'state':'FAILED','message_state':state['state'],'reason':str(reason)[:500]}

def cancel_protocol_trajectory(conn,message_id,participant_id,reason,now_fn):
    stamp=now_fn();trajectory=conn.execute("SELECT * FROM protocol_cognitive_trajectories WHERE message_id=? AND participant_id=?",(message_id,participant_id)).fetchone()
    if trajectory is None:raise ValueError('protocol trajectory missing')
    if trajectory['state']=='RESPONSE_RECONCILED':return {'state':'RESPONSE_RECONCILED'}
    conn.execute("UPDATE operator_message_deliveries SET delivery_state='CANCELLED',delivered_at=COALESCE(delivered_at,?) WHERE message_id=? AND recipient=? AND delivery_state NOT IN ('APPLIED','FAILED')",(stamp,message_id,participant_id))
    protocol_trajectory_update(conn,message_id,participant_id,now_fn,state='CANCELLED',result_digest=digest(str(reason)))
    state=_reconcile_protocol_message_state(conn,message_id,stamp)
    _event(conn,trajectory['mission_id'],'PROTOCOL_PARTICIPANT_CANCELLED',{'message_id':message_id,'participant_id':participant_id,'reason':str(reason)[:500],'authority_effect':'NONE'},now_fn)
    return {'state':'CANCELLED','message_state':state['state'],'reason':str(reason)[:500]}

def _command_result(conn,command_id):
    row=conn.execute("SELECT * FROM operator_commands WHERE command_id=?",(command_id,)).fetchone()
    if row is None:raise ValueError("operator command missing")
    result=dict(row)
    try:result["payload"]=json.loads(result.pop("payload_json"))
    except Exception:result["payload"]={}
    try:result["result"]=json.loads(result.pop("result_json")) if result.get("result_json") else None
    except Exception:result["result"]=None
    receipt=conn.execute("SELECT receipt_digest FROM operator_command_receipts WHERE command_id=?",(command_id,)).fetchone()
    if receipt:result["receipt_digest"]=receipt["receipt_digest"]
    return result


def apply_command(conn,value,now_fn,*,principal_id=PRIMARY_OPERATOR):
    cmd=OperatorCommand.from_dict(value);mission_only={"PAUSE_SCOPE","STOP_SCOPE","TAKE_CONTROL","RELEASE_CONTROL","RESUME_SCOPE"}
    if cmd.action in mission_only and cmd.target!="mission:"+cmd.mission_id:raise ValueError("mission control action requires mission scope target")
    if cmd.action in {"RESUME_SCOPE","RELEASE_CONTROL","AMEND_PLAN","REASSIGN","APPROVE_PROPOSAL"} and cmd.expected_revision is None:raise ValueError("expected control revision required")
    grant=_grant_for(conn,principal_id,cmd.mission_id,cmd.action,now_fn());participant_id=_participant_for_principal(conn,principal_id)["participant_id"];existing=conn.execute("SELECT command_digest FROM operator_commands WHERE command_id=?",(cmd.command_id,)).fetchone()
    if existing is not None:
        if existing["command_digest"]!=cmd.payload_digest:raise ValueError("command_id payload conflict")
        return {**_command_result(conn,cmd.command_id),"idempotent":True}
    if not _mission_exists(conn,cmd.mission_id):raise ValueError("mission not found")
    terminal=mission_terminal_state(conn,cmd.mission_id)
    if terminal is not None and cmd.action not in {"REQUEST_STATUS","ANNOTATE"}:raise ValueError("mission terminal state:"+terminal)
    conn.execute("BEGIN IMMEDIATE")
    try:
        state=ensure_control_state(conn,cmd.mission_id,now_fn)
        if cmd.expected_revision is not None and int(cmd.expected_revision)!=int(state["control_epoch"]):raise ValueError("expected control revision mismatch")
        stamp=now_fn();conn.execute("INSERT INTO operator_commands VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(cmd.command_id,cmd.payload_digest,cmd.mission_id,cmd.action,cmd.target,canonical(cmd.payload),principal_id,participant_id,grant["grant_id"],1000 if principal_id==PRIMARY_OPERATOR else 900,int(state["control_epoch"]),"PERSISTED","ACCEPTED","APPLYING","PENDING",stamp,stamp,None,None))
        if cmd.action=="REQUEST_STATUS":result={"control":dict(state),"mission_id":cmd.mission_id}
        elif cmd.action in {"MESSAGE","ANNOTATE"}:result=_store_message(conn,cmd,state,now_fn,kind=cmd.action,participant_id=participant_id)
        elif cmd.action=="AMEND_CONTEXT":
            content=cmd.payload.get("content")
            if not isinstance(content,(dict,list,str)):raise ValueError("context content")
            revision=int(state["context_revision"])+1;raw=canonical(content);conn.execute("INSERT INTO mission_context_revisions VALUES(?,?,?,?,?,?)",(cmd.mission_id,revision,cmd.command_id,raw,digest(content),now_fn()));conn.execute("UPDATE mission_operator_control SET context_revision=?,last_command_id=?,updated_at=? WHERE mission_id=?",(revision,cmd.command_id,now_fn(),cmd.mission_id));result={"context_revision":revision,"content_digest":digest(content)}
        elif cmd.action=="AMEND_PLAN":
            content=cmd.payload.get("content")
            if not isinstance(content,(dict,list,str)):raise ValueError("plan content")
            raw=canonical(content);content_digest=digest(content);scope_change=_plan_scope_extension(cmd.payload)
            if scope_change is not None:
                proposal_id="plan-amendment-"+uuid.uuid4().hex;conn.execute("INSERT INTO operator_pending_plan_amendments VALUES(?,?,?,?,?,?,?,?)",(proposal_id,cmd.mission_id,cmd.command_id,raw,content_digest,canonical(scope_change),"AWAITING_SCOPE_ACTIVATION",now_fn()));result={"proposal_id":proposal_id,"content_digest":content_digest,"state":"AWAITING_SCOPE_ACTIVATION","requested_scope":scope_change,"plan_revision":int(state["plan_revision"]),"scope_escalated":False}
            else:
                revision=int(state["plan_revision"])+1;conn.execute("INSERT INTO mission_plan_revisions VALUES(?,?,?,?,?,?)",(cmd.mission_id,revision,cmd.command_id,raw,content_digest,now_fn()));conn.execute("UPDATE mission_operator_control SET plan_revision=?,last_command_id=?,updated_at=? WHERE mission_id=?",(revision,cmd.command_id,now_fn(),cmd.mission_id));result={"plan_revision":revision,"content_digest":content_digest,"scope_escalated":False}
        elif cmd.action=="APPROVE_PROPOSAL":
            proposal_id=cmd.payload.get("proposal_id");proposal_digest=cmd.payload.get("proposal_digest")
            if not isinstance(proposal_id,str) or not proposal_id or not isinstance(proposal_digest,str) or len(proposal_digest)!=64:raise ValueError("proposal approval")
            conn.execute("INSERT INTO operator_approvals VALUES(?,?,?,?,?)",(cmd.mission_id,proposal_id,proposal_digest,cmd.command_id,now_fn()));result={"proposal_id":proposal_id,"proposal_digest":proposal_digest,"approved":True}
        elif cmd.action=="REVOKE_CAPABILITY":
            capability=cmd.payload.get("capability")
            if not isinstance(capability,str) or not capability.strip() or len(capability)>180:raise ValueError("capability")
            state=_bump_control(conn,cmd.mission_id,now_fn,last_command_id=cmd.command_id);conn.execute("INSERT INTO operator_capability_revocations VALUES(?,?,?,?,?,NULL)",(cmd.mission_id,capability.strip(),cmd.command_id,state["control_epoch"],now_fn()));result={"capability":capability.strip(),"revoked":True,"control":state}
        elif cmd.action in {"PAUSE_SCOPE","STOP_SCOPE","TAKE_CONTROL","RELEASE_CONTROL"}:
            if cmd.action=="PAUSE_SCOPE":state=_bump_control(conn,cmd.mission_id,now_fn,pause=True,last_command_id=cmd.command_id);driver=_driver_fence(conn,cmd.mission_id,now_fn,state="PAUSED",reason="OPERATOR_PAUSE")
            elif cmd.action=="STOP_SCOPE":state=_bump_control(conn,cmd.mission_id,now_fn,pause=True,stop=True,last_command_id=cmd.command_id);driver=_driver_fence(conn,cmd.mission_id,now_fn,state="STOPPED",reason="OPERATOR_STOP")
            elif cmd.action=="TAKE_CONTROL":state=_bump_control(conn,cmd.mission_id,now_fn,owner=principal_id,last_command_id=cmd.command_id);driver=_driver_fence(conn,cmd.mission_id,now_fn,state=None,reason="OPERATOR_TAKE_CONTROL")
            else:state=_bump_control(conn,cmd.mission_id,now_fn,owner=AUTONOMOUS_OWNER,last_command_id=cmd.command_id);driver=_driver_fence(conn,cmd.mission_id,now_fn,state=None,reason="OPERATOR_RELEASE_CONTROL")
            assignments=_release_assignment_handoff(conn,cmd.mission_id,now_fn,principal_id=principal_id,generation=int((driver or {}).get("generation") or 1),control_epoch=int(state["control_epoch"])) if cmd.action=="RELEASE_CONTROL" else _fence_assignments(conn,cmd.mission_id,now_fn);result={"control":state,"driver_fence":driver,"assignments":assignments}
        elif cmd.action=="RESUME_SCOPE":
            latch=str(cmd.payload.get("latch") or "ALL").upper()
            if latch not in {"PAUSE","STOP","ALL"}:raise ValueError("resume latch")
            state=_bump_control(conn,cmd.mission_id,now_fn,pause=False if latch in {"PAUSE","ALL"} else None,stop=False if latch in {"STOP","ALL"} else None,last_command_id=cmd.command_id);result={"control":state,"driver_resume_required":bool(state["control_owner"]==AUTONOMOUS_OWNER and not state["pause_latch"] and not state["stop_latch"])}
        elif cmd.action=="CANCEL_ASSIGNMENT":
            assignment_id=cmd.payload.get("assignment_id")
            if not isinstance(assignment_id,str) or not assignment_id:raise ValueError("assignment_id")
            row=conn.execute("SELECT * FROM mission_execution_assignments WHERE assignment_id=? AND mission_id=?",(assignment_id,cmd.mission_id)).fetchone()
            if row is None:raise ValueError("assignment not found")
            if row["state"] not in {"READY","CLAIMED"}:raise ValueError("assignment not cancellable")
            new_state="CANCEL_REQUESTED" if row["state"]=="CLAIMED" else "CANCELLED";conn.execute("UPDATE mission_execution_assignments SET state=?,finished_at=CASE WHEN ?='CANCELLED' THEN ? ELSE finished_at END WHERE assignment_id=?",(new_state,new_state,now_fn(),assignment_id));result={"assignment_id":assignment_id,"state":new_state}
        elif cmd.action=="REASSIGN":
            assignment_id=cmd.payload.get("assignment_id");material=cmd.payload.get("material_drone_id")
            if not isinstance(assignment_id,str) or not assignment_id or not isinstance(material,str) or not material:raise ValueError("reassign")
            old=conn.execute("SELECT * FROM mission_execution_assignments WHERE assignment_id=? AND mission_id=?",(assignment_id,cmd.mission_id)).fetchone()
            if old is None or old["state"] not in {"READY","CLAIMED","CANCEL_REQUESTED","CANCELLED","STALE_RESULT"}:raise ValueError("assignment not reassignable")
            fence=_driver_fence(conn,cmd.mission_id,now_fn,state=None,reason="OPERATOR_REASSIGN");driver=_driver_row(conn,cmd.mission_id);generation=int(driver["generation"]) if driver else int(old["lease_generation"])+1;current=ensure_control_state(conn,cmd.mission_id,now_fn)
            if old["state"] in {"CLAIMED","CANCEL_REQUESTED"}:conn.execute("UPDATE mission_execution_assignments SET state='CANCEL_REQUESTED' WHERE assignment_id=?",(assignment_id,));result={"previous_assignment_id":assignment_id,"requested_material_drone_id":material,"state":"WAITING_CHECKPOINT","control_epoch":current["control_epoch"],"driver_fence":fence,"lease_generation":generation};new_id=None
            else:
                conn.execute("UPDATE mission_execution_assignments SET state='CANCELLED',finished_at=COALESCE(finished_at,?) WHERE assignment_id=?",(now_fn(),assignment_id));conn.execute("UPDATE mission_execution_assignments SET lease_generation=? WHERE mission_id=? AND state='READY' AND assignment_id<>?",(generation,cmd.mission_id,assignment_id));new_id="assignment-"+uuid.uuid4().hex
            if new_id is not None:
                cols={r[1] for r in conn.execute("PRAGMA table_info(mission_execution_assignments)")}
                required={"control_epoch","context_revision","plan_revision","dispatch_authority"}
                if not required.issubset(cols):raise ValueError("operator assignment schema unavailable")
                conn.execute("INSERT INTO mission_execution_assignments(assignment_id,mission_id,phase_id,logical_drone_id,material_drone_id,input_digest,input_json,state,lease_generation,control_epoch,context_revision,plan_revision,dispatch_authority,created_at,claimed_at,finished_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(new_id,cmd.mission_id,old["phase_id"],old["logical_drone_id"],material,old["input_digest"],old["input_json"],"READY",generation,int(current["control_epoch"]),int(current["context_revision"]),int(current["plan_revision"]),principal_id,now_fn(),None,None))
                result={"previous_assignment_id":assignment_id,"assignment_id":new_id,"material_drone_id":material,"state":"READY","control_epoch":current["control_epoch"],"driver_fence":fence,"lease_generation":generation}
        else:raise ValueError("operator action not implemented")
        final_state=ensure_control_state(conn,cmd.mission_id,now_fn);execution_state="APPLIED";observation_state="CONTROL_STATE_OBSERVED" if cmd.action in CONTROL_ACTIONS else "PERSISTED";completed_at=now_fn()
        if cmd.action in {"PAUSE_SCOPE","STOP_SCOPE","TAKE_CONTROL"} and int((result.get("assignments") or {}).get("cancel_requested") or 0)>0:execution_state="CONTAINMENT_PENDING";observation_state="PARTIAL";completed_at=None
        elif cmd.action=="CANCEL_ASSIGNMENT" and result.get("state")=="CANCEL_REQUESTED":execution_state="CONTAINMENT_PENDING";observation_state="PARTIAL";completed_at=None
        elif cmd.action=="REASSIGN" and result.get("state")=="WAITING_CHECKPOINT":execution_state="WAITING_CHECKPOINT";observation_state="PARTIAL";completed_at=None
        elif cmd.action=="AMEND_PLAN" and result.get("state")=="AWAITING_SCOPE_ACTIVATION":execution_state="AWAITING_SCOPE_ACTIVATION";observation_state="PENDING_AUTHORITY";completed_at=None
        conn.execute("UPDATE operator_commands SET execution_state=?,observation_state=?,completed_at=?,result_json=? WHERE command_id=?",(execution_state,observation_state,completed_at,canonical(result),cmd.command_id));event_id=_event(conn,cmd.mission_id,"OPERATOR_COMMAND_APPLIED",{"command_id":cmd.command_id,"action":cmd.action,"target":cmd.target,"control_epoch":final_state["control_epoch"],"effect_class":action_effect(cmd.action),"authority_effect":"OPERATOR_SCOPED_CONTROL" if cmd.action in CONTROL_ACTIONS else "NONE"},now_fn,command_id=cmd.command_id);receipt={"schema":"lion.operator-command-receipt/v1","command_id":cmd.command_id,"command_digest":cmd.payload_digest,"mission_id":cmd.mission_id,"action":cmd.action,"principal_id":principal_id,"participant_id":participant_id,"grant_id":grant["grant_id"],"effective_priority":1000 if principal_id==PRIMARY_OPERATOR else 900,"control_epoch":final_state["control_epoch"],"context_revision":final_state["context_revision"],"plan_revision":final_state["plan_revision"],"event_id":event_id,"delivery_state":"PERSISTED","admission_state":"ACCEPTED","execution_state":execution_state,"observation_state":observation_state,"created_at":now_fn()};receipt["receipt_digest"]=command_receipt_digest(receipt);conn.execute("INSERT INTO operator_command_receipts VALUES(?,?,?,?)",(cmd.command_id,receipt["receipt_digest"],canonical(receipt),receipt["created_at"]));conn.commit();return {**_command_result(conn,cmd.command_id),"receipt":receipt,"idempotent":False}
    except Exception:conn.rollback();raise


def command_status(conn,command_id):return _command_result(conn,command_id)
def events_after(conn,mission_id,after=0,*,limit=200):
    if type(after) is not int or after<0 or type(limit) is not int or not 1<=limit<=1000:raise ValueError("event cursor")
    values=[]
    for row in conn.execute("SELECT * FROM operator_events WHERE mission_id=? AND event_id>? ORDER BY event_id LIMIT ?",(mission_id,after,limit)).fetchall():
        value=dict(row)
        try:value["payload"]=json.loads(value.pop("payload_json"))
        except Exception:value["payload"]={}
        values.append(value)
    return {"mission_id":mission_id,"events":values,"next_cursor":values[-1]["event_id"] if values else after}
def acknowledge_events(conn,consumer_id,mission_id,event_id,now_fn):
    if not isinstance(consumer_id,str) or not consumer_id or type(event_id) is not int or event_id<0:raise ValueError("consumer cursor")
    prior=conn.execute("SELECT event_id FROM operator_consumer_cursors WHERE consumer_id=? AND mission_id=?",(consumer_id,mission_id)).fetchone()
    if prior and int(event_id)<int(prior["event_id"]):raise ValueError("event cursor regression")
    conn.execute("INSERT INTO operator_consumer_cursors VALUES(?,?,?,?) ON CONFLICT(consumer_id,mission_id) DO UPDATE SET event_id=excluded.event_id,updated_at=excluded.updated_at",(consumer_id,mission_id,event_id,now_fn()));conn.commit();return {"consumer_id":consumer_id,"mission_id":mission_id,"event_id":event_id}
def mission_snapshot(conn,mission_id,now_fn=None):
    control=control_state(conn,mission_id,None) or _legacy_default_state(mission_id);commands=[dict(r) for r in conn.execute("SELECT command_id,action,target,principal_id,effective_priority,delivery_state,admission_state,execution_state,observation_state,created_at,completed_at FROM operator_commands WHERE mission_id=? ORDER BY admitted_at DESC LIMIT 50",(mission_id,))];messages=[dict(r) for r in conn.execute("SELECT message_id,command_id,from_participant,target,kind,content,context_revision,plan_revision,state,created_at,applied_at,applied_assignment_id,correlation_id,causation_id,fanout_id,recipient_set_digest FROM operator_messages WHERE mission_id=? ORDER BY created_at DESC LIMIT 200",(mission_id,))];deliveries=[dict(r) for r in conn.execute("SELECT d.* FROM operator_message_deliveries d JOIN operator_messages m ON m.message_id=d.message_id WHERE m.mission_id=? ORDER BY m.created_at,d.recipient",(mission_id,))];return {"schema":"lion.operator-mission-projection/v1","mission_id":mission_id,"control":control,"commands":commands,"messages":messages,"message_deliveries":deliveries,"recipient_routes":[dict(r) for r in conn.execute("SELECT r.* FROM operator_protocol_recipient_routes r JOIN operator_messages m ON m.message_id=r.message_id WHERE m.mission_id=? ORDER BY m.created_at,r.recipient",(mission_id,))],"cognitive_trajectories":[dict(r) for r in conn.execute("SELECT * FROM protocol_cognitive_trajectories WHERE mission_id=? ORDER BY created_at,participant_id",(mission_id,))],"control_capabilities":{"block_new_admissions":"SUPPORTED","cancel_ready_assignments":"SUPPORTED","cancel_inflight":"BEST_EFFORT_CHECKPOINT_REQUIRED","remote_unreachable_worker":"LEASE_EXPIRY_ONLY","emergency_helper":"PREPROVISIONED_EXACT_INVENTORY_ONLY"},"operator":participant_snapshot(conn),"operator_proxy":participant_snapshot(conn,SENTINELX_PROXY_PRINCIPAL),"authority_effect":"NONE"}
def force_epoch_at_least(conn,mission_id,minimum_epoch,now_fn,*,incarnation_id=None):
    if type(minimum_epoch) is not int or minimum_epoch<1:raise ValueError("minimum epoch")
    state=ensure_control_state(conn,mission_id,now_fn);changed=False
    if int(state["control_epoch"])<minimum_epoch:conn.execute("UPDATE mission_operator_control SET control_epoch=?,incarnation_id=?,control_owner=?,pause_latch=1,stop_latch=1,updated_at=? WHERE mission_id=?",(minimum_epoch,incarnation_id or ("incarnation-"+uuid.uuid4().hex),PRIMARY_OPERATOR,now_fn(),mission_id));_driver_fence(conn,mission_id,now_fn,state="STOPPED",reason="EPOCH_FLOOR_RECONCILIATION");_fence_assignments(conn,mission_id,now_fn);changed=True
    conn.commit();return {**ensure_control_state(conn,mission_id,now_fn),"reconciled":changed}
