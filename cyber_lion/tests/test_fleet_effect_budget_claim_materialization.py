from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
VERIFIED_HEAD = "b352d1c3d472e2b8d247b7194d2d62864611906b"
VERIFIED_TREE = "ee402be211f1b85ca0018ecccc0c972de56b0cb9"
SUPERSEDED_CONTRACT_DIGEST = "c361104b0faa96f24afd7cecaf11284ea762aa25a3cee715319481789f1163d2"
SUPERSEDED_IMPLEMENTATION_DIGEST = "83c359c2292c352a53ec8f4e1184f00afc03545378ac6a27f84c84284f227465"


def file_sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


class FleetEffectBudgetClaimMaterializationTests(unittest.TestCase):
    def setUp(self):
        self.contract_digest = file_sha256(ROOT / "cyber_lion" / "contracts" / "fleet_effect_budget.py")
        self.implementation_digest = file_sha256(ROOT / "cyber_lion" / "enterprise" / "fleet_effect_budget.py")

    def test_contract_map_claim_is_exact_restrictive_and_evidence_bound(self):
        text = (ROOT / "cyber_lion" / "CONTRACT_MAP.md").read_text(encoding="utf-8")
        for token in (
            "Fleet Aggregate Effect Budget — VERIFIED candidate",
            f"VERIFIED_HEAD={VERIFIED_HEAD}",
            f"VERIFIED_TREE={VERIFIED_TREE}",
            f"CONTRACT_DIGEST={self.contract_digest}",
            f"IMPLEMENTATION_DIGEST={self.implementation_digest}",
            "DEDICATED_RUN=33615802655",
            "CORE_RUN=33615802648",
            "CAN_RESTRICT_AUTHORITY=YES",
            "CAN_CREATE_AUTHORITY=NO",
            "CAN_EXPAND_AUTHORITY=NO",
            "CAN_SUBSTITUTE_AUTHORITY=NO",
            "valid authority + no budget => DENY",
            "budget + no authority => DENY",
            "DISTRIBUTED_CONSENSUS=NO_CLAIM",
            "GLOBAL_MULTI_HOST_REPOSITORY_JOURNAL_LINEARIZABILITY=NO_CLAIM",
            "MONETARY_BUDGET=NO_CLAIM",
            "TOKEN_BUDGET=NO_CLAIM",
            "PRODUCTION_DEPLOYMENT=NO_CLAIM",
            "INTEGRATED=NO",
            "OBSERVED=NO",
            "SINGLE_RUNTIME_ATTACH_ONLY",
        ):
            self.assertIn(token, text)
        self.assertNotIn(SUPERSEDED_CONTRACT_DIGEST, text)
        self.assertNotIn(SUPERSEDED_IMPLEMENTATION_DIGEST, text)

    def test_capability_map_claim_cannot_promote_budget_into_authority(self):
        text = (ROOT / "cyber_lion" / "CAPABILITY_MAP.md").read_text(encoding="utf-8")
        for token in (
            "aggregate effect budget",
            "VERIFIED candidate; restrictive only",
            "CAN_RESTRICT_AUTHORITY=YES",
            "CAN_CREATE_AUTHORITY=NO",
            "CAN_EXPAND_AUTHORITY=NO",
            "CAN_SUBSTITUTE_AUTHORITY=NO",
            "valid authority + no budget => DENY",
            "budget + no authority => DENY",
            "SINGLE_RUNTIME_ATTACH_ONLY",
        ):
            self.assertIn(token, text)
        self.assertIn("nie `INTEGRATED` ani `OBSERVED`", text)

    def test_implementation_map_provenance_matches_live_source_digests(self):
        path = ROOT / "LION" / "architecture" / "implementation-map.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        matches = [component for component in payload["components"] if component.get("id") == "fleet-aggregate-effect-budget"]
        self.assertEqual(len(matches), 1)
        component = matches[0]
        self.assertEqual(component["state"], "VERIFIED")
        evidence = tuple(component["evidence"])
        for token in (
            "PR#249",
            f"head:{VERIFIED_HEAD}",
            f"tree:{VERIFIED_TREE}",
            f"contract-sha256:{self.contract_digest}",
            f"implementation-sha256:{self.implementation_digest}",
            "run:33615802655",
            "run:33615802648",
        ):
            self.assertIn(token, evidence)
        self.assertNotIn(f"contract-sha256:{SUPERSEDED_CONTRACT_DIGEST}", evidence)
        self.assertNotIn(f"implementation-sha256:{SUPERSEDED_IMPLEMENTATION_DIGEST}", evidence)

        note = component["note"]
        for token in (
            "CAN_RESTRICT_AUTHORITY=YES",
            "CAN_CREATE_AUTHORITY=NO",
            "CAN_EXPAND_AUTHORITY=NO",
            "CAN_SUBSTITUTE_AUTHORITY=NO",
            "Not INTEGRATED or OBSERVED",
            "SINGLE_RUNTIME_ATTACH_ONLY",
            "No distributed consensus",
            "global multi-host repository journal linearizability",
            "monetary budget",
            "token budget",
            "production deployment",
        ):
            self.assertIn(token, note)

        self.assertEqual(payload["observed_from"]["commit"], "c67ed65c9c26bc2a59b39786c5c410cd8490cbc7")
        self.assertEqual(payload["observed_from"]["tree"], "96dfdfb4cc26c094895b010aacc11a3b685d62fc")
        self.assertEqual(payload["freshness"]["state"], "STALE")

    def test_repository_mutation_pep_remains_single_runtime_attach_only(self):
        text = (ROOT / "cyber_lion" / "enterprise" / "repository_mutation_pep.py").read_text(encoding="utf-8")
        self.assertIn("SINGLE_RUNTIME_ATTACH_ONLY", text)


if __name__ == "__main__":
    unittest.main()
