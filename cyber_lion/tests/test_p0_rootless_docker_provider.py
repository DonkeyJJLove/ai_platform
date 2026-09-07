from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
PROVIDER_PATH = ROOT / "tools" / "p0_rootless_docker_provider.py"
INSTALLER_PATH = ROOT / "deploy" / "docker" / "lion-p0-provider" / "install.sh"
UNIT_PATH = ROOT / "deploy" / "docker" / "lion-p0-provider" / "lion-p0-rootless-docker-provider.service"


class RootlessDockerProviderP0Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ.setdefault("LION_P0_ALLOWED_CALLER_UID", "993")
        spec = importlib.util.spec_from_file_location("p0_rootless_docker_provider", PROVIDER_PATH)
        assert spec and spec.loader
        cls.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.module)

    def request(self, operation: str = "PING", payload=None):
        return {
            "schema_version": "1.0.0",
            "request_id": "0" * 64,
            "operation": operation,
            "mission_id": "mission-p0",
            "fleet_id": "lion-local-swarm-p0",
            "run_id": "run-p0",
            "source_head": "1" * 40,
            "source_tree": "2" * 40,
            "plan_digest": "3" * 64,
            "payload": {} if payload is None else payload,
        }

    def test_provider_accepts_closed_ping_request(self):
        self.module._validate_request(self.request())

    def test_provider_rejects_unknown_operation_and_extra_field(self):
        req = self.request(operation="ARBITRARY_DOCKER")
        with self.assertRaises(self.module.Deny):
            self.module._validate_request(req)
        req = self.request()
        req["command"] = ["docker", "run", "--privileged"]
        with self.assertRaises(self.module.Deny):
            self.module._validate_request(req)

    def test_provider_has_no_shell_or_rootful_socket_default(self):
        source = PROVIDER_PATH.read_text(encoding="utf-8")
        self.assertIn("shell=False", source)
        self.assertNotIn("shell=True", source)
        self.assertNotIn("unix:///var/run/docker.sock", source)
        self.assertNotIn('"/var/run/docker.sock"', source)

    def test_docker_client_state_stays_inside_private_provider_state(self):
        source = PROVIDER_PATH.read_text(encoding="utf-8")
        self.assertNotIn('"HOME": "/nonexistent"', source)
        self.assertIn('client_home = STATE_DIR / "client-home"', source)
        self.assertIn('"DOCKER_CONFIG": str(docker_config)', source)
        self.assertIn('"XDG_CACHE_HOME": str(xdg_cache)', source)
        self.assertIn('"XDG_CONFIG_HOME": str(xdg_config)', source)

    def test_mutating_surface_is_exact_and_bounded(self):
        self.assertEqual(
            self.module.MUTATING,
            {"BUILD_P0_IMAGE", "CREATE_NETWORK", "RUN_DRONE", "STOP_DRONE", "REMOVE_DRONE", "REMOVE_NETWORK"},
        )

    def test_installer_targets_exact_lab_users_and_never_docker_group(self):
        source = INSTALLER_PATH.read_text(encoding="utf-8")
        self.assertIn('TARGET_HOST="LION-AUTH-LAB"', source)
        self.assertIn('RUNTIME_USER="lion-container-runtime-lab"', source)
        self.assertIn('RUNNER_USER="lion-maintenance-runner"', source)
        self.assertIn('PROVIDER_GROUP="lion-docker-p0"', source)
        self.assertIn('usermod -aG "$PROVIDER_GROUP" "$RUNNER_USER"', source)
        self.assertNotIn("usermod -aG docker", source)
        self.assertNotIn("chmod 666 /var/run/docker.sock", source)
        self.assertNotIn("chown root:docker /var/run/docker.sock", source)

    def test_runner_restart_is_exact_and_opt_in(self):
        source = INSTALLER_PATH.read_text(encoding="utf-8")
        self.assertIn(
            'RUNNER_UNIT="actions.runner.DonkeyJJLove-ai_platform.lion-moon-r9d8-test.service"',
            source,
        )
        self.assertIn("RESTART_RUNNER:-0", source)
        self.assertNotIn("systemctl restart actions.runner.*", source)

    def test_service_runs_provider_as_rootless_owner_with_hardening(self):
        source = UNIT_PATH.read_text(encoding="utf-8")
        for token in (
            "User=lion-container-runtime-lab",
            "SupplementaryGroups=lion-docker-p0",
            "NoNewPrivileges=yes",
            "PrivateDevices=yes",
            "ProtectSystem=strict",
            "ProtectHome=tmpfs",
            "BindReadOnlyPaths=/run/user/1000/docker.sock",
            "RestrictAddressFamilies=AF_UNIX",
            "CapabilityBoundingSet=",
        ):
            self.assertIn(token, source)


if __name__ == "__main__":
    unittest.main()
