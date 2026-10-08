"""Falsifiers for the independent always-run PR merge currentness gate."""
from __future__ import annotations

from pathlib import Path
import json
import tempfile
import unittest
from unittest.mock import patch

from tools import lion_pr_merge_gate as gate

ROOT = Path(__file__).resolve().parents[2]
BASE = "a" * 40
HEAD = "b" * 40
MERGE = "c" * 40
TREE = "d" * 40
CANDIDATE_TREE = "e" * 40
REPO = "DonkeyJJLove/ai_platform"


def event():
    return {
        "pull_request": {
            "number": 429,
            "base": {"ref": "master", "sha": BASE, "repo": {"full_name": REPO}},
            "head": {"sha": HEAD},
        },
    }


def live_pr():
    return {"number": 429, "state": "open", "base": {"ref": "master", "sha": BASE}, "head": {"sha": HEAD}}


def live_branch():
    return {"commit": {"sha": BASE}}


def raw_commit(*, parents=(BASE, HEAD), tree=TREE):
    return ("tree " + tree + "\n" + "".join("parent " + p + "\n" for p in parents) +
            "author operator <operator@example.test> 1 +0000\n\nmsg\n").encode()


class PrMergeGateTests(unittest.TestCase):
    def test_valid_two_parent_synthetic_merge(self):
        self.assertEqual(gate.parse_commit(raw_commit()), {"tree": TREE, "parents": [BASE, HEAD]})

    def test_missing_or_extra_parents_fail_closed(self):
        for parents in ((BASE,), (BASE, HEAD, "f" * 40), ()):
            with self.subTest(parents=parents), self.assertRaisesRegex(gate.MergeGateError, "cardinality"):
                gate.parse_commit(raw_commit(parents=parents))

    def test_duplicate_trees_fail_closed(self):
        with self.assertRaisesRegex(gate.MergeGateError, "cardinality"):
            gate.parse_commit(b"tree " + TREE.encode() + b"\ntree " + TREE.encode() +
                              b"\nparent " + BASE.encode() + b"\nparent " + HEAD.encode() + b"\n\n")

    def test_project_and_base_scope_must_match(self):
        good = gate.extract_event(event(), REPO)
        self.assertEqual(good["pr_number"], 429)
        for mutation in ("base-ref", "base-repo", "head"):
            candidate = event()
            if mutation == "base-ref":
                candidate["pull_request"]["base"]["ref"] = "dev"
            elif mutation == "base-repo":
                candidate["pull_request"]["base"]["repo"]["full_name"] = "foreign/repo"
            else:
                candidate["pull_request"]["head"]["sha"] = "not_sha"
            with self.subTest(mutation=mutation), self.assertRaises(gate.MergeGateError):
                gate.extract_event(candidate, REPO)

    def test_exact_live_identity_binds_both_parents_and_trees(self):
        value = gate.validate_live(
            gate.extract_event(event(), REPO), live_pr(), live_branch(),
            MERGE, gate.parse_commit(raw_commit()), TREE, CANDIDATE_TREE,
        )
        self.assertEqual(value["synthetic_parents"], [BASE, HEAD])
        self.assertEqual(value["candidate_tree"], CANDIDATE_TREE)
        self.assertEqual(value["execution_tree"], TREE)
        # A real merge can differ from the candidate's tree. This is not false drift.
        self.assertNotEqual(value["execution_tree"], value["candidate_tree"])

    def test_stale_pr_or_master_denies(self):
        identity = gate.extract_event(event(), REPO)
        variants = [
            ({"number": 429, "state": "closed", "base": {"ref": "master", "sha": BASE}, "head": {"sha": HEAD}}, live_branch()),
            ({"number": 429, "state": "open", "base": {"ref": "master", "sha": "f" * 40}, "head": {"sha": HEAD}}, live_branch()),
            (live_pr(), {"commit": {"sha": "f" * 40}}),
        ]
        for pr, branch in variants:
            with self.subTest(pr=pr, branch=branch), self.assertRaises(gate.MergeGateError):
                gate.validate_live(identity, pr, branch, MERGE, gate.parse_commit(raw_commit()), TREE, CANDIDATE_TREE)

    def test_swapped_parent_or_checkout_tree_denies(self):
        identity = gate.extract_event(event(), REPO)
        for parents, tree in (((HEAD, BASE), TREE), ((BASE, HEAD), "f" * 40)):
            with self.subTest(parents=parents, tree=tree), self.assertRaises(gate.MergeGateError):
                gate.validate_live(identity, live_pr(), live_branch(), MERGE,
                                   gate.parse_commit(raw_commit(parents=parents)),
                                   tree, CANDIDATE_TREE)

    def test_checkout_sha_drift_denies_before_network(self):
        def fake_git(_root, *args, **_):
            return "f" * 40 if args == ("rev-parse", "HEAD") else ""
        with patch.object(gate, "git", side_effect=fake_git):
            with self.assertRaisesRegex(gate.MergeGateError, "checkout_does_not_match"):
                gate.evaluate(ROOT, event(), {"GITHUB_REPOSITORY": REPO, "GITHUB_SHA": MERGE, "GITHUB_TOKEN": "x"},
                              api_get=lambda *_: self.fail("network must not be reached"))

    def test_valid_mocked_live_evidence_is_read_only(self):
        def fake_git(_root, *args, **kwargs):
            outputs = {
                ("rev-parse", "HEAD"): MERGE,
                ("cat-file", "-p", "HEAD"): raw_commit(),
                ("rev-parse", "HEAD^{tree}"): TREE,
                ("rev-parse", "HEAD^2^{tree}"): CANDIDATE_TREE,
            }
            return outputs[args]
        def fake_api(url, token):
            self.assertEqual(token, "read-only")
            return live_branch() if url.endswith("/branches/master") else live_pr()
        with (patch.object(gate, "git", side_effect=fake_git),
              patch.object(gate, "truth_currentness", return_value={"subject_digest": "f" * 64, "tracked_git_leaves": 1}),
              patch("tools.lion_workflow_homeostasis.audit", return_value={"blocking_defect_count": 0, "audit_digest": "f" * 64, "workflow_count": 27})):
            v = gate.evaluate(ROOT, event(), {"GITHUB_REPOSITORY": REPO, "GITHUB_SHA": MERGE, "GITHUB_TOKEN": "read-only"}, api_get=fake_api)
        self.assertFalse(v["other_workflows_aggregated"])
        self.assertEqual(v["source"]["execution_sha"], MERGE)

    def test_workflow_defect_denies(self):
        with patch.object(gate, "git", side_effect=lambda _root, *a, **kw:
                          {("rev-parse", "HEAD"): MERGE, ("cat-file", "-p", "HEAD"): raw_commit(),
                           ("rev-parse", "HEAD^{tree}"): TREE, ("rev-parse", "HEAD^2^{tree}"): CANDIDATE_TREE}[a]):
            with patch("tools.lion_workflow_homeostasis.audit", return_value={"blocking_defect_count": 1}):
                with self.assertRaisesRegex(gate.MergeGateError, "workflow_homeostasis_blocking"):
                    gate.evaluate(ROOT, event(), {"GITHUB_REPOSITORY": REPO, "GITHUB_SHA": MERGE, "GITHUB_TOKEN": "read-only"},
                                  api_get=lambda url, _: live_branch() if url.endswith("/branches/master") else live_pr())

    def test_current_repository_truth_bound(self):
        actual = gate.truth_currentness(ROOT)
        self.assertEqual(len(actual["subject_digest"]), 64)
        self.assertGreater(actual["tracked_git_leaves"], 1000)

    def test_no_merge_authority_or_automatic_effect(self):
        self.assertEqual(gate.SCHEMA, "lion.pr-merge-currentness-gate/v1")
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "event.json").write_text("{}", encoding="utf-8")
            code = gate.main(["--repository", str(ROOT), "--event", str(root / "event.json"),
                              "--output", str(root / "result.json")])
            record = json.loads((root / "result.json").read_text(encoding="utf-8"))
            self.assertEqual(code, 2)
            self.assertEqual(record["result"], "FAIL_CLOSED")
            self.assertEqual(record["authority_effect"], "NONE")
            self.assertFalse(record["merge_executed"])


if __name__ == "__main__":
    unittest.main()
