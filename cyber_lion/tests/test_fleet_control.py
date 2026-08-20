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
    ParentAuthorityAdmission,
    VerifiedFleetCapability,
    VerifierBinding,
    deterministic_fleet_state,
)


BASE = "1" * 40
REPO = "DonkeyJJLove/example"


def drone(
    suffix: str,
    *,
    mission: str | None = None,
    branch: str | None = None,
    path: str | None = None,
    baseline: str = BASE,
    authority: str = "read",
    dependencies: tuple[str, ...] = (),
) -> DroneSpec:
    name = mission or f"mission-{suffix}"
    return DroneSpec(
        drone_id=f"drone-{suffix}",
        mission_id=name,
        parent_mission_id="fleet-root",
        repository=REPO,
        baseline_sha=baseline,
        branch=branch or f"mission/{suffix}",
        workspace=f"/work/{suffix}",
        sandbox_id=f"sandbox-{suffix}",
        authority_ceiling=authority,
        write_scope=(path or f"src/{suffix}.py",),
        read_scope=("src",),
        test_scope=("tests",),
        resource_budget=(("cpu", 1.0), ("runtime_seconds", 60.0)),
        dependencies=dependencies,
        evidence_refs=(f"contract:{suffix}",),
    )


class AuthoritySource:
    def __init__(self, *, ceiling: str = "local_write", grant_digest: str = "grant:root") -> None:
        self.ceiling = ceiling
        self.grant_digest = grant_digest

    def resolve_parent_authority(self, spec: DroneSpec) -> ParentAuthorityAdmission:
        return ParentAuthorityAdmission(
            mission_id=spec.mission_id,
            parent_mission_id=spec.parent_mission_id,
            repository=spec.repository,
            baseline_sha=spec.baseline_sha,
            authority_ceiling=self.ceiling,
            grant_digest=self.grant_digest,
        )


def snapshot(
    n: int,
    *,
    evidence_refs: tuple[str, ...] = ("anchor:fleet-probe",),
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
        evidence_refs=evidence_refs,
    )


