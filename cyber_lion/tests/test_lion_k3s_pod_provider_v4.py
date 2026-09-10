import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "lion_k3s_pod_provider_v4_test_view",
    ROOT / "tools" / "lion_k3s_pod_provider_v4.py",
)
mod = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(mod)


class VktK3sProviderV4Tests(unittest.TestCase):
    def test_fixed_target_and_immutable_images(self):
        self.assertEqual(mod.OSS_TEST_NAMESPACE, "oss-test-itsdangerous")
        self.assertEqual(mod.OSS_TEST_JOB, "itsdangerous-pytest")
        self.assertEqual(mod.OSS_TEST_REPOSITORY, "https://github.com/pallets/itsdangerous.git")
        self.assertEqual(mod.OSS_TEST_COMMIT, "672971d66a2ef9f85151e53283113f33d642dabd")
        self.assertRegex(mod.OSS_GIT_IMAGE, r"^alpine/git@sha256:[0-9a-f]{64}$")
        self.assertRegex(mod.OSS_PYTHON_IMAGE, r"^python@sha256:[0-9a-f]{64}$")

    def test_operation_surface_is_exact(self):
        self.assertEqual(
            mod.OSS_OPERATIONS,
            {"START_OSS_REPO_TEST", "READ_OSS_REPO_TEST_EVIDENCE", "STOP_OSS_REPO_TEST"},
        )

    def test_manifest_is_non_privileged_and_has_no_host_escape(self):
        payload = mod.oss_test_manifest()
        items = payload["items"]
        self.assertEqual(items[0]["kind"], "Namespace")
        self.assertEqual(items[0]["metadata"]["name"], mod.OSS_TEST_NAMESPACE)
        job = next(x for x in items if x["kind"] == "Job")
        spec = job["spec"]["template"]["spec"]
        self.assertFalse(spec["automountServiceAccountToken"])
        self.assertTrue(spec["securityContext"]["runAsNonRoot"])
        self.assertEqual(spec["securityContext"]["runAsUser"], 1000)
        self.assertNotIn("hostNetwork", spec)
        self.assertNotIn("hostPID", spec)
        self.assertNotIn("hostIPC", spec)
        for volume in spec["volumes"]:
            self.assertNotIn("hostPath", volume)
        for container in spec["initContainers"] + spec["containers"]:
            sc = container["securityContext"]
            self.assertTrue(sc["runAsNonRoot"])
            self.assertFalse(sc["allowPrivilegeEscalation"])
            self.assertTrue(sc["readOnlyRootFilesystem"])
            self.assertEqual(sc["capabilities"]["drop"], ["ALL"])
            self.assertNotIn("privileged", sc)

    def test_manifest_network_is_ingress_deny_dns_and_https_only(self):
        policy = next(x for x in mod.oss_test_manifest()["items"] if x["kind"] == "NetworkPolicy")
        self.assertEqual(policy["spec"]["ingress"], [])
        ports = {
            (p["protocol"], p["port"])
            for rule in policy["spec"]["egress"]
            for p in rule.get("ports", [])
        }
        self.assertEqual(ports, {("UDP", 53), ("TCP", 53), ("TCP", 443)})

    def test_clone_and_test_commands_are_fixed(self):
        job = next(x for x in mod.oss_test_manifest()["items"] if x["kind"] == "Job")
        spec = job["spec"]["template"]["spec"]
        clone_script = spec["initContainers"][0]["args"][0]
        test_script = spec["containers"][0]["args"][0]
        self.assertIn(mod.OSS_TEST_REPOSITORY, clone_script)
        self.assertIn(mod.OSS_TEST_COMMIT, clone_script)
        self.assertIn("git rev-parse HEAD", clone_script)
        self.assertIn("python -m pytest", test_script)
        self.assertIn("pytest freezegun", test_script)

    def test_systemd_unit_runs_v4(self):
        unit = (ROOT / "deploy" / "k8s" / "vkt-r3" / "lion-k3s-pod-provider@.service").read_text()
        self.assertIn("lion_k3s_pod_provider_v4.py", unit)
        self.assertNotIn("ExecStart=/usr/bin/python3 /opt/lion/k3s-vkt-r3/repo/tools/lion_k3s_pod_provider_v3.py", unit)


if __name__ == "__main__":
    unittest.main()
