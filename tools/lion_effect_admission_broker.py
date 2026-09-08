#!/usr/bin/env python3
from __future__ import annotations

import fcntl
import hashlib
import json
import os
from pathlib import Path
import pwd
import re
import shutil
import socket
import struct
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from typing import Any


SCHEMA = "1.0.0"

EXPECTED_HOST = "LION-AUTH-LAB"
HOST_ID = "host_f78ddce3275144e4"

SENTINEL_USER = "sentinelx"
RUNNER_USER = "lion-maintenance-runner"
PROVIDER_GROUP = "lion-docker-p0"

REPOSITORY = "DonkeyJJLove/ai_platform"
REPO_URL = "https://github.com/DonkeyJJLove/ai_platform.git"
BRANCH = "experiment/local-swarm-p0-docker-polygon"

INSTALL_ROOT = Path("/opt/lion/effect-admission")
FIXED_REPO = INSTALL_ROOT / "scale64-repo"
IDENTITY_FILE = INSTALL_ROOT / "scale64-source-identity.json"

STATE_ROOT = Path("/var/lib/lion-effect-admission")
LOCK_FILE = STATE_ROOT / "scale64.lock"
WORKSPACE_ROOT = INSTALL_ROOT / "workspaces"
RUNNER_EXEC_CLIENT = "/usr/local/libexec/lion-runner-exec-client.py"

PROVIDER_INSTALL = (
    "deploy/docker/lion-p0-provider/install.sh"
)

HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")

MAX_REQUEST = 16 * 1024
MAX_RESPONSE = 8 * 1024 * 1024
MAX_LOG_RETURN = 256 * 1024


class Deny(RuntimeError):
    pass


def canonical(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()

    with path.open("rb") as handle:
        while True:
            block = handle.read(1024 * 1024)

            if not block:
                break

            h.update(block)

    return h.hexdigest()


def now() -> str:
    return (
        datetime.now(timezone.utc)
        .isoformat()
        .replace("+00:00", "Z")
    )


def atomic_json(
    path: Path,
    value: dict[str, Any],
) -> None:

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    tmp = path.with_name(
        path.name
        + ".tmp-"
        + sha256(os.urandom(16))[:12]
    )

    tmp.write_bytes(
        canonical(value) + b"\n"
    )

    os.chmod(tmp, 0o600)

    os.replace(
        tmp,
        path,
    )


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )

    if not isinstance(
        value,
        dict,
    ):
        raise Deny(
            f"{path}:not-object"
        )

    return value


def require_hex40(
    value: Any,
    label: str,
) -> str:

    if (
        not isinstance(value, str)
        or not HEX40.fullmatch(value)
    ):
        raise Deny(
            f"{label}:invalid"
        )

    return value


def require_hex64(
    value: Any,
    label: str,
) -> str:

    if (
        not isinstance(value, str)
        or not HEX64.fullmatch(value)
    ):
        raise Deny(
            f"{label}:invalid"
        )

    return value


def run(
    argv: list[str],
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    timeout: int = 600,
    capture: bool = False,
) -> subprocess.CompletedProcess[bytes]:

    proc = subprocess.run(
        argv,
        cwd=(
            str(cwd)
            if cwd is not None
            else None
        ),
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=(
            subprocess.PIPE
            if capture
            else subprocess.DEVNULL
        ),
        stderr=(
            subprocess.PIPE
            if capture
            else subprocess.DEVNULL
        ),
        shell=False,
        timeout=timeout,
        check=False,
    )

    if proc.returncode != 0:
        detail = ""

        if capture:
            detail = (
                proc.stderr.decode(
                    "utf-8",
                    "replace",
                )[-2000:]
            )

        raise Deny(
            "command-failed:"
            + os.path.basename(argv[0])
            + ":rc="
            + str(proc.returncode)
            + ":"
            + detail
        )

    return proc


