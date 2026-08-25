"""Fail-closed non-effectful consumption boundary for BuilderInvocationPermit."""
from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any, Protocol

from cyber_lion.contracts.builder_entry_permit import BUILDER_CAPABILITY_CLASS, TrustedBuilderSubject
from cyber_lion.contracts.builder_invocation_consumption import (
    SCHEMA_VERSION,
    BuilderInvocationConsumptionPermit,
    compute_invocation_consumption_replay_digest,
)
from cyber_lion.contracts.builder_invocation_permit import BuilderInvocationPermit
from cyber_lion.contracts.candidate_build_authorization import TrustedRepositoryBaseline
from cyber_lion.enterprise.builder_entry_permit import PinnedTrustedBuilderSubjectSource
from cyber_lion.enterprise.candidate_build_authorization import (
    LiveAdmittedResourceAuthority,
    LiveResourceAuthorityAdmission,
)
from cyber_lion.enterprise.persistent_authority_state import (
    PersistentAuthorityStoreOrigin,
    PersistentBuilderEntryIssuanceRecord,
    PersistentBuilderInvocationIssuanceRecord,
    SQLiteAuthorityStateStore,
)
from cyber_lion.enterprise.trusted_control_plane_runtime import (
    build_authority_state_store,
    verify_authority_state_store_origin,
)


class BuilderInvocationConsumptionError(RuntimeError):
    pass


_EFFECT_METHODS = frozenset({
    "execute", "write", "push", "merge", "deploy", "release", "create_branch",
    "create_pr", "run_test", "build_candidate", "consume_candidate", "start_builder",
    "spawn", "popen", "issue_grant",
})


class TrustedRepositoryBaselineSource(Protocol):
    def current(self, repository: str) -> TrustedRepositoryBaseline: ...


class F005StateSource(Protocol):
    def current(self) -> Mapping[str, Any]: ...


class PersistentBuilderInvocationConsumptionReplayGuard:
    """Restart-safe R20 replay guard pinned to the canonical process/store origin."""

    DOMAIN = "builder-invocation-permit-consumption"
    __slots__ = ("_store", "_origin")

    def __init__(self) -> None:
        try:
            store = build_authority_state_store()
            origin = verify_authority_state_store_origin()
        except Exception as exc:
            raise BuilderInvocationConsumptionError("canonical persistent replay store unavailable") from exc
        if type(store) is not SQLiteAuthorityStateStore or not store.ready():
            raise BuilderInvocationConsumptionError("canonical persistent replay store invalid")
        if type(origin) is not PersistentAuthorityStoreOrigin:
            raise BuilderInvocationConsumptionError("canonical replay store origin invalid")
        self._store = store
        self._origin = origin

    def consume(self, replay_digest: str, *, consumed_at: str) -> bool:
        try:
            current = verify_authority_state_store_origin()
        except Exception as exc:
            raise BuilderInvocationConsumptionError("canonical replay store origin unavailable") from exc
        if current != self._origin:
            raise BuilderInvocationConsumptionError("canonical replay store origin drift")
        return self._store.consume_replay(self.DOMAIN, replay_digest, consumed_at)


