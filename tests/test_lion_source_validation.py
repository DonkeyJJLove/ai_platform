import unittest

from tools.lion_source_validation import classify_gate


def gate(*, reasons=(), critical=True, effect_mismatch=False, package_mismatch=False,
         authority_count=0, package_match=True, authority_effect="NONE"):
    return {
        "result": "PASS" if not reasons else "FAIL",
        "reasons": list(reasons),
        "head": "a"*40,
        "tree": "b"*40,
        "candidate_subject_digest": "c"*64,
        "authority_effect": authority_effect,
        "critical_tests": {"pass": critical},
        "facts": {
            "effect_inventory_mismatch": effect_mismatch,
            "package_identity_mismatch": package_mismatch,
            "non_none_authority_effect_count": authority_count,
        },
        "package": {"match": package_match},
        "production_inventory": {"taxonomy_status": "PASS"},
    }


class SourceValidationTests(unittest.TestCase):
    def test_fully_current_passes(self):
        x=classify_gate(gate())
        self.assertEqual(x["result"],"PASS")
        self.assertEqual(x["currentness_state"],"CURRENT")

    def test_only_carrier_last_drift_is_source_pass(self):
        x=classify_gate(gate(reasons=(
            "STALE_EXACT_CURRENTNESS_CARRIER","TRUTH_PLANE_MISMATCH",
        )))
        self.assertEqual(x["result"],"PASS")
        self.assertEqual(x["currentness_state"],"CURRENTNESS_INVALIDATED_PENDING_CLOSURE")
        self.assertEqual(x["blocking_source_reasons"],[])

    def test_other_gate_reason_fails(self):
        x=classify_gate(gate(reasons=("PACKAGE_IDENTITY_MISMATCH",)))
        self.assertEqual(x["result"],"FAIL")
        self.assertIn("PACKAGE_IDENTITY_MISMATCH",x["blocking_source_reasons"])

    def test_structural_failures_cannot_be_relabelled_currentness(self):
        for overrides in (
            {"critical":False},
            {"effect_mismatch":True},
            {"package_mismatch":True},
            {"authority_count":1},
            {"package_match":False},
            {"authority_effect":"ALLOW"},
        ):
            with self.subTest(overrides=overrides):
                x=classify_gate(gate(
                    reasons=("STALE_EXACT_CURRENTNESS_CARRIER","TRUTH_PLANE_MISMATCH"),
                    **overrides
                ))
                self.assertEqual(x["result"],"FAIL")
                self.assertIn("SOURCE_VALIDATION_STRUCTURAL_FAILURE",x["blocking_source_reasons"])

    def test_unknown_reason_never_promoted(self):
        x=classify_gate(gate(reasons=("FUTURE_UNKNOWN_GATE",)))
        self.assertEqual(x["result"],"FAIL")


if __name__=="__main__":
    unittest.main()
