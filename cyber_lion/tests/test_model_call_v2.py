import unittest
from dataclasses import asdict
from cyber_lion.contracts.model_call_v2 import *

Z="0"*64

def v1_record():
    return {
        "model_call_id":"mc:1",
        "schema_id":"lion.model-call/v1",
        "mission_id":"m:1",
        "phase_id":"p:1",
        "task_id":"t:1",
        "assignment_id":"a:1",
        "logical_drone_id":"drone:1",
        "material_worker_id":"worker:1",
        "requested_capability":"coordination",
        "provider":"local-gpt",
        "model_requested":"model:req",
        "model_declared":"model:decl",
        "model_attested":"model:att",
        "transport":"LOCAL",
        "selection_reason":"policy match",
        "candidate_set_digest":Z,
        "context_revision":3,
        "state":"INTENT_DURABLE",
        "input_digest":Z,
        "result_digest":None,
        "downstream_consumer":"consumer:1",
        "created_at":"2026-09-25T10:00:00Z",
        "started_at":None,
        "finished_at":None,
        "updated_at":"2026-09-25T10:00:00Z",
        "authority_effect":"NONE",
        "intent_digest":Z,
    }

class ModelCallV2Tests(unittest.TestCase):
    def test_v1_projection_preserves_complete_semantic_payload_and_adds_refs(self):
        v1=v1_record()
        v2=project_v1_to_v2(
            v1,
            invocation_ref="inv:1",
            attempt_ref="attempt:1",
            provider_ref="provider-ref:local",
            model_release_ref="release:1",
            transport_profile_ref="transport-profile:local",
            causal_group_ref="causal:1",
        )
        self.assertEqual(v2.schema_id,"lion.model-call/v2")
        self.assertEqual(v2.source_schema_id,"lion.model-call/v1")
        for field in (
            "model_call_id","mission_id","phase_id","task_id","assignment_id",
            "logical_drone_id","material_worker_id","requested_capability","provider",
            "model_requested","model_declared","model_attested","selection_reason",
            "candidate_set_digest","context_revision","state","input_digest",
            "result_digest","downstream_consumer","created_at","started_at",
            "finished_at","updated_at","intent_digest",
        ):
            self.assertEqual(getattr(v2,field),v1[field])
        self.assertEqual(v2.invocation_ref,"inv:1")
        self.assertEqual(v2.attempt_ref,"attempt:1")
        self.assertEqual(v2.model_release_ref,"release:1")

    def test_missing_legacy_field_is_not_silently_dropped(self):
        v1=v1_record()
        del v1["logical_drone_id"]
        with self.assertRaises(ModelCallV2Error):
            project_v1_to_v2(
                v1,
                invocation_ref="inv:1",
                attempt_ref="attempt:1",
                provider_ref="provider-ref:local",
                model_release_ref="release:1",
                transport_profile_ref="transport-profile:local",
                causal_group_ref="causal:1",
            )

    def test_sentinelx_transport_is_representable(self):
        v1=v1_record()
        v1["transport"]="UNREPRESENTED_LEGACY_SAAS"
        v2=project_v1_to_v2(
            v1,
            invocation_ref="inv:saas",
            attempt_ref="attempt:saas",
            provider_ref="provider-ref:saas",
            model_release_ref="release:declared",
            transport_profile_ref="sentinelx",
            causal_group_ref="causal:dual",
        )
        # Generic legacy transports do not silently become SentinelX.
        self.assertEqual(v2.transport,"OTHER_MEDIATED")
        sentinelx=ModelCallV2(
            **{**asdict(v2),
               "transport":"SENTINELX_MEDIATED_SAAS",
               "record_digest":""}
        ).sealed()
        self.assertEqual(sentinelx.transport,"SENTINELX_MEDIATED_SAAS")

    def test_model_call_result_is_not_authority(self):
        v2=project_v1_to_v2(
            v1_record(),
            invocation_ref="inv:1",
            attempt_ref="attempt:1",
            provider_ref="provider-ref:local",
            model_release_ref="release:1",
            transport_profile_ref="transport-profile:local",
            causal_group_ref="causal:1",
        )
        with self.assertRaises(ModelCallV2Error):
            ModelCallV2(**{**asdict(v2),"authority_effect":"ALLOW","record_digest":""}).sealed()

if __name__=="__main__":
    unittest.main()
