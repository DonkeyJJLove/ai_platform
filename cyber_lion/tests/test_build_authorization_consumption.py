from dataclasses import replace
from datetime import datetime, timezone
import unittest
from unittest.mock import patch

from cyber_lion.contracts.build_authorization_consumption import compute_consumption_replay_digest
from cyber_lion.contracts.candidate_build_authorization import (
    BoundedCandidateBuildAuthorization,
    TrustedRepositoryBaseline,
    canonical_repo_path_resource,
)
from cyber_lion.enterprise.candidate_build_authorization import (
    LiveAdmittedResourceAuthority,
    LiveResourceAuthorityAdmission,
)
from cyber_lion.enterprise.build_authorization_consumption import (
    BuildAuthorizationConsumptionEngine,
    BuildAuthorizationConsumptionError,
    PersistentBuildAuthorizationConsumptionReplayGuard,
)

REPO = "DonkeyJJLove/ai_platform"
PATH = "cyber_lion/example.py"
RESOURCE = canonical_repo_path_resource(REPO, PATH)
SHA = "1" * 40
TREE = "2" * 40
NOW = datetime(2026, 8, 25, 1, 0, tzinfo=timezone.utc)


class BaselineSource:
    def __init__(self, baseline): self.baseline = baseline
    def current(self, repository): return self.baseline


class F005Source:
    def __init__(self, state=None):
        self.state = state or {"state": "QUARANTINED", "effect_authority": "DENY"}
    def current(self): return self.state


class ReplayGuard:
    def __init__(self): self.seen = set()
    def consume(self, replay_digest, *, consumed_at):
        if replay_digest in self.seen: return False
        self.seen.add(replay_digest); return True


class ReplayStore:
    def __init__(self): self.calls = []
    def consume_replay(self, domain, digest, consumed_at):
        self.calls.append((domain, digest, consumed_at)); return True


def make_live(**changes):
    values = dict(
        repository=REPO,
        mission_id="E004",
        grant_id="grant-1",
        action="BUILD_CANDIDATE",
        resource_scope=(RESOURCE,),
        lineage_digest="3" * 64,
        provenance_id="trusted-control-plane:1",
        epoch=4,
        epoch_state_version=8,
        authority_ceiling="local_write",
        root_grant_id="root-1",
        root_grant_digest="4" * 64,
        authenticated_grant_digests=("5" * 64,),
        leaf_key_id="key-1",
        leaf_algorithm="ed25519",
        replay_digest="6" * 64,
        admitted_at="2026-08-25T00:30:00+00:00",
    )
    values.update(changes)
    return LiveAdmittedResourceAuthority(**values).validate()


def make_baseline(**changes):
    values = dict(repository=REPO, master_sha=SHA, master_tree_sha=TREE, observed_at="2026-08-25T00:45:00+00:00")
    values.update(changes)
    return TrustedRepositoryBaseline(**values).validate()


def make_authorization(live=None, baseline=None, **changes):
    live = live or make_live(); baseline = baseline or make_baseline()
    issuance = "7" * 64
    values = dict(
        schema_version="1.0.0",
        authorization_id=f"cba:{issuance}",
        admission_request_id="gca:1",
        admission_request_digest="8" * 64,
        gate_request_id="gate-request-1",
        gate_request_digest="9" * 64,
        gate_event_id="gate-event-1",
        gate_decision_digest="a" * 64,
        pdp_receipt_id="receipt-1",
        pdp_request_id="gate-request-1",
        pdp_request_digest="9" * 64,
        pdp_decision_digest="a" * 64,
        pdp_replay_key="b" * 64,
        policy_binding="policy:abc",
        grant_id=live.grant_id,
        leaf_grant_digest=live.leaf_grant_digest,
        authority_lineage_digest=live.lineage_digest,
        authority_provenance_id=live.provenance_id,
        authority_epoch=live.epoch,
        authority_state_version=live.epoch_state_version,
        root_grant_id=live.root_grant_id,
        root_grant_digest=live.root_grant_digest,
        live_admission_digest=live.digest(),
        authority_admitted_at=live.admitted_at,
        repository=REPO,
        baseline_master_sha=baseline.master_sha,
        baseline_master_tree_sha=baseline.master_tree_sha,
        baseline_observation_digest=baseline.digest(),
        candidate_scope=(PATH,),
        resource_scope=(RESOURCE,),
        action="BUILD_CANDIDATE",
        requested_authority="local_write",
        effective_authority_ceiling="local_write",
        valid_from="2026-08-25T00:00:00+00:00",
        expires_at="2026-08-26T00:00:00+00:00",
        issuance_replay_digest=issuance,
    )
    values.update(changes)
    return BoundedCandidateBuildAuthorization(**values).sealed()


