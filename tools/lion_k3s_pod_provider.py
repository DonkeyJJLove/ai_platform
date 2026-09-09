#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import pwd
import re
import socket
import struct
import subprocess
import sys
import time
from datetime import datetime, timezone
from typing import Any

SCHEMA = "1.0.0"
PROJECT = "LION_EVOLUSION"
MISSION_ID = "VKT-R3-384-REAL-POD-MISSION-CONTROL-R2"
TRUST_CLASS = "TEST_ONLY"
EXPECTED_HOST = "LION-AUTH-LAB"
RUNNER_USER = "lion-maintenance-runner"
NAMESPACE = "vkt-r3"
K3S_UNIT = "lion-k3s-vkt-r3.service"
K3S_BIN = Path("/opt/lion/k3s/k3s")
K3S_VERSION = "v1.36.4+k3s1"
K3S_SHA256 = "835873f37245fc615f547a2fe2af9402a347875f13fa64a1f136de644955ea3f"
KUBECONFIG = Path("/var/lib/lion-effect-admission/vkt-r3-k3s/kubeconfig.yaml")
K3S_DATA_DIR = Path("/var/lib/lion-effect-admission/vkt-r3-k3s/data")
STATE_ROOT = Path("/var/lib/lion/k3s-vkt-r3")
RECEIPT_ROOT = STATE_ROOT / "receipts"
FIXED_REPO = Path("/opt/lion/k3s-vkt-r3/repo")
SOURCE_IDENTITY = Path("/opt/lion/k3s-vkt-r3/source-identity.json")
MANIFEST_PATH = STATE_ROOT / "manifest.json"
MAX_REQUEST = 64 * 1024
MAX_RESPONSE = 8 * 1024 * 1024
SHA40 = re.compile(r"^[0-9a-f]{40}$")
SHA64 = re.compile(r"^[0-9a-f]{64}$")
SAFE_RUN_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
EXPECTED_COUNTS = {"TIGER": 128, "SPECTRA": 128, "LION": 128}
ALLOWED_OPERATIONS = {
    "PRECHECK_POD_RUNTIME",
    "PREPARE_LOCAL_K8S",
    "MATERIALIZE_VKT_PODS",
    "READ_POD_EVIDENCE",
    "STOP_VKT_PODS",
}
ALLOWED_IMAGES = {"python:3.12-alpine"}
ALLOWED_KINDS = {
    "Namespace",
    "ConfigMap",
    "Service",
    "Deployment",
    "StatefulSet",
    "NetworkPolicy",
    "ServiceAccount",
    "Role",
    "RoleBinding",
}


class Deny(RuntimeError):
    pass


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def require_sha40(value: Any, label: str) -> str:
    if not isinstance(value, str) or not SHA40.fullmatch(value):
        raise Deny(f"{label}:invalid")
    return value


def require_sha64(value: Any, label: str) -> str:
    if not isinstance(value, str) or not SHA64.fullmatch(value):
        raise Deny(f"{label}:invalid")
    return value


def require_run_id(value: Any) -> str:
    if not isinstance(value, str) or not SAFE_RUN_ID.fullmatch(value):
        raise Deny("run_id:invalid")
    return value


def atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp-" + sha256(os.urandom(16))[:12])
    tmp.write_bytes(canonical(value) + b"\n")
    os.chmod(tmp, 0o600)
    os.replace(tmp, path)


def run(argv: list[str], *, timeout: int = 120) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(
        argv,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        shell=False,
        timeout=timeout,
        check=False,
        env={"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8", "K3S_DATA_DIR": str(K3S_DATA_DIR)},
    )
    if proc.returncode != 0:
        raise Deny(f"command-failed:{os.path.basename(argv[0])}:rc={proc.returncode}:{(proc.stderr or proc.stdout)[-2000:]}")
    return proc


def peer_uid() -> int:
    sock = socket.fromfd(0, socket.AF_UNIX, socket.SOCK_STREAM)
    raw = sock.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i"))
    sock.close()
    return struct.unpack("3i", raw)[1]


