from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from tools.lion_r24_whole_integration_gate import (
    MATRIX_PATH,
    PROHIBITED_FACTS,
    REQUIRED_TRUE,
    _deployment_currentness,
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

    def test_h5_without_live_state_remains_explicit_predeployment(self):
        result = _deployment_currentness("a" * 40, "b" * 40, None)
        self.assertEqual(result["deployment_state"], "PRE_H5_NOT_DEPLOYED")
        self.assertTrue(result["current"])
        self.assertFalse(result["state_present"])

    def test_h5_exact_live_state_is_postdeployment_current(self):
        head, tree = "a" * 40, "b" * 40
        state = {
            "status": "READY",
            "repo_head": head,
            "repo_tree": tree,
            "candidate_head": head,
            "candidate_tree": tree,
            "panel_8780": True,
            "panel_surface": "CANONICAL_CONVERSATION_MODEL_CHAT",
            "legacy_thread_mutation": "RETIRED",
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.json"
            path.write_text(json.dumps(state), encoding="utf-8")
            result = _deployment_currentness(head, tree, path)
        self.assertEqual(result["deployment_state"], "POST_H5_DEPLOYED")
        self.assertTrue(result["current"])
        self.assertEqual(result["mismatches"], [])

    def test_h5_live_identity_mismatch_fails_closed(self):
        head, tree = "a" * 40, "b" * 40
        state = {
            "status": "READY",
            "repo_head": "c" * 40,
            "repo_tree": tree,
            "candidate_head": "c" * 40,
            "candidate_tree": tree,
            "panel_8780": True,
            "panel_surface": "CANONICAL_CONVERSATION_MODEL_CHAT",
            "legacy_thread_mutation": "RETIRED",
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.json"
            path.write_text(json.dumps(state), encoding="utf-8")
            result = _deployment_currentness(head, tree, path)
        self.assertEqual(result["deployment_state"], "POST_H5_DEPLOYMENT_MISMATCH")
        self.assertFalse(result["current"])
        self.assertTrue(any(x.startswith("repo_head:") for x in result["mismatches"]))

    def test_h5_requested_missing_state_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "missing.json"
            result = _deployment_currentness("a" * 40, "b" * 40, path)
        self.assertEqual(result["deployment_state"], "POST_H5_STATE_MISSING")
        self.assertFalse(result["current"])
        self.assertEqual(result["mismatches"], ["STATE_MISSING"])


if __name__ == "__main__":
    unittest.main()
