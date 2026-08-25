"""Fail-closed non-effectful builder-entry permit issuer."""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from hashlib import sha256
import json
from typing import Any, Mapping, Protocol

from cyber_lion.contracts.builder_entry_permit import (
    BUILDER_CAPABILITY_CLASS,
    SCHEMA_VERSION,
    BuilderEntryPermit,
    TrustedBuilderSubject,
    compute_builder_entry_replay_digest,
)
from cyber_lion.contracts.build_authorization_consumption import (
    BuildAuthorizationConsumptionPermit,
)
from cyber_lion.contracts.candidate_build_authorization import TrustedRepositoryBaseline
from cyber_lion.enterprise.candidate_build_authorization import (
    LiveAdmittedResourceAuthority,
    LiveResourceAuthorityAdmission,
)


class BuilderEntryPermitError(RuntimeError):
    pass


_EFFECT_METHODS = frozenset(
    {
        "execute",
        "write",
        "push",
        "merge",
        "deploy",
        "release",
        "create_branch",
        "create_pr",
        "run_test",
        "build_candidate",
        "consume_candidate",
        "start_builder",
        "issue_grant",
    }
)

_BACKEND_PROVENANCE_DOMAIN = b"LION/E004-PINNED-BUILDER-BACKEND-PROVENANCE/1\0"
PINNED_BUILDER_BACKEND_IDENTITY = "lion.control-plane.builder-registry/v1"
PINNED_BUILDER_BACKEND_IMPLEMENTATION_DIGEST = sha256(
    b"LION/E004-PINNED-BUILDER-CONTROL-PLANE-BACKEND/1"
).hexdigest()
PINNED_BUILDER_SOURCE_IMPLEMENTATION_DIGEST = sha256(
    b"LION/E004-PINNED-TRUSTED-BUILDER-SOURCE/2"
).hexdigest()


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def _utc(value: str, name: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, ValueError) as exc:
        raise BuilderEntryPermitError(f"{name} invalid") from exc
    if parsed.tzinfo is None:
        raise BuilderEntryPermitError(f"{name} must be timezone-aware")
    return parsed.astimezone(timezone.utc)


def _sealed_subject_digest(subject: object) -> str:
    if type(subject) is not TrustedBuilderSubject:
        raise BuilderEntryPermitError("trusted builder subject type invalid")
    try:
        subject.validate()
    except Exception as exc:
        raise BuilderEntryPermitError("trusted builder subject invalid") from exc
    if not subject.subject_digest or subject.subject_digest != subject.compute_digest():
        raise BuilderEntryPermitError("trusted builder subject must be sealed")
    return subject.subject_digest


def _backend_provenance_digest(
    records: tuple[TrustedBuilderSubject, ...],
) -> str:
    if type(records) is not tuple:
        raise BuilderEntryPermitError("builder backend snapshot must be tuple")
    digests = tuple(_sealed_subject_digest(record) for record in records)
    payload = {
        "backend_identity": PINNED_BUILDER_BACKEND_IDENTITY,
        "backend_implementation_digest": PINNED_BUILDER_BACKEND_IMPLEMENTATION_DIGEST,
        "record_subject_digests": list(digests),
    }
    return sha256(
        _BACKEND_PROVENANCE_DOMAIN + _canonical_json(payload)
    ).hexdigest()


def _load_pinned_builder_records() -> tuple[TrustedBuilderSubject, ...]:
    """Read the control-plane-owned snapshot.

    The default fail-closed implementation contains no local record injection
    surface. Deployment composition must replace this internal read boundary
    with the trusted control-plane binding before builder entry is enabled.
    """
    return ()


class TrustedRepositoryBaselineSource(Protocol):
    def current(self, repository: str) -> TrustedRepositoryBaseline:
        ...


class F005StateSource(Protocol):
    def current(self) -> Mapping[str, Any]:
        ...


class BuilderEntryReplayGuard(Protocol):
    def consume(self, replay_digest: str, *, consumed_at: str) -> bool:
        ...


