import unittest
from dataclasses import asdict
from datetime import datetime,timezone
from cyber_lion.contracts.executor_provisioning import ExecutorProvisioningRequest,ProviderTrustBinding,ProvisionedExecutor
from cyber_lion.contracts.policy_gate import GateApplied,PDPDecisionReceipt
from cyber_lion.contracts.runtime_enforcement import CanonicalPDPDecisionEvidence,PDPSourceTrustBinding,RequestedRuntimeEffect,RuntimeIdentityBinding
from cyber_lion.enterprise.control_plane import ActionProposal
from cyber_lion.enterprise.live_authority_admission import LiveAdmittedAuthority,LiveAuthorityAdmission
from cyber_lion.enterprise.runtime_enforcement import InMemoryRuntimeAdmissionReplayGuard,RuntimeAdmissionEngine,RuntimeEnforcementError,_pdp_receipt_digest
Z="0"*64
F="f"*64
NOW=datetime(2026,8,23,13,0,tzinfo=timezone.utc)
POLICY="policy@1:sha256:"+Z

class FakeAdmission(LiveAuthorityAdmission):
    def __init__(self,fail=False,changed=False):self.fail=fail;self.changed=changed
    def revalidate(self,admitted,*,now):
        if self.fail:raise RuntimeError("revoked")
        if self.changed:return LiveAdmittedAuthority(**{**admitted.__dict__,"epoch_state_version":admitted.epoch_state_version+1})
        return admitted

class FakePDPSource:
    source_id="pdp";source_instance_id="pdp:1";implementation_digest=Z;trust_anchor_id="anchor";trust_anchor_digest=Z
    def __init__(self,g,r,*,stale=False,stale_policy=False):
        expires="2026-08-23T12:30:00+00:00" if stale else "2026-08-23T14:00:00+00:00"
        self.e=CanonicalPDPDecisionEvidence(g.request_id,g.gate_event_id,g.proposal_id,g.decision_digest,_pdp_receipt_digest(r),r.request_digest,r.replay_key,g.policy_binding,g.authority_lineage_digest,g.observability_state,self.source_id,self.source_instance_id,self.implementation_digest,self.trust_anchor_id,self.trust_anchor_digest,"2026-08-23T12:00:00+00:00",expires).sealed()
        self.stale_policy=stale_policy
    def resolve(self,request_id,gate_event_id):return self.e
    def current_policy_binding(self,policy_binding):return "policy@2:sha256:"+F if self.stale_policy else policy_binding

def source_trust():return PDPSourceTrustBinding("pdp","pdp:1",Z,"anchor",Z).validate()

def authority():
    return LiveAdmittedAuthority(repository="DonkeyJJLove/ai_platform",pr_number=1,base_sha="a"*40,head_sha="b"*40,mission_id="mission:1",grant_id="grant:1",lineage_digest=Z,provenance_id="prov",epoch=1,epoch_state_version=1,authority_ceiling="external_write",root_grant_id="grant:1",root_grant_digest=Z,authenticated_grant_digests=(Z,),leaf_key_id="key",leaf_algorithm="ed25519",replay_digest=Z,admitted_at="2026-08-23T12:00:00+00:00").validate()

def proposal(authority_class="read",target="workspace/input.txt"):
    return ActionProposal("proposal:1","mission:1","swarm:1","agent:1","cap",authority_class,"READ_FILE" if authority_class=="read" else "WRITE_FILE",target,True,("ev",),("trace",),payload_digest=Z).validate()

def gate(p,obs="HEALTHY",rationale="canonical"):
    return GateApplied("gate:1","request:1",p.proposal_id,"ALLOW",p.requested_authority,POLICY,Z,Z,Z,obs,"GREEN",rationale).sealed()

def receipt(g,receipt_id="receipt:1",replay=Z):return PDPDecisionReceipt(receipt_id,g.request_id,g.gate_event_id,Z,g.decision_digest,replay).validate()

def provisioning():
    trust=ProviderTrustBinding("provider","provider:1",Z,"provider-anchor",Z).validate()
    req=ExecutorProvisioningRequest("1.0.0","prov-req","idem","drone:1","executor:1","mission:1","LION-F009-RUNTIME-ENFORCEMENT-PROOF","DonkeyJJLove/ai_platform","a"*40,"b"*40,"mission/f009-runtime-admission",("cyber_lion",),("cyber_lion/contracts/runtime_enforcement.py",),"python",Z,Z,Z,(),"2026-08-23T12:00:00+00:00").validate()
    pe=ProvisionedExecutor("1.0.0","prov-receipt",req.request_id,req.digest(),req.idempotency_key,req.drone_id,req.executor_id,"runtime:1","sandbox:1","workspace:1",req.mission_id,req.parent_mission_id,req.repository,req.baseline_sha,req.baseline_tree_sha,req.branch,req.read_scope,req.write_scope,req.runtime_class,req.image_digest,req.sandbox_profile_digest,req.resource_profile_digest,(),trust.provider_id,trust.provider_instance_id,trust.implementation_digest,trust.trust_anchor_id,trust.trust_anchor_digest,Z,"provider:ev","2026-08-23T12:01:00+00:00").validate_for(req,trust)
    return req,trust,pe

def identity(pe=None,**changes):
    if pe is None:pe=provisioning()[2]
    values=dict(workload_identity=pe.drone_id,execution_subject=pe.executor_id,runtime_instance_id=pe.runtime_instance_id,sandbox_id=pe.sandbox_id,workspace_id=pe.workspace_id,runtime_attestation_digest=pe.runtime_attestation_digest,provisioned_executor_digest=pe.digest())
    values.update(changes);return RuntimeIdentityBinding(**values).validate()

