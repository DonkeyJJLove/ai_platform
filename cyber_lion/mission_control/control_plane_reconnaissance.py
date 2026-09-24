"""Bounded, read-oriented control-plane reconnaissance capability.

The capability is selected by PhaseExecutionContract.capability_classes.  It
never grants authority, never interprets a phase name as permission, and never
executes model text.  Deterministic observations are persisted as mission
artifacts; local/SaaS model output remains advisory proposal data.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
from pathlib import Path
from typing import Any, Iterable

from . import global_scheduler as sched
from cyber_lion.contracts.phase_execution_contract import compile_panel_phase_contracts, preflight_execution_contracts, PhaseExecutionContractError

CAPABILITY_CLASS = "CONTROL_PLANE_RECONNAISSANCE"
CAPABILITY_ID = "CONTROL_PLANE_RECONNAISSANCE_V1"
CAPABILITY_VERSION = "1"
SCHEMA_ID = "lion.control-plane-reconnaissance/v1"
WINDOWS_OBSERVATION_SCHEMA = "lion.control-plane-windows-observation/v1"
WINDOWS_OBSERVATION_EVENT = "CONTROL_PLANE_WINDOWS_OBSERVATION"
EVIDENCE_BUNDLE_SCHEMA = "lion.control-plane-evidence-bundle/v1"
INTELLIGENCE_SCHEMA = "lion.control-plane-intelligence/v1"
SUCCESSOR_SCHEMA = "lion.successor-repair-lpcl-proposal/v1"
BASELINE_SCHEMA = "lion.control-plane-recon-baseline/v1"
LOCAL_ANALYSIS_SCHEMA = "lion.control-plane-local-analysis/v1"
LANGUAGE_GAP_SCHEMA = "lion.lpcl-language-gap-matrix/v1"
MATERIAL_EXECUTION_MODE = "CENTRAL_BOUNDED_READER_ATTRIBUTED_TO_MATERIAL_IDENTITIES"
TRAJECTORY_ROLES = ("PRIMARY_RECONSTRUCTION", "ADVERSARIAL_FALSIFICATION", "ALTERNATIVE_EXPLANATION")
LOCAL_MATERIAL = ("MD025", "MD026", "MD027")
DOCKER_FLEET_CURRENTNESS = Path(os.environ.get("LION_DOCKER_LOCAL_MODEL_CURRENTNESS", "/mnt/c/Users/d2j3/AppData/Local/LION/r23-autonomy/fleet-currentness.json"))


def _canon(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def digest(value: Any) -> str:
    return hashlib.sha256(_canon(value).encode("utf-8")).hexdigest()


def _json(value: str | None, default: Any) -> Any:
    try:
        return json.loads(value or "")
    except Exception:
        return default


def _table(conn: sqlite3.Connection, name: str) -> bool:
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone() is not None


def open_read_only(db_path: Path) -> sqlite3.Connection:
    path=Path(db_path).resolve()
    conn=sqlite3.connect("file:"+path.as_posix()+"?mode=ro",uri=True)
    conn.row_factory=sqlite3.Row
    conn.execute("PRAGMA query_only=ON")
    return conn


def _status_counts(conn: sqlite3.Connection, table: str, field: str = "status") -> dict[str, int]:
    if table=="saas_handoff_requests" and field=="status":
        rows=conn.execute("SELECT status,COUNT(*) FROM saas_handoff_requests GROUP BY status") if _table(conn,table) else ()
    elif table=="saas_session_bindings" and field=="status":
        rows=conn.execute("SELECT status,COUNT(*) FROM saas_session_bindings GROUP BY status") if _table(conn,table) else ()
    elif table=="mission_dual_evaluations" and field=="state":
        rows=conn.execute("SELECT state,COUNT(*) FROM mission_dual_evaluations GROUP BY state") if _table(conn,table) else ()
    else:
        raise ValueError("unregistered status-count query")
    return {str(r[0]): int(r[1]) for r in rows}


def _sha_file(path: Path) -> str | None:
    try:
        h=hashlib.sha256()
        with path.open("rb") as f:
            while True:
                b=f.read(1024*1024)
                if not b: break
                h.update(b)
        return h.hexdigest()
    except OSError:
        return None


def _root() -> Path:
    return Path(__file__).resolve().parents[2]


def _latest_windows_observation(conn: sqlite3.Connection, mission_id: str, phase_id: str) -> dict[str, Any] | None:
    rows=conn.execute(
        "SELECT observed_at,payload_json,payload_digest FROM protocol_messages WHERE mission_id=? AND protocol='EVIDENCE' AND from_id='LPCL_PANEL' AND phase=? ORDER BY id DESC LIMIT 30",
        (mission_id,phase_id),
    ).fetchall()
    for row in rows:
        payload=_json(row["payload_json"],{})
        if payload.get("event")==WINDOWS_OBSERVATION_EVENT and payload.get("schema")==WINDOWS_OBSERVATION_SCHEMA and payload.get("authority_effect")=="NONE":
            return {**payload,"protocol_observed_at":row["observed_at"],"protocol_payload_digest":row["payload_digest"]}
    return None


# Closed vocabulary: every token in an executable recon contract must resolve
# to one of these deterministic observation domains. Unknown tokens fail closed.
TOKEN_DOMAIN: dict[str,str] = {}
def _reg(domain: str, *tokens: str) -> None:
    for token in tokens:
        if token in TOKEN_DOMAIN and TOKEN_DOMAIN[token] != domain:
            raise RuntimeError(f"duplicate reconnaissance token {token}")
        TOKEN_DOMAIN[token]=domain

_reg("panel",
    "LIVE_8780_RUNTIME","PANEL_SOURCE","LOCAL_PANEL_CHECKOUT","LIVE_PANEL_PROJECTION","GITHUB_MASTER",
    "PROCESS_IDENTITY","PACKAGE_IDENTITY","GIT_IDENTITY","HEALTH_READBACK","PROCESS_ARGUMENTS",
    "FRONTEND_REVISION","CONTROL_PROVIDER_ROUTES","MODEL_ENDPOINT","THREAD_RUNTIME","PARSER_COMPARISON",
    "HEAD_TREE_READBACK","PACKAGE_SHA256","WORKTREE_STATE","RUNTIME_PROCESS_IDENTITY","EXACT_GITHUB_MASTER")
_reg("mission_control",
    "LIVE_8766_RUNTIME","MISSION_CONTROL_DB","MISSION_CONTROL_SOURCE","LIVE_8766_PACKAGE","LIVE_MISSION_CONTROL_PROJECTION",
    "API_ROUTE_MAP","DRIVER_STATE_MODEL","SCHEDULER_STATE_MODEL","PROCESS_CONTRACT_STATE","SQLITE_IDENTITY",
    "LPCL12_COMPILER_READBACK","PREFLIGHT_READBACK","CAPABILITY_REGISTRY_READBACK","EXACT_SOURCE_READBACK","RESTART_DURABILITY")
_reg("broker",
    "BROKER_DB","BROKER_SOURCE","CURRENT_BROKER_STATE","LIVE_BROKER_PROJECTION","SAAS_SESSION_BINDINGS","PRIVILEGED_BROKER_PACKAGE",
    "SCHEMA_READBACK","REQUEST_STATE_COUNTS","BINDING_STATE_COUNTS","RECEIPT_STATE_COUNTS","CLAIM_GENERATION_READBACK",
    "TRANSPORT_CLASSIFICATION","AUTOMATIC_CONSUMER_EVIDENCE","SESSION_STATE","PENDING_REQUEST_STATE",
    "RESPONDED_ROWS","BROKER_RECEIPT_ROWS","PROGRESS_STATE_HISTORY","MIGRATION_HISTORY","CURRENT_BROKER_DB","BROKER_TRANSPORT_READBACK")
_reg("thread",
    "THREAD_DB","THREAD_DELIVERY_SOURCE","DELIVERY_CANDIDATES","RECEIPT_LINKAGE","DEDUPLICATION_RULE","DELETION_BEHAVIOR")
_reg("dual",
    "DUAL_RESULT_STORE","DUAL_CREATE_PATH","LOCAL_RESULT_PATH","SAAS_LINK_PATH","JOIN_CONDITIONS")
_reg("post_astra",
    "CURRENT_POST_ASTRA_MISSION","CROSS_MISSION_STATE","CROSS_MISSION_RECEIPTS","CROSS_MISSION_BLOCKING_GATE")
_reg("projection","FIELD_BY_FIELD_PROJECTION_COMPARISON")
_reg("recon_history",
    "RECON_EVIDENCE_SET","ALL_RECON_PHASE_RECEIPTS","CLAIM_TO_EVIDENCE_MAP","UNCERTAINTY_REGISTER","COUNTEREXAMPLES",
    "IMPLEMENTATION_GAP_MATRIX","LANGUAGE_GAP_MATRIX")
_reg("artifacts",
    "CONTROL_PLANE_INTELLIGENCE_BUNDLE","INTELLIGENCE_BUNDLE","INTELLIGENCE_BUNDLE_DIGEST",
    "SUCCESSOR_LPCL_PROPOSAL_DIGEST","SUCCESSOR_CAPABILITY_MATRIX","SUCCESSOR_COMPLETION_CONTRACT")
_reg("baseline",
    "PRE_RECON_BASELINE","POST_RECON_BASELINE","STATE_DIFF","REQUEST_COUNT_DIFF","BINDING_DIFF","REPOSITORY_DIFF")
_reg("process_language","CANONICAL_PROCESS_LANGUAGE_SOURCE","LPCL12_PROCESS_CONTRACT","BACKWARD_COMPATIBILITY")
_reg("successor_lineage","CONTROL_PLANE_INTELLIGENCE_BUNDLE_READBACK")
_reg("docker_fleet","LIVE_DOCKER_FLEET","LOCAL_MODEL_IDENTITY","DOCKER_HEARTBEATS","UNIQUE_CONTAINER_IDS","DYNAMIC_DOCKER_BINDING","LOGICAL_MATERIAL_TOPOLOGY")

SEMANTIC_VERIFY_EVIDENCE = frozenset({
    "PARSER_COMPARISON","TRANSPORT_CLASSIFICATION","FIELD_BY_FIELD_PROJECTION_COMPARISON",
    "RESPONDED_ROWS","CROSS_MISSION_STATE","HEAD_TREE_READBACK","JOIN_CONDITIONS",
})
SAAS_ADVISORY_EVIDENCE = frozenset({"TRANSPORT_CLASSIFICATION","FIELD_BY_FIELD_PROJECTION_COMPARISON"})


def build_observation_plan(contract: dict[str,Any]) -> dict[str,Any]:
    requested=[]
    for token in list(contract.get("currentness_requirements") or [])+list(contract.get("evidence_requirements") or []):
        if token not in requested: requested.append(token)
    unsupported=[x for x in requested if x not in TOKEN_DOMAIN]
    domains=[]
    for token in requested:
        d=TOKEN_DOMAIN.get(token)
        if d and d not in domains:domains.append(d)
    return {"requested_tokens":requested,"domains":domains,"unsupported_tokens":unsupported,"digest":digest({"tokens":requested,"domains":domains})}


def trajectory_roles(contract: dict[str,Any]) -> tuple[str,...]:
    execution=str(contract.get("execution_class") or "")
    evidence=set(contract.get("evidence_requirements") or [])
    if execution=="COGNITIVE":return TRAJECTORY_ROLES
    if evidence & SEMANTIC_VERIFY_EVIDENCE:return (TRAJECTORY_ROLES[0],)
    return ()


def saas_advisory_required(contract: dict[str,Any]) -> bool:
    execution=str(contract.get("execution_class") or "")
    evidence=set(contract.get("evidence_requirements") or [])
    return execution=="COGNITIVE" or bool(evidence & SAAS_ADVISORY_EVIDENCE)


def _material_target(contract: dict[str,Any], plan: dict[str,Any]) -> int:
    execution=str(contract.get("execution_class") or "")
    if execution=="OBSERVE":base=4
    elif execution=="COGNITIVE":base=4
    elif execution=="VALIDATE":base=4
    else:base=6
    cross=sum(1 for d in plan.get("domains",[]) if d in {"panel","mission_control","broker","thread","dual","post_astra"})
    if execution=="VERIFY" and cross>=3:base=8
    return max(2,min(16,base))


def _cohort_logical_ids(ordinal: int) -> list[str]:
    start=(int(ordinal)-1)*8+1
    return [f"LD{i:03d}" for i in range(start,start+8)]


def _material_ids_for_phase(ordinal: int, target: int, *, semantic: bool) -> list[str]:
    start=((int(ordinal)-1)*4)%64+1
    ids=[]
    for off in range(target):
        n=((start-1+off)%64)+1;ids.append(f"MD{n:03d}")
    if semantic:
        forced=list(LOCAL_MATERIAL[:target]);base=[x for x in ids if x not in forced];ids=base[:max(0,target-len(forced))]+forced
    return list(dict.fromkeys(ids))[:target]


def ensure_material_leases(conn: sqlite3.Connection, mission_id: str, phase_id: str, contract: dict[str,Any], now_fn) -> list[dict[str,Any]]:
    plan=build_observation_plan(contract);target=_material_target(contract,plan);semantic=bool(trajectory_roles(contract))
    ordinal=int(contract["ordinal"])
    ready=sorted(str(r["logical_id"]) for r in conn.execute("SELECT logical_id FROM material_workers WHERE mission_id=? AND ready=1 ORDER BY logical_id",(mission_id,)) if r["logical_id"])
    if not ready:raise ValueError("recon material identity unavailable")
    target=min(target,len(ready))
    start=((ordinal-1)*4)%len(ready)
    rotated=ready[start:]+ready[:start]
    mids=rotated[:target]
    if semantic:
        forced=[x for x in LOCAL_MATERIAL if x in ready][:target]
        base=[x for x in mids if x not in forced]+[x for x in ready if x not in mids and x not in forced]
        mids=(base[:max(0,target-len(forced))]+forced)[:target]
    if _table(conn,"logical_drones"):
        lids_all=sorted(str(r["logical_id"]) for r in conn.execute("SELECT logical_id FROM logical_drones WHERE mission_id=? ORDER BY logical_id",(mission_id,)) if r["logical_id"])
    else:
        lids_all=_cohort_logical_ids(ordinal)
    if not lids_all:raise ValueError("recon logical identity unavailable")
    lstart=((ordinal-1)*8)%len(lids_all);lrot=lids_all[lstart:]+lids_all[:lstart];lids=lrot[:min(8,len(lrot))]
    stamp=now_fn()
    for idx,mid in enumerate(mids):
        row=conn.execute("SELECT * FROM mission_recon_material_leases WHERE mission_id=? AND phase_id=? AND material_drone_id=?",(mission_id,phase_id,mid)).fetchone()
        if row:continue
        lease_id="recon-lease-"+hashlib.sha256(f"{mission_id}|{phase_id}|{mid}".encode()).hexdigest()[:32]
        conn.execute("INSERT INTO mission_recon_material_leases VALUES(?,?,?,?,?,?,?,?,?,?)",
                     (lease_id,mission_id,phase_id,lids[idx%len(lids)],mid,"CONTROL_PLANE_RECONNAISSANCE",MATERIAL_EXECUTION_MODE,"ACTIVE",stamp,None))
    conn.commit()
    return [dict(r) for r in conn.execute("SELECT * FROM mission_recon_material_leases WHERE mission_id=? AND phase_id=? ORDER BY material_drone_id",(mission_id,phase_id))]


def release_material_leases(conn: sqlite3.Connection, mission_id: str, phase_id: str, now_fn) -> None:
    conn.execute("UPDATE mission_recon_material_leases SET state='RELEASED',released_at=COALESCE(released_at,?) WHERE mission_id=? AND phase_id=? AND state='ACTIVE'",(now_fn(),mission_id,phase_id));conn.commit()


def _mc_snapshot(conn: sqlite3.Connection, mission_id: str, phase_id: str) -> dict[str,Any]:
    root=_root();mission=conn.execute("SELECT * FROM missions WHERE mission_id=?",(mission_id,)).fetchone();process=conn.execute("SELECT * FROM mission_process_specs WHERE mission_id=?",(mission_id,)).fetchone();driver=conn.execute("SELECT * FROM mission_execution_drivers WHERE mission_id=?",(mission_id,)).fetchone();scheduler=conn.execute("SELECT * FROM mission_scheduler_state WHERE scheduler_id='GLOBAL_MISSION_SCHEDULER_V1'").fetchone();turn=conn.execute("SELECT * FROM mission_scheduler_turns WHERE mission_id=?",(mission_id,)).fetchone();pre=conn.execute("SELECT * FROM mission_execution_preflights WHERE mission_id=?",(mission_id,)).fetchone()
    contracts=[dict(r) for r in conn.execute("SELECT phase_id,contract_source,execution_class,capability_classes_json,effect_ceiling,binding_mode,contract_digest FROM mission_phase_execution_contracts WHERE mission_id=? ORDER BY ordinal",(mission_id,))]
    bindings=[dict(r) for r in conn.execute("SELECT * FROM mission_phase_capability_bindings WHERE mission_id=? ORDER BY phase_id,capability_class",(mission_id,))]
    carrier=(root/"mission_control_v3.py") if (root/"mission_control_v3.py").is_file() else (root/"tools/lion_mission_control_v3.py")
    source_files={"mission_control_v3.py":carrier,"cyber_lion/mission_control/global_scheduler.py":root/"cyber_lion/mission_control/global_scheduler.py","cyber_lion/contracts/phase_execution_contract.py":root/"cyber_lion/contracts/phase_execution_contract.py","cyber_lion/mission_control/control_plane_reconnaissance.py":root/"cyber_lion/mission_control/control_plane_reconnaissance.py","cyber_lion/process_language/lpcl.py":root/"cyber_lion/process_language/lpcl.py"}
    hashes={rel:_sha_file(path) for rel,path in source_files.items() if path.is_file()}
    source=carrier.read_text(encoding="utf-8",errors="replace") if carrier.is_file() else ""
    api_routes=sorted(set(re.findall(r"['\"](/api/v3/[^'\"]+)",source)))[:200]
    parser_match=re.search(r"(?ms)^def _lpcl_pairs\(.*?(?=^def |\Z)",source)
    return {
        "runtime_identity":{"pid":os.getpid(),"root":str(root),"source_hashes":hashes,"parser_sha256":hashlib.sha256((parser_match.group(0) if parser_match else "").encode()).hexdigest()},
        "db":{"path":str(Path(conn.execute("PRAGMA database_list").fetchone()[2])),"integrity":conn.execute("PRAGMA integrity_check").fetchone()[0],"schema_version":conn.execute("PRAGMA schema_version").fetchone()[0],"page_count":conn.execute("PRAGMA page_count").fetchone()[0]},
        "mission":dict(mission) if mission else None,"process":dict(process) if process else None,"driver":dict(driver) if driver else None,"scheduler":dict(scheduler) if scheduler else None,"turn":dict(turn) if turn else None,
        "preflight":_json(pre["preflight_json"],{}) if pre else None,"contracts":contracts,"bindings":bindings,"api_routes":api_routes,
    }


def _broker_snapshot(conn: sqlite3.Connection, mission_id: str) -> dict[str,Any]:
    tables={r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    schema={}
    if "saas_handoff_requests" in tables:schema["saas_handoff_requests"]=[r[1] for r in conn.execute("PRAGMA table_info(saas_handoff_requests)")]
    if "saas_session_bindings" in tables:schema["saas_session_bindings"]=[r[1] for r in conn.execute("PRAGMA table_info(saas_session_bindings)")]
    if "saas_broker_receipts" in tables:schema["saas_broker_receipts"]=[r[1] for r in conn.execute("PRAGMA table_info(saas_broker_receipts)")]
    requests=_status_counts(conn,"saas_handoff_requests");bindings=_status_counts(conn,"saas_session_bindings");receipts=int(conn.execute("SELECT COUNT(*) FROM saas_broker_receipts").fetchone()[0]) if "saas_broker_receipts" in tables else 0
    responded=int(conn.execute("SELECT COUNT(*) FROM saas_handoff_requests WHERE status='RESPONDED'").fetchone()[0]) if "saas_handoff_requests" in tables else 0
    pending=int(conn.execute("SELECT COUNT(*) FROM saas_handoff_requests WHERE status IN ('PENDING','WAITING_SUPERVISOR','WAITING_OPERATOR_OVERDUE','CLAIMED')").fetchone()[0]) if "saas_handoff_requests" in tables else 0
    max_generation=int(conn.execute("SELECT COALESCE(MAX(claim_generation),0) FROM saas_handoff_requests").fetchone()[0]) if "saas_handoff_requests" in tables else 0
    transports=[r[0] for r in conn.execute("SELECT DISTINCT transport FROM saas_handoff_requests WHERE transport IS NOT NULL")]+([r[0] for r in conn.execute("SELECT DISTINCT transport FROM saas_session_bindings WHERE transport IS NOT NULL")] if "saas_session_bindings" in tables else []) if "saas_handoff_requests" in tables else []
    autonomous=any("AUTONOM" in str(x).upper() for x in transports)
    active_binding=conn.execute("SELECT binding_id,mission_id,model_identity,transport,status,expires_at,binding_scope,authority_effect FROM saas_session_bindings WHERE status='BOUND' ORDER BY bound_at DESC LIMIT 1").fetchone() if "saas_session_bindings" in tables else None
    return {"schema":schema,"schema_digest":digest(schema),"request_state_counts":requests,"binding_state_counts":bindings,"receipt_count":receipts,"responded_count":responded,"pending_count":pending,"max_claim_generation":max_generation,"transports":sorted(set(str(x) for x in transports if x)),"autonomous_transport_claimed":autonomous,"active_binding":dict(active_binding) if active_binding else None}


def _dual_snapshot(conn: sqlite3.Connection) -> dict[str,Any]:
    out={"available":_table(conn,"mission_dual_evaluations") and _table(conn,"mission_dual_receipts")}
    if out["available"]:
        out["evaluation_count"]=int(conn.execute("SELECT COUNT(*) FROM mission_dual_evaluations").fetchone()[0]);out["receipt_count"]=int(conn.execute("SELECT COUNT(*) FROM mission_dual_receipts").fetchone()[0]);out["state_counts"]=_status_counts(conn,"mission_dual_evaluations","state")
    return out


def _post_astra_snapshot(conn: sqlite3.Connection) -> dict[str,Any]:
    mid="LION-POST-ASTRA-SAAS-TRANSPORT-TRUTH-REACQUIRE-R1";m=conn.execute("SELECT * FROM missions WHERE mission_id=?",(mid,)).fetchone();p=conn.execute("SELECT * FROM mission_process_specs WHERE mission_id=?",(mid,)).fetchone();d=conn.execute("SELECT * FROM mission_execution_drivers WHERE mission_id=?",(mid,)).fetchone();rc=int(conn.execute("SELECT COUNT(*) FROM mission_execution_receipts WHERE mission_id=?",(mid,)).fetchone()[0])
    return {"mission":dict(m) if m else None,"process":dict(p) if p else None,"driver":dict(d) if d else None,"receipt_count":rc}



def _docker_fleet_snapshot(conn: sqlite3.Connection, mission_id: str) -> dict[str,Any]:
    try:
        value=json.loads(DOCKER_FLEET_CURRENTNESS.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"valid":False,"reason":"CURRENTNESS_UNAVAILABLE:"+type(exc).__name__,"authority_effect":"NONE"}
    if not isinstance(value,dict):
        return {"valid":False,"reason":"CURRENTNESS_MALFORMED","authority_effect":"NONE"}
    claimed=value.get("currentness_digest");body=dict(value);body.pop("currentness_digest",None)
    digest_valid=isinstance(claimed,str) and bool(re.fullmatch(r"[0-9a-f]{64}",claimed)) and digest(body)==claimed
    if value.get("schema")!="lion.docker-local-model-fleet-currentness/v1" or value.get("physical_host")!="MOON":
        return {"valid":False,"reason":"CURRENTNESS_IDENTITY","currentness_digest":claimed,"digest_valid":digest_valid,"authority_effect":"NONE"}
    from datetime import datetime as _dt, timezone as _tz
    try:
        stamp=_dt.now(_tz.utc);observed=_dt.fromisoformat(str(value.get("observed_at") or "").replace("Z","+00:00"));currentness_age=(stamp-observed).total_seconds()
    except Exception:
        return {"valid":False,"reason":"CURRENTNESS_TIMESTAMP","currentness_digest":claimed,"digest_valid":digest_valid,"authority_effect":"NONE"}
    workers=value.get("workers") if isinstance(value.get("workers"),list) else []
    expected_ids={f"MD{i:03d}" for i in range(1,33)}
    worker_ids={str(w.get("material_worker_id") or "") for w in workers}
    container_ids={str(w.get("container_id") or "") for w in workers}
    heartbeat_ages=[]
    for worker in workers:
        try:
            hb=_dt.fromisoformat(str(worker.get("heartbeat_observed_at") or "").replace("Z","+00:00"));heartbeat_ages.append((stamp-hb).total_seconds())
        except Exception:
            heartbeat_ages.append(float("inf"))
    heartbeat_max=max(heartbeat_ages) if heartbeat_ages else float("inf")
    worker_health=bool(len(workers)==32 and worker_ids==expected_ids and len(container_ids)==32 and "" not in container_ids and all(
        bool(w.get("ready")) and w.get("container_state")=="running" and w.get("model")=="gpt-oss-20b-MXFP4" for w in workers
    ))
    mission=conn.execute("SELECT logical_count,material_target,materialized,ready,runtime_state,adapter FROM missions WHERE mission_id=?",(mission_id,)).fetchone() if _table(conn,"missions") else None
    db_workers=conn.execute("SELECT logical_id,pod_uid,ready FROM material_workers WHERE mission_id=? ORDER BY logical_id",(mission_id,)).fetchall() if _table(conn,"material_workers") else []
    logical_total=int(conn.execute("SELECT COUNT(*) FROM logical_drones WHERE mission_id=?",(mission_id,)).fetchone()[0]) if _table(conn,"logical_drones") else 0
    topology_count=int(conn.execute("SELECT COUNT(*) FROM mission_execution_assignments WHERE mission_id=? AND phase_id='__TOPOLOGY__'",(mission_id,)).fetchone()[0]) if _table(conn,"mission_execution_assignments") else 0
    topology_material_count=int(conn.execute("SELECT COUNT(DISTINCT material_drone_id) FROM mission_execution_assignments WHERE mission_id=? AND phase_id='__TOPOLOGY__'",(mission_id,)).fetchone()[0]) if _table(conn,"mission_execution_assignments") else 0
    db_worker_ids={str(r["logical_id"] or "") for r in db_workers};db_container_ids={str(r["pod_uid"] or "") for r in db_workers}
    mission_dict=dict(mission) if mission else {}
    binding_valid=bool(
        mission and int(mission["logical_count"])==logical_total==topology_count and int(mission["material_target"])==32
        and int(mission["materialized"])==32 and int(mission["ready"])==32
        and mission["runtime_state"]=="DOCKER_LOCAL_MODEL_FLEET_BOUND" and mission["adapter"]=="LPCL_DOCKER_LOCAL_MODEL"
        and len(db_workers)==32 and db_worker_ids==expected_ids and db_container_ids==container_ids
        and all(int(r["ready"])==1 for r in db_workers) and topology_material_count==32
    )
    valid=bool(
        digest_valid and -5.0<=currentness_age<=20.0 and -5.0<=min(heartbeat_ages or [float("inf")])
        and heartbeat_max<=20.0 and value.get("state")=="READY" and int(value.get("materialized") or 0)==32
        and int(value.get("ready") or 0)==32 and int(value.get("unique_worker_ids") or 0)==32
        and int(value.get("unique_container_ids") or 0)==32 and value.get("model")=="gpt-oss-20b-MXFP4"
        and worker_health and binding_valid
    )
    return {
        "valid":valid,
        "reason":None if valid else "DOCKER_FLEET_OR_BINDING_NOT_CURRENT",
        "schema":value.get("schema"),"physical_host":value.get("physical_host"),"state":value.get("state"),
        "observed_at":value.get("observed_at"),"currentness_age_seconds":round(currentness_age,6),
        "currentness_digest":claimed,"digest_valid":digest_valid,"materialized":value.get("materialized"),"ready":value.get("ready"),
        "unique_worker_ids":len(worker_ids),"unique_container_ids":len(container_ids),"model":value.get("model"),
        "heartbeat_max_age_seconds":round(heartbeat_max,6) if heartbeat_max!=float("inf") else None,
        "worker_ids":sorted(worker_ids),"container_ids":sorted(container_ids),"worker_health":worker_health,
        "binding_valid":binding_valid,"mission":mission_dict,"logical_total":logical_total,"topology_assignment_count":topology_count,
        "topology_material_count":topology_material_count,"db_container_ids":sorted(db_container_ids),
        "authority_effect":"NONE",
    }


def _successor_lineage_snapshot(conn: sqlite3.Connection, mission_id: str) -> dict[str,Any]:
    mission=conn.execute("SELECT mission_id,state,spec_digest,source_head,source_tree FROM missions WHERE mission_id=?",(mission_id,)).fetchone()
    if mission is None:
        return {"valid":False,"reason":"SUCCESSOR_MISSION_MISSING"}
    matches=[]
    for row in conn.execute("SELECT * FROM mission_artifacts WHERE artifact_type='SUCCESSOR_REPAIR_LPCL_PROPOSAL' AND authority_effect='NONE' ORDER BY updated_at,artifact_id"):
        content=_json(row["content_json"],{})
        text=content.get("lpcl_text")
        proposal_digest=content.get("proposal_digest")
        if proposal_digest!=mission["spec_digest"] or not isinstance(text,str):
            continue
        if hashlib.sha256(text.encode("utf-8")).hexdigest()!=mission["spec_digest"]:
            continue
        matches.append((row,content))
    if len(matches)!=1:
        return {"valid":False,"reason":"SUCCESSOR_PROPOSAL_CARDINALITY","proposal_match_count":len(matches),"mission_spec_digest":mission["spec_digest"]}
    proposal_row,proposal=matches[0]
    source_mid=proposal_row["mission_id"]
    predecessor=conn.execute("SELECT mission_id,state,spec_digest,source_head,source_tree FROM missions WHERE mission_id=?",(source_mid,)).fetchone()
    intel_row=conn.execute("SELECT * FROM mission_artifacts WHERE mission_id=? AND artifact_type='CONTROL_PLANE_INTELLIGENCE_BUNDLE' AND authority_effect='NONE' ORDER BY updated_at DESC LIMIT 1",(source_mid,)).fetchone()
    if predecessor is None or intel_row is None:
        return {"valid":False,"reason":"PREDECESSOR_INTELLIGENCE_MISSING","source_mission_id":source_mid}
    intel=_json(intel_row["content_json"],{})
    expected=proposal.get("intelligence_bundle_digest")
    observed=intel.get("bundle_digest")
    valid=bool(source_mid!=mission_id and predecessor["state"]=='COMPLETE' and isinstance(expected,str) and len(expected)==64 and observed==expected)
    return {
        "valid":valid,"reason":None if valid else "PREDECESSOR_INTELLIGENCE_DIGEST_MISMATCH",
        "source_mission_id":source_mid,"source_mission_state":predecessor["state"],
        "proposal_artifact_id":proposal_row["artifact_id"],"proposal_content_digest":proposal_row["content_digest"],
        "proposal_digest":proposal.get("proposal_digest"),"mission_spec_digest":mission["spec_digest"],
        "intelligence_artifact_id":intel_row["artifact_id"],"intelligence_content_digest":intel_row["content_digest"],
        "intelligence_bundle_digest":observed,"expected_intelligence_bundle_digest":expected,
        "authority_effect":"NONE",
    }


def _recon_history(conn: sqlite3.Connection, mission_id: str) -> dict[str,Any]:
    artifacts=sched.list_artifacts(conn,mission_id)
    receipts=[dict(r) for r in conn.execute("SELECT * FROM mission_generic_action_receipts WHERE mission_id=? ORDER BY observed_at",(mission_id,))]
    trajectories=[dict(r) for r in conn.execute("SELECT * FROM mission_recon_trajectories WHERE mission_id=? ORDER BY created_at",(mission_id,))]
    advisories=[dict(r) for r in conn.execute("SELECT * FROM mission_recon_saas_advisories WHERE mission_id=? ORDER BY created_at",(mission_id,))]
    return {"artifact_summaries":[{"artifact_id":a["artifact_id"],"artifact_type":a["artifact_type"],"phase_id":a["phase_id"],"content_digest":a["content_digest"],"revision":a["revision"]} for a in artifacts],"action_receipts":receipts,"trajectories":trajectories,"saas_advisories":advisories}


def _process_language_snapshot() -> dict[str,Any]:
    root=_root();paths=["cyber_lion/process_language/lpcl.py","cyber_lion/contracts/phase_execution_contract.py","LION/architecture/v1_4/LION_PROCESS_CONTRACT_PLANE.md"]
    hashes={rel:_sha_file(root/rel) for rel in paths if (root/rel).is_file()}
    return {"source_hashes":hashes,"canonical_lpcl_source_present":bool(hashes.get("cyber_lion/process_language/lpcl.py")),"lpcl12_compiler_present":bool(hashes.get("cyber_lion/contracts/phase_execution_contract.py")),"process_contract_doc_present":bool(hashes.get("LION/architecture/v1_4/LION_PROCESS_CONTRACT_PLANE.md"))}


def _baseline_core(conn: sqlite3.Connection, mission_id: str) -> dict[str,Any]:
    broker=_broker_snapshot(conn,mission_id);missions=[tuple(r) for r in conn.execute("SELECT mission_id,state,runtime_state,spec_digest FROM missions ORDER BY mission_id")]
    return {"mission_id":mission_id,"broker":{"responded_count":broker["responded_count"],"receipt_count":broker["receipt_count"],"binding_state_counts":broker["binding_state_counts"],"active_binding":broker["active_binding"]},"missions_digest":digest(missions),"mission_count":len(missions),"protocol_count":int(conn.execute("SELECT COUNT(*) FROM protocol_messages WHERE mission_id=?",(mission_id,)).fetchone()[0]),"action_receipt_count":int(conn.execute("SELECT COUNT(*) FROM mission_action_receipts WHERE mission_id=?",(mission_id,)).fetchone()[0])}


def capture_pre_recon_baselines(conn: sqlite3.Connection, now_fn) -> None:
    rows=conn.execute("SELECT DISTINCT mission_id FROM mission_phase_execution_contracts WHERE capability_classes_json LIKE '%CONTROL_PLANE_RECONNAISSANCE%'").fetchall()
    for row in rows:
        mid=row[0]
        if sched.artifact(conn,mid,"CONTROL_PLANE_RECON_BASELINE_PRE"):
            continue
        pre=conn.execute("SELECT preflight_json,preflight_digest,generated_at FROM mission_execution_preflights WHERE mission_id=?",(mid,)).fetchone()
        content={"schema":BASELINE_SCHEMA,"captured_before_registry_reconciliation":True,"captured_at":now_fn(),"preflight":_json(pre["preflight_json"],{}) if pre else None,"preflight_digest":pre["preflight_digest"] if pre else None,"core":_baseline_core(conn,mid),"authority_effect":"NONE"}
        sched.put_artifact(conn,mid,"CONTROL_PLANE_RECON_BASELINE_PRE",content,now_fn,schema_id=BASELINE_SCHEMA)


def _panel_snapshot(conn: sqlite3.Connection, mission_id: str, phase_id: str) -> dict[str,Any] | None:
    value=_latest_windows_observation(conn,mission_id,phase_id)
    return value.get("snapshot") if value else None


def _panel_fingerprint_from_snapshot(phase_id: str, panel: dict[str,Any] | None) -> str | None:
    if not isinstance(panel,dict): return None
    runtime=panel.get("runtime") or {}; repo=panel.get("repo") or {}; thread=panel.get("thread_db") or {}; github=repo.get("github_master") or {}; features=panel.get("source_features") or {}
    feature_digest=runtime.get("feature_vector_digest") or (digest(features) if features else None)
    value={"phase":phase_id,"runtime_loaded":runtime.get("runtime_source_sha256"),"gateway_loaded":runtime.get("gateway_source_sha256"),"feature_digest":feature_digest,"local":{"head":repo.get("local_head"),"tree":repo.get("local_tree")},"github":{"head":github.get("head"),"tree":github.get("tree")},"thread":thread.get("identity_digest")}
    required=(value["runtime_loaded"],value["gateway_loaded"],value["local"]["head"],value["local"]["tree"],value["github"]["head"],value["github"]["tree"],value["thread"])
    if any(not isinstance(x,str) or not x for x in required): return None
    return digest(value)


def _stable_mc_identity(value: dict[str,Any]) -> dict[str,Any]:
    runtime=value.get("runtime_identity") or {}; db=value.get("db") or {}; mission=value.get("mission") or {}; pre=value.get("preflight") or {}
    return {
        "source_hashes":runtime.get("source_hashes") or {},"parser_sha256":runtime.get("parser_sha256"),
        "db":{"schema_version":db.get("schema_version")},
        "mission":{"mission_id":mission.get("mission_id"),"spec_digest":mission.get("spec_digest"),"source_head":mission.get("source_head"),"source_tree":mission.get("source_tree"),"adapter":mission.get("adapter")},
        "preflight_digest":digest(pre) if pre else None,
        "contract_digests":sorted(str(x.get("contract_digest")) for x in (value.get("contracts") or []) if x.get("contract_digest")),
        "binding_digests":sorted(str(x.get("binding_digest")) for x in (value.get("bindings") or []) if x.get("binding_digest")),
    }


def _stable_broker_identity(value: dict[str,Any]) -> dict[str,Any]:
    binding=value.get("active_binding") or {}
    return {"schema_digest":value.get("schema_digest"),"request_state_counts":value.get("request_state_counts") or {},"binding_state_counts":value.get("binding_state_counts") or {},"receipt_count":value.get("receipt_count"),"responded_count":value.get("responded_count"),"pending_count":value.get("pending_count"),"max_claim_generation":value.get("max_claim_generation"),"transports":value.get("transports") or [],"autonomous_transport_claimed":value.get("autonomous_transport_claimed"),"active_binding":{"binding_id":binding.get("binding_id"),"mission_id":binding.get("mission_id"),"transport":binding.get("transport"),"status":binding.get("status"),"binding_scope":binding.get("binding_scope"),"authority_effect":binding.get("authority_effect")}}


def _stable_projection_identity(value: dict[str,Any]) -> dict[str,Any]:
    panel=value.get("panel") or {}; mc=value.get("mission_control") or {}; broker=value.get("broker") or {}
    pending=panel.get("pending") or {}; lease=panel.get("lease") or {}; receipt=panel.get("last_receipt") or {}; mission=mc.get("mission") or {}; process=mc.get("process") or {}
    return {"panel":{"channel":panel.get("channel"),"session":panel.get("session"),"transport":panel.get("transport"),"pending_count":panel.get("pending_count"),"pending_state":panel.get("pending_state"),"automatic_hop":panel.get("automatic_hop"),"authority":panel.get("authority"),"lease_state":lease.get("state"),"pending_request_id":pending.get("request_id"),"last_receipt_digest":receipt.get("receipt_digest")},"broker":_stable_broker_identity(broker),"mission_control":{"mission_id":mission.get("mission_id"),"state":mission.get("state"),"runtime_state":mission.get("runtime_state"),"spec_digest":mission.get("spec_digest"),"current_phase":process.get("current_phase"),"progress":process.get("progress")}}


def _stable_history_identity(value: dict[str,Any], phase_id: str) -> dict[str,Any]:
    arts=[{"artifact_type":x.get("artifact_type"),"phase_id":x.get("phase_id"),"content_digest":x.get("content_digest"),"revision":x.get("revision")} for x in (value.get("artifact_summaries") or []) if x.get("phase_id")!=phase_id]
    receipts=[{"phase_id":x.get("phase_id"),"action_ir_digest":x.get("action_ir_digest"),"evidence_digest":x.get("evidence_digest"),"status":x.get("status")} for x in (value.get("action_receipts") or []) if x.get("phase_id")!=phase_id]
    return {"artifacts":arts,"action_receipts":receipts}


def observation_generation_fingerprint(observations: dict[str,Any]) -> str | None:
    if not isinstance(observations,dict): return None
    phase_id=str(observations.get("phase_id") or ""); domains=observations.get("domains") or {}; stable={}
    for name in sorted(domains):
        value=domains.get(name)
        if value is None: stable[name]=None
        elif name=="panel": stable[name]=_panel_fingerprint_from_snapshot(phase_id,value)
        elif name=="mission_control": stable[name]=_stable_mc_identity(value)
        elif name=="broker": stable[name]=_stable_broker_identity(value)
        elif name=="thread": stable[name]={"identity_digest":value.get("identity_digest"),"schema_version":value.get("schema_version"),"integrity":value.get("integrity")}
        elif name=="dual": stable[name]={"available":value.get("available"),"evaluation_count":value.get("evaluation_count"),"receipt_count":value.get("receipt_count"),"state_counts":value.get("state_counts") or {}}
        elif name=="post_astra":
            m=value.get("mission") or {}; d=value.get("driver") or {}; stable[name]={"mission":{"mission_id":m.get("mission_id"),"state":m.get("state"),"runtime_state":m.get("runtime_state"),"spec_digest":m.get("spec_digest")},"driver":{"state":d.get("state"),"current_phase":d.get("current_phase"),"blocking_gate":d.get("blocking_gate"),"next_action":d.get("next_action")},"receipt_count":value.get("receipt_count")}
        elif name=="projection": stable[name]=_stable_projection_identity(value)
        elif name in {"recon_history","artifacts"}: stable[name]=_stable_history_identity(value if name=="recon_history" else {"artifact_summaries":value},phase_id)
        elif name=="process_language": stable[name]={"source_hashes":value.get("source_hashes") or {},"canonical_lpcl_source_present":value.get("canonical_lpcl_source_present"),"lpcl12_compiler_present":value.get("lpcl12_compiler_present")}
        elif name=="successor_lineage": stable[name]={k:value.get(k) for k in ("valid","source_mission_id","source_mission_state","proposal_digest","mission_spec_digest","intelligence_bundle_digest","expected_intelligence_bundle_digest","proposal_content_digest","intelligence_content_digest")}
        elif name=="docker_fleet": stable[name]={k:value.get(k) for k in ("valid","state","materialized","ready","unique_worker_ids","unique_container_ids","model","binding_valid","logical_total","topology_assignment_count","topology_material_count","container_ids","db_container_ids")}
        elif name=="baseline": stable[name]={"pre_digest":digest(value.get("pre")) if value.get("pre") else None,"post_core":{"mission_count":(value.get("post_core") or {}).get("mission_count"),"missions_digest":(value.get("post_core") or {}).get("missions_digest"),"broker":(value.get("post_core") or {}).get("broker")}}
        else: stable[name]=value
    return digest({"schema":"lion.recon-observation-generation-fingerprint/v1","phase_id":phase_id,"domains":stable})


def _bundle_observation_fingerprint(phase_id: str, content: dict[str,Any]) -> str | None:
    explicit=content.get("observation_fingerprint")
    if isinstance(explicit,str) and len(explicit)==64:return explicit
    # Backward-compatible generations used Windows source_fingerprint only.
    explicit=content.get("source_fingerprint")
    if isinstance(explicit,str) and len(explicit)==64:return explicit
    observations=content.get("observations") or {}
    return observation_generation_fingerprint(observations) or _panel_fingerprint_from_snapshot(phase_id,((observations.get("domains") or {}).get("panel")))


def _record_bundle_generation(conn: sqlite3.Connection, mission_id: str, phase_id: str, artifact: dict[str,Any], now_fn) -> dict[str,Any]:
    content=artifact.get("content") or {}; generations=sched.recon_evidence_generations(conn,mission_id,phase_id)
    if generations:
        current=generations[-1]
        if current["evidence_bundle_digest"]==artifact["content_digest"]:return current
    raw_generation=int(content.get("reacquisition_generation") or 0); generation=max(1,raw_generation)
    if generations:generation=max(generation,int(generations[-1]["generation"])+1)
    fp=_bundle_observation_fingerprint(phase_id,content); trigger=str(content.get("reacquisition_trigger") or ("LEGACY_FROZEN_BUNDLE_IMPORT" if raw_generation==0 else "INITIAL_BOUNDED_OBSERVATION"))
    return sched.record_recon_evidence_generation(conn,mission_id,phase_id,generation,fp,artifact["content_digest"],content,trigger,now_fn)


def evidence_reacquisition_request(conn: sqlite3.Connection, mission_id: str, phase_id: str, existing_bundle: dict[str,Any], contract: dict[str,Any], *, db_path: Path, require_parked: bool=True) -> dict[str,Any] | None:
    driver=conn.execute("SELECT state,blocking_gate,generation FROM mission_execution_drivers WHERE mission_id=?",(mission_id,)).fetchone()
    if not driver:return None
    if require_parked and (driver["state"] not in {"WAITING","BLOCKED"} or driver["blocking_gate"]!="EVIDENCE_INCOMPLETE"):return None
    ro=open_read_only(db_path)
    try:fresh,missing=collect_observations(ro,mission_id,phase_id,contract,db_path=db_path)
    finally:ro.close()
    if missing:return None
    latest_fp=observation_generation_fingerprint(fresh); current_fp=_bundle_observation_fingerprint(phase_id,existing_bundle.get("content") or {})
    if not latest_fp or not current_fp or latest_fp==current_fp:return None
    generations=sched.recon_evidence_generations(conn,mission_id,phase_id)
    if any(x.get("source_fingerprint")==latest_fp for x in generations):return None
    next_generation=max([int(x["generation"]) for x in generations] or [1])+1
    return {"mission_id":mission_id,"phase_id":phase_id,"current_observation_fingerprint":current_fp,"new_observation_fingerprint":latest_fp,"next_generation":next_generation,"driver_generation":int(driver["generation"]),"trigger":"NEW_BOUNDED_OBSERVATION_AFTER_EVIDENCE_INCOMPLETE","authority_effect":"NONE"}


def collect_observations(conn: sqlite3.Connection, mission_id: str, phase_id: str, contract: dict[str,Any], *, db_path: Path) -> tuple[dict[str,Any],list[str]]:
    plan=build_observation_plan(contract)
    if plan["unsupported_tokens"]:
        return {"plan":plan},["UNSUPPORTED_RECIPE:"+x for x in plan["unsupported_tokens"]]
    panel=_panel_snapshot(conn,mission_id,phase_id)
    domains={}
    # A current Windows observation is useful auxiliary evidence for source-feature
    # classification even when the phase did not make it a hard currentness token.
    if panel is not None:domains["panel"]=panel
    elif "panel" in plan["domains"]:domains["panel"]=None
    if "mission_control" in plan["domains"]:domains["mission_control"]=_mc_snapshot(conn,mission_id,phase_id)
    if "broker" in plan["domains"]:domains["broker"]=_broker_snapshot(conn,mission_id)
    if "thread" in plan["domains"]:domains["thread"]=(panel or {}).get("thread_db") if panel else None
    if "dual" in plan["domains"]:domains["dual"]=_dual_snapshot(conn)
    if "post_astra" in plan["domains"]:domains["post_astra"]=_post_astra_snapshot(conn)
    if "projection" in plan["domains"]:domains["projection"]={"panel":(panel or {}).get("saas_projection") if panel else None,"broker":_broker_snapshot(conn,mission_id),"mission_control":_mc_snapshot(conn,mission_id,phase_id)}
    if "recon_history" in plan["domains"]:domains["recon_history"]=_recon_history(conn,mission_id)
    if "artifacts" in plan["domains"]:domains["artifacts"]=_recon_history(conn,mission_id)["artifact_summaries"]
    if "process_language" in plan["domains"]:domains["process_language"]=_process_language_snapshot()
    if "successor_lineage" in plan["domains"]:domains["successor_lineage"]=_successor_lineage_snapshot(conn,mission_id)
    if "docker_fleet" in plan["domains"]:domains["docker_fleet"]=_docker_fleet_snapshot(conn,mission_id)
    if "baseline" in plan["domains"]:
        pre=sched.artifact(conn,mission_id,"CONTROL_PLANE_RECON_BASELINE_PRE");domains["baseline"]={"pre":pre["content"] if pre else None,"post_core":_baseline_core(conn,mission_id)}
    missing=[]
    for domain,value in domains.items():
        if value is None:missing.append("MISSING_DOMAIN:"+domain)
    lineage=domains.get("successor_lineage")
    if "successor_lineage" in plan["domains"] and (not isinstance(lineage,dict) or not lineage.get("valid")):
        missing.append("SUCCESSOR_LINEAGE_INVALID:"+str((lineage or {}).get("reason") or "UNKNOWN"))
    docker_fleet=domains.get("docker_fleet")
    if "docker_fleet" in plan["domains"] and (not isinstance(docker_fleet,dict) or not docker_fleet.get("valid")):
        missing.append("DOCKER_FLEET_INVALID:"+str((docker_fleet or {}).get("reason") or "UNKNOWN"))
    if "panel" in plan["domains"] and panel is None:missing.append("WINDOWS_OBSERVATION_REQUIRED")
    return {"schema":SCHEMA_ID,"plan":plan,"mission_id":mission_id,"phase_id":phase_id,"domains":domains,"authority_effect":"NONE"},sorted(set(missing))


def _model_view(observations: dict[str,Any]) -> dict[str,Any]:
    domains=observations.get("domains") or {};panel=domains.get("panel") or {};mc=domains.get("mission_control") or {};broker=domains.get("broker") or {};post=domains.get("post_astra") or {};projection=domains.get("projection") or {}
    return {
        "mission_id":observations.get("mission_id"),"phase_id":observations.get("phase_id"),"requested_tokens":observations.get("plan",{}).get("requested_tokens"),
        "panel":{"runtime":panel.get("runtime"),"repo":panel.get("repo"),"thread_db":panel.get("thread_db"),"model":panel.get("model"),"saas_projection":panel.get("saas_projection"),"source_features":panel.get("source_features")},
        "mission_control":{"runtime_identity":mc.get("runtime_identity"),"db":mc.get("db"),"mission":mc.get("mission"),"driver":mc.get("driver"),"scheduler":mc.get("scheduler"),"preflight":mc.get("preflight")},
        "broker":{"request_state_counts":broker.get("request_state_counts"),"binding_state_counts":broker.get("binding_state_counts"),"responded_count":broker.get("responded_count"),"receipt_count":broker.get("receipt_count"),"pending_count":broker.get("pending_count"),"transports":broker.get("transports"),"autonomous_transport_claimed":broker.get("autonomous_transport_claimed")},
        "post_astra":{"mission":post.get("mission"),"driver":post.get("driver"),"receipt_count":post.get("receipt_count")},
        "projection":projection,
    }


def _classification(observations: dict[str,Any], baseline: dict[str,Any] | None) -> dict[str,Any]:
    d=observations.get("domains") or {};panel=d.get("panel") or {};mc=d.get("mission_control") or {};broker=d.get("broker") or {};proj=d.get("projection") or {};post=d.get("post_astra") or {}
    pre=(baseline or {}).get("preflight") if baseline else None
    parser={"panel":(panel.get("source_features") or {}).get("lpcl_parser_sha256"),"mission_control":(mc.get("runtime_identity") or {}).get("parser_sha256"),"canonical":((d.get("process_language") or {}).get("source_hashes") or {}).get("cyber_lion/process_language/lpcl.py")}
    panel_saas=panel.get("saas_projection") or {};projection_diffs=[]
    if proj:
        b=proj.get("broker") or {}
        if panel_saas.get("transport") not in (None,*(b.get("transports") or [])):projection_diffs.append("transport")
        panel_pending=panel_saas.get("pending_count")
        if panel_pending is not None and int(panel_pending)!=int(b.get("pending_count") or 0):projection_diffs.append("pending_count")
        if panel_saas.get("automatic_hop") not in (False,"UNAVAILABLE",None):projection_diffs.append("automatic_hop")
    responded=int(broker.get("responded_count") or 0);receipts=int(broker.get("receipt_count") or 0)
    return {
        "parser_semantic_drift":{"identified":all(parser.values()),"hashes":parser,"classification":"MULTIPLE_IMPLEMENTATIONS_WITH_CANONICAL_COMPILER" if all(parser.values()) else "INCOMPLETE"},
        "initial_capability_preflight":{"captured":bool(pre),"bound_count":pre.get("bound_count") if isinstance(pre,dict) else None,"unbound_count":pre.get("unbound_count") if isinstance(pre,dict) else None,"classification":"VALID_BUT_UNBOUND" if isinstance(pre,dict) and pre.get("invalid_count")==0 and int(pre.get("unbound_count") or 0)>0 else "OTHER"},
        "saas_transport":{"transports":broker.get("transports"),"automatic_hop":False if not broker.get("autonomous_transport_claimed") else True,"operator_mediation_required":not broker.get("autonomous_transport_claimed"),"classification":"SESSION_MEDIATED_MANUAL" if not broker.get("autonomous_transport_claimed") else "AUTONOMOUS_CLAIM_PRESENT"},
        "projection":{"differences":projection_diffs,"classification":"MATCH" if not projection_diffs else "DRIFT"},
        "broker_receipts":{"responded":responded,"broker_receipts":receipts,"delta":responded-receipts,"classification":"LEGACY_OR_NON_BROKER_RECEIPTS_PRESENT" if responded!=receipts else "COMPLETE","backfill_required":responded>receipts},
        "post_astra":{"exists":bool(post.get("mission")),"state":((post.get("mission") or {}).get("state")),"gate":((post.get("driver") or {}).get("blocking_gate")),"classification":"FAIL_CLOSED_WAIT" if (post.get("driver") or {}).get("blocking_gate")=="CAPABILITY_NOT_AVAILABLE" else "OBSERVED"},
    }


def _source_features(panel: dict[str,Any]) -> dict[str,Any]:
    return (panel.get("source_features") or {}) if panel else {}


def _source_currentness_attestation(conn: sqlite3.Connection, mission_id: str, *, registered_head: str | None, registered_tree: str | None, current_head: str | None, current_tree: str | None) -> dict[str,Any] | None:
    if not _table(conn,"protocol_messages"):
        return None
    for row in conn.execute("SELECT from_id,protocol,payload_json FROM protocol_messages WHERE mission_id=? ORDER BY id DESC",(mission_id,)):
        payload=_json(row["payload_json"],{})
        if row["from_id"]!="BOOTSTRAP_RECONCILER" or row["protocol"]!="CURRENTNESS" or payload.get("event")!="SUCCESSOR_SOURCE_CURRENTNESS_REBOUND":
            continue
        if payload.get("authority_effect")!="NONE":
            continue
        if payload.get("registered_source_head")!=registered_head or payload.get("registered_source_tree")!=registered_tree:
            continue
        if payload.get("current_source_head")!=current_head or payload.get("current_source_tree")!=current_tree or payload.get("merge_commit")!=current_head:
            continue
        if payload.get("ancestry_verified") is not True or payload.get("changed_paths_verified") is not True or payload.get("lpcl_unchanged") is not True:
            continue
        repair_head=payload.get("repair_head");changed_digest=payload.get("changed_paths_digest");checks=payload.get("required_ci")
        if not isinstance(repair_head,str) or not re.fullmatch(r"[0-9a-f]{40}",repair_head):
            continue
        if not isinstance(changed_digest,str) or not re.fullmatch(r"[0-9a-f]{64}",changed_digest):
            continue
        if not isinstance(payload.get("pr_number"),int) or payload["pr_number"]<1:
            continue
        if not isinstance(checks,dict) or not checks or any(v!="PASS" for v in checks.values()):
            continue
        return payload
    return None


def _lpcl11_compat_probe() -> bool:
    try:
        contracts=compile_panel_phase_contracts({},"SYNTHETIC-LEGACY-MISSION",[{"id":"SYNTHETIC_PHASE"}],"LPCL/1.1")
        pf=preflight_execution_contracts(contracts,{})
        return len(contracts)==1 and pf.invalid_count==0 and contracts[0].contract_source=="LEGACY_INFERRED_SAFE"
    except (PhaseExecutionContractError,ValueError,TypeError):
        return False


def _lpcl12_compat_probe() -> bool:
    pairs={
        "PHASE_01_EXECUTION_CLASS":"VERIFY",
        "PHASE_01_CAPABILITY_CLASS":"MISSION_RUNTIME_RECONCILIATION",
        "PHASE_01_EFFECT_CEILING":"NONE",
        "PHASE_01_BINDING_MODE":"DYNAMIC",
        "PHASE_01_ON_MISSING_CAPABILITY":"WAIT_AND_DISCOVER",
        "PHASE_01_AUTO_RESUME":"TRUE",
        "PHASE_01_VERIFY_BEFORE_MUTATE":"TRUE",
        "PHASE_01_CURRENTNESS":"CURRENT_MISSION_RUNTIME",
        "PHASE_01_EVIDENCE":"LIVE_RUNTIME_READBACK",
        "PHASE_01_COMPLETION_01":"SYNTHETIC=PASS",
    }
    try:
        contracts=compile_panel_phase_contracts(pairs,"SYNTHETIC-MISSION",[{"id":"SYNTHETIC_PHASE"}],"LPCL/1.2")
        pf=preflight_execution_contracts(contracts,{})
        return len(contracts)==1 and pf.invalid_count==0 and pf.unbound_count==1
    except (PhaseExecutionContractError,ValueError,TypeError):
        return False


def _bootstrap_reconciler_evidence(conn: sqlite3.Connection, mission_id: str, event: str, *, registered_head: str | None, registered_tree: str | None, current_head: str | None, current_tree: str | None) -> dict[str,Any] | None:
    if not _table(conn,"protocol_messages"):
        return None
    for row in conn.execute("SELECT from_id,protocol,payload_json FROM protocol_messages WHERE mission_id=? ORDER BY id DESC",(mission_id,)):
        payload=_json(row["payload_json"],{})
        if row["from_id"]!="BOOTSTRAP_RECONCILER" or payload.get("event")!=event or payload.get("authority_effect")!="NONE":
            continue
        if payload.get("source_head")!=registered_head or payload.get("source_tree")!=registered_tree:
            continue
        if payload.get("current_source_head")!=current_head or payload.get("current_source_tree")!=current_tree:
            continue
        return payload
    return None


def _runtime_revision_terminal_evidence(conn: sqlite3.Connection, mission_id: str, *, mission: dict[str,Any], github_master: dict[str,Any], runtime_identity: dict[str,Any], db_identity: dict[str,Any], source_currentness_bound: bool) -> dict[str,Any] | None:
    payload=_bootstrap_reconciler_evidence(conn,mission_id,"SUCCESSOR_RUNTIME_REVISIONS_CONVERGED",registered_head=mission.get("source_head"),registered_tree=mission.get("source_tree"),current_head=github_master.get("head"),current_tree=github_master.get("tree"))
    if not payload or not source_currentness_bound:
        return None
    hashes=runtime_identity.get("source_hashes") or {};recon_sha=hashes.get("cyber_lion/mission_control/control_plane_reconnaissance.py")
    if payload.get("live_recon_sha256")!=recon_sha or not isinstance(recon_sha,str) or not re.fullmatch(r"[0-9a-f]{64}",recon_sha):
        return None
    if payload.get("restart_durability")!="PASS" or payload.get("service_state")!="active" or payload.get("db_integrity")!="ok" or db_identity.get("integrity")!="ok":
        return None
    if not isinstance(payload.get("live_package_digest"),str) or not re.fullmatch(r"[0-9a-f]{64}",payload["live_package_digest"]):
        return None
    if not isinstance(payload.get("deployment_control_receipt"),str) or not re.fullmatch(r"[0-9a-f]{64}",payload["deployment_control_receipt"]):
        return None
    return payload


def _preflight_binding_terminal_evidence(conn: sqlite3.Connection, mission_id: str, *, mission: dict[str,Any], github_master: dict[str,Any], preflight: dict[str,Any], source_currentness_bound: bool) -> dict[str,Any] | None:
    payload=_bootstrap_reconciler_evidence(conn,mission_id,"SUCCESSOR_PREFLIGHT_RUNTIME_BINDING_VISIBLE",registered_head=mission.get("source_head"),registered_tree=mission.get("source_tree"),current_head=github_master.get("head"),current_tree=github_master.get("tree"))
    if not payload or not source_currentness_bound:
        return None
    if payload.get("lpcl_digest")!=mission.get("spec_digest") or payload.get("preflight_digest")!=preflight.get("preflight_digest"):
        return None
    expected=(int(preflight.get("bound_count") or 0),int(preflight.get("unbound_count") or 0),int(preflight.get("invalid_count") or 0),str(preflight.get("mission_readiness") or ""))
    observed=(int(payload.get("bound_count") or 0),int(payload.get("unbound_count") or 0),int(payload.get("invalid_count") or 0),str(payload.get("mission_readiness") or ""))
    if expected!=(8,0,0,"READY_BOUND") or observed!=expected or int(payload.get("phase_count") or 0)!=8 or int(payload.get("contract_count") or 0)!=8:
        return None
    if payload.get("panel_acceptance")!="PASS" or not isinstance(payload.get("capability_registry_digest"),str) or not re.fullmatch(r"[0-9a-f]{64}",payload["capability_registry_digest"]):
        return None
    return payload


def _panel_projection_terminal_evidence(conn: sqlite3.Connection, mission_id: str, *, mission: dict[str,Any], github_master: dict[str,Any]) -> dict[str,Any] | None:
    payload=_bootstrap_reconciler_evidence(conn,mission_id,"SUCCESSOR_PANEL_TRUTH_PROJECTION_REPAIRED",registered_head=mission.get("source_head"),registered_tree=mission.get("source_tree"),current_head=github_master.get("head"),current_tree=github_master.get("tree"))
    if not payload:
        return None
    if payload.get("field_by_field_projection_comparison")!="PASS" or payload.get("browser_acceptance")!="PASS" or payload.get("exact_source_readback")!="PASS":
        return None
    if payload.get("lpcl_digest")!=mission.get("spec_digest"):
        return None
    if not isinstance(payload.get("comparison_digest"),str) or not re.fullmatch(r"[0-9a-f]{64}",payload["comparison_digest"]):
        return None
    return payload


def _broker_receipt_lineage_current(conn: sqlite3.Connection) -> tuple[bool,dict[str,int]]:
    if not (_table(conn,"saas_handoff_requests") and _table(conn,"saas_broker_receipts")):
        return False,{"missing":-1,"orphan":-1}
    missing=int(conn.execute("SELECT COUNT(*) FROM saas_handoff_requests r LEFT JOIN saas_broker_receipts b ON b.request_id=r.request_id WHERE r.status='RESPONDED' AND (r.receipt_digest IS NULL OR b.request_id IS NULL OR b.receipt_digest!=r.receipt_digest)").fetchone()[0])
    orphan=int(conn.execute("SELECT COUNT(*) FROM saas_broker_receipts b LEFT JOIN saas_handoff_requests r ON r.request_id=b.request_id WHERE r.request_id IS NULL").fetchone()[0])
    return missing==0 and orphan==0,{"missing":missing,"orphan":orphan}


def _prior_successor_phases_pass(conn: sqlite3.Connection, mission_id: str, terminal_phase: str) -> tuple[bool,dict[str,str]]:
    if not _table(conn,"mission_phases"):
        return False,{}
    rows=conn.execute("SELECT ordinal,phase_id,status FROM mission_phases WHERE mission_id=? ORDER BY ordinal",(mission_id,)).fetchall()
    status={str(r["phase_id"]):str(r["status"]) for r in rows}
    terminal=next((r for r in rows if r["phase_id"]==terminal_phase),None)
    if terminal is None:
        return False,status
    prior=[r for r in rows if int(r["ordinal"])<int(terminal["ordinal"])]
    return len(prior)==7 and all(str(r["status"])=="PASS" for r in prior),status


def derive_facts(conn: sqlite3.Connection, mission_id: str, phase_id: str, contract: dict[str,Any], observations: dict[str,Any], *, artifacts: dict[str,Any], baseline: dict[str,Any] | None, local_analysis: dict[str,Any] | None, saas_advisory: dict[str,Any] | None) -> tuple[dict[str,bool],dict[str,Any]]:
    d=observations.get("domains") or {};panel=d.get("panel") or {};mc=d.get("mission_control") or {};broker=d.get("broker") or {};thread=d.get("thread") or {};dual=d.get("dual") or {};post=d.get("post_astra") or {};hist=d.get("recon_history") or {};lang=d.get("process_language") or {};successor_lineage=d.get("successor_lineage") or {};docker_fleet=d.get("docker_fleet") or {}
    features=_source_features(panel);classes=_classification(observations,baseline)
    runtime=panel.get("runtime") or {};repo=panel.get("repo") or {};model=panel.get("model") or {};sources=panel.get("sources") or {}
    pre=mc.get("preflight") or {};driver=mc.get("driver") or {};scheduler=mc.get("scheduler") or {};contracts=mc.get("contracts") or []
    artifacts=artifacts or {}
    language_art=artifacts.get("LANGUAGE_GAP_MATRIX")
    intel_art=artifacts.get("CONTROL_PLANE_INTELLIGENCE_BUNDLE")
    succ_art=artifacts.get("SUCCESSOR_REPAIR_LPCL_PROPOSAL")
    post_diff=artifacts.get("CONTROL_PLANE_RECON_BASELINE_POST")
    github_master=repo.get("github_master") or {};mc_mission=mc.get("mission") or {};mc_runtime=mc.get("runtime_identity") or {};mc_db=mc.get("db") or {}
    exact_registered_source=bool(mc_mission.get("source_head") and mc_mission.get("source_tree") and github_master.get("head")==mc_mission.get("source_head") and github_master.get("tree")==mc_mission.get("source_tree"))
    source_currentness_attestation=None if exact_registered_source else _source_currentness_attestation(conn,mission_id,registered_head=mc_mission.get("source_head"),registered_tree=mc_mission.get("source_tree"),current_head=github_master.get("head"),current_tree=github_master.get("tree"))
    source_currentness_bound=bool(exact_registered_source or source_currentness_attestation)
    live_package_identified=bool((mc_runtime.get("source_hashes") or {}).get("mission_control_v3.py") and (mc_runtime.get("source_hashes") or {}).get("cyber_lion/mission_control/control_plane_reconnaissance.py"))
    broker_db_current=bool(mc_db.get("integrity")=="ok" and broker.get("schema_digest") and broker.get("request_state_counts") is not None)
    predecessor_intelligence_bound=bool(successor_lineage.get("valid") and successor_lineage.get("proposal_digest")==mc_mission.get("spec_digest") and successor_lineage.get("intelligence_bundle_digest")==successor_lineage.get("expected_intelligence_bundle_digest"))
    runtime_revision_evidence=_runtime_revision_terminal_evidence(conn,mission_id,mission=mc_mission,github_master=github_master,runtime_identity=mc_runtime,db_identity=mc_db,source_currentness_bound=source_currentness_bound)
    preflight_binding_evidence=_preflight_binding_terminal_evidence(conn,mission_id,mission=mc_mission,github_master=github_master,preflight=pre,source_currentness_bound=source_currentness_bound)
    panel_projection_evidence=_panel_projection_terminal_evidence(conn,mission_id,mission=mc_mission,github_master=github_master)
    broker_transports=list(broker.get("transports") or [])
    broker_transport_truthful=bool(broker.get("schema_digest") and broker.get("autonomous_transport_claimed") is False and any(str(x) in {"CHATGPT_SENTINELX_MCP","CHATGPT_SENTINELX_SESSION_MEDIATED"} for x in broker_transports))
    broker_receipt_lineage_ok,broker_receipt_counts=_broker_receipt_lineage_current(conn)
    legacy_lpcl_11_compatible=_lpcl11_compat_probe()
    lpcl_12_compatible=_lpcl12_compat_probe()
    prior_phases_pass,prior_phase_status=_prior_successor_phases_pass(conn,mission_id,phase_id)
    dynamic_docker_binding_ready=bool(docker_fleet.get("valid") and docker_fleet.get("binding_valid") and docker_fleet.get("worker_health") and docker_fleet.get("state")=="READY" and docker_fleet.get("model")=="gpt-oss-20b-MXFP4" and int(docker_fleet.get("logical_total") or 0)==int(docker_fleet.get("topology_assignment_count") or -1) and int(docker_fleet.get("topology_material_count") or 0)==32)
    panel_runtime_observed=bool(isinstance(panel,dict) and (panel.get("runtime") or {}).get("pid") and (panel.get("runtime") or {}).get("runtime_source_sha256"))
    baseline_and_fleet_bound=bool(source_currentness_bound and live_package_identified and broker_db_current and mc_db.get("integrity")=="ok" and panel_runtime_observed and dynamic_docker_binding_ready)
    terminal_validation=all((
        source_currentness_bound,
        runtime_revision_evidence is not None,
        preflight_binding_evidence is not None,
        broker_transport_truthful,
        broker_receipt_lineage_ok,
        panel_projection_evidence is not None,
        legacy_lpcl_11_compatible,
        lpcl_12_compatible,
        prior_phases_pass,
        mc_db.get("integrity")=="ok",
        bool(runtime.get("runtime_source_sha256") and runtime.get("gateway_source_sha256")),
    ))
    values: dict[str,bool] = {
        "BASELINE_AND_FLEET_BOUND":baseline_and_fleet_bound,
        "DYNAMIC_DOCKER_BINDING_READY":dynamic_docker_binding_ready,
        "PANEL_RUNTIME_IDENTITY_CAPTURED":bool(runtime.get("pid") and runtime.get("runtime_source_sha256") and runtime.get("gateway_source_sha256")),
        "MISSION_CONTROL_RUNTIME_IDENTITY_CAPTURED":bool((mc.get("runtime_identity") or {}).get("pid") and (mc.get("runtime_identity") or {}).get("source_hashes")),
        "GITHUB_MASTER_IDENTITY_CAPTURED":bool((repo.get("github_master") or {}).get("head") and (repo.get("github_master") or {}).get("tree")),
        "BROKER_DB_IDENTITY_CAPTURED":bool(broker.get("schema_digest") and broker.get("request_state_counts") is not None),
        "THREAD_DB_IDENTITY_CAPTURED":bool(thread.get("integrity")=="ok" and thread.get("identity_digest")),
        "PANEL_PROCESS_ARGUMENTS_RECONSTRUCTED":bool(runtime.get("argv") and runtime.get("mission_control_url")),
        "PANEL_FRONTEND_IDENTITY_CAPTURED":bool(runtime.get("frontend_revision")),
        "PANEL_PROVIDER_GRAPH_RECONSTRUCTED":bool(panel.get("provider_graph")),
        "LOCAL_MODEL_ROUTE_IDENTIFIED":bool(model.get("endpoint") and model.get("health") in {"ok","PASS"}),
        "THREAD_DELIVERY_RUNTIME_IDENTIFIED":bool(features.get("thread_delivery_exact_once") and sources.get("cyber_lion/app_coordination/saas_thread_delivery.py")),
        "PANEL_PARSER_IDENTIFIED":bool(features.get("lpcl_parser_sha256")),
        "MISSION_CONTROL_PARSER_IDENTIFIED":bool((mc.get("runtime_identity") or {}).get("parser_sha256")),
        "CANONICAL_COMPILER_IDENTIFIED":bool(lang.get("lpcl12_compiler_present")),
        "PARSER_SEMANTIC_DRIFT_CLASSIFIED":classes["parser_semantic_drift"]["classification"]!="INCOMPLETE",
        "PANEL_EMPTY_CAPABILITY_PREFLIGHT_CLASSIFIED":classes["initial_capability_preflight"]["classification"]=="VALID_BUT_UNBOUND",
        "MISSION_REGISTRATION_PATH_RECONSTRUCTED":bool((mc.get("runtime_identity") or {}).get("source_hashes") and features.get("panel_exact_source_state_machine")),
        "MISSION_ACTIVATION_PATH_RECONSTRUCTED":bool(features.get("panel_exact_source_state_machine") and (mc.get("mission") or {}).get("authorized_at")),
        "DRIVER_PATH_RECONSTRUCTED":bool(driver and (mc.get("runtime_identity") or {}).get("source_hashes")),
        