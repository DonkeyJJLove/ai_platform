from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "LION" / "architecture" / "v1_4" / "r24_conversation_identity.schema.json"

REQUIRED_INVARIANTS = {
    "CONVERSATION_ID != MISSION_ID",
    "CONVERSATION_ID != PROVIDER_SESSION_ID",
    "CONVERSATION_ID != NATIVE_SAAS_PROJECT_THREAD_ID",
    "CONVERSATION_ID != PROTOCOL_CORRELATION_ID",
    "MODEL_CHAT != PROTOCOL_CHANNEL",
    "LOGICAL_DRONE != MATERIAL_WORKER",
    "PARTICIPANT_IDENTITY != EXECUTOR_IDENTITY",
    "MISSION_BINDING != CONVERSATION_IDENTITY",
    "MODEL_ROUTE != CONVERSATION_IDENTITY",
    "LOCAL_PROVIDER_SESSION != SAAS_PROVIDER_SESSION",
    "RESPONSE_DELIVERY_REQUIRES_EXACT_IDENTITY_MATCH",
    "AUTHORITY_EFFECT == NONE",
}

TARGET_ENTITIES = {
    "conversations",
    "conversation_lineage",
    "conversation_bindings",
    "conversation_provider_lanes",
    "conversation_threads",
    "conversation_messages",
    "conversation_delivery_events",
    "conversation_delivery_cursors",
    "conversation_external_bridges",
    "conversation_migration_provenance",
}

DELIVERY_DIMENSIONS = (
    "conversation_id",
    "binding_epoch",
    "lane_id",
    "message_id",
    "causation_id",
    "correlation_id",
    "context_digest",
    "participant_id",
)


class IdentityContractViolation(ValueError):
    pass


def _load_schema():
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def _semantic_validate(value):
    required = {
        "conversation_id", "binding_epoch", "channel", "lane_id", "message_id",
        "causation_id", "correlation_id", "context_digest", "authority_effect",
    }
    missing = required - set(value)
    if missing:
        raise IdentityContractViolation("missing:" + ",".join(sorted(missing)))
    if value["authority_effect"] != "NONE":
        raise IdentityContractViolation("authority_effect")
    conversation_id = value["conversation_id"]
    for field in (
        "mission_id",
        "provider_session_ref",
        "native_saas_project_thread_id",
        "protocol_correlation_id",
    ):
        if value.get(field) is not None and value.get(field) == conversation_id:
            raise IdentityContractViolation(f"conversation identity collapsed into {field}")
    if value.get("participant_id") is not None and value.get("participant_id") == value.get("executor_id"):
        raise IdentityContractViolation("participant identity collapsed into executor identity")
    if value.get("participant_kind") == "LOGICAL_DRONE" and not str(value.get("participant_id") or "").startswith("drone:LD"):
        raise IdentityContractViolation("material worker implicitly promoted to logical drone")
    if value.get("participant_kind") == "MATERIAL_WORKER" and not str(value.get("participant_id") or "").startswith("worker:MD"):
        raise IdentityContractViolation("logical drone implicitly promoted to material worker")
    if value.get("native_saas_project_thread_id") is not None and not value.get("external_bridge_id"):
        raise IdentityContractViolation("native SaaS thread requires explicit bridge")
    if value.get("model_route") == conversation_id:
        raise IdentityContractViolation("model route collapsed into conversation identity")
    return True


def _delivery_matches(request, response):
    return all(request.get(field) == response.get(field) for field in DELIVERY_DIMENSIONS)


def _base():
    return {
        "conversation_id": "conv-01HZX",
        "mission_id": "LION-R24-MISSION-001",
        "binding_epoch": 1,
        "channel": "MODEL_CHAT",
        "model_route": "SAAS",
        "lane_id": "lane-saas-1",
        "provider": "SAAS",
        "provider_session_ref": "provider-session-saas-01",
        "native_saas_project_thread_id": "saas-thread-project-01",
        "external_bridge_id": "bridge-01",
        "protocol_correlation_id": "protocol-correlation-01",
        "participant_id": "drone:LD001",
        "participant_kind": "LOGICAL_DRONE",
        "executor_id": "executor:material:MD001",
        "executor_kind": "MATERIAL",
        "message_id": "msg-01",
        "causation_id": "cause-01",
        "correlation_id": "corr-01",
        "context_digest": "a" * 64,
        "authority_effect": "NONE",
    }


