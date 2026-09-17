from __future__ import annotations

import hashlib
import json
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from cyber_lion.mission_control.supervisor_projection import supervisor_projection

SCHEMA_VERSION = 8
SCHEMA_ID = "lion.saas-broker/v1"
TRANSPORT = "CHATGPT_SENTINELX_SESSION_MEDIATED"  # read-only legacy/manual compatibility
ATTESTATION_CLASS = "OPERATOR_SESSION_PLUS_CONNECTOR_ROUNDTRIP"
CONTROL_TRANSPORT = "SENTINELX_OPERATOR_CONTROL"
DIRECT_TRANSPORT = "OPENAI_RESPONSES_API_MEDIATED"
DIRECT_ATTESTATION_CLASS = "OPENAI_RESPONSES_API_RECEIPT"
DIRECT_PROVIDER = "OPENAI"
FIREFOX_TRANSPORT = "CHATGPT_FIREFOX_PROJECT_MEDIATED"
FIREFOX_ATTESTATION_CLASS = "FIREFOX_UI_PROJECT_BOUND_OBSERVATION"
FIREFOX_PROVIDER = "CHATGPT_UI"
MEDIATOR_HEARTBEAT_TTL_SECONDS = 45
SUPPORTED_TRANSPORT_ATTESTATIONS = {
    TRANSPORT: ATTESTATION_CLASS,
    DIRECT_TRANSPORT: DIRECT_ATTESTATION_CLASS,
    FIREFOX_TRANSPORT: FIREFOX_ATTESTATION_CLASS,
}

DDL = r"""
CREATE TABLE IF NOT EXISTS saas_session_bindings(
  binding_id TEXT PRIMARY KEY,
  mission_id TEXT,
  lpcl_digest TEXT,
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
  mission_id TEXT,
  lpcl_digest TEXT,
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
  retry_of_request_id TEXT,
  scope_type TEXT NOT NULL DEFAULT 'MISSION',
  scope_id TEXT,
  thread_id TEXT,
  transport TEXT,
  control_transport TEXT,
  inference_transport TEXT,
  provider TEXT,
  provider_conversation_id TEXT,
  provider_response_id TEXT,
  authority_effect TEXT NOT NULL DEFAULT 'NONE',
  claim_generation INTEGER NOT NULL DEFAULT 0,
  claim_expires_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_saas_request_mission ON saas_handoff_requests(mission_id,status,created_at);
CREATE TABLE IF NOT EXISTS saas_direct_bridge_heartbeats(
  bridge_id TEXT PRIMARY KEY,
  state TEXT NOT NULL,
  provider TEXT NOT NULL,
  model_id TEXT,
  credential_state TEXT NOT NULL,
  observed_at TEXT NOT NULL,
  details_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS saas_mediator_heartbeats(
  mediator_id TEXT PRIMARY KEY,
  transport TEXT NOT NULL,
  state TEXT NOT NULL,
  project_title TEXT,
  chat_title TEXT,
  browser TEXT,
  observed_at TEXT NOT NULL,
  details_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS saas_transport_transitions(
  transition_id TEXT PRIMARY KEY,
  request_id TEXT NOT NULL,
  from_transport TEXT NOT NULL,
  to_transport TEXT NOT NULL,
  reason TEXT NOT NULL,
  transitioned_at TEXT NOT NULL,
  authority_effect TEXT NOT NULL,
  transition_digest TEXT NOT NULL UNIQUE
);
CREATE TRIGGER IF NOT EXISTS saas_transport_transition_immutable BEFORE UPDATE ON saas_transport_transitions
BEGIN SELECT RAISE(ABORT,'immutable SaaS transport transition'); END;
"""


def _canon(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def _digest(value):
    return hashlib.sha256(_canon(value).encode("utf-8")).hexdigest()


def _parse_ts(value):
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def _future(stamp, seconds):
    return (_parse_ts(stamp) + timedelta(seconds=int(seconds))).astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _record_transport_transition(conn,row,to_transport,reason,stamp):
    from_transport=row['inference_transport'] or row['transport'] or TRANSPORT
    if from_transport==to_transport:return None
    value={"request_id":row["request_id"],"from_transport":from_transport,"to_transport":to_transport,"reason":reason,"transitioned_at":stamp,"authority_effect":"NONE"}
    tdigest=_digest(value);tid="saas-transition-"+tdigest[:32]
    conn.execute("INSERT OR IGNORE INTO saas_transport_transitions(transition_id,request_id,from_transport,to_transport,reason,transitioned_at,authority_effect,transition_digest) VALUES(?,?,?,?,?,?,?,?)",(tid,row['request_id'],from_transport,to_transport,reason,stamp,'NONE',tdigest))
    return tdigest


def _columns(conn, table):
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def _ensure_column(conn, table, name, ddl):
    if name not in _columns(conn, table):
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}")


