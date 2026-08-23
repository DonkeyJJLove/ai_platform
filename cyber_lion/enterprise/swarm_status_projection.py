"""Helpers for externally auditable LION status projections."""
from __future__ import annotations
from cyber_lion.contracts.swarm_status import compute_status_digest,compute_revision_digest

REQUIRED_CONTEXT_KEYS=("observed_master","governor","architecture","critical_path","formations","missions","drones","role_assignments","dependencies","blockers","channels","pending_messages","epistemic_state","source_refs")

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

def classify_live_master(status:dict,*,live_commit:str,live_tree:str)->str:
    validate_status_projection(status);observed=status["observed_master"]
    if not live_commit or not live_tree:return "UNKNOWN"
    if observed.get("commit")!=live_commit or observed.get("tree")!=live_tree:return "STALE"
    return status["epistemic_state"]
