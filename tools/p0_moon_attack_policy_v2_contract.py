from __future__ import annotations
from dataclasses import asdict,dataclass
from hashlib import sha256
import json,re
from typing import Tuple

_SHA64=re.compile(r"^[0-9a-f]{64}$")
_CLASSES=frozenset({"PRE_EFFECT_GUARD","SURFACE_EFFECT_ITSELF","POST_OBSERVATION_DECISION","DOWNSTREAM_CURRENTNESS_GUARD"})
_RELATIONS=frozenset({"BEFORE_SURFACE_EFFECT","AT_SURFACE_EFFECT","AFTER_SURFACE_EFFECT","AFTER_SOURCE_EFFECT_AND_STATE_WRITE_BEFORE_DOWNSTREAM_EFFECT"})
_EVIDENCE_CLASSES=frozenset({"BYPASS_DENIAL","ADMISSION_DECISION_NEGATIVE_EVIDENCE","DOWNSTREAM_CURRENTNESS_NEGATIVE_EVIDENCE"})
_EVIDENCE_STATES=frozenset({"CANONICAL_DENIAL_PRESENT","CONTROL_FLOW_OBSERVED_EVIDENCE_REQUIRED"})
MAPPING_DOMAIN=b"LION/MOON-ATTACK-EFFECT-BOUNDARY-MAPPING/2"
SURFACE_REQ_DOMAIN=b"LION/MOON-SURFACE-BYPASS-REQUIREMENT/2"
SECURITY_REQ_DOMAIN=b"LION/MOON-REHOMED-SECURITY-REQUIREMENT/2"
POLICY_DOMAIN=b"LION/MEDIATION-ATTACK-REQUIREMENT-POLICY/2"
REPORT_DOMAIN=b"LION/MOON-PERMISSION-POLICY-TOPOLOGY-READINESS/2"

class MoonAttackPolicyV2ContractError(ValueError):pass

def _text(v,n):
    if not isinstance(v,str) or not v.strip() or "\x00" in v:raise MoonAttackPolicyV2ContractError(f"{n} invalid")
    return v
def _sha(v,n):
    _text(v,n)
    if _SHA64.fullmatch(v) is None:raise MoonAttackPolicyV2ContractError(f"{n} must be sha256")
    return v
def _tuple(v,n,required=False):
    if type(v) is not tuple or (required and not v):raise MoonAttackPolicyV2ContractError(f"{n} must be immutable tuple")
    for x in v:_text(x,n)
    if len(set(v))!=len(v):raise MoonAttackPolicyV2ContractError(f"{n} must be unique")
    return v
def _digest(domain,obj):
    raw=json.dumps(asdict(obj),sort_keys=True,separators=(",",":"),ensure_ascii=False,default=list).encode()
    return sha256(domain+b"\0"+raw).hexdigest()

@dataclass(frozen=True)
class EffectBoundaryAttackMapping:
    attack_id:str;origin_surface_digest:str;classification:str;pep_name:str;expected_denial:str;surface_effect_entrypoint:str;effect_boundary_relation:str;target_surface_digest:str;required_evidence_class:str;rationale:str;source_refs:Tuple[str,...]
    def validate(self):
        _text(self.attack_id,"attack_id");_sha(self.origin_surface_digest,"origin_surface_digest");_text(self.pep_name,"pep_name");_text(self.expected_denial,"expected_denial");_text(self.surface_effect_entrypoint,"surface_effect_entrypoint");_text(self.rationale,"rationale");_tuple(self.source_refs,"source_refs",True)
        if self.classification not in _CLASSES:raise MoonAttackPolicyV2ContractError("classification invalid")
        if self.effect_boundary_relation not in _RELATIONS:raise MoonAttackPolicyV2ContractError("effect boundary relation invalid")
        if self.required_evidence_class not in _EVIDENCE_CLASSES:raise MoonAttackPolicyV2ContractError("required evidence class invalid")
        if self.target_surface_digest:_sha(self.target_surface_digest,"target_surface_digest")
        if self.classification=="PRE_EFFECT_GUARD":
            if self.effect_boundary_relation!="BEFORE_SURFACE_EFFECT" or self.target_surface_digest!=self.origin_surface_digest or self.required_evidence_class!="BYPASS_DENIAL":raise MoonAttackPolicyV2ContractError("pre-effect mapping invalid")
        if self.classification=="POST_OBSERVATION_DECISION":
            if self.effect_boundary_relation!="AFTER_SURFACE_EFFECT" or self.required_evidence_class!="ADMISSION_DECISION_NEGATIVE_EVIDENCE":raise MoonAttackPolicyV2ContractError("post-observation mapping invalid")
        if self.classification=="DOWNSTREAM_CURRENTNESS_GUARD":
            if self.effect_boundary_relation!="AFTER_SOURCE_EFFECT_AND_STATE_WRITE_BEFORE_DOWNSTREAM_EFFECT" or not self.target_surface_digest or self.required_evidence_class!="DOWNSTREAM_CURRENTNESS_NEGATIVE_EVIDENCE":raise MoonAttackPolicyV2ContractError("downstream mapping invalid")
        return self
    def digest(self):self.validate();return _digest(MAPPING_DOMAIN,self)

@dataclass(frozen=True)
class SurfaceBypassRequirementV2:
    surface_digest:str;attack_ids:Tuple[str,...];policy_version:str;rationale:str
    def validate(self):
        _sha(self.surface_digest,"surface_digest");_tuple(self.attack_ids,"attack_ids",True);_text(self.policy_version,"policy_version");_text(self.rationale,"rationale");return self
    def digest(self):self.validate();return _digest(SURFACE_REQ_DOMAIN,self)