def migrate(conn, now_fn, *, source_head, source_tree):
    # Rebuild only the two legacy tables whose NOT NULL mission binding prevented
    # zero-mission cognition. All rows and legacy columns are copied transactionally.
    for table in ('saas_handoff_requests','saas_session_bindings'):
        schema=conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=?",(table,)).fetchone()
        if schema and any(r[1]=='mission_id' and r[3] for r in conn.execute('PRAGMA table_info('+table+')')):
            old_columns=[r[1] for r in conn.execute('PRAGMA table_info('+table+')')]
            sql=schema[0].replace(table,table+'_nullable',1).replace('mission_id TEXT NOT NULL','mission_id TEXT').replace('lpcl_digest TEXT NOT NULL','lpcl_digest TEXT')
            with conn:
                conn.execute(sql)
                names=','.join('"'+c+'"' for c in old_columns)
                conn.execute('INSERT INTO '+table+'_nullable ('+names+') SELECT '+names+' FROM '+table)
                conn.execute('DROP TABLE '+table)
                conn.execute('ALTER TABLE '+table+'_nullable RENAME TO '+table)
    conn.executescript(DDL)
    for name,ddl in [('scope_type',"TEXT NOT NULL DEFAULT 'MISSION'"),('scope_id','TEXT'),('thread_id','TEXT'),('transport','TEXT'),('control_transport','TEXT'),('inference_transport','TEXT'),('provider','TEXT'),('provider_conversation_id','TEXT'),('provider_response_id','TEXT'),('authority_effect',"TEXT NOT NULL DEFAULT 'NONE'"),('claim_generation','INTEGER NOT NULL DEFAULT 0'),('claim_expires_at','TEXT')]:
        _ensure_column(conn,'saas_handoff_requests',name,ddl)
    conn.execute("UPDATE saas_handoff_requests SET scope_id=mission_id WHERE scope_id IS NULL AND scope_type='MISSION'")
    conn.execute('UPDATE saas_handoff_requests SET transport=? WHERE transport IS NULL',(TRANSPORT,))
    conn.execute('UPDATE saas_handoff_requests SET inference_transport=transport WHERE inference_transport IS NULL')
    conn.executescript("""CREATE TABLE IF NOT EXISTS saas_broker_receipts(
        request_id TEXT PRIMARY KEY, receipt_digest TEXT NOT NULL UNIQUE,
        receipt_json TEXT NOT NULL, created_at TEXT NOT NULL);
        CREATE TRIGGER IF NOT EXISTS saas_receipt_immutable BEFORE UPDATE ON saas_broker_receipts
        BEGIN SELECT RAISE(ABORT,'immutable SaaS receipt'); END;""")
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
         "Canonical cognitive broker: optional mission context, thread scopes, claims and immutable receipts; authority NONE."),
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


def _active_request_rows(conn, scope_type, scope_id, question_digest):
    return conn.execute(
        "SELECT * FROM saas_handoff_requests WHERE scope_type=? AND scope_id=? AND question_digest=? "
        "AND status IN ('PENDING','CREATED','QUEUED','WAITING_SUPERVISOR','WAITING_OPERATOR_OVERDUE','WAITING_PROVIDER','WAITING_PROVIDER_OVERDUE','WAITING_BROWSER_MEDIATOR','WAITING_BROWSER_OVERDUE','CLAIMED') "
        "ORDER BY created_at,request_id",
        (scope_type, scope_id, question_digest),
    ).fetchall()


MEDIATOR_STATES = {"STARTING","LOGIN_REQUIRED","PROJECT_BINDING_REQUIRED","CHAT_BINDING_REQUIRED","READY","DEGRADED","STOPPED"}


def record_mediator_heartbeat(conn, payload, now_fn):
    if type(payload) is not dict or set(payload) != {"mediator_id","transport","state","project_title","chat_title","browser","authority_effect"}:
        raise ValueError("mediator heartbeat schema")
    if payload.get("authority_effect") != "NONE":
        raise ValueError("mediator authority")
    mediator_id=payload.get("mediator_id");transport=payload.get("transport");state=payload.get("state")
    if not isinstance(mediator_id,str) or not mediator_id or len(mediator_id)>96:raise ValueError("mediator_id")
    if transport != FIREFOX_TRANSPORT:raise ValueError("mediator transport")
    if state not in MEDIATOR_STATES:raise ValueError("mediator state")
    for key in ("project_title","chat_title","browser"):
        value=payload.get(key)
        if value is not None and (not isinstance(value,str) or len(value)>240):raise ValueError("mediator "+key)
    stamp=now_fn();details={"authority_effect":"NONE","transport":transport,"state":state}
    conn.execute(
        "INSERT INTO saas_mediator_heartbeats(mediator_id,transport,state,project_title,chat_title,browser,observed_at,details_json) VALUES(?,?,?,?,?,?,?,?) "
        "ON CONFLICT(mediator_id) DO UPDATE SET transport=excluded.transport,state=excluded.state,project_title=excluded.project_title,chat_title=excluded.chat_title,browser=excluded.browser,observed_at=excluded.observed_at,details_json=excluded.details_json",
        (mediator_id,transport,state,payload.get("project_title"),payload.get("chat_title"),payload.get("browser"),stamp,_canon(details)),
    )
    conn.commit();return {**payload,"observed_at":stamp,"fresh":True,"promoted_request_ids":[]}


