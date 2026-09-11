#!/usr/bin/env python3
from __future__ import annotations

import errno
import importlib.util
import json
import re
import subprocess
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
V3_PATH = HERE / "lion_k3s_pod_provider_v3.py"

OSS_OPERATIONS = {
    "START_OSS_REPO_TEST",
    "READ_OSS_REPO_TEST_EVIDENCE",
    "STOP_OSS_REPO_TEST",
}
OSS_TEST_NAMESPACE = "oss-test-itsdangerous"
OSS_TEST_JOB = "itsdangerous-pytest"
OSS_TEST_REPOSITORY = "https://github.com/pallets/itsdangerous.git"
OSS_TEST_COMMIT = "672971d66a2ef9f85151e53283113f33d642dabd"
OSS_GIT_IMAGE = "alpine/git@sha256:53a6239398162098fed2f49a46512f9cbba9e3f31b9f2cea4fa90129ee069a99"
OSS_PYTHON_IMAGE = "python@sha256:782412e85d0f0984994c290652577d4018aff08145c85b262bb63dc0c7522254"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError("module-load-failed:" + str(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


v3 = _load("lion_k3s_pod_provider_v3_overlay", V3_PATH)
_original_install = v3.v2.install_into_core


def _kubectl_optional(core, args: list[str], timeout: int = 60) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(core.K3S_BIN), "kubectl", "--kubeconfig", str(core.KUBECONFIG), *args],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        shell=False,
        timeout=timeout,
        check=False,
        env={
            "PATH": "/usr/sbin:/usr/bin:/sbin:/bin",
            "LANG": "C.UTF-8",
            "LC_ALL": "C.UTF-8",
            "K3S_DATA_DIR": str(core.K3S_DATA_DIR),
        },
    )


def _namespace_probe(core) -> subprocess.CompletedProcess[str]:
    return _kubectl_optional(core, ["get", "namespace", OSS_TEST_NAMESPACE, "-o", "name"], 20)


def _security() -> dict[str, Any]:
    return {
        "runAsNonRoot": True,
        "runAsUser": 1000,
        "allowPrivilegeEscalation": False,
        "readOnlyRootFilesystem": True,
        "capabilities": {"drop": ["ALL"]},
    }


def oss_test_manifest() -> dict[str, Any]:
    clone_script = f"""set -eu
rm -rf /work/repo
git clone --no-tags {OSS_TEST_REPOSITORY} /work/repo
cd /work/repo
git checkout --detach {OSS_TEST_COMMIT}
HEAD=\"$(git rev-parse HEAD)\"
test \"$HEAD\" = \"{OSS_TEST_COMMIT}\"
printf '%s\\n' \"$HEAD\" > /work/source-commit
printf 'CLONED_HEAD=%s\\n' \"$HEAD\"
"""
    test_script = f"""set -eu
EXPECTED=\"{OSS_TEST_COMMIT}\"
ACTUAL=\"$(cat /work/source-commit)\"
test \"$ACTUAL\" = \"$EXPECTED\"
python -m pip install --disable-pip-version-check --no-cache-dir --target /work/site /work/repo pytest freezegun
export PYTHONPATH=/work/site
python -m pytest -q --tb=short /work/repo/tests
"""
    sec = _security()
    return {
        "apiVersion": "v1",
        "kind": "List",
        "items": [
            {
                "apiVersion": "v1",
                "kind": "Namespace",
                "metadata": {
                    "name": OSS_TEST_NAMESPACE,
                    "labels": {"lion.openai/test-class": "oss-repo-test", "lion.openai/trust": "TEST_ONLY"},
                },
            },
            {
                "apiVersion": "networking.k8s.io/v1",
                "kind": "NetworkPolicy",
                "metadata": {"name": "oss-test-egress", "namespace": OSS_TEST_NAMESPACE},
                "spec": {
                    "podSelector": {},
                    "policyTypes": ["Ingress", "Egress"],
                    "ingress": [],
                    "egress": [
                        {
                            "to": [{"ipBlock": {"cidr": "10.43.0.0/16"}}],
                            "ports": [{"protocol": "UDP", "port": 53}, {"protocol": "TCP", "port": 53}],
                        },
                        {
                            "to": [{"ipBlock": {"cidr": "10.42.0.0/16"}}],
                            "ports": [{"protocol": "UDP", "port": 53}, {"protocol": "TCP", "port": 53}],
                        },
                        {
                            "to": [{"ipBlock": {"cidr": "0.0.0.0/0"}}],
                            "ports": [{"protocol": "TCP", "port": 443}],
                        },
                    ],
                },
            },
            {
                "apiVersion": "batch/v1",
                "kind": "Job",
                "metadata": {
                    "name": OSS_TEST_JOB,
                    "namespace": OSS_TEST_NAMESPACE,
                    "labels": {"lion.openai/test-class": "oss-repo-test"},
                },
                "spec": {
                    "backoffLimit": 0,
                    "activeDeadlineSeconds": 600,
                    "ttlSecondsAfterFinished": 3600,
                    "template": {
                        "metadata": {
                            "labels": {"job-name": OSS_TEST_JOB, "lion.openai/test-class": "oss-repo-test"}
                        },
                        "spec": {
                            "automountServiceAccountToken": False,
                            "restartPolicy": "Never",
                            "securityContext": {
                                "runAsNonRoot": True,
                                "runAsUser": 1000,
                                "runAsGroup": 1000,
                                "fsGroup": 1000,
                                "seccompProfile": {"type": "RuntimeDefault"},
                            },
                            "initContainers": [
                                {
                                    "name": "git-clone",
                                    "image": OSS_GIT_IMAGE,
                                    "imagePullPolicy": "IfNotPresent",
                                    "command": ["/bin/sh", "-ec"],
                                    "args": [clone_script],
                                    "env": [{"name": "HOME", "value": "/tmp"}],
                                    "securityContext": dict(sec),
                                    "volumeMounts": [
                                        {"name": "work", "mountPath": "/work"},
                                        {"name": "tmp", "mountPath": "/tmp"},
                                    ],
                                }
                            ],
                            "containers": [
                                {
                                    "name": "pytest",
                                    "image": OSS_PYTHON_IMAGE,
                                    "imagePullPolicy": "IfNotPresent",
                                    "command": ["/bin/sh", "-ec"],
                                    "args": [test_script],
                                    "env": [
                                        {"name": "HOME", "value": "/tmp"},
                                        {"name": "TMPDIR", "value": "/tmp"},
                                        {"name": "PIP_CACHE_DIR", "value": "/tmp/pip"},
                                    ],
                                    "securityContext": dict(sec),
                                    "volumeMounts": [
                                        {"name": "work", "mountPath": "/work"},
                                        {"name": "tmp", "mountPath": "/tmp"},
                                    ],
                                }
                            ],
                            "volumes": [{"name": "work", "emptyDir": {}}, {"name": "tmp", "emptyDir": {}}],
                        },
                    },
                },
            },
        ],
    }