class PersistentBuilderInvocationIssuanceSource:
    """Read-only R19 provenance plus exact transitive R17 ancestry on one canonical origin."""

    __slots__ = ("_store", "_origin")

    def __init__(self) -> None:
        try:
            store = build_authority_state_store()
            origin = verify_authority_state_store_origin()
        except Exception as exc:
            raise BuilderInvocationConsumptionError("canonical persistent authority store unavailable") from exc
        if type(store) is not SQLiteAuthorityStateStore or not store.ready():
            raise BuilderInvocationConsumptionError("canonical persistent authority store invalid")
        if type(origin) is not PersistentAuthorityStoreOrigin:
            raise BuilderInvocationConsumptionError("canonical authority store origin invalid")
        self._store = store
        self._origin = origin

    def _current_origin(self) -> PersistentAuthorityStoreOrigin:
        try:
            current = verify_authority_state_store_origin()
        except Exception as exc:
            raise BuilderInvocationConsumptionError("canonical authority store origin unavailable") from exc
        if current != self._origin:
            raise BuilderInvocationConsumptionError("canonical authority store origin drift")
        return current

    def resolve(self, permit_id: str) -> PersistentBuilderInvocationIssuanceRecord:
        current = self._current_origin()
        try:
            record = self._store.resolve_builder_invocation_issuance(permit_id)
        except Exception as exc:
            raise BuilderInvocationConsumptionError("durable builder invocation issuance unavailable") from exc
        if type(record) is not PersistentBuilderInvocationIssuanceRecord:
            raise BuilderInvocationConsumptionError("durable builder invocation issuance type invalid")
        try:
            record.validate()
        except Exception as exc:
            raise BuilderInvocationConsumptionError("durable builder invocation issuance invalid") from exc
        if (record.authority_store_origin_id, record.authority_store_origin_digest) != (current.origin_id, current.origin_digest):
            raise BuilderInvocationConsumptionError("durable builder invocation issuance origin mismatch")

        try:
            ancestor = self._store.resolve_builder_entry_issuance(record.source_builder_entry_permit_id)
        except Exception as exc:
            raise BuilderInvocationConsumptionError("durable builder entry ancestry unavailable") from exc
        if type(ancestor) is not PersistentBuilderEntryIssuanceRecord:
            raise BuilderInvocationConsumptionError("durable builder entry ancestry type invalid")
        try:
            ancestor.validate()
        except Exception as exc:
            raise BuilderInvocationConsumptionError("durable builder entry ancestry invalid") from exc
        if (
            record.source_builder_entry_permit_id,
            record.source_builder_entry_permit_digest,
        ) != (
            ancestor.builder_entry_permit_id,
            ancestor.builder_entry_permit_digest,
        ):
            raise BuilderInvocationConsumptionError("builder invocation R17 ancestry identity mismatch")
        if (
            record.authority_store_origin_id,
            record.authority_store_origin_digest,
            ancestor.authority_store_origin_id,
            ancestor.authority_store_origin_digest,
        ) != (
            current.origin_id,
            current.origin_digest,
            current.origin_id,
            current.origin_digest,
        ):
            raise BuilderInvocationConsumptionError("builder invocation R17/R19 ancestry origin mismatch")
        return record


def _utc(value: str, name: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, ValueError) as exc:
        raise BuilderInvocationConsumptionError(f"{name} invalid") from exc
    if parsed.tzinfo is None:
        raise BuilderInvocationConsumptionError(f"{name} must be timezone-aware")
    return parsed.astimezone(timezone.utc)


def _sealed_invocation(value: object) -> BuilderInvocationPermit:
    if type(value) is not BuilderInvocationPermit:
        raise BuilderInvocationConsumptionError("exact BuilderInvocationPermit required")
    try:
        value.validate()
    except Exception as exc:
        raise BuilderInvocationConsumptionError("builder invocation permit invalid") from exc
    if (
        not value.builder_invocation_permit_digest
        or value.builder_invocation_permit_digest != value.compute_digest()
        or value.builder_invocation_replay_digest != value.compute_builder_invocation_replay_digest()
    ):
        raise BuilderInvocationConsumptionError("builder invocation permit must be sealed and source-bound")
    if value.state != "BUILDER_INVOCATION_PERMIT_ISSUED" or value.action != "BUILD_CANDIDATE":
        raise BuilderInvocationConsumptionError("builder invocation permit state/action invalid")
    if value.builder_capability_class != BUILDER_CAPABILITY_CLASS:
        raise BuilderInvocationConsumptionError("builder invocation capability invalid")
    if (
        value.authority_effect,
        value.execution_effect,
        value.repository_ref_effect,
        value.external_effect,
    ) != ("NONE", "NONE", "NONE", "NONE"):
        raise BuilderInvocationConsumptionError("builder invocation permit carries effects")
    return value


def _live_receipt(value: object) -> LiveAdmittedResourceAuthority:
    if type(value) is not LiveAdmittedResourceAuthority:
        raise BuilderInvocationConsumptionError("exact live authority receipt required")
    try:
        value.validate()
    except Exception as exc:
        raise BuilderInvocationConsumptionError("live authority receipt invalid") from exc
    return value


def _f005_ok(value: Mapping[str, Any]) -> None:
    if not isinstance(value, Mapping) or value.get("state") != "QUARANTINED" or value.get("effect_authority") != "DENY":
        raise BuilderInvocationConsumptionError("F005 quarantine invariant failed")


def _sealed_subject(value: object) -> TrustedBuilderSubject:
    if type(value) is not TrustedBuilderSubject:
        raise BuilderInvocationConsumptionError("exact TrustedBuilderSubject required")
    try:
        value.validate()
    except Exception as exc:
        raise BuilderInvocationConsumptionError("trusted builder subject invalid") from exc
    if not value.subject_digest or value.subject_digest != value.compute_digest():
        raise BuilderInvocationConsumptionError("trusted builder subject must be sealed")
    return value


