from __future__ import annotations

import copy
import json
import os
import subprocess
from pathlib import Path
import unittest

from cyber_lion.architecture_projection.truth_plane import (
    TruthProjectionError,
    validate_truth_projection,
)

STATE_PATH = Path("LION/architecture/canonical-state-v1-3-candidate.json")
IMPLEMENTATION_MAP_PATH = Path("LION/architecture/implementation-map.json")
REGISTRY_PATH = Path("cyber_lion/registry/repositories.json")
FIXTURE_MASTER_HEAD = "9a90d463a4131b5e73a37bfb4a28194ecfa892dc"
PRE_EPHEMERAL_MASTER_HEAD = "9082a974e8105dd7e47afc889583b1fc67535b59"
FIXTURE_MASTER_TREE = "1414a21efce8f35892134060cd0d77f2d4d08e9b"
OLD_MASTER_HEAD = "22ae615c3ec6eedf2a500d0d70d8ecc97ba1cabd"
C0_HEAD = "f8d8e44191d5c84ecca9feec1a8602f574948619"
C1_HEAD = "0f75af9212a814177e08a5c206d1a8504b0937d5"


class TruthPlaneReconciliationTests(unittest.TestCase):
    def state(self):
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))

    def validate(self, payload=None, *, head=FIXTURE_MASTER_HEAD, tree=FIXTURE_MASTER_TREE):
        return validate_truth_projection(
            self.state() if payload is None else payload,
            current_head=head,
            current_tree=tree,
        )

    def _live_gate_enabled(self):
        return (
            bool(os.environ.get("LION_LIVE_MASTER_HEAD") and os.environ.get("LION_LIVE_MASTER_TREE"))
            or os.environ.get("LION_P0_LIVE_CURRENTNESS") == "1"
            or os.environ.get("GITHUB_ACTIONS") == "true"
        )

    def _resolve_live_branch(self, branch):
        exact_ref = f"refs/heads/{branch}"
        proc = subprocess.run(
            ["git", "ls-remote", "--exit-code", "origin", exact_ref],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(proc.returncode, 0, f"LIVE_REF_UNAVAILABLE:{branch}")
        lines = [line for line in proc.stdout.splitlines() if line.strip()]
        self.assertEqual(len(lines), 1, f"LIVE_REF_CARDINALITY_INVALID:{branch}")
        parts = lines[0].split()
        self.assertEqual(len(parts), 2, f"LIVE_REF_RESOLUTION_INVALID:{branch}")
        self.assertEqual(parts[1], exact_ref, f"LIVE_REF_RESOLUTION_INVALID:{branch}")
        head = parts[0]
        self.assertEqual(len(head), 40, f"LIVE_HEAD_INVALID:{branch}")
        self.assertEqual(head, head.lower(), f"LIVE_HEAD_INVALID:{branch}")
        self.assertTrue(all(ch in "0123456789abcdef" for ch in head), f"LIVE_HEAD_INVALID:{branch}")

        fetched = subprocess.run(
            ["git", "fetch", "--no-tags", "--depth=1", "origin", exact_ref],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
            timeout=30,
        )
        self.assertEqual(fetched.returncode, 0, f"LIVE_REF_FETCH_FAILED:{branch}:{fetched.stderr.strip()}")
        fetched_head = subprocess.run(
            ["git", "rev-parse", "FETCH_HEAD^{commit}"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        tree = subprocess.run(
            ["git", "rev-parse", "FETCH_HEAD^{tree}"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        self.assertEqual(fetched_head, head, f"LIVE_REF_FETCH_DRIFT:{branch}")
        self.assertEqual(len(tree), 40, f"LIVE_TREE_INVALID:{branch}")
        return head, tree

    def live_identity(self):
        head = os.environ.get("LION_LIVE_MASTER_HEAD")
        tree = os.environ.get("LION_LIVE_MASTER_TREE")
        if head and tree:
            return head, tree
        if not self._live_gate_enabled():
            self.skipTest("LIVE_CURRENTNESS_EVIDENCE_UNAVAILABLE")
        return self._resolve_live_branch("master")

    def test_fixture_projection_is_structurally_valid(self):
        state = self.validate()
        self.assertEqual(state["baseline"]["head"], FIXTURE_MASTER_HEAD)
        self.assertEqual(state["baseline"]["tree"], FIXTURE_MASTER_TREE)
        self.assertEqual(state["baseline"]["currentness"], "CURRENT")

    def test_live_master_truth_projection_is_current(self):
        head, tree = self.live_identity()
        state = validate_truth_projection(self.state(), current_head=head, current_tree=tree)
        self.assertEqual(state["baseline"]["head"], head)
        self.assertEqual(state["baseline"]["tree"], tree)
        self.assertEqual(state["baseline"]["currentness"], "CURRENT")

    def test_live_registry_generated_from_is_current(self):
        head, _ = self.live_identity()
        registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
        self.assertIn(head, registry["generated_from"])

    def test_live_candidate_frontier_is_exact(self):
        if not self._live_gate_enabled():
            self.skipTest("LIVE_CURRENTNESS_EVIDENCE_UNAVAILABLE")
        master, _ = self.live_identity()
        records = {item["id"]: item for item in self.state()["records"]}
        bindings = {
            "B0GenerativityProtocol": "mission/b0-bean-generativity-protocol-r1",
            "ActionSpec": "mission/c0-action-ir-schema-freeze-r3",
            "LCMS": "mission/c1-lcms-canonicalization-r1",
            "ReadonlyProcessAdapter": "mission/c2-readonly-process-exec-r1",
            "HybridModelRouter": "mission/p0-entry-candidate-r1",
            "PhysicalActionSpec": "mission/p0-entry-candidate-r1",
            "P0EntryCandidate": "mission/p0-entry-candidate-r1",
        }
        resolved = {}
        for record_id, branch in bindings.items():
            if branch not in resolved:
                resolved[branch] = self._resolve_live_branch(branch)
            head, tree = resolved[branch]
            record = records[record_id]
            self.assertEqual(record["head"], head, f"STALE_CANDIDATE_HEAD:{record_id}")
            self.assertEqual(record["tree"], tree, f"STALE_CANDIDATE_TREE:{record_id}")

        self.assertEqual(records["ActionSpec"]["base_head"], PRE_EPHEMERAL_MASTER_HEAD, "ACTION_SPEC_GENEALOGY_DRIFT")
        self.assertNotEqual(records["ActionSpec"]["base_head"], master, "ACTION_SPEC_SHOULD_BE_STALE_AFTER_MASTER_HISTORY_ADVANCE")
        self.assertEqual(records["ActionSpec"]["status"], "STALE_BASE_CANDIDATE")
        self.assertEqual(records["LCMS"]["base_head"], records["ActionSpec"]["head"], "STALE_CANDIDATE_BASE:LCMS")
        self.assertEqual(
            records["ReadonlyProcessAdapter"]["base_head"],
            records["LCMS"]["head"],
            "STALE_CANDIDATE_BASE:ReadonlyProcessAdapter",
        )
        for record_id in (
            "B0GenerativityProtocol",
            "HybridModelRouter",
            "PhysicalActionSpec",
            "P0EntryCandidate",
        ):
            record = records[record_id]
            self.assertEqual(record["status"], "STALE_BASE_CANDIDATE")
            self.assertNotEqual(record["base_head"], master)

        mediation = records["GlobalCompleteMediation"]
        self.assertEqual(
            (mediation["plane"], mediation["status"], mediation["integrated"]),
            ("UNKNOWN", "UNKNOWN", False),
        )

    def test_head_drift_is_rejected_if_current_is_declared(self):
        with self.assertRaisesRegex(TruthProjectionError, "baseline currentness contradiction"):
            self.validate(head="f" * 40)

    def test_tree_drift_is_rejected_if_current_is_declared(self):
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

    def test_current_master_candidate_cannot_carry_stale_base(self):
        state = self.state()
        candidate = next(item for item in state["records"] if item["id"] == "ActionSpec")
        candidate["status"] = "CURRENT_MASTER_BASE_CANDIDATE"
        self.assertEqual(candidate["base_head"], PRE_EPHEMERAL_MASTER_HEAD)
        with self.assertRaisesRegex(TruthProjectionError, "current master-base candidate is stale"):
            self.validate(state)

    def test_stale_candidate_cannot_hide_current_master_base(self):
        state = self.state()
        candidate = next(item for item in state["records"] if item["id"] == "B0GenerativityProtocol")
        candidate["base_head"] = FIXTURE_MASTER_HEAD
        with self.assertRaisesRegex(TruthProjectionError, "candidate base currentness contradiction"):
            self.validate(state)

    def test_stacked_candidate_cannot_claim_master_base(self):
        state = self.state()
        candidate = next(item for item in state["records"] if item["id"] == "LCMS")
        candidate["base_head"] = FIXTURE_MASTER_HEAD
        with self.assertRaisesRegex(TruthProjectionError, "candidate base currentness contradiction"):
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
        self.assertNotEqual(legacy["observed_from"]["commit"], FIXTURE_MASTER_HEAD)

    def test_registry_identity_is_preserved(self):
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
        self.assertIn(FIXTURE_MASTER_HEAD, registry["generated_from"])

    def test_r2e4_and_budget_are_as_is_on_current_master_projection(self):
        records = {item["id"]: item for item in self.validate()["records"]}
        for record_id in ("R2E4EvidenceBinding", "FleetAggregateEffectBudget"):
            record = records[record_id]
            self.assertEqual(record["plane"], "AS_IS")
            self.assertTrue(record["integrated"])
            self.assertIsNone(record["pr"])
            self.assertIsNone(record["head"])
            self.assertIsNone(record["tree"])
            self.assertIn(f"master:{PRE_EPHEMERAL_MASTER_HEAD}", record["evidence_refs"])

    def test_candidate_frontier_and_stale_candidates_are_explicit(self):
        records = {item["id"]: item for item in self.validate()["records"]}
        expected = {
            "B0GenerativityProtocol": (251, "85e77ac077f89ce892c1254d01f88a0889034b2f", "e36f84e2fd1be653718dff1a33bbed7e420d41fa", "STALE_BASE_CANDIDATE", OLD_MASTER_HEAD),
            "ActionSpec": (256, "f8d8e44191d5c84ecca9feec1a8602f574948619", "b303b628e18dd1b31bb19c923cd0f18e2f050ae9", "STALE_BASE_CANDIDATE", PRE_EPHEMERAL_MASTER_HEAD),
            "LCMS": (257, "0f75af9212a814177e08a5c206d1a8504b0937d5", "e722488cda090e62a379584c12f7cee8daa43de1", "CURRENT_STACKED_CANDIDATE", C0_HEAD),
            "ReadonlyProcessAdapter": (258, "86dc7ac367ad2cd83e873e0ae3508f42a72eaac5", "4ab9157f89edc69f35cc0169bf8926c71af21313", "CURRENT_STACKED_CANDIDATE", C1_HEAD),
            "HybridModelRouter": (253, "61b963e8664d6832f8bfe22bd31327ff63618a07", "656a777f096d6ddacc8b923e39658d1ff72ef376", "STALE_BASE_CANDIDATE", OLD_MASTER_HEAD),
            "PhysicalActionSpec": (253, "61b963e8664d6832f8bfe22bd31327ff63618a07", "656a777f096d6ddacc8b923e39658d1ff72ef376", "STALE_BASE_CANDIDATE", OLD_MASTER_HEAD),
            "P0EntryCandidate": (253, "61b963e8664d6832f8bfe22bd31327ff63618a07", "656a777f096d6ddacc8b923e39658d1ff72ef376", "STALE_BASE_CANDIDATE", OLD_MASTER_HEAD),
        }
        for record_id, (pr, head, tree, status, base_head) in expected.items():
            record = records[record_id]
            self.assertEqual(record["plane"], "CANDIDATE")
            self.assertFalse(record["integrated"])
            self.assertEqual(record["pr"], pr)
            self.assertEqual(record["head"], head)
            self.assertEqual(record["tree"], tree)
            self.assertEqual(record["status"], status)
            self.assertEqual(record["base_head"], base_head)

    def test_global_complete_mediation_remains_unknown(self):
        record = next(item for item in self.validate()["records"] if item["id"] == "GlobalCompleteMediation")
        self.assertEqual(record["plane"], "UNKNOWN")
        self.assertEqual(record["status"], "UNKNOWN")
        self.assertFalse(record["integrated"])


if __name__ == "__main__":
    unittest.main()
