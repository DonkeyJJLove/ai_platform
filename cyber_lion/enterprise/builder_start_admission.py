"""Fail-closed, non-effectful builder start admission boundary."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
import sqlite3
from typing import Any, Protocol

from cyber_lion.contracts.builder_entry_permit import BUILDER_CAPABILITY_CLASS, TrustedBuilderSubject
from cyber_lion.contracts.builder_invocation_consumption import BuilderInvocationConsumptionPermit
from cyber_lion.contracts.builder_start_admission import (
    ADMISSION_STATE,
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
    PersistentBuilderInvocationIssuanceRecord,
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


def _canonical_json(value: object) -> str:
    payload = asdict(value)
    for name in ("candidate_scope", "resource_scope"):
        if name in payload:
            payload[name] = list(payload[name])
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


@dataclass(frozen=True)
class PersistentBuilderInvocationConsumptionIssuanceRecord:
    invocation_consumption_permit_id: str
    invocation_consumption_permit_digest: str
    invocation_consumption_replay_digest: str
    source_builder_invocation_permit_id: str
    source_builder_invocation_permit_digest: str
    source_builder_invocation_replay_digest: str
    source_builder_entry_permit_id: str
    source_builder_entry_permit_digest: str
    repository: str
    baseline_master_sha: str
    baseline_master_tree_sha: str
    current_baseline_digest: str
    action: str
    candidate_scope: tuple[str, ...]
    resource_scope: tuple[str, ...]
    authority_epoch: int
    authority_state_version: int
    root_grant_id: str
    root_grant_digest: str
    current_authority_digest: str
    builder_subject_id: str
    builder_instance_id: str
    builder_capability_class: str
    builder_identity_digest: str
    builder_implementation_digest: str
    builder_attestation_digest: str
    current_builder_subject_digest: str
    authority_store_origin_id: str
    authority_store_origin_digest: str
    issued_at: str

    def validate(self) -> "PersistentBuilderInvocationConsumptionIssuanceRecord":
        if not self.invocation_consumption_permit_id.startswith("bicp:"):
            raise BuilderStartAdmissionError("R20 issuance id invalid")
        if len(self.invocation_consumption_permit_digest) != 64 or len(self.invocation_consumption_replay_digest) != 64:
            raise BuilderStartAdmissionError("R20 issuance digest invalid")
        if self.authority_store_origin_id != f"aso:{self.authority_store_origin_digest}":
            raise BuilderStartAdmissionError("R20 issuance origin binding invalid")
        if self.action != "BUILD_CANDIDATE" or self.builder_capability_class != BUILDER_CAPABILITY_CLASS:
            raise BuilderStartAdmissionError("R20 issuance semantics invalid")
        return self


@dataclass(frozen=True)
class PersistentBuilderStartAdmissionIssuanceRecord:
    builder_start_admission_id: str
    builder_start_admission_digest: str
    builder_start_admission_replay_digest: str
    source_invocation_consumption_permit_id: str
    source_invocation_consumption_permit_digest: str
    source_invocation_consumption_replay_digest: str
    source_builder_invocation_permit_id: str
    source_builder_invocation_permit_digest: str
    source_builder_entry_permit_id: str
    source_builder_entry_permit_digest: str
    repository: str
    baseline_master_sha: str
    baseline_master_tree_sha: str
    current_baseline_digest: str
    action: str
    candidate_scope: tuple[str, ...]
    resource_scope: tuple[str, ...]
    authority_epoch: int
    authority_state_version: int
    root_grant_id: str
    root_grant_digest: str
    current_authority_digest: str
    builder_subject_id: str
    builder_instance_id: str
    builder_capability_class: str
    builder_identity_digest: str
    builder_implementation_digest: str
    builder_attestation_digest: str
    current_builder_subject_digest: str
    process_profile_id: str
    process_profile_digest: str
    launch_policy_digest: str
    authority_store_origin_id: str
    authority_store_origin_digest: str
    issued_at: str

    def validate(self) -> "PersistentBuilderStartAdmissionIssuanceRecord":
        if not self.builder_start_admission_id.startswith("bsa:"):
            raise BuilderStartAdmissionError("R21 issuance id invalid")
        if len(self.builder_start_admission_digest) != 64 or len(self.builder_start_admission_replay_digest) != 64:
            raise BuilderStartAdmissionError("R21 issuance digest invalid")
        if self.authority_store_origin_id != f"aso:{self.authority_store_origin_digest}":
            raise BuilderStartAdmissionError("R21 issuance origin binding invalid")
        if self.action != "BUILD_CANDIDATE" or self.builder_capability_class != BUILDER_CAPABILITY_CLASS:
            raise BuilderStartAdmissionError("R21 issuance semantics invalid")
        return self


class _R21Persistence:
    """Canonical-origin pinned R20/R21 artifact provenance stored beside authority state."""

    R20_TABLE = "builder_invocation_consumption_issuance"
    R21_TABLE = "builder_start_admission_issuance"

    def __init__(self) -> None:
        try:
            origin = verify_authority_state_store_origin()
        except Exception as exc:
            raise BuilderStartAdmissionError("canonical origin unavailable") from exc
        if type(origin) is not PersistentAuthorityStoreOrigin:
            raise BuilderStartAdmissionError("canonical origin invalid")
        self._origin = origin
        self._path = origin.canonical_database_path
        self._ensure_schema()

    def _current_origin(self) -> PersistentAuthorityStoreOrigin:
        try:
            current = verify_authority_state_store_origin()
        except Exception as exc:
            raise BuilderStartAdmissionError("canonical origin unavailable") from exc
        if current != self._origin:
            raise BuilderStartAdmissionError("canonical origin drift")
        return current

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._path, timeout=5, isolation_level=None, check_same_thread=False)
        connection.execute("PRAGMA journal_mode=WAL")
        return connection

    def _ensure_schema(self) -> None:
        self._current_origin()
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS builder_invocation_consumption_issuance (
                    permit_id TEXT NOT NULL PRIMARY KEY,
                    permit_digest TEXT NOT NULL UNIQUE,
                    replay_digest TEXT NOT NULL UNIQUE,
                    record_json TEXT NOT NULL,
                    issued_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS builder_start_admission_issuance (
                    admission_id TEXT NOT NULL PRIMARY KEY,
                    admission_digest TEXT NOT NULL UNIQUE,
                    replay_digest TEXT NOT NULL UNIQUE,
                    record_json TEXT NOT NULL,
                    issued_at TEXT NOT NULL
                );
                """
            )

    @staticmethod
    def _decode(record_json: str, cls: type) -> object:
        payload = json.loads(record_json)
        payload["candidate_scope"] = tuple(payload["candidate_scope"])
        payload["resource_scope"] = tuple(payload["resource_scope"])
        return cls(**payload).validate()

    def record_r20(self, record: PersistentBuilderInvocationConsumptionIssuanceRecord) -> None:
        record.validate()
        current = self._current_origin()
        if (record.authority_store_origin_id, record.authority_store_origin_digest) != (current.origin_id, current.origin_digest):
            raise BuilderStartAdmissionError("R20 issuance origin mismatch")
        try:
            with self._connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                connection.execute(
                    f"INSERT INTO {self.R20_TABLE} VALUES(?,?,?,?,?)",
                    (record.invocation_consumption_permit_id, record.invocation_consumption_permit_digest,
                     record.invocation_consumption_replay_digest, _canonical_json(record), record.issued_at),
                )
                connection.execute("COMMIT")
        except sqlite3.IntegrityError as exc:
            raise BuilderStartAdmissionError("R20 issuance already exists or conflicts") from exc

    def resolve_r20(self, permit_id: str) -> PersistentBuilderInvocationConsumptionIssuanceRecord:
        current = self._current_origin()
        with self._connect() as connection:
            rows = connection.execute(f"SELECT record_json FROM {self.R20_TABLE} WHERE permit_id=?", (permit_id,)).fetchall()
        if len(rows) != 1:
            raise BuilderStartAdmissionError("durable R20 issuance missing or ambiguous")
        record = self._decode(rows[0][0], PersistentBuilderInvocationConsumptionIssuanceRecord)
        if (record.authority_store_origin_id, record.authority_store_origin_digest) != (current.origin_id, current.origin_digest):
            raise BuilderStartAdmissionError("durable R20 issuance origin mismatch")
        return record

    def record_r21(self, record: PersistentBuilderStartAdmissionIssuanceRecord) -> None:
        record.validate()
        current = self._current_origin()
        if (record.authority_store_origin_id, record.authority_store_origin_digest) != (current.origin_id, current.origin_digest):
            raise BuilderStartAdmissionError("R21 issuance origin mismatch")
        try:
            with self._connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                connection.execute(
                    f"INSERT INTO {self.R21_TABLE} VALUES(?,?,?,?,?)",
                    (record.builder_start_admission_id, record.builder_start_admission_digest,
                     record.builder_start_admission_replay_digest, _canonical_json(record), record.issued_at),
                )
                connection.execute("COMMIT")
        except sqlite3.IntegrityError as exc:
            raise BuilderStartAdmissionError("R21 issuance already exists or conflicts") from exc

    def resolve_r21(self, admission_id: str) -> PersistentBuilderStartAdmissionIssuanceRecord:
        current = self._current_origin()
        with self._connect() as connection:
            rows = connection.execute(f"SELECT record_json FROM {self.R21_TABLE} WHERE admission_id=?", (admission_id,)).fetchall()
        if len(rows) != 1:
            raise BuilderStartAdmissionError("durable R21 issuance missing or ambiguous")
        record = self._decode(rows[0][0], PersistentBuilderStartAdmissionIssuanceRecord)
        if (record.authority_store_origin_id, record.authority_store_origin_digest) != (current.origin_id, current.origin_digest):
            raise BuilderStartAdmissionError("durable R21 issuance origin mismatch")
        return record