class PersistentBuilderEntryReplayGuard:
    DOMAIN = "candidate-builder-entry-consumption"

    def __init__(self, store: object):
        if not callable(getattr(store, "consume_replay", None)):
            raise BuilderEntryPermitError("persistent replay store unavailable")
        self._store = store

    def consume(self, replay_digest: str, *, consumed_at: str) -> bool:
        return self._store.consume_replay(self.DOMAIN, replay_digest, consumed_at)


class TrustedBuilderSubjectSource(ABC):
    """Legacy shape only; inheritance never establishes trust."""

    source_kind = "untrusted-abstract-source"

    @abstractmethod
    def _lookup_exact(
        self,
        *,
        builder_subject_id: str,
        builder_instance_id: str,
        repository: str,
        candidate_scope: tuple[str, ...],
        resource_scope: tuple[str, ...],
    ) -> tuple[TrustedBuilderSubject, ...]:
        raise NotImplementedError


class PinnedBuilderControlPlaneBackend:
    """Concrete, read-only source-of-record boundary.

    The constructor accepts no records, identity, implementation digest, or
    provenance input from its caller. Its snapshot is obtained only through
    the module-internal control-plane read boundary.
    """

    backend_identity = PINNED_BUILDER_BACKEND_IDENTITY
    backend_implementation_digest = PINNED_BUILDER_BACKEND_IMPLEMENTATION_DIGEST
    __slots__ = ("_records", "_provenance_digest")

    def __init_subclass__(cls, **kwargs: object) -> None:
        raise TypeError("PinnedBuilderControlPlaneBackend is final")

    def __init__(self) -> None:
        if type(self) is not PinnedBuilderControlPlaneBackend:
            raise BuilderEntryPermitError("exact pinned builder backend required")
        records = _load_pinned_builder_records()
        if type(records) is not tuple:
            raise BuilderEntryPermitError("builder backend snapshot invalid")
        self._records = records
        self._provenance_digest = _backend_provenance_digest(records)

    @property
    def provenance_digest(self) -> str:
        return self._provenance_digest

    def verify_origin(self) -> None:
        if type(self) is not PinnedBuilderControlPlaneBackend:
            raise BuilderEntryPermitError("exact pinned builder backend required")
        if type(self).backend_identity != PINNED_BUILDER_BACKEND_IDENTITY:
            raise BuilderEntryPermitError("builder backend identity mismatch")
        if (
            type(self).backend_implementation_digest
            != PINNED_BUILDER_BACKEND_IMPLEMENTATION_DIGEST
        ):
            raise BuilderEntryPermitError("builder backend implementation mismatch")
        expected = _backend_provenance_digest(self._records)
        if self._provenance_digest != expected:
            raise BuilderEntryPermitError("builder backend provenance mismatch")

    def resolve_exact(
        self,
        *,
        builder_subject_id: str,
        builder_instance_id: str,
        repository: str,
        candidate_scope: tuple[str, ...],
        resource_scope: tuple[str, ...],
    ) -> TrustedBuilderSubject:
        self.verify_origin()
        records = tuple(
            record
            for record in self._records
            if type(record) is TrustedBuilderSubject
            and record.builder_subject_id == builder_subject_id
            and record.builder_instance_id == builder_instance_id
            and record.repository == repository
            and record.candidate_scope == candidate_scope
            and record.resource_scope == resource_scope
        )
        if len(records) == 0:
            raise BuilderEntryPermitError("trusted builder subject not found")
        if len(records) > 1:
            raise BuilderEntryPermitError("trusted builder subject lookup ambiguous")
        subject = records[0]
        _sealed_subject_digest(subject)
        return subject


