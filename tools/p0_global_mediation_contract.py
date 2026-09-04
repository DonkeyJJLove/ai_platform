"""Exact evidence-only carrier for current global mediation status."""
from __future__ import annotations
from dataclasses import asdict,dataclass
from hashlib import sha256
import json,re
from typing import Tuple
from cyber_lion.contracts.production_mediation import MediationClosureRecord
_SHA64=re.compile(r"^[0-9a-f]{64}$")
_STATUSES=frozenset({"MEDIATED","UNMEDIATED","PARTIAL","UNKNOWN"})
MEDIATION_CLOSURE_RECORD_DIGEST_DOMAIN=b"LION/GLOBAL-MEDIATION-CLOSURE-RECORD/1"
class GlobalMediationClosureContractError(ValueError):pass

def _text(v,n):
    if not isinstance(v,str) or not v.strip() or "\x00" in v:raise GlobalMediationClosureContractError(f"{n} invalid")
    return v

def _sha(v,n):
    _text(v,n)
    if not _SHA64.fullmatch(v):raise GlobalMediationClosureContractError(f"{n} must be sha256")
    return v

def _tuple(v,n,required=False):
    if type(v) is not tuple or (required and not v):raise GlobalMediationClosureContractError(f"{n} must be immutable tuple")
    return v

def _digest(domain,obj):
    raw=json.dumps(asdict(obj),sort_keys=True,separators=(",",":"),ensure_ascii=False,default=list).encode()
    return sha256(domain+b"\0"+raw).hexdigest()

def mediation_closure_record_digest(record:MediationClosureRecord)->str:
    if type(record) is not MediationClosureRecord:raise GlobalMediationClosureContractError("exact mediation closure record required")
    record.validate()
    return _digest(MEDIATION_CLOSURE_RECORD_DIGEST_DOMAIN,record)

@dataclass(frozen=True)
class GlobalMediationSurfaceStatus:
    surface_digest:str
    status:str
    closure_record_digest:str
    evidence_refs:Tuple[str,...]
    def validate(self):
        _sha(self.surface_digest,"surface_digest");_tuple(self.evidence_refs,"evidence_refs")
        if self.status not in _STATUSES:raise GlobalMediationClosureContractError("status invalid")
        if self.closure_record_digest:_sha(self.closure_record_digest,"closure_record_digest")
        if self.status=="MEDIATED" and not self.closure_record_digest:raise GlobalMediationClosureContractError("MEDIATED requires closure record")
        return self

@dataclass(frozen=True)
class GlobalMediationClosureCarrier:
    repository:str
    revision:str
    tree_digest:str
    inventory_digest:str
    scan_digest:str
    taxonomy_report_digest:str
    surface_count:int
    unclassified_count:int
    surface_statuses:Tuple[GlobalMediationSurfaceStatus,...]
    explicit_unknown_surface_digests:Tuple[str,...]
    evidence_refs:Tuple[str,...]
    global_status:str
    def validate(self):
        for n in ("repository","revision","tree_digest"):_text(getattr(self,n),n)
        for n in ("inventory_digest","scan_digest","taxonomy_report_digest"):_sha(getattr(self,n),n)
        if type(self.surface_count) is not int or self.surface_count<0 or type(self.unclassified_count) is not int or self.unclassified_count<0:raise GlobalMediationClosureContractError("counts invalid")
        _tuple(self.surface_statuses,"surface_statuses");_tuple(self.explicit_unknown_surface_digests,"explicit_unknown_surface_digests");_tuple(self.evidence_refs,"evidence_refs")
        for x in self.surface_statuses:x.validate()
        if len(self.surface_statuses)!=self.surface_count or len({x.surface_digest for x in self.surface_statuses})!=len(self.surface_statuses):raise GlobalMediationClosureContractError("surface status cardinality mismatch")
        for d in self.explicit_unknown_surface_digests:_sha(d,"explicit_unknown_surface_digest")
        known={x.surface_digest:x for x in self.surface_statuses}
        if set(self.explicit_unknown_surface_digests)-set(known):raise GlobalMediationClosureContractError("explicit unknown outside inventory")
        if any(known[d].status!="UNKNOWN" for d in self.explicit_unknown_surface_digests):raise GlobalMediationClosureContractError("explicit unknown cannot be promoted")
        if self.global_status not in {"PASS","UNKNOWN"}:raise GlobalMediationClosureContractError("global status invalid")
        if self.global_status=="PASS" and (self.unclassified_count or not self.surface_statuses or any(x.status!="MEDIATED" for x in self.surface_statuses) or self.explicit_unknown_surface_digests or not self.evidence_refs):raise GlobalMediationClosureContractError("PASS requires exact closed current matrix")
        return self
    def digest(self):self.validate();return _digest(b"LION/GLOBAL-MEDIATION-CLOSURE-CARRIER/1",self)
