import unittest
from cyber_lion.contracts.runtime_reconciliation import RuntimeEffectObservation,RuntimeObserverTrustBinding,RuntimeReconciliationContractError,RuntimeReconciliationReceipt
Z="0"*64
F="f"*64

class RuntimeReconciliationContractTests(unittest.TestCase):
    def trust(self):return RuntimeObserverTrustBinding("obs","obs:1",Z,"anchor",Z).validate()
    def observation(self,state="OBSERVED"):return RuntimeEffectObservation("o","exec",Z,Z,Z,"WRITE_FILE","workspace/out",state,F,("event",),("side",) if state!="UNKNOWN" else (),"obs","obs:1",Z,"anchor",Z,"2026-08-23T14:00:00+00:00").sealed()
    def test_observation_is_tamper_evident(self):
        o=self.observation();bad=RuntimeEffectObservation(**{**o.__dict__,"effect_digest":Z});self.assertRaises(RuntimeReconciliationContractError,bad.validate)
    def test_partial_unknown_requires_side_effect_evidence(self):
        o=self.observation("PARTIAL_UNKNOWN");bad=RuntimeEffectObservation(**{**o.__dict__,"side_effect_refs":(),"observation_digest":""});self.assertRaises(RuntimeReconciliationContractError,bad.validate,check_digest=False)
    def test_matched_receipt_cannot_carry_anomalies(self):
        r=RuntimeReconciliationReceipt("r",Z,Z,Z,"exec",Z,"MATCHED",("X",),F,"2026-08-23T14:01:00+00:00");self.assertRaises(RuntimeReconciliationContractError,r.validate,check_digest=False)
if __name__=="__main__":unittest.main()