def runner_exec_call(operation: str, *, repo: Path | None = None, head: str | None = None, tree: str | None = None, provider_operation: str | None = None, run_request_id: str | None = None, timeout: int = 900) -> dict[str, Any]:
    argv=["/usr/bin/python3",RUNNER_EXEC_CLIENT]
    if operation=="IDENTITY": argv += ["identity"]
    elif operation in {"STATIC_UNITTEST","STATIC_PYCOMPILE"}:
        if repo is None or head is None or tree is None: raise Deny("runner-exec-static-args")
        argv += ["static-unittest" if operation=="STATIC_UNITTEST" else "static-pycompile","--repo-path",str(repo),"--source-head",head,"--source-tree",tree]
    elif operation=="PROVIDER_CALL":
        if provider_operation not in {"PING","LIST_FLEET_RESOURCES"} or head is None or tree is None: raise Deny("runner-exec-provider-args")
        argv += ["provider-call","--provider-operation",provider_operation,"--source-head",head,"--source-tree",tree]
    elif operation=="SCALE64_RUN":
        if head is None or tree is None or run_request_id is None: raise Deny("runner-exec-scale64-args")
        argv += ["scale64-run","--source-head",head,"--source-tree",tree,"--run-request-id",run_request_id]
    else: raise Deny("runner-exec-operation-denied")
    proc=run(argv,capture=True,timeout=timeout)
    value=json.loads(proc.stdout.decode("utf-8"))
    if not isinstance(value,dict) or value.get("ok") is not True or not isinstance(value.get("result"),dict): raise Deny("runner-exec-failed")
    return value["result"]

def runner_env(
    repo: Path,
) -> dict[str, str]:

    return {
        "PATH": "/usr/bin:/bin",
        "HOME": "/tmp",
        "PYTHONPATH": str(repo),
        "PYTHONDONTWRITEBYTECODE": "1",
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
    }


def remote_head() -> str:
    proc = run(
        [
            "/usr/bin/git",
            "ls-remote",
            "--exit-code",
            REPO_URL,
            f"refs/heads/{BRANCH}",
        ],
        capture=True,
        timeout=60,
    )

    lines = [
        line
        for line in
        proc.stdout.decode(
            "utf-8",
            "strict",
        ).splitlines()
        if line.strip()
    ]

    if len(lines) != 1:
        raise Deny(
            "remote-head-cardinality"
        )

    fields = lines[0].split()

    if (
        len(fields) != 2
        or fields[1]
        != f"refs/heads/{BRANCH}"
    ):
        raise Deny(
            "remote-head-malformed"
        )

    return require_hex40(
        fields[0],
        "remote-head",
    )


def checkout_exact(head: str, tree: str) -> Path:
    WORKSPACE_ROOT.mkdir(parents=True,exist_ok=True)
    os.chown(WORKSPACE_ROOT,0,0); os.chmod(WORKSPACE_ROOT,0o755)
    workspace=Path(tempfile.mkdtemp(prefix="lion-admission-source-",dir=str(WORKSPACE_ROOT)))
    runner=pwd.getpwnam(RUNNER_USER); os.chown(workspace,runner.pw_uid,runner.pw_gid); os.chmod(workspace,0o750)
    repo=workspace/"repo"
    try:
        run(["/usr/bin/git","init",str(repo)],timeout=30)
        run(["/usr/bin/git","-C",str(repo),"remote","add","origin",REPO_URL],timeout=30)
        observed=remote_head()
        if observed!=head: raise Deny("LIVE_SOURCE_HEAD_DRIFT:"+observed)
        run(["/usr/bin/git","-C",str(repo),"fetch","--no-tags","--depth=1","origin",f"refs/heads/{BRANCH}"],timeout=180)
        run(["/usr/bin/git","-C",str(repo),"checkout","--detach","FETCH_HEAD"],timeout=60)
        actual_head=run(["/usr/bin/git","-C",str(repo),"rev-parse","HEAD"],capture=True).stdout.decode().strip()
        actual_tree=run(["/usr/bin/git","-C",str(repo),"rev-parse","HEAD^{tree}"],capture=True).stdout.decode().strip()
        if actual_head!=head or actual_tree!=tree: raise Deny("checkout-identity-mismatch")
        return repo
    except Exception:
        shutil.rmtree(workspace,ignore_errors=True); raise

