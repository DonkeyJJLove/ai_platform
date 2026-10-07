from __future__ import annotations

import hashlib
import importlib
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cyber_lion.app_coordination.cognitive_continuity import build_mission_cognitive_continuity


class CognitiveReadinessActivationTests(unittest.TestCase):
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

    def _lpcl(self, mission_id: str, capability: str) -> str:
        return (
            "PROJECT=LION_EVOLUSION\n"
            "MODE=AUTONOMOUS_EXECUTE\n"
            "CONTROL_LANGUAGE=LPCL/1.2\n"
            f"MISSION_ID={mission_id}\n"
            "MISSION_TITLE=Cognitive readiness test\n"
            "MISSION_OBJECTIVE=Verify cognitive readiness before activation\n"
            "MISSION_DESCRIPTION=Unit test\n"
            "LOGICAL_DRONE_COUNT=1\n"
            "MATERIAL_DRONE_COUNT=0\n"
            "PROTOCOLS=LPCL,AUTHORITY,CURRENTNESS,EVIDENCE,VALIDATION,RECEIPT,CONTROL\n"
            "PHASE_01=COGNITIVE_PHASE|Cognitive phase\n"
            "PHASE_01_EXECUTION_CLASS=COGNITIVE\n"
            f"PHASE_01_CAPABILITY_CLASS={capability}\n"
            "PHASE_01_EFFECT_CEILING=NONE\n"
            "PHASE_01_BINDING_MODE=DYNAMIC\n"
            "PHASE_01_ON_MISSING_CAPABILITY=WAIT_AND_DISCOVER\n"
            "PHASE_01_AUTO_RESUME=TRUE\n"
            "PHASE_01_VERIFY_BEFORE_MUTATE=TRUE\n"
            "PHASE_01_CURRENTNESS=COGNITIVE_BINDING_CURRENT\n"
            "PHASE_01_EVIDENCE=COGNITIVE_READINESS_PROJECTION\n"
            "PHASE_01_COMPLETION_01=COGNITIVE_PHASE_DONE=PASS\n"
        )

    def _register(self, mission_id: str, capability: str):
        text = self._lpcl(mission_id, capability)
        spec = {
            "mission_id": mission_id,
            "title": mission_id,
            "objective": "Verify cognitive readiness before activation",
            "description": "Unit test",
            "lpcl_digest": hashlib.sha256(text.encode()).hexdigest(),
            "lpcl_text": text,
            "source_head": "a" * 40,
            "source_tree": "b" * 40,
            "logical_count": 1,
            "material_target": 0,
            "phases": [{"id": "COGNITIVE_PHASE", "title": "Cognitive phase"}],
            "protocols": list(self.mc.PROTOCOLS),
        }
        self.mc.register_lpcl_mission(spec)
        return spec

    def _ready_saas_projection(self, spec, conversation_id="conv-ready", epoch=1):
        sync_digest = "5" * 64
        conversation = {
            "conversation_id": conversation_id,
            "state": "BOUND",
            "current_binding": {
                "mission_id": spec["mission_id"],
                "binding_epoch": epoch,
                "state": "BOUND",
            },
            "lanes": [{
                "lane_id": "lane-saas",
                "binding_epoch": epoch,
                "provider": "SAAS",
                "provider_session_ref": "broker-binding-1",
                "state": "READY",
            }],
            "external_bridges": [{
                "bridge_id": "bridge-1",
                "external_system": "CHATGPT_SAAS",
                "external_thread_ref": "native-1",
                "created_at": 1,
                "provenance_json": "{}",
            }],
        }
        messages = [{
            "message_id": "assistant-1",
            "lane_id": "lane-saas",
            "role": "ASSISTANT",
            "created_at": 2,
            "metadata": {
                "provider_session_ref": "broker-binding-1",
                "provider_session_ref_class": "SAAS_BROKER_SESSION_BINDING",
                "synchronization_checkpoint_digest": sync_digest,
                "response_meta": {
                    "projection_digest": "6" * 64,
                    "actual_payload_bytes_digest": "7" * 64,
                    "response_digest": "8" * 64,
                    "synchronization_checkpoint_digest": sync_digest,
                },
            },
        }]
        capabilities = {
            "SAAS": {
                "currentness": "CURRENT",
                "text_input": "SUPPORTED",
            }
        }
        c = self.mc.connect()
        try:
            contracts = [
                self.mc.global_sched.phase_execution_contract(c, spec["mission_id"], "COGNITIVE_PHASE")
            ]
        finally:
            c.close()
        return build_mission_cognitive_continuity(
            mission_id=spec["mission_id"],
            lpcl_digest=spec["lpcl_digest"],
            source_head=spec["source_head"],
            source_tree=spec["source_tree"],
            phase_contracts=contracts,
            conversation=conversation,
            messages=messages,
            provider_capabilities=capabilities,
            expected_conversation_id=conversation_id,
            expected_binding_epoch=epoch,
            shared_context_digest="9" * 64,
            synchronization_checkpoint_digest=sync_digest,
            observed_at="2026-10-06T16:00:00Z",
        )

    def test_saas_required_activation_is_denied_without_cognitive_binding(self):
        spec = self._register("COG-SAAS-NO-BIND-R1", "SAAS_DELEGATION")
        with self.assertRaisesRegex(ValueError, "cognitive readiness binding required"):
            self.mc.activate_lpcl_mission(
                spec["mission_id"],
                {"lpcl_digest": spec["lpcl_digest"], "activation_event": "EXPLICIT_UI_ACTIVATION"},
            )
        c = self.mc.connect()
        try:
            row = c.execute("SELECT state FROM missions WHERE mission_id=?", (spec["mission_id"],)).fetchone()
            self.assertEqual(row["state"], "REGISTERED")
        finally:
            c.close()

    def test_exact_current_readiness_allows_separate_explicit_activation(self):
        spec = self._register("COG-SAAS-READY-R1", "SAAS_DELEGATION")
        projection = self._ready_saas_projection(spec)
        payload = {
            "lpcl_digest": spec["lpcl_digest"],
            "activation_event": "EXPLICIT_UI_ACTIVATION",
            "conversation_id": "conv-ready",
            "binding_epoch": 1,
            "readiness_projection_digest": projection["projection_digest"],
        }
        with (
            patch.object(self.mc, "_cognitive_readiness_readback", return_value={"readiness": projection}),
            patch.object(self.mc, "bind_lpcl_execution", return_value={"mission_id": spec["mission_id"], "state": "AUTHORIZED"}),
        ):
            out = self.mc.activate_lpcl_mission(spec["mission_id"], payload)
        self.assertEqual(out["state"], "AUTHORIZED")
        c = self.mc.connect()
        try:
            mission = c.execute("SELECT state FROM missions WHERE mission_id=?", (spec["mission_id"],)).fetchone()
            process = c.execute("SELECT authority_state FROM mission_process_specs WHERE mission_id=?", (spec["mission_id"],)).fetchone()
            self.assertEqual(mission["state"], "AUTHORIZED")
            self.assertEqual(process["authority_state"], "EXPLICIT_USER_ACTIVATION")
        finally:
            c.close()

    def test_readiness_digest_substitution_fails_closed(self):
        spec = self._register("COG-SAAS-DIGEST-R1", "SAAS_DELEGATION")
        projection = self._ready_saas_projection(spec)
        with patch.object(self.mc, "_cognitive_readiness_readback", return_value={"readiness": projection}):
            with self.assertRaisesRegex(ValueError, "cognitive readiness digest drift"):
                self.mc.activate_lpcl_mission(
                    spec["mission_id"],
                    {
                        "lpcl_digest": spec["lpcl_digest"],
                        "activation_event": "EXPLICIT_UI_ACTIVATION",
                        "conversation_id": "conv-ready",
                        "binding_epoch": 1,
                        "readiness_projection_digest": "f" * 64,
                    },
                )

    def test_non_cognitive_mission_preserves_existing_activation_path(self):
        spec = self._register("COG-NONE-R1", "CONTROL_PLANE_RECONNAISSANCE")
        with (
            patch.object(self.mc, "_cognitive_readiness_readback") as readback,
            patch.object(self.mc, "bind_lpcl_execution", return_value={"mission_id": spec["mission_id"], "state": "AUTHORIZED"}),
        ):
            out = self.mc.activate_lpcl_mission(
                spec["mission_id"],
                {"lpcl_digest": spec["lpcl_digest"], "activation_event": "EXPLICIT_UI_ACTIVATION"},
            )
        readback.assert_not_called()
        self.assertEqual(out["state"], "AUTHORIZED")


if __name__ == "__main__":
    unittest.main()
