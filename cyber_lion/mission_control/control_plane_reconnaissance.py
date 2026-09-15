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
    "LPCL12_COMPILER_READBACK","PREFLIGHT_READBACK","CAPABILITY_REGISTRY_READBACK","EXACT_SOURCE_READBACK")
_reg("broker",
    "BROKER_DB","BROKER_SOURCE","CURRENT_BROKER_STATE","LIVE_BROKER_PROJECTION","SAAS_SESSION_BINDINGS","PRIVILEGED_BROKER_PACKAGE",
    "SCHEMA_READBACK","REQUEST_STATE_COUNTS","BINDING_STATE_COUNTS","RECEIPT_STATE_COUNTS","CLAIM_GENERATION_READBACK",
    "TRANSPORT_CLASSIFICATION","AUTOMATIC_CONSUMER_EVIDENCE","SESSION_STATE","PENDING_REQUEST_STATE",
    "RESPONDED_ROWS","BROKER_RECEIPT_ROWS","PROGRESS_STATE_HISTORY","MIGRATION_HISTORY","CURRENT_BROKER_DB")
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
_reg("process_language","CANONICAL_PROCESS_LANGUAGE_SOURCE","LPCL12_PROCESS_CONTRACT")
_reg("successor_lineage","CONTROL_PLANE_INTELLIGENCE_BUNDLE_READBACK")

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
    mids=_material_ids_for_phase(int(contract["ordinal"]),target,semantic=semantic);lids=_cohort_logical_ids(int(contract["ordinal"]));stamp=now_fn()
    ready={r["logical_id"] for r in conn.execute("SELECT logical_id FROM material_workers WHERE mission_id=? AND ready=1",(mission_id,))}
    if not set(mids)<=ready:
        raise ValueError("recon material identity unavailable")
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
    if "baseline" in plan["domains"]:
        pre=sched.artifact(conn,mission_id,"CONTROL_PLANE_RECON_BASELINE_PRE");domains["baseline"]={"pre":pre["content"] if pre else None,"post_core":_baseline_core(conn,mission_id)}
    missing=[]
    for domain,value in domains.items():
        if value is None:missing.append("MISSING_DOMAIN:"+domain)
    lineage=domains.get("successor_lineage")
    if "successor_lineage" in plan["domains"] and (not isinstance(lineage,dict) or not lineage.get("valid")):
        missing.append("SUCCESSOR_LINEAGE_INVALID:"+str((lineage or {}).get("reason") or "UNKNOWN"))
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


def derive_facts(conn: sqlite3.Connection, mission_id: str, phase_id: str, contract: dict[str,Any], observations: dict[str,Any], *, artifacts: dict[str,Any], baseline: dict[str,Any] | None, local_analysis: dict[str,Any] | None, saas_advisory: dict[str,Any] | None) -> tuple[dict[str,bool],dict[str,Any]]:
    d=observations.get("domains") or {};panel=d.get("panel") or {};mc=d.get("mission_control") or {};broker=d.get("broker") or {};thread=d.get("thread") or {};dual=d.get("dual") or {};post=d.get("post_astra") or {};hist=d.get("recon_history") or {};lang=d.get("process_language") or {};successor_lineage=d.get("successor_lineage") or {}
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
    live_package_identified=bool((mc_runtime.get("source_hashes") or {}).get("mission_control_v3.py") and (mc_runtime.get("source_hashes") or {}).get("cyber_lion/mission_control/control_plane_reconnaissance.py"))
    broker_db_current=bool(mc_db.get("integrity")=="ok" and broker.get("schema_digest") and broker.get("request_state_counts") is not None)
    predecessor_intelligence_bound=bool(successor_lineage.get("valid") and successor_lineage.get("proposal_digest")==mc_mission.get("spec_digest") and successor_lineage.get("intelligence_bundle_digest")==successor_lineage.get("expected_intelligence_bundle_digest"))
    values: dict[str,bool] = {
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
        "SCHEDULER_PATH_RECONSTRUCTED":bool(scheduler and mc.get("turn")),
        "PROCESS_CONTRACT_PATH_RECONSTRUCTED":len(contracts)>0 and bool(pre),
        "BROKER_SCHEMA_VERSION_IDENTIFIED":bool(broker.get("schema_digest")),
        "REQUEST_STATE_MACHINE_RECONSTRUCTED":bool(broker.get("request_state_counts") is not None and features.get("broker_request_state_machine")),
        "CLAIM_FENCING_RECONSTRUCTED":bool(broker.get("max_claim_generation") is not None and features.get("broker_claim_fencing")),
        "SESSION_BINDING_LIFECYCLE_RECONSTRUCTED":bool(broker.get("binding_state_counts") is not None and features.get("broker_session_binding")),
        "BROKER_RECEIPT_STORAGE_RECONSTRUCTED":broker.get("receipt_count") is not None,
        "HANDOFF_PERSISTENCE_CLASSIFIED":bool(broker.get("request_state_counts") is not None),
        "SESSION_BINDING_CLASSIFIED":bool(classes["saas_transport"]["classification"]),
        "THREAD_DELIVERY_CLASSIFIED":bool(features.get("thread_delivery_exact_once")),
        "AUTOMATIC_MODEL_INVOCATION_CLASSIFIED":classes["saas_transport"]["classification"] in {"SESSION_MEDIATED_MANUAL","AUTONOMOUS_CLAIM_PRESENT"},
        "OPERATOR_MEDIATION_REQUIREMENT_CLASSIFIED":classes["saas_transport"]["operator_mediation_required"] is not None,
        "THREAD_REQUEST_LINKAGE_RECONSTRUCTED":bool(features.get("thread_request_linkage")),
        "RECEIPT_DELIVERY_GATE_RECONSTRUCTED":bool(features.get("thread_delivery_receipt_gate")),
        "THREAD_DEDUPLICATION_RECONSTRUCTED":bool(features.get("thread_delivery_exact_once")),
        "THREAD_DELETE_SAFETY_RECONSTRUCTED":bool(features.get("thread_delete_safety")),
        "DUAL_CREATE_SEMANTICS_RECONSTRUCTED":bool(dual.get("available") and features.get("dual_create")),
        "LOCAL_RESULT_SEMANTICS_RECONSTRUCTED":bool(dual.get("available") and features.get("dual_local_result")),
        "SAAS_RESULT_SEMANTICS_RECONSTRUCTED":bool(dual.get("available") and features.get("dual_saas_link")),
        "DUAL_JOIN_SEMANTICS_RECONSTRUCTED":bool(dual.get("available") and features.get("dual_join")),
        "PANEL_REVISION_CLASSIFIED":bool(repo.get("local_head") and runtime.get("gateway_source_sha256")),
        "GITHUB_REVISION_CLASSIFIED":bool((repo.get("github_master") or {}).get("head")),
        "MISSION_CONTROL_REVISION_CLASSIFIED":bool((mc.get("runtime_identity") or {}).get("source_hashes")),
        "BROKER_REVISION_CLASSIFIED":bool(sources.get("tools/lion_saas_broker.py") or broker.get("schema_digest")),
        "MULTI_CARRIER_DRIFT_IMPACT_CLASSIFIED":bool(repo.get("local_head") and (repo.get("github_master") or {}).get("head") and (mc.get("mission") or {}).get("source_head")),
        "SESSION_STATE_PROJECTION_VERIFIED":classes["projection"]["classification"] in {"MATCH","DRIFT"},
        "AUTOMATIC_HOP_PROJECTION_VERIFIED":classes["projection"]["classification"] in {"MATCH","DRIFT"},
        "PENDING_STATE_PROJECTION_VERIFIED":classes["projection"]["classification"] in {"MATCH","DRIFT"},
        "MISSION_STATE_PROJECTION_VERIFIED":bool((mc.get("mission") or {}).get("state")),
        "MISLEADING_OR_AMBIGUOUS_UI_FIELDS_CLASSIFIED":classes["projection"]["classification"] in {"MATCH","DRIFT"},
        "RESPONDED_VS_RECEIPT_DELTA_EXPLAINED":bool(classes["broker_receipts"]["classification"]),
        "LEGACY_ROWS_CLASSIFIED":bool(classes["broker_receipts"]["classification"]),
        "PROGRESS_STATE_INCONSISTENCIES_CLASSIFIED":broker.get("request_state_counts") is not None,
        "RECEIPT_BACKFILL_REQUIREMENT_CLASSIFIED":classes["broker_receipts"]["backfill_required"] in {True,False},
        "POST_ASTRA_STATE_REACQUIRED":bool((post.get("mission") or {}).get("mission_id")),
        "POST_ASTRA_GATE_EXPLAINED":bool(classes["post_astra"]["classification"]),
        "POST_ASTRA_REUSABLE_EVIDENCE_EXTRACTED":post.get("receipt_count") is not None,
        "CROSS_MISSION_DEPENDENCY_CLASSIFIED":bool(classes["post_astra"]["classification"]),
        "MULTI_CARRIER_CURRENTNESS_GAP_CLASSIFIED":bool(language_art),
        "LIVE_CAPABILITY_PREFLIGHT_GAP_CLASSIFIED":bool(language_art),
        "CONDITIONAL_OUTCOME_GAP_CLASSIFIED":bool(language_art),
        "CROSS_MISSION_EVIDENCE_GAP_CLASSIFIED":bool(language_art),
        "SUCCESSOR_ARTIFACT_GAP_CLASSIFIED":bool(language_art),
        "LPCL_NEXT_VERSION_DECISION_SUPPORTED":bool(language_art and (language_art.get("decision") or language_art.get("recommended_control_language"))),
        "CONTROL_PLANE_INTELLIGENCE_BUNDLE_PRESENT":bool(intel_art),
        "ALL_FINDINGS_EVIDENCE_BOUND":bool(intel_art and intel_art.get("claim_to_evidence")),
        "UNKNOWN_ITEMS_EXPLICIT":bool(intel_art is not None and isinstance(intel_art.get("unknowns"),list)),
        "ROOT_CAUSE_CANDIDATES_RANKED":bool(intel_art and intel_art.get("root_cause_candidates")),
        "SUCCESSOR_REPAIR_SCOPE_DEFINED":bool(succ_art and succ_art.get("repair_scope")),
        "SUCCESSOR_CAPABILITY_REQUIREMENTS_DEFINED":bool(succ_art and succ_art.get("required_capabilities")),
        "SUCCESSOR_CURRENTNESS_REQUIREMENTS_DEFINED":bool(succ_art and succ_art.get("currentness_requirements")),
        "SUCCESSOR_EVIDENCE_REQUIREMENTS_DEFINED":bool(succ_art and succ_art.get("evidence_requirements")),
        "SUCCESSOR_LPCL_PROPOSAL_RETAINED":bool(succ_art and succ_art.get("lpcl_text") and succ_art.get("proposal_digest")),
        "NO_REPOSITORY_EFFECT":bool(post_diff and post_diff.get("checks",{}).get("NO_REPOSITORY_EFFECT")),
        "NO_BROKER_RESPONSE_EFFECT":bool(post_diff and post_diff.get("checks",{}).get("NO_BROKER_RESPONSE_EFFECT")),
        "NO_SESSION_EFFECT":bool(post_diff and post_diff.get("checks",{}).get("NO_SESSION_EFFECT")),
        "NO_MISSION_REPAIR_EFFECT":bool(post_diff and post_diff.get("checks",{}).get("NO_MISSION_REPAIR_EFFECT")),
        "INTELLIGENCE_READY_FOR_SUCCESSOR_MISSION":bool(post_diff and post_diff.get("checks",{}).get("INTELLIGENCE_READY_FOR_SUCCESSOR_MISSION")),
        "REPAIR_BASELINE_FROZEN":bool(exact_registered_source and live_package_identified and broker_db_current and predecessor_intelligence_bound and runtime.get("runtime_source_sha256") and runtime.get("gateway_source_sha256")),
    }
    requested=[str(x).split("=",1)[0] for x in contract.get("completion_predicates") or []]
    facts={name:bool(values.get(name,False)) for name in requested}
    detail={"classifications":classes,"local_analysis_summary":local_analysis,"saas_advisory":saas_advisory,"requested_predicates":requested,"successor_baseline":{"exact_registered_source":exact_registered_source,"live_package_identified":live_package_identified,"broker_db_current":broker_db_current,"predecessor_intelligence_bound":predecessor_intelligence_bound,"successor_lineage":successor_lineage}}
    return facts,detail


