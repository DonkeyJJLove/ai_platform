"""Transactional persistent epoch, revocation, root-anchor, and replay state.

This module supplies persistence missing from the process-local authority_revocation
reference implementation. It does not mint grants or authorize effects.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import sqlite3
from threading import RLock
from typing import Iterable


class PersistentAuthorityStateError(RuntimeError):
    """Raised when persistent authority state cannot be proven safe."""


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


class SQLiteAuthorityStateStore:
    """Restart-safe canonical state with transactionally monotonic updates."""

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
        state = self.current_epoch(context)
        if state.epoch != epoch:
            raise PersistentAuthorityStateError("root anchor must bind current epoch")
        if not root_grant_id or not isinstance(root_grant_id, str):
            raise PersistentAuthorityStateError("root_grant_id is invalid")
        if not isinstance(root_grant_digest, str) or len(root_grant_digest) != 64:
            raise PersistentAuthorityStateError("root_grant_digest is invalid")
        with self._lock, self._connect() as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
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


class DurableReplayGuard:
    """Restart-safe replay guard. Exactly one insertion wins for a given key."""

    def __init__(self, store: SQLiteAuthorityStateStore, *, domain: str) -> None:
        self._store = store
        self._domain = domain

    def consume(self, replay_key_digest: str, *, consumed_at: str) -> bool:
        return self._store.consume_replay(self._domain, replay_key_digest, consumed_at)