def _provider_call(operation: str, head: str, tree: str) -> dict[str, Any]:
    if operation not in {"PING","LIST_FLEET_RESOURCES"}: raise Deny("provider-operation-not-precheck-safe")
    return runner_exec_call("PROVIDER_CALL",provider_operation=operation,head=head,tree=tree,timeout=60)

def precheck_scale64(head: str, tree: str) -> dict[str, Any]:
    live=remote_head()
    if live != head: raise Deny("LIVE_SOURCE_HEAD_DRIFT:"+live)
    identity_path=Path("/opt/lion/docker-p0-provider/build-context/source-identity.json")
    provider_identity=load_json(identity_path) if identity_path.is_file() else None
    provider_head=provider_identity.get("source_head") if provider_identity else None
    provider_tree=provider_identity.get("source_tree") if provider_identity else None
    provider_current=provider_head==head and provider_tree==tree
    docker_version=None; containers=None; networks=None
    if provider_current:
        docker_version=_provider_call("PING",head,tree).get("docker_server_version")
        inventory=_provider_call("LIST_FLEET_RESOURCES",head,tree)
        containers=inventory.get("containers"); networks=inventory.get("networks")
        if not isinstance(containers,list) or not isinstance(networks,list): raise Deny("fleet-inventory-malformed")
    container_count=len(containers) if containers is not None else None
    network_count=len(networks) if networks is not None else None
    clean=provider_current and container_count==0 and network_count==0
    return {"source_head":head,"source_tree":tree,"provider_source_head":provider_head,"provider_source_tree":provider_tree,"provider_current":provider_current,"docker_server_version":docker_version,"containers":containers,"networks":networks,"container_count":container_count,"network_count":network_count,"stale_resources":None if not provider_current else not clean,"clean_for_new_run":clean}

def static_gate(repo: Path) -> None:
    head=run(["/usr/bin/git","-C",str(repo),"rev-parse","HEAD"],capture=True).stdout.decode().strip()
    tree=run(["/usr/bin/git","-C",str(repo),"rev-parse","HEAD^{tree}"],capture=True).stdout.decode().strip()
    runner_exec_call("STATIC_UNITTEST",repo=repo,head=head,tree=tree,timeout=300)
    runner_exec_call("STATIC_PYCOMPILE",repo=repo,head=head,tree=tree,timeout=90)

def refresh_provider(
    repo: Path,
    head: str,
    tree: str,
) -> None:

    installer = (
        repo
        / PROVIDER_INSTALL
    )

    if not installer.is_file():
        raise Deny(
            "provider-installer-missing"
        )

    env = dict(os.environ)
    env["RESTART_RUNNER"] = "0"

    run(
        [
            "/usr/bin/bash",
            str(installer),
            str(repo),
            head,
            tree,
        ],
        cwd=repo,
        env=env,
        timeout=300,
    )


def install_fixed_source(
    repo: Path,
    head: str,
    tree: str,
) -> None:

    if FIXED_REPO.exists():
        shutil.rmtree(
            FIXED_REPO
        )

    shutil.copytree(
        repo,
        FIXED_REPO,
        symlinks=True,
    )

    git_dir = FIXED_REPO / ".git"

    if git_dir.exists():
        shutil.rmtree(git_dir)

    for root, dirs, files in os.walk(
        FIXED_REPO
    ):
        for dirname in dirs:
            os.chmod(
                Path(root) / dirname,
                0o755,
            )

        for filename in files:
            os.chmod(
                Path(root) / filename,
                0o444,
            )

    atomic_json(
        IDENTITY_FILE,
        {
            "schema_version": SCHEMA,
            "repository": REPOSITORY,
            "branch": BRANCH,
            "source_head": head,
            "source_tree": tree,
            "trust_class": "TEST_ONLY",
            "installed_at": now(),
        },
    )

    os.chmod(
        IDENTITY_FILE,
        0o444,
    )


