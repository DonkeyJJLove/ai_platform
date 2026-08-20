"""Post-execution bridge from immutable runtime evidence to current live authority."""
from __future__ import annotations

from datetime import datetime

from cyber_lion.contracts.runtime_authority_binding import (
    AuthorityAttestationBinding,
    AuthorityBoundRuntimeEvidence,
    RuntimeAuthorityBindingError,
    RuntimeEvidenceReference,
)
from .authority_source import AuthorityLookupKey
from .live_authority_admission import LiveAdmittedAuthority, LiveAuthorityAdmission, LiveAuthorityAdmissionError


class RuntimeAuthorityBridgeError(RuntimeAuthorityBindingError):
    """Raised when runtime evidence cannot be bound to current authority safely."""


class RuntimeAuthorityBridge:
    """Bind runtime evidence only through a linearized LiveAuthorityAdmission boundary."""

    def __init__(
        self,
        *,
        live_admission: LiveAuthorityAdmission,
        repository: str,
        pr_number: int,
        base_sha: str,
        head_sha: str,
        mission_id: str,
    ) -> None:
        if type(live_admission) is not LiveAuthorityAdmission:
            raise RuntimeAuthorityBridgeError("live_admission must be exact LiveAuthorityAdmission")
        self._live_admission = live_admission
        self._repository = repository
        self._pr_number = pr_number
        self._base_sha = base_sha
        self._head_sha = head_sha
        self._mission_id = mission_id
        AuthorityLookupKey(
            repository=repository,
            pr_number=pr_number,
            base_sha=base_sha,
            head_sha=head_sha,
            mission_id=mission_id,
            grant_id="validation-placeholder",
        ).validate()
        if live_admission.context.mission_id != mission_id:
            raise RuntimeAuthorityBridgeError("live admission context mismatch")

    def bind(
        self,
        runtime: RuntimeEvidenceReference,
        *,
        grant_id: str,
        admission_nonce: str,
        binding_nonce: str,
        now: datetime,
    ) -> AuthorityBoundRuntimeEvidence:
        if not isinstance(runtime, RuntimeEvidenceReference):
            raise RuntimeAuthorityBridgeError("runtime evidence reference is required")
        runtime.validate()
        if (
            runtime.repository != self._repository
            or runtime.base_sha != self._base_sha
            or runtime.head_sha != self._head_sha
            or runtime.mission_id != self._mission_id
        ):
            raise RuntimeAuthorityBridgeError("runtime evidence does not match bridge context")
        if not isinstance(grant_id, str) or not grant_id.strip():
            raise RuntimeAuthorityBridgeError("grant_id is required")
        if not isinstance(admission_nonce, str) or not admission_nonce.strip():
            raise RuntimeAuthorityBridgeError("admission_nonce is required")
        if not isinstance(binding_nonce, str) or not binding_nonce.strip():
            raise RuntimeAuthorityBridgeError("binding_nonce is required")
        if not isinstance(now, datetime) or now.tzinfo is None:
            raise RuntimeAuthorityBridgeError("trusted now must be timezone-aware")

        try:
            admitted = self._live_admission.admit(
                repository=self._repository,
                pr_number=self._pr_number,
                base_sha=self._base_sha,
                head_sha=self._head_sha,
                mission_id=self._mission_id,
                grant_id=grant_id,
                now=now,
                replay_nonce=admission_nonce,
            )
            finalized = self._live_admission.finalize_binding(
                admitted,
                runtime_evidence_digest=runtime.runtime_evidence_digest,
                binding_nonce=binding_nonce,
                now=now,
            )
        except LiveAuthorityAdmissionError as exc:
            raise RuntimeAuthorityBridgeError("live authority admission/finalization failed closed") from exc
        if type(admitted) is not LiveAdmittedAuthority:
            raise RuntimeAuthorityBridgeError("live authority admission result is invalid")
        admitted.validate()
        finalized.validate()
        if finalized.live_admission_digest != admitted.digest():
            raise RuntimeAuthorityBridgeError("binding finalization is not bound to live admission")
        if finalized.runtime_evidence_digest != runtime.runtime_evidence_digest:
            raise RuntimeAuthorityBridgeError("binding finalization is not bound to runtime evidence")
        if finalized.binding_nonce != binding_nonce:
            raise RuntimeAuthorityBridgeError("binding finalization nonce mismatch")
        if (
            finalized.epoch != admitted.epoch
            or finalized.authority_state_version != admitted.epoch_state_version
            or finalized.grant_id != admitted.grant_id
            or finalized.root_grant_id != admitted.root_grant_id
            or finalized.root_grant_digest != admitted.root_grant_digest
        ):
            raise RuntimeAuthorityBridgeError("binding finalization authority state mismatch")

        binding = AuthorityAttestationBinding(
            schema_version="1.2.0",
            binding_id=f"runtime-authority:{runtime.runtime_evidence_digest}:{admitted.digest()}:{finalized.digest()}",
            binding_nonce=binding_nonce,
            mission_id=self._mission_id,
            repository=self._repository,
            pr_number=self._pr_number,
            base_sha=self._base_sha,
            head_sha=self._head_sha,
            runtime_evidence_digest=runtime.runtime_evidence_digest,
            runtime_instance_id=runtime.runtime_instance_id,
            run_id=runtime.run_id,
            run_attempt=runtime.run_attempt,
            provenance_ref=runtime.provenance_ref,
            artifact_digest=runtime.artifact_digest,
            grant_id=admitted.grant_id,
            authority_lineage_digest=admitted.lineage_digest,
            authenticated_grant_digest=admitted.leaf_grant_digest,
            authority_epoch=admitted.epoch,
            authority_provenance_id=admitted.provenance_id,
            authority_key_id=admitted.leaf_key_id,
            authority_algorithm=admitted.leaf_algorithm,
            live_admission_digest=admitted.digest(),
            live_admission_replay_digest=admitted.replay_digest,
            authority_state_version=admitted.epoch_state_version,
            authority_root_grant_digest=admitted.root_grant_digest,
            authority_admitted_at=admitted.admitted_at,
            live_finalization_digest=finalized.digest(),
            live_finalization_key_digest=finalized.finalization_key_digest,
            authority_finalized_at=finalized.finalized_at,
        ).validate()

        return AuthorityBoundRuntimeEvidence(
            runtime_evidence_digest=runtime.runtime_evidence_digest,
            runtime_instance_id=runtime.runtime_instance_id,
            provenance_ref=runtime.provenance_ref,
            artifact_digest=runtime.artifact_digest,
            mission_id=self._mission_id,
            repository=self._repository,
            base_sha=self._base_sha,
            head_sha=self._head_sha,
            grant_id=admitted.grant_id,
            authority_lineage_digest=admitted.lineage_digest,
            authenticated_grant_digest=admitted.leaf_grant_digest,
            authority_epoch=admitted.epoch,
            authority_provenance_id=admitted.provenance_id,
            authority_ceiling=admitted.authority_ceiling,
            live_admission_digest=admitted.digest(),
            live_admission_replay_digest=admitted.replay_digest,
            authority_state_version=admitted.epoch_state_version,
            authority_root_grant_digest=admitted.root_grant_digest,
            authority_admitted_at=admitted.admitted_at,
            live_finalization_digest=finalized.digest(),
            live_finalization_key_digest=finalized.finalization_key_digest,
            authority_finalized_at=finalized.finalized_at,
            binding_digest=binding.digest(),
        ).validate()


