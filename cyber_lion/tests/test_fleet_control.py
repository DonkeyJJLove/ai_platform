from __future__ import annotations

import dataclasses
import unittest

from cyber_lion.enterprise.fleet_control import (
    DependencyGraph,
    DroneSpec,
    FleetAdmissionGate,
    FleetCapabilitySnapshot,
    FleetException,
    FleetScheduler,
    LeaseRegistry,
    MissionRegistry,
)


BASE = "1" * 40


def drone(
    suffix: str,
    *,
    mission: str | None = None,
    branch: str | None = None,
    path: str | None = None,
    baseline: str = BASE,
    authority: str = "read",
    parent_authority: str = "local_write",
    dependencies: tuple[str, ...] = (),
) -> DroneSpec:
    name = mission or f"mission-{suffix}"
    write_path = path or f"src/{suffix}.py"
    return DroneSpec(
        drone_id=f"drone-{suffix}",
        mission_id=name,
        parent_mission_id="fleet-root",
        repository="DonkeyJJLove/example",
        baseline_sha=baseline,
        branch=branch or f"mission/{suffix}",
        workspace=f"/work/{suffix}",
        sandbox_id=f"sandbox-{suffix}",
        authority_ceiling=authority,
        parent_authority_ceiling=parent_authority,
        write_scope=(write_path,),
        read_scope=("src",),
        test_scope=("tests",),
        resource_budget=(("cpu", 1.0), ("runtime_seconds", 60.0)),
        dependencies=dependencies,
        evidence_refs=(f"evidence:{suffix}",),
    )


def capability_snapshot(
    n: int,
    *,
    epistemic_class: str = "OBSERVED",
    sandbox_isolation: bool = True,
    authority_isolation: bool = True,
    adversarial: bool = True,
    sustained: bool = False,
) -> FleetCapabilitySnapshot:
    return FleetCapabilitySnapshot(
        epistemic_class=epistemic_class,
        executor_ids=tuple(f"executor-{i}" for i in range(n)),
        sandbox_ids=tuple(f"sandbox-{i}" for i in range(n)),
        process_fanout=max(100, n),
        sandbox_isolation_verified=sandbox_isolation,
        authority_isolation_verified=authority_isolation,
        branch_ownership_verified=True,
        path_ownership_verified=True,
        mission_identity_verified=True,
        evidence_complete=True,
        scheduler_stability_verified=True,
        no_unexplained_mutation_verified=True,
        bounded_retries_verified=True,
        duplicate_execution_control_verified=True,
        deadlock_control_verified=True,
        ci_pressure_acceptable=True,
        resource_pressure_acceptable=True,
        observability_verified=True,
        replay_verified=True,
        adversarial_suite_verified=adversarial,
        sustained_operation_verified=sustained,
        evidence_refs=("observed:fleet-probe",),
    )


class DroneSpecTests(unittest.TestCase):
    def test_drone_identity_is_immutable(self) -> None:
        spec = drone("a").validate()
        with self.assertRaises(dataclasses.FrozenInstanceError):
            spec.drone_id = "mutated"  # type: ignore[misc]

    def test_path_escape_is_rejected(self) -> None:
        spec = dataclasses.replace(drone("a"), write_scope=("../escape.py",))
        with self.assertRaises(FleetException):
            spec.validate()

    def test_absolute_path_is_rejected(self) -> None:
        spec = dataclasses.replace(drone("a"), write_scope=("/tmp/escape.py",))
        with self.assertRaises(FleetException):
            spec.validate()

    def test_child_authority_cannot_exceed_parent(self) -> None:
        spec = drone("a", authority="external_write", parent_authority="read")
        with self.assertRaises(FleetException):
            spec.validate()

    def test_explicit_scopes_are_required(self) -> None:
        spec = dataclasses.replace(drone("a"), test_scope=())
        with self.assertRaises(FleetException):
            spec.validate()