def _log_tail(core, pod: str, container: str, limit: int = 256 * 1024) -> str:
    proc = _kubectl_optional(core, ["logs", "-n", OSS_TEST_NAMESPACE, pod, "-c", container, "--tail=2000"], 30)
    raw = ((proc.stdout or "") + (proc.stderr or "")).encode("utf-8", "replace")
    if len(raw) > limit:
        raw = raw[-limit:]
    return raw.decode("utf-8", "replace")


def start_oss_repo_test(core) -> dict[str, Any]:
    if not core.service_active() or not core.KUBECONFIG.is_file():
        raise core.Deny("oss-test-k3s-not-ready")
    probe = _namespace_probe(core)
    if probe.returncode == 0:
        raise core.Deny("oss-test-namespace-already-exists")
    text = (probe.stderr or probe.stdout).lower()
    if "notfound" not in text and "not found" not in text:
        raise core.Deny("oss-test-namespace-probe-failed:" + (probe.stderr or probe.stdout)[-1000:])
    payload = oss_test_manifest()
    path = core.STATE_ROOT / "oss-test-itsdangerous.json"
    path.write_bytes(core.canonical(payload) + b"\n")
    path.chmod(0o600)
    core.kubectl(["apply", "-f", str(path)], timeout=120)
    return {
        "status": "STARTED",
        "namespace": OSS_TEST_NAMESPACE,
        "job": OSS_TEST_JOB,
        "repository": OSS_TEST_REPOSITORY,
        "commit": OSS_TEST_COMMIT,
        "git_image": OSS_GIT_IMAGE,
        "python_image": OSS_PYTHON_IMAGE,
        "manifest_sha256": core.sha256(core.canonical(payload)),
        "production_target_testing": False,
        "external_egress": "DNS_AND_TCP_443_ONLY",
        "vendor_requests": 0,
    }


