#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import time
from datetime import datetime, timezone

EXPECTED_HOST = "LION-AUTH-LAB"
NAMESPACE = "vkt-r3"
STATE_ROOT = Path("/var/lib/lion-effect-admission/vkt-r3-k3s")
K3S_BIN = Path("/var/lib/lion-effect-admission/k3s/k3s")
KUBECONFIG = STATE_ROOT / "kubeconfig.yaml"
PID_FILE = STATE_ROOT / "k3s.pid"
LOG_FILE = STATE_ROOT / "k3s.log"
RECEIPT_ROOT = STATE_ROOT / "receipts"
EXPECTED_COUNTS = {"TIGER": 128, "SPECTRA": 128, "LION": 128}


def now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def digest(value: object) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def atomic_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(canonical(value) + b"\n")
    os.replace(tmp, path)


def run(argv: list[str], timeout: int = 60, capture: bool = True) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(
        argv,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE if capture else subprocess.DEVNULL,
        stderr=subprocess.PIPE if capture else subprocess.DEVNULL,
        text=True,
        timeout=timeout,
        check=False,
        shell=False,
        env={"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8"},
    )
    if proc.returncode != 0:
        raise RuntimeError(f"command failed rc={proc.returncode}: {argv[0]}: {(proc.stderr or proc.stdout)[-1200:]}")
    return proc


def require_host() -> None:
    actual = socket.gethostname()
    if actual.casefold() != EXPECTED_HOST.casefold():
        raise RuntimeError(f"HOST_IDENTITY_MISMATCH:{actual}")


def k3s_alive() -> bool:
    if not PID_FILE.is_file():
        return False
    try:
        pid = int(PID_FILE.read_text().strip())
        os.kill(pid, 0)
        return True
    except Exception:
        return False


def kubectl(args: list[str], timeout: int = 60) -> subprocess.CompletedProcess[str]:
    return run([str(K3S_BIN), "kubectl", "--kubeconfig", str(KUBECONFIG), *args], timeout=timeout)


