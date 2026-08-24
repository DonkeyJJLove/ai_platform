import unittest

from cyber_lion.enterprise.code_perception_observation import (
    CodePerceptionObservationError,
    ObservationRequest,
    parse_projection_lines,
    select_exact_run,
    validate_commit_identity,
)


EXPECTED = ObservationRequest(
    repository="DonkeyJJLove/ai_platform",
    workflow_name="Cyber-Lion Core",
    workflow_id=337046823,
    workflow_path=".github/workflows/cyber-lion-contracts.yml",
    branch="master",
    head_sha="f" * 40,
    tree_sha="e" * 40,
    tree_semantic_digest="d" * 64,
    file_count=336,
    symbol_count=4272,
    edge_count=28185,
)


class CodePerceptionObservationTests(unittest.TestCase):
    def exact_run(self, **overrides):
        item = {
            "id": 123,
            "name": "Cyber-Lion Core",
            "workflow_id": 337046823,
            "path": ".github/workflows/cyber-lion-contracts.yml",
            "event": "push",
            "head_branch": "master",
            "head_sha": "f" * 40,
            "status": "completed",
            "conclusion": "success",
        }
        item.update(overrides)
        return item

    def exact_commit(self, **overrides):
        item = {
            "sha": "f" * 40,
            "commit": {"tree": {"sha": "e" * 40}},
        }
        item.update(overrides)
        return item

    def test_select_exact_run_positive(self):
        run = select_exact_run({"workflow_runs": [self.exact_run()]}, EXPECTED)
        self.assertEqual(run["id"], 123)

    def test_reject_wrong_workflow_name(self):
        with self.assertRaises(CodePerceptionObservationError):
            select_exact_run({"workflow_runs": [self.exact_run(name="Other")]}, EXPECTED)

    def test_reject_same_name_wrong_workflow_id(self):
        with self.assertRaises(CodePerceptionObservationError):
            select_exact_run({"workflow_runs": [self.exact_run(workflow_id=999)]}, EXPECTED)

    def test_reject_same_name_wrong_workflow_path(self):
        with self.assertRaises(CodePerceptionObservationError):
            select_exact_run({"workflow_runs": [self.exact_run(path=".github/workflows/impostor.yml")]}, EXPECTED)

    def test_failed_canonical_workflow_cannot_be_replaced_by_successful_impostor(self):
        canonical_failed = self.exact_run(conclusion="failure")
        impostor = self.exact_run(id=124, workflow_id=999, path=".github/workflows/impostor.yml")
        with self.assertRaises(CodePerceptionObservationError):
            select_exact_run({"workflow_runs": [canonical_failed, impostor]}, EXPECTED)

    def test_reject_pull_request_run(self):
        with self.assertRaises(CodePerceptionObservationError):
            select_exact_run({"workflow_runs": [self.exact_run(event="pull_request")]}, EXPECTED)

    def test_reject_wrong_branch(self):
        with self.assertRaises(CodePerceptionObservationError):
            select_exact_run({"workflow_runs": [self.exact_run(head_branch="feature")]}, EXPECTED)

    def test_reject_wrong_head(self):
        with self.assertRaises(CodePerceptionObservationError):
            select_exact_run({"workflow_runs": [self.exact_run(head_sha="a" * 40)]}, EXPECTED)

    def test_reject_non_success(self):
        with self.assertRaises(CodePerceptionObservationError):
            select_exact_run({"workflow_runs": [self.exact_run(conclusion="failure")]}, EXPECTED)

    def test_reject_duplicate_exact_runs(self):
        with self.assertRaises(CodePerceptionObservationError):
            select_exact_run({"workflow_runs": [self.exact_run(), self.exact_run(id=124)]}, EXPECTED)

    def test_commit_identity_positive(self):
        self.assertEqual(validate_commit_identity(self.exact_commit(), EXPECTED), "e" * 40)

    def test_reject_commit_head_substitution(self):
        with self.assertRaisesRegex(CodePerceptionObservationError, "head substitution"):
            validate_commit_identity(self.exact_commit(sha="a" * 40), EXPECTED)

    def test_reject_expected_tree_substitution(self):
        payload = {"sha": "f" * 40, "commit": {"tree": {"sha": "a" * 40}}}
        with self.assertRaisesRegex(CodePerceptionObservationError, "tree substitution"):
            validate_commit_identity(payload, EXPECTED)

    def test_projection_line_positive(self):
        line = (
            "CODE_PERCEPTION_CANDIDATE_PROJECTION "
            f"head={'f' * 40} tree={'e' * 40} digest={'c' * 64} "
            f"tree_semantic_digest={'d' * 64} files=336 symbols=4272 edges=28185"
        )
        matches = parse_projection_lines([line], EXPECTED)
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["digest"], "c" * 64)

    def test_projection_wrong_head_is_rejected(self):
        line = (
            "CODE_PERCEPTION_CANDIDATE_PROJECTION "
            f"head={'a' * 40} tree={'e' * 40} digest={'c' * 64} "
            f"tree_semantic_digest={'d' * 64} files=336 symbols=4272 edges=28185"
        )
        self.assertEqual(parse_projection_lines([line], EXPECTED), ())

    def test_projection_wrong_tree_is_rejected(self):
        line = (
            "CODE_PERCEPTION_CANDIDATE_PROJECTION "
            f"head={'f' * 40} tree={'a' * 40} digest={'c' * 64} "
            f"tree_semantic_digest={'d' * 64} files=336 symbols=4272 edges=28185"
        )
        self.assertEqual(parse_projection_lines([line], EXPECTED), ())

    def test_projection_wrong_counts_are_rejected(self):
        line = (
            "CODE_PERCEPTION_CANDIDATE_PROJECTION "
            f"head={'f' * 40} tree={'e' * 40} digest={'c' * 64} "
            f"tree_semantic_digest={'d' * 64} files=335 symbols=4272 edges=28185"
        )
        self.assertEqual(parse_projection_lines([line], EXPECTED), ())

    def test_projection_missing_line_is_rejected_by_absence(self):
        self.assertEqual(parse_projection_lines(["no projection here"], EXPECTED), ())


if __name__ == "__main__":
    unittest.main()