class PinnedTrustedBuilderSubjectSource:
    """Exact adapter over the exact pinned control-plane backend."""

    source_kind = "trusted-control-plane"
    source_implementation_digest = PINNED_BUILDER_SOURCE_IMPLEMENTATION_DIGEST
    __slots__ = ("_backend",)

    def __init_subclass__(cls, **kwargs: object) -> None:
        raise TypeError("PinnedTrustedBuilderSubjectSource is final")

    def __init__(self, *, backend: PinnedBuilderControlPlaneBackend) -> None:
        if type(self) is not PinnedTrustedBuilderSubjectSource:
            raise BuilderEntryPermitError("exact pinned builder source required")
        if type(backend) is not PinnedBuilderControlPlaneBackend:
            raise BuilderEntryPermitError("exact pinned builder backend required")
        backend.verify_origin()
        self._backend = backend

    @property
    def backend(self) -> PinnedBuilderControlPlaneBackend:
        return self._backend

    @property
    def source_attestation_digest(self) -> str:
        # Evidence-only projection of backend-owned provenance.
        return self._backend.provenance_digest

    def verify_origin(self) -> None:
        if type(self) is not PinnedTrustedBuilderSubjectSource:
            raise BuilderEntryPermitError("exact pinned builder source required")
        if type(self).source_kind != "trusted-control-plane":
            raise BuilderEntryPermitError("builder source kind mismatch")
        if (
            type(self).source_implementation_digest
            != PINNED_BUILDER_SOURCE_IMPLEMENTATION_DIGEST
        ):
            raise BuilderEntryPermitError("builder source implementation mismatch")
        if type(self._backend) is not PinnedBuilderControlPlaneBackend:
            raise BuilderEntryPermitError("builder source backend type mismatch")
        self._backend.verify_origin()

    def resolve_exact(
        self,
        *,
        builder_subject_id: str,
        builder_instance_id: str,
        repository: str,
        candidate_scope: tuple[str, ...],
        resource_scope: tuple[str, ...],
    ) -> TrustedBuilderSubject:
        self.verify_origin()
        subject = self._backend.resolve_exact(
            builder_subject_id=builder_subject_id,
            builder_instance_id=builder_instance_id,
            repository=repository,
            candidate_scope=candidate_scope,
            resource_scope=resource_scope,
        )
        _sealed_subject_digest(subject)
        expected = (
            builder_subject_id,
            builder_instance_id,
            repository,
            candidate_scope,
            resource_scope,
            BUILDER_CAPABILITY_CLASS,
            "ADMITTED",
            "trusted-control-plane",
        )
        actual = (
            subject.builder_subject_id,
            subject.builder_instance_id,
            subject.repository,
            subject.candidate_scope,
            subject.resource_scope,
            subject.capability_class,
            subject.state,
            subject.source_kind,
        )
        if actual != expected:
            raise BuilderEntryPermitError("trusted builder subject binding mismatch")
        return subject


