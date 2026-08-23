import unittest
from cyber_lion.contracts.runtime_enforcement import RequestedRuntimeEffect,RuntimeAdmission,RuntimeEnforcementContractError,RuntimeIdentityBinding
Z="0"*64

class RuntimeEnforcementContractTests(unittest.TestCase):
    def identity(self):
        return RuntimeIdentityBinding("workload:a","subject:a","runtime:1","sandbox:1","workspace:1",Z).validate()
    def effect(self):
        i=self.identity()
        return RequestedRuntimeEffect("effect:1","proposal:1","mission:1","policy@1:sha256:"+Z,Z,"read","READ_FILE","workspace/input.txt",Z,"HEALTHY",i.digest()).validate()
    def test_identity_digest_is_deterministic(self):
        i=self.identity();self.assertEqual(i.digest(),i.digest())
    def test_effect_binds_runtime_identity(self):
        e=self.effect();self.assertEqual(len(e.digest()),64)
        bad=RequestedRuntimeEffect(**{**e.__dict__,"runtime_identity_digest":"f"*64})
        self.assertNotEqual(e.digest(),bad.digest())
    def test_admission_is_tamper_evident(self):
        e=self.effect();i=self.identity();a=RuntimeAdmission("admission","request","gate","proposal:1",Z,Z,Z,Z,"policy@1:sha256:"+Z,"read",e.digest(),i.digest(),"HEALTHY",Z).sealed();a.validate()
        bad=RuntimeAdmission(**{**a.__dict__,"effective_authority":"external_write"})
        self.assertRaises(RuntimeEnforcementContractError,bad.validate)
    def test_unknown_observability_is_rejected(self):
        e=self.effect();bad=RequestedRuntimeEffect(**{**e.__dict__,"observability_state":"UNKNOWN"})
        self.assertRaises(RuntimeEnforcementContractError,bad.validate)

if __name__=="__main__":unittest.main()
