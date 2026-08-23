import unittest
from datetime import datetime,timezone
from cyber_lion.contracts.runtime_currentness import EffectTimeCurrentnessEvidence
from cyber_lion.contracts.runtime_execution import RuntimeExecutionReceipt
from cyber_lion.contracts.runtime_reconciliation import RuntimeEffectObservation,RuntimeObserverTrustBinding
from cyber_lion.enterprise.runtime_reconciliation import RuntimeReconciler,RuntimeReconciliationError
Z="0"*64
F="f"*64
NOW=datetime(2026,8,23,14,5,tzinfo=timezone.utc)

class Observer:
    source_id="obs";source_instance_id="obs:1";implementation_digest=Z;trust_anchor_id="anchor";trust_anchor_digest=Z
    def __init__(self,o=None,fail=False):self.o=o;self.fail=fail
    def observe(self,_):
        if self.fail:raise RuntimeError("lost")
        return self.o

def trust():return RuntimeObserverTrustBinding("obs","obs:1",Z,"anchor",Z).validate()
def currentness():return EffectTimeCurrentnessEvidence("cur",Z,Z,Z,Z,Z,"policy@1:sha256:"+Z,"HEALTHY","current","current:1",Z,"anchor",Z,"2026-08-23T14:00:00+00:00").sealed()
def receipt(*,outcome="SUCCEEDED",state="OBSERVED",effect=F,events=("event",),refs=("side",)):
    return RuntimeExecutionReceipt("rr","exec",Z,Z,Z,Z,"mission","executor","runtime","sandbox","workspace",Z,F,1,"WRITE_FILE","workspace/out",Z,outcome,state,effect,events,refs).sealed()
def observation(*,state="OBSERVED",effect=F,events=("event",),refs=("side",)):
    return RuntimeEffectObservation("o","exec",Z,Z,Z,"WRITE_FILE","workspace/out",state,effect,events,refs,"obs","obs:1",Z,"anchor",Z,"2026-08-23T14:01:00+00:00").sealed()

class RuntimeReconciliationTests(unittest.TestCase):
    def reconciler(self,o=None,fail=False):return RuntimeReconciler(observer=Observer(o,fail),observer_trust=trust(),clock=lambda:NOW)
    def test_success_requires_independent_exact_match(self):
        out=self.reconciler(observation()).reconcile(receipt=receipt(),currentness=currentness());self.assertEqual(out.disposition,"MATCHED");self.assertEqual(out.anomaly_codes,())
    def test_receipt_effect_mismatch_is_not_success(self):
        out=self.reconciler(observation(effect=Z)).reconcile(receipt=receipt(),currentness=currentness());self.assertEqual(out.disposition,"MISMATCH");self.assertIn("EFFECT_DIGEST_MISMATCH",out.anomaly_codes)
    def test_success_receipt_without_observed_effect_is_mismatch(self):
        out=self.reconciler(observation(state="UNKNOWN",effect=F,refs=())).reconcile(receipt=receipt(),currentness=currentness());self.assertEqual(out.disposition,"MISMATCH");self.assertIn("SUCCESS_WITHOUT_OBSERVED_EFFECT",out.anomaly_codes)
    def test_aborted_unknown_stays_unknown(self):
        r=receipt(outcome="ABORTED",state="UNKNOWN",events=("aborted",),refs=(),effect=Z);o=observation(state="UNKNOWN",events=("aborted",),refs=(),effect=Z);out=self.reconciler(o).reconcile(receipt=r,currentness=currentness());self.assertEqual(out.disposition,"UNKNOWN");self.assertIn("UNKNOWN_EFFECT",out.anomaly_codes)
    def test_partial_unknown_never_matches_success(self):
        r=receipt(outcome="ABORTED",state="PARTIAL_UNKNOWN",events=("partial",),refs=("side",),effect=F);o=observation(state="PARTIAL_UNKNOWN",events=("partial",),refs=("side",),effect=F);out=self.reconciler(o).reconcile(receipt=r,currentness=currentness());self.assertEqual(out.disposition,"NON_SUCCESS_RECONCILED")
    def test_missing_independent_observation_fails_closed(self):
        self.assertRaises(RuntimeReconciliationError,self.reconciler(fail=True).reconcile,receipt=receipt(),currentness=currentness())
    def test_currentness_must_bind_same_admission(self):
        c=EffectTimeCurrentnessEvidence(**{**currentness().__dict__,"admission_digest":F,"evidence_digest":""}).sealed();self.assertRaises(RuntimeReconciliationError,self.reconciler(observation()).reconcile,receipt=receipt(),currentness=c)
if __name__=="__main__":unittest.main()
