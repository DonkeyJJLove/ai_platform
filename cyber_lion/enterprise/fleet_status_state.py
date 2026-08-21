"""Durable single-runtime status state for FCSR P0 R1R + R2 source journal."""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
from typing import Callable, Iterator, Protocol

from cyber_lion.contracts.fleet_status import (
    AUTHORITY_STATES,
    EFFECT_STATES,
    RECONCILIATION_STATES,
    SANDBOX_STATES,
    FleetStatusContractError,
    FleetStatusIdentity,
    TrustedVerificationEvidence,
    VerificationTrustPins,
    canonical_json,
)
from cyber_lion.contracts.fleet_status_sources import (
    MissingStatusSource,
    ReconciledStatusFact,
    SourceCheckpoint,
    SourceConflict,
    StatusSourceBatch,
    StatusSourceIdentity,
    StatusSourceObservation,
    StatusSourceRead,
    canonical_json as source_canonical_json,
)

TERMINAL_MISSIONS = frozenset({"DONE", "FAILED", "TERMINATED"})
TERMINAL_AUTHORITY = frozenset({"NONE", "REVOKED", "EXPIRED"})
TERMINAL_EFFECT = frozenset({"NONE", "APPLIED", "FAILED_NO_EFFECT"})
TERMINAL_RECONCILIATION = frozenset({"NOT_REQUIRED", "RESOLVED"})


class FleetStatusStateError(RuntimeError):
    """Fail-closed state-layer error."""


class TrustedVerificationSource(Protocol):
    """Composition-root supplied verifier evidence source."""

    def resolve(self, verification_id: str) -> TrustedVerificationEvidence:
        ...


def _utc(value: datetime) -> str:
    if value.tzinfo is None:
        raise FleetStatusStateError("trusted clock must return timezone-aware datetime")
    return value.astimezone(timezone.utc).isoformat()


def _parse_utc(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, ValueError) as exc:
        raise FleetStatusStateError("source timestamp invalid") from exc
    if parsed.tzinfo is None:
        raise FleetStatusStateError("source timestamp must be timezone-aware")
    return parsed.astimezone(timezone.utc)


def _now(clock: Callable[[], datetime]) -> str:
    return _utc(clock())


def _event_digest(previous: str, event_type: str, mission_id: str | None, payload: dict[str, object], observed_at: str) -> str:
    body = {
        "previous_digest": previous,
        "event_type": event_type,
        "mission_id": mission_id,
        "payload": payload,
        "observed_at": observed_at,
    }
    return sha256(canonical_json(body)).hexdigest()


def _receipt_digest(previous: str, receipt_id: str, mission_id: str, source_ref: str, observed_at: str) -> str:
    return sha256(canonical_json({
        "previous_digest": previous,
        "receipt_id": receipt_id,
        "mission_id": mission_id,
        "source_ref": source_ref,
        "observed_at": observed_at,
    })).hexdigest()


def _source_batch_digest(identity_digest: str, sequence: int, source_observed_at: str, read_digest: str) -> str:
    return sha256(source_canonical_json({
        "source_identity_digest": identity_digest,
        "source_sequence": sequence,
        "source_observed_at": source_observed_at,
        "read_digest": read_digest,
    })).hexdigest()


def _source_chain_digest(previous: str, batch_digest: str) -> str:
    return sha256((previous + batch_digest).encode("ascii")).hexdigest()