def _verify_exact_issuance(permit: BuilderInvocationPermit, record: PersistentBuilderInvocationIssuanceRecord) -> None:
    expected = (
        permit.builder_invocation_permit_id,
        permit.builder_invocation_permit_digest,
        permit.builder_invocation_replay_digest,
        permit.source_builder_entry_permit_id,
        permit.source_builder_entry_permit_digest,
        permit.repository,
        permit.baseline_master_sha,
        permit.baseline_master_tree_sha,
        permit.current_baseline_digest,
        permit.action,
        permit.candidate_scope,
        permit.resource_scope,
        permit.authority_epoch,
        permit.authority_state_version,
        permit.root_grant_id,
        permit.root_grant_digest,
        permit.current_authority_digest,
        permit.builder_subject_id,
        permit.builder_instance_id,
        permit.builder_capability_class,
        permit.builder_identity_digest,
        permit.builder_implementation_digest,
        permit.builder_attestation_digest,
        permit.current_builder_subject_digest,
        permit.checked_at,
    )
    actual = (
        record.builder_invocation_permit_id,
        record.builder_invocation_permit_digest,
        record.builder_invocation_replay_digest,
        record.source_builder_entry_permit_id,
        record.source_builder_entry_permit_digest,
        record.repository,
        record.baseline_master_sha,
        record.baseline_master_tree_sha,
        record.current_baseline_digest,
        record.action,
        record.candidate_scope,
        record.resource_scope,
        record.authority_epoch,
        record.authority_state_version,
        record.root_grant_id,
        record.root_grant_digest,
        record.current_authority_digest,
        record.builder_subject_id,
        record.builder_instance_id,
        record.builder_capability_class,
        record.builder_identity_digest,
        record.builder_implementation_digest,
        record.builder_attestation_digest,
        record.current_builder_subject_digest,
        record.issued_at,
    )
    if actual != expected:
        raise BuilderInvocationConsumptionError("builder invocation durable issuance provenance mismatch")


