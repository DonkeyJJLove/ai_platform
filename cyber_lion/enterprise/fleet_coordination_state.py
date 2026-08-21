"""Restart-durable deterministic fleet coordination state for F005-B.

This module owns scheduler bookkeeping, dispatch fencing, dependency readiness, and
branch/path leases. It deliberately has no repository mutation, execution, verifier,
merge, release, deployment, or authority-grant capability.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path, PurePosixPath
import re
import sqlite3
from typing import Callable, Iterator, Mapping, Sequence

from cyber_lion.contracts.fleet_coordination import (
    TERMINAL_STATES,
    FleetCoordinationSnapshot,
    FleetCoordinationSpec,
    FleetDispatch,
    FleetLease,
    FleetMissionState,
    FleetPlanRequest,
    canonical_json,
)

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_ZERO_DIGEST = "0" * 64


class FleetCoordinationStateError(RuntimeError):
    """Fail-closed durable coordination error."""


def _require_text(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip() or "\x00" in value:
        raise FleetCoordinationStateError(f"{name} is invalid")
    return value


def _require_digest(value: object, name: str) -> str:
    value = _require_text(value, name)
    if not _SHA256.fullmatch(value):
        raise FleetCoordinationStateError(f"{name} must be sha256 hex")
    return value


def _utc(value: datetime) -> str:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise FleetCoordinationStateError("trusted clock must return timezone-aware datetime")
    return value.astimezone(timezone.utc).isoformat()


def _parse_utc(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise FleetCoordinationStateError("stored timestamp is invalid") from exc
    if parsed.tzinfo is None:
        raise FleetCoordinationStateError("stored timestamp is not timezone-aware")
    return parsed.astimezone(timezone.utc)


def _path_overlap(left: str, right: str) -> bool:
    a = PurePosixPath(left).parts
    b = PurePosixPath(right).parts
    shared = min(len(a), len(b))
    return a[:shared] == b[:shared]


def _event_digest(
    previous: str,
    event_type: str,
    mission_id: str | None,
    payload: Mapping[str, object],
    observed_at: str,
) -> str:
    return sha256(canonical_json({
        "previous_digest": previous,
        "event_type": event_type,
        "mission_id": mission_id,
        "payload": dict(payload),
        "observed_at": observed_at,
    })).hexdigest()


def _dispatches_json(dispatches: Sequence[FleetDispatch]) -> str:
    return json.dumps(
        [dispatch.canonical_dict() for dispatch in dispatches],
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def _dispatches_from_json(raw: str) -> tuple[FleetDispatch, ...]:
    try:
        values = json.loads(raw)
    except (TypeError, json.JSONDecodeError) as exc:
        raise FleetCoordinationStateError("stored dispatch result is invalid JSON") from exc
    if not isinstance(values, list):
        raise FleetCoordinationStateError("stored dispatch result must be a list")
    result: list[FleetDispatch] = []
    for value in values:
        if not isinstance(value, dict):
            raise FleetCoordinationStateError("stored dispatch entry is invalid")
        try:
            dispatch = FleetDispatch(
                dispatch_id=value["dispatch_id"],
                fencing_token=value["fencing_token"],
                request_id=value["request_id"],
                coordinator_id=value["coordinator_id"],
                mission_id=value["mission_id"],
                drone_id=value["drone_id"],
                generation=value["generation"],
                repository=value["repository"],
                baseline_sha=value["baseline_sha"],
                baseline_tree_sha=value["baseline_tree_sha"],
                branch=value["branch"],
                write_scope=tuple(value["write_scope"]),
                issued_at=value["issued_at"],
            ).validate()
        except (KeyError, TypeError, ValueError) as exc:
            raise FleetCoordinationStateError("stored dispatch entry failed validation") from exc
        result.append(dispatch)
    return tuple(result)


class FleetCoordinationStore:
    """SQLite-backed coordination state with replay-safe dispatch and durable leases."""

    def __init__(
        self,
        db_path: str | Path,
        *,
        coordinator_id: str,
        clock: Callable[[], datetime],
    ) -> None:
        self._coordinator_id = _require_text(coordinator_id, "coordinator_id")
        self._clock = clock
        self._db_path = str(Path(db_path))
        self._conn = sqlite3.connect(self._db_path, isolation_level=None)
        try:
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA foreign_keys=ON")
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA synchronous=FULL")
            self._conn.execute("PRAGMA busy_timeout=5000")
            self._init_schema()
            self._bind_coordinator()
            self.verify_event_chain(self._conn)
            self._verify_consistency(self._conn)
        except Exception:
            self._conn.close()
            raise

    @property
    def coordinator_id(self) -> str:
        return self._coordinator_id

    @property
    def db_path(self) -> str:
        return self._db_path

    def close(self) -> None:
        self._conn.close()

    def _init_schema(self) -> None:
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS fleet_coordination_meta(
                singleton INTEGER PRIMARY KEY CHECK(singleton=1),
                coordinator_id TEXT NOT NULL,
                revision INTEGER NOT NULL,
                event_head TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS fleet_coordination_mission(
                mission_id TEXT PRIMARY KEY,
                drone_id TEXT NOT NULL UNIQUE,
                repository TEXT NOT NULL,
                baseline_sha TEXT NOT NULL,
                baseline_tree_sha TEXT NOT NULL,
                branch TEXT NOT NULL,
                write_scope_json TEXT NOT NULL,
                dependencies_json TEXT NOT NULL,
                evidence_refs_json TEXT NOT NULL,
                spec_digest TEXT NOT NULL UNIQUE,
                state TEXT NOT NULL,
                generation INTEGER NOT NULL,
                dispatch_id TEXT,
                fencing_token TEXT,
                terminal_evidence_ref TEXT,
                last_requeue_evidence_ref TEXT,
                registered_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS fleet_coordination_dependency(
                mission_id TEXT NOT NULL REFERENCES fleet_coordination_mission(mission_id) ON DELETE RESTRICT,
                dependency_mission_id TEXT NOT NULL,
                PRIMARY KEY(mission_id, dependency_mission_id)
            );

            CREATE TABLE IF NOT EXISTS fleet_coordination_active_lease(
                repository TEXT NOT NULL,
                lease_kind TEXT NOT NULL,
                resource TEXT NOT NULL,
                mission_id TEXT NOT NULL REFERENCES fleet_coordination_mission(mission_id) ON DELETE RESTRICT,
                drone_id TEXT NOT NULL,
                dispatch_id TEXT NOT NULL,
                generation INTEGER NOT NULL,
                acquired_at TEXT NOT NULL,
                PRIMARY KEY(repository, lease_kind, resource)
            );

            CREATE TABLE IF NOT EXISTS fleet_coordination_plan(
                request_id TEXT PRIMARY KEY,
                request_digest TEXT NOT NULL,
                request_json TEXT NOT NULL,
                result_json TEXT NOT NULL,
                result_digest TEXT NOT NULL,
                observed_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS fleet_coordination_event(
                seq INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id TEXT NOT NULL UNIQUE,
                event_type TEXT NOT NULL,
                mission_id TEXT,
                payload_json TEXT NOT NULL,
                previous_digest TEXT NOT NULL,
                event_digest TEXT NOT NULL UNIQUE,
                observed_at TEXT NOT NULL
            );

            CREATE TRIGGER IF NOT EXISTS fleet_coordination_plan_no_update
            BEFORE UPDATE ON fleet_coordination_plan
            BEGIN SELECT RAISE(ABORT,'fleet_coordination_plan is append-only'); END;
            CREATE TRIGGER IF NOT EXISTS fleet_coordination_plan_no_delete
            BEFORE DELETE ON fleet_coordination_plan
            BEGIN SELECT RAISE(ABORT,'fleet_coordination_plan is append-only'); END;
            CREATE TRIGGER IF NOT EXISTS fleet_coordination_event_no_update
            BEFORE UPDATE ON fleet_coordination_event
            BEGIN SELECT RAISE(ABORT,'fleet_coordination_event is append-only'); END;
            CREATE TRIGGER IF NOT EXISTS fleet_coordination_event_no_delete
            BEFORE DELETE ON fleet_coordination_event
            BEGIN SELECT RAISE(ABORT,'fleet_coordination_event is append-only'); END;
            """
        )

    def _bind_coordinator(self) -> None:
        row = self._conn.execute(
            "SELECT coordinator_id FROM fleet_coordination_meta WHERE singleton=1"
        ).fetchone()
        if row is None:
            self._conn.execute(
                "INSERT INTO fleet_coordination_meta(singleton,coordinator_id,revision,event_head) VALUES(1,?,?,?)",
                (self._coordinator_id, 0, _ZERO_DIGEST),
            )
        elif row["coordinator_id"] != self._coordinator_id:
            raise FleetCoordinationStateError("coordinator instance substitution denied")

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
        conn = sqlite3.connect(self._db_path, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA query_only=ON")
        return conn

    def _trusted_now(self, c: sqlite3.Connection) -> str:
        observed_at = _utc(self._clock())
        row = c.execute(
            "SELECT observed_at FROM fleet_coordination_event ORDER BY seq DESC LIMIT 1"
        ).fetchone()
        if row is not None and _parse_utc(observed_at) < _parse_utc(row["observed_at"]):
            raise FleetCoordinationStateError("trusted clock rollback denied")
        return observed_at

    def _bump(self, c: sqlite3.Connection) -> None:
        c.execute("UPDATE fleet_coordination_meta SET revision=revision+1 WHERE singleton=1")

    def _append_event(
        self,
        c: sqlite3.Connection,
        *,
        event_type: str,
        mission_id: str | None,
        payload: Mapping[str, object],
        observed_at: str,
    ) -> str:
        meta = c.execute(
            "SELECT event_head FROM fleet_coordination_meta WHERE singleton=1"
        ).fetchone()
        if meta is None:
            raise FleetCoordinationStateError("coordination metadata missing")
        previous = meta["event_head"]
        digest = _event_digest(previous, event_type, mission_id, payload, observed_at)
        c.execute(
            """INSERT INTO fleet_coordination_event(
               event_id,event_type,mission_id,payload_json,previous_digest,event_digest,observed_at
               ) VALUES(?,?,?,?,?,?,?)""",
            (
                digest,
                event_type,
                mission_id,
                canonical_json(payload).decode("utf-8"),
                previous,
                digest,
                observed_at,
            ),
        )
        c.execute(
            "UPDATE fleet_coordination_meta SET event_head=? WHERE singleton=1",
            (digest,),
        )
        return digest

    def verify_event_chain(self, conn: sqlite3.Connection | None = None) -> str:
        c = conn or self.open_query_reader()
        close = conn is None
        try:
            previous = _ZERO_DIGEST
            last = previous
            previous_time: datetime | None = None
            for row in c.execute("SELECT * FROM fleet_coordination_event ORDER BY seq"):
                try:
                    payload = json.loads(row["payload_json"])
                except json.JSONDecodeError as exc:
                    raise FleetCoordinationStateError("event payload corruption") from exc
                if not isinstance(payload, dict):
                    raise FleetCoordinationStateError("event payload corruption")
                expected = _event_digest(
                    previous,
                    row["event_type"],
                    row["mission_id"],
                    payload,
                    row["observed_at"],
                )
                current_time = _parse_utc(row["observed_at"])
                if previous_time is not None and current_time < previous_time:
                    raise FleetCoordinationStateError("event time ordering corruption")
                if (
                    row["previous_digest"] != previous
                    or row["event_digest"] != expected
                    or row["event_id"] != expected
                ):
                    raise FleetCoordinationStateError("event chain corruption")
                previous = expected
                last = expected
                previous_time = current_time
            meta = c.execute(
                "SELECT event_head FROM fleet_coordination_meta WHERE singleton=1"
            ).fetchone()
            if meta is None or meta["event_head"] != last:
                raise FleetCoordinationStateError("event chain head mismatch")
            return last
        finally:
            if close:
                c.close()

    def register_mission(self, spec: FleetCoordinationSpec) -> None:
        spec.validate()
        digest = spec.digest()
        with self._write() as c:
            existing = c.execute(
                "SELECT spec_digest FROM fleet_coordination_mission WHERE mission_id=?",
                (spec.mission_id,),
            ).fetchone()
            if existing is not None:
                if existing["spec_digest"] == digest:
                    return
                raise FleetCoordinationStateError("mission identity substitution denied")
            other = c.execute(
                "SELECT mission_id FROM fleet_coordination_mission WHERE drone_id=?",
                (spec.drone_id,),
            ).fetchone()
            if other is not None:
                raise FleetCoordinationStateError("drone is already bound to another mission")
            graph = self._dependency_graph(c)
            graph[spec.mission_id] = frozenset(spec.dependencies)
            if self._has_cycle(graph):
                raise FleetCoordinationStateError("dependency cycle detected")
            observed_at = self._trusted_now(c)
            c.execute(
                """INSERT INTO fleet_coordination_mission(
                   mission_id,drone_id,repository,baseline_sha,baseline_tree_sha,branch,
                   write_scope_json,dependencies_json,evidence_refs_json,spec_digest,state,generation,
                   dispatch_id,fencing_token,terminal_evidence_ref,last_requeue_evidence_ref,
                   registered_at,updated_at
                   ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    spec.mission_id,
                    spec.drone_id,
                    spec.repository,
                    spec.baseline_sha,
                    spec.baseline_tree_sha,
                    spec.branch,
                    json.dumps(spec.write_scope, separators=(",", ":")),
                    json.dumps(spec.dependencies, separators=(",", ":")),
                    json.dumps(spec.evidence_refs, separators=(",", ":")),
                    digest,
                    "STARTING",
                    0,
                    None,
                    None,
                    None,
                    None,
                    observed_at,
                    observed_at,
                ),
            )
            for dependency in spec.dependencies:
                c.execute(
                    "INSERT INTO fleet_coordination_dependency(mission_id,dependency_mission_id) VALUES(?,?)",
                    (spec.mission_id, dependency),
                )
            self._append_event(
                c,
                event_type="MISSION_REGISTERED",
                mission_id=spec.mission_id,
                payload={"drone_id": spec.drone_id, "spec_digest": digest},
                observed_at=observed_at,
            )
            self._bump(c)

    def plan(self, request: FleetPlanRequest) -> tuple[FleetDispatch, ...]:
        request.validate()
        if request.coordinator_id != self._coordinator_id:
            raise FleetCoordinationStateError("plan request coordinator binding mismatch")
        request_digest = request.digest()
        with self._write() as c:
            cached = c.execute(
                "SELECT request_digest,result_json,result_digest FROM fleet_coordination_plan WHERE request_id=?",
                (request.request_id,),
            ).fetchone()
            if cached is not None:
                if cached["request_digest"] != request_digest:
                    raise FleetCoordinationStateError("request_id replay with different request denied")
                expected_result_digest = sha256(cached["result_json"].encode("utf-8")).hexdigest()
                if cached["result_digest"] != expected_result_digest:
                    raise FleetCoordinationStateError("stored plan result digest mismatch")
                return _dispatches_from_json(cached["result_json"])

            observed_at = self._trusted_now(c)
            current_heads = request.head_map()
            selected: list[FleetDispatch] = []
            candidates = c.execute(
                """SELECT * FROM fleet_coordination_mission
                   WHERE state IN ('STARTING','WAITING') ORDER BY mission_id"""
            ).fetchall()
            for row in candidates:
                if len(selected) >= request.max_parallel:
                    break
                if not self._dependencies_done(c, row["mission_id"]):
                    continue
                actual_head = current_heads.get(row["repository"])
                if actual_head is None:
                    raise FleetCoordinationStateError(
                        f"current head missing for repository: {row['repository']}"
                    )
                if actual_head != row["baseline_sha"]:
                    raise FleetCoordinationStateError(
                        f"stale baseline: {row['repository']}:{row['mission_id']}"
                    )
                write_scope = tuple(json.loads(row["write_scope_json"]))
                if not self._leases_available(c, row["repository"], row["branch"], write_scope):
                    continue
                generation = row["generation"] + 1
                dispatch_seed = {
                    "coordinator_id": self._coordinator_id,
                    "request_digest": request_digest,
                    "mission_id": row["mission_id"],
                    "drone_id": row["drone_id"],
                    "spec_digest": row["spec_digest"],
                    "generation": generation,
                    "issued_at": observed_at,
                }
                dispatch_id = sha256(canonical_json({"kind": "dispatch", **dispatch_seed})).hexdigest()
                fencing_token = sha256(canonical_json({"kind": "fence", **dispatch_seed})).hexdigest()
                dispatch = FleetDispatch(
                    dispatch_id=dispatch_id,
                    fencing_token=fencing_token,
                    request_id=request.request_id,
                    coordinator_id=self._coordinator_id,
                    mission_id=row["mission_id"],
                    drone_id=row["drone_id"],
                    generation=generation,
                    repository=row["repository"],
                    baseline_sha=row["baseline_sha"],
                    baseline_tree_sha=row["baseline_tree_sha"],
                    branch=row["branch"],
                    write_scope=write_scope,
                    issued_at=observed_at,
                ).validate()
                self._claim_leases(c, dispatch)
                c.execute(
                    """UPDATE fleet_coordination_mission
                       SET state='RUNNING',generation=?,dispatch_id=?,fencing_token=?,
                           terminal_evidence_ref=NULL,last_requeue_evidence_ref=NULL,updated_at=?
                       WHERE mission_id=?""",
                    (
                        generation,
                        dispatch_id,
                        fencing_token,
                        observed_at,
                        row["mission_id"],
                    ),
                )
                self._append_event(
                    c,
                    event_type="MISSION_DISPATCHED",
                    mission_id=row["mission_id"],
                    payload={
                        "request_id": request.request_id,
                        "request_digest": request_digest,
                        "dispatch_id": dispatch_id,
                        "fencing_token": fencing_token,
                        "generation": generation,
                        "spec_digest": row["spec_digest"],
                    },
                    observed_at=observed_at,
                )
                selected.append(dispatch)

            result_json = _dispatches_json(selected)
            result_digest = sha256(result_json.encode("utf-8")).hexdigest()
            c.execute(
                """INSERT INTO fleet_coordination_plan(
                   request_id,request_digest,request_json,result_json,result_digest,observed_at
                   ) VALUES(?,?,?,?,?,?)""",
                (
                    request.request_id,
                    request_digest,
                    canonical_json(request.canonical_dict()).decode("utf-8"),
                    result_json,
                    result_digest,
                    observed_at,
                ),
            )
            self._append_event(
                c,
                event_type="PLAN_COMMITTED",
                mission_id=None,
                payload={
                    "request_id": request.request_id,
                    "request_digest": request_digest,
                    "result_digest": result_digest,
                    "dispatch_ids": [dispatch.dispatch_id for dispatch in selected],
                },
                observed_at=observed_at,
            )
            self._bump(c)
            return tuple(selected)

    def requeue(
        self,
        mission_id: str,
        *,
        dispatch_id: str,
        fencing_token: str,
        evidence_ref: str,
    ) -> None:
        _require_text(mission_id, "mission_id")
        _require_digest(dispatch_id, "dispatch_id")
        _require_digest(fencing_token, "fencing_token")
        _require_text(evidence_ref, "evidence_ref")
        with self._write() as c:
            row = self._require_mission(c, mission_id)
            if row["state"] == "WAITING":
                if (
                    row["dispatch_id"] == dispatch_id
                    and row["fencing_token"] == fencing_token
                    and row["last_requeue_evidence_ref"] == evidence_ref
                ):
                    return
                raise FleetCoordinationStateError("requeue replay binding mismatch")
            if row["state"] != "RUNNING":
                raise FleetCoordinationStateError("only RUNNING mission may be requeued")
            self._require_active_dispatch(row, dispatch_id, fencing_token)
            observed_at = self._trusted_now(c)
            released = self._release_leases(c, mission_id, dispatch_id)
            c.execute(
                """UPDATE fleet_coordination_mission
                   SET state='WAITING',terminal_evidence_ref=NULL,last_requeue_evidence_ref=?,updated_at=?
                   WHERE mission_id=?""",
                (evidence_ref, observed_at, mission_id),
            )
            self._append_event(
                c,
                event_type="MISSION_REQUEUED",
                mission_id=mission_id,
                payload={
                    "dispatch_id": dispatch_id,
                    "generation": row["generation"],
                    "evidence_ref": evidence_ref,
                    "released_lease_count": released,
                },
                observed_at=observed_at,
            )
            self._bump(c)

    def record_terminal(
        self,
        mission_id: str,
        *,
        dispatch_id: str,
        fencing_token: str,
        terminal_state: str,
        evidence_ref: str,
    ) -> None:
        _require_text(mission_id, "mission_id")
        _require_digest(dispatch_id, "dispatch_id")
        _require_digest(fencing_token, "fencing_token")
        _require_text(evidence_ref, "evidence_ref")
        if terminal_state not in TERMINAL_STATES:
            raise FleetCoordinationStateError("terminal_state is invalid")
        with self._write() as c:
            row = self._require_mission(c, mission_id)
            if row["state"] in TERMINAL_STATES:
                if (
                    row["state"] == terminal_state
                    and row["dispatch_id"] == dispatch_id
                    and row["fencing_token"] == fencing_token
                    and row["terminal_evidence_ref"] == evidence_ref
                ):
                    return
                raise FleetCoordinationStateError("terminal replay binding mismatch")
            if row["state"] != "RUNNING":
                raise FleetCoordinationStateError("only RUNNING mission may become terminal")
            self._require_active_dispatch(row, dispatch_id, fencing_token)
            observed_at = self._trusted_now(c)
            released = self._release_leases(c, mission_id, dispatch_id)
            c.execute(
                """UPDATE fleet_coordination_mission
                   SET state=?,terminal_evidence_ref=?,last_requeue_evidence_ref=NULL,updated_at=?
                   WHERE mission_id=?""",
                (terminal_state, evidence_ref, observed_at, mission_id),
            )
            self._append_event(
                c,
                event_type="MISSION_TERMINAL",
                mission_id=mission_id,
                payload={
                    "dispatch_id": dispatch_id,
                    "generation": row["generation"],
                    "terminal_state": terminal_state,
                    "evidence_ref": evidence_ref,
                    "released_lease_count": released,
                },
                observed_at=observed_at,
            )
            self._bump(c)

    def mission_state(self, mission_id: str) -> FleetMissionState:
        _require_text(mission_id, "mission_id")
        reader = self.open_query_reader()
        try:
            row = self._require_mission(reader, mission_id)
            return self._mission_state(row)
        finally:
            reader.close()

    def active_leases(self) -> tuple[FleetLease, ...]:
        reader = self.open_query_reader()
        try:
            return self._leases(reader)
        finally:
            reader.close()

    def snapshot(self) -> FleetCoordinationSnapshot:
        reader = self.open_query_reader()
        try:
            meta = reader.execute(
                "SELECT coordinator_id,revision,event_head FROM fleet_coordination_meta WHERE singleton=1"
            ).fetchone()
            if meta is None:
                raise FleetCoordinationStateError("coordination metadata missing")
            missions = tuple(
                self._mission_state(row)
                for row in reader.execute(
                    "SELECT * FROM fleet_coordination_mission ORDER BY mission_id"
                )
            )
            return FleetCoordinationSnapshot(
                coordinator_id=meta["coordinator_id"],
                revision=meta["revision"],
                event_head=meta["event_head"],
                missions=missions,
                active_leases=self._leases(reader),
            ).validate()
        finally:
            reader.close()

    def _mission_state(self, row: sqlite3.Row) -> FleetMissionState:
        return FleetMissionState(
            mission_id=row["mission_id"],
            drone_id=row["drone_id"],
            state=row["state"],
            generation=row["generation"],
            spec_digest=row["spec_digest"],
            dispatch_id=row["dispatch_id"],
            fencing_token=row["fencing_token"],
            terminal_evidence_ref=row["terminal_evidence_ref"],
            updated_at=row["updated_at"],
        ).validate()

    def _leases(self, c: sqlite3.Connection) -> tuple[FleetLease, ...]:
        return tuple(
            FleetLease(
                mission_id=row["mission_id"],
                drone_id=row["drone_id"],
                dispatch_id=row["dispatch_id"],
                generation=row["generation"],
                repository=row["repository"],
                lease_kind=row["lease_kind"],
                resource=row["resource"],
                acquired_at=row["acquired_at"],
            ).validate()
            for row in c.execute(
                """SELECT * FROM fleet_coordination_active_lease
                   ORDER BY repository,lease_kind,resource,mission_id"""
            )
        )

    def _dependency_graph(self, c: sqlite3.Connection) -> dict[str, frozenset[str]]:
        graph = {
            row["mission_id"]: frozenset()
            for row in c.execute("SELECT mission_id FROM fleet_coordination_mission")
        }
        mutable = {mission_id: set() for mission_id in graph}
        for row in c.execute(
            "SELECT mission_id,dependency_mission_id FROM fleet_coordination_dependency"
        ):
            mutable.setdefault(row["mission_id"], set()).add(row["dependency_mission_id"])
        return {mission_id: frozenset(deps) for mission_id, deps in mutable.items()}

    @staticmethod
    def _has_cycle(graph: Mapping[str, frozenset[str]]) -> bool:
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(node: str) -> bool:
            if node in visited:
                return False
            if node in visiting:
                return True
            visiting.add(node)
            for dependency in graph.get(node, frozenset()):
                if dependency in graph and visit(dependency):
                    return True
            visiting.remove(node)
            visited.add(node)
            return False

        return any(visit(node) for node in graph)

    def _dependencies_done(self, c: sqlite3.Connection, mission_id: str) -> bool:
        deps = c.execute(
            """SELECT d.dependency_mission_id,m.state
               FROM fleet_coordination_dependency AS d
               LEFT JOIN fleet_coordination_mission AS m
                 ON m.mission_id=d.dependency_mission_id
               WHERE d.mission_id=?""",
            (mission_id,),
        ).fetchall()
        return all(row["state"] == "DONE" for row in deps)

    def _leases_available(
        self,
        c: sqlite3.Connection,
        repository: str,
        branch: str,
        write_scope: tuple[str, ...],
    ) -> bool:
        branch_owner = c.execute(
            """SELECT mission_id FROM fleet_coordination_active_lease
               WHERE repository=? AND lease_kind='BRANCH' AND resource=?""",
            (repository, branch),
        ).fetchone()
        if branch_owner is not None:
            return False
        path_rows = c.execute(
            """SELECT resource FROM fleet_coordination_active_lease
               WHERE repository=? AND lease_kind='PATH'""",
            (repository,),
        ).fetchall()
        return not any(
            _path_overlap(candidate, row["resource"])
            for candidate in write_scope
            for row in path_rows
        )

    def _claim_leases(self, c: sqlite3.Connection, dispatch: FleetDispatch) -> None:
        dispatch.validate()
        values = [
            (
                dispatch.repository,
                "BRANCH",
                dispatch.branch,
                dispatch.mission_id,
                dispatch.drone_id,
                dispatch.dispatch_id,
                dispatch.generation,
                dispatch.issued_at,
            )
        ]
        values.extend(
            (
                dispatch.repository,
                "PATH",
                path,
                dispatch.mission_id,
                dispatch.drone_id,
                dispatch.dispatch_id,
                dispatch.generation,
                dispatch.issued_at,
            )
            for path in dispatch.write_scope
        )
        try:
            c.executemany(
                """INSERT INTO fleet_coordination_active_lease(
                   repository,lease_kind,resource,mission_id,drone_id,dispatch_id,generation,acquired_at
                   ) VALUES(?,?,?,?,?,?,?,?)""",
                values,
            )
        except sqlite3.IntegrityError as exc:
            raise FleetCoordinationStateError("lease conflict during atomic claim") from exc

    @staticmethod
    def _release_leases(c: sqlite3.Connection, mission_id: str, dispatch_id: str) -> int:
        cursor = c.execute(
            "DELETE FROM fleet_coordination_active_lease WHERE mission_id=? AND dispatch_id=?",
            (mission_id, dispatch_id),
        )
        return cursor.rowcount

    @staticmethod
    def _require_mission(c: sqlite3.Connection, mission_id: str) -> sqlite3.Row:
        row = c.execute(
            "SELECT * FROM fleet_coordination_mission WHERE mission_id=?",
            (mission_id,),
        ).fetchone()
        if row is None:
            raise FleetCoordinationStateError(f"unknown mission: {mission_id}")
        return row

    @staticmethod
    def _require_active_dispatch(row: sqlite3.Row, dispatch_id: str, fencing_token: str) -> None:
        if row["dispatch_id"] != dispatch_id or row["fencing_token"] != fencing_token:
            raise FleetCoordinationStateError("stale or foreign dispatch fencing token denied")

    def _verify_consistency(self, c: sqlite3.Connection) -> None:
        for row in c.execute("SELECT * FROM fleet_coordination_plan"):
            expected = sha256(row["result_json"].encode("utf-8")).hexdigest()
            if row["result_digest"] != expected:
                raise FleetCoordinationStateError("stored plan result digest mismatch")
            _dispatches_from_json(row["result_json"])

        active_by_mission: dict[str, list[sqlite3.Row]] = {}
        for lease in c.execute("SELECT * FROM fleet_coordination_active_lease"):
            active_by_mission.setdefault(lease["mission_id"], []).append(lease)

        for row in c.execute("SELECT * FROM fleet_coordination_mission"):
            state = self._mission_state(row)
            leases = active_by_mission.get(row["mission_id"], [])
            if state.state == "RUNNING":
                write_scope = tuple(json.loads(row["write_scope_json"]))
                expected_resources = {("BRANCH", row["branch"])} | {
                    ("PATH", path) for path in write_scope
                }
                actual_resources = {(lease["lease_kind"], lease["resource"]) for lease in leases}
                if actual_resources != expected_resources:
                    raise FleetCoordinationStateError("RUNNING mission lease set is incomplete or ambiguous")
                for lease in leases:
                    if (
                        lease["drone_id"] != row["drone_id"]
                        or lease["dispatch_id"] != row["dispatch_id"]
                        or lease["generation"] != row["generation"]
                        or lease["repository"] != row["repository"]
                    ):
                        raise FleetCoordinationStateError("active lease binding mismatch")
            elif leases:
                raise FleetCoordinationStateError("non-RUNNING mission owns active leases")