def receive() -> dict[str, Any]:
    raw = sys.stdin.buffer.readline(MAX_REQUEST + 1)
    if len(raw) > MAX_REQUEST:
        raise Deny("request-too-large")
    try:
        value = json.loads(raw.decode("utf-8"))
    except Exception as exc:
        raise Deny("invalid-json") from exc
    if not isinstance(value, dict):
        raise Deny("request-not-object")
    return value


def reply(value: dict[str, Any]) -> None:
    raw = canonical(value) + b"\n"
    if len(raw) > MAX_RESPONSE:
        raw = canonical({"ok": False, "error": "response-too-large"}) + b"\n"
    sys.stdout.buffer.write(raw)
    sys.stdout.buffer.flush()


def source_identity(head: str, tree: str) -> dict[str, Any]:
    if not SOURCE_IDENTITY.is_file() or not FIXED_REPO.is_dir():
        raise Deny("fixed-source-missing")
    value = json.loads(SOURCE_IDENTITY.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise Deny("source-identity-not-object")
    if value.get("repository") != "DonkeyJJLove/ai_platform":
        raise Deny("source-repository-mismatch")
    if value.get("source_head") != head or value.get("source_tree") != tree:
        raise Deny("source-identity-mismatch")
    if value.get("trust_class") != TRUST_CLASS:
        raise Deny("source-trust-mismatch")
    return value


def k3s_binary_state() -> dict[str, Any]:
    exists = K3S_BIN.is_file()
    digest = sha256_file(K3S_BIN) if exists else None
    if exists and digest != K3S_SHA256:
        raise Deny("k3s-sha256-mismatch")
    return {
        "path": str(K3S_BIN),
        "exists": exists,
        "sha256": digest,
        "expected_sha256": K3S_SHA256,
        "expected_version": K3S_VERSION,
    }


def service_active() -> bool:
    proc = subprocess.run(
        ["/bin/systemctl", "is-active", "--quiet", K3S_UNIT],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return proc.returncode == 0


def kubectl(args: list[str], *, timeout: int = 60) -> subprocess.CompletedProcess[str]:
    if not K3S_BIN.is_file():
        raise Deny("k3s-binary-missing")
    if not KUBECONFIG.is_file():
        raise Deny("kubeconfig-missing")
    return run([str(K3S_BIN), "kubectl", "--kubeconfig", str(KUBECONFIG), *args], timeout=timeout)


def _pod_specs(document: dict[str, Any]) -> list[dict[str, Any]]:
    kind = document.get("kind")
    if kind in {"Deployment", "StatefulSet"}:
        spec = document.get("spec", {})
        return [spec.get("template", {}).get("spec", {})]
    return []


def validate_manifest_payload(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict) or payload.get("kind") != "VktPodMaterialization":
        raise Deny("manifest-envelope-invalid")
    docs = payload.get("documents")
    if not isinstance(docs, list) or not docs:
        raise Deny("manifest-documents-invalid")
    sets: dict[str, dict[str, Any]] = {}
    namespace_seen = False
    for doc in docs:
        if not isinstance(doc, dict):
            raise Deny("manifest-document-not-object")
        kind = doc.get("kind")
        if kind not in ALLOWED_KINDS:
            raise Deny(f"manifest-kind-denied:{kind}")
        meta = doc.get("metadata", {}) or {}
        if kind == "Namespace":
            if meta.get("name") != NAMESPACE:
                raise Deny("namespace-mismatch")
            namespace_seen = True
        elif meta.get("namespace") != NAMESPACE:
            raise Deny("resource-outside-fixed-namespace")
        for pod_spec in _pod_specs(doc):
            for forbidden in ("hostNetwork", "hostPID", "hostIPC"):
                if pod_spec.get(forbidden) is True:
                    raise Deny(f"pod-{forbidden}-denied")
            for volume in pod_spec.get("volumes", []) or []:
                if "hostPath" in volume:
                    raise Deny("hostPath-denied")
            containers = pod_spec.get("containers", []) or []
            if not containers:
                raise Deny("pod-container-missing")
            for container in containers:
                image = container.get("image")
                if image not in ALLOWED_IMAGES:
                    raise Deny(f"image-denied:{image}")
                security = container.get("securityContext", {}) or {}
                if security.get("privileged") is True:
                    raise Deny("privileged-container-denied")
                if meta.get("labels", {}).get("component") == "drone":
                    if security.get("allowPrivilegeEscalation") is not False:
                        raise Deny("drone-privilege-escalation-not-disabled")
                    if security.get("runAsNonRoot") is not True:
                        raise Deny("drone-must-run-as-non-root")
                    if security.get("readOnlyRootFilesystem") is not True:
                        raise Deny("drone-rootfs-must-be-readonly")
                    if (security.get("capabilities", {}) or {}).get("drop") != ["ALL"]:
                        raise Deny("drone-capabilities-must-drop-all")
        if kind == "StatefulSet":
            sets[str(meta.get("name"))] = doc
    if not namespace_seen:
        raise Deny("namespace-document-missing")
    expected_names = {"tiger-drone": "TIGER", "spectra-drone": "SPECTRA", "lion-drone": "LION"}
    if set(sets) != set(expected_names):
        raise Deny("statefulset-cardinality-or-name-mismatch")
    for name, fleet in expected_names.items():
        doc = sets[name]
        if doc.get("spec", {}).get("replicas") != 128:
            raise Deny(f"fleet-replicas-invalid:{fleet}")
        labels = doc.get("spec", {}).get("template", {}).get("metadata", {}).get("labels", {}) or {}
        if labels.get("component") != "drone" or labels.get("fleet") != fleet:
            raise Deny(f"fleet-label-invalid:{fleet}")
    return {"namespace": NAMESPACE, "fleet_counts": EXPECTED_COUNTS, "drone_pods": 384, "documents": len(docs)}


def load_manifest() -> tuple[dict[str, Any], dict[str, Any]]:
    path = FIXED_REPO / "tools" / "lion_k3s_pod_materializer.py"
    if not path.is_file():
        raise Deny("materializer-missing")
    spec = importlib.util.spec_from_file_location("lion_vkt_fixed_materializer", path)
    if spec is None or spec.loader is None:
        raise Deny("materializer-import-failed")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    payload = module.manifest()
    contract = validate_manifest_payload(payload)
    return payload, contract


def pod_evidence() -> dict[str, Any]:
    if not service_active():
        return {"status": "K3S_NOT_RUNNING", "materialized": 0, "ready": 0, "by_fleet": {f: {"materialized": 0, "ready": 0, "restarts": 0} for f in EXPECTED_COUNTS}, "pods": []}
    out = kubectl(["get", "pods", "-n", NAMESPACE, "-o", "json"], timeout=30)
    data = json.loads(out.stdout)
    rows: list[dict[str, Any]] = []
    counts = {f: {"materialized": 0, "ready": 0, "restarts": 0} for f in EXPECTED_COUNTS}
    infra: list[dict[str, Any]] = []
    for item in data.get("items", []):
        meta = item.get("metadata", {}) or {}
        status = item.get("status", {}) or {}
        labels = meta.get("labels", {}) or {}
        conds = status.get("conditions", []) or []
        ready = any(c.get("type") == "Ready" and c.get("status") == "True" for c in conds)
        restarts = sum(int(c.get("restartCount", 0) or 0) for c in status.get("containerStatuses", []) or [])
        states = []
        for cs in status.get("containerStatuses", []) or []:
            state = cs.get("state", {}) or {}
            waiting = state.get("waiting") or {}
            terminated = state.get("terminated") or {}
            states.append({
                "name": cs.get("name"),
                "ready": bool(cs.get("ready")),
                "restart_count": int(cs.get("restartCount", 0) or 0),
                "waiting_reason": waiting.get("reason"),
                "waiting_message": waiting.get("message"),
                "terminated_reason": terminated.get("reason"),
                "terminated_message": terminated.get("message"),
                "terminated_exit_code": terminated.get("exitCode"),
            })
        common = {"name": meta.get("name"), "uid": meta.get("uid"), "pod_ip": status.get("podIP"), "phase": status.get("phase"), "ready": ready, "restarts": restarts, "container_states": states}
        fleet = str(labels.get("fleet", "")).upper()
        if labels.get("component") == "drone" and fleet in counts:
            row = {"fleet": fleet, **common}
            rows.append(row)
            counts[fleet]["materialized"] += 1
            counts[fleet]["ready"] += 1 if ready else 0
            counts[fleet]["restarts"] += restarts
        else:
            infra.append({"component": labels.get("component"), **common})
    uid_values = sorted(str(r.get("uid") or "") for r in rows)
    events = []
    try:
        ev = json.loads(kubectl(["get", "events", "-n", NAMESPACE, "-o", "json"], timeout=30).stdout)
        for item in (ev.get("items", []) or [])[-100:]:
            events.append({
                "type": item.get("type"),
                "reason": item.get("reason"),
                "message": item.get("message"),
                "object": (item.get("involvedObject") or {}).get("name"),
                "count": item.get("count"),
            })
    except Exception:
        events = []
    return {
        "status": "MATERIALIZED" if len(rows) == 384 else "PARTIAL",
        "materialized": len(rows),
        "ready": sum(1 for r in rows if r["ready"]),
        "by_fleet": counts,
        "pod_uid_set_sha256": sha256("\n".join(uid_values).encode("utf-8")),
        "unique_uid_count": len({u for u in uid_values if u}),
        "restart_count_total": sum(v["restarts"] for v in counts.values()),
        "pods": rows,
        "infrastructure": infra,
        "events": events,
        "vendor_requests": 0,
    }


def precheck() -> dict[str, Any]:
    binary = k3s_binary_state()
    evidence = pod_evidence() if service_active() and KUBECONFIG.is_file() else None
    return {"status": "READY" if binary["exists"] else "K3S_BINARY_MISSING", "host": socket.gethostname(), "namespace": NAMESPACE, "k3s": binary, "k3s_service_active": service_active(), "kubeconfig_exists": KUBECONFIG.is_file(), "evidence": evidence, "direct_vendor_testing": False, "vendor_requests": 0}


def prepare_local_k8s() -> dict[str, Any]:
    binary = k3s_binary_state()
    if not binary["exists"]:
        raise Deny("k3s-binary-missing")
    run(["/bin/systemctl", "start", K3S_UNIT], timeout=30)
    deadline = time.time() + 120
    last = ""
    while time.time() < deadline:
        if KUBECONFIG.is_file():
            try:
                out = kubectl(["get", "nodes", "-o", "json"], timeout=10)
                data = json.loads(out.stdout)
                items = data.get("items", [])
                if items and any(c.get("type") == "Ready" and c.get("status") == "True" for c in items[0].get("status", {}).get("conditions", []) or []):
                    return {"status": "READY", "node_count": len(items), "k3s": binary}
                last = out.stdout[-1000:]
            except Exception as exc:
                last = str(exc)
        time.sleep(2)
    raise Deny("k3s-not-ready:" + last[-1000:])


def materialize() -> dict[str, Any]:
    if not service_active():
        raise Deny("k3s-service-not-active")
    payload, contract = load_manifest()
    STATE_ROOT.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text("\n---\n".join(json.dumps(d, sort_keys=True) for d in payload["documents"]), encoding="utf-8")
    os.chmod(MANIFEST_PATH, 0o600)
    kubectl(["apply", "-f", str(MANIFEST_PATH)], timeout=180)
    return {"status": "APPLIED", "manifest_sha256": sha256(canonical(payload)), "contract": contract}


def stop_vkt_pods() -> dict[str, Any]:
    if not service_active() or not KUBECONFIG.is_file():
        return {"status": "ALREADY_STOPPED", "namespace": NAMESPACE}
    proc = subprocess.run([str(K3S_BIN), "kubectl", "--kubeconfig", str(KUBECONFIG), "delete", "namespace", NAMESPACE, "--ignore-not-found=true", "--wait=true", "--timeout=90s"], stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, shell=False, timeout=100, check=False, env={"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8"})
    if proc.returncode != 0:
        raise Deny("namespace-cleanup-failed:" + (proc.stderr or proc.stdout)[-1200:])
    return {"status": "STOPPED", "namespace": NAMESPACE}


def write_receipt(req: dict[str, Any], status: str, result: Any) -> dict[str, Any]:
    run_id = req["run_id"]
    receipt = {"schema_version": SCHEMA, "timestamp": now(), "project": PROJECT, "mission_id": MISSION_ID, "run_id": run_id, "request_id": req["request_id"], "source_head": req["source_head"], "source_tree": req["source_tree"], "operation": req["operation"], "status": status, "result_digest": sha256(canonical(result)), "vendor_requests": 0}
    path = RECEIPT_ROOT / run_id / f"{req['request_id']}.json"
    if path.exists():
        raise Deny("request-replay")
    atomic_json(path, receipt)
    return {"receipt_path": str(path), "receipt_sha256": sha256_file(path)}


def validate_request(req: dict[str, Any]) -> tuple[str, str, str]:
    expected = {"schema_version", "request_id", "operation", "mission_id", "run_id", "source_head", "source_tree"}
    if set(req) != expected:
        raise Deny("request-field-set")
    if req.get("schema_version") != SCHEMA:
        raise Deny("schema-mismatch")
    require_sha64(req.get("request_id"), "request_id")
    operation = req.get("operation")
    if operation not in ALLOWED_OPERATIONS:
        raise Deny("operation-not-allowlisted")
    if req.get("mission_id") != MISSION_ID:
        raise Deny("mission-id-mismatch")
    require_run_id(req.get("run_id"))
    head = require_sha40(req.get("source_head"), "source_head")
    tree = require_sha40(req.get("source_tree"), "source_tree")
    return operation, head, tree


def handle(req: dict[str, Any]) -> dict[str, Any]:
    if os.geteuid() != 0:
        raise Deny("provider-not-root")
    if socket.gethostname() != EXPECTED_HOST:
        raise Deny("wrong-host")
    expected_uid = pwd.getpwnam(RUNNER_USER).pw_uid
    if peer_uid() != expected_uid:
        raise Deny("caller-uid-denied")
    operation, head, tree = validate_request(req)
    source_identity(head, tree)
    receipt_path = RECEIPT_ROOT / req["run_id"] / f"{req['request_id']}.json"
    if receipt_path.exists():
        raise Deny("request-replay")
    if operation == "PRECHECK_POD_RUNTIME":
        result = precheck()
    elif operation == "PREPARE_LOCAL_K8S":
        result = prepare_local_k8s()
    elif operation == "MATERIALIZE_VKT_PODS":
        result = materialize()
    elif operation == "READ_POD_EVIDENCE":
        result = pod_evidence()
    elif operation == "STOP_VKT_PODS":
        result = stop_vkt_pods()
    else:
        raise Deny("operation-unreachable")
    evidence = write_receipt(req, "PASS", result)
    return {**result, **evidence}


def main() -> int:
    request_id = None
    try:
        req = receive()
        if isinstance(req.get("request_id"), str):
            request_id = req["request_id"]
        result = handle(req)
        reply({"ok": True, "request_id": request_id, "result": result})
        return 0
    except Exception as exc:
        reply({"ok": False, "request_id": request_id, "error": type(exc).__name__ + ":" + str(exc)[:3000]})
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