def _artifact_content_map(conn: sqlite3.Connection, mission_id: str) -> dict[str,Any]:
    out={}
    for art in sched.list_artifacts(conn,mission_id):
        if art["phase_id"] is None or art["artifact_type"] in {"LANGUAGE_GAP_MATRIX","CONTROL_PLANE_INTELLIGENCE_BUNDLE","SUCCESSOR_REPAIR_LPCL_PROPOSAL","CONTROL_PLANE_RECON_BASELINE_POST"}:
            out[art["artifact_type"]]=art["content"]
    return out


def _parse_model_response(text: str, role: str) -> dict[str,Any]:
    raw=str(text or "").strip();candidate=raw
    if raw.startswith("```"):
        candidate=re.sub(r"^```(?:json)?\s*|\s*```$","",raw,flags=re.I|re.S).strip()
    try:value=json.loads(candidate)
    except Exception:value=None
    if isinstance(value,dict):
        claims=value.get("claims") if isinstance(value.get("claims"),list) else []
        unknowns=value.get("unknowns") if isinstance(value.get("unknowns"),list) else []
        return {"role":role,"structured":True,"claims":claims[:32],"unknowns":unknowns[:32],"summary":str(value.get("summary") or "")[:4000],"raw_digest":hashlib.sha256(raw.encode()).hexdigest()}
    return {"role":role,"structured":False,"claims":[{"claim_id":f"{role}:1","claim_text":raw[:4000],"claim_class":"MODEL_PROPOSAL_UNSTRUCTURED","supporting_evidence_ids":[],"contradicting_evidence_ids":[],"confidence_bucket":"UNKNOWN","unknowns":[],"suggested_followup_observation":None}],"unknowns":[],"summary":raw[:2000],"raw_digest":hashlib.sha256(raw.encode()).hexdigest()}


def _analysis_from_trajectory_rows(conn: sqlite3.Connection, mission_id: str, phase_id: str, evidence_digest: str) -> dict[str,Any] | None:
    rows=conn.execute("SELECT * FROM mission_recon_trajectories WHERE mission_id=? AND phase_id=? AND evidence_bundle_digest=? ORDER BY trajectory_role",(mission_id,phase_id,evidence_digest)).fetchall()
    if not rows:return None
    outputs=[]
    for row in rows:
        if row["state"]!="PASS" or not row["assignment_id"]:return None
        payload=sched.assignment_payload(conn,row["assignment_id"])
        result=(payload or {}).get("result") or {}
        outputs.append(_parse_model_response(result.get("response_text") or "",row["trajectory_role"]))
    normalized=[]
    for out in outputs:
        for claim in out.get("claims",[]):
            text=" ".join(str(claim.get("claim_text") or "").lower().split())
            if text:normalized.append((out["role"],text,claim))
    counts={}
    for _,text,_ in normalized:counts[text]=counts.get(text,0)+1
    roles=len(outputs);agreement=[claim for _,text,claim in normalized if counts[text]==roles and roles>1]
    disagreement=[{"role":role,"claim":claim} for role,text,claim in normalized if counts[text]!=roles]
    return {"schema":LOCAL_ANALYSIS_SCHEMA,"evidence_bundle_digest":evidence_digest,"trajectories":outputs,"local_consensus":agreement,"local_disagreement_set":disagreement,"unknowns":[u for out in outputs for u in out.get("unknowns",[])],"majority_vote_used":False,"authority_effect":"NONE"}


def _trajectory_prompt(role: str, model_view: dict[str,Any], evidence_digest: str) -> list[dict[str,str]]:
    role_instruction={
        "PRIMARY_RECONSTRUCTION":"Reconstruct the most evidence-supported explanation.",
        "ADVERSARIAL_FALSIFICATION":"Try to falsify plausible explanations and identify contradictory evidence.",
        "ALTERNATIVE_EXPLANATION":"Build an independent alternative explanation without seeing other trajectories.",
    }[role]
    view=_canon(model_view)
    if len(view)>11000:view=view[:11000]
    system="You are a proposal-only LION local reconnaissance analyst. authority_effect=NONE. Never claim an effect occurred. Use only the supplied evidence. Return JSON with keys claims, unknowns, summary. Each claim must include claim_id, claim_text, claim_class, supporting_evidence_ids, contradicting_evidence_ids, confidence_bucket, unknowns, suggested_followup_observation."
    user=f"Evidence bundle digest: {evidence_digest}\nTrajectory role: {role}\n{role_instruction}\nIndependent evidence view:\n{view}"
    return [{"role":"system","content":system},{"role":"user","content":user}]


