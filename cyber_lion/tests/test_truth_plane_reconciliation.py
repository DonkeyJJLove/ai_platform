from __future__ import annotations

import copy
import json
import os
import subprocess
from pathlib import Path
import unittest

from cyber_lion.architecture_projection.truth_plane import (
    CARRIER_PATHS,
    CURRENTNESS_MODE,
    SUBJECT_DIGEST_DOMAIN,
    SubjectEntry,
    TruthProjectionError,
    classify_candidate_base_currentness,
    derive_subject_currentness,
    subject_digest,
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

    def _isolated_currentness_fixture_state(self):
        state = self.state()

        for record in state["records"]:
            if (
                record.get("plane") == "CANDIDATE"
                and record.get("status")
                in {
                    "CURRENT_MASTER_BASE_CANDIDATE",
                    "CURRENT_STACKED_CANDIDATE",
                }
            ):
                record["status"] = "STALE_BASE_CANDIDATE"

        return state

    def _entries_for_tree(self, treeish="HEAD"):
        proc = subprocess.run(
            ["git", "ls-tree", "-r", "-z", treeish],
            check=True,
            capture_output=True,
        )
        entries = []
        for raw in proc.stdout.split(b"\0"):
            if not raw:
                continue
            meta, path = raw.split(b"\t", 1)
            mode, object_type, object_sha = meta.decode("ascii").split()
            entries.append(SubjectEntry(path.decode("utf-8"), mode, object_type, object_sha))
        return tuple(entries)

    def checkout_subject_digest(self, treeish="HEAD"):
        return subject_digest(self._entries_for_tree(treeish))


    def validate(
        self,
        payload=None,
        *,
        head=None,
        tree=FIXTURE_MASTER_TREE,
        current_subject_digest=None,
    ):
        value = self.state() if payload is None else payload

        if head is None:
            current_bases = {
                item["base_head"]
                for item in value["records"]
                if (
                    item.get("plane") == "CANDIDATE"
                    and item.get("status") == "CURRENT_MASTER_BASE_CANDIDATE"
                )
            }

            head = (
                next(iter(current_bases))
                if len(current_bases) == 1
                else FIXTURE_MASTER_HEAD
            )

        observed = (
            current_subject_digest
            or value["baseline"]["subject_digest"]
        )

        return validate_truth_projection(
            value,
            current_head=head,
            current_tree=tree,
            current_subject_digest=observed,
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

    def _resolve_live_pr(self, pr_number):
        self.assertIsInstance(pr_number, int, "LIVE_PR_NUMBER_INVALID")
        self.assertGreater(pr_number, 0, "LIVE_PR_NUMBER_INVALID")
        exact_ref = f"refs/pull/{pr_number}/head"
        proc = subprocess.run(
            ["git", "ls-remote", "--exit-code", "origin", exact_ref],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(proc.returncode, 0, f"LIVE_PR_REF_UNAVAILABLE:{pr_number}")
        lines = [line for line in proc.stdout.splitlines() if line.strip()]
        self.assertEqual(len(lines), 1, f"LIVE_PR_REF_CARDINALITY_INVALID:{pr_number}")
        head, resolved_ref = lines[0].split()
        self.assertEqual(resolved_ref, exact_ref, f"LIVE_PR_REF_RESOLUTION_INVALID:{pr_number}")
        fetched = subprocess.run(
            ["git", "fetch", "--no-tags", "--depth=1", "origin", exact_ref],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
            timeout=30,
        )
        self.assertEqual(fetched.returncode, 0, f"LIVE_PR_REF_FETCH_FAILED:{pr_number}:{fetched.stderr.strip()}")
        fetched_head = subprocess.run(
            ["git", "rev-parse", "FETCH_HEAD^{commit}"],
            check=True, capture_output=True, text=True,
        ).stdout.strip()
        tree = subprocess.run(
            ["git", "rev-parse", "FETCH_HEAD^{tree}"],
            check=True, capture_output=True, text=True,
        ).stdout.strip()
        self.assertEqual(fetched_head, head, f"LIVE_PR_REF_FETCH_DRIFT:{pr_number}")
        return head, tree


    def _candidate_currentness_evidence(
        self,
        record,
        *,
        current_head,
        current_tree,
    ):
        self.assertEqual(record["plane"], "CANDIDATE")

        if record["base_head"] == current_head:
            return None

        fetched = subprocess.run(
            [
                "git",
                "fetch",
                "--no-tags",
                "--depth=64",
                "origin",
                "refs/heads/master",
            ],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
            timeout=60,
        )

        self.assertEqual(
            fetched.returncode,
            0,
            f"LIVE_MASTER_HISTORY_FETCH_FAILED:{fetched.stderr.strip()}",
        )

        revs = subprocess.run(
            [
                "git",
                "rev-list",
                "--first-parent",
                "--reverse",
                f"{record['base_head']}..{current_head}",
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )

        self.assertEqual(
            revs.returncode,
            0,
            f"LIVE_ANCESTRY_UNAVAILABLE:{record['id']}",
        )

        shas = [
            line.strip()
            for line in revs.stdout.splitlines()
            if line.strip()
        ]

        chain = []
        expected_parent = record["base_head"]

        for sha in shas:
            parent = subprocess.run(
                ["git", "rev-parse", f"{sha}^1"],
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()

            self.assertEqual(
                parent,
                expected_parent,
                f"LIVE_ANCESTRY_NONCONTIGUOUS:{record['id']}",
            )

            paths = subprocess.run(
                ["git", "diff", "--name-only", parent, sha],
                check=True,
                capture_output=True,
                text=True,
            ).stdout.splitlines()

            paths = [
                item.strip()
                for item in paths
                if item.strip()
            ]

            self.assertTrue(
                paths,
                f"LIVE_ANCESTRY_EMPTY_DELTA:{record['id']}:{sha}",
            )

            chain.append(
                {
                    "sha": sha,
                    "parent_sha": parent,
                    "paths": paths,
                }
            )

            expected_parent = sha

        return {
            "pr": record["pr"],
            "candidate_head": record["head"],
            "candidate_tree": record["tree"],
            "base_head": record["base_head"],
            "current_head": current_head,
            "current_tree": current_tree,
            "ancestry_verified": expected_parent == current_head,
            "intervening_commits": chain,
        }

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
        baseline = state["baseline"]
        self.assertEqual(baseline["subject_digest_domain"], SUBJECT_DIGEST_DOMAIN)
        self.assertEqual(baseline["currentness_mode"], CURRENTNESS_MODE)
        self.assertEqual(len(baseline["subject_digest"]), 64)
        self.assertNotIn("head", baseline)
        self.assertNotIn("tree", baseline)
        self.assertNotIn("currentness", baseline)


    def test_live_master_truth_projection_is_current(self):
        head, tree = self.live_identity()

        observed_head, observed_tree = self._resolve_live_branch(
            "master"
        )

        self.assertEqual(
            observed_head,
            head,
            "LIVE_MASTER_HEAD_DRIFT",
        )

        self.assertEqual(
            observed_tree,
            tree,
            "LIVE_MASTER_TREE_DRIFT",
        )

        live_digest = self.checkout_subject_digest("FETCH_HEAD")

        live_state_text = subprocess.run(
            [
                "git",
                "show",
                f"FETCH_HEAD:{STATE_PATH.as_posix()}",
            ],
            check=True,
            capture_output=True,
            text=True,
        ).stdout

        live_state = json.loads(live_state_text)

        live_candidate_evidence = {}
        for record in live_state["records"]:
            if (
                record.get("plane") == "CANDIDATE"
                and record.get("status") == "CURRENT_MASTER_BASE_CANDIDATE"
                and record.get("base_head") != head
            ):
                live_candidate_evidence[record["pr"]] = (
                    self._candidate_currentness_evidence(
                        record,
                        current_head=head,
                        current_tree=tree,
                    )
                )

        validated_live = validate_truth_projection(
            live_state,
            current_head=head,
            current_tree=tree,
            current_subject_digest=live_digest,
            candidate_currentness_evidence=live_candidate_evidence,
        )

        self.assertEqual(
            validated_live["baseline"]["subject_digest"],
            live_digest,
        )

        self.assertEqual(
            derive_subject_currentness(
                validated_live["baseline"]["subject_digest"],
                live_digest,
            ),
            "CURRENT",
        )

        local_digest = self.checkout_subject_digest("HEAD")
        local_declared = self.state()["baseline"]["subject_digest"]

        self.assertEqual(
            local_declared,
            local_digest,
            "CHECKOUT_SUBJECT_DIGEST_DRIFT",
        )

        self.assertEqual(
            derive_subject_currentness(
                local_declared,
                local_digest,
            ),
            "CURRENT",
        )

    def test_live_registry_generated_from_is_current(self):
        registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
        declared = self.state()["baseline"]["subject_digest"]
        self.assertEqual(registry["generated_from"], f"truth-subject-v1@{declared}")


    def test_live_candidate_frontier_is_exact(self):
        if not self._live_gate_enabled():
            self.skipTest(
                "LIVE_CURRENTNESS_EVIDENCE_UNAVAILABLE"
            )

        master, master_tree = self.live_identity()

        records = {
            item["id"]: item
            for item in self.state()["records"]
        }

        candidates = [
            item
            for item in records.values()
            if item["plane"] == "CANDIDATE"
        ]

        for record in candidates:
            head, tree = self._resolve_live_pr(record["pr"])

            self.assertEqual(
                record["head"],
                head,
                f"STALE_CANDIDATE_HEAD:{record['id']}",
            )

            self.assertEqual(
                record["tree"],
                tree,
                f"STALE_CANDIDATE_TREE:{record['id']}",
            )

        current_compatible = {
            "CURRENT_MASTER_BASE_CANDIDATE",
            "CURRENT_STACKED_CANDIDATE",
        }

        for record in candidates:
            status = record["status"]

            if status == "CURRENT_MASTER_BASE_CANDIDATE":
                evidence = (
                    None
                    if record["base_head"] == master
                    else self._candidate_currentness_evidence(
                        record,
                        current_head=master,
                        current_tree=master_tree,
                    )
                )

                classification = (
                    classify_candidate_base_currentness(
                        pr=record["pr"],
                        candidate_head=record["head"],
                        candidate_tree=record["tree"],
                        base_head=record["base_head"],
                        current_head=master,
                        current_tree=master_tree,
                        evidence=evidence,
                    )
                )

                self.assertEqual(
                    classification,
                    "CURRENT_COMPATIBLE",
                    f"CURRENT_CANDIDATE_NOT_LIVE_COMPATIBLE:{record['id']}",
                )

            elif status == "CURRENT_STACKED_CANDIDATE":
                parents = [
                    item
                    for item in candidates
                    if item["head"] == record["base_head"]
                ]

                self.assertEqual(
                    len(parents),
                    1,
                    f"CURRENT_STACK_PARENT_CARDINALITY:{record['id']}",
                )

                self.assertIn(
                    parents[0]["status"],
                    current_compatible,
                    f"CURRENT_STACK_PARENT_STALE:{record['id']}",
                )

            elif status == "STALE_BASE_CANDIDATE":
                self.assertNotEqual(
                    record["base_head"],
                    master,
                    f"STALE_CANDIDATE_CLAIMS_LIVE_MASTER:{record['id']}",
                )

            else:
                self.fail(
                    f"UNKNOWN_CANDIDATE_STATUS:{record['id']}:{status}"
                )

        mediation = records["GlobalCompleteMediation"]

        self.assertEqual(
            (
                mediation["plane"],
                mediation["status"],
                mediation["integrated"],
            ),
            ("UNKNOWN", "UNKNOWN", False),
        )

    def test_wrong_subject_digest_fails_closed(self):
        with self.assertRaisesRegex(TruthProjectionError, "baseline subject digest contradiction"):
            self.validate(current_subject_digest="f" * 64)

    def test_malformed_subject_digest_fails_closed(self):
        with self.assertRaisesRegex(TruthProjectionError, "exact lowercase SHA-256"):
            self.validate(current_subject_digest="not-a-digest")

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
        candidate = next(item for item in state["records"] if item["id"] == "LCMS")
        candidate["integrated"] = True
        with self.assertRaisesRegex(TruthProjectionError, "candidate silently promoted"):
            self.validate(state)


    def test_current_master_candidate_cannot_carry_stale_base(self):
        state = self.state()

        candidate = next(
            item
            for item in state["records"]
            if item["id"] == "ActionSpec"
        )
        candidate.update({
            "plane": "CANDIDATE",
            "status": "CURRENT_MASTER_BASE_CANDIDATE",
            "evidence_refs": ["PR#279"],
            "integrated": False,
            "pr": 279,
            "head": "3c6929f35623a3f4a16cfdc129ffbbf660a6d1f6",
            "tree": "d1b15db9a399fa6e6bbeae760827f02ce8158d61",
            "base_head": "af1e5da79ebd83dfca2d22ba1fc9cab372e54b5e",
        })

        self.assertNotEqual(
            candidate["base_head"],
            FIXTURE_MASTER_HEAD,
        )

        with self.assertRaisesRegex(
            TruthProjectionError,
            "candidate base currentness is unproven",
        ):
            self.validate(
                state,
                head=FIXTURE_MASTER_HEAD,
            )

    def test_stale_candidate_cannot_hide_current_master_base(self):
        state = self._isolated_currentness_fixture_state()
        candidate = next(item for item in state["records"] if item["id"] == "B0GenerativityProtocol")
        candidate["base_head"] = FIXTURE_MASTER_HEAD
        with self.assertRaisesRegex(TruthProjectionError, "candidate base currentness contradiction"):
            self.validate(state, head=FIXTURE_MASTER_HEAD)

    def test_stacked_candidate_cannot_claim_master_base(self):
        state = self._isolated_currentness_fixture_state()
        candidate = next(item for item in state["records"] if item["id"] == "LCMS")
        candidate["base_head"] = FIXTURE_MASTER_HEAD
        with self.assertRaisesRegex(TruthProjectionError, "candidate base currentness contradiction"):
            self.validate(state, head=FIXTURE_MASTER_HEAD)

    def test_historical_projection_cannot_claim_current_after_material_drift(self):
        state = self.state()
        state["historical_projections"][0]["currentness"] = "CURRENT"
        with self.assertRaisesRegex(TruthProjectionError, "historical currentness contradiction"):
            self.validate(state)

    def _selected_c0_state(self, *, base_head):
        state = self.state()
        action = next(item for item in state["records"] if item["id"] == "ActionSpec")
        action.update({
            "plane": "CANDIDATE",
            "status": "CURRENT_MASTER_BASE_CANDIDATE",
            "integrated": False,
            "pr": 279,
            "head": "3c6929f35623a3f4a16cfdc129ffbbf660a6d1f6",
            "tree": "d1b15db9a399fa6e6bbeae760827f02ce8158d61",
            "base_head": base_head,
            "evidence_refs": [
                "PR#279",
                "cyber_lion/contracts/v1/action_spec.schema.json@3c6929f35623a3f4a16cfdc129ffbbf660a6d1f6",
            ],
        })
        next(item for item in state["records"] if item["id"] == "LCMS")["status"] = "STALE_BASE_CANDIDATE"
        next(item for item in state["records"] if item["id"] == "ReadonlyProcessAdapter")["status"] = "STALE_BASE_CANDIDATE"
        return state, action

    def _candidate_evidence(self, action, *, current_head, current_tree, chain, verified=True, **overrides):
        value = {
            "pr": action["pr"],
            "candidate_head": action["head"],
            "candidate_tree": action["tree"],
            "base_head": action["base_head"],
            "current_head": current_head,
            "current_tree": current_tree,
            "ancestry_verified": verified,
            "intervening_commits": chain,
        }
        value.update(overrides)
        return value

    def _validate_selected_c0(self, state, action, *, current_head, current_tree=FIXTURE_MASTER_TREE, evidence=None):
        kwargs = {} if evidence is None else {"candidate_currentness_evidence": {action["pr"]: evidence}}
        return validate_truth_projection(
            state,
            current_head=current_head,
            current_tree=current_tree,
            current_subject_digest=state["baseline"]["subject_digest"],
            **kwargs,
        )

    def test_f01_exact_base_equals_live_master_is_current(self):
        state, action = self._selected_c0_state(base_head=FIXTURE_MASTER_HEAD)
        self._validate_selected_c0(state, action, current_head=FIXTURE_MASTER_HEAD)

    def test_f02_one_carrier_only_descendant_is_current(self):
        base = "1" * 40
        current = "2" * 40
        state, action = self._selected_c0_state(base_head=base)
        evidence = self._candidate_evidence(action, current_head=current, current_tree=FIXTURE_MASTER_TREE, chain=[{
            "sha": current, "parent_sha": base, "paths": ["LION/architecture/canonical-state-v1-3-candidate.json"]
        }])
        self._validate_selected_c0(state, action, current_head=current, evidence=evidence)

    def test_f03_multiple_contiguous_carrier_only_descendants_are_current(self):
        base, mid, current = "1" * 40, "2" * 40, "3" * 40
        state, action = self._selected_c0_state(base_head=base)
        evidence = self._candidate_evidence(action, current_head=current, current_tree=FIXTURE_MASTER_TREE, chain=[
            {"sha": mid, "parent_sha": base, "paths": ["LION/architecture/canonical-state-v1-3-candidate.json"]},
            {"sha": current, "parent_sha": mid, "paths": ["cyber_lion/registry/repositories.json"]},
        ])
        self._validate_selected_c0(state, action, current_head=current, evidence=evidence)

    def test_f04_canonical_state_only_descendant_is_current(self):
        self.test_f02_one_carrier_only_descendant_is_current()

    def test_f05_registry_only_descendant_is_current(self):
        base, current = "4" * 40, "5" * 40
        state, action = self._selected_c0_state(base_head=base)
        evidence = self._candidate_evidence(action, current_head=current, current_tree=FIXTURE_MASTER_TREE, chain=[{
            "sha": current, "parent_sha": base, "paths": ["cyber_lion/registry/repositories.json"]
        }])
        self._validate_selected_c0(state, action, current_head=current, evidence=evidence)

    def _assert_nonprojection_descendant_is_stale(self, path):
        base, current = "6" * 40, "7" * 40
        state, action = self._selected_c0_state(base_head=base)
        evidence = self._candidate_evidence(action, current_head=current, current_tree=FIXTURE_MASTER_TREE, chain=[{
            "sha": current, "parent_sha": base, "paths": [path]
        }])
        with self.assertRaisesRegex(TruthProjectionError, "current master-base candidate is stale"):
            self._validate_selected_c0(state, action, current_head=current, evidence=evidence)

    def test_f06_truth_test_descendant_is_stale(self):
        self._assert_nonprojection_descendant_is_stale("cyber_lion/tests/test_truth_plane_reconciliation.py")

    def test_f07_truth_plane_descendant_is_stale(self):
        self._assert_nonprojection_descendant_is_stale("cyber_lion/architecture_projection/truth_plane.py")

    def test_f08_c0_source_descendant_is_stale(self):
        self._assert_nonprojection_descendant_is_stale("cyber_lion/contracts/v1/action_spec.schema.json")

    def test_f09_arbitrary_production_source_descendant_is_stale(self):
        self._assert_nonprojection_descendant_is_stale("cyber_lion/enterprise/control_plane.py")

    def test_f10_workflow_descendant_is_stale(self):
        self._assert_nonprojection_descendant_is_stale(".github/workflows/cyber-lion-core.yml")

    def _assert_unproven(self, chain, *, verified=True, max_commits=None):
        base, current = "8" * 40, "9" * 40
        state, action = self._selected_c0_state(base_head=base)
        evidence = self._candidate_evidence(action, current_head=current, current_tree=FIXTURE_MASTER_TREE, chain=chain, verified=verified)
        kwargs = {}
        if max_commits is not None:
            result = classify_candidate_base_currentness(
                pr=action["pr"], candidate_head=action["head"], candidate_tree=action["tree"],
                base_head=base, current_head=current, current_tree=FIXTURE_MASTER_TREE,
                evidence=evidence, max_projection_commits=max_commits,
            )
            self.assertEqual(result, "UNKNOWN")
            return
        with self.assertRaisesRegex(TruthProjectionError, "candidate base currentness is unproven"):
            self._validate_selected_c0(state, action, current_head=current, evidence=evidence)

    def test_f11_broken_parent_chain_is_unknown(self):
        self._assert_unproven([{"sha": "9" * 40, "parent_sha": "a" * 40, "paths": ["LION/architecture/canonical-state-v1-3-candidate.json"]}])

    def test_f12_missing_ancestry_proof_is_unknown(self):
        self._assert_unproven([{"sha": "9" * 40, "parent_sha": "8" * 40, "paths": ["LION/architecture/canonical-state-v1-3-candidate.json"]}], verified=False)

    def test_f13_omitted_intervening_commit_is_unknown(self):
        self._assert_unproven([{"sha": "9" * 40, "parent_sha": "a" * 40, "paths": ["LION/architecture/canonical-state-v1-3-candidate.json"]}])

    def test_f14_reordered_ancestry_is_unknown(self):
        self._assert_unproven([
            {"sha": "a" * 40, "parent_sha": "b" * 40, "paths": ["LION/architecture/canonical-state-v1-3-candidate.json"]},
            {"sha": "9" * 40, "parent_sha": "8" * 40, "paths": ["cyber_lion/registry/repositories.json"]},
        ])

    def test_f15_more_than_16_projection_commits_is_unknown(self):
        base = "8" * 40
        chain = []
        parent = base
        for index in range(17):
            sha = f"{index + 1:040x}"
            chain.append({"sha": sha, "parent_sha": parent, "paths": ["LION/architecture/canonical-state-v1-3-candidate.json"]})
            parent = sha
        action_head = "3c6929f35623a3f4a16cfdc129ffbbf660a6d1f6"
        result = classify_candidate_base_currentness(
            pr=279, candidate_head=action_head, candidate_tree="d1b15db9a399fa6e6bbeae760827f02ce8158d61",
            base_head=base, current_head=parent, current_tree=FIXTURE_MASTER_TREE,
            evidence={
                "pr": 279, "candidate_head": action_head, "candidate_tree": "d1b15db9a399fa6e6bbeae760827f02ce8158d61",
                "base_head": base, "current_head": parent, "current_tree": FIXTURE_MASTER_TREE,
                "ancestry_verified": True, "intervening_commits": chain,
            },
        )
        self.assertEqual(result, "UNKNOWN")

    def _assert_identity_substitution_denied(self, key, replacement):
        base, current = "b" * 40, "c" * 40
        state, action = self._selected_c0_state(base_head=base)
        evidence = self._candidate_evidence(action, current_head=current, current_tree=FIXTURE_MASTER_TREE, chain=[{
            "sha": current, "parent_sha": base, "paths": ["LION/architecture/canonical-state-v1-3-candidate.json"]
        }])
        evidence[key] = replacement
        with self.assertRaisesRegex(TruthProjectionError, "candidate currentness evidence identity mismatch"):
            self._validate_selected_c0(state, action, current_head=current, evidence=evidence)

    def test_f16_candidate_base_substitution_is_denied(self):
        self._assert_identity_substitution_denied("base_head", "d" * 40)

    def test_f17_candidate_head_substitution_is_denied(self):
        self._assert_identity_substitution_denied("candidate_head", "d" * 40)

    def test_f18_candidate_tree_substitution_is_denied(self):
        self._assert_identity_substitution_denied("candidate_tree", "d" * 40)

    def test_f19_pr_identity_substitution_is_denied(self):
        self._assert_identity_substitution_denied("pr", 256)

    def test_f20_serialized_current_without_proof_is_denied(self):
        state, action = self._selected_c0_state(base_head="e" * 40)
        with self.assertRaisesRegex(TruthProjectionError, "candidate base currentness is unproven"):
            self._validate_selected_c0(state, action, current_head="f" * 40)

    def test_f21_stale_c1_cannot_become_current_by_selected_c0_relabel(self):
        state, action = self._selected_c0_state(base_head=FIXTURE_MASTER_HEAD)
        c1 = next(item for item in state["records"] if item["id"] == "LCMS")
        c1["status"] = "CURRENT_STACKED_CANDIDATE"
        with self.assertRaisesRegex(TruthProjectionError, "stacked candidate parent identity is ambiguous or missing"):
            self._validate_selected_c0(state, action, current_head=FIXTURE_MASTER_HEAD)

    def test_f22_stale_c2_cannot_become_current_through_stale_c1(self):
        state, action = self._selected_c0_state(base_head=FIXTURE_MASTER_HEAD)
        c1 = next(item for item in state["records"] if item["id"] == "LCMS")
        c1["status"] = "STALE_BASE_CANDIDATE"
        c2 = next(item for item in state["records"] if item["id"] == "ReadonlyProcessAdapter")
        c2["status"] = "CURRENT_STACKED_CANDIDATE"
        with self.assertRaisesRegex(TruthProjectionError, "stacked candidate parent is not current-compatible"):
            self._validate_selected_c0(state, action, current_head=FIXTURE_MASTER_HEAD)

    def test_r16_carrier_only_sync_keeps_selected_c0_current_without_rewriting_genealogy(self):
        base = "af1e5da79ebd83dfca2d22ba1fc9cab372e54b5e"
        sync = "62312e4e93acc7145c031006d330f21476539f28"
        state, action = self._selected_c0_state(base_head=base)
        evidence = self._candidate_evidence(action, current_head=sync, current_tree="a31e8d072e1c725c6b8efabe43c5cd8131b13c11", chain=[{
            "sha": sync, "parent_sha": base, "paths": [
                "LION/architecture/canonical-state-v1-3-candidate.json",
                "cyber_lion/registry/repositories.json",
            ]
        }])
        self._validate_selected_c0(
            state, action, current_head=sync, current_tree="a31e8d072e1c725c6b8efabe43c5cd8131b13c11", evidence=evidence
        )
        self.assertEqual(action["base_head"], base)
        records = {item["id"]: item for item in state["records"]}
        self.assertEqual(records["LCMS"]["status"], "STALE_BASE_CANDIDATE")
        self.assertEqual(records["ReadonlyProcessAdapter"]["status"], "STALE_BASE_CANDIDATE")

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
        self.assertEqual(registry["generated_from"], f"truth-subject-v1@{self.state()['baseline']['subject_digest']}")

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
        records = {
            item["id"]: item
            for item in self.validate()["records"]
        }

        candidates = {
            record_id: record
            for record_id, record in records.items()
            if record["plane"] == "CANDIDATE"
        }

        persistent_candidates = {
            "B0GenerativityProtocol",
            "LCMS",
            "ReadonlyProcessAdapter",
            "HybridModelRouter",
            "PhysicalActionSpec",
            "P0EntryCandidate",
        }
        self.assertIn(
            set(candidates),
            (persistent_candidates, persistent_candidates | {"ActionSpec"}),
        )

        canonical_statuses = {
            "CURRENT_MASTER_BASE_CANDIDATE",
            "CURRENT_STACKED_CANDIDATE",
            "STALE_BASE_CANDIDATE",
        }

        for record_id, record in candidates.items():
            self.assertFalse(record["integrated"], f"CANDIDATE_INTEGRATED:{record_id}")
            self.assertIsInstance(record["pr"], int, f"CANDIDATE_PR_INVALID:{record_id}")
            self.assertGreater(record["pr"], 0)
            for field in ("head", "tree", "base_head"):
                self.assertIsInstance(record[field], str, f"CANDIDATE_IDENTITY_INVALID:{record_id}:{field}")
                self.assertEqual(len(record[field]), 40, f"CANDIDATE_IDENTITY_LENGTH:{record_id}:{field}")
            self.assertIn(record["status"], canonical_statuses, f"CANDIDATE_STATUS_INVALID:{record_id}")

        for record_id in persistent_candidates:
            self.assertEqual(
                candidates[record_id]["status"],
                "STALE_BASE_CANDIDATE",
                f"KNOWN_STALE_CANDIDATE_NOT_EXPLICIT:{record_id}",
            )

        action = records["ActionSpec"]
        if action["plane"] == "CANDIDATE":
            self.assertEqual(set(candidates), persistent_candidates | {"ActionSpec"})
            self.assertEqual(action["status"], "STALE_BASE_CANDIDATE")
            self.assertFalse(action["integrated"])
            self.assertEqual(action["pr"], 286)
            self.assertEqual(action["head"], "7176409f8d43c0b04eac57aaada98ad201c2d556")
            self.assertEqual(action["tree"], "ce644dd231d49c0f69bbb51e8bb472acba0c0e05")
            self.assertEqual(action["base_head"], "db51d0eb8784cb3b9a45a180aa421b35bc86d9c3")
        else:
            self.assertEqual(set(candidates), persistent_candidates)
            self.assertEqual(action["plane"], "AS_IS")
            self.assertEqual(action["status"], "INTEGRATED_VERIFIED_PRIMITIVE")
            self.assertTrue(action["integrated"])
            self.assertIsNone(action["pr"])
            self.assertIsNone(action["head"])
            self.assertIsNone(action["tree"])
            self.assertIsNone(action["base_head"])
            self.assertIn("cyber_lion/contracts/v1/action_spec.schema.json", action["evidence_refs"])
            self.assertIn("cyber_lion/contracts/v1/action_spec_support_matrix.json", action["evidence_refs"])
            self.assertIn("PR#286", action["evidence_refs"])
            master_refs = [ref for ref in action["evidence_refs"] if ref.startswith("master:")]
            self.assertEqual(len(master_refs), 1)
            self.assertRegex(master_refs[0], r"^master:[0-9a-f]{40}$")

        mediation = records["GlobalCompleteMediation"]
        self.assertEqual(
            (mediation["plane"], mediation["status"], mediation["integrated"]),
            ("UNKNOWN", "UNKNOWN", False),
        )

    def test_subject_digest_is_order_independent_and_carrier_only_change_is_invisible(self):
        entries = self._entries_for_tree()
        baseline = subject_digest(entries)
        self.assertEqual(subject_digest(tuple(reversed(entries))), baseline)
        changed = tuple(
            SubjectEntry(e.path, e.mode, e.object_type, "f" * 40) if e.path in CARRIER_PATHS else e
            for e in entries
        )
        self.assertEqual(subject_digest(changed), baseline)

    def test_noncarrier_blob_mutation_degrades_subject_currentness(self):
        entries = list(self._entries_for_tree())
        idx = next(i for i, e in enumerate(entries) if e.path not in CARRIER_PATHS and e.mode == "100644")
        e = entries[idx]
        entries[idx] = SubjectEntry(e.path, e.mode, e.object_type, "f" * 40)
        declared = subject_digest(self._entries_for_tree())
        mutated = subject_digest(entries)
        self.assertNotEqual(mutated, declared)
        self.assertEqual(derive_subject_currentness(declared, mutated), "STALE")

    def test_included_entry_mode_mutation_degrades_subject_currentness(self):
        entries = list(self._entries_for_tree())
        idx = next(i for i, e in enumerate(entries) if e.path not in CARRIER_PATHS and e.mode == "100644")
        e = entries[idx]
        entries[idx] = SubjectEntry(e.path, "100755", e.object_type, e.object_sha)
        declared = subject_digest(self._entries_for_tree())
        self.assertEqual(derive_subject_currentness(declared, subject_digest(entries)), "STALE")

    def test_included_entry_addition_and_deletion_degrade_subject_currentness(self):
        entries = list(self._entries_for_tree())
        declared = subject_digest(entries)
        added = entries + [SubjectEntry("synthetic/r9-negative.txt", "100644", "blob", "a" * 40)]
        self.assertEqual(derive_subject_currentness(declared, subject_digest(added)), "STALE")
        drop = next(i for i, e in enumerate(entries) if e.path not in CARRIER_PATHS)
        deleted = entries[:drop] + entries[drop + 1:]
        self.assertEqual(derive_subject_currentness(declared, subject_digest(deleted)), "STALE")

    def test_serialized_current_cannot_self_promote_projection(self):
        state = self.state()
        state["baseline"]["currentness"] = "CURRENT"
        with self.assertRaisesRegex(TruthProjectionError, "baseline keys are not canonical"):
            self.validate(state)

    def test_subject_entry_validation_is_fail_closed(self):
        entries = list(self._entries_for_tree())
        with self.assertRaisesRegex(TruthProjectionError, "unsupported Git leaf mode/type"):
            subject_digest(entries + [SubjectEntry("synthetic/bad", "100600", "blob", "a" * 40)])
        with self.assertRaisesRegex(TruthProjectionError, "subject path is not canonical"):
            subject_digest(entries + [SubjectEntry("../escape", "100644", "blob", "a" * 40)])
        with self.assertRaisesRegex(TruthProjectionError, "duplicate subject path"):
            subject_digest(entries + [entries[0]])

    def test_lair_truth_is_target_or_post_merge_integrated(self):
        record = next(item for item in self.validate()["records"] if item["id"] == "LAIR")
        if record["plane"] == "TARGET":
            self.assertEqual(record["status"], "TARGET_NOT_INTEGRATED")
            self.assertFalse(record["integrated"])
            self.assertEqual(record["evidence_refs"], [])
            for field in ("pr", "head", "tree", "base_head"):
                self.assertIsNone(record[field])
            return

        self.assertEqual(record["plane"], "AS_IS")
        self.assertEqual(record["status"], "INTEGRATED_VERIFIED_PRIMITIVE")
        self.assertTrue(record["integrated"])
        for field in ("pr", "head", "tree", "base_head"):
            self.assertIsNone(record[field])
        self.assertIn("cyber_lion/contracts/action_ir.py", record["evidence_refs"])
        self.assertIn("cyber_lion/contracts/v1/action_spec.schema.json", record["evidence_refs"])
        pr_refs = [ref for ref in record["evidence_refs"] if ref.startswith("PR#")]
        self.assertEqual(len(pr_refs), 1)
        self.assertRegex(pr_refs[0], r"^PR#[1-9][0-9]*$")
        master_refs = [ref for ref in record["evidence_refs"] if ref.startswith("master:")]
        self.assertEqual(len(master_refs), 1)
        self.assertRegex(master_refs[0], r"^master:[0-9a-f]{40}$")

    def test_global_complete_mediation_remains_unknown(self):
        record = next(item for item in self.validate()["records"] if item["id"] == "GlobalCompleteMediation")
        self.assertEqual(record["plane"], "UNKNOWN")
        self.assertEqual(record["status"], "UNKNOWN")
        self.assertFalse(record["integrated"])


if __name__ == "__main__":
    unittest.main()
