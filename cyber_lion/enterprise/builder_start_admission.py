"""Fail-closed, non-effectful builder start admission boundary."""
from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any, Protocol

from cyber_lion.contracts.builder_entry_permit import BUILDER_CAPABILITY_CLASS, TrustedBuilderSubject
from cyber_lion.contracts.builder_invocation_consumption import BuilderInvocationConsumptionPermit
from cyber_lion.contracts.builder_start_admission import (
    SCHEMA_VERSION,
    BuilderStartAdmission,
    compute_builder_start_admission_replay_digest,
    compute_launch_policy_digest,
    compute_process_profile_digest,
)
from cyber_lion.contracts.candidate_build_authorization import TrustedRepositoryBaseline
from cyber_lion.enterprise.builder_entry_permit import PinnedTrustedBuilderSubjectSource
from cyber_lion.enterprise.candidate_build_authorization import LiveAdmittedResourceAuthority, LiveResourceAuthorityAdmission
from cyber_lion.enterprise.persistent_authority_state import (
    PersistentAuthorityStoreOrigin,
    PersistentBuilderEntryIssuanceRecord,
    PersistentBuilderInvocationConsumptionIssuanceRecord,
    PersistentBuilderInvocationIssuanceRecord,
    PersistentBuilderStartAdmissionIssuanceRecord,
    SQLiteAuthorityStateStore,
)
from cyber_lion.enterprise.trusted_control_plane_runtime import build_authority_state_store, verify_authority_state_store_origin


class BuilderStartAdmissionError(RuntimeError):
    pass


_EFFECT_METHODS = frozenset({
    "execute", "write", "push", "merge", "deploy", "release", "create_branch", "create_pr",
    "run_test", "build_candidate", "consume_candidate", "start_builder", "spawn", "popen",
    "fork", "exec", "allocate_workspace", "issue_grant",
})


class TrustedRepositoryBaselineSource(Protocol):
    def current(self, repository: str) -> TrustedRepositoryBaseline: ...


class F005StateSource(Protocol):
    def current(self) -> Mapping[str, Any]: ...


def _canonical_store() -> tuple[SQLiteAuthorityStateStore, PersistentAuthorityStoreOrigin]:
    try:
        origin = verify_authority_state_store_origin()
        store = build_authority_state_store()
    except Exception as exc:
        raise BuilderStartAdmissionError("canonical authority persistence unavailable") from exc
    if type(origin) is not PersistentAuthorityStoreOrigin or type(store) is not SQLiteAuthorityStateStore or store.ready() is not True:
        raise BuilderStartAdmissionError("canonical authority persistence invalid")
    if store.resolve_authority_store_origin() != origin:
        raise BuilderStartAdmissionError("canonical authority persistence origin mismatch")
    return store, origin


def record_builder_invocation_consumption_issuance(permit: BuilderInvocationConsumptionPermit) -> None:
    if type(permit) is not BuilderInvocationConsumptionPermit:
        raise BuilderStartAdmissionError("exact R20 permit required")
    permit.validate()
    if not permit.invocation_consumption_permit_digest or permit.invocation_consumption_permit_digest != permit.compute_digest():
        raise BuilderStartAdmissionError("sealed R20 permit required")
    store, origin = _canonical_store()
    record = PersistentBuilderInvocationConsumptionIssuanceRecord(
        invocation_consumption_permit_id=permit.invocation_consumption_permit_id,
        invocation_consumption_permit_digest=permit.invocation_consumption_permit_digest,
        invocation_consumption_replay_digest=permit.invocation_consumption_replay_digest,
        source_builder_invocation_permit_id=permit.source_builder_invocation_permit_id,
        source_builder_invocation_permit_digest=permit.source_builder_invocation_permit_digest,
        source_builder_invocation_replay_digest=permit.source_builder_invocation_replay_digest,
        source_builder_entry_permit_id=permit.source_builder_entry_permit_id,
        source_builder_entry_permit_digest=permit.source_builder_entry_permit_digest,
        repository=permit.repository,
        baseline_master_sha=permit.baseline_master_sha,
        baseline_master_tree_sha=permit.baseline_master_tree_sha,
        current_baseline_digest=permit.current_baseline_digest,
        action=permit.action,
        candidate_scope=permit.candidate_scope,
        resource_scope=permit.resource_scope,
        authority_epoch=permit.authority_epoch,
        authority_state_version=permit.authority_state_version,
        root_grant_id=permit.root_grant_id,
        root_grant_digest=permit.root_grant_digest,
        current_authority_digest=permit.current_authority_digest,
        builder_subject_id=permit.builder_subject_id,
        builder_instance_id=permit.builder_instance_id,
        builder_capability_class=permit.builder_capability_class,
        builder_identity_digest=permit.builder_identity_digest,
        builder_implementation_digest=permit.builder_implementation_digest,
        builder_attestation_digest=permit.builder_attestation_digest,
        current_builder_subject_digest=permit.current_builder_subject_digest,
        authority_store_origin_id=origin.origin_id,
        authority_store_origin_digest=origin.origin_digest,
        issued_at=permit.checked_at,
    ).validate()
    store.record_builder_invocation_consumption_issuance(record)


