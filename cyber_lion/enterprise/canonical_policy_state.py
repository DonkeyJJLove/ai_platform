"""Restart-durable canonical policy state; policy state is not authority."""
from __future__ import annotations

from dataclasses import asdict
from hashlib import sha256
import json
import sqlite3
from pathlib import Path

from cyber_lion.contracts.policy_gate import PolicyRevision


class CanonicalPolicyStateError(RuntimeError):
    pass


def _canon(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _digest_policy(policy: PolicyRevision) -> str:
    policy.validate()
    return sha256(_canon(asdict(policy))).hexdigest()


class CanonicalPolicyStore:
    """Append-only policy registry with one explicit current active revision."""

    def __init__(self, db_path: str | Path, *, registry_id: str) -> None:
        if not isinstance(registry_id, str) or not registry_id:
            raise CanonicalPolicyStateError("registry_id required")
        self.registry_id = registry_id
        self.db_path = str(Path(db_path))
        self._conn = sqlite3.connect(self.db_path, isolation_level=None)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=FULL")
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS canonical_policy_meta(
              singleton INTEGER PRIMARY KEY CHECK(singleton=1),
              registry_id TEXT NOT NULL,
              generation INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS canonical_policy_revision(
              policy_id TEXT NOT NULL,
              revision TEXT NOT NULL,
              policy_digest TEXT NOT NULL UNIQUE,
              policy_json TEXT NOT NULL,
              source_provenance_ref TEXT NOT NULL,
              PRIMARY KEY(policy_id, revision)
            );
            CREATE TABLE IF NOT EXISTS canonical_policy_active(
              policy_id TEXT PRIMARY KEY,
              revision TEXT NOT NULL,
              policy_digest TEXT NOT NULL,
              generation INTEGER NOT NULL,
              FOREIGN KEY(policy_id, revision) REFERENCES canonical_policy_revision(policy_id, revision)
            );
            CREATE TRIGGER IF NOT EXISTS canonical_policy_revision_no_update
              BEFORE UPDATE ON canonical_policy_revision BEGIN SELECT RAISE(ABORT,'policy revision append-only'); END;
            CREATE TRIGGER IF NOT EXISTS canonical_policy_revision_no_delete
              BEFORE DELETE ON canonical_policy_revision BEGIN SELECT RAISE(ABORT,'policy revision append-only'); END;
            """
        )
        row = self._conn.execute("SELECT registry_id FROM canonical_policy_meta WHERE singleton=1").fetchone()
        if row is None:
            self._conn.execute("INSERT INTO canonical_policy_meta VALUES(1,?,0)", (registry_id,))
        elif row[0] != registry_id:
            self._conn.close()
            raise CanonicalPolicyStateError("policy registry substitution denied")

    def close(self) -> None:
        self._conn.close()

    def register_initial(self, policy: PolicyRevision, *, source_provenance_ref: str) -> PolicyRevision:
        policy.validate()
        if not policy.active:
            raise CanonicalPolicyStateError("initial canonical policy must be active")
        if not source_provenance_ref:
            raise CanonicalPolicyStateError("policy provenance required")
        if self._conn.execute("SELECT 1 FROM canonical_policy_active WHERE policy_id=?", (policy.policy_id,)).fetchone():
            raise CanonicalPolicyStateError("explicit supersession required")
        dg = _digest_policy(policy)
        raw = _canon(asdict(policy)).decode("utf-8")
        try:
            self._conn.execute("BEGIN IMMEDIATE")
            self._conn.execute(
                "INSERT INTO canonical_policy_revision VALUES(?,?,?,?,?)",
                (policy.policy_id, policy.revision, dg, raw, source_provenance_ref),
            )
            generation = int(self._conn.execute("SELECT generation FROM canonical_policy_meta WHERE singleton=1").fetchone()[0]) + 1
            self._conn.execute("UPDATE canonical_policy_meta SET generation=? WHERE singleton=1", (generation,))
            self._conn.execute(
                "INSERT INTO canonical_policy_active VALUES(?,?,?,?)",
                (policy.policy_id, policy.revision, dg, generation),
            )
            self._conn.execute("COMMIT")
        except Exception:
            if self._conn.in_transaction:
                self._conn.execute("ROLLBACK")
            raise
        return policy

    def supersede(self, policy: PolicyRevision, *, expected_revision: str, expected_digest: str, source_provenance_ref: str) -> PolicyRevision:
        policy.validate()
        if not policy.active:
            raise CanonicalPolicyStateError("superseding canonical policy must be active")
        if not source_provenance_ref:
            raise CanonicalPolicyStateError("policy provenance required")
        current = self._conn.execute(
            "SELECT revision,policy_digest,generation FROM canonical_policy_active WHERE policy_id=?",
            (policy.policy_id,),
        ).fetchone()
        if current is None or current[0] != expected_revision or current[1] != expected_digest:
            raise CanonicalPolicyStateError("exact current policy binding mismatch")
        if policy.revision == expected_revision:
            raise CanonicalPolicyStateError("policy revision reuse denied")
        if self._conn.execute(
            "SELECT 1 FROM canonical_policy_revision WHERE policy_id=? AND revision=?",
            (policy.policy_id, policy.revision),
        ).fetchone():
            raise CanonicalPolicyStateError("historical policy rollback/reuse denied")
        dg = _digest_policy(policy)
        raw = _canon(asdict(policy)).decode("utf-8")
        try:
            self._conn.execute("BEGIN IMMEDIATE")
            self._conn.execute(
                "INSERT INTO canonical_policy_revision VALUES(?,?,?,?,?)",
                (policy.policy_id, policy.revision, dg, raw, source_provenance_ref),
            )
            generation = int(current[2]) + 1
            self._conn.execute("UPDATE canonical_policy_meta SET generation=? WHERE singleton=1", (generation,))
            self._conn.execute(
                "UPDATE canonical_policy_active SET revision=?,policy_digest=?,generation=? WHERE policy_id=?",
                (policy.revision, dg, generation, policy.policy_id),
            )
            self._conn.execute("COMMIT")
        except Exception:
            if self._conn.in_transaction:
                self._conn.execute("ROLLBACK")
            raise
        return policy

    def resolve_current(self, policy_id: str) -> PolicyRevision:
        row = self._conn.execute(
            "SELECT r.policy_json,a.policy_digest FROM canonical_policy_active a JOIN canonical_policy_revision r "
            "ON r.policy_id=a.policy_id AND r.revision=a.revision WHERE a.policy_id=?",
            (policy_id,),
        ).fetchone()
        if row is None:
            raise CanonicalPolicyStateError("canonical policy unavailable")
        try:
            raw = json.loads(row[0])
            policy = PolicyRevision(**raw).validate()
        except Exception as exc:
            raise CanonicalPolicyStateError("stored policy invalid") from exc
        if _digest_policy(policy) != row[1] or not policy.active:
            raise CanonicalPolicyStateError("canonical policy corruption/inactive state")
        return policy

    def current_binding_digest(self, policy_id: str) -> str:
        policy = self.resolve_current(policy_id)
        return _digest_policy(policy)
