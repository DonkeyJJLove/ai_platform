"""Deterministic fleet-control primitives for bounded software-factory experiments.

This module is deliberately a control-plane slice, not an executor. It records immutable
drone contracts, exact dependency/lease state and evidence-backed scale admission. It
never creates model contexts, sandboxes, credentials or GitHub effects by itself.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Dict, Iterable, Mapping, Sequence, Tuple

from .models import EnterpriseModelError, authority_rank


class FleetException(EnterpriseModelError):
    """Raised when a fleet invariant fails closed."""


DRONE_STATES = {
    "STARTING",
    "RUNNING",
    "WAITING",
    "BLOCKED",
    "DEGRADED",
    "FAILED",
    "DONE",
    "TERMINATED",
}
SCALE_LEVELS = (1, 2, 5, 10, 25, 50, 100)
PROMOTION_EPISTEMIC_CLASSES = {"OBSERVED", "ANCHORED"}


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
    """Immutable contract for one coding drone."""

    drone_id: str
    mission_id: str
    parent_mission_id: str
    repository: str
    baseline_sha: str
    branch: str
    workspace: str
    sandbox_id: str
    authority_ceiling: str
    parent_authority_ceiling: str
    write_scope: Tuple[str, ...]
    read_scope: Tuple[str, ...]
    test_scope: Tuple[str, ...]
    resource_budget: Tuple[Tuple[str, float], ...]
    dependencies: Tuple[str, ...] = ()
    evidence_refs: Tuple[str, ...] = ()

    def validate(self) -> "DroneSpec":
        for field_name in (
            "drone_id",
            "mission_id",
            "parent_mission_id",
            "repository",
            "baseline_sha",
            "branch",
            "workspace",
            "sandbox_id",
        ):
            _require_text(getattr(self, field_name), field_name)

        if self.branch.startswith("refs/"):
            raise FleetException("branch must be a repository branch name, not a ref path")
        if len(self.baseline_sha) != 40 or any(ch not in "0123456789abcdef" for ch in self.baseline_sha.lower()):
            raise FleetException("baseline_sha must be a full 40-character hex SHA")

        _validate_scope(self.write_scope, "write_scope")
        _validate_scope(self.read_scope, "read_scope")
        _validate_scope(self.test_scope, "test_scope")

        if not isinstance(self.dependencies, tuple) or len(set(self.dependencies)) != len(self.dependencies):
            raise FleetException("dependencies must be a unique tuple")
        if self.mission_id in self.dependencies:
            raise FleetException("mission cannot depend on itself")

        if not isinstance(self.resource_budget, tuple) or not self.resource_budget:
            raise FleetException("resource_budget must be a non-empty tuple")
        budget_keys = [key for key, _ in self.resource_budget]
        if len(set(budget_keys)) != len(budget_keys):
            raise FleetException("resource_budget keys must be unique")
        for key, value in self.resource_budget:
            _require_text(key, "resource_budget key")
            if not isinstance(value, (int, float)) or value < 0:
                raise FleetException("resource_budget values must be non-negative numbers")

        if authority_rank(self.authority_ceiling) > authority_rank(self.parent_authority_ceiling):
            raise FleetException("child authority exceeds parent authority")

        return self


@dataclass(frozen=True)
class FleetCapabilitySnapshot:
    """Evidence-bound observations used to admit a fleet scale level."""

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
        if not isinstance(self.executor_ids, tuple) or len(set(self.executor_ids)) != len(self.executor_ids):
            raise FleetException("executor_ids must be a tuple of unique identifiers")
        if not isinstance(self.sandbox_ids, tuple) or len(set(self.sandbox_ids)) != len(self.sandbox_ids):
            raise FleetException("sandbox_ids must be a tuple of unique identifiers")
        if any(not item for item in self.executor_ids + self.sandbox_ids):
            raise FleetException("executor/sandbox identifiers must be non-empty")
        if not isinstance(self.evidence_refs, tuple) or not self.evidence_refs:
            raise FleetException("capability snapshot requires evidence_refs")
        if len(set(self.evidence_refs)) != len(self.evidence_refs):
            raise FleetException("evidence_refs must be unique")
        return self


@dataclass(frozen=True)
class ScaleAdmission:
    requested_concurrency: int
    admitted: bool
    scientific_level: str
    rationale: str


class FleetAdmissionGate:
    """Fail-closed promotion gate for 1→2→5→10→25→50→100."""

    _COMMON_SCALE_GATES = (
        "sandbox_isolation_verified",
        "authority_isolation_verified",
        "branch_ownership_verified",
        "path_ownership_verified",
        "mission_identity_verified",
        "evidence_complete",
        "scheduler_stability_verified",
        "no_unexplained_mutation_verified",
        "bounded_retries_verified",
        "duplicate_execution_control_verified",
        "deadlock_control_verified",
        "ci_pressure_acceptable",
        "resource_pressure_acceptable",
        "observability_verified",
        "replay_verified",
    )

    def evaluate(self, snapshot: FleetCapabilitySnapshot, requested_concurrency: int) -> ScaleAdmission:
        snapshot.validate()
        if requested_concurrency not in SCALE_LEVELS:
            raise FleetException(f"unsupported scale level: {requested_concurrency}")

        if len(snapshot.executor_ids) < 1 or len(snapshot.sandbox_ids) < 1:
            return ScaleAdmission(requested_concurrency, False, "L0", "no demonstrated executor+sandbox pair")

        if requested_concurrency == 1:
            return ScaleAdmission(1, True, "L1", "single executor context demonstrated")

        if snapshot.epistemic_class not in PROMOTION_EPISTEMIC_CLASSES:
            return ScaleAdmission(
                requested_concurrency,
                False,
                "L1",
                "scale promotion requires OBSERVED or ANCHORED evidence",
            )
        if len(snapshot.executor_ids) < requested_concurrency:
            return ScaleAdmission(
                requested_concurrency,
                False,
                "L1",
                "insufficient independent executor contexts",
            )
        if len(snapshot.sandbox_ids) < requested_concurrency:
            return ScaleAdmission(
                requested_concurrency,
                False,
                "L1",
                "insufficient isolated sandboxes",
            )

        missing = [name for name in self._COMMON_SCALE_GATES if not getattr(snapshot, name)]
        if missing:
            return ScaleAdmission(
                requested_concurrency,
                False,
                "L1",
                "scale gates failed: " + ",".join(sorted(missing)),
            )

        if requested_concurrency == 100 and not snapshot.adversarial_suite_verified:
            return ScaleAdmission(100, False, "L3", "100-way admission requires adversarial suite evidence")

        if requested_concurrency == 100:
            level = "L5" if snapshot.sustained_operation_verified else "L4"
        elif requested_concurrency >= 25:
            level = "L3"
        else:
            level = "L2"
        return ScaleAdmission(requested_concurrency, True, level, "all required scale gates satisfied")


class MissionRegistry:
    """Deterministic runtime mission state with heartbeat/result replay guards."""

    def __init__(self) -> None:
        self._drones: Dict[str, DroneSpec] = {}
        self._state: Dict[str, str] = {}
        self._heartbeat: Dict[str, int] = {}

    def register(self, drone: DroneSpec) -> None:
        drone.validate()
        if drone.mission_id in self._drones:
            raise FleetException(f"duplicate mission dispatch: {drone.mission_id}")
        if any(existing.drone_id == drone.drone_id for existing in self._drones.values()):
            raise FleetException(f"duplicate drone identity: {drone.drone_id}")
        self._drones[drone.mission_id] = drone
        self._state[drone.mission_id] = "STARTING"
        self._heartbeat[drone.mission_id] = 0

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
        if authority_rank(requested_authority) > authority_rank(drone.authority_ceiling):
            raise FleetException("requested authority exceeds drone authority ceiling")

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
        drone = self._drones[mission_id]
        if outcome == "SUCCEEDED":
            if not verifier_id or verifier_id == drone.drone_id:
                raise FleetException("successful result requires independent verifier")
            self._state[mission_id] = "DONE"
        elif outcome == "FAILED":
            self._state[mission_id] = "FAILED"
        else:
            self._state[mission_id] = "TERMINATED"

    def terminate(self, mission_id: str) -> None:
        self._require_mission(mission_id)
        self._state[mission_id] = "TERMINATED"

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
    """Repository coordination plus exclusive branch/path write leases."""

    def __init__(self) -> None:
        self._repository_leases: Dict[str, set[str]] = {}
        self._branch_leases: Dict[Tuple[str, str], str] = {}
        self._path_leases: Dict[Tuple[str, str], str] = {}

    def claim(self, drone: DroneSpec) -> None:
        drone.validate()
        branch_key = (drone.repository, drone.branch)
        existing_branch = self._branch_leases.get(branch_key)
        if existing_branch and existing_branch != drone.drone_id:
            raise FleetException("branch lease conflict")

        for path in drone.write_scope:
            for (repository, leased_path), owner in self._path_leases.items():
                if repository == drone.repository and owner != drone.drone_id and _path_overlap(path, leased_path):
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
    """Deterministically select conflict-free ready missions."""

    def plan(
        self,
        drones: Sequence[DroneSpec],
        *,
        current_heads: Mapping[str, str],
        completed_missions: Iterable[str] = (),
        max_parallel: int = 1,
    ) -> Tuple[str, ...]:
        if not isinstance(max_parallel, int) or max_parallel <= 0 or max_parallel > 100:
            raise FleetException("max_parallel must be in [1,100]")

        validated = [drone.validate() for drone in drones]
        mission_ids = [drone.mission_id for drone in validated]
        drone_ids = [drone.drone_id for drone in validated]
        if len(set(mission_ids)) != len(mission_ids):
            raise FleetException("duplicate mission dispatch")
        if len(set(drone_ids)) != len(drone_ids):
            raise FleetException("duplicate drone identity")

        for drone in validated:
            if current_heads.get(drone.repository) != drone.baseline_sha:
                raise FleetException(f"stale baseline: {drone.repository}:{drone.mission_id}")

        graph = DependencyGraph()
        by_mission = {drone.mission_id: drone for drone in validated}
        for drone in sorted(validated, key=lambda item: item.mission_id):
            graph.add_mission(drone.mission_id, drone.dependencies)

        ready = graph.ready(completed_missions)
        leases = LeaseRegistry()
        selected: list[str] = []
        for mission_id in ready:
            if len(selected) >= max_parallel:
                break
            drone = by_mission[mission_id]
            try:
                leases.claim(drone)
            except FleetException as exc:
                if "lease conflict" in str(exc):
                    continue
                raise
            selected.append(mission_id)
        return tuple(selected)