class MissionRegistryTests(unittest.TestCase):
    def test_duplicate_mission_dispatch_is_rejected(self) -> None:
        registry = MissionRegistry()
        registry.register(drone("a"))
        with self.assertRaises(FleetException):
            registry.register(drone("b", mission="mission-a"))

    def test_cross_mission_authority_request_is_rejected(self) -> None:
        registry = MissionRegistry()
        registry.register(drone("a"))
        with self.assertRaises(FleetException):
            registry.authorize_request("mission-a", "drone-other", "read")

    def test_authority_request_cannot_exceed_drone_ceiling(self) -> None:
        registry = MissionRegistry()
        registry.register(drone("a", authority="read"))
        with self.assertRaises(FleetException):
            registry.authorize_request("mission-a", "drone-a", "local_write")

    def test_false_success_report_from_builder_is_rejected(self) -> None:
        registry = MissionRegistry()
        registry.register(drone("a"))
        registry.heartbeat("mission-a", 1)
        with self.assertRaises(FleetException):
            registry.report_result(
                "mission-a",
                outcome="SUCCEEDED",
                evidence_refs=("builder:self-report",),
                verifier_id="drone-a",
            )

    def test_success_without_heartbeat_is_rejected(self) -> None:
        registry = MissionRegistry()
        registry.register(drone("a"))
        with self.assertRaises(FleetException):
            registry.report_result(
                "mission-a",
                outcome="SUCCEEDED",
                evidence_refs=("verify:1",),
                verifier_id="verifier-1",
            )

    def test_late_result_after_cancel_is_rejected(self) -> None:
        registry = MissionRegistry()
        registry.register(drone("a"))
        registry.heartbeat("mission-a", 1)
        registry.terminate("mission-a")
        with self.assertRaises(FleetException):
            registry.report_result(
                "mission-a",
                outcome="FAILED",
                evidence_refs=("late:1",),
            )

    def test_snapshot_is_deterministic(self) -> None:
        registry = MissionRegistry()
        registry.register(drone("b"))
        registry.register(drone("a"))
        registry.heartbeat("mission-b", 2)
        registry.heartbeat("mission-a", 1)
        self.assertEqual(
            registry.snapshot(),
            (("mission-a", "STARTING", 1), ("mission-b", "STARTING", 2)),
        )


class DependencyGraphTests(unittest.TestCase):
    def test_dependency_cycle_is_rejected(self) -> None:
        graph = DependencyGraph()
        graph.add_mission("a", ("b",))
        with self.assertRaises(FleetException):
            graph.add_mission("b", ("a",))

    def test_ready_is_sorted_and_dependency_bound(self) -> None:
        graph = DependencyGraph()
        graph.add_mission("b", ("a",))
        graph.add_mission("a")
        graph.add_mission("c")
        self.assertEqual(graph.ready(()), ("a", "c"))
        self.assertEqual(graph.ready(("a",)), ("b", "c"))


class LeaseRegistryTests(unittest.TestCase):
    def test_same_branch_two_drones_is_rejected(self) -> None:
        leases = LeaseRegistry()
        leases.claim(drone("a", branch="mission/shared"))
        with self.assertRaises(FleetException):
            leases.claim(drone("b", branch="mission/shared"))

    def test_same_file_two_drones_is_rejected(self) -> None:
        leases = LeaseRegistry()
        leases.claim(drone("a", path="src/shared.py"))
        with self.assertRaises(FleetException):
            leases.claim(drone("b", path="src/shared.py"))

    def test_parent_child_path_overlap_is_rejected(self) -> None:
        leases = LeaseRegistry()
        leases.claim(drone("a", path="src/service"))
        with self.assertRaises(FleetException):
            leases.claim(drone("b", path="src/service/api.py"))

    def test_disjoint_paths_in_same_repository_are_allowed(self) -> None:
        leases = LeaseRegistry()
        leases.claim(drone("a", path="src/a.py"))
        leases.claim(drone("b", path="src/b.py"))
        snapshot = leases.snapshot()
        self.assertIn(("path", "DonkeyJJLove/example:src/a.py", "drone-a"), snapshot)
        self.assertIn(("path", "DonkeyJJLove/example:src/b.py", "drone-b"), snapshot)