def _current_mediator(conn, stamp):
    row=conn.execute("SELECT * FROM saas_mediator_heartbeats ORDER BY observed_at DESC LIMIT 1").fetchone()
    if row is None:return None
    out=dict(row);age=(_parse_ts(stamp)-_parse_ts(out["observed_at"])).total_seconds();out["heartbeat_age_seconds"]=max(0.0,round(age,3));out["fresh"]=0<=age<=MEDIATOR_HEARTBEAT_TTL_SECONDS
    if not out["fresh"]:out["state"]="STALE"
    try:out["details"]=json.loads(out.pop("details_json"))
    except Exception:out["details"]={}
    return out


def _current_direct_bridge(conn, stamp):
    row=conn.execute("SELECT * FROM saas_direct_bridge_heartbeats ORDER BY observed_at DESC LIMIT 1").fetchone()
    if row is None:return None
    out=dict(row);age=(_parse_ts(stamp)-_parse_ts(out["observed_at"])).total_seconds();out["heartbeat_age_seconds"]=max(0.0,round(age,3));out["fresh"]=0<=age<=45
    if not out["fresh"]:out["state"]="STALE"
    try:out["details"]=json.loads(out.pop("details_json"))
    except Exception:out["details"]={}
    return out


def record_direct_bridge_heartbeat(conn,payload,now_fn):
    required={"bridge_id","state","provider","model_id","credential_state","authority_effect"}
    if type(payload) is not dict or set(payload)!=required:raise ValueError("direct bridge heartbeat schema")
    if payload.get("authority_effect")!="NONE" or payload.get("provider")!=DIRECT_PROVIDER:raise ValueError("direct bridge authority/provider")
    if payload.get("state") not in {"READY","BLOCKED_CREDENTIAL","DEGRADED","STOPPED"}:raise ValueError("direct bridge state")
    if payload.get("credential_state") not in {"PRESENT","ABSENT","INVALID","UNKNOWN"}:raise ValueError("credential state")
    stamp=now_fn();details={"authority_effect":"NONE","control_transport":CONTROL_TRANSPORT,"inference_transport":DIRECT_TRANSPORT}
    conn.execute("INSERT INTO saas_direct_bridge_heartbeats(bridge_id,state,provider,model_id,credential_state,observed_at,details_json) VALUES(?,?,?,?,?,?,?) ON CONFLICT(bridge_id) DO UPDATE SET state=excluded.state,provider=excluded.provider,model_id=excluded.model_id,credential_state=excluded.credential_state,observed_at=excluded.observed_at,details_json=excluded.details_json",(payload['bridge_id'],payload['state'],payload['provider'],payload.get('model_id'),payload['credential_state'],stamp,_canon(details)))
    conn.commit();return {**payload,"observed_at":stamp,"fresh":True}


def _attestation_for_transport(transport):
    value=SUPPORTED_TRANSPORT_ATTESTATIONS.get(transport)
    if value is None:raise ValueError("unsupported transport")
    return value


def _public_created_request(row, *, deduplicated=False):
    return {
        "request_id": row["request_id"],
        "request_code": row["request_code"],
        "mission_id": row["mission_id"],
        "lpcl_digest": row["lpcl_digest"],
        "scope_type": row["scope_type"],
        "scope_id": row["scope_id"],
        "thread_id": row["thread_id"],
        "created_at": row["created_at"],
        "deadline_at": row["expires_at"],
        "question_digest": row["question_digest"],
        "status": row["status"],
        "state": row["status"],
        "progress_state": row["progress_state"],
        "expires_at": row["expires_at"],
        "retry_of_request_id": row["retry_of_request_id"],
        "transport": row["transport"] or TRANSPORT,
        "control_transport": row["control_transport"] or CONTROL_TRANSPORT,
        "inference_transport": row["inference_transport"] or row["transport"] or TRANSPORT,
        "provider": row["provider"],
        "provider_conversation_id": row["provider_conversation_id"],
        "provider_response_id": row["provider_response_id"],
        "operator_trigger": "LION SaaS",
        "deduplicated": bool(deduplicated),
        "authority_effect": "NONE",
    }


