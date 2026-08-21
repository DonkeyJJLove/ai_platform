from __future__ import annotations

import dataclasses
import unittest

from cyber_lion.contracts.fleet_coordination import (
    FleetCoordinationContractError,
    FleetCoordinationSpec,
    FleetDispatch,
    FleetPlanRequest,
)


BASE = "a" * 40
TREE = "b" * 40


def spec(**overrides) -> FleetCoordinationSpec:
    values = dict(
        mission_id="mission-a",
        drone_id="drone-a",
        repository="DonkeyJJLove/ai_platform",
        baseline_sha=BASE,
        baseline_tree_sha=TREE,
        branch="mission/f005-b-a",
        write_scope=("cyber_lion/example.py",),
        dependencies=(),
        evidence_refs=("authority:F005-B",),
    )
    values.update(overrides)
    return FleetCoordinationSpec(**values)


def request(**overrides) -> FleetPlanRequest:
    values = dict(
        request_id="plan-1",
        coordinator_id="coordinator-1",
        current_heads=(("DonkeyJJLove/ai_platform", BASE),),
        max_parallel=2,
    )
    values.update(overrides)
    return FleetPlanRequest(**values)


class FleetCoordinationContractTests(unittest.TestCase):
    def test_spec_is_immutable_and_digest_is_deterministic(self) -> None:
        value = spec().validate()
        self.assertEqual(value.digest(), spec().digest())
        self.assertEqual(len(value.digest()), 64)
        with self.assertRaises(dataclasses.FrozenInstanceError):
            value.mission_id = "other"  # type: ignore[misc]

    def test_write_scope_requires_canonical_concrete_paths(self) -> None:
        for bad in (
            ("../escape",),
            ("/absolute",),
            ("cyber_lion//x.py",),
            ("cyber_lion/./x.py",),
            ("cyber_lion/**",),
            ("cyber_lion\\x.py",),
        ):
            with self.subTest(path=bad):
                with self.assertRaises(FleetCoordinationContractError):
                    spec(write_scope=bad).validate()

    def test_dependency_identity_is_unique_and_cannot_self_reference(self) -> None:
        with self.assertRaises(FleetCoordinationContractError):
            spec(dependencies=("dep", "dep")).validate()
        with self.assertRaises(FleetCoordinationContractError):
            spec(dependencies=("mission-a",)).validate()

    def test_git_identity_is_exact_lowercase_sha_and_safe_branch(self) -> None:
        with self.assertRaises(FleetCoordinationContractError):
            spec(baseline_sha="A" * 40).validate()
        with self.assertRaises(FleetCoordinationContractError):
            spec(branch="refs/heads/mission/a").validate()
        with self.assertRaises(FleetCoordinationContractError):
            spec(branch="mission/a..b").validate()

    def test_plan_request_binds_unique_repository_heads_and_bounded_parallelism(self) -> None:
        self.assertEqual(request().head_map(), {"DonkeyJJLove/ai_platform": BASE})
        with self.assertRaises(FleetCoordinationContractError):
            request(current_heads=(
                ("DonkeyJJLove/ai_platform", BASE),
                ("DonkeyJJLove/ai_platform", BASE),
            )).validate()
        with self.assertRaises(FleetCoordinationContractError):
            request(max_parallel=101).validate()
        with self.assertRaises(FleetCoordinationContractError):
            request(max_parallel=True).validate()

    def test_dispatch_validation_binds_exact_spec_and_plan(self) -> None:
        mission = spec().validate()
        plan = request().validate()
        dispatch = FleetDispatch(
            dispatch_id="1" * 64,
            fencing_token="2" * 64,
            request_id=plan.request_id,
            coordinator_id=plan.coordinator_id,
            mission_id=mission.mission_id,
            drone_id=mission.drone_id,
            generation=1,
            repository=mission.repository,
            baseline_sha=mission.baseline_sha,
            baseline_tree_sha=mission.baseline_tree_sha,
            branch=mission.branch,
            write_scope=mission.write_scope,
            issued_at="2026-08-21T14:00:00+00:00",
        )
        dispatch.validate_for(mission, plan)
        with self.assertRaises(FleetCoordinationContractError):
            dataclasses.replace(dispatch, baseline_tree_sha="c" * 40).validate_for(mission, plan)


if __name__ == "__main__":
    unittest.main()
