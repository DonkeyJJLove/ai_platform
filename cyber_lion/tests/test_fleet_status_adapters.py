from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import inspect
from types import SimpleNamespace
import unittest

from cyber_lion.contracts.fleet_status import TrustedVerificationEvidence
from cyber_lion.contracts.fleet_status_sources import StatusSourceIdentity
from cyber_lion.enterprise.fleet_status_adapters import (
    AuthorityStatusView,
    CIStatusAdapter,
    CIStatusView,
    FleetControlStatusAdapter,
    HeartbeatStatusAdapter,
    HeartbeatStatusView,
    PersistentAuthorityStatusAdapter,
    RepositoryEffectStatusAdapter,
    RepositoryEffectView,
    RepositoryStateStatusAdapter,
    RepositoryStateView,
    RuntimeAttestationStatusAdapter,
    RuntimeAuthorityStatusAdapter,
    TrustedVerificationStatusAdapter,
)

NOW = datetime(2026, 8, 21, 10, 0, tzinfo=timezone.utc)
CLOCK = lambda: NOW


def identity(kind, source_id=None):
    return StatusSourceIdentity(
        source_id or f"source-{kind.lower()}", kind, f"instance-{kind.lower()}", "1"*64, "anchor-1"
    ).validate()


class FCPRegistry:
    def __init__(self):
        self._spec = SimpleNamespace(
            drone_id="drone-1", mission_id="mission-1", parent_mission_id="parent-1",
            repository="DonkeyJJLove/ai_platform", baseline_sha="a"*40, branch="mission/1",
            sandbox_id="sandbox-1", read_scope=("**",), write_scope=("cyber_lion/**",),
        )
    def mission_ids(self): return ("mission-1",)
    def spec(self, mission_id): return self._spec
    def state(self, mission_id): return "RUNNING"
    def snapshot(self): return (("mission-1", "RUNNING", 7),)


class Provider:
    def __init__(self, method, values):
        setattr(self, method, lambda: tuple(values))


