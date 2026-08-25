"""Transactional persistent epoch, revocation, root-anchor, replay, and issuance state.

This module supplies restart-safe canonical authority state. It does not mint grants or
authorize effects. All durable authority/capability provenance tables are owned here.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
import sqlite3
from threading import RLock
from typing import Iterable


class PersistentAuthorityStateError(RuntimeError):
    """Raised when persistent authority state cannot be proven safe."""


def _sha256(value: object, *, name: str) -> str:
    if not isinstance(value, str) or len(value) != 64:
        raise PersistentAuthorityStateError(f"{name} is invalid")
    try:
        int(value, 16)
    except ValueError as exc:
        raise PersistentAuthorityStateError(f"{name} is invalid") from exc
    if value.lower() != value:
        raise PersistentAuthorityStateError(f"{name} is invalid")
    return value


def _sha40(value: object, *, name: str) -> str:
    if not isinstance(value, str) or len(value) != 40:
        raise PersistentAuthorityStateError(f"{name} is invalid")
    try:
        int(value, 16)
    except ValueError as exc:
        raise PersistentAuthorityStateError(f"{name} is invalid") from exc
    if value.lower() != value:
        raise PersistentAuthorityStateError(f"{name} is invalid")
    return value


def _text(value: object, *, name: str, limit: int = 512) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > limit or "\x00" in value:
        raise PersistentAuthorityStateError(f"{name} is invalid")
    return value


def _scope(value: object, *, name: str) -> tuple[str, ...]:
    if type(value) is not tuple or not value or len(set(value)) != len(value):
        raise PersistentAuthorityStateError(f"{name} is invalid")
    for item in value:
        _text(item, name=name, limit=2048)
    return value


def _canonical_record_json(record: object) -> str:
    payload = asdict(record)
    for key in ("candidate_scope", "resource_scope"):
        if key in payload:
            payload[key] = list(payload[key])
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _decode_record(value: str, cls: type):
    try:
        payload = json.loads(value)
    except (TypeError, json.JSONDecodeError) as exc:
        raise PersistentAuthorityStateError("issuance record is malformed") from exc
    if not isinstance(payload, dict) or set(payload) != set(cls.__dataclass_fields__):
        raise PersistentAuthorityStateError("issuance record is noncanonical")
    for key in ("candidate_scope", "resource_scope"):
        if key in payload and type(payload[key]) is list:
            payload[key] = tuple(payload[key])
    try:
        return cls(**payload).validate()
    except (TypeError, ValueError) as exc:
        raise PersistentAuthorityStateError("issuance record is invalid") from exc


@dataclass(frozen=True)
class PersistentEpochSnapshot:
    trust_domain: str
    tenant_id: str
    organization_id: str
    mission_id: str
    epoch: int
    revoked_grant_ids: tuple[str, ...]
    version: int

    def context(self) -> tuple[str, str, str, str]:
        return (self.trust_domain, self.tenant_id, self.organization_id, self.mission_id)


@dataclass(frozen=True)
class PersistentRootAnchor:
    trust_domain: str
    tenant_id: str
    organization_id: str
    mission_id: str
    epoch: int
    root_grant_id: str
    root_grant_digest: str


@dataclass(frozen=True)
class PersistentAuthorityStoreOrigin:
    origin_id: str
    origin_digest: str
    runtime_factory_version: str
    repository_root: str
    canonical_database_path: str

    def validate(self) -> "PersistentAuthorityStoreOrigin":
        _text(self.origin_id, name="origin_id", limit=256)
        _sha256(self.origin_digest, name="origin_digest")
        _text(self.runtime_factory_version, name="runtime_factory_version", limit=64)
        _text(self.repository_root, name="repository_root", limit=4096)
        _text(self.canonical_database_path, name="canonical_database_path", limit=4096)
        if self.origin_id != f"aso:{self.origin_digest}":
            raise PersistentAuthorityStateError("authority store origin id binding mismatch")
        if not Path(self.repository_root).is_absolute() or not Path(self.canonical_database_path).is_absolute():
            raise PersistentAuthorityStateError("authority store origin path is invalid")
        return self

    def canonical_json(self) -> str:
        self.validate()
        return json.dumps(asdict(self), sort_keys=True, separators=(",", ":"), ensure_ascii=False)

    @classmethod
    def from_json(cls, value: str) -> "PersistentAuthorityStoreOrigin":
        try:
            payload = json.loads(value)
        except (TypeError, json.JSONDecodeError) as exc:
            raise PersistentAuthorityStateError("authority store origin record is malformed") from exc
        if not isinstance(payload, dict) or set(payload) != set(cls.__dataclass_fields__):
            raise PersistentAuthorityStateError("authority store origin record is noncanonical")
        return cls(**payload).validate()


@dataclass(frozen=True)
class PersistentBuilderEntryIssuanceRecord:
    builder_entry_permit_id: str
    builder_entry_permit_digest: str
    builder_entry_replay_digest: str
    repository: str
    baseline_master_sha: str
    baseline_master_tree_sha: str
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
    authority_store_origin_id: str
    authority_store_origin_digest: str
    issued_at: str

    def validate(self) -> "PersistentBuilderEntryIssuanceRecord":
        for name in ("builder_entry_permit_id","repository","action","root_grant_id","builder_subject_id","builder_instance_id","builder_capability_class","authority_store_origin_id","issued_at"):
            _text(getattr(self, name), name=name, limit=2048)
        for name in ("builder_entry_permit_digest","builder_entry_replay_digest","root_grant_digest","current_authority_digest","builder_identity_digest","builder_implementation_digest","builder_attestation_digest","authority_store_origin_digest"):
            _sha256(getattr(self, name), name=name)
        _sha40(self.baseline_master_sha, name="baseline_master_sha"); _sha40(self.baseline_master_tree_sha, name="baseline_master_tree_sha")
        _scope(self.candidate_scope, name="candidate_scope"); _scope(self.resource_scope, name="resource_scope")
        if self.authority_store_origin_id != f"aso:{self.authority_store_origin_digest}" or self.action != "BUILD_CANDIDATE" or self.builder_capability_class != "DETACHED_CANDIDATE_BUILD_ONLY":
            raise PersistentAuthorityStateError("builder entry issuance semantics invalid")
        if isinstance(self.authority_epoch, bool) or not isinstance(self.authority_epoch, int) or self.authority_epoch < 0:
            raise PersistentAuthorityStateError("authority_epoch is invalid")
        if isinstance(self.authority_state_version, bool) or not isinstance(self.authority_state_version, int) or self.authority_state_version < 1:
            raise PersistentAuthorityStateError("authority_state_version is invalid")
        return self

    def canonical_json(self) -> str: self.validate(); return _canonical_record_json(self)
    @classmethod
    def from_json(cls, value: str): return _decode_record(value, cls)


@dataclass(frozen=True)
class PersistentBuilderInvocationIssuanceRecord:
    builder_invocation_permit_id: str
    builder_invocation_permit_digest: str
    builder_invocation_replay_digest: str
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

    def validate(self) -> "PersistentBuilderInvocationIssuanceRecord":
        for name in ("builder_invocation_permit_id","source_builder_entry_permit_id","repository","action","root_grant_id","builder_subject_id","builder_instance_id","builder_capability_class","authority_store_origin_id","issued_at"):
            _text(getattr(self, name), name=name, limit=2048)
        for name in ("builder_invocation_permit_digest","builder_invocation_replay_digest","source_builder_entry_permit_digest","current_baseline_digest","root_grant_digest","current_authority_digest","builder_identity_digest","builder_implementation_digest","builder_attestation_digest","current_builder_subject_digest","authority_store_origin_digest"):
            _sha256(getattr(self, name), name=name)
        _sha40(self.baseline_master_sha, name="baseline_master_sha"); _sha40(self.baseline_master_tree_sha, name="baseline_master_tree_sha")
        _scope(self.candidate_scope, name="candidate_scope"); _scope(self.resource_scope, name="resource_scope")
        if self.authority_store_origin_id != f"aso:{self.authority_store_origin_digest}" or self.action != "BUILD_CANDIDATE" or self.builder_capability_class != "DETACHED_CANDIDATE_BUILD_ONLY":
            raise PersistentAuthorityStateError("builder invocation issuance semantics invalid")
        if isinstance(self.authority_epoch, bool) or not isinstance(self.authority_epoch, int) or self.authority_epoch < 0:
            raise PersistentAuthorityStateError("authority_epoch is invalid")
        if isinstance(self.authority_state_version, bool) or not isinstance(self.authority_state_version, int) or self.authority_state_version < 1:
            raise PersistentAuthorityStateError("authority_state_version is invalid")
        return self

    def canonical_json(self) -> str: self.validate(); return _canonical_record_json(self)
    @classmethod
    def from_json(cls, value: str): return _decode_record(value, cls)


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

    def validate(self):
        for name in ("invocation_consumption_permit_id","source_builder_invocation_permit_id","source_builder_entry_permit_id","repository","action","root_grant_id","builder_subject_id","builder_instance_id","builder_capability_class","authority_store_origin_id","issued_at"):
            _text(getattr(self, name), name=name, limit=2048)
        for name in ("invocation_consumption_permit_digest","invocation_consumption_replay_digest","source_builder_invocation_permit_digest","source_builder_invocation_replay_digest","source_builder_entry_permit_digest","current_baseline_digest","root_grant_digest","current_authority_digest","builder_identity_digest","builder_implementation_digest","builder_attestation_digest","current_builder_subject_digest","authority_store_origin_digest"):
            _sha256(getattr(self, name), name=name)
        _sha40(self.baseline_master_sha, name="baseline_master_sha"); _sha40(self.baseline_master_tree_sha, name="baseline_master_tree_sha")
        _scope(self.candidate_scope, name="candidate_scope"); _scope(self.resource_scope, name="resource_scope")
        if not self.invocation_consumption_permit_id.startswith("bicp:") or self.authority_store_origin_id != f"aso:{self.authority_store_origin_digest}" or self.action != "BUILD_CANDIDATE" or self.builder_capability_class != "DETACHED_CANDIDATE_BUILD_ONLY":
            raise PersistentAuthorityStateError("builder invocation consumption issuance semantics invalid")
        return self

    def canonical_json(self) -> str: self.validate(); return _canonical_record_json(self)
    @classmethod
    def from_json(cls, value: str): return _decode_record(value, cls)


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

    def validate(self):
        for name in ("builder_start_admission_id","source_invocation_consumption_permit_id","source_builder_invocation_permit_id","source_builder_entry_permit_id","repository","action","root_grant_id","builder_subject_id","builder_instance_id","builder_capability_class","process_profile_id","authority_store_origin_id","issued_at"):
            _text(getattr(self, name), name=name, limit=2048)
        for name in ("builder_start_admission_digest","builder_start_admission_replay_digest","source_invocation_consumption_permit_digest","source_invocation_consumption_replay_digest","source_builder_invocation_permit_digest","source_builder_entry_permit_digest","current_baseline_digest","root_grant_digest","current_authority_digest","builder_identity_digest","builder_implementation_digest","builder_attestation_digest","current_builder_subject_digest","process_profile_digest","launch_policy_digest","authority_store_origin_digest"):
            _sha256(getattr(self, name), name=name)
        _sha40(self.baseline_master_sha, name="baseline_master_sha"); _sha40(self.baseline_master_tree_sha, name="baseline_master_tree_sha")
        _scope(self.candidate_scope, name="candidate_scope"); _scope(self.resource_scope, name="resource_scope")
        if not self.builder_start_admission_id.startswith("bsa:") or not self.process_profile_id.startswith("bpp:") or self.authority_store_origin_id != f"aso:{self.authority_store_origin_digest}" or self.action != "BUILD_CANDIDATE" or self.builder_capability_class != "DETACHED_CANDIDATE_BUILD_ONLY":
            raise PersistentAuthorityStateError("builder start admission issuance semantics invalid")
        return self

    def canonical_json(self) -> str: self.validate(); return _canonical_record_json(self)
    @classmethod
    def from_json(cls, value: str): return _decode_record(value, cls)


@dataclass(frozen=True)
class PersistentBindingFinalization:
    trust_domain: str
    tenant_id: str
    organization_id: str
    mission_id: str
    epoch: int
    authority_state_version: int
    grant_id: str
    root_grant_id: str
    root_grant_digest: str
    live_admission_digest: str
    runtime_evidence_digest: str
    binding_nonce: str
    finalization_key_digest: str
    finalized_at: str

    def validate(self):
        for name in ("trust_domain","tenant_id","organization_id","mission_id","grant_id","root_grant_id","binding_nonce","finalized_at"):
            _text(getattr(self, name), name=name)
        for name in ("root_grant_digest","live_admission_digest","runtime_evidence_digest","finalization_key_digest"):
            _sha256(getattr(self, name), name=name)
        if isinstance(self.epoch, bool) or not isinstance(self.epoch, int) or self.epoch < 0:
            raise PersistentAuthorityStateError("epoch is invalid")
        if isinstance(self.authority_state_version, bool) or not isinstance(self.authority_state_version, int) or self.authority_state_version < 1:
            raise PersistentAuthorityStateError("authority_state_version is invalid")
        return self

    def canonical_payload(self) -> bytes:
        self.validate(); return json.dumps(asdict(self), sort_keys=True, separators=(",", ":")).encode("utf-8")
    def digest(self) -> str: return hashlib.sha256(self.canonical_payload()).hexdigest()


class SQLiteAuthorityStateStore:
    FINALIZATION_DOMAIN = "live-authority-binding-finalization"
    REQUIRED_TABLES = frozenset({
        "authority_epoch_state", "authority_root_anchor", "replay_state", "authority_store_origin",
        "builder_entry_issuance", "builder_invocation_issuance",
        "builder_invocation_consumption_issuance", "builder_start_admission_issuance",
    })

    def __init__(self, database_path: str) -> None:
        if not isinstance(database_path, str) or not database_path.strip():
            raise PersistentAuthorityStateError("database_path is required")
        self._path = str(Path(database_path)); self._lock = RLock(); self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._path, timeout=5, isolation_level=None, check_same_thread=False)
        connection.execute("PRAGMA foreign_keys=ON"); connection.execute("PRAGMA journal_mode=WAL")
        return connection

    def _initialize(self) -> None:
        with self._lock, self._connect() as connection:
            connection.executescript("""
            CREATE TABLE IF NOT EXISTS authority_epoch_state (trust_domain TEXT NOT NULL,tenant_id TEXT NOT NULL,organization_id TEXT NOT NULL,mission_id TEXT NOT NULL,epoch INTEGER NOT NULL,revoked_json TEXT NOT NULL,version INTEGER NOT NULL,PRIMARY KEY(trust_domain,tenant_id,organization_id,mission_id));
            CREATE TABLE IF NOT EXISTS authority_root_anchor (trust_domain TEXT NOT NULL,tenant_id TEXT NOT NULL,organization_id TEXT NOT NULL,mission_id TEXT NOT NULL,epoch INTEGER NOT NULL,root_grant_id TEXT NOT NULL,root_grant_digest TEXT NOT NULL,PRIMARY KEY(trust_domain,tenant_id,organization_id,mission_id,epoch));
            CREATE TABLE IF NOT EXISTS replay_state (replay_domain TEXT NOT NULL,replay_key_digest TEXT NOT NULL,consumed_at TEXT NOT NULL,PRIMARY KEY(replay_domain,replay_key_digest));
            CREATE TABLE IF NOT EXISTS authority_store_origin (singleton INTEGER NOT NULL PRIMARY KEY CHECK(singleton=1),origin_id TEXT NOT NULL UNIQUE,origin_digest TEXT NOT NULL UNIQUE,record_json TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS builder_entry_issuance (builder_entry_permit_id TEXT NOT NULL PRIMARY KEY,builder_entry_permit_digest TEXT NOT NULL UNIQUE,builder_entry_replay_digest TEXT NOT NULL UNIQUE,record_json TEXT NOT NULL,issued_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS builder_invocation_issuance (builder_invocation_permit_id TEXT NOT NULL PRIMARY KEY,builder_invocation_permit_digest TEXT NOT NULL UNIQUE,builder_invocation_replay_digest TEXT NOT NULL UNIQUE,record_json TEXT NOT NULL,issued_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS builder_invocation_consumption_issuance (invocation_consumption_permit_id TEXT NOT NULL PRIMARY KEY,invocation_consumption_permit_digest TEXT NOT NULL UNIQUE,invocation_consumption_replay_digest TEXT NOT NULL UNIQUE,record_json TEXT NOT NULL,issued_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS builder_start_admission_issuance (builder_start_admission_id TEXT NOT NULL PRIMARY KEY,builder_start_admission_digest TEXT NOT NULL UNIQUE,builder_start_admission_replay_digest TEXT NOT NULL UNIQUE,record_json TEXT NOT NULL,issued_at TEXT NOT NULL);
            """)

    @staticmethod
    def _context(context):
        if type(context) is not tuple or len(context) != 4 or any(not isinstance(x,str) or not x for x in context):
            raise PersistentAuthorityStateError("authority context is invalid")
        return context

    @staticmethod
    def _revoked_json(values):
        items=tuple(values)
        if any(not isinstance(x,str) or not x for x in items) or len(set(items)) != len(items):
            raise PersistentAuthorityStateError("revoked grant ids are invalid")
        return json.dumps(sorted(items), separators=(",", ":"))

    def bootstrap_context(self, context, *, epoch: int, revoked_grant_ids: Iterable[str]=()):
        context=self._context(context); revoked=self._revoked_json(revoked_grant_ids)
        if isinstance(epoch,bool) or not isinstance(epoch,int) or epoch<0: raise PersistentAuthorityStateError("epoch must be non-negative")
        with self._lock,self._connect() as c:
            try:
                c.execute("BEGIN IMMEDIATE"); c.execute("INSERT INTO authority_epoch_state VALUES(?,?,?,?,?,?,1)",(*context,epoch,revoked)); c.execute("COMMIT")
            except sqlite3.IntegrityError as exc:
                c.execute("ROLLBACK"); raise PersistentAuthorityStateError("authority context is already bootstrapped") from exc
        return self.current_epoch(context)

    def current_epoch(self, context):
        context=self._context(context)
        with self._connect() as c: row=c.execute("SELECT epoch,revoked_json,version FROM authority_epoch_state WHERE trust_domain=? AND tenant_id=? AND organization_id=? AND mission_id=?",context).fetchone()
        if row is None: raise PersistentAuthorityStateError("authority context is not bootstrapped")
        return PersistentEpochSnapshot(*context,int(row[0]),tuple(json.loads(row[1])),int(row[2]))

    def advance_epoch(self, context, *, epoch:int, revoked_grant_ids:Iterable[str]):
        context=self._context(context); revoked_json=self._revoked_json(revoked_grant_ids); candidate=set(json.loads(revoked_json))
        with self._lock,self._connect() as c:
            c.execute("BEGIN IMMEDIATE"); row=c.execute("SELECT epoch,revoked_json,version FROM authority_epoch_state WHERE trust_domain=? AND tenant_id=? AND organization_id=? AND mission_id=?",context).fetchone()
            if row is None: c.execute("ROLLBACK"); raise PersistentAuthorityStateError("authority context is not bootstrapped")
            prev=int(row[0]); prev_rev=set(json.loads(row[1]))
            if epoch<prev or (epoch==prev and not prev_rev.issubset(candidate)):
                c.execute("ROLLBACK"); raise PersistentAuthorityStateError("authority epoch/revocation cannot roll back")
            c.execute("UPDATE authority_epoch_state SET epoch=?,revoked_json=?,version=? WHERE trust_domain=? AND tenant_id=? AND organization_id=? AND mission_id=?",(epoch,revoked_json,int(row[2])+1,*context)); c.execute("COMMIT")
        return self.current_epoch(context)

    def register_root(self, context, *, epoch:int, root_grant_id:str, root_grant_digest:str):
        context=self._context(context); _text(root_grant_id,name="root_grant_id"); _sha256(root_grant_digest,name="root_grant_digest")
        with self._lock,self._connect() as c:
            try:
                c.execute("BEGIN IMMEDIATE"); row=c.execute("SELECT epoch FROM authority_epoch_state WHERE trust_domain=? AND tenant_id=? AND organization_id=? AND mission_id=?",context).fetchone()
                if row is None or int(row[0])!=epoch: c.execute("ROLLBACK"); raise PersistentAuthorityStateError("root anchor must bind current epoch")
                c.execute("INSERT INTO authority_root_anchor VALUES(?,?,?,?,?,?,?)",(*context,epoch,root_grant_id,root_grant_digest)); c.execute("COMMIT")
            except sqlite3.IntegrityError as exc:
                c.execute("ROLLBACK"); raise PersistentAuthorityStateError("root anchor already exists") from exc
        return PersistentRootAnchor(*context,epoch,root_grant_id,root_grant_digest)

    def resolve_root(self, context, *, epoch:int):
        context=self._context(context)
        with self._connect() as c: row=c.execute("SELECT root_grant_id,root_grant_digest FROM authority_root_anchor WHERE trust_domain=? AND tenant_id=? AND organization_id=? AND mission_id=? AND epoch=?",(*context,epoch)).fetchone()
        if row is None: raise PersistentAuthorityStateError("root anchor is missing")
        return PersistentRootAnchor(*context,epoch,row[0],row[1])

    def consume_replay(self,replay_domain:str,replay_key_digest:str,consumed_at:str)->bool:
        _text(replay_domain,name="replay_domain"); _sha256(replay_key_digest,name="replay_key_digest"); _text(consumed_at,name="consumed_at",limit=1024)
        with self._connect() as c:
            try:
                c.execute("BEGIN IMMEDIATE"); c.execute("INSERT INTO replay_state VALUES(?,?,?)",(replay_domain,replay_key_digest,consumed_at)); c.execute("COMMIT"); return True
            except sqlite3.IntegrityError:
                c.execute("ROLLBACK"); return False

    def register_authority_store_origin(self, origin):
        if type(origin) is not PersistentAuthorityStoreOrigin: raise PersistentAuthorityStateError("exact authority store origin required")
        origin.validate()
        with self._lock,self._connect() as c:
            try:
                c.execute("BEGIN IMMEDIATE"); c.execute("INSERT INTO authority_store_origin VALUES(1,?,?,?)",(origin.origin_id,origin.origin_digest,origin.canonical_json())); c.execute("COMMIT")
            except sqlite3.IntegrityError as exc:
                c.execute("ROLLBACK"); raise PersistentAuthorityStateError("authority store origin is already registered") from exc
        return origin

    def resolve_authority_store_origin(self):
        with self._connect() as c: rows=c.execute("SELECT record_json FROM authority_store_origin WHERE singleton=1").fetchall()
        if len(rows)!=1: raise PersistentAuthorityStateError("authority store origin is missing or ambiguous")
        return PersistentAuthorityStoreOrigin.from_json(rows[0][0])

    def _require_record_origin(self, record: object, *, error_label: str) -> None:
        record.validate(); origin=self.resolve_authority_store_origin()
        if (record.authority_store_origin_id,record.authority_store_origin_digest)!=(origin.origin_id,origin.origin_digest):
            raise PersistentAuthorityStateError(f"{error_label} store origin mismatch")

    def _require_resolved_origin(self, record: object, *, error_label: str) -> None:
        origin=self.resolve_authority_store_origin()
        if (record.authority_store_origin_id,record.authority_store_origin_digest)!=(origin.origin_id,origin.origin_digest):
            raise PersistentAuthorityStateError(f"{error_label} origin mismatch")

    def record_builder_entry_issuance(self,record):
        if type(record) is not PersistentBuilderEntryIssuanceRecord: raise PersistentAuthorityStateError("exact builder entry issuance record required")
        self._require_record_origin(record,error_label="builder entry issuance")
        with self._lock,self._connect() as c:
            try:
                c.execute("BEGIN IMMEDIATE")
                c.execute("INSERT INTO builder_entry_issuance VALUES(?,?,?,?,?)",(record.builder_entry_permit_id,record.builder_entry_permit_digest,record.builder_entry_replay_digest,record.canonical_json(),record.issued_at))
                c.execute("COMMIT")
            except sqlite3.IntegrityError as exc:
                c.execute("ROLLBACK"); raise PersistentAuthorityStateError("builder entry issuance already exists or conflicts") from exc
        return record

    def resolve_builder_entry_issuance(self,builder_entry_permit_id):
        _text(builder_entry_permit_id,name="builder_entry_permit_id",limit=2048)
        with self._connect() as c:
            rows=c.execute("SELECT record_json FROM builder_entry_issuance WHERE builder_entry_permit_id=?",(builder_entry_permit_id,)).fetchall()
        if len(rows)!=1: raise PersistentAuthorityStateError("builder entry issuance is missing or ambiguous")
        record=PersistentBuilderEntryIssuanceRecord.from_json(rows[0][0])
        if record.builder_entry_permit_id!=builder_entry_permit_id: raise PersistentAuthorityStateError("builder entry issuance lookup binding mismatch")
        self._require_resolved_origin(record,error_label="builder entry issuance")
        return record

    def record_builder_invocation_issuance(self,record):
        if type(record) is not PersistentBuilderInvocationIssuanceRecord: raise PersistentAuthorityStateError("exact builder invocation issuance record required")
        self._require_record_origin(record,error_label="builder invocation issuance")
        with self._lock,self._connect() as c:
            try:
                c.execute("BEGIN IMMEDIATE")
                c.execute("INSERT INTO builder_invocation_issuance VALUES(?,?,?,?,?)",(record.builder_invocation_permit_id,record.builder_invocation_permit_digest,record.builder_invocation_replay_digest,record.canonical_json(),record.issued_at))
                c.execute("COMMIT")
            except sqlite3.IntegrityError as exc:
                c.execute("ROLLBACK"); raise PersistentAuthorityStateError("builder invocation issuance already exists or conflicts") from exc
        return record

    def resolve_builder_invocation_issuance(self,builder_invocation_permit_id):
        _text(builder_invocation_permit_id,name="builder_invocation_permit_id",limit=2048)
        with self._connect() as c:
            rows=c.execute("SELECT record_json FROM builder_invocation_issuance WHERE builder_invocation_permit_id=?",(builder_invocation_permit_id,)).fetchall()
        if len(rows)!=1: raise PersistentAuthorityStateError("builder invocation issuance is missing or ambiguous")
        record=PersistentBuilderInvocationIssuanceRecord.from_json(rows[0][0])
        if record.builder_invocation_permit_id!=builder_invocation_permit_id: raise PersistentAuthorityStateError("builder invocation issuance lookup binding mismatch")
        self._require_resolved_origin(record,error_label="builder invocation issuance")
        return record

    def record_builder_invocation_consumption_issuance(self,record):
        if type(record) is not PersistentBuilderInvocationConsumptionIssuanceRecord: raise PersistentAuthorityStateError("exact builder invocation consumption issuance record required")
        self._require_record_origin(record,error_label="builder invocation consumption issuance")
        with self._lock,self._connect() as c:
            try:
                c.execute("BEGIN IMMEDIATE")
                c.execute("INSERT INTO builder_invocation_consumption_issuance VALUES(?,?,?,?,?)",(record.invocation_consumption_permit_id,record.invocation_consumption_permit_digest,record.invocation_consumption_replay_digest,record.canonical_json(),record.issued_at))
                c.execute("COMMIT")
            except sqlite3.IntegrityError as exc:
                c.execute("ROLLBACK"); raise PersistentAuthorityStateError("builder invocation consumption issuance already exists or conflicts") from exc
        return record

    def resolve_builder_invocation_consumption_issuance(self,invocation_consumption_permit_id):
        _text(invocation_consumption_permit_id,name="invocation_consumption_permit_id",limit=2048)
        with self._connect() as c:
            rows=c.execute("SELECT record_json FROM builder_invocation_consumption_issuance WHERE invocation_consumption_permit_id=?",(invocation_consumption_permit_id,)).fetchall()
        if len(rows)!=1: raise PersistentAuthorityStateError("builder invocation consumption issuance is missing or ambiguous")
        record=PersistentBuilderInvocationConsumptionIssuanceRecord.from_json(rows[0][0])
        if record.invocation_consumption_permit_id!=invocation_consumption_permit_id: raise PersistentAuthorityStateError("builder invocation consumption issuance lookup binding mismatch")
        self._require_resolved_origin(record,error_label="builder invocation consumption issuance")
        return record

    def record_builder_start_admission_issuance(self,record):
        if type(record) is not PersistentBuilderStartAdmissionIssuanceRecord: raise PersistentAuthorityStateError("exact builder start admission issuance record required")
        self._require_record_origin(record,error_label="builder start admission issuance")
        with self._lock,self._connect() as c:
            try:
                c.execute("BEGIN IMMEDIATE")
                c.execute("INSERT INTO builder_start_admission_issuance VALUES(?,?,?,?,?)",(record.builder_start_admission_id,record.builder_start_admission_digest,record.builder_start_admission_replay_digest,record.canonical_json(),record.issued_at))
                c.execute("COMMIT")
            except sqlite3.IntegrityError as exc:
                c.execute("ROLLBACK"); raise PersistentAuthorityStateError("builder start admission issuance already exists or conflicts") from exc
        return record

    def resolve_builder_start_admission_issuance(self,builder_start_admission_id):
        _text(builder_start_admission_id,name="builder_start_admission_id",limit=2048)
        with self._connect() as c:
            rows=c.execute("SELECT record_json FROM builder_start_admission_issuance WHERE builder_start_admission_id=?",(builder_start_admission_id,)).fetchall()
        if len(rows)!=1: raise PersistentAuthorityStateError("builder start admission issuance is missing or ambiguous")
        record=PersistentBuilderStartAdmissionIssuanceRecord.from_json(rows[0][0])
        if record.builder_start_admission_id!=builder_start_admission_id: raise PersistentAuthorityStateError("builder start admission issuance lookup binding mismatch")
        self._require_resolved_origin(record,error_label="builder start admission issuance")
        return record

    def finalize_binding(self, context, *, expected_epoch:int, expected_state_version:int, grant_id:str, expected_root_grant_id:str, expected_root_grant_digest:str, live_admission_digest:str, runtime_evidence_digest:str, binding_nonce:str, finalized_at:str):
        context=self._context(context)
        if isinstance(expected_epoch,bool) or not isinstance(expected_epoch,int) or expected_epoch<0: raise PersistentAuthorityStateError("expected_epoch is invalid")
        if isinstance(expected_state_version,bool) or not isinstance(expected_state_version,int) or expected_state_version<1: raise PersistentAuthorityStateError("expected_state_version is invalid")
        for n,v in (("grant_id",grant_id),("expected_root_grant_id",expected_root_grant_id),("binding_nonce",binding_nonce),("finalized_at",finalized_at)): _text(v,name=n)
        for n,v in (("expected_root_grant_digest",expected_root_grant_digest),("live_admission_digest",live_admission_digest),("runtime_evidence_digest",runtime_evidence_digest)): _sha256(v,name=n)
        key=hashlib.sha256((f"{self.FINALIZATION_DOMAIN}\x00{live_admission_digest}\x00{runtime_evidence_digest}\x00{binding_nonce}").encode()).hexdigest()
        with self._lock,self._connect() as c:
            try:
                c.execute("BEGIN IMMEDIATE"); state=c.execute("SELECT epoch,revoked_json,version FROM authority_epoch_state WHERE trust_domain=? AND tenant_id=? AND organization_id=? AND mission_id=?",context).fetchone()
                if state is None: c.execute("ROLLBACK"); raise PersistentAuthorityStateError("authority context is not bootstrapped")
                epoch=int(state[0]); revoked=set(json.loads(state[1])); version=int(state[2])
                if epoch!=expected_epoch or version!=expected_state_version or grant_id in revoked: c.execute("ROLLBACK"); raise PersistentAuthorityStateError("authority state changed before binding finalization")
                root=c.execute("SELECT root_grant_id,root_grant_digest FROM authority_root_anchor WHERE trust_domain=? AND tenant_id=? AND organization_id=? AND mission_id=? AND epoch=?",(*context,epoch)).fetchone()
                if root is None or root[0]!=expected_root_grant_id or root[1]!=expected_root_grant_digest: c.execute("ROLLBACK"); raise PersistentAuthorityStateError("root anchor changed before binding finalization")
                c.execute("INSERT INTO replay_state VALUES(?,?,?)",(self.FINALIZATION_DOMAIN,key,finalized_at)); c.execute("COMMIT")
            except sqlite3.IntegrityError as exc:
                c.execute("ROLLBACK"); raise PersistentAuthorityStateError("binding finalization replay rejected") from exc
        return PersistentBindingFinalization(*context,expected_epoch,expected_state_version,grant_id,expected_root_grant_id,expected_root_grant_digest,live_admission_digest,runtime_evidence_digest,binding_nonce,key,finalized_at).validate()

    def ready(self)->bool:
        try:
            with self._connect() as c: names={row[0] for row in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            return self.REQUIRED_TABLES.issubset(names)
        except Exception:
            return False


class PersistentEpochStateProvider:
    def __init__(self,store): self._store=store
    def current(self,context): return self._store.current_epoch(context)

class PersistentRootAnchorProvider:
    def __init__(self,store): self._store=store
    def resolve(self,context,epoch): return self._store.resolve_root(context,epoch=epoch)

class PersistentBindingFinalizer:
    def __init__(self,store):
        if not isinstance(store,SQLiteAuthorityStateStore): raise PersistentAuthorityStateError("binding finalizer store is invalid")
        self._store=store
    def finalize(self,context,**kwargs): return self._store.finalize_binding(context,**kwargs)

class DurableReplayGuard:
    def __init__(self,store,*,domain:str): self._store=store; self._domain=domain
    def consume(self,replay_key_digest:str,*,consumed_at:str)->bool: return self._store.consume_replay(self._domain,replay_key_digest,consumed_at)
