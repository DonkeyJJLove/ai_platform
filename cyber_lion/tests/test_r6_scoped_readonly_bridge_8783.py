"""Executable regressions for the exact source-bound WSL bridge listener.

Test only: no real listener, Windows process, SQLite write or LION transport effect.
"""
from __future__ import annotations

from contextlib import redirect_stderr
from hashlib import sha256
import importlib.util
import io
from pathlib import Path
import sys
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
BRIDGE = ROOT / "deploy/mission-control/v3/lion-windows-cognitive-readonly-bridge.py"
PIN = ROOT / "deploy/mission-control/v3/lion-windows-cognitive-readonly-bridge.sha256"
UNIT = ROOT / "deploy/mission-control/v3/lion-windows-8780-readonly-bridge.service"
TARGET = "/srv/lion-e4-candidate-r1/runtime/provider-8780/bridge.py"


def load_bridge():
    spec = importlib.util.spec_from_file_location("_lion_r6_verified_readonly_bridge", BRIDGE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ScopedReadOnlyBridgeTests(unittest.TestCase):
    def test_bridge_exact_sha_matches_source_carrier_and_unit_requires_pin(self):
        observed = sha256(BRIDGE.read_bytes()).hexdigest()
        self.assertEqual(PIN.read_text(encoding="utf-8"), observed + "  " + TARGET + "\n")
        unit = UNIT.read_text(encoding="utf-8")
        self.assertIn("bridge.sha256", unit)
        self.assertIn("bridge.py --serve --port 8783", unit)

    def test_only_explicit_wsl_listener_ports_allowed(self):
        bridge = load_bridge()
        seen = []

        class FakeServer:
            def __init__(self, address, handler):
                seen.append((address, handler))
            def __enter__(self):
                return self
            def __exit__(self, *_):
                pass
            def serve_forever(self):
                seen.append("SERVE")

        for port in (8780, 8783):
            seen.clear()
            with patch.object(bridge, "ThreadingHTTPServer", FakeServer), patch.object(
                sys, "argv", ["bridge", "--serve", "--port", str(port)]
            ):
                bridge.main()
            self.assertEqual(seen[0], (("127.0.0.1", port), bridge.Handler))
            self.assertEqual(seen[1], "SERVE")

        for forbidden in ("8784", "0", "8766", "18780"):
            seen.clear()
            with patch.object(bridge, "ThreadingHTTPServer", FakeServer), patch.object(
                sys, "argv", ["bridge", "--serve", "--port", forbidden]
            ), redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as error:
                    bridge.main()
            self.assertEqual(error.exception.code, 2)
            self.assertEqual(seen, [])

    def test_upstream_remains_native_windows_canonical_8780(self):
        bridge = load_bridge()
        self.assertEqual(bridge.WINDOWS_CANONICAL, "http://127.0.0.1:8780")
        self.assertEqual(bridge._allowed_target("/health"), bridge.WINDOWS_CANONICAL + "/health")
        for forbidden in (
            "/api/conversations", "/api/operator/commands", "/api/state",
            "/api/missions/M/cognitive-readiness?conversation_id=x&binding_epoch=0",
            "/api/missions/M/cognitive-readiness?conversation_id=x&binding_epoch=1&extra=a",
        ):
            self.assertIsNone(bridge._allowed_target(forbidden))
        scoped = "/api/missions/M/cognitive-readiness?conversation_id=conv-1&binding_epoch=1"
        self.assertEqual(bridge._allowed_target(scoped), bridge.WINDOWS_CANONICAL + scoped)

    def test_mutation_methods_stay_forbidden(self):
        bridge = load_bridge()
        class FakeRequest:
            def __init__(self):
                self.errors = []
            def _error(self, status, code):
                self.errors.append((status, code))
        for method in ("do_POST", "do_PUT", "do_DELETE", "do_PATCH"):
            request = FakeRequest()
            getattr(bridge.Handler, method)(request)
            self.assertEqual(request.errors, [(405, "MUTATION_FORBIDDEN")])

if __name__ == "__main__":
    unittest.main()
