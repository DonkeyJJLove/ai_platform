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
SCHEMA_VERSION = 4
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
  applied_assignment_id TEXT
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
    stamp = now_fn()
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
    cur=conn.execute("UPDATE mission_execution_assignments SET lease_generation=? WHERE mission_id=? AND state='READY'",(int(generation),mission_id))
    if "control_epoch" in cols:conn.execute("UPDATE mission_execution_assignments SET control_epoch=? WHERE mission_id=? AND state='READY'",(int(state["control_epoch"]),mission_id))
    if "dispatch_authority" in cols:conn.execute("UPDATE mission_execution_assignments SET dispatch_authority=? WHERE mission_id=? AND state='READY'",(authority_owner,mission_id))
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
    out={};tables=_tables(conn)
    if 'logical_drones' in tables:
        for row in conn.execute('SELECT logical_id,role FROM logical_drones WHERE mission_id=?',(mission_id,)):out[str(row['logical_id'])]={'recipient':'drone:'+str(row['logical_id']),'kind':'LOGICAL','role':str(row['role'] or '')}
    if 'material_workers' in tables:
        for row in conn.execute('SELECT pod_name,logical_id FROM material_workers WHERE mission_id=?',(mission_id,)):
            if row['pod_name']:out[str(row['pod_name'])]={'recipient':'drone:'+str(row['pod_name']),'kind':'MATERIAL','role':str(row['logical_id'] or '')}
    if 'mission_execution_assignments' in tables:
        for row in conn.execute('SELECT logical_drone_id,material_drone_id FROM mission_execution_assignments WHERE mission_id=?',(mission_id,)):
            for name,kind in ((row['logical_drone_id'],'LOGICAL'),(row['material_drone_id'],'MATERIAL')):
                if name and str(name) not in out:out[str(name)]={'recipient':'drone:'+str(name),'kind':kind,'role':''}
    return out

def resolve_target(conn,mission_id,target):
    if not _mission_exists(conn,mission_id):raise ValueError('mission not found')
    prefix,ident=target.split(':',1);inv=_mission_drone_inventory(conn,mission_id)
    if prefix=='mission':
        if ident!=mission_id:raise ValueError('target mission mismatch')
        return sorted({v['recipient'] for v in inv.values()})
    if prefix=='drone':
        if ident not in inv:raise ValueError('unresolved drone target')
        return [inv[ident]['recipient']]
    if prefix=='operator':
        row=conn.execute("SELECT participant_id FROM operator_participants WHERE participant_id=? AND state='ACTIVE'",('operator:'+ident,)).fetchone()
        if row is None:raise ValueError('unresolved operator target')
        return [target]
    if prefix=='swarm':
        if ident!=mission_id:raise ValueError('unresolved swarm target')
        return sorted({v['recipient'] for v in inv.values()})
    if prefix=='group':
        if ident not in {'architecture','security','runtime'}:raise ValueError('unresolved group target')
        values=[]
        for item in inv.values():
            role=item['role'].upper()
            if ident=='runtime' or (ident=='security' and 'SECUR' in role) or (ident=='architecture' and any(x in role for x in ('ARCH','PLANNER','CONTROL'))):values.append(item['recipient'])
        return sorted(set(values))
    raise ValueError('unresolved target')

def _message_target_matches(target,mission_id,material_drone_id,logical_drone_id):
    if target=='mission:'+mission_id:return True
    if target.startswith('drone:'):return target.split(':',1)[1] in {str(material_drone_id or ''),str(logical_drone_id or '')}
    return False

def assignment_context(conn,mission_id,material_drone_id,logical_drone_id):
    state=conn.execute("SELECT * FROM mission_operator_control WHERE mission_id=?",(mission_id,)).fetchone()
    if state is None:return {"control":None,"context":None,"plan":None,"messages":[]}
    context=conn.execute("SELECT * FROM mission_context_revisions WHERE mission_id=? ORDER BY revision DESC LIMIT 1",(mission_id,)).fetchone();plan=conn.execute("SELECT * FROM mission_plan_revisions WHERE mission_id=? ORDER BY revision DESC LIMIT 1",(mission_id,)).fetchone();messages=[]
    for row in conn.execute("SELECT * FROM operator_messages WHERE mission_id=? AND state IN ('PENDING','PARTIAL') ORDER BY created_at,message_id",(mission_id,)):
        value=dict(row);direct=_message_target_matches(value["target"],mission_id,material_drone_id,logical_drone_id);delivered=conn.execute("SELECT 1 FROM operator_message_deliveries WHERE message_id=? AND recipient IN (?,?) AND delivery_state!='APPLIED' LIMIT 1",(value['message_id'],'drone:'+str(material_drone_id or ''),'drone:'+str(logical_drone_id or ''))).fetchone()
        if direct or delivered:messages.append(value)
    return {"control":dict(state),"context":dict(context) if context else None,"plan":dict(plan) if plan else None,"messages":messages[:64]}