def create_request(conn, mission_id, question, now_fn, *, ttl_seconds=900, scope_type=None, thread_id=None, scope_id=None, authority_effect="NONE", inference_transport=None, provider=None, control_transport=CONTROL_TRANSPORT):
    if type(ttl_seconds) is not int or not 1 <= ttl_seconds <= 86400:
        raise ValueError('request deadline')
    if thread_id is not None and (not isinstance(thread_id,str) or len(thread_id)!=32 or any(c not in '0123456789abcdef' for c in thread_id)):
        raise ValueError('thread_id')
    if not isinstance(question, str) or not question.strip() or len(question) > 8000:
        raise ValueError("saas question")
    legacy=scope_type is None
    if authority_effect!='NONE':raise ValueError('broker is cognition only; authority_effect must be NONE')
    if legacy:
        mission, process = _mission_binding(conn, mission_id)
        scope_type='MISSION';scope_id=mission_id;lpcl_digest=mission['spec_digest']
    else:
        if scope_type not in {'CONTROL_PLANE','THREAD','MISSION'}:raise ValueError('scope_type')
        if scope_type=='THREAD' and (not isinstance(thread_id,str) or len(thread_id)!=32 or any(c not in '0123456789abcdef' for c in thread_id)):raise ValueError('thread_id')
        if scope_type=='CONTROL_PLANE' and (mission_id is not None or thread_id is not None):raise ValueError('control-plane context')
        if scope_type=='MISSION' and not mission_id:raise ValueError('mission_id required for mission scope')
        if mission_id is not None:
            mission=conn.execute('SELECT state FROM missions WHERE mission_id=?',(mission_id,)).fetchone()
            if mission is None:raise ValueError('mission context not found')
            if scope_type=='MISSION' and str(mission['state']).upper() in {'COMPLETE','COMPLETED','SUPERSEDED','CANCELLED','FAILED','FAIL','STOPPED'}:
                raise ValueError('mission context terminal')
        expected=thread_id if scope_type=='THREAD' else mission_id if scope_type=='MISSION' else 'GLOBAL_SUPERVISOR_CHANNEL'
        if scope_id is not None and scope_id!=expected:raise ValueError('scope_id mismatch')
        scope_id=expected;lpcl_digest=None
    stamp = now_fn()
    question = question.strip()
    qdigest = hashlib.sha256(question.encode("utf-8")).hexdigest()
    retry_of = None
    if legacy:
        target_transport=TRANSPORT;provider=None;control_transport=None;initial_status="PENDING";progress_state="WAITING_OPERATOR"
    else:
        target_transport=inference_transport or DIRECT_TRANSPORT
        if target_transport not in {DIRECT_TRANSPORT,FIREFOX_TRANSPORT}:raise ValueError("inference transport")
        expected_provider=DIRECT_PROVIDER if target_transport==DIRECT_TRANSPORT else FIREFOX_PROVIDER
        if provider is not None and provider!=expected_provider:raise ValueError("provider mismatch")
        provider=expected_provider
        if control_transport!=CONTROL_TRANSPORT:raise ValueError("control transport")
        initial_status="WAITING_PROVIDER" if target_transport==DIRECT_TRANSPORT else "WAITING_BROWSER_MEDIATOR"
        progress_state=initial_status
    if not legacy:
        # Reconcile time/session/terminal-mission state before deciding whether
        # a new handoff is semantically independent or a retry of an existing one.
        _expire(conn, stamp)
        same_all=list(_active_request_rows(conn,scope_type,scope_id,qdigest))
        foreign=[r for r in same_all if (r['inference_transport'] or r['transport'] or TRANSPORT)!=target_transport]
        claimed_foreign=next((r for r in foreign if r['status']=='CLAIMED'),None)
        if claimed_foreign:
            # Never fan out while an older transport already owns a live claim.
            return _public_created_request(claimed_foreign,deduplicated=True)
        if foreign:
            retry_of=foreign[-1]['request_id']
            for prior in foreign:_record_transport_transition(conn,prior,target_transport,"EXPLICIT_REQUEST_TRANSPORT_CHANGE",stamp)
            conn.executemany(
                "UPDATE saas_handoff_requests SET status='SUPERSEDED',progress_state='SUPERSEDED_EXPLICIT_TRANSPORT_CHANGE',claim_expires_at=NULL WHERE request_id=?",
                [(r['request_id'],) for r in foreign],
            )
        same=[r for r in same_all if (r['inference_transport'] or r['transport'] or TRANSPORT)==target_transport]
        if same:
            overdue={'WAITING_OPERATOR_OVERDUE','WAITING_PROVIDER_OVERDUE','WAITING_BROWSER_OVERDUE'}
            live=[r for r in same if r['status'] not in overdue]
            if live:
                # Prefer a claimed request, then the oldest stable request. Collapse
                # stale duplicate siblings without invalidating the canonical poll id.
                canonical=next((r for r in live if r['status']=='CLAIMED'),live[0])
                for row in same:
                    if row['request_id']==canonical['request_id'] or row['status']=='CLAIMED':continue
                    conn.execute("UPDATE saas_handoff_requests SET status='SUPERSEDED',progress_state='SUPERSEDED_DUPLICATE',claim_expires_at=NULL WHERE request_id=?",(row['request_id'],))
                conn.commit()
                refreshed=conn.execute('SELECT * FROM saas_handoff_requests WHERE request_id=?',(canonical['request_id'],)).fetchone()
                return _public_created_request(refreshed,deduplicated=True)
            # The same unresolved semantic request already timed out waiting for
            # mediation. Preserve its history, collapse all stale siblings and
            # create one explicit retry linked to the latest predecessor.
            retry_of=same[-1]['request_id']
            conn.executemany(
                "UPDATE saas_handoff_requests SET status='SUPERSEDED',progress_state='SUPERSEDED_BY_RETRY',claim_expires_at=NULL WHERE request_id=?",
                [(r['request_id'],) for r in same],
            )
    request_id = "saas-" + uuid.uuid4().hex
    request_code = secrets.token_hex(4).upper()
    token = secrets.token_hex(32)
    expires = _future(stamp, ttl_seconds)
    conn.execute(
        "INSERT INTO saas_handoff_requests(request_id,mission_id,lpcl_digest,request_code,response_token,question,question_digest,status,created_at,expires_at,progress_state,retry_of_request_id,scope_type,scope_id,thread_id,transport,control_transport,inference_transport,provider,authority_effect) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (request_id, mission_id, lpcl_digest, request_code, token, question, qdigest, initial_status, stamp, expires, progress_state,retry_of,scope_type,scope_id,thread_id,target_transport,control_transport,target_transport,provider,"NONE"),
    )
    conn.commit()
    row=conn.execute('SELECT * FROM saas_handoff_requests WHERE request_id=?',(request_id,)).fetchone()
    return _public_created_request(row)