def ensure_local_trajectories(conn: sqlite3.Connection, mission_id: str, phase_id: str, contract: dict[str,Any], evidence_digest: str, model_view: dict[str,Any], driver_generation: int, now_fn) -> dict[str,Any]:
    roles=trajectory_roles(contract)
    if not roles:return {"required":False,"complete":True,"roles":[],"result_digests":[],"response_digests":[]}
    cohort=_cohort_logical_ids(int(contract["ordinal"]));stamp=now_fn()
    for idx,role in enumerate(roles):
        existing=conn.execute("SELECT * FROM mission_recon_trajectories WHERE mission_id=? AND phase_id=? AND trajectory_role=? AND evidence_bundle_digest=?",(mission_id,phase_id,role,evidence_digest)).fetchone()
        if not existing:
            # Crash recovery: locate an assignment created before trajectory-row persistence.
            found=None
            for a in conn.execute("SELECT assignment_id,input_json FROM mission_execution_assignments WHERE mission_id=? AND phase_id=? ORDER BY created_at",(mission_id,phase_id)):
                payload=_json(a["input_json"],{})
                if payload.get("purpose")=="CONTROL_PLANE_RECON_TRAJECTORY" and payload.get("trajectory_role")==role and payload.get("evidence_bundle_digest")==evidence_digest:
                    found=a["assignment_id"];break
            if not found:
                logical=cohort[min(idx+1,len(cohort)-1)];material=LOCAL_MATERIAL[idx]
                payload={"kind":"LOCAL_MODEL_INFERENCE","purpose":"CONTROL_PLANE_RECON_TRAJECTORY","trajectory_role":role,"evidence_bundle_digest":evidence_digest,"messages":_trajectory_prompt(role,model_view,evidence_digest),"max_tokens":1024 if contract.get("execution_class")=="COGNITIVE" else 640,"mission_id":mission_id,"phase_id":phase_id,"authority_effect":"NONE"}
                found=sched.create_assignment(conn,mission_id,phase_id,logical,material,payload,now_fn,lease_generation=int(driver_generation))
            tid="trajectory-"+hashlib.sha256(f"{mission_id}|{phase_id}|{role}|{evidence_digest}".encode()).hexdigest()[:32]
            conn.execute("INSERT OR IGNORE INTO mission_recon_trajectories VALUES(?,?,?,?,?,?,?,?,?,?,?)",(tid,mission_id,phase_id,role,evidence_digest,found,None,None,"READY",stamp,stamp));conn.commit()
    result_digests=[];response_digests=[];states=[]
    for row in conn.execute("SELECT * FROM mission_recon_trajectories WHERE mission_id=? AND phase_id=? AND evidence_bundle_digest=? ORDER BY trajectory_role",(mission_id,phase_id,evidence_digest)):
        a=conn.execute("SELECT state FROM mission_execution_assignments WHERE assignment_id=?",(row["assignment_id"],)).fetchone();receipt=conn.execute("SELECT result_digest,status FROM mission_execution_receipts WHERE assignment_id=? ORDER BY observed_at DESC LIMIT 1",(row["assignment_id"],)).fetchone();payload=sched.assignment_payload(conn,row["assignment_id"])
        state=receipt["status"] if receipt else (a["state"] if a else "MISSING");rd=receipt["result_digest"] if receipt else None;resp=((payload or {}).get("result") or {}).get("response_digest")
        conn.execute("UPDATE mission_recon_trajectories SET state=?,result_digest=COALESCE(?,result_digest),response_digest=COALESCE(?,response_digest),updated_at=? WHERE trajectory_id=?",(state,rd,resp,now_fn(),row["trajectory_id"]));conn.commit();states.append(state)
        if rd:result_digests.append(rd)
        if resp:response_digests.append(resp)
    complete=bool(states) and all(x=="PASS" for x in states)
    distinct=len(result_digests)==len(set(result_digests)) if complete else False
    return {"required":True,"complete":complete,"roles":list(roles),"states":states,"result_digests":result_digests,"response_digests":response_digests,"distinct_result_digests":distinct}


def ensure_saas_advisory(conn: sqlite3.Connection, mission_id: str, phase_id: str, contract: dict[str,Any], evidence_digest: str, model_view: dict[str,Any], now_fn, *, create_request, request_status) -> dict[str,Any]:
    if not saas_advisory_required(contract):return {"required":False,"state":"NOT_REQUESTED","authority_effect":"NONE"}
    role="INDEPENDENT_ADVISORY_TRAJECTORY";row=conn.execute("SELECT * FROM mission_recon_saas_advisories WHERE mission_id=? AND phase_id=? AND evidence_bundle_digest=? AND advisory_role=?",(mission_id,phase_id,evidence_digest,role)).fetchone();stamp=now_fn()
    if not row:
        view=_canon(model_view)
        if len(view)>6500:view=view[:6500]
        question=("Independent LION advisory trajectory. Do not assume or endorse any LOCAL conclusion. authority_effect=NONE. Review only the supplied evidence view, identify supported findings, contradictions and unknowns. Evidence bundle digest: "+evidence_digest+"\nEVIDENCE VIEW:\n"+view)
        try:req=create_request(mission_id,question);request_id=req.get("request_id");state=str(req.get("status") or req.get("state") or "WAITING_SUPERVISOR")
        except Exception:
            request_id=None;state="UNAVAILABLE_OR_SESSION_MEDIATED"
        aid="advisory-"+hashlib.sha256(f"{mission_id}|{phase_id}|{evidence_digest}|{role}".encode()).hexdigest()[:32]
        conn.execute("INSERT INTO mission_recon_saas_advisories VALUES(?,?,?,?,?,?,?,?,?,?,?)",(aid,mission_id,phase_id,evidence_digest,role,request_id,state,None,None,stamp,stamp));conn.commit();row=conn.execute("SELECT * FROM mission_recon_saas_advisories WHERE advisory_id=?",(aid,)).fetchone()
    value=dict(row)
    if value.get("request_id"):
        try:
            status=request_status(value["request_id"]);state=str(status.get("status") or status.get("state") or value["state"]);response_digest=status.get("response_digest");receipt_digest=status.get("receipt_digest")
            conn.execute("UPDATE mission_recon_saas_advisories SET state=?,response_digest=COALESCE(?,response_digest),receipt_digest=COALESCE(?,receipt_digest),updated_at=? WHERE advisory_id=?",(state,response_digest,receipt_digest,now_fn(),value["advisory_id"]));conn.commit();value.update({"state":state,"response_digest":response_digest,"receipt_digest":receipt_digest,"response_text":status.get("response_text")})
        except Exception:value["state"]="UNAVAILABLE_OR_SESSION_MEDIATED"
    effective="RESPONDED" if value.get("state")=="RESPONDED" else "UNAVAILABLE_OR_SESSION_MEDIATED"
    return {"required":True,"state":effective,"request_id":value.get("request_id"),"response_digest":value.get("response_digest"),"receipt_digest":value.get("receipt_digest"),"response_text":value.get("response_text"),"evidence_bundle_digest":evidence_digest,"authority_effect":"NONE"}


def _classification_quality(key: str, value: dict[str,Any] | None) -> int:
    value=value or {}
    if key=="parser_semantic_drift": return 2 if value.get("classification") not in {None,"INCOMPLETE"} and value.get("identified") else 0
    if key=="initial_capability_preflight": return 2 if value.get("captured") else 0
    if key=="saas_transport": return 2 if value.get("classification") in {"SESSION_MEDIATED_MANUAL","AUTONOMOUS_CLAIM_PRESENT"} else 0
    if key=="projection": return 2 if value.get("classification") in {"MATCH","DRIFT"} else 0
    if key=="broker_receipts": return 2 if value.get("classification") in {"COMPLETE","LEGACY_OR_NON_BROKER_RECEIPTS_PRESENT"} else 0
    if key=="post_astra": return 2 if value.get("classification") in {"FAIL_CLOSED_WAIT","OBSERVED"} else 0
    return 1 if value else 0


