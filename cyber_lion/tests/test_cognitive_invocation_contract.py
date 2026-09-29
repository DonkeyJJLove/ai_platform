import unittest
from dataclasses import replace
from cyber_lion.contracts.cognitive_invocation import *
Z="0"*64
class CognitiveInvocationTests(unittest.TestCase):
    def test_provider_endpoint_session_invocation_are_distinct(self):
        p=CognitiveProvider("provider:saas","SAAS","profile:saas").validate()
        e=CognitiveEndpoint("endpoint:saas","provider:saas","SAAS","transport:sentinelx","PROVIDER_DECLARED",None).validate()
        b=CognitiveSessionBinding("binding:1","THREAD",None,"thread:1","endpoint:saas","session:1",1,"release:declared",Z,"2026-09-25T00:00:00Z","2026-09-26T00:00:00Z").sealed()
        i=InvocationIntent("inv:1","parent:1","msg:1",Z,"binding:1",b.binding_digest,"SAAS","route:1","COORDINATION","2026-09-25T01:00:00Z","causal:1").validate()
        self.assertEqual(len({p.provider_id,e.endpoint_id,b.binding_id,i.invocation_id}),4)
    def test_transport_current_does_not_mean_reconciled(self):
        c=InvocationCurrentness("inv:1","CURRENT","CURRENT","UNKNOWN","UNKNOWN","2026-09-25T00:00:00Z",("obs:1",)).validate()
        r=InvocationReconciliation("inv:1","attempt:1",Z,None,None,"UNKNOWN",("obs:1",)).validate()
        self.assertEqual(c.transport_state,"CURRENT"); self.assertEqual(r.state,"UNKNOWN")
    def test_dual_legs_keep_separate_identity(self):
        a=InvocationIntent("inv:local","parent:1","msg:1",Z,"binding:l",Z,"LOCAL","route:1","PLANNING","2026-09-25T01:00:00Z","causal:dual").validate()
        b=InvocationIntent("inv:saas","parent:1","msg:1",Z,"binding:s",Z,"SAAS","route:1","PLANNING","2026-09-25T01:00:00Z","causal:dual").validate()
        self.assertNotEqual(a.invocation_id,b.invocation_id); self.assertEqual(a.causal_group_ref,b.causal_group_ref)
    def test_reconciled_requires_reported_and_delivery_evidence(self):
        with self.assertRaises(CognitiveInvocationError):
            InvocationReconciliation("inv:1","attempt:1",Z,None,None,"RECONCILED",("obs:1",)).validate()
    def test_cognitive_invocation_never_mints_authority(self):
        with self.assertRaises(CognitiveInvocationError):
            CognitiveProvider("provider:x","LOCAL","profile",authority_effect="WRITE").validate()
if __name__=="__main__":unittest.main()