class FleetStatusStore:
    """Status/evidence store only; it has no authority or external-effect capability."""

    def __init__(
        self,
        db_path: str | Path,
        *,
        registry_instance_id: str,
        clock: Callable[[], datetime],
        verification_source: TrustedVerificationSource,
        verification_pins: VerificationTrustPins,
    ) -> None:
        if not registry_instance_id or "\x00" in registry_instance_id:
            raise FleetStatusStateError("registry_instance_id invalid")
        verification_pins.validate()
        self._db_path = str(Path(db_path))
        self._registry_instance_id = registry_instance_id
        self._clock = clock
        self._verification_source = verification_source
        self._verification_pins = verification_pins
        self._conn = sqlite3.connect(self._db_path, isolation_level=None)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=FULL")
        self._init_schema()
        self._bind_instance()

    @property
    def registry_instance_id(self) -> str:
        return self._registry_instance_id

    @property
    def db_path(self) -> str:
        return self._db_path

    def close(self) -> None:
        self._conn.close()

    def _init_schema(self) -> None:
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS fleet_meta(
                singleton INTEGER PRIMARY KEY CHECK(singleton=1),
                registry_instance_id TEXT NOT NULL,
                revision INTEGER NOT NULL,
                event_head TEXT NOT NULL,
                receipt_head TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS fleet_identity(
                drone_id TEXT PRIMARY KEY,
                executor_id TEXT NOT NULL UNIQUE,
                mission_id TEXT NOT NULL UNIQUE,
                parent_mission_id TEXT NOT NULL,
                repository TEXT NOT NULL,
                baseline_sha TEXT NOT NULL,
                baseline_tree_sha TEXT NOT NULL,
                branch TEXT NOT NULL,
                read_scope_json TEXT NOT NULL,
                write_scope_json TEXT NOT NULL,
                sandbox_id TEXT NOT NULL,
                identity_digest TEXT NOT NULL UNIQUE
            );

            CREATE TABLE IF NOT EXISTS fleet_mission(
                mission_id TEXT PRIMARY KEY REFERENCES fleet_identity(mission_id),
                phase TEXT NOT NULL,
                status TEXT NOT NULL,
                closure_state TEXT NOT NULL,
                current_operation TEXT,
                current_blocker TEXT,
                dependency_state TEXT NOT NULL,
                branch_head TEXT,
                observed_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS fleet_runtime(
                mission_id TEXT PRIMARY KEY REFERENCES fleet_identity(mission_id),
                runtime_id TEXT NOT NULL UNIQUE,
                evidence_ref TEXT NOT NULL,
                bound_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS fleet_heartbeat(
                mission_id TEXT PRIMARY KEY REFERENCES fleet_identity(mission_id),
                runtime_id TEXT NOT NULL,
                sequence INTEGER NOT NULL,
                deadline_seconds INTEGER NOT NULL,
                source_ref TEXT NOT NULL,
                observed_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS fleet_projection(
                mission_id TEXT NOT NULL REFERENCES fleet_identity(mission_id),
                kind TEXT NOT NULL,
                state TEXT NOT NULL,
                source_ref TEXT NOT NULL,
                observed_at TEXT NOT NULL,
                PRIMARY KEY(mission_id, kind)
            );

            CREATE TABLE IF NOT EXISTS fleet_verification(
                mission_id TEXT PRIMARY KEY REFERENCES fleet_identity(mission_id),
                verification_id TEXT NOT NULL UNIQUE,
                verification_state TEXT NOT NULL,
                verifier_id TEXT NOT NULL,
                verifier_identity_digest TEXT NOT NULL,
                verifier_implementation_digest TEXT NOT NULL,
                trust_anchor_id TEXT NOT NULL,
                trust_anchor_digest TEXT NOT NULL,
                evidence_digest TEXT NOT NULL,
                source_provenance_ref TEXT NOT NULL,
                epistemic_class TEXT NOT NULL,
                observed_at TEXT NOT NULL,
                binding_digest TEXT NOT NULL UNIQUE
            );

            CREATE TABLE IF NOT EXISTS fleet_lease(
                lease_id TEXT PRIMARY KEY,
                mission_id TEXT NOT NULL REFERENCES fleet_identity(mission_id),
                lease_type TEXT NOT NULL,
                resource TEXT NOT NULL,
                state TEXT NOT NULL,
                source_ref TEXT NOT NULL,
                observed_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS fleet_event(
                seq INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id TEXT NOT NULL UNIQUE,
                event_type TEXT NOT NULL,
                mission_id TEXT,
                payload_json TEXT NOT NULL,
                previous_digest TEXT NOT NULL,
                event_digest TEXT NOT NULL UNIQUE,
                observed_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS fleet_receipt(
                seq INTEGER PRIMARY KEY AUTOINCREMENT,
                receipt_id TEXT NOT NULL UNIQUE,
                mission_id TEXT NOT NULL REFERENCES fleet_identity(mission_id),
                source_ref TEXT NOT NULL,
                previous_digest TEXT NOT NULL,
                receipt_digest TEXT NOT NULL UNIQUE,
                observed_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS fleet_source_batch(
                seq INTEGER PRIMARY KEY AUTOINCREMENT,
                source_id TEXT NOT NULL,
                source_kind TEXT NOT NULL,
                source_instance_id TEXT NOT NULL,
                source_implementation_digest TEXT NOT NULL,
                trust_anchor_id TEXT NOT NULL,
                source_identity_digest TEXT NOT NULL,
                source_sequence INTEGER NOT NULL,
                source_observed_at TEXT NOT NULL,
                ingested_at TEXT NOT NULL,
                read_digest TEXT NOT NULL,
                batch_digest TEXT NOT NULL UNIQUE,
                previous_source_chain_digest TEXT NOT NULL,
                source_chain_digest TEXT NOT NULL UNIQUE,
                UNIQUE(source_id, source_sequence)
            );

            CREATE TABLE IF NOT EXISTS fleet_source_observation(
                seq INTEGER PRIMARY KEY AUTOINCREMENT,
                batch_digest TEXT NOT NULL REFERENCES fleet_source_batch(batch_digest),
                observation_index INTEGER NOT NULL,
                observation_id TEXT NOT NULL,
                observation_digest TEXT NOT NULL,
                mission_id TEXT,
                drone_id TEXT,
                dimension TEXT NOT NULL,
                state TEXT NOT NULL,
                provenance_ref TEXT NOT NULL,
                evidence_digest TEXT NOT NULL,
                epistemic_class TEXT NOT NULL,
                observation_json TEXT NOT NULL,
                UNIQUE(batch_digest, observation_index),
                UNIQUE(batch_digest, observation_id)
            );

            CREATE TABLE IF NOT EXISTS fleet_source_checkpoint(
                source_id TEXT PRIMARY KEY,
                source_identity_digest TEXT NOT NULL,
                source_kind TEXT NOT NULL,
                source_instance_id TEXT NOT NULL,
                source_implementation_digest TEXT NOT NULL,
                trust_anchor_id TEXT NOT NULL,
                source_sequence INTEGER NOT NULL,
                source_observed_at TEXT NOT NULL,
                read_digest TEXT NOT NULL,
                batch_digest TEXT NOT NULL,
                source_chain_digest TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS fleet_source_decision(
                seq INTEGER PRIMARY KEY AUTOINCREMENT,
                decision_id TEXT NOT NULL UNIQUE,
                mission_id TEXT,
                drone_id TEXT,
                dimension TEXT NOT NULL,
                decision_type TEXT NOT NULL,
                decision_digest TEXT NOT NULL UNIQUE,
                decision_json TEXT NOT NULL,
                observed_at TEXT NOT NULL
            );

            CREATE TRIGGER IF NOT EXISTS fleet_event_no_update
            BEFORE UPDATE ON fleet_event BEGIN SELECT RAISE(ABORT,'fleet_event is append-only'); END;
            CREATE TRIGGER IF NOT EXISTS fleet_event_no_delete
            BEFORE DELETE ON fleet_event BEGIN SELECT RAISE(ABORT,'fleet_event is append-only'); END;
            CREATE TRIGGER IF NOT EXISTS fleet_receipt_no_update
            BEFORE UPDATE ON fleet_receipt BEGIN SELECT RAISE(ABORT,'fleet_receipt is append-only'); END;
            CREATE TRIGGER IF NOT EXISTS fleet_receipt_no_delete
            BEFORE DELETE ON fleet_receipt BEGIN SELECT RAISE(ABORT,'fleet_receipt is append-only'); END;
            CREATE TRIGGER IF NOT EXISTS fleet_source_batch_no_update
            BEFORE UPDATE ON fleet_source_batch BEGIN SELECT RAISE(ABORT,'fleet_source_batch is append-only'); END;
            CREATE TRIGGER IF NOT EXISTS fleet_source_batch_no_delete
            BEFORE DELETE ON fleet_source_batch BEGIN SELECT RAISE(ABORT,'fleet_source_batch is append-only'); END;
            CREATE TRIGGER IF NOT EXISTS fleet_source_observation_no_update
            BEFORE UPDATE ON fleet_source_observation BEGIN SELECT RAISE(ABORT,'fleet_source_observation is append-only'); END;
            CREATE TRIGGER IF NOT EXISTS fleet_source_observation_no_delete
            BEFORE DELETE ON fleet_source_observation BEGIN SELECT RAISE(ABORT,'fleet_source_observation is append-only'); END;
            CREATE TRIGGER IF NOT EXISTS fleet_source_decision_no_update
            BEFORE UPDATE ON fleet_source_decision BEGIN SELECT RAISE(ABORT,'fleet_source_decision is append-only'); END;
            CREATE TRIGGER IF NOT EXISTS fleet_source_decision_no_delete
            BEFORE DELETE ON fleet_source_decision BEGIN SELECT RAISE(ABORT,'fleet_source_decision is append-only'); END;
            """
        )

    def _bind_instance(self) -> None:
        row = self._conn.execute("SELECT * FROM fleet_meta WHERE singleton=1").fetchone()
        if row is None:
            self._conn.execute(
                "INSERT INTO fleet_meta(singleton,registry_instance_id,revision,event_head,receipt_head) VALUES(1,?,?,?,?)",
                (self._registry_instance_id, 0, "0" * 64, "0" * 64),
            )
        elif row["registry_instance_id"] != self._registry_instance_id:
            raise FleetStatusStateError("registry instance substitution denied")

    @contextmanager
    def _write(self) -> Iterator[sqlite3.Connection]:
        try:
            self._conn.execute("BEGIN IMMEDIATE")
            yield self._conn
            self._conn.execute("COMMIT")
        except Exception:
            if self._conn.in_transaction:
                self._conn.execute("ROLLBACK")
            raise

    def open_query_reader(self) -> sqlite3.Connection:
        """Return a capability-reduced query-only connection."""
        conn = sqlite3.connect(self._db_path, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA query_only=ON")
        return conn

    def _bump(self, c: sqlite3.Connection) -> None:
        c.execute("UPDATE fleet_meta SET revision=revision+1 WHERE singleton=1")

    def _append_event(
        self,
        c: sqlite3.Connection,
        *,
        event_type: str,
        mission_id: str | None,
        payload: dict[str, object],
        observed_at: str,
    ) -> str:
        meta = c.execute("SELECT event_head FROM fleet_meta WHERE singleton=1").fetchone()
        previous = meta["event_head"]
        digest = _event_digest(previous, event_type, mission_id, payload, observed_at)
        event_id = sha256((digest + event_type).encode()).hexdigest()
        c.execute(
            """INSERT INTO fleet_event(event_id,event_type,mission_id,payload_json,previous_digest,event_digest,observed_at)
               VALUES(?,?,?,?,?,?,?)""",
            (event_id, event_type, mission_id, canonical_json(payload).decode(), previous, digest, observed_at),
        )
        c.execute("UPDATE fleet_meta SET event_head=? WHERE singleton=1", (digest,))
        return event_id

    def verify_event_chain(self, conn: sqlite3.Connection | None = None) -> str:
        c = conn or self.open_query_reader()
        close = conn is None
        try:
            previous = "0" * 64
            last = previous
            for row in c.execute("SELECT * FROM fleet_event ORDER BY seq"):
                payload = json.loads(row["payload_json"])
                expected = _event_digest(previous, row["event_type"], row["mission_id"], payload, row["observed_at"])
                if row["previous_digest"] != previous or row["event_digest"] != expected:
                    raise FleetStatusStateError("event chain corruption")
                previous = expected
                last = expected
            meta = c.execute("SELECT event_head FROM fleet_meta WHERE singleton=1").fetchone()
            if meta["event_head"] != last:
                raise FleetStatusStateError("event chain head mismatch")
            return last
        finally:
            if close:
                c.close()

    def verify_receipt_chain(self, conn: sqlite3.Connection | None = None) -> str:
        c = conn or self.open_query_reader()
        close = conn is None
        try:
            previous = "0" * 64
            last = previous
            for row in c.execute("SELECT * FROM fleet_receipt ORDER BY seq"):
                expected = _receipt_digest(previous, row["receipt_id"], row["mission_id"], row["source_ref"], row["observed_at"])
                if row["previous_digest"] != previous or row["receipt_digest"] != expected:
                    raise FleetStatusStateError("receipt chain corruption")
                previous = expected
                last = expected
            meta = c.execute("SELECT receipt_head FROM fleet_meta WHERE singleton=1").fetchone()
            if meta["receipt_head"] != last:
                raise FleetStatusStateError("receipt chain head mismatch")
            return last
        finally:
            if close:
                c.close()

    def ingest_source_read(self, read: StatusSourceRead) -> SourceCheckpoint:
        """Journal one pinned read after adapter/trust validation; sequence is registry-owned."""
        if type(read) is not StatusSourceRead:
            raise FleetStatusStateError("source read must use exact contract type")
        read.validate()
        ingested_at = _now(self._clock)
        source_time = _parse_utc(read.source_observed_at)
        if source_time > _parse_utc(ingested_at):
            raise FleetStatusStateError("source observation time cannot be in the future")
        identity = read.source_identity
        identity_digest = identity.digest()
        read_digest = read.digest()
        with self._write() as c:
            checkpoint = c.execute(
                "SELECT * FROM fleet_source_checkpoint WHERE source_id=?",
                (identity.source_id,),
            ).fetchone()
            if checkpoint is None:
                sequence = 1
                previous_chain = "0" * 64
            else:
                expected_identity = (
                    checkpoint["source_identity_digest"], checkpoint["source_kind"],
                    checkpoint["source_instance_id"], checkpoint["source_implementation_digest"],
                    checkpoint["trust_anchor_id"],
                )
                actual_identity = (
                    identity_digest, identity.source_kind, identity.source_instance_id,
                    identity.source_implementation_digest, identity.trust_anchor_id,
                )
                if actual_identity != expected_identity:
                    raise FleetStatusStateError("source identity/implementation substitution denied")
                previous_time = _parse_utc(checkpoint["source_observed_at"])
                if source_time < previous_time:
                    raise FleetStatusStateError("source time regression denied")
                if source_time == previous_time:
                    if read_digest != checkpoint["read_digest"]:
                        raise FleetStatusStateError("same source time with different content denied")
                    return SourceCheckpoint(
                        identity.source_id, identity_digest, int(checkpoint["source_sequence"]),
                        checkpoint["source_observed_at"], checkpoint["read_digest"],
                        checkpoint["batch_digest"], checkpoint["source_chain_digest"],
                    ).validate()
                sequence = int(checkpoint["source_sequence"]) + 1
                previous_chain = checkpoint["source_chain_digest"]

            batch_digest = _source_batch_digest(identity_digest, sequence, read.source_observed_at, read_digest)
            source_chain_digest = _source_chain_digest(previous_chain, batch_digest)
            c.execute(
                """INSERT INTO fleet_source_batch(
                   source_id,source_kind,source_instance_id,source_implementation_digest,trust_anchor_id,
                   source_identity_digest,source_sequence,source_observed_at,ingested_at,read_digest,batch_digest,
                   previous_source_chain_digest,source_chain_digest
                   ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    identity.source_id, identity.source_kind, identity.source_instance_id,
                    identity.source_implementation_digest, identity.trust_anchor_id, identity_digest,
                    sequence, read.source_observed_at, ingested_at, read_digest, batch_digest,
                    previous_chain, source_chain_digest,
                ),
            )
            for index, observation in enumerate(read.observations):
                payload = observation.canonical_dict()
                c.execute(
                    """INSERT INTO fleet_source_observation(
                       batch_digest,observation_index,observation_id,observation_digest,mission_id,drone_id,
                       dimension,state,provenance_ref,evidence_digest,epistemic_class,observation_json
                       ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        batch_digest, index, observation.observation_id, observation.digest(),
                        observation.mission_id, observation.drone_id, observation.dimension, observation.state,
                        observation.provenance_ref, observation.evidence_digest, observation.epistemic_class,
                        source_canonical_json(payload).decode("utf-8"),
                    ),
                )
            c.execute(
                """INSERT INTO fleet_source_checkpoint(
                   source_id,source_identity_digest,source_kind,source_instance_id,source_implementation_digest,
                   trust_anchor_id,source_sequence,source_observed_at,read_digest,batch_digest,source_chain_digest
                   ) VALUES(?,?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(source_id) DO UPDATE SET
                   source_identity_digest=excluded.source_identity_digest,
                   source_kind=excluded.source_kind,
                   source_instance_id=excluded.source_instance_id,
                   source_implementation_digest=excluded.source_implementation_digest,
                   trust_anchor_id=excluded.trust_anchor_id,
                   source_sequence=excluded.source_sequence,
                   source_observed_at=excluded.source_observed_at,
                   read_digest=excluded.read_digest,
                   batch_digest=excluded.batch_digest,
                   source_chain_digest=excluded.source_chain_digest""",
                (
                    identity.source_id, identity_digest, identity.source_kind, identity.source_instance_id,
                    identity.source_implementation_digest, identity.trust_anchor_id, sequence,
                    read.source_observed_at, read_digest, batch_digest, source_chain_digest,
                ),
            )
            self._append_event(
                c,
                event_type="SOURCE_BATCH_INGESTED",
                mission_id=None,
                payload={
                    "source_id": identity.source_id,
                    "source_sequence": sequence,
                    "batch_digest": batch_digest,
                    "source_chain_digest": source_chain_digest,
                },
                observed_at=ingested_at,
            )
            self._bump(c)
        return SourceCheckpoint(
            identity.source_id, identity_digest, sequence, read.source_observed_at,
            read_digest, batch_digest, source_chain_digest,
        ).validate()

    def verify_source_chains(self, conn: sqlite3.Connection | None = None) -> dict[str, str]:
        c = conn or self.open_query_reader()
        close = conn is None
        try:
            heads: dict[str, str] = {}
            sources = [row[0] for row in c.execute("SELECT DISTINCT source_id FROM fleet_source_batch ORDER BY source_id")]
            for source_id in sources:
                previous = "0" * 64
                expected_sequence = 1
                last_batch = None
                for batch in c.execute("SELECT * FROM fleet_source_batch WHERE source_id=? ORDER BY source_sequence", (source_id,)):
                    if int(batch["source_sequence"]) != expected_sequence:
                        raise FleetStatusStateError("source sequence gap/corruption")
                    identity = StatusSourceIdentity(
                        batch["source_id"], batch["source_kind"], batch["source_instance_id"],
                        batch["source_implementation_digest"], batch["trust_anchor_id"],
                    ).validate()
                    if identity.digest() != batch["source_identity_digest"]:
                        raise FleetStatusStateError("source identity digest corruption")
                    observation_digests: list[str] = []
                    observations = c.execute(
                        "SELECT * FROM fleet_source_observation WHERE batch_digest=? ORDER BY observation_index",
                        (batch["batch_digest"],),
                    ).fetchall()
                    for index, observation in enumerate(observations):
                        if int(observation["observation_index"]) != index:
                            raise FleetStatusStateError("source observation index corruption")
                        payload = json.loads(observation["observation_json"])
                        if not isinstance(payload, dict):
                            raise FleetStatusStateError("source observation payload corruption")
                        typed = dict(payload)
                        items = typed.get("value_items")
                        if not isinstance(items, list) or any(not isinstance(item, list) or len(item) != 2 for item in items):
                            raise FleetStatusStateError("source observation value_items corruption")
                        typed["value_items"] = tuple((str(item[0]), str(item[1])) for item in items)
                        try:
                            StatusSourceObservation(**typed).validate()
                        except Exception as exc:
                            raise FleetStatusStateError("source observation contract corruption") from exc
                        digest = sha256(source_canonical_json(payload)).hexdigest()
                        if digest != observation["observation_digest"]:
                            raise FleetStatusStateError("source observation digest corruption")
                        if payload.get("observation_id") != observation["observation_id"]:
                            raise FleetStatusStateError("source observation identity corruption")
                        observation_digests.append(digest)
                    read_digest = sha256(source_canonical_json({
                        "source_identity": identity.canonical_dict(),
                        "source_observed_at": batch["source_observed_at"],
                        "observation_digests": observation_digests,
                    })).hexdigest()
                    if read_digest != batch["read_digest"]:
                        raise FleetStatusStateError("source read digest corruption")
                    expected_batch = _source_batch_digest(
                        batch["source_identity_digest"], int(batch["source_sequence"]),
                        batch["source_observed_at"], batch["read_digest"],
                    )
                    if expected_batch != batch["batch_digest"]:
                        raise FleetStatusStateError("source batch digest corruption")
                    expected_chain = _source_chain_digest(previous, expected_batch)
                    if batch["previous_source_chain_digest"] != previous or batch["source_chain_digest"] != expected_chain:
                        raise FleetStatusStateError("source hash chain corruption")
                    previous = expected_chain
                    last_batch = batch
                    expected_sequence += 1
                checkpoint = c.execute("SELECT * FROM fleet_source_checkpoint WHERE source_id=?", (source_id,)).fetchone()
                if checkpoint is None or last_batch is None:
                    raise FleetStatusStateError("source checkpoint missing")
                if (
                    int(checkpoint["source_sequence"]) != int(last_batch["source_sequence"])
                    or checkpoint["batch_digest"] != last_batch["batch_digest"]
                    or checkpoint["source_chain_digest"] != previous
                    or checkpoint["read_digest"] != last_batch["read_digest"]
                    or checkpoint["source_observed_at"] != last_batch["source_observed_at"]
                ):
                    raise FleetStatusStateError("source checkpoint corruption")
                heads[source_id] = previous
            return heads
        finally:
            if close:
                c.close()

    def verify_source_decisions(self, conn: sqlite3.Connection | None = None) -> None:
        c = conn or self.open_query_reader()
        close = conn is None
        try:
            for row in c.execute("SELECT * FROM fleet_source_decision ORDER BY seq"):
                try:
                    payload = json.loads(row["decision_json"])
                except json.JSONDecodeError as exc:
                    raise FleetStatusStateError("source decision JSON corruption") from exc
                if not isinstance(payload, dict) or payload.get("decision_type") != row["decision_type"]:
                    raise FleetStatusStateError("source decision type corruption")
                digest = sha256(source_canonical_json(payload)).hexdigest()
                if digest != row["decision_digest"]:
                    raise FleetStatusStateError("source decision digest corruption")
                dtype = row["decision_type"]
                try:
                    if dtype == "FACT":
                        value = dict(payload["fact"])
                        value["value_items"] = tuple(tuple(item) for item in value["value_items"])
                        value["source_ids"] = tuple(value["source_ids"])
                        value["evidence_refs"] = tuple(value["evidence_refs"])
                        ReconciledStatusFact(**value).validate()
                    elif dtype == "CONFLICT":
                        value = dict(payload["conflict"])
                        value["source_ids"] = tuple(value["source_ids"])
                        value["observation_ids"] = tuple(value["observation_ids"])
                        value["evidence_refs"] = tuple(value["evidence_refs"])
                        SourceConflict(**value).validate()
                    elif dtype == "MISSING":
                        value = dict(payload["missing"])
                        value["expected_source_kinds"] = tuple(value["expected_source_kinds"])
                        MissingStatusSource(**value).validate()
                    else:
                        raise FleetStatusStateError("unknown source decision type")
                except FleetStatusStateError:
                    raise
                except Exception as exc:
                    raise FleetStatusStateError("source decision contract corruption") from exc
        finally:
            if close:
                c.close()

    def source_observation_rows(
        self,
        conn: sqlite3.Connection | None = None,
        *,
        current_only: bool = True,
    ) -> list[dict[str, object]]:
        c = conn or self.open_query_reader()
        close = conn is None
        try:
            if current_only:
                rows = c.execute(
                    """SELECT b.source_id,b.source_kind,b.source_instance_id,b.source_implementation_digest,
                       b.trust_anchor_id,b.source_sequence,b.source_observed_at,b.ingested_at,b.batch_digest,
                       b.source_chain_digest,o.observation_json
                       FROM fleet_source_batch b
                       JOIN fleet_source_checkpoint cp
                         ON cp.source_id=b.source_id AND cp.source_sequence=b.source_sequence
                       JOIN fleet_source_observation o ON b.batch_digest=o.batch_digest
                       ORDER BY b.source_id,o.observation_index"""
                ).fetchall()
            else:
                rows = c.execute(
                    """SELECT b.source_id,b.source_kind,b.source_instance_id,b.source_implementation_digest,
                       b.trust_anchor_id,b.source_sequence,b.source_observed_at,b.ingested_at,b.batch_digest,
                       b.source_chain_digest,o.observation_json
                       FROM fleet_source_observation o JOIN fleet_source_batch b ON b.batch_digest=o.batch_digest
                       ORDER BY b.source_id,b.source_sequence,o.observation_index"""
                ).fetchall()
            return [dict(row) for row in rows]
        finally:
            if close:
                c.close()

    def source_checkpoints(self, conn: sqlite3.Connection | None = None) -> list[dict[str, object]]:
        c = conn or self.open_query_reader()
        close = conn is None
        try:
            rows = c.execute("SELECT * FROM fleet_source_checkpoint ORDER BY source_id").fetchall()
            return [dict(row) for row in rows]
        finally:
            if close:
                c.close()

    def record_source_decisions(
        self,
        facts: tuple[ReconciledStatusFact, ...],
        conflicts: tuple[SourceConflict, ...],
        missing: tuple[MissingStatusSource, ...] = (),
    ) -> None:
        if type(facts) is not tuple or type(conflicts) is not tuple or type(missing) is not tuple:
            raise FleetStatusStateError("source decisions must be tuples")
        observed_at = _now(self._clock)
        decisions: list[tuple[str, str | None, str | None, str, str, str, str]] = []
        for fact in facts:
            if type(fact) is not ReconciledStatusFact:
                raise FleetStatusStateError("invalid reconciled fact")
            fact.validate()
            payload = {
                "decision_type": "FACT",
                "decision_observed_at": observed_at,
                "fact": {
                    **asdict(fact),
                    "value_items": [list(item) for item in fact.value_items],
                    "source_ids": list(fact.source_ids),
                    "evidence_refs": list(fact.evidence_refs),
                },
            }
            raw = source_canonical_json(payload)
            digest = sha256(raw).hexdigest()
            decision_id = f"fact:{fact.mission_id}:{fact.dimension}:{digest}"
            decisions.append((decision_id, fact.mission_id, fact.value_dict().get("drone_id"), fact.dimension, "FACT", digest, raw.decode()))
        for conflict in conflicts:
            if type(conflict) is not SourceConflict:
                raise FleetStatusStateError("invalid source conflict")
            conflict.validate()
            payload = {
                "decision_type": "CONFLICT",
                "decision_observed_at": observed_at,
                "conflict": {
                    **asdict(conflict),
                    "source_ids": list(conflict.source_ids),
                    "observation_ids": list(conflict.observation_ids),
                    "evidence_refs": list(conflict.evidence_refs),
                },
            }
            raw = source_canonical_json(payload)
            digest = sha256(raw).hexdigest()
            decision_id = f"conflict:{conflict.conflict_id}:{digest}"
            decisions.append((decision_id, conflict.mission_id, conflict.drone_id, conflict.dimension, "CONFLICT", digest, raw.decode()))
        for item in missing:
            if type(item) is not MissingStatusSource:
                raise FleetStatusStateError("invalid missing source decision")
            item.validate()
            payload = {
                "decision_type": "MISSING",
                "decision_observed_at": observed_at,
                "missing": {
                    **asdict(item),
                    "expected_source_kinds": list(item.expected_source_kinds),
                },
            }
            raw = source_canonical_json(payload)
            digest = sha256(raw).hexdigest()
            decision_id = f"missing:{item.mission_id}:{item.dimension}:{digest}"
            decisions.append((decision_id, item.mission_id, item.drone_id, item.dimension, "MISSING", digest, raw.decode()))
        if not decisions:
            return
        with self._write() as c:
            inserted = 0
            for decision_id, mission_id, drone_id, dimension, decision_type, digest, raw in decisions:
                cursor = c.execute(
                    """INSERT OR IGNORE INTO fleet_source_decision(
                       decision_id,mission_id,drone_id,dimension,decision_type,decision_digest,decision_json,observed_at
                       ) VALUES(?,?,?,?,?,?,?,?)""",
                    (decision_id, mission_id, drone_id, dimension, decision_type, digest, raw, observed_at),
                )
                inserted += cursor.rowcount
            if inserted:
                self._append_event(
                    c, event_type="SOURCE_RECONCILIATION_DECISION", mission_id=None,
                    payload={"inserted": inserted}, observed_at=observed_at,
                )
                self._bump(c)

    def latest_source_decisions(self, conn: sqlite3.Connection | None = None) -> list[dict[str, object]]:
        c = conn or self.open_query_reader()
        close = conn is None
        try:
            rows = c.execute(
                """SELECT d.* FROM fleet_source_decision d
                   JOIN (
                     SELECT COALESCE(mission_id,'' ) AS mission_key,dimension,MAX(seq) AS max_seq
                     FROM fleet_source_decision GROUP BY COALESCE(mission_id,''),dimension
                   ) x ON COALESCE(d.mission_id,'')=x.mission_key AND d.dimension=x.dimension AND d.seq=x.max_seq
                   ORDER BY d.seq"""
            ).fetchall()
            return [dict(row) for row in rows]
        finally:
            if close:
                c.close()

    def identity_row(self, mission_id: str) -> dict[str, object] | None:
        reader = self.open_query_reader()
        try:
            row = reader.execute("SELECT * FROM fleet_identity WHERE mission_id=?", (mission_id,)).fetchone()
            return dict(row) if row is not None else None
        finally:
            reader.close()

    def runtime_row(self, mission_id: str) -> dict[str, object] | None:
        reader = self.open_query_reader()
        try:
            row = reader.execute("SELECT * FROM fleet_runtime WHERE mission_id=?", (mission_id,)).fetchone()
            return dict(row) if row is not None else None
        finally:
            reader.close()

    def has_receipt(self, receipt_id: str) -> bool:
        reader = self.open_query_reader()
        try:
            return reader.execute("SELECT 1 FROM fleet_receipt WHERE receipt_id=?", (receipt_id,)).fetchone() is not None
        finally:
            reader.close()

    def register_identity(self, identity: FleetStatusIdentity) -> None:
        identity.validate()
        observed_at = _now(self._clock)
        with self._write() as c:
            c.execute(
                """INSERT INTO fleet_identity(
                   drone_id,executor_id,mission_id,parent_mission_id,repository,baseline_sha,baseline_tree_sha,
                   branch,read_scope_json,write_scope_json,sandbox_id,identity_digest
                   ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    identity.drone_id, identity.executor_id, identity.mission_id, identity.parent_mission_id,
                    identity.repository, identity.baseline_sha, identity.baseline_tree_sha, identity.branch,
                    json.dumps(identity.read_scope), json.dumps(identity.write_scope), identity.sandbox_id, identity.digest(),
                ),
            )
            self._append_event(
                c, event_type="IDENTITY_REGISTERED", mission_id=identity.mission_id,
                payload={"identity_digest": identity.digest()}, observed_at=observed_at,
            )
            self._bump(c)

    def set_mission_state(
        self,
        mission_id: str,
        *,
        phase: str,
        status: str,
        closure_state: str = "OPEN",
        current_operation: str | None = None,
        current_blocker: str | None = None,
        dependency_state: str = "READY",
        branch_head: str | None = None,
    ) -> None:
        if status == "DONE" or closure_state == "CLOSED":
            raise FleetStatusStateError("DONE/CLOSED require dedicated evidence-gated transition")
        observed_at = _now(self._clock)
        with self._write() as c:
            if c.execute("SELECT 1 FROM fleet_identity WHERE mission_id=?", (mission_id,)).fetchone() is None:
                raise FleetStatusStateError("unknown mission")
            c.execute(
                """INSERT INTO fleet_mission(mission_id,phase,status,closure_state,current_operation,current_blocker,
                   dependency_state,branch_head,observed_at) VALUES(?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(mission_id) DO UPDATE SET phase=excluded.phase,status=excluded.status,
                   closure_state=excluded.closure_state,current_operation=excluded.current_operation,
                   current_blocker=excluded.current_blocker,dependency_state=excluded.dependency_state,
                   branch_head=excluded.branch_head,observed_at=excluded.observed_at""",
                (mission_id, phase, status, closure_state, current_operation, current_blocker, dependency_state, branch_head, observed_at),
            )
            self._append_event(c, event_type="MISSION_STATE", mission_id=mission_id,
                               payload={"phase": phase, "status": status, "closure_state": closure_state}, observed_at=observed_at)
            self._bump(c)

    def bind_runtime(self, mission_id: str, runtime_id: str, evidence_ref: str) -> None:
        if not runtime_id or not evidence_ref:
            raise FleetStatusStateError("runtime binding invalid")
        observed_at = _now(self._clock)
        with self._write() as c:
            if c.execute("SELECT 1 FROM fleet_identity WHERE mission_id=?", (mission_id,)).fetchone() is None:
                raise FleetStatusStateError("unknown mission")
            try:
                c.execute("INSERT INTO fleet_runtime(mission_id,runtime_id,evidence_ref,bound_at) VALUES(?,?,?,?)",
                          (mission_id, runtime_id, evidence_ref, observed_at))
            except sqlite3.IntegrityError as exc:
                raise FleetStatusStateError("runtime substitution or duplicate binding denied") from exc
            self._append_event(c, event_type="RUNTIME_BOUND", mission_id=mission_id,
                               payload={"runtime_id": runtime_id, "evidence_ref": evidence_ref}, observed_at=observed_at)
            self._bump(c)

    def heartbeat(self, mission_id: str, runtime_id: str, *, sequence: int, deadline_seconds: int, source_ref: str) -> None:
        if isinstance(sequence, bool) or not isinstance(sequence, int) or sequence < 1:
            raise FleetStatusStateError("heartbeat sequence invalid")
        if isinstance(deadline_seconds, bool) or not isinstance(deadline_seconds, int) or deadline_seconds <= 0:
            raise FleetStatusStateError("heartbeat deadline invalid")
        if not source_ref:
            raise FleetStatusStateError("heartbeat source missing")
        observed_at = _now(self._clock)
        with self._write() as c:
            runtime = c.execute("SELECT runtime_id FROM fleet_runtime WHERE mission_id=?", (mission_id,)).fetchone()
            if runtime is None or runtime["runtime_id"] != runtime_id:
                raise FleetStatusStateError("heartbeat runtime mismatch")
            old = c.execute("SELECT sequence,observed_at FROM fleet_heartbeat WHERE mission_id=?", (mission_id,)).fetchone()
            if old is not None:
                if sequence <= old["sequence"]:
                    raise FleetStatusStateError("heartbeat sequence rollback")
                if observed_at <= old["observed_at"]:
                    raise FleetStatusStateError("heartbeat time rollback")
            c.execute(
                """INSERT INTO fleet_heartbeat(mission_id,runtime_id,sequence,deadline_seconds,source_ref,observed_at)
                   VALUES(?,?,?,?,?,?)
                   ON CONFLICT(mission_id) DO UPDATE SET runtime_id=excluded.runtime_id,sequence=excluded.sequence,
                   deadline_seconds=excluded.deadline_seconds,source_ref=excluded.source_ref,observed_at=excluded.observed_at""",
                (mission_id, runtime_id, sequence, deadline_seconds, source_ref, observed_at),
            )
            self._append_event(c, event_type="HEARTBEAT", mission_id=mission_id,
                               payload={"runtime_id": runtime_id, "sequence": sequence, "deadline_seconds": deadline_seconds, "source_ref": source_ref},
                               observed_at=observed_at)
            self._bump(c)

    def project_observed_state(self, mission_id: str, *, kind: str, state: str, source_ref: str) -> None:
        """Ingest an OBSERVED adapter fact; caller cannot label it ANCHORED/PASS."""
        allowed = {
            "authority": AUTHORITY_STATES,
            "sandbox": SANDBOX_STATES,
            "effect": EFFECT_STATES,
            "reconciliation": RECONCILIATION_STATES,
        }
        if kind not in allowed or state not in allowed[kind] or state == "UNKNOWN":
            raise FleetStatusStateError("projection kind/state invalid")
        if not source_ref:
            raise FleetStatusStateError("projection source missing")
        observed_at = _now(self._clock)
        with self._write() as c:
            if c.execute("SELECT 1 FROM fleet_identity WHERE mission_id=?", (mission_id,)).fetchone() is None:
                raise FleetStatusStateError("unknown mission")
            c.execute(
                """INSERT INTO fleet_projection(mission_id,kind,state,source_ref,observed_at) VALUES(?,?,?,?,?)
                   ON CONFLICT(mission_id,kind) DO UPDATE SET state=excluded.state,source_ref=excluded.source_ref,
                   observed_at=excluded.observed_at""",
                (mission_id, kind, state, source_ref, observed_at),
            )
            self._append_event(c, event_type=f"{kind.upper()}_OBSERVED", mission_id=mission_id,
                               payload={"state": state, "source_ref": source_ref}, observed_at=observed_at)
            self._bump(c)

    def project_verification(self, verification_id: str) -> TrustedVerificationEvidence:
        """Resolve from the composition-root source; raw evidence is never a caller parameter."""
        evidence = self._verification_source.resolve(verification_id)
        if type(evidence) is not TrustedVerificationEvidence:
            raise FleetStatusStateError("verification source returned invalid type")
        try:
            evidence.validate()
        except FleetStatusContractError as exc:
            raise FleetStatusStateError("verification evidence invalid") from exc
        pins = self._verification_pins
        expected = (
            pins.verifier_id, pins.verifier_identity_digest, pins.verifier_implementation_digest,
            pins.trust_anchor_id, pins.trust_anchor_digest,
        )
        actual = (
            evidence.verifier_id, evidence.verifier_identity_digest, evidence.verifier_implementation_digest,
            evidence.trust_anchor_id, evidence.trust_anchor_digest,
        )
        if actual != expected:
            raise FleetStatusStateError("verification source/pin substitution denied")
        observed_at = _now(self._clock)
        with self._write() as c:
            identity = c.execute("SELECT drone_id,executor_id FROM fleet_identity WHERE mission_id=?", (evidence.mission_id,)).fetchone()
            if identity is None:
                raise FleetStatusStateError("verification mission unknown")
            if identity["drone_id"] != evidence.drone_id or identity["executor_id"] != evidence.executor_id:
                raise FleetStatusStateError("verification identity binding mismatch")
            c.execute(
                """INSERT INTO fleet_verification(
                   mission_id,verification_id,verification_state,verifier_id,verifier_identity_digest,
                   verifier_implementation_digest,trust_anchor_id,trust_anchor_digest,evidence_digest,
                   source_provenance_ref,epistemic_class,observed_at,binding_digest
                   ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(mission_id) DO UPDATE SET verification_id=excluded.verification_id,
                   verification_state=excluded.verification_state,verifier_id=excluded.verifier_id,
                   verifier_identity_digest=excluded.verifier_identity_digest,
                   verifier_implementation_digest=excluded.verifier_implementation_digest,
                   trust_anchor_id=excluded.trust_anchor_id,trust_anchor_digest=excluded.trust_anchor_digest,
                   evidence_digest=excluded.evidence_digest,source_provenance_ref=excluded.source_provenance_ref,
                   epistemic_class=excluded.epistemic_class,observed_at=excluded.observed_at,
                   binding_digest=excluded.binding_digest""",
                (
                    evidence.mission_id, evidence.verification_id, evidence.verification_state, evidence.verifier_id,
                    evidence.verifier_identity_digest, evidence.verifier_implementation_digest, evidence.trust_anchor_id,
                    evidence.trust_anchor_digest, evidence.evidence_digest, evidence.source_provenance_ref,
                    evidence.epistemic_class, evidence.observed_at, evidence.binding_digest(),
                ),
            )
            self._append_event(c, event_type="VERIFICATION_PROJECTED", mission_id=evidence.mission_id,
                               payload={"verification_id": verification_id, "binding_digest": evidence.binding_digest()},
                               observed_at=observed_at)
            self._bump(c)
        return evidence

    def mark_verified_done(
        self,
        mission_id: str,
        *,
        phase: str = "VERIFY",
        branch_head: str | None = None,
        current_operation: str | None = None,
        current_blocker: str | None = None,
        dependency_state: str = "READY",
    ) -> None:
        observed_at = _now(self._clock)
        with self._write() as c:
            row = c.execute(
                """SELECT i.drone_id,i.executor_id,v.* FROM fleet_identity i
                   JOIN fleet_verification v ON v.mission_id=i.mission_id WHERE i.mission_id=?""",
                (mission_id,),
            ).fetchone()
            if row is None or row["verification_state"] != "PASS" or row["epistemic_class"] not in {"OBSERVED", "ANCHORED"}:
                raise FleetStatusStateError("trusted independent PASS required")
            if row["verifier_id"] in {row["drone_id"], row["executor_id"]}:
                raise FleetStatusStateError("verifier is not independent")
            c.execute(
                """INSERT INTO fleet_mission(mission_id,phase,status,closure_state,current_operation,current_blocker,
                   dependency_state,branch_head,observed_at)
                   VALUES(?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(mission_id) DO UPDATE SET phase=excluded.phase,status='DONE',
                   closure_state='READY_TO_CLOSE',current_operation=excluded.current_operation,
                   current_blocker=excluded.current_blocker,dependency_state=excluded.dependency_state,
                   branch_head=excluded.branch_head,observed_at=excluded.observed_at""",
                (mission_id, phase, "DONE", "READY_TO_CLOSE", current_operation, current_blocker, dependency_state, branch_head, observed_at),
            )
            self._append_event(c, event_type="MISSION_DONE", mission_id=mission_id,
                               payload={"verification_id": row["verification_id"]}, observed_at=observed_at)
            self._bump(c)

    def record_lease(self, mission_id: str, *, lease_id: str, lease_type: str, resource: str, state: str, source_ref: str) -> None:
        if lease_type not in {"REPOSITORY", "BRANCH", "PATH"} or state not in {"ACTIVE", "STALE_HELD", "RELEASED"}:
            raise FleetStatusStateError("lease invalid")
        if not lease_id or not resource or not source_ref:
            raise FleetStatusStateError("lease fields missing")
        observed_at = _now(self._clock)
        with self._write() as c:
            identity = c.execute("SELECT repository FROM fleet_identity WHERE mission_id=?", (mission_id,)).fetchone()
            if identity is None:
                raise FleetStatusStateError("unknown mission")
            if state in {"ACTIVE", "STALE_HELD"}:
                active = c.execute(
                    """SELECT l.lease_type,l.resource,i.repository FROM fleet_lease l
                       JOIN fleet_identity i ON i.mission_id=l.mission_id
                       WHERE l.state IN ('ACTIVE','STALE_HELD') AND l.lease_id<>?""",
                    (lease_id,),
                ).fetchall()
                for row in active:
                    if row["repository"] != identity["repository"] or row["lease_type"] != lease_type:
                        continue
                    if lease_type in {"REPOSITORY", "BRANCH"} and row["resource"] == resource:
                        raise FleetStatusStateError("duplicate active write lease")
                    if lease_type == "PATH":
                        a = resource.rstrip("/")
                        b = row["resource"].rstrip("/")
                        if a == b or a.startswith(b + "/") or b.startswith(a + "/"):
                            raise FleetStatusStateError("overlapping active path lease")
            c.execute(
                """INSERT INTO fleet_lease(lease_id,mission_id,lease_type,resource,state,source_ref,observed_at)
                   VALUES(?,?,?,?,?,?,?)
                   ON CONFLICT(lease_id) DO UPDATE SET state=excluded.state,source_ref=excluded.source_ref,
                   observed_at=excluded.observed_at""",
                (lease_id, mission_id, lease_type, resource, state, source_ref, observed_at),
            )
            self._append_event(c, event_type="LEASE_STATE", mission_id=mission_id,
                               payload={"lease_id": lease_id, "lease_type": lease_type, "resource": resource, "state": state},
                               observed_at=observed_at)
            self._bump(c)

    def append_receipt(self, mission_id: str, *, receipt_id: str, source_ref: str) -> str:
        if not receipt_id or not source_ref:
            raise FleetStatusStateError("receipt invalid")
        observed_at = _now(self._clock)
        with self._write() as c:
            if c.execute("SELECT 1 FROM fleet_identity WHERE mission_id=?", (mission_id,)).fetchone() is None:
                raise FleetStatusStateError("unknown mission")
            previous = c.execute("SELECT receipt_head FROM fleet_meta WHERE singleton=1").fetchone()["receipt_head"]
            digest = _receipt_digest(previous, receipt_id, mission_id, source_ref, observed_at)
            c.execute(
                """INSERT INTO fleet_receipt(receipt_id,mission_id,source_ref,previous_digest,receipt_digest,observed_at)
                   VALUES(?,?,?,?,?,?)""",
                (receipt_id, mission_id, source_ref, previous, digest, observed_at),
            )
            c.execute("UPDATE fleet_meta SET receipt_head=? WHERE singleton=1", (digest,))
            self._append_event(c, event_type="RECEIPT_APPENDED", mission_id=mission_id,
                               payload={"receipt_id": receipt_id, "receipt_digest": digest}, observed_at=observed_at)
            self._bump(c)
            return digest

    def close_mission(self, mission_id: str) -> None:
        observed_at = _now(self._clock)
        self.verify_event_chain()
        self.verify_receipt_chain()
        self.verify_source_chains()
        self.verify_source_decisions()
        with self._write() as c:
            mission = c.execute("SELECT * FROM fleet_mission WHERE mission_id=?", (mission_id,)).fetchone()
            if mission is None or mission["status"] not in TERMINAL_MISSIONS:
                raise FleetStatusStateError("terminal mission required")
            if mission["status"] == "DONE":
                verification = c.execute("SELECT verification_state FROM fleet_verification WHERE mission_id=?", (mission_id,)).fetchone()
                if verification is None or verification["verification_state"] != "PASS":
                    raise FleetStatusStateError("verification evidence incomplete")
            active_conflict = c.execute(
                """SELECT 1 FROM fleet_source_decision d
                   JOIN (
                     SELECT dimension,MAX(seq) AS max_seq FROM fleet_source_decision
                     WHERE mission_id=? GROUP BY dimension
                   ) x ON d.dimension=x.dimension AND d.seq=x.max_seq
                   WHERE d.mission_id=? AND d.decision_type='CONFLICT' LIMIT 1""",
                (mission_id, mission_id),
            ).fetchone()
            if active_conflict is not None:
                raise FleetStatusStateError("active source conflict prevents closure")
            for kind, terminal in (
                ("authority", TERMINAL_AUTHORITY),
                ("effect", TERMINAL_EFFECT),
                ("reconciliation", TERMINAL_RECONCILIATION),
            ):
                row = c.execute("SELECT state FROM fleet_projection WHERE mission_id=? AND kind=?", (mission_id, kind)).fetchone()
                if row is None or row["state"] not in terminal:
                    raise FleetStatusStateError(f"{kind} evidence incomplete")
            sandbox = c.execute("SELECT state FROM fleet_projection WHERE mission_id=? AND kind='sandbox'", (mission_id,)).fetchone()
            if sandbox is None:
                raise FleetStatusStateError("sandbox evidence incomplete")
            lease = c.execute("SELECT 1 FROM fleet_lease WHERE mission_id=? AND state IN ('ACTIVE','STALE_HELD')", (mission_id,)).fetchone()
            if lease is not None:
                raise FleetStatusStateError("active write lease prevents closure")
            receipt = c.execute("SELECT receipt_id FROM fleet_receipt WHERE mission_id=? ORDER BY seq DESC LIMIT 1", (mission_id,)).fetchone()
            if receipt is None:
                raise FleetStatusStateError("valid receipt chain evidence required")
            c.execute("UPDATE fleet_mission SET phase='CLOSE',closure_state='CLOSED',observed_at=? WHERE mission_id=?",
                      (observed_at, mission_id))
            self._append_event(c, event_type="MISSION_CLOSED", mission_id=mission_id,
                               payload={"last_receipt_id": receipt["receipt_id"]}, observed_at=observed_at)
            self._bump(c)

    def snapshot_rows(self) -> dict[str, object]:
        """One read transaction, one trusted time, all chains valid or unavailable."""
        conn = self.open_query_reader()
        try:
            conn.execute("BEGIN")
            self.verify_event_chain(conn)
            receipt_head = self.verify_receipt_chain(conn)
            source_heads = self.verify_source_chains(conn)
            self.verify_source_decisions(conn)
            meta = dict(conn.execute("SELECT * FROM fleet_meta WHERE singleton=1").fetchone())
            data = {
                "observed_at": _now(self._clock),
                "meta": meta,
                "identities": [dict(r) for r in conn.execute("SELECT * FROM fleet_identity ORDER BY drone_id")],
                "missions": {r["mission_id"]: dict(r) for r in conn.execute("SELECT * FROM fleet_mission")},
                "runtimes": {r["mission_id"]: dict(r) for r in conn.execute("SELECT * FROM fleet_runtime")},
                "heartbeats": {r["mission_id"]: dict(r) for r in conn.execute("SELECT * FROM fleet_heartbeat")},
                "projections": {(r["mission_id"], r["kind"]): dict(r) for r in conn.execute("SELECT * FROM fleet_projection")},
                "verifications": {r["mission_id"]: dict(r) for r in conn.execute("SELECT * FROM fleet_verification")},
                "leases": [dict(r) for r in conn.execute("SELECT * FROM fleet_lease")],
                "receipts": [dict(r) for r in conn.execute("SELECT * FROM fleet_receipt ORDER BY seq")],
                "receipt_head": receipt_head,
                "source_heads": source_heads,
                "source_observations": self.source_observation_rows(conn),
                "source_decisions": self.latest_source_decisions(conn),
            }
            conn.execute("COMMIT")
            return data
        except Exception:
            if conn.in_transaction:
                conn.execute("ROLLBACK")
            raise
        finally:
            conn.close()