def prepare_scale64(
    head: str,
    tree: str,
) -> dict[str, Any]:

    repo = checkout_exact(
        head,
        tree,
    )

    workspace = repo.parent

    try:
        static_gate(repo)

        refresh_provider(
            repo,
            head,
            tree,
        )

        install_fixed_source(
            repo,
            head,
            tree,
        )

        return {
            "prepared": True,
            "source_head": head,
            "source_tree": tree,
            "fixed_repo": str(
                FIXED_REPO
            ),
            "provider_refreshed": True,
            "static_gate": "PASS",
        }

    finally:
        shutil.rmtree(
            workspace,
            ignore_errors=True,
        )


def fixed_identity() -> dict[str, Any]:
    if not IDENTITY_FILE.is_file():
        raise Deny(
            "SCALE64_NOT_PREPARED"
        )

    value = load_json(
        IDENTITY_FILE
    )

    require_hex40(
        value.get("source_head"),
        "identity.source_head",
    )

    require_hex40(
        value.get("source_tree"),
        "identity.source_tree",
    )

    if (
        value.get("trust_class")
        != "TEST_ONLY"
    ):
        raise Deny(
            "identity-trust-invalid"
        )

    return value


def log_tail(
    path: Path,
) -> str:

    if not path.is_file():
        return ""

    raw = path.read_bytes()

    if len(raw) > MAX_LOG_RETURN:
        raw = raw[
            -MAX_LOG_RETURN:
        ]

    return raw.decode(
        "utf-8",
        "replace",
    )


