import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("lion_k3s_pod_materializer", ROOT / "tools" / "lion_k3s_pod_materializer.py")
mod = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(mod)


class VktPodMaterializerTests(unittest.TestCase):
    def test_fixed_host_and_namespace(self):
        self.assertEqual(mod.EXPECTED_HOST, "LION-AUTH-LAB")
        self.assertEqual(mod.NAMESPACE, "vkt-r3")

    def test_exact_fleet_cardinality(self):
        self.assertEqual(mod.EXPECTED_COUNTS, {"TIGER": 128, "SPECTRA": 128, "LION": 128})
        self.assertEqual(sum(mod.EXPECTED_COUNTS.values()), 384)

    def test_manifest_materializes_real_kubernetes_workloads(self):
        docs = mod.manifest()["documents"]
        sets = [x for x in docs if x.get("kind") == "StatefulSet"]
        self.assertEqual(len(sets), 3)
        self.assertEqual({x["metadata"]["name"] for x in sets}, {"tiger-drone", "spectra-drone", "lion-drone"})
        self.assertTrue(all(x["spec"]["replicas"] == 128 for x in sets))
        self.assertTrue(all(x["spec"]["template"]["metadata"]["labels"]["component"] == "drone" for x in sets))

    def test_no_privileged_drone_containers(self):
        for obj in mod.manifest()["documents"]:
            if obj.get("kind") != "StatefulSet":
                continue
            sc = obj["spec"]["template"]["spec"]["containers"][0]["securityContext"]
            self.assertIs(sc["allowPrivilegeEscalation"], False)
            self.assertIs(sc["readOnlyRootFilesystem"], True)
            self.assertIs(sc["runAsNonRoot"], True)
            self.assertEqual(sc["capabilities"]["drop"], ["ALL"])

    def test_vendor_runtime_not_embedded_in_drone_contract(self):
        text = (ROOT / "tools" / "lion_k3s_pod_materializer.py").read_text(encoding="utf-8")
        self.assertNotIn("viktor.com", text)
        self.assertNotIn("api.viktor.com", text)

    def test_embedded_runtime_sources_are_valid_python(self):
        data = mod.manifest()["documents"][1]["data"]
        self.assertIn("drone.py", data)
        self.assertIn("router.py", data)
        for name in ("drone.py", "router.py"):
            self.assertNotIn("\\n", data[name])
            compile(data[name], name, "exec")



if __name__ == "__main__":
    unittest.main()
