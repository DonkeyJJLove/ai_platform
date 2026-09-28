from __future__ import annotations

import json
from pathlib import Path
import unittest

from tools.lion_r24_whole_integration_gate import (
    MATRIX_PATH,
    PROHIBITED_FACTS,
    REQUIRED_TRUE,
    evaluate_final_facts,
)


def passing_facts():
    value = {key: False if key in {
        "partial_final_state",
        "manual_ui_refresh_required",
        "repo_live_currentness_mismatch",
        "package_identity_mismatch",
        "stale_exact_currentness_carrier",
        "effect_inventory_mismatch",
        "truth_plane_mismatch",
    } else 0 for key in PROHIBITED_FACTS}
    value.update({key: True for key in REQUIRED_TRUE})
    return value


class R24WholeIntegrationGateTests(unittest.TestCase):
    def test_clean_final_fact_set_passes(self):
        self.assertEqual(evaluate_final_facts(passing_facts()), [])

    def test_every_required_prohibition_fails_closed(self):
        for key, reason in PROHIBITED_FACTS.items():
            with self.subTest(key=key):
                facts = passing_facts()
                facts[key] = True if isinstance(facts[key], bool) else 1
                self.assertIn(reason, evaluate_final_facts(facts))

    def test_every_required_positive_evidence_is_mandatory(self):
        for key, reason in REQUIRED_TRUE.items():
            with self.subTest(key=key):
                facts = passing_facts()
                facts[key] = False
                self.assertIn(reason, evaluate_final_facts(facts))

    def test_matrix_is_exactly_t01_through_t40(self):
        value = json.loads(MATRIX_PATH.read_text(encoding="utf-8"))
        tests = value["tests"]
        self.assertEqual([x["id"] for x in tests], [f"T{i:02d}" for i in range(1, 41)])
        self.assertEqual(len({x["id"] for x in tests}), 40)
        self.assertTrue(all(x["evidence_ref"] for x in tests))
        self.assertEqual(value["authority_effect"], "NONE")


if __name__ == "__main__":
    unittest.main()
