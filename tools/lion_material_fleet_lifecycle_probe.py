#!/usr/bin/env python3
"""Bounded read-only operator entrypoint for mission-scoped fleet demand.

Not a second Mission Control and not a Docker action adapter. The canonical
mission SQLite is opened with mode=ro/query_only. No CLI argument can assert
deployed runtime identity, grant admission, register LPCL, or create a worker.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
import sys
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cyber_lion.mission_control.material_fleet_lifecycle import (
    FleetLifecycleProjectionError,
    project_lifecycle,
)


class ProbeError(ValueError):
    pass


def _existing_regular_file(value: str, *, label: str, max_bytes: int | None = None) -> Path:
    path = Path(value)
    if not path.is_absolute() or path.is_symlink() or not path.is_file():
        raise ProbeError(label + " must be an existing absolute regular file")
    if max_bytes is not None and path.stat().st_size > max_bytes:
        raise ProbeError(label + " file too large")
    return path


def _read_carrier(value: str | None):
    if value is None:
        return None
    file = _existing_regular_file(value, label="fleet carrier", max_bytes=2_000_000)
    try:
        document = json.loads(file.read_text(encoding="utf-8"))
    except (UnicodeError, json.JSONDecodeError) as error:
        raise ProbeError("fleet carrier not valid UTF-8 JSON") from error
    if type(document) is not dict:
        raise ProbeError("fleet carrier must be a JSON object")
    return document


def project_from_database(
    *,
    db_path: str,
    mission_id: str,
    fleet_carrier_path: str | None = None,
    now: datetime | None = None,
) -> dict:
    database = _existing_regular_file(db_path, label="Mission Control database")
    fleet = _read_carrier(fleet_carrier_path)
    # URI quoting prevents a filesystem '?' or '#' from being interpreted as a
    # SQLite open-mode override, and never creates a replacement database.
    uri = "file:" + quote(str(database), safe="/:") + "?mode=ro"
    conn = sqlite3.connect(uri, uri=True, timeout=4)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA query_only=ON")
        before = conn.total_changes
        result = project_lifecycle(
            conn, mission_id, fleet_carrier=fleet,
            current_source=None,  # no self-asserted deployment identity
            at=now or datetime.now(timezone.utc),
        )
        if conn.total_changes != before:
            raise ProbeError("read-only projection attempted a write")
        if result["effect_admitted"] is not False or result["authority_effect"] != "NONE":
            raise ProbeError("non-authorizing projection invariant")
        return result
    finally:
        conn.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description="LION fleet lifecycle diagnostic; no effects")
    parser.add_argument("--db", required=True, help="existing canonical mission-control SQLite")
    parser.add_argument("--mission-id", required=True, help="exact known mission identity")
    parser.add_argument("--fleet-carrier", help="optional canonical fleet-currentness JSON")
    parser.add_argument("--fail-if-blocked", action="store_true")
    arguments = parser.parse_args(argv)
    try:
        result = project_from_database(
            db_path=arguments.db,
            mission_id=arguments.mission_id,
            fleet_carrier_path=arguments.fleet_carrier,
        )
    except (ProbeError, FleetLifecycleProjectionError, sqlite3.Error, OSError, ValueError) as error:
        print(json.dumps({
            "status": "BLOCKED_FAIL_CLOSED",
            "reason_type": type(error).__name__,
            "authority_effect": "NONE",
            "execution_effect": "NONE",
        }, sort_keys=True))
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 3 if arguments.fail_if_blocked and result["state"] in {"BLOCKED", "UNREGISTERED"} else 0


if __name__ == "__main__":
    raise SystemExit(main())
