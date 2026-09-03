from __future__ import annotations

import copy
import json
from pathlib import Path
import unittest

from cyber_lion.architecture_projection.truth_plane import (
    TruthProjectionError,
    validate_truth_projection,
)


STATE_PATH = Path("LION/architecture/canonical-state-v1-3-candidate.json")
IMPLEMENTATION_MAP_PATH = Path("LION/architecture/implementation-map.json")
REGISTRY_PATH = Path("cyber_lion/registry/repositories.json")
MASTER_HEAD = "22ae615c3ec6eedf2a500d0d70d8ecc97ba1cabd"
MASTER_TREE = "ac8474a13d46e568787b2fc5bd77955e8b0febda"


class TruthPlaneReconciliationTests(unittest.TestCase):
    def state(self):
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))

    def validate(self, payload=None, *, head=MASTER_HEAD, tree=MASTER_TREE):
        return validate_truth_projection(
            self.state() if payload is None else payload,
            current_head=head,
            current_tree=tree,
        )

    def test_exact_master_truth_projection_is_valid(self):
        state = self.validate()
        self.assertEqual(state["baseline"]["head"], MASTER_HEAD)
        self.assertEqual(state["baseline"]["tree"], MASTER_TREE)
        self.assertEqual(state["baseline"]["currentness"], "CURRENT")

    def test_head_drift_degrades_current_and_is_rejected_if_declared_current(self):
        with self.assertRaisesRegex(TruthProjectionError, "baseline currentness contradiction"):
            self.validate(head="f" * 40)

    def test_tree_drift_degrades_current_and_is_rejected_if_declared_current(self):
        with self.assertRaisesRegex(TruthProjectionError, "baseline currentness contradiction"):
            self.validate(tree="e" * 40)

    def test_duplicate_component_across_planes_fails_closed(self):
        state = self.state()
        duplicate = copy.deepcopy(state["records"][0])
        duplicate["plane"] = "TARGET"
        duplicate["status"] = "TARGET_NOT_IMPLEMENTED"
        duplicate["evidence_refs"] = []
        duplicate["integrated"] = False
        state["records"].append(duplicate)
        with self.assertRaisesRegex(TruthProjectionError, "duplicate truth record"):
            self.validate(state)

    def test_target_with_live_implementation_evidence_fails_closed(self):
        state = self.state()
        target = next(item for item in state["records"] if item["id"] == "AutonomyBlueprint")
        target["evidence_refs"] = ["cyber_lion/enterprise/control_plane.py"]
        with self.assertRaisesRegex(TruthProjectionError, "TARGET cannot carry live implementation evidence"):
            self.validate(state)

    def test_candidate_cannot_be_silently_promoted_to_as_is(self):
        state = self.state()
        candidate = next(item for item in state["records"] if item["id"] == "ActionSpec")
        candidate["integrated"] = True
        with self.assertRaisesRegex(TruthProjectionError, "candidate silently promoted"):
            self.validate(state)

    def test_historical_projection_cannot_claim_current_after_material_drift(self):
        state = self.state()
        state["historical_projections"][0]["currentness"] = "CURRENT"
        with self.assertRaisesRegex(TruthProjectionError, "historical currentness contradiction"):
            self.validate(state)

    def test_legacy_implementation_map_is_literal_stale(self):
        legacy = json.loads(IMPLEMENTATION_MAP_PATH.read_text(encoding="utf-8"))
        self.assertEqual(legacy["freshness"]["state"], "STALE")
        self.assertEqual(legacy["observed_from"]["commit"], "c67ed65c9c26bc2a59b39786c5c410cd8490cbc7")
        self.assertNotEqual(legacy["observed_from"]["commit"], MASTER_HEAD)

    def test_registry_identity_is_preserved_but_ai_platform_maturity_is_current(self):
        registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
        by_id = {item["id"]: item for item in registry["repositories"]}
        self.assertEqual(set(by_id), {
            "DonkeyJJLove/ai_platform",
            "DonkeyJJLove/chunk-chunk",
            "DonkeyJJLove/glitchlab",
            "DonkeyJJLove/HA2D",
            "DonkeyJJLove/hipotezy_nadawcze_LLM",
            "DonkeyJJLove/mosaic_lab_pro.py",
            "DonkeyJJLove/sbom",
            "DonkeyJJLove/swarm",
            "DonkeyJJLove/SymulacjaKaskadySieciowej",
            "DonkeyJJLove/writeups",
        })
        self.assertEqual(by_id["DonkeyJJLove/ai_platform"]["default_branch"], "master")
        self.assertEqual(by_id["DonkeyJJLove/ai_platform"]["maturity"], "INTEGRATED_ENGINEERING_PLATFORM")
        self.assertIn(MASTER_HEAD, registry["generated_from"])

    def test_r2e4_and_budget_are_as_is_after_child_first_stack_closure(self):
        records = {item["id"]: item for item in self.validate()["records"]}
        for record_id in ("R2E4EvidenceBinding", "FleetAggregateEffectBudget"):
            record = records[record_id]
            self.assertEqual(record["plane"], "AS_IS")
            self.assertTrue(record["integrated"])
            self.assertIsNone(record["pr"])
            self.assertIsNone(record["head"])
            self.assertIsNone(record["tree"])
            self.assertIn(f"master:{MASTER_HEAD}", record["evidence_refs"])

    def test_current_open_candidate_frontier_stays_non_integrated(self):
        records = {item["id"]: item for item in self.validate()["records"]}
        expected = {
            "B0GenerativityProtocol": (251, "85e77ac077f89ce892c1254d01f88a0889034b2f", "e36f84e2fd1be653718dff1a33bbed7e420d41fa"),
            "ActionSpec": (252, "d31a6385793909909b62d2d6bf7825713dbe3dab", "e1977c7f1375cfc458c06afa91d469c612a7bc0d"),
            "P0EntryCandidate": (253, "61b963e8664d6832f8bfe22bd31327ff63618a07", "656a777f096d6ddacc8b923e39658d1ff72ef376"),
        }
        for record_id, (pr, head, tree) in expected.items():
            record = records[record_id]
            self.assertEqual(record["plane"], "CANDIDATE")
            self.assertFalse(record["integrated"])
            self.assertEqual(record["pr"], pr)
            self.assertEqual(record["head"], head)
            self.assertEqual(record["tree"], tree)
            self.assertEqual(record["base_head"], MASTER_HEAD)

    def test_global_complete_mediation_remains_unknown(self):
        record = next(item for item in self.validate()["records"] if item["id"] == "GlobalCompleteMediation")
        self.assertEqual(record["plane"], "UNKNOWN")
        self.assertEqual(record["status"], "UNKNOWN")
        self.assertFalse(record["integrated"])


if __name__ == "__main__":
    unittest.main()