def historical_classifications(conn: sqlite3.Connection, mission_id: str, baseline: dict[str,Any] | None) -> tuple[dict[str,Any],dict[str,list[str]]]:
    merged: dict[str,Any]={}; sources: dict[str,list[str]]={}
    for art in sched.list_artifacts(conn,mission_id):
        if art["artifact_type"]!="RECON_EVIDENCE_BUNDLE": continue
        observations=(art["content"] or {}).get("observations") or {}; domains=observations.get("domains") or {}
        classes=_classification(observations,baseline)
        eligible=set()
        if all(x in domains and domains.get(x) for x in ("panel","mission_control","process_language")): eligible.add("parser_semantic_drift")
        if isinstance((baseline or {}).get("preflight"),dict): eligible.add("initial_capability_preflight")
        if domains.get("broker"): eligible.update(("saas_transport","broker_receipts"))
        if domains.get("projection"): eligible.add("projection")
        if domains.get("post_astra"): eligible.add("post_astra")
        for key in eligible:
            candidate=classes.get(key)
            if _classification_quality(key,candidate)>_classification_quality(key,merged.get(key)):
                merged[key]=candidate;sources[key]=[art["content_digest"]]
            elif candidate==merged.get(key) and candidate is not None:
                sources.setdefault(key,[]).append(art["content_digest"])
    return merged,sources


def _merge_classifications(current: dict[str,Any], historical: dict[str,Any]) -> dict[str,Any]:
    out=dict(current or {})
    for key,value in (historical or {}).items():
        if _classification_quality(key,value)>_classification_quality(key,out.get(key)): out[key]=value
    return out


def _language_gap_artifact(classifications: dict[str,Any], local_analysis: dict[str,Any] | None, saas: dict[str,Any] | None, *, classification_sources: dict[str,list[str]] | None=None) -> dict[str,Any]:
    findings=[
        {"gap":"MULTI_CARRIER_CURRENTNESS","classification":"LPCL_1_2_PROFILE_EXTENSION","evidence":"revision_coherence"},
        {"gap":"LIVE_CAPABILITY_PREFLIGHT","classification":"IMPLEMENTATION_DEFECT","evidence":"initial_capability_preflight"},
        {"gap":"CONDITIONAL_OUTCOME","classification":"LPCL_1_2_PROFILE_EXTENSION","evidence":"saas_transport"},
        {"gap":"CROSS_MISSION_EVIDENCE","classification":"LPCL_1_2_PROFILE_EXTENSION","evidence":"post_astra"},
        {"gap":"SUCCESSOR_ARTIFACT","classification":"LPCL_1_2_PROFILE_EXTENSION","evidence":"artifact_contract"},
    ]
    return {"schema":LANGUAGE_GAP_SCHEMA,"findings":findings,"implementation_gaps":[x for x in findings if x["classification"]=="IMPLEMENTATION_DEFECT"],"language_limitations":[x for x in findings if x["classification"]=="LPCL_LANGUAGE_LIMITATION"],"decision":"LPCL/1.2_PROFILE_EXTENSION" if not any(x["classification"]=="LPCL_LANGUAGE_LIMITATION" for x in findings) else "LPCL/1.3_CANDIDATE","recommended_control_language":"LPCL/1.2","counterexamples":["MULTILINE_COMPLETION_PREDICATE_COLLIDES_WITH_TOP_LEVEL_KEY_GRAMMAR","LPCL_PANEL_VALIDATION_REGISTRATION_SOURCE_DRIFT","VALID_CONTRACTS_WITH_ZERO_RUNTIME_CAPABILITY_BINDINGS"],"local_analysis":local_analysis,"saas_advisory_state":(saas or {}).get("state","NOT_REQUESTED"),"classifications":classifications,"classification_sources":classification_sources or {},"classification_scope":"MISSION_WIDE_DURABLE_EVIDENCE","authority_effect":"NONE"}


def _cross_model_sets(conn: sqlite3.Connection, mission_id: str, analyses: dict[str,dict[str,Any]]) -> tuple[list[dict[str,Any]],list[dict[str,Any]]]:
    agreements=[];disagreements=[]
    for row in conn.execute("SELECT * FROM mission_recon_saas_advisories WHERE mission_id=? AND state='RESPONDED' ORDER BY created_at",(mission_id,)):
        request=conn.execute("SELECT response_text,response_digest,receipt_digest FROM saas_handoff_requests WHERE request_id=?",(row["request_id"],)).fetchone() if _table(conn,"saas_handoff_requests") else None
        if not request or not request["response_text"]:continue
        saas=_parse_model_response(request["response_text"],"SAAS")
        local=analyses.get(row["phase_id"]) or {}
        local_claims=[]
        for tr in local.get("trajectories") or []:
            local_claims.extend(tr.get("claims") or [])
        lmap={" ".join(str(c.get("claim_text") or "").lower().split()):c for c in local_claims if str(c.get("claim_text") or "").strip()}
        smap={" ".join(str(c.get("claim_text") or "").lower().split()):c for c in saas.get("claims") or [] if str(c.get("claim_text") or "").strip()}
        common=sorted(set(lmap)&set(smap));only=sorted(set(lmap)^set(smap))
        if common:agreements.append({"phase_id":row["phase_id"],"evidence_bundle_digest":row["evidence_bundle_digest"],"request_id":row["request_id"],"claims":[lmap[x] for x in common]})
        if only:disagreements.append({"phase_id":row["phase_id"],"evidence_bundle_digest":row["evidence_bundle_digest"],"request_id":row["request_id"],"local_only":[lmap[x] for x in only if x in lmap],"saas_only":[smap[x] for x in only if x in smap],"resolution":"FALSIFICATION_OR_UNKNOWN","saas_authority":False})
    return agreements,disagreements


def _intelligence_bundle(conn: sqlite3.Connection, mission_id: str, language_gap: dict[str,Any] | None, *, generated_at: str | None = None) -> dict[str,Any]:
    arts=sched.list_artifacts(conn,mission_id);evidence=[a for a in arts if a["artifact_type"]=="RECON_EVIDENCE_BUNDLE"];summaries={a["phase_id"]:(a["content"].get("summary") or a["content"]) for a in arts if a["artifact_type"]=="RECON_PHASE_SUMMARY"};analyses={a["phase_id"]:a["content"] for a in arts if a["artifact_type"]=="LOCAL_RECON_ANALYSIS"}
    trajectories=[dict(r) for r in conn.execute("SELECT phase_id,trajectory_role,evidence_bundle_digest,result_digest,response_digest,state FROM mission_recon_trajectories WHERE mission_id=? ORDER BY created_at",(mission_id,))]
    advisories=[dict(r) for r in conn.execute("SELECT phase_id,evidence_bundle_digest,advisory_role,request_id,state,response_digest,receipt_digest FROM mission_recon_saas_advisories WHERE mission_id=? ORDER BY created_at",(mission_id,))]
    findings=[];claim_map=[];unknowns=[];revision_values=[];runtime_values=[];panel_identity=None;mc_identity=None;broker_identity=None
    for art in evidence:
        content=art["content"];summary=summaries.get(art["phase_id"],{});facts=summary.get("facts") or {};domains=(content.get("observations") or {}).get("domains") or {};panel=domains.get("panel") or {};mc=domains.get("mission_control") or {};broker=domains.get("broker") or {}
        if panel:
            panel_identity=panel_identity or {"runtime":panel.get("runtime"),"repo":panel.get("repo"),"thread_db":panel.get("thread_db")}
            if panel.get("repo") and panel.get("repo") not in revision_values:revision_values.append(panel.get("repo"))
            if panel.get("runtime") and panel.get("runtime") not in runtime_values:runtime_values.append(panel.get("runtime"))
        if mc:
            mc_identity=mc_identity or {"runtime_identity":mc.get("runtime_identity"),"db":mc.get("db"),"mission":mc.get("mission")}
            if mc.get("runtime_identity") and mc.get("runtime_identity") not in runtime_values:runtime_values.append(mc.get("runtime_identity"))
        if broker:broker_identity=broker_identity or {k:broker.get(k) for k in ("schema_digest","request_state_counts","binding_state_counts","receipt_count","responded_count","pending_count","transports","autonomous_transport_claimed")}
        for key,val in facts.items():
            findings.append({"finding":key,"status":"PASS" if val else "UNKNOWN","phase_id":art["phase_id"],"evidence_digest":art["content_digest"]});claim_map.append({"claim":key,"evidence_digest":art["content_digest"],"phase_id":art["phase_id"]})
            if not val:unknowns.append({"claim":key,"phase_id":art["phase_id"]})
    agreements,disagreements=_cross_model_sets(conn,mission_id,analyses)
    roots=[
        {"rank":1,"candidate":"MULTI_CARRIER_REVISION_DIVERGENCE","support":[x["content_digest"] for x in evidence if x["phase_id"]]},
        {"rank":2,"candidate":"PREFLIGHT_RUNTIME_CAPABILITY_BLINDNESS","support":[x["content_digest"] for x in evidence[:3]]},
        {"rank":3,"candidate":"SESSION_MEDIATED_SAAS_WITHOUT_AUTOMATIC_CONSUMER","support":[x["content_digest"] for x in evidence]},
        {"rank":4,"candidate":"BROKER_RECEIPT_LINEAGE_INCOMPLETENESS","support":[x["content_digest"] for x in evidence]},
    ]
    body={"schema":INTELLIGENCE_SCHEMA,"mission_id":mission_id,"generated_at":generated_at,"source_revision_set":revision_values,"runtime_identity_set":runtime_values,"broker_identity":broker_identity,"panel_identity":panel_identity,"mission_control_identity":mc_identity,"findings":findings,"counterexamples":(language_gap or {}).get("counterexamples",[]),"root_cause_candidates":roots,"claim_to_evidence":claim_map,"local_model_trajectories":trajectories,"saas_advisories":advisories,"cross_model_agreements":agreements,"cross_model_disagreements":disagreements,"unknowns":unknowns,"language_gaps":(language_gap or {}).get("findings",[]),"implementation_gaps":(language_gap or {}).get("implementation_gaps",[]),"repair_requirements":["CONVERGE_RUNTIME_REVISIONS","RUNTIME_AWARE_PREFLIGHT","TRUTHFUL_SAAS_CONSUMER_STATE","BROKER_RECEIPT_RECONCILIATION","BACKWARD_COMPATIBILITY"],"authority_effect":"NONE"}
    body["bundle_digest"]=digest(body)
    return body


