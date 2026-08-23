"""Deterministic operational status contracts for LION."""
from __future__ import annotations
from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Any,Mapping

ACTION_STATES={"PLANNED","ACCEPTED","STARTED","IN_PROGRESS","BLOCKED","VERIFYING","COMPLETED","FAILED","CANCELLED","SUPERSEDED"}
TERMINAL_ACTION_STATES={"COMPLETED","FAILED","CANCELLED","SUPERSEDED"}
REPORT_TYPES={"ACTION_PLANNED","ACTION_ACCEPTED","ACTION_STARTED","ACTION_PROGRESS","ACTION_BLOCKED","ACTION_VERIFYING","ACTION_COMPLETED","ACTION_FAILED","ACTION_CANCELLED","ACTION_SUPERSEDED","STATUS_REPORT","ROLE_ACCEPTED","ROLE_RELEASED","FORMATION_PROPOSED","FORMATION_JOINED","FORMATION_SPLIT","FORMATION_MERGED","BLOCKER","HANDOFF","EVIDENCE","VERIFY_REQUEST","RECONCILIATION"}
TRANSITIONS={
"PLANNED":{"ACCEPTED","CANCELLED","SUPERSEDED"},"ACCEPTED":{"STARTED","CANCELLED","SUPERSEDED"},"STARTED":{"IN_PROGRESS","BLOCKED","VERIFYING","COMPLETED","FAILED","CANCELLED","SUPERSEDED"},"IN_PROGRESS":{"BLOCKED","VERIFYING","COMPLETED","FAILED","CANCELLED","SUPERSEDED"},"BLOCKED":{"IN_PROGRESS","FAILED","CANCELLED","SUPERSEDED"},"VERIFYING":{"COMPLETED","FAILED","BLOCKED","SUPERSEDED"}
}
class SwarmStatusError(ValueError):pass

def canonical_json(value:Any)->bytes:return json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()
def digest(value:Any)->str:return sha256(canonical_json(value)).hexdigest()
def logical_status_payload(status:Mapping[str,Any])->dict[str,Any]:
    excluded={"revision","status_digest","previous_status_digest","revision_digest","previous_revision_digest","generated_at"}
    return {k:v for k,v in status.items() if k not in excluded}
def compute_status_digest(status:Mapping[str,Any])->str:return digest(logical_status_payload(status))
def compute_revision_digest(*,revision:int,status_digest:str,previous_revision_digest:str)->str:
    return digest({"revision":revision,"status_digest":status_digest,"previous_revision_digest":previous_revision_digest})

@dataclass(frozen=True)
class StatusReport:
    operation_id:str;expected_revision:int;expected_status_digest:str;reporter_drone_id:str;mission_id:str;event_type:str;payload:Mapping[str,Any];evidence_refs:tuple[str,...];observed_at:str
    def validate(self):
        for n,v in (("operation_id",self.operation_id),("expected_status_digest",self.expected_status_digest),("reporter_drone_id",self.reporter_drone_id),("mission_id",self.mission_id),("observed_at",self.observed_at)):
            if not isinstance(v,str) or not v.strip():raise SwarmStatusError(f"{n} invalid")
        if type(self.expected_revision) is not int or self.expected_revision<0:raise SwarmStatusError("expected_revision invalid")
        if self.event_type not in REPORT_TYPES:raise SwarmStatusError("unknown event_type")
        if not isinstance(self.payload,Mapping):raise SwarmStatusError("payload must be mapping")
        if type(self.evidence_refs) is not tuple or not self.evidence_refs:raise SwarmStatusError("evidence_refs required")
        return self

def transition_allowed(old:str,new:str)->bool:
    if old in TERMINAL_ACTION_STATES:return False
    return new in TRANSITIONS.get(old,set())