def resolve_builder_start_admission_issuance(admission_id: str) -> PersistentBuilderStartAdmissionIssuanceRecord:
    store, _ = _canonical_store()
    return store.resolve_builder_start_admission_issuance(admission_id)


def _sealed_r20(value: object) -> BuilderInvocationConsumptionPermit:
    if type(value) is not BuilderInvocationConsumptionPermit:
        raise BuilderStartAdmissionError("exact BuilderInvocationConsumptionPermit required")
    try:
        value.validate()
    except Exception as exc:
        raise BuilderStartAdmissionError("R20 source permit invalid") from exc
    if not value.invocation_consumption_permit_digest or value.invocation_consumption_permit_digest != value.compute_digest():
        raise BuilderStartAdmissionError("R20 source permit must be sealed")
    if value.state != "BUILDER_INVOCATION_CONSUMPTION_PERMIT_ISSUED":
        raise BuilderStartAdmissionError("R20 source state invalid")
    if (value.authority_effect, value.execution_effect, value.repository_ref_effect, value.external_effect) != ("NONE", "NONE", "NONE", "NONE"):
        raise BuilderStartAdmissionError("R20 source carries effects")
    return value


def _sealed_subject(value: object) -> TrustedBuilderSubject:
    if type(value) is not TrustedBuilderSubject:
        raise BuilderStartAdmissionError("exact TrustedBuilderSubject required")
    value.validate()
    if not value.subject_digest or value.subject_digest != value.compute_digest():
        raise BuilderStartAdmissionError("trusted builder subject must be sealed")
    return value


def _utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise BuilderStartAdmissionError("builder validity timestamp must be timezone-aware")
    return parsed.astimezone(timezone.utc)


def _f005_ok(value: Mapping[str, Any]) -> None:
    if not isinstance(value, Mapping) or (
        value.get("state"), value.get("effect_authority"), value.get("resume_policy")
    ) != ("QUARANTINED", "DENY", "REATTEST_NEW_EPOCH_ONLY"):
        raise BuilderStartAdmissionError("F005 quarantine invariant failed")


def _exact_r20_record(permit: BuilderInvocationConsumptionPermit, record: PersistentBuilderInvocationConsumptionIssuanceRecord) -> None:
    expected = (
        permit.invocation_consumption_permit_id, permit.invocation_consumption_permit_digest,
        permit.invocation_consumption_replay_digest, permit.source_builder_invocation_permit_id,
        permit.source_builder_invocation_permit_digest, permit.source_builder_invocation_replay_digest,
        permit.source_builder_entry_permit_id, permit.source_builder_entry_permit_digest,
        permit.repository, permit.baseline_master_sha, permit.baseline_master_tree_sha, permit.current_baseline_digest,
        permit.action, permit.candidate_scope, permit.resource_scope, permit.authority_epoch, permit.authority_state_version,
        permit.root_grant_id, permit.root_grant_digest, permit.current_authority_digest, permit.builder_subject_id,
        permit.builder_instance_id, permit.builder_capability_class, permit.builder_identity_digest,
        permit.builder_implementation_digest, permit.builder_attestation_digest, permit.current_builder_subject_digest,
        permit.checked_at,
    )
    actual = (
        record.invocation_consumption_permit_id, record.invocation_consumption_permit_digest,
        record.invocation_consumption_replay_digest, record.source_builder_invocation_permit_id,
        record.source_builder_invocation_permit_digest, record.source_builder_invocation_replay_digest,
        record.source_builder_entry_permit_id, record.source_builder_entry_permit_digest,
        record.repository, record.baseline_master_sha, record.baseline_master_tree_sha, record.current_baseline_digest,
        record.action, record.candidate_scope, record.resource_scope, record.authority_epoch, record.authority_state_version,
        record.root_grant_id, record.root_grant_digest, record.current_authority_digest, record.builder_subject_id,
        record.builder_instance_id, record.builder_capability_class, record.builder_identity_digest,
        record.builder_implementation_digest, record.builder_attestation_digest, record.current_builder_subject_digest,
        record.issued_at,
    )
    if actual != expected:
        raise BuilderStartAdmissionError("R20 durable artifact provenance mismatch")