def start_k3s() -> dict:
    require_host()
    STATE_ROOT.mkdir(parents=True, exist_ok=True)
    RECEIPT_ROOT.mkdir(parents=True, exist_ok=True)
    if not K3S_BIN.is_file():
        raise RuntimeError(f"K3S_BINARY_MISSING:{K3S_BIN}")
    if k3s_alive():
        return {"status": "ALREADY_RUNNING", "pid": int(PID_FILE.read_text())}

    log = LOG_FILE.open("ab", buffering=0)
    proc = subprocess.Popen(
        [
            str(K3S_BIN), "server",
            "--write-kubeconfig", str(KUBECONFIG),
            "--write-kubeconfig-mode", "600",
            "--data-dir", str(STATE_ROOT / "data"),
            "--disable", "traefik",
            "--disable", "servicelb",
            "--disable", "metrics-server",
            "--flannel-backend", "host-gw",
            "--node-name", "lion-auth-lab",
        ],
        stdin=subprocess.DEVNULL,
        stdout=log,
        stderr=log,
        start_new_session=True,
        env={"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "K3S_KUBECONFIG_MODE": "600"},
    )
    PID_FILE.write_text(str(proc.pid) + "\n")

    deadline = time.time() + 90
    last = ""
    while time.time() < deadline:
        if proc.poll() is not None:
            tail = LOG_FILE.read_text(errors="replace")[-4000:]
            raise RuntimeError(f"K3S_EXITED_EARLY:{proc.returncode}:{tail}")
        if KUBECONFIG.is_file():
            try:
                out = kubectl(["get", "nodes", "-o", "json"], timeout=10)
                data = json.loads(out.stdout)
                items = data.get("items", [])
                if items and any(
                    c.get("type") == "Ready" and c.get("status") == "True"
                    for c in items[0].get("status", {}).get("conditions", [])
                ):
                    receipt = {"sample_utc": now(), "status": "READY", "pid": proc.pid, "node_count": len(items)}
                    atomic_json(RECEIPT_ROOT / "k3s_start.json", receipt)
                    return receipt
                last = out.stdout[-1000:]
            except Exception as exc:
                last = str(exc)
        time.sleep(2)
    raise RuntimeError(f"K3S_NOT_READY:{last}")


def runtime_configmap() -> str:
    drone_py = r'''import json, os, socket, time, urllib.request\nfleet=os.environ['FLEET']; pod=os.environ.get('POD_NAME','?'); drone=pod.rsplit('-',1)[-1] if '-' in pod else pod\nwhile True:\n    body=json.dumps({'fleet':fleet,'drone_id':drone,'pod':pod,'t':time.time()}).encode()\n    try:\n        req=urllib.request.Request('http://vkt-fleet-router:8080/heartbeat',data=body,headers={'Content-Type':'application/json'})\n        urllib.request.urlopen(req,timeout=2).read()\n    except Exception:\n        pass\n    time.sleep(2)\n'''
    router_py = r'''from http.server import BaseHTTPRequestHandler,HTTPServer\nimport json,threading,time\nstate={}\nclass H(BaseHTTPRequestHandler):\n    def do_POST(self):\n        n=int(self.headers.get('Content-Length','0')); b=self.rfile.read(n)\n        try:\n            x=json.loads(b); state[(x.get('fleet'),x.get('drone_id'))]=x\n        except Exception: pass\n        self.send_response(204); self.end_headers()\n    def do_GET(self):\n        if self.path!='/state': self.send_response(404); self.end_headers(); return\n        b=json.dumps({'sample_utc':time.time(),'count':len(state),'items':list(state.values())}).encode()\n        self.send_response(200); self.send_header('Content-Type','application/json'); self.send_header('Content-Length',str(len(b))); self.end_headers(); self.wfile.write(b)\n    def log_message(self,*a): pass\nHTTPServer(('0.0.0.0',8080),H).serve_forever()\n'''
    # Raw literals make the embedded source readable in this generator, but
    # ConfigMap file data must contain real LF bytes, not backslash+n tokens.
    drone_py = drone_py.replace('\\n', '\n')
    router_py = router_py.replace('\\n', '\n')
    return json.dumps({"drone.py": drone_py, "router.py": router_py})


def manifest() -> dict:
    docs: list[dict] = []
    docs.append({
        "apiVersion": "v1", "kind": "Namespace", "metadata": {"name": NAMESPACE}
    })
    docs.append({
        "apiVersion": "v1", "kind": "ConfigMap", "metadata": {"name": "vkt-runtime", "namespace": NAMESPACE},
        "data": json.loads(runtime_configmap()),
    })
    docs.append({
        "apiVersion": "v1", "kind": "Service", "metadata": {"name": "vkt-fleet-router", "namespace": NAMESPACE},
        "spec": {"selector": {"app": "vkt-fleet-router"}, "ports": [{"port": 8080, "targetPort": 8080}]},
    })
    docs.append({
        "apiVersion": "apps/v1", "kind": "Deployment", "metadata": {"name": "vkt-fleet-router", "namespace": NAMESPACE},
        "spec": {
            "replicas": 1,
            "selector": {"matchLabels": {"app": "vkt-fleet-router"}},
            "template": {
                "metadata": {"labels": {"app": "vkt-fleet-router", "vkt-run": "vkt-r3", "component": "infra"}},
                "spec": {"containers": [{
                    "name": "router", "image": "python:3.12-alpine", "imagePullPolicy": "IfNotPresent",
                    "command": ["python", "/opt/vkt/router.py"],
                    "ports": [{"containerPort": 8080}],
                    "volumeMounts": [{"name": "runtime", "mountPath": "/opt/vkt"}],
                    "resources": {"requests": {"cpu": "5m", "memory": "12Mi"}, "limits": {"cpu": "100m", "memory": "64Mi"}},
                }], "volumes": [{"name": "runtime", "configMap": {"name": "vkt-runtime"}}]},
            },
        },
    })

    for fleet in ("TIGER", "SPECTRA", "LION"):
        name = fleet.lower() + "-drone"
        docs.append({
            "apiVersion": "apps/v1", "kind": "StatefulSet", "metadata": {"name": name, "namespace": NAMESPACE},
            "spec": {
                "serviceName": name,
                "replicas": 128,
                "podManagementPolicy": "Parallel",
                "selector": {"matchLabels": {"app": name}},
                "template": {
                    "metadata": {"labels": {"app": name, "vkt-run": "vkt-r3", "component": "drone", "fleet": fleet}},
                    "spec": {
                        "terminationGracePeriodSeconds": 5,
                        "containers": [{
                            "name": "drone", "image": "python:3.12-alpine", "imagePullPolicy": "IfNotPresent",
                            "command": ["/usr/local/bin/python3", "/opt/vkt/drone.py"],
                            "env": [
                                {"name": "FLEET", "value": fleet},
                                {"name": "POD_NAME", "valueFrom": {"fieldRef": {"fieldPath": "metadata.name"}}},
                            ],
                            "volumeMounts": [{"name": "runtime", "mountPath": "/opt/vkt"}],
                            "resources": {"requests": {"cpu": "1m", "memory": "8Mi"}, "limits": {"cpu": "50m", "memory": "32Mi"}},
                            "securityContext": {"allowPrivilegeEscalation": False, "readOnlyRootFilesystem": True, "runAsNonRoot": True, "runAsUser": 65532, "capabilities": {"drop": ["ALL"]}},
                        }],
                        "volumes": [{"name": "runtime", "configMap": {"name": "vkt-runtime"}}],
                    },
                },
            },
        })
    return {"apiVersion": "vkt.lpcl/v1", "kind": "VktPodMaterialization", "documents": docs}


def apply_manifest() -> dict:
    if not k3s_alive():
        start_k3s()
    payload = manifest()
    tmp = STATE_ROOT / "vkt-r3.json"
    tmp.write_text("\n---\n".join(json.dumps(d) for d in payload["documents"]))
    run([str(K3S_BIN), "kubectl", "--kubeconfig", str(KUBECONFIG), "apply", "-f", str(tmp)], timeout=120)
    receipt = {"sample_utc": now(), "status": "APPLIED", "namespace": NAMESPACE, "expected_pods": 384, "manifest_sha256": digest(payload)}
    atomic_json(RECEIPT_ROOT / "apply.json", receipt)
    return receipt


def status() -> dict:
    if not k3s_alive():
        return {"sample_utc": now(), "status": "K3S_NOT_RUNNING", "materialized": 0, "ready": 0}
    out = kubectl(["get", "pods", "-n", NAMESPACE, "-o", "json"], timeout=30)
    data = json.loads(out.stdout)
    rows = []
    counts = {k: {"materialized": 0, "ready": 0, "restarts": 0} for k in EXPECTED_COUNTS}
    for item in data.get("items", []):
        labels = item.get("metadata", {}).get("labels", {}) or {}
        fleet = str(labels.get("fleet", "")).upper()
        if labels.get("component") != "drone" or fleet not in counts:
            continue
        conds = item.get("status", {}).get("conditions", []) or []
        ready = any(c.get("type") == "Ready" and c.get("status") == "True" for c in conds)
        restarts = sum(int(c.get("restartCount", 0) or 0) for c in item.get("status", {}).get("containerStatuses", []) or [])
        counts[fleet]["materialized"] += 1
        counts[fleet]["ready"] += 1 if ready else 0
        counts[fleet]["restarts"] += restarts
        rows.append({
            "fleet": fleet,
            "name": item.get("metadata", {}).get("name"),
            "uid": item.get("metadata", {}).get("uid"),
            "pod_ip": item.get("status", {}).get("podIP"),
            "phase": item.get("status", {}).get("phase"),
            "ready": ready,
            "restarts": restarts,
        })
    result = {
        "sample_utc": now(), "status": "MATERIALIZED" if len(rows) == 384 else "PARTIAL",
        "materialized": len(rows), "ready": sum(1 for r in rows if r["ready"]), "by_fleet": counts,
        "pod_uid_set_sha256": hashlib.sha256("\n".join(sorted(r["uid"] or "" for r in rows)).encode()).hexdigest(),
        "pods": rows,
    }
    atomic_json(RECEIPT_ROOT / "status.json", result)
    return result


def stop() -> dict:
    require_host()
    if k3s_alive():
        try:
            kubectl(["delete", "namespace", NAMESPACE, "--wait=false"], timeout=30)
        except Exception:
            pass
        try:
            pid = int(PID_FILE.read_text().strip())
            os.kill(pid, 15)
        except Exception:
            pass
    result = {"sample_utc": now(), "status": "STOP_REQUESTED", "namespace": NAMESPACE}
    atomic_json(RECEIPT_ROOT / "stop.json", result)
    return result


def precheck() -> dict:
    require_host()
    return {
        "sample_utc": now(), "host": socket.gethostname(), "k3s_binary": str(K3S_BIN),
        "k3s_binary_exists": K3S_BIN.is_file(), "k3s_running": k3s_alive(),
        "namespace": NAMESPACE, "expected_pods": 384, "counts": EXPECTED_COUNTS,
        "direct_vendor_testing": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["precheck", "start-k3s", "apply", "status", "stop"])
    args = parser.parse_args()
    fn = {"precheck": precheck, "start-k3s": start_k3s, "apply": apply_manifest, "status": status, "stop": stop}[args.command]
    try:
        print(json.dumps({"ok": True, "result": fn()}, sort_keys=True))
        return 0
    except Exception as exc:
        print(json.dumps({"ok": False, "error": type(exc).__name__, "message": str(exc)}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