def run_scale64(
    request_id: str,
    head: str,
    tree: str,
) -> dict[str, Any]:

    identity = fixed_identity()

    if (
        identity["source_head"]
        != head
    ):
        raise Deny(
            "prepared-head-mismatch"
        )

    if (
        identity["source_tree"]
        != tree
    ):
        raise Deny(
            "prepared-tree-mismatch"
        )

    live = remote_head()

    if live != head:
        raise Deny(
            "LIVE_SOURCE_HEAD_DRIFT:"
            + live
        )

    STATE_ROOT.mkdir(
        parents=True,
        exist_ok=True,
    )

    lock_handle = LOCK_FILE.open(
        "a+b"
    )

    try:
        fcntl.flock(
            lock_handle.fileno(),
            fcntl.LOCK_EX
            | fcntl.LOCK_NB,
        )
    except BlockingIOError as exc:
        raise Deny(
            "ACTIVE_SCALE64_RUN_EXISTS"
        ) from exc

    run_dir = (
        STATE_ROOT
        / request_id
    )

    if run_dir.exists():
        raise Deny(
            "REQUEST_REPLAY"
        )

    run_dir.mkdir(
        mode=0o700
    )

    log_path = (
        run_dir / "run.log"
    )

    evidence_path = (
        run_dir / "evidence.json"
    )

    status_path = (
        run_dir / "status.json"
    )

    atomic_json(
        status_path,
        {
            "state": "RUNNING",
            "request_id": request_id,
            "source_head": head,
            "source_tree": tree,
            "started_at": now(),
        },
    )

    try:
        rr=runner_exec_call("SCALE64_RUN",head=head,tree=tree,run_request_id=request_id,timeout=900)
        rc=rr.get("returncode")
        log_text=rr.get("log")
        evidence_obj=rr.get("evidence")
        relay_evidence_sha256=rr.get("source_evidence_sha256")
        if not isinstance(rc,int) or not isinstance(log_text,str): raise Deny("runner-exec-scale64-result-malformed")
        log_path.write_text(log_text,encoding="utf-8")
        if evidence_obj is not None:
            if not isinstance(evidence_obj,dict): raise Deny("runner-exec-evidence-malformed")
            require_hex64(relay_evidence_sha256,"relay_evidence_sha256")
            atomic_json(evidence_path,evidence_obj)
            broker_evidence_sha256=sha256_file(evidence_path)
            if broker_evidence_sha256 != relay_evidence_sha256:
                raise Deny("EVIDENCE_RELAY_HASH_MISMATCH")
        proc=subprocess.CompletedProcess(args=[RUNNER_EXEC_CLIENT],returncode=rc)
        tail=log_tail(log_path)

        if proc.returncode != 0:
            atomic_json(
                status_path,
                {
                    "state": "FAILED",
                    "request_id": (
                        request_id
                    ),
                    "source_head": head,
                    "source_tree": tree,
                    "finished_at": now(),
                    "returncode": (
                        proc.returncode
                    ),
                    "log_tail": tail,
                },
            )

            raise Deny(
                "SCALE64_RUN_FAILED:"
                + str(
                    proc.returncode
                )
            )

        if not evidence_path.is_file():
            raise Deny(
                "evidence-missing"
            )

        evidence = load_json(
            evidence_path
        )

        if (
            evidence.get(
                "source_head"
            )
            != head
        ):
            raise Deny(
                "evidence-head"
            )

        if (
            evidence.get(
                "source_tree"
            )
            != tree
        ):
            raise Deny(
                "evidence-tree"
            )

        if (
            evidence.get(
                "drone_count"
            )
            != 64
        ):
            raise Deny(
                "evidence-drone-count"
            )

        if (
            evidence.get(
                "requested_soak_seconds"
            )
            != 180
        ):
            raise Deny(
                "evidence-soak"
            )

        if (
            evidence.get(
                "poll_seconds"
            )
            != 15
        ):
            raise Deny(
                "evidence-poll"
            )

        if (
            evidence.get(
                "failure"
            )
            is not None
        ):
            raise Deny(
                "evidence-failure"
            )

        if (
            evidence.get(
                "cleanup_verified"
            )
            is not True
        ):
            raise Deny(
                "cleanup-not-verified"
            )

        containers = (
            evidence.get(
                "container_ids"
            )
        )

        results = (
            evidence.get(
                "work_results"
            )
        )

        snapshots = (
            evidence.get(
                "soak_snapshots"
            )
        )

        if (
            not isinstance(
                containers,
                dict,
            )
            or len(containers)
            != 64
        ):
            raise Deny(
                "container-cardinality"
            )

        if (
            not isinstance(
                results,
                list,
            )
            or len(results)
            != 64
        ):
            raise Deny(
                "work-result-cardinality"
            )

        if (
            not isinstance(
                snapshots,
                list,
            )
            or len(snapshots)
            < 11
        ):
            raise Deny(
                "snapshot-cardinality"
            )

        required_log_lines = {
            "FULL_FLEET_BARRIER=PASS",
            "FINAL_RUNNING=64/64",
            "SCALE64_SUCCESS=True",
        }

        lines = set(
            tail.splitlines()
        )

        missing = (
            required_log_lines
            - lines
        )

        if missing:
            raise Deny(
                "terminal-evidence-missing:"
                + ",".join(
                    sorted(missing)
                )
            )

        image_digest = (
            evidence.get(
                "image_digest"
            )
        )

        require_hex64(
            image_digest,
            "image_digest",
        )

        image_info = (
            evidence.get(
                "image_info"
            )
        )

        if not isinstance(
            image_info,
            dict,
        ):
            raise Deny(
                "image-info-missing"
            )

        image_size = (
            image_info.get(
                "size_bytes"
            )
        )

        if (
            not isinstance(
                image_size,
                int,
            )
            or image_size <= 0
        ):
            raise Deny(
                "image-size-invalid"
            )

        result_digest = None

        for line in tail.splitlines():
            if line.startswith(
                "SCALE64_RESULT_DIGEST="
            ):
                result_digest = (
                    line.split(
                        "=",
                        1,
                    )[1]
                )

        require_hex64(
            result_digest,
            "scale64_result_digest",
        )

        started = (
            evidence.get(
                "soak_started_at"
            )
        )

        completed = (
            evidence.get(
                "soak_completed_at"
            )
        )

        if (
            not isinstance(
                started,
                str,
            )
            or not isinstance(
                completed,
                str,
            )
        ):
            raise Deny(
                "soak-time-missing"
            )

        start_dt = (
            datetime
            .fromisoformat(
                started.replace(
                    "Z",
                    "+00:00",
                )
            )
        )

        end_dt = (
            datetime
            .fromisoformat(
                completed.replace(
                    "Z",
                    "+00:00",
                )
            )
        )

        soak_duration = (
            end_dt - start_dt
        ).total_seconds()

        if soak_duration < 165:
            raise Deny(
                "soak-too-short"
            )

        summary = {
            "classification": (
                "FULL_SUCCESS"
            ),
            "run_request_id": (
                request_id
            ),
            "run_id": evidence.get(
                "run_id"
            ),
            "host_id": HOST_ID,
            "hostname": (
                EXPECTED_HOST
            ),
            "source_head": head,
            "source_tree": tree,
            "logical_drones": 64,
            "materialized_containers": 64,
            "full_fleet_barrier": (
                "PASS"
            ),
            "soak_duration_seconds": (
                round(
                    soak_duration,
                    3,
                )
            ),
            "soak_snapshots": len(
                snapshots
            ),
            "work_results": 64,
            "scale64_result_digest": (
                result_digest
            ),
            "restarts": 0,
            "failures": 0,
            "final_running": 64,
            "cleanup_verified": True,
            "image_digest": (
                "sha256:"
                + image_digest
            ),
            "image_size_bytes": (
                image_size
            ),
            "evidence_path": str(
                evidence_path
            ),
            "evidence_sha256": broker_evidence_sha256,
            "relay_evidence_sha256": relay_evidence_sha256,
            "evidence_relay_match": True,
        }

        atomic_json(
            run_dir / "summary.json",
            summary,
        )

        atomic_json(
            status_path,
            {
                "state": "SUCCEEDED",
                "request_id": (
                    request_id
                ),
                "finished_at": now(),
                "summary": summary,
            },
        )

        return summary

    except Exception as exc:
        if not status_path.is_file():
            pass

        raise

    finally:
        lock_handle.close()