def verify_authority_bound_n2_pair(
    first: AuthorityBoundRuntimeEvidence,
    second: AuthorityBoundRuntimeEvidence,
) -> tuple[AuthorityBoundRuntimeEvidence, AuthorityBoundRuntimeEvidence]:
    """Validate two distinct runtime records under one compatible live authority root."""
    if not isinstance(first, AuthorityBoundRuntimeEvidence) or not isinstance(second, AuthorityBoundRuntimeEvidence):
        raise RuntimeAuthorityBridgeError("N2 pair requires authority-bound runtime evidence")
    first.validate()
    second.validate()
    common_first = (
        first.mission_id,
        first.repository,
        first.base_sha,
        first.head_sha,
        first.grant_id,
        first.authority_lineage_digest,
        first.authenticated_grant_digest,
        first.authority_epoch,
        first.authority_provenance_id,
        first.authority_ceiling,
        first.authority_state_version,
        first.authority_root_grant_digest,
    )
    common_second = (
        second.mission_id,
        second.repository,
        second.base_sha,
        second.head_sha,
        second.grant_id,
        second.authority_lineage_digest,
        second.authenticated_grant_digest,
        second.authority_epoch,
        second.authority_provenance_id,
        second.authority_ceiling,
        second.authority_state_version,
        second.authority_root_grant_digest,
    )
    if common_first != common_second:
        raise RuntimeAuthorityBridgeError("N2 runtime evidence does not share one live authority root")
    if first.runtime_instance_id == second.runtime_instance_id:
        raise RuntimeAuthorityBridgeError("one runtime instance cannot satisfy authority-bound N2")
    if first.runtime_evidence_digest == second.runtime_evidence_digest:
        raise RuntimeAuthorityBridgeError("duplicate runtime evidence cannot satisfy authority-bound N2")
    if first.provenance_ref == second.provenance_ref:
        raise RuntimeAuthorityBridgeError("duplicate provenance cannot satisfy authority-bound N2")
    if first.live_admission_digest == second.live_admission_digest:
        raise RuntimeAuthorityBridgeError("duplicate live admission receipt cannot satisfy N2")
    if first.live_admission_replay_digest == second.live_admission_replay_digest:
        raise RuntimeAuthorityBridgeError("duplicate live admission replay receipt cannot satisfy N2")
    if first.live_finalization_digest == second.live_finalization_digest:
        raise RuntimeAuthorityBridgeError("duplicate live finalization receipt cannot satisfy N2")
    if first.live_finalization_key_digest == second.live_finalization_key_digest:
        raise RuntimeAuthorityBridgeError("duplicate live finalization key cannot satisfy N2")
    if first.binding_digest == second.binding_digest:
        raise RuntimeAuthorityBridgeError("duplicate authority binding cannot satisfy N2")
    return (first, second)
