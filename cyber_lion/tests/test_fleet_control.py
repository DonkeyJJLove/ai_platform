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
    TrustedVerifierIdentity,
    VerifiedFleetCapability,
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
    return DroneSpec(
        drone_id=f"drone-{suffix}",
        mission_id=mission or f"mission-{suffix}",
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
    def __init__(self, ceiling: str = "local_write") -> None:
        self.ceiling = ceiling

    def resolve_parent_authority(self, spec: DroneSpec) -> ParentAuthorityAdmission:
        return ParentAuthorityAdmission(
            mission_id=spec.mission_id,
            parent_mission_id=spec.parent_mission_id,
            repository=spec.repository,
            baseline_sha=spec.baseline_sha,
            authority_ceiling=self.ceiling,
            grant_digest="grant:root",
        )


class TrustSource:
    def __init__(self) -> None:
        self.records: dict[tuple[str, str, str], TrustedVerifierIdentity] = {}

    def add(self, verifier_id: str, mission_id: str, capability: str) -> TrustedVerifierIdentity:
        identity = TrustedVerifierIdentity(
            verifier_id=verifier_id,
            mission_id=mission_id,
            capabilities=(capability,),
            identity_digest=f"identity:{verifier_id}:{mission_id}:{capability}",
            trust_anchor_id="root:test",
        )
        self.records[(verifier_id, mission_id, capability)] = identity
        return identity

    def resolve_verifier(
        self,
        verifier_id: str,
        mission_id: str,
        required_capability: str,
    ) -> TrustedVerifierIdentity:
        key = (verifier_id, mission_id, required_capability)
        if key not in self.records:
            raise FleetException("untrusted verifier")
        return self.records[key]


def snapshot(n: int, *, adversarial: bool = True, sustained: bool = False) -> FleetCapabilitySnapshot:
    return FleetCapabilitySnapshot(
        epistemic_class="OBSERVED",
        executor_ids=tuple(f"executor-{i}" for i in range(n)),
        sandbox_ids=tuple(f"sandbox-{i}" for i in range(n)),
        process_fanout=max(100, n),
        sandbox_isolation_verified=True,
        authority_isolation_verified=True,
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
        evidence_refs=("anchor:fleet-probe",),
    )


class TrustedFleetVerifier:
    verifier_id = "fleet-verifier"

    def __init__(self, identity: TrustedVerifierIdentity) -> None:
        self.identity = identity

    def verify(
        self,
        raw: FleetCapabilitySnapshot,
        requested_concurrency: int,
    ) -> VerifiedFleetCapability:
        raw.validate()
        common = (
            raw.sandbox_isolation_verified,
            raw.authority_isolation_verified,
            raw.branch_ownership_verified,
            raw.path_ownership_verified,
            raw.mission_identity_verified,
            raw.evidence_complete,
            raw.scheduler_stability_verified,
            raw.no_unexplained_mutation_verified,
            raw.bounded_retries_verified,
            raw.duplicate_execution_control_verified,
            raw.deadlock_control_verified,
            raw.ci_pressure_acceptable,
            raw.resource_pressure_acceptable,
            raw.observability_verified,
            raw.replay_verified,
        )
        if not all(common):
            raise FleetException("fleet gate failure")
        if len(raw.executor_ids) < requested_concurrency or len(raw.sandbox_ids) < requested_concurrency:
            raise FleetException("insufficient fleet capacity")
        return VerifiedFleetCapability(
            snapshot_digest=raw.digest(),
            verified_concurrency=requested_concurrency,
            executor_ids=raw.executor_ids,
            sandbox_ids=raw.sandbox_ids,
            epistemic_class=raw.epistemic_class,
            gates_passed=True,
            adversarial_suite_verified=raw.adversarial_suite_verified,
            sustained_operation_verified=raw.sustained_operation_verified,
            verifier_id=self.identity.verifier_id,
            verifier_identity_digest=self.identity.identity_digest,
            trust_anchor_id=self.identity.trust_anchor_id,
            evidence_refs=("anchor:fleet-probe",),
        )


class FleetResolver:
    def __init__(self, verifier: TrustedFleetVerifier | object) -> None:
        self.verifier = verifier

    def resolve_fleet_verifier(self, verifier_id: str):
        if getattr(self.verifier, "verifier_id", None) != verifier_id:
            raise FleetException("fleet verifier not registered")
        return self.verifier


class DroneContractTests(unittest.TestCase):
    def test_immutable(self) -> None:
        spec = drone("a")
        with self.assertRaises(dataclasses.FrozenInstanceError):
            spec.drone_id = "x"  # type: ignore[misc]

    def test_path_escape_denied(self) -> None:
        with self.assertRaises(FleetException):
            dataclasses.replace(drone("a"), write_scope=("../x",)).validate()

    def test_parent_authority_not_self_declared(self) -> None:
        self.assertFalse(hasattr(drone("a"), "parent_authority_ceiling"))


class MissionAndVerifierTests(unittest.TestCase):
    def setUp(self) -> None:
        self.trust = TrustSource()
        self.registry = MissionRegistry(AuthoritySource(), self.trust)

    def test_child_authority_checked_against_parent(self) -> None:
        with self.assertRaises(FleetException):
            MissionRegistry(AuthoritySource("read"), self.trust).register(
                drone("a", authority="external_write")
            )

    def test_duplicate_mission_denied(self) -> None:
        self.registry.register(drone("a"))
        with self.assertRaises(FleetException):
            self.registry.register(drone("b", mission="mission-a"))

    def test_fake_registered_verifier_denied(self) -> None:
        self.registry.register(drone("a"))
        with self.assertRaises(FleetException):
            self.registry.bind_verifier("mission-a", "fake-verifier", "verify:a")

    def test_builder_alias_denied_even_if_trusted(self) -> None:
        self.registry.register(drone("a"))
        self.trust.add("drone-a", "mission-a", "mission_result_verify")
        with self.assertRaises(FleetException):
            self.registry.bind_verifier("mission-a", "drone-a", "verify:a")

    def test_wrong_mission_verifier_denied(self) -> None:
        self.registry.register(drone("a"))
        self.trust.add("verifier-1", "mission-b", "mission_result_verify")
        with self.assertRaises(FleetException):
            self.registry.bind_verifier("mission-a", "verifier-1", "verify:a")

    def test_trusted_verifier_evidence_bound_to_result(self) -> None:
        self.registry.register(drone("a"))
        self.trust.add("verifier-1", "mission-a", "mission_result_verify")
        self.registry.bind_verifier("mission-a", "verifier-1", "verify:a")
        self.registry.heartbeat("mission-a", 1)
        with self.assertRaises(FleetException):
            self.registry.report_result(
                "mission-a", outcome="SUCCEEDED",
                evidence_refs=("other",), verifier_id="verifier-1",
            )

    def test_trusted_verifier_allows_success(self) -> None:
        self.registry.register(drone("a"))
        self.trust.add("verifier-1", "mission-a", "mission_result_verify")
        self.registry.bind_verifier("mission-a", "verifier-1", "verify:a")
        self.registry.heartbeat("mission-a", 1)
        self.registry.report_result(
            "mission-a", outcome="SUCCEEDED",
            evidence_refs=("verify:a",), verifier_id="verifier-1",
        )
        self.assertEqual(self.registry.state("mission-a"), "DONE")


class LeaseAndSchedulerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.trust = TrustSource()
        self.registry = MissionRegistry(AuthoritySource(), self.trust)
        self.leases = LeaseRegistry()
        self.scheduler = FleetScheduler(self.registry, self.leases)

    def test_dependency_cycle_denied(self) -> None:
        graph = DependencyGraph()
        graph.add_mission("a", ("b",))
        with self.assertRaises(FleetException):
            graph.add_mission("b", ("a",))

    def test_stale_baseline_denied(self) -> None:
        self.registry.register(drone("a"))
        with self.assertRaises(FleetException):
            self.scheduler.plan(current_heads={REPO: "2" * 40})

    def test_running_mission_not_redispatched(self) -> None:
        self.registry.register(drone("a"))
        self.assertEqual(self.scheduler.plan(current_heads={REPO: BASE}), ("mission-a",))
        self.assertEqual(self.scheduler.plan(current_heads={REPO: BASE}), ())

    def test_branch_lease_survives_cycles(self) -> None:
        self.registry.register(drone("a", branch="mission/shared", path="src/a.py"))
        self.scheduler.plan(current_heads={REPO: BASE})
        self.registry.register(drone("b", branch="mission/shared", path="src/b.py"))
        self.assertEqual(self.scheduler.plan(current_heads={REPO: BASE}, max_parallel=2), ())

    def test_path_lease_survives_cycles(self) -> None:
        self.registry.register(drone("a", path="src/shared.py"))
        self.scheduler.plan(current_heads={REPO: BASE})
        self.registry.register(drone("b", path="src/shared.py"))
        self.assertEqual(self.scheduler.plan(current_heads={REPO: BASE}, max_parallel=2), ())

    def test_completed_state_derived_from_registry(self) -> None:
        self.registry.register(drone("a"))
        self.registry.register(drone("b", dependencies=("mission-a",)))
        self.assertEqual(self.scheduler.plan(current_heads={REPO: BASE}, max_parallel=2), ("mission-a",))
        self.registry.heartbeat("mission-a", 1)
        self.trust.add("verifier-1", "mission-a", "mission_result_verify")
        self.registry.bind_verifier("mission-a", "verifier-1", "verify:a")
        self.registry.report_result(
            "mission-a", outcome="SUCCEEDED",
            evidence_refs=("verify:a",), verifier_id="verifier-1",
        )
        self.assertEqual(self.scheduler.plan(current_heads={REPO: BASE}, max_parallel=2), ("mission-b",))

    def test_state_contains_persistent_leases(self) -> None:
        self.registry.register(drone("a"))
        self.scheduler.plan(current_heads={REPO: BASE})
        state = deterministic_fleet_state(self.registry, self.leases)
        self.assertEqual(state[0], ("mission-a",))
        self.assertTrue(any(row[0] == "branch" for row in state[2]))


class FleetTrustTests(unittest.TestCase):
    def make_gate(self):
        trust = TrustSource()
        identity = trust.add("fleet-verifier", "*", "fleet_scale_verify")
        verifier = TrustedFleetVerifier(identity)
        return FleetAdmissionGate(
            verifier_id="fleet-verifier",
            trust_source=trust,
            resolver=FleetResolver(verifier),
        ), trust, identity

    def test_fake_observed_snapshot_without_trusted_verifier_denied(self) -> None:
        trust = TrustSource()
        gate = FleetAdmissionGate(
            verifier_id="evil",
            trust_source=trust,
            resolver=FleetResolver(object()),
        )
        with self.assertRaises(FleetException):
            gate.evaluate(snapshot(100), 100)

    def test_untrusted_injected_verifier_denied_by_identity_binding(self) -> None:
        _, trust, identity = self.make_gate()

        class EvilVerifier:
            verifier_id = "fleet-verifier"
            def verify(self, raw, requested):
                return VerifiedFleetCapability(
                    snapshot_digest=raw.digest(),
                    verified_concurrency=requested,
                    executor_ids=raw.executor_ids,
                    sandbox_ids=raw.sandbox_ids,
                    epistemic_class="OBSERVED",
                    gates_passed=True,
                    adversarial_suite_verified=True,
                    sustained_operation_verified=True,
                    verifier_id="fleet-verifier",
                    verifier_identity_digest="forged",
                    trust_anchor_id=identity.trust_anchor_id,
                    evidence_refs=("fake",),
                )

        evil_gate = FleetAdmissionGate(
            verifier_id="fleet-verifier",
            trust_source=trust,
            resolver=FleetResolver(EvilVerifier()),
        )
        with self.assertRaises(FleetException):
            evil_gate.evaluate(snapshot(100), 100)

    def test_snapshot_digest_binding(self) -> None:
        _, trust, identity = self.make_gate()

        class BadDigestVerifier(TrustedFleetVerifier):
            def verify(self, raw, requested):
                good = super().verify(raw, requested)
                return dataclasses.replace(good, snapshot_digest="0" * 64)

        bad = FleetAdmissionGate(
            verifier_id="fleet-verifier",
            trust_source=trust,
            resolver=FleetResolver(BadDigestVerifier(identity)),
        )
        with self.assertRaises(FleetException):
            bad.evaluate(snapshot(2), 2)

    def test_process_fanout_not_executor_parallelism(self) -> None:
        gate, _, _ = self.make_gate()
        with self.assertRaises(FleetException):
            gate.evaluate(snapshot(1), 2)

    def test_l4_requires_100_trusted_capacity(self) -> None:
        gate, _, _ = self.make_gate()
        decision = gate.evaluate(snapshot(100), 100)
        self.assertTrue(decision.admitted)
        self.assertEqual(decision.scientific_level, "L4")

    def test_l5_requires_sustained_evidence(self) -> None:
        gate, _, _ = self.make_gate()
        decision = gate.evaluate(snapshot(100, sustained=True), 100)
        self.assertEqual(decision.scientific_level, "L5")


if __name__ == "__main__":
    unittest.main()
