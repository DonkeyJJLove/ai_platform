"""Mission-scoped durable operator participation in the LION swarm.

This layer owns communication-session lifecycle and routes authenticated human
messages into the existing operator_messages -> mission assignment -> local
worker path.  It never grants effect authority; operator-control pairing and
control_epoch remain independent.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from cyber_lion.mission_control import global_scheduler, operator_control

SCHEMA_ID = "lion.operator-swarm-session/v1"
SCHEMA_VERSION = 1
MAX_SESSION_SECONDS = 8 * 60 * 60
DEFAULT_WORKERS = ()
_ALLOWED_TYPES = frozenset({"REQUEST", "MESSAGE", "HANDOFF", "EVIDENCE", "RESPONSE", "STATUS"})
_ACTIVE_DRIVER_STATES = frozenset({"ACTIVE", "WAITING", "BLOCKED"})
_VERIFIER_SCHEMA = "lion.swarm-verifier-record/v1"
_VERIFIER_VERDICTS = frozenset({"SUPPORTED_BY_TRUSTED_CONTEXT", "CONTRADICTED_BY_TRUSTED_CONTEXT", "UNKNOWN"})
_VERIFIER_EVIDENCE_CLASSES = frozenset({"TRUSTED_TOPOLOGY_CONTEXT", "OPERATOR_MESSAGE", "MODEL_CLAIM"})

DDL = r"""
CREATE TABLE IF NOT EXISTS operator_swarm_sessions(
  session_id TEXT PRIMARY KEY,
  mission_id TEXT NOT NULL,
  swarm_id TEXT NOT NULL,
  state TEXT NOT NULL,
  mode TEXT NOT NULL,
  session_epoch INTEGER NOT NULL,
  activation_time TEXT NOT NULL,
  mission_deadline TEXT NOT NULL,
  created_by TEXT NOT NULL,
  binding_digest TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  closed_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_operator_swarm_sessions_mission
  ON operator_swarm_sessions(mission_id,state,created_at);
CREATE TABLE IF NOT EXISTS operator_swarm_members(
  session_id TEXT NOT NULL,
  participant_id TEXT NOT NULL,
  principal_id TEXT,
  member_kind TEXT NOT NULL,
  role TEXT NOT NULL,
  binding_id TEXT NOT NULL,
  state TEXT NOT NULL,
  joined_at TEXT NOT NULL,
  last_seen_at TEXT NOT NULL,
  lease_expires_at TEXT NOT NULL,
  PRIMARY KEY(session_id,participant_id),
  UNIQUE(binding_id)
);
CREATE TABLE IF NOT EXISTS operator_swarm_cursors(
  session_id TEXT NOT NULL,
  participant_id TEXT NOT NULL,
  sequence INTEGER NOT NULL,
  updated_at TEXT NOT NULL,
  PRIMARY KEY(session_id,participant_id)
);
CREATE TABLE IF NOT EXISTS operator_swarm_rounds(
  round_id TEXT PRIMARY KEY,
  session_id TEXT NOT NULL,
  root_message_id TEXT NOT NULL UNIQUE,
  primary_worker TEXT NOT NULL,
  verifier_worker TEXT,
  primary_assignment_id TEXT,
  verifier_assignment_id TEXT,
  primary_response TEXT,
  verifier_response TEXT,
  state TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS operator_swarm_dispatches(
  dispatch_id TEXT PRIMARY KEY,
  session_id TEXT NOT NULL,
  round_id TEXT NOT NULL,
  root_message_id TEXT NOT NULL,
  mission_message_id TEXT NOT NULL,
  assignment_id TEXT NOT NULL UNIQUE,
  recipient TEXT NOT NULL,
  stage TEXT NOT NULL,
  state TEXT NOT NULL,
  created_at TEXT NOT NULL,
  completed_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_operator_swarm_dispatch_state
  ON operator_swarm_dispatches(session_id,state,created_at);
CREATE TABLE IF NOT EXISTS operator_swarm_events(
  event_id INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id TEXT NOT NULL,
  mission_id TEXT NOT NULL,
  event_type TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  payload_digest TEXT NOT NULL,
  observed_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS operator_swarm_schema_migrations(
  version INTEGER PRIMARY KEY,
  schema_id TEXT NOT NULL,
  applied_at TEXT NOT NULL
);
"""


def _parse(ts: str) -> datetime:
    value=datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _cols(conn, table: str) -> set[str]:
    return {r[0] for r in conn.execute("SELECT name FROM pragma_table_info(?)",(table,))}


def migrate(conn, now_fn) -> None:
    operator_control.migrate(conn, now_fn)
    global_scheduler.migrate(conn, now_fn)
    conn.executescript(DDL)
    cols=_cols(conn, "operator_general_messages")
    additions={
      "session_id":"TEXT", "mission_id":"TEXT", "swarm_id":"TEXT",
      "correlation_id":"TEXT", "causation_id":"TEXT", "session_epoch":"INTEGER",
      "expires_at":"TEXT", "envelope_digest":"TEXT", "thread_id":"TEXT",
    }
    for name,ddl in additions.items():
        if name not in cols: conn.execute(f"ALTER TABLE operator_general_messages ADD COLUMN {name} {ddl}")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_operator_general_session_sequence ON operator_general_messages(session_id,sequence)")
    stamp=now_fn();conn.execute("INSERT OR IGNORE INTO operator_swarm_schema_migrations VALUES(?,?,?)",(SCHEMA_VERSION,SCHEMA_ID,stamp));conn.commit()


def _event(conn, session_id: str, mission_id: str, event_type: str, payload: dict[str,Any], now_fn) -> int:
    raw=operator_control.canonical(payload);cur=conn.execute("INSERT INTO operator_swarm_events(session_id,mission_id,event_type,payload_json,payload_digest,observed_at) VALUES(?,?,?,?,?,?)",(session_id,mission_id,event_type,raw,operator_control.digest(payload),now_fn()));return int(cur.lastrowid)


def _mission(conn, mission_id: str):
    row=conn.execute("SELECT * FROM missions WHERE mission_id=?",(mission_id,)).fetchone()
    if row is None: raise ValueError("swarm mission missing")
    return dict(row)


def _session(conn, session_id: str) -> dict[str,Any]:
    row=conn.execute("SELECT * FROM operator_swarm_sessions WHERE session_id=?",(session_id,)).fetchone()
    if row is None: raise ValueError("swarm session missing")
    return dict(row)


def _principal_participant(principal_id: str) -> str:
    if principal_id==operator_control.PRIMARY_OPERATOR:return operator_control.PRIMARY_PARTICIPANT
    if principal_id==operator_control.SENTINELX_PROXY_PRINCIPAL:return operator_control.SENTINELX_PROXY_PARTICIPANT
    raise ValueError("swarm principal denied")


def _active_grant_deadline(conn, principal_id: str, mission_id: str, stamp: str) -> str|None:
    rows=conn.execute("SELECT mission_scope,expires_at,actions_json FROM operator_grants WHERE principal_id=? AND revoked_at IS NULL AND (expires_at IS NULL OR expires_at>?) ORDER BY issued_at DESC",(principal_id,stamp)).fetchall()
    for row in rows:
        if row["mission_scope"] not in {"*",mission_id}:continue
        try:actions=set(json.loads(row["actions_json"]))
        except Exception:actions=set()
        if "MESSAGE" in actions:return row["expires_at"]
    raise ValueError("swarm communication not granted")


def _binding(session_id: str, participant_id: str, session_epoch: int, deadline: str) -> tuple[str,str]:
    material={"session_id":session_id,"participant_id":participant_id,"session_epoch":session_epoch,"deadline":deadline}
    dg=operator_control.digest(material);return "swbind-"+dg[:32],dg


def _join(conn, session: dict[str,Any], participant_id: str, principal_id: str|None, member_kind: str, role: str, now_fn, *, lease_expires_at: str|None=None) -> dict[str,Any]:
    stamp=now_fn();deadline=session["mission_deadline"];lease=lease_expires_at or deadline
    if _parse(lease)>_parse(deadline):lease=deadline
    binding_id,_=_binding(session["session_id"],participant_id,int(session["session_epoch"]),deadline)
    conn.execute("INSERT INTO operator_swarm_members(session_id,participant_id,principal_id,member_kind,role,binding_id,state,joined_at,last_seen_at,lease_expires_at) VALUES(?,?,?,?,?,?,?, ?,?,?) ON CONFLICT(session_id,participant_id) DO UPDATE SET principal_id=excluded.principal_id,member_kind=excluded.member_kind,role=excluded.role,state='ACTIVE',last_seen_at=excluded.last_seen_at,lease_expires_at=excluded.lease_expires_at",(session["session_id"],participant_id,principal_id,member_kind,role,binding_id,"ACTIVE",stamp,stamp,lease))
    conn.execute("INSERT OR IGNORE INTO operator_swarm_cursors VALUES(?,?,0,?)",(session["session_id"],participant_id,stamp))
    return dict(conn.execute("SELECT * FROM operator_swarm_members WHERE session_id=? AND participant_id=?",(session["session_id"],participant_id)).fetchone())


def open_session(conn, principal_id: str, mission_id: str, now_fn, *, duration_seconds: int=MAX_SESSION_SECONDS, workers=None, mode="TWO_DRONE_VERIFY") -> dict[str,Any]:
    if principal_id!=operator_control.PRIMARY_OPERATOR:raise ValueError("only primary operator may open swarm session")
    if type(duration_seconds) is not int or not 60<=duration_seconds<=MAX_SESSION_SECONDS:raise ValueError("swarm session duration")
    if workers is None or workers==() or workers==[]:
        rows=conn.execute("SELECT logical_id FROM material_workers WHERE mission_id=? AND ready=1 ORDER BY logical_id LIMIT 2",(mission_id,)).fetchall()
        workers=[str(r["logical_id"]) for r in rows if r["logical_id"]]
    if not isinstance(workers,(list,tuple)) or len(workers)<2 or len(set(workers))!=len(workers):raise ValueError("swarm workers")
    stamp=now_fn();m=_mission(conn,mission_id)
    ps=conn.execute("SELECT authority_state FROM mission_process_specs WHERE mission_id=?",(mission_id,)).fetchone()
    if not ps or ps["authority_state"]!="EXPLICIT_USER_ACTIVATION":raise ValueError("swarm mission not explicitly activated")
    driver=conn.execute("SELECT generation,state FROM mission_execution_drivers WHERE mission_id=?",(mission_id,)).fetchone()
    if not driver or driver["state"] not in _ACTIVE_DRIVER_STATES:raise ValueError("swarm mission driver not active")
    active=conn.execute("SELECT * FROM operator_swarm_sessions WHERE mission_id=? AND state='ACTIVE' ORDER BY created_at DESC LIMIT 1",(mission_id,)).fetchone()
    if active:
        value=dict(active)
        if _parse(value["mission_deadline"])>_parse(stamp):
            session=_session(conn,value["session_id"])
            existing={r[0] for r in conn.execute("SELECT participant_id FROM operator_swarm_members WHERE session_id=? AND member_kind='MATERIAL_WORKER' AND state='ACTIVE'",(value["session_id"],)).fetchall()}
            for index,worker in enumerate(workers):
                worker=str(worker).strip()
                participant="worker:"+worker
                if participant not in existing:
                    _join(conn,session,participant,None,"MATERIAL_WORKER","PRIMARY" if not existing and index==0 else "VERIFIER",now_fn)
                    existing.add(participant)
            conn.commit()
            return session_snapshot(conn,value["session_id"],principal_id,now_fn)
    activation=stamp;deadline=_parse(stamp)+timedelta(seconds=duration_seconds)
    grant_deadline=_active_grant_deadline(conn,principal_id,mission_id,stamp)
    if grant_deadline and _parse(grant_deadline)<deadline:deadline=_parse(grant_deadline)
    if deadline<=_parse(stamp):raise ValueError("swarm communication grant expired")
    deadline_s=_iso(deadline);sid="swarm-session-"+uuid.uuid4().hex;epoch=1;swarm_id=mission_id
    binding_digest=operator_control.digest({"session_id":sid,"mission_id":mission_id,"swarm_id":swarm_id,"session_epoch":epoch,"deadline":deadline_s})
    conn.execute("INSERT INTO operator_swarm_sessions VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",(sid,mission_id,swarm_id,"ACTIVE",mode,epoch,activation,deadline_s,principal_id,binding_digest,stamp,stamp,None))
    session=_session(conn,sid)
    _join(conn,session,operator_control.PRIMARY_PARTICIPANT,operator_control.PRIMARY_OPERATOR,"HUMAN","PRIMARY_OPERATOR",now_fn)
    proxy=conn.execute("SELECT participant_id FROM operator_participants WHERE principal_id=? AND state='ACTIVE'",(operator_control.SENTINELX_PROXY_PRINCIPAL,)).fetchone()
    if proxy:_join(conn,session,operator_control.SENTINELX_PROXY_PARTICIPANT,operator_control.SENTINELX_PROXY_PRINCIPAL,"TRANSPORT_PROXY","SENTINELX_PROXY",now_fn)
    for index,worker in enumerate(workers):
        worker=str(worker).strip()
        if not worker or len(worker)>96:raise ValueError("swarm worker identity")
        _join(conn,session,"worker:"+worker,None,"MATERIAL_WORKER","PRIMARY" if index==0 else "VERIFIER",now_fn)
    _event(conn,sid,mission_id,"SWARM_SESSION_OPENED",{"session_id":sid,"mission_id":mission_id,"deadline":deadline_s,"workers":list(workers),"authority_effect":"NONE"},now_fn)
    conn.commit();return session_snapshot(conn,sid,principal_id,now_fn)


def ensure_member(conn, session_id: str, principal_id: str, now_fn) -> dict[str,Any]:
    s=_session(conn,session_id);stamp=now_fn();_active_grant_deadline(conn,principal_id,s["mission_id"],stamp);participant=_principal_participant(principal_id)
    row=conn.execute("SELECT * FROM operator_swarm_members WHERE session_id=? AND participant_id=?",(session_id,participant)).fetchone()
    if row is None:return _join(conn,s,participant,principal_id,"HUMAN" if principal_id==operator_control.PRIMARY_OPERATOR else "TRANSPORT_PROXY","PRIMARY_OPERATOR" if principal_id==operator_control.PRIMARY_OPERATOR else "SENTINELX_PROXY",now_fn)
    stamp=now_fn();conn.execute("UPDATE operator_swarm_members SET last_seen_at=?,state='ACTIVE' WHERE session_id=? AND participant_id=?",(stamp,session_id,participant));return dict(conn.execute("SELECT * FROM operator_swarm_members WHERE session_id=? AND participant_id=?",(session_id,participant)).fetchone())


def active_session(conn, principal_id: str, now_fn) -> dict[str,Any]|None:
    participant=_principal_participant(principal_id);stamp=now_fn()
    row=conn.execute("SELECT s.* FROM operator_swarm_sessions s JOIN operator_swarm_members m ON m.session_id=s.session_id WHERE m.participant_id=? AND s.state='ACTIVE' ORDER BY s.created_at DESC LIMIT 1",(participant,)).fetchone()
    if not row:return None
    value=dict(row)
    if _parse(value["mission_deadline"])<=_parse(stamp):
        conn.execute("UPDATE operator_swarm_sessions SET state='EXPIRED',updated_at=?,closed_at=? WHERE session_id=?",(stamp,stamp,value["session_id"]));conn.commit();return None
    return session_snapshot(conn,value["session_id"],principal_id,now_fn)


def _session_guard(conn, session_id: str, principal_id: str, now_fn) -> tuple[dict[str,Any],dict[str,Any]]:
    s=_session(conn,session_id);stamp=now_fn()
    if s["state"]!="ACTIVE":raise ValueError("swarm session not active")
    if _parse(s["mission_deadline"])<=_parse(stamp):
        conn.execute("UPDATE operator_swarm_sessions SET state='EXPIRED',updated_at=?,closed_at=? WHERE session_id=?",(stamp,stamp,session_id));conn.commit();raise ValueError("swarm session expired")
    member=ensure_member(conn,session_id,principal_id,now_fn)
    if member["state"]!="ACTIVE":raise ValueError("swarm membership inactive")
    return s,member


def _general_insert(conn, s: dict[str,Any], *, from_id: str, to_id: str, kind: str, content: str, command_id: str, correlation_id: str|None, causation_id: str|None, now_fn, thread_id: str|None=None) -> dict[str,Any]:
    if kind not in _ALLOWED_TYPES:raise ValueError("swarm message type")
    if not isinstance(content,str) or not content.strip() or len(content.encode("utf-8"))>8192:raise ValueError("swarm message content")
    content=content.strip();stamp=now_fn();payload={"event":kind,"text":content};payload_digest=operator_control.digest(payload)
    envelope_material={"protocol":"OPERATOR","from_id":from_id,"to_id":to_id,"kind":kind,"payload_digest":payload_digest,"session_id":s["session_id"],"mission_id":s["mission_id"],"swarm_id":s["swarm_id"],"correlation_id":correlation_id,"causation_id":causation_id,"session_epoch":s["session_epoch"],"expires_at":s["mission_deadline"]}
    envelope_digest=operator_control.digest(envelope_material);mid="swmsg-"+operator_control.digest({"session_id":s["session_id"],"command_id":command_id,"envelope_digest":envelope_digest})[:32]
    conn.execute("INSERT INTO operator_general_messages(message_id,channel_id,command_id,from_participant,to_participant,kind,content,content_digest,state,created_at,session_id,mission_id,swarm_id,correlation_id,causation_id,session_epoch,expires_at,envelope_digest,thread_id) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(mid,operator_control.GENERAL_CHANNEL_ID,command_id,from_id,to_id,kind,content,operator_control.digest(content),"PERSISTED",stamp,s["session_id"],s["mission_id"],s["swarm_id"],correlation_id,causation_id,int(s["session_epoch"]),s["mission_deadline"],envelope_digest,thread_id))
    return dict(conn.execute("SELECT * FROM operator_general_messages WHERE message_id=?",(mid,)).fetchone())


def _mission_message_direct(conn, s: dict[str,Any], *, from_id: str, target: str, kind: str, content: str, command_id: str, now_fn) -> dict[str,Any]:
    state=operator_control.control_state(conn,s["mission_id"],now_fn);recipients=operator_control.resolve_target(conn,s["mission_id"],target);stamp=now_fn();mid="opmsg-"+operator_control.digest({"session_id":s["session_id"],"command_id":command_id,"target":target})[:32]
    conn.execute("INSERT INTO operator_messages(message_id,mission_id,command_id,from_participant,target,kind,content,content_digest,context_revision,plan_revision,state,created_at,applied_at,applied_assignment_id) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,NULL,NULL)",(mid,s["mission_id"],command_id,from_id,target,kind,content,operator_control.digest(content),int(state["context_revision"]),int(state["plan_revision"]),"PENDING" if recipients else "PERSISTED_NO_CURRENT_RECIPIENT",stamp))
    for r in recipients:conn.execute("INSERT OR IGNORE INTO operator_message_deliveries(message_id,recipient,delivery_state,delivered_at,applied_at,applied_assignment_id) VALUES(?,?,?,NULL,NULL,NULL)",(mid,r,"PERSISTED"))
    return {"message_id":mid,"recipients":recipients}


def _driver_generation(conn, mission_id: str) -> int:
    row=conn.execute("SELECT generation,state FROM mission_execution_drivers WHERE mission_id=?",(mission_id,)).fetchone()
    if not row or row["state"] not in _ACTIVE_DRIVER_STATES:raise ValueError("swarm driver unavailable")
    return int(row["generation"])


def _trusted_participant_context(conn, s: dict[str,Any], material_worker: str, logical_drone: str) -> dict[str,Any]:
    topology=conn.execute("SELECT COUNT(*) AS n FROM mission_execution_assignments WHERE mission_id=? AND phase_id='__TOPOLOGY__' AND material_drone_id=? AND logical_drone_id=?",(s["mission_id"],material_worker,logical_drone)).fetchone()
    return {
      "schema":"lion.communication-participant-context/v1",
      "mission_id":s["mission_id"],
      "swarm_id":s["swarm_id"],
      "cognitive_executor":"model:local",
      "model":"gpt-oss-20b-MXFP4",
      "material_worker":"worker:"+material_worker,
      "logical_drone":"drone:"+logical_drone,
      "topology_binding_observed":bool(topology and int(topology["n"] or 0)>0),
      "operator":"operator:primary",
      "remote_supervisor":"model:saas",
      "control_plane":"mission_control",
      "roles":{
        "model:local":"shared proposal-only cognitive executor",
        "worker:"+material_worker:"bounded material runtime/executor for the current assignment",
        "drone:"+logical_drone:"logical mission role/context; not a physical agent and not a model",
        "operator:primary":"human operator",
        "model:saas":"remote cognitive supervisor",
        "mission_control":"control plane and durable routing/receipt boundary",
      },
      "mediated_communication":True,
      "communication_message_authority_effect":"NONE",
      "authority_note":"authority_effect=NONE describes this communication/model output; it does not redefine the operator-control state of the human operator",
      "communication_paths":[
        "operator:primary->mission_control->drone:"+logical_drone+"->worker:"+material_worker+"->model:local",
        "model:local->worker:"+material_worker+"->mission_control->operator:primary",
        "model:local->mission_control->model:saas",
        "model:saas->mission_control->worker:"+material_worker+"->model:local",
      ],
      "rules":[
        "MODEL_NE_WORKER",
        "MODEL_NE_LOGICAL_DRONE",
        "LOGICAL_DRONE_NE_PHYSICAL_AGENT",
        "WORKER_NE_COGNITIVE_MODEL",
        "COMMUNICATION_NE_AUTHORITY",
        "EFFECTS_REQUIRE_SEPARATE_ADMISSION",
      ],
      "authority_effect":"NONE",
    }


def _context_ref_exists(context: dict[str,Any], prefix: str, ref: str) -> bool:
    marker=prefix+"."
    if not ref.startswith(marker):return False
    value:Any=context
    for part in ref[len(marker):].split("."):
        if not part or not isinstance(value,dict) or part not in value:return False
        value=value[part]
    return True


def _parse_verifier_record(text: str, source_context: dict[str,Any], verifier_context: dict[str,Any]) -> dict[str,Any]:
    raw=str(text or "").strip()
    if raw.startswith("```") and raw.endswith("```"):
        lines=raw.splitlines()
        if len(lines)>=3 and lines[0].strip().lower() in {"```","```json"} and lines[-1].strip()=="```":
            raw="\n".join(lines[1:-1]).strip()
    try:value=json.loads(raw)
    except Exception as exc:raise ValueError("verifier output must be one JSON object") from exc
    if type(value) is not dict or set(value)!={"schema","source_participant","claims","unknowns","summary"}:raise ValueError("verifier record root schema")
    if value["schema"]!=_VERIFIER_SCHEMA:raise ValueError("verifier record schema_version")
    expected_source=str(source_context.get("material_worker") or "")
    if value["source_participant"]!=expected_source:raise ValueError("verifier source participant mismatch")
    claims=value["claims"];unknowns=value["unknowns"];summary=value["summary"]
    if type(claims) is not list or not 1<=len(claims)<=32:raise ValueError("verifier claims")
    if type(unknowns) is not list or len(unknowns)>32 or any(not isinstance(x,str) or not x.strip() for x in unknowns):raise ValueError("verifier unknowns")
    if not isinstance(summary,str) or not summary.strip() or len(summary)>4000:raise ValueError("verifier summary")
    normalized=[]
    for item in claims:
        if type(item) is not dict or set(item)!={"claim","evidence","verdict"}:raise ValueError("verifier claim schema")
        claim=item["claim"];evidence=item["evidence"];verdict=item["verdict"]
        if not isinstance(claim,str) or not claim.strip() or len(claim)>2000:raise ValueError("verifier claim")
        if verdict not in _VERIFIER_VERDICTS:raise ValueError("verifier verdict")
        if type(evidence) is not list or len(evidence)>16:raise ValueError("verifier evidence")
        trusted=False;clean_evidence=[]
        for ev in evidence:
            if type(ev) is not dict or set(ev)!={"class","ref"}:raise ValueError("verifier evidence schema")
            cls=ev["class"];ref=ev["ref"]
            if cls not in _VERIFIER_EVIDENCE_CLASSES or not isinstance(ref,str) or not ref:raise ValueError("verifier evidence class/ref")
            if cls=="TRUSTED_TOPOLOGY_CONTEXT":
                if not (_context_ref_exists(source_context,"TRUSTED_SOURCE_CONTEXT_JSON",ref) or _context_ref_exists(verifier_context,"TRUSTED_VERIFIER_CONTEXT_JSON",ref)):
                    raise ValueError("verifier trusted-context ref")
                trusted=True
            elif cls=="OPERATOR_MESSAGE":
                if ref!="AUTHENTICATED_OPERATOR_MESSAGE":raise ValueError("verifier operator-message ref")
                trusted=True
            elif ref!="UNTRUSTED_PRIMARY_RESPONSE":
                raise ValueError("verifier model-claim ref")
            clean_evidence.append({"class":cls,"ref":ref})
        if verdict!="UNKNOWN" and not trusted:raise ValueError("verifier verdict lacks independent trusted evidence")
        normalized.append({"claim":claim.strip(),"evidence":clean_evidence,"verdict":verdict})
    return {"schema":_VERIFIER_SCHEMA,"source_participant":expected_source,"claims":normalized,"unknowns":[x.strip() for x in unknowns],"summary":summary.strip()}


def _assignment(conn, s: dict[str,Any], *, material_worker: str, mission_message_id: str, stage: str, round_id: str, now_fn, trusted_source_context: dict[str,Any]|None=None) -> str:
    generation=_driver_generation(conn,s["mission_id"])
    logical_rows=conn.execute("SELECT logical_drone_id FROM mission_execution_assignments WHERE mission_id=? AND phase_id='__TOPOLOGY__' AND material_drone_id=? ORDER BY logical_drone_id",(s["mission_id"],material_worker)).fetchall()
    logical_ids=[str(r["logical_drone_id"]) for r in logical_rows if r["logical_drone_id"]]
    logical=(logical_ids[0 if stage=="PRIMARY" else min(1,len(logical_ids)-1)] if logical_ids else ("SWARM_"+material_worker.replace("-","_")+"_"+round_id[-8:]+"_"+stage[:1])[:96])
    trusted_context=_trusted_participant_context(conn,s,material_worker,logical)
    trusted_json=operator_control.canonical(trusted_context)
    ontology=(
        "LION PARTICIPANT ONTOLOGY: model:local is the shared cognitive model and is NOT a logical drone and NOT a material worker. "
        "drone:LDxxx is a logical software role/context; it is NOT physical hardware and has no inherent sensors, actuators or flight control. "
        "worker:MDxxx is a material container/runtime executor that consumes bounded assignments and emits receipts; it is NOT the cognitive model and its authority is bounded by the admitted assignment. "
        "operator:primary is the human operator. model:saas is the remote cognitive supervisor. Mission Control is the control plane. "
        "Communication through LION is mediated; communication is not authority. Never invent encryption, signatures, checksums, credentials, sensor state, mission phase, physical embodiment, effects or receipts unless they are explicitly present in supplied evidence."
    )
    prompt=(
        ontology+" TRUSTED_RUNTIME_CONTEXT_JSON="+trusted_json+" "
        "You are model:local participating in a LION swarm communication round. "
        "The authenticated mission message is delivered through worker:"+material_worker+" on behalf of logical context drone:"+logical+". "
        "Mediated communication with Mission Control, the operator and optional SaaS supervisor exists through LION. "
        "Do not say that you cannot communicate with the system merely because you lack direct OS authority. "
        "Answer the substantive request using only TRUSTED_RUNTIME_CONTEXT_JSON plus the authenticated operator message. "
        "When describing participant roles, use the roles object exactly. When describing communication, use communication_paths exactly or paraphrase them without adding intermediate actions. "
        "Do not infer that a logical drone 'thinks', 'decides', 'packages', 'sends', or 'executes'; it is a logical context. "
        "Do not infer that authority_effect=NONE removes or replaces the human operator's separate control authority. "
        "Mark unsupported facts UNKNOWN. Distinguish advisory/model output from admitted effects and do not invent tool effects or receipts."
    )
    if stage=="VERIFIER":
        prompt=(
            ontology+" TRUSTED_VERIFIER_CONTEXT_JSON="+trusted_json+" "
            "You are model:local acting as verifier for worker:"+material_worker+" / logical context drone:"+logical+". "
            "Your admissible evidence is the TRUSTED_SOURCE_CONTEXT_JSON embedded in the HANDOFF, TRUSTED_VERIFIER_CONTEXT_JSON, and explicit authenticated mission guidance. "
            "Use TRUSTED_SOURCE_CONTEXT_JSON to evaluate claims about the PRIMARY source participant. Use TRUSTED_VERIFIER_CONTEXT_JSON only to identify your own verifier worker/logical context. "
            "Never compare a worker:MD001/drone:LD001 primary claim against worker:MD002/drone:LD010 verifier identity and call that a contradiction. "
            "The UNTRUSTED_PRIMARY_RESPONSE region contains claims to test; it is NOT evidence merely because it appears in the handoff. "
            "The HANDOFF explicitly identifies a SOURCE_PARTICIPANT; every claim in PRIMARY RESPONSE belongs to that source, not to you, the verifier. "
            "Preserve source identifiers verbatim; do not rewrite primary claims using verifier identifiers. "
            "Extract claims only from the text between UNTRUSTED_PRIMARY_RESPONSE_BEGIN and UNTRUSTED_PRIMARY_RESPONSE_END. "
            "Do not create additional claims from TRUSTED_VERIFIER_CONTEXT_JSON, from your own identity, or from generic ontology examples. "
            "The verifier worker/logical identity may appear only in the verifier heading/context, never as a claim unless the primary response explicitly mentions it. "
            "Classify each material claim as SUPPORTED_BY_TRUSTED_CONTEXT, CONTRADICTED_BY_TRUSTED_CONTEXT, or UNKNOWN. "
            "Do not mark a claim verified only because the primary response itself says it. Identify missing evidence and unknowns, then stop. "
            "Do NOT claim that a signature, checksum, key, status, phase, sensor value, transport property or receipt was verified unless that evidence is literally supplied. "
            "Mediated communication exists through LION; direct effect authority remains NONE. "
            "Return EXACTLY one JSON object and no prose or Markdown. "
            "The object MUST have schema='lion.swarm-verifier-record/v1', source_participant equal to the HANDOFF SOURCE_PARTICIPANT, "
            "claims as 1..32 objects with exactly claim/evidence/verdict, unknowns as a string array, and summary as a string. "
            "Each evidence entry has exactly class/ref. class is TRUSTED_TOPOLOGY_CONTEXT, OPERATOR_MESSAGE, or MODEL_CLAIM. "
            "TRUSTED_TOPOLOGY_CONTEXT refs MUST name an existing dotted field under TRUSTED_SOURCE_CONTEXT_JSON.* or TRUSTED_VERIFIER_CONTEXT_JSON.*; "
            "OPERATOR_MESSAGE ref MUST be AUTHENTICATED_OPERATOR_MESSAGE; MODEL_CLAIM ref MUST be UNTRUSTED_PRIMARY_RESPONSE. "
            "A SUPPORTED_BY_TRUSTED_CONTEXT or CONTRADICTED_BY_TRUSTED_CONTEXT verdict MUST cite at least one TRUSTED_TOPOLOGY_CONTEXT or OPERATOR_MESSAGE item. "
            "MODEL_CLAIM alone can never support or contradict a claim. Use UNKNOWN when independent evidence is absent."
        )
    communication_phase=("COMMUNICATION_"+round_id[-12:]+"_"+stage)[:96]
    payload={"kind":"LOCAL_MODEL_INFERENCE","capability":"OPERATOR_SWARM_COMMUNICATION_R1","messages":[{"role":"user","content":prompt}],"max_tokens":768 if stage=="VERIFIER" else 512,"purpose":"OPERATOR_SWARM_"+stage,"trajectory_role":stage,"session_id":s["session_id"],"round_id":round_id,"operator_message_id":mission_message_id,"communication_source":"worker:"+material_worker,"logical_context":"drone:"+logical,"communication_phase":communication_phase,"trusted_participant_context":trusted_context,"trusted_source_context":trusted_source_context if stage=="VERIFIER" else None,"evidence_classes":["TRUSTED_TOPOLOGY_CONTEXT","OPERATOR_MESSAGE","MODEL_CLAIM"] if stage=="VERIFIER" else ["TRUSTED_TOPOLOGY_CONTEXT","OPERATOR_MESSAGE"]}
    return global_scheduler.create_assignment(conn,s["mission_id"],communication_phase,logical,material_worker,payload,now_fn,lease_generation=generation,dispatch_authority="AUTONOMOUS")


def send_message(conn, principal_id: str, session_id: str, command_id: str, target: str, content: str, now_fn, *, kind="REQUEST", correlation_id=None, causation_id=None, thread_id=None, verifier_worker=None) -> dict[str,Any]:
    s,member=_session_guard(conn,session_id,principal_id,now_fn)
    if not isinstance(command_id,str) or not command_id.strip() or len(command_id)>192:raise ValueError("swarm command_id")
    existing=conn.execute("SELECT * FROM operator_general_messages WHERE command_id=?",(command_id,)).fetchone()
    if existing:
        if existing["session_id"]!=session_id or existing["content_digest"]!=operator_control.digest(content.strip()):raise ValueError("swarm command_id conflict")
        return {"schema":"lion.operator-swarm-send/v1","idempotent":True,"message":_envelope(dict(existing)),"authority_effect":"NONE"}
    target=str(target or "").strip()
    if target==ASSISTANT_PARTICIPANT:
        assistant=conn.execute("SELECT 1 FROM operator_swarm_members WHERE session_id=? AND participant_id=? AND state='ACTIVE'",(session_id,ASSISTANT_PARTICIPANT)).fetchone()
        if assistant is None:raise ValueError("assistant not attached")
        root=_general_insert(conn,s,from_id=member["participant_id"],to_id=ASSISTANT_PARTICIPANT,kind=kind,content=content,command_id=command_id,correlation_id=correlation_id,causation_id=causation_id,now_fn=now_fn,thread_id=thread_id)
        conn.execute("INSERT OR IGNORE INTO operator_general_deliveries(message_id,recipient,delivery_state,delivered_at,receipt_digest) VALUES(?,?,?,NULL,NULL)",(root["message_id"],ASSISTANT_PARTICIPANT,"PERSISTED"))
        _event(conn,session_id,s["mission_id"],"SWARM_ASSISTANT_REQUEST_PERSISTED",{"message_id":root["message_id"],"from":member["participant_id"],"to":ASSISTANT_PARTICIPANT,"authority_effect":"NONE"},now_fn)
        conn.commit();return {"schema":"lion.operator-swarm-send/v1","idempotent":False,"session_id":session_id,"round_id":None,"message":_envelope(root),"assignments":[],"authority_effect":"NONE"}
    members=[dict(r) for r in conn.execute("SELECT * FROM operator_swarm_members WHERE session_id=? AND member_kind='MATERIAL_WORKER' AND state='ACTIVE' ORDER BY role,participant_id",(session_id,)).fetchall()]
    allowed={m["participant_id"] for m in members}
    if target.startswith("worker:"):selected=[target] if target in allowed else []
    elif target.startswith("drone:"):
        ident=target.split(":",1)[1]
        legacy_worker="worker:"+ident
        if legacy_worker in allowed:
            selected=[legacy_worker]  # legacy drone:MDxxx alias
        else:
            # Logical drone target: resolve its bound material worker and route
            # to the canonical worker participant in this session.
            row=conn.execute("SELECT material_drone_id FROM mission_execution_assignments WHERE mission_id=? AND phase_id='__TOPOLOGY__' AND logical_drone_id=? ORDER BY assignment_id LIMIT 1",(s["mission_id"],ident)).fetchone()
            canonical=("worker:"+str(row["material_drone_id"])) if row and row["material_drone_id"] else None
            selected=[canonical] if canonical in allowed else []
    elif target in {"swarm:"+s["swarm_id"],"mission:"+s["mission_id"]}:selected=sorted(allowed)
    else:raise ValueError("swarm target")
    if not selected:raise ValueError("swarm target has no active recipient")
    root=_general_insert(conn,s,from_id=member["participant_id"],to_id=target,kind=kind,content=content,command_id=command_id,correlation_id=correlation_id,causation_id=causation_id,now_fn=now_fn,thread_id=thread_id)
    for recipient in selected:conn.execute("INSERT OR IGNORE INTO operator_general_deliveries(message_id,recipient,delivery_state,delivered_at,receipt_digest) VALUES(?,?,?,NULL,NULL)",(root["message_id"],recipient,"PERSISTED"))
    round_id="swround-"+uuid.uuid4().hex;primary=selected[0].split(":",1)[1]
    verifier=None
    if verifier_worker is not None:
        candidate=str(verifier_worker).strip()
        if candidate and candidate!=primary and ("worker:"+candidate) in allowed:verifier=candidate
        elif candidate:raise ValueError("swarm verifier unavailable")
    if verifier is None:
        verifier=next((m["participant_id"].split(":",1)[1] for m in members if m["participant_id"]!=selected[0]),None)
    conn.execute("INSERT INTO operator_swarm_rounds VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",(round_id,session_id,root["message_id"],primary,verifier,None,None,None,None,"DISPATCHING",now_fn(),now_fn()))
    conn.commit()  # preserve canonical envelope before bounded command admission
    for index,recipient in enumerate(selected):
        worker=recipient.split(":",1)[1];mcid=command_id+"-"+worker
        command={"command_id":mcid,"mission_id":s["mission_id"],"action":"MESSAGE","target":recipient,"payload":{"content":content},"correlation_id":root["message_id"],"causation_id":causation_id}
        operator_control.apply_command(conn,command,now_fn,principal_id=principal_id)
        mrow=conn.execute("SELECT message_id FROM operator_messages WHERE mission_id=? AND command_id=?",(s["mission_id"],mcid)).fetchone()
        if not mrow:raise ValueError("swarm mission message missing")
        aid=_assignment(conn,s,material_worker=worker,mission_message_id=mrow["message_id"],stage="PRIMARY",round_id=round_id,now_fn=now_fn)
        did="swdispatch-"+uuid.uuid4().hex;conn.execute("INSERT INTO operator_swarm_dispatches VALUES(?,?,?,?,?,?,?,?,?,?,?)",(did,session_id,round_id,root["message_id"],mrow["message_id"],aid,recipient,"PRIMARY","READY",now_fn(),None))
        if index==0:conn.execute("UPDATE operator_swarm_rounds SET primary_assignment_id=?,state='PRIMARY_DISPATCHED',updated_at=? WHERE round_id=?",(aid,now_fn(),round_id))
    _event(conn,session_id,s["mission_id"],"SWARM_REQUEST_DISPATCHED",{"session_id":session_id,"round_id":round_id,"message_id":root["message_id"],"target":target,"recipients":selected,"authority_effect":"NONE"},now_fn)
    conn.commit();return {"schema":"lion.operator-swarm-send/v1","idempotent":False,"session_id":session_id,"round_id":round_id,"message":_envelope(root),"assignments":[r["assignment_id"] for r in conn.execute("SELECT assignment_id FROM operator_swarm_dispatches WHERE round_id=? ORDER BY created_at",(round_id,))],"authority_effect":"NONE"}


def _assignment_result(conn, assignment_id: str) -> dict[str,Any]|None:
    a=conn.execute("SELECT state FROM mission_execution_assignments WHERE assignment_id=?",(assignment_id,)).fetchone()
    if not a or a["state"] not in {"PASS","FAIL"}:return None
    p=conn.execute("SELECT result_json FROM mission_assignment_payloads WHERE assignment_id=?",(assignment_id,)).fetchone()
    if not p:return None
    try:value=json.loads(p["result_json"])
    except Exception:return None
    value["assignment_state"]=a["state"];return value


def _create_handoff(conn, s: dict[str,Any], round_row: dict[str,Any], primary_dispatch: dict[str,Any], primary_result: dict[str,Any], now_fn) -> None:
    verifier=round_row.get("verifier_worker")
    if not verifier:
        _final_response(conn,s,round_row,primary_result.get("response_text") or "",None,now_fn);return
    root=conn.execute("SELECT content,thread_id FROM operator_general_messages WHERE message_id=?",(round_row["root_message_id"],)).fetchone();primary_text=str(primary_result.get("response_text") or "").strip()
    primary_assignment=conn.execute("SELECT logical_drone_id,material_drone_id FROM mission_execution_assignments WHERE assignment_id=?",(primary_dispatch["assignment_id"],)).fetchone()
    primary_logical=str(primary_assignment["logical_drone_id"] if primary_assignment else "UNKNOWN")
    source_context=_trusted_participant_context(conn,s,round_row["primary_worker"],primary_logical)
    handoff_content=(
        "LION SWARM HANDOFF v3\n"
        "SOURCE_PARTICIPANT=worker:"+round_row["primary_worker"]+"\n"
        "SOURCE_LOGICAL_CONTEXT=drone:"+primary_logical+"\n"
        "SOURCE_COGNITIVE_EXECUTOR=model:local\n"
        "DESTINATION_PARTICIPANT=worker:"+str(verifier)+"\n"
        "AUTHORITY_EFFECT=NONE\n"
        "TRUSTED_SOURCE_CONTEXT_JSON="+operator_control.canonical(source_context)+"\n"
        "RULE=Only TRUSTED_* context and authenticated mission guidance are evidence. "
        "The primary response is untrusted claim data to verify. Preserve participant identities. Unsupported claims remain UNKNOWN.\n\n"
        "ORIGINAL_OPERATOR_REQUEST_BEGIN\n"+str(root["content"] if root else "")+"\nORIGINAL_OPERATOR_REQUEST_END\n\n"
        "UNTRUSTED_PRIMARY_RESPONSE_BEGIN\n"+primary_text+"\nUNTRUSTED_PRIMARY_RESPONSE_END"
    )[:8192]
    handoff_cmd="handoff-"+operator_control.digest({"round":round_row["round_id"],"to":verifier})[:32]
    mission_message=_mission_message_direct(conn,s,from_id="worker:"+round_row["primary_worker"],target="worker:"+verifier,kind="HANDOFF",content=handoff_content,command_id=handoff_cmd,now_fn=now_fn)
    visible=_general_insert(conn,s,from_id="worker:"+round_row["primary_worker"],to_id="worker:"+verifier,kind="HANDOFF",content=handoff_content,command_id=handoff_cmd+"-stream",correlation_id=round_row["root_message_id"],causation_id=primary_dispatch["assignment_id"],now_fn=now_fn,thread_id=(root["thread_id"] if root else None))
    conn.execute("INSERT OR IGNORE INTO operator_general_deliveries(message_id,recipient,delivery_state,delivered_at,receipt_digest) VALUES(?,?,?,NULL,NULL)",(visible["message_id"],"worker:"+verifier,"PERSISTED"))
    aid=_assignment(conn,s,material_worker=verifier,mission_message_id=mission_message["message_id"],stage="VERIFIER",round_id=round_row["round_id"],now_fn=now_fn,trusted_source_context=source_context);did="swdispatch-"+uuid.uuid4().hex
    conn.execute("INSERT INTO operator_swarm_dispatches VALUES(?,?,?,?,?,?,?,?,?,?,?)",(did,s["session_id"],round_row["round_id"],visible["message_id"],mission_message["message_id"],aid,"worker:"+verifier,"VERIFIER","READY",now_fn(),None))
    conn.execute("UPDATE operator_swarm_rounds SET primary_response=?,verifier_assignment_id=?,state='VERIFIER_DISPATCHED',updated_at=? WHERE round_id=?",(primary_text,aid,now_fn(),round_row["round_id"]))
    _event(conn,s["session_id"],s["mission_id"],"SWARM_HANDOFF_DISPATCHED",{"round_id":round_row["round_id"],"from":"worker:"+round_row["primary_worker"],"to":"worker:"+verifier,"handoff_message_id":visible["message_id"],"assignment_id":aid,"authority_effect":"NONE"},now_fn)


def _final_response(conn, s: dict[str,Any], round_row: dict[str,Any], primary_text: str, verifier_text: str|None, now_fn) -> dict[str,Any]:
    pa=conn.execute("SELECT logical_drone_id,material_drone_id FROM mission_execution_assignments WHERE assignment_id=?",(round_row.get("primary_assignment_id"),)).fetchone()
    primary_logical=str(pa["logical_drone_id"] if pa else "UNKNOWN")
    content=("PRIMARY [worker:"+str(round_row["primary_worker"])+" | drone:"+primary_logical+" | model:local]\n"+primary_text.strip())[:8192]
    from_id="worker:"+round_row["primary_worker"]
    if verifier_text is not None:
        va=conn.execute("SELECT logical_drone_id,material_drone_id FROM mission_execution_assignments WHERE assignment_id=?",(round_row.get("verifier_assignment_id"),)).fetchone()
        verifier_logical=str(va["logical_drone_id"] if va else "UNKNOWN")
        content=(content+"\n\nVERIFIER [worker:"+str(round_row.get("verifier_worker") or round_row["primary_worker"])+" | drone:"+verifier_logical+" | model:local]\n"+verifier_text.strip())[:8192]
        from_id="worker:"+str(round_row.get("verifier_worker") or round_row["primary_worker"])
    cmd="response-"+operator_control.digest({"round":round_row["round_id"],"content":content})[:32]
    root=conn.execute("SELECT thread_id FROM operator_general_messages WHERE message_id=?",(round_row["root_message_id"],)).fetchone();msg=_general_insert(conn,s,from_id=from_id,to_id=operator_control.PRIMARY_PARTICIPANT,kind="RESPONSE",content=content,command_id=cmd,correlation_id=round_row["root_message_id"],causation_id=round_row.get("verifier_assignment_id") or round_row.get("primary_assignment_id"),now_fn=now_fn,thread_id=(root["thread_id"] if root else None))
    conn.execute("INSERT OR IGNORE INTO operator_general_deliveries(message_id,recipient,delivery_state,delivered_at,receipt_digest) VALUES(?,?,?,NULL,NULL)",(msg["message_id"],operator_control.PRIMARY_PARTICIPANT,"PERSISTED"))
    conn.execute("UPDATE operator_swarm_rounds SET verifier_response=?,state='COMPLETE',updated_at=? WHERE round_id=?",(verifier_text,now_fn(),round_row["round_id"]))
    _event(conn,s["session_id"],s["mission_id"],"SWARM_ROUND_COMPLETE",{"round_id":round_row["round_id"],"response_message_id":msg["message_id"],"authority_effect":"NONE"},now_fn);return msg


def reconcile_session(conn, session_id: str, now_fn) -> dict[str,Any]:
    s=_session(conn,session_id);processed=0;handoffs=0;responses=0
    rows=[dict(r) for r in conn.execute("SELECT * FROM operator_swarm_dispatches WHERE session_id=? AND state='READY' ORDER BY created_at,dispatch_id",(session_id,)).fetchall()]
    for d in rows:
        result=_assignment_result(conn,d["assignment_id"])
        if result is None:continue
        ids=result.get("operator_message_ids") or []
        if d["mission_message_id"] not in ids:
            conn.execute("UPDATE operator_swarm_dispatches SET state='FAILED_BINDING',completed_at=? WHERE dispatch_id=?",(now_fn(),d["dispatch_id"]));_event(conn,session_id,s["mission_id"],"SWARM_ASSIGNMENT_BINDING_FAIL",{"assignment_id":d["assignment_id"],"required_message_id":d["mission_message_id"],"observed_message_ids":ids,"authority_effect":"NONE"},now_fn);processed+=1;continue
        stamp=now_fn();conn.execute("UPDATE operator_swarm_dispatches SET state='COMPLETE',completed_at=? WHERE dispatch_id=?",(stamp,d["dispatch_id"]));conn.execute("UPDATE operator_general_deliveries SET delivery_state='CONSUMED',delivered_at=COALESCE(delivered_at,?) WHERE message_id=? AND recipient=? AND delivery_state IN ('PERSISTED','DELIVERED')",(stamp,d["root_message_id"],d["recipient"]));rr=dict(conn.execute("SELECT * FROM operator_swarm_rounds WHERE round_id=?",(d["round_id"],)).fetchone());processed+=1
        if result.get("assignment_state")!="PASS":
            conn.execute("UPDATE operator_swarm_rounds SET state='FAILED',updated_at=? WHERE round_id=?",(now_fn(),d["round_id"]));continue
        if d["stage"]=="PRIMARY":_create_handoff(conn,s,rr,d,result,now_fn);handoffs+=1
        else:
            primary=str(rr.get("primary_response") or "");verifier_raw=str(result.get("response_text") or "")
            assignment=conn.execute("SELECT input_json FROM mission_execution_assignments WHERE assignment_id=?",(d["assignment_id"],)).fetchone()
            try:
                verifier_input=json.loads(assignment["input_json"] if assignment else "{}")
                source_context=verifier_input.get("trusted_source_context") or {}
                verifier_context=verifier_input.get("trusted_participant_context") or {}
                verifier_record=_parse_verifier_record(verifier_raw,source_context,verifier_context)
            except Exception as exc:
                conn.execute("UPDATE operator_swarm_dispatches SET state='FAILED_VERIFIER_SCHEMA',completed_at=? WHERE dispatch_id=?",(now_fn(),d["dispatch_id"]))
                conn.execute("UPDATE operator_swarm_rounds SET verifier_response=?,state='FAILED_VERIFIER_SCHEMA',updated_at=? WHERE round_id=?",(verifier_raw[:8192],now_fn(),d["round_id"]))
                _event(conn,session_id,s["mission_id"],"SWARM_VERIFIER_SCHEMA_FAIL",{"round_id":d["round_id"],"assignment_id":d["assignment_id"],"error":type(exc).__name__+":"+str(exc)[:400],"authority_effect":"NONE"},now_fn)
                continue
            verifier=operator_control.canonical(verifier_record)
            _event(conn,session_id,s["mission_id"],"SWARM_VERIFIER_RECORD_ACCEPTED",{"round_id":d["round_id"],"assignment_id":d["assignment_id"],"record_digest":operator_control.digest(verifier_record),"source_participant":verifier_record["source_participant"],"claim_count":len(verifier_record["claims"]),"authority_effect":"NONE"},now_fn)
            _final_response(conn,s,rr,primary,verifier,now_fn);responses+=1
    if processed:conn.commit()
    return {"processed":processed,"handoffs":handoffs,"responses":responses,"authority_effect":"NONE"}


def _envelope(row: dict[str,Any], delivery_state: str|None=None) -> dict[str,Any]:
    payload={"event":str(row.get("kind") or "MESSAGE"),"text":str(row.get("content") or "")}
    return {"id":row.get("message_id"),"sequence":int(row.get("sequence") or 0),"observed_at":row.get("created_at"),"protocol":"OPERATOR","from_id":row.get("from_participant"),"to_id":row.get("to_participant"),"phase":"COMMUNICATION_WINDOW","direction":"INTERNAL","session_id":row.get("session_id"),"mission_id":row.get("mission_id"),"swarm_id":row.get("swarm_id"),"correlation_id":row.get("correlation_id"),"causation_id":row.get("causation_id"),"session_epoch":row.get("session_epoch"),"expires_at":row.get("expires_at"),"payload":payload,"payload_digest":operator_control.digest(payload),"envelope_digest":row.get("envelope_digest"),"thread_id":row.get("thread_id"),"delivery_state":delivery_state or row.get("state") or "PERSISTED"}


def session_stream(conn, session_id: str, principal_id: str, now_fn, *, after=0, limit=25) -> dict[str,Any]:
    if type(after) is not int or after<0 or type(limit) is not int or not 1<=limit<=25:raise ValueError("swarm cursor")
    s,member=_session_guard(conn,session_id,principal_id,now_fn);reconcile_session(conn,session_id,now_fn)
    rows=conn.execute("SELECT * FROM operator_general_messages WHERE session_id=? AND sequence>? ORDER BY sequence LIMIT ?",(session_id,after,limit)).fetchall();messages=[];stamp=now_fn()
    for raw in rows:
        row=dict(raw);delivery=None
        if row["to_participant"]==member["participant_id"]:
            d=conn.execute("SELECT * FROM operator_general_deliveries WHERE message_id=? AND recipient=?",(row["message_id"],member["participant_id"])).fetchone()
            if d and d["delivery_state"]=="PERSISTED":conn.execute("UPDATE operator_general_deliveries SET delivery_state='DELIVERED',delivered_at=COALESCE(delivered_at,?) WHERE message_id=? AND recipient=?",(stamp,row["message_id"],member["participant_id"]));delivery="DELIVERED"
            elif d:delivery=d["delivery_state"]
        messages.append(_envelope(row,delivery))
    cursor=messages[-1]["sequence"] if messages else after
    conn.execute("UPDATE operator_swarm_cursors SET sequence=CASE WHEN sequence<? THEN ? ELSE sequence END,updated_at=? WHERE session_id=? AND participant_id=?",(cursor,cursor,stamp,session_id,member["participant_id"]));conn.execute("UPDATE operator_swarm_members SET last_seen_at=? WHERE session_id=? AND participant_id=?",(stamp,session_id,member["participant_id"]));conn.commit()
    return {"schema":"lion.operator-swarm-stream/v1","session_id":session_id,"mission_id":s["mission_id"],"swarm_id":s["swarm_id"],"state":s["state"],"participant_id":member["participant_id"],"mission_deadline":s["mission_deadline"],"session_epoch":s["session_epoch"],"messages":messages,"next_cursor":cursor,"authority_effect":"NONE"}



def assistant_stream(conn, session_id: str, principal_id: str, now_fn, *, after=0, limit=25) -> dict[str,Any]:
    if principal_id!=operator_control.SENTINELX_PROXY_PRINCIPAL:raise ValueError("assistant read requires SentinelX proxy")
    if type(after) is not int or after<0 or type(limit) is not int or not 1<=limit<=25:raise ValueError("swarm cursor")
    s,_=_session_guard(conn,session_id,principal_id,now_fn);assistant=conn.execute("SELECT * FROM operator_swarm_members WHERE session_id=? AND participant_id=? AND state='ACTIVE'",(session_id,ASSISTANT_PARTICIPANT)).fetchone()
    if assistant is None:raise ValueError("assistant not attached")
    reconcile_session(conn,session_id,now_fn)
    rows=conn.execute("SELECT * FROM operator_general_messages WHERE session_id=? AND sequence>? ORDER BY sequence LIMIT ?",(session_id,after,limit)).fetchall();messages=[];stamp=now_fn()
    for raw in rows:
        row=dict(raw);delivery=None
        if row["to_participant"]==ASSISTANT_PARTICIPANT:
            d=conn.execute("SELECT * FROM operator_general_deliveries WHERE message_id=? AND recipient=?",(row["message_id"],ASSISTANT_PARTICIPANT)).fetchone()
            if d and d["delivery_state"]=="PERSISTED":
                conn.execute("UPDATE operator_general_deliveries SET delivery_state='DELIVERED',delivered_at=COALESCE(delivered_at,?) WHERE message_id=? AND recipient=?",(stamp,row["message_id"],ASSISTANT_PARTICIPANT));delivery="DELIVERED"
            elif d:delivery=d["delivery_state"]
        messages.append(_envelope(row,delivery))
    cursor=messages[-1]["sequence"] if messages else after
    conn.execute("UPDATE operator_swarm_cursors SET sequence=CASE WHEN sequence<? THEN ? ELSE sequence END,updated_at=? WHERE session_id=? AND participant_id=?",(cursor,cursor,stamp,session_id,ASSISTANT_PARTICIPANT))
    conn.execute("UPDATE operator_swarm_members SET last_seen_at=? WHERE session_id=? AND participant_id=?",(stamp,session_id,ASSISTANT_PARTICIPANT));conn.commit()
    return {"schema":"lion.operator-swarm-assistant-stream/v1","session_id":session_id,"mission_id":s["mission_id"],"swarm_id":s["swarm_id"],"state":s["state"],"participant_id":ASSISTANT_PARTICIPANT,"mission_deadline":s["mission_deadline"],"session_epoch":s["session_epoch"],"messages":messages,"next_cursor":cursor,"authority_effect":"NONE"}

def session_snapshot(conn, session_id: str, principal_id: str, now_fn) -> dict[str,Any]:
    s=_session(conn,session_id);participant=_principal_participant(principal_id);member=conn.execute("SELECT * FROM operator_swarm_members WHERE session_id=? AND participant_id=?",(session_id,participant)).fetchone()
    if member is None:member=_join(conn,s,participant,principal_id,"HUMAN" if principal_id==operator_control.PRIMARY_OPERATOR else "TRANSPORT_PROXY","PRIMARY_OPERATOR" if principal_id==operator_control.PRIMARY_OPERATOR else "SENTINELX_PROXY",now_fn);conn.commit()
    members=[dict(r) for r in conn.execute("SELECT * FROM operator_swarm_members WHERE session_id=? ORDER BY member_kind,participant_id",(session_id,)).fetchall()];rounds=[dict(r) for r in conn.execute("SELECT * FROM operator_swarm_rounds WHERE session_id=? ORDER BY created_at",(session_id,)).fetchall()]
    return {"schema":SCHEMA_ID,"session":s,"participant":dict(member),"members":members,"rounds":rounds,"authority_effect":"NONE"}



ASSISTANT_PARTICIPANT = "assistant:chatgpt"


def attach_assistant(conn, principal_id: str, session_id: str, now_fn, *, model_identity: str="UNKNOWN") -> dict[str,Any]:
    if principal_id!=operator_control.SENTINELX_PROXY_PRINCIPAL:raise ValueError("assistant attach requires SentinelX proxy")
    s,_=_session_guard(conn,session_id,principal_id,now_fn)
    if not isinstance(model_identity,str) or not model_identity.strip() or len(model_identity)>120:raise ValueError("assistant model identity")
    member=_join(conn,s,ASSISTANT_PARTICIPANT,principal_id,"COGNITIVE_ASSISTANT","REMOTE_COGNITIVE_PARTICIPANT",now_fn)
    _event(conn,session_id,s["mission_id"],"SWARM_ASSISTANT_ATTACHED",{"session_id":session_id,"participant_id":ASSISTANT_PARTICIPANT,"transport_participant":operator_control.SENTINELX_PROXY_PARTICIPANT,"model_identity":model_identity.strip(),"authority_effect":"NONE"},now_fn)
    conn.commit()
    out=session_snapshot(conn,session_id,principal_id,now_fn);out["assistant"]={"participant_id":ASSISTANT_PARTICIPANT,"model_identity":model_identity.strip(),"authority_effect":"NONE"};return out


def assistant_send(conn, principal_id: str, session_id: str, command_id: str, target: str, content: str, now_fn, *, kind="MESSAGE", correlation_id=None, causation_id=None, thread_id=None) -> dict[str,Any]:
    if principal_id!=operator_control.SENTINELX_PROXY_PRINCIPAL:raise ValueError("assistant send requires SentinelX proxy")
    s,_=_session_guard(conn,session_id,principal_id,now_fn)
    assistant=conn.execute("SELECT * FROM operator_swarm_members WHERE session_id=? AND participant_id=? AND state='ACTIVE'",(session_id,ASSISTANT_PARTICIPANT)).fetchone()
    if assistant is None:raise ValueError("assistant not attached")
    if not isinstance(command_id,str) or not command_id.strip() or len(command_id)>192:raise ValueError("swarm command_id")
    existing=conn.execute("SELECT * FROM operator_general_messages WHERE command_id=?",(command_id,)).fetchone()
    if existing:
        if existing["session_id"]!=session_id or existing["content_digest"]!=operator_control.digest(content.strip()):raise ValueError("swarm command_id conflict")
        return {"schema":"lion.operator-swarm-assistant-send/v1","idempotent":True,"message":_envelope(dict(existing)),"authority_effect":"NONE"}
    allowed_targets={operator_control.PRIMARY_PARTICIPANT,operator_control.SENTINELX_PROXY_PARTICIPANT}
    allowed_targets.update(r[0] for r in conn.execute("SELECT participant_id FROM operator_swarm_members WHERE session_id=? AND member_kind='MATERIAL_WORKER' AND state='ACTIVE'",(session_id,)).fetchall())
    if target not in allowed_targets:raise ValueError("assistant target")
    msg=_general_insert(conn,s,from_id=ASSISTANT_PARTICIPANT,to_id=target,kind=kind,content=content,command_id=command_id,correlation_id=correlation_id,causation_id=causation_id,now_fn=now_fn,thread_id=thread_id)
    conn.execute("INSERT OR IGNORE INTO operator_general_deliveries(message_id,recipient,delivery_state,delivered_at,receipt_digest) VALUES(?,?,?,NULL,NULL)",(msg["message_id"],target,"PERSISTED"))
    _event(conn,session_id,s["mission_id"],"SWARM_ASSISTANT_MESSAGE",{"message_id":msg["message_id"],"from":ASSISTANT_PARTICIPANT,"to":target,"kind":kind,"authority_effect":"NONE"},now_fn)
    conn.commit();return {"schema":"lion.operator-swarm-assistant-send/v1","idempotent":False,"message":_envelope(msg),"authority_effect":"NONE"}

def close_session(conn, session_id: str, principal_id: str, now_fn) -> dict[str,Any]:
    s,member=_session_guard(conn,session_id,principal_id,now_fn)
    if principal_id!=operator_control.PRIMARY_OPERATOR:raise ValueError("only primary operator may close swarm session")
    stamp=now_fn();conn.execute("UPDATE operator_swarm_sessions SET state='CLOSED',updated_at=?,closed_at=? WHERE session_id=?",(stamp,stamp,session_id));conn.execute("UPDATE operator_swarm_members SET state='LEFT',last_seen_at=? WHERE session_id=?",(stamp,session_id));_event(conn,session_id,s["mission_id"],"SWARM_SESSION_CLOSED",{"session_id":session_id,"authority_effect":"NONE"},now_fn);conn.commit();return session_snapshot(conn,session_id,principal_id,now_fn)


def phase_evidence(conn, mission_id: str, phase_id: str, now_fn) -> tuple[bool,dict[str,Any]]:
    row=conn.execute("SELECT * FROM operator_swarm_sessions WHERE mission_id=? ORDER BY created_at DESC LIMIT 1",(mission_id,)).fetchone();session=dict(row) if row else None
    active=bool(session and session["state"]=='ACTIVE' and _parse(session["mission_deadline"])>_parse(now_fn()))
    complete_rounds=0
    if session:complete_rounds=int(conn.execute("SELECT COUNT(*) FROM operator_swarm_rounds WHERE session_id=? AND state='COMPLETE'",(session["session_id"],)).fetchone()[0])
    if phase_id=='SESSION_BOOTSTRAP':ok=active
    elif phase_id=='TWO_DRONE_ROUNDTRIP':ok=complete_rounds>=1
    elif phase_id=='OPERATOR_FOLLOWUP':ok=complete_rounds>=2
    elif phase_id=='COMMUNICATION_WINDOW':ok=bool(session and session["state"] in {'CLOSED','EXPIRED'})
    else:ok=False
    evidence={"mission_id":mission_id,"phase_id":phase_id,"session_id":session.get("session_id") if session else None,"session_state":session.get("state") if session else None,"mission_deadline":session.get("mission_deadline") if session else None,"complete_rounds":complete_rounds,"predicate":"PASS" if ok else "WAITING","authority_effect":"NONE"}
    return ok,evidence