@dataclass(frozen=True)
class RehomedSecurityRequirementV2:
    attack_id:str;origin_surface_digest:str;classification:str;target_surface_digest:str;pep_name:str;expected_denial:str;effect_boundary_relation:str;required_evidence_class:str;evidence_state:str;rationale:str;evidence_refs:Tuple[str,...]
    def validate(self):
        _text(self.attack_id,"attack_id");_sha(self.origin_surface_digest,"origin_surface_digest");_text(self.classification,"classification");_text(self.pep_name,"pep_name");_text(self.expected_denial,"expected_denial");_text(self.effect_boundary_relation,"effect_boundary_relation");_text(self.required_evidence_class,"required_evidence_class");_text(self.rationale,"rationale");_tuple(self.evidence_refs,"evidence_refs",True)
        if self.target_surface_digest:_sha(self.target_surface_digest,"target_surface_digest")
        if self.classification not in {"POST_OBSERVATION_DECISION","DOWNSTREAM_CURRENTNESS_GUARD"}:raise MoonAttackPolicyV2ContractError("rehomed class invalid")
        if self.required_evidence_class not in {"ADMISSION_DECISION_NEGATIVE_EVIDENCE","DOWNSTREAM_CURRENTNESS_NEGATIVE_EVIDENCE"}:raise MoonAttackPolicyV2ContractError("rehomed evidence class invalid")
        if self.evidence_state not in _EVIDENCE_STATES:raise MoonAttackPolicyV2ContractError("rehomed evidence state invalid")
        if self.evidence_state=="CANONICAL_DENIAL_PRESENT":raise MoonAttackPolicyV2ContractError("candidate cannot claim missing denial evidence")
        return self
    def digest(self):self.validate();return _digest(SECURITY_REQ_DOMAIN,self)

@dataclass(frozen=True)
class MediationAttackRequirementPolicyV2:
    inventory_digest:str;revision:str;policy_version:str;predecessor_policy_digest:str;surface_requirements:Tuple[SurfaceBypassRequirementV2,...];security_requirements:Tuple[RehomedSecurityRequirementV2,...];boundary_mapping_digests:Tuple[str,...];evidence_refs:Tuple[str,...]
    def validate(self):
        _sha(self.inventory_digest,"inventory_digest");_text(self.revision,"revision");_text(self.policy_version,"policy_version");_sha(self.predecessor_policy_digest,"predecessor_policy_digest");_tuple(self.boundary_mapping_digests,"boundary_mapping_digests",True);_tuple(self.evidence_refs,"evidence_refs",True)
        if type(self.surface_requirements) is not tuple or not self.surface_requirements:raise MoonAttackPolicyV2ContractError("surface requirements required")
        if type(self.security_requirements) is not tuple or len(self.security_requirements)!=2:raise MoonAttackPolicyV2ContractError("two rehomed security requirements required")
        for x in self.surface_requirements:x.validate()
        for x in self.security_requirements:x.validate()
        if len({x.surface_digest for x in self.surface_requirements})!=len(self.surface_requirements):raise MoonAttackPolicyV2ContractError("duplicate surface requirement")
        if len({x.attack_id for x in self.security_requirements})!=len(self.security_requirements):raise MoonAttackPolicyV2ContractError("duplicate security requirement")
        return self
    def digest(self):self.validate();return _digest(POLICY_DOMAIN,self)
    def required_attack_map(self):return {x.surface_digest:x.attack_ids for x in self.surface_requirements}

@dataclass(frozen=True)
class PermissionPolicyTopologyReadinessReportV2:
    inventory_digest:str;taxonomy_digest:str;predecessor_policy_digest:str;policy_v2_digest:str;mapping_digests:Tuple[str,...];security_requirement_digests:Tuple[str,...];closure_record_digests:Tuple[str,...];global_carrier_digest:str;seven_mediated_count:int;unknown_outside_seven_count:int;unresolved_security_requirement_keys:Tuple[str,...];next_evidence_plan:Tuple[str,...];global_status:str;evidence_refs:Tuple[str,...]
    def validate(self):
        for n in ("inventory_digest","taxonomy_digest","predecessor_policy_digest","policy_v2_digest","global_carrier_digest"):_sha(getattr(self,n),n)
        _tuple(self.mapping_digests,"mapping_digests",True);_tuple(self.security_requirement_digests,"security_requirement_digests",True);_tuple(self.closure_record_digests,"closure_record_digests",True);_tuple(self.unresolved_security_requirement_keys,"unresolved_security_requirement_keys",True);_tuple(self.next_evidence_plan,"next_evidence_plan",True);_tuple(self.evidence_refs,"evidence_refs",True)
        if self.seven_mediated_count!=7 or self.unknown_outside_seven_count!=229:raise MoonAttackPolicyV2ContractError("unexpected v2 closure counts")
        if self.unresolved_security_requirement_keys!=("STALE_AUTHORITY_SOURCE","UNTRUSTED_PERMISSION"):raise MoonAttackPolicyV2ContractError("security requirements must remain explicit")
        if self.global_status!="UNKNOWN":raise MoonAttackPolicyV2ContractError("global status must remain UNKNOWN")
        return self
    def digest(self):self.validate();return _digest(REPORT_DOMAIN,self)
