"""Authoritative single-store fleet aggregate effect budget provider.

This provider is a coordination restriction only.  It consumes no AuthorityGrant and
cannot mint authority.  A caller must first prove authority independently, then present
the derived authority_effect_key in an exact reservation request.
"""
from __future__ import annotations

from contextlib import closing
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from threading import RLock
from typing import Callable

from cyber_lion.contracts.fleet_effect_budget import (
    FleetEffectBudgetContractError,
    FleetEffectBudgetSnapshot,
    FleetEffectEnvelope,
    FleetEffectReservation,
    FleetEffectReservationRequest,
)


class FleetEffectBudgetError(RuntimeError):
    pass


class FleetEffectBudgetStore:
    """Linearizable SQLite reference provider for one authoritative fleet envelope."""

    dependency_id = "fleet-effect-budget-store"

    def __init__(
        self,
        db_path: str | Path,
        *,
        envelope: FleetEffectEnvelope,
        clock: Callable[[], datetime],
        identity_digest: str,
        implementation_digest: str,
    ) -> None:
        if type(envelope) is not FleetEffectEnvelope:
            raise FleetEffectBudgetError("exact FleetEffectEnvelope required")
        envelope.validate()
        if not callable(clock):
            raise FleetEffectBudgetError("trusted clock required")
        for name, value in (("identity_digest", identity_digest), ("implementation_digest", implementation_digest)):
            if not isinstance(value, str) or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
                raise FleetEffectBudgetError(f"{name} invalid")
        self.identity_digest = identity_digest
        self.implementation_digest = implementation_digest
        self._path = str(Path(db_path))
        self._envelope = envelope
        self._clock = clock
        self._lock = RLock()
        Path(self._path).parent.mkdir(parents=True, exist_ok=True)
        self._initialize()
        self._bind_envelope()

    @property
    def db_path(self) -> str:
        return self._path

    @property
    def envelope(self) -> FleetEffectEnvelope:
        return self._envelope

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._path, timeout=10.0, isolation_level=None, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=FULL")
        return conn

    def _now(self) -> datetime:
        value = self._clock()
        if type(value) is not datetime or value.tzinfo is None:
            raise FleetEffectBudgetError("trusted clock returned invalid time")
        return value.astimezone(timezone.utc)

    def _initialize(self) -> None:
        with closing(self._connect()) as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS fleet_effect_budget_meta(
                    singleton INTEGER PRIMARY KEY CHECK(singleton=1),
                    envelope_id TEXT NOT NULL,
                    fleet_id TEXT NOT NULL,
                    generation INTEGER NOT NULL,
                    envelope_digest TEXT NOT NULL,
                    policy_digest TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS fleet_effect_reservation(
                    reservation_id TEXT PRIMARY KEY,
                    request_digest TEXT NOT NULL UNIQUE,
                    effect_id TEXT NOT NULL UNIQUE,
                    mission_id TEXT NOT NULL,
                    executor_id TEXT NOT NULL,
                    runtime_id TEXT NOT NULL,
                    repository TEXT NOT NULL,
                    branch TEXT NOT NULL,
                    changed_paths_json TEXT NOT NULL,
                    authority_effect_key TEXT NOT NULL UNIQUE,
                    authority_epoch INTEGER NOT NULL,
                    envelope_id TEXT NOT NULL,
                    envelope_generation INTEGER NOT NULL,
                    envelope_digest TEXT NOT NULL,
                    state TEXT NOT NULL,
                    reserved_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    finalized_at TEXT
                );
                CREATE INDEX IF NOT EXISTS fleet_effect_active_repository
                    ON fleet_effect_reservation(state,repository,expires_at);
                CREATE INDEX IF NOT EXISTS fleet_effect_active_branch
                    ON fleet_effect_reservation(state,repository,branch,expires_at);
                CREATE TRIGGER IF NOT EXISTS fleet_effect_reservation_no_delete
                    BEFORE DELETE ON fleet_effect_reservation
                    BEGIN SELECT RAISE(ABORT,'fleet effect reservation is durable'); END;
                """
            )

    def _bind_envelope(self) -> None:
        expected = (
            self._envelope.envelope_id,
            self._envelope.fleet_id,
            self._envelope.generation,
            self._envelope.digest(),
            self._envelope.policy_digest,
        )
        with self._lock, closing(self._connect()) as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT envelope_id,fleet_id,generation,envelope_digest,policy_digest FROM fleet_effect_budget_meta WHERE singleton=1").fetchone()
            if row is None:
                conn.execute("INSERT INTO fleet_effect_budget_meta VALUES(1,?,?,?,?,?)", expected)
                conn.execute("COMMIT")
                return
            actual = tuple(row)
            if actual != expected:
                conn.execute("ROLLBACK")
                raise FleetEffectBudgetError("fleet effect envelope substitution/generation drift denied")
            conn.execute("COMMIT")

    @staticmethod
    def _reservation(row: sqlite3.Row) -> FleetEffectReservation:
        try:
            paths = tuple(json.loads(row["changed_paths_json"]))
        except (TypeError, ValueError) as exc:
            raise FleetEffectBudgetError("stored reservation path evidence corrupt") from exc
        return FleetEffectReservation(
            reservation_id=row["reservation_id"], request_digest=row["request_digest"], effect_id=row["effect_id"],
            mission_id=row["mission_id"], executor_id=row["executor_id"], runtime_id=row["runtime_id"],
            repository=row["repository"], branch=row["branch"], changed_paths=paths,
            authority_effect_key=row["authority_effect_key"], authority_epoch=row["authority_epoch"],
            envelope_id=row["envelope_id"], envelope_generation=row["envelope_generation"],
            envelope_digest=row["envelope_digest"], state=row["state"], reserved_at=row["reserved_at"],
            expires_at=row["expires_at"], finalized_at=row["finalized_at"],
        ).validate()

    @staticmethod
    def _active_where(now_iso: str) -> tuple[str, tuple[str, str]]:
        return "state='RESERVED' AND expires_at>?", (now_iso,)

    def _expire_locked(self, conn: sqlite3.Connection, now_iso: str) -> None:
        conn.execute(
            "UPDATE fleet_effect_reservation SET state='EXPIRED', finalized_at=? "
            "WHERE state='RESERVED' AND expires_at<=?",
            (now_iso, now_iso),
        )

    def reserve_exact(self, request: FleetEffectReservationRequest) -> FleetEffectReservation:
        if type(request) is not FleetEffectReservationRequest:
            raise FleetEffectBudgetError("exact FleetEffectReservationRequest required")
        request.validate()
        now = self._now()
        now_iso = now.isoformat()
        if request.envelope_generation != self._envelope.generation:
            raise FleetEffectBudgetError("stale envelope generation denied")
        if now < datetime.fromisoformat(self._envelope.valid_from.replace("Z", "+00:00")).astimezone(timezone.utc):
            raise FleetEffectBudgetError("fleet effect envelope is not yet current")
        if now >= datetime.fromisoformat(self._envelope.expires_at.replace("Z", "+00:00")).astimezone(timezone.utc):
            raise FleetEffectBudgetError("fleet effect envelope expired")
        requested = datetime.fromisoformat(request.requested_at.replace("Z", "+00:00")).astimezone(timezone.utc)
        expires = datetime.fromisoformat(request.expires_at.replace("Z", "+00:00")).astimezone(timezone.utc)
        if requested != now:
            raise FleetEffectBudgetError("reservation request must bind exact trusted current time")
        if expires > datetime.fromisoformat(self._envelope.expires_at.replace("Z", "+00:00")).astimezone(timezone.utc):
            raise FleetEffectBudgetError("reservation cannot outlive envelope")

        with self._lock, closing(self._connect()) as conn:
            try:
                conn.execute("BEGIN IMMEDIATE")
                self._expire_locked(conn, now_iso)
                meta = conn.execute("SELECT envelope_id,generation,envelope_digest FROM fleet_effect_budget_meta WHERE singleton=1").fetchone()
                expected_meta = (self._envelope.envelope_id, self._envelope.generation, self._envelope.digest())
                if meta is None or tuple(meta) != expected_meta:
                    raise FleetEffectBudgetError("authoritative budget meta ambiguous or stale")

                if conn.execute(
                    "SELECT 1 FROM fleet_effect_reservation WHERE reservation_id=? OR request_digest=? OR effect_id=? OR authority_effect_key=?",
                    (request.reservation_id, request.digest(), request.effect_id, request.authority_effect_key),
                ).fetchone() is not None:
                    raise FleetEffectBudgetError("reservation/effect/authority replay denied")

                active_writers = conn.execute(
                    "SELECT COUNT(*) FROM fleet_effect_reservation WHERE state='RESERVED' AND expires_at>?", (now_iso,)
                ).fetchone()[0]
                repo_count = conn.execute(
                    "SELECT COUNT(*) FROM fleet_effect_reservation WHERE state='RESERVED' AND expires_at>? AND repository=?",
                    (now_iso, request.repository),
                ).fetchone()[0]
                branch_count = conn.execute(
                    "SELECT COUNT(*) FROM fleet_effect_reservation WHERE state='RESERVED' AND expires_at>? AND repository=? AND branch=?",
                    (now_iso, request.repository, request.branch),
                ).fetchone()[0]
                if active_writers >= self._envelope.max_concurrent_writers:
                    raise FleetEffectBudgetError("fleet concurrent writer budget exhausted")
                if repo_count >= self._envelope.max_active_repository_effects:
                    raise FleetEffectBudgetError("repository effect budget exhausted")
                if branch_count >= self._envelope.max_active_branch_effects:
                    raise FleetEffectBudgetError("branch effect budget exhausted")

                for path in request.changed_paths:
                    path_count = 0
                    for row in conn.execute(
                        "SELECT changed_paths_json FROM fleet_effect_reservation WHERE state='RESERVED' AND expires_at>? AND repository=?",
                        (now_iso, request.repository),
                    ):
                        try:
                            existing = tuple(json.loads(row[0]))
                        except (TypeError, ValueError) as exc:
                            raise FleetEffectBudgetError("active path reservation evidence corrupt") from exc
                        if path in existing:
                            path_count += 1
                    if path_count >= self._envelope.max_active_path_effects:
                        raise FleetEffectBudgetError(f"path effect budget exhausted: {path}")

                conn.execute(
                    """INSERT INTO fleet_effect_reservation(
                    reservation_id,request_digest,effect_id,mission_id,executor_id,runtime_id,repository,branch,
                    changed_paths_json,authority_effect_key,authority_epoch,envelope_id,envelope_generation,envelope_digest,
                    state,reserved_at,expires_at,finalized_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,'RESERVED',?,?,NULL)""",
                    (
                        request.reservation_id, request.digest(), request.effect_id, request.mission_id, request.executor_id,
                        request.runtime_id, request.repository, request.branch,
                        json.dumps(list(request.changed_paths), separators=(",", ":")), request.authority_effect_key,
                        request.authority_epoch, self._envelope.envelope_id, self._envelope.generation,
                        self._envelope.digest(), now_iso, request.expires_at,
                    ),
                )
                row = conn.execute("SELECT * FROM fleet_effect_reservation WHERE reservation_id=?", (request.reservation_id,)).fetchone()
                conn.execute("COMMIT")
            except Exception:
                if conn.in_transaction:
                    conn.execute("ROLLBACK")
                raise
        if row is None:
            raise FleetEffectBudgetError("reservation write disappeared")
        return self._reservation(row)

    def get(self, reservation_id: str) -> FleetEffectReservation:
        if not isinstance(reservation_id, str) or not reservation_id.strip():
            raise FleetEffectBudgetError("reservation_id required")
        now_iso = self._now().isoformat()
        with self._lock, closing(self._connect()) as conn:
            conn.execute("BEGIN IMMEDIATE")
            self._expire_locked(conn, now_iso)
            row = conn.execute("SELECT * FROM fleet_effect_reservation WHERE reservation_id=?", (reservation_id,)).fetchone()
            conn.execute("COMMIT")
        if row is None:
            raise FleetEffectBudgetError("reservation unavailable")
        return self._reservation(row)

    def validate_for_effect(
        self,
        reservation: FleetEffectReservation,
        *,
        effect_id: str,
        mission_id: str,
        runtime_id: str,
        repository: str,
        branch: str,
        changed_paths: tuple[str, ...],
        authority_effect_key: str,
        authority_epoch: int,
    ) -> FleetEffectReservation:
        if type(reservation) is not FleetEffectReservation:
            raise FleetEffectBudgetError("exact reservation required")
        reservation.validate()
        current = self.get(reservation.reservation_id)
        if current.digest() != reservation.digest():
            raise FleetEffectBudgetError("reservation changed since admission")
        expected = (
            effect_id, mission_id, runtime_id, repository, branch, changed_paths,
            authority_effect_key, authority_epoch, self._envelope.envelope_id,
            self._envelope.generation, self._envelope.digest(), "RESERVED",
        )
        actual = (
            current.effect_id, current.mission_id, current.runtime_id, current.repository, current.branch,
            current.changed_paths, current.authority_effect_key, current.authority_epoch,
            current.envelope_id, current.envelope_generation, current.envelope_digest, current.state,
        )
        if actual != expected:
            raise FleetEffectBudgetError("reservation does not bind exact effect/runtime/authority scope")
        return current

    def _terminal(self, reservation_id: str, state: str) -> FleetEffectReservation:
        if state not in {"RELEASED", "FINALIZED"}:
            raise FleetEffectBudgetError("terminal state invalid")
        now_iso = self._now().isoformat()
        with self._lock, closing(self._connect()) as conn:
            conn.execute("BEGIN IMMEDIATE")
            self._expire_locked(conn, now_iso)
            cur = conn.execute(
                "UPDATE fleet_effect_reservation SET state=?, finalized_at=? WHERE reservation_id=? AND state='RESERVED' AND expires_at>?",
                (state, now_iso, reservation_id, now_iso),
            )
            if cur.rowcount != 1:
                conn.execute("ROLLBACK")
                raise FleetEffectBudgetError("reservation cannot transition from current state")
            row = conn.execute("SELECT * FROM fleet_effect_reservation WHERE reservation_id=?", (reservation_id,)).fetchone()
            conn.execute("COMMIT")
        return self._reservation(row)

    def release(self, reservation_id: str) -> FleetEffectReservation:
        return self._terminal(reservation_id, "RELEASED")

    def finalize(self, reservation_id: str) -> FleetEffectReservation:
        return self._terminal(reservation_id, "FINALIZED")

    def snapshot(self) -> FleetEffectBudgetSnapshot:
        now_iso = self._now().isoformat()
        with self._lock, closing(self._connect()) as conn:
            conn.execute("BEGIN IMMEDIATE")
            self._expire_locked(conn, now_iso)
            rows = conn.execute(
                "SELECT reservation_id,repository,branch,changed_paths_json FROM fleet_effect_reservation "
                "WHERE state='RESERVED' AND expires_at>? ORDER BY reservation_id", (now_iso,)
            ).fetchall()
            conn.execute("COMMIT")
        repos: dict[str, int] = {}
        branches: dict[tuple[str, str], int] = {}
        paths: dict[tuple[str, str], int] = {}
        ids: list[str] = []
        for row in rows:
            ids.append(row["reservation_id"])
            repos[row["repository"]] = repos.get(row["repository"], 0) + 1
            key = (row["repository"], row["branch"])
            branches[key] = branches.get(key, 0) + 1
            try:
                changed = tuple(json.loads(row["changed_paths_json"]))
            except (TypeError, ValueError) as exc:
                raise FleetEffectBudgetError("snapshot path evidence corrupt") from exc
            for path in changed:
                pkey = (row["repository"], path)
                paths[pkey] = paths.get(pkey, 0) + 1
        return FleetEffectBudgetSnapshot(
            envelope_id=self._envelope.envelope_id,
            envelope_generation=self._envelope.generation,
            envelope_digest=self._envelope.digest(),
            active_writers=len(rows),
            active_repository_effects=tuple((k, repos[k]) for k in sorted(repos)),
            active_branch_effects=tuple((k[0], k[1], branches[k]) for k in sorted(branches)),
            active_path_effects=tuple((k[0], k[1], paths[k]) for k in sorted(paths)),
            active_reservation_ids=tuple(ids),
            observed_at=now_iso,
        ).validate()