def _expire(conn, now_value):
    # A mission-scoped advisory cannot outlive its mission as an actionable
    # pending handoff. Preserve the row, but terminalize it as historical.
    tables={r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    if 'missions' in tables:
        conn.execute(
            "UPDATE saas_handoff_requests SET status='SUPERSEDED',progress_state='SUPERSEDED_TERMINAL_MISSION',claim_expires_at=NULL "
            "WHERE scope_type='MISSION' AND status IN ('PENDING','CREATED','QUEUED','WAITING_SUPERVISOR','WAITING_OPERATOR_OVERDUE','WAITING_PROVIDER','WAITING_PROVIDER_OVERDUE','WAITING_BROWSER_MEDIATOR','WAITING_BROWSER_OVERDUE','CLAIMED') "
            "AND mission_id IN (SELECT mission_id FROM missions WHERE UPPER(state) IN ('COMPLETE','COMPLETED','SUPERSEDED','CANCELLED','FAILED','FAIL','STOPPED'))"
        )
    # Request deadlines are advisory progress deadlines, not destructive TTLs.
    # A handoff remains answerable until it is explicitly responded/rejected/superseded.
    conn.execute(
        "UPDATE saas_handoff_requests SET progress_state='WAITING_OPERATOR_OVERDUE', "
        "deadline_elapsed_at=COALESCE(deadline_elapsed_at,?) "
        "WHERE status='PENDING' AND expires_at<=?",
        (now_value, now_value),
    )
    conn.execute("UPDATE saas_handoff_requests SET status=CASE WHEN inference_transport=? THEN 'WAITING_PROVIDER' WHEN inference_transport=? THEN 'WAITING_BROWSER_MEDIATOR' ELSE 'WAITING_SUPERVISOR' END,progress_state=CASE WHEN inference_transport=? THEN 'WAITING_PROVIDER' WHEN inference_transport=? THEN 'WAITING_BROWSER_MEDIATOR' ELSE 'WAITING_SUPERVISOR' END,claim_expires_at=NULL WHERE status='CLAIMED' AND claim_expires_at<=?",(DIRECT_TRANSPORT,FIREFOX_TRANSPORT,DIRECT_TRANSPORT,FIREFOX_TRANSPORT,now_value))
    conn.execute("UPDATE saas_handoff_requests SET status=CASE WHEN inference_transport=? THEN 'WAITING_PROVIDER_OVERDUE' WHEN inference_transport=? THEN 'WAITING_BROWSER_OVERDUE' ELSE 'WAITING_OPERATOR_OVERDUE' END,progress_state=CASE WHEN inference_transport=? THEN 'WAITING_PROVIDER_OVERDUE' WHEN inference_transport=? THEN 'WAITING_BROWSER_OVERDUE' ELSE 'WAITING_OPERATOR_OVERDUE' END,deadline_elapsed_at=COALESCE(deadline_elapsed_at,?) WHERE status IN ('CREATED','QUEUED','WAITING_SUPERVISOR','WAITING_PROVIDER','WAITING_BROWSER_MEDIATOR') AND expires_at<=?",(DIRECT_TRANSPORT,FIREFOX_TRANSPORT,DIRECT_TRANSPORT,FIREFOX_TRANSPORT,now_value,now_value))
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
    out["transport"] = out.get("transport") or TRANSPORT
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


def cancel_request(conn, request_id, now_fn):
    """Cancel an explicit local handoff; never alter an accepted response or binding."""
    with conn:
        row = conn.execute('SELECT status FROM saas_handoff_requests WHERE request_id=?', (request_id,)).fetchone()
        if row is None:
            return {'request_id': request_id, 'status': 'NOT_FOUND', 'cancelled': False, 'authority_effect': 'NONE'}
        changed = conn.execute("UPDATE saas_handoff_requests SET status='CANCELLED', progress_state='CANCELLED_BY_OPERATOR' WHERE request_id=? AND status IN ('PENDING','CREATED','QUEUED','WAITING_SUPERVISOR','WAITING_OPERATOR_OVERDUE','WAITING_PROVIDER','WAITING_PROVIDER_OVERDUE','WAITING_BROWSER_MEDIATOR','WAITING_BROWSER_OVERDUE','CLAIMED')", (request_id,)).rowcount
    result = request_status(conn, request_id, now_fn)
    return {'request_id': request_id, 'status': result['status'], 'cancelled': bool(changed), 'authority_effect': 'NONE'}


def request_status(conn, request_id, now_fn):
    stamp = now_fn(); _expire(conn, stamp); conn.commit()
    row = conn.execute("SELECT * FROM saas_handoff_requests WHERE request_id=?", (request_id,)).fetchone()
    if row is None:
        raise ValueError("saas request not found")
    out = dict(row)
    out.pop("response_token", None)
    out["deadline_at"]=out["expires_at"]
    out["state"]=out["status"]
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
        "SELECT request_id,request_code,status,created_at,expires_at,question_digest,progress_state,deadline_elapsed_at,retry_of_request_id FROM saas_handoff_requests WHERE (? IS NULL OR mission_id=?) AND status IN ('PENDING','WAITING_SUPERVISOR','WAITING_OPERATOR_OVERDUE','WAITING_PROVIDER','WAITING_PROVIDER_OVERDUE','WAITING_BROWSER_MEDIATOR','WAITING_BROWSER_OVERDUE','CLAIMED') ORDER BY created_at ASC LIMIT 1",
        (mission_id,mission_id),
    ).fetchone()
    pending_count = int(conn.execute("SELECT COUNT(*) FROM saas_handoff_requests WHERE (? IS NULL OR mission_id=?) AND status IN ('PENDING','WAITING_SUPERVISOR','WAITING_OPERATOR_OVERDUE','WAITING_PROVIDER','WAITING_PROVIDER_OVERDUE','WAITING_BROWSER_MEDIATOR','WAITING_BROWSER_OVERDUE','CLAIMED')", (mission_id,mission_id)).fetchone()[0])
    pending_value = dict(pending) if pending else None
    if pending_value is not None:
        pending_value["dual_request_id"] = _dual_request_id(conn, pending_value["request_id"])
    last_response = conn.execute(
        "SELECT request_id,responded_at,response_digest,receipt_digest,binding_id FROM saas_handoff_requests WHERE (? IS NULL OR mission_id=?) AND status='RESPONDED' ORDER BY responded_at DESC LIMIT 1",
        (mission_id,mission_id),
    ).fetchone()
    mediator=_current_mediator(conn,stamp)
    browser_ready=bool(mediator and mediator.get("fresh") and mediator.get("state")=="READY" and mediator.get("transport")==FIREFOX_TRANSPORT)
    direct_bridge=_current_direct_bridge(conn,stamp)
    direct_ready=bool(direct_bridge and direct_bridge.get("fresh") and direct_bridge.get("state")=="READY" and direct_bridge.get("credential_state")=="PRESENT")
    target_transport=DIRECT_TRANSPORT
    out = {
        "mission_id": mission_id,
        "state": "BOUND" if binding else ("PENDING_HANDOFF" if pending else "UNBOUND"),
        "channel_state": "DIRECT_PROVIDER_READY" if direct_ready else ("BLOCKED_CREDENTIAL" if direct_bridge and direct_bridge.get("credential_state")=="ABSENT" else "WAITING_DIRECT_PROVIDER"),
        "session_attestation_state": "BOUND" if binding else ("EXPIRED" if last_binding and last_binding['status']=='EXPIRED' else "NOT_ATTESTED"),
        "session_scope": "GLOBAL_SUPERVISOR_CHANNEL",
        "schema": SCHEMA_ID,
        "schema_version": SCHEMA_VERSION,
        "automatic_hop": "AVAILABLE" if direct_ready else "UNAVAILABLE",
        "binding": dict(binding) if binding else None,
        "last_binding": dict(last_binding) if last_binding else None,
        "pending": pending_value,
        "pending_count": pending_count,
        "last_response": dict(last_response) if last_response else None,
        "queue_policy": "FIFO_MULTI_PENDING",
        "duplicate_policy": "EXACT_SCOPE_QUESTION_DEDUPE_WITH_OVERDUE_RETRY_LINEAGE",
        "terminal_mission_pending_policy": "SUPERSEDE_PRESERVE_HISTORY",
        "transport": target_transport,
        "automatic_local_to_saas_hop": direct_ready,
        "operator_mediation_required": False,
        "direct_bridge": direct_bridge,
        "browser_mediator": mediator,
        "browser_ready": browser_ready,
        "control_transport": CONTROL_TRANSPORT,
        "inference_transport": DIRECT_TRANSPORT,
        "provider": DIRECT_PROVIDER,
        "mediator": mediator,
        "cryptographic_provider_attestation": False,
        "authority_effect": "NONE",
    }
    out["supervisor_projection"] = supervisor_projection(out, now=stamp, observed_at=stamp)
    return out


