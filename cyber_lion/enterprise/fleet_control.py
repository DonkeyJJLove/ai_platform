"""Deterministic fleet-control primitives for bounded software-factory experiments.

This module is a control-plane slice, not an executor. Scale promotion is accepted only
through an injected trusted evidence verifier. Parent authority is resolved externally.
Scheduler state and leases persist across planning cycles.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import PurePosixPath
from typing import Dict, Iterable, Mapping, Protocol, Tuple

from .models import EnterpriseModelError, authority_rank


class FleetException(EnterpriseModelError):
    """Raised when a fleet invariant fails closed."""


DRONE_STATES = {
    "STARTING", "RUNNING", "WAITING", "BLOCKED",
    "DEGRADED", "FAILED", "DONE", "TERMINATED",
}
SCALE_LEVELS = (1, 2, 5, 10, 25, 50, 100)
PROMOTION_EPISTEMIC_CLASSES = {"OBSERVED", "ANCHORED"}
TERMINAL_STATES = {"FAILED", "DONE", "TERMINATED"}


def _require_text(value: str, field: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise FleetException(f"{field} is required")


def _validate_scope(scope: Tuple[str, ...], field: str) -> None:
    if not isinstance(scope, tuple) or not scope:
        raise FleetException(f"{field} must be a non-empty tuple")
    if len(set(scope)) != len(scope):
        raise FleetException(f"{field} entries must be unique")
    for raw in scope:
        _require_text(raw, field)
        if "\\" in raw:
            raise FleetException(f"{field} must use repository-relative POSIX paths")
        path = PurePosixPath(raw)
        if path.is_absolute() or ".." in path.parts or str(path) in {"", "."}:
            raise FleetException(f"{field} contains unsafe path: {raw!r}")


def _path_overlap(left: str, right: str) -> bool:
    a = PurePosixPath(left).parts
    b = PurePosixPath(right).parts
    shared = min(len(a), len(b))
    return a[:shared] == b[:shared]


@dataclass(frozen=True)
class DroneSpec:
    """Immutable exact binding for one coding drone."""

    drone_id: str
    mission_id: str
    parent_mission_id: str
    repository: str
    baseline_sha: str
    branch: str
    workspace: str
    sandbox_id: str
    authority_ceiling: str
    write_scope: Tuple[str, ...]
    read_scope: Tuple[str, ...]
    test_scope: Tuple[str, ...]
    resource_budget: Tuple[Tuple[str, float], ...]
    dependencies: Tuple[str, ...] = ()
    evidence_refs: Tuple[str, ...] = ()

    def validate(self) -> "DroneSpec":
        for field_name in (
            "drone_id", "mission_id", "parent_mission_id", "repository",
            "baseline_sha", "branch", "workspace", "sandbox_id",
        ):
            _require_text(getattr(self, field_name), field_name)
        authority_rank(self.authority_ceiling)
        if self.branch.startswith("refs/"):
            raise FleetException("branch must be a repository branch name, not a ref path")
        if len(self.baseline_sha) != 40 or any(
            ch not in "0123456789abcdef" for ch in self.baseline_sha.lower()
        ):
            raise FleetException("baseline_sha must be a full 40-character hex SHA")
        _validate_scope(self.write_scope, "write_scope")
        _validate_scope(self.read_scope, "read_scope")
        _validate_scope(self.test_scope, "test_scope")
        if not isinstance(self.dependencies, tuple) or len(set(self.dependencies)) != len(self.dependencies):
            raise FleetException("dependencies must be a unique tuple")
        if self.mission_id in self.dependencies:
            raise FleetException("mission cannot depend on itself")
        if not isinstance(self.evidence_refs, tuple) or not self.evidence_refs:
            raise FleetException("drone contract requires evidence_refs")
        if not isinstance(self.resource_budget, tuple) or not self.resource_budget:
            raise FleetException("resource_budget must be a non-empty tuple")
        keys = [key for key, _ in self.resource_budget]
        if len(set(keys)) != len(keys):
            raise FleetException("resource_budget keys must be unique")
        for key, value in self.resource_budget:
            _require_text(key, "resource_budget key")
            if not isinstance(value, (int, float)) or value < 0:
                raise FleetException("resource_budget values must be non-negative numbers")
        return self


@dataclass(frozen=True)
class ParentAuthorityAdmission:
    mission_id: str
    parent_mission_id: str
    repository: str
    baseline_sha: str
    authority_ceiling: str
    grant_digest: str

    def validate_for(self, drone: DroneSpec) -> "ParentAuthorityAdmission":
        drone.validate()
        for value, field in (
            (self.mission_id, "mission_id"),
            (self.parent_mission_id, "parent_mission_id"),
            (self.repository, "repository"),
            (self.baseline_sha, "baseline_sha"),
            (self.grant_digest, "grant_digest"),
        ):
            _require_text(value, field)
        authority_rank(self.authority_ceiling)
        if (
            self.mission_id != drone.mission_id
            or self.parent_mission_id != drone.parent_mission_id
            or self.repository != drone.repository
            or self.baseline_sha != drone.baseline_sha
        ):
            raise FleetException("parent authority admission binding mismatch")
        if authority_rank(drone.authority_ceiling) > authority_rank(self.authority_ceiling):
            raise FleetException("child authority exceeds trusted parent admission")
        return self


class ParentAuthoritySource(Protocol):
    def resolve_parent_authority(self, drone: DroneSpec) -> ParentAuthorityAdmission:
        ...


@dataclass(frozen=True)
class FleetCapabilitySnapshot:
    """Untrusted claim bundle; never sufficient for scale promotion by itself."""

    epistemic_class: str
    executor_ids: Tuple[str, ...]
    sandbox_ids: Tuple[str, ...]
    process_fanout: int
    sandbox_isolation_verified: bool
    authority_isolation_verified: bool
    branch_ownership_verified: bool
    path_ownership_verified: bool
    mission_identity_verified: bool
    evidence_complete: bool
    scheduler_stability_verified: bool
    no_unexplained_mutation_verified: bool
    bounded_retries_verified: bool
    duplicate_execution_control_verified: bool
    deadlock_control_verified: bool
    ci_pressure_acceptable: bool
    resource_pressure_acceptable: bool
    observability_verified: bool
    replay_verified: bool
    adversarial_suite_verified: bool = False
    sustained_operation_verified: bool = False
    evidence_refs: Tuple[str, ...] = ()

    def validate(self) -> "FleetCapabilitySnapshot":
        if self.epistemic_class not in {"OBSERVED", "ANCHORED", "INFERRED", "SIMULATED"}:
            raise FleetException("invalid capability epistemic_class")
        if self.process_fanout < 1:
            raise FleetException("process_fanout must be positive")
        for values, field in (
            (self.executor_ids, "executor_ids"),
            (self.sandbox_ids, "sandbox_ids"),
            (self.evidence_refs, "evidence_refs"),
        ):
            if not isinstance(values, tuple) or not values:
                raise FleetException(f"{field} must be a non-empty tuple")
            if len(set(values)) != len(values) or any(not item for item in values):
                raise FleetException(f"{field} must contain unique non-empty values")
        return self

    def digest(self) -> str:
        self.validate()
        payload = {
            "epistemic_class": self.epistemic_class,
            "executor_ids": self.executor_ids,
            "sandbox_ids": self.sandbox_ids,
            "process_fanout": self.process_fanout,
            "sandbox_isolation_verified": self.sandbox_isolation_verified,
            "authority_isolation_verified": self.authority_isolation_verified,
            "branch_ownership_verified": self.branch_ownership_verified,
            "path_ownership_verified": self.path_ownership_verified,
            "mission_identity_verified": self.mission_identity_verified,
            "evidence_complete": self.evidence_complete,
            "scheduler_stability_verified": self.scheduler_stability_verified,
            "no_unexplained_mutation_verified": self.no_unexplained_mutation_verified,
            "bounded_retries_verified": self.bounded_retries_verified,
            "duplicate_execution_control_verified": self.duplicate_execution_control_verified,
            "deadlock_control_verified": self.deadlock_control_verified,
            "ci_pressure_acceptable": self.ci_pressure_acceptable,
            "resource_pressure_acceptable": self.resource_pressure_acceptable,
            "observability_verified": self.observability_verified,
            "replay_verified": self.replay_verified,
            "adversarial_suite_verified": self.adversarial_suite_verified,
            "sustained_operation_verified": self.sustained_operation_verified,
            "evidence_refs": self.evidence_refs,
        }
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        return sha256(raw).hexdigest()


@dataclass(frozen=True)
class VerifiedFleetCapability:
    snapshot_digest: str
    verified_concurrency: int
    executor_ids: Tuple[str, ...]
    sandbox_ids: Tuple[str, ...]
    epistemic_class: str
    gates_passed: bool
    adversarial_suite_verified: bool
    sustained_operation_verified: bool
    verifier_id: str
    evidence_refs: Tuple[str, ...]

    def validate_for(
        self,
        snapshot: FleetCapabilitySnapshot,
        requested_concurrency: int,
    ) -> "VerifiedFleetCapability":
        snapshot.validate()
        if self.snapshot_digest != snapshot.digest():
            raise FleetException("verified capability does not bind exact snapshot digest")
        if self.verified_concurrency < requested_concurrency:
            raise FleetException("trusted verifier did not verify requested concurrency")
        if self.executor_ids != snapshot.executor_ids or self.sandbox_ids != snapshot.sandbox_ids:
            raise FleetException("trusted verifier executor/sandbox binding mismatch")
        if self.epistemic_class not in PROMOTION_EPISTEMIC_CLASSES:
            raise FleetException("trusted scale evidence must be OBSERVED or ANCHORED")
        if len(self.executor_ids) < requested_concurrency or len(self.sandbox_ids) < requested_concurrency:
            raise FleetException("trusted evidence lacks independent executor/sandbox capacity")
        if not self.gates_passed:
            raise FleetException("trusted fleet scale gates did not pass")
        _require_text(self.verifier_id, "verifier_id")
        if not self.evidence_refs:
            raise FleetException("verified capability requires evidence_refs")
        return self


class FleetEvidenceVerifier(Protocol):
    def verify(
        self,
        snapshot: FleetCapabilitySnapshot,
        requested_concurrency: int,
    ) -> VerifiedFleetCapability:
        ...


@dataclass(frozen=True)
class ScaleAdmission:
    requested_concurrency: int
    admitted: bool
    scientific_level: str
    rationale: str
    verification_digest: str | None = None


class FleetAdmissionGate:
    """Scale gate that trusts only an injected verifier boundary, never raw claims."""

    def __init__(self, verifier: FleetEvidenceVerifier) -> None:
        self._verifier = verifier

    def evaluate(self, snapshot: FleetCapabilitySnapshot, requested_concurrency: int) -> ScaleAdmission:
        snapshot.validate()
        if requested_concurrency not in SCALE_LEVELS:
            raise FleetException(f"unsupported scale level: {requested_concurrency}")
        if requested_concurrency == 1:
            if not snapshot.executor_ids or not snapshot.sandbox_ids:
                return ScaleAdmission(1, False, "L0", "no demonstrated executor+sandbox pair")
            return ScaleAdmission(1, True, "L1", "single executor context demonstrated")

        verified = self._verifier.verify(snapshot, requested_concurrency)
        if not isinstance(verified, VerifiedFleetCapability):
            raise FleetException("trusted verifier returned invalid capability evidence")
        verified.validate_for(snapshot, requested_concurrency)

        if requested_concurrency == 100 and not verified.adversarial_suite_verified:
            return ScaleAdmission(100, False, "L3", "100-way admission requires adversarial suite evidence")
        if requested_concurrency == 100:
            level = "L5" if verified.sustained_operation_verified else "L4"
        elif requested_concurrency >= 25:
            level = "L3"
        else:
            level = "L2"
        return ScaleAdmission(
            requested_concurrency,
            True,
            level,
            "trusted evidence verified all required scale gates",
            verification_digest=verified.snapshot_digest,
        )


@dataclass(frozen=True)
class VerifierBinding:
    mission_id: str
    verifier_id: str
    evidence_ref: str

    def validate(self) -> "VerifierBinding":
        _require_text(self.mission_id, "mission_id")
        _require_text(self.verifier_id, "verifier_id")
        _require_text(self.evidence_ref, "evidence_ref")
        return self


class MissionRegistry:
    """Persistent mission state with trusted parent-authority and verifier bindings."""

    def __init__(self, authority_source: ParentAuthoritySource) -> None:
        self._authority_source = authority_source
        self._drones: Dict[str, DroneSpec] = {}
        self._state: Dict[str, str] = {}
        self._heartbeat: Dict[str, int] = {}
        self._verifiers: Dict[str, Dict[str, VerifierBinding]] = {}

    def register(self, drone: DroneSpec) -> None:
        drone.validate()
        if drone.mission_id in self._drones:
            raise FleetException(f"duplicate mission dispatch: {drone.mission_id}")
        if any(existing.drone_id == drone.drone_id for existing in self._drones.values()):
            raise FleetException(f"duplicate drone identity: {drone.drone_id}")
        admission = self._authority_source.resolve_parent_authority(drone)
        if not isinstance(admission, ParentAuthorityAdmission):
            raise FleetException("authority source returned invalid admission")
        admission.validate_for(drone)
        self._drones[drone.mission_id] = drone
        self._state[drone.mission_id] = "STARTING"
        self._heartbeat[drone.mission_id] = 0

    def register_verifier(self, binding: VerifierBinding) -> None:
        binding.validate()
        self._require_mission(binding.mission_id)
        drone = self._drones[binding.mission_id]
        if binding.verifier_id == drone.drone_id:
            raise FleetException("builder cannot be registered as independent verifier")
        existing = self._verifiers.setdefault(binding.mission_id, {})
        if binding.verifier_id in existing:
            raise FleetException("duplicate verifier binding")
        existing[binding.verifier_id] = binding

    def set_state(self, mission_id: str, state: str) -> None:
        self._require_mission(mission_id)
        if state not in DRONE_STATES:
            raise FleetException(f"invalid mission state: {state}")
        if self._state[mission_id] == "TERMINATED" and state != "TERMINATED":
            raise FleetException("terminated mission cannot transition")
        self._state[mission_id] = state

    def heartbeat(self, mission_id: str, sequence: int) -> None:
        self._require_mission(mission_id)
        if self._state[mission_id] == "TERMINATED":
            raise FleetException("terminated mission cannot heartbeat")
        if not isinstance(sequence, int) or sequence <= self._heartbeat[mission_id]:
            raise FleetException("heartbeat sequence must increase monotonically")
        self._heartbeat[mission_id] = sequence

    def authorize_request(self, mission_id: str, drone_id: str, requested_authority: str) -> None:
        self._require_mission(mission_id)
        drone = self._drones[mission_id]
        if drone.drone_id != drone_id:
            raise FleetException("cross-mission/drone authority request denied")
        admission = self._authority_source.resolve_parent_authority(drone)
        admission.validate_for(drone)
        if authority_rank(requested_authority) > authority_rank(drone.authority_ceiling):
            raise FleetException("requested authority exceeds drone authority ceiling")
        if authority_rank(requested_authority) > authority_rank(admission.authority_ceiling):
            raise FleetException("requested authority exceeds trusted parent admission")

    def report_result(
        self,
        mission_id: str,
        *,
        outcome: str,
        evidence_refs: Tuple[str, ...],
        verifier_id: str | None = None,
    ) -> None:
        self._require_mission(mission_id)
        if self._state[mission_id] == "TERMINATED":
            raise FleetException("late result from terminated mission denied")
        if self._heartbeat[mission_id] <= 0:
            raise FleetException("result denied without heartbeat evidence")
        if not isinstance(evidence_refs, tuple) or not evidence_refs:
            raise FleetException("result requires evidence_refs")
        if outcome not in {"SUCCEEDED", "FAILED", "ABORTED"}:
            raise FleetException("invalid result outcome")
        if outcome == "SUCCEEDED":
            if not verifier_id:
                raise FleetException("successful result requires independent verifier")
            binding = self._verifiers.get(mission_id, {}).get(verifier_id)
            if binding is None:
                raise FleetException("successful result requires registered mission verifier")
            if binding.evidence_ref not in evidence_refs:
                raise FleetException("result evidence is not bound to registered verifier")
            self._state[mission_id] = "DONE"
        elif outcome == "FAILED":
            self._state[mission_id] = "FAILED"
        else:
            self._state[mission_id] = "TERMINATED"

    def terminate(self, mission_id: str) -> None:
        self._require_mission(mission_id)
        self._state[mission_id] = "TERMINATED"

    def spec(self, mission_id: str) -> DroneSpec:
        self._require_mission(mission_id)
        return self._drones[mission_id]

    def state(self, mission_id: str) -> str:
        self._require_mission(mission_id)
        return self._state[mission_id]

    def mission_ids(self) -> Tuple[str, ...]:
        return tuple(sorted(self._drones))

    def snapshot(self) -> Tuple[Tuple[str, str, int], ...]:
        return tuple(
            sorted(
                (mission_id, self._state[mission_id], self._heartbeat[mission_id])
                for mission_id in self._drones
            )
        )

    def _require_mission(self, mission_id: str) -> None:
        if mission_id not in self._drones:
            raise FleetException(f"unknown mission: {mission_id}")


class DependencyGraph:
    """Dynamic mission DAG with cycle rejection."""

    def __init__(self) -> None:
        self._deps: Dict[str, frozenset[str]] = {}

    def add_mission(self, mission_id: str, dependencies: Iterable[str] = ()) -> None:
        _require_text(mission_id, "mission_id")
        if mission_id in self._deps:
            raise FleetException(f"duplicate dependency node: {mission_id}")
        deps = frozenset(dependencies)
        if mission_id in deps:
            raise FleetException("mission cannot depend on itself")
        candidate = dict(self._deps)
        candidate[mission_id] = deps
        if self._has_cycle(candidate):
            raise FleetException("dependency cycle detected")
        self._deps = candidate

    def ready(self, completed_missions: Iterable[str]) -> Tuple[str, ...]:
        completed = frozenset(completed_missions)
        return tuple(
            sorted(
                mission_id
                for mission_id, deps in self._deps.items()
                if mission_id not in completed and deps.issubset(completed)
            )
        )

    @staticmethod
    def _has_cycle(graph: Mapping[str, frozenset[str]]) -> bool:
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(node: str) -> bool:
            if node in visited:
                return False
            if node in visiting:
                return True
            visiting.add(node)
            for dependency in graph.get(node, frozenset()):
                if dependency in graph and visit(dependency):
                    return True
            visiting.remove(node)
            visited.add(node)
            return False

        return any(visit(node) for node in graph)


class LeaseRegistry:
    """Persistent repository coordination plus exclusive branch/path write leases."""

    def __init__(self) -> None:
        self._repository_leases: Dict[str, set[str]] = {}
        self._branch_leases: Dict[Tuple[str, str], str] = {}
        self._path_leases: Dict[Tuple[str, str], str] = {}

    def claim(self, drone: DroneSpec) -> None:
        drone.validate()
        branch_key = (drone.repository, drone.branch)
        owner = self._branch_leases.get(branch_key)
        if owner and owner != drone.drone_id:
            raise FleetException("branch lease conflict")
        for path in drone.write_scope:
            for (repository, leased_path), existing_owner in self._path_leases.items():
                if (
                    repository == drone.repository
                    and existing_owner != drone.drone_id
                    and _path_overlap(path, leased_path)
                ):
                    raise FleetException(f"path lease conflict: {path} overlaps {leased_path}")
        self._repository_leases.setdefault(drone.repository, set()).add(drone.drone_id)
        self._branch_leases[branch_key] = drone.drone_id
        for path in drone.write_scope:
            self._path_leases[(drone.repository, path)] = drone.drone_id

    def release(self, drone_id: str) -> None:
        for repository in list(self._repository_leases):
            owners = self._repository_leases[repository]
            owners.discard(drone_id)
            if not owners:
                del self._repository_leases[repository]
        self._branch_leases = {
            key: owner for key, owner in self._branch_leases.items() if owner != drone_id
        }
        self._path_leases = {
            key: owner for key, owner in self._path_leases.items() if owner != drone_id
        }

    def snapshot(self) -> Tuple[Tuple[str, str, str], ...]:
        rows = [
            ("repo", repository, drone_id)
            for repository, owners in self._repository_leases.items()
            for drone_id in owners
        ]
        rows.extend(
            ("branch", f"{repository}:{branch}", owner)
            for (repository, branch), owner in self._branch_leases.items()
        )
        rows.extend(
            ("path", f"{repository}:{path}", owner)
            for (repository, path), owner in self._path_leases.items()
        )
        return tuple(sorted(rows))


class FleetScheduler:
    """Persistent scheduler over MissionRegistry and LeaseRegistry."""

    def __init__(self, registry: MissionRegistry, leases: LeaseRegistry) -> None:
        self._registry = registry
        self._leases = leases

    def plan(
        self,
        *,
        current_heads: Mapping[str, str],
        max_parallel: int = 1,
    ) -> Tuple[str, ...]:
        if not isinstance(max_parallel, int) or max_parallel <= 0 or max_parallel > 100:
            raise FleetException("max_parallel must be in [1,100]")

        self._release_terminal_leases()
        graph = DependencyGraph()
        completed = {
            mission_id
            for mission_id in self._registry.mission_ids()
            if self._registry.state(mission_id) == "DONE"
        }
        for mission_id in self._registry.mission_ids():
            spec = self._registry.spec(mission_id)
            if current_heads.get(spec.repository) != spec.baseline_sha:
                raise FleetException(f"stale baseline: {spec.repository}:{mission_id}")
            graph.add_mission(mission_id, spec.dependencies)

        selected: list[str] = []
        for mission_id in graph.ready(completed):
            if len(selected) >= max_parallel:
                break
            if self._registry.state(mission_id) not in {"STARTING", "WAITING"}:
                continue
            spec = self._registry.spec(mission_id)
            try:
                self._leases.claim(spec)
            except FleetException as exc:
                if "lease conflict" in str(exc):
                    continue
                raise
            self._registry.set_state(mission_id, "RUNNING")
            selected.append(mission_id)
        return tuple(selected)

    def _release_terminal_leases(self) -> None:
        for mission_id in self._registry.mission_ids():
            if self._registry.state(mission_id) in TERMINAL_STATES:
                self._leases.release(self._registry.spec(mission_id).drone_id)


def deterministic_fleet_state(
    registry: MissionRegistry,
    leases: LeaseRegistry,
) -> Tuple[Tuple[str, ...], Tuple[Tuple[str, str, int], ...], Tuple[Tuple[str, str, str], ...]]:
    return (registry.mission_ids(), registry.snapshot(), leases.snapshot())
