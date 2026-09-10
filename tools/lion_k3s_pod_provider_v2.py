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


def install_into_core(core) -> None:
    core.ALLOWED_IMAGES = {RUNTIME_IMAGE}

    def load_manifest_v2():
        payload = transformed_manifest()
        return payload, core.validate_manifest_payload(payload)

    core.load_manifest = load_manifest_v2


def main() -> int:
    core = _load("lion_k3s_pod_provider_core_v2_runtime", CORE_PATH)
    install_into_core(core)
    return core.main()


if __name__ == "__main__":
    raise SystemExit(main())
