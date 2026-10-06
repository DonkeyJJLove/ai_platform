from __future__ import annotations

import hashlib
import importlib
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cyber_lion.app_coordination.cognitive_continuity import (
    build_mission_cognitive_continuity,
    build_synchronization_checkpoint,
)


class CognitiveActivationGateTests(unittest.TestCase):
    def setUp(self):
        tools = Path(__file__).resolve().parents[2] / "tools"
        if str(tools) not in sys.path:
            sys.path.insert(0, str(tools))
        compat = importlib.import_module("lion_mission_control_compat")
        sys.modules["mission_control_compat"] = compat
        self.mc = importlib.import_module("lion_mission_control_v3")
        self.td = tempfile.TemporaryDirectory()
        self.addCleanup(self.td.cleanup)
        self.old_db, self.old_legacy = self.mc.DB, self.mc.LEGACY_DB
        self.addCleanup(lambda: setattr(self.mc, "DB", self.old_db))
        self.addCleanup(lambda: setattr(self.mc, "LEGACY_DB", self.old_legacy))
        self.mc.DB = Path(self.td.name) / "mc.db"
        self.mc.LEGACY_DB = Path(self.td.name) / "none.db"
        self.mc.migrate()

    @staticmethod
    def cognitive_lpcl():
        return "\n".join([
            "CONTROL_LANGUAGE=LPCL/1.2",
            "PHASE_01_EXECUTION_CLASS=COGNITIVE",
            "PHASE_01_CAPABILITY_CLASS=SAAS_DELEGATION",
            "PHASE_01_EFFECT_CEILING=NONE",
            "PHASE_01_BINDING_MODE=DYNAMIC",
            "PHASE_01_ON_MISSING_CAPABILITY=WAIT_AND_DISCOVER",
            "PHASE_01_AUTO_RESUME=FALSE",
            "PHASE_01_VERIFY_BEFORE_MUTATE=TRUE",
            "PHASE_01_CURRENTNESS=COGNITIVE_PROVIDER_CURRENT",
            "PHASE_01_EVIDENCE=COGNITIVE_READINESS",
            "PHASE_01_COMPLETION_01=COGNITIVE_PATH=PASS",
        ]) + "\n"

    def spec(self, mid: str, text: str):
        return {
            "mission_id": mid,
            "title": mid,
            "objective": "cognitive gate",
            "description": "cognitive gate",
            "lpcl_digest": hashlib.sha256(text.encode()).hexdigest(),
            "lpcl_text": text,
            "source_head": "a" * 40,
            "source_tree": "b" * 40,
            "logical_count": 1,
            "material_target": 0,
            "phases": [{"id": "COGNITIVE", "title": "Cognitive"}],
            "protocols": list(self.mc.PROTOCOLS),
        }

    @staticmethod
    def conversation(mid: str):
        return {
            "conversation_id": "conv-1",
            "state": "BOUND",
            "current_binding": {
                "binding_epoch": 2,
                "mission_id": mid,
                "state": "BOUND",
            },
            "lineage": {
                "predecessor_conversation_id": "conv-0",
                "transition": "BIND",
            },
            "lanes": [{
                "binding_epoch": 2,
                "lane_id": "lane-saas",
                "provider": "SAAS",
                "provider_session_ref": "binding-saas-1",
                "state": "ACTIVE",
            }],
            "external_bridges": [{
                "bridge_id": "bridge-1",
                "external_system": "CHATGPT_PROJECT",
                "external_thread_ref": "native-1",
                "created_at": 1,
                "provenance_json": "{}",
            }],
        }

    @staticmethod
    def messages():
        return [
            {
                "message_id": "msg-user",
                "lane_id": "lane-saas",
                "role": "USER",
                "content": "sync",
                "created_at": 1,
                "metadata": {
                    "canonical_context": True,
                    "shared_context_digest": "4" * 64,
                },
            },
            {
                "message_id": "msg-saas",
                "lane_id": "lane-saas",
                "role": "ASSISTANT",
                "content": "ack",
                "created_at": 2,
                "metadata": {
                    "canonical_context": True,
                    "provider_session_ref": "binding-saas-1",
                    "provider_session_ref_class": "SAAS_BROKER_SESSION_BINDING",
                    "response_meta": {
                        "projection_digest": "5" * 64,
                        "actual_payload_bytes_digest": "6" * 64,
                        "response_digest": "7" * 64,
                    },
                },
            },
        ]

    def evidence(self, spec):
        conversation = self.conversation(spec["mission_id"])
        messages = self.messages()
        checkpoint = build_synchronization_checkpoint(
            mission_id=spec["mission_id"],
            lpcl_digest=spec["lpcl_digest"],
            source_head=spec["source_head"],
            source_tree=spec["source_tree"],
            conversation=conversation,
            messages=messages,
            consumer_role="MISSION_ACTIVATION_PREFLIGHT",
            shared_context_digest="4" * 64,
        )
        contracts = [{
            "phase_id": "COGNITIVE",
            "capability_classes": ["SAAS_DELEGATION"],
        }]
        readiness = build_mission_cognitive_continuity(
            mission_id=spec["mission_id"],
            lpcl_digest=spec["lpcl_digest"],
            source_head=spec["source_head"],
            source_tree=spec["source_tree"],
            phase_contracts=contracts,
            conversation=conversation,
            messages=messages,
            provider_capabilities={
                "SAAS": {"currentness": "CURRENT", "text_input": "SUPPORTED"},
            },
            expected_conversation_id="conv-1",
            expected_binding_epoch=2,
            shared_context_digest="4" * 64,
            synchronization_checkpoint_digest=checkpoint.checkpoint_digest,
            observed_at="2026-10-06T12:00:00Z",
        )
        return checkpoint.to_dict(), readiness

    def persist_evidence(self, mid, checkpoint, readiness):
        c = self.mc.connect()
        self.mc._process_message(
            c, mid, "THREAD", "LPCL_PANEL", "MISSION_CONTROL", None,
            {
                "event": "COGNITIVE_SYNCHRONIZATION_CHECKPOINT",
                "checkpoint": checkpoint,
                "authority_effect": "NONE",
            },
        )
        self.mc._process_message(
            c, mid, "VALIDATION", "LPCL_PANEL", "MISSION_CONTROL", None,
            {
                "event": "COGNITIVE_READINESS_PROJECTION",
                "projection": readiness,
                "authority_effect": "NONE",
            },
        )
        c.commit()
        c.close()

    def test_cognitive_mission_cannot_activate_without_readiness(self):
        spec = self.spec("COGNITIVE-GATE-R1", self.cognitive_lpcl())
        self.mc.register_lpcl_mission(spec)
        with self.assertRaisesRegex(ValueError, "cognitive readiness required"):
            self.mc.activate_lpcl_mission(
                spec["mission_id"],
                {
                    "lpcl_digest": spec["lpcl_digest"],
                    "activation_event": "EXPLICIT_UI_ACTIVATION",
                },
            )
        c = self.mc.connect()
        state = c.execute(
            "SELECT state FROM missions WHERE mission_id=?", (spec["mission_id"],)
        ).fetchone()["state"]
        c.close()
        self.assertEqual(state, "REGISTERED")

    def test_current_durable_readiness_allows_explicit_activation(self):
        spec = self.spec("COGNITIVE-GATE-R2", self.cognitive_lpcl())
        self.mc.register_lpcl_mission(spec)
        checkpoint, readiness = self.evidence(spec)
        self.persist_evidence(spec["mission_id"], checkpoint, readiness)
        with patch.object(
            self.mc,
            "bind_lpcl_execution",
            side_effect=lambda mid: self.mc.process_snapshot(mid),
        ):
            out = self.mc.activate_lpcl_mission(
                spec["mission_id"],
                {
                    "lpcl_digest": spec["lpcl_digest"],
                    "activation_event": "EXPLICIT_UI_ACTIVATION",
                    "synchronization_checkpoint": checkpoint,
                    "cognitive_readiness": readiness,
                },
            )
        self.assertEqual(out["state"], "AUTHORIZED")
        auth = next(
            msg["payload"] for msg in out["protocol_messages"]
            if msg["protocol"] == "AUTHORITY"
            and msg["payload"].get("event") == "MISSION_AUTHORIZED"
        )
        self.assertEqual(auth["cognitive_providers"], ["SAAS"])
        self.assertEqual(auth["cognitive_readiness"], "VERIFIED")

    def test_readiness_must_be_durable_not_client_only(self):
        spec = self.spec("COGNITIVE-GATE-R3", self.cognitive_lpcl())
        self.mc.register_lpcl_mission(spec)
        checkpoint, readiness = self.evidence(spec)
        with self.assertRaisesRegex(ValueError, "synchronization evidence not durable"):
            self.mc.activate_lpcl_mission(
                spec["mission_id"],
                {
                    "lpcl_digest": spec["lpcl_digest"],
                    "activation_event": "EXPLICIT_UI_ACTIVATION",
                    "synchronization_checkpoint": checkpoint,
                    "cognitive_readiness": readiness,
                },
            )

    def test_tampered_readiness_is_rejected(self):
        spec = self.spec("COGNITIVE-GATE-R4", self.cognitive_lpcl())
        self.mc.register_lpcl_mission(spec)
        checkpoint, readiness = self.evidence(spec)
        self.persist_evidence(spec["mission_id"], checkpoint, readiness)
        readiness = dict(readiness)
        readiness["binding_epoch"] = 3
        with self.assertRaisesRegex(ValueError, "cognitive readiness invalid"):
            self.mc.activate_lpcl_mission(
                spec["mission_id"],
                {
                    "lpcl_digest": spec["lpcl_digest"],
                    "activation_event": "EXPLICIT_UI_ACTIVATION",
                    "synchronization_checkpoint": checkpoint,
                    "cognitive_readiness": readiness,
                },
            )

    def test_non_cognitive_mission_keeps_existing_activation_shape(self):
        text = "PROJECT=LION_EVOLUSION\n"
        spec = self.spec("NO-COGNITIVE-GATE-R1", text)
        self.mc.register_lpcl_mission(spec)
        with patch.object(
            self.mc,
            "bind_lpcl_execution",
            side_effect=lambda mid: self.mc.process_snapshot(mid),
        ):
            out = self.mc.activate_lpcl_mission(
                spec["mission_id"],
                {
                    "lpcl_digest": spec["lpcl_digest"],
                    "activation_event": "EXPLICIT_UI_ACTIVATION",
                },
            )
        self.assertEqual(out["state"], "AUTHORIZED")


if __name__ == "__main__":
    unittest.main()