class TrustedFixtureVerifier:
    """Test stand-in for a trusted external measurement verifier."""

    COMMON = (
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

    def verify(
        self,
        raw: FleetCapabilitySnapshot,
        requested_concurrency: int,
    ) -> VerifiedFleetCapability:
        raw.validate()
        if "anchor:fleet-probe" not in raw.evidence_refs:
            raise FleetException("trusted evidence anchor missing")
        if raw.epistemic_class not in {"OBSERVED", "ANCHORED"}:
            raise FleetException("trusted verifier rejects non-promotable epistemic class")
        if not all(getattr(raw, name) for name in self.COMMON):
            raise FleetException("trusted verifier rejects failed scale gate")
        if len(raw.executor_ids) < requested_concurrency or len(raw.sandbox_ids) < requested_concurrency:
            raise FleetException("trusted verifier rejects insufficient capacity")
        return VerifiedFleetCapability(
            snapshot_digest=raw.digest(),
            verified_concurrency=requested_concurrency,
            executor_ids=raw.executor_ids,
            sandbox_ids=raw.sandbox_ids,
            epistemic_class=raw.epistemic_class,
            gates_passed=True,
            adversarial_suite_verified=raw.adversarial_suite_verified,
            sustained_operation_verified=raw.sustained_operation_verified,
            verifier_id="trusted-fleet-probe-v1",
            evidence_refs=("anchor:fleet-probe",),
        )


class DigestMismatchVerifier(TrustedFixtureVerifier):
    def verify(self, raw: FleetCapabilitySnapshot, requested_concurrency: int) -> VerifiedFleetCapability:
        good = super().verify(raw, requested_concurrency)
        return dataclasses.replace(good, snapshot_digest="0" * 64)


class DroneContractTests(unittest.TestCase):
    def test_drone_identity_is_immutable(self) -> None:
        spec = drone("a").validate()
        with self.assertRaises(dataclasses.FrozenInstanceError):
            spec.drone_id = "changed"  # type: ignore[misc]

    def test_path_escape_is_rejected(self) -> None:
        with self.assertRaises(FleetException):
            dataclasses.replace(drone("a"), write_scope=("../escape.py",)).validate()

    def test_absolute_path_is_rejected(self) -> None:
        with self.assertRaises(FleetException):
            dataclasses.replace(drone("a"), write_scope=("/tmp/x",)).validate()

    def test_scope_is_required(self) -> None:
        with self.assertRaises(FleetException):
            dataclasses.replace(drone("a"), test_scope=()).validate()

    def test_parent_authority_is_not_self_declared(self) -> None:
        self.assertFalse(hasattr(drone("a"), "parent_authority_ceiling"))


class AuthorityBindingTests(unittest.TestCase):
    def test_child_authority_checked_against_trusted_parent(self) -> None:
        registry = MissionRegistry(AuthoritySource(ceiling="read"))
        with self.assertRaises(FleetException):
            registry.register(drone("a", authority="external_write"))

    def test_exact_parent_binding_mismatch_denied(self) -> None:
        class BadSource(AuthoritySource):
            def resolve_parent_authority(self, spec: DroneSpec) -> ParentAuthorityAdmission:
                result = super().resolve_parent_authority(spec)
                return dataclasses.replace(result, repository="DonkeyJJLove/other")
        with self.assertRaises(FleetException):
            MissionRegistry(BadSource()).register(drone("a"))

    def test_cross_mission_authority_request_denied(self) -> None:
        registry = MissionRegistry(AuthoritySource())
        registry.register(drone("a"))
        with self.assertRaises(FleetException):
            registry.authorize_request("mission-a", "drone-other", "read")

    def test_runtime_authority_cannot_exceed_trusted_parent(self) -> None:
        registry = MissionRegistry(AuthoritySource(ceiling="read"))
        registry.register(drone("a", authority="read"))
        with self.assertRaises(FleetException):
            registry.authorize_request("mission-a", "drone-a", "local_write")


class MissionRegistryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = MissionRegistry(AuthoritySource())

    def test_duplicate_mission_denied(self) -> None:
        self.registry.register(drone("a"))
        with self.assertRaises(FleetException):
            self.registry.register(drone("b", mission="mission-a"))

    def test_duplicate_drone_id_denied(self) -> None:
        first = drone("a")
        second = dataclasses.replace(drone("b"), drone_id=first.drone_id)
        self.registry.register(first)
        with self.assertRaises(FleetException):
            self.registry.register(second)

    def test_unknown_verifier_denied(self) -> None:
        self.registry.register(drone("a"))
        self.registry.heartbeat("mission-a", 1)
        with self.assertRaises(FleetException):
            self.registry.report_result(
                "mission-a", outcome="SUCCEEDED",
                evidence_refs=("verify:a",), verifier_id="fake-verifier",
            )

    def test_builder_verifier_alias_denied(self) -> None:
        self.registry.register(drone("a"))
        with self.assertRaises(FleetException):
            self.registry.register_verifier(
                VerifierBinding("mission-a", "drone-a", "verify:a")
            )

    def test_verifier_must_be_bound_to_exact_mission(self) -> None:
        self.registry.register(drone("a"))
        self.registry.register(drone("b"))
        self.registry.register_verifier(
            VerifierBinding("mission-b", "verifier-1", "verify:b")
        )
        self.registry.heartbeat("mission-a", 1)
        with self.assertRaises(FleetException):
            self.registry.report_result(
                "mission-a", outcome="SUCCEEDED",
                evidence_refs=("verify:b",), verifier_id="verifier-1",
            )

    def test_verifier_evidence_must_bind_result(self) -> None:
        self.registry.register(drone("a"))
        self.registry.register_verifier(
            VerifierBinding("mission-a", "verifier-1", "verify:a")
        )
        self.registry.heartbeat("mission-a", 1)
        with self.assertRaises(FleetException):
            self.registry.report_result(
                "mission-a", outcome="SUCCEEDED",
                evidence_refs=("something-else",), verifier_id="verifier-1",
            )

    def test_registered_independent_verifier_allows_success(self) -> None:
        self.registry.register(drone("a"))
        self.registry.register_verifier(
            VerifierBinding("mission-a", "verifier-1", "verify:a")
        )
        self.registry.heartbeat("mission-a", 1)
        self.registry.report_result(
            "mission-a", outcome="SUCCEEDED",
            evidence_refs=("verify:a", "test:pass"), verifier_id="verifier-1",
        )
        self.assertEqual(self.registry.state("mission-a"), "DONE")

    def test_missing_heartbeat_denied(self) -> None:
        self.registry.register(drone("a"))
        self.registry.register_verifier(
            VerifierBinding("mission-a", "verifier-1", "verify:a")
        )
        with self.assertRaises(FleetException):
            self.registry.report_result(
                "mission-a", outcome="SUCCEEDED",
                evidence_refs=("verify:a",), verifier_id="verifier-1",
            )

    def test_late_result_after_cancel_denied(self) -> None:
        self.registry.register(drone("a"))
        self.registry.heartbeat("mission-a", 1)
        self.registry.terminate("mission-a")
        with self.assertRaises(FleetException):
            self.registry.report_result(
                "mission-a", outcome="FAILED", evidence_refs=("late:a",)
            )


class DependencyAndLeaseTests(unittest.TestCase):
    def test_dependency_cycle_denied(self) -> None:
        graph = DependencyGraph()
        graph.add_mission("a", ("b",))
        with self.assertRaises(FleetException):
            graph.add_mission("b", ("a",))

    def test_same_branch_two_drones_denied(self) -> None:
        leases = LeaseRegistry()
        leases.claim(drone("a", branch="mission/shared"))
        with self.assertRaises(FleetException):
            leases.claim(drone("b", branch="mission/shared"))

    def test_same_file_two_drones_denied(self) -> None:
        leases = LeaseRegistry()
        leases.claim(drone("a", path="src/shared.py"))
        with self.assertRaises(FleetException):
            leases.claim(drone("b", path="src/shared.py"))

    def test_parent_child_path_prefix_collision_denied(self) -> None:
        leases = LeaseRegistry()
        leases.claim(drone("a", path="src/service"))
        with self.assertRaises(FleetException):
            leases.claim(drone("b", path="src/service/api.py"))

    def test_disjoint_paths_allowed(self) -> None:
        leases = LeaseRegistry()
        leases.claim(drone("a", path="src/a.py"))
        leases.claim(drone("b", path="src/b.py"))
        self.assertEqual(len([x for x in leases.snapshot() if x[0] == "path"]), 2)


class PersistentSchedulerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = MissionRegistry(AuthoritySource())
        self.leases = LeaseRegistry()
        self.scheduler = FleetScheduler(self.registry, self.leases)

    def test_stale_baseline_denied(self) -> None:
        self.registry.register(drone("a"))
        with self.assertRaises(FleetException):
            self.scheduler.plan(current_heads={REPO: "2" * 40})

    def test_scheduler_is_deterministic(self) -> None:
        for spec in (drone("c"), drone("a"), drone("b")):
            self.registry.register(spec)
        self.assertEqual(
            self.scheduler.plan(current_heads={REPO: BASE}, max_parallel=2),
            ("mission-a", "mission-b"),
        )

    def test_running_mission_not_dispatched_twice(self) -> None:
        self.registry.register(drone("a"))
        first = self.scheduler.plan(current_heads={REPO: BASE}, max_parallel=1)
        second = self.scheduler.plan(current_heads={REPO: BASE}, max_parallel=1)
        self.assertEqual(first, ("mission-a",))
        self.assertEqual(second, ())

    def test_branch_lease_survives_scheduling_cycles(self) -> None:
        self.registry.register(drone("a", branch="mission/shared", path="src/a.py"))
        self.scheduler.plan(current_heads={REPO: BASE})
        self.registry.register(drone("b", branch="mission/shared", path="src/b.py"))
        self.assertEqual(self.scheduler.plan(current_heads={REPO: BASE}, max_parallel=2), ())

    def test_path_lease_survives_scheduling_cycles(self) -> None:
        self.registry.register(drone("a", path="src/shared.py"))
        self.scheduler.plan(current_heads={REPO: BASE})
        self.registry.register(drone("b", path="src/shared.py"))
        self.assertEqual(self.scheduler.plan(current_heads={REPO: BASE}, max_parallel=2), ())

    def test_completed_state_is_derived_from_registry(self) -> None:
        self.registry.register(drone("a"))
        self.registry.register(drone("b", dependencies=("mission-a",)))
        self.assertEqual(
            self.scheduler.plan(current_heads={REPO: BASE}, max_parallel=2),
            ("mission-a",),
        )
        self.registry.heartbeat("mission-a", 1)
        self.registry.register_verifier(
            VerifierBinding("mission-a", "verifier-1", "verify:a")
        )
        self.registry.report_result(
            "mission-a", outcome="SUCCEEDED",
            evidence_refs=("verify:a",), verifier_id="verifier-1",
        )
        self.assertEqual(
            self.scheduler.plan(current_heads={REPO: BASE}, max_parallel=2),
            ("mission-b",),
        )

    def test_deterministic_fleet_state_includes_persistent_leases(self) -> None:
        self.registry.register(drone("a"))
        self.scheduler.plan(current_heads={REPO: BASE})
        state = deterministic_fleet_state(self.registry, self.leases)
        self.assertEqual(state[0], ("mission-a",))
        self.assertTrue(any(row[0] == "branch" for row in state[2]))


class TrustedEvidenceAdmissionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.gate = FleetAdmissionGate(TrustedFixtureVerifier())

    def test_raw_snapshot_cannot_be_evaluated_without_verifier_boundary(self) -> None:
        with self.assertRaises(TypeError):
            FleetAdmissionGate()  # type: ignore[call-arg]

    def test_arbitrary_evidence_ref_cannot_promote(self) -> None:
        with self.assertRaises(FleetException):
            self.gate.evaluate(snapshot(2, evidence_refs=("caller:assertion",)), 2)

    def test_inferred_evidence_cannot_promote(self) -> None:
        with self.assertRaises(FleetException):
            self.gate.evaluate(snapshot(2, epistemic_class="INFERRED"), 2)

    def test_failed_sandbox_isolation_denied(self) -> None:
        with self.assertRaises(FleetException):
            self.gate.evaluate(snapshot(2, sandbox_isolation=False), 2)

    def test_failed_authority_isolation_denied(self) -> None:
        with self.assertRaises(FleetException):
            self.gate.evaluate(snapshot(2, authority_isolation=False), 2)

    def test_snapshot_digest_mismatch_denied(self) -> None:
        with self.assertRaises(FleetException):
            FleetAdmissionGate(DigestMismatchVerifier()).evaluate(snapshot(2), 2)

    def test_process_fanout_not_executor_parallelism(self) -> None:
        raw = dataclasses.replace(snapshot(1), process_fanout=100)
        with self.assertRaises(FleetException):
            self.gate.evaluate(raw, 2)

    def test_scale_ladder_1_to_50_with_trusted_evidence(self) -> None:
        expected = {1: "L1", 2: "L2", 5: "L2", 10: "L2", 25: "L3", 50: "L3"}
        raw = snapshot(100)
        for level, scientific_level in expected.items():
            with self.subTest(level=level):
                result = self.gate.evaluate(raw, level)
                self.assertTrue(result.admitted)
                self.assertEqual(result.scientific_level, scientific_level)

    def test_false_l4_without_adversarial_evidence_denied(self) -> None:
        result = self.gate.evaluate(snapshot(100, adversarial=False), 100)
        self.assertFalse(result.admitted)
        self.assertEqual(result.scientific_level, "L3")

    def test_l4_requires_trusted_100_way_evidence(self) -> None:
        result = self.gate.evaluate(snapshot(100), 100)
        self.assertTrue(result.admitted)
        self.assertEqual(result.scientific_level, "L4")
        self.assertEqual(result.verification_digest, snapshot(100).digest())

    def test_l5_requires_sustained_evidence(self) -> None:
        self.assertEqual(
            self.gate.evaluate(snapshot(100, sustained=True), 100).scientific_level,
            "L5",
        )


if __name__ == "__main__":
    unittest.main()
