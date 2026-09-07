from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import unittest

from tools.p0_docker_drone_runtime import (
    CONTROL_KEY,
    MAX_HOLD_SECONDS,
    _split_payload,
    execute_capsule,
)
from tools.p0_docker_fleet_contract import DockerFleetPolygonContractError, MissionCapsule

ROOT = Path(__file__).resolve().parents[2]
SCALE_RUNNER = ROOT / "tools" / "p0_docker_scale64_soak.py"
D = lambda value: sha256(value.encode()).hexdigest()


def capsule(control=None):
    payload = {"contracts": 7, "epoch": "1.4"}
    if control is not None:
        payload[CONTROL_KEY] = control
    return MissionCapsule.issue(
        mission_id="lion-local-swarm-scale64",
        fleet_id="lion-local-swarm-scale64",
        drone_id="drone-scale64-00",
        role="architecture",
        generation=1,
        work_unit_id="work-scale64-00",
        issued_at="2099-01-01T00:00:00Z",
        expires_at="2099-01-01T01:00:00Z",
        operation="ARCHITECTURE_DIGEST",
        input_payload=payload,
        policy_digest=D("policy"),
    )


class DockerScale64Tests(unittest.TestCase):
    def test_scale_control_is_bounded_and_removed_from_d0_payload(self):
        control = {
            "mode": "hold_after_result",
            "hold_seconds": 360,
            "heartbeat_seconds": 15,
            "scale_run_id": "scale64-static",
        }
        operation_payload, parsed = _split_payload(capsule(control).input_payload)
        self.assertEqual(parsed, control)
        self.assertNotIn(CONTROL_KEY, operation_payload)
        result = execute_capsule(capsule(control))
        self.assertEqual(result.status, "SUCCEEDED")
        self.assertEqual(result.result["object_count"], 2)

    def test_scale_control_rejects_unbounded_hold_and_unknown_keys(self):
        good = {
            "mode": "hold_after_result",
            "hold_seconds": 360,
            "heartbeat_seconds": 15,
            "scale_run_id": "scale64-static",
        }
        for bad in (
            {**good, "hold_seconds": MAX_HOLD_SECONDS + 1},
            {**good, "heartbeat_seconds": 1},
            {**good, "command": "sleep 999"},
            {**good, "mode": "arbitrary_exec"},
        ):
            with self.assertRaises(DockerFleetPolygonContractError):
                _split_payload(capsule(bad).input_payload)

    def test_scale_runner_is_exactly_64_and_three_minutes_by_default(self):
        source = SCALE_RUNNER.read_text(encoding="utf-8")
        self.assertIn("DRONE_COUNT = 64", source)
        self.assertIn("SOAK_SECONDS = 180", source)
        self.assertIn("POLL_SECONDS = 15", source)
        self.assertIn('MISSION_ID = "lion-local-swarm-scale64"', source)
        self.assertIn('FLEET_ID = "lion-local-swarm-scale64"', source)

    def test_scale_runner_uses_existing_bounded_provider_only(self):
        source = SCALE_RUNNER.read_text(encoding="utf-8")
        self.assertIn('call("RUN_DRONE"', source)
        self.assertIn('call("INSPECT_DRONE"', source)
        self.assertIn('call("LIST_MISSION_RESOURCES"', source)
        self.assertIn('request("REMOVE_DRONE"', source)
        self.assertIn('request("REMOVE_NETWORK"', source)
        self.assertIn('send_request', source)
        for forbidden in (
            "subprocess.run",
            "os.system",
            "--privileged",
            "--network=host",
            "docker system prune",
        ):
            self.assertNotIn(forbidden, source)

    def test_scale_runner_has_failure_safe_teardown_and_cleanup_gate(self):
        source = SCALE_RUNNER.read_text(encoding="utf-8")
        self.assertIn("finally:", source)
        self.assertIn('print("===== DISSOLVE FLEET =====")', source)
        self.assertIn("cleanup_verified = not inventory", source)
        self.assertIn("return 0 if success else 1", source)


if __name__ == "__main__":
    unittest.main()
