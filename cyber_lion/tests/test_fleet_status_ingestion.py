from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import tempfile
from pathlib import Path
import unittest

from cyber_lion.contracts.fleet_status import TrustedVerificationEvidence, VerificationTrustPins
from cyber_lion.contracts.fleet_status_sources import (
    ReconciledStatusFact,
    StatusSourceIdentity,
    StatusSourceObservation,
    StatusSourcePin,
    StatusSourceRead,
)
from cyber_lion.enterprise.fleet_status_ingestion import FleetStatusIngestion, FleetStatusIngestionError
from cyber_lion.enterprise.fleet_status_projection import FleetStatusProjector
from cyber_lion.enterprise.fleet_status_sources import StatusSourceReconciler, StatusSourceTrustRegistry
from cyber_lion.enterprise.fleet_status_state import FleetStatusStore


class Clock:
    def __init__(self):
        self.value = datetime(2026, 8, 21, 10, 0, tzinfo=timezone.utc)
    def __call__(self): return self.value
    def tick(self, seconds=1): self.value += timedelta(seconds=seconds)


class VerificationSource:
    def __init__(self):
        self.evidence = TrustedVerificationEvidence(
            "verify-1", "mission-1", "drone-1", "executor-1", "verifier-1",
            "1"*64, "2"*64, "anchor-v", "3"*64, "PASS", "4"*64,
            "verify-prov", "ANCHORED", "2026-08-21T10:00:00+00:00",
        )
    def resolve(self, verification_id):
        if verification_id != self.evidence.verification_id:
            raise KeyError(verification_id)
        return self.evidence


PINS = VerificationTrustPins("verifier-1", "1"*64, "2"*64, "anchor-v", "3"*64)


def sid(source_id, kind, marker):
    identity = StatusSourceIdentity(source_id, kind, f"instance-{source_id}", marker*64, f"anchor-{source_id}").validate()
    pin = StatusSourcePin(
        identity.source_id, identity.source_kind, identity.source_instance_id,
        identity.source_implementation_digest, identity.trust_anchor_id, identity.digest(),
    ).validate()
    return identity, pin


def items(**values):
    out = []
    for key, value in values.items():
        if isinstance(value, (tuple, list)):
            raw = json.dumps(list(value), separators=(",", ":"))
        elif value is None:
            raw = "null"
        else:
            raw = str(value)
        out.append((key, raw))
    return tuple(sorted(out))


def digest(text):
    return sha256(text.encode()).hexdigest()


def obs(source_id, mission, dimension, state, *, drone=None, executor=None, runtime=None, repository=None, baseline=None, value_items=(), suffix=""):
    evidence = digest(f"{source_id}|{mission}|{dimension}|{state}|{suffix}|{value_items}")
    return StatusSourceObservation(
        digest(f"obs|{source_id}|{mission}|{dimension}|{suffix}"), mission, drone, executor, runtime,
        repository, baseline, dimension, state, value_items,
        f"prov:{source_id}:{mission}:{dimension}:{suffix or '1'}", evidence, "ANCHORED",
    ).validate()


class FixedAdapter:
    def __init__(self, identity, clock, observations=()):
        self._identity = identity
        self.clock = clock
        self.observations = tuple(observations)
        self.fail = False
    @property
    def source_identity(self): return self._identity
    def read(self):
        if self.fail:
            raise RuntimeError("source down")
        return StatusSourceRead(self._identity, self.clock().isoformat(), self.observations).validate()


def mission_obs(source_id="fcp", state="RUNNING", mission="mission-1", drone="drone-1", branch="mission/1", baseline="a"*40):
    identity = obs(
        source_id, mission, "IDENTITY", "OBSERVED", drone=drone,
        repository="DonkeyJJLove/ai_platform", baseline=baseline,
        value_items=items(
            baseline_sha=baseline, branch=branch, drone_id=drone, parent_mission_id="parent-1",
            read_scope=("**",), repository="DonkeyJJLove/ai_platform", sandbox_id=f"sandbox-{mission}",
            write_scope=(f"work/{mission}/**",),
        ), suffix="identity",
    )
    mission_state = obs(
        source_id, mission, "MISSION", state, drone=drone,
        repository="DonkeyJJLove/ai_platform", baseline=baseline,
        value_items=items(closure_state="OPEN", dependency_state="UNKNOWN", phase="IMPLEMENT"), suffix="mission",
    )
    return identity, mission_state


