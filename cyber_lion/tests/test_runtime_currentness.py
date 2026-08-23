import unittest
from datetime import datetime,timezone
from cyber_lion.contracts.executor_sandbox import SandboxOperation
from cyber_lion.contracts.runtime_currentness import CurrentnessSourceTrustBinding
from cyber_lion.contracts.runtime_enforcement import RequestedRuntimeEffect,RuntimeAdmission,RuntimeIdentityBinding
from cyber_lion.enterprise.live_authority_admission import LiveAdmittedAuthority,LiveAuthorityAdmission
from cyber_lion.enterprise.runtime_currentness import EffectTimeCurrentnessGuardedSandbox,RuntimeCurrentnessError
Z="0"*64
F="f"*64
NOW=datetime(2026,8,23,14,0,tzinfo=timezone.utc)
POLICY="policy@1:sha256:"+Z

class FakeAdmission(LiveAuthorityAdmission):
    def __init__(self,fail=False,changed=False):self.fail=fail;self.changed=changed
    def revalidate(self,a,*,now):
        if self.fail:raise RuntimeError("revoked")
        if self.changed:return LiveAdmittedAuthority(**{**a.__dict__,"epoch_state_version":a.epoch_state_version+1})
        return a
class Source:
    source_id="current";source_instance_id="current:1";implementation_digest=Z;trust_anchor_id="anchor";trust_anchor_digest=Z
    def __init__(self,a,policy=POLICY,obs="HEALTHY"):self.a=a;self.policy=policy;self.obs=obs
    def resolve_authority(self,_):return self.a
    def current_policy_binding(self,_):return self.policy
    def current_observability_state(self,*_):return self.obs
class Inner:
    policy_digest=Z
    def __init__(self):self.calls=0
    def execute(self,op,*,payload=b""):self.calls+=1;return (op,payload)

def authority():return LiveAdmittedAuthority("repo",1,"a"*40,"b"*40,"mission","grant",Z,"prov",1,1,"read","grant",Z,(Z,),"key","ed25519",Z,"2026-08-23T13:00:00+00:00").validate()
def identity():return RuntimeIdentityBinding("drone","executor","runtime","sandbox","workspace",Z,Z).validate()
def effect(i):return RequestedRuntimeEffect("effect","proposal","mission",POLICY,Z,"read","READ_FILE","workspace/input",Z,"HEALTHY",i.digest()).validate()
def admission(a,e,i):return RuntimeAdmission("adm","request","gate","proposal",Z,Z,Z,a.digest(),Z,POLICY,"read",e.digest(),i.digest(),Z,"HEALTHY",Z).sealed()
def op():return SandboxOperation("exec","mission","drone","executor","sandbox","workspace",Z,F,1,Z,"READ_FILE","workspace/input").validate()
def trust():return CurrentnessSourceTrustBinding("current","current:1",Z,"anchor",Z).validate()

class RuntimeCurrentnessTests(unittest.TestCase):
    def fixture(self,*,fail=False,changed=False,policy=POLICY,obs="HEALTHY",source_authority=None):
        a=authority();i=identity();e=effect(i);adm=admission(a,e,i);inner=Inner();src=Source(source_authority or a,policy,obs)
        g=EffectTimeCurrentnessGuardedSandbox(inner=inner,admission=adm,effect=e,runtime_identity=i,authority_admission=FakeAdmission(fail,changed),currentness_source=src,currentness_trust=trust(),clock=lambda:NOW)
        return g,inner
    def test_current_state_allows_one_inner_effect_and_emits_evidence(self):
        g,inner=self.fixture();g.execute(op());self.assertEqual(inner.calls,1);g.last_currentness_evidence.validate()
    def test_revocation_after_admission_denied_before_effect(self):
        g,inner=self.fixture(fail=True);self.assertRaises(RuntimeCurrentnessError,g.execute,op());self.assertEqual(inner.calls,0)
    def test_authority_change_after_admission_denied(self):
        g,inner=self.fixture(changed=True);self.assertRaises(RuntimeCurrentnessError,g.execute,op());self.assertEqual(inner.calls,0)
    def test_policy_change_after_admission_denied(self):
        g,inner=self.fixture(policy="policy@2:sha256:"+F);self.assertRaises(RuntimeCurrentnessError,g.execute,op());self.assertEqual(inner.calls,0)
    def test_observability_loss_after_admission_denied(self):
        g,inner=self.fixture(obs="LOST");self.assertRaises(RuntimeCurrentnessError,g.execute,op());self.assertEqual(inner.calls,0)
    def test_authority_source_substitution_denied(self):
        other=LiveAdmittedAuthority(**{**authority().__dict__,"epoch_state_version":2});g,inner=self.fixture(source_authority=other);self.assertRaises(RuntimeCurrentnessError,g.execute,op());self.assertEqual(inner.calls,0)
if __name__=="__main__":unittest.main()