class FleetStatusAdapterTests(unittest.TestCase):
    def test_fcp_counter_is_not_promoted_to_wall_clock_heartbeat(self):
        adapter = FleetControlStatusAdapter(identity("FLEET_CONTROL"), FCPRegistry(), CLOCK)
        result = adapter.read()
        self.assertEqual({o.dimension for o in result.observations}, {"IDENTITY", "MISSION"})
        mission = next(o for o in result.observations if o.dimension == "MISSION")
        self.assertEqual(mission.value_dict()["fcp_heartbeat_sequence"], "7")
        self.assertNotIn("HEARTBEAT", {o.dimension for o in result.observations})

    def test_runtime_attestation_maps_subject_to_executor_without_fabricating_baseline(self):
        runtime = SimpleNamespace(
            subject_id="executor-1", runtime_instance_id="runtime-1", repository="DonkeyJJLove/ai_platform",
            commit_sha="b"*40, run_id="11", run_attempt=1, mission_id="mission-1", artifact_digest="2"*64,
            implementation_digest="3"*64, attestation_digest="4"*64, provenance_ref="runtime-prov", trust_anchor_id="ta",
        )
        adapter = RuntimeAttestationStatusAdapter(
            identity("RUNTIME_ATTESTATION"), Provider("list_verified_runtime", (runtime,)), CLOCK
        )
        obs = adapter.read().observations[0]
        self.assertEqual(obs.executor_id, "executor-1")
        self.assertEqual(obs.runtime_id, "runtime-1")
        self.assertIsNone(obs.baseline_sha)
        self.assertNotIn("tree_sha", obs.value_dict())

    def test_runtime_authority_is_corroboration_not_active_permission(self):
        binding = SimpleNamespace(
            runtime_instance_id="runtime-1", provenance_ref="bind-prov", mission_id="mission-1",
            repository="DonkeyJJLove/ai_platform", base_sha="a"*40, head_sha="b"*40, grant_id="grant-1",
            authority_epoch=3, authority_state_version=9, authority_root_grant_digest="5"*64,
            binding_digest="6"*64,
        )
        adapter = RuntimeAuthorityStatusAdapter(
            identity("RUNTIME_AUTHORITY"), Provider("list_authority_bound_runtime", (binding,)), CLOCK
        )
        observations = adapter.read().observations
        authority = next(o for o in observations if o.dimension == "AUTHORITY")
        runtime = next(o for o in observations if o.dimension == "RUNTIME")
        self.assertEqual(authority.state, "BOUND")
        self.assertNotEqual(authority.state, "ACTIVE")
        self.assertEqual(runtime.value_dict()["commit_sha"], "b"*40)
        self.assertEqual(authority.value_dict()["base_sha"], "a"*40)

    def test_repository_source_distinguishes_baseline_from_live_branch_head(self):
        view = RepositoryStateView(
            "mission-1", "DonkeyJJLove/ai_platform", "mission/1",
            "a"*40, "b"*40, "c"*40, "d"*40,
            NOW.isoformat(), "repo-prov", "7"*64,
        )
        adapter = RepositoryStateStatusAdapter(
            identity("REPOSITORY"), Provider("list_repository_states", (view,)), CLOCK
        )
        obs = adapter.read().observations[0]
        values = obs.value_dict()
        self.assertEqual(obs.baseline_sha, "a"*40)
        self.assertEqual(values["baseline_tree_sha"], "b"*40)
        self.assertEqual(values["branch_head_sha"], "c"*40)
        self.assertEqual(values["branch_tree_sha"], "d"*40)

    def test_empty_provider_read_uses_current_trusted_adapter_time(self):
        adapter = PersistentAuthorityStatusAdapter(
            identity("AUTHORITY_STATE"), Provider("list_authority_status", ()), CLOCK
        )
        read = adapter.read()
        self.assertEqual(read.source_observed_at, NOW.isoformat())
        self.assertEqual(read.observations, ())

    def test_heartbeat_preserves_source_record_time_inside_evidence(self):
        view = HeartbeatStatusView("mission-1", "runtime-1", 4, 30, NOW.isoformat(), "hb-prov", "8"*64)
        adapter = HeartbeatStatusAdapter(
            identity("HEARTBEAT"), Provider("list_heartbeat_status", (view,)), CLOCK
        )
        obs = adapter.read().observations[0]
        self.assertEqual(obs.value_dict()["heartbeat_observed_at"], NOW.isoformat())
        self.assertEqual(obs.value_dict()["sequence"], "4")

    def test_verification_adapter_preserves_exact_trusted_evidence_identity(self):
        evidence = TrustedVerificationEvidence(
            "verify-1", "mission-1", "drone-1", "executor-1", "verifier-1",
            "1"*64, "2"*64, "anchor-v", "3"*64, "PASS", "4"*64,
            "verify-prov", "ANCHORED", NOW.isoformat(),
        )
        adapter = TrustedVerificationStatusAdapter(
            identity("VERIFICATION"), Provider("list_verification_evidence", (evidence,)), CLOCK
        )
        obs = adapter.read().observations[0]
        self.assertEqual(obs.state, "PASS")
        self.assertEqual(obs.executor_id, "executor-1")
        self.assertEqual(obs.value_dict()["verifier_id"], "verifier-1")

    def test_effect_ci_and_authority_adapters_remain_descriptive(self):
        effect = RepositoryEffectView(
            "mission-1", "effect-1", "APPLIED", "DonkeyJJLove/ai_platform",
            "a"*40, "b"*40, "b"*40, NOW.isoformat(), "effect-prov", "9"*64,
        )
        e = RepositoryEffectStatusAdapter(identity("EFFECT"), Provider("list_effect_states", (effect,)), CLOCK).read()
        self.assertEqual(e.observations[0].state, "APPLIED")
        ci = CIStatusView(
            "mission-1", "DonkeyJJLove/ai_platform", "b"*40, "Cyber-Lion Core", "1", "SUCCESS",
            NOW.isoformat(), "ci-prov", "a"*64,
        )
        c = CIStatusAdapter(identity("CI"), Provider("list_ci_status", (ci,)), CLOCK).read()
        self.assertEqual(c.observations[0].state, "SUCCESS")
        authority = AuthorityStatusView("mission-1", "ACTIVE", "grant-1", 1, 2, NOW.isoformat(), "auth-prov", "b"*64)
        a = PersistentAuthorityStatusAdapter(identity("AUTHORITY_STATE"), Provider("list_authority_status", (authority,)), CLOCK).read()
        self.assertEqual(a.observations[0].state, "ACTIVE")

    def test_adapter_surface_has_no_status_store_or_authority_mutation_method(self):
        forbidden = {"grant", "revoke", "execute", "acquire", "release", "project", "dispatch"}
        for cls in (
            FleetControlStatusAdapter, RuntimeAttestationStatusAdapter, RuntimeAuthorityStatusAdapter,
            PersistentAuthorityStatusAdapter, RepositoryEffectStatusAdapter, TrustedVerificationStatusAdapter,
            RepositoryStateStatusAdapter, CIStatusAdapter, HeartbeatStatusAdapter,
        ):
            public = {name for name, _ in inspect.getmembers(cls) if not name.startswith("_")}
            self.assertTrue(forbidden.isdisjoint(public), f"{cls.__name__}: {public & forbidden}")


if __name__ == "__main__":
    unittest.main()
