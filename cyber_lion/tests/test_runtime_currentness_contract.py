import unittest
from cyber_lion.contracts.runtime_currentness import CurrentnessSourceTrustBinding,EffectTimeCurrentnessEvidence,RuntimeCurrentnessContractError
Z="0"*64
F="f"*64

class RuntimeCurrentnessContractTests(unittest.TestCase):
    def trust(self):return CurrentnessSourceTrustBinding("src","src:1",Z,"anchor",Z).validate()
    def evidence(self):return EffectTimeCurrentnessEvidence("ev",Z,Z,Z,Z,Z,"policy@1:sha256:"+Z,"HEALTHY","src","src:1",Z,"anchor",Z,"2026-08-23T14:00:00+00:00").sealed()
    def test_trust_binding_exact(self):self.assertEqual(self.trust().binding(),("src","src:1",Z,"anchor",Z))
    def test_evidence_tamper_is_denied(self):
        e=self.evidence();bad=EffectTimeCurrentnessEvidence(**{**e.__dict__,"policy_binding":"policy@2:sha256:"+F});self.assertRaises(RuntimeCurrentnessContractError,bad.validate)
    def test_unknown_observability_is_denied(self):
        e=self.evidence();bad=EffectTimeCurrentnessEvidence(**{**e.__dict__,"observability_state":"UNKNOWN","evidence_digest":""});self.assertRaises(RuntimeCurrentnessContractError,bad.validate,check_digest=False)
if __name__=="__main__":unittest.main()
