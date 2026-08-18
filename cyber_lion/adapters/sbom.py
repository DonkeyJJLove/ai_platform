"""Compatibility adapter for DonkeyJJLove/sbom AID event envelopes.

The adapter preserves the complete legacy event under ``payload.compat``.
A legacy event named ``gate`` is *not* promoted to Cyber-Lion ``GateApplied``
without an explicit future gate-result adapter. Names are not authority.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, Mapping

from cyber_lion.contracts.events import Authority, EventEnvelope, Provenance
from cyber_lion.contracts.identity import entity_from_aid


class SBOMAdapterError(ValueError):
    pass


_EVENT_MAP = {
    "sbom": "ObservationCreated",
    "scan": "ObservationCreated",
    "delta": "DeltaDetected",
    "gate": "ObservationCreated",
}


def _event_id(event: Mapping[str, Any], correlation_id: str) -> str:
    canonical = json.dumps(event, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    digest = hashlib.sha256((correlation_id + "\n" + canonical).encode("utf-8")).hexdigest()
    return f"sbom-event:{digest}"


def adapt_sbom_event(event: Mapping[str, Any], *, correlation_id: str) -> EventEnvelope:
    if not correlation_id or not correlation_id.strip():
        raise SBOMAdapterError("correlation_id must be explicit; adapter will not invent trace identity")
    if not isinstance(event, Mapping):
        raise SBOMAdapterError("event must be a mapping")
    timestamp = event.get("@timestamp")
    legacy_type = event.get("event_type")
    aid = event.get("aid")
    payload = event.get("payload", {})
    if not isinstance(timestamp, str) or not timestamp:
        raise SBOMAdapterError("legacy @timestamp is required")
    if not isinstance(legacy_type, str) or not legacy_type:
        raise SBOMAdapterError("legacy event_type is required")
    if not isinstance(aid, Mapping):
        raise SBOMAdapterError("legacy aid object is required")
    if not isinstance(payload, Mapping):
        raise SBOMAdapterError("legacy payload must be an object")

    entity = entity_from_aid(aid)
    mapped_type = _EVENT_MAP.get(legacy_type, "ObservationCreated")

    envelope = EventEnvelope(
        schema_version="1.0.0",
        event_id=_event_id(event, correlation_id),
        event_type=mapped_type,
        occurred_at=timestamp,
        correlation_id=correlation_id.strip(),
        entity=entity.to_dict(),
        source={
            "adapter": "cyber_lion.adapters.sbom",
            "repository": "DonkeyJJLove/sbom",
            "legacy_event_type": legacy_type,
        },
        provenance=Provenance(
            epistemic_status="OBSERVED",
            upstream=[],
            transformation_chain=["sbom-aid-envelope→cyber-lion-event-v1"],
        ),
        authority=Authority(requested="none", effective="none"),
        epistemic_state="FORMALISED",
        payload={
            "compat": {"sbom_event": dict(event)},
            "legacy_payload": dict(payload),
            "legacy_message": event.get("msg"),
            "authority_interpretation": "none",
        },
    )
    return envelope.validate()