class R24ConversationIdentityContractTests(unittest.TestCase):
    def test_schema_declares_complete_identity_invariants_and_target_entities(self):
        schema = _load_schema()
        self.assertEqual(schema["$id"], "lion://schemas/r24/conversation-identity/v1")
        self.assertTrue(REQUIRED_INVARIANTS.issubset(set(schema["x-lion-semantic-invariants"])))
        self.assertEqual(set(schema["x-lion-target-entities"]), TARGET_ENTITIES)
        self.assertEqual(tuple(schema["x-lion-delivery-match-dimensions"]), DELIVERY_DIMENSIONS)
        self.assertEqual(schema["x-lion-phase1-runtime-conformance"], "RED_NOT_IMPLEMENTED")

    def test_mission_id_cannot_be_used_as_conversation_identity(self):
        value = _base()
        value["mission_id"] = value["conversation_id"]
        with self.assertRaisesRegex(IdentityContractViolation, "mission_id"):
            _semantic_validate(value)

    def test_material_worker_cannot_become_logical_drone_implicitly(self):
        value = _base()
        value["participant_kind"] = "LOGICAL_DRONE"
        value["participant_id"] = "worker:MD001"
        with self.assertRaisesRegex(IdentityContractViolation, "material worker"):
            _semantic_validate(value)

    def test_provider_session_cannot_be_used_as_conversation_identity(self):
        value = _base()
        value["provider_session_ref"] = value["conversation_id"]
        with self.assertRaisesRegex(IdentityContractViolation, "provider_session_ref"):
            _semantic_validate(value)

    def test_native_saas_project_thread_requires_bridge_and_cannot_be_conversation_identity(self):
        value = _base()
        value["external_bridge_id"] = None
        with self.assertRaisesRegex(IdentityContractViolation, "explicit bridge"):
            _semantic_validate(value)
        value = _base()
        value["native_saas_project_thread_id"] = value["conversation_id"]
        with self.assertRaisesRegex(IdentityContractViolation, "native_saas_project_thread_id"):
            _semantic_validate(value)

    def test_protocol_correlation_cannot_become_model_chat_identity(self):
        value = _base()
        value["protocol_correlation_id"] = value["conversation_id"]
        with self.assertRaisesRegex(IdentityContractViolation, "protocol_correlation_id"):
            _semantic_validate(value)

    def test_cross_conversation_response_delivery_is_denied(self):
        request = _base()
        response = copy.deepcopy(request)
        self.assertTrue(_delivery_matches(request, response))
        response["conversation_id"] = "conv-other"
        self.assertFalse(_delivery_matches(request, response))
        response = copy.deepcopy(request)
        response["binding_epoch"] += 1
        self.assertFalse(_delivery_matches(request, response))
        response = copy.deepcopy(request)
        response["participant_id"] = "drone:LD002"
        self.assertFalse(_delivery_matches(request, response))

    def test_dual_provider_sessions_must_be_distinct(self):
        local = _base()
        local.update({
            "model_route": "DUAL",
            "lane_id": "lane-local-1",
            "provider": "LOCAL",
            "provider_session_ref": "provider-session-local-01",
            "native_saas_project_thread_id": None,
            "external_bridge_id": None,
        })
        saas = _base()
        saas.update({
            "model_route": "DUAL",
            "lane_id": "lane-saas-1",
            "provider": "SAAS",
            "provider_session_ref": "provider-session-saas-01",
        })
        self.assertTrue(_semantic_validate(local))
        self.assertTrue(_semantic_validate(saas))
        self.assertNotEqual(local["provider_session_ref"], saas["provider_session_ref"])
        self.assertEqual(local["context_digest"], saas["context_digest"])

    def test_bind_and_detach_are_successor_operations(self):
        schema = _load_schema()
        semantics = schema["x-lion-successor-semantics"]
        self.assertEqual(semantics["BIND"], "FREEZE_PREDECESSOR_AND_CREATE_BOUND_SUCCESSOR")
        self.assertEqual(semantics["DETACH"], "FREEZE_PREDECESSOR_AND_CREATE_UNBOUND_SUCCESSOR")
        self.assertEqual(semantics["HISTORY_REWRITE"], "FORBIDDEN")


if __name__ == "__main__":
    unittest.main()
