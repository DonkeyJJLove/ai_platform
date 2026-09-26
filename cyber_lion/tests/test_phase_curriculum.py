from __future__ import annotations
import unittest

from cyber_lion.mission_control import phase_curriculum as curriculum
from tools.phase_curriculum_test_harness import PhaseCurriculumTests as _Harness


class PhaseCurriculumContractTests(unittest.TestCase):
    def test_contract_classification_is_semantic_not_phase_id(self):
        case=_Harness("test_contract_classification_is_semantic_not_phase_id")
        case.setUp()
        try:
            case.test_contract_classification_is_semantic_not_phase_id()
        finally:
            case.tearDown()

    def test_p06_lineage_composes_verified_lessons(self):
        case=_Harness("test_p06_style_lineage_is_composed_from_prior_lessons")
        case.setUp()
        try:
            case.test_p06_style_lineage_is_composed_from_prior_lessons()
        finally:
            case.tearDown()


if __name__=="__main__":
    unittest.main()