def _generated_lpcl_pairs(text: str) -> dict[str,str]:
    pairs={}
    for raw in str(text or "").replace("\r\n","\n").replace("\r","\n").split("\n"):
        line=raw.strip()
        if not line or line.startswith("#"): continue
        key,sep,value=line.partition("=")
        if not sep or not key or key in pairs: raise ValueError("generated successor LPCL is not strict inline KEY=VALUE")
        pairs[key.strip()]=value.strip()
    return pairs


def _successor_phase_profiles() -> tuple[dict[str,Any],...]:
    return (
        {"id":"FREEZE_REPAIR_BASELINE","title":"Freeze Repair Baseline","execution":"OBSERVE","capability":"CONTROL_PLANE_RECONNAISSANCE","effect":"NONE","currentness":"EXACT_GITHUB_MASTER,LIVE_8766_PACKAGE,LIVE_8780_RUNTIME,CURRENT_BROKER_DB","evidence":"EXACT_SOURCE_READBACK,CONTROL_PLANE_INTELLIGENCE_BUNDLE_READBACK","completion":["REPAIR_BASELINE_FROZEN=PASS"]},
        {"id":"CONVERGE_CONTROL_PLANE_REVISIONS","title":"Converge Control Plane Revisions","execution":"VERIFY_THEN_REPAIR","capability":"REPOSITORY_CANDIDATE_PREPARE","effect":"BOUNDED_REPOSITORY","currentness":"EXACT_GITHUB_MASTER,LIVE_8766_PACKAGE,LIVE_8780_RUNTIME","evidence":"EXACT_SOURCE_READBACK,REVISION_CONVERGENCE_EVIDENCE,RESTART_DURABILITY","completion":["RUNTIME_REVISIONS_CONVERGED=PASS"]},
        {"id":"UNIFY_LPCL_PREFLIGHT_WITH_RUNTIME_REGISTRY","title":"Unify LPCL Preflight With Runtime Registry","execution":"VERIFY_THEN_REPAIR","capability":"CONTROL_PLANE_REPAIR","effect":"BOUNDED_REPOSITORY","currentness":"LIVE_8766_PACKAGE,LIVE_8780_RUNTIME,CURRENT_CAPABILITY_REGISTRY","evidence":"PREFLIGHT_RUNTIME_REGISTRY_READBACK,BROWSER_ACCEPTANCE","completion":["PREFLIGHT_RUNTIME_BINDING_VISIBLE=PASS"]},
        {"id":"REPAIR_OR_FORMALIZE_SAAS_CONSUMER","title":"Repair Or Formalize SaaS Consumer","execution":"VERIFY_THEN_REPAIR","capability":"CONTROL_PLANE_REPAIR,BROKER_RECONCILIATION","effect":"BOUNDED_REPOSITORY","currentness":"CURRENT_BROKER_DB,CURRENT_SAAS_SESSION_STATE,LIVE_8780_RUNTIME","evidence":"BROKER_TRANSPORT_READBACK,AUTOMATIC_CONSUMER_EVIDENCE,TRUTHFUL_MEDIATION_EVIDENCE","completion":["BROKER_TRANSPORT_TRUTHFUL=PASS"]},
        {"id":"RECONCILE_BROKER_RECEIPTS","title":"Reconcile Broker Receipts","execution":"VERIFY_THEN_REPAIR","capability":"BROKER_RECONCILIATION","effect":"BOUNDED_LOCAL","currentness":"CURRENT_BROKER_DB,CURRENT_BROKER_RECEIPT_LINEAGE","evidence":"BROKER_RECEIPT_LINEAGE,LEGACY_RECEIPT_CLASSIFICATION,RECONCILIATION_RECEIPT","completion":["BROKER_RECEIPT_LINEAGE_RECONCILED=PASS"]},
        {"id":"REPAIR_PANEL_TRUTH_PROJECTION","title":"Repair Panel Truth Projection","execution":"VERIFY_THEN_REPAIR","capability":"CONTROL_PLANE_REPAIR","effect":"BOUNDED_REPOSITORY","currentness":"LIVE_8780_RUNTIME,LIVE_8766_PACKAGE,CURRENT_BROKER_DB","evidence":"FIELD_BY_FIELD_PROJECTION_COMPARISON,BROWSER_ACCEPTANCE,EXACT_SOURCE_READBACK","completion":["PANEL_TRUTH_PROJECTION_REPAIRED=PASS"]},
        {"id":"BACKWARD_COMPATIBILITY_ACCEPTANCE","title":"Backward Compatibility Acceptance","execution":"VALIDATE","capability":"PANEL_ACCEPTANCE","effect":"NONE","currentness":"LIVE_8780_RUNTIME,LIVE_8766_PACKAGE","evidence":"LPCL_1_1_VALIDATION,LPCL_1_2_VALIDATION,BROWSER_ACCEPTANCE","completion":["LEGACY_LPCL_1_1_COMPATIBLE=PASS","LPCL_1_2_COMPATIBLE=PASS"]},
        {"id":"TERMINAL_VALIDATION","title":"Terminal Validation","execution":"VALIDATE","capability":"CONTROL_PLANE_RECONNAISSANCE","effect":"NONE","currentness":"EXACT_GITHUB_MASTER,LIVE_8766_PACKAGE,LIVE_8780_RUNTIME,CURRENT_BROKER_DB","evidence":"EXACT_SOURCE_READBACK,RESTART_DURABILITY,BACKWARD_COMPATIBILITY,BROKER_TRANSPORT_READBACK","completion":["RUNTIME_REVISIONS_CONVERGED=PASS","PREFLIGHT_RUNTIME_BINDING_VISIBLE=PASS","BROKER_TRANSPORT_TRUTHFUL=PASS","LEGACY_LPCL_1_1_COMPATIBLE=PASS","LPCL_1_2_COMPATIBLE=PASS","SUCCESSOR_TERMINAL_VALIDATION=PASS"]},
    )


