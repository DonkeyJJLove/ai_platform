"""Immutable contracts for durable fleet coordination F005-B R1.

These objects describe coordination state and dispatch fencing only. They grant no
repository authority, execute no work, and cannot promote fleet scale.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from pathlib import PurePosixPath
import re
from typing import Any, Mapping, Tuple

_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_REPO = re.compile(r"^[^/\s]+/[^/\s]+$")
_BRANCH_FORBIDDEN = frozenset(" ~^:?*[\\")
MISSION_STATES = frozenset({"STARTING", "WAITING", "RUNNING", "DONE", "FAILED", "TERMINATED"})
TERMINAL_STATES = frozenset({"DONE", "FAILED", "TERMINATED"})
LEASE_KINDS = frozenset({"BRANCH", "PATH"})

class FleetCoordinationContractError(ValueError):
    pass

def canonical_json(value: Mapping[str, Any]) -> bytes:
    return json.dumps(dict(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")

def _text(value: Any, name: str, *, limit: int = 4096, optional: bool = False) -> str | None:
    if optional and value is None:
        return None
    if not isinstance(value, str) or not value.strip() or len(value) > limit or any(ord(ch) < 32 or ord(ch) == 127 for ch in value):
        raise FleetCoordinationContractError(f"{name} is invalid")
    return value

def _sha40(value: Any, name: str) -> str:
    value = _text(value, name, limit=40); assert isinstance(value, str)
    if not _SHA40.fullmatch(value): raise FleetCoordinationContractError(f"{name} must be a full lowercase git SHA")
    return value

def _sha256(value: Any, name: str, *, optional: bool = False) -> str | None:
    if optional and value is None: return None
    value = _text(value, name, limit=64); assert isinstance(value, str)
    if not _SHA256.fullmatch(value): raise FleetCoordinationContractError(f"{name} must be sha256 hex")
    return value

def _repository(value: Any) -> str:
    value = _text(value, "repository"); assert isinstance(value, str)
    if not _REPO.fullmatch(value): raise FleetCoordinationContractError("repository must use owner/name form")
    return value

def _branch(value: Any) -> str:
    value = _text(value, "branch", limit=255); assert isinstance(value, str)
    if value.startswith(("refs/", "/")) or value.endswith(("/", ".", ".lock")) or ".." in value or "//" in value or "@{" in value or any(ch in value for ch in _BRANCH_FORBIDDEN):
        raise FleetCoordinationContractError("branch is not a safe repository branch name")
    return value

def _string_tuple(value: Any, name: str, *, nonempty: bool = False) -> Tuple[str, ...]:
    if type(value) is not tuple or (nonempty and not value): raise FleetCoordinationContractError(f"{name} must be a {'non-empty ' if nonempty else ''}tuple")
    for item in value: _text(item, name)
    if len(set(value)) != len(value): raise FleetCoordinationContractError(f"{name} entries must be unique")
    return value

def _write_scope(value: Any) -> Tuple[str, ...]:
    scope = _string_tuple(value, "write_scope", nonempty=True)
    for raw in scope:
        path = PurePosixPath(raw)
        if "\\" in raw or any(ch in raw for ch in "*?[]") or path.is_absolute() or ".." in path.parts or str(path) in {"", "."} or str(path) != raw:
            raise FleetCoordinationContractError("write_scope contains a non-canonical or unsafe path")
    return scope

def _heads(value: Any) -> Tuple[Tuple[str, str], ...]:
    if type(value) is not tuple or not value: raise FleetCoordinationContractError("current_heads must be a non-empty tuple")
    repos=[]
    for row in value:
        if type(row) is not tuple or len(row) != 2: raise FleetCoordinationContractError("current_heads entries must be pairs")
        repos.append(_repository(row[0])); _sha40(row[1], "current head")
    if len(repos) != len(set(repos)): raise FleetCoordinationContractError("current_heads repositories must be unique")
    return value

@dataclass(frozen=True)
class FleetCoordinationSpec:
    mission_id: str; drone_id: str; repository: str; baseline_sha: str; baseline_tree_sha: str; branch: str
    write_scope: Tuple[str, ...]; dependencies: Tuple[str, ...] = (); evidence_refs: Tuple[str, ...] = ()
    def validate(self):
        _text(self.mission_id,"mission_id"); _text(self.drone_id,"drone_id"); _repository(self.repository); _sha40(self.baseline_sha,"baseline_sha"); _sha40(self.baseline_tree_sha,"baseline_tree_sha"); _branch(self.branch); _write_scope(self.write_scope); _string_tuple(self.dependencies,"dependencies"); _string_tuple(self.evidence_refs,"evidence_refs",nonempty=True)
        if self.mission_id in self.dependencies: raise FleetCoordinationContractError("mission cannot depend on itself")
        return self
    def canonical_dict(self):
        self.validate(); v=asdict(self); v["write_scope"]=list(self.write_scope); v["dependencies"]=list(self.dependencies); v["evidence_refs"]=list(self.evidence_refs); return v
    def digest(self): return sha256(canonical_json(self.canonical_dict())).hexdigest()

@dataclass(frozen=True)
class FleetPlanRequest:
    request_id: str; coordinator_id: str; current_heads: Tuple[Tuple[str,str], ...]; max_parallel: int = 1
    def validate(self):
        _text(self.request_id,"request_id"); _text(self.coordinator_id,"coordinator_id"); _heads(self.current_heads)
        if isinstance(self.max_parallel,bool) or not isinstance(self.max_parallel,int) or not 1 <= self.max_parallel <= 100: raise FleetCoordinationContractError("max_parallel must be in [1,100]")
        return self
    def head_map(self): self.validate(); return dict(self.current_heads)
    def canonical_dict(self): self.validate(); return {"request_id":self.request_id,"coordinator_id":self.coordinator_id,"current_heads":[list(x) for x in self.current_heads],"max_parallel":self.max_parallel}
    def digest(self): return sha256(canonical_json(self.canonical_dict())).hexdigest()

@dataclass(frozen=True)
class FleetDispatch:
    dispatch_id: str; fencing_token: str; request_id: str; coordinator_id: str; mission_id: str; drone_id: str; generation: int; repository: str; baseline_sha: str; baseline_tree_sha: str; branch: str; write_scope: Tuple[str,...]; issued_at: str
    def validate(self):
        _sha256(self.dispatch_id,"dispatch_id"); _sha256(self.fencing_token,"fencing_token")
        for n in ("request_id","coordinator_id","mission_id","drone_id","issued_at"): _text(getattr(self,n),n)
        if isinstance(self.generation,bool) or not isinstance(self.generation,int) or self.generation < 1: raise FleetCoordinationContractError("generation must be positive")
        _repository(self.repository); _sha40(self.baseline_sha,"baseline_sha"); _sha40(self.baseline_tree_sha,"baseline_tree_sha"); _branch(self.branch); _write_scope(self.write_scope); return self
    def canonical_dict(self): self.validate(); v=asdict(self); v["write_scope"]=list(self.write_scope); return v
    def validate_for(self,spec,request):
        self.validate(); spec.validate(); request.validate()
        if (self.request_id,self.coordinator_id,self.mission_id,self.drone_id,self.repository,self.baseline_sha,self.baseline_tree_sha,self.branch,self.write_scope)!=(request.request_id,request.coordinator_id,spec.mission_id,spec.drone_id,spec.repository,spec.baseline_sha,spec.baseline_tree_sha,spec.branch,spec.write_scope): raise FleetCoordinationContractError("dispatch binding mismatch")
        return self

@dataclass(frozen=True)
class FleetMissionState:
    mission_id: str; drone_id: str; state: str; generation: int; spec_digest: str; dispatch_id: str|None; fencing_token: str|None; terminal_evidence_ref: str|None; updated_at: str
    def validate(self):
        _text(self.mission_id,"mission_id"); _text(self.drone_id,"drone_id"); _sha256(self.spec_digest,"spec_digest"); _sha256(self.dispatch_id,"dispatch_id",optional=True); _sha256(self.fencing_token,"fencing_token",optional=True); _text(self.terminal_evidence_ref,"terminal_evidence_ref",optional=True); _text(self.updated_at,"updated_at")
        if self.state not in MISSION_STATES or isinstance(self.generation,bool) or not isinstance(self.generation,int) or self.generation < 0: raise FleetCoordinationContractError("mission state is invalid")
        if self.state=="RUNNING" and (not self.dispatch_id or not self.fencing_token or self.generation<1): raise FleetCoordinationContractError("RUNNING requires fenced dispatch")
        if self.state in TERMINAL_STATES and self.terminal_evidence_ref is None: raise FleetCoordinationContractError("terminal mission requires evidence reference")
        return self

@dataclass(frozen=True)
class FleetLease:
    mission_id: str; drone_id: str; dispatch_id: str; generation: int; repository: str; lease_kind: str; resource: str; acquired_at: str
    def validate(self):
        for n in ("mission_id","drone_id","resource","acquired_at"): _text(getattr(self,n),n)
        _sha256(self.dispatch_id,"dispatch_id"); _repository(self.repository)
        if self.lease_kind not in LEASE_KINDS or isinstance(self.generation,bool) or not isinstance(self.generation,int) or self.generation<1: raise FleetCoordinationContractError("lease is invalid")
        _branch(self.resource) if self.lease_kind=="BRANCH" else _write_scope((self.resource,)); return self

@dataclass(frozen=True)
class FleetCoordinationSnapshot:
    coordinator_id: str; revision: int; event_head: str; missions: Tuple[FleetMissionState,...]; active_leases: Tuple[FleetLease,...]
    def validate(self):
        _text(self.coordinator_id,"coordinator_id"); _sha256(self.event_head,"event_head")
        if isinstance(self.revision,bool) or not isinstance(self.revision,int) or self.revision<0 or type(self.missions) is not tuple or type(self.active_leases) is not tuple: raise FleetCoordinationContractError("snapshot is invalid")
        for x in self.missions: x.validate()
        for x in self.active_leases: x.validate()
        if len({x.mission_id for x in self.missions}) != len(self.missions): raise FleetCoordinationContractError("duplicate missions")
        return self
