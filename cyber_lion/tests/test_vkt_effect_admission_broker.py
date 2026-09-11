import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("vkt_broker", ROOT / "tools" / "lion_vkt_effect_admission_broker.py")
mod = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(mod)


class VktEffectAdmissionBrokerTests(unittest.TestCase):
    def test_operation_allowlist_is_exact(self):
        self.assertEqual(mod.OPERATIONS, {
            "PING",
            "PRECHECK_POD_RUNTIME",
            "PREPARE_LOCAL_K8S",
            "MATERIALIZE_VKT_PODS",
            "READ_POD_EVIDENCE",
            "STOP_VKT_PODS",
            "START_OSS_REPO_TEST",
            "READ_OSS_REPO_TEST_EVIDENCE",
            "STOP_OSS_REPO_TEST",
        })

    def test_only_mutating_start_operations_require_live_currentness(self):
        self.assertEqual(mod.LIVE_CURRENTNESS_REQUIRED, {
            "PREPARE_LOCAL_K8S",
            "MATERIALIZE_VKT_PODS",
            "START_OSS_REPO_TEST",
        })
        self.assertNotIn("PRECHECK_POD_RUNTIME", mod.LIVE_CURRENTNESS_REQUIRED)
        self.assertNotIn("READ_POD_EVIDENCE", mod.LIVE_CURRENTNESS_REQUIRED)
        self.assertNotIn("STOP_VKT_PODS", mod.LIVE_CURRENTNESS_REQUIRED)
        self.assertNotIn("READ_OSS_REPO_TEST_EVIDENCE", mod.LIVE_CURRENTNESS_REQUIRED)
        self.assertNotIn("STOP_OSS_REPO_TEST", mod.LIVE_CURRENTNESS_REQUIRED)

    def test_fixed_scope(self):
        self.assertEqual(mod.EXPECTED_HOST, "LION-AUTH-LAB")
        self.assertEqual(mod.BRANCH, "master")
        self.assertEqual(mod.MISSION_ID, "VKT-R3-384-REAL-POD-MISSION-CONTROL-R2")

    def test_run_id_validation(self):
        self.assertEqual(mod.require_run_id("vkt-r3-run-001"), "vkt-r3-run-001")
        for bad in ("", "../x", "a/b", "a b"):
            with self.assertRaises(mod.Deny):
                mod.require_run_id(bad)


if __name__ == "__main__":
    unittest.main()