def _respond_locked(conn, request_id, response_token, answer, now_fn, *, model_identity, transport=TRANSPORT, attestation_class=ATTESTATION_CLASS, lease_seconds=7200, claim_generation=None, provider=None, provider_conversation_id=None, provider_response_id=None):
    if type(lease_seconds) is not int or not 1 <= lease_seconds <= 86400:
        raise ValueError('session lease')
    if not isinstance(answer, str) or not answer.strip() or len(answer) > 24000:
        raise ValueError("saas answer")
    if not isinstance(model_identity, str) or not model_identity.strip() or len(model_identity) > 120:
        raise ValueError("model identity")
    conn.execute("BEGIN IMMEDIATE")
    stamp = now_fn(); _expire(conn, stamp)
    row = conn.execute("SELECT * FROM saas_handoff_requests WHERE request_id=?", (request_id,)).fetchone()
    if row is None:
        raise ValueError("saas request not found")
    if row["status"] not in {"PENDING","CLAIMED"}:
        raise ValueError("saas request not pending")
    if row['status']=='CLAIMED' and (type(claim_generation) is not int or claim_generation!=row['claim_generation']):
        raise ValueError('stale claim generation')
    if not isinstance(response_token, str) or not secrets.compare_digest(response_token, row["response_token"]):
        raise ValueError("saas response token")
    if row["lpcl_digest"]:
        mission, process = _mission_binding(conn, row["mission_id"])
        if mission["spec_digest"] != row["lpcl_digest"]:raise ValueError("saas lpcl digest drift")
    row_transport=row["transport"] or TRANSPORT
    expected_attestation=_attestation_for_transport(row_transport)
    if transport!=row_transport or attestation_class!=expected_attestation:raise ValueError("request transport/attestation")
    supervisor_role="CHATGPT_FIREFOX_PROJECT_MEDIATOR" if transport==FIREFOX_TRANSPORT else "OPENAI_RESPONSES_SUPERVISOR" if transport==DIRECT_TRANSPORT else "CHATGPT_SAAS_SUPERVISOR"
    expected_provider=DIRECT_PROVIDER if transport==DIRECT_TRANSPORT else FIREFOX_PROVIDER if transport==FIREFOX_TRANSPORT else None
    if provider is not None and expected_provider is not None and provider!=expected_provider:raise ValueError("provider mismatch")
    provider=provider or expected_provider
    answer = answer.strip()
    rdigest = hashlib.sha256(answer.encode("utf-8")).hexdigest()
    binding_id = "saas-binding-" + uuid.uuid4().hex
    expires = _future(stamp, lease_seconds)
    attestation = {
        "binding_id": binding_id,
        "mission_id": row["mission_id"],
        "lpcl_digest": row["lpcl_digest"],
        "supervisor_role": supervisor_role,
        "model_identity": model_identity.strip(),
        "transport": transport,
        "control_transport": row["control_transport"] or CONTROL_TRANSPORT,
        "inference_transport": row["inference_transport"] or transport,
        "provider": provider,
        "provider_conversation_id": provider_conversation_id,
        "provider_response_id": provider_response_id,
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
        (binding_id,row["mission_id"],row["lpcl_digest"],supervisor_role,model_identity.strip(),transport,attestation_class,"NONE","BOUND",stamp,stamp,expires,request_id,_canon(attestation),adigest,"GLOBAL_SUPERVISOR_CHANNEL"),
    )
    meta = {"model_identity": model_identity.strip(), "transport": transport, "control_transport":row["control_transport"] or CONTROL_TRANSPORT,"inference_transport":row["inference_transport"] or transport,"provider":provider,"provider_conversation_id":provider_conversation_id,"provider_response_id":provider_response_id,"attestation_class": attestation_class, "authority_effect": "NONE", "binding_scope": "GLOBAL_SUPERVISOR_CHANNEL"}
    receipt = {
        "request_id": request_id,
        "request_code": row["request_code"],
        "scope_type":row["scope_type"],"scope_id":row["scope_id"],"thread_id":row["thread_id"],
        "model_identity":model_identity.strip(),"transport":transport,"control_transport":row["control_transport"] or CONTROL_TRANSPORT,"inference_transport":row["inference_transport"] or transport,"provider":provider,"provider_conversation_id":provider_conversation_id,"provider_response_id":provider_response_id,
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
    conn.execute("INSERT INTO saas_broker_receipts VALUES(?,?,?,?)",(request_id,receipt_digest,_canon(receipt),stamp))
    conn.execute(
        "UPDATE saas_handoff_requests SET status='RESPONDED',progress_state='RECEIPT_BOUND',responded_at=?,response_text=?,response_digest=?,binding_id=?,response_meta_json=?,receipt_digest=?,provider=?,provider_conversation_id=?,provider_response_id=? WHERE request_id=?",
        (stamp,answer,rdigest,binding_id,_canon(meta),receipt_digest,provider,provider_conversation_id,provider_response_id,request_id),
    )
    conn.commit()
    return {"status":"RESPONDED","answer":answer,"binding":attestation,"receipt":{**receipt,"receipt_digest":receipt_digest}}


WAITING_STATES=('CREATED','QUEUED','WAITING_SUPERVISOR','WAITING_OPERATOR_OVERDUE','WAITING_PROVIDER','WAITING_PROVIDER_OVERDUE','WAITING_BROWSER_MEDIATOR','WAITING_BROWSER_OVERDUE','CLAIMED')


def claim(conn,request_id,now_fn,*,lease_seconds=300):
    if type(lease_seconds) is not int or not 1<=lease_seconds<=300:raise ValueError('claim lease')
    conn.execute('BEGIN IMMEDIATE')
    try:
        stamp=now_fn();_expire(conn,stamp)
        row=conn.execute('SELECT * FROM saas_handoff_requests WHERE request_id=?',(request_id,)).fetchone()
        if row is None or row['status'] not in {'WAITING_SUPERVISOR','WAITING_OPERATOR_OVERDUE','WAITING_PROVIDER','WAITING_PROVIDER_OVERDUE','WAITING_BROWSER_MEDIATOR','WAITING_BROWSER_OVERDUE','QUEUED'}:raise ValueError('request not claimable')
        token=secrets.token_hex(32);generation=row['claim_generation']+1;expires=_future(stamp,lease_seconds)
        conn.execute("UPDATE saas_handoff_requests SET status='CLAIMED',progress_state='CLAIMED',response_token=?,claim_generation=?,claim_expires_at=? WHERE request_id=?",(token,generation,expires,request_id))
        conn.commit()
        return {'request_id':request_id,'question':row['question'],'question_digest':row['question_digest'],'response_token':token,'claim_generation':generation,'claim_expires_at':expires,'authority_effect':'NONE'}
    except Exception:
        conn.rollback();raise


def broker_pending(conn,now_fn):
    _expire(conn,now_fn());conn.commit()
    rows=conn.execute("SELECT request_id FROM saas_handoff_requests WHERE status IN ('CREATED','QUEUED','WAITING_SUPERVISOR','WAITING_OPERATOR_OVERDUE','WAITING_PROVIDER','WAITING_PROVIDER_OVERDUE','WAITING_BROWSER_MEDIATOR','WAITING_BROWSER_OVERDUE','CLAIMED') ORDER BY created_at,request_id LIMIT 100").fetchall()
    return {'requests':[request_status(conn,r[0],now_fn) for r in rows],'authority_effect':'NONE'}


def respond(conn,request_id,response_token,answer,now_fn,**options):
    try:return _respond_locked(conn,request_id,response_token,answer,now_fn,**options)
    except Exception:
        conn.rollback();raise
