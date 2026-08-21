"""Capability-reduced Repository Mutation PEP core R2.

Operation callers provide intent/candidate/authority evidence and audit timestamps only.
Verification source, exact-CAS effect port, independent observer, trusted clock, dependency
pins, runtime-scope pin and the canonical local journal are composition-root owned.

The journal is deliberately SINGLE_RUNTIME_ATTACH_ONLY, not a globally linearizable
multi-host effect store. Authority must carry the exact runtime-scope constraint. This is
a reference enforcement core, not complete mediation or an L2 claim.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from typing import Protocol

from cyber_lion.contracts.repository_mutation import (
    AttachProviderResult,
    CandidateVerificationSource,
    DetachedRepositoryCandidate,
    ExactRefAttachIntent,
    RepositoryAttachAdmission,
    RepositoryEffectReceipt,
    RepositoryMutationContractError,
    TrustedDependencyPin,
    TrustedRefState,
    TrustedVerifierPin,
    VerifiedDetachedCandidate,
    canonical_attach_resource,
    canonical_authority_effect_key,
    canonical_verification_constraint,
    canonical_runtime_binding_digest,
)
from cyber_lion.enterprise.authority_grant import AuthorityGrant, AuthorityGrantError
from cyber_lion.enterprise.live_authority_admission import (
    LiveAdmittedAuthority,
    LiveAuthorityAdmission,
    LiveAuthorityAdmissionError,
)
from cyber_lion.enterprise.repository_mutation_state import (
    JOURNAL_SCOPE_CLASS,
    RepositoryAttachJournal,
    RepositoryEffectState,
    RepositoryMutationStateError,
)

class RepositoryMutationPEPError(RuntimeError):
    pass

class ExactFastForwardRefPort(Protocol):
    dependency_id:str
    identity_digest:str
    implementation_digest:str
    def compare_and_swap_fast_forward(self,*,repository:str,branch:str,expected_old_sha:str,candidate_commit_sha:str)->AttachProviderResult: ...

class TrustedRefObserverPort(Protocol):
    dependency_id:str
    identity_digest:str
    implementation_digest:str
    def observe_ref(self,*,repository:str,branch:str)->TrustedRefState: ...

class TrustedClockPort(Protocol):
    dependency_id:str
    identity_digest:str
    implementation_digest:str
    def now(self)->datetime: ...

def _bind_dependency(dependency:object,pin:TrustedDependencyPin,*,required_method:str,role:str)->None:
    if type(pin) is not TrustedDependencyPin:
        raise RepositoryMutationPEPError(f"{role} pin is invalid")
    pin.validate()
    actual=(getattr(dependency,"dependency_id",None),getattr(dependency,"identity_digest",None),getattr(dependency,"implementation_digest",None))
    expected=(pin.dependency_id,pin.identity_digest,pin.implementation_digest)
    if actual!=expected:
        raise RepositoryMutationPEPError(f"{role} does not match trusted composition-root pin")
    if not callable(getattr(dependency,required_method,None)):
        raise RepositoryMutationPEPError(f"{role} lacks required capability {required_method}")

def _deny(*,admission_id:str,effect_id:str,intent:ExactRefAttachIntent,candidate:DetachedRepositoryCandidate,
          verification_digest:str,rationale:str,authority_effect_key:str="0"*64,runtime_binding_digest:str="0"*64)->RepositoryAttachAdmission:
    return RepositoryAttachAdmission(
        admission_id=admission_id, decision="DENY",
        rationale=rationale or "repository mutation admission failed closed",
        effect_id=effect_id, authority_effect_key=authority_effect_key,
        intent_digest=intent.digest(), candidate_digest=candidate.digest(),
        verification_digest=verification_digest, runtime_binding_digest=runtime_binding_digest,
    ).validate()

class RepositoryMutationPEP:
    """Admit and apply one exact verified ref attachment inside one trusted runtime scope."""

    def __init__(self,*,live_admission:LiveAuthorityAdmission,
                 verification_source:CandidateVerificationSource,verifier_pin:TrustedVerifierPin,
                 effect_port:ExactFastForwardRefPort,effect_pin:TrustedDependencyPin,
                 observer:TrustedRefObserverPort,observer_pin:TrustedDependencyPin,
                 clock:TrustedClockPort,clock_pin:TrustedDependencyPin,
                 runtime_scope_pin:TrustedDependencyPin)->None:
        if type(live_admission) is not LiveAuthorityAdmission:
            raise RepositoryMutationPEPError("live_admission must be exact LiveAuthorityAdmission")
        if not isinstance(verification_source,CandidateVerificationSource):
            raise RepositoryMutationPEPError("verification source must implement CandidateVerificationSource")
        if type(verifier_pin) is not TrustedVerifierPin:
            raise RepositoryMutationPEPError("trusted verifier pin is invalid")
        verifier_pin.validate(); verification_source.validate_pin(verifier_pin)
        _bind_dependency(effect_port,effect_pin,required_method="compare_and_swap_fast_forward",role="exact-CAS effect provider")
        _bind_dependency(observer,observer_pin,required_method="observe_ref",role="independent ref observer")
        _bind_dependency(clock,clock_pin,required_method="now",role="trusted clock")
        if type(runtime_scope_pin) is not TrustedDependencyPin:
            raise RepositoryMutationPEPError("runtime scope pin is invalid")
        runtime_scope_pin.validate()
        ids={effect_pin.dependency_id,observer_pin.dependency_id,clock_pin.dependency_id,runtime_scope_pin.dependency_id}
        if len(ids)!=4 or effect_pin.identity_digest==observer_pin.identity_digest:
            raise RepositoryMutationPEPError("effect, observer, clock and runtime scope must be independently pinned")

        self._live_admission=live_admission
        self._verification_source=verification_source
        self._verifier_pin=verifier_pin
        self._effect_port=effect_port
        self._effect_pin=effect_pin
        self._observer=observer
        self._observer_pin=observer_pin
        self._clock=clock
        self._clock_pin=clock_pin
        self._runtime_scope_pin=runtime_scope_pin

        r1=canonical_runtime_binding_digest(verifier_pin,effect_pin,observer_pin)
        material=(r1+clock_pin.digest()+runtime_scope_pin.digest()+JOURNAL_SCOPE_CLASS).encode("utf-8")
        self._runtime_binding_digest=sha256(b"LION/REPOSITORY-RUNTIME-BINDING/1.2.0\x00"+material).hexdigest()
        self._runtime_scope_constraint=f"runtime_scope:{runtime_scope_pin.digest()}"
        self._journal=RepositoryAttachJournal()
        if self._journal.scope_class!="SINGLE_RUNTIME_ATTACH_ONLY":
            raise RepositoryMutationPEPError("repository journal scope classification is invalid")

    @property
    def journal_path(self)->str: return self._journal.path
    @property
    def journal_scope_class(self)->str: return self._journal.scope_class
    @property
    def runtime_scope_constraint(self)->str: return self._runtime_scope_constraint

    def _trusted_now(self)->datetime:
        _bind_dependency(self._clock,self._clock_pin,required_method="now",role="trusted clock")
        value=self._clock.now()
        if type(value) is not datetime or value.tzinfo is None:
            raise RepositoryMutationPEPError("trusted clock returned invalid time")
        return value.astimezone(timezone.utc)

    @staticmethod
    def _bind_candidate(intent:ExactRefAttachIntent,candidate:DetachedRepositoryCandidate,
                        verification:VerifiedDetachedCandidate,*,pin:TrustedVerifierPin)->None:
        intent.validate(); candidate.validate(); verification.validate_for(candidate,pin=pin)
        expected=(intent.repository,intent.branch,intent.expected_head_sha,intent.expected_parent_sha,
                  intent.candidate_commit_sha,intent.candidate_tree_sha,intent.candidate_verification_digest)
        actual=(candidate.repository,candidate.branch,candidate.expected_head_sha,candidate.expected_parent_sha,
                candidate.candidate_commit_sha,candidate.candidate_tree_sha,verification.digest())
        if actual!=expected: raise RepositoryMutationPEPError("attach intent does not bind exact verified candidate")

    @staticmethod
    def _bind_expected_ref(intent:ExactRefAttachIntent,trusted_state:TrustedRefState)->None:
        if type(trusted_state) is not TrustedRefState: raise RepositoryMutationPEPError("trusted ref state must be exact TrustedRefState")
        trusted_state.validate()
        if (trusted_state.repository,trusted_state.branch,trusted_state.head_sha)!=(intent.repository,intent.branch,intent.expected_head_sha):
            raise RepositoryMutationPEPError("trusted ref state does not match exact expected head")

    def _bind_authority(self,*,intent:ExactRefAttachIntent,admitted:LiveAdmittedAuthority,
                        authority_leaf:AuthorityGrant)->tuple[str,str]:
        if type(admitted) is not LiveAdmittedAuthority: raise RepositoryMutationPEPError("live authority receipt must be exact LiveAdmittedAuthority")
        if type(authority_leaf) is not AuthorityGrant: raise RepositoryMutationPEPError("authority leaf must be exact AuthorityGrant")
        admitted.validate(); authority_leaf.validate()
        if (admitted.repository!=intent.repository or admitted.head_sha!=intent.expected_head_sha or admitted.mission_id!=intent.mission_id):
            raise RepositoryMutationPEPError("live authority does not bind exact repository/head/mission")
        if authority_leaf.grant_id!=admitted.grant_id: raise RepositoryMutationPEPError("authority leaf does not match live admitted grant")
        grant_digest=authority_leaf.digest()
        if grant_digest!=admitted.leaf_grant_digest: raise RepositoryMutationPEPError("authority leaf digest does not match authenticated live admission")
        if authority_leaf.mission_id!=intent.mission_id or authority_leaf.epoch!=admitted.epoch:
            raise RepositoryMutationPEPError("authority leaf mission/epoch does not match live admission")
        if intent.action not in authority_leaf.actions: raise RepositoryMutationPEPError("authority leaf does not authorize fast_forward_ref")
        if canonical_attach_resource(intent) not in authority_leaf.resource_scope:
            raise RepositoryMutationPEPError("authority leaf does not bind exact attach resource")
        required={"force:false","single_effect:true",canonical_verification_constraint(intent),self._runtime_scope_constraint}
        if not required.issubset(authority_leaf.constraints):
            raise RepositoryMutationPEPError("authority leaf lacks exact attach/runtime-scope constraints")
        return grant_digest, admitted.digest()

    def _observe(self,intent:ExactRefAttachIntent)->TrustedRefState:
        observed=self._observer.observe_ref(repository=intent.repository,branch=intent.branch)
        if type(observed) is not TrustedRefState: raise RepositoryMutationPEPError("observer returned invalid ref state type")
        return observed.validate()

    def admit(self,*,intent:ExactRefAttachIntent,candidate:DetachedRepositoryCandidate,
              admitted:LiveAdmittedAuthority,authority_leaf:AuthorityGrant,
              admission_id:str,effect_id:str)->RepositoryAttachAdmission:
        """Reserve one effect using composition-root clock; operation callers cannot supply time."""
        if type(intent) is not ExactRefAttachIntent: raise RepositoryMutationPEPError("intent must be exact ExactRefAttachIntent")
        if type(candidate) is not DetachedRepositoryCandidate: raise RepositoryMutationPEPError("candidate must be exact DetachedRepositoryCandidate")
        intent.validate(); candidate.validate()
        provisional="0"*64; authority_effect_key="0"*64
        try:
            if not isinstance(admission_id,str) or not admission_id.strip(): raise RepositoryMutationPEPError("admission_id is required")
            if not isinstance(effect_id,str) or not effect_id.strip(): raise RepositoryMutationPEPError("effect_id is required")
            verified=self._verification_source.resolve_exact(candidate,pin=self._verifier_pin)
            provisional=verified.digest()
            self._bind_candidate(intent,candidate,verified,pin=self._verifier_pin)
            before=self._observe(intent); self._bind_expected_ref(intent,before)
            now=self._trusted_now()
            prepared_at=now.isoformat()
            current=self._live_admission.revalidate(admitted,now=now)
            grant_digest,live_digest=self._bind_authority(intent=intent,admitted=current,authority_leaf=authority_leaf)
            authority_effect_key=canonical_authority_effect_key(mission_id=intent.mission_id,grant_id=current.grant_id,grant_digest=grant_digest,epoch=current.epoch)
            decision=RepositoryAttachAdmission(
                admission_id=admission_id,decision="ALLOW",
                rationale="exact verified candidate, pinned dependencies, trusted clock, current authority and single-runtime scope",
                effect_id=effect_id,authority_effect_key=authority_effect_key,
                intent_digest=intent.digest(),candidate_digest=candidate.digest(),
                verification_digest=verified.digest(),runtime_binding_digest=self._runtime_binding_digest,
                live_admission_digest=live_digest,grant_id=current.grant_id,grant_digest=grant_digest,authority_epoch=current.epoch,
            ).validate()
            self._journal.prepare(
                effect_id=effect_id,authority_effect_key=authority_effect_key,admission_id=admission_id,
                admission_digest=decision.digest(),intent_digest=intent.digest(),candidate_digest=candidate.digest(),
                repository=intent.repository,branch=intent.branch,expected_head_sha=intent.expected_head_sha,
                expected_parent_sha=intent.expected_parent_sha,candidate_commit_sha=intent.candidate_commit_sha,
                candidate_tree_sha=intent.candidate_tree_sha,verification_digest=verified.digest(),
                runtime_binding_digest=self._runtime_binding_digest,live_admission_digest=live_digest,
                grant_id=current.grant_id,grant_digest=grant_digest,authority_epoch=current.epoch,prepared_at=prepared_at)
            return decision
        except (AuthorityGrantError,LiveAuthorityAdmissionError,RepositoryMutationContractError,
                RepositoryMutationPEPError,RepositoryMutationStateError,TypeError,ValueError) as exc:
            return _deny(admission_id=admission_id,effect_id=effect_id,intent=intent,candidate=candidate,
                         verification_digest=provisional,rationale=str(exc),authority_effect_key=authority_effect_key,
                         runtime_binding_digest=self._runtime_binding_digest)

    def _assert_journal_binding(self,state:RepositoryEffectState,admission:RepositoryAttachAdmission,intent:ExactRefAttachIntent)->None:
        expected=(admission.effect_id,admission.authority_effect_key,admission.admission_id,admission.digest(),
                  admission.intent_digest,admission.candidate_digest,intent.repository,intent.branch,
                  intent.expected_head_sha,intent.expected_parent_sha,intent.candidate_commit_sha,
                  intent.candidate_tree_sha,admission.verification_digest,admission.runtime_binding_digest,
                  admission.live_admission_digest,admission.grant_id,admission.grant_digest,admission.authority_epoch)
        actual=(state.effect_id,state.authority_effect_key,state.admission_id,state.admission_digest,
                state.intent_digest,state.candidate_digest,state.repository,state.branch,state.expected_head_sha,
                state.expected_parent_sha,state.candidate_commit_sha,state.candidate_tree_sha,state.verification_digest,
                state.runtime_binding_digest,state.live_admission_digest,state.grant_id,state.grant_digest,state.authority_epoch)
        if actual!=expected: raise RepositoryMutationPEPError("durable journal does not bind exact admission/intent/evidence")
        if admission.runtime_binding_digest!=self._runtime_binding_digest:
            raise RepositoryMutationPEPError("admission was created under a different trusted runtime binding")

    def _receipt(self,*,admission:RepositoryAttachAdmission,intent:ExactRefAttachIntent,observed:TrustedRefState)->RepositoryEffectReceipt:
        if admission.decision!="ALLOW" or admission.grant_digest is None: raise RepositoryMutationPEPError("invalid admission for success receipt")
        return RepositoryEffectReceipt(
            effect_id=admission.effect_id,admission_id=admission.admission_id,admission_digest=admission.digest(),
            repository=intent.repository,branch=intent.branch,expected_head_sha=intent.expected_head_sha,
            candidate_commit_sha=intent.candidate_commit_sha,candidate_tree_sha=intent.candidate_tree_sha,
            observed_head_sha=observed.head_sha,verification_digest=admission.verification_digest,
            grant_digest=admission.grant_digest,provider_id=self._effect_pin.dependency_id,
            observer_id=self._observer_pin.dependency_id,observed_at=observed.observed_at).validate()

    def _reconcile_without_new_effect(self,*,admission:RepositoryAttachAdmission,intent:ExactRefAttachIntent,finalized_at:str)->RepositoryEffectReceipt|None:
        try: observed=self._observe(intent)
        except Exception:
            finalized_at=self._trusted_now().isoformat()
            self._journal.mark_reconcile_required(admission.effect_id,observed_head_sha=None,finalized_at=finalized_at); return None
        finalized_at=self._trusted_now().isoformat()
        if observed.repository==intent.repository and observed.branch==intent.branch and observed.head_sha==intent.candidate_commit_sha:
            self._journal.mark_applied(admission.effect_id,observed_head_sha=observed.head_sha,finalized_at=finalized_at)
            return self._receipt(admission=admission,intent=intent,observed=observed)
        self._journal.mark_reconcile_required(admission.effect_id,observed_head_sha=observed.head_sha,finalized_at=finalized_at)
        return None

    def execute(self,*,admission:RepositoryAttachAdmission,intent:ExactRefAttachIntent,
                admitted:LiveAdmittedAuthority,authority_leaf:AuthorityGrant)->RepositoryEffectReceipt|None:
        """Attempt one CAS. Trusted time is read internally; no operation caller controls currentness."""
        if type(admission) is not RepositoryAttachAdmission: raise RepositoryMutationPEPError("admission must be exact RepositoryAttachAdmission")
        admission.validate(); intent.validate()
        if admission.decision!="ALLOW": raise RepositoryMutationPEPError("denied admission cannot execute repository effect")
        if admission.intent_digest!=intent.digest(): raise RepositoryMutationPEPError("admission does not bind exact attach intent")
        state=self._journal.get(admission.effect_id); self._assert_journal_binding(state,admission,intent)
        if state.status=="RECONCILE_REQUIRED" or (state.status=="PREPARED" and state.effect_attempted_at is not None):
            finalized_at=self._trusted_now().isoformat()
            return self._reconcile_without_new_effect(admission=admission,intent=intent,finalized_at=finalized_at)
        if state.status!="PREPARED": raise RepositoryMutationPEPError("repository effect is already terminal")

        before=self._observe(intent); self._bind_expected_ref(intent,before)
        pre_now=self._trusted_now()
        current=self._live_admission.revalidate(admitted,now=pre_now)
        grant_digest,live_digest=self._bind_authority(intent=intent,admitted=current,authority_leaf=authority_leaf)
        if (current.grant_id!=admission.grant_id or current.epoch!=admission.authority_epoch or
            grant_digest!=admission.grant_digest or live_digest!=admission.live_admission_digest):
            raise RepositoryMutationPEPError("authority changed between admission and effect execution")

        self._journal.mark_attempted(admission.effect_id,attempted_at=pre_now.isoformat())

        final_now=None
        try:
            final_now=self._trusted_now()
            final=self._live_admission.revalidate(admitted,now=final_now)
            final_grant,final_live=self._bind_authority(intent=intent,admitted=final,authority_leaf=authority_leaf)
            if (final.grant_id!=admission.grant_id or final.epoch!=admission.authority_epoch or
                final_grant!=admission.grant_digest or final_live!=admission.live_admission_digest):
                raise RepositoryMutationPEPError("authority changed at final pre-effect revalidation")
        except Exception:
            stamp=(final_now or pre_now).isoformat()
            self._journal.mark_reconcile_required(admission.effect_id,observed_head_sha=None,finalized_at=stamp)
            raise

        result=None
        try:
            candidate_result=self._effect_port.compare_and_swap_fast_forward(
                repository=intent.repository,branch=intent.branch,
                expected_old_sha=intent.expected_head_sha,candidate_commit_sha=intent.candidate_commit_sha)
            if type(candidate_result) is not AttachProviderResult: raise RepositoryMutationPEPError("effect provider returned invalid result type")
            candidate_result.validate()
            if candidate_result.provider_id!=self._effect_pin.dependency_id: raise RepositoryMutationPEPError("effect provider result identity mismatch")
            result=candidate_result
        except Exception:
            result=None

        try: observed=self._observe(intent)
        except Exception:
            finalized_at=self._trusted_now().isoformat()
            self._journal.mark_reconcile_required(admission.effect_id,observed_head_sha=None,finalized_at=finalized_at); return None
        finalized_at=self._trusted_now().isoformat()
        if observed.repository==intent.repository and observed.branch==intent.branch and observed.head_sha==intent.candidate_commit_sha:
            self._journal.mark_applied(admission.effect_id,observed_head_sha=observed.head_sha,finalized_at=finalized_at)
            return self._receipt(admission=admission,intent=intent,observed=observed)
        if (result is not None and result.status=="FAILED_NO_EFFECT" and
            observed.repository==intent.repository and observed.branch==intent.branch and observed.head_sha==intent.expected_head_sha):
            self._journal.mark_failed_no_effect(admission.effect_id,observed_head_sha=observed.head_sha,finalized_at=finalized_at)
            return None
        self._journal.mark_reconcile_required(admission.effect_id,observed_head_sha=observed.head_sha,finalized_at=finalized_at)
        return None
