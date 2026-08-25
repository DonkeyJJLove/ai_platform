import unittest

from cyber_lion.architecture_projection.gap import canonical_target_gaps, classify_historical_projection


class ArchitectureProjectionGapTests(unittest.TestCase):
    def test_target_gap_register_is_deterministic_and_explicit(self):
        first = canonical_target_gaps()
        second = canonical_target_gaps()
        self.assertEqual(first, second)
        self.assertTrue(any(g.target_id == "BeanSpec" and g.status == "TARGET_ONLY" for g in first))
        self.assertTrue(any(g.target_id == "GlobalCompleteMediation" and g.status == "UNKNOWN" for g in first))
        self.assertEqual(len({g.digest() for g in first}), len(first))

    def test_stale_existing_implementation_map_is_not_promoted(self):
        self.assertEqual(
            classify_historical_projection(
                observed_commit="c67ed65c9c26bc2a59b39786c5c410cd8490cbc7",
                current_commit="0f14d8be07cbb2aa84ddf7aea7ef994228e747b8",
            ),
            "SUPERSEDED",
        )
        self.assertEqual(classify_historical_projection(observed_commit="a" * 40, current_commit="a" * 40), "VERIFIED_REFERENCE")


if __name__ == "__main__":
    unittest.main()
