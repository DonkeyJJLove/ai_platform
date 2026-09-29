import unittest
from cyber_lion.contracts.evidence_bound_learning_episode import *
Z="0"*64
def ev(cls,avail="2026-09-25T10:00:00Z",ing="2026-09-25T10:00:00Z",inc=True):
    return EpisodeEvidenceRef("ref:"+cls.lower(),Z,cls,"2026-09-25T09:00:00Z","2026-09-25T09:30:00Z",ing,avail,inc)
class EBLETests(unittest.TestCase):
    def episode(self,**kw):
        d=dict(episode_id="ep:1",model_release_ref="release:1",causal_group_ref="cg:1",task_family="UNKNOWN_RECOVERY",episode_class="CONTRASTIVE_CANDIDATE",outcome="PARTIAL",input_cutoff="2026-09-25T11:00:00Z",decision_time="2026-09-25T11:05:00Z",message_refs=("msg:1",),invocation_refs=("inv:1",),attempt_refs=("att:1",),assignment_refs=("as:1",),model_call_refs=(),broker_receipt_refs=(),result_refs=("res:1",),observation_refs=("obs:1",),reconciliation_refs=("rec:1",),evidence=(ev("INDEPENDENT_OBSERVATION"),),teacher_output_refs=(),rights_basis_ref="rights:1",classification="INTERNAL",allowed_uses=("EVALUATION",),teacher_consultation_scope="NONE")
        d.update(kw);return EvidenceBoundLearningEpisode(**d)
    def test_future_evidence_cannot_enter_input(self):
        late=ev("INDEPENDENT_OBSERVATION","2026-09-25T12:00:00Z","2026-09-25T12:00:00Z",True)
        with self.assertRaises(EvidenceBoundLearningEpisodeError):self.episode(evidence=(late,)).sealed()
    def test_teacher_output_is_not_ground_truth(self):
        with self.assertRaises(EvidenceBoundLearningEpisodeError):self.episode(episode_class="POSITIVE_CANDIDATE",outcome="CONFIRMED_SUCCESS",evidence=(ev("TEACHER_OUTPUT"),),teacher_output_refs=("teacher:1",)).sealed()
    def test_unknown_is_not_positive_or_negative(self):
        with self.assertRaises(EvidenceBoundLearningEpisodeError):self.episode(episode_class="NEGATIVE_CANDIDATE",outcome="UNKNOWN").sealed()
    def test_existing_rnd_bridge(self):
        e=self.episode().sealed();obs=to_evidence_observation(e,source_digest=Z,observed_at="2026-09-25T12:00:00Z");self.assertEqual(obs.observation_kind,"EVIDENCE_BOUND_LEARNING_EPISODE")
if __name__=="__main__":unittest.main()
