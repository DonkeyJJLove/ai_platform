import dataclasses
import unittest
from cyber_lion.contracts.policy_gate import GateApplied,GateRequested,PDPDecisionReceipt,PolicyGateContractError,PolicyRevision
H="0"*64

class PolicyGateContractTests(unittest.TestCase):
    def test_policy_revision_and_gate_records_are_digest_bound(self):
        p=PolicyRevision("p","7","sha256:"+H,"GREEN").validate();self.assertIn("p@7",p.binding)
        r=GateRequested("r","proposal",p.binding,H,H,H,"HEALTHY","GREEN","read",("e",)).sealed()
        self.assertEqual(len(r.request_digest),64);r.validate()
        with self.assertRaises(PolicyGateContractError): dataclasses.replace(r,proposal_id="other").validate()
        a=GateApplied("g","r","proposal","ALLOW","read",p.binding,H,H,H,"HEALTHY","GREEN","ok").sealed()
        self.assertEqual(len(a.decision_digest),64);a.validate()
        PDPDecisionReceipt("x","r","g",r.request_digest,a.decision_digest,H).validate()
    def test_deny_cannot_carry_effective_authority(self):
        with self.assertRaises(PolicyGateContractError):
            GateApplied("g","r","p","DENY","read","p@1:x",H,H,H,"HEALTHY","GREEN","no").validate()
