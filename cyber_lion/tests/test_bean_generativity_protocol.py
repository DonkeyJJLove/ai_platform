from __future__ import annotations

import inspect
import json
import unittest

from cyber_lion.tests.experiments.bean_generativity import (
    BeanGenerativityProtocol,
    GenerativityExample,
    GenerativityProblem,
)
from cyber_lion.enterprise.complete_mediation import EffectSurfaceScanner
import cyber_lion.tests.experiments.bean_generativity as generativity


REPO = "DonkeyJJLove/ai_platform"
BASELINE = "9082a974e8105dd7e47afc889583b1fc67535b59"
TREE = "1414a21efce8f35892134060cd0d77f2d4d08e9b"


def text_problem() -> GenerativityProblem:
    return GenerativityProblem(
        problem_id="unseen-text-canonicalization-r1",
        problem_family="heterogeneous-text-normalization",
        required_capability="canonicalize-untrusted-label-sequence",
        input_kind="text-list",
        output_kind="text-list",
        training_examples=(
            GenerativityExample(
                "txt-train-1", (" B ", "a", "b", "A "), ("a", "b")
            ),
            GenerativityExample(
                "txt-train-2", (" z", "Y ", "y", "Z"), ("y", "z")
            ),
        ),
        holdout_examples=(
            GenerativityExample(
                "txt-holdout-1", (" C", "c ", "A", "a"), ("a", "c")
            ),
            GenerativityExample(
                "txt-holdout-2", ("Q ", " q", "R"), ("q", "r")
            ),
        ),
        provenance_refs=("b0:evidence:text-fixture-v1", "b0:holdout:text-v1"),
        baseline_revision=BASELINE,
        baseline_tree_digest=TREE,
    ).validate()


def telemetry_problem(*, falsify_holdout: bool = False) -> GenerativityProblem:
    expected = 3 if falsify_holdout else 2
    return GenerativityProblem(
        problem_id=(
            "falsification-telemetry-r1"
            if falsify_holdout
            else "unseen-telemetry-threshold-r1"
        ),
        problem_family="numeric-telemetry-reduction",
        required_capability="count-high-telemetry-samples",
        input_kind="int-list",
        output_kind="int",
        training_examples=(
            GenerativityExample("num-train-1", (1, 7, 8, 10), 3),
            GenerativityExample("num-train-2", (7, 7, 6), 2),
            GenerativityExample("num-train-3", (0, 1, 2), 0),
        ),
        holdout_examples=(
            GenerativityExample("num-holdout-1", (6, 7, 9), expected),
            GenerativityExample("num-holdout-2", (7, 0, 7, 8), 3),
        ),
        provenance_refs=(
            "b0:evidence:telemetry-fixture-v1",
            "b0:holdout:telemetry-v1",
        ),
        baseline_revision=BASELINE,
        baseline_tree_digest=TREE,
    ).validate()


class BeanGenerativityProtocolTests(unittest.TestCase):
    def test_two_dissimilar_unseen_problem_families_terminal_pass(self):
        protocol = BeanGenerativityProtocol()
        text = protocol.run(text_problem())
        telemetry = protocol.run(telemetry_problem())

        self.assertEqual(text.status, "PASS")
        self.assertEqual(telemetry.status, "PASS")
        self.assertEqual(text.workflow_type, telemetry.workflow_type)
        self.assertNotEqual(text.problem_family, telemetry.problem_family)
        self.assertNotEqual(text.problem_digest, telemetry.problem_digest)
        self.assertNotEqual(text.generated_spec_digest, telemetry.generated_spec_digest)
        self.assertTrue(text.verified_candidate_digest)
        self.assertTrue(telemetry.verified_candidate_digest)
        self.assertEqual(text.resolution_disposition, "GENERATE_SPEC")
        self.assertEqual(telemetry.resolution_disposition, "GENERATE_SPEC")
        for evidence in (text, telemetry):
            self.assertEqual(
                (
                    evidence.authority_effect,
                    evidence.execution_effect,
                    evidence.repository_ref_effect,
                    evidence.external_effect,
                ),
                ("NONE", "NONE", "NONE", "NONE"),
            )

        print(
            "B0_TERMINAL_EVIDENCE="
            + json.dumps(
                {
                    "baseline": BASELINE,
                    "tree": TREE,
                    "workflow_type": text.workflow_type,
                    "problems": [
                        {
                            "problem_id": text.problem_id,
                            "family": text.problem_family,
                            "status": text.status,
                            "terminal_digest": text.digest(),
                            "verified_candidate_digest": (
                                text.verified_candidate_digest
                            ),
                            "generated_spec_digest": text.generated_spec_digest,
                        },
                        {
                            "problem_id": telemetry.problem_id,
                            "family": telemetry.problem_family,
                            "status": telemetry.status,
                            "terminal_digest": telemetry.digest(),
                            "verified_candidate_digest": (
                                telemetry.verified_candidate_digest
                            ),
                            "generated_spec_digest": telemetry.generated_spec_digest,
                        },
                    ],
                    "attach": "NONE",
                    "authority_effect": "NONE",
                },
                sort_keys=True,
                separators=(",", ":"),
            )
        )

    def test_holdout_counterexample_is_explicit_falsification_not_fake_pass(self):
        evidence = BeanGenerativityProtocol().run(
            telemetry_problem(falsify_holdout=True)
        )
        self.assertEqual(evidence.status, "FALSIFIED")
        self.assertFalse(evidence.verified_candidate_digest)
        self.assertIn("holdout mismatch", evidence.failure_reason)
        self.assertEqual(evidence.repository_ref_effect, "NONE")

    def test_protocol_source_contains_no_problem_specific_workflow_switch(self):
        source = inspect.getsource(generativity)
        for forbidden in (
            "unseen-text-canonicalization-r1",
            "unseen-telemetry-threshold-r1",
            "heterogeneous-text-normalization",
            "numeric-telemetry-reduction",
        ):
            self.assertNotIn(forbidden, source)
        self.assertNotIn("subprocess", source)
        self.assertNotIn("urllib", source)
        self.assertNotIn("requests", source)
        self.assertNotIn("socket.", source)
        self.assertNotIn("git push", source)

    def test_protocol_has_no_detected_effect_surface(self):
        source = inspect.getsource(generativity)
        inventory = EffectSurfaceScanner().scan(
            repository=REPO,
            revision=BASELINE,
            tree_digest=TREE,
            sources={"cyber_lion/enterprise/bean_generativity.py": source},
        )
        self.assertEqual(inventory.surfaces, ())
        self.assertEqual(inventory.unclassified_refs, ())


if __name__ == "__main__":
    unittest.main()