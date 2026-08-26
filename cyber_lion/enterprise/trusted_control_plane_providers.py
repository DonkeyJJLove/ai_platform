"""Concrete persistent providers for the trusted control-plane service."""
from __future__ import annotations

from collections.abc import Callable, Mapping
from hashlib import sha256
import inspect
import json
from pathlib import Path
import sqlite3
from threading import RLock

from .trusted_control_plane_service import (
    TrustedControlPlaneStore,
    TrustedSignatureVerifier,
    TrustedControlPlaneServiceError,
    validate_maintenance_mission_record,
    validate_maintenance_policy_record,
)


class TrustedControlPlaneProviderError(RuntimeError):
    pass


_RUNTIME_IMPL_DOMAIN = b"LION/E004-BUILDER-RUNTIME-IMPLEMENTATION/1\0"
_RUNTIME_RESOLVER_DOMAIN = b"LION/E004-BUILDER-RUNTIME-RESOLVER/1\0"
_PROVIDER_SOURCE_ORIGIN_DOMAIN = b"LION/E004-BUILDER-RUNTIME-SOURCE-ORIGIN/1\0"
_MAINTENANCE_SOURCE_ORIGIN_DOMAIN = b"LION/E006-R9D8L-MAINTENANCE-STATE-SOURCE/1\0"
_DATABASE_IDENTITY_DOMAIN = b"LION/E004-TRUSTED-CONTROL-PLANE-DATABASE/1\0"