def read_evidence(
    request_id: str,
) -> dict[str, Any]:

    target = (
        STATE_ROOT
        / request_id
    )

    if not target.is_dir():
        raise Deny(
            "UNKNOWN_RUN_REQUEST_ID"
        )

    status = load_json(
        target / "status.json"
    )

    summary = None

    if (
        target / "summary.json"
    ).is_file():
        summary = load_json(
            target / "summary.json"
        )

    evidence = None

    if (
        target / "evidence.json"
    ).is_file():
        evidence = load_json(
            target / "evidence.json"
        )

    return {
        "status": status,
        "summary": summary,
        "evidence_ready": (
            evidence is not None
        ),
        "evidence": evidence,
        "log_tail": log_tail(
            target / "run.log"
        ),
    }


def peer_uid() -> int:
    sock = socket.fromfd(
        0,
        socket.AF_UNIX,
        socket.SOCK_STREAM,
    )

    raw = sock.getsockopt(
        socket.SOL_SOCKET,
        socket.SO_PEERCRED,
        struct.calcsize("3i"),
    )

    sock.close()

    _, uid, _ = (
        struct.unpack(
            "3i",
            raw,
        )
    )

    return uid


def receive() -> dict[str, Any]:
    raw = (
        sys.stdin.buffer.readline(
            MAX_REQUEST + 1
        )
    )

    if len(raw) > MAX_REQUEST:
        raise Deny(
            "REQUEST_TOO_LARGE"
        )

    try:
        value = json.loads(
            raw.decode(
                "utf-8"
            )
        )

    except Exception as exc:
        raise Deny(
            "INVALID_JSON"
        ) from exc

    if not isinstance(
        value,
        dict,
    ):
        raise Deny(
            "REQUEST_NOT_OBJECT"
        )

    return value


def reply(
    value: dict[str, Any],
) -> None:

    raw = (
        canonical(value)
        + b"\n"
    )

    if len(raw) > MAX_RESPONSE:
        raw = canonical(
            {
                "ok": False,
                "error": (
                    "RESPONSE_TOO_LARGE"
                ),
            }
        ) + b"\n"

    sys.stdout.buffer.write(raw)
    sys.stdout.buffer.flush()


