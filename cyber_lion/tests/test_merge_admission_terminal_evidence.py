from __future__ import annotations

import inspect
import unittest

from cyber_lion.enterprise.merge_admission_terminal_evidence import (
    R6TerminalEvidenceError,
    _rejecting_verifier,
    render_terminal_evidence,
    run_non_consuming_admission,
    validate_exact_identity,
    validate_terminal_literals,
)

HEAD = "d" * 40
TREE = "e" * 40
PARENT = "c" * 40


class R6MergeAdmissionTerminalEvidenceTests(unittest.TestCase):
    def test_successful_admission_emits_exactly_one_ok(self):
        result = run_non_consuming_admission(
            head_sha=HEAD, parent_sha=PARENT, suffix="allow"
        )
        lines = render_terminal_evidence(result)
        validate_terminal_literals(lines)
        self.assertEqual(lines.count("MERGE_ADMISSION_TERMINAL=OK"), 1)
        self.assertEqual(lines.count("NO_MERGE_AUTHORIZATION_INFERRED=YES"), 1)

    def test_denied_admission_cannot_emit_ok(self):
        result = run_non_consuming_admission(
            head_sha=HEAD, parent_sha=PARENT, suffix="deny",
            verifier=_rejecting_verifier,
        )
        lines = render_terminal_evidence(result)
        validate_terminal_literals(lines)
        self.assertIn("MERGE_ADMISSION_TERMINAL=DENY", lines)
        self.assertNotIn("MERGE_ADMISSION_TERMINAL=OK", lines)

    def test_step_or_test_success_cannot_create_terminal_ok(self):
        parameters = inspect.signature(render_terminal_evidence).parameters
        self.assertNotIn("test_success", parameters)
        self.assertNotIn("job_success", parameters)
        with self.assertRaises(R6TerminalEvidenceError):
            render_terminal_evidence(True)  # type: ignore[arg-type]

    def test_non_consuming_path_never_infers_merge_authorization(self):
        result = run_non_consuming_admission(
            head_sha=HEAD, parent_sha=PARENT, suffix="non-consuming"
        )
        lines = render_terminal_evidence(result)
        self.assertIn("NO_MERGE_AUTHORIZATION_INFERRED=YES", lines)

    def test_duplicate_terminal_literal_fails_closed(self):
        with self.assertRaises(R6TerminalEvidenceError):
            validate_terminal_literals((
                "MERGE_ADMISSION_TERMINAL=OK",
                "MERGE_ADMISSION_TERMINAL=OK",
                "NO_MERGE_AUTHORIZATION_INFERRED=YES",
            ))

    def test_contradictory_terminal_literal_fails_closed(self):
        with self.assertRaises(R6TerminalEvidenceError):
            validate_terminal_literals((
                "MERGE_ADMISSION_TERMINAL=OK",
                "MERGE_ADMISSION_TERMINAL=DENY",
                "NO_MERGE_AUTHORIZATION_INFERRED=YES",
            ))

    def test_missing_terminal_literal_fails_closed(self):
        with self.assertRaises(R6TerminalEvidenceError):
            validate_terminal_literals(("NO_MERGE_AUTHORIZATION_INFERRED=YES",))

    def test_duplicate_no_authorization_literal_fails_closed(self):
        with self.assertRaises(R6TerminalEvidenceError):
            validate_terminal_literals((
                "MERGE_ADMISSION_TERMINAL=OK",
                "NO_MERGE_AUTHORIZATION_INFERRED=YES",
                "NO_MERGE_AUTHORIZATION_INFERRED=YES",
            ))

    def test_candidate_head_tree_parent_mismatch_fails_before_acceptance(self):
        with self.assertRaises(R6TerminalEvidenceError):
            validate_exact_identity(
                expected_head=HEAD, expected_tree=TREE, expected_parent=PARENT,
                actual_head=HEAD, actual_tree="f" * 40, actual_parent=PARENT,
            )

    def test_exact_candidate_identity_passes(self):
        validate_exact_identity(
            expected_head=HEAD, expected_tree=TREE, expected_parent=PARENT,
            actual_head=HEAD, actual_tree=TREE, actual_parent=PARENT,
        )


if __name__ == "__main__":
    unittest.main()