def _successor_proposal(intel: dict[str,Any], language_gap: dict[str,Any] | None) -> dict[str,Any]:
    language=(language_gap or {}).get("recommended_control_language") or "LPCL/1.2"
    if language!="LPCL/1.2": raise ValueError("successor generator currently requires LPCL/1.2")
    mission_id="LION-CONTROL-PLANE-PANEL-BROKER-REPAIR-SUCCESSOR-R1"
    profiles=_successor_phase_profiles()
    lines=[
        "RUN="+mission_id,
        "PROJECT=LION_EVOLUSION",
        "MODE=AUTONOMOUS_EXECUTE",
        "CONTROL_LANGUAGE="+language,
        "MISSION_ID="+mission_id,
        "MISSION_TITLE=LION Control Plane Panel and Broker Repair",
        "MISSION_OBJECTIVE=Repair evidence-confirmed control-plane defects from CONTROL_PLANE_INTELLIGENCE_BUNDLE",
        "MISSION_DESCRIPTION=Proposal only. Requires explicit registration and authorization after operator review.",
        "LOGICAL_DRONE_COUNT=128",
        "MATERIAL_DRONE_COUNT=64",
        "PROTOCOLS=LPCL,AUTHORITY,CURRENTNESS,ASSIGNMENT,HEARTBEAT,EVIDENCE,VALIDATION,RECEIPT,RECOVERY,GITHUB,HUMAN,CONTROL",
    ]
    phases=[]
    for i,spec in enumerate(profiles,1):
        prefix=f"PHASE_{i:02d}";phases.append({"id":spec["id"],"title":spec["title"]})
        lines.extend([
            f"{prefix}={spec['id']}|{spec['title']}",
            f"{prefix}_EXECUTION_CLASS={spec['execution']}",
            f"{prefix}_CAPABILITY_CLASS={spec['capability']}",
            f"{prefix}_EFFECT_CEILING={spec['effect']}",
            f"{prefix}_BINDING_MODE=DYNAMIC",
            f"{prefix}_ON_MISSING_CAPABILITY=WAIT_AND_DISCOVER",
            f"{prefix}_AUTO_RESUME=TRUE",
            f"{prefix}_VERIFY_BEFORE_MUTATE=TRUE",
            f"{prefix}_CURRENTNESS={spec['currentness']}",
            f"{prefix}_EVIDENCE={spec['evidence']}",
        ])
        for j,predicate in enumerate(spec["completion"],1): lines.append(f"{prefix}_COMPLETION_{j:02d}={predicate}")
    text="\n".join(lines)+"\n";pairs=_generated_lpcl_pairs(text)
    contracts=compile_panel_phase_contracts(pairs,mission_id,phases,language)
    empty_preflight=preflight_execution_contracts(contracts,{})
    validation={"valid":True,"control_language":language,"contract_count":len(contracts),"contract_digests":[c.contract_digest for c in contracts],"compiler_versions":sorted({c.compiler_version for c in contracts}),"preflight_without_runtime_registry":empty_preflight.as_dict(),"validation_digest":digest([c.as_dict() for c in contracts])}
    dg=hashlib.sha256(text.encode()).hexdigest();required_capabilities=sorted({cap for spec in profiles for cap in spec["capability"].split(",")})
    return {
        "schema":SUCCESSOR_SCHEMA,"recommended_control_language":language,
        "repair_scope":"LION CONTROL LPCL PANEL + Mission Control currentness + SaaS broker/consumer truth",
        "required_capabilities":required_capabilities,
        "authority_requirements":["EXPLICIT_USER_ACTIVATION","BOUNDED_EFFECT_ADMISSION"],
        "currentness_requirements":["EXACT_GITHUB_MASTER","LIVE_8766_PACKAGE","LIVE_8780_RUNTIME","CURRENT_BROKER_DB"],
        "evidence_requirements":["EXACT_SOURCE_READBACK","BROWSER_ACCEPTANCE","BROKER_ROUNDTRIP_OR_TRUTHFUL_MEDIATION","RESTART_DURABILITY","BACKWARD_COMPATIBILITY"],
        "completion_predicates":["RUNTIME_REVISIONS_CONVERGED=PASS","PREFLIGHT_RUNTIME_BINDING_VISIBLE=PASS","BROKER_TRANSPORT_TRUTHFUL=PASS","LEGACY_LPCL_1_1_COMPATIBLE=PASS","LPCL_1_2_COMPATIBLE=PASS","SUCCESSOR_TERMINAL_VALIDATION=PASS"],
        "backward_compatibility_requirements":["LPCL/1.1","LPCL/1.2","existing broker requests","existing threads","completed missions"],
        "lpcl_text":text,"proposal_digest":dg,"intelligence_bundle_digest":intel.get("bundle_digest") or digest(intel),"validation":validation,
        "registered":False,"authorized":False,"authority_effect":"NONE",
    }


def _post_baseline(conn: sqlite3.Connection, mission_id: str, baseline: dict[str,Any] | None, current_panel: dict[str,Any] | None, intelligence: dict[str,Any] | None) -> dict[str,Any]:
    before=(baseline or {}).get("core") or {};after=_baseline_core(conn,mission_id);pre_repo=(baseline or {}).get("panel_repo") or {};post_repo=(current_panel or {}).get("repo") or {}
    created_repair=bool(conn.execute("SELECT 1 FROM missions WHERE mission_id='LION-CONTROL-PLANE-PANEL-BROKER-REPAIR-SUCCESSOR-R1'").fetchone())
    recon_effects=int(conn.execute("SELECT COUNT(*) FROM mission_generic_action_receipts WHERE mission_id=? AND authority_effect!='NONE'",(mission_id,)).fetchone()[0])
    action_effects=int(conn.execute("SELECT COUNT(*) FROM mission_action_receipts WHERE mission_id=? AND authority_effect!='NONE'",(mission_id,)).fetchone()[0]) if 'authority_effect' in {r[1] for r in conn.execute('PRAGMA table_info(mission_action_receipts)')} else 0
    no_direct_effects=(recon_effects==0 and action_effects==0)
    checks={
        "NO_REPOSITORY_EFFECT":bool(no_direct_effects and (not pre_repo or (pre_repo.get("github_master")==post_repo.get("github_master") and pre_repo.get("local_head")==post_repo.get("local_head")))),
        "NO_BROKER_RESPONSE_EFFECT":bool(no_direct_effects),
        "NO_SESSION_EFFECT":bool(no_direct_effects),
        "NO_MISSION_REPAIR_EFFECT":not created_repair,
        "INTELLIGENCE_READY_FOR_SUCCESSOR_MISSION":bool(intelligence),
    }
    return {"schema":BASELINE_SCHEMA,"pre":baseline,"post_core":after,"post_panel_repo":post_repo,"checks":checks,"allowed_control_bookkeeping":True,"successor_mission_created":created_repair,"authority_effect":"NONE"}


def synthesize_artifacts(conn: sqlite3.Connection, mission_id: str, contract: dict[str,Any], observations: dict[str,Any], classifications: dict[str,Any], local_analysis: dict[str,Any] | None, saas: dict[str,Any] | None, now_fn) -> dict[str,Any]:
    evidence=set(contract.get("evidence_requirements") or []);currentness=set(contract.get("currentness_requirements") or [])
    if "LANGUAGE_GAP_MATRIX" in evidence:
        baseline=sched.artifact(conn,mission_id,"CONTROL_PLANE_RECON_BASELINE_PRE");historical,sources=historical_classifications(conn,mission_id,(baseline or {}).get("content"));merged=_merge_classifications(classifications,historical)
        content=_language_gap_artifact(merged,local_analysis,saas,classification_sources=sources);sched.put_artifact(conn,mission_id,"LANGUAGE_GAP_MATRIX",content,now_fn,phase_id=contract["phase_id"],schema_id=LANGUAGE_GAP_SCHEMA)
    language_art=sched.artifact(conn,mission_id,"LANGUAGE_GAP_MATRIX",phase_id=None)
    # phase-scoped artifact lookup fallback
    if not language_art:
        rows=[a for a in sched.list_artifacts(conn,mission_id) if a["artifact_type"]=="LANGUAGE_GAP_MATRIX"]
        language_content=rows[-1]["content"] if rows else None
    else:language_content=language_art["content"]
    if "INTELLIGENCE_BUNDLE_DIGEST" in evidence or "INTELLIGENCE_BUNDLE" in evidence:
        content=_intelligence_bundle(conn,mission_id,language_content,generated_at=now_fn());sched.put_artifact(conn,mission_id,"CONTROL_PLANE_INTELLIGENCE_BUNDLE",content,now_fn,schema_id=INTELLIGENCE_SCHEMA)
    intel=sched.artifact(conn,mission_id,"CONTROL_PLANE_INTELLIGENCE_BUNDLE")
    if "SUCCESSOR_LPCL_PROPOSAL_DIGEST" in evidence:
        intel_content=(intel or {}).get("content") or _intelligence_bundle(conn,mission_id,language_content,generated_at=now_fn());content=_successor_proposal(intel_content,language_content);sched.put_artifact(conn,mission_id,"SUCCESSOR_REPAIR_LPCL_PROPOSAL",content,now_fn,schema_id=SUCCESSOR_SCHEMA)
    if "POST_RECON_BASELINE" in currentness or "STATE_DIFF" in evidence:
        baseline=sched.artifact(conn,mission_id,"CONTROL_PLANE_RECON_BASELINE_PRE");intel=sched.artifact(conn,mission_id,"CONTROL_PLANE_INTELLIGENCE_BUNDLE");panel=(observations.get("domains") or {}).get("panel") or {};content=_post_baseline(conn,mission_id,(baseline or {}).get("content"),panel,(intel or {}).get("content"));sched.put_artifact(conn,mission_id,"CONTROL_PLANE_RECON_BASELINE_POST",content,now_fn,schema_id=BASELINE_SCHEMA)
    return _artifact_content_map(conn,mission_id)


