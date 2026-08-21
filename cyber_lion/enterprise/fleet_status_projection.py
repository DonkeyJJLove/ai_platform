"""Canonical snapshot projection for FCSR P0 R1R."""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from hashlib import sha256
import json
from typing import Any

from cyber_lion.contracts.fleet_status import (
    DroneStatusRecord,
    FleetAggregate,
    FleetAnomaly,
    FleetStatusSnapshot,
    SCOPE_CLASS,
)
from cyber_lion.enterprise.fleet_status_state import FleetStatusStore, FleetStatusStateError


def _dt(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _anomaly(kind: str, drone_id: str, mission_id: str, observed_at: str, refs: tuple[str, ...] = ()) -> FleetAnomaly:
    aid = sha256(f"{kind}|{drone_id}|{mission_id}|{observed_at}".encode()).hexdigest()[:24]
    return FleetAnomaly(aid, kind, "BLOCKING", mission_id, drone_id, refs, observed_at)


class FleetStatusProjector:
    """Projects one atomic durable read model into the public snapshot contract."""

    def __init__(self, store: FleetStatusStore):
        self._store = store

    def snapshot(self) -> FleetStatusSnapshot:
        rows = self._store.snapshot_rows()
        observed_at = str(rows["observed_at"])
        meta = rows["meta"]
        identities = rows["identities"]
        missions = rows["missions"]
        runtimes = rows["runtimes"]
        heartbeats = rows["heartbeats"]
        projections = rows["projections"]
        verifications = rows["verifications"]
        leases = rows["leases"]
        receipts = rows["receipts"]
        receipt_head = str(rows["receipt_head"])

        records: list[DroneStatusRecord] = []
        anomalies: list[FleetAnomaly] = []
        for identity in identities:
            drone_id = identity["drone_id"]
            mission_id = identity["mission_id"]
            executor_id = identity["executor_id"]
            mission = missions.get(mission_id)
            runtime = runtimes.get(mission_id)
            heartbeat = heartbeats.get(mission_id)
            verification = verifications.get(mission_id)

            if mission is None:
                anomalies.append(_anomaly("MISSING_MISSION_STATE", drone_id, mission_id, observed_at))
                phase = "UNKNOWN"
                mission_status = "UNKNOWN"
                closure_state = "UNKNOWN"
                current_operation = None
                current_blocker = "missing mission state"
                dependency_state = "UNKNOWN"
                branch_head = None
            else:
                phase = mission["phase"]
                mission_status = mission["status"]
                closure_state = mission["closure_state"]
                current_operation = mission["current_operation"]
                current_blocker = mission["current_blocker"]
                dependency_state = mission["dependency_state"]
                branch_head = mission["branch_head"]

            runtime_id = runtime["runtime_id"] if runtime else None
            heartbeat_state = "UNKNOWN"
            heartbeat_sequence = 0
            heartbeat_deadline = None
            heartbeat_age = None
            last_heartbeat_at = None

            if runtime is None:
                heartbeat_state = "MISSING"
                mission_status = "UNREACHABLE"
                anomalies.append(_anomaly("MISSING_RUNTIME", drone_id, mission_id, observed_at))
            elif heartbeat is None:
                heartbeat_state = "WAITING_FIRST_HEARTBEAT"
                mission_status = "UNREACHABLE"
                anomalies.append(_anomaly("MISSING_HEARTBEAT", drone_id, mission_id, observed_at, (runtime["evidence_ref"],)))
            else:
                heartbeat_sequence = int(heartbeat["sequence"])
                heartbeat_deadline = int(heartbeat["deadline_seconds"])
                last_heartbeat_at = heartbeat["observed_at"]
                heartbeat_age = max(0.0, (_dt(observed_at) - _dt(last_heartbeat_at)).total_seconds())
                if heartbeat_age > heartbeat_deadline:
                    heartbeat_state = "STALE"
                    mission_status = "UNREACHABLE"
                    anomalies.append(_anomaly("STALE_HEARTBEAT", drone_id, mission_id, observed_at, (heartbeat["source_ref"],)))
                else:
                    heartbeat_state = "HEALTHY"

            def proj(kind: str) -> dict[str, Any] | None:
                return projections.get((mission_id, kind))

            authority = proj("authority")
            sandbox = proj("sandbox")
            effect = proj("effect")
            reconciliation = proj("reconciliation")

            authority_state = authority["state"] if authority else "UNKNOWN"
            authority_ref = authority["source_ref"] if authority else None
            authority_observed_at = authority["observed_at"] if authority else None
            if authority_state == "ACTIVE" and heartbeat_state in {"STALE", "MISSING", "WAITING_FIRST_HEARTBEAT"}:
                authority_state = "UNUSABLE_STALE_OBSERVABILITY"

            sandbox_state = sandbox["state"] if sandbox else "UNKNOWN"
            sandbox_ref = sandbox["source_ref"] if sandbox else None
            effect_state = effect["state"] if effect else "UNKNOWN"
            effect_ref = effect["source_ref"] if effect else None
            reconciliation_state = reconciliation["state"] if reconciliation else "UNKNOWN"
            reconciliation_ref = reconciliation["source_ref"] if reconciliation else None

            verification_state = verification["verification_state"] if verification else "UNKNOWN"
            verifier_id = verification["verifier_id"] if verification else None
            verification_ref = verification["source_provenance_ref"] if verification else None

            mission_leases = [x for x in leases if x["mission_id"] == mission_id]
            active_leases = tuple(sorted(x["lease_id"] for x in mission_leases if x["state"] in {"ACTIVE", "STALE_HELD"}))
            if any(x["state"] == "STALE_HELD" for x in mission_leases):
                lease_state = "STALE_HELD"
            elif any(x["state"] == "ACTIVE" for x in mission_leases):
                lease_state = "ACTIVE"
            elif mission_leases and all(x["state"] == "RELEASED" for x in mission_leases):
                lease_state = "RELEASED"
            else:
                lease_state = "UNKNOWN"

            mission_receipts = [x for x in receipts if x["mission_id"] == mission_id]
            last_receipt = mission_receipts[-1]["receipt_id"] if mission_receipts else None

            evidence_refs = []
            if runtime:
                evidence_refs.append(runtime["evidence_ref"])
            if heartbeat:
                evidence_refs.append(heartbeat["source_ref"])
            for item in (authority_ref, sandbox_ref, verification_ref, effect_ref, reconciliation_ref):
                if item:
                    evidence_refs.append(item)
            evidence_refs.extend(x["source_ref"] for x in mission_leases)
            evidence_refs.extend(x["source_ref"] for x in mission_receipts)
            evidence_refs_t = tuple(dict.fromkeys(evidence_refs))

            critical_present = all([
                mission is not None,
                runtime is not None,
                heartbeat is not None,
                authority is not None,
                sandbox is not None,
                verification is not None,
                effect is not None,
                reconciliation is not None,
                bool(mission_receipts),
            ])
            evidence_state = "COMPLETE" if critical_present else ("PARTIAL" if evidence_refs_t else "MISSING")
            epistemic_class = verification["epistemic_class"] if critical_present else "UNKNOWN"

            record = DroneStatusRecord(
                drone_id=drone_id,
                executor_id=executor_id,
                runtime_id=runtime_id,
                mission_id=mission_id,
                parent_mission_id=identity["parent_mission_id"],
                mission_phase=phase,
                mission_status=mission_status,
                closure_state=closure_state,
                repository=identity["repository"],
                baseline_sha=identity["baseline_sha"],
                baseline_tree_sha=identity["baseline_tree_sha"],
                branch=identity["branch"],
                branch_head=branch_head,
                read_scope=tuple(json.loads(identity["read_scope_json"])),
                write_scope=tuple(json.loads(identity["write_scope_json"])),
                authority_state=authority_state,
                authority_ref=authority_ref,
                authority_observed_at=authority_observed_at,
                lease_state=lease_state,
                active_lease_refs=active_leases,
                sandbox_id=identity["sandbox_id"],
                sandbox_state=sandbox_state,
                sandbox_evidence_ref=sandbox_ref,
                heartbeat_state=heartbeat_state,
                heartbeat_sequence=heartbeat_sequence,
                heartbeat_deadline_seconds=heartbeat_deadline,
                heartbeat_age_seconds=heartbeat_age,
                last_heartbeat_at=last_heartbeat_at,
                current_operation=current_operation,
                current_blocker=current_blocker,
                dependency_state=dependency_state,
                verification_state=verification_state,
                verifier_id=verifier_id,
                verification_ref=verification_ref,
                effect_state=effect_state,
                effect_id=None,
                effect_ref=effect_ref,
                reconciliation_state=reconciliation_state,
                reconciliation_ref=reconciliation_ref,
                evidence_state=evidence_state,
                epistemic_class=epistemic_class,
                evidence_refs=evidence_refs_t,
                last_receipt_id=last_receipt,
                receipt_chain_head_digest=receipt_head if mission_receipts else None,
                last_observed_at=observed_at,
            )
            record.validate()
            records.append(record)

        total = len(records)
        unreachable = sum(r.mission_status == "UNREACHABLE" for r in records)
        reachable = total - unreachable
        aggregate = FleetAggregate(
            total_known_drones=total,
            reachable_drones=reachable,
            unreachable_drones=unreachable,
            active_missions=sum(r.mission_status not in {"DONE", "FAILED", "TERMINATED", "UNKNOWN", "UNREACHABLE"} for r in records),
            idle_drones=sum(r.mission_phase == "IDLE" and r.mission_status != "UNREACHABLE" for r in records),
            running_drones=sum(r.mission_status == "RUNNING" for r in records),
            waiting_drones=sum(r.mission_status == "WAITING" for r in records),
            blocked_drones=sum(r.mission_status == "BLOCKED" for r in records),
            degraded_drones=sum(r.mission_status == "DEGRADED" for r in records),
            failed_drones=sum(r.mission_status == "FAILED" for r in records),
            done_not_closed=sum(r.mission_status == "DONE" and r.closure_state != "CLOSED" for r in records),
            missions_in_verification=sum(r.mission_phase == "VERIFY" and r.closure_state != "CLOSED" for r in records),
            missions_in_reconciliation=sum(r.mission_phase == "RECONCILE" and r.closure_state != "CLOSED" for r in records),
            active_authority_count=sum(r.authority_state == "ACTIVE" for r in records),
            active_write_lease_count=sum(r.lease_state in {"ACTIVE", "STALE_HELD"} for r in records),
            unresolved_effect_count=sum(r.effect_state in {"PREPARED", "ATTEMPTED", "RECONCILE_REQUIRED", "UNKNOWN"} for r in records),
            stale_heartbeat_count=sum(r.heartbeat_state == "STALE" for r in records),
            unknown_state_count=sum(
                any(v == "UNKNOWN" for v in (
                    r.mission_phase, r.mission_status, r.closure_state, r.authority_state, r.lease_state,
                    r.sandbox_state, r.verification_state, r.effect_state, r.reconciliation_state,
                ))
                for r in records
            ),
        )
        aggregate.validate()
        snapshot_id = sha256(f"{meta['registry_instance_id']}|{meta['revision']}|{observed_at}".encode()).hexdigest()
        provisional = FleetStatusSnapshot(
            schema_version="1.0.0",
            snapshot_id=snapshot_id,
            snapshot_revision=int(meta["revision"]),
            snapshot_digest="0" * 64,
            observed_at=observed_at,
            registry_instance_id=meta["registry_instance_id"],
            scope_class=SCOPE_CLASS,
            aggregate=aggregate,
            drone_records=tuple(records),
            anomalies=tuple(anomalies),
        )
        digest = provisional.recompute_digest()
        snapshot = replace(provisional, snapshot_digest=digest)
        snapshot.validate()
        return snapshot
