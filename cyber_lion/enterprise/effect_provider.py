"""Adapters from existing governed effect-specific paths to generic EffectContract.

These adapters are intentionally inert. They normalize already-admitted effect intent
and evidence; they do not execute, attach, launch, authorize, observe, or reconcile.
"""
from __future__ import annotations

from cyber_lion.contracts.effect import EffectContract,EffectContractError
from cyber_lion.contracts.repository_mutation import ExactRefAttachIntent
from cyber_lion.contracts.runtime_enforcement import RequestedRuntimeEffect,RuntimeAdmission


class EffectProviderAdapterError(RuntimeError):
    pass


def _require_observers(observer_ids:tuple[str,...],channels:tuple[str,...])->None:
    if type(observer_ids) is not tuple or not observer_ids or len(set(observer_ids))!=len(observer_ids):
        raise EffectProviderAdapterError("independent observer identities are required")
    if type(channels) is not tuple or not channels or len(set(channels))!=len(channels):
        raise EffectProviderAdapterError("observation channels are required")


class RepositoryMutationEffectAdapter:
    provider_class="repository_mutation_pep"

    def normalize(
        self,
        *,
        intent:ExactRefAttachIntent,
        requested_authority:str,
        authority_evidence_digest:str,
        currentness_evidence_digest:str,
        pep_identity_digest:str,
        execution_identity_digest:str,
        required_observer_ids:tuple[str,...],
        required_observation_channels:tuple[str,...],
    )->EffectContract:
        try:intent.validate()
        except Exception as exc:raise EffectProviderAdapterError("exact repository attach intent required") from exc
        _require_observers(required_observer_ids,required_observation_channels)
        return EffectContract(
            effect_id=f"effect:repository:{intent.digest()}",
            effect_class="repository.fast_forward_ref",
            mission_id=intent.mission_id,
            provider_class=self.provider_class,
            exact_effect_digest=intent.digest(),
            requested_authority=requested_authority,
            authority_evidence_digest=authority_evidence_digest,
            currentness_evidence_digest=currentness_evidence_digest,
            pep_identity_digest=pep_identity_digest,
            execution_identity_digest=execution_identity_digest,
            target=f"repo:{intent.repository}:{intent.branch}",
            payload_digest=intent.candidate_verification_digest,
            required_observer_ids=required_observer_ids,
            required_observation_channels=required_observation_channels,
            reconciliation_required=True,
        ).validate()


class F009RuntimeEffectAdapter:
    provider_class="f009_runtime_admission"

    def normalize(
        self,
        *,
        effect:RequestedRuntimeEffect,
        admission:RuntimeAdmission,
        currentness_evidence_digest:str,
        pep_identity_digest:str,
        required_observer_ids:tuple[str,...],
        required_observation_channels:tuple[str,...],
    )->EffectContract:
        try:
            effect.validate();admission.validate()
        except Exception as exc:raise EffectProviderAdapterError("valid F009 effect/admission required") from exc
        _require_observers(required_observer_ids,required_observation_channels)
        if admission.requested_effect_digest!=effect.digest():raise EffectProviderAdapterError("runtime effect substitution detected")
        if admission.proposal_id!=effect.proposal_id:raise EffectProviderAdapterError("proposal substitution detected")
        if admission.authority_lineage_digest!=effect.authority_lineage_digest:raise EffectProviderAdapterError("authority lineage substitution detected")
        if admission.runtime_identity_digest!=effect.runtime_identity_digest:raise EffectProviderAdapterError("execution identity substitution detected")
        if admission.effective_authority!=effect.requested_authority:raise EffectProviderAdapterError("authority class substitution detected")
        if admission.observability_state!=effect.observability_state:raise EffectProviderAdapterError("observability substitution detected")
        return EffectContract(
            effect_id=f"effect:runtime:{effect.digest()}",
            effect_class=f"runtime.{effect.action_class}",
            mission_id=effect.mission_id,
            provider_class=self.provider_class,
            exact_effect_digest=effect.digest(),
            requested_authority=admission.effective_authority,
            authority_evidence_digest=admission.live_authority_digest,
            currentness_evidence_digest=currentness_evidence_digest,
            pep_identity_digest=pep_identity_digest,
            execution_identity_digest=admission.runtime_identity_digest,
            target=effect.resource,
            payload_digest=effect.payload_digest,
            required_observer_ids=required_observer_ids,
            required_observation_channels=required_observation_channels,
            reconciliation_required=True,
        ).validate()
