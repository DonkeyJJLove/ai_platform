"""Durable pre-effect fence for one canonical repository branch-ref delete.

This module persists exact-once effect reservation and post-effect observation state.  It
is not an authority source, does not call GitHub, and cannot execute a repository effect.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
import re
import sqlite3
from threading import RLock

_STATES = {"PREPARED", "ATTEMPTED", "OBSERVED", "RECONCILED", "UNKNOWN"}
_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_HEX64 = re.compile(r"^[0-9a-f]{64}$")


class RepositoryDeleteFenceError(RuntimeError):
    pass


def _text(value: object, name: str, *, limit: int = 4096) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > limit or "\x00" in value:
        raise RepositoryDeleteFenceError(f"{name} is invalid")
    return value


def _sha40(value: object, name: str) -> str:
    value = _text(value, name, limit=40)
    if _SHA40.fullmatch(value) is None:
        raise RepositoryDeleteFenceError(f"{name} is invalid")
    return value


def _hex64(value: object, name: str) -> str:
    value = _text(value, name, limit=64)
    if _HEX64.fullmatch(value) is None:
        raise RepositoryDeleteFenceError(f"{name} is invalid")
    return value


@dataclass(frozen=True)
class RepositoryDeleteFenceRecord:
    effect_key: str
    admission_digest: str
    repository: str
    mission_id: str
    authority_lineage_digest: str
    policy_digest: str
    control_comment_id: int
    branch: str
    expected_branch_head: str
    expected_master: str
    expected_master_tree: str
    provider_id: str
    execution_id: str
    authority_epoch: int
    state: str
    prepared_at: str
    attempted_at: str | None = None
    observed_at: str | None = None
    reconciled_at: str | None = None
    observation_digest: str | None = None
    reconciliation_digest: str | None = None

    def validate(self) -> "RepositoryDeleteFenceRecord":
        for name in (
            "effect_key", "admission_digest", "repository", "mission_id",
            "authority_lineage_digest", "policy_digest", "branch", "provider_id",
            "execution_id", "prepared_at",
        ):
            _text(getattr(self, name), name)
        for name in ("effect_key", "admission_digest", "authority_lineage_digest", "policy_digest"):
            _hex64(getattr(self, name), name)
        for name in ("expected_branch_head", "expected_master", "expected_master_tree"):
            _sha40(getattr(self, name), name)
        if not isinstance(self.control_comment_id, int) or isinstance(self.control_comment_id, bool) or self.control_comment_id <= 0:
            raise RepositoryDeleteFenceError("control_comment_id is invalid")
        if not isinstance(self.authority_epoch, int) or isinstance(self.authority_epoch, bool) or self.authority_epoch < 0:
            raise RepositoryDeleteFenceError("authority_epoch is invalid")
        if self.state not in _STATES:
            raise RepositoryDeleteFenceError("state is invalid")
        if self.state == "PREPARED" and any((self.attempted_at, self.observed_at, self.reconciled_at, self.observation_digest, self.reconciliation_digest)):
            raise RepositoryDeleteFenceError("PREPARED state contains later evidence")
        if self.state in {"ATTEMPTED", "OBSERVED", "RECONCILED"} and not self.attempted_at:
            raise RepositoryDeleteFenceError("attempted state lacks attempted_at")
        if self.state in {"OBSERVED", "RECONCILED"}:
            if not self.observed_at or self.observation_digest is None:
                raise RepositoryDeleteFenceError("observed state lacks observation")
            _hex64(self.observation_digest, "observation_digest")
        if self.state == "RECONCILED":
            if not self.reconciled_at or self.reconciliation_digest is None:
                raise RepositoryDeleteFenceError("RECONCILED state lacks reconciliation")
            _hex64(self.reconciliation_digest, "reconciliation_digest")
        if self.reconciliation_digest is not None:
            _hex64(self.reconciliation_digest, "reconciliation_digest")
        return self


class RepositoryDeleteFence:
    """SQLite-backed, restart-safe, process-safe exact-once delete effect fence."""

    def __init__(self, database_path: str) -> None:
        if not isinstance(database_path, str) or not database_path.strip():
            raise RepositoryDeleteFenceError("database path is required")
        path = Path(database_path)
        if not path.is_absolute():
            raise RepositoryDeleteFenceError("database path must be absolute")
        path.parent.mkdir(parents=True, exist_ok=True)
        self._path = str(path)
        self._lock = RLock()
        self._initialize()

    @classmethod
    def from_trusted_environment(cls) -> "RepositoryDeleteFence":
        raw = os.environ.get("LION_CP_DATABASE_PATH", "")
        path = Path(raw)
        if not raw or not path.is_absolute():
            raise RepositoryDeleteFenceError("trusted persistent database unavailable")
        workspace_raw = os.environ.get("GITHUB_WORKSPACE")
        if workspace_raw:
            workspace = Path(workspace_raw).resolve()
            resolved = path.resolve()
            if resolved == workspace or workspace in resolved.parents:
                raise RepositoryDeleteFenceError("delete fence database must remain outside repository")
        return cls(str(path))

    def _connect(self):
        connection = sqlite3.connect(self._path, timeout=10, isolation_level=None, check_same_thread=False)
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA synchronous=FULL")
        return connection

    def _initialize(self) -> None:
        with self._lock, self._connect() as connection:
            connection.executescript("""
            CREATE TABLE IF NOT EXISTS repository_delete_effect (
                effect_key TEXT PRIMARY KEY,
                admission_digest TEXT NOT NULL UNIQUE,
                repository TEXT NOT NULL,
                mission_id TEXT NOT NULL,
                authority_lineage_digest TEXT NOT NULL,
                policy_digest TEXT NOT NULL,
                control_comment_id INTEGER NOT NULL,
                branch TEXT NOT NULL,
                expected_branch_head TEXT NOT NULL,
                expected_master TEXT NOT NULL,
                expected_master_tree TEXT NOT NULL,
                provider_id TEXT NOT NULL,
                execution_id TEXT NOT NULL,
                authority_epoch INTEGER NOT NULL,
                state TEXT NOT NULL,
                prepared_at TEXT NOT NULL,
                attempted_at TEXT,
                observed_at TEXT,
                reconciled_at TEXT,
                observation_digest TEXT,
                reconciliation_digest TEXT
            );
            CREATE UNIQUE INDEX IF NOT EXISTS repository_delete_effect_exact_binding
              ON repository_delete_effect(
                repository,mission_id,authority_lineage_digest,policy_digest,
                control_comment_id,branch,expected_branch_head,expected_master,
                expected_master_tree,provider_id,execution_id,authority_epoch
              );
            """)

    @staticmethod
    def _row(record) -> RepositoryDeleteFenceRecord:
        if record is None:
            raise RepositoryDeleteFenceError("delete effect is unknown")
        return RepositoryDeleteFenceRecord(*record).validate()

    def get(self, effect_key: str) -> RepositoryDeleteFenceRecord:
        _hex64(effect_key, "effect_key")
        with self._connect() as connection:
            row = connection.execute(
                "SELECT effect_key,admission_digest,repository,mission_id,authority_lineage_digest,policy_digest,control_comment_id,branch,expected_branch_head,expected_master,expected_master_tree,provider_id,execution_id,authority_epoch,state,prepared_at,attempted_at,observed_at,reconciled_at,observation_digest,reconciliation_digest FROM repository_delete_effect WHERE effect_key=?",
                (effect_key,),
            ).fetchone()
        return self._row(row)

    def prepare(self, record: RepositoryDeleteFenceRecord) -> RepositoryDeleteFenceRecord:
        if type(record) is not RepositoryDeleteFenceRecord or record.validate().state != "PREPARED":
            raise RepositoryDeleteFenceError("exact pristine PREPARED record required")
        with self._lock, self._connect() as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                connection.execute(
                    "INSERT INTO repository_delete_effect VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        record.effect_key, record.admission_digest, record.repository, record.mission_id,
                        record.authority_lineage_digest, record.policy_digest, record.control_comment_id,
                        record.branch, record.expected_branch_head, record.expected_master,
                        record.expected_master_tree, record.provider_id, record.execution_id,
                        record.authority_epoch, record.state, record.prepared_at, None, None, None, None, None,
                    ),
                )
                connection.execute("COMMIT")
            except sqlite3.IntegrityError as exc:
                connection.execute("ROLLBACK")
                raise RepositoryDeleteFenceError("delete effect replay or binding collision denied") from exc
        return self.get(record.effect_key)

    def mark_attempted(self, effect_key: str, *, attempted_at: str) -> RepositoryDeleteFenceRecord:
        _text(attempted_at, "attempted_at")
        with self._lock, self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            cursor = connection.execute(
                "UPDATE repository_delete_effect SET state='ATTEMPTED',attempted_at=? WHERE effect_key=? AND state='PREPARED' AND attempted_at IS NULL",
                (attempted_at, effect_key),
            )
            if cursor.rowcount != 1:
                connection.execute("ROLLBACK")
                raise RepositoryDeleteFenceError("delete effect cannot enter ATTEMPTED")
            connection.execute("COMMIT")
        return self.get(effect_key)

    def mark_observed(self, effect_key: str, *, observation_digest: str, observed_at: str) -> RepositoryDeleteFenceRecord:
        _hex64(observation_digest, "observation_digest"); _text(observed_at, "observed_at")
        with self._lock, self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            cursor = connection.execute(
                "UPDATE repository_delete_effect SET state='OBSERVED',observation_digest=?,observed_at=? WHERE effect_key=? AND state='ATTEMPTED'",
                (observation_digest, observed_at, effect_key),
            )
            if cursor.rowcount != 1:
                connection.execute("ROLLBACK")
                raise RepositoryDeleteFenceError("delete effect cannot enter OBSERVED")
            connection.execute("COMMIT")
        return self.get(effect_key)

    def mark_reconciled(self, effect_key: str, *, reconciliation_digest: str, reconciled_at: str) -> RepositoryDeleteFenceRecord:
        _hex64(reconciliation_digest, "reconciliation_digest"); _text(reconciled_at, "reconciled_at")
        with self._lock, self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            cursor = connection.execute(
                "UPDATE repository_delete_effect SET state='RECONCILED',reconciliation_digest=?,reconciled_at=? WHERE effect_key=? AND state='OBSERVED'",
                (reconciliation_digest, reconciled_at, effect_key),
            )
            if cursor.rowcount != 1:
                connection.execute("ROLLBACK")
                raise RepositoryDeleteFenceError("delete effect cannot enter RECONCILED")
            connection.execute("COMMIT")
        return self.get(effect_key)

    def mark_unknown(self, effect_key: str) -> RepositoryDeleteFenceRecord:
        with self._lock, self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            cursor = connection.execute(
                "UPDATE repository_delete_effect SET state='UNKNOWN' WHERE effect_key=? AND state IN ('PREPARED','ATTEMPTED','OBSERVED')",
                (effect_key,),
            )
            if cursor.rowcount != 1:
                connection.execute("ROLLBACK")
                raise RepositoryDeleteFenceError("delete effect cannot enter UNKNOWN")
            connection.execute("COMMIT")
        return self.get(effect_key)
