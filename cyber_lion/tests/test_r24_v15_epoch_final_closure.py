import hashlib
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "LION/evidence/r24-v15-epoch-final-closure"


class R24V15EpochFinalClosureTests(unittest.TestCase):
    def test_branch_ledger_is_closed_world(self):
        data = json.loads((EVIDENCE / "BRANCH_CLOSURE_LEDGER.json").read_text(encoding="utf-8"))
        rows = data["branches"]
        self.assertEqual(data["remote_non_master_branch_count"], 68)
        self.assertEqual(len(rows), 68)
        self.assertEqual(len({x["branch"] for x in rows}), 68)
        self.assertEqual(len({(x["branch"], x["head"]) for x in rows}), 68)
        self.assertEqual(data["unknown_count"], 0)
        self.assertFalse(any(x["classification"] == "UNKNOWN" for x in rows))
        self.assertEqual(
            data["class_counts"],
            {
                "DIAGNOSTIC_ARCHIVE": 8,
                "INTEGRATED_BY_MERGED_PR": 25,
                "INTEGRATED_BY_SUCCESSOR": 5,
                "INTEGRATED_EXACT": 9,
                "SELECTIVE_PORT_REQUIRED": 1,
                "SUPERSEDED": 20,
            },
        )

    def test_selective_port_is_exact_and_present(self):
        data = json.loads((EVIDENCE / "BRANCH_CLOSURE_LEDGER.json").read_text(encoding="utf-8"))
        selected = [x for x in data["branches"] if x["classification"] == "SELECTIVE_PORT_REQUIRED"]
        self.assertEqual([x["branch"] for x in selected], ["mission/r24-bounded-mutation-substrate-bootstrap-r1"])
        port = data["selective_port"]
        self.assertEqual(port["state"], "STAGED_IN_FINAL_CLOSURE_CANDIDATE")
        self.assertEqual(set(port["source_sha256"]), set(port["candidate_sha256"]))
        for rel, expected in port["candidate_sha256"].items():
            observed = hashlib.sha256((ROOT / rel).read_bytes()).hexdigest()
            self.assertEqual(observed, expected, rel)
        self.assertNotEqual(
            port["source_sha256"]["cyber_lion/mission_control/bounded_mutation_substrate.py"],
            port["candidate_sha256"]["cyber_lion/mission_control/bounded_mutation_substrate.py"],
        )

    def test_next_epoch_candidate_is_explicitly_preserved(self):
        data = json.loads((EVIDENCE / "BRANCH_CLOSURE_LEDGER.json").read_text(encoding="utf-8"))
        nxt = data["preserved_next_epoch_local_candidate"]
        self.assertEqual(nxt["branch"], "mission/v15-communication-envelope-r1")
        self.assertEqual(nxt["head"], "55ddb1e9496127ca6e23d7896463c7c12d13b118")
        self.assertFalse(nxt["remote_ref_present"])

    def test_security_input_binds_all_current_alerts_without_dismissal(self):
        data = json.loads((EVIDENCE / "SECURITY_CLOSURE_INPUT.json").read_text(encoding="utf-8"))
        self.assertEqual(data["baseline_head"], "46cbc109ec283e3e87554d733699afeba783df7b")
        self.assertEqual(data["open_code_scanning_count"], 12)
        self.assertEqual(data["dependabot_open"], 0)
        self.assertEqual(data["secret_scanning_open"], 0)
        self.assertFalse(data["dismiss_or_suppress_as_fix"])
        self.assertEqual(len(data["alerts"]), 12)
        self.assertEqual({x["ref"] for x in data["alerts"]}, {"refs/heads/master"})
        self.assertEqual({x["commit_sha"] for x in data["alerts"]}, {data["baseline_head"]})
        groups = data["root_cause_groups"]
        self.assertEqual(groups["JS_CODE_CONSTRUCTION"]["count"], 7)
        self.assertEqual(groups["LPCL_REGEX_REDOS"]["count"], 4)
        self.assertEqual(groups["FIREFOX_RESPONSE_TOKEN_PLAINTEXT"]["count"], 1)


if __name__ == "__main__":
    unittest.main()
