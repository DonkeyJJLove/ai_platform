"""Binding layer between canonical BeanSpec and the existing E004 builder chain.

This module deliberately does not construct permits, consume them, launch builders, or
mutate repository refs.  It binds an already externally issued BuilderInvocationPermit
to one BeanSpec and converts an already produced DetachedRepositoryCandidate into a
non-authoritative BeanCandidate.
"""
from __future__ import annotations
from dataclasses import asdict,dataclass
from hashlib import sha256
import json,re
from typing import Tuple
from .bean import BeanContractError,BeanSpec
from .bean_candidate import BeanCandidate
from .builder_invocation_permit import BuilderInvocationPermit
from .repository_mutation import DetachedRepositoryCandidate
_SHA64=re.compile(r"^[0-9a-f]{64}$")

@dataclass(frozen=True)
class BeanBuilderChainBinding:
    binding_id:str
    bean_id:str
    bean_spec_digest:str
    builder_invocation_permit_digest:str
    repository:str
    baseline_master_sha:str
    candidate_scope:Tuple[str,...]
    evidence_refs:Tuple[str,...]
    authority_effect:str="NONE"
    execution_effect:str="NONE"
    repository_ref_effect:str="NONE"
    external_effect:str="NONE"
    def validate(self):
        if not self.binding_id or not self.bean_id or not self.repository:raise BeanContractError("binding identity required")
        for name in ("bean_spec_digest","builder_invocation_permit_digest"):
            value=getattr(self,name)
            if not isinstance(value,str) or not _SHA64.fullmatch(value):raise BeanContractError(f"{name} invalid")
        if type(self.candidate_scope) is not tuple or not self.candidate_scope or len(set(self.candidate_scope))!=len(self.candidate_scope):raise BeanContractError("candidate_scope invalid")
        if type(self.evidence_refs) is not tuple or not self.evidence_refs or len(set(self.evidence_refs))!=len(self.evidence_refs):raise BeanContractError("evidence_refs invalid")
        if (self.authority_effect,self.execution_effect,self.repository_ref_effect,self.external_effect)!=("NONE","NONE","NONE","NONE"):raise BeanContractError("Bean builder binding cannot carry effects")
        return self
    def digest(self):
        self.validate();raw=json.dumps(asdict(self),sort_keys=True,separators=(",",":"),ensure_ascii=False,default=list).encode();return sha256(b"LION/BEAN-BUILDER-CHAIN-BINDING/1\0"+raw).hexdigest()

def bind_bean_to_builder_permit(*,spec:BeanSpec,permit:BuilderInvocationPermit,evidence_refs:Tuple[str,...])->BeanBuilderChainBinding:
    spec.validate();permit.validate()
    if not permit.builder_invocation_permit_digest:raise BeanContractError("builder permit must be sealed")
    if permit.action!="BUILD_CANDIDATE":raise BeanContractError("only existing detached candidate builder chain is admissible")
    if (permit.authority_effect,permit.execution_effect,permit.repository_ref_effect,permit.external_effect)!=("NONE","NONE","NONE","NONE"):raise BeanContractError("effectful builder permit denied")
    return BeanBuilderChainBinding(binding_id=f"bean-build:{spec.spec_digest()}:{permit.builder_invocation_permit_digest}",bean_id=spec.bean_id,bean_spec_digest=spec.spec_digest(),builder_invocation_permit_digest=permit.builder_invocation_permit_digest,repository=permit.repository,baseline_master_sha=permit.baseline_master_sha,candidate_scope=permit.candidate_scope,evidence_refs=evidence_refs).validate()

def detached_repository_candidate_to_bean_candidate(*,binding:BeanBuilderChainBinding,spec:BeanSpec,permit:BuilderInvocationPermit,candidate:DetachedRepositoryCandidate,builder_identity_digest:str)->BeanCandidate:
    binding.validate();spec.validate();permit.validate();candidate.validate()
    if binding.bean_id!=spec.bean_id or binding.bean_spec_digest!=spec.spec_digest():raise BeanContractError("BeanSpec substitution detected")
    if binding.builder_invocation_permit_digest!=permit.builder_invocation_permit_digest:raise BeanContractError("builder permit substitution detected")
    if candidate.repository!=binding.repository or candidate.expected_head_sha!=binding.baseline_master_sha:raise BeanContractError("detached candidate baseline/repository substitution detected")
    if tuple(candidate.changed_paths)!=tuple(binding.candidate_scope):raise BeanContractError("detached candidate scope substitution detected")
    # Git tree SHA is a 40-char object id, so bind the Bean implementation by hashing the exact detached-candidate digest.
    implementation_digest=sha256(b"LION/BEAN-REPOSITORY-IMPLEMENTATION/1\0"+candidate.digest().encode("ascii")).hexdigest()
    return BeanCandidate(candidate_id=f"bean-candidate:{candidate.digest()}",bean_id=spec.bean_id,spec_digest=spec.spec_digest(),implementation_digest=implementation_digest,builder_identity_digest=builder_identity_digest,build_evidence_refs=(binding.digest(),permit.builder_invocation_permit_digest,candidate.digest()),acceptance_evidence_refs=(),verifier_identity_digests=(),verification_evidence_refs=(),state="BUILT").validate()