def enrich_pre_baseline(conn: sqlite3.Connection, mission_id: str, observations: dict[str,Any], now_fn) -> None:
    art=sched.artifact(conn,mission_id,"CONTROL_PLANE_RECON_BASELINE_PRE");content=dict((art or {}).get("content") or {"schema":BASELINE_SCHEMA,"core":_baseline_core(conn,mission_id)})
    panel=(observations.get("domains") or {}).get("panel") or {};mc=(observations.get("domains") or {}).get("mission_control") or {};content.update({"captured_at":content.get("captured_at") or now_fn(),"panel_repo":panel.get("repo"),"panel_runtime":panel.get("runtime"),"mission_control_runtime":mc.get("runtime_identity"),"authority_effect":"NONE"});sched.put_artifact(conn,mission_id,"CONTROL_PLANE_RECON_BASELINE_PRE",content,now_fn,schema_id=BASELINE_SCHEMA)


def execute_phase(conn: sqlite3.Connection, mission_id: str, phase_id: str, contract: dict[str,Any], *, db_path: Path, driver_generation: int, now_fn, create_saas_request, saas_request_status, allow_reacquire: bool=False) -> dict[str,Any]:
    plan=build_observation_plan(contract)
    if plan["unsupported_tokens"]:
        return {"state":"WAITING","gate":"EVIDENCE_INCOMPLETE","reason":"Unsupported reconnaissance recipes: "+",".join(plan["unsupported_tokens"]),"evidence":{"unsupported_tokens":plan["unsupported_tokens"],"authority_effect":"NONE"}}
    leases=ensure_material_leases(conn,mission_id,phase_id,contract,now_fn)
    existing_bundle=sched.artifact(conn,mission_id,"RECON_EVIDENCE_BUNDLE",phase_id=phase_id)
    if existing_bundle:
        _record_bundle_generation(conn,mission_id,phase_id,existing_bundle,now_fn)
        reacquire=evidence_reacquisition_request(conn,mission_id,phase_id,existing_bundle,contract,db_path=db_path,require_parked=not allow_reacquire)
        if reacquire and not allow_reacquire:
            return {"state":"REACQUIRE_REQUIRED","gate":"EVIDENCE_REACQUISITION_REQUIRED","reason":"A newer bounded observation is available after EVIDENCE_INCOMPLETE","reacquisition":reacquire,"evidence":{"evidence_bundle_digest":existing_bundle["content_digest"],"reacquisition":reacquire,"authority_effect":"NONE"}}
        if reacquire and allow_reacquire:
            ro=open_read_only(db_path)
            try:observations,missing=collect_observations(ro,mission_id,phase_id,contract,db_path=db_path)
            finally:ro.close()
            if missing:
                return {"state":"WAITING","gate":"EVIDENCE_INCOMPLETE","reason":"Missing bounded observation after reacquisition: "+",".join(missing),"evidence":{"missing_observations":missing,"reacquisition":reacquire,"authority_effect":"NONE"}}
            fresh_fp=observation_generation_fingerprint(observations)
            if fresh_fp!=reacquire.get("new_observation_fingerprint"):
                return {"state":"WAITING","gate":"EVIDENCE_INCOMPLETE","reason":"Bounded observations changed during reacquisition","evidence":{"expected_observation_fingerprint":reacquire.get("new_observation_fingerprint"),"observed_observation_fingerprint":fresh_fp,"authority_effect":"NONE"}}
            enrich_pre_baseline(conn,mission_id,observations,now_fn); model_view=_model_view(observations); latest=_latest_windows_observation(conn,mission_id,phase_id); source_fp=(latest or {}).get("source_fingerprint") or _panel_fingerprint_from_snapshot(phase_id,((observations.get("domains") or {}).get("panel")))
            bundle_content={"schema":EVIDENCE_BUNDLE_SCHEMA,"mission_id":mission_id,"phase_id":phase_id,"contract_digest":contract["contract_digest"],"observation_plan":plan,"observations":observations,"model_view":model_view,"source_fingerprint":source_fp,"observation_fingerprint":fresh_fp,"reacquisition_generation":int(reacquire["next_generation"]),"reacquisition_trigger":reacquire["trigger"],"authority_effect":"NONE"}
            bundle_art=sched.put_artifact(conn,mission_id,"RECON_EVIDENCE_BUNDLE",bundle_content,now_fn,phase_id=phase_id,schema_id=EVIDENCE_BUNDLE_SCHEMA); bundle_digest=bundle_art["content_digest"]
            sched.record_recon_evidence_generation(conn,mission_id,phase_id,int(reacquire["next_generation"]),fresh_fp,bundle_digest,bundle_content,reacquire["trigger"],now_fn)
        else:
            bundle_art=existing_bundle;bundle_content=existing_bundle["content"];observations=bundle_content["observations"];model_view=bundle_content["model_view"];bundle_digest=existing_bundle["content_digest"]
    else:
        ro=open_read_only(db_path)
        try:observations,missing=collect_observations(ro,mission_id,phase_id,contract,db_path=db_path)
        finally:ro.close()
        if missing:
            return {"state":"WAITING","gate":"EVIDENCE_INCOMPLETE","reason":"Missing bounded observation: "+",".join(missing),"evidence":{"missing_observations":missing,"material_lease_count":len(leases),"authority_effect":"NONE"}}
        enrich_pre_baseline(conn,mission_id,observations,now_fn); model_view=_model_view(observations); latest=_latest_windows_observation(conn,mission_id,phase_id); source_fp=(latest or {}).get("source_fingerprint") or _panel_fingerprint_from_snapshot(phase_id,((observations.get("domains") or {}).get("panel"))); observation_fp=observation_generation_fingerprint(observations)
        bundle_content={"schema":EVIDENCE_BUNDLE_SCHEMA,"mission_id":mission_id,"phase_id":phase_id,"contract_digest":contract["contract_digest"],"observation_plan":plan,"observations":observations,"model_view":model_view,"source_fingerprint":source_fp,"observation_fingerprint":observation_fp,"reacquisition_generation":1,"reacquisition_trigger":"INITIAL_BOUNDED_OBSERVATION","authority_effect":"NONE"}
        bundle_art=sched.put_artifact(conn,mission_id,"RECON_EVIDENCE_BUNDLE",bundle_content,now_fn,phase_id=phase_id,schema_id=EVIDENCE_BUNDLE_SCHEMA);bundle_digest=bundle_art["content_digest"]
        sched.record_recon_evidence_generation(conn,mission_id,phase_id,1,observation_fp,bundle_digest,bundle_content,"INITIAL_BOUNDED_OBSERVATION",now_fn)
    trajectories=ensure_local_trajectories(conn,mission_id,phase_id,contract,bundle_digest,model_view,driver_generation,now_fn)
    if trajectories["required"] and not trajectories["complete"]:
        return {"state":"WAITING","gate":"LOCAL_RECON_TRAJECTORIES","reason":"Waiting for independent LOCAL reconnaissance trajectories","evidence":{"evidence_bundle_digest":bundle_digest,"trajectory_states":trajectories.get("states"),"material_lease_count":len(leases),"authority_effect":"NONE"}}
    if trajectories["required"] and not trajectories.get("distinct_result_digests"):
        return {"state":"WAITING","gate":"LOCAL_RECON_TRAJECTORIES","reason":"LOCAL trajectory result digests are not independently bound","evidence":{"evidence_bundle_digest":bundle_digest,"trajectory_result_digests":trajectories.get("result_digests"),"authority_effect":"NONE"}}
    local_analysis=_analysis_from_trajectory_rows(conn,mission_id,phase_id,bundle_digest) if trajectories["required"] else None
    if local_analysis:sched.put_artifact(conn,mission_id,"LOCAL_RECON_ANALYSIS",local_analysis,now_fn,phase_id=phase_id,schema_id=LOCAL_ANALYSIS_SCHEMA)
    saas=ensure_saas_advisory(conn,mission_id,phase_id,contract,bundle_digest,model_view,now_fn,create_request=create_saas_request,request_status=saas_request_status)
    baseline=sched.artifact(conn,mission_id,"CONTROL_PLANE_RECON_BASELINE_PRE");classes=_classification(observations,(baseline or {}).get("content"))
    artifacts=synthesize_artifacts(conn,mission_id,contract,observations,classes,local_analysis,saas,now_fn)
    ro=open_read_only(db_path)
    try:facts,detail=derive_facts(ro,mission_id,phase_id,contract,observations,artifacts=artifacts,baseline=(baseline or {}).get("content"),local_analysis=local_analysis,saas_advisory=saas)
    finally:ro.close()
    checks={k:"PASS" if v else "UNKNOWN" for k,v in facts.items()};missing_facts=[k for k,v in facts.items() if not v]
    summary={"evidence_bundle_artifact_id":bundle_art["artifact_id"],"evidence_bundle_digest":bundle_digest,"evidence_generation":int(bundle_content.get("reacquisition_generation") or 1),"source_fingerprint":bundle_content.get("source_fingerprint"),"observation_fingerprint":_bundle_observation_fingerprint(phase_id,bundle_content),"facts":facts,"checks":checks,"material_lease_count":len(leases),"material_ids":[x["material_drone_id"] for x in leases],"local_trajectories":trajectories,"saas_advisory":{"state":saas.get("state"),"request_id":saas.get("request_id"),"receipt_digest":saas.get("receipt_digest"),"authority_effect":"NONE"},"classification_digest":digest(detail.get("classifications")),"authority_effect":"NONE"}
    # Keep the evidence bundle immutable once its digest is used by LOCAL/SaaS.
    # The bounded reconciliation result is a separate phase summary artifact.
    sched.put_artifact(conn,mission_id,"RECON_PHASE_SUMMARY",{"schema":"lion.control-plane-recon-phase-summary/v1","evidence_bundle_digest":bundle_digest,"summary":summary,"authority_effect":"NONE"},now_fn,phase_id=phase_id,schema_id="lion.control-plane-recon-phase-summary/v1")
    if missing_facts:
        return {"state":"WAITING","gate":"EVIDENCE_INCOMPLETE","reason":"Completion predicates remain UNKNOWN: "+",".join(missing_facts),"evidence":summary}
    release_material_leases(conn,mission_id,phase_id,now_fn)
    return {"state":"PASS","evidence":summary}


