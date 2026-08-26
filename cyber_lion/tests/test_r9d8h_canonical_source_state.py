from __future__ import annotations

import tempfile
from pathlib import Path
import unittest

from cyber_lion.contracts.policy_gate import PolicyRevision
from cyber_lion.enterprise.canonical_policy_state import CanonicalPolicyStateError, CanonicalPolicyStore
from cyber_lion.enterprise.canonical_mission_state import CanonicalMissionStateError, CanonicalMissionStore, mission_digest
from cyber_lion.enterprise.models import MissionSpec


class CanonicalSourceStateTests(unittest.TestCase):
    def test_policy_requires_explicit_current_record_and_supersession(self):
        with tempfile.TemporaryDirectory() as td:
            store = CanonicalPolicyStore(Path(td) / "policy.sqlite", registry_id="policy-registry:E006")
            with self.assertRaises(CanonicalPolicyStateError):
                store.resolve_current("maintenance-policy")
            p1 = PolicyRevision("maintenance-policy", "1", "sha256:" + "1" * 64, "AMBER", True)
            store.register_initial(p1, source_provenance_ref="external:policy:1")
            self.assertEqual(store.resolve_current("maintenance-policy"), p1)
            with self.assertRaises(CanonicalPolicyStateError):
                store.register_initial(p1, source_provenance_ref="external:policy:1")
            p2 = PolicyRevision("maintenance-policy", "2", "sha256:" + "2" * 64, "AMBER", True)
            with self.assertRaises(CanonicalPolicyStateError):
                store.supersede(p2, expected_revision="0", expected_digest="0" * 64, source_provenance_ref="external:policy:2")
            store.supersede(
                p2,
                expected_revision="1",
                expected_digest=store.current_binding_digest("maintenance-policy"),
                source_provenance_ref="external:policy:2",
            )
            self.assertEqual(store.resolve_current("maintenance-policy"), p2)
            store.close()

    def test_policy_inactive_record_cannot_become_current(self):
        with tempfile.TemporaryDirectory() as td:
            store = CanonicalPolicyStore(Path(td) / "policy.sqlite", registry_id="policy-registry:E006")
            p = PolicyRevision("maintenance-policy", "1", "sha256:" + "3" * 64, "AMBER", False)
            with self.assertRaises(CanonicalPolicyStateError):
                store.register_initial(p, source_provenance_ref="external:policy:inactive")
            store.close()

    def test_mission_requires_provenance_and_exact_supersession(self):
        with tempfile.TemporaryDirectory() as td:
            store = CanonicalMissionStore(Path(td) / "mission.sqlite", registry_id="mission-registry:E006")
            m1 = MissionSpec(
                mission_id="E006-REPOSITORY-MAINTENANCE",
                purpose="governed repository maintenance",
                required_capabilities=("repository_ref.delete",),
                authority_ceiling="external_write",
                risk_class="AMBER",
                max_agents=4,
                observability_quorum=1.0,
                require_independent_verifier=True,
                max_total_cost_units=8.0,
            ).validate()
            with self.assertRaises(CanonicalMissionStateError):
                store.register_initial(m1, source_provenance_ref="")
            store.register_initial(m1, source_provenance_ref="external:mission:1")
            observed, revision, digest = store.resolve_current(m1.mission_id)
            self.assertEqual((observed, revision, digest), (m1, 1, mission_digest(m1)))
            with self.assertRaises(CanonicalMissionStateError):
                store.supersede(m1, expected_revision=0, expected_digest="0" * 64, source_provenance_ref="external:mission:2")
            m2 = MissionSpec(
                mission_id=m1.mission_id,
                purpose=m1.purpose,
                required_capabilities=m1.required_capabilities,
                authority_ceiling=m1.authority_ceiling,
                risk_class=m1.risk_class,
                max_agents=5,
                observability_quorum=m1.observability_quorum,
                require_independent_verifier=m1.require_independent_verifier,
                max_total_cost_units=10.0,
            ).validate()
            store.supersede(m2, expected_revision=1, expected_digest=digest, source_provenance_ref="external:mission:2")
            observed2, revision2, digest2 = store.resolve_current(m1.mission_id)
            self.assertEqual(observed2, m2)
            self.assertEqual(revision2, 2)
            self.assertNotEqual(digest2, digest)
            store.close()


if __name__ == "__main__":
    unittest.main()