class BuilderInvocationConsumptionEngine:
    """Consume exact R19 issuance once; never start a builder or produce candidate effects."""

    def __init__(
        self,
        *,
        live_authority: LiveResourceAuthorityAdmission,
        baseline_source: TrustedRepositoryBaselineSource,
        f005_state_source: F005StateSource,
        builder_source: PinnedTrustedBuilderSubjectSource,
    ) -> None:
        if type(live_authority) is not LiveResourceAuthorityAdmission:
            raise BuilderInvocationConsumptionError("live authority admission required")
        if type(builder_source) is not PinnedTrustedBuilderSubjectSource:
            raise BuilderInvocationConsumptionError("exact pinned builder source required")
        builder_source.verify_origin()
        for obj, method in ((baseline_source, "current"), (f005_state_source, "current")):
            if not callable(getattr(obj, method, None)):
                raise BuilderInvocationConsumptionError("builder invocation consumption dependency unavailable")
        self._live = live_authority
        self._baseline = baseline_source
        self._f005 = f005_state_source
        self._builders = builder_source
        self._source_issuance = PersistentBuilderInvocationIssuanceSource()
        self._replay = PersistentBuilderInvocationConsumptionReplayGuard()

    def issue_permit(
        self,
        *,
        source_permit: BuilderInvocationPermit,
        admitted_authority: LiveAdmittedResourceAuthority,
        trusted_now: datetime,
    ) -> BuilderInvocationConsumptionPermit:
        permit = _sealed_invocation(source_permit)
        admitted = _live_receipt(admitted_authority)
        if not isinstance(trusted_now, datetime) or trusted_now.tzinfo is None:
            raise BuilderInvocationConsumptionError("trusted_now must be timezone-aware")
        now = trusted_now.astimezone(timezone.utc)

        record = self._source_issuance.resolve(permit.builder_invocation_permit_id)
        _verify_exact_issuance(permit, record)

        current = self._baseline.current(permit.repository)
        if type(current) is not TrustedRepositoryBaseline:
            raise BuilderInvocationConsumptionError("trusted baseline type invalid")
        try:
            current.validate()
        except Exception as exc:
            raise BuilderInvocationConsumptionError("trusted baseline invalid") from exc
        if (current.repository, current.master_sha, current.master_tree_sha) != (
            permit.repository, permit.baseline_master_sha, permit.baseline_master_tree_sha
        ):
            raise BuilderInvocationConsumptionError("builder invocation consumption baseline stale")
        if current.digest() != permit.current_baseline_digest:
            raise BuilderInvocationConsumptionError("builder invocation current baseline digest drift")

        try:
            authority = self._live.revalidate(admitted, now=now)
        except Exception as exc:
            raise BuilderInvocationConsumptionError("current authority revalidation failed") from exc
        if type(authority) is not LiveAdmittedResourceAuthority:
            raise BuilderInvocationConsumptionError("revalidated authority type invalid")
        try:
            authority.validate()
        except Exception as exc:
            raise BuilderInvocationConsumptionError("revalidated authority invalid") from exc
        expected_authority = (
            permit.repository, permit.authority_epoch, permit.authority_state_version,
            permit.root_grant_id, permit.root_grant_digest, permit.current_authority_digest,
            permit.resource_scope, "BUILD_CANDIDATE",
        )
        actual_authority = (
            authority.repository, authority.epoch, authority.epoch_state_version,
            authority.root_grant_id, authority.root_grant_digest, authority.digest(),
            authority.resource_scope, authority.action,
        )
        if actual_authority != expected_authority:
            raise BuilderInvocationConsumptionError("builder invocation/current authority mismatch")

        self._builders.verify_origin()
        subject = _sealed_subject(self._builders.resolve_exact(
            builder_subject_id=permit.builder_subject_id,
            builder_instance_id=permit.builder_instance_id,
            repository=permit.repository,
            candidate_scope=permit.candidate_scope,
            resource_scope=permit.resource_scope,
        ))
        expected_builder = (
            permit.builder_subject_id, permit.builder_instance_id, permit.builder_capability_class,
            permit.repository, permit.candidate_scope, permit.resource_scope,
            permit.builder_identity_digest, permit.builder_implementation_digest,
            permit.builder_attestation_digest, permit.current_builder_subject_digest,
            "ADMITTED", "trusted-control-plane",
        )
        actual_builder = (
            subject.builder_subject_id, subject.builder_instance_id, subject.capability_class,
            subject.repository, subject.candidate_scope, subject.resource_scope,
            subject.identity_digest, subject.implementation_digest,
            subject.attestation_digest, subject.subject_digest,
            subject.state, subject.source_kind,
        )
        if actual_builder != expected_builder:
            raise BuilderInvocationConsumptionError("builder invocation/current builder mismatch")
        if now < _utc(subject.valid_from, "builder valid_from") or now >= _utc(subject.expires_at, "builder expires_at"):
            raise BuilderInvocationConsumptionError("builder subject outside validity window")

        _f005_ok(self._f005.current())

        kwargs = dict(
            source_builder_invocation_permit_id=permit.builder_invocation_permit_id,
            source_builder_invocation_permit_digest=permit.builder_invocation_permit_digest,
            source_builder_invocation_replay_digest=permit.builder_invocation_replay_digest,
            source_builder_entry_permit_id=permit.source_builder_entry_permit_id,
            source_builder_entry_permit_digest=permit.source_builder_entry_permit_digest,
            repository=permit.repository,
            baseline_master_sha=permit.baseline_master_sha,
            baseline_master_tree_sha=permit.baseline_master_tree_sha,
            current_baseline_digest=current.digest(),
            action="BUILD_CANDIDATE",
            candidate_scope=permit.candidate_scope,
            resource_scope=permit.resource_scope,
            authority_epoch=permit.authority_epoch,
            authority_state_version=permit.authority_state_version,
            root_grant_id=permit.root_grant_id,
            root_grant_digest=permit.root_grant_digest,
            current_authority_digest=authority.digest(),
            builder_subject_id=subject.builder_subject_id,
            builder_instance_id=subject.builder_instance_id,
            builder_capability_class=subject.capability_class,
            builder_identity_digest=subject.identity_digest,
            builder_implementation_digest=subject.implementation_digest,
            builder_attestation_digest=subject.attestation_digest,
            current_builder_subject_digest=subject.subject_digest,
        )
        replay = compute_invocation_consumption_replay_digest(**kwargs)
        checked_at = now.isoformat()
        if self._replay.consume(replay, consumed_at=checked_at) is not True:
            raise BuilderInvocationConsumptionError("builder invocation consumption replay denied")
        return BuilderInvocationConsumptionPermit(
            schema_version=SCHEMA_VERSION,
            invocation_consumption_permit_id=f"bicp:{replay}",
            invocation_consumption_replay_digest=replay,
            checked_at=checked_at,
            **kwargs,
        ).sealed()

    @classmethod
    def assert_no_effect_surface(cls) -> None:
        for name in _EFFECT_METHODS:
            if hasattr(cls, name):
                raise BuilderInvocationConsumptionError(f"effect surface present: {name}")
