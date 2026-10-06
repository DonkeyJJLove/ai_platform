"""A01 regression tests for source/session-bound effective model context."""
import json
from hashlib import sha256
from pathlib import Path
import tempfile
import unittest

from cyber_lion.app_coordination.local_intelligence_gateway import Gateway, local_model_payload_bytes
from cyber_lion.app_coordination.hybrid_gateway_extension import apply_hybrid_gateway_extension
from cyber_lion.app_coordination.saas_handoff_extension import apply_saas_handoff_extension
from cyber_lion.app_coordination.lion_context_provider import SOURCES


class GatewayContextBindingA01Tests(unittest.TestCase):
    def repo(self):
        td=tempfile.TemporaryDirectory();root=Path(td.name)
        for rel in SOURCES:
            p=root/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_text("x",encoding="utf-8")
        auth={"invariants":[
            "LPCL_GENERATION_NE_AUTHORITY",
            "USER_EXPLICIT_LAUNCH_OR_RUN_OF_EXACT_LPCL_IS_EXTERNAL_ACTIVATION_EVENT",
            "SUCCESSOR_IDENTITY_OUTSIDE_BOUND_SCOPE_REQUIRES_NEW_LPCL_AND_NEW_USER_LAUNCH",
        ]}
        (root/SOURCES[1]).write_text(json.dumps(auth),encoding="utf-8")
        (root/SOURCES[-2]).write_text(json.dumps({"architecture_epoch":"1.5"}),encoding="utf-8")
        (root/SOURCES[-1]).write_text(json.dumps({"preferred_release":"lion-rag30-v1.5-r1"}),encoding="utf-8")
        return td,root

    @staticmethod
    def git(op,args):
        return {"head":"a"*40,"tree":"b"*40} if op=="head_tree" else []

    def gateway(self,root,provider,currentness,**kwargs):
        return Gateway(root,None,None,None,"http://127.0.0.1:8772","b"*64,provider,currentness,self.git,**kwargs)

    def test_unbound_runtime_payload_contains_unknown_not_legacy_identity_literals(self):
        td,root=self.repo();self.addCleanup(td.cleanup);calls=[]
        g=self.gateway(root,lambda messages,max_tokens:(calls.append(messages) or "ok"),lambda kind,args:{})
        out=g.chat("Explain LION architecture",output_language="en")
        self.assertEqual(out["answer"],"ok");self.assertEqual(len(calls),1)
        system,user=calls[0]
        payload=system["content"]+"\n"+user["content"]
        self.assertIn("ARCHITECTURE_EPOCH_SOURCE=1.5",payload)
        self.assertIn("LOCAL_COGNITIVE_EXECUTOR=UNKNOWN_NOT_RUNTIME_ATTESTED",payload)
        self.assertIn("SAAS_BRIDGE_STATE=UNKNOWN",payload)
        self.assertIn("MATERIAL_DRONE_REQUESTED=UNKNOWN",payload)
        for stale in ("ARCHITECTURE_EPOCH=1.4","MATERIAL_EPOCH=R10","MATERIAL_DRONE_COUNT=12","gpt-oss-20b-MXFP4","SAAS_BRIDGE_STATE=EXTERNAL_SESSION_MEDIATED"):
            self.assertNotIn(stale,payload)

    def test_observed_local_model_identity_is_bound_into_state_and_payload(self):
        td,root=self.repo();self.addCleanup(td.cleanup);calls=[]
        def currentness(kind,args):
            if kind=="local_model":return {"models":[{"id":"observed-local-model"}],"health":{"gpu_name":"Observed GPU"}}
            return {}
        g=self.gateway(root,lambda messages,max_tokens:(calls.append(messages) or "ok"),currentness)
        state=g.state()
        self.assertEqual(state["local_cognitive_executor"],"observed-local-model")
        self.assertEqual(state["gpu"],"Observed GPU")
        self.assertEqual(state["local_model_identity_evidence_class"],"LOCAL_RUNTIME_OBSERVATION")
        g.chat("Explain LION architecture",output_language="en")
        payload=calls[0][0]["content"]+"\n"+calls[0][1]["content"]
        self.assertIn("observed-local-model",payload)
        self.assertIn("LOCAL_MODEL_IDENTITY_EVIDENCE=LOCAL_RUNTIME_OBSERVATION",payload)
        provenance=g.chat("Explain LION architecture",output_language="en")["provider_provenance"]
        sent_messages=calls[-1]
        expected=sha256(local_model_payload_bytes(sent_messages,520)).hexdigest()
        self.assertEqual(provenance["actual_payload_bytes_digest"],expected)
        self.assertEqual(provenance["shared_context_digest"],g.ctx.digest)
        self.assertEqual(provenance["response_digest"],sha256(b"ok").hexdigest())

    def test_bound_supervisor_projection_drives_outbound_transport(self):
        td,root=self.repo();self.addCleanup(td.cleanup);calls=[]
        class ExtendedGateway(Gateway):pass
        apply_hybrid_gateway_extension(ExtendedGateway);apply_saas_handoff_extension(ExtendedGateway)
        projection={
            "channel":"READY","session":"BOUND","model":"bound-saas-model",
            "transport":"CHATGPT_SENTINELX_SESSION_MEDIATED","automatic_hop":False,
            "authority":"NONE","pending":{},"last_receipt":{},"lease":{},"freshness":{},
            "unknown_reasons":[],
        }
        def control(op,args):
            if op=="recent":return {"focus_mission_id":None,"missions":[]}
            if op=="saas_status":return {"state":"BOUND","supervisor_projection":projection,"authority_effect":"NONE"}
            raise AssertionError(op)
        def currentness(kind,args):
            if kind=="local_model":return {"models":[{"id":"bound-local-model"}]}
            return {}
        g=ExtendedGateway(root,None,None,None,"http://127.0.0.1:8772","b"*64,lambda messages,max_tokens:(calls.append(messages) or "ok"),currentness,self.git,control_provider=control)
        g.chat("Explain LION architecture",output_language="en")
        payload=calls[0][0]["content"]+"\n"+calls[0][1]["content"]
        self.assertIn("LOCAL_COGNITIVE_EXECUTOR=bound-local-model",payload)
        self.assertIn("SAAS_BRIDGE_STATE=CHATGPT_SENTINELX_SESSION_MEDIATED",payload)
        self.assertIn("AUTOMATIC_SAAS_HOP_AVAILABLE=FALSE",payload)
        self.assertNotIn("EXTERNAL_SESSION_MEDIATED",payload)

    def test_sentinelx_completed_turn_is_fenced_to_original_claim_generation(self):
        source=(Path(__file__).resolve().parents[2]/"LION/runtime_compat/r20/node-panel/src/secure-mcp-relay.js").read_text(encoding="utf-8")
        self.assertIn("makeTurn(row, claim.claim_generation)",source)
        self.assertIn("turn.request_hash !== rec.turn_request_hash",source)
        self.assertIn("STALE_TURN_GENERATION",source)
        self.assertIn("NEW_BROKER_REQUEST_REQUIRED",source)
        self.assertNotIn("rec.claim_generation = claim.claim_generation",source)

    def test_capability_answer_keeps_unknown_identity_unknown(self):
        td,root=self.repo();self.addCleanup(td.cleanup)
        g=self.gateway(root,lambda messages,max_tokens:(_ for _ in ()).throw(AssertionError("model should not run")),lambda kind,args:{})
        out=g.chat("What local model is active?",output_language="en")
        self.assertEqual(out["route"],"LION_CAPABILITY_CURRENTNESS")
        self.assertIn("UNKNOWN_NOT_RUNTIME_ATTESTED",out["answer"])
        self.assertNotIn("gpt-oss-20b-MXFP4",out["answer"])


if __name__=="__main__":
    unittest.main()
