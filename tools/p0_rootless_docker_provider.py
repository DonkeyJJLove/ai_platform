#!/usr/bin/env python3
from __future__ import annotations

import base64
import grp
import hashlib
import json
import os
from pathlib import Path
import pwd
import re
import socket
import sqlite3
import struct
import subprocess
from typing import Any

SCHEMA = "1.0.0"
PROJECT = "LION_EVOLUSION"
ARCH_EPOCH = "1.4"
EXPERIMENT = "LOCAL_SWARM_P0"
TRUST = "TEST_ONLY"

SOCKET_PATH = Path(os.environ.get("LION_P0_PROVIDER_SOCKET", "/run/lion-docker-p0/provider.sock"))
STATE_DIR = Path(os.environ.get("LION_P0_STATE_DIR", "/var/lib/lion/docker-p0-provider"))
BUILD_CONTEXT = Path(os.environ.get("LION_P0_BUILD_CONTEXT", "/opt/lion/docker-p0-provider/build-context"))
DOCKER_HOST = os.environ.get("LION_P0_DOCKER_HOST", "unix:///run/user/1000/docker.sock")
ALLOWED_CALLER_UID = int(os.environ.get("LION_P0_ALLOWED_CALLER_UID", "-1"))
PROVIDER_GROUP = os.environ.get("LION_P0_PROVIDER_GROUP", "lion-docker-p0")
MAX_REQUEST = 128 * 1024
MAX_OUTPUT = 256 * 1024
SHA40 = re.compile(r"^[0-9a-f]{40}$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
SAFE_DOCKER_NAME = re.compile(r"^[a-z0-9][a-z0-9_.-]{0,127}$")
ROLES = {"architecture", "security", "runtime", "provenance", "falsifier"}
MUTATING = {"BUILD_P0_IMAGE", "CREATE_NETWORK", "RUN_DRONE", "STOP_DRONE", "REMOVE_DRONE", "REMOVE_NETWORK"}


class Deny(RuntimeError):
    pass


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _sha256_hex(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _require_exact_keys(value: dict[str, Any], expected: set[str], label: str) -> None:
    if set(value) != expected:
        raise Deny(f"{label}: field set mismatch")


def _safe_id(value: Any, label: str) -> str:
    if not isinstance(value, str) or not SAFE_ID.fullmatch(value):
        raise Deny(f"{label}: invalid")
    return value


def _docker_name(value: Any, label: str) -> str:
    if not isinstance(value, str) or not SAFE_DOCKER_NAME.fullmatch(value):
        raise Deny(f"{label}: invalid")
    return value


def _sha(value: Any, regex: re.Pattern[str], label: str) -> str:
    if not isinstance(value, str) or not regex.fullmatch(value):
        raise Deny(f"{label}: invalid")
    return value


def _docker(argv: list[str], *, timeout: int = 60) -> str:
    if not argv or argv[0] != "docker":
        raise Deny("internal docker argv invalid")
    env = {
        "PATH": "/usr/bin:/bin",
        "HOME": "/nonexistent",
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "DOCKER_HOST": DOCKER_HOST,
    }
    proc = subprocess.run(
        argv,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        shell=False,
        env=env,
        timeout=timeout,
        check=False,
    )
    out = proc.stdout
    err = proc.stderr
    if len(out.encode("utf-8", "replace")) > MAX_OUTPUT or len(err.encode("utf-8", "replace")) > MAX_OUTPUT:
        raise Deny("docker output exceeded bound")
    if proc.returncode != 0:
        raise Deny(f"docker operation failed rc={proc.returncode}: {err.strip()[:1024]}")
    return out


def _peer_uid(conn: socket.socket) -> int:
    raw = conn.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i"))
    _, uid, _ = struct.unpack("3i", raw)
    return uid


def _recv_request(conn: socket.socket) -> dict[str, Any]:
    buf = bytearray()
    while True:
        part = conn.recv(8192)
        if not part:
            break
        buf.extend(part)
        if len(buf) > MAX_REQUEST:
            raise Deny("request too large")
        if b"\n" in part:
            break
    raw = bytes(buf).split(b"\n", 1)[0]
    try:
        value = json.loads(raw.decode("utf-8"))
    except Exception as exc:
        raise Deny("invalid JSON request") from exc
    if not isinstance(value, dict):
        raise Deny("request must be object")
    return value


def _validate_request(req: dict[str, Any]) -> None:
    _require_exact_keys(
        req,
        {
            "schema_version", "request_id", "operation", "mission_id", "fleet_id",
            "run_id", "source_head", "source_tree", "plan_digest", "payload",
        },
        "request",
    )
    if req["schema_version"] != SCHEMA:
        raise Deny("schema mismatch")
    _sha(req["request_id"], SHA256, "request_id")
    if req["operation"] not in {
        "PING", "BUILD_P0_IMAGE", "CREATE_NETWORK", "RUN_DRONE", "WAIT_DRONE",
        "INSPECT_DRONE", "LOGS_DRONE", "STOP_DRONE", "REMOVE_DRONE", "REMOVE_NETWORK",
    }:
        raise Deny("operation not allowlisted")
    for key in ("mission_id", "fleet_id", "run_id"):
        _safe_id(req[key], key)
    _sha(req["source_head"], SHA40, "source_head")
    _sha(req["source_tree"], SHA40, "source_tree")
    _sha(req["plan_digest"], SHA256, "plan_digest")
    if not isinstance(req["payload"], dict):
        raise Deny("payload must be object")


def _labels(req: dict[str, Any], resource_class: str, *, extra: dict[str, str] | None = None) -> list[str]:
    labels = {
        "lion.project": PROJECT,
        "lion.architecture_epoch": ARCH_EPOCH,
        "lion.experiment_epoch": EXPERIMENT,
        "lion.mission_id": req["mission_id"],
        "lion.fleet_id": req["fleet_id"],
        "lion.run_id": req["run_id"],
        "lion.resource_class": resource_class,
        "lion.trust_class": TRUST,
        "lion.plan_digest": req["plan_digest"],
        "lion.source_head": req["source_head"],
        "lion.source_tree": req["source_tree"],
    }
    if extra:
        labels.update(extra)
    result: list[str] = []
    for key in sorted(labels):
        result += ["--label", f"{key}={labels[key]}"]
    return result


def _db() -> sqlite3.Connection:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(STATE_DIR / "fence.sqlite")
    conn.execute(
        "CREATE TABLE IF NOT EXISTS requests("
        "request_id TEXT PRIMARY KEY, request_digest TEXT NOT NULL, "
        "operation TEXT NOT NULL, state TEXT NOT NULL)"
    )
    return conn


def _fence(req: dict[str, Any]) -> None:
    if req["operation"] not in MUTATING:
        return
    digest = _sha256_hex(_canonical(req))
    with _db() as conn:
        try:
            conn.execute(
                "INSERT INTO requests(request_id, request_digest, operation, state) VALUES(?,?,?,?)",
                (req["request_id"], digest, req["operation"], "ATTEMPTED"),
            )
        except sqlite3.IntegrityError as exc:
            raise Deny("replayed mutating request") from exc


def _assert_labels(kind: str, name: str, req: dict[str, Any]) -> None:
    if kind == "container":
        raw = _docker(["docker", "inspect", name])
        try:
            obj = json.loads(raw)
            labels = obj[0]["Config"]["Labels"] or {}
        except Exception as exc:
            raise Deny("container observation malformed") from exc
    elif kind == "network":
        raw = _docker(["docker", "network", "inspect", name])
        try:
            obj = json.loads(raw)
            labels = obj[0]["Labels"] or {}
        except Exception as exc:
            raise Deny("network observation malformed") from exc
    else:
        raise Deny("unknown resource kind")
    expected = {
        "lion.project": PROJECT,
        "lion.architecture_epoch": ARCH_EPOCH,
        "lion.experiment_epoch": EXPERIMENT,
        "lion.mission_id": req["mission_id"],
        "lion.fleet_id": req["fleet_id"],
        "lion.run_id": req["run_id"],
        "lion.trust_class": TRUST,
        "lion.plan_digest": req["plan_digest"],
        "lion.source_head": req["source_head"],
        "lion.source_tree": req["source_tree"],
    }
    for key, value in expected.items():
        if labels.get(key) != value:
            raise Deny(f"{kind} label mismatch: {key}")


def _image_tag(req: dict[str, Any]) -> str:
    return f"lion-p0:{req['plan_digest'][:16]}"


def _dispatch(req: dict[str, Any]) -> dict[str, Any]:
    op = req["operation"]
    p = req["payload"]

    if op == "PING":
        _require_exact_keys(p, set(), "payload")
        version = _docker(["docker", "version", "--format", "{{.Server.Version}}"]).strip()
        return {"status": "OK", "docker_server_version": version, "docker_host": DOCKER_HOST}

    if op == "BUILD_P0_IMAGE":
        _require_exact_keys(p, set(), "payload")
        if not BUILD_CONTEXT.is_dir():
            raise Deny("fixed build context unavailable")
        tag = _image_tag(req)
        argv = ["docker", "build", "--pull", "--platform", "linux/amd64"]
        argv += _labels(req, "drone-image")
        argv += ["-t", tag, str(BUILD_CONTEXT)]
        _docker(argv, timeout=300)
        image_id = _docker(["docker", "image", "inspect", "--format", "{{.Id}}", tag]).strip()
        if not image_id.startswith("sha256:") or not SHA256.fullmatch(image_id[7:]):
            raise Deny("built image identity invalid")
        return {"status": "OK", "image_tag": tag, "image_digest": image_id[7:]}

    if op == "CREATE_NETWORK":
        _require_exact_keys(p, {"network_name"}, "payload")
        name = _docker_name(p["network_name"], "network_name")
        if not name.startswith("lion-p0-") or not name.endswith("-internal"):
            raise Deny("network name outside P0 namespace")
        argv = ["docker", "network", "create", "--internal"] + _labels(req, "fleet-network") + [name]
        network_id = _docker(argv).strip()
        return {"status": "OK", "network_name": name, "network_id": network_id}

    if op == "RUN_DRONE":
        _require_exact_keys(
            p,
            {
                "container_name", "network_name", "image_digest", "drone_id", "role",
                "generation", "executor_id", "lease_id", "capsule_digest", "capsule_b64",
            },
            "payload",
        )
        name = _docker_name(p["container_name"], "container_name")
        network = _docker_name(p["network_name"], "network_name")
        image_digest = _sha(p["image_digest"], SHA256, "image_digest")
        drone_id = _safe_id(p["drone_id"], "drone_id")
        role = p["role"]
        if role not in ROLES:
            raise Deny("role invalid")
        generation = p["generation"]
        if isinstance(generation, bool) or not isinstance(generation, int) or generation < 1:
            raise Deny("generation invalid")
        executor_id = _safe_id(p["executor_id"], "executor_id")
        lease_id = _sha(p["lease_id"], SHA256, "lease_id")
        capsule_digest = _sha(p["capsule_digest"], SHA256, "capsule_digest")
        if not name.startswith("lion-p0-") or not network.startswith("lion-p0-") or not network.endswith("-internal"):
            raise Deny("resource name outside P0 namespace")
        try:
            capsule = base64.b64decode(p["capsule_b64"], validate=True)
        except Exception as exc:
            raise Deny("capsule base64 invalid") from exc
        if not capsule or len(capsule) > 64 * 1024:
            raise Deny("capsule size invalid")
        try:
            obj = json.loads(capsule.decode("utf-8"))
        except Exception as exc:
            raise Deny("capsule JSON invalid") from exc
        if _canonical(obj) + b"\n" != capsule:
            raise Deny("capsule bytes are not canonical")
        if not isinstance(obj, dict):
            raise Deny("capsule must be object")
        _require_exact_keys(
            obj,
            {
                "schema_version", "mission_id", "fleet_id", "drone_id", "role",
                "generation", "work_unit_id", "issued_at", "expires_at", "operation",
                "input_payload", "input_digest", "policy_digest", "capsule_digest",
            },
            "capsule",
        )
        if obj.get("schema_version") != SCHEMA:
            raise Deny("capsule schema mismatch")
        _sha(obj.get("input_digest"), SHA256, "capsule.input_digest")
        _sha(obj.get("policy_digest"), SHA256, "capsule.policy_digest")
        supplied_capsule_digest = _sha(obj.get("capsule_digest"), SHA256, "capsule.capsule_digest")
        if not isinstance(obj.get("input_payload"), dict):
            raise Deny("capsule input_payload invalid")
        calculated_input_digest = hashlib.sha256(
            b"LION/MISSION-INPUT/P0\0" + _canonical(obj["input_payload"])
        ).hexdigest()
        if calculated_input_digest != obj["input_digest"]:
            raise Deny("capsule input digest mismatch")
        unsigned_capsule = dict(obj)
        unsigned_capsule.pop("capsule_digest")
        calculated_capsule_digest = hashlib.sha256(
            b"LION/MISSION-CAPSULE/P0\0" + _canonical(unsigned_capsule)
        ).hexdigest()
        if calculated_capsule_digest != supplied_capsule_digest:
            raise Deny("capsule digest mismatch")
        for key, expected in (
            ("mission_id", req["mission_id"]),
            ("fleet_id", req["fleet_id"]),
            ("drone_id", drone_id),
            ("role", role),
            ("generation", generation),
            ("capsule_digest", capsule_digest),
        ):
            if obj.get(key) != expected:
                raise Deny(f"capsule binding mismatch: {key}")

        cap_dir = STATE_DIR / "capsules" / req["run_id"]
        cap_dir.mkdir(parents=True, exist_ok=True)
        cap_path = cap_dir / f"{drone_id}.json"
        if cap_path.exists():
            if cap_path.read_bytes() != capsule:
                raise Deny("capsule path collision")
        else:
            cap_path.write_bytes(capsule)
            os.chmod(cap_path, 0o400)

        extra = {
            "lion.drone_id": drone_id,
            "lion.role": role,
            "lion.generation": str(generation),
            "lion.executor_id": executor_id,
            "lion.lease_id": lease_id,
            "lion.capsule_digest": capsule_digest,
        }
        argv = [
            "docker", "run", "--detach", "--name", name,
            "--network", network,
            "--read-only",
            "--user", "65532:65532",
            "--cap-drop", "ALL",
            "--security-opt", "no-new-privileges",
            "--pids-limit", "64",
            "--memory", "134217728",
            "--cpus", "0.20",
            "--restart", "no",
            "--tmpfs", "/tmp:rw,noexec,nosuid,nodev,size=16777216",
            "--mount", f"type=bind,src={cap_path},dst=/mission/capsule.json,readonly",
        ]
        argv += _labels(req, "drone", extra=extra)
        argv += [f"sha256:{image_digest}"]
        container_id = _docker(argv).strip()
        return {"status": "OK", "container_name": name, "container_id": container_id}

    if op in {"WAIT_DRONE", "INSPECT_DRONE", "LOGS_DRONE", "STOP_DRONE", "REMOVE_DRONE"}:
        _require_exact_keys(p, {"container_name"}, "payload")
        name = _docker_name(p["container_name"], "container_name")
        if not name.startswith("lion-p0-"):
            raise Deny("container outside P0 namespace")
        _assert_labels("container", name, req)
        if op == "WAIT_DRONE":
            exit_code = _docker(["docker", "wait", name]).strip()
            return {"status": "OK", "container_name": name, "exit_code": int(exit_code)}
        if op == "INSPECT_DRONE":
            raw = _docker(["docker", "inspect", name])
            return {"status": "OK", "container_name": name, "inspect": json.loads(raw)[0]}
        if op == "LOGS_DRONE":
            return {"status": "OK", "container_name": name, "logs": _docker(["docker", "logs", name])}
        if op == "STOP_DRONE":
            _docker(["docker", "stop", "--time", "5", name])
            return {"status": "OK", "container_name": name}
        _docker(["docker", "rm", "--force", name])
        return {"status": "OK", "container_name": name}

    if op == "REMOVE_NETWORK":
        _require_exact_keys(p, {"network_name"}, "payload")
        name = _docker_name(p["network_name"], "network_name")
        if not name.startswith("lion-p0-") or not name.endswith("-internal"):
            raise Deny("network outside P0 namespace")
        _assert_labels("network", name, req)
        _docker(["docker", "network", "rm", name])
        return {"status": "OK", "network_name": name}

    raise Deny("unreachable operation")


def _serve_one(conn: socket.socket) -> None:
    if _peer_uid(conn) != ALLOWED_CALLER_UID:
        raise Deny("peer uid not authorized")
    req = _recv_request(conn)
    _validate_request(req)
    _fence(req)
    result = _dispatch(req)
    response = {"ok": True, "request_id": req["request_id"], "result": result}
    conn.sendall(_canonical(response) + b"\n")


def main() -> int:
    if os.geteuid() == 0:
        raise SystemExit("provider must not run as root")
    expected_user = "lion-container-runtime-lab"
    if pwd.getpwuid(os.geteuid()).pw_name != expected_user:
        raise SystemExit("provider must run as lion-container-runtime-lab")
    if ALLOWED_CALLER_UID < 0:
        raise SystemExit("LION_P0_ALLOWED_CALLER_UID is required")
    group_gid = grp.getgrnam(PROVIDER_GROUP).gr_gid
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    if SOCKET_PATH.exists():
        SOCKET_PATH.unlink()
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.bind(str(SOCKET_PATH))
    os.chown(SOCKET_PATH, -1, group_gid)
    os.chmod(SOCKET_PATH, 0o660)
    sock.listen(16)
    while True:
        conn, _ = sock.accept()
        with conn:
            try:
                _serve_one(conn)
            except Exception as exc:
                response = {"ok": False, "error": type(exc).__name__, "detail": str(exc)[:1024]}
                try:
                    conn.sendall(_canonical(response) + b"\n")
                except OSError:
                    pass


if __name__ == "__main__":
    raise SystemExit(main())
