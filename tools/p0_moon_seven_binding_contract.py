from __future__ import annotations
from dataclasses import asdict,dataclass
from hashlib import sha256
import json,re
from typing import Tuple

_SHA64=re.compile(r"^[0-9a-f]{64}$")
_SHA40=re.compile(r"^[0-9a-f]{40}$")
EVIDENCE_STATES=frozenset({"OBSERVED","CANDIDATE_UNOBSERVED"})
EXECUTION_CLASSES=frozenset({"STRUCTURAL_ONLY","SAFE_LIVE_DENIAL","BLOCKED_LIVE"})
COMPONENT_DOMAINS={
    "effect_contract":b"LION/MOON-SEVEN-EFFECT-CONTRACT/1",
    "authority_source":b"LION/MOON-SEVEN-AUTHORITY-SOURCE/1",
    "currentness_source":b"LION/MOON-SEVEN-CURRENTNESS-SOURCE/1",
    "pep_identity":b"LION/MOON-SEVEN-PEP-IDENTITY/1",
    "execution_boundary":b"LION/MOON-SEVEN-EXECUTION-BOUNDARY/1",
    "observer_identity":b"LION/MOON-SEVEN-OBSERVER-IDENTITY/1",
    "reconciliation_boundary":b"LION/MOON-SEVEN-RECONCILIATION-BOUNDARY/1",
    "replay_guard":b"LION/MOON-SEVEN-REPLAY-GUARD/1",
    "bounded_scope":b"LION/MOON-SEVEN-BOUNDED-SCOPE/1",
    "verifier_identity":b"LION/MOON-SEVEN-VERIFIER-IDENTITY/1",
}
BUNDLE_DOMAIN=b"LION/MOON-SEVEN-EVIDENCE-BUNDLE/1"
OUTCOME_DOMAIN=b"LION/MOON-SEVEN-BINDING-OUTCOME/1"
ATTACK_DOMAIN=b"LION/MOON-SEVEN-BYPASS-ATTACK-SPEC/1"
CARRIER_DOMAIN=b"LION/MOON-SEVEN-FALSIFICATION-CARRIER-SPEC/1"
PLAN_DOMAIN=b"LION/MOON-SEVEN-BINDING-PLAN/1"

class MoonSevenContractError(ValueError):pass

def _text(v,n):
    if not isinstance(v,str) or not v.strip() or "\x00" in v:raise MoonSevenContractError(f"{n} invalid")
    return v

def _sha(v,n):
    _text(v,n)
    if not _SHA64.fullmatch(v):raise MoonSevenContractError(f"{n} must be sha256")
    return v

def _tuple(v,n,required=False):
    if type(v) is not tuple or (required and not v):raise MoonSevenContractError(f"{n} must be immutable tuple")
    if len(set(v))!=len(v):raise MoonSevenContractError(f"{n} must be unique")
    for x in v:_text(x,n)
    return v

def _digest(domain,obj):
    raw=json.dumps(asdict(obj),sort_keys=True,separators=(",",":"),ensure_ascii=False,default=list).encode()
    return sha256(domain+b"\0"+raw).hexdigest()

@dataclass(frozen=True)
class MoonEvidenceComponent:
    component_type:str
    subject:str
    revision:str
    payload:Tuple[Tuple[str,str],...]
    evidence_refs:Tuple[str,...]
    evidence_state:str
    def validate(self):
        if self.component_type not in COMPONENT_DOMAINS:raise MoonSevenContractError("unknown component type")
        _text(self.subject,"subject")
        if not _SHA40.fullmatch(self.revision):raise MoonSevenContractError("revision must be git sha")
        if type(self.payload) is not tuple or not self.payload:raise MoonSevenContractError("payload required")
        keys=[]
        for item in self.payload:
            if type(item) is not tuple or len(item)!=2:raise MoonSevenContractError("payload item invalid")
            k,v=item;_text(k,"payload key");_text(v,"payload value");keys.append(k)
        if len(set(keys))!=len(keys) or tuple(sorted(self.payload))!=self.payload:raise MoonSevenContractError("payload must be unique canonical tuple")
        _tuple(self.evidence_refs,"evidence_refs",True)
        if self.evidence_state not in EVIDENCE_STATES:raise MoonSevenContractError("invalid evidence state")
        return self
    def digest(self):self.validate();return _digest(COMPONENT_DOMAINS[self.component_type],self)

@dataclass(frozen=True)
class MoonSurfaceEvidenceBundle:
    surface_digest:str
    effect_contract_digest:str
    authority_source_digest:str
    currentness_source_digest:str
    pep_identity_digest:str
    execution_boundary_digest:str
    observer_identity_digests:Tuple[str,...]
    reconciliation_boundary_digest:str
    replay_guard_digest:str
    bounded_scope_digest:str
    verifier_identity_digest:str
    blockers:Tuple[str,...]
    evidence_refs:Tuple[str,...]
    def validate(self):
        for n in ("surface_digest","effect_contract_digest","authority_source_digest","currentness_source_digest","pep_identity_digest","execution_boundary_digest","reconciliation_boundary_digest","replay_guard_digest","bounded_scope_digest","verifier_identity_digest"):_sha(getattr(self,n),n)
        if type(self.observer_identity_digests) is not tuple or not self.observer_identity_digests:raise MoonSevenContractError("observer identities required")
        for x in self.observer_identity_digests:_sha(x,"observer_identity_digest")
        _tuple(self.blockers,"blockers");_tuple(self.evidence_refs,"evidence_refs",True);return self
    def digest(self):self.validate();return _digest(BUNDLE_DOMAIN,self)

