from __future__ import annotations

import re
from typing import Any

EVENT_SCHEMA = "lion.observation-event/v1"
EVENT_TYPES = {
    "RUN_DISCOVERED", "RUN_STARTED", "PHASE_STARTED", "PHASE_COMPLETED", "METRIC", "PARTICIPANT",
    "ARTIFACT", "RECEIPT", "EVIDENCE", "WARNING", "ERROR", "RUN_COMPLETED", "CLEANUP_STARTED",
    "CLEANUP_COMPLETED", "RUN_RECONCILED", "CHANNEL_MESSAGE",
}
EVENT_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,191}$")
MAX_EVENT_BYTES = 65536
ALLOWED_FIELDS = {
    "schema_version", "event_id", "run_id", "timestamp", "event_type", "process_language", "process_class",
    "adapter_type", "host", "runtime", "phase", "status", "source", "target", "authority", "evidence_class",
    "payload", "artifact_refs", "receipt_refs",
}
FORBIDDEN_CONTROL_KEYS = {
    "command", "shell", "kubectl", "docker", "start_operation", "stop_operation", "delete_operation", "exec"
}


def _reject_control_keys(value: Any) -> None:
    if isinstance(value, dict):
        lowered = {str(key).lower() for key in value}
        if FORBIDDEN_CONTROL_KEYS & lowered:
            raise ValueError("control-like payload key denied")
        for child in value.values():
            _reject_control_keys(child)
    elif isinstance(value, list):
        for child in value:
            _reject_control_keys(child)


def validate_event(event: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(event, dict):
        raise ValueError("event must be object")
    extra = set(event) - ALLOWED_FIELDS
    if extra:
        raise ValueError("unexpected event fields:" + ",".join(sorted(extra)))
    if event.get("schema_version") != EVENT_SCHEMA:
        raise ValueError("event schema mismatch")
    for key in ("event_id", "run_id"):
        value = event.get(key)
        if not isinstance(value, str) or not EVENT_ID_RE.fullmatch(value):
            raise ValueError(f"invalid {key}")
    if event.get("event_type") not in EVENT_TYPES:
        raise ValueError("invalid event_type")
    if not isinstance(event.get("timestamp"), (int, float)):
        raise ValueError("invalid timestamp")
    payload = event.get("payload") or {}
    if not isinstance(payload, dict):
        raise ValueError("payload must be object")
    _reject_control_keys(payload)
    for field in ("source", "target", "authority"):
        value = event.get(field)
        if value is not None and not isinstance(value, dict):
            raise ValueError(f"{field} must be object")
    for field in ("artifact_refs", "receipt_refs"):
        value = event.get(field)
        if value is not None and not isinstance(value, list):
            raise ValueError(f"{field} must be array")
    return dict(event)
