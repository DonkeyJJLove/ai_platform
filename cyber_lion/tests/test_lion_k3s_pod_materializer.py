import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "lion_k3s_pod_materializer",
    ROOT / "tools" / "lion_k3s_pod_materializer.py",
)
mod = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(mod)


def test_fixed_host_and_namespace():
    assert mod.EXPECTED_HOST == "LION-AUTH-LAB"
    assert mod.NAMESPACE == "vkt-r3"


def test_exact_fleet_cardinality():
    assert mod.EXPECTED_COUNTS == {"TIGER": 128, "SPECTRA": 128, "LION": 128}
    assert sum(mod.EXPECTED_COUNTS.values()) == 384


def test_manifest_materializes_real_kubernetes_workloads():
    payload = mod.manifest()
    docs = payload["documents"]
    sets = [x for x in docs if x.get("kind") == "StatefulSet"]
    assert len(sets) == 3
    assert {x["metadata"]["name"] for x in sets} == {"tiger-drone", "spectra-drone", "lion-drone"}
    assert all(x["spec"]["replicas"] == 128 for x in sets)
    assert all(x["spec"]["template"]["metadata"]["labels"]["component"] == "drone" for x in sets)


def test_no_privileged_drone_containers():
    payload = mod.manifest()
    for obj in payload["documents"]:
        if obj.get("kind") != "StatefulSet":
            continue
        c = obj["spec"]["template"]["spec"]["containers"][0]
        sc = c["securityContext"]
        assert sc["allowPrivilegeEscalation"] is False
        assert sc["readOnlyRootFilesystem"] is True
        assert sc["runAsNonRoot"] is True
        assert sc["capabilities"]["drop"] == ["ALL"]


def test_vendor_runtime_not_embedded_in_drone_contract():
    text = (ROOT / "tools" / "lion_k3s_pod_materializer.py").read_text(encoding="utf-8")
    assert "viktor.com" not in text
    assert "api.viktor.com" not in text
