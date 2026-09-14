"""Read-only supervisor view shared by the panel and capability answers."""
from __future__ import annotations

from datetime import datetime, timezone
from collections.abc import Mapping


def _timestamp(value):
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed.astimezone(timezone.utc) if parsed.tzinfo else None
    except (ValueError, TypeError):
        return None


def _record(value, fields):
    if not isinstance(value, Mapping):
        return None
    return {key: value[key] for key in fields if key in value}


def supervisor_projection(bridge, *, now, observed_at=None, max_age_seconds=120):
    """Project supplied evidence only; no I/O, authority or session mutation.

    ``observed_at`` means the time the caller actually read bridge status, not
    the binding creation date. A current lease alone cannot refresh a snapshot.
    ``now`` is explicit so replay and tests evaluate identical evidence.
    """
    source = bridge if isinstance(bridge, Mapping) else {}
    binding = source.get("binding") or source.get("last_binding")
    binding = binding if isinstance(binding, Mapping) else {}
    reasons = []
    current = _timestamp(now)
    observed = _timestamp(observed_at)
    if not source:
        reasons.append("BRIDGE_UNAVAILABLE")
    if source.get("error"):
        reasons.append("BRIDGE_READ_FAILED:" + str(source["error"]))
    age = (current - observed).total_seconds() if current and observed else None
    freshness = "UNKNOWN" if age is None or age < 0 else ("STALE" if age > max_age_seconds else "FRESH")
    if freshness != "FRESH":
        reasons.append("OBSERVATION_" + freshness)
    expiry = binding.get("expires_at")
    expires = _timestamp(expiry)
    lease = "NONE" if not binding else ("UNKNOWN" if not expires or not current else ("ACTIVE" if expires > current else "EXPIRED"))
    reported_session = source.get("session_attestation_state") or ("BOUND" if source.get("state") == "BOUND" else "UNKNOWN")
    session = reported_session
    if not source.get("binding") and binding.get("status") == "EXPIRED":
        session = "EXPIRED"
    if reported_session == "BOUND":
        if lease == "EXPIRED":
            session = "EXPIRED"
        elif lease != "ACTIVE" or freshness != "FRESH":
            session = "UNKNOWN"
            reasons.append("BOUND_CURRENTNESS_UNVERIFIED")
    channel = source.get("channel_state") or "UNKNOWN"
    model = binding.get("model_identity") or "UNKNOWN"
    transport = binding.get("transport") or source.get("transport") or "UNKNOWN"
    hop = source.get("automatic_local_to_saas_hop")
    hop = hop if isinstance(hop, bool) else None
    for key, value in (("CHANNEL", channel), ("MODEL", model), ("TRANSPORT", transport), ("SESSION", session)):
        if value == "UNKNOWN":
            reasons.append(key + "_UNKNOWN")
    if hop is None:
        reasons.append("AUTOMATIC_HOP_UNKNOWN")
    if lease == "UNKNOWN":
        reasons.append("LEASE_UNKNOWN")
    pending_count = source.get("pending_count")
    if not isinstance(pending_count, int) or isinstance(pending_count, bool) or pending_count < 0:
        pending_count = None
    pending_state = "UNKNOWN" if "pending" not in source else ("PRESENT" if source.get("pending") else "NONE")
    receipt_state = "UNKNOWN" if "last_response" not in source else ("PRESENT" if source.get("last_response") else "NONE")
    return {
        "schema": "lion.supervisor-projection/v1",
        "channel": channel, "session": session, "reported_session": reported_session,
        "model": model, "transport": transport,
        "mission_id": source.get("mission_id"),
        "session_scope": source.get("session_scope") or binding.get("binding_scope"),
        "pending": _record(source.get("pending"), ("request_id", "request_code", "status", "progress_state", "created_at", "expires_at", "dual_request_id")),
        "pending_count": pending_count, "pending_state": pending_state, "last_receipt_state": receipt_state,
        "last_receipt": _record(source.get("last_response"), ("request_id", "responded_at", "response_digest", "receipt_digest", "binding_id")),
        "lease": {"state": lease, "expires_at": expiry},
        "authority": "NONE", "reported_authority": source.get("authority_effect") or binding.get("authority_effect") or "UNKNOWN",
        "automatic_hop": hop,
        "freshness": {"state": freshness, "observed_at": observed_at, "evaluated_at": now},
        "unknown_reasons": list(dict.fromkeys(reasons)),
    }
