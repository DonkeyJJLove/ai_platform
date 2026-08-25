"""Concrete persistent providers for the trusted control-plane service.

These providers are deliberately capability-reduced. The SQLite store exposes exact
read operations to the service and other trusted in-process admission boundaries;
bootstrap writes are separate trusted-process methods and are never selected by normal
admission callers. Signature verification is delegated to a runtime-bound callable so
key custody remains outside repository content.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
import json
from pathlib import Path
import sqlite3
from threading import RLock

from .trusted_control_plane_service import (
    TrustedControlPlaneStore,
    TrustedSignatureVerifier,
)


class TrustedControlPlaneProviderError(RuntimeError):
    """Raised when persistent provider state cannot be proven canonical."""


def _canonical_json(value: Mapping[str, object]) -> str:
    if not isinstance(value, Mapping):
        raise TrustedControlPlaneProviderError("provider record must be a mapping")
    return json.dumps(dict(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _decode_record(raw: str) -> Mapping[str, object]:
    try:
        value = json.loads(raw)
    except (TypeError, json.JSONDecodeError) as exc:
        raise TrustedControlPlaneProviderError("persistent provider record is corrupt") from exc
    if not isinstance(value, Mapping):
        raise TrustedControlPlaneProviderError("persistent provider record is not an object")
    return dict(value)


class SQLiteTrustedControlPlaneStore(TrustedControlPlaneStore):
    """Restart-safe exact-record store used behind TrustedControlPlaneService.

    ``put_*`` methods are trusted bootstrap operations. Runtime admission paths only use
    the exact read operations. Builder-subject records deliberately share this existing
    store rather than creating an independent trust database.
    """

    BUILDER_LOOKUP_FIELDS = (
        "repository",
        "builder_subject_id",
        "builder_instance_id",
        "candidate_scope_digest",
        "resource_scope_digest",
        "capability_class",
    )

    def __init__(self, database_path: str) -> None:
        if not isinstance(database_path, str) or not database_path.strip():
            raise TrustedControlPlaneProviderError("database_path is required")
        self._path = str(Path(database_path))
        self._lock = RLock()
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._path, timeout=5, isolation_level=None)
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA journal_mode=WAL")
        return connection

    def _initialize(self) -> None:
        with self._lock, self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS pr_bootstrap (
                    repository TEXT NOT NULL,
                    pr_number INTEGER NOT NULL,
                    base_sha TEXT NOT NULL,
                    head_sha TEXT NOT NULL,
                    merge_method TEXT NOT NULL,
                    record_json TEXT NOT NULL,
                    PRIMARY KEY(repository, pr_number, base_sha, head_sha, merge_method, record_json)
                );
                CREATE TABLE IF NOT EXISTS authority_lineage (
                    repository TEXT NOT NULL,
                    pr_number INTEGER NOT NULL,
                    base_sha TEXT NOT NULL,
                    head_sha TEXT NOT NULL,
                    mission_id TEXT NOT NULL,
                    grant_id TEXT NOT NULL,
                    record_json TEXT NOT NULL,
                    PRIMARY KEY(repository, pr_number, base_sha, head_sha, mission_id, grant_id, record_json)
                );
                CREATE TABLE IF NOT EXISTS builder_subject (
                    repository TEXT NOT NULL,
                    builder_subject_id TEXT NOT NULL,
                    builder_instance_id TEXT NOT NULL,
                    candidate_scope_digest TEXT NOT NULL,
                    resource_scope_digest TEXT NOT NULL,
                    capability_class TEXT NOT NULL,
                    record_json TEXT NOT NULL,
                    PRIMARY KEY(
                        repository,
                        builder_subject_id,
                        builder_instance_id,
                        candidate_scope_digest,
                        resource_scope_digest,
                        capability_class,
                        record_json
                    )
                );
                """
            )

    @staticmethod
    def _lookup(record: Mapping[str, object], fields: tuple[str, ...], label: str) -> Mapping[str, object]:
        lookup = record.get("lookup_key") if isinstance(record, Mapping) else None
        if not isinstance(lookup, Mapping):
            raise TrustedControlPlaneProviderError(f"{label} record lookup_key is required")
        if frozenset(lookup.keys()) != frozenset(fields):
            raise TrustedControlPlaneProviderError(f"{label} lookup_key is not canonical")
        return lookup

    def put_pr_bootstrap(self, record: Mapping[str, object]) -> None:
        fields = ("repository", "pr_number", "base_sha", "head_sha", "merge_method")
        lookup = self._lookup(record, fields, "bootstrap")
        raw = _canonical_json(record)
        with self._lock, self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                "INSERT OR IGNORE INTO pr_bootstrap VALUES(?,?,?,?,?,?)",
                tuple(lookup[name] for name in fields) + (raw,),
            )
            connection.execute("COMMIT")

    def put_authority_record(self, record: Mapping[str, object]) -> None:
        fields = ("repository", "pr_number", "base_sha", "head_sha", "mission_id", "grant_id")
        lookup = self._lookup(record, fields, "authority")
        raw = _canonical_json(record)
        with self._lock, self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                "INSERT OR IGNORE INTO authority_lineage VALUES(?,?,?,?,?,?,?)",
                tuple(lookup[name] for name in fields) + (raw,),
            )
            connection.execute("COMMIT")

    def put_builder_subject_record(self, record: Mapping[str, object]) -> None:
        """Trusted bootstrap write for one exact builder-subject record."""
        fields = self.BUILDER_LOOKUP_FIELDS
        lookup = self._lookup(record, fields, "builder subject")
        if record.get("record_kind") != "builder-subject":
            raise TrustedControlPlaneProviderError("builder subject record kind is invalid")
        if not isinstance(record.get("subject"), Mapping):
            raise TrustedControlPlaneProviderError("builder subject payload is invalid")
        raw = _canonical_json(record)
        with self._lock, self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                "INSERT OR IGNORE INTO builder_subject VALUES(?,?,?,?,?,?,?)",
                tuple(lookup[name] for name in fields) + (raw,),
            )
            connection.execute("COMMIT")

    def lookup_pr_bootstrap_exact(
        self, *, repository: str, pr_number: int, base_sha: str, head_sha: str,
        merge_method: str,
    ) -> tuple[Mapping[str, object], ...]:
        with self._lock, self._connect() as connection:
            rows = connection.execute(
                "SELECT record_json FROM pr_bootstrap WHERE repository=? AND pr_number=? "
                "AND base_sha=? AND head_sha=? AND merge_method=? ORDER BY record_json",
                (repository, pr_number, base_sha, head_sha, merge_method),
            ).fetchall()
        return tuple(_decode_record(row[0]) for row in rows)

    def lookup_authority_exact(
        self, *, repository: str, pr_number: int, base_sha: str, head_sha: str,
        mission_id: str, grant_id: str,
    ) -> tuple[Mapping[str, object], ...]:
        with self._lock, self._connect() as connection:
            rows = connection.execute(
                "SELECT record_json FROM authority_lineage WHERE repository=? AND pr_number=? "
                "AND base_sha=? AND head_sha=? AND mission_id=? AND grant_id=? ORDER BY record_json",
                (repository, pr_number, base_sha, head_sha, mission_id, grant_id),
            ).fetchall()
        return tuple(_decode_record(row[0]) for row in rows)

    def lookup_builder_subject_exact(
        self,
        *,
        repository: str,
        builder_subject_id: str,
        builder_instance_id: str,
        candidate_scope_digest: str,
        resource_scope_digest: str,
        capability_class: str,
    ) -> tuple[Mapping[str, object], ...]:
        with self._lock, self._connect() as connection:
            rows = connection.execute(
                "SELECT record_json FROM builder_subject WHERE repository=? "
                "AND builder_subject_id=? AND builder_instance_id=? "
                "AND candidate_scope_digest=? AND resource_scope_digest=? "
                "AND capability_class=? ORDER BY record_json",
                (
                    repository,
                    builder_subject_id,
                    builder_instance_id,
                    candidate_scope_digest,
                    resource_scope_digest,
                    capability_class,
                ),
            ).fetchall()
        return tuple(_decode_record(row[0]) for row in rows)

    def ready(self) -> bool:
        try:
            with self._connect() as connection:
                names = {row[0] for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )}
            return {"pr_bootstrap", "authority_lineage", "builder_subject"}.issubset(names)
        except Exception:
            return False


class TrustedSignatureVerifierAdapter(TrustedSignatureVerifier):
    """Bind service verification to a runtime-supplied cryptographic verifier."""

    def __init__(self, verifier: Callable[[bytes, str, str, str], bool], *, ready: Callable[[], bool] | None = None) -> None:
        if not callable(verifier):
            raise TrustedControlPlaneProviderError("verifier must be callable")
        if ready is not None and not callable(ready):
            raise TrustedControlPlaneProviderError("ready callback must be callable")
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