class BuilderEntryPermitEngine:
    """Issue one entry permit; never consume it or start a builder."""

    def __init__(
        self,
        *,
        live_authority: LiveResourceAuthorityAdmission,
        baseline_source: TrustedRepositoryBaselineSource,
        f005_state_source: F005StateSource,
        builder_source: PinnedTrustedBuilderSubjectSource,
        replay_guard: BuilderEntryReplayGuard,
    ):
        if type(live_authority) is not LiveResourceAuthorityAdmission:
            raise BuilderEntryPermitError("live authority admission required")
        if type(builder_source) is not PinnedTrustedBuilderSubjectSource:
            raise BuilderEntryPermitError("exact pinned trusted builder source required")
        if type(builder_source.backend) is not PinnedBuilderControlPlaneBackend:
            raise BuilderEntryPermitError("exact pinned builder backend required")
        builder_source.verify_origin()
        for obj, method in (
            (baseline_source, "current"),
            (f005_state_source, "current"),
            (replay_guard, "consume"),
        ):
            if not callable(getattr(obj, method, None)):
                raise BuilderEntryPermitError("builder entry dependency unavailable")
        self._live = live_authority
        self._baseline = baseline_source
        self._f005 = f005_state_source
        self._builders = builder_source
        self._replay = replay_guard

    @staticmethod
    def _permit(value: object) -> BuildAuthorizationConsumptionPermit:
        if type(value) is not BuildAuthorizationConsumptionPermit:
            raise BuilderEntryPermitError("exact consumption permit required")
        try:
            value.validate()
        except Exception as exc:
            raise BuilderEntryPermitError("consumption permit invalid") from exc
        if (
            not value.consumption_permit_digest
            or value.consumption_permit_digest != value.compute_digest()
        ):
            raise BuilderEntryPermitError("consumption permit must be sealed")
        if value.consumption_replay_digest != value.compute_consumption_replay_digest():
            raise BuilderEntryPermitError("source replay binding invalid")
        if (
            value.state != "CONSUMPTION_PERMIT_ISSUED"
            or value.action != "BUILD_CANDIDATE"
        ):
            raise BuilderEntryPermitError("source permit state/action invalid")
        return value

    @staticmethod
    def _live_receipt(value: object) -> LiveAdmittedResourceAuthority:
        if type(value) is not LiveAdmittedResourceAuthority:
            raise BuilderEntryPermitError("exact live authority receipt required")
        try:
            value.validate()
        except Exception as exc:
            raise BuilderEntryPermitError("live authority receipt invalid") from exc
        return value

    @staticmethod
    def _f005_ok(value: Mapping[str, Any]) -> None:
        if (
            not isinstance(value, Mapping)
            or value.get("state") != "QUARANTINED"
            or value.get("effect_authority") != "DENY"
        ):
            raise BuilderEntryPermitError("F005 quarantine invariant failed")

    @staticmethod
    def _trusted_subject(
        value: object,
        *,
        builder_subject_id: str,
        builder_instance_id: str,
        repository: str,
        candidate_scope: tuple[str, ...],
        resource_scope: tuple[str, ...],
    ) -> TrustedBuilderSubject:
        if type(value) is not TrustedBuilderSubject:
            raise BuilderEntryPermitError("trusted builder subject type invalid")
        try:
            value.validate()
        except Exception as exc:
            raise BuilderEntryPermitError("trusted builder subject invalid") from exc
        if not value.subject_digest or value.subject_digest != value.compute_digest():
            raise BuilderEntryPermitError("trusted builder subject must be sealed")
        expected = (
            builder_subject_id,
            builder_instance_id,
            repository,
            candidate_scope,
            resource_scope,
            BUILDER_CAPABILITY_CLASS,
            "ADMITTED",
            "trusted-control-plane",
        )
        actual = (
            value.builder_subject_id,
            value.builder_instance_id,
            value.repository,
            value.candidate_scope,
            value.resource_scope,
            value.capability_class,
            value.state,
            value.source_kind,
        )
        if actual != expected:
            raise BuilderEntryPermitError(
                "trusted builder subject request binding mismatch"
            )
        return value

    def issue_permit(
        self,
        *,
        source_permit: BuildAuthorizationConsumptionPermit,
        admitted_authority: LiveAdmittedResourceAuthority,
        builder_subject_id: str,
        builder_instance_id: str,
        trusted_now: datetime,
    ) -> BuilderEntryPermit:
        permit = self._permit(source_permit)
        admitted = self._live_receipt(admitted_authority)
        if not isinstance(trusted_now, datetime) or trusted_now.tzinfo is None:
            raise BuilderEntryPermitError("trusted_now must be timezone-aware")
        now = trusted_now.astimezone(timezone.utc)
        if now < _utc(
            permit.authorization_valid_from, "authorization valid_from"
        ) or now >= _utc(
            permit.authorization_expires_at, "authorization expires_at"
        ):
            raise BuilderEntryPermitError(
                "source authorization outside validity window"
            )

        current = self._baseline.current(permit.repository)
        if type(current) is not TrustedRepositoryBaseline:
            raise BuilderEntryPermitError("trusted baseline type invalid")
        current.validate()
        if (current.repository, current.master_sha, current.master_tree_sha) != (
            permit.repository,
            permit.baseline_master_sha,
            permit.baseline_master_tree_sha,
        ):
            raise BuilderEntryPermitError("builder-entry baseline stale")

        try:
            authority = self._live.revalidate(admitted, now=now)
        except Exception as exc:
            raise BuilderEntryPermitError(
                "current authority revalidation failed"
            ) from exc
        if type(authority) is not LiveAdmittedResourceAuthority:
            raise BuilderEntryPermitError("revalidated authority type invalid")
        authority.validate()
        expected_authority = (
            permit.repository,
            permit.grant_id,
            permit.leaf_grant_digest,
            permit.authority_lineage_digest,
            permit.authority_provenance_id,
            permit.authority_epoch,
            permit.authority_state_version,
            permit.root_grant_id,
            permit.root_grant_digest,
            permit.current_authority_digest,
            permit.resource_scope,
            "BUILD_CANDIDATE",
        )
        actual_authority = (
            authority.repository,
            authority.grant_id,
            authority.leaf_grant_digest,
            authority.lineage_digest,
            authority.provenance_id,
            authority.epoch,
            authority.epoch_state_version,
            authority.root_grant_id,
            authority.root_grant_digest,
            authority.digest(),
            authority.resource_scope,
            authority.action,
        )
        if actual_authority != expected_authority:
            raise BuilderEntryPermitError(
                "source permit/current authority mismatch"
            )

        self._f005_ok(self._f005.current())

        # Source origin and backend provenance are revalidated immediately before
        # subject resolution, and still before any replay state mutation.
        self._builders.verify_origin()
        if type(self._builders.backend) is not PinnedBuilderControlPlaneBackend:
            raise BuilderEntryPermitError("pinned builder backend drift")
        self._builders.backend.verify_origin()

        subject = self._builders.resolve_exact(
            builder_subject_id=builder_subject_id,
            builder_instance_id=builder_instance_id,
            repository=permit.repository,
            candidate_scope=permit.candidate_scope,
            resource_scope=permit.resource_scope,
        )
        subject = self._trusted_subject(
            subject,
            builder_subject_id=builder_subject_id,
            builder_instance_id=builder_instance_id,
            repository=permit.repository,
            candidate_scope=permit.candidate_scope,
            resource_scope=permit.resource_scope,
        )
        if now < _utc(subject.valid_from, "builder valid_from") or now >= _utc(
            subject.expires_at, "builder expires_at"
        ):
            raise BuilderEntryPermitError("builder subject outside validity window")

        current_baseline_digest = current.digest()
        current_authority_digest = authority.digest()
        kwargs = dict(
            source_consumption_permit_id=permit.consumption_permit_id,
            source_consumption_permit_digest=permit.consumption_permit_digest,
            source_consumption_replay_digest=permit.consumption_replay_digest,
            repository=permit.repository,
            baseline_master_sha=permit.baseline_master_sha,
            baseline_master_tree_sha=permit.baseline_master_tree_sha,
            current_baseline_digest=current_baseline_digest,
            action="BUILD_CANDIDATE",
            candidate_scope=permit.candidate_scope,
            resource_scope=permit.resource_scope,
            authority_epoch=permit.authority_epoch,
            authority_state_version=permit.authority_state_version,
            root_grant_id=permit.root_grant_id,
            root_grant_digest=permit.root_grant_digest,
            current_authority_digest=current_authority_digest,
            builder_subject_id=subject.builder_subject_id,
            builder_instance_id=subject.builder_instance_id,
            builder_capability_class=subject.capability_class,
            builder_identity_digest=subject.identity_digest,
            builder_implementation_digest=subject.implementation_digest,
            builder_attestation_digest=subject.attestation_digest,
        )
        replay = compute_builder_entry_replay_digest(**kwargs)
        checked_at = now.isoformat()
        if self._replay.consume(replay, consumed_at=checked_at) is not True:
            raise BuilderEntryPermitError("builder entry replay denied")
        return BuilderEntryPermit(
            schema_version=SCHEMA_VERSION,
            builder_entry_permit_id=f"bep:{replay}",
            checked_at=checked_at,
            builder_entry_replay_digest=replay,
            **kwargs,
        ).sealed()

    @classmethod
    def assert_no_effect_surface(cls) -> None:
        for name in _EFFECT_METHODS:
            if hasattr(cls, name):
                raise BuilderEntryPermitError(f"effect surface present: {name}")