def note_assignment_application(conn,assignment_id,result,now_fn):
    if "mission_execution_assignments" not in _tables(conn):return {"applied_messages":0,"partial_messages":0}
    row=conn.execute("SELECT mission_id,logical_drone_id,material_drone_id FROM mission_execution_assignments WHERE assignment_id=?",(assignment_id,)).fetchone()
    if row is None:raise ValueError("assignment missing")
    ids=result.get("operator_message_ids") or []
    if not isinstance(ids,list) or any(not isinstance(x,str) for x in ids):ids=[]
    stamp=now_fn();applied=0;partial=0;responses=[];recipients=['drone:'+str(row['material_drone_id'] or ''),'drone:'+str(row['logical_drone_id'] or '')]
    for message_id in ids[:64]:
        matched=0
        for recipient in recipients:matched+=conn.execute("UPDATE operator_message_deliveries SET delivery_state='APPLIED',delivered_at=COALESCE(delivered_at,?),applied_at=?,applied_assignment_id=? WHERE message_id=? AND recipient=? AND delivery_state!='APPLIED'",(stamp,stamp,assignment_id,message_id,recipient)).rowcount
        if matched==0:matched=conn.execute("UPDATE operator_messages SET state='APPLIED',applied_at=?,applied_assignment_id=? WHERE message_id=? AND mission_id=? AND state='PENDING'",(stamp,assignment_id,message_id,row['mission_id'])).rowcount
        counts=conn.execute("SELECT COUNT(*) total,SUM(CASE WHEN delivery_state='APPLIED' THEN 1 ELSE 0 END) applied FROM operator_message_deliveries WHERE message_id=?",(message_id,)).fetchone()
        if counts and int(counts['total'] or 0)>0:
            total=int(counts['total']);done=int(counts['applied'] or 0);state='APPLIED' if done==total else 'PARTIAL';conn.execute("UPDATE operator_messages SET state=?,applied_at=CASE WHEN ?='APPLIED' THEN ? ELSE applied_at END,applied_assignment_id=CASE WHEN ?='APPLIED' THEN ? ELSE applied_assignment_id END WHERE message_id=?",(state,state,stamp,state,assignment_id,message_id));applied+=1 if state=='APPLIED' else 0;partial+=1 if state=='PARTIAL' else 0
        else:applied+=int(bool(matched))
        response_text=result.get('response_text')
        if matched and isinstance(response_text,str) and response_text.strip():
            reply_id='opreply-'+digest({'assignment_id':assignment_id,'message_id':message_id,'response':response_text})[:32];from_participant='drone:'+str(row['material_drone_id'] or row['logical_drone_id']);original=conn.execute('SELECT context_revision,plan_revision FROM operator_messages WHERE message_id=?',(message_id,)).fetchone();conn.execute("INSERT OR IGNORE INTO operator_messages VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(reply_id,row['mission_id'],'assignment:'+assignment_id,from_participant,PRIMARY_PARTICIPANT,'RESPONSE',response_text.strip(),digest(response_text.strip()),int(original['context_revision'] if original else 0),int(original['plan_revision'] if original else 0),'DELIVERED',stamp,stamp,assignment_id));responses.append(reply_id)
    if applied or partial:_event(conn,row['mission_id'],'OPERATOR_MESSAGE_APPLIED',{'assignment_id':assignment_id,'message_ids':ids[:64],'applied_messages':applied,'partial_messages':partial,'response_message_ids':responses},now_fn)
    return {"applied_messages":applied,"partial_messages":partial,"response_message_ids":responses}

def _store_message(conn,cmd,state,now_fn,*,kind,participant_id):
    content=cmd.payload.get("content")
    if not isinstance(content,str) or not content.strip() or len(content)>16000:raise ValueError("message content")
    content=content.strip();message_id="opmsg-"+digest({"command_id":cmd.command_id,"target":cmd.target})[:32];recipients=resolve_target(conn,cmd.mission_id,cmd.target);message_state='PENDING' if recipients else 'PERSISTED_NO_CURRENT_RECIPIENT';created=now_fn();conn.execute("INSERT OR IGNORE INTO operator_messages VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(message_id,cmd.mission_id,cmd.command_id,participant_id,cmd.target,kind,content,digest(content),int(state["context_revision"]),int(state["plan_revision"]),message_state,created,None,None));[conn.execute("INSERT OR IGNORE INTO operator_message_deliveries VALUES(?,?,?,NULL,NULL,NULL)",(message_id,r,'PERSISTED')) for r in recipients];return {"message_id":message_id,"target":cmd.target,"state":message_state,"recipients":recipients,"recipient_count":len(recipients)}

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
                cols={r[1] for r in conn.execute("PRAGMA table_info(mission_execution_assignments)")};values={"assignment_id":new_id,"mission_id":cmd.mission_id,"phase_id":old["phase_id"],"logical_drone_id":old["logical_drone_id"],"material_drone_id":material,"input_digest":old["input_digest"],"input_json":old["input_json"],"state":"READY","lease_generation":generation,"created_at":now_fn(),"claimed_at":None,"finished_at":None}
                if "control_epoch" in cols:values["control_epoch"]=int(current["control_epoch"])
                if "context_revision" in cols:values["context_revision"]=int(current["context_revision"])
                if "plan_revision" in cols:values["plan_revision"]=int(current["plan_revision"])
                if "dispatch_authority" in cols:values["dispatch_authority"]=principal_id
                conn.execute("INSERT INTO mission_execution_assignments(assignment_id,mission_id,phase_id,logical_drone_id,material_drone_id,input_digest,input_json,state,lease_generation,created_at,claimed_at,finished_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",(new_id,cmd.mission_id,old["phase_id"],old["logical_drone_id"],material,old["input_digest"],old["input_json"],"READY",generation,values["created_at"],None,None))
                if "control_epoch" in cols:conn.execute("UPDATE mission_execution_assignments SET control_epoch=? WHERE assignment_id=?",(int(current["control_epoch"]),new_id))
                if "context_revision" in cols:conn.execute("UPDATE mission_execution_assignments SET context_revision=? WHERE assignment_id=?",(int(current["context_revision"]),new_id))
                if "plan_revision" in cols:conn.execute("UPDATE mission_execution_assignments SET plan_revision=? WHERE assignment_id=?",(int(current["plan_revision"]),new_id))
                if "dispatch_authority" in cols:conn.execute("UPDATE mission_execution_assignments SET dispatch_authority=? WHERE assignment_id=?",(principal_id,new_id))
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
    control=control_state(conn,mission_id,None) or _legacy_default_state(mission_id);commands=[dict(r) for r in conn.execute("SELECT command_id,action,target,principal_id,effective_priority,delivery_state,admission_state,execution_state,observation_state,created_at,completed_at FROM operator_commands WHERE mission_id=? ORDER BY admitted_at DESC LIMIT 50",(mission_id,))];messages=[dict(r) for r in conn.execute("SELECT message_id,from_participant,target,kind,content,context_revision,plan_revision,state,created_at,applied_at,applied_assignment_id FROM operator_messages WHERE mission_id=? ORDER BY created_at DESC LIMIT 100",(mission_id,))];deliveries=[dict(r) for r in conn.execute("SELECT d.* FROM operator_message_deliveries d JOIN operator_messages m ON m.message_id=d.message_id WHERE m.mission_id=? ORDER BY m.created_at,d.recipient",(mission_id,))];return {"schema":"lion.operator-mission-projection/v1","mission_id":mission_id,"control":control,"commands":commands,"messages":messages,"message_deliveries":deliveries,"control_capabilities":{"block_new_admissions":"SUPPORTED","cancel_ready_assignments":"SUPPORTED","cancel_inflight":"BEST_EFFORT_CHECKPOINT_REQUIRED","remote_unreachable_worker":"LEASE_EXPIRY_ONLY","emergency_helper":"PREPROVISIONED_EXACT_INVENTORY_ONLY"},"operator":participant_snapshot(conn),"operator_proxy":participant_snapshot(conn,SENTINELX_PROXY_PRINCIPAL),"authority_effect":"NONE"}
def force_epoch_at_least(conn,mission_id,minimum_epoch,now_fn,*,incarnation_id=None):
    if type(minimum_epoch) is not int or minimum_epoch<1:raise ValueError("minimum epoch")
    state=ensure_control_state(conn,mission_id,now_fn);changed=False
    if int(state["control_epoch"])<minimum_epoch:conn.execute("UPDATE mission_operator_control SET control_epoch=?,incarnation_id=?,control_owner=?,pause_latch=1,stop_latch=1,updated_at=? WHERE mission_id=?",(minimum_epoch,incarnation_id or ("incarnation-"+uuid.uuid4().hex),PRIMARY_OPERATOR,now_fn(),mission_id));_driver_fence(conn,mission_id,now_fn,state="STOPPED",reason="EPOCH_FLOOR_RECONCILIATION");_fence_assignments(conn,mission_id,now_fn);changed=True
    conn.commit();return {**ensure_control_state(conn,mission_id,now_fn),"reconciled":changed}
