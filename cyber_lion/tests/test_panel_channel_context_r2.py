from __future__ import annotations

from pathlib import Path
import unittest

from cyber_lion.app_coordination import hybrid_gateway_extension
from cyber_lion.app_coordination.saas_handoff_extension import (
    ROUTE_CONTEXT,
    THREAD_CONTEXT,
    apply_saas_handoff_extension,
)


ROOT = Path(__file__).resolve().parents[2]


class PanelChannelContextR2Tests(unittest.TestCase):
    def test_firefox_mediator_is_explicit_opt_in(self):
        source = (ROOT / "tools" / "firefox_mediator" / "mediator.js").read_text(encoding="utf-8")
        self.assertIn("relayEnabled=false", source)
        self.assertIn("async function tick(){if(!relayEnabled)return;await ensureDriver();", source)
        self.assertIn('status("DISABLED",{reason:"RELAY_OFF"});\nserver.listen', source)
        self.assertIn('reason:"EXPLICIT_RELAY_ON"', source)
        self.assertIn('/control/relay/off', source)

    def test_ui_patch_makes_channel_context_scroll_and_operator_state_explicit(self):
        from cyber_lion.app_coordination import local_intelligence_gateway as gateway

        original = gateway.UI
        try:
            hybrid_gateway_extension._patch_ui()
            ui = gateway.UI
            self.assertIn("SAAS · SentinelX default", ui)
            self.assertIn("DUAL · LOCAL + SaaS", ui)
            self.assertIn('id="chatContext"', ui)
            self.assertIn("lastPayload?.thread_context", ui)
            self.assertIn("lionViewportEpoch", ui)
            self.assertIn("v.epoch!==lionViewportEpoch", ui)
            self.assertIn("block:role==='assistant'?'start':'end'", ui)
            self.assertIn("addMsg(m.role,m.content,{scroll:false})", ui)
            self.assertIn("sort((a,b)=>Number(b.created_at||0)-Number(a.created_at||0))", ui)
            self.assertIn("UNPAIRED · CONTROLS DISABLED", ui)
            self.assertIn("setOperatorControlAvailability(false)", ui)
            self.assertIn("Browser relay: WŁĄCZ", ui)
        finally:
            gateway.UI = original

    def test_thread_context_is_attested_and_thread_scoped_saas_carries_mission_context(self):
        class Dummy:
            def __init__(self):
                self.calls = []
                self.control_provider = self.control

            def _route(self, message):
                return "MODEL_ONLY", "base"

            def state(self):
                return {}

            def chat(self, message, use_web=False, history=None, output_language="auto"):
                return {"route": "MODEL_ONLY", "answer": "local", "tool_calls": [], "material_receipts": []}

            def control(self, op, args):
                self.calls.append((op, args))
                if op == "recent":
                    return {"focus_mission_id": "M1", "missions": [{"mission_id": "M1", "current_phase": "P1"}]}
                if op == "post_message":
                    return {"ok": True}
                if op == "saas_request":
                    return {
                        "request_code": "ABCD1234",
                        "request_id": "saas-" + "1" * 32,
                        "transport": "CHATGPT_SENTINELX_SESSION_MEDIATED",
                        "authority_effect": "NONE",
                    }
                raise AssertionError((op, args))

        apply_saas_handoff_extension(Dummy)
        dummy = Dummy()
        thread_token = THREAD_CONTEXT.set("a" * 32)
        route_token = ROUTE_CONTEXT.set("SAAS")
        try:
            out = dummy.chat("status", output_language="pl")
        finally:
            THREAD_CONTEXT.reset(thread_token)
            ROUTE_CONTEXT.reset(route_token)

        attest = [args for op, args in dummy.calls if op == "post_message"]
        self.assertEqual(len(attest), 1)
        self.assertEqual(attest[0]["protocol"], "THREAD")
        self.assertEqual(attest[0]["payload"]["event"], "THREAD_CONTEXT_BOUND")
        self.assertEqual(attest[0]["payload"]["mission_id"], "M1")
        self.assertEqual(attest[0]["payload"]["composer_route"], "SAAS")
        self.assertEqual(attest[0]["payload"]["authority_effect"], "NONE")

        requests = [args for op, args in dummy.calls if op == "saas_request"]
        self.assertEqual(len(requests), 1)
        self.assertEqual(requests[0]["scope_type"], "THREAD")
        self.assertEqual(requests[0]["thread_id"], "a" * 32)
        self.assertEqual(requests[0]["mission_id"], "M1")
        self.assertEqual(out["thread_context"]["binding_state"], "BOUND_TO_FOCUS_MISSION")
        self.assertEqual(out["thread_context"]["mission_id"], "M1")
        self.assertIn("CHATGPT_SENTINELX_SESSION_MEDIATED", out["answer"])
        self.assertIn("Firefox nie jest automatycznie uruchamiany", out["answer"])

    def test_degraded_dual_control_plane_scope_does_not_encode_mission_as_broker_scope(self):
        class Dummy:
            def __init__(self):
                self.calls = []
                self.control_provider = self.control

            def _route(self, message):
                return "MODEL_ONLY", "base"

            def state(self):
                return {}

            def chat(self, message, use_web=False, history=None, output_language="auto"):
                return {"route": "MODEL_ONLY", "answer": "LOCAL", "tool_calls": [], "material_receipts": []}

            def control(self, op, args):
                self.calls.append((op, args))
                if op == "recent":
                    return {"focus_mission_id": "M1", "missions": []}
                if op == "process":
                    raise RuntimeError("mission snapshot temporarily unavailable")
                if op == "saas_request":
                    return {
                        "request_code": "DUAL1234",
                        "request_id": "saas-" + "2" * 32,
                        "transport": "CHATGPT_SENTINELX_SESSION_MEDIATED",
                        "authority_effect": "NONE",
                    }
                raise AssertionError((op, args))

        apply_saas_handoff_extension(Dummy)
        dummy = Dummy()
        route_token = ROUTE_CONTEXT.set("DUAL")
        try:
            out = dummy.chat("compare", output_language="pl")
        finally:
            ROUTE_CONTEXT.reset(route_token)

        requests = [args for op, args in dummy.calls if op == "saas_request"]
        self.assertEqual(len(requests), 1)
        self.assertEqual(requests[0]["scope_type"], "CONTROL_PLANE")
        self.assertNotIn("mission_id", requests[0])
        self.assertNotIn("thread_id", requests[0])
        self.assertEqual(out["thread_context"]["mission_id"], "M1")
        self.assertEqual(out["thread_context"]["binding_state"], "UNBOUND")


if __name__ == "__main__":
    unittest.main()
