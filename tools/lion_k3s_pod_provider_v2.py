#!/usr/bin/env python3
from __future__ import annotations

import copy
import importlib.util
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
CORE_PATH = HERE / "lion_k3s_pod_provider.py"
MATERIALIZER_PATH = HERE / "lion_k3s_pod_materializer.py"
RUNTIME_IMAGE = "python@sha256:782412e85d0f0984994c290652577d4018aff08145c85b262bb63dc0c7522254"
DRONE_COMMAND = ["/usr/local/bin/python3", "/opt/vkt/drone.py"]
ROUTER_COMMAND = ["/usr/local/bin/python3", "/opt/vkt/router.py"]
DRONE_UID = 1000


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"module-load-failed:{path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def transformed_manifest() -> dict[str, Any]:
    core = _load("lion_k3s_pod_provider_core_v2_view", CORE_PATH)
    materializer = _load("lion_k3s_pod_materializer_v2_view", MATERIALIZER_PATH)
    payload = copy.deepcopy(materializer.manifest())
    for doc in payload.get("documents", []):
        if doc.get("kind") not in {"Deployment", "StatefulSet"}:
            continue
        meta = doc.get("spec", {}).get("template", {}).get("metadata", {}) or {}
        pod_spec = doc.get("spec", {}).get("template", {}).get("spec", {}) or {}
        for container in pod_spec.get("containers", []) or []:
            container["image"] = RUNTIME_IMAGE
            if meta.get("labels", {}).get("component") == "drone":
                container["command"] = list(DRONE_COMMAND)
                sc = container.setdefault("securityContext", {})
                sc["runAsNonRoot"] = True
                sc["runAsUser"] = DRONE_UID
                sc["allowPrivilegeEscalation"] = False
                sc["readOnlyRootFilesystem"] = True
                sc["capabilities"] = {"drop": ["ALL"]}
            elif container.get("name") == "router":
                container["command"] = list(ROUTER_COMMAND)
    core.ALLOWED_IMAGES = {RUNTIME_IMAGE}
    core.validate_manifest_payload(payload)
    return payload


def _stuck_zero_restart_names(evidence: dict[str, Any]) -> list[str]:
    names: list[str] = []
    for pod in evidence.get("pods", []) or []:
        if pod.get("ready") is True or int(pod.get("restarts", 0) or 0) != 0:
            continue
        states = pod.get("container_states", []) or []
        if not any(s.get("waiting_reason") == "ContainerCreating" for s in states):
            continue
        name = str(pod.get("name") or "")
        parts = name.rsplit("-", 1)
        if len(parts) != 2 or parts[0] not in {"tiger-drone", "spectra-drone", "lion-drone"} or not parts[1].isdigit():
            raise RuntimeError("stuck-recycle-name-denied:" + name)
        names.append(name)
    names = sorted(set(names))
    if len(names) > 16:
        raise RuntimeError(f"stuck-recycle-cardinality-exceeded:{len(names)}")
    return names


def install_into_core(core) -> None:
    core.ALLOWED_IMAGES = {RUNTIME_IMAGE}
    original_materialize = core.materialize
    original_pod_evidence = core.pod_evidence

    def pod_evidence_v2():
        result = original_pod_evidence()
        try:
            import json as _json
            nodes = _json.loads(core.kubectl(["get", "nodes", "-o", "json"], timeout=30).stdout)
            items = nodes.get("items", []) or []
            result["node_evidence"] = [{
                "name": (n.get("metadata") or {}).get("name"),
                "podCIDR": (n.get("spec") or {}).get("podCIDR"),
                "podCIDRs": (n.get("spec") or {}).get("podCIDRs") or [],
                "capacity": (n.get("status") or {}).get("capacity") or {},
                "allocatable": (n.get("status") or {}).get("allocatable") or {},
                "conditions": [{"type": c.get("type"), "status": c.get("status"), "reason": c.get("reason"), "message": c.get("message")} for c in ((n.get("status") or {}).get("conditions") or [])],
            } for n in items]
        except Exception as exc:
            result["node_evidence_error"] = str(exc)[:500]
        return result

    def load_manifest_v2():
        payload = transformed_manifest()
        return payload, core.validate_manifest_payload(payload)

    def materialize_v2():
        recycled: list[str] = []
        try:
            evidence = core.pod_evidence()
            recycled = _stuck_zero_restart_names(evidence)
        except Exception as exc:
            text = str(exc).lower()
            if "notfound" not in text and "not found" not in text:
                raise
        for name in recycled:
            core.kubectl(["delete", "pod", "-n", core.NAMESPACE, name, "--wait=false"], timeout=30)
        result = original_materialize()
        # ConfigMap content changes do not themselves restart the Deployment.
        # Recycle only the single fixed router Pod so it remounts the exact runtime payload.
        router_recycled = []
        try:
            import json as _json
            data = _json.loads(core.kubectl(["get", "pods", "-n", core.NAMESPACE, "-l", "app=vkt-fleet-router", "-o", "json"], timeout=30).stdout)
            names = sorted(str((x.get("metadata") or {}).get("name") or "") for x in (data.get("items") or []))
            names = [n for n in names if n.startswith("vkt-fleet-router-")]
            if len(names) > 1:
                raise RuntimeError(f"router-recycle-cardinality:{len(names)}")
            for name in names:
                core.kubectl(["delete", "pod", "-n", core.NAMESPACE, name, "--wait=false"], timeout=30)
                router_recycled.append(name)
        except Exception as exc:
            text = str(exc).lower()
            if "notfound" not in text and "not found" not in text:
                raise
        result["recycled_stuck_zero_restart"] = recycled
        result["recycled_count"] = len(recycled)
        result["router_recycled"] = router_recycled
        return result

    def stop_v2():
        if not core.service_active() or not core.KUBECONFIG.is_file():
            return {"status": "ALREADY_STOPPED", "namespace": core.NAMESPACE}
        core.kubectl(["delete", "namespace", core.NAMESPACE, "--ignore-not-found=true", "--wait=true", "--timeout=90s"], timeout=100)
        return {"status": "STOPPED", "namespace": core.NAMESPACE}

    core.load_manifest = load_manifest_v2
    core.pod_evidence = pod_evidence_v2
    core.materialize = materialize_v2
    core.stop_vkt_pods = stop_v2


def main() -> int:
    core = _load("lion_k3s_pod_provider_core_v2_runtime", CORE_PATH)
    install_into_core(core)
    return core.main()


if __name__ == "__main__":
    raise SystemExit(main())
