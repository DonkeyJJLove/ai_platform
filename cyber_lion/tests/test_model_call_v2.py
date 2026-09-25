import unittest
from cyber_lion.contracts.model_call_v2 import *
Z="0"*64
class ModelCallV2Tests(unittest.TestCase):
    def test_v1_projection_preserves_identity_and_adds_refs(self):
        v1={"model_call_id":"mc:1","mission_id":"m:1","phase_id":"p:1","task_id":"t:1","assignment_id":"a:1","requested_capability":"coordination","transport":"LOCAL","input_digest":Z,"result_digest":None,"state":"INTENT_DURABLE"}
        v2=project_v1_to_v2(v1,invocation_ref="inv:1",attempt_ref="attempt:1",provider_ref="provider:local",model_release_ref="release:1",transport_profile_ref="transport:local",causal_group_ref="causal:1")
        self.assertEqual(v2.schema_id,"lion.model-call/v2"); self.assertEqual(v2.model_call_id,"mc:1"); self.assertEqual(v2.invocation_ref,"inv:1")
    def test_sentinelx_transport_is_representable(self):
        r=ModelCallV2("mc:2","m:1","p:1","t:1","a:1","inv:s","attempt:s","provider:saas","release:declared","transport:sentinelx","causal:1","coordination","SENTINELX_MEDIATED_SAAS",None,None,"SEND_ATTEMPT").sealed()
        self.assertEqual(r.transport,"SENTINELX_MEDIATED_SAAS")
    def test_model_call_result_is_not_authority(self):
        with self.assertRaises(ModelCallV2Error):
            ModelCallV2("mc:3","m:1","p:1","t:1","a:1","inv:1","attempt:1","provider:1","release:1","transport:1","causal:1","coordination","LOCAL",None,Z,"RESPONSE_RECONCILED",authority_effect="ALLOW").sealed()
if __name__=="__main__":unittest.main()
