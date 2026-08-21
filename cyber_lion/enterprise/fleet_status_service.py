"""Capability-reduced read-only service for canonical fleet status."""
from __future__ import annotations

import json
from typing import Protocol
from urllib.parse import parse_qs, urlsplit

from cyber_lion.contracts.fleet_status import FleetStatusSnapshot


class FleetStatusReader(Protocol):
    def snapshot(self) -> FleetStatusSnapshot:
        ...


class FleetStatusService:
    """Pure GET surface. No DB, clock, verifier, or provider is caller-selectable."""

    def __init__(self, reader: FleetStatusReader):
        if not hasattr(reader, "snapshot"):
            raise TypeError("reader must expose snapshot()")
        self._reader = reader

    @staticmethod
    def _json(status: int, payload: dict[str, object]) -> tuple[int, dict[str, str], bytes]:
        body = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        return status, {"content-type": "application/json", "content-length": str(len(body))}, body

    def handle(self, method: str, target: str, body: bytes = b"") -> tuple[int, dict[str, str], bytes]:
        if method != "GET":
            return self._json(405, {"error": "METHOD_NOT_ALLOWED"})
        if body:
            return self._json(400, {"error": "GET_BODY_DENIED"})
        parsed = urlsplit(target)
        query = parse_qs(parsed.query, keep_blank_values=True)
        allowed = {
            "/healthz": set(),
            "/v1/fleet/snapshot": set(),
            "/v1/fleet/anomalies": set(),
            "/v1/fleet/drone": {"drone_id"},
            "/v1/fleet/mission": {"mission_id"},
        }
        if parsed.path not in allowed:
            return self._json(404, {"error": "NOT_FOUND"})
        if set(query) - allowed[parsed.path]:
            return self._json(400, {"error": "UNKNOWN_QUERY_PARAMETER"})
        for key, values in query.items():
            if len(values) != 1 or not values[0] or "\x00" in values[0] or len(values[0]) > 512:
                return self._json(400, {"error": "INVALID_QUERY_PARAMETER"})
        try:
            snapshot = self._reader.snapshot()
            wire = snapshot.to_wire()
        except Exception:
            return self._json(503, {"error": "STATUS_UNAVAILABLE"})

        if parsed.path == "/healthz":
            return self._json(200, {
                "status": "ok",
                "snapshot_revision": snapshot.snapshot_revision,
                "snapshot_digest": snapshot.snapshot_digest,
                "observed_at": snapshot.observed_at,
            })
        if parsed.path == "/v1/fleet/snapshot":
            return self._json(200, wire)
        if parsed.path == "/v1/fleet/anomalies":
            return self._json(200, {"anomalies": wire["anomalies"], "snapshot_digest": snapshot.snapshot_digest})
        if parsed.path == "/v1/fleet/drone":
            drone_id = query.get("drone_id", [None])[0]
            if drone_id is None:
                return self._json(400, {"error": "drone_id required"})
            match = next((r for r in wire["drone_records"] if r["drone_id"] == drone_id), None)
            return self._json(200, {"record": match, "snapshot_digest": snapshot.snapshot_digest}) if match else self._json(404, {"error": "DRONE_NOT_FOUND"})
        mission_id = query.get("mission_id", [None])[0]
        if mission_id is None:
            return self._json(400, {"error": "mission_id required"})
        match = next((r for r in wire["drone_records"] if r["mission_id"] == mission_id), None)
        return self._json(200, {"record": match, "snapshot_digest": snapshot.snapshot_digest}) if match else self._json(404, {"error": "MISSION_NOT_FOUND"})
