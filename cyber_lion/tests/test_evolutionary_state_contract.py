from dataclasses import replace
import unittest

from cyber_lion.contracts.evolutionary_state import (
    EvolutionaryStateError,
    GoalContract,
    SystemSnapshot,
    WorldSnapshot,
    assert_exact_gap_binding,
    derive_gap,
)


class EvolutionaryStateContractTests(unittest.TestCase):
    def goal(self):
        return GoalContract(
            goal_id="E006-GOAL",
            revision=1,
            objective="close one governed evolutionary loop",
            constraints=("no-self-authorization", "no-release"),
            success_conditions=("reconciled-next-epoch",),
            stop_conditions=("hard-blocker",),
            defer_conditions=("required-evidence-unknown",),
            source_ref="issue:198",
        ).validate()

    def world(self, state="CURRENT"):
        return WorldSnapshot(
            snapshot_id="WORLD-E006-1",
            observed_at="2026-08-25T21:35:00Z",
            captured_at="2026-08-25T21:35:01Z",
            epistemic_state=state,
            observations=(("problem", "missing canonical capability unit"),),
            source_refs=("repo:DonkeyJJLove/ai_platform",),
            evidence_refs=("git:3bdb3a6d9558135100796a38971d8eada24d65d2",),
            freshness_deadline="2026-08-26T21:35:00Z" if state == "CURRENT" else "",
        ).validate()

    def system(self, state="CURRENT", unknowns=()):
        return SystemSnapshot(
            snapshot_id="SYSTEM-E006-1",
            observed_at="2026-08-25T21:35:00Z",
            captured_at="2026-08-25T21:35:02Z",
            epistemic_state=state,
            repository="DonkeyJJLove/ai_platform",
            revision="3bdb3a6d9558135100796a38971d8eada24d65d2",
            tree_digest="baseline-tree-bound-by-git-commit",
            implementation_facts=(("GoalContract", "TARGET_ONLY"), ("BeanSpec", "TARGET_ONLY")),
            test_evidence_refs=("ci:baseline",),
            observation_refs=("architecture_projection/gap.py",),
            freshness_deadline="2026-08-26T21:35:00Z" if state == "CURRENT" else "",
            unknowns=unknowns,
        ).validate()

    def gap(self, *, world=None, system=None, unknowns=()):
        return derive_gap(
            gap_id="GAP-E006-1",
            goal=self.goal(),
            world=world or self.world(),
            system=system or self.system(),
            missing_capabilities=("GoalContract", "WorldSnapshot", "SystemSnapshot", "Gap"),
            unsatisfied_conditions=("canonical-state-triad-absent",),
            evidence_refs=("architecture_projection/gap.py",),
            falsification_conditions=("existing-canonical-contract-proves-equivalent-semantics",),
            unknowns=unknowns,
        )

    def test_digest_is_deterministic_and_semantic_change_changes_digest(self):
        goal = self.goal()
        self.assertEqual(goal.digest(), self.goal().digest())
        self.assertNotEqual(goal.digest(), replace(goal, objective="different objective").digest())

    def test_current_world_requires_freshness(self):
        with self.assertRaises(EvolutionaryStateError):
            replace(self.world(), freshness_deadline="").validate()

    def test_current_system_requires_freshness(self):
        with self.assertRaises(EvolutionaryStateError):
            replace(self.system(), freshness_deadline="").validate()

    def test_unknown_system_requires_named_unknowns(self):
        with self.assertRaises(EvolutionaryStateError):
            self.system(state="UNKNOWN")

    def test_unknown_is_preserved_into_gap(self):
        system = self.system(state="UNKNOWN", unknowns=("GlobalCompleteMediation",))
        gap = self.gap(system=system)
        self.assertEqual(gap.epistemic_state, "UNKNOWN")
        self.assertIn("system:GlobalCompleteMediation", gap.unknowns)

    def test_explicit_unknown_forces_unknown_even_if_snapshots_are_current(self):
        gap = self.gap(unknowns=("effect-surface-enumeration-incomplete",))
        self.assertEqual(gap.epistemic_state, "UNKNOWN")

    def test_gap_does_not_select_or_authorize_solution(self):
        gap = self.gap()
        self.assertFalse(hasattr(gap, "grant"))
        self.assertFalse(hasattr(gap, "credential"))
        self.assertFalse(hasattr(gap, "execution_effect"))
        self.assertFalse(hasattr(gap, "authority_effect"))

    def test_exact_binding_accepts_original_inputs(self):
        goal, world, system = self.goal(), self.world(), self.system()
        gap = derive_gap(
            gap_id="GAP-BIND",
            goal=goal,
            world=world,
            system=system,
            missing_capabilities=("BeanSpec",),
            unsatisfied_conditions=("domain-independent-capability-unit-absent",),
            evidence_refs=("architecture_projection/gap.py",),
            falsification_conditions=("equivalent-live-contract-found",),
        )
        assert_exact_gap_binding(gap=gap, goal=goal, world=world, system=system)

    def test_world_substitution_is_denied(self):
        goal, world, system = self.goal(), self.world(), self.system()
        gap = derive_gap(
            gap_id="GAP-BIND",
            goal=goal,
            world=world,
            system=system,
            missing_capabilities=("BeanSpec",),
            unsatisfied_conditions=("domain-independent-capability-unit-absent",),
            evidence_refs=("architecture_projection/gap.py",),
            falsification_conditions=("equivalent-live-contract-found",),
        )
        substituted = replace(world, observations=(("problem", "different payload same stable id"),))
        with self.assertRaises(EvolutionaryStateError):
            assert_exact_gap_binding(gap=gap, goal=goal, world=substituted, system=system)

    def test_goal_revision_requires_exact_parent_binding(self):
        with self.assertRaises(EvolutionaryStateError):
            replace(self.goal(), revision=2).validate()


if __name__ == "__main__":
    unittest.main()
