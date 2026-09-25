import unittest
from cyber_lion.contracts.coordinator_competency import *
class CoordinatorCompetencyTests(unittest.TestCase):
    def rows(self):
        return tuple(CompetencyEvidence(c,("task:"+c.lower(),),("evidence:"+c.lower(),),"PASS") for c in COMPETENCIES)
    def test_each_competency_has_own_evidence(self):
        p=CoordinatorCompetencyProfile("profile:1","release:1",self.rows()).validate()
        self.assertEqual(len(p.records),10)
    def test_missing_competency_fails(self):
        with self.assertRaises(CoordinatorCompetencyError):CoordinatorCompetencyProfile("p","r",self.rows()[:-1]).validate()
    def test_better_competence_does_not_widen_authority(self):
        with self.assertRaises(CoordinatorCompetencyError):CoordinatorCompetencyProfile("p","r",self.rows(),authority_effect="WRITE").validate()
if __name__=="__main__":unittest.main()