def read_oss_repo_test_evidence(core) -> dict[str, Any]:
    if not core.service_active() or not core.KUBECONFIG.is_file():
        return {"status": "K3S_NOT_RUNNING", "namespace": OSS_TEST_NAMESPACE, "repository": OSS_TEST_REPOSITORY, "commit": OSS_TEST_COMMIT, "vendor_requests": 0}
    if _namespace_probe(core).returncode != 0:
        return {"status": "ABSENT", "namespace": OSS_TEST_NAMESPACE, "repository": OSS_TEST_REPOSITORY, "commit": OSS_TEST_COMMIT, "vendor_requests": 0}
    job_proc = _kubectl_optional(core, ["get", "job", OSS_TEST_JOB, "-n", OSS_TEST_NAMESPACE, "-o", "json"], 20)
    if job_proc.returncode != 0:
        return {"status": "PENDING", "namespace": OSS_TEST_NAMESPACE, "job": OSS_TEST_JOB, "repository": OSS_TEST_REPOSITORY, "commit": OSS_TEST_COMMIT, "vendor_requests": 0}
    job = json.loads(job_proc.stdout)
    js = job.get("status", {}) or {}
    succeeded = int(js.get("succeeded", 0) or 0)
    failed = int(js.get("failed", 0) or 0)
    active = int(js.get("active", 0) or 0)
    status = "PASS" if succeeded == 1 and failed == 0 else ("FAIL" if failed > 0 else ("RUNNING" if active > 0 else "PENDING"))
    pods_proc = _kubectl_optional(core, ["get", "pods", "-n", OSS_TEST_NAMESPACE, "-l", f"job-name={OSS_TEST_JOB}", "-o", "json"], 20)
    pods_data = json.loads(pods_proc.stdout) if pods_proc.returncode == 0 else {"items": []}
    pod_rows: list[dict[str, Any]] = []
    clone_log = ""
    pytest_log = ""
    for item in pods_data.get("items", []) or []:
        meta = item.get("metadata", {}) or {}
        ps = item.get("status", {}) or {}
        name = str(meta.get("name") or "")
        states = []
        for key in ("initContainerStatuses", "containerStatuses"):
            for cs in ps.get(key, []) or []:
                state = cs.get("state", {}) or {}
                term = state.get("terminated") or {}
                waiting = state.get("waiting") or {}
                states.append({
                    "name": cs.get("name"),
                    "ready": bool(cs.get("ready")),
                    "restart_count": int(cs.get("restartCount", 0) or 0),
                    "image": cs.get("image"),
                    "image_id": cs.get("imageID"),
                    "exit_code": term.get("exitCode"),
                    "terminated_reason": term.get("reason"),
                    "waiting_reason": waiting.get("reason"),
                })
        pod_rows.append({"name": name, "uid": meta.get("uid"), "phase": ps.get("phase"), "pod_ip": ps.get("podIP"), "states": states})
        if name:
            clone_log = _log_tail(core, name, "git-clone")
            pytest_log = _log_tail(core, name, "pytest")
    summary = re.search(r"(\d+ passed(?:, \d+ (?:skipped|xfailed|xpassed|failed))*(?: in [0-9.]+s)?)", pytest_log)
    return {
        "status": status,
        "namespace": OSS_TEST_NAMESPACE,
        "job": OSS_TEST_JOB,
        "repository": OSS_TEST_REPOSITORY,
        "commit": OSS_TEST_COMMIT,
        "job_status": {
            "active": active,
            "succeeded": succeeded,
            "failed": failed,
            "start_time": js.get("startTime"),
            "completion_time": js.get("completionTime"),
        },
        "pods": pod_rows,
        "clone_log": clone_log,
        "pytest_log": pytest_log,
        "pytest_summary": summary.group(1) if summary else None,
        "production_target_testing": False,
        "vendor_requests": 0,
    }


def stop_oss_repo_test(core) -> dict[str, Any]:
    if not core.service_active() or not core.KUBECONFIG.is_file():
        return {"status": "ALREADY_STOPPED", "namespace": OSS_TEST_NAMESPACE, "vendor_requests": 0}
    core.kubectl(["delete", "namespace", OSS_TEST_NAMESPACE, "--ignore-not-found=true", "--wait=true", "--timeout=90s"], timeout=100)
    return {"status": "STOPPED", "namespace": OSS_TEST_NAMESPACE, "vendor_requests": 0}


def install_into_core_v4(core) -> None:
    _original_install(core)
    core.ALLOWED_OPERATIONS = set(core.ALLOWED_OPERATIONS) | set(OSS_OPERATIONS)
    original_handle = core.handle

    def handle_v4(req: dict[str, Any]) -> dict[str, Any]:
        op = req.get("operation")
        if op not in OSS_OPERATIONS:
            return original_handle(req)
        try:
            return original_handle(req)
        except core.Deny as exc:
            if str(exc) != "operation-unreachable":
                raise
        if op == "START_OSS_REPO_TEST":
            result = start_oss_repo_test(core)
        elif op == "READ_OSS_REPO_TEST_EVIDENCE":
            result = read_oss_repo_test_evidence(core)
        elif op == "STOP_OSS_REPO_TEST":
            result = stop_oss_repo_test(core)
        else:
            raise core.Deny("oss-operation-unreachable")
        evidence = core.write_receipt(req, "PASS", result)
        return {**result, **evidence}

    core.handle = handle_v4


v3.v2.install_into_core = install_into_core_v4


def main() -> int:
    return v3.v2.main()


if __name__ == "__main__":
    raise SystemExit(main())