def _canonical_json(value: Mapping[str, object]) -> str:
    if not isinstance(value, Mapping):
        raise TrustedControlPlaneProviderError("provider record must be a mapping")
    return json.dumps(dict(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _decode_record(raw: object) -> dict[str, object]:
    try:
        value = json.loads(raw)
    except (TypeError, json.JSONDecodeError) as exc:
        raise TrustedControlPlaneProviderError("persistent provider record is corrupt") from exc
    if not isinstance(value, Mapping):
        raise TrustedControlPlaneProviderError("persistent provider record is not an object")
    return dict(value)


def _digest(value: object, label: str) -> str:
    if not isinstance(value, str) or len(value) != 64:
        raise TrustedControlPlaneProviderError(f"{label} invalid")
    try:
        int(value, 16)
    except ValueError as exc:
        raise TrustedControlPlaneProviderError(f"{label} invalid") from exc
    if value.lower() != value:
        raise TrustedControlPlaneProviderError(f"{label} invalid")
    return value


def compute_runtime_provider_implementation_digest(runtime_or_type: object) -> str:
    cls = runtime_or_type if isinstance(runtime_or_type, type) else type(runtime_or_type)
    try:
        source = inspect.getsource(cls)
    except (OSError, TypeError) as exc:
        raise TrustedControlPlaneProviderError("runtime provider implementation is not inspectable") from exc
    return sha256(_RUNTIME_IMPL_DOMAIN + source.encode("utf-8")).hexdigest()


def _callable_implementation_digest(callback: Callable[..., object]) -> str:
    try:
        source = inspect.getsource(callback)
    except (OSError, TypeError) as exc:
        raise TrustedControlPlaneProviderError("runtime resolver implementation is not inspectable") from exc
    return sha256(_RUNTIME_RESOLVER_DOMAIN + source.encode("utf-8")).hexdigest()


class SQLiteTrustedControlPlaneStore(TrustedControlPlaneStore):
    BUILDER_LOOKUP_FIELDS = (
        "repository",
        "builder_subject_id",
        "builder_instance_id",
        "candidate_scope_digest",
        "resource_scope_digest",
        "capability_class",
    )
    RUNTIME_PROVIDER_LOOKUP_FIELDS = (
        "provider_id",
        "process_profile_digest",
        "launch_policy_digest",
        "capability_class",
    )
    MAINTENANCE_POLICY_LOOKUP_FIELDS = ("repository", "mission_id", "policy_id")
    MAINTENANCE_MISSION_LOOKUP_FIELDS = ("repository", "mission_id")

    def __init__(self, database_path: str) -> None:
        if not isinstance(database_path, str) or not database_path.strip():
            raise TrustedControlPlaneProviderError("database_path is required")
        self._path = str(Path(database_path))
        self._lock = RLock()
        self._initialize()

    def database_identity(self) -> str:
        path = str(Path(self._path).resolve())
        return sha256(_DATABASE_IDENTITY_DOMAIN + path.encode("utf-8")).hexdigest()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._path, timeout=5, isolation_level=None)
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA journal_mode=WAL")
        return connection

    def _initialize(self) -> None:
        with self._lock, self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS pr_bootstrap(
                    repository TEXT NOT NULL,
                    pr_number INTEGER NOT NULL,
                    base_sha TEXT NOT NULL,
                    head_sha TEXT NOT NULL,
                    merge_method TEXT NOT NULL,
                    record_json TEXT NOT NULL,
                    PRIMARY KEY(repository,pr_number,base_sha,head_sha,merge_method,record_json)
                );
                CREATE TABLE IF NOT EXISTS authority_lineage(
                    repository TEXT NOT NULL,
                    pr_number INTEGER NOT NULL,
                    base_sha TEXT NOT NULL,
                    head_sha TEXT NOT NULL,
                    mission_id TEXT NOT NULL,
                    grant_id TEXT NOT NULL,
                    record_json TEXT NOT NULL,
                    PRIMARY KEY(repository,pr_number,base_sha,head_sha,mission_id,grant_id,record_json)
                );
                CREATE TABLE IF NOT EXISTS builder_subject(
                    repository TEXT NOT NULL,
                    builder_subject_id TEXT NOT NULL,
                    builder_instance_id TEXT NOT NULL,
                    candidate_scope_digest TEXT NOT NULL,
                    resource_scope_digest TEXT NOT NULL,
                    capability_class TEXT NOT NULL,
                    record_json TEXT NOT NULL,
                    PRIMARY KEY(repository,builder_subject_id,builder_instance_id,candidate_scope_digest,resource_scope_digest,capability_class,record_json)
                );
                CREATE TABLE IF NOT EXISTS builder_process_runtime_provider(
                    provider_id TEXT NOT NULL,
                    process_profile_digest TEXT NOT NULL,
                    launch_policy_digest TEXT NOT NULL,
                    capability_class TEXT NOT NULL,
                    record_json TEXT NOT NULL,
                    PRIMARY KEY(provider_id,process_profile_digest,launch_policy_digest,capability_class,record_json)
                );
                CREATE TABLE IF NOT EXISTS maintenance_policy(
                    repository TEXT NOT NULL,
                    mission_id TEXT NOT NULL,
                    policy_id TEXT NOT NULL,
                    revision TEXT NOT NULL,
                    active INTEGER NOT NULL CHECK(active IN (0,1)),
                    record_json TEXT NOT NULL,
                    PRIMARY KEY(repository,mission_id,policy_id,revision,record_json)
                );
                CREATE TABLE IF NOT EXISTS maintenance_mission(
                    repository TEXT NOT NULL,
                    mission_id TEXT NOT NULL,
                    record_json TEXT NOT NULL,
                    PRIMARY KEY(repository,mission_id,record_json)
                );
                """
            )

    @staticmethod
    def _lookup(record: Mapping[str, object], fields: tuple[str, ...], label: str) -> Mapping[str, object]:
        lookup = record.get("lookup_key") if isinstance(record, Mapping) else None
        if not isinstance(lookup, Mapping) or frozenset(lookup.keys()) != frozenset(fields):
            raise TrustedControlPlaneProviderError(f"{label} lookup_key invalid")
        return lookup

    def put_pr_bootstrap(self, record: Mapping[str, object]) -> None:
        fields = ("repository", "pr_number", "base_sha", "head_sha", "merge_method")
        lookup = self._lookup(record, fields, "bootstrap")
        raw = _canonical_json(record)
        with self._lock, self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute("INSERT OR IGNORE INTO pr_bootstrap VALUES(?,?,?,?,?,?)", tuple(lookup[name] for name in fields) + (raw,))
            connection.execute("COMMIT")

    def put_authority_record(self, record: Mapping[str, object]) -> None:
        fields = ("repository", "pr_number", "base_sha", "head_sha", "mission_id", "grant_id")
        lookup = self._lookup(record, fields, "authority")
        raw = _canonical_json(record)
        with self._lock, self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute("INSERT OR IGNORE INTO authority_lineage VALUES(?,?,?,?,?,?,?)", tuple(lookup[name] for name in fields) + (raw,))
            connection.execute("COMMIT")

    def put_builder_subject_record(self, record: Mapping[str, object]) -> None:
        fields = self.BUILDER_LOOKUP_FIELDS
        lookup = self._lookup(record, fields, "builder subject")
        if record.get("record_kind") != "builder-subject" or not isinstance(record.get("subject"), Mapping):
            raise TrustedControlPlaneProviderError("builder subject record invalid")
        raw = _canonical_json(record)
        with self._lock, self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute("INSERT OR IGNORE INTO builder_subject VALUES(?,?,?,?,?,?,?)", tuple(lookup[name] for name in fields) + (raw,))
            connection.execute("COMMIT")

    def put_builder_process_runtime_provider_record(self, record: Mapping[str, object]) -> None:
        fields = self.RUNTIME_PROVIDER_LOOKUP_FIELDS
        lookup = self._lookup(record, fields, "builder process runtime provider")
        if record.get("record_kind") != "builder-process-runtime-provider" or not isinstance(record.get("provider"), Mapping):
            raise TrustedControlPlaneProviderError("runtime provider record invalid")
        raw = _canonical_json(record)
        with self._lock, self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute("INSERT OR IGNORE INTO builder_process_runtime_provider VALUES(?,?,?,?,?)", tuple(lookup[name] for name in fields) + (raw,))
            connection.execute("COMMIT")

    def put_maintenance_policy_record(self, record: Mapping[str, object]) -> None:
        """Administrative provisioning primitive; never called by maintenance execution."""
        fields = self.MAINTENANCE_POLICY_LOOKUP_FIELDS
        lookup = self._lookup(record, fields, "maintenance policy")
        try:
            canonical = validate_maintenance_policy_record(record, expected_binding=dict(lookup))
        except TrustedControlPlaneServiceError as exc:
            raise TrustedControlPlaneProviderError("maintenance policy record invalid") from exc
        raw = _canonical_json(canonical)
        revision = canonical["revision"]
        active = 1 if canonical["active"] is True else 0
        with self._lock, self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                "INSERT OR IGNORE INTO maintenance_policy(repository,mission_id,policy_id,revision,active,record_json) VALUES(?,?,?,?,?,?)",
                (lookup["repository"], lookup["mission_id"], lookup["policy_id"], revision, active, raw),
            )
            connection.execute("COMMIT")

    def put_maintenance_mission_record(self, record: Mapping[str, object]) -> None:
        """Administrative provisioning primitive; never called by maintenance execution."""
        fields = self.MAINTENANCE_MISSION_LOOKUP_FIELDS
        lookup = self._lookup(record, fields, "maintenance mission")
        try:
            canonical = validate_maintenance_mission_record(record, expected_binding=dict(lookup))
        except TrustedControlPlaneServiceError as exc:
            raise TrustedControlPlaneProviderError("maintenance mission record invalid") from exc
        raw = _canonical_json(canonical)
        with self._lock, self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                "INSERT OR IGNORE INTO maintenance_mission(repository,mission_id,record_json) VALUES(?,?,?)",
                (lookup["repository"], lookup["mission_id"], raw),
            )
            connection.execute("COMMIT")

    def lookup_pr_bootstrap_exact(self, *, repository: str, pr_number: int, base_sha: str, head_sha: str, merge_method: str) -> tuple[Mapping[str, object], ...]:
        with self._lock, self._connect() as connection:
            rows = connection.execute(
                "SELECT record_json FROM pr_bootstrap WHERE repository=? AND pr_number=? AND base_sha=? AND head_sha=? AND merge_method=? ORDER BY record_json",
                (repository, pr_number, base_sha, head_sha, merge_method),
            ).fetchall()
        return tuple(_decode_record(row[0]) for row in rows)

    def lookup_authority_exact(self, *, repository: str, pr_number: int, base_sha: str, head_sha: str, mission_id: str, grant_id: str) -> tuple[Mapping[str, object], ...]:
        with self._lock, self._connect() as connection:
            rows = connection.execute(
                "SELECT record_json FROM authority_lineage WHERE repository=? AND pr_number=? AND base_sha=? AND head_sha=? AND mission_id=? AND grant_id=? ORDER BY record_json",
                (repository, pr_number, base_sha, head_sha, mission_id, grant_id),
            ).fetchall()
        return tuple(_decode_record(row[0]) for row in rows)

    def lookup_builder_subject_exact(self, *, repository: str, builder_subject_id: str, builder_instance_id: str, candidate_scope_digest: str, resource_scope_digest: str, capability_class: str) -> tuple[Mapping[str, object], ...]:
        with self._lock, self._connect() as connection:
            rows = connection.execute(
                "SELECT record_json FROM builder_subject WHERE repository=? AND builder_subject_id=? AND builder_instance_id=? AND candidate_scope_digest=? AND resource_scope_digest=? AND capability_class=? ORDER BY record_json",
                (repository, builder_subject_id, builder_instance_id, candidate_scope_digest, resource_scope_digest, capability_class),
            ).fetchall()
        return tuple(_decode_record(row[0]) for row in rows)

    def lookup_builder_process_runtime_provider_exact(self, *, provider_id: str, process_profile_digest: str, launch_policy_digest: str, capability_class: str) -> tuple[Mapping[str, object], ...]:
        with self._lock, self._connect() as connection:
            rows = connection.execute(
                "SELECT record_json FROM builder_process_runtime_provider WHERE provider_id=? AND process_profile_digest=? AND launch_policy_digest=? AND capability_class=? ORDER BY record_json",
                (provider_id, process_profile_digest, launch_policy_digest, capability_class),
            ).fetchall()
        return tuple(_decode_record(row[0]) for row in rows)

    def lookup_maintenance_policy_exact(self, *, repository: str, mission_id: str, policy_id: str) -> tuple[Mapping[str, object], ...]:
        with self._lock, self._connect() as connection:
            rows = connection.execute(
                "SELECT record_json FROM maintenance_policy WHERE repository=? AND mission_id=? AND policy_id=? AND active=1 ORDER BY revision,record_json",
                (repository, mission_id, policy_id),
            ).fetchall()
        return tuple(_decode_record(row[0]) for row in rows)

    def lookup_maintenance_mission_exact(self, *, repository: str, mission_id: str) -> tuple[Mapping[str, object], ...]:
        with self._lock, self._connect() as connection:
            rows = connection.execute(
                "SELECT record_json FROM maintenance_mission WHERE repository=? AND mission_id=? ORDER BY record_json",
                (repository, mission_id),
            ).fetchall()
        return tuple(_decode_record(row[0]) for row in rows)

    def ready(self) -> bool:
        try:
            with self._connect() as connection:
                names = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            return {
                "pr_bootstrap",
                "authority_lineage",
                "builder_subject",
                "builder_process_runtime_provider",
                "maintenance_policy",
                "maintenance_mission",
            }.issubset(names)
        except Exception:
            return False


class PinnedMaintenanceStateSource:
    """Capability-reduced read-only maintenance state reader bound to one external DB origin."""

    __slots__ = ("_store", "_database_identity", "_source_origin_digest", "_source_origin_id")

    def __init__(self, store: SQLiteTrustedControlPlaneStore) -> None:
        if type(store) is not SQLiteTrustedControlPlaneStore or store.ready() is not True:
            raise TrustedControlPlaneProviderError("trusted maintenance state source unavailable")
        self._store = store
        self._database_identity = store.database_identity()
        self._source_origin_digest = sha256(
            _MAINTENANCE_SOURCE_ORIGIN_DOMAIN + self._database_identity.encode("ascii")
        ).hexdigest()
        self._source_origin_id = f"maintenance-state:{self._source_origin_digest}"
        self.verify_origin()

    @property
    def source_origin_id(self) -> str:
        return self._source_origin_id

    @property
    def source_origin_digest(self) -> str:
        return self._source_origin_digest

    def verify_origin(self) -> bool:
        if self._store.ready() is not True or self._store.database_identity() != self._database_identity:
            raise TrustedControlPlaneProviderError("maintenance state source database origin drift")
        expected = sha256(_MAINTENANCE_SOURCE_ORIGIN_DOMAIN + self._database_identity.encode("ascii")).hexdigest()
        if expected != self._source_origin_digest or self._source_origin_id != f"maintenance-state:{expected}":
            raise TrustedControlPlaneProviderError("maintenance state source origin mismatch")
        return True

    def resolve_maintenance_policy_exact(self, *, repository: str, mission_id: str, policy_id: str):
        from cyber_lion.contracts.policy_gate import PolicyRevision

        self.verify_origin()
        binding = {"repository": repository, "mission_id": mission_id, "policy_id": policy_id}
        rows = self._store.lookup_maintenance_policy_exact(**binding)
        if len(rows) != 1:
            raise TrustedControlPlaneProviderError("maintenance policy record missing or ambiguous")
        try:
            record = validate_maintenance_policy_record(rows[0], expected_binding=binding)
            policy = PolicyRevision(**dict(record["policy_payload"])).validate()
        except Exception as exc:
            raise TrustedControlPlaneProviderError("maintenance policy record invalid") from exc
        self.verify_origin()
        return policy, record["provenance_ref"], self._source_origin_id

    def resolve_maintenance_mission_exact(self, *, repository: str, mission_id: str):
        from cyber_lion.enterprise.models import MissionSpec

        self.verify_origin()
        binding = {"repository": repository, "mission_id": mission_id}
        rows = self._store.lookup_maintenance_mission_exact(**binding)
        if len(rows) != 1:
            raise TrustedControlPlaneProviderError("maintenance mission record missing or ambiguous")
        try:
            record = validate_maintenance_mission_record(rows[0], expected_binding=binding)
            payload = dict(record["mission_payload"])
            payload["required_capabilities"] = tuple(payload["required_capabilities"])
            mission = MissionSpec(**payload).validate()
        except Exception as exc:
            raise TrustedControlPlaneProviderError("maintenance mission record invalid") from exc
        self.verify_origin()
        return mission, record["provenance_ref"], self._source_origin_id


class PinnedRuntimeResolver:
    """Pinned executable resolver identity; arbitrary callables are not a source authority."""

    __slots__ = ("_resolver", "implementation_identity", "attestation_digest")

    def __init__(self, resolver: Callable[..., object], *, implementation_identity: str, attestation_digest: str) -> None:
        if not callable(resolver):
            raise TrustedControlPlaneProviderError("runtime resolver unavailable")
        _digest(implementation_identity, "runtime resolver implementation identity")
        _digest(attestation_digest, "runtime resolver attestation digest")
        actual = _callable_implementation_digest(resolver)
        if actual != implementation_identity:
            raise TrustedControlPlaneProviderError("runtime resolver implementation binding mismatch")
        self._resolver = resolver
        self.implementation_identity = implementation_identity
        self.attestation_digest = attestation_digest

    def resolve(self, runtime_instance_identity: str):
        return self._resolver(runtime_instance_identity)

    def verify(self) -> bool:
        if _callable_implementation_digest(self._resolver) != self.implementation_identity:
            raise TrustedControlPlaneProviderError("runtime resolver implementation drift")
        _digest(self.attestation_digest, "runtime resolver attestation digest")
        return True


class PinnedBuilderProcessRuntimeProviderSource:
    __slots__ = ("_store", "_runtime_resolver", "_database_identity", "_source_origin_digest", "_source_origin_id")

    def __init__(self, store: SQLiteTrustedControlPlaneStore, *, runtime_resolver: PinnedRuntimeResolver) -> None:
        if type(store) is not SQLiteTrustedControlPlaneStore or store.ready() is not True or type(runtime_resolver) is not PinnedRuntimeResolver:
            raise TrustedControlPlaneProviderError("trusted runtime provider source unavailable")
        self._store = store
        self._runtime_resolver = runtime_resolver
        self._database_identity = store.database_identity()
        self._source_origin_digest = self._compute_origin_digest()
        self._source_origin_id = f"bprps:{self._source_origin_digest}"
        self.verify_origin()

    @property
    def source_origin_id(self) -> str:
        return self._source_origin_id

    @property
    def source_origin_digest(self) -> str:
        return self._source_origin_digest

    def _compute_origin_digest(self) -> str:
        payload = "\n".join((self._store.database_identity(), self._runtime_resolver.implementation_identity, self._runtime_resolver.attestation_digest)).encode("utf-8")
        return sha256(_PROVIDER_SOURCE_ORIGIN_DOMAIN + payload).hexdigest()

    def verify_origin(self) -> bool:
        if self._store.ready() is not True or self._store.database_identity() != self._database_identity:
            raise TrustedControlPlaneProviderError("runtime provider source database origin drift")
        self._runtime_resolver.verify()
        if self._compute_origin_digest() != self._source_origin_digest or self._source_origin_id != f"bprps:{self._source_origin_digest}":
            raise TrustedControlPlaneProviderError("runtime provider source origin mismatch")
        return True

    def resolve_exact(self, *, provider_id: str, process_profile_digest: str, launch_policy_digest: str):
        from cyber_lion.contracts.builder_process_launch import BuilderProcessRuntimeProviderDescriptor, PROVIDER_CAPABILITY_CLASS, PREPARE_CAPABILITY_CLASS

        self.verify_origin()
        rows = self._store.lookup_builder_process_runtime_provider_exact(
            provider_id=provider_id,
            process_profile_digest=process_profile_digest,
            launch_policy_digest=launch_policy_digest,
            capability_class=PROVIDER_CAPABILITY_CLASS,
        )
        if len(rows) != 1:
            raise TrustedControlPlaneProviderError("runtime provider record missing or ambiguous")
        record = rows[0]
        payload = record.get("provider")
        if record.get("record_kind") != "builder-process-runtime-provider" or not isinstance(payload, Mapping):
            raise TrustedControlPlaneProviderError("runtime provider record invalid")
        try:
            descriptor = BuilderProcessRuntimeProviderDescriptor(**dict(payload)).validate()
        except Exception as exc:
            raise TrustedControlPlaneProviderError("runtime provider descriptor invalid") from exc
        expected = {
            "provider_id": provider_id,
            "process_profile_digest": process_profile_digest,
            "launch_policy_digest": launch_policy_digest,
            "capability_class": PROVIDER_CAPABILITY_CLASS,
        }
        if descriptor.descriptor_digest != descriptor.compute_digest() or dict(record.get("lookup_key", {})) != expected:
            raise TrustedControlPlaneProviderError("runtime provider binding invalid")
        if (
            descriptor.provider_id,
            descriptor.supported_process_profile_digest,
            descriptor.supported_launch_policy_digest,
            descriptor.capability_class,
            descriptor.prepare_capability_class,
        ) != (provider_id, process_profile_digest, launch_policy_digest, PROVIDER_CAPABILITY_CLASS, PREPARE_CAPABILITY_CLASS):
            raise TrustedControlPlaneProviderError("runtime provider semantic binding mismatch")
        self.verify_origin()
        return descriptor

    def resolve_bound_runtime(self, *, provider_id: str, process_profile_digest: str, launch_policy_digest: str):
        self.verify_origin()
        descriptor = self.resolve_exact(provider_id=provider_id, process_profile_digest=process_profile_digest, launch_policy_digest=launch_policy_digest)
        try:
            runtime = self._runtime_resolver.resolve(descriptor.runtime_instance_identity)
        except Exception as exc:
            raise TrustedControlPlaneProviderError("runtime provider instance unavailable") from exc
        if runtime is None or getattr(runtime, "descriptor", None) != descriptor or getattr(runtime, "runtime_instance_identity", None) != descriptor.runtime_instance_identity:
            raise TrustedControlPlaneProviderError("runtime provider instance binding mismatch")
        if getattr(runtime, "provider_identity_digest", None) != descriptor.provider_identity_digest or getattr(runtime, "provider_attestation_digest", None) != descriptor.provider_attestation_digest:
            raise TrustedControlPlaneProviderError("runtime provider executable identity/attestation mismatch")
        actual_impl = compute_runtime_provider_implementation_digest(runtime)
        if actual_impl != descriptor.provider_implementation_digest or getattr(runtime, "provider_implementation_digest", None) != descriptor.provider_implementation_digest:
            raise TrustedControlPlaneProviderError("runtime provider executable implementation mismatch")
        for method_name in ("prepare_launch", "observe_held", "observe_gate", "commit_start", "observe_launch", "freeze_or_kill"):
            if not callable(getattr(runtime, method_name, None)):
                raise TrustedControlPlaneProviderError("runtime provider executable capability invalid")
        self.verify_origin()
        return runtime


class TrustedSignatureVerifierAdapter(TrustedSignatureVerifier):
    def __init__(self, verifier: Callable[..., bool], *, ready: Callable[[], bool] | None = None) -> None:
        if not callable(verifier) or (ready is not None and not callable(ready)):
            raise TrustedControlPlaneProviderError("verifier invalid")
        self._verifier = verifier
        self._ready = ready

    def verify(self, payload: bytes, signature: str, key_id: str, algorithm: str) -> bool:
        try:
            result = self._verifier(payload, signature, key_id, algorithm)
        except Exception as exc:
            raise TrustedControlPlaneProviderError("signature backend failed closed") from exc
        if type(result) is not bool:
            raise TrustedControlPlaneProviderError("signature backend returned non-boolean result")
        return result

    def ready(self) -> bool:
        if self._ready is None:
            return True
        try:
            return self._ready() is True
        except Exception:
            return False