def make_engine(live=None, baseline=None, f005=None, replay=None):
    admitted = live or make_live(); current_baseline = baseline or make_baseline()
    live_admission = object.__new__(LiveResourceAuthorityAdmission)
    engine = BuildAuthorizationConsumptionEngine(
        live_authority=live_admission,
        baseline_source=BaselineSource(current_baseline),
        f005_state_source=F005Source(f005),
        replay_guard=replay or ReplayGuard(),
    )
    return engine, live_admission, admitted


class BuildAuthorizationConsumptionTests(unittest.TestCase):
    def test_issue_permit_happy_path_and_no_effect_surface(self):
        live = make_live(); baseline = make_baseline(); auth = make_authorization(live, baseline)
        engine, admission, _ = make_engine(live, baseline)
        with patch.object(LiveResourceAuthorityAdmission, "revalidate", return_value=live):
            permit = engine.issue_permit(authorization=auth, admitted_authority=live, trusted_now=NOW)
        expected_replay = compute_consumption_replay_digest(
            authorization_id=auth.authorization_id,
            authorization_digest=auth.authorization_digest,
            issuance_replay_digest=auth.issuance_replay_digest,
            repository=auth.repository,
            baseline_master_sha=auth.baseline_master_sha,
            baseline_master_tree_sha=auth.baseline_master_tree_sha,
            baseline_observation_digest=auth.baseline_observation_digest,
            current_baseline_digest=baseline.digest(),
            candidate_scope=auth.candidate_scope,
            resource_scope=auth.resource_scope,
            action="BUILD_CANDIDATE",
            grant_id=auth.grant_id,
            leaf_grant_digest=auth.leaf_grant_digest,
            authority_lineage_digest=auth.authority_lineage_digest,
            authority_provenance_id=auth.authority_provenance_id,
            authority_epoch=auth.authority_epoch,
            authority_state_version=auth.authority_state_version,
            root_grant_id=auth.root_grant_id,
            root_grant_digest=auth.root_grant_digest,
            live_admission_digest=auth.live_admission_digest,
            current_authority_digest=live.digest(),
            authorization_valid_from=auth.valid_from,
            authorization_expires_at=auth.expires_at,
        )
        self.assertEqual(permit.authorization_digest, auth.authorization_digest)
        self.assertEqual(permit.consumption_replay_digest, expected_replay)
        self.assertEqual(permit.consumption_replay_digest, permit.compute_consumption_replay_digest())
        self.assertEqual(permit.consumption_permit_id, f"cbcp:{permit.consumption_replay_digest}")
        self.assertEqual((permit.authority_effect, permit.execution_effect, permit.repository_ref_effect, permit.external_effect), ("NONE", "NONE", "NONE", "NONE"))
        engine.assert_no_effect_surface()

    def test_duplicate_consumption_denied(self):
        live = make_live(); baseline = make_baseline(); auth = make_authorization(live, baseline); replay = ReplayGuard()
        engine, _, _ = make_engine(live, baseline, replay=replay)
        with patch.object(LiveResourceAuthorityAdmission, "revalidate", return_value=live):
            engine.issue_permit(authorization=auth, admitted_authority=live, trusted_now=NOW)
            with self.assertRaisesRegex(BuildAuthorizationConsumptionError, "replay denied"):
                engine.issue_permit(authorization=auth, admitted_authority=live, trusted_now=NOW)

    def test_baseline_sha_and_tree_drift_denied(self):
        live = make_live(); old = make_baseline(); auth = make_authorization(live, old)
        for drift in (make_baseline(master_sha="f" * 40), make_baseline(master_tree_sha="e" * 40)):
            replay = ReplayGuard(); engine, _, _ = make_engine(live, drift, replay=replay)
            with patch.object(LiveResourceAuthorityAdmission, "revalidate", return_value=live):
                with self.assertRaisesRegex(BuildAuthorizationConsumptionError, "baseline stale"):
                    engine.issue_permit(authorization=auth, admitted_authority=live, trusted_now=NOW)
            self.assertEqual(replay.seen, set())

    def test_authority_epoch_state_root_and_lineage_substitution_denied(self):
        base_live = make_live(); baseline = make_baseline(); auth = make_authorization(base_live, baseline)
        variants = (
            make_live(epoch=5), make_live(epoch_state_version=9),
            make_live(root_grant_digest="d" * 64), make_live(lineage_digest="e" * 64),
            make_live(provenance_id="trusted-control-plane:other"),
        )
        for current in variants:
            replay = ReplayGuard(); engine, _, _ = make_engine(base_live, baseline, replay=replay)
            with patch.object(LiveResourceAuthorityAdmission, "revalidate", return_value=current):
                with self.assertRaisesRegex(BuildAuthorizationConsumptionError, "binding mismatch"):
                    engine.issue_permit(authorization=auth, admitted_authority=base_live, trusted_now=NOW)
            self.assertEqual(replay.seen, set())

    def test_revoked_or_expired_revalidation_failure_denied(self):
        live = make_live(); baseline = make_baseline(); auth = make_authorization(live, baseline)
        replay = ReplayGuard(); engine, _, _ = make_engine(live, baseline, replay=replay)
        with patch.object(LiveResourceAuthorityAdmission, "revalidate", side_effect=RuntimeError("revoked")):
            with self.assertRaisesRegex(BuildAuthorizationConsumptionError, "revalidation failed"):
                engine.issue_permit(authorization=auth, admitted_authority=live, trusted_now=NOW)
        self.assertEqual(replay.seen, set())
        expired = make_authorization(live, baseline, expires_at="2026-08-25T00:59:00+00:00")
        with self.assertRaisesRegex(BuildAuthorizationConsumptionError, "expired"):
            engine.issue_permit(authorization=expired, admitted_authority=live, trusted_now=NOW)
        self.assertEqual(replay.seen, set())

    def test_f005_dependency_injection_denied_before_replay(self):
        live = make_live(); baseline = make_baseline(); auth = make_authorization(live, baseline); replay = ReplayGuard()
        engine, _, _ = make_engine(live, baseline, f005={"state": "ACTIVE", "effect_authority": "ALLOW"}, replay=replay)
        with patch.object(LiveResourceAuthorityAdmission, "revalidate", return_value=live):
            with self.assertRaisesRegex(BuildAuthorizationConsumptionError, "F005 quarantine"):
                engine.issue_permit(authorization=auth, admitted_authority=live, trusted_now=NOW)
        self.assertEqual(replay.seen, set())

    def test_authorization_substitution_denied_before_replay(self):
        live = make_live(); baseline = make_baseline(); auth = make_authorization(live, baseline)
        forged = replace(auth, authorization_digest="0" * 64)
        replay = ReplayGuard(); engine, _, _ = make_engine(live, baseline, replay=replay)
        with self.assertRaises(BuildAuthorizationConsumptionError):
            engine.issue_permit(authorization=forged, admitted_authority=live, trusted_now=NOW)
        self.assertEqual(replay.seen, set())

    def test_persistent_guard_uses_separate_consumption_domain(self):
        store = ReplayStore(); guard = PersistentBuildAuthorizationConsumptionReplayGuard(store)
        self.assertTrue(guard.consume("a" * 64, consumed_at="2026-08-25T01:00:00+00:00"))
        self.assertEqual(store.calls[0][0], "candidate-build-authorization-consumption")


if __name__ == "__main__":
    unittest.main()