@dataclass(frozen=True)
class MoonBindingOutcome:
    surface_digest:str
    candidate_digest:str
    binding_digest:str
    chain_digest:str
    status:str
    blockers:Tuple[str,...]
    evidence_refs:Tuple[str,...]
    def validate(self):
        _sha(self.surface_digest,"surface_digest");_sha(self.candidate_digest,"candidate_digest")
        if self.binding_digest:_sha(self.binding_digest,"binding_digest")
        if self.chain_digest:_sha(self.chain_digest,"chain_digest")
        if self.status not in {"RESOLVED","BLOCKED"}:raise MoonSevenContractError("invalid outcome status")
        _tuple(self.blockers,"blockers");_tuple(self.evidence_refs,"evidence_refs",True)
        if self.status=="RESOLVED" and (not self.binding_digest or not self.chain_digest or self.blockers):raise MoonSevenContractError("resolved outcome incomplete")
        if self.status=="BLOCKED" and (self.binding_digest or self.chain_digest or not self.blockers):raise MoonSevenContractError("blocked outcome invalid")
        return self
    def digest(self):self.validate();return _digest(OUTCOME_DOMAIN,self)

@dataclass(frozen=True)
class MoonSafeAttackSpec:
    attack_id:str
    surface_digests:Tuple[str,...]
    family:str
    attempted_entrypoint:str
    expected_denial:str
    execution_class:str
    target_mutation_allowed:bool
    evidence_refs:Tuple[str,...]
    def validate(self):
        for n in ("attack_id","family","attempted_entrypoint","expected_denial"):_text(getattr(self,n),n)
        if type(self.surface_digests) is not tuple or not self.surface_digests:raise MoonSevenContractError("attack surfaces required")
        for x in self.surface_digests:_sha(x,"surface_digest")
        if self.execution_class not in EXECUTION_CLASSES:raise MoonSevenContractError("invalid execution class")
        if type(self.target_mutation_allowed) is not bool or self.target_mutation_allowed:raise MoonSevenContractError("target mutation must be forbidden")
        _tuple(self.evidence_refs,"evidence_refs",True);return self
    def digest(self):self.validate();return _digest(ATTACK_DOMAIN,self)

@dataclass(frozen=True)
class MoonFalsificationCarrierSpec:
    repository:str
    parent_revision:str
    control_issue:int
    runner_name:str
    runner_agent_id:int
    execution_host:str
    machine_id:str
    target_path:str
    fence_path:str
    surface_digests:Tuple[str,...]
    attack_digests:Tuple[str,...]
    observation_receipt_required:bool
    generic_shell:bool
    arbitrary_command:bool
    arbitrary_path:bool
    live_execution:bool
    state:str
    evidence_refs:Tuple[str,...]
    def validate(self):
        for n in ("repository","runner_name","execution_host","machine_id","target_path","fence_path"):_text(getattr(self,n),n)
        if not _SHA40.fullmatch(self.parent_revision):raise MoonSevenContractError("parent revision invalid")
        if self.control_issue!=144 or self.runner_agent_id!=24:raise MoonSevenContractError("carrier authority binding invalid")
        if type(self.surface_digests) is not tuple or len(self.surface_digests)!=7:raise MoonSevenContractError("exact seven surfaces required")
        for x in self.surface_digests:_sha(x,"surface_digest")
        if type(self.attack_digests) is not tuple or not self.attack_digests:raise MoonSevenContractError("attack digests required")
        for x in self.attack_digests:_sha(x,"attack_digest")
        if not self.observation_receipt_required or self.generic_shell or self.arbitrary_command or self.arbitrary_path or self.live_execution:raise MoonSevenContractError("carrier must remain bounded and unattached")
        if self.state!="CANDIDATE_UNATTACHED":raise MoonSevenContractError("invalid carrier state")
        _tuple(self.evidence_refs,"evidence_refs",True);return self
    def digest(self):self.validate();return _digest(CARRIER_DOMAIN,self)

@dataclass(frozen=True)
class MoonSevenBindingPlan:
    inventory_digest:str
    scan_digest:str
    candidate_count:int
    resolved_binding_count:int
    reconstructed_chain_count:int
    blocked_count:int
    bypass_result_count:int
    outcomes:Tuple[MoonBindingOutcome,...]
    attacks:Tuple[MoonSafeAttackSpec,...]
    carrier_digest:str
    live_falsification_executed:bool
    global_status:str
    evidence_refs:Tuple[str,...]
    def validate(self):
        _sha(self.inventory_digest,"inventory_digest");_sha(self.scan_digest,"scan_digest");_sha(self.carrier_digest,"carrier_digest")
        if (self.candidate_count,self.resolved_binding_count,self.reconstructed_chain_count,self.blocked_count,self.bypass_result_count)!=(7,5,5,2,0):raise MoonSevenContractError("unexpected plan counts")
        if type(self.outcomes) is not tuple or len(self.outcomes)!=7 or type(self.attacks) is not tuple or not self.attacks:raise MoonSevenContractError("plan matrix invalid")
        for x in self.outcomes:x.validate()
        for x in self.attacks:x.validate()
        if self.live_falsification_executed or self.global_status!="UNKNOWN":raise MoonSevenContractError("live/global state invalid")
        _tuple(self.evidence_refs,"evidence_refs",True);return self
    def digest(self):self.validate();return _digest(PLAN_DOMAIN,self)
