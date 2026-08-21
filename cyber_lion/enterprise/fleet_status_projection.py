"""Canonical snapshot projection for FCSR P0 R1R + R2 source decisions."""
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
from cyber_lion.enterprise.fleet_status_state import FleetStatusStore


def _dt(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamp must be timezone-aware")
    return parsed


def _anomaly(kind: str, drone_id: str | None, mission_id: str | None, observed_at: str, refs: tuple[str, ...] = ()) -> FleetAnomaly:
    aid = sha256(f"{kind}|{drone_id}|{mission_id}|{observed_at}|{'|'.join(refs)}".encode()).hexdigest()[:24]
    return FleetAnomaly(aid, kind, "BLOCKING", mission_id, drone_id, refs, observed_at)


def _decision_payload(row: dict[str, object]) -> dict[str, Any]:
    payload = json.loads(str(row["decision_json"]))
    if not isinstance(payload, dict) or payload.get("decision_type") != row["decision_type"]:
        raise ValueError("source decision payload mismatch")
    return payload


def _fact_payload(row: dict[str, object] | None) -> dict[str, Any] | None:
    if row is None or row["decision_type"] != "FACT":
        return None
    payload = _decision_payload(row).get("fact")
    if not isinstance(payload, dict):
        raise ValueError("source FACT payload invalid")
    return payload


def _value_dict(fact: dict[str, Any] | None) -> dict[str, str]:
    if fact is None:
        return {}
    items = fact.get("value_items")
    if not isinstance(items, list):
        raise ValueError("source FACT value_items invalid")
    out: dict[str, str] = {}
    for item in items:
        if not isinstance(item, list) or len(item) != 2 or not all(isinstance(x, str) for x in item):
            raise ValueError("source FACT value item invalid")
        if item[0] in out:
            raise ValueError("source FACT value key duplicate")
        out[item[0]] = item[1]
    return out


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
        source_observations = rows.get("source_observations", [])
        source_decisions = rows.get("source_decisions", [])

        decision_by_key: dict[tuple[str, str], dict[str, object]] = {}
        global_decisions: list[dict[str, object]] = []
        for decision in source_decisions:
            mission_id = decision.get("mission_id")
            dimension = decision.get("dimension")
            if isinstance(mission_id, str) and isinstance(dimension, str):
                decision_by_key[(mission_id, dimension)] = decision
            else:
                global_decisions.append(decision)

        source_refs_by_mission: dict[str, list[str]] = {}
        for row in source_observations:
            payload = json.loads(str(row["observation_json"]))
            mission_id = payload.get("mission_id")
            provenance_ref = payload.get("provenance_ref")
            if isinstance(mission_id, str) and isinstance(provenance_ref, str):
                source_refs_by_mission.setdefault(mission_id, []).append(provenance_ref)

        records: list[DroneStatusRecord] = []
        anomalies: list[FleetAnomaly] = []

        # Source conflicts/missing evidence are visible even for a mission not yet eligible
        # for a canonical DroneStatusRecord (for example FCP identity without executor/runtime).
        for decision in source_decisions:
            dtype = str(decision["decision_type"])
            payload = _decision_payload(decision)
            if dtype == "CONFLICT":
                conflict = payload.get("conflict")
                if not isinstance(conflict, dict):
                    raise ValueError("source conflict payload invalid")
                refs = tuple(conflict.get("evidence_refs", ()))
                anomalies.append(_anomaly(
                    str(conflict.get("conflict_type", "SOURCE_CONFLICT")),
                    conflict.get("drone_id") if isinstance(conflict.get("drone_id"), str) else None,
                    conflict.get("mission_id") if isinstance(conflict.get("mission_id"), str) else None,
                    str(conflict.get("observed_at", decision["observed_at"])),
                    tuple(str(x) for x in refs),
                ))
            elif dtype == "MISSING":
                missing = payload.get("missing")
                if not isinstance(missing, dict):
                    raise ValueError("missing-source payload invalid")
                dimension = str(missing.get("dimension", decision["dimension"]))
                anomalies.append(_anomaly(
                    f"MISSING_STATUS_SOURCE_{dimension}",
                    missing.get("drone_id") if isinstance(missing.get("drone_id"), str) else None,
                    missing.get("mission_id") if isinstance(missing.get("mission_id"), str) else None,
                    str(missing.get("observed_at", decision["observed_at"])),
                ))

        for identity in identities:
            drone_id = identity["drone_id"]
            mission_id = identity["mission_id"]
            executor_id = identity["executor_id"]
            mission = missions.get(mission_id)
            runtime = runtimes.get(mission_id)
            heartbeat = heartbeats.get(mission_id)
            verification = verifications.get(mission_id)

            mission_decision = decision_by_key.get((mission_id, "MISSION"))
            runtime_decision = decision_by_key.get((mission_id, "RUNTIME"))
            heartbeat_decision = decision_by_key.get((mission_id, "HEARTBEAT"))
            authority_decision = decision_by_key.get((mission_id, "AUTHORITY"))
            lease_decision = decision_by_key.get((mission_id, "LEASE"))
            sandbox_decision = decision_by_key.get((mission_id, "SANDBOX"))
            verification_decision = decision_by_key.get((mission_id, "VERIFICATION"))
            effect_decision = decision_by_key.get((mission_id, "EFFECT"))
            reconciliation_decision = decision_by_key.get((mission_id, "RECONCILIATION"))
            repository_decision = decision_by_key.get((mission_id, "REPOSITORY"))
            receipt_decision = decision_by_key.get((mission_id, "RECEIPT"))

            active_decisions = {
                "MISSION": mission_decision,
                "RUNTIME": runtime_decision,
                "HEARTBEAT": heartbeat_decision,
                "AUTHORITY": authority_decision,
                "LEASE": lease_decision,
                "SANDBOX": sandbox_decision,
                "VERIFICATION": verification_decision,
                "EFFECT": effect_decision,
                "RECONCILIATION": reconciliation_decision,
                "REPOSITORY": repository_decision,
                "RECEIPT": receipt_decision,
                "IDENTITY": decision_by_key.get((mission_id, "IDENTITY")),
                "CI": decision_by_key.get((mission_id, "CI")),
            }
            conflict_dimensions = {
                dimension for dimension, decision in active_decisions.items()
                if decision is not None and decision["decision_type"] == "CONFLICT"
            }
            missing_dimensions = {
                dimension for dimension, decision in active_decisions.items()
                if decision is not None and decision["decision_type"] == "MISSING"
            }
            conflict_types = set()
            for decision in active_decisions.values():
                if decision is not None and decision["decision_type"] == "CONFLICT":
                    payload = _decision_payload(decision).get("conflict")
                    if isinstance(payload, dict):
                        conflict_types.add(str(payload.get("conflict_type")))

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

            mission_fact = _fact_payload(mission_decision)
            if mission_fact is not None:
                values = _value_dict(mission_fact)
                phase = values.get("phase", phase)
                mission_status = str(mission_fact.get("state", mission_status))
                closure_state = values.get("closure_state", closure_state)
                current_operation = values.get("current_operation") or current_operation
                current_blocker = values.get("current_blocker") or current_blocker
                dependency_state = values.get("dependency_state", dependency_state)
            if "MISSION" in conflict_dimensions or "MISSION" in missing_dimensions:
                phase = "UNKNOWN"
                mission_status = "UNKNOWN"
                closure_state = "UNKNOWN"

            repo_fact = _fact_payload(repository_decision)
            if repo_fact is not None:
                branch_head = _value_dict(repo_fact).get("branch_head_sha") or branch_head
            if "REPOSITORY" in conflict_dimensions or "REPOSITORY" in missing_dimensions:
                branch_head = None

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

            # R2 wall-clock heartbeat source overrides the legacy process-local heartbeat table.
            heartbeat_fact = _fact_payload(heartbeat_decision)
            if heartbeat_fact is not None:
                values = _value_dict(heartbeat_fact)
                hb_runtime = values.get("runtime_id")
                if hb_runtime != runtime_id:
                    heartbeat_state = "UNKNOWN"
                    mission_status = "UNREACHABLE"
                else:
                    heartbeat_sequence = int(values["sequence"])
                    heartbeat_deadline = int(values["deadline_seconds"])
                    last_heartbeat_at = values["heartbeat_observed_at"]
                    heartbeat_age = max(0.0, (_dt(observed_at) - _dt(last_heartbeat_at)).total_seconds())
                    if heartbeat_age > heartbeat_deadline:
                        heartbeat_state = "STALE"
                        mission_status = "UNREACHABLE"
                        anomalies.append(_anomaly("STALE_HEARTBEAT", drone_id, mission_id, observed_at, tuple(heartbeat_fact.get("evidence_refs", ()))))
                    else:
                        heartbeat_state = "HEALTHY"
                        if mission_fact is not None and "MISSION" not in conflict_dimensions and "MISSION" not in missing_dimensions:
                            mission_status = str(mission_fact.get("state", mission_status))
                        elif mission is not None:
                            mission_status = mission["status"]
            if "RUNTIME" in conflict_dimensions or "RUNTIME" in missing_dimensions:
                runtime_id = None if "RUNTIME" in missing_dimensions else runtime_id
                heartbeat_state = "UNKNOWN"
                mission_status = "UNREACHABLE"
            if "HEARTBEAT" in conflict_dimensions:
                heartbeat_state = "UNKNOWN"
                mission_status = "UNREACHABLE"
            elif "HEARTBEAT" in missing_dimensions:
                heartbeat_state = "UNKNOWN"
                mission_status = "UNREACHABLE"

            def proj(kind: str) -> dict[str, Any] | None:
                return projections.get((mission_id, kind))

            authority = proj("authority")
            sandbox = proj("sandbox")
            effect = proj("effect")
            reconciliation = proj("reconciliation")

            authority_state = authority["state"] if authority else "UNKNOWN"
            authority_ref = authority["source_ref"] if authority else None
            authority_observed_at = authority["observed_at"] if authority else None
            if "AUTHORITY" in conflict_dimensions or "AUTHORITY" in missing_dimensions:
                authority_state, authority_ref, authority_observed_at = "UNKNOWN", None, None
            if authority_state == "ACTIVE" and heartbeat_state in {"STALE", "MISSING", "WAITING_FIRST_HEARTBEAT", "UNKNOWN"}:
                authority_state = "UNUSABLE_STALE_OBSERVABILITY"

            sandbox_state = sandbox["state"] if sandbox else "UNKNOWN"
            sandbox_ref = sandbox["source_ref"] if sandbox else None
            if "SANDBOX" in conflict_dimensions or "SANDBOX" in missing_dimensions:
                sandbox_state, sandbox_ref = "UNKNOWN", None

            effect_state = effect["state"] if effect else "UNKNOWN"
            effect_ref = effect["source_ref"] if effect else None
            if "EFFECT" in conflict_dimensions or "EFFECT" in missing_dimensions:
                effect_state, effect_ref = "UNKNOWN", None

            reconciliation_state = reconciliation["state"] if reconciliation else "UNKNOWN"
            reconciliation_ref = reconciliation["source_ref"] if reconciliation else None
            if "RECONCILIATION" in conflict_dimensions or "RECONCILIATION" in missing_dimensions:
                reconciliation_state, reconciliation_ref = "UNKNOWN", None

            verification_state = verification["verification_state"] if verification else "UNKNOWN"
            verifier_id = verification["verifier_id"] if verification else None
            verification_ref = verification["source_provenance_ref"] if verification else None
            if "VERIFICATION" in conflict_dimensions or "VERIFICATION" in missing_dimensions:
                verification_state, verifier_id, verification_ref = "UNKNOWN", None, None

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
            if "LEASE" in conflict_dimensions or "LEASE" in missing_dimensions:
                lease_state = "UNKNOWN"

            mission_receipts = [x for x in receipts if x["mission_id"] == mission_id]
            last_receipt = mission_receipts[-1]["receipt_id"] if mission_receipts else None
            if "RECEIPT" in conflict_dimensions or "RECEIPT" in missing_dimensions:
                last_receipt = None

            # Positive mission completion must not survive a critical source disagreement.
            if mission_status == "DONE" and verification_state != "PASS":
                mission_status = "UNKNOWN"
            if "DONE_WITH_UNRECONCILED_EFFECT" in conflict_types:
                mission_status = "UNKNOWN"
            if "CLOSED_WITH_ACTIVE_AUTHORITY" in conflict_types or "CLOSED_WITH_ACTIVE_WRITE_LEASE" in conflict_types:
                closure_state = "UNKNOWN"

            effect_id = None
            effect_fact = _fact_payload(effect_decision)
            if effect_fact is not None and "EFFECT" not in conflict_dimensions and "EFFECT" not in missing_dimensions:
                effect_id = _value_dict(effect_fact).get("effect_id")

            evidence_refs: list[str] = []
            if runtime:
                evidence_refs.append(runtime["evidence_ref"])
            if heartbeat:
                evidence_refs.append(heartbeat["source_ref"])
            for item in (authority_ref, sandbox_ref, verification_ref, effect_ref, reconciliation_ref):
                if item:
                    evidence_refs.append(item)
            evidence_refs.extend(x["source_ref"] for x in mission_leases)
            evidence_refs.extend(x["source_ref"] for x in mission_receipts)
            evidence_refs.extend(source_refs_by_mission.get(mission_id, ()))
            for decision in active_decisions.values():
                if decision is None or decision["decision_type"] != "FACT":
                    continue
                fact = _fact_payload(decision)
                if fact:
                    evidence_refs.extend(str(x) for x in fact.get("evidence_refs", ()))
            evidence_refs_t = tuple(dict.fromkeys(evidence_refs))

            critical_dimensions = {"MISSION", "RUNTIME", "HEARTBEAT", "AUTHORITY", "SANDBOX", "VERIFICATION", "EFFECT", "RECONCILIATION", "RECEIPT"}
            source_critical_missing = bool(missing_dimensions.intersection(critical_dimensions))
            source_critical_conflict = bool(conflict_dimensions.intersection(critical_dimensions | {"IDENTITY", "REPOSITORY"}))
            critical_present = all([
                mission is not None,
                runtime is not None,
                heartbeat_fact is not None or heartbeat is not None,
                authority is not None,
                sandbox is not None,
                verification is not None,
                effect is not None,
                reconciliation is not None,
                bool(mission_receipts),
            ]) and not source_critical_missing and not source_critical_conflict
            if source_critical_conflict:
                evidence_state = "CONFLICT"
            else:
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
                effect_id=effect_id,
                effect_ref=effect_ref,
                reconciliation_state=reconciliation_state,
                reconciliation_ref=reconciliation_ref,
                evidence_state=evidence_state,
                epistemic_class=epistemic_class,
                evidence_refs=evidence_refs_t,
                last_receipt_id=last_receipt,
                receipt_chain_head_digest=receipt_head if mission_receipts and last_receipt else None,
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
                or r.evidence_state in {"CONFLICT", "UNKNOWN"}
                for r in records
            ),
        )
        aggregate.validate()

        # Stable anomaly de-duplication: a source conflict and a legacy derived anomaly may overlap.
        anomaly_by_id = {item.anomaly_id: item for item in anomalies}
        anomalies = list(anomaly_by_id.values())
        anomalies.sort(key=lambda item: item.anomaly_id)

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
