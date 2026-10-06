from __future__ import annotations
import hashlib
import unittest

from cyber_lion.app_coordination.cognitive_continuity import (
    CognitiveContinuityError,
    active_saas_bridge,
    build_mission_cognitive_continuity,
    build_synchronization_checkpoint,
    provider_requirements,
    validate_activation_readiness,
)


class CognitiveContinuityTests(unittest.TestCase):
    def contracts(self, *classes):
        return [{"phase_id": f"P{i}", "capability_classes": [value]} for i, value in enumerate(classes, 1)]

    def conversation(self):
        return {
            "conversation_id": "conv-1",
            "state": "BOUND",
            "current_binding": {"binding_epoch": 2, "mission_id": "M1", "state": "BOUND"},
            "lineage": {"predecessor_conversation_id": "conv-0", "transition": "BIND"},
            "lanes": [
                {"binding_epoch": 2, "lane_id": "lane-local", "provider": "LOCAL", "provider_session_ref": None, "state": "READY"},
                {"binding_epoch": 2, "lane_id": "lane-saas", "provider": "SAAS", "provider_session_ref": "binding-saas-1", "state": "ACTIVE"},
            ],
            "external_bridges": [
                {
                    "bridge_id": "bridge-old", "external_system": "CHATGPT_PROJECT",
                    "external_thread_ref": "native-old", "created_at": 1,
                    "provenance_json": "{}",
                },
                {
                    "bridge_id": "bridge-new", "external_system": "CHATGPT_PROJECT",
                    "external_thread_ref": "native-new", "created_at": 2,
                    "provenance_json": '{"supplied":{"supersedes_bridge_id":"bridge-old"}}',
                },
            ],
        }

    def messages(self):
        return [
            {
                "message_id": "msg-local", "lane_id": "lane-local", "role": "ASSISTANT",
                "content": "local", "created_at": 1, "metadata": {
                    "canonical_context": True,
                    "provider_session_ref_class": "UNKNOWN_NOT_PROVIDER_ATTESTED",
                    "response_meta": {},
                },
            },
            {
                "message_id": "msg-saas", "lane_id": "lane-saas", "role": "ASSISTANT",
                "content": "saas", "created_at": 2, "metadata": {
                    "canonical_context": True,
                    "provider_session_ref": "binding-saas-1",
                    "provider_session_ref_class": "SAAS_BROKER_SESSION_BINDING",
                    "response_meta": {
                        "projection_digest": "a" * 64,
                        "actual_payload_bytes_digest": "b" * 64,
                        "response_digest": "c" * 64,
                    },
                },
            },
        ]

    def capabilities(self):
        return {
            "LOCAL": {"currentness": "CURRENT", "text_input": "SUPPORTED"},
            "SAAS": {"currentness": "CURRENT", "text_input": "SUPPORTED"},
        }

    def test_provider_requirements_use_capability_classes_not_mission_enum(self):
        self.assertEqual(provider_requirements(self.contracts("LOCAL_MODEL_INFERENCE")), ("LOCAL",))
        self.assertEqual(provider_requirements(self.contracts("DUAL_MODEL_INFERENCE")), ("LOCAL", "SAAS"))
        self.assertEqual(provider_requirements(self.contracts("UNRELATED_CAPABILITY")), ())

    def test_successor_checkpoint_is_bounded_and_does_not_inherit_bridge_or_session(self):
        messages = [
            {
                "message_id": f"m{i}", "role": "USER", "content": f"body-{i}",
                "created_at": i, "lane_id": "lane-local", "correlation_id": f"c{i}",
                "causation_id": f"k{i}", "context_digest": "d" * 64,
            }
            for i in range(40)
        ]
        cp = build_synchronization_checkpoint(
            mission_id="M1", lpcl_digest="1" * 64, source_head="2" * 40,
            source_tree="3" * 40, conversation=self.conversation(), messages=messages,
            consumer_role="SAAS_COORDINATOR", shared_context_digest="4" * 64,
            artifact_refs=("artifact:a",), open_dependencies=("dep:a",),
            last_reconciled_event="event:9",
        )
        self.assertEqual(cp.predecessor_conversation_id, "conv-0")
        self.assertEqual(len(cp.history_message_ids), 32)
        payload = cp.to_dict()
        self.assertNotIn("provider_session_ref", payload)
        self.assertNotIn("external_thread_ref", payload)

    def test_active_bridge_honors_supersession(self):
        self.assertEqual(active_saas_bridge(self.conversation()["external_bridges"])["bridge_id"], "bridge-new")

    def test_dual_readiness_requires_separate_provider_evidence(self):
        projection = build_mission_cognitive_continuity(
            mission_id="M1", lpcl_digest="1" * 64, source_head="2" * 40, source_tree="3" * 40,
            phase_contracts=self.contracts("DUAL_MODEL_INFERENCE"),
            conversation=self.conversation(), messages=self.messages(),
            provider_capabilities=self.capabilities(), expected_conversation_id="conv-1",
            expected_binding_epoch=2, shared_context_digest="4" * 64,
            synchronization_checkpoint_digest="5" * 64, observed_at="2026-10-06T12:00:00Z",
        )
        self.assertEqual(projection["state"], "READY")
        self.assertEqual(projection["required_providers"], ["LOCAL", "SAAS"])
        self.assertIsNone(projection["provider_paths"]["LOCAL"]["provider_session_refs"][0] if projection["provider_paths"]["LOCAL"]["provider_session_refs"] else None)
        self.assertEqual(projection["provider_paths"]["SAAS"]["external_thread_ref"], "native-new")
        validate_activation_readiness(
            projection, mission_id="M1", lpcl_digest="1" * 64,
            required_providers=("LOCAL", "SAAS"), conversation_id="conv-1", binding_epoch=2,
        )

    def test_saas_actual_payload_digest_missing_blocks(self):
        messages = self.messages()
        messages[1]["metadata"]["response_meta"].pop("actual_payload_bytes_digest")
        projection = build_mission_cognitive_continuity(
            mission_id="M1", lpcl_digest="1" * 64, source_head="2" * 40, source_tree="3" * 40,
            phase_contracts=self.contracts("SAAS_DELEGATION"),
            conversation=self.conversation(), messages=messages,
            provider_capabilities=self.capabilities(), expected_conversation_id="conv-1",
            expected_binding_epoch=2, shared_context_digest="4" * 64,
            synchronization_checkpoint_digest="5" * 64,
        )
        self.assertEqual(projection["state"], "WAITING")
        self.assertIn("SAAS_ACTUAL_PAYLOAD_DIGEST_REQUIRED", projection["blockers"])
        with self.assertRaises(CognitiveContinuityError):
            validate_activation_readiness(
                projection, mission_id="M1", lpcl_digest="1" * 64,
                required_providers=("SAAS",), conversation_id="conv-1", binding_epoch=2,
            )

    def test_wrong_epoch_fails_readiness(self):
        projection = build_mission_cognitive_continuity(
            mission_id="M1", lpcl_digest="1" * 64, source_head="2" * 40, source_tree="3" * 40,
            phase_contracts=self.contracts("LOCAL_MODEL_INFERENCE"),
            conversation=self.conversation(), messages=self.messages(),
            provider_capabilities=self.capabilities(), expected_conversation_id="conv-1",
            expected_binding_epoch=3, shared_context_digest="4" * 64,
            synchronization_checkpoint_digest="5" * 64,
        )
        self.assertIn("BINDING_EPOCH_MISMATCH", projection["blockers"])


if __name__ == "__main__":
    unittest.main()
