import unittest
from dataclasses import replace
from cyber_lion.contracts.cognitive_invocation import *
from cyber_lion.contracts.evidence_bound_learning_episode import *
from cyber_lion.contracts.model_call_v2 import *
from cyber_lion.contracts.model_release import *
from cyber_lion.contracts.coordinator_competency import *
Z="0"*64
def evidence(cls,*,available="2026-09-25T10:00:00Z",ingested="2026-09-25T10:00:00Z",included=True):
    return EpisodeEvidenceRef("ref:"+cls.lower(),Z,cls,"2026-09-25T09:00:00Z","2026-09-25T09:30:00Z",ingested,available,included)
def episode(**changes):
    values=dict(episode_id="ep:eval",model_release_ref="release:1",causal_group_ref="cg:1",task_family="UNKNOWN_RECOVERY",episode_class="CONTRASTIVE_CANDIDATE",outcome="PARTIAL",input_cutoff="2026-09-25T11:00:00Z",decision_time="2026-09-25T11:05:00Z",message_refs=("msg:1",),invocation_refs=("inv:1",),attempt_refs=("att:1",),assignment_refs=("as:1",),model_call_refs=(),broker_receipt_refs=(),result_refs=("res:1",),observation_refs=("obs:1",),reconciliation_refs=("rec:1",),evidence=(evidence("INDEPENDENT_OBSERVATION"),),teacher_output_refs=(),rights_basis_ref="rights:1",classification="INTERNAL",allowed_uses=("EVALUATION",),teacher_consultation_scope="NONE")
    values.update(changes);return EvidenceBoundLearningEpisode(**values)
class V15CognitiveEvolutionBehavioralEvals(unittest.TestCase):
    def test_TRANSPORT_READY_IS_NOT_COGNITION_DONE(self):
        c=InvocationCurrentness("inv:1","CURRENT","CURRENT","UNKNOWN","UNKNOWN","2026-09-25T10:00:00Z",("obs:1",)).validate()
        r=InvocationReconciliation("inv:1","att:1",Z,None,None,"UNKNOWN",("obs:1",)).validate()
        self.assertEqual(c.transport_state,"CURRENT");self.assertEqual(r.state,"UNKNOWN")
    def test_SENTINELX_READY_IS_NOT_SAAS_SESSION_READY(self):
        c=InvocationCurrentness("inv:1","CURRENT","UNKNOWN","UNKNOWN","UNKNOWN","2026-09-25T10:00:00Z",("sentinelx:ready",)).validate()
        self.assertEqual(c.session_state,"UNKNOWN")
    def test_MODEL_HEARTBEAT_IS_NOT_INFERENCE(self):
        c=InvocationCurrentness("inv:1","CURRENT","NOT_APPLICABLE","CURRENT","CURRENT","2026-09-25T10:00:00Z",("heartbeat:1",)).validate()
        self.assertNotEqual(c.runtime_state,"RECONCILED")
    def test_UNKNOWN_INVOCATION_REQUIRES_RECONCILIATION(self):
        rec=InvocationReceipt("receipt:1","att:1","transport:sentinelx","OUTCOME_UNKNOWN",None,"2026-09-25T10:00:00Z").validate()
        self.assertEqual(rec.state,"OUTCOME_UNKNOWN");self.assertIsNone(rec.result_digest)
    def test_DUAL_LEGS_KEEP_SEPARATE_IDENTITY(self):
        a=InvocationIntent("inv:local","parent:1","msg:1",Z,"binding:l",Z,"LOCAL","route:1","PLANNING","2026-09-25T12:00:00Z","causal:dual").validate()
        b=InvocationIntent("inv:saas","parent:1","msg:1",Z,"binding:s",Z,"SAAS","route:1","PLANNING","2026-09-25T12:00:00Z","causal:dual").validate()
        self.assertNotEqual(a.invocation_id,b.invocation_id);self.assertEqual(a.causal_group_ref,b.causal_group_ref)
    def test_COGNITIVE_RESULT_IS_NOT_AUTHORITY(self):
        with self.assertRaises(ModelCallV2Error):
            ModelCallV2("mc:1","m:1","p:1","t:1","a:1","inv:1","att:1","provider:1","release:1","transport:local","cg:1","planning","LOCAL",Z,Z,"RESPONSE_RECONCILED",authority_effect="ALLOW").sealed()
    def test_TEACHER_OUTPUT_IS_NOT_GROUND_TRUTH(self):
        with self.assertRaises(EvidenceBoundLearningEpisodeError):
            episode(episode_class="POSITIVE_CANDIDATE",outcome="CONFIRMED_SUCCESS",evidence=(evidence("TEACHER_OUTPUT"),),teacher_output_refs=("teacher:1",)).sealed()
    def test_FUTURE_EVIDENCE_CANNOT_ENTER_INPUT(self):
        late=evidence("INDEPENDENT_OBSERVATION",available="2026-09-25T12:00:00Z",ingested="2026-09-25T12:00:00Z")
        with self.assertRaises(EvidenceBoundLearningEpisodeError):episode(evidence=(late,)).sealed()
    def test_UNKNOWN_EPISODE_IS_NOT_POSITIVE_OR_NEGATIVE(self):
        with self.assertRaises(EvidenceBoundLearningEpisodeError):episode(episode_class="POSITIVE_CANDIDATE",outcome="UNKNOWN").sealed()
    def test_MODEL_RELEASE_CANNOT_CHANGE_IN_PLACE(self):
        r=ModelRelease("release:1",Z,None,Z,Z,Z,Z,Z,Z).sealed()
        with self.assertRaises(ModelReleaseError):replace(r,prompt_profile_digest="1"*64).validate()
    def test_BETTER_COMPETENCE_DOES_NOT_WIDEN_AUTHORITY(self):
        rows=tuple(CompetencyEvidence(c,("task:1",),("evidence:1",),"PASS") for c in COMPETENCIES)
        with self.assertRaises(CoordinatorCompetencyError):CoordinatorCompetencyProfile("profile:1","release:1",rows,authority_effect="WRITE").validate()
if __name__=="__main__":unittest.main()
