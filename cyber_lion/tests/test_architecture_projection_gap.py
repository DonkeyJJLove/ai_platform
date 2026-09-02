import unittest

from cyber_lion.architecture_projection.gap import (
    GapRecord,
    canonical_gap_projection,
    canonical_target_gaps,
    classify_historical_projection,
    classify_projection_currentness,
    transition_gap_status,
)


class ArchitectureProjectionGapTests(unittest.TestCase):
    def test_gap_projection_is_deterministic_and_separates_as_is_target_unknown(self):
        first = canonical_gap_projection()
        second = canonical_target_gaps()
        self.assertEqual(first, second)
        by_id = {g.target_id: g for g in first}

        for integrated in (
            "GoalContract",
            "WorldSnapshot",
            "SystemSnapshot",
            "Gap",
            "BeanSpec",
            "BeanCandidate",
            "BeanInstance",
            "CapabilityNeed",
            "CompositionContract",
            "CompositionEngine",
            "MosaicCell",
            "HeterogeneousMosaicPlanner",
            "BeanBuilderChainBinding",
        ):
            self.assertEqual(by_id[integrated].status, "VERIFIED_REFERENCE")
            self.assertEqual(by_id[integrated].evidence_class, "LIVE_CODE")
            self.assertTrue(by_id[integrated].evidence_ref)

        for target in (
            "AutonomyBlueprint",
            "MaterializerRegistry",
            "ActionSpec",
            "LAIR",
            "LCMS",
            "LocalConsole",
        ):
            self.assertEqual(by_id[target].status, "TARGET_ONLY")

        self.assertEqual(by_id["GlobalCompleteMediation"].status, "UNKNOWN")
        self.assertEqual(len({g.digest() for g in first}), len(first))

    def test_currentness_requires_exact_head_and_tree_and_degrades_on_drift(self):
        current_head = "2be0b312407920ac25d812f1c0bb6ecfcb31aa4c"
        current_tree = "3c9705f85301e73f268228f3c36f6ae82a641633"
        self.assertEqual(
            classify_projection_currentness(
                observed_commit=current_head,
                observed_tree=current_tree,
                current_commit=current_head,
                current_tree=current_tree,
            ),
            "CURRENT",
        )
        self.assertEqual(
            classify_projection_currentness(
                observed_commit="c67ed65c9c26bc2a59b39786c5c410cd8490cbc7",
                observed_tree="96dfdfb4cc26c094895b010aacc11a3b685d62fc",
                current_commit=current_head,
                current_tree=current_tree,
            ),
            "STALE",
        )
        self.assertEqual(
            classify_projection_currentness(
                observed_commit="c67ed65c9c26bc2a59b39786c5c410cd8490cbc7",
                observed_tree="96dfdfb4cc26c094895b010aacc11a3b685d62fc",
                current_commit=current_head,
                current_tree=current_tree,
                material_drift=False,
            ),
            "UNKNOWN",
        )

    def test_historical_projection_semantics_are_preserved(self):
        self.assertEqual(
            classify_historical_projection(
                observed_commit="c67ed65c9c26bc2a59b39786c5c410cd8490cbc7",
                current_commit="0f14d8be07cbb2aa84ddf7aea7ef994228e747b8",
            ),
            "SUPERSEDED",
        )
        self.assertEqual(
            classify_historical_projection(observed_commit="a" * 40, current_commit="a" * 40),
            "VERIFIED_REFERENCE",
        )

    def test_invalid_gap_status_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "status vocabulary is closed"):
            GapRecord("BeanSpec", "MAGICALLY_IMPLEMENTED").validate()

    def test_integrated_status_requires_literal_evidence(self):
        with self.assertRaisesRegex(ValueError, "explicit observed evidence class"):
            GapRecord("BeanSpec", "VERIFIED_REFERENCE").validate()
        with self.assertRaisesRegex(ValueError, "explicit evidence_ref"):
            GapRecord(
                "BeanSpec",
                "VERIFIED_REFERENCE",
                evidence_class="LIVE_CODE",
            ).validate()

    def test_target_only_cannot_hide_live_implementation_evidence(self):
        with self.assertRaisesRegex(ValueError, "cannot carry live implementation evidence"):
            GapRecord(
                "BeanSpec",
                "TARGET_ONLY",
                evidence_class="LIVE_CODE",
                evidence_ref="cyber_lion/contracts/bean.py",
            ).validate()

    def test_unknown_gap_promotion_requires_and_persists_explicit_evidence(self):
        unknown = GapRecord("GlobalCompleteMediation", "UNKNOWN").validate()
        with self.assertRaisesRegex(ValueError, "explicit observed evidence class"):
            transition_gap_status(unknown, new_status="VERIFIED_REFERENCE")
        with self.assertRaisesRegex(ValueError, "explicit evidence_ref"):
            transition_gap_status(
                unknown,
                new_status="VERIFIED_REFERENCE",
                evidence_class="CURRENT_TEST",
            )
        promoted = transition_gap_status(
            unknown,
            new_status="VERIFIED_REFERENCE",
            evidence_class="CURRENT_TEST",
            evidence_ref="test:complete-mediation-proof",
        )
        self.assertEqual(promoted.status, "VERIFIED_REFERENCE")
        self.assertEqual(promoted.evidence_class, "CURRENT_TEST")
        self.assertEqual(promoted.evidence_ref, "test:complete-mediation-proof")

    def test_invalid_currentness_identity_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "exact lowercase SHA-1"):
            classify_projection_currentness(
                observed_commit="not-a-sha",
                observed_tree="a" * 40,
                current_commit="b" * 40,
                current_tree="c" * 40,
            )


if __name__ == "__main__":
    unittest.main()
