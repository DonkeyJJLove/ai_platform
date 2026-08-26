"""Fail-closed adapter from canonical fleet evidence to the LION status mapping.

This module is read-only and non-authoritative. It never upgrades missing, stale,
conflicted, or otherwise incomplete evidence to CURRENT/HEALTHY.
"""
from __future__ import annotations

from dataclasses import asdict
import re

from cyber_lion.contracts.fleet_status import FleetStatusSnapshot
from cyber_lion.contracts.swarm_status import compute_revision_digest, compute_status_digest
from .swarm_status_projection import validate_status_projection

_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_ZERO = "0" * 64


class CanonicalLionStatusAdapterError(RuntimeError):
    pass


def _sha(value: str, name: str) -> str:
    if not isinstance(value, str) or _SHA40.fullmatch(value) is None:
        raise CanonicalLionStatusAdapterError(f"{name} must be an exact lowercase git SHA")
    return value


def _refs(snapshot: FleetStatusSnapshot) -> list[str]:
    refs = {f"fleet-snapshot:{snapshot.snapshot_digest}"}
    for record in snapshot.drone_records:
        refs.update(record.evidence_refs)
        for value in (
            record.authority_ref,
            record.sandbox_evidence_ref,
            record.verification_ref,
            record.effect_ref,
            record.reconciliation_ref,
        ):
            if value:
                refs.add(value)
    for anomaly in snapshot.anomalies:
        refs.update(anomaly.evidence_refs)
    return sorted(refs)


def derive_observability(snapshot: FleetStatusSnapshot) -> str:
    snapshot.validate()
    if snapshot.anomalies:
        return "LOST" if any(a.severity in {"ERROR", "BLOCKING"} for a in snapshot.anomalies) else "DEGRADED"
    if not snapshot.drone_records:
        return "LOST"
    states = {r.heartbeat_state for r in snapshot.drone_records}
    if states <= {"HEALTHY", "NOT_EXPECTED"} and all(
        r.evidence_state == "COMPLETE" and r.epistemic_class in {"OBSERVED", "ANCHORED"}
        for r in snapshot.drone_records
    ):
        return "HEALTHY"
    if states & {"STALE", "MISSING", "WAITING_FIRST_HEARTBEAT", "UNKNOWN"}:
        return "LOST"
    return "DEGRADED"


def adapt_fleet_status(
    snapshot: FleetStatusSnapshot,
    *,
    observed_master: str,
    observed_tree: str,
    exact_master_relation_proven: bool,
) -> tuple[dict[str, object], str]:
    """Return validated LION status plus derived observability.

    ``exact_master_relation_proven`` is evidence supplied by the fixed repository
    observation composition root. False can never be upgraded here.
    """
    snapshot.validate()
    master = _sha(observed_master, "observed_master")
    tree = _sha(observed_tree, "observed_tree")
    if type(exact_master_relation_proven) is not bool:
        raise CanonicalLionStatusAdapterError("exact_master_relation_proven must be boolean")

    observability = derive_observability(snapshot)
    anomaly_types = {a.anomaly_type for a in snapshot.anomalies}
    has_conflict = any("CONFLICT" in kind for kind in anomaly_types)
    has_blocker = any(a.severity in {"ERROR", "BLOCKING"} for a in snapshot.anomalies)
    has_stale = any(r.heartbeat_state == "STALE" for r in snapshot.drone_records)
    has_unknown = (
        snapshot.aggregate.unknown_state_count > 0
        or any(r.evidence_state in {"PARTIAL", "MISSING", "CONFLICT", "UNKNOWN"} for r in snapshot.drone_records)
        or any(r.epistemic_class == "UNKNOWN" for r in snapshot.drone_records)
    )

    if has_conflict:
        epistemic = "CONFLICTED"
    elif has_stale:
        epistemic = "STALE"
    elif has_blocker or has_unknown or observability != "HEALTHY" or not exact_master_relation_proven:
        epistemic = "UNKNOWN"
    else:
        epistemic = "CURRENT"

    records = list(snapshot.drone_records)
    status: dict[str, object] = {
        "schema_version": "1.0.0",
        "system_id": "LION",
        "revision": int(snapshot.snapshot_revision),
        "status_digest": "",
        "previous_status_digest": _ZERO,
        "revision_digest": "",
        "previous_revision_digest": _ZERO,
        "generated_at": snapshot.observed_at,
        "observed_master": {"commit": master, "tree": tree},
        "governor": {"state": "OBSERVED_FROM_FLEET_STATUS", "registry_instance_id": snapshot.registry_instance_id},
        "architecture": {"fleet_snapshot_digest": snapshot.snapshot_digest, "scope_class": snapshot.scope_class},
        "critical_path": [r.current_operation for r in records if r.current_operation],
        "formations": [],
        "missions": sorted({r.mission_id for r in records}),
        "drones": sorted({r.drone_id for r in records}),
        "role_assignments": [],
        "dependencies": sorted({r.dependency_state for r in records}),
        "blockers": sorted({a.anomaly_type for a in snapshot.anomalies} | {r.current_blocker for r in records if r.current_blocker}),
        "channels": [],
        "pending_messages": [],
        "epistemic_state": epistemic,
        "source_refs": _refs(snapshot),
        "current_actions": [r.current_operation for r in records if r.current_operation],
        "history": [],
    }
    status["status_digest"] = compute_status_digest(status)
    status["revision_digest"] = compute_revision_digest(
        revision=int(status["revision"]),
        status_digest=str(status["status_digest"]),
        previous_revision_digest=str(status["previous_revision_digest"]),
    )
    validate_status_projection(status)
    return status, observability
