"""Canonical FCSR R2 ingestion: trusted source reads -> journal -> reconcile -> project.

The ingestion composition root owns its fixed adapters, trust registry and clock. Callers
cannot select providers, source identities, clocks, authority, leases, or effects.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
import re
from typing import Callable, Iterable

from cyber_lion.contracts.fleet_status import FleetStatusIdentity
from cyber_lion.contracts.fleet_status_sources import (
    MissingStatusSource,
    ReconciledStatusFact,
    SourceConflict,
    StatusSourceIdentity,
    StatusSourceObservation,
    StatusSourceRead,
)
from cyber_lion.enterprise.fleet_status_adapters import ReadOnlyStatusSource
from cyber_lion.enterprise.fleet_status_sources import (
    PRIMARY_OWNERS,
    PersistedSourceObservation,
    StatusSourceReconciler,
    StatusSourceTrustRegistry,
)
from cyber_lion.enterprise.fleet_status_state import FleetStatusStateError, FleetStatusStore

_SHA40 = re.compile(r"^[0-9a-f]{40}$")


class FleetStatusIngestionError(RuntimeError):
    """Fail-closed ingestion error."""


@dataclass(frozen=True)
class IngestionCycleResult:
    facts: tuple[ReconciledStatusFact, ...]
    conflicts: tuple[SourceConflict, ...]
    missing: tuple[MissingStatusSource, ...]
    source_ids: tuple[str, ...]


def _now(clock: Callable[[], datetime]) -> str:
    value = clock()
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise FleetStatusIngestionError("ingestion clock must be timezone-aware")
    return value.astimezone(timezone.utc).isoformat()


def _sha40(value: str | None, name: str) -> str:
    if not isinstance(value, str) or not _SHA40.fullmatch(value):
        raise FleetStatusIngestionError(f"{name} must be a full lowercase git SHA")
    return value


def _scope(value: str, name: str) -> tuple[str, ...]:
    try:
        raw = json.loads(value)
    except (TypeError, json.JSONDecodeError) as exc:
        raise FleetStatusIngestionError(f"{name} is not canonical JSON") from exc
    if not isinstance(raw, list) or not raw or any(not isinstance(x, str) or not x for x in raw):
        raise FleetStatusIngestionError(f"{name} is invalid")
    result = tuple(raw)
    if len(set(result)) != len(result):
        raise FleetStatusIngestionError(f"{name} contains duplicates")
    return result


def _observation_from_json(raw: str) -> StatusSourceObservation:
    try:
        payload = json.loads(raw)
    except (TypeError, json.JSONDecodeError) as exc:
        raise FleetStatusIngestionError("persisted observation JSON is invalid") from exc
    if not isinstance(payload, dict):
        raise FleetStatusIngestionError("persisted observation must be an object")
    payload = dict(payload)
    items = payload.get("value_items")
    if not isinstance(items, list):
        raise FleetStatusIngestionError("persisted observation value_items invalid")
    try:
        payload["value_items"] = tuple((str(item[0]), str(item[1])) for item in items if isinstance(item, list) and len(item) == 2)
    except (TypeError, IndexError) as exc:
        raise FleetStatusIngestionError("persisted observation value_items invalid") from exc
    if len(payload["value_items"]) != len(items):
        raise FleetStatusIngestionError("persisted observation value_items invalid")
    try:
        return StatusSourceObservation(**payload).validate()
    except Exception as exc:
        raise FleetStatusIngestionError("persisted observation contract validation failed") from exc


def _persisted(rows: Iterable[dict[str, object]]) -> tuple[PersistedSourceObservation, ...]:
    result: list[PersistedSourceObservation] = []
    for row in rows:
        identity = StatusSourceIdentity(
            str(row["source_id"]),
            str(row["source_kind"]),
            str(row["source_instance_id"]),
            str(row["source_implementation_digest"]),
            str(row["trust_anchor_id"]),
        ).validate()
        result.append(PersistedSourceObservation(
            source_identity=identity,
            source_sequence=int(row["source_sequence"]),
            source_observed_at=str(row["source_observed_at"]),
            ingested_at=str(row["ingested_at"]),
            batch_digest=str(row["batch_digest"]),
            source_chain_digest=str(row["source_chain_digest"]),
            observation=_observation_from_json(str(row["observation_json"])),
        ).validate())
    return tuple(result)


def _synthetic_conflict(
    kind: str,
    mission_id: str,
    dimension: str,
    facts: tuple[ReconciledStatusFact, ...],
    observed_at: str,
    *,
    drone_id: str | None = None,
) -> SourceConflict:
    source_ids = tuple(sorted({source for fact in facts for source in fact.source_ids}))
    evidence_refs = tuple(sorted({ref for fact in facts for ref in fact.evidence_refs}))
    if not source_ids:
        raise FleetStatusIngestionError("synthetic source conflict requires source evidence")
    raw = f"{kind}|{mission_id}|{dimension}|{'|'.join(source_ids)}|{'|'.join(evidence_refs)}"
    return SourceConflict(
        conflict_id=sha256(raw.encode()).hexdigest(),
        conflict_type=kind,
        mission_id=mission_id,
        drone_id=drone_id,
        dimension=dimension,
        source_ids=source_ids,
        observation_ids=(),
        evidence_refs=evidence_refs,
        observed_at=observed_at,
    ).validate()


class FleetStatusIngestion:
    """Fixed-adapter source ingestion. Status writes cannot grant operational authority."""

    def __init__(
        self,
        store: FleetStatusStore,
        *,
        adapters: tuple[ReadOnlyStatusSource, ...],
        trust_registry: StatusSourceTrustRegistry,
        reconciler: StatusSourceReconciler,
        clock: Callable[[], datetime],
    ) -> None:
        if not isinstance(store, FleetStatusStore):
            raise FleetStatusIngestionError("exact FleetStatusStore required")
        if type(adapters) is not tuple:
            raise FleetStatusIngestionError("adapters must be a fixed tuple")
        if not isinstance(trust_registry, StatusSourceTrustRegistry):
            raise FleetStatusIngestionError("trust registry required")
        if not isinstance(reconciler, StatusSourceReconciler):
            raise FleetStatusIngestionError("source reconciler required")
        identities: list[StatusSourceIdentity] = []
        for adapter in adapters:
            if not hasattr(adapter, "source_identity") or not callable(getattr(adapter, "read", None)):
                raise FleetStatusIngestionError("adapter must expose only a readable status-source capability")
            identity = adapter.source_identity
            trust_registry.admit(identity)
            identities.append(identity)
        ids = [item.source_id for item in identities]
        if len(ids) != len(set(ids)):
            raise FleetStatusIngestionError("duplicate configured source_id")
        self._store = store
        self._adapters = adapters
        self._trust = trust_registry
        self._reconciler = reconciler
        self._clock = clock
        self._configured_identities = tuple(identities)

    @property
    def source_ids(self) -> tuple[str, ...]:
        return tuple(sorted(item.source_id for item in self._configured_identities))

    def _read_all(self) -> tuple[StatusSourceRead, ...]:
        reads: list[StatusSourceRead] = []
        for adapter in self._adapters:
            expected = self._trust.admit(adapter.source_identity)
            try:
                read = adapter.read()
            except Exception as exc:
                raise FleetStatusIngestionError("status source read failed closed") from exc
            if type(read) is not StatusSourceRead:
                raise FleetStatusIngestionError("adapter returned wrong source read type")
            read.validate()
            self._trust.admit(read.source_identity)
            if read.source_identity != expected:
                raise FleetStatusIngestionError("adapter/read source identity substitution denied")
            reads.append(read)
        return tuple(reads)

    def _missing(
        self,
        facts: tuple[ReconciledStatusFact, ...],
        conflicts: tuple[SourceConflict, ...],
        observed_at: str,
    ) -> tuple[MissingStatusSource, ...]:
        by_fact = {(item.mission_id, item.dimension) for item in facts}
        by_conflict = {(item.mission_id, item.dimension) for item in conflicts if item.mission_id is not None}
        identity_by_mission = {item.mission_id: item for item in facts if item.dimension == "IDENTITY"}
        missions = {item.mission_id for item in facts}
        for row in self._store.source_observation_rows():
            payload = json.loads(str(row["observation_json"]))
            mission_id = payload.get("mission_id")
            if isinstance(mission_id, str) and mission_id:
                missions.add(mission_id)
        reader = self._store.open_query_reader()
        try:
            missions.update(str(row[0]) for row in reader.execute("SELECT mission_id FROM fleet_identity"))
        finally:
            reader.close()
        missing: list[MissingStatusSource] = []
        for mission_id in sorted(missions):
            identity = identity_by_mission.get(mission_id)
            drone_id = identity.value_dict().get("drone_id") if identity else None
            if drone_id is None:
                row = self._store.identity_row(mission_id)
                drone_id = str(row["drone_id"]) if row else None
            for dimension, owner_kinds in PRIMARY_OWNERS.items():
                key = (mission_id, dimension)
                if key in by_fact or key in by_conflict:
                    continue
                missing.append(MissingStatusSource(
                    mission_id=mission_id,
                    drone_id=drone_id,
                    dimension=dimension,
                    expected_source_kinds=tuple(owner_kinds),
                    observed_at=observed_at,
                ).validate())
        return tuple(sorted(missing, key=lambda item: (item.mission_id, item.dimension)))

    @staticmethod
    def _blocked(conflicts: tuple[SourceConflict, ...]) -> set[tuple[str, str]]:
        return {
            (item.mission_id, item.dimension)
            for item in conflicts
            if item.mission_id is not None
        }

    def _identity_runtime_conflicts(
        self,
        facts: tuple[ReconciledStatusFact, ...],
        conflicts: tuple[SourceConflict, ...],
        observed_at: str,
    ) -> tuple[SourceConflict, ...]:
        result = list(conflicts)
        by_key = {(fact.mission_id, fact.dimension): fact for fact in facts}
        blocked = self._blocked(conflicts)
        for mission_id in sorted({fact.mission_id for fact in facts}):
            identity = by_key.get((mission_id, "IDENTITY"))
            runtime = by_key.get((mission_id, "RUNTIME"))
            repository = by_key.get((mission_id, "REPOSITORY"))
            if identity is None or runtime is None or repository is None:
                continue
            if any((mission_id, dimension) in blocked for dimension in ("IDENTITY", "RUNTIME", "REPOSITORY")):
                continue
            iv = identity.value_dict()
            rv = runtime.value_dict()
            gv = repository.value_dict()
            try:
                candidate = FleetStatusIdentity(
                    drone_id=iv["drone_id"],
                    executor_id=rv["executor_id"],
                    mission_id=mission_id,
                    parent_mission_id=iv["parent_mission_id"],
                    repository=iv["repository"],
                    baseline_sha=_sha40(iv.get("baseline_sha"), "identity baseline_sha"),
                    baseline_tree_sha=_sha40(gv.get("baseline_tree_sha"), "repository baseline_tree_sha"),
                    branch=iv["branch"],
                    read_scope=_scope(iv["read_scope"], "read_scope"),
                    write_scope=_scope(iv["write_scope"], "write_scope"),
                    sandbox_id=iv["sandbox_id"],
                ).validate()
            except (KeyError, Exception) as exc:
                if isinstance(exc, FleetStatusIngestionError):
                    raise
                raise FleetStatusIngestionError("canonical identity assembly failed") from exc
            existing = self._store.identity_row(mission_id)
            if existing is not None:
                old = FleetStatusIdentity(
                    str(existing["drone_id"]), str(existing["executor_id"]), str(existing["mission_id"]),
                    str(existing["parent_mission_id"]), str(existing["repository"]), str(existing["baseline_sha"]),
                    str(existing["baseline_tree_sha"]), str(existing["branch"]),
                    tuple(json.loads(str(existing["read_scope_json"]))),
                    tuple(json.loads(str(existing["write_scope_json"]))), str(existing["sandbox_id"]),
                ).validate()
                if old != candidate:
                    result.append(_synthetic_conflict(
                        "CANONICAL_IDENTITY_SUBSTITUTION", mission_id, "IDENTITY",
                        (identity, runtime, repository), observed_at, drone_id=candidate.drone_id,
                    ))
            runtime_row = self._store.runtime_row(mission_id)
            runtime_id = rv.get("runtime_id")
            if runtime_row is not None and runtime_id != runtime_row["runtime_id"]:
                result.append(_synthetic_conflict(
                    "RUNTIME_SUBSTITUTION", mission_id, "RUNTIME", (runtime,), observed_at,
                    drone_id=candidate.drone_id,
                ))
        unique = {item.conflict_id: item for item in result}
        return tuple(sorted(unique.values(), key=lambda item: item.conflict_id))

    def _apply_safe_facts(
        self,
        facts: tuple[ReconciledStatusFact, ...],
        conflicts: tuple[SourceConflict, ...],
        missing: tuple[MissingStatusSource, ...],
    ) -> None:
        by_key = {(fact.mission_id, fact.dimension): fact for fact in facts}
        blocked = self._blocked(conflicts)
        missing_keys = {(item.mission_id, item.dimension) for item in missing}

        # Immutable identity is assembled only from complete FCP + verified runtime + repository-baseline evidence.
        for mission_id in sorted({fact.mission_id for fact in facts}):
            identity = by_key.get((mission_id, "IDENTITY"))
            runtime = by_key.get((mission_id, "RUNTIME"))
            repository = by_key.get((mission_id, "REPOSITORY"))
            required = {"IDENTITY": identity, "RUNTIME": runtime, "REPOSITORY": repository}
            if any(value is None for value in required.values()):
                continue
            if any((mission_id, dim) in blocked or (mission_id, dim) in missing_keys for dim in required):
                continue
            assert identity is not None and runtime is not None and repository is not None
            iv, rv, gv = identity.value_dict(), runtime.value_dict(), repository.value_dict()
            if iv.get("repository") != rv.get("repository") or iv.get("repository") != gv.get("repository"):
                continue
            if iv.get("baseline_sha") != gv.get("baseline_sha") or iv.get("branch") != gv.get("branch"):
                continue
            candidate = FleetStatusIdentity(
                iv["drone_id"], rv["executor_id"], mission_id, iv["parent_mission_id"], iv["repository"],
                _sha40(iv.get("baseline_sha"), "baseline_sha"),
                _sha40(gv.get("baseline_tree_sha"), "baseline_tree_sha"),
                iv["branch"], _scope(iv["read_scope"], "read_scope"), _scope(iv["write_scope"], "write_scope"),
                iv["sandbox_id"],
            ).validate()
            existing = self._store.identity_row(mission_id)
            if existing is None:
                self._store.register_identity(candidate)
            runtime_row = self._store.runtime_row(mission_id)
            runtime_id = rv["runtime_id"]
            if runtime_row is None:
                self._store.bind_runtime(mission_id, runtime_id, runtime.evidence_refs[0])

        # Verification is resolved again by the store's fixed trusted verifier source.
        for fact in facts:
            if fact.dimension != "VERIFICATION" or (fact.mission_id, "VERIFICATION") in blocked:
                continue
            if self._store.identity_row(fact.mission_id) is None:
                continue
            verification_id = fact.value_dict().get("verification_id")
            if verification_id:
                try:
                    self._store.project_verification(verification_id)
                except Exception as exc:
                    raise FleetStatusIngestionError("trusted verification projection failed closed") from exc

        # Mission operational state stays distinct from verification/effect/reconciliation.
        for fact in facts:
            if fact.dimension != "MISSION" or (fact.mission_id, "MISSION") in blocked:
                continue
            if self._store.identity_row(fact.mission_id) is None:
                continue
            values = fact.value_dict()
            phase = values.get("phase", "UNKNOWN")
            closure = values.get("closure_state", "OPEN")
            dependency = values.get("dependency_state", "UNKNOWN")
            repo = by_key.get((fact.mission_id, "REPOSITORY"))
            branch_head = repo.value_dict().get("branch_head_sha") if repo else None
            if fact.state == "DONE":
                blocking_types = {
                    item.conflict_type for item in conflicts if item.mission_id == fact.mission_id
                }
                if blocking_types.intersection({"DONE_WITHOUT_VERIFICATION", "DONE_WITH_UNRECONCILED_EFFECT"}):
                    continue
                try:
                    self._store.mark_verified_done(
                        fact.mission_id, phase=phase, branch_head=branch_head,
                        dependency_state=dependency,
                    )
                except FleetStatusStateError as exc:
                    raise FleetStatusIngestionError("DONE projection failed closed") from exc
            else:
                if closure == "CLOSED":
                    continue
                try:
                    self._store.set_mission_state(
                        fact.mission_id, phase=phase, status=fact.state, closure_state=closure,
                        dependency_state=dependency, branch_head=branch_head,
                    )
                except FleetStatusStateError as exc:
                    raise FleetStatusIngestionError("mission state projection failed closed") from exc

        for fact in facts:
            mapping = {
                "AUTHORITY": "authority",
                "SANDBOX": "sandbox",
                "EFFECT": "effect",
                "RECONCILIATION": "reconciliation",
            }
            kind = mapping.get(fact.dimension)
            if kind is None or (fact.mission_id, fact.dimension) in blocked:
                continue
            if self._store.identity_row(fact.mission_id) is None or fact.state == "UNKNOWN":
                continue
            try:
                self._store.project_observed_state(
                    fact.mission_id, kind=kind, state=fact.state,
                    source_ref=fact.evidence_refs[0],
                )
            except FleetStatusStateError as exc:
                raise FleetStatusIngestionError(f"{fact.dimension} projection failed closed") from exc

        for fact in facts:
            if fact.dimension != "LEASE" or (fact.mission_id, "LEASE") in blocked:
                continue
            if self._store.identity_row(fact.mission_id) is None or fact.state == "UNKNOWN":
                continue
            values = fact.value_dict()
            required = ("lease_id", "lease_type", "resource")
            if any(not values.get(key) for key in required):
                raise FleetStatusIngestionError("lease fact is incomplete")
            try:
                self._store.record_lease(
                    fact.mission_id, lease_id=values["lease_id"], lease_type=values["lease_type"],
                    resource=values["resource"], state=fact.state, source_ref=fact.evidence_refs[0],
                )
            except FleetStatusStateError as exc:
                raise FleetStatusIngestionError("lease projection failed closed") from exc

        for fact in facts:
            if fact.dimension != "RECEIPT" or (fact.mission_id, "RECEIPT") in blocked:
                continue
            if self._store.identity_row(fact.mission_id) is None:
                continue
            receipt_id = fact.value_dict().get("receipt_id")
            if not receipt_id:
                raise FleetStatusIngestionError("receipt fact is incomplete")
            if not self._store.has_receipt(receipt_id):
                try:
                    self._store.append_receipt(
                        fact.mission_id, receipt_id=receipt_id, source_ref=fact.evidence_refs[0]
                    )
                except FleetStatusStateError as exc:
                    raise FleetStatusIngestionError("receipt projection failed closed") from exc

    def run_cycle(self) -> IngestionCycleResult:
        observed_at = _now(self._clock)
        reads = self._read_all()  # provider failures occur before any source-journal write
        for read in reads:
            try:
                self._store.ingest_source_read(read)
            except Exception as exc:
                raise FleetStatusIngestionError("source journal ingestion failed closed") from exc
        try:
            self._store.verify_source_chains()
            rows = _persisted(self._store.source_observation_rows(current_only=True))
            facts, conflicts = self._reconciler.reconcile(rows, observed_at=observed_at)
            global_conflicts = self._reconciler.detect_global_conflicts(facts, observed_at=observed_at)
            conflicts = tuple(sorted({item.conflict_id: item for item in conflicts + global_conflicts}.values(), key=lambda item: item.conflict_id))
            conflicts = self._identity_runtime_conflicts(facts, conflicts, observed_at)
            missing = self._missing(facts, conflicts, observed_at)
            self._store.record_source_decisions(facts, conflicts, missing)
            self._apply_safe_facts(facts, conflicts, missing)
        except FleetStatusIngestionError:
            raise
        except Exception as exc:
            raise FleetStatusIngestionError("source reconciliation/projection failed closed") from exc
        return IngestionCycleResult(facts, conflicts, missing, self.source_ids)
