"""Restart-durable canonical MissionSpec registry; organizational state is not authority."""
from __future__ import annotations

from dataclasses import asdict
from hashlib import sha256
import json
import sqlite3
from pathlib import Path

from .models import MissionSpec


class CanonicalMissionStateError(RuntimeError):
    pass


def _canon(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def mission_digest(mission: MissionSpec) -> str:
    mission.validate()
    data = asdict(mission)
    data["required_capabilities"] = list(mission.required_capabilities)
    return sha256(_canon(data)).hexdigest()


def _mission_json(mission: MissionSpec) -> str:
    data = asdict(mission)
    data["required_capabilities"] = list(mission.required_capabilities)
    return _canon(data).decode("utf-8")


class CanonicalMissionStore:
    """Append-only MissionSpec history with explicit current revision selection."""

    def __init__(self, db_path: str | Path, *, registry_id: str) -> None:
        if not isinstance(registry_id, str) or not registry_id:
            raise CanonicalMissionStateError("registry_id required")
        self.registry_id = registry_id
        self.db_path = str(Path(db_path))
        self._conn = sqlite3.connect(self.db_path, isolation_level=None)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=FULL")
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS canonical_mission_meta(
              singleton INTEGER PRIMARY KEY CHECK(singleton=1),
              registry_id TEXT NOT NULL,
              generation INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS canonical_mission_revision(
              mission_id TEXT NOT NULL,
              revision INTEGER NOT NULL,
              mission_digest TEXT NOT NULL UNIQUE,
              mission_json TEXT NOT NULL,
              source_provenance_ref TEXT NOT NULL,
              PRIMARY KEY(mission_id, revision)
            );
            CREATE TABLE IF NOT EXISTS canonical_mission_active(
              mission_id TEXT PRIMARY KEY,
              revision INTEGER NOT NULL,
              mission_digest TEXT NOT NULL,
              generation INTEGER NOT NULL,
              FOREIGN KEY(mission_id, revision) REFERENCES canonical_mission_revision(mission_id, revision)
            );
            CREATE TRIGGER IF NOT EXISTS canonical_mission_revision_no_update
              BEFORE UPDATE ON canonical_mission_revision BEGIN SELECT RAISE(ABORT,'mission revision append-only'); END;
            CREATE TRIGGER IF NOT EXISTS canonical_mission_revision_no_delete
              BEFORE DELETE ON canonical_mission_revision BEGIN SELECT RAISE(ABORT,'mission revision append-only'); END;
            """
        )
        row = self._conn.execute("SELECT registry_id FROM canonical_mission_meta WHERE singleton=1").fetchone()
        if row is None:
            self._conn.execute("INSERT INTO canonical_mission_meta VALUES(1,?,0)", (registry_id,))
        elif row[0] != registry_id:
            self._conn.close()
            raise CanonicalMissionStateError("mission registry substitution denied")

    def close(self) -> None:
        self._conn.close()

    def register_initial(self, mission: MissionSpec, *, source_provenance_ref: str) -> MissionSpec:
        mission.validate()
        if not source_provenance_ref:
            raise CanonicalMissionStateError("mission provenance required")
        if self._conn.execute("SELECT 1 FROM canonical_mission_active WHERE mission_id=?", (mission.mission_id,)).fetchone():
            raise CanonicalMissionStateError("explicit supersession required")
        digest = mission_digest(mission)
        try:
            self._conn.execute("BEGIN IMMEDIATE")
            self._conn.execute(
                "INSERT INTO canonical_mission_revision VALUES(?,?,?,?,?)",
                (mission.mission_id, 1, digest, _mission_json(mission), source_provenance_ref),
            )
            self._conn.execute("UPDATE canonical_mission_meta SET generation=1 WHERE singleton=1")
            self._conn.execute(
                "INSERT INTO canonical_mission_active VALUES(?,?,?,?)",
                (mission.mission_id, 1, digest, 1),
            )
            self._conn.execute("COMMIT")
        except Exception:
            if self._conn.in_transaction:
                self._conn.execute("ROLLBACK")
            raise
        return mission

    def supersede(self, mission: MissionSpec, *, expected_revision: int, expected_digest: str, source_provenance_ref: str) -> MissionSpec:
        mission.validate()
        if not source_provenance_ref:
            raise CanonicalMissionStateError("mission provenance required")
        current = self._conn.execute(
            "SELECT revision,mission_digest,generation FROM canonical_mission_active WHERE mission_id=?",
            (mission.mission_id,),
        ).fetchone()
        if current is None or int(current[0]) != expected_revision or current[1] != expected_digest:
            raise CanonicalMissionStateError("exact current mission binding mismatch")
        next_revision = expected_revision + 1
        digest = mission_digest(mission)
        if self._conn.execute(
            "SELECT 1 FROM canonical_mission_revision WHERE mission_id=? AND revision=?",
            (mission.mission_id, next_revision),
        ).fetchone():
            raise CanonicalMissionStateError("historical mission rollback/reuse denied")
        try:
            self._conn.execute("BEGIN IMMEDIATE")
            self._conn.execute(
                "INSERT INTO canonical_mission_revision VALUES(?,?,?,?,?)",
                (mission.mission_id, next_revision, digest, _mission_json(mission), source_provenance_ref),
            )
            generation = int(current[2]) + 1
            self._conn.execute("UPDATE canonical_mission_meta SET generation=? WHERE singleton=1", (generation,))
            self._conn.execute(
                "UPDATE canonical_mission_active SET revision=?,mission_digest=?,generation=? WHERE mission_id=?",
                (next_revision, digest, generation, mission.mission_id),
            )
            self._conn.execute("COMMIT")
        except Exception:
            if self._conn.in_transaction:
                self._conn.execute("ROLLBACK")
            raise
        return mission

    def resolve_current(self, mission_id: str) -> tuple[MissionSpec, int, str]:
        row = self._conn.execute(
            "SELECT r.mission_json,a.revision,a.mission_digest FROM canonical_mission_active a "
            "JOIN canonical_mission_revision r ON r.mission_id=a.mission_id AND r.revision=a.revision "
            "WHERE a.mission_id=?",
            (mission_id,),
        ).fetchone()
        if row is None:
            raise CanonicalMissionStateError("canonical mission unavailable")
        try:
            raw = json.loads(row[0])
            raw["required_capabilities"] = tuple(raw.get("required_capabilities", ()))
            mission = MissionSpec(**raw).validate()
        except Exception as exc:
            raise CanonicalMissionStateError("stored mission invalid") from exc
        digest = mission_digest(mission)
        if digest != row[2]:
            raise CanonicalMissionStateError("canonical mission corruption")
        return mission, int(row[1]), digest
