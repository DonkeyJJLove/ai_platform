"""Regression for the exact isolated WSL bridge listener and cognitive consumer."""
from __future__ import annotations
from pathlib import Path
import ast
import unittest

ROOT = Path(__file__).resolve().parents[2]
BROKER = ROOT / "tools" / "lion_effect_admission_broker.py"
MISSION = ROOT / "tools" / "lion_mission_control_v3.py"
BRIDGE_UNIT = ROOT / "deploy" / "mission-control" / "v3" / "lion-windows-8780-readonly-bridge.service"

class WindowsCognitiveBridgePortTests(unittest.TestCase):
    def test_installed_unit_keeps_exact_bridge_and_moves_only_wsl_listener(self):
        source = BRIDGE_UNIT.read_text(encoding="utf-8")
        self.assertIn("ExecStartPre=/usr/bin/sha256sum -c /srv/lion-e4-candidate-r1/runtime/provider-8780/bridge.sha256", source)
        self.assertIn("bridge.py --serve --port 8783", source)
        self.assertNotIn("bridge.py --serve --port 8780", source)
        self.assertIn("User=sentinelx", source)
        self.assertIn("NoNewPrivileges=true", source)
        self.assertIn("Conflicts=lion-lpcl-panel-8780-recovery.service", source)

    def test_canonical_mission_control_deploy_uses_the_new_scoped_bridge_address(self):
        raw = BROKER.read_text(encoding="utf-8")
        ast.parse(raw)
        self.assertIn('Environment="LION_COGNITIVE_READINESS_URL=http://127.0.0.1:8783"', raw)
        self.assertIn("MISSION_CONTROL_V3_DROPIN_TEXT", raw)
        self.assertIn("MISSION_CONTROL_V3_INSTALL", raw)
        self.assertIn("MISSION_CONTROL_V3_STAGE_CURRENT_MASTER", raw)

    def test_readiness_consumer_keeps_existing_fail_closed_source_binding(self):
        source=MISSION.read_text(encoding="utf-8")
        self.assertIn("os.environ.get('LION_COGNITIVE_READINESS_URL'", source)
        self.assertIn("cognitive readiness endpoint must be local HTTP", source)
        self.assertIn("validate_cognitive_readiness_projection",source)
        self.assertIn("activation currentness drift",source)

if __name__ == "__main__":
    unittest.main()
