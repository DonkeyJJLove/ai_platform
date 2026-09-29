from __future__ import annotations

import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
GATEWAY = ROOT / "cyber_lion" / "app_coordination" / "local_intelligence_gateway.py"
BROKER_MAIN = ROOT / "browser_broker" / "src" / "main.cjs"
CANONICAL_CONSUMER = ROOT / "browser_broker" / "src" / "canonical-conversation-consumer.cjs"
MANIFEST = ROOT / "LION" / "architecture" / "v1_4" / "R24_COMPLEMENTARY_FEATURE_PRESERVATION.json"


class R24ComplementaryIntegrationContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.gateway = GATEWAY.read_text(encoding="utf-8")
        cls.broker = BROKER_MAIN.read_text(encoding="utf-8")
        cls.manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))

    def test_feature_preservation_manifest_is_exact_f01_f24(self):
        rows = self.manifest["features"]
        self.assertEqual([x["id"] for x in rows], [f"F{i:02d}" for i in range(1, 25)])
        self.assertTrue(all(x["required"] is True for x in rows))
        self.assertEqual(self.manifest["ui_contract"]["lpcl_root_path"], "/")
        self.assertEqual(self.manifest["ui_contract"]["standalone_model_chat_role"], "DIAGNOSTIC_ONLY")
        self.assertEqual(self.manifest["authority_effect"], "NONE")

    def test_complementary_ui_preserves_lpcl_and_adds_canonical_model_chat(self):
        required = (
            "LPCL mission intake",
            "Waliduj LPCL",
            "Zarejestruj misję",
            "Autoryzuj dokładny LPCL",
            "HUMAN OPERATOR CONTROL",
            "LION BUS · PROTOKÓŁ ROJU",
            "Model Calls",
            "LION Local Model",
            'data-module="canonical-model-chat"',
            'data-module="protocol-plane"',
        )
        for marker in required:
            with self.subTest(marker=marker):
                self.assertIn(marker, self.gateway)
        self.assertIn("/api/conversations", self.gateway)
        self.assertIn("/api/operator/", self.gateway)

    def test_electron_lpcl_panel_targets_full_shell_not_chat_diagnostic(self):
        self.assertIn("const PANEL=process.env.LION_PANEL_URL||'http://127.0.0.1:8780';", self.broker)
        self.assertNotIn("const PANEL=process.env.LION_PANEL_URL||'http://127.0.0.1:8780/r24-model-chat';", self.broker)
        self.assertIn("const CONTROL_PORT=Number(process.env.LION_BROWSER_CONTROL_PORT||8793);", self.broker)
        self.assertIn("listen(CONTROL_PORT,'127.0.0.1')", self.broker)
        self.assertIn("LPCL PANEL", self.broker)
        self.assertIn("ChatGPT SaaS", self.broker)

    def test_legacy_thread_mutation_remains_retired(self):
        self.assertIn("legacy thread mutation retired", self.gateway)
        self.assertIn("canonical_surface':'/api/conversations'", self.gateway)

    def test_canonical_saas_consumer_uses_conversation_identity_not_legacy_thread_identity(self):
        self.assertTrue(CANONICAL_CONSUMER.exists(), "canonical SaaS consumer successor missing")
        source = CANONICAL_CONSUMER.read_text(encoding="utf-8")
        for field in (
            "conversation_id", "binding_epoch", "lane_id", "request_message_id",
            "causation_id", "correlation_id", "context_digest", "broker_request_id",
            "external_thread_ref",
        ):
            with self.subTest(field=field):
                self.assertIn(field, source)
        self.assertNotIn("panel_thread_id", source)
        self.assertNotIn("currentConversation", source)

    def test_auto_provisioned_saas_bridge_contract_is_explicit(self):
        self.assertTrue(CANONICAL_CONSUMER.exists(), "canonical SaaS consumer successor missing")
        source = CANONICAL_CONSUMER.read_text(encoding="utf-8")
        for marker in (
            "AUTO_CREATE",
            "creation_receipt_digest",
            "external_thread_ref",
            "conversation_external_bridges",
            "EXPLICIT_BRIDGE_ONLY",
            "SUPERSEDED",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, source)

    def test_active_saas_tab_cannot_override_canonical_bridge(self):
        self.assertTrue(CANONICAL_CONSUMER.exists(), "canonical SaaS consumer successor missing")
        source = CANONICAL_CONSUMER.read_text(encoding="utf-8")
        self.assertIn("CANONICAL_BRIDGE_WINS", source)
        self.assertIn("bridge_id", source)

    def test_bind_successor_does_not_inherit_native_saas_thread(self):
        self.assertIn("conversation_bind", self.gateway)
        self.assertIn("conversation_detach", self.gateway)
        self.assertTrue(CANONICAL_CONSUMER.exists(), "canonical SaaS consumer successor missing")
        source = CANONICAL_CONSUMER.read_text(encoding="utf-8")
        self.assertIn("NO_HIDDEN_SUCCESSOR_INHERITANCE", source)

    def test_model_chat_restart_restores_last_selected_canonical_conversation(self):
        self.assertIn("const CMC_ACTIVE_KEY='lion-r24-active-conversation';", self.gateway)
        self.assertIn("localStorage.setItem(CMC_ACTIVE_KEY,c.conversation_id)", self.gateway)
        self.assertIn("const restored=localStorage.getItem(CMC_ACTIVE_KEY)", self.gateway)
        self.assertIn("cmcConversations.some(c=>c.conversation_id===restored)", self.gateway)
        self.assertIn("localStorage.removeItem(CMC_ACTIVE_KEY)", self.gateway)

    def test_model_chat_terminal_events_clear_only_matching_pending_request(self):
        self.assertIn("['DELIVERED','FAILED','DENIED','SUPERSEDED']", self.gateway)
        self.assertIn("terminal.map(e=>e.correlation_id)", self.gateway)
        self.assertIn("row.includes(corr)", self.gateway)
        self.assertIn("terminal[terminal.length-1].state", self.gateway)


if __name__ == "__main__":
    unittest.main()