class FleetSchedulerTests(unittest.TestCase):
    def test_stale_baseline_is_rejected(self) -> None:
        scheduler = FleetScheduler()
        with self.assertRaises(FleetException):
            scheduler.plan(
                [drone("a")],
                current_heads={"DonkeyJJLove/example": "2" * 40},
            )

    def test_scheduler_is_deterministic(self) -> None:
        scheduler = FleetScheduler()
        specs = [drone("c"), drone("a"), drone("b")]
        planned = scheduler.plan(
            specs,
            current_heads={"DonkeyJJLove/example": BASE},
            max_parallel=2,
        )
        self.assertEqual(planned, ("mission-a", "mission-b"))

    def test_scheduler_respects_dependencies(self) -> None:
        scheduler = FleetScheduler()
        specs = [
            drone("a"),
            drone("b", dependencies=("mission-a",)),
        ]
        first = scheduler.plan(
            specs,
            current_heads={"DonkeyJJLove/example": BASE},
            max_parallel=2,
        )
        second = scheduler.plan(
            specs,
            current_heads={"DonkeyJJLove/example": BASE},
            completed_missions=("mission-a",),
            max_parallel=2,
        )
        self.assertEqual(first, ("mission-a",))
        self.assertEqual(second, ("mission-b",))

    def test_scheduler_serializes_path_conflict(self) -> None:
        scheduler = FleetScheduler()
        specs = [
            drone("a", path="src/shared.py"),
            drone("b", path="src/shared.py"),
        ]
        planned = scheduler.plan(
            specs,
            current_heads={"DonkeyJJLove/example": BASE},
            max_parallel=2,
        )
        self.assertEqual(planned, ("mission-a",))


class FleetAdmissionTests(unittest.TestCase):
    def test_malformed_duplicate_executor_evidence_is_rejected(self) -> None:
        snapshot = dataclasses.replace(
            capability_snapshot(2),
            executor_ids=("executor-1", "executor-1"),
        )
        with self.assertRaises(FleetException):
            FleetAdmissionGate().evaluate(snapshot, 2)

    def test_process_fanout_does_not_equal_executor_parallelism(self) -> None:
        snapshot = dataclasses.replace(
            capability_snapshot(1),
            process_fanout=100,
        )
        decision = FleetAdmissionGate().evaluate(snapshot, 2)
        self.assertFalse(decision.admitted)
        self.assertEqual(decision.scientific_level, "L1")
        self.assertIn("executor", decision.rationale)

    def test_inferred_evidence_cannot_promote_scale(self) -> None:
        decision = FleetAdmissionGate().evaluate(
            capability_snapshot(2, epistemic_class="INFERRED"),
            2,
        )
        self.assertFalse(decision.admitted)

    def test_unproven_sandbox_isolation_denies_scale(self) -> None:
        decision = FleetAdmissionGate().evaluate(
            capability_snapshot(2, sandbox_isolation=False),
            2,
        )
        self.assertFalse(decision.admitted)
        self.assertIn("sandbox_isolation_verified", decision.rationale)

    def test_unproven_authority_isolation_denies_scale(self) -> None:
        decision = FleetAdmissionGate().evaluate(
            capability_snapshot(2, authority_isolation=False),
            2,
        )
        self.assertFalse(decision.admitted)
        self.assertIn("authority_isolation_verified", decision.rationale)

    def test_scale_ladder_dry_run(self) -> None:
        gate = FleetAdmissionGate()
        snapshot = capability_snapshot(100)
        expected = {
            1: "L1",
            2: "L2",
            5: "L2",
            10: "L2",
            25: "L3",
            50: "L3",
            100: "L4",
        }
        for level, scientific_level in expected.items():
            with self.subTest(level=level):
                decision = gate.evaluate(snapshot, level)
                self.assertTrue(decision.admitted)
                self.assertEqual(decision.scientific_level, scientific_level)

    def test_100_way_requires_adversarial_suite(self) -> None:
        decision = FleetAdmissionGate().evaluate(
            capability_snapshot(100, adversarial=False),
            100,
        )
        self.assertFalse(decision.admitted)
        self.assertEqual(decision.scientific_level, "L3")

    def test_sustained_100_way_is_l5_only_with_sustained_evidence(self) -> None:
        decision = FleetAdmissionGate().evaluate(
            capability_snapshot(100, sustained=True),
            100,
        )
        self.assertTrue(decision.admitted)
        self.assertEqual(decision.scientific_level, "L5")


if __name__ == "__main__":
    unittest.main()
