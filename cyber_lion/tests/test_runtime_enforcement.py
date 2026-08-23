import unittest
from datetime import datetime,timezone
from cyber_lion.contracts.policy_gate import GateApplied,PDPDecisionReceipt
from cyber_lion.contracts.runtime_enforcement import RequestedRuntimeEffect,RuntimeIdentityBinding
from cyber_lion.enterprise.control_plane import ActionProposal
from cyber_lion.enterprise.live_authority_admission import LiveAdmittedAuthority,LiveAuthorityAdmission
from cyber_lion.enterprise.runtime_enforcement import InMemoryRuntimeAdmissionReplayGuard,RuntimeAdmissionEngine,RuntimeEnforcementError
Z="0"*64
NOW=datetime(2026,8,23,13,0,tzinfo=timezone.utc)

class FakeAdmission(LiveAuthorityAdmission):
    def __init__(self,fail=False,changed=False):self.fail=fail;self.changed=changed
    def revalidate(self,admitted,*,now):
        if self.fail:raise RuntimeError("revoked")
        if self.changed:return LiveAdmittedAuthority(**{**admitted.__dict__,"epoch_state_version":admitted.epoch_state_version+1})
        return admitted

def authority():
    return LiveAdmittedAuthority(repository="DonkeyJJLove/ai_platform",pr_number=1,base_sha="a"*40,head_sha="b"*40,mission_id="mission:1",grant_id="grant:1",lineage_digest=Z,provenance_id="prov",epoch=1,epoch_state_version=1,authority_ceiling="external_write",root_grant_id="grant:1",root_grant_digest=Z,authenticated_grant_digests=(Z,),leaf_key_id="key",leaf_algorithm="ed25519",replay_digest=Z,admitted_at="2026-08-23T12:00:00+00:00").validate()

def proposal(authority_class="read",target="workspace/input.txt"):
    return ActionProposal("proposal:1","mission:1","swarm:1","agent:1","cap",authority_class,"READ_FILE" if authority_class=="read" else "WRITE_FILE",target,True,("ev",),("trace",),payload_digest=Z).validate()

def gate(p,obs="HEALTHY"):
    return GateApplied("gate:1","request:1",p.proposal_id,"ALLOW",p.requested_authority,"policy@1:sha256:"+Z,Z,Z,Z,obs,"GREEN","ok").sealed()

def receipt(g):
    return PDPDecisionReceipt("receipt:1",g.request_id,g.gate_event_id,Z,g.decision_digest,Z).validate()

def identity(workload="workload:1"):
    return RuntimeIdentityBinding(workload,"subject:1","runtime:1","sandbox:1","workspace:1",Z).validate()

def effect(p,i,obs="HEALTHY",resource=None):
    return RequestedRuntimeEffect("effect:1",p.proposal_id,p.mission_id,"policy@1:sha256:"+Z,Z,p.requested_authority,p.action_class,resource or p.target,Z,obs,i.digest()).validate()

class RuntimeAdmissionTests(unittest.TestCase):
    def engine(self,**kw):return RuntimeAdmissionEngine(authority_admission=FakeAdmission(**kw),replay_guard=InMemoryRuntimeAdmissionReplayGuard())
    def admit(self,engine=None,p=None,g=None,r=None,a=None,i=None,e=None):
        p=p or proposal();g=g or gate(p);r=r or receipt(g);a=a or authority();i=i or identity();e=e or effect(p,i,g.observability_state)
        return (engine or self.engine()).admit(gate=g,pdp_receipt=r,admitted_authority=a,proposal=p,effect=e,runtime_identity=i,trusted_now=NOW)
    def test_exact_chain_produces_sealed_admission(self):
        out=self.admit();out.validate();self.assertEqual(out.policy_binding,"policy@1:sha256:"+Z);self.assertEqual(len(out.admission_digest),64)
    def test_gate_replay_is_single_use_for_exact_effect(self):
        eng=self.engine();self.admit(engine=eng);self.assertRaises(RuntimeEnforcementError,self.admit,eng)
    def test_wrong_resource_is_denied(self):
        p=proposal();i=identity();self.assertRaises(RuntimeEnforcementError,self.admit,None,p,None,None,None,i,effect(p,i,resource="workspace/other.txt"))
    def test_wrong_workload_identity_digest_is_denied(self):
        p=proposal();good=identity();other=identity("workload:other");self.assertRaises(RuntimeEnforcementError,self.admit,None,p,None,None,None,other,effect(p,good))
    def test_revoked_authority_fails_before_runtime_admission(self):
        self.assertRaises(RuntimeEnforcementError,self.admit,self.engine(fail=True))
    def test_changed_live_authority_is_stale_and_denied(self):
        self.assertRaises(RuntimeEnforcementError,self.admit,self.engine(changed=True))
    def test_degraded_observability_denies_write_even_if_gate_is_forged_allow(self):
        p=proposal("external_write");g=gate(p,"DEGRADED");i=identity();self.assertRaises(RuntimeEnforcementError,self.admit,None,p,g,receipt(g),None,i,effect(p,i,"DEGRADED"))
    def test_forged_gate_digest_is_denied(self):
        p=proposal();g=gate(p);bad=GateApplied(**{**g.__dict__,"decision_digest":"f"*64});self.assertRaises(RuntimeEnforcementError,self.admit,None,p,bad,receipt(g))
    def test_effect_payload_substitution_is_denied(self):
        p=proposal();i=identity();e=RequestedRuntimeEffect(**{**effect(p,i).__dict__,"payload_digest":"f"*64});self.assertRaises(RuntimeEnforcementError,self.admit,None,p,None,None,None,i,e)

if __name__=="__main__":unittest.main()
