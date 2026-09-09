import copy
import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module

provider = load("lion_k3s_pod_provider", ROOT / "tools" / "lion_k3s_pod_provider.py")
materializer = load("lion_k3s_pod_materializer", ROOT / "tools" / "lion_k3s_pod_materializer.py")


class VktK3sProviderTests(unittest.TestCase):
    def manifest(self):
        return copy.deepcopy(materializer.manifest())

    def assertDenied(self, payload):
        with self.assertRaises(provider.Deny):
            provider.validate_manifest_payload(payload)

    def test_operation_allowlist_is_exact(self):
        self.assertEqual(provider.ALLOWED_OPERATIONS, {"PRECHECK_POD_RUNTIME", "PREPARE_LOCAL_K8S", "MATERIALIZE_VKT_PODS", "READ_POD_EVIDENCE", "STOP_VKT_PODS"})

    def test_current_manifest_passes_bounded_contract(self):
        result = provider.validate_manifest_payload(self.manifest())
        self.assertEqual(result["drone_pods"], 384)
        self.assertEqual(result["fleet_counts"], {"TIGER": 128, "SPECTRA": 128, "LION": 128})

    def test_arbitrary_namespace_is_denied(self):
        p = self.manifest(); p["documents"][1]["metadata"]["namespace"] = "default"; self.assertDenied(p)

    def test_arbitrary_image_is_denied(self):
        p = self.manifest(); target = next(d for d in p["documents"] if d.get("kind") == "StatefulSet"); target["spec"]["template"]["spec"]["containers"][0]["image"] = "busybox:latest"; self.assertDenied(p)

    def test_privileged_drone_is_denied(self):
        p = self.manifest(); target = next(d for d in p["documents"] if d.get("kind") == "StatefulSet"); target["spec"]["template"]["spec"]["containers"][0]["securityContext"]["privileged"] = True; self.assertDenied(p)

    def test_host_path_is_denied(self):
        p = self.manifest(); target = next(d for d in p["documents"] if d.get("kind") == "StatefulSet"); target["spec"]["template"]["spec"]["volumes"].append({"name": "escape", "hostPath": {"path": "/"}}); self.assertDenied(p)

    def test_cardinality_drift_is_denied(self):
        p = self.manifest(); target = next(d for d in p["documents"] if d.get("metadata", {}).get("name") == "lion-drone"); target["spec"]["replicas"] = 127; self.assertDenied(p)


if __name__ == "__main__":
    unittest.main()