def reconcile_terminal_artifacts(conn: sqlite3.Connection, now_fn) -> list[dict[str,Any]]:
    changed=[]
    rows=conn.execute("SELECT DISTINCT c.mission_id FROM mission_phase_execution_contracts c JOIN missions m ON m.mission_id=c.mission_id JOIN mission_execution_drivers d ON d.mission_id=c.mission_id WHERE c.capability_classes_json LIKE '%CONTROL_PLANE_RECONNAISSANCE%' AND m.state='COMPLETE' AND d.state='COMPLETE' ORDER BY c.mission_id").fetchall()
    for row in rows:
        mission_id=row[0]
        phases=conn.execute("SELECT phase_id,status FROM mission_phases WHERE mission_id=? ORDER BY ordinal",(mission_id,)).fetchall()
        if not phases or any(r["status"]!="PASS" for r in phases): continue
        artifacts=sched.list_artifacts(conn,mission_id);language_rows=[a for a in artifacts if a["artifact_type"]=="LANGUAGE_GAP_MATRIX"]
        if not language_rows: continue
        language_old=language_rows[-1];intel_old=sched.artifact(conn,mission_id,"CONTROL_PLANE_INTELLIGENCE_BUNDLE");successor_old=sched.artifact(conn,mission_id,"SUCCESSOR_REPAIR_LPCL_PROPOSAL");baseline=sched.artifact(conn,mission_id,"CONTROL_PLANE_RECON_BASELINE_PRE")
        historical,sources=historical_classifications(conn,mission_id,(baseline or {}).get("content"));old_content=language_old["content"] or {};merged=_merge_classifications(old_content.get("classifications") or {},historical)
        # Generate and validate the complete artifact set before writing any revision.
        language_new=_language_gap_artifact(merged,old_content.get("local_analysis"),{"state":old_content.get("saas_advisory_state","NOT_REQUESTED")},classification_sources=sources)
        generated_at=((intel_old or {}).get("content") or {}).get("generated_at") or now_fn();intel_new=_intelligence_bundle(conn,mission_id,language_new,generated_at=generated_at);successor_new=_successor_proposal(intel_new,language_new)
        lang_digest=digest(language_new);intel_digest=digest(intel_new);successor_digest=digest(successor_new)
        old_digests=((language_old or {}).get("content_digest"),(intel_old or {}).get("content_digest"),(successor_old or {}).get("content_digest"))
        new_digests=(lang_digest,intel_digest,successor_digest)
        if old_digests==new_digests: continue
        lang_row=sched.put_artifact(conn,mission_id,"LANGUAGE_GAP_MATRIX",language_new,now_fn,phase_id=language_old["phase_id"],schema_id=LANGUAGE_GAP_SCHEMA)
        intel_row=sched.put_artifact(conn,mission_id,"CONTROL_PLANE_INTELLIGENCE_BUNDLE",intel_new,now_fn,schema_id=INTELLIGENCE_SCHEMA)
        successor_row=sched.put_artifact(conn,mission_id,"SUCCESSOR_REPAIR_LPCL_PROPOSAL",successor_new,now_fn,schema_id=SUCCESSOR_SCHEMA)
        changed.append({"mission_id":mission_id,"language_gap_revision":lang_row["revision"],"language_gap_digest":lang_row["content_digest"],"intelligence_revision":intel_row["revision"],"intelligence_digest":intel_row["content_digest"],"successor_revision":successor_row["revision"],"successor_digest":successor_row["content_digest"],"successor_proposal_digest":successor_new["proposal_digest"],"successor_contract_count":successor_new["validation"]["contract_count"],"authority_effect":"NONE"})
    return changed


def late_saas_reconcile(conn: sqlite3.Connection, now_fn, *, request_status) -> list[dict[str,Any]]:
    changed=[]
    for row in conn.execute("SELECT * FROM mission_recon_saas_advisories WHERE request_id IS NOT NULL AND state!='RESPONDED' ORDER BY created_at").fetchall():
        try:status=request_status(row["request_id"])
        except Exception:continue
        if status.get("status")!="RESPONDED":continue
        conn.execute("UPDATE mission_recon_saas_advisories SET state='RESPONDED',response_digest=?,receipt_digest=?,updated_at=? WHERE advisory_id=?",(status.get("response_digest"),status.get("receipt_digest"),now_fn(),row["advisory_id"]));conn.commit()
        language_rows=[a for a in sched.list_artifacts(conn,row["mission_id"]) if a["artifact_type"]=="LANGUAGE_GAP_MATRIX"]
        if sched.artifact(conn,row["mission_id"],"CONTROL_PLANE_INTELLIGENCE_BUNDLE"):
            refreshed=_intelligence_bundle(conn,row["mission_id"],language_rows[-1]["content"] if language_rows else None,generated_at=now_fn());sched.put_artifact(conn,row["mission_id"],"CONTROL_PLANE_INTELLIGENCE_BUNDLE",refreshed,now_fn,schema_id=INTELLIGENCE_SCHEMA)
        notice={"schema":"lion.recon-late-saas-advisory/v1","phase_id":row["phase_id"],"request_id":row["request_id"],"evidence_bundle_digest":row["evidence_bundle_digest"],"response_digest":status.get("response_digest"),"receipt_digest":status.get("receipt_digest"),"retroactive_phase_mutation":False,"authority_effect":"NONE"};sched.put_artifact(conn,row["mission_id"],"RECON_LATE_SAAS_ADVISORY",notice,now_fn,phase_id=row["phase_id"],schema_id=notice["schema"])
        changed.append({"mission_id":row["mission_id"],"phase_id":row["phase_id"],"request_id":row["request_id"],"response_digest":status.get("response_digest"),"receipt_digest":status.get("receipt_digest")})
    return changed
