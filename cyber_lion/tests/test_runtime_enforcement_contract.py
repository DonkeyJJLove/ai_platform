import unittest
from cyber_lion.contracts.runtime_enforcement import CanonicalPDPDecisionEvidence,PDPSourceTrustBinding,RequestedRuntimeEffect,RuntimeAdmission,RuntimeEnforcementContractError,RuntimeIdentityBinding
Z="0"*64
F="f"*64

class RuntimeEnforcementContractTests(unittest.TestCase):
    def trust(self):return PDPSourceTrustBinding("pdp","pdp:1",Z,"anchor",Z).validate()
    def evidence(self):
        return CanonicalPDPDecisionEvidence("request","gate","proposal",Z,Z,Z,Z,"policy@1:sha256:"+Z,Z,"HEALTHY","pdp","pdp:1",Z,"anchor",Z,"2026-08-23T12:00:00+00:00","2026-08-23T14:00:00+00:00").sealed()
    def identity(self):return RuntimeIdentityBinding("drone:1","executor:1","runtime:1","sandbox:1","workspace:1",Z,Z).validate()
    def effect(self):
        i=self.identity();return RequestedRuntimeEffect("effect:1","proposal","mission","policy@1:sha256:"+Z,Z,"read","READ_FILE","workspace/input.txt",Z,"HEALTHY",i.digest()).validate()
    def test_trust_binding_is_exact(self):self.assertEqual(self.trust().binding(),("pdp","pdp:1",Z,"anchor",Z))
    def test_pdp_evidence_is_tamper_evident(self):
        e=self.evidence();e.validate();bad=CanonicalPDPDecisionEvidence(**{**e.__dict__,"replay_key":F});self.assertRaises(RuntimeEnforcementContractError,bad.validate)
    def test_pdp_evidence_requires_forward_expiry(self):
        e=self.evidence();bad=CanonicalPDPDecisionEvidence(**{**e.__dict__,"expires_at":e.issued_at,"evidence_digest":""});self.assertRaises(RuntimeEnforcementContractError,bad.validate,check_digest=False)
    def test_identity_digest_binds_provisioned_executor(self):
        i=self.identity();bad=RuntimeIdentityBinding(**{**i.__dict__,"provisioned_executor_digest":F});self.assertNotEqual(i.digest(),bad.digest())
    def test_effect_binds_runtime_identity(self):
        e=self.effect();bad=RequestedRuntimeEffect(**{**e.__dict__,"runtime_identity_digest":F});self.assertNotEqual(e.digest(),bad.digest())
    def test_admission_is_tamper_evident(self):
        e=self.effect();i=self.identity();a=RuntimeAdmission("admission","request","gate","proposal",Z,Z,Z,Z,Z,"policy@1:sha256:"+Z,"read",e.digest(),i.digest(),Z,"HEALTHY",Z).sealed();a.validate()
        bad=RuntimeAdmission(**{**a.__dict__,"effective_authority":"external_write"});self.assertRaises(RuntimeEnforcementContractError,bad.validate)
    def test_unknown_observability_is_rejected(self):
        e=self.effect();bad=RequestedRuntimeEffect(**{**e.__dict__,"observability_state":"UNKNOWN"});self.assertRaises(RuntimeEnforcementContractError,bad.validate)

if __name__=="__main__":unittest.main()