class BuilderStartAdmissionEngine:
    REPLAY_DOMAIN = "builder-start-admission"

    def __init__(self, *, live_authority: LiveResourceAuthorityAdmission, baseline_source: TrustedRepositoryBaselineSource,
                 f005_state_source: F005StateSource, builder_source: PinnedTrustedBuilderSubjectSource) -> None:
        if type(live_authority) is not LiveResourceAuthorityAdmission:
            raise BuilderStartAdmissionError("live authority admission required")
        if type(builder_source) is not PinnedTrustedBuilderSubjectSource:
            raise BuilderStartAdmissionError("exact pinned builder source required")
        builder_source.verify_origin()
        for obj, method in ((baseline_source, "current"), (f005_state_source, "current")):
            if not callable(getattr(obj, method, None)):
                raise BuilderStartAdmissionError("R21 dependency unavailable")
        self._live = live_authority; self._baseline = baseline_source; self._f005 = f005_state_source; self._builders = builder_source
        self._store, self._origin = _canonical_store()

    def issue_admission(self, *, source_permit: BuilderInvocationConsumptionPermit,
                        admitted_authority: LiveAdmittedResourceAuthority, trusted_now: datetime) -> BuilderStartAdmission:
        permit = _sealed_r20(source_permit)
        if type(admitted_authority) is not LiveAdmittedResourceAuthority:
            raise BuilderStartAdmissionError("exact live authority receipt required")
        admitted_authority.validate()
        if not isinstance(trusted_now, datetime) or trusted_now.tzinfo is None:
            raise BuilderStartAdmissionError("trusted_now must be timezone-aware")
        now = trusted_now.astimezone(timezone.utc)
        origin = verify_authority_state_store_origin()
        if origin != self._origin:
            raise BuilderStartAdmissionError("canonical origin drift")
        r20 = self._store.resolve_builder_invocation_consumption_issuance(permit.invocation_consumption_permit_id)
        if type(r20) is not PersistentBuilderInvocationConsumptionIssuanceRecord:
            raise BuilderStartAdmissionError("exact durable R20 issuance required")
        r20.validate(); _exact_r20_record(permit, r20)
        r19 = self._store.resolve_builder_invocation_issuance(permit.source_builder_invocation_permit_id)
        if type(r19) is not PersistentBuilderInvocationIssuanceRecord:
            raise BuilderStartAdmissionError("exact durable R19 ancestor required")
        r19.validate()
        if (permit.source_builder_invocation_permit_id, permit.source_builder_invocation_permit_digest, permit.source_builder_invocation_replay_digest) != (
            r19.builder_invocation_permit_id, r19.builder_invocation_permit_digest, r19.builder_invocation_replay_digest):
            raise BuilderStartAdmissionError("R20/R19 ancestry mismatch")
        r17 = self._store.resolve_builder_entry_issuance(r19.source_builder_entry_permit_id)
        if type(r17) is not PersistentBuilderEntryIssuanceRecord:
            raise BuilderStartAdmissionError("exact durable R17 ancestor required")
        r17.validate()
        if (permit.source_builder_entry_permit_id, permit.source_builder_entry_permit_digest,
            r19.source_builder_entry_permit_id, r19.source_builder_entry_permit_digest) != (
            r17.builder_entry_permit_id, r17.builder_entry_permit_digest,
            r17.builder_entry_permit_id, r17.builder_entry_permit_digest):
            raise BuilderStartAdmissionError("R19/R17 ancestry mismatch")
        if (r20.authority_store_origin_id, r20.authority_store_origin_digest,
            r19.authority_store_origin_id, r19.authority_store_origin_digest,
            r17.authority_store_origin_id, r17.authority_store_origin_digest) != (
            origin.origin_id, origin.origin_digest, origin.origin_id, origin.origin_digest, origin.origin_id, origin.origin_digest):
            raise BuilderStartAdmissionError("transitive provenance origin mismatch")
        current = self._baseline.current(permit.repository)
        if type(current) is not TrustedRepositoryBaseline:
            raise BuilderStartAdmissionError("trusted baseline type invalid")
        current.validate()
        if (current.repository, current.master_sha, current.master_tree_sha, current.digest()) != (
            permit.repository, permit.baseline_master_sha, permit.baseline_master_tree_sha, permit.current_baseline_digest):
            raise BuilderStartAdmissionError("R21 baseline stale")
        try:
            authority = self._live.revalidate(admitted_authority, now=now)
        except Exception as exc:
            raise BuilderStartAdmissionError("R21 authority currentness failed") from exc
        authority.validate()
        if (authority.repository, authority.epoch, authority.epoch_state_version, authority.root_grant_id,
            authority.root_grant_digest, authority.digest(), authority.resource_scope, authority.action) != (
            permit.repository, permit.authority_epoch, permit.authority_state_version, permit.root_grant_id,
            permit.root_grant_digest, permit.current_authority_digest, permit.resource_scope, "BUILD_CANDIDATE"):
            raise BuilderStartAdmissionError("R21 authority mismatch")
        self._builders.verify_origin()
        subject = _sealed_subject(self._builders.resolve_exact(
            builder_subject_id=permit.builder_subject_id, builder_instance_id=permit.builder_instance_id,
            repository=permit.repository, candidate_scope=permit.candidate_scope, resource_scope=permit.resource_scope))
        if (subject.builder_subject_id, subject.builder_instance_id, subject.capability_class,
            subject.identity_digest, subject.implementation_digest, subject.attestation_digest, subject.subject_digest,
            subject.repository, subject.candidate_scope, subject.resource_scope, subject.state, subject.source_kind) != (
            permit.builder_subject_id, permit.builder_instance_id, permit.builder_capability_class,
            permit.builder_identity_digest, permit.builder_implementation_digest, permit.builder_attestation_digest,
            permit.current_builder_subject_digest, permit.repository, permit.candidate_scope, permit.resource_scope,
            "ADMITTED", "trusted-control-plane"):
            raise BuilderStartAdmissionError("R21 builder currentness mismatch")
        if now < _utc(subject.valid_from) or now >= _utc(subject.expires_at):
            raise BuilderStartAdmissionError("builder outside validity window")
        profile_kwargs = dict(
            repository=permit.repository, action="BUILD_CANDIDATE", candidate_scope=permit.candidate_scope,
            resource_scope=permit.resource_scope, builder_subject_id=subject.builder_subject_id,
            builder_instance_id=subject.builder_instance_id, builder_capability_class=subject.capability_class,
            builder_identity_digest=subject.identity_digest, builder_implementation_digest=subject.implementation_digest,
            builder_attestation_digest=subject.attestation_digest, current_builder_subject_digest=subject.subject_digest)
        process_profile_digest = compute_process_profile_digest(**profile_kwargs)
        process_profile_id = f"bpp:{process_profile_digest}"
        launch_policy_digest = compute_launch_policy_digest()
        _f005_ok(self._f005.current())
        kwargs = dict(
            source_invocation_consumption_permit_id=permit.invocation_consumption_permit_id,
            source_invocation_consumption_permit_digest=permit.invocation_consumption_permit_digest,
            source_invocation_consumption_replay_digest=permit.invocation_consumption_replay_digest,
            source_builder_invocation_permit_id=permit.source_builder_invocation_permit_id,
            source_builder_invocation_permit_digest=permit.source_builder_invocation_permit_digest,
            source_builder_entry_permit_id=permit.source_builder_entry_permit_id,
            source_builder_entry_permit_digest=permit.source_builder_entry_permit_digest,
            repository=permit.repository, baseline_master_sha=permit.baseline_master_sha,
            baseline_master_tree_sha=permit.baseline_master_tree_sha, current_baseline_digest=current.digest(),
            action="BUILD_CANDIDATE", candidate_scope=permit.candidate_scope, resource_scope=permit.resource_scope,
            authority_epoch=permit.authority_epoch, authority_state_version=permit.authority_state_version,
            root_grant_id=permit.root_grant_id, root_grant_digest=permit.root_grant_digest,
            current_authority_digest=authority.digest(), builder_subject_id=subject.builder_subject_id,
            builder_instance_id=subject.builder_instance_id, builder_capability_class=subject.capability_class,
            builder_identity_digest=subject.identity_digest, builder_implementation_digest=subject.implementation_digest,
            builder_attestation_digest=subject.attestation_digest, current_builder_subject_digest=subject.subject_digest,
            process_profile_id=process_profile_id, process_profile_digest=process_profile_digest,
            launch_policy_digest=launch_policy_digest)
        replay = compute_builder_start_admission_replay_digest(**kwargs)
        checked_at = now.isoformat()
        if self._store.consume_replay(self.REPLAY_DOMAIN, replay, checked_at) is not True:
            raise BuilderStartAdmissionError("builder start admission replay denied")
        admission = BuilderStartAdmission(
            schema_version=SCHEMA_VERSION, builder_start_admission_id=f"bsa:{replay}",
            builder_start_admission_replay_digest=replay, checked_at=checked_at, **kwargs).sealed()
        current_origin = verify_authority_state_store_origin()
        if current_origin != origin:
            raise BuilderStartAdmissionError("canonical origin drift before R21 durable issuance")
        record = PersistentBuilderStartAdmissionIssuanceRecord(
            builder_start_admission_id=admission.builder_start_admission_id,
            builder_start_admission_digest=admission.builder_start_admission_digest,
            builder_start_admission_replay_digest=admission.builder_start_admission_replay_digest,
            source_invocation_consumption_permit_id=admission.source_invocation_consumption_permit_id,
            source_invocation_consumption_permit_digest=admission.source_invocation_consumption_permit_digest,
            source_invocation_consumption_replay_digest=admission.source_invocation_consumption_replay_digest,
            source_builder_invocation_permit_id=admission.source_builder_invocation_permit_id,
            source_builder_invocation_permit_digest=admission.source_builder_invocation_permit_digest,
            source_builder_entry_permit_id=admission.source_builder_entry_permit_id,
            source_builder_entry_permit_digest=admission.source_builder_entry_permit_digest,
            repository=admission.repository, baseline_master_sha=admission.baseline_master_sha,
            baseline_master_tree_sha=admission.baseline_master_tree_sha, current_baseline_digest=admission.current_baseline_digest,
            action=admission.action, candidate_scope=admission.candidate_scope, resource_scope=admission.resource_scope,
            authority_epoch=admission.authority_epoch, authority_state_version=admission.authority_state_version,
            root_grant_id=admission.root_grant_id, root_grant_digest=admission.root_grant_digest,
            current_authority_digest=admission.current_authority_digest, builder_subject_id=admission.builder_subject_id,
            builder_instance_id=admission.builder_instance_id, builder_capability_class=admission.builder_capability_class,
            builder_identity_digest=admission.builder_identity_digest, builder_implementation_digest=admission.builder_implementation_digest,
            builder_attestation_digest=admission.builder_attestation_digest, current_builder_subject_digest=admission.current_builder_subject_digest,
            process_profile_id=admission.process_profile_id, process_profile_digest=admission.process_profile_digest,
            launch_policy_digest=admission.launch_policy_digest, authority_store_origin_id=current_origin.origin_id,
            authority_store_origin_digest=current_origin.origin_digest, issued_at=admission.checked_at).validate()
        try:
            self._store.record_builder_start_admission_issuance(record)
        except Exception as exc:
            raise BuilderStartAdmissionError("durable R21 issuance failed closed") from exc
        return admission

    @classmethod
    def assert_no_effect_surface(cls) -> None:
        for name in _EFFECT_METHODS:
            if hasattr(cls, name):
                raise BuilderStartAdmissionError(f"effect surface present: {name}")
