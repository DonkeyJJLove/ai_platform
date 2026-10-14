"""Fail-closed LION stable desktop release selector; disposable Windows tests only."""
from __future__ import annotations
import hashlib
import json
import pathlib
import subprocess
import tempfile
import unittest

ROUTER = pathlib.Path(__file__).with_name("Start-LION-Current.ps1")
HEAD = "a" * 40
TREE = "b" * 40

def digest(p: pathlib.Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()

class ReleaseSelectorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="lion-desktop-selector-")
        self.addCleanup(self.temp.cleanup)
        self.root = pathlib.Path(self.temp.name)
        (self.root / "operator").mkdir()
        staging = self.root / "staging"
        staging.mkdir()
        entry = self.root / "desktop" / "release-test-r1" / "browser_broker" / "src"
        entry.mkdir(parents=True)
        self.entry = entry / "main.cjs"
        self.entry.write_text("'use strict';\n// disposable test\n", encoding="utf-8")
        self.launcher = staging / "Start-LION-Desktop-Test.ps1"
        self.launcher.write_text(
            "[CmdletBinding()]param([switch]$ValidateOnly)\n"
            "if($ValidateOnly){Write-Output 'RESULT=PASS_LION_DESKTOP_FIXTURE_PREFLIGHT';exit 0}\n"
            "Write-Output 'RESULT=DISPOSABLE_ONLY_NO_REAL_ELECTRON'\n"
            "exit 0\n", encoding="utf-8"
        )
        self.manifest = staging / "Desktop-Test-Manifest.json"
        self.manifest.write_text(json.dumps({
            "local_head": HEAD, "git_tree": TREE, "file_count": 38
        }), encoding="utf-8")
        self.pointer = self.root / "operator" / "current-release.json"
        self.value = {
            "schema": "lion.desktop.operator-current-release/v1",
            "repository": "DonkeyJJLove/ai_platform",
            "generation": 1,
            "release_id": "TEST_RELEASE_R1",
            "source_head": HEAD,
            "source_tree": TREE,
            "launcher_relative_path": "staging/Start-LION-Desktop-Test.ps1",
            "launcher_sha256": digest(self.launcher),
            "manifest_relative_path": "staging/Desktop-Test-Manifest.json",
            "manifest_sha256": digest(self.manifest),
            "entrypoint_relative_path": "desktop/release-test-r1/browser_broker/src/main.cjs",
            "entrypoint_sha256": digest(self.entry),
        }
        self.write_pointer()

    def write_pointer(self):
        self.pointer.write_text(json.dumps(self.value), encoding="utf-8")

    def run_router(self, *args):
        return subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive",
             "-ExecutionPolicy", "Bypass", "-File", str(ROUTER),
             "-LionRoot", str(self.root), *args],
            capture_output=True, text=True, timeout=25
        )

    def test_inspect_only_never_invokes_selected_launcher(self):
        result = self.run_router("-InspectOnly")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertIn("RESULT=ROUTER_INSPECT_PASS_NO_LAUNCH", result.stdout)
        self.assertNotIn("FIXTURE_PREFLIGHT", result.stdout)

    def test_validation_invokes_exact_release_preflight_only(self):
        result = self.run_router("-ValidateOnly")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertIn("RESULT=ROUTER_VALIDATE_PASS", result.stdout)
        self.assertNotIn("DISPOSABLE_ONLY_NO_REAL_ELECTRON", result.stdout)

    def test_modified_entrypoint_denied_not_fallback_to_older_release(self):
        (self.root / "desktop" / "release-old-r1").mkdir()
        self.entry.write_text("modified without release change", encoding="utf-8")
        result = self.run_router("-InspectOnly")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("ENTRYPOINT_DIGEST_MISMATCH", result.stderr + result.stdout)

    def test_malicious_path_rejected_before_access(self):
        self.value["launcher_relative_path"] = "../outside.ps1"
        self.write_pointer()
        result = self.run_router("-InspectOnly")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("LAUNCHER_LOCATION_INVALID", result.stderr + result.stdout)

    def test_traversal_under_staging_prefix_denied(self):
        self.value["launcher_relative_path"] = "staging/../outside.ps1"
        self.write_pointer()
        result = self.run_router("-InspectOnly")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("LAUNCHER_UNSAFE_PATH", result.stderr + result.stdout)

    def test_malformed_selector_denied(self):
        self.value["schema"] = "different"
        self.write_pointer()
        result = self.run_router("-InspectOnly")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("SCHEMA_MISMATCH", result.stderr + result.stdout)

    def test_unknown_fields_denied(self):
        self.value["bypass_security"] = True
        self.write_pointer()
        result = self.run_router("-InspectOnly")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("UNRECOGNIZED_POINTER_FIELDS", result.stderr + result.stdout)

    def test_no_selected_release_never_falls_back_to_previous_launcher(self):
        self.pointer.unlink()
        result = self.run_router("-InspectOnly")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("LION_CURRENT_RELEASE_NOT_SELECTED", result.stderr + result.stdout)

    def test_hash_pins_hold_across_unmodified_pointer_generation(self):
        result = self.run_router("-InspectOnly")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.value["generation"] = 2
        self.value["release_id"] = "TEST_RELEASE_R2"
        self.write_pointer()
        result = self.run_router("-InspectOnly")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertIn("GENERATION=2", result.stdout)

if __name__ == "__main__":
    unittest.main()
