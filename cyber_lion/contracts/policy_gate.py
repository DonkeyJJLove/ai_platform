"""Canonical PDP/Gate contracts. Evidence and status never mint authority."""
from __future__ import annotations
from dataclasses import dataclass, asdict
from hashlib import sha256
import json,re
from typing import Tuple

_SHA256=re.compile(r"^sha256:[0-9a-f]{64}$")
_HEX64=re.compile(r"^[0-9a-f]{64}$")
LANES={"GREEN","AMBER","RED"}
OBSERVABILITY_STATES={"HEALTHY","DEGRADED","LOST"}
DECISIONS={"ALLOW","DENY"}

class PolicyGateContractError(ValueError): pass

def _text(v,name):
    if not isinstance(v,str) or not v.strip(): raise PolicyGateContractError(f"{name} required")
    return v

def _canon(obj): return json.dumps(obj,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()
def _digest(obj): return sha256(_canon(obj)).hexdigest()

@dataclass(frozen=True)
class PolicyRevision:
    policy_id:str; revision:str; content_digest:str; lane:str; active:bool=True
    schema_version:str="1.0.0"
    def validate(self):
        if self.schema_version!="1.0.0": raise PolicyGateContractError("unsupported policy schema")
        _text(self.policy_id,"policy_id");_text(self.revision,"revision")
        if not _SHA256.fullmatch(self.content_digest): raise PolicyGateContractError("content_digest must be sha256:<hex>")
        if self.lane not in LANES: raise PolicyGateContractError("invalid lane")
        if type(self.active) is not bool: raise PolicyGateContractError("active must be boolean")
        return self
    @property
    def binding(self): self.validate(); return f"{self.policy_id}@{self.revision}:{self.content_digest}"

@dataclass(frozen=True)
class GateRequested:
    request_id:str; proposal_id:str; policy_binding:str; authority_lineage_digest:str
    enterprise_graph_digest:str; status_digest:str; observability_state:str; lane:str
    requested_authority:str; evidence_refs:Tuple[str,...]; request_digest:str=""
    schema_version:str="1.0.0"
    def canonical_payload(self):
        d=asdict(self);d.pop("request_digest");d["evidence_refs"]=list(self.evidence_refs);return d
    def compute_digest(self): return _digest(self.canonical_payload())
    def validate(self):
        if self.schema_version!="1.0.0": raise PolicyGateContractError("unsupported GateRequested schema")
        for n in ("request_id","proposal_id","policy_binding","requested_authority"): _text(getattr(self,n),n)
        for n in ("authority_lineage_digest","enterprise_graph_digest","status_digest"):
            if not _HEX64.fullmatch(getattr(self,n)): raise PolicyGateContractError(f"{n} must be canonical sha256 hex")
        if self.observability_state not in OBSERVABILITY_STATES: raise PolicyGateContractError("invalid observability_state")
        if self.lane not in LANES: raise PolicyGateContractError("invalid lane")
        if not self.evidence_refs or len(set(self.evidence_refs))!=len(self.evidence_refs): raise PolicyGateContractError("unique evidence_refs required")
        if self.request_digest and self.request_digest!=self.compute_digest(): raise PolicyGateContractError("request_digest mismatch")
        return self
    def sealed(self):
        self.validate();return GateRequested(**{**asdict(self),"request_digest":self.compute_digest()})

@dataclass(frozen=True)
class GateApplied:
    gate_event_id:str; request_id:str; proposal_id:str; decision:str; effective_authority:str
    policy_binding:str; authority_lineage_digest:str; enterprise_graph_digest:str; status_digest:str
    observability_state:str; lane:str; rationale:str; decision_digest:str=""; schema_version:str="1.0.0"
    def canonical_payload(self):
        d=asdict(self);d.pop("decision_digest");return d
    def compute_digest(self): return _digest(self.canonical_payload())
    def validate(self):
        if self.schema_version!="1.0.0": raise PolicyGateContractError("unsupported GateApplied schema")
        for n in ("gate_event_id","request_id","proposal_id","policy_binding","rationale"): _text(getattr(self,n),n)
        if self.decision not in DECISIONS: raise PolicyGateContractError("invalid decision")
        if self.decision=="DENY" and self.effective_authority!="none": raise PolicyGateContractError("DENY requires none authority")
        if self.observability_state not in OBSERVABILITY_STATES or self.lane not in LANES: raise PolicyGateContractError("invalid lane/observability")
        for n in ("authority_lineage_digest","enterprise_graph_digest","status_digest"):
            if not _HEX64.fullmatch(getattr(self,n)): raise PolicyGateContractError(f"{n} invalid")
        if self.decision_digest and self.decision_digest!=self.compute_digest(): raise PolicyGateContractError("decision_digest mismatch")
        return self
    def sealed(self):
        self.validate();return GateApplied(**{**asdict(self),"decision_digest":self.compute_digest()})

@dataclass(frozen=True)
class PDPDecisionReceipt:
    receipt_id:str; request_id:str; gate_event_id:str; request_digest:str; decision_digest:str
    replay_key:str; schema_version:str="1.0.0"
    def validate(self):
        if self.schema_version!="1.0.0": raise PolicyGateContractError("unsupported receipt schema")
        for n in ("receipt_id","request_id","gate_event_id"): _text(getattr(self,n),n)
        for n in ("request_digest","decision_digest","replay_key"):
            if not _HEX64.fullmatch(getattr(self,n)): raise PolicyGateContractError(f"{n} invalid")
        return self