def handle(
    request: dict[str, Any],
) -> dict[str, Any]:

    sentinel_uid = (
        pwd.getpwnam(
            SENTINEL_USER
        ).pw_uid
    )

    if peer_uid() != sentinel_uid:
        raise Deny(
            "CALLER_UID_DENIED"
        )

    if os.getuid() != 0:
        raise Deny(
            "BROKER_NOT_ROOT"
        )

    if (
        socket.gethostname()
        != EXPECTED_HOST
    ):
        raise Deny(
            "WRONG_HOST"
        )

    if (
        request.get(
            "schema_version"
        )
        != SCHEMA
    ):
        raise Deny(
            "SCHEMA_MISMATCH"
        )

    request_id = require_hex64(
        request.get(
            "request_id"
        ),
        "request_id",
    )

    operation = request.get(
        "operation"
    )

    if operation == "PING":
        if set(request) != {
            "schema_version",
            "request_id",
            "operation",
        }:
            raise Deny(
                "PING_FIELD_SET"
            )

        prepared = None

        if IDENTITY_FILE.is_file():
            prepared = fixed_identity()

        return {
            "broker": "READY",
            "authority_class": (
                "BOUNDED_PRIVILEGED_ADMISSION"
            ),
            "host_id": HOST_ID,
            "hostname": (
                EXPECTED_HOST
            ),
            "caller_uid": (
                pwd.getpwnam(
                    SENTINEL_USER
                ).pw_uid
            ),
            "direct_docker_authority": (
                False
            ),
            "prepared_scale64": (
                prepared
            ),
            "operations": [
                "PING",
                "PRECHECK_SCALE64",
                "PREPARE_SCALE64",
                "RUN_SCALE64",
                "READ_EVIDENCE",
            ],
        }

    if operation == "PRECHECK_SCALE64":
        if set(request) != {"schema_version", "request_id", "operation", "source_head", "source_tree"}:
            raise Deny("PRECHECK_FIELD_SET")
        head = require_hex40(request["source_head"], "source_head")
        tree = require_hex40(request["source_tree"], "source_tree")
        return precheck_scale64(head, tree)

    if operation == "PREPARE_SCALE64":
        if set(request) != {
            "schema_version",
            "request_id",
            "operation",
            "source_head",
            "source_tree",
        }:
            raise Deny(
                "PREPARE_FIELD_SET"
            )

        head = require_hex40(
            request[
                "source_head"
            ],
            "source_head",
        )

        tree = require_hex40(
            request[
                "source_tree"
            ],
            "source_tree",
        )

        return prepare_scale64(
            head,
            tree,
        )

    if operation == "RUN_SCALE64":
        if set(request) != {
            "schema_version",
            "request_id",
            "operation",
            "source_head",
            "source_tree",
        }:
            raise Deny(
                "RUN_FIELD_SET"
            )

        head = require_hex40(
            request[
                "source_head"
            ],
            "source_head",
        )

        tree = require_hex40(
            request[
                "source_tree"
            ],
            "source_tree",
        )

        return run_scale64(
            request_id,
            head,
            tree,
        )

    if operation == "READ_EVIDENCE":
        if set(request) != {
            "schema_version",
            "request_id",
            "operation",
            "run_request_id",
        }:
            raise Deny(
                "READ_FIELD_SET"
            )

        target = require_hex64(
            request[
                "run_request_id"
            ],
            "run_request_id",
        )

        return read_evidence(
            target
        )

    raise Deny(
        "OPERATION_NOT_ALLOWLISTED"
    )


def main() -> int:
    request_id = None

    try:
        request = receive()

        candidate = request.get(
            "request_id"
        )

        if isinstance(
            candidate,
            str,
        ):
            request_id = candidate

        result = handle(
            request
        )

        reply(
            {
                "ok": True,
                "request_id": (
                    request_id
                ),
                "result": result,
            }
        )

        return 0

    except Exception as exc:
        reply(
            {
                "ok": False,
                "request_id": (
                    request_id
                ),
                "error": (
                    type(exc).__name__
                    + ":"
                    + str(exc)[:2000]
                ),
            }
        )

        return 2


if __name__ == "__main__":
    raise SystemExit(main())