def record_builder_invocation_consumption_issuance(permit: BuilderInvocationConsumptionPermit) -> None:
    """Called by R20 only after replay consumption and sealing; failure is fail-closed."""
    if type(permit) is not BuilderInvocationConsumptionPermit:
        raise BuilderStartAdmissionError("exact R20 permit required")
    permit.validate()
    if not permit.invocation_consumption_permit_digest or permit.invocation_consumption_permit_digest != permit.compute_digest():
        raise BuilderStartAdmissionError("sealed R20 permit required")
    origin = verify_authority_state_store_origin()
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
    _R21Persistence().record_r20(record)


def resolve_builder_start_admission_issuance(admission_id: str) -> PersistentBuilderStartAdmissionIssuanceRecord:
    return _R21Persistence().resolve_r21(admission_id)


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


class BuilderStartAdmissionEngine:
    """Issue one durable non-effectful admission; never launch a process."""

    REPLAY_DOMAIN = "builder-start-admission"

    def __init__(
        self,
        *,
        live_authority: LiveResourceAuthorityAdmission,
        baseline_source: TrustedRepositoryBaselineSource,
        f005_state_source: F005StateSource,
        builder_source: PinnedTrustedBuilderSubjectSource,
    ) -> None:
        if type(live_authority) is not LiveResourceAuthorityAdmission:
            raise BuilderStartAdmissionError("live authority admission required")
        if type(builder_source) is not PinnedTrustedBuilderSubjectSource:
            raise BuilderStartAdmissionError("exact pinned builder source required")
        builder_source.verify_origin()
        for obj, method in ((baseline_source, "current"), (f005_state_source, "current")):
            if not callable(getattr(obj, method, None)):
                raise BuilderStartAdmissionError("R21 dependency unavailable")
        self._live = live_authority
        self._baseline = baseline_source
        self._f005 = f005_state_source
        self._builders = builder_source
        self._persistence = _R21Persistence()
        store = build_authority_state_store()
        if type(store) is not SQLiteAuthorityStateStore or not store.ready():
            raise BuilderStartAdmissionError("canonical authority store invalid")
        self._store = store

    def issue_admission(
        self,
        *,
        source_permit: BuilderInvocationConsumptionPermit,
        admitted_authority: LiveAdmittedResourceAuthority,
        trusted_now: datetime,
    ) -> BuilderStartAdmission:
        permit = _sealed_r20(source_permit)
        if type(admitted_authority) is not LiveAdmittedResourceAuthority:
            raise BuilderStartAdmissionError("exact live authority receipt required")
        admitted_authority.validate()
        if not isinstance(trusted_now, datetime) or trusted_now.tzinfo is None:
            raise BuilderStartAdmissionError("trusted_now must be timezone-aware")
        now = trusted_now.astimezone(timezone.utc)

        origin = verify_authority_state_store_origin()
        r20 = self._persistence.resolve_r20(permit.invocation_consumption_permit_id)
        exact_r20 = (
            r20.invocation_consumption_permit_id, r20.invocation_consumption_permit_digest,
            r20.invocation_consumption_replay_digest, r20.source_builder_invocation_permit_id,
            r20.source_builder_invocation_permit_digest, r20.source_builder_invocation_replay_digest,
            r20.source_builder_entry_permit_id, r20.source_builder_entry_permit_digest,
            r20.repository, r20.baseline_master_sha, r20.baseline_master_tree_sha, r20.current_baseline_digest,
            r20.action, r20.candidate_scope, r20.resource_scope, r20.authority_epoch, r20.authority_state_version,
            r20.root_grant_id, r20.root_grant_digest, r20.current_authority_digest, r20.builder_subject_id,
            r20.builder_instance_id, r20.builder_capability_class, r20.builder_identity_digest,
            r20.builder_implementation_digest, r20.builder_attestation_digest, r20.current_builder_subject_digest,
            r20.issued_at,
        )
        exact_permit = (
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
        if exact_r20 != exact_permit:
            raise BuilderStartAdmissionError("R20 durable artifact provenance mismatch")

        r19 = self._store.resolve_builder_invocation_issuance(permit.source_builder_invocation_permit_id)
        if type(r19) is not PersistentBuilderInvocationIssuanceRecord:
            raise BuilderStartAdmissionError("exact durable R19 ancestor required")
        r19.validate()
        if (
            permit.source_builder_invocation_permit_id,
            permit.source_builder_invocation_permit_digest,
            permit.source_builder_invocation_replay_digest,
        ) != (
            r19.builder_invocation_permit_id,
            r19.builder_invocation_permit_digest,
            r19.builder_invocation_replay_digest,
        ):
            raise BuilderStartAdmissionError("R20/R19 ancestry mismatch")
        r17 = self._store.resolve_builder_entry_issuance(r19.source_builder_entry_permit_id)
        if type(r17) is not PersistentBuilderEntryIssuanceRecord:
            raise BuilderStartAdmissionError("exact durable R17 ancestor required")
        r17.validate()
        if (
            permit.source_builder_entry_permit_id, permit.source_builder_entry_permit_digest,
            r19.source_builder_entry_permit_id, r19.source_builder_entry_permit_digest,
        ) != (
            r17.builder_entry_permit_id, r17.builder_entry_permit_digest,
            r17.builder_entry_permit_id, r17.builder_entry_permit_digest,
        ):
            raise BuilderStartAdmissionError("R19/R17 ancestry mismatch")
        if (
            r20.authority_store_origin_id, r20.authority_store_origin_digest,
            r19.authority_store_origin_id, r19.authority_store_origin_digest,
            r17.authority_store_origin_id, r17.authority_store_origin_digest,
        ) != (
            origin.origin_id, origin.origin_digest,
            origin.origin_id, origin.origin_digest,
            origin.origin_id, origin.origin_digest,
        ):
            raise BuilderStartAdmissionError("transitive provenance origin mismatch")

        current = self._baseline.current(permit.repository)
        if type(current) is not TrustedRepositoryBaseline:
            raise BuilderStartAdmissionError("trusted baseline type invalid")
        current.validate()
        if (current.repository, current.master_sha, current.master_tree_sha, current.digest()) != (
            permit.repository, permit.baseline_master_sha, permit.baseline_master_tree_sha, permit.current_baseline_digest
        ):
            raise BuilderStartAdmissionError("R21 baseline stale")

        try:
            authority = self._live.revalidate(admitted_authority, now=now)
        except Exception as exc:
            raise BuilderStartAdmissionError("R21 authority currentness failed") from exc
        authority.validate()
        if (
            authority.repository, authority.epoch, authority.epoch_state_version, authority.root_grant_id,
            authority.root_grant_digest, authority.digest(), authority.resource_scope, authority.action,
        ) != (
            permit.repository, permit.authority_epoch, permit.authority_state_version, permit.root_grant_id,
            permit.root_grant_digest, permit.current_authority_digest, permit.resource_scope, "BUILD_CANDIDATE",
        ):
            raise BuilderStartAdmissionError("R21 authority mismatch")

        self._builders.verify_origin()
        subject = _sealed_subject(self._builders.resolve_exact(
            builder_subject_id=permit.builder_subject_id,
            builder_instance_id=permit.builder_instance_id,
            repository=permit.repository,
            candidate_scope=permit.candidate_scope,
            resource_scope=permit.resource_scope,
        ))
        if (
            subject.builder_subject_id, subject.builder_instance_id, subject.capability_class,
            subject.identity_digest, subject.implementation_digest, subject.attestation_digest, subject.subject_digest,
            subject.repository, subject.candidate_scope, subject.resource_scope, subject.state, subject.source_kind,
        ) != (
            permit.builder_subject_id, permit.builder_instance_id, permit.builder_capability_class,
            permit.builder_identity_digest, permit.builder_implementation_digest, permit.builder_attestation_digest,
            permit.current_builder_subject_digest, permit.repository, permit.candidate_scope, permit.resource_scope,
            "ADMITTED", "trusted-control-plane",
        ):
            raise BuilderStartAdmissionError("R21 builder currentness mismatch")
        if now < _utc(subject.valid_from) or now >= _utc(subject.expires_at):
            raise BuilderStartAdmissionError("builder outside validity window")

        profile_kwargs = dict(
            repository=permit.repository,
            action="BUILD_CANDIDATE",
            candidate_scope=permit.candidate_scope,
            resource_scope=permit.resource_scope,
            builder_subject_id=subject.builder_subject_id,
            builder_instance_id=subject.builder_instance_id,
            builder_capability_class=subject.capability_class,
            builder_identity_digest=subject.identity_digest,
            builder_implementation_digest=subject.implementation_digest,
            builder_attestation_digest=subject.attestation_digest,
            current_builder_subject_digest=subject.subject_digest,
        )
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
            process_profile_id=process_profile_id,
            process_profile_digest=process_profile_digest,
            launch_policy_digest=launch_policy_digest,
        )
        replay = compute_builder_start_admission_replay_digest(**kwargs)
        checked_at = now.isoformat()
        if self._store.consume_replay(self.REPLAY_DOMAIN, replay, checked_at) is not True:
            raise BuilderStartAdmissionError("builder start admission replay denied")
        admission = BuilderStartAdmission(
            schema_version=SCHEMA_VERSION,
            builder_start_admission_id=f"bsa:{replay}",
            builder_start_admission_replay_digest=replay,
            checked_at=checked_at,
            **kwargs,
        ).sealed()

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
            repository=admission.repository,
            baseline_master_sha=admission.baseline_master_sha,
            baseline_master_tree_sha=admission.baseline_master_tree_sha,
            current_baseline_digest=admission.current_baseline_digest,
            action=admission.action,
            candidate_scope=admission.candidate_scope,
            resource_scope=admission.resource_scope,
            authority_epoch=admission.authority_epoch,
            authority_state_version=admission.authority_state_version,
            root_grant_id=admission.root_grant_id,
            root_grant_digest=admission.root_grant_digest,
            current_authority_digest=admission.current_authority_digest,
            builder_subject_id=admission.builder_subject_id,
            builder_instance_id=admission.builder_instance_id,
            builder_capability_class=admission.builder_capability_class,
            builder_identity_digest=admission.builder_identity_digest,
            builder_implementation_digest=admission.builder_implementation_digest,
            builder_attestation_digest=admission.builder_attestation_digest,
            current_builder_subject_digest=admission.current_builder_subject_digest,
            process_profile_id=admission.process_profile_id,
            process_profile_digest=admission.process_profile_digest,
            launch_policy_digest=admission.launch_policy_digest,
            authority_store_origin_id=current_origin.origin_id,
            authority_store_origin_digest=current_origin.origin_digest,
            issued_at=admission.checked_at,
        ).validate()
        self._persistence.record_r21(record)
        return admission

    @classmethod
    def assert_no_effect_surface(cls) -> None:
        for name in _EFFECT_METHODS:
            if hasattr(cls, name):
                raise BuilderStartAdmissionError(f"effect surface present: {name}")
