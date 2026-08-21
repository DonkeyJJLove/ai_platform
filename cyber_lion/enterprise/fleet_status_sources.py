"""Trust and reconciliation policy for FCSR R2 status sources.

This module consumes already journaled observations. It cannot grant authority,
change a live lease, dispatch missions, or execute repository effects.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from typing import Iterable, Mapping, Sequence

from cyber_lion.contracts.fleet_status_sources import (
    ReconciledStatusFact,
    SourceConflict,
    StatusSourceIdentity,
    StatusSourceObservation,
    StatusSourcePin,
)


class FleetStatusSourceError(RuntimeError):
    """Fail-closed source trust/reconciliation error."""


PRIMARY_OWNERS: Mapping[str, tuple[str, ...]] = {
    "IDENTITY": ("FLEET_CONTROL",),
    "MISSION": ("FLEET_CONTROL",),
    "RUNTIME": ("RUNTIME_ATTESTATION",),
    "HEARTBEAT": ("HEARTBEAT",),
    "AUTHORITY": ("AUTHORITY_STATE",),
    "LEASE": ("LEASE_STATE",),
    "SANDBOX": ("SANDBOX",),
    "VERIFICATION": ("VERIFICATION",),
    "EFFECT": ("EFFECT",),
    "RECONCILIATION": ("RECONCILIATION",),
    "RECEIPT": ("RECEIPT",),
    "REPOSITORY": ("REPOSITORY",),
    "CI": ("CI",),
}

CORROBORATORS: Mapping[str, tuple[str, ...]] = {
    "AUTHORITY": ("RUNTIME_AUTHORITY",),
    "RUNTIME": ("RUNTIME_AUTHORITY",),
}


@dataclass(frozen=True)
class PersistedSourceObservation:
    source_identity: StatusSourceIdentity
    source_sequence: int
    source_observed_at: str
    ingested_at: str
    batch_digest: str
    source_chain_digest: str
    observation: StatusSourceObservation

    def validate(self) -> "PersistedSourceObservation":
        self.source_identity.validate()
        self.observation.validate()
        if isinstance(self.source_sequence, bool) or not isinstance(self.source_sequence, int) or self.source_sequence < 1:
            raise FleetStatusSourceError("persisted source_sequence invalid")
        for value, name in ((self.source_observed_at, "source_observed_at"), (self.ingested_at, "ingested_at")):
            try:
                parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            except (AttributeError, ValueError) as exc:
                raise FleetStatusSourceError(f"{name} invalid") from exc
            if parsed.tzinfo is None:
                raise FleetStatusSourceError(f"{name} must be timezone-aware")
        if len(self.batch_digest) != 64 or len(self.source_chain_digest) != 64:
            raise FleetStatusSourceError("persisted digest invalid")
        return self


class StatusSourceTrustRegistry:
    """Composition-root-owned immutable source pin registry."""

    def __init__(self, pins: tuple[StatusSourcePin, ...]) -> None:
        if type(pins) is not tuple or not pins:
            raise FleetStatusSourceError("at least one source pin is required")
        by_id: dict[str, StatusSourcePin] = {}
        for pin in pins:
            if type(pin) is not StatusSourcePin:
                raise FleetStatusSourceError("invalid source pin type")
            pin.validate()
            if pin.source_id in by_id:
                raise FleetStatusSourceError("duplicate status source pin")
            by_id[pin.source_id] = pin
        self._pins = by_id

    def admit(self, identity: StatusSourceIdentity) -> StatusSourceIdentity:
        if type(identity) is not StatusSourceIdentity:
            raise FleetStatusSourceError("source identity must use exact contract type")
        pin = self._pins.get(identity.source_id)
        if pin is None:
            raise FleetStatusSourceError("untrusted status source")
        try:
            return pin.validate_identity(identity)
        except Exception as exc:
            raise FleetStatusSourceError("status source pin mismatch") from exc

    def source_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._pins))


def _conflict(
    kind: str,
    *,
    mission_id: str | None,
    drone_id: str | None,
    dimension: str,
    rows: Sequence[PersistedSourceObservation],
    observed_at: str,
) -> SourceConflict:
    sources = tuple(sorted({row.source_identity.source_id for row in rows}))
    observations = tuple(sorted({row.observation.observation_id for row in rows}))
    refs = tuple(sorted({row.observation.provenance_ref for row in rows}))
    raw = f"{kind}|{mission_id}|{drone_id}|{dimension}|{'|'.join(sources)}|{'|'.join(observations)}"
    return SourceConflict(
        conflict_id=sha256(raw.encode()).hexdigest(),
        conflict_type=kind,
        mission_id=mission_id,
        drone_id=drone_id,
        dimension=dimension,
        source_ids=sources,
        observation_ids=observations,
        evidence_refs=refs,
        observed_at=observed_at,
    ).validate()


def _row_key(row: PersistedSourceObservation) -> tuple[object, ...]:
    obs = row.observation
    return (
        obs.state,
        obs.value_items,
        obs.drone_id,
        obs.executor_id,
        obs.runtime_id,
        obs.repository,
        obs.baseline_sha,
    )


class StatusSourceReconciler:
    """Dimension-owner reconciler. Disagreement degrades knowledge, never authority."""

    def latest_per_source(
        self,
        rows: Iterable[PersistedSourceObservation],
    ) -> tuple[PersistedSourceObservation, ...]:
        latest: dict[tuple[str, str | None, str], PersistedSourceObservation] = {}
        for row in rows:
            row.validate()
            key = (
                row.source_identity.source_id,
                row.observation.mission_id,
                row.observation.dimension,
            )
            previous = latest.get(key)
            if previous is None or row.source_sequence > previous.source_sequence:
                latest[key] = row
        return tuple(latest.values())

    def reconcile(
        self,
        rows: Iterable[PersistedSourceObservation],
        *,
        observed_at: str,
    ) -> tuple[tuple[ReconciledStatusFact, ...], tuple[SourceConflict, ...]]:
        latest = self.latest_per_source(rows)
        groups: dict[tuple[str | None, str], list[PersistedSourceObservation]] = {}
        for row in latest:
            groups.setdefault((row.observation.mission_id, row.observation.dimension), []).append(row)

        facts: list[ReconciledStatusFact] = []
        conflicts: list[SourceConflict] = []
        for (mission_id, dimension), group in groups.items():
            if mission_id is None:
                continue
            owner_kinds = PRIMARY_OWNERS.get(dimension, ())
            owners = [row for row in group if row.source_identity.source_kind in owner_kinds]
            if not owners:
                continue
            if dimension in {"IDENTITY", "MISSION"} and len({row.source_identity.source_id for row in owners}) > 1:
                conflicts.append(_conflict(
                    "DUPLICATE_MISSION_OWNER",
                    mission_id=mission_id,
                    drone_id=owners[0].observation.drone_id,
                    dimension=dimension,
                    rows=owners,
                    observed_at=observed_at,
                ))
                continue
            canonical = _row_key(owners[0])
            if any(_row_key(row) != canonical for row in owners[1:]):
                conflicts.append(_conflict(
                    "SOURCE_PROVENANCE_CONFLICT",
                    mission_id=mission_id,
                    drone_id=owners[0].observation.drone_id,
                    dimension=dimension,
                    rows=owners,
                    observed_at=observed_at,
                ))
                continue

            corroborators = [
                row for row in group
                if row.source_identity.source_kind in CORROBORATORS.get(dimension, ())
            ]
            if corroborators:
                owner_values = owners[0].observation.value_dict()
                for row in corroborators:
                    overlap = set(owner_values).intersection(row.observation.value_dict())
                    if any(owner_values[key] != row.observation.value_dict()[key] for key in overlap):
                        conflicts.append(_conflict(
                            "CORROBORATING_SOURCE_DISAGREEMENT",
                            mission_id=mission_id,
                            drone_id=owners[0].observation.drone_id,
                            dimension=dimension,
                            rows=tuple(owners) + (row,),
                            observed_at=observed_at,
                        ))
                        break
                else:
                    corroborators = list(corroborators)
                    sources = tuple(sorted({row.source_identity.source_id for row in owners + corroborators}))
                    refs = tuple(sorted({row.observation.provenance_ref for row in owners + corroborators}))
                    epistemic = "ANCHORED" if all(
                        row.observation.epistemic_class == "ANCHORED" for row in owners + corroborators
                    ) else "OBSERVED"
                    fact = ReconciledStatusFact(
                        mission_id=mission_id,
                        dimension=dimension,
                        state=owners[0].observation.state,
                        value_items=owners[0].observation.value_items,
                        source_ids=sources,
                        evidence_refs=refs,
                        epistemic_class=epistemic,
                    ).validate()
                    facts.append(fact)
                    continue
                continue

            sources = tuple(sorted({row.source_identity.source_id for row in owners}))
            refs = tuple(sorted({row.observation.provenance_ref for row in owners}))
            epistemic = "ANCHORED" if all(
                row.observation.epistemic_class == "ANCHORED" for row in owners
            ) else "OBSERVED"
            facts.append(ReconciledStatusFact(
                mission_id=mission_id,
                dimension=dimension,
                state=owners[0].observation.state,
                value_items=owners[0].observation.value_items,
                source_ids=sources,
                evidence_refs=refs,
                epistemic_class=epistemic,
            ).validate())

        facts.sort(key=lambda item: (item.mission_id, item.dimension))
        conflicts.sort(key=lambda item: item.conflict_id)
        return tuple(facts), tuple(conflicts)

    def detect_global_conflicts(
        self,
        facts: Sequence[ReconciledStatusFact],
        *,
        observed_at: str,
    ) -> tuple[SourceConflict, ...]:
        by_key = {(fact.mission_id, fact.dimension): fact for fact in facts}
        conflicts: list[SourceConflict] = []

        def synthetic(kind: str, fact_set: Sequence[ReconciledStatusFact], dimension: str, mission_id: str | None = None) -> SourceConflict:
            source_ids = tuple(sorted({sid for fact in fact_set for sid in fact.source_ids}))
            refs = tuple(sorted({ref for fact in fact_set for ref in fact.evidence_refs}))
            mid = mission_id if mission_id is not None else (fact_set[0].mission_id if fact_set else None)
            drone = None
            if fact_set:
                drone = fact_set[0].value_dict().get("drone_id")
            raw = f"{kind}|{mid}|{dimension}|{'|'.join(source_ids)}|{'|'.join(refs)}"
            return SourceConflict(
                sha256(raw.encode()).hexdigest(), kind, mid, drone, dimension,
                source_ids, (), refs, observed_at,
            ).validate()

        identity_facts = [fact for fact in facts if fact.dimension == "IDENTITY"]
        by_drone: dict[str, list[ReconciledStatusFact]] = {}
        by_branch: dict[tuple[str, str], list[ReconciledStatusFact]] = {}
        for fact in identity_facts:
            values = fact.value_dict()
            drone = values.get("drone_id")
            repository = values.get("repository")
            branch = values.get("branch")
            if drone:
                by_drone.setdefault(drone, []).append(fact)
            if repository and branch:
                by_branch.setdefault((repository, branch), []).append(fact)
        for group in by_drone.values():
            missions = {item.mission_id for item in group}
            if len(missions) > 1:
                for mission_id in sorted(missions):
                    conflicts.append(synthetic("DUPLICATE_DRONE_ID", group, "IDENTITY", mission_id))
        for group in by_branch.values():
            active = []
            for fact in group:
                mission = by_key.get((fact.mission_id, "MISSION"))
                if mission is None or mission.state not in {"DONE", "FAILED", "TERMINATED"}:
                    active.append(fact)
            missions = {item.mission_id for item in active}
            if len(missions) > 1:
                for mission_id in sorted(missions):
                    conflicts.append(synthetic("DUPLICATE_BRANCH_OWNER", active, "IDENTITY", mission_id))

        runtime_facts = [fact for fact in facts if fact.dimension == "RUNTIME"]
        by_executor: dict[str, list[ReconciledStatusFact]] = {}
        for fact in runtime_facts:
            executor = fact.value_dict().get("executor_id")
            if executor:
                by_executor.setdefault(executor, []).append(fact)
            identity = by_key.get((fact.mission_id, "IDENTITY"))
            if identity is not None:
                iv = identity.value_dict()
                rv = fact.value_dict()
                if rv.get("repository") != iv.get("repository"):
                    conflicts.append(synthetic("MISSION_REGISTRY_RUNTIME_DISAGREEMENT", (identity, fact), "RUNTIME", fact.mission_id))
        for group in by_executor.values():
            missions = {item.mission_id for item in group}
            if len(missions) > 1:
                for mission_id in sorted(missions):
                    conflicts.append(synthetic("DUPLICATE_EXECUTOR_ID", group, "RUNTIME", mission_id))

        heartbeat_facts = [fact for fact in facts if fact.dimension == "HEARTBEAT"]
        for fact in heartbeat_facts:
            runtime = by_key.get((fact.mission_id, "RUNTIME"))
            if runtime is None:
                continue
            if fact.value_dict().get("runtime_id") != runtime.value_dict().get("runtime_id"):
                conflicts.append(synthetic("HEARTBEAT_RUNTIME_DISAGREEMENT", (runtime, fact), "HEARTBEAT", fact.mission_id))

        repository_facts = [fact for fact in facts if fact.dimension == "REPOSITORY"]
        for fact in repository_facts:
            identity = by_key.get((fact.mission_id, "IDENTITY"))
            if identity is None:
                continue
            iv = identity.value_dict()
            rv = fact.value_dict()
            if rv.get("repository", iv.get("repository")) != iv.get("repository"):
                conflicts.append(synthetic("REPOSITORY_IDENTITY_DISAGREEMENT", (identity, fact), "REPOSITORY", fact.mission_id))
            if rv.get("baseline_sha") != iv.get("baseline_sha"):
                conflicts.append(synthetic("STALE_BASELINE", (identity, fact), "REPOSITORY", fact.mission_id))
            if rv.get("branch") != iv.get("branch"):
                conflicts.append(synthetic("BRANCH_OWNERSHIP_DISAGREEMENT", (identity, fact), "REPOSITORY", fact.mission_id))

        lease_facts = [fact for fact in facts if fact.dimension == "LEASE" and fact.state in {"ACTIVE", "STALE_HELD"}]
        for idx, left in enumerate(lease_facts):
            lv = left.value_dict()
            for right in lease_facts[idx + 1:]:
                rv = right.value_dict()
                if lv.get("repository") != rv.get("repository") or lv.get("lease_type") != rv.get("lease_type"):
                    continue
                if left.mission_id == right.mission_id:
                    continue
                a = lv.get("resource", "").rstrip("/")
                b = rv.get("resource", "").rstrip("/")
                overlap = a == b or (a and b and (a.startswith(b + "/") or b.startswith(a + "/")))
                if overlap:
                    conflicts.append(synthetic("OVERLAPPING_WRITE_LEASE", (left, right), "LEASE", left.mission_id))
                    conflicts.append(synthetic("OVERLAPPING_WRITE_LEASE", (left, right), "LEASE", right.mission_id))

        for mission_id in sorted({fact.mission_id for fact in facts}):
            mission = by_key.get((mission_id, "MISSION"))
            if mission is None:
                continue
            verification = by_key.get((mission_id, "VERIFICATION"))
            effect = by_key.get((mission_id, "EFFECT"))
            reconciliation = by_key.get((mission_id, "RECONCILIATION"))
            authority = by_key.get((mission_id, "AUTHORITY"))
            lease = by_key.get((mission_id, "LEASE"))
            if mission.state == "DONE" and (verification is None or verification.state != "PASS"):
                conflicts.append(synthetic("DONE_WITHOUT_VERIFICATION", (mission,), "VERIFICATION", mission_id))
            if mission.state == "DONE" and (
                effect is None
                or effect.state in {"PREPARED", "ATTEMPTED", "RECONCILE_REQUIRED", "UNKNOWN"}
                or reconciliation is None
                or reconciliation.state not in {"RESOLVED", "NOT_REQUIRED"}
            ):
                conflicts.append(synthetic("DONE_WITH_UNRECONCILED_EFFECT", (mission,) + tuple(x for x in (effect, reconciliation) if x), "RECONCILIATION", mission_id))
            closure = mission.value_dict().get("closure_state")
            if closure == "CLOSED" and authority is not None and authority.state == "ACTIVE":
                conflicts.append(synthetic("CLOSED_WITH_ACTIVE_AUTHORITY", (mission, authority), "AUTHORITY", mission_id))
            if closure == "CLOSED" and lease is not None and lease.state in {"ACTIVE", "STALE_HELD"}:
                conflicts.append(synthetic("CLOSED_WITH_ACTIVE_WRITE_LEASE", (mission, lease), "LEASE", mission_id))

        unique = {item.conflict_id: item for item in conflicts}
        return tuple(sorted(unique.values(), key=lambda item: item.conflict_id))
