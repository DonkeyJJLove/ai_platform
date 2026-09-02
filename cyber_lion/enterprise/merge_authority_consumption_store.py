"""Durable exact-key merge-authority consumption state for external runtime use."""
from __future__ import annotations

from pathlib import Path
import os
import sqlite3
from threading import RLock

from .merge_authority_consumption import (
    MergeAuthorityConsumptionKey,
    MergeAuthorityConsumptionObservation,
    MergeAuthorityConsumptionState,
    MergeAuthorityConsumptionWriteCapability,
)


class MergeAuthorityConsumptionStoreError(RuntimeError):
    pass


class SQLiteMergeAuthorityConsumptionStore(MergeAuthorityConsumptionWriteCapability):
    def __init__(self, database_path: str, *, repository_root: str) -> None:
        db = Path(database_path)
        root = Path(repository_root)
        if not db.is_absolute() or not root.is_absolute():
            raise MergeAuthorityConsumptionStoreError("runtime paths must be absolute")
        try:
            root_resolved = root.resolve(strict=True)
            parent = db.parent.resolve(strict=True)
        except OSError as exc:
            raise MergeAuthorityConsumptionStoreError("runtime path is unavailable") from exc
        db_resolved = parent / db.name
        if db_resolved == root_resolved or root_resolved in db_resolved.parents:
            raise MergeAuthorityConsumptionStoreError("consumption database must be outside repository")
        self._path = str(db_resolved)
        self._lock = RLock()
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._path, timeout=5, isolation_level=None)
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA synchronous=FULL")
        return connection

    def _initialize(self) -> None:
        with self._lock, self._connect() as connection:
            connection.executescript("""
                CREATE TABLE IF NOT EXISTS merge_authority_consumption(
                    repository TEXT NOT NULL,
                    pr_number INTEGER NOT NULL,
                    base_sha TEXT NOT NULL,
                    head_sha TEXT NOT NULL,
                    grant_id TEXT NOT NULL,
                    grant_digest TEXT NOT NULL,
                    lineage_digest TEXT NOT NULL,
                    epoch INTEGER NOT NULL,
                    merge_method TEXT NOT NULL,
                    state TEXT NOT NULL,
                    state_version INTEGER NOT NULL,
                    provenance_id TEXT NOT NULL,
                    PRIMARY KEY(
                        repository,pr_number,base_sha,head_sha,grant_id,
                        grant_digest,lineage_digest,epoch,merge_method
                    )
                );
            """)

    @staticmethod
    def _params(key: MergeAuthorityConsumptionKey) -> tuple[object, ...]:
        key.validate()
        return key.binding()

    @staticmethod
    def _observation(
        key: MergeAuthorityConsumptionKey,
        state: MergeAuthorityConsumptionState,
        version: int,
        provenance_id: str,
    ) -> MergeAuthorityConsumptionObservation:
        return MergeAuthorityConsumptionObservation(
            key=key,
            state=state,
            state_version=str(version),
            provenance_id=provenance_id,
        ).validate()

    def observe_consumption_exact(
        self, key: MergeAuthorityConsumptionKey
    ) -> MergeAuthorityConsumptionObservation:
        params = self._params(key)
        with self._lock, self._connect() as connection:
            rows = connection.execute(
                """
                SELECT state,state_version,provenance_id
                FROM merge_authority_consumption
                WHERE repository=? AND pr_number=? AND base_sha=? AND head_sha=?
                  AND grant_id=? AND grant_digest=? AND lineage_digest=?
                  AND epoch=? AND merge_method=?
                """,
                params,
            ).fetchall()
        if len(rows) > 1:
            raise MergeAuthorityConsumptionStoreError("consumption cardinality invalid")
        if not rows:
            return self._observation(
                key,
                MergeAuthorityConsumptionState.AVAILABLE,
                0,
                "lab-debian:consumption:implicit-available",
            )
        state_raw, version, provenance_id = rows[0]
        try:
            state = MergeAuthorityConsumptionState(state_raw)
        except ValueError as exc:
            raise MergeAuthorityConsumptionStoreError("consumption state corrupt") from exc
        return self._observation(key, state, int(version), provenance_id)

    def consume_exact(
        self, key: MergeAuthorityConsumptionKey
    ) -> MergeAuthorityConsumptionObservation:
        params = self._params(key)
        provenance_id = "lab-debian:consumption:consume"
        with self._lock, self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            rows = connection.execute(
                """
                SELECT state,state_version,provenance_id
                FROM merge_authority_consumption
                WHERE repository=? AND pr_number=? AND base_sha=? AND head_sha=?
                  AND grant_id=? AND grant_digest=? AND lineage_digest=?
                  AND epoch=? AND merge_method=?
                """,
                params,
            ).fetchall()
            if len(rows) > 1:
                connection.execute("ROLLBACK")
                raise MergeAuthorityConsumptionStoreError("consumption cardinality invalid")
            if not rows:
                connection.execute(
                    "INSERT INTO merge_authority_consumption VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                    params + (
                        MergeAuthorityConsumptionState.CONSUMED.value,
                        1,
                        provenance_id,
                    ),
                )
                version = 1
            else:
                state_raw, version_raw, existing_provenance = rows[0]
                state = MergeAuthorityConsumptionState(state_raw)
                if state is MergeAuthorityConsumptionState.CONSUMED:
                    connection.execute("COMMIT")
                    return self._observation(
                        key, state, int(version_raw), existing_provenance
                    )
                if state is not MergeAuthorityConsumptionState.AVAILABLE:
                    connection.execute("ROLLBACK")
                    raise MergeAuthorityConsumptionStoreError(
                        "consumption transition denied"
                    )
                version = int(version_raw) + 1
                connection.execute(
                    """
                    UPDATE merge_authority_consumption
                    SET state=?,state_version=?,provenance_id=?
                    WHERE repository=? AND pr_number=? AND base_sha=? AND head_sha=?
                      AND grant_id=? AND grant_digest=? AND lineage_digest=?
                      AND epoch=? AND merge_method=?
                    """,
                    (
                        MergeAuthorityConsumptionState.CONSUMED.value,
                        version,
                        provenance_id,
                    ) + params,
                )
            connection.execute("COMMIT")
        return self._observation(
            key,
            MergeAuthorityConsumptionState.CONSUMED,
            version,
            provenance_id,
        )


def build_consumption_store_from_environment() -> SQLiteMergeAuthorityConsumptionStore:
    return SQLiteMergeAuthorityConsumptionStore(
        os.environ.get("CYBER_LION_CONSUMPTION_DB_PATH", ""),
        repository_root=os.environ.get("CYBER_LION_REPOSITORY_ROOT", ""),
    )
