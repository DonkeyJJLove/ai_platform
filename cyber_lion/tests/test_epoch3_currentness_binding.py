from __future__ import annotations

import unittest
from unittest.mock import patch

from tools import lion_effect_admission_broker as broker


class Epoch3CurrentnessBindingTests(unittest.TestCase):
    HEAD = "849db8f5ea6434f5647ee072cd4835fd2264e078"
    TREE = "fccec66a96e8d914dff8b835ccbbadd9dca0a608"

    @classmethod
    def _request(cls, operation: str, **extra):
        req = {
            "schema_version": "1.0.0",
            "request_id": "a" * 64,
            "operation": operation,
            "mission_id": broker.E3_ID,
            "source_head": cls.HEAD,
            "source_tree": cls.TREE,
            "spec_digest": broker.E3_LPCL_DIGEST,
        }
        req.update(extra)
        return req

    def test_read_rejects_currentness_before_runtime_read(self):
        with patch.object(broker, "mission64_verify_current", side_effect=broker.Deny("MISSION64_LIVE_SOURCE_DRIFT")) as verify, patch.object(broker, "e3_read") as read:
            with self.assertRaisesRegex(broker.Deny, "MISSION64_LIVE_SOURCE_DRIFT"):
                broker.e3_handle(self._request("EPOCH3_M64_READ"))
        verify.assert_called_once_with(self.HEAD, self.TREE)
        read.assert_not_called()

    def test_restart_one_rejects_currentness_before_material_effect(self):
        req = self._request("EPOCH3_M64_RESTART_ONE", pod_name="e3-ld10-worker-canary")
        with patch.object(broker, "mission64_verify_current", side_effect=broker.Deny("MISSION64_LIVE_SOURCE_DRIFT")) as verify, patch.object(broker, "e3_read") as read, patch.object(broker, "mission64_kubectl") as kubectl:
            with self.assertRaisesRegex(broker.Deny, "MISSION64_LIVE_SOURCE_DRIFT"):
                broker.e3_handle(req)
        verify.assert_called_once_with(self.HEAD, self.TREE)
        read.assert_not_called()
        kubectl.assert_not_called()

    def test_logical_component_rejects_currentness_before_material_effect(self):
        req = self._request("EPOCH3_M64_RESTART_LOGICAL", logical_id="LD10")
        with patch.object(broker, "mission64_verify_current", side_effect=broker.Deny("MISSION64_LIVE_SOURCE_DRIFT")) as verify, patch.object(broker, "e3_rows") as rows, patch.object(broker, "mission64_kubectl") as kubectl:
            with self.assertRaisesRegex(broker.Deny, "MISSION64_LIVE_SOURCE_DRIFT"):
                broker.e3_component_handle(req)
        verify.assert_called_once_with(self.HEAD, self.TREE)
        rows.assert_not_called()
        kubectl.assert_not_called()

    def test_read_uses_verified_currentness_on_success(self):
        runtime = {"mission_id": broker.E3_ID, "state": "RUNNING", "materialized": 64, "ready": 64, "unique_uid_count": 64, "pods": []}
        with patch.object(broker, "mission64_verify_current") as verify, patch.object(broker, "e3_read", return_value=runtime), patch.object(broker, "e3_receipt", return_value={"control_receipt": {"receipt_digest": "verified"}}):
            out = broker.e3_handle(self._request("EPOCH3_M64_READ"))
        verify.assert_called_once_with(self.HEAD, self.TREE)
        self.assertEqual(out["control_receipt"]["receipt_digest"], "verified")
        self.assertEqual(out["state"], "RUNNING")


if __name__ == "__main__":
    unittest.main()
