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
MASTER_HEAD = "2be0b312407920ac25d812f1c0bb6ecfcb31aa4c"
MASTER_TREE = "3c9705f85301e73f268228f3c36f6ae82a641633"


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
        target = next(item for item in state["records"] if item["id"] == "ActionSpec")
        target["evidence_refs"] = ["cyber_lion/enterprise/control_plane.py"]
        with self.assertRaisesRegex(TruthProjectionError, "TARGET cannot carry live implementation evidence"):
            self.validate(state)

    def test_candidate_cannot_be_silently_promoted_to_as_is(self):
        state = self.state()
        candidate = next(item for item in state["records"] if item["id"] == "R2E4EvidenceBinding")
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

    def test_candidate_frontier_remains_candidate_and_exact(self):
        records = {item["id"]: item for item in self.validate()["records"]}
        r2e4 = records["R2E4EvidenceBinding"]
        budget = records["FleetAggregateEffectBudget"]
        self.assertEqual(r2e4["plane"], "CANDIDATE")
        self.assertFalse(r2e4["integrated"])
        self.assertEqual(r2e4["pr"], 248)
        self.assertEqual(r2e4["head"], "8bf8934a0cf2809b58b460c01976cf82ae0692e7")
        self.assertEqual(r2e4["tree"], "eee3ea5f4f0a116e0f5409b6885a4fb0a5f691d1")
        self.assertEqual(r2e4["base_head"], MASTER_HEAD)

        self.assertEqual(budget["plane"], "CANDIDATE")
        self.assertFalse(budget["integrated"])
        self.assertEqual(budget["pr"], 249)
        self.assertEqual(budget["head"], "46174de77634ce2b6d62bd6709f8ff3470d51951")
        self.assertEqual(budget["tree"], "a2c2ca9594dd30174e0892f48464678da27e1bf2")
        self.assertEqual(budget["base_head"], r2e4["head"])


if __name__ == "__main__":
    unittest.main()
