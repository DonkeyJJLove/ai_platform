"""Fail-closed prepare/commit boundary for the first real builder process-start effect.

The module deliberately contains no subprocess/fork/exec implementation. A runtime provider
must be supplied by the trusted runtime composition and must match a descriptor resolved from
the trusted control plane. Tests use effect-free fakes; production providers are separate.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from typing import Mapping, Protocol, Any

from cyber_lion.contracts.builder_process_launch import (
    BuilderProcessIdentity,
    BuilderProcessLaunchRequest,
    BuilderProcessLaunchReceipt,
    BuilderProcessRuntimeProviderDescriptor,
    EFFECT_CLASS,
    HELD_STATE,
    STARTED_STATE,
    compute_launch_replay_digest,
)
from cyber_lion.contracts.builder_start_admission import BuilderStartAdmission, compute_launch_policy_digest, compute_process_profile_digest
from cyber_lion.contracts.candidate_build_authorization import TrustedRepositoryBaseline
from cyber_lion.contracts.builder_entry_permit import TrustedBuilderSubject
from cyber_lion.enterprise.builder_entry_permit import PinnedTrustedBuilderSubjectSource
from cyber_lion.enterprise.builder_start_admission import resolve_builder_start_admission_issuance
from cyber_lion.enterprise.candidate_build_authorization import LiveAdmittedResourceAuthority, LiveResourceAuthorityAdmission
from cyber_lion.enterprise.persistent_authority_state import (
    DurableReplayGuard,
    PersistentBuilderProcessLaunchIntent,
    PersistentBuilderProcessLaunchReceipt,
    PersistentBuilderStartAdmissionIssuanceRecord,
    SQLiteAuthorityStateStore,
)
from cyber_lion.enterprise.trusted_control_plane_runtime import build_authority_state_store, verify_authority_state_store_origin


class BuilderProcessLaunchError(RuntimeError):
    pass


class TrustedRepositoryBaselineSource(Protocol):
    def current(self, repository: str) -> TrustedRepositoryBaseline: ...


class F005StateSource(Protocol):
    def current(self) -> Mapping[str, Any]: ...


class BuilderProcessRuntimeProviderSource(Protocol):
    def resolve_exact(self, *, provider_id: str, process_profile_digest: str, launch_policy_digest: str) -> BuilderProcessRuntimeProviderDescriptor: ...


class BuilderProcessRuntimeProvider(Protocol):
    @property
    def descriptor(self) -> BuilderProcessRuntimeProviderDescriptor: ...
    def prepare_launch(self, request: BuilderProcessLaunchRequest) -> BuilderProcessIdentity: ...
    def commit_start(self, request: BuilderProcessLaunchRequest, held: BuilderProcessIdentity) -> BuilderProcessIdentity: ...
    def observe_launch(self, launch_id: str) -> BuilderProcessIdentity: ...
    def freeze_or_kill(self, launch_id: str) -> None: ...


R21_ISSUANCE_RECORD_DOMAIN = b"LION/E004-BUILDER-START-ADMISSION-ISSUANCE-RECORD/1\0"


def _utc_text(value: datetime) -> str:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise BuilderProcessLaunchError("trusted time must be timezone-aware")
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _sealed_r21(value: object) -> BuilderStartAdmission:
    if type(value) is not BuilderStartAdmission:
        raise BuilderProcessLaunchError("exact BuilderStartAdmission required")
    value.validate()
    if not value.builder_start_admission_digest or value.builder_start_admission_digest != value.compute_digest():
        raise BuilderProcessLaunchError("sealed R21 admission required")
    if (value.authority_effect, value.execution_effect, value.repository_ref_effect, value.external_effect) != ("NONE", "NONE", "NONE", "NONE"):
        raise BuilderProcessLaunchError("R21 source carries effects")
    return value


def _sealed_subject(value: object) -> TrustedBuilderSubject:
    if type(value) is not TrustedBuilderSubject:
        raise BuilderProcessLaunchError("exact trusted builder subject required")
    value.validate()
    if not value.subject_digest or value.subject_digest != value.compute_digest():
        raise BuilderProcessLaunchError("sealed builder subject required")
    return value


def _f005_ok(value: Mapping[str, Any]) -> None:
    if not isinstance(value, Mapping) or (value.get("state"), value.get("effect_authority"), value.get("resume_policy")) != (
        "QUARANTINED", "DENY", "REATTEST_NEW_EPOCH_ONLY"
    ):
        raise BuilderProcessLaunchError("F005 quarantine sentinel failed")


def _r21_record_digest(record: PersistentBuilderStartAdmissionIssuanceRecord) -> str:
    record.validate()
    return sha256(R21_ISSUANCE_RECORD_DOMAIN + record.canonical_json().encode("utf-8")).hexdigest()


def _exact_r21_record(admission: BuilderStartAdmission, record: PersistentBuilderStartAdmissionIssuanceRecord) -> None:
    expected = (
        admission.builder_start_admission_id, admission.builder_start_admission_digest,
        admission.builder_start_admission_replay_digest, admission.source_invocation_consumption_permit_id,
        admission.source_invocation_consumption_permit_digest, admission.source_invocation_consumption_replay_digest,
        admission.source_builder_invocation_permit_id, admission.source_builder_invocation_permit_digest,
        admission.source_builder_entry_permit_id, admission.source_builder_entry_permit_digest,
        admission.repository, admission.baseline_master_sha, admission.baseline_master_tree_sha,
        admission.current_baseline_digest, admission.action, admission.candidate_scope, admission.resource_scope,
        admission.authority_epoch, admission.authority_state_version, admission.root_grant_id,
        admission.root_grant_digest, admission.current_authority_digest, admission.builder_subject_id,
        admission.builder_instance_id, admission.builder_capability_class, admission.builder_identity_digest,
        admission.builder_implementation_digest, admission.builder_attestation_digest,
        admission.current_builder_subject_digest, admission.process_profile_id, admission.process_profile_digest,
        admission.launch_policy_digest, admission.checked_at,
    )
    actual = (
        record.builder_start_admission_id, record.builder_start_admission_digest,
        record.builder_start_admission_replay_digest, record.source_invocation_consumption_permit_id,
        record.source_invocation_consumption_permit_digest, record.source_invocation_consumption_replay_digest,
        record.source_builder_invocation_permit_id, record.source_builder_invocation_permit_digest,
        record.source_builder_entry_permit_id, record.source_builder_entry_permit_digest,
        record.repository, record.baseline_master_sha, record.baseline_master_tree_sha,
        record.current_baseline_digest, record.action, record.candidate_scope, record.resource_scope,
        record.authority_epoch, record.authority_state_version, record.root_grant_id,
        record.root_grant_digest, record.current_authority_digest, record.builder_subject_id,
        record.builder_instance_id, record.builder_capability_class, record.builder_identity_digest,
        record.builder_implementation_digest, record.builder_attestation_digest,
        record.current_builder_subject_digest, record.process_profile_id, record.process_profile_digest,
        record.launch_policy_digest, record.issued_at,
    )
    if actual != expected:
        raise BuilderProcessLaunchError("R21 durable artifact provenance mismatch")


class BuilderProcessLaunchBoundary:
    REPLAY_DOMAIN = "builder-process-launch"

    def __init__(self, *, live_authority: LiveResourceAuthorityAdmission,
                 baseline_source: TrustedRepositoryBaselineSource,
                 f005_state_source: F005StateSource,
                 builder_source: PinnedTrustedBuilderSubjectSource,
                 provider_source: BuilderProcessRuntimeProviderSource) -> None:
        if type(live_authority) is not LiveResourceAuthorityAdmission:
            raise BuilderProcessLaunchError("live authority admission required")
        if type(builder_source) is not PinnedTrustedBuilderSubjectSource:
            raise BuilderProcessLaunchError("exact pinned builder source required")
        for obj, method in ((baseline_source, "current"), (f005_state_source, "current"), (provider_source, "resolve_exact")):
            if not callable(getattr(obj, method, None)):
                raise BuilderProcessLaunchError("R22 dependency unavailable")
        builder_source.verify_origin()
        self._live = live_authority
        self._baseline = baseline_source
        self._f005 = f005_state_source
        self._builders = builder_source
        self._providers = provider_source
        self._store = build_authority_state_store()
        self._origin = verify_authority_state_store_origin()
        if type(self._store) is not SQLiteAuthorityStateStore or self._store.ready() is not True:
            raise BuilderProcessLaunchError("canonical persistence unavailable")
        if self._store.resolve_authority_store_origin() != self._origin:
            raise BuilderProcessLaunchError("canonical persistence origin mismatch")
        self._replay = DurableReplayGuard(self._store, domain=self.REPLAY_DOMAIN)

    def _currentness(self, *, admission: BuilderStartAdmission, admitted_authority: LiveAdmittedResourceAuthority,
                     trusted_now: datetime, expected_provider: BuilderProcessRuntimeProviderDescriptor) -> tuple[str, TrustedBuilderSubject, BuilderProcessRuntimeProviderDescriptor]:
        now = trusted_now.astimezone(timezone.utc)
        if verify_authority_state_store_origin() != self._origin:
            raise BuilderProcessLaunchError("canonical origin drift")
        current = self._baseline.current(admission.repository)
        if type(current) is not TrustedRepositoryBaseline:
            raise BuilderProcessLaunchError("trusted baseline invalid")
        current.validate()
        if (current.repository, current.master_sha, current.master_tree_sha, current.digest()) != (
            admission.repository, admission.baseline_master_sha, admission.baseline_master_tree_sha, admission.current_baseline_digest
        ):
            raise BuilderProcessLaunchError("baseline stale")
        try:
            authority = self._live.revalidate(admitted_authority, now=now)
        except Exception as exc:
            raise BuilderProcessLaunchError("authority currentness failed") from exc
        authority.validate()
        if (authority.repository, authority.epoch, authority.epoch_state_version, authority.root_grant_id,
            authority.root_grant_digest, authority.digest(), authority.resource_scope, authority.action) != (
            admission.repository, admission.authority_epoch, admission.authority_state_version,
            admission.root_grant_id, admission.root_grant_digest, admission.current_authority_digest,
            admission.resource_scope, "BUILD_CANDIDATE"):
            raise BuilderProcessLaunchError("authority mismatch")
        self._builders.verify_origin()
        subject = _sealed_subject(self._builders.resolve_exact(
            builder_subject_id=admission.builder_subject_id, builder_instance_id=admission.builder_instance_id,
            repository=admission.repository, candidate_scope=admission.candidate_scope, resource_scope=admission.resource_scope,
        ))
        if (subject.subject_digest, subject.identity_digest, subject.implementation_digest, subject.attestation_digest) != (
            admission.current_builder_subject_digest, admission.builder_identity_digest,
            admission.builder_implementation_digest, admission.builder_attestation_digest):
            raise BuilderProcessLaunchError("builder currentness mismatch")
        start = datetime.fromisoformat(subject.valid_from.replace("Z", "+00:00")).astimezone(timezone.utc)
        end = datetime.fromisoformat(subject.expires_at.replace("Z", "+00:00")).astimezone(timezone.utc)
        if now < start or now >= end:
            raise BuilderProcessLaunchError("builder outside validity")
        profile_kwargs = dict(
            repository=admission.repository, action=admission.action,
            candidate_scope=admission.candidate_scope, resource_scope=admission.resource_scope,
            builder_subject_id=subject.builder_subject_id, builder_instance_id=subject.builder_instance_id,
            builder_capability_class=subject.capability_class, builder_identity_digest=subject.identity_digest,
            builder_implementation_digest=subject.implementation_digest, builder_attestation_digest=subject.attestation_digest,
            current_builder_subject_digest=subject.subject_digest,
        )
        if compute_process_profile_digest(**profile_kwargs) != admission.process_profile_digest or admission.process_profile_id != f"bpp:{admission.process_profile_digest}":
            raise BuilderProcessLaunchError("process profile drift")
        if compute_launch_policy_digest() != admission.launch_policy_digest:
            raise BuilderProcessLaunchError("launch policy drift")
        descriptor = self._providers.resolve_exact(
            provider_id=expected_provider.provider_id,
            process_profile_digest=admission.process_profile_digest,
            launch_policy_digest=admission.launch_policy_digest,
        )
        if type(descriptor) is not BuilderProcessRuntimeProviderDescriptor:
            raise BuilderProcessLaunchError("exact trusted runtime provider descriptor required")
        descriptor.validate()
        if not descriptor.descriptor_digest or descriptor.descriptor_digest != descriptor.compute_digest() or descriptor != expected_provider:
            raise BuilderProcessLaunchError("runtime provider currentness mismatch")
        _f005_ok(self._f005.current())
        return authority.digest(), subject, descriptor

    def build_request(self, *, source_admission: BuilderStartAdmission,
                      admitted_authority: LiveAdmittedResourceAuthority,
                      runtime_provider_descriptor: BuilderProcessRuntimeProviderDescriptor,
                      trusted_now: datetime) -> BuilderProcessLaunchRequest:
        admission = _sealed_r21(source_admission)
        if not isinstance(trusted_now, datetime) or trusted_now.tzinfo is None:
            raise BuilderProcessLaunchError("trusted time invalid")
        record = resolve_builder_start_admission_issuance(admission.builder_start_admission_id)
        if type(record) is not PersistentBuilderStartAdmissionIssuanceRecord:
            raise BuilderProcessLaunchError("exact durable R21 issuance required")
        record.validate(); _exact_r21_record(admission, record)
        authority_digest, subject, descriptor = self._currentness(
            admission=admission, admitted_authority=admitted_authority, trusted_now=trusted_now,
            expected_provider=runtime_provider_descriptor,
        )
        kwargs = dict(
            source_builder_start_admission_id=admission.builder_start_admission_id,
            source_builder_start_admission_digest=admission.builder_start_admission_digest,
            source_builder_start_admission_replay_digest=admission.builder_start_admission_replay_digest,
            source_builder_start_issuance_record_id=f"bsair:{admission.builder_start_admission_id}",
            source_builder_start_issuance_record_digest=_r21_record_digest(record),
            repository=admission.repository, baseline_master_sha=admission.baseline_master_sha,
            baseline_master_tree_sha=admission.baseline_master_tree_sha,
            authority_epoch=admission.authority_epoch, authority_state_version=admission.authority_state_version,
            root_grant_id=admission.root_grant_id, root_grant_digest=admission.root_grant_digest,
            expected_current_authority_digest=authority_digest,
            builder_subject_id=subject.builder_subject_id, builder_instance_id=subject.builder_instance_id,
            builder_identity_digest=subject.identity_digest, builder_implementation_digest=subject.implementation_digest,
            builder_attestation_digest=subject.attestation_digest, expected_builder_subject_digest=subject.subject_digest,
            process_profile_id=admission.process_profile_id, process_profile_digest=admission.process_profile_digest,
            launch_policy_digest=admission.launch_policy_digest, runtime_provider_id=descriptor.provider_id,
            runtime_provider_identity_digest=descriptor.provider_identity_digest,
            runtime_provider_implementation_digest=descriptor.provider_implementation_digest,
            runtime_provider_attestation_digest=descriptor.provider_attestation_digest,
        )
        replay = compute_launch_replay_digest(**kwargs)
        return BuilderProcessLaunchRequest(launch_request_id=f"bplr:{replay}", launch_replay_digest=replay, **kwargs).sealed()

    def launch(self, *, request: BuilderProcessLaunchRequest, source_admission: BuilderStartAdmission,
               admitted_authority: LiveAdmittedResourceAuthority, runtime_provider: BuilderProcessRuntimeProvider,
               trusted_now: datetime) -> BuilderProcessLaunchReceipt:
        admission = _sealed_r21(source_admission)
        if type(request) is not BuilderProcessLaunchRequest:
            raise BuilderProcessLaunchError("exact launch request required")
        request.validate()
        if not request.launch_request_digest or request.launch_request_digest != request.compute_digest():
            raise BuilderProcessLaunchError("sealed launch request required")
        descriptor = runtime_provider.descriptor
        if type(descriptor) is not BuilderProcessRuntimeProviderDescriptor:
            raise BuilderProcessLaunchError("runtime provider descriptor invalid")
        descriptor.validate()
        rebuilt = self.build_request(source_admission=admission, admitted_authority=admitted_authority,
                                     runtime_provider_descriptor=descriptor, trusted_now=trusted_now)
        if rebuilt != request:
            raise BuilderProcessLaunchError("launch request currentness mismatch")
        prepared_at = _utc_text(trusted_now)
        intent = PersistentBuilderProcessLaunchIntent.from_request(request, authority_store_origin=self._origin, prepared_at=prepared_at)
        self._store.record_builder_process_launch_intent(intent)
        try:
            consumed = self._replay.consume(request.launch_replay_digest, consumed_at=prepared_at)
        except Exception as exc:
            raise BuilderProcessLaunchError("launch replay persistence failed closed") from exc
        if consumed is not True:
            raise BuilderProcessLaunchError("launch replay denied")
        held = runtime_provider.prepare_launch(request)
        if type(held) is not BuilderProcessIdentity:
            raise BuilderProcessLaunchError("runtime provider returned invalid held identity")
        held.validate()
        if not held.identity_digest or held.identity_digest != held.compute_digest() or held.state != HELD_STATE:
            raise BuilderProcessLaunchError("provider prepare must return sealed HELD identity")
        if (held.runtime_provider_id, held.runtime_provider_identity_digest, held.process_profile_id, held.process_profile_digest,
            held.launch_policy_digest, held.builder_subject_id, held.builder_instance_id) != (
            descriptor.provider_id, descriptor.provider_identity_digest, request.process_profile_id, request.process_profile_digest,
            request.launch_policy_digest, request.builder_subject_id, request.builder_instance_id):
            raise BuilderProcessLaunchError("held process identity binding mismatch")
        # HELD identity and token are provider-durable materialization evidence. It must still not execute builder code.
        authority_digest, subject, current_descriptor = self._currentness(
            admission=admission, admitted_authority=admitted_authority, trusted_now=trusted_now,
            expected_provider=descriptor,
        )
        if current_descriptor != descriptor:
            raise BuilderProcessLaunchError("provider drift before commit")
        started = runtime_provider.commit_start(request, held)
        if type(started) is not BuilderProcessIdentity:
            raise BuilderProcessLaunchError("runtime provider start identity invalid")
        started.validate()
        if not started.identity_digest or started.identity_digest != started.compute_digest() or started.state != STARTED_STATE:
            raise BuilderProcessLaunchError("commit_start must return sealed STARTED identity")
        observed = runtime_provider.observe_launch(started.launch_id)
        if type(observed) is not BuilderProcessIdentity:
            raise BuilderProcessLaunchError("process start observation invalid")
        observed.validate()
        if not observed.identity_digest or observed.identity_digest != observed.compute_digest() or observed != started:
            try:
                runtime_provider.freeze_or_kill(started.launch_id)
            finally:
                raise BuilderProcessLaunchError("process launch continuity unknown; runtime containment requested")
        receipt = BuilderProcessLaunchReceipt(
            launch_receipt_id=f"bplx:{request.launch_replay_digest}", launch_request_id=request.launch_request_id,
            launch_request_digest=request.launch_request_digest, launch_replay_digest=request.launch_replay_digest,
            source_builder_start_admission_id=admission.builder_start_admission_id,
            source_builder_start_admission_digest=admission.builder_start_admission_digest,
            repository=admission.repository, baseline_master_sha=admission.baseline_master_sha,
            baseline_master_tree_sha=admission.baseline_master_tree_sha,
            authority_digest_at_launch=authority_digest, builder_subject_digest_at_launch=subject.subject_digest,
            process_profile_id=request.process_profile_id, process_profile_digest=request.process_profile_digest,
            launch_policy_digest=request.launch_policy_digest, runtime_provider_id=descriptor.provider_id,
            runtime_provider_identity_digest=descriptor.provider_identity_digest,
            runtime_provider_implementation_digest=descriptor.provider_implementation_digest,
            runtime_provider_attestation_digest=descriptor.provider_attestation_digest,
            launch_id=started.launch_id, execution_environment_id=started.execution_environment_id,
            process_handle_reference=started.process_handle_reference, process_identity_token=started.process_identity_token,
            process_identity_digest=started.identity_digest, launch_started_at=started.started_at,
            launch_observed_at=_utc_text(trusted_now),
        ).sealed()
        durable = PersistentBuilderProcessLaunchReceipt.from_receipt(receipt, authority_store_origin=self._origin)
        try:
            self._store.record_builder_process_launch_receipt(durable)
        except Exception as exc:
            try:
                runtime_provider.freeze_or_kill(started.launch_id)
            finally:
                raise BuilderProcessLaunchError("launch occurred but durable receipt failed; containment requested") from exc
        return receipt
