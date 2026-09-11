from __future__ import annotations

def normalize(evidence: dict) -> dict:
    router = evidence.get("router_state") or {}
    mission = router.get("mission") or {}
    by = evidence.get("by_fleet") or {}
    return {
        "materialized": int(evidence.get("materialized") or 0),
        "ready": int(evidence.get("ready") or 0),
        "restarts": int(evidence.get("restart_count_total") or 0),
        "unique_uid_count": int(evidence.get("unique_uid_count") or 0),
        "uid_set": evidence.get("pod_uid_set_sha256"),
        "vendor_requests": int(evidence.get("vendor_requests") or 0),
        "by_fleet": by,
        "fresh_drones": int(router.get("fresh_count") or 0),
        "fresh_by_fleet": router.get("fresh_by_fleet") or {},
        "messages_total": int(router.get("messages_total") or 0),
        "ack_count": int(router.get("ack_count") or 0),
        "ack_rate": float(router.get("ack_rate") or 0.0),
        "duplicates": int(router.get("duplicates") or 0),
        "orphans": int(router.get("orphans") or 0),
        "cases_total": int(router.get("cases_total") or 36),
        "cases_seen": int(router.get("cases_seen") or 0),
        "cases_proven": int(router.get("cases_proven") or 0),
        "participants": router.get("participants") or {},
        "mission": mission,
        "events": router.get("events") or [],
        "messages": router.get("messages") or [],
        "case_state": router.get("case_state") or [],
        "router_error": evidence.get("router_state_error"),
    }

def verify_read_only(snapshot: dict) -> list[str]:
    errors=[]
    if snapshot.get("vendor_requests") != 0: errors.append("VENDOR_REQUESTS_NONZERO")
    if snapshot.get("materialized") not in (0,384): errors.append("POD_CARDINALITY_PARTIAL")
    if snapshot.get("unique_uid_count") not in (0,384): errors.append("UID_CARDINALITY_INVALID")
    return errors
