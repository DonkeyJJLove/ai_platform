"""Helpers for externally auditable LION status projections."""
from __future__ import annotations
from cyber_lion.contracts.swarm_status import compute_status_digest,compute_revision_digest

REQUIRED_CONTEXT_KEYS=("observed_master","governor","architecture","critical_path","formations","missions","drones","role_assignments","dependencies","blockers","channels","pending_messages","epistemic_state","source_refs")
PROJECTION_ONLY_PATHS=frozenset({
    "LION/status.json",
    "LION/architecture/implementation-map.json",
    "LION/ops/mission-registry.json",
    "LION/ops/drone-registry.json",
    "LION/ops/future-mission-pool.json",
})
DEFAULT_MAX_PROJECTION_COMMITS=16

def validate_status_projection(status:dict)->dict:
    for key in ("schema_version","system_id","revision","status_digest","previous_status_digest","revision_digest","previous_revision_digest","current_actions","history","generated_at",*REQUIRED_CONTEXT_KEYS):
        if key not in status:raise ValueError(f"status missing {key}")
    if status["schema_version"]!="1.0.0" or status["system_id"]!="LION":raise ValueError("status identity invalid")
    if status["epistemic_state"] not in {"CURRENT","STALE","UNKNOWN","CONFLICTED"}:raise ValueError("invalid epistemic state")
    expected=compute_status_digest(status)
    if expected!=status["status_digest"]:raise ValueError("status digest mismatch")
    expected_rev=compute_revision_digest(revision=status["revision"],status_digest=status["status_digest"],previous_revision_digest=status["previous_revision_digest"])
    if expected_rev!=status["revision_digest"]:raise ValueError("revision digest mismatch")
    for key in ("formations","missions","drones","role_assignments","dependencies","blockers","channels","pending_messages","current_actions","history","source_refs"):
        if not isinstance(status[key],list):raise ValueError(f"{key} must be list")
    return status

def _sha40(value)->bool:
    return isinstance(value,str) and len(value)==40 and all(c in "0123456789abcdef" for c in value)

def classify_live_master(status:dict,*,live_commit:str,live_tree:str,observed_commit_tree:str|None=None,ancestry_verified:bool=False,intervening_commits:tuple[dict,...]=(),max_projection_commits:int=DEFAULT_MAX_PROJECTION_COMMITS)->str:
    """Classify freshness without requiring a self-referential status commit SHA.

    Exact observed commit/tree equality is CURRENT-compatible. A descendant live
    master is also CURRENT-compatible only when the caller supplies a verified,
    contiguous ancestry chain from the observed commit and every intervening
    commit changes only the closed projection allowlist. Missing ancestry proof
    is UNKNOWN; any proven non-projection change is STALE.
    """
    validate_status_projection(status);observed=status["observed_master"]
    observed_commit=observed.get("commit");observed_tree=observed.get("tree")
    if not (_sha40(observed_commit) and _sha40(observed_tree) and _sha40(live_commit) and _sha40(live_tree)):return "UNKNOWN"
    if live_commit==observed_commit:
        if live_tree!=observed_tree:return "STALE"
        return status["epistemic_state"]
    if not ancestry_verified:return "UNKNOWN"
    if observed_commit_tree!=observed_tree:return "UNKNOWN"
    if not isinstance(max_projection_commits,int) or max_projection_commits<1:return "UNKNOWN"
    chain=tuple(intervening_commits)
    if not chain or len(chain)>max_projection_commits:return "UNKNOWN"
    expected_parent=observed_commit
    for item in chain:
        if not isinstance(item,dict):return "UNKNOWN"
        sha=item.get("sha");parent=item.get("parent_sha");paths=item.get("paths")
        if not (_sha40(sha) and _sha40(parent)) or parent!=expected_parent:return "UNKNOWN"
        if not isinstance(paths,(list,tuple)) or not paths:return "UNKNOWN"
        normalized=tuple(str(p) for p in paths)
        if any(p not in PROJECTION_ONLY_PATHS for p in normalized):return "STALE"
        expected_parent=sha
    if expected_parent!=live_commit:return "UNKNOWN"
    return status["epistemic_state"]
