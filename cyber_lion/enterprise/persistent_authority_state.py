"""Transactional persistent epoch, revocation, root-anchor, replay, and binding-finalization state.

This module supplies persistence missing from the process-local authority_revocation
reference implementation. It does not mint grants or authorize effects.
"""
from __future__ import annotations

from dataclasses import dataclass
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


def _text(value: object, *, name: str, limit: int = 512) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > limit or "\x00" in value:
        raise PersistentAuthorityStateError(f"{name} is invalid")
    return value


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

    def validate(self) -> "PersistentBindingFinalization":
        for name in (
            "trust_domain", "tenant_id", "organization_id", "mission_id", "grant_id",
            "root_grant_id", "binding_nonce", "finalized_at",
        ):
            _text(getattr(self, name), name=name)
        if isinstance(self.epoch, bool) or not isinstance(self.epoch, int) or self.epoch < 0:
            raise PersistentAuthorityStateError("epoch is invalid")
        if (
            isinstance(self.authority_state_version, bool)
            or not isinstance(self.authority_state_version, int)
            or self.authority_state_version < 1
        ):
            raise PersistentAuthorityStateError("authority_state_version is invalid")
        for name in (
            "root_grant_digest", "live_admission_digest", "runtime_evidence_digest",
            "finalization_key_digest",
        ):
            _sha256(getattr(self, name), name=name)
        return self

    def canonical_payload(self) -> bytes:
        self.validate()
        return json.dumps(
            {
                "authority_state_version": self.authority_state_version,
                "binding_nonce": self.binding_nonce,
                "epoch": self.epoch,
                "finalization_key_digest": self.finalization_key_digest,
                "finalized_at": self.finalized_at,
                "grant_id": self.grant_id,
                "live_admission_digest": self.live_admission_digest,
                "mission_id": self.mission_id,
                "organization_id": self.organization_id,
                "root_grant_digest": self.root_grant_digest,
                "root_grant_id": self.root_grant_id,
                "runtime_evidence_digest": self.runtime_evidence_digest,
                "tenant_id": self.tenant_id,
                "trust_domain": self.trust_domain,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")

    def digest(self) -> str:
        return hashlib.sha256(self.canonical_payload()).hexdigest()


class SQLiteAuthorityStateStore:
    """Restart-safe canonical state with transactionally monotonic updates."""

    FINALIZATION_DOMAIN = "live-authority-binding-finalization"

    def __init__(self, database_path: str) -> None:
        if not isinstance(database_path, str) or not database_path.strip():
            raise PersistentAuthorityStateError("database_path is required")
        self._path = str(Path(database_path))
        self._lock = RLock()
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._path, timeout=5, isolation_level=None, check_same_thread=False)
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA journal_mode=WAL")
        return connection

    def _initialize(self) -> None:
        with self._lock, self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS authority_epoch_state (
                    trust_domain TEXT NOT NULL,
                    tenant_id TEXT NOT NULL,
                    organization_id TEXT NOT NULL,
                    mission_id TEXT NOT NULL,
                    epoch INTEGER NOT NULL,
                    revoked_json TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    PRIMARY KEY(trust_domain, tenant_id, organization_id, mission_id)
                );
                CREATE TABLE IF NOT EXISTS authority_root_anchor (
                    trust_domain TEXT NOT NULL,
                    tenant_id TEXT NOT NULL,
                    organization_id TEXT NOT NULL,
                    mission_id TEXT NOT NULL,
                    epoch INTEGER NOT NULL,
                    root_grant_id TEXT NOT NULL,
                    root_grant_digest TEXT NOT NULL,
                    PRIMARY KEY(trust_domain, tenant_id, organization_id, mission_id, epoch)
                );
                CREATE TABLE IF NOT EXISTS replay_state (
                    replay_domain TEXT NOT NULL,
                    replay_key_digest TEXT NOT NULL,
                    consumed_at TEXT NOT NULL,
                    PRIMARY KEY(replay_domain, replay_key_digest)
                );
                """
            )

    @staticmethod
    def _context(context: tuple[str, str, str, str]) -> tuple[str, str, str, str]:
        if type(context) is not tuple or len(context) != 4 or any(not isinstance(x, str) or not x for x in context):
            raise PersistentAuthorityStateError("authority context is invalid")
        return context

    @staticmethod
    def _revoked_json(values: Iterable[str]) -> str:
        items = tuple(values)
        if any(not isinstance(item, str) or not item for item in items):
            raise PersistentAuthorityStateError("revoked grant id is invalid")
        if len(set(items)) != len(items):
            raise PersistentAuthorityStateError("revoked grant ids must be unique")
        return json.dumps(sorted(items), separators=(",", ":"))

    def bootstrap_context(self, context: tuple[str, str, str, str], *, epoch: int, revoked_grant_ids: Iterable[str] = ()) -> PersistentEpochSnapshot:
        context = self._context(context)
        if not isinstance(epoch, int) or isinstance(epoch, bool) or epoch < 0:
            raise PersistentAuthorityStateError("epoch must be non-negative")
        revoked_json = self._revoked_json(revoked_grant_ids)
        with self._lock, self._connect() as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                connection.execute(
                    "INSERT INTO authority_epoch_state VALUES(?,?,?,?,?,?,1)",
                    (*context, epoch, revoked_json),
                )
                connection.execute("COMMIT")
            except sqlite3.IntegrityError as exc:
                connection.execute("ROLLBACK")
                raise PersistentAuthorityStateError("authority context is already bootstrapped") from exc
        return self.current_epoch(context)

    def current_epoch(self, context: tuple[str, str, str, str]) -> PersistentEpochSnapshot:
        context = self._context(context)
        with self._connect() as connection:
            row = connection.execute(
                "SELECT epoch, revoked_json, version FROM authority_epoch_state WHERE trust_domain=? AND tenant_id=? AND organization_id=? AND mission_id=?",
                context,
            ).fetchone()
        if row is None:
            raise PersistentAuthorityStateError("authority context is not bootstrapped")
        revoked = tuple(json.loads(row[1]))
        return PersistentEpochSnapshot(*context, int(row[0]), revoked, int(row[2]))

    def advance_epoch(self, context: tuple[str, str, str, str], *, epoch: int, revoked_grant_ids: Iterable[str]) -> PersistentEpochSnapshot:
        context = self._context(context)
        revoked_json = self._revoked_json(revoked_grant_ids)
        candidate = set(json.loads(revoked_json))
        with self._lock, self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT epoch, revoked_json, version FROM authority_epoch_state WHERE trust_domain=? AND tenant_id=? AND organization_id=? AND mission_id=?",
                context,
            ).fetchone()
            if row is None:
                connection.execute("ROLLBACK")
                raise PersistentAuthorityStateError("authority context is not bootstrapped")
            previous_epoch = int(row[0])
            previous_revoked = set(json.loads(row[1]))
            if epoch < previous_epoch:
                connection.execute("ROLLBACK")
                raise PersistentAuthorityStateError("authority epoch cannot roll back")
            if epoch == previous_epoch and not previous_revoked.issubset(candidate):
                connection.execute("ROLLBACK")
                raise PersistentAuthorityStateError("revocation cannot be removed in one epoch")
            version = int(row[2]) + 1
            connection.execute(
                "UPDATE authority_epoch_state SET epoch=?, revoked_json=?, version=? WHERE trust_domain=? AND tenant_id=? AND organization_id=? AND mission_id=?",
                (epoch, revoked_json, version, *context),
            )
            connection.execute("COMMIT")
        return self.current_epoch(context)

    def register_root(self, context: tuple[str, str, str, str], *, epoch: int, root_grant_id: str, root_grant_digest: str) -> PersistentRootAnchor:
        context = self._context(context)
        if not root_grant_id or not isinstance(root_grant_id, str):
            raise PersistentAuthorityStateError("root_grant_id is invalid")
        _sha256(root_grant_digest, name="root_grant_digest")
        with self._lock, self._connect() as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                row = connection.execute(
                    "SELECT epoch FROM authority_epoch_state WHERE trust_domain=? AND tenant_id=? AND organization_id=? AND mission_id=?",
                    context,
                ).fetchone()
                if row is None or int(row[0]) != epoch:
                    connection.execute("ROLLBACK")
                    raise PersistentAuthorityStateError("root anchor must bind current epoch")
                connection.execute(
                    "INSERT INTO authority_root_anchor VALUES(?,?,?,?,?,?,?)",
                    (*context, epoch, root_grant_id, root_grant_digest),
                )
                connection.execute("COMMIT")
            except sqlite3.IntegrityError as exc:
                connection.execute("ROLLBACK")
                raise PersistentAuthorityStateError("root anchor already exists") from exc
        return PersistentRootAnchor(*context, epoch, root_grant_id, root_grant_digest)

    def resolve_root(self, context: tuple[str, str, str, str], *, epoch: int) -> PersistentRootAnchor:
        context = self._context(context)
        with self._connect() as connection:
            row = connection.execute(
                "SELECT root_grant_id, root_grant_digest FROM authority_root_anchor WHERE trust_domain=? AND tenant_id=? AND organization_id=? AND mission_id=? AND epoch=?",
                (*context, epoch),
            ).fetchone()
        if row is None:
            raise PersistentAuthorityStateError("root anchor is missing")
        return PersistentRootAnchor(*context, epoch, row[0], row[1])

    def consume_replay(self, replay_domain: str, replay_key_digest: str, consumed_at: str) -> bool:
        if not isinstance(replay_domain, str) or not replay_domain or not isinstance(replay_key_digest, str) or len(replay_key_digest) != 64:
            raise PersistentAuthorityStateError("replay key is invalid")
        with self._connect() as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                connection.execute(
                    "INSERT INTO replay_state VALUES(?,?,?)",
                    (replay_domain, replay_key_digest, consumed_at),
                )
                connection.execute("COMMIT")
                return True
            except sqlite3.IntegrityError:
                connection.execute("ROLLBACK")
                return False

    def finalize_binding(
        self,
        context: tuple[str, str, str, str],
        *,
        expected_epoch: int,
        expected_state_version: int,
        grant_id: str,
        expected_root_grant_id: str,
        expected_root_grant_digest: str,
        live_admission_digest: str,
        runtime_evidence_digest: str,
        binding_nonce: str,
        finalized_at: str,
    ) -> PersistentBindingFinalization:
        context = self._context(context)
        if isinstance(expected_epoch, bool) or not isinstance(expected_epoch, int) or expected_epoch < 0:
            raise PersistentAuthorityStateError("expected_epoch is invalid")
        if (
            isinstance(expected_state_version, bool)
            or not isinstance(expected_state_version, int)
            or expected_state_version < 1
        ):
            raise PersistentAuthorityStateError("expected_state_version is invalid")
        for name, value in (
            ("grant_id", grant_id),
            ("expected_root_grant_id", expected_root_grant_id),
            ("binding_nonce", binding_nonce),
            ("finalized_at", finalized_at),
        ):
            _text(value, name=name)
        for name, value in (
            ("expected_root_grant_digest", expected_root_grant_digest),
            ("live_admission_digest", live_admission_digest),
            ("runtime_evidence_digest", runtime_evidence_digest),
        ):
            _sha256(value, name=name)

        finalization_key_digest = hashlib.sha256(
            (
                f"{self.FINALIZATION_DOMAIN}\x00{live_admission_digest}\x00"
                f"{runtime_evidence_digest}\x00{binding_nonce}"
            ).encode("utf-8")
        ).hexdigest()

        with self._lock, self._connect() as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                state_row = connection.execute(
                    "SELECT epoch, revoked_json, version FROM authority_epoch_state WHERE trust_domain=? AND tenant_id=? AND organization_id=? AND mission_id=?",
                    context,
                ).fetchone()
                if state_row is None:
                    connection.execute("ROLLBACK")
                    raise PersistentAuthorityStateError("authority context is not bootstrapped")
                epoch = int(state_row[0])
                revoked = set(json.loads(state_row[1]))
                version = int(state_row[2])
                if epoch != expected_epoch or version != expected_state_version:
                    connection.execute("ROLLBACK")
                    raise PersistentAuthorityStateError("authority state changed before binding finalization")
                if grant_id in revoked:
                    connection.execute("ROLLBACK")
                    raise PersistentAuthorityStateError("grant was revoked before binding finalization")
                root_row = connection.execute(
                    "SELECT root_grant_id, root_grant_digest FROM authority_root_anchor WHERE trust_domain=? AND tenant_id=? AND organization_id=? AND mission_id=? AND epoch=?",
                    (*context, epoch),
                ).fetchone()
                if root_row is None:
                    connection.execute("ROLLBACK")
                    raise PersistentAuthorityStateError("root anchor is missing during binding finalization")
                if root_row[0] != expected_root_grant_id or root_row[1] != expected_root_grant_digest:
                    connection.execute("ROLLBACK")
                    raise PersistentAuthorityStateError("root anchor changed before binding finalization")
                connection.execute(
                    "INSERT INTO replay_state VALUES(?,?,?)",
                    (self.FINALIZATION_DOMAIN, finalization_key_digest, finalized_at),
                )
                connection.execute("COMMIT")
            except sqlite3.IntegrityError as exc:
                connection.execute("ROLLBACK")
                raise PersistentAuthorityStateError("binding finalization replay rejected") from exc

        return PersistentBindingFinalization(
            *context,
            expected_epoch,
            expected_state_version,
            grant_id,
            expected_root_grant_id,
            expected_root_grant_digest,
            live_admission_digest,
            runtime_evidence_digest,
            binding_nonce,
            finalization_key_digest,
            finalized_at,
        ).validate()

    def ready(self) -> bool:
        try:
            with self._connect() as connection:
                names = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            return {"authority_epoch_state", "authority_root_anchor", "replay_state"}.issubset(names)
        except Exception:
            return False


class PersistentEpochStateProvider:
    def __init__(self, store: SQLiteAuthorityStateStore) -> None:
        self._store = store

    def current(self, context: tuple[str, str, str, str]) -> PersistentEpochSnapshot:
        return self._store.current_epoch(context)


class PersistentRootAnchorProvider:
    def __init__(self, store: SQLiteAuthorityStateStore) -> None:
        self._store = store

    def resolve(self, context: tuple[str, str, str, str], epoch: int) -> PersistentRootAnchor:
        return self._store.resolve_root(context, epoch=epoch)


class PersistentBindingFinalizer:
    """Adapter exposing only linearizable binding finalization over the trusted store."""

    def __init__(self, store: SQLiteAuthorityStateStore) -> None:
        if not isinstance(store, SQLiteAuthorityStateStore):
            raise PersistentAuthorityStateError("binding finalizer store is invalid")
        self._store = store

    def finalize(
        self,
        context: tuple[str, str, str, str],
        **kwargs: object,
    ) -> PersistentBindingFinalization:
        return self._store.finalize_binding(context, **kwargs)


class DurableReplayGuard:
    """Restart-safe replay guard. Exactly one insertion wins for a given key."""

    def __init__(self, store: SQLiteAuthorityStateStore, *, domain: str) -> None:
        self._store = store
        self._domain = domain

    def consume(self, replay_key_digest: str, *, consumed_at: str) -> bool:
        return self._store.consume_replay(self._domain, replay_key_digest, consumed_at)
