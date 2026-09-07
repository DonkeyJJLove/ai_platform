import unittest

from cyber_lion.tests.experiments.bean_generativity import (
    GenerativityProblem,
    GenerativityProtocolError,
)


class R22FFactoryGenerativityFalsifier(unittest.TestCase):
    def test_general_factory_generativity_is_falsified_by_out_of_grammar_family(self):
        problem = GenerativityProblem(
            problem_id="r22f-out-of-grammar",
            problem_family="continuous-signal-transform",
            required_capability="continuous-transform",
            input_kind="float-list",
            output_kind="int",
            training_examples=(),
            holdout_examples=(),
            provenance_refs=("r22f:falsifier",),
            baseline_revision="r22f",
            baseline_tree_digest="r22f",
        )
        with self.assertRaises(GenerativityProtocolError):
            problem.validate()


if __name__ == "__main__":
    unittest.main()