def runtime_obs(source_id="runtime", mission="mission-1", executor="executor-1", runtime="runtime-1", commit="c"*40):
    return obs(
        source_id, mission, "RUNTIME", "VERIFIED", executor=executor, runtime=runtime,
        repository="DonkeyJJLove/ai_platform",
        value_items=items(commit_sha=commit, executor_id=executor, repository="DonkeyJJLove/ai_platform", runtime_id=runtime),
        suffix=runtime,
    )


def repository_obs(source_id="repo", mission="mission-1", branch="mission/1", baseline="a"*40, tree="b"*40, head="c"*40):
    return obs(
        source_id, mission, "REPOSITORY", "OBSERVED", repository="DonkeyJJLove/ai_platform", baseline=baseline,
        value_items=items(
            baseline_sha=baseline, baseline_tree_sha=tree, branch=branch, branch_head_sha=head,
            branch_tree_sha="d"*40, repository="DonkeyJJLove/ai_platform",
        ), suffix="repo",
    )


class FleetStatusIngestionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "fleet.sqlite3"
        self.clock = Clock()
        self.verify_source = VerificationSource()
        self.store = FleetStatusStore(
            self.db, registry_instance_id="registry-1", clock=self.clock,
            verification_source=self.verify_source, verification_pins=PINS,
        )
        self.identities = {}
        self.pins = {}
        for source_id, kind, marker in (
            ("fcp", "FLEET_CONTROL", "1"), ("runtime", "RUNTIME_ATTESTATION", "2"),
            ("repo", "REPOSITORY", "3"), ("verify", "VERIFICATION", "4"),
            ("effect", "EFFECT", "5"), ("reconcile", "RECONCILIATION", "6"),
            ("authority-a", "AUTHORITY_STATE", "7"), ("authority-b", "AUTHORITY_STATE", "8"),
            ("ci", "CI", "9"), ("heartbeat", "HEARTBEAT", "a"),
        ):
            self.identities[source_id], self.pins[source_id] = sid(source_id, kind, marker)

    def tearDown(self):
        self.store.close(); self.tmp.cleanup()

    def ingestion(self, adapters):
        pins = tuple(self.pins[a.source_identity.source_id] for a in adapters)
        return FleetStatusIngestion(
            self.store, adapters=tuple(adapters), trust_registry=StatusSourceTrustRegistry(pins),
            reconciler=StatusSourceReconciler(), clock=self.clock,
        )

    def base_adapters(self, state="RUNNING", executor="executor-1", runtime="runtime-1", baseline="a"*40):
        fcp = FixedAdapter(self.identities["fcp"], self.clock, mission_obs(state=state, baseline=baseline))
        rt = FixedAdapter(self.identities["runtime"], self.clock, (runtime_obs(executor=executor, runtime=runtime),))
        repo = FixedAdapter(self.identities["repo"], self.clock, (repository_obs(baseline=baseline),))
        return fcp, rt, repo

    def test_complete_identity_requires_fcp_runtime_and_repository_baseline(self):
        cycle = self.ingestion(self.base_adapters()).run_cycle()
        row = self.store.identity_row("mission-1")
        self.assertIsNotNone(row)
        self.assertEqual(row["executor_id"], "executor-1")
        self.assertEqual(row["baseline_tree_sha"], "b"*40)
        self.assertEqual(self.store.runtime_row("mission-1")["runtime_id"], "runtime-1")
        self.assertNotIn("RUNTIME", {(x.mission_id, x.dimension)[1] for x in cycle.conflicts})

    def test_fcp_only_is_not_promoted_to_fake_canonical_drone(self):
        fcp = FixedAdapter(self.identities["fcp"], self.clock, mission_obs())
        self.ingestion((fcp,)).run_cycle()
        snap = FleetStatusProjector(self.store).snapshot()
        self.assertEqual(snap.aggregate.total_known_drones, 0)
        kinds = {a.anomaly_type for a in snap.anomalies}
        self.assertIn("MISSING_STATUS_SOURCE_RUNTIME", kinds)
        self.assertIn("MISSING_STATUS_SOURCE_REPOSITORY", kinds)

    def test_absent_wall_clock_heartbeat_is_not_fabricated_and_runtime_is_unreachable(self):
        self.ingestion(self.base_adapters()).run_cycle()
        record = FleetStatusProjector(self.store).snapshot().drone_records[0]
        self.assertEqual(record.mission_status, "UNREACHABLE")
        self.assertEqual(record.heartbeat_state, "UNKNOWN")
        self.assertNotEqual(record.mission_phase, "IDLE")

    def test_real_heartbeat_source_can_make_runtime_reachable_then_stale(self):
        fcp, rt, repo = self.base_adapters()
        heartbeat = obs(
            "heartbeat", "mission-1", "HEARTBEAT", "OBSERVED", runtime="runtime-1",
            value_items=items(deadline_seconds=10, heartbeat_observed_at=self.clock().isoformat(), runtime_id="runtime-1", sequence=1),
            suffix="hb1",
        )
        hb = FixedAdapter(self.identities["heartbeat"], self.clock, (heartbeat,))
        ingestion = self.ingestion((fcp, rt, repo, hb))
        ingestion.run_cycle()
        record = FleetStatusProjector(self.store).snapshot().drone_records[0]
        self.assertEqual(record.heartbeat_state, "HEALTHY")
        self.assertEqual(record.mission_status, "RUNNING")
        self.clock.tick(11)
        record = FleetStatusProjector(self.store).snapshot().drone_records[0]
        self.assertEqual(record.heartbeat_state, "STALE")
        self.assertEqual(record.mission_status, "UNREACHABLE")

    def test_two_authority_owners_disagree_and_snapshot_degrades_to_unknown(self):
        fcp, rt, repo = self.base_adapters()
        a1 = FixedAdapter(self.identities["authority-a"], self.clock, (
            obs("authority-a", "mission-1", "AUTHORITY", "ACTIVE", value_items=items(grant_id="g1"), suffix="a"),
        ))
        a2 = FixedAdapter(self.identities["authority-b"], self.clock, (
            obs("authority-b", "mission-1", "AUTHORITY", "REVOKED", value_items=items(grant_id="g1"), suffix="b"),
        ))
        cycle = self.ingestion((fcp, rt, repo, a1, a2)).run_cycle()
        self.assertTrue(any(c.conflict_type == "SOURCE_PROVENANCE_CONFLICT" and c.dimension == "AUTHORITY" for c in cycle.conflicts))
        record = FleetStatusProjector(self.store).snapshot().drone_records[0]
        self.assertEqual(record.authority_state, "UNKNOWN")
        self.assertEqual(record.evidence_state, "CONFLICT")

    def test_empty_new_source_snapshot_clears_old_positive_authority_to_unknown(self):
        fcp, rt, repo = self.base_adapters()
        authority = FixedAdapter(self.identities["authority-a"], self.clock, (
            obs("authority-a", "mission-1", "AUTHORITY", "ACTIVE", value_items=items(grant_id="g1"), suffix="active"),
        ))
        ingestion = self.ingestion((fcp, rt, repo, authority))
        ingestion.run_cycle()
        first = FleetStatusProjector(self.store).snapshot().drone_records[0]
        self.assertEqual(first.authority_state, "UNUSABLE_STALE_OBSERVABILITY")
        self.clock.tick()
        authority.observations = ()
        ingestion.run_cycle()
        second = FleetStatusProjector(self.store).snapshot().drone_records[0]
        self.assertEqual(second.authority_state, "UNKNOWN")

    def test_ci_success_does_not_mint_done(self):
        fcp, rt, repo = self.base_adapters(state="RUNNING")
        ci = FixedAdapter(self.identities["ci"], self.clock, (
            obs("ci", "mission-1", "CI", "SUCCESS", repository="DonkeyJJLove/ai_platform", baseline="c"*40,
                value_items=items(head_sha="c"*40, run_id="1", workflow="Cyber-Lion Core"), suffix="ci"),
        ))
        self.ingestion((fcp, rt, repo, ci)).run_cycle()
        record = FleetStatusProjector(self.store).snapshot().drone_records[0]
        self.assertNotEqual(record.mission_status, "DONE")

    def test_applied_effect_does_not_mint_done(self):
        fcp, rt, repo = self.base_adapters(state="RUNNING")
        effect = FixedAdapter(self.identities["effect"], self.clock, (
            obs("effect", "mission-1", "EFFECT", "APPLIED", repository="DonkeyJJLove/ai_platform", baseline="a"*40,
                value_items=items(effect_id="e1", candidate_commit_sha="c"*40), suffix="effect"),
        ))
        self.ingestion((fcp, rt, repo, effect)).run_cycle()
        record = FleetStatusProjector(self.store).snapshot().drone_records[0]
        self.assertNotEqual(record.mission_status, "DONE")
        self.assertEqual(record.effect_state, "APPLIED")

    def test_done_without_verification_is_detected_and_not_positive(self):
        fcp, rt, repo = self.base_adapters(state="DONE")
        cycle = self.ingestion((fcp, rt, repo)).run_cycle()
        self.assertTrue(any(c.conflict_type == "DONE_WITHOUT_VERIFICATION" for c in cycle.conflicts))
        record = FleetStatusProjector(self.store).snapshot().drone_records[0]
        self.assertNotEqual(record.mission_status, "DONE")

    def test_done_with_verification_but_missing_effect_reconciliation_is_denied(self):
        fcp, rt, repo = self.base_adapters(state="DONE")
        verification = obs(
            "verify", "mission-1", "VERIFICATION", "PASS", drone="drone-1", executor="executor-1",
            value_items=items(
                executor_id="executor-1", verification_id="verify-1", verifier_id="verifier-1",
                verifier_identity_digest="1"*64, verifier_implementation_digest="2"*64,
                trust_anchor_id="anchor-v", trust_anchor_digest="3"*64,
            ), suffix="verify",
        )
        verify = FixedAdapter(self.identities["verify"], self.clock, (verification,))
        cycle = self.ingestion((fcp, rt, repo, verify)).run_cycle()
        self.assertTrue(any(c.conflict_type == "DONE_WITH_UNRECONCILED_EFFECT" for c in cycle.conflicts))
        record = FleetStatusProjector(self.store).snapshot().drone_records[0]
        self.assertNotEqual(record.mission_status, "DONE")
        self.assertEqual(record.verification_state, "PASS")

    def test_done_requires_verification_and_terminal_effect_reconciliation(self):
        fcp, rt, repo = self.base_adapters(state="DONE")
        verification = obs(
            "verify", "mission-1", "VERIFICATION", "PASS", drone="drone-1", executor="executor-1",
            value_items=items(
                executor_id="executor-1", verification_id="verify-1", verifier_id="verifier-1",
                verifier_identity_digest="1"*64, verifier_implementation_digest="2"*64,
                trust_anchor_id="anchor-v", trust_anchor_digest="3"*64,
            ), suffix="verify",
        )
        verify = FixedAdapter(self.identities["verify"], self.clock, (verification,))
        effect = FixedAdapter(self.identities["effect"], self.clock, (
            obs("effect", "mission-1", "EFFECT", "APPLIED", repository="DonkeyJJLove/ai_platform",
                value_items=items(effect_id="e1", candidate_commit_sha="c"*40), suffix="e"),
        ))
        rec = FixedAdapter(self.identities["reconcile"], self.clock, (
            obs("reconcile", "mission-1", "RECONCILIATION", "RESOLVED", value_items=(), suffix="r"),
        ))
        heartbeat = obs(
            "heartbeat", "mission-1", "HEARTBEAT", "OBSERVED", runtime="runtime-1",
            value_items=items(deadline_seconds=60, heartbeat_observed_at=self.clock().isoformat(), runtime_id="runtime-1", sequence=1),
            suffix="done-hb",
        )
        hb = FixedAdapter(self.identities["heartbeat"], self.clock, (heartbeat,))
        cycle = self.ingestion((fcp, rt, repo, verify, effect, rec, hb)).run_cycle()
        self.assertFalse(any(c.conflict_type.startswith("DONE_") for c in cycle.conflicts))
        record = FleetStatusProjector(self.store).snapshot().drone_records[0]
        self.assertEqual(record.mission_status, "DONE")
        self.assertEqual(record.verification_state, "PASS")

    def test_runtime_substitution_is_detected_against_immutable_binding(self):
        fcp, rt, repo = self.base_adapters()
        ingestion = self.ingestion((fcp, rt, repo))
        ingestion.run_cycle()
        self.clock.tick()
        rt.observations = (runtime_obs(runtime="runtime-2"),)
        cycle = ingestion.run_cycle()
        self.assertTrue(any(c.conflict_type == "RUNTIME_SUBSTITUTION" for c in cycle.conflicts))
        self.assertEqual(self.store.runtime_row("mission-1")["runtime_id"], "runtime-1")
        record = FleetStatusProjector(self.store).snapshot().drone_records[0]
        self.assertEqual(record.mission_status, "UNREACHABLE")
        self.assertEqual(record.evidence_state, "CONFLICT")

    def test_stale_baseline_is_detected_from_repository_source(self):
        fcp, rt, _ = self.base_adapters(baseline="a"*40)
        repo = FixedAdapter(self.identities["repo"], self.clock, (repository_obs(baseline="f"*40),))
        cycle = self.ingestion((fcp, rt, repo)).run_cycle()
        self.assertTrue(any(c.conflict_type == "STALE_BASELINE" for c in cycle.conflicts))
        self.assertIsNone(self.store.identity_row("mission-1"))


    def test_duplicate_drone_executor_branch_and_lease_conflicts_are_detected(self):
        facts = (
            ReconciledStatusFact("m1", "IDENTITY", "REGISTERED", items(branch="same", drone_id="d1", repository="DonkeyJJLove/ai_platform", baseline_sha="a"*40, parent_mission_id="p", read_scope="**", sandbox_id="s1", write_scope="a/**"), ("fcp",), ("p1",), "OBSERVED").validate(),
            ReconciledStatusFact("m2", "IDENTITY", "REGISTERED", items(branch="same", drone_id="d1", repository="DonkeyJJLove/ai_platform", baseline_sha="a"*40, parent_mission_id="p", read_scope="**", sandbox_id="s2", write_scope="b/**"), ("fcp",), ("p2",), "OBSERVED").validate(),
            ReconciledStatusFact("m1", "MISSION", "RUNNING", items(closure_state="OPEN", dependency_state="READY", phase="IMPLEMENT"), ("fcp",), ("p1",), "OBSERVED").validate(),
            ReconciledStatusFact("m2", "MISSION", "RUNNING", items(closure_state="OPEN", dependency_state="READY", phase="IMPLEMENT"), ("fcp",), ("p2",), "OBSERVED").validate(),
            ReconciledStatusFact("m1", "RUNTIME", "VERIFIED", items(executor_id="executor-x", runtime_id="r1", repository="DonkeyJJLove/ai_platform", commit_sha="b"*40), ("rt",), ("r1p",), "ANCHORED").validate(),
            ReconciledStatusFact("m2", "RUNTIME", "VERIFIED", items(executor_id="executor-x", runtime_id="r2", repository="DonkeyJJLove/ai_platform", commit_sha="b"*40), ("rt",), ("r2p",), "ANCHORED").validate(),
            ReconciledStatusFact("m1", "LEASE", "ACTIVE", items(lease_id="l1", lease_type="PATH", repository="DonkeyJJLove/ai_platform", resource="cyber_lion"), ("lease",), ("l1p",), "OBSERVED").validate(),
            ReconciledStatusFact("m2", "LEASE", "ACTIVE", items(lease_id="l2", lease_type="PATH", repository="DonkeyJJLove/ai_platform", resource="cyber_lion/tests"), ("lease",), ("l2p",), "OBSERVED").validate(),
        )
        conflicts = StatusSourceReconciler().detect_global_conflicts(facts, observed_at=self.clock().isoformat())
        kinds = {c.conflict_type for c in conflicts}
        self.assertIn("DUPLICATE_DRONE_ID", kinds)
        self.assertIn("DUPLICATE_EXECUTOR_ID", kinds)
        self.assertIn("DUPLICATE_BRANCH_OWNER", kinds)
        self.assertIn("OVERLAPPING_WRITE_LEASE", kinds)

    def test_duplicate_mission_owner_is_detected_before_projection(self):
        i2, p2 = sid("fcp-2", "FLEET_CONTROL", "b")
        trust = StatusSourceTrustRegistry((self.pins["fcp"], p2))
        first = FixedAdapter(self.identities["fcp"], self.clock, mission_obs())
        second = FixedAdapter(i2, self.clock, (
            obs("fcp-2", "mission-1", "IDENTITY", "REGISTERED", drone="drone-1", repository="DonkeyJJLove/ai_platform", baseline="a"*40, value_items=items(branch="mission/1", drone_id="drone-1", parent_mission_id="parent-1", read_scope="**", repository="DonkeyJJLove/ai_platform", sandbox_id="sandbox-1", write_scope="cyber_lion/**"), suffix="id2"),
            obs("fcp-2", "mission-1", "MISSION", "RUNNING", drone="drone-1", repository="DonkeyJJLove/ai_platform", baseline="a"*40, value_items=items(closure_state="OPEN", dependency_state="READY", fcp_heartbeat_sequence=1, phase="IMPLEMENT"), suffix="m2"),
        ))
        ingestion = FleetStatusIngestion(self.store, adapters=(first, second), trust_registry=trust, reconciler=StatusSourceReconciler(), clock=self.clock)
        cycle = ingestion.run_cycle()
        self.assertTrue(any(c.conflict_type == "DUPLICATE_MISSION_OWNER" for c in cycle.conflicts))
        self.assertIsNone(self.store.identity_row("mission-1"))

    def test_source_failure_occurs_before_any_journal_write(self):
        fcp, rt, repo = self.base_adapters()
        rt.fail = True
        ingestion = self.ingestion((fcp, rt, repo))
        with self.assertRaises(FleetStatusIngestionError):
            ingestion.run_cycle()
        self.assertEqual(self.store.source_checkpoints(), [])

    def test_run_cycle_has_no_caller_provider_or_clock_selection(self):
        import inspect
        sig = inspect.signature(FleetStatusIngestion.run_cycle)
        self.assertEqual(list(sig.parameters), ["self"])


if __name__ == "__main__":
    unittest.main()
