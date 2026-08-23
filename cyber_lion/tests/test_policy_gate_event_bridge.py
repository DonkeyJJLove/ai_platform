import unittest
from cyber_lion.contracts.policy_gate import GateApplied,GateRequested
from cyber_lion.enterprise.policy_gate_event_bridge import gate_applied_event,gate_requested_event
H="0"*64

class PolicyGateEventBridgeTests(unittest.TestCase):
    def test_gate_requested_and_applied_form_explicit_causal_chain(self):
        r=GateRequested("r","p","policy@1:sha256:"+H,H,H,H,"HEALTHY","GREEN","read",("evidence",)).sealed()
        re=gate_requested_event(r,occurred_at="2026-08-23T10:00:00+00:00",correlation_id="c")
        self.assertEqual(re.event_type,"GateRequested");self.assertEqual(re.authority.effective,"none")
        a=GateApplied("gate:r","r","p","ALLOW","read",r.policy_binding,H,H,H,"HEALTHY","GREEN","ok").sealed()
        ae=gate_applied_event(a,request_event_id=re.event_id,occurred_at="2026-08-23T10:00:01+00:00",correlation_id="c")
        self.assertEqual(ae.event_type,"GateApplied");self.assertEqual(ae.causation_id,re.event_id);self.assertEqual(ae.authority.gate_event_id,a.gate_event_id)
    def test_denied_gate_never_exposes_gate_authority_reference(self):
        a=GateApplied("gate:r","r","p","DENY","none","policy@1:sha256:"+H,H,H,H,"LOST","RED","lost observability").sealed()
        e=gate_applied_event(a,request_event_id="event:r",occurred_at="2026-08-23T10:00:01+00:00",correlation_id="c")
        self.assertEqual(e.authority.effective,"none");self.assertIsNone(e.authority.gate_event_id)