def effect(p,i,obs="HEALTHY",resource=None,payload=Z):return RequestedRuntimeEffect("effect:1",p.proposal_id,p.mission_id,POLICY,Z,p.requested_authority,p.action_class,resource or p.target,payload,obs,i.digest()).validate()

class RuntimeAdmissionTests(unittest.TestCase):
    def engine(self,g,r,*,authority_fail=False,authority_changed=False,stale=False,stale_policy=False):
        return RuntimeAdmissionEngine(authority_admission=FakeAdmission(authority_fail,authority_changed),pdp_source=FakePDPSource(g,r,stale=stale,stale_policy=stale_policy),pdp_source_trust=source_trust(),replay_guard=InMemoryRuntimeAdmissionReplayGuard())
    def admit(self,engine=None,p=None,g=None,r=None,a=None,i=None,e=None,prov=None):
        p=p or proposal();g=g or gate(p);r=r or receipt(g);a=a or authority();req,trust,pe=prov or provisioning();i=i or identity(pe);e=e or effect(p,i,g.observability_state);eng=engine or self.engine(g,r)
        return eng.admit(gate=g,pdp_receipt=r,admitted_authority=a,proposal=p,effect=e,runtime_identity=i,provisioned_executor=pe,provisioning_request=req,provider_trust=trust,trusted_now=NOW)
    def test_exact_chain_produces_sealed_admission(self):
        out=self.admit();out.validate();self.assertEqual(out.policy_binding,POLICY);self.assertEqual(len(out.admission_digest),64)
    def test_replayed_admission_is_denied(self):
        p=proposal();g=gate(p);r=receipt(g);eng=self.engine(g,r);self.admit(eng,p,g,r);self.assertRaises(RuntimeEnforcementError,self.admit,eng,p,g,r)
    def test_self_consistent_forged_gate_allow_is_denied(self):
        p=proposal();canonical=gate(p);cr=receipt(canonical);eng=self.engine(canonical,cr);forged=gate(p,rationale="forged");fr=receipt(forged);self.assertRaises(RuntimeEnforcementError,self.admit,eng,p,forged,fr)
    def test_self_consistent_forged_pdp_receipt_is_denied(self):
        p=proposal();g=gate(p);r=receipt(g);eng=self.engine(g,r);forged=receipt(g,"receipt:forged",F);self.assertRaises(RuntimeEnforcementError,self.admit,eng,p,g,forged)
    def test_stale_canonical_gate_is_denied(self):
        p=proposal();g=gate(p);r=receipt(g);self.assertRaises(RuntimeEnforcementError,self.admit,self.engine(g,r,stale=True),p,g,r)
    def test_stale_policy_binding_is_denied(self):
        p=proposal();g=gate(p);r=receipt(g);self.assertRaises(RuntimeEnforcementError,self.admit,self.engine(g,r,stale_policy=True),p,g,r)
    def test_revoked_authority_is_denied(self):
        p=proposal();g=gate(p);r=receipt(g);self.assertRaises(RuntimeEnforcementError,self.admit,self.engine(g,r,authority_fail=True),p,g,r)
    def test_changed_live_authority_is_denied(self):
        p=proposal();g=gate(p);r=receipt(g);self.assertRaises(RuntimeEnforcementError,self.admit,self.engine(g,r,authority_changed=True),p,g,r)
    def _assert_identity_substitution_denied(self,**changes):
        p=proposal();g=gate(p);r=receipt(g);prov=provisioning();bad=identity(prov[2],**changes);e=effect(p,bad);self.assertRaises(RuntimeEnforcementError,self.admit,self.engine(g,r),p,g,r,None,bad,e,prov)
    def test_wrong_workload_identity(self):self._assert_identity_substitution_denied(workload_identity="drone:other")
    def test_wrong_execution_subject(self):self._assert_identity_substitution_denied(execution_subject="executor:other")
    def test_wrong_runtime_instance(self):self._assert_identity_substitution_denied(runtime_instance_id="runtime:other")
    def test_wrong_sandbox(self):self._assert_identity_substitution_denied(sandbox_id="sandbox:other")
    def test_wrong_workspace(self):self._assert_identity_substitution_denied(workspace_id="workspace:other")
    def test_wrong_runtime_attestation(self):self._assert_identity_substitution_denied(runtime_attestation_digest=F)
    def test_wrong_resource(self):
        p=proposal();g=gate(p);r=receipt(g);prov=provisioning();i=identity(prov[2]);self.assertRaises(RuntimeEnforcementError,self.admit,self.engine(g,r),p,g,r,None,i,effect(p,i,resource="workspace/other.txt"),prov)
    def test_payload_substitution(self):
        p=proposal();g=gate(p);r=receipt(g);prov=provisioning();i=identity(prov[2]);self.assertRaises(RuntimeEnforcementError,self.admit,self.engine(g,r),p,g,r,None,i,effect(p,i,payload=F),prov)
    def test_degraded_write_denied_even_with_canonical_allow(self):
        p=proposal("external_write");g=gate(p,"DEGRADED");r=receipt(g);prov=provisioning();i=identity(prov[2]);self.assertRaises(RuntimeEnforcementError,self.admit,self.engine(g,r),p,g,r,None,i,effect(p,i,"DEGRADED"),prov)
    def test_lost_observability_denies_any_effect(self):
        p=proposal("read");g=gate(p,"LOST");r=receipt(g);prov=provisioning();i=identity(prov[2]);self.assertRaises(RuntimeEnforcementError,self.admit,self.engine(g,r),p,g,r,None,i,effect(p,i,"LOST"),prov)

if __name__=="__main__":unittest.main()
