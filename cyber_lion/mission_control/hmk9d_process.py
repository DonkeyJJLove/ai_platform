from __future__ import annotations

import hashlib
import json

SCHEMA_ID = "lion.hmk9d.process/v1"
STEP_SCHEMA_ID = "lion.hmk9d.step/v1"
PROFILE_ID = "LION_OPERATOR_CONVERSATION_HMK9D_V1"
AUTHORITY_EFFECT = "NONE"
AXES = ("T", "S", "R", "E", "I", "F", "A", "P", "D")
EPISTEMIC = frozenset({"OBSERVED", "DERIVED", "ASSUMED", "HYPOTHESIS", "UNKNOWN"})

BRIDGES = {
    "PLAN_PAUSE": {"mode": None, "delta": {"T":1.0,"S":1.0,"R":0.5,"E":-1.0,"I":0.5,"F":0.0,"A":0.5,"P":1.0,"D":-1.0}},
    "CORE_PERIPH": {"mode": None, "delta": {"T":0.5,"S":2.0,"R":0.5,"E":-0.5,"I":1.0,"F":1.0,"A":1.0,"P":1.0,"D":0.5}},
    "SILENCE_EXHALE": {"mode": None, "delta": {"T":1.0,"S":1.0,"R":0.0,"E":-2.0,"I":0.0,"F":0.0,"A":0.5,"P":1.0,"D":0.0}},
    "VILLAGE_CITY": {"mode": None, "delta": {"T":0.5,"S":1.0,"R":2.0,"E":1.0,"I":1.0,"F":2.0,"A":1.0,"P":1.0,"D":0.5}},
    "EDGE_PATIENCE": {"mode": "PATIENCE", "delta": {"T":1.0,"S":0.5,"R":0.5,"E":-0.5,"I":0.0,"F":0.5,"A":1.0,"P":0.5,"D":-0.5}},
    "LOCUS_MEDIUM_MANDATE": {"mode": None, "delta": {"T":1.0,"S":0.5,"R":1.0,"E":0.5,"I":2.0,"F":2.0,"A":0.0,"P":1.0,"D":1.0}},
    "HUMAN_AI": {"mode": None, "delta": {"T":1.0,"S":1.0,"R":1.0,"E":0.5,"I":0.5,"F":1.0,"A":1.0,"P":2.0,"D":0.5}},
    "THRESHOLD_TRANSITION": {"mode": None, "delta": {"T":1.0,"S":0.5,"R":1.0,"E":-0.5,"I":1.0,"F":1.0,"A":0.0,"P":1.0,"D":3.0}},
    "SEMANTICS_ENERGY": {"mode": None, "delta": {"T":0.5,"S":1.0,"R":0.5,"E":0.0,"I":0.5,"F":1.0,"A":0.0,"P":1.0,"D":1.0}},
}
CONVERSATION_PATH = tuple(BRIDGES)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def migrate(conn, now_fn):
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS hmk9d_process_runs(
      process_id TEXT PRIMARY KEY,
      schema_id TEXT NOT NULL,
      profile_id TEXT NOT NULL,
      mission_id TEXT NOT NULL,
      correlation_id TEXT NOT NULL,
      message_id TEXT NOT NULL UNIQUE,
      status TEXT NOT NULL,
      current_ordinal INTEGER NOT NULL,
      state_vector_json TEXT NOT NULL,
      energy_proxy_total REAL NOT NULL,
      created_at TEXT NOT NULL,
      updated_at TEXT NOT NULL,
      authority_effect TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS hmk9d_process_steps(
      step_id TEXT PRIMARY KEY,
      schema_id TEXT NOT NULL,
      process_id TEXT NOT NULL,
      ordinal INTEGER NOT NULL,
      bridge_id TEXT NOT NULL,
      mode TEXT,
      state_before_json TEXT NOT NULL,
      vector_delta_json TEXT NOT NULL,
      state_after_json TEXT NOT NULL,
      energy_local_proxy REAL NOT NULL,
      energy_basis TEXT NOT NULL,
      epistemic_status TEXT NOT NULL,
      evidence_json TEXT NOT NULL,
      observed_at TEXT NOT NULL,
      event_topic TEXT NOT NULL,
      authority_effect TEXT NOT NULL,
      UNIQUE(process_id, ordinal),
      FOREIGN KEY(process_id) REFERENCES hmk9d_process_runs(process_id)
    );
    CREATE INDEX IF NOT EXISTS idx_hmk9d_runs_thread
      ON hmk9d_process_runs(correlation_id,created_at,process_id);
    CREATE INDEX IF NOT EXISTS idx_hmk9d_runs_mission
      ON hmk9d_process_runs(mission_id,status,created_at);
    CREATE INDEX IF NOT EXISTS idx_hmk9d_steps_process
      ON hmk9d_process_steps(process_id,ordinal);
    """)
    conn.commit()
    return {"schema":SCHEMA_ID,"state":"READY","authority_effect":AUTHORITY_EFFECT}


def conversation_process_id(mission_id, correlation_id, message_id):
    raw={"mission_id":mission_id,"correlation_id":correlation_id,"message_id":message_id,"profile_id":PROFILE_ID}
    return "hmkproc-"+digest(raw)[:32]


def ensure_conversation_process(conn, mission_id, correlation_id, message_id, now_fn):
    if not all(isinstance(v,str) and v for v in (mission_id,correlation_id,message_id)):
        raise ValueError("hmk9d conversation identity")
    process_id=conversation_process_id(mission_id,correlation_id,message_id)
    stamp=now_fn()
    zero={axis:0.0 for axis in AXES}
    conn.execute("""INSERT OR IGNORE INTO hmk9d_process_runs(
      process_id,schema_id,profile_id,mission_id,correlation_id,message_id,status,current_ordinal,
      state_vector_json,energy_proxy_total,created_at,updated_at,authority_effect
    ) VALUES(?,?,?,?,?,?,'ACTIVE',0,?,0.0,?,?,'NONE')""",
    (process_id,SCHEMA_ID,PROFILE_ID,mission_id,correlation_id,message_id,canonical(zero),stamp,stamp))
    conn.commit()
    return process_id


def _step_id(process_id, ordinal, bridge_id):
    return "hmkstep-"+digest({"process_id":process_id,"ordinal":ordinal,"bridge_id":bridge_id})[:32]


def advance(conn, process_id, bridge_id, evidence, now_fn, *, epistemic_status="OBSERVED"):
    if bridge_id not in BRIDGES:raise ValueError("hmk9d bridge")
    if epistemic_status not in EPISTEMIC:raise ValueError("hmk9d epistemic")
    if type(evidence) is not dict:raise ValueError("hmk9d evidence")
    run=conn.execute("SELECT * FROM hmk9d_process_runs WHERE process_id=?",(process_id,)).fetchone()
    if not run:raise ValueError("hmk9d process missing")
    next_ordinal=int(run["current_ordinal"])+1
    if next_ordinal>len(CONVERSATION_PATH):
        return {"process_id":process_id,"status":"COMPLETE","idempotent":True,"authority_effect":"NONE"}
    expected=CONVERSATION_PATH[next_ordinal-1]
    if bridge_id!=expected:raise ValueError("hmk9d bridge order")
    prior=conn.execute("SELECT * FROM hmk9d_process_steps WHERE process_id=? AND ordinal=?",(process_id,next_ordinal)).fetchone()
    if prior:
        return {"process_id":process_id,"step_id":prior["step_id"],"ordinal":next_ordinal,"idempotent":True,"authority_effect":"NONE"}
    before=json.loads(run["state_vector_json"])
    spec=BRIDGES[bridge_id];delta=dict(spec["delta"])
    after={axis:float(before.get(axis,0.0))+float(delta[axis]) for axis in AXES}
    energy_proxy=sum(abs(float(delta[a])) for a in AXES)/len(AXES)
    stamp=now_fn();sid=_step_id(process_id,next_ordinal,bridge_id)
    conn.execute("""INSERT INTO hmk9d_process_steps(
      step_id,schema_id,process_id,ordinal,bridge_id,mode,state_before_json,vector_delta_json,
      state_after_json,energy_local_proxy,energy_basis,epistemic_status,evidence_json,observed_at,
      event_topic,authority_effect
    ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,'NONE')""",
    (sid,STEP_SCHEMA_ID,process_id,next_ordinal,bridge_id,spec.get("mode"),canonical(before),canonical(delta),
     canonical(after),energy_proxy,"DECLARED_BRIDGE_VECTOR_L1_MEAN_NOT_EMPIRICAL_RISK",epistemic_status,
     canonical(evidence),stamp,"hmk9d.step@v1"))
    complete=next_ordinal==len(CONVERSATION_PATH)
    conn.execute("""UPDATE hmk9d_process_runs
                    SET status=?,current_ordinal=?,state_vector_json=?,
                        energy_proxy_total=energy_proxy_total+?,updated_at=?
                    WHERE process_id=?""",
                 ("COMPLETE" if complete else "ACTIVE",next_ordinal,canonical(after),energy_proxy,stamp,process_id))
    conn.commit()
    return {"process_id":process_id,"step_id":sid,"ordinal":next_ordinal,"bridge_id":bridge_id,
            "status":"COMPLETE" if complete else "ACTIVE","idempotent":False,"authority_effect":"NONE"}


def dispatch_prefix(conn, process_id, *, message_id, correlation_id, scope_target, logical_drone_id,
                    material_worker_id, dispatch_authority, history_count, now_fn):
    evidence=[
      ("PLAN_PAUSE",{"message_id":message_id,"correlation_id":correlation_id,"fact":"OPERATOR_MESSAGE_PERSISTED"},"OBSERVED"),
      ("CORE_PERIPH",{"history_turns":int(history_count),"fact":"CAUSAL_HISTORY_COMPACTED"},"DERIVED"),
      ("SILENCE_EXHALE",{"serialization":"ONE_ACTIVE_TURN_PER_CORRELATION","fact":"TURN_SERIALIZATION_BARRIER"},"DERIVED"),
      ("VILLAGE_CITY",{"scope_target":scope_target,"selected_material_worker":material_worker_id,"fact":"MISSION_SCOPE_TO_SINGLE_EXECUTOR"},"DERIVED"),
      ("EDGE_PATIENCE",{"mode":"PATIENCE","history_turns":int(history_count),"fact":"SERIAL_CAUSAL_CHUNKING"},"DERIVED"),
      ("LOCUS_MEDIUM_MANDATE",{"logical_drone_id":logical_drone_id,"material_worker_id":material_worker_id,
                                "dispatch_authority":dispatch_authority,"direct_effect_authority":"NONE"},"OBSERVED"),
    ]
    run=conn.execute("SELECT current_ordinal FROM hmk9d_process_runs WHERE process_id=?",(process_id,)).fetchone()
    if not run:raise ValueError("hmk9d process missing")
    current=int(run["current_ordinal"])
    out=[]
    for ordinal,(bridge,refs,epistemic) in enumerate(evidence,1):
        if current>=ordinal:continue
        if current+1!=ordinal:raise ValueError("hmk9d dispatch prefix gap")
        out.append(advance(conn,process_id,bridge,refs,now_fn,epistemic_status=epistemic))
        current=ordinal
    return out


def reconcile_observed(conn, now_fn, *, limit=64):
    runs=conn.execute("""SELECT * FROM hmk9d_process_runs
                         WHERE status='ACTIVE' ORDER BY created_at,process_id LIMIT ?""",(int(limit),)).fetchall()
    advanced=0
    for run in runs:
        pid=run["process_id"];ordinal=int(run["current_ordinal"])
        assignment=None
        for candidate in conn.execute("""SELECT * FROM mission_execution_assignments
                                         WHERE input_json LIKE ? ORDER BY created_at DESC LIMIT 32""",
                                      ('%'+pid+'%',)).fetchall():
            try:payload=json.loads(candidate["input_json"] or "{}")
            except Exception:continue
            if payload.get("hmk9d_process_id")==pid:
                assignment=candidate;break
        if not assignment:continue
        if ordinal<7:
            call=conn.execute("""SELECT * FROM mission_model_calls
                                 WHERE assignment_id=? ORDER BY created_at DESC LIMIT 1""",
                              (assignment["assignment_id"],)).fetchone()
            if call:
                advance(conn,pid,"HUMAN_AI",{
                    "assignment_id":assignment["assignment_id"],"model_call_id":call["model_call_id"],
                    "provider":call["provider"],"model_declared":call["model_declared"],
                    "transport":call["transport"],"state":call["state"],
                    "material_worker_id":call["material_worker_id"],"logical_drone_id":call["logical_drone_id"],
                },now_fn,epistemic_status="OBSERVED");advanced+=1;ordinal=7
        if ordinal>=7 and ordinal<8 and assignment["state"]=="PASS":
            receipt=conn.execute("""SELECT receipt_id,result_digest,observed_at,status
                                    FROM mission_execution_receipts WHERE assignment_id=?
                                    ORDER BY observed_at DESC LIMIT 1""",(assignment["assignment_id"],)).fetchone()
            if receipt:
                advance(conn,pid,"THRESHOLD_TRANSITION",{
                    "assignment_id":assignment["assignment_id"],"receipt_id":receipt["receipt_id"],
                    "receipt_status":receipt["status"],"result_digest":receipt["result_digest"],
                    "meaning":"DURABLE_RESULT_COMMIT_ONLY;NO_AUTHORITY_GRANTED",
                },now_fn,epistemic_status="OBSERVED");advanced+=1;ordinal=8
        if ordinal>=8 and ordinal<9:
            reply=conn.execute("""SELECT message_id,content,applied_assignment_id,created_at
                                  FROM operator_messages
                                  WHERE correlation_id=? AND causation_id=? AND kind='RESPONSE'
                                    AND applied_assignment_id=?
                                  ORDER BY created_at DESC LIMIT 1""",
                               (run["correlation_id"],run["message_id"],assignment["assignment_id"])).fetchone()
            if reply:
                advance(conn,pid,"SEMANTICS_ENERGY",{
                    "response_message_id":reply["message_id"],"assignment_id":assignment["assignment_id"],
                    "response_digest":hashlib.sha256(str(reply["content"]).encode("utf-8")).hexdigest(),
                    "feedback":"CORRELATED_RESPONSE_PERSISTED",
                },now_fn,epistemic_status="OBSERVED");advanced+=1
    return {"runs_checked":len(runs),"steps_advanced":advanced,"authority_effect":"NONE"}


def thread_projection(conn, correlation_id, *, limit=100):
    runs=[dict(r) for r in conn.execute("""SELECT * FROM hmk9d_process_runs
                                          WHERE correlation_id=? ORDER BY created_at,process_id LIMIT ?""",
                                       (correlation_id,int(limit))).fetchall()]
    out=[]
    for run in runs:
        run["state_vector_9d"]=json.loads(run.pop("state_vector_json"))
        steps=[]
        for row in conn.execute("""SELECT * FROM hmk9d_process_steps
                                   WHERE process_id=? ORDER BY ordinal""",(run["process_id"],)).fetchall():
            item=dict(row)
            item["state_before_9d"]=json.loads(item.pop("state_before_json"))
            item["delta_vector_9d"]=json.loads(item.pop("vector_delta_json"))
            item["state_after_9d"]=json.loads(item.pop("state_after_json"))
            item["evidence"]=json.loads(item.pop("evidence_json"))
            steps.append(item)
        run["steps"]=steps
        out.append(run)
    return {"schema":"lion.hmk9d.thread-projection/v1","profile_id":PROFILE_ID,"axes":list(AXES),
            "processes":out,"authority_effect":"NONE"}
