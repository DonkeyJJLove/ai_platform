#!/usr/bin/env python3
from __future__ import annotations

import fcntl
import hashlib
import http.client
import json
import os
from pathlib import Path
import pwd
import re
import shutil
import socket
import sqlite3
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
TRUST_CLASS = "TEST_ONLY"

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
        stdout_tail = ""
        stderr_tail = ""

        if capture:
            stdout_tail = proc.stdout.decode(
                "utf-8",
                "replace",
            )[-4096:]
            stderr_tail = proc.stderr.decode(
                "utf-8",
                "replace",
            )[-4096:]

        raise Deny(
            "command-failed:"
            + os.path.basename(argv[0])
            + ":rc="
            + str(proc.returncode)
            + ":stdout_tail="
            + repr(stdout_tail)
            + ":stderr_tail="
            + repr(stderr_tail)
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


def handoff_exact_workspace_to_runner(workspace: Path) -> None:
    root = WORKSPACE_ROOT.resolve()
    resolved = workspace.resolve()
    if resolved.parent != root:
        raise Deny("workspace-handoff-outside-root")
    if not workspace.name.startswith("lion-admission-source-"):
        raise Deny("workspace-handoff-shape")

    runner = pwd.getpwnam(RUNNER_USER)
    uid = runner.pw_uid
    gid = runner.pw_gid

    for current, directories, files in os.walk(
        workspace,
        topdown=True,
        followlinks=False,
    ):
        current_path = Path(current)
        if current_path.is_symlink():
            os.lchown(current_path, uid, gid)
        else:
            os.chown(current_path, uid, gid)

        for name in directories:
            path = current_path / name
            if path.is_symlink():
                os.lchown(path, uid, gid)
            else:
                os.chown(path, uid, gid)

        for name in files:
            path = current_path / name
            if path.is_symlink():
                os.lchown(path, uid, gid)
            else:
                os.chown(path, uid, gid)

    os.chown(workspace, uid, gid)


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
        handoff_exact_workspace_to_runner(workspace)
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

def static_gate(repo: Path, head: str, tree: str) -> None:
    require_hex40(head, "static-gate-head")
    require_hex40(tree, "static-gate-tree")
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
    env["GIT_CONFIG_COUNT"] = "1"
    env["GIT_CONFIG_KEY_0"] = "safe.directory"
    env["GIT_CONFIG_VALUE_0"] = str(repo)

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

    os.chmod(FIXED_REPO, 0o755)

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
        static_gate(repo, head, tree)

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



# ---- LION Mission64 bounded Kubernetes control extension -----------------
MISSION64_ID = "LION-R4-PREFLIGHT-L12-M64-MISSION-CONTROL-V3"
MISSION64_NAMESPACE = "lion-mission64-r4-preflight"
MISSION64_K3S_BIN = Path("/opt/lion/k3s/k3s")
MISSION64_K3S_UNIT = "lion-k3s-vkt-r3.service"
MISSION64_KUBECONFIG = Path("/var/lib/lion-effect-admission/vkt-r3-k3s/kubeconfig.yaml")
MISSION64_K3S_SHA256 = "835873f37245fc615f547a2fe2af9402a347875f13fa64a1f136de644955ea3f"
MISSION64_IMAGE = "python@sha256:782412e85d0f0984994c290652577d4018aff08145c85b262bb63dc0c7522254"
MISSION64_LOGICAL = (
    ("LD01","MISSION_PLANNER",6),
    ("LD02","AUTHORITY_CURRENTNESS",6),
    ("LD03","REPOSITORY_CURRENTNESS",6),
    ("LD04","LOCAL_MODEL_ROUTER",6),
    ("LD05","SAAS_DELEGATION",5),
    ("LD06","DETERMINISTIC_EXECUTION",5),
    ("LD07","WEB_EVIDENCE",5),
    ("LD08","MATERIAL_SCHEDULER",5),
    ("LD09","SECURITY_FALSIFIER",5),
    ("LD10","VALIDATION",5),
    ("LD11","RECOVERY",5),
    ("LD12","RECONCILIATION",5),
)
MISSION64_STATE = STATE_ROOT / "mission64"
MISSION64_MASTER_REPO = "https://github.com/DonkeyJJLove/ai_platform.git"
MISSION64_MASTER_BRANCH = "master"


def mission64_spec() -> dict[str, Any]:
    value={
        "schema_version":"1.0.0",
        "mission_id":MISSION64_ID,
        "namespace":MISSION64_NAMESPACE,
        "logical_drones":[{"id":i,"role":r,"replicas":n} for i,r,n in MISSION64_LOGICAL],
        "logical_drone_count":12,
        "material_pod_count":64,
        "image":MISSION64_IMAGE,
        "network":"DENY_ALL",
        "authority_effect":"BOUNDED_MISSION_CONTROL",
    }
    value["spec_digest"]=sha256(canonical(value))
    return value


def mission64_require_envelope(request: dict[str,Any], *, worker: bool=False) -> tuple[str,str,str]:
    expected={"schema_version","request_id","operation","mission_id","source_head","source_tree","spec_digest"}
    if worker: expected.add("pod_name")
    if set(request)!=expected: raise Deny("MISSION64_FIELD_SET")
    if request.get("mission_id")!=MISSION64_ID: raise Deny("MISSION64_ID_MISMATCH")
    spec=mission64_spec()
    if request.get("spec_digest")!=spec["spec_digest"]: raise Deny("MISSION64_SPEC_DIGEST_MISMATCH")
    head=require_hex40(request.get("source_head"),"source_head")
    tree=require_hex40(request.get("source_tree"),"source_tree")
    return head,tree,spec["spec_digest"]


def mission64_git_identity() -> tuple[str,str]:
    td=Path(tempfile.mkdtemp(prefix="lion-mission64-currentness-"))
    try:
        run(["/usr/bin/git","init",str(td)],timeout=30)
        run(["/usr/bin/git","-C",str(td),"remote","add","origin",MISSION64_MASTER_REPO],timeout=30)
        run(["/usr/bin/git","-C",str(td),"fetch","--no-tags","--depth=1","origin",f"refs/heads/{MISSION64_MASTER_BRANCH}"],timeout=180)
        head=run(["/usr/bin/git","-C",str(td),"rev-parse","FETCH_HEAD"],capture=True,timeout=30).stdout.decode().strip()
        tree=run(["/usr/bin/git","-C",str(td),"rev-parse","FETCH_HEAD^{tree}"],capture=True,timeout=30).stdout.decode().strip()
        return require_hex40(head,"mission64-live-head"),require_hex40(tree,"mission64-live-tree")
    finally:
        shutil.rmtree(td,ignore_errors=True)


def mission64_verify_current(head:str,tree:str)->None:
    live_h,live_t=mission64_git_identity()
    if live_h!=head or live_t!=tree: raise Deny("MISSION64_LIVE_SOURCE_DRIFT:"+live_h+":"+live_t)


def mission64_k3s_state()->dict[str,Any]:
    exists=MISSION64_K3S_BIN.is_file()
    digest=sha256_file(MISSION64_K3S_BIN) if exists else None
    if not exists or digest!=MISSION64_K3S_SHA256: raise Deny("MISSION64_K3S_IDENTITY_MISMATCH")
    active=subprocess.run(["/bin/systemctl","is-active","--quiet",MISSION64_K3S_UNIT],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,check=False).returncode==0
    return {"exists":exists,"sha256":digest,"service_active":active,"kubeconfig_exists":MISSION64_KUBECONFIG.is_file()}


def mission64_kubectl(args:list[str], *, payload:bytes|None=None, timeout:int=120, check:bool=True)->subprocess.CompletedProcess[bytes]:
    if not MISSION64_KUBECONFIG.is_file(): raise Deny("MISSION64_KUBECONFIG_MISSING")
    argv=[str(MISSION64_K3S_BIN),"kubectl","--kubeconfig",str(MISSION64_KUBECONFIG),*args]
    kwargs={"stdout":subprocess.PIPE,"stderr":subprocess.PIPE,"shell":False,"check":False,"timeout":timeout,"env":{"PATH":"/usr/sbin:/usr/bin:/sbin:/bin","LANG":"C.UTF-8","LC_ALL":"C.UTF-8"}}
    if payload is None: kwargs["stdin"]=subprocess.DEVNULL
    else: kwargs["input"]=payload
    proc=subprocess.run(argv,**kwargs)
    if check and proc.returncode!=0: raise Deny("MISSION64_KUBECTL_FAILED:"+(proc.stderr or proc.stdout).decode("utf-8","replace")[-2000:])
    return proc


def mission64_wait_k3s(timeout:float=120)->None:
    end=datetime.now(timezone.utc).timestamp()+timeout
    last=""
    while datetime.now(timezone.utc).timestamp()<end:
        state=mission64_k3s_state()
        if state["service_active"] and state["kubeconfig_exists"]:
            p=mission64_kubectl(["get","nodes","-o","json"],timeout=15,check=False)
            if p.returncode==0:
                try:
                    data=json.loads(p.stdout.decode())
                    if any(any(c.get("type")=="Ready" and c.get("status")=="True" for c in (x.get("status",{}).get("conditions") or [])) for x in data.get("items",[])): return
                except Exception as exc: last=str(exc)
            else: last=(p.stderr or p.stdout).decode("utf-8","replace")[-1000:]
        import time as _time; _time.sleep(2)
    raise Deny("MISSION64_K3S_NOT_READY:"+last)


def mission64_start_k3s()->None:
    state=mission64_k3s_state()
    if not state["service_active"]:
        proc=subprocess.run(["/bin/systemctl","start",MISSION64_K3S_UNIT],stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,shell=False,check=False,timeout=60)
        if proc.returncode!=0: raise Deny("MISSION64_K3S_START_FAILED:"+(proc.stderr or proc.stdout).decode("utf-8","replace")[-2000:])
    mission64_wait_k3s()


def mission64_manifest()->dict[str,Any]:
    spec=mission64_spec(); docs=[]
    labels={"lion.openai/mission":MISSION64_ID.lower(),"lion.openai/spec":spec["spec_digest"][:16]}
    docs.append({"apiVersion":"v1","kind":"Namespace","metadata":{"name":MISSION64_NAMESPACE,"labels":labels}})
    for logical_id,role,replicas in MISSION64_LOGICAL:
        name=logical_id.lower()+"-worker"
        plabels={**labels,"app":name,"component":"material-drone","logical-drone":logical_id.lower()}
        docs.append({
            "apiVersion":"apps/v1","kind":"Deployment","metadata":{"name":name,"namespace":MISSION64_NAMESPACE,"labels":plabels},
            "spec":{"replicas":replicas,"selector":{"matchLabels":{"app":name}},"strategy":{"type":"RollingUpdate","rollingUpdate":{"maxUnavailable":1,"maxSurge":1}},"template":{
                "metadata":{"labels":plabels},
                "spec":{"automountServiceAccountToken":False,"terminationGracePeriodSeconds":3,"securityContext":{"runAsNonRoot":True,"runAsUser":1000,"runAsGroup":1000,"seccompProfile":{"type":"RuntimeDefault"}},"containers":[{
                    "name":"drone","image":MISSION64_IMAGE,"imagePullPolicy":"IfNotPresent","command":["/bin/sh","-ec","echo MISSION=$MISSION_ID LOGICAL=$LOGICAL_DRONE ROLE=$LOGICAL_ROLE POD=$POD_NAME; while true; do sleep 3600; done"],
                    "env":[{"name":"MISSION_ID","value":MISSION64_ID},{"name":"LOGICAL_DRONE","value":logical_id},{"name":"LOGICAL_ROLE","value":role},{"name":"POD_NAME","valueFrom":{"fieldRef":{"fieldPath":"metadata.name"}}},{"name":"POD_UID","valueFrom":{"fieldRef":{"fieldPath":"metadata.uid"}}}],
                    "resources":{"requests":{"cpu":"1m","memory":"8Mi"},"limits":{"cpu":"50m","memory":"32Mi"}},
                    "securityContext":{"allowPrivilegeEscalation":False,"readOnlyRootFilesystem":True,"runAsNonRoot":True,"runAsUser":1000,"capabilities":{"drop":["ALL"]}}
                }]}
            }}
        })
    docs.append({"apiVersion":"networking.k8s.io/v1","kind":"NetworkPolicy","metadata":{"name":"deny-all","namespace":MISSION64_NAMESPACE},"spec":{"podSelector":{},"policyTypes":["Ingress","Egress"],"ingress":[],"egress":[]}})
    return {"apiVersion":"v1","kind":"List","items":docs}


def mission64_validate_manifest(value:dict[str,Any])->None:
    if value.get("kind")!="List" or type(value.get("items")) is not list: raise Deny("MISSION64_MANIFEST_SHAPE")
    deps=[x for x in value["items"] if x.get("kind")=="Deployment"]
    if len(deps)!=12 or sum(int(x.get("spec",{}).get("replicas",-1)) for x in deps)!=64: raise Deny("MISSION64_CARDINALITY")
    if [int(x["spec"]["replicas"]) for x in deps] != [x[2] for x in MISSION64_LOGICAL]: raise Deny("MISSION64_DISTRIBUTION")
    for doc in deps:
        ps=doc["spec"]["template"]["spec"]
        if ps.get("automountServiceAccountToken") is not False: raise Deny("MISSION64_SERVICE_ACCOUNT")
        for forbidden in ("hostNetwork","hostPID","hostIPC"):
            if ps.get(forbidden) is True: raise Deny("MISSION64_HOST_NAMESPACE")
        for vol in ps.get("volumes",[]) or []:
            if "hostPath" in vol: raise Deny("MISSION64_HOSTPATH")
        for c in ps.get("containers",[]):
            if c.get("image")!=MISSION64_IMAGE: raise Deny("MISSION64_IMAGE")
            sc=c.get("securityContext") or {}
            if sc.get("allowPrivilegeEscalation") is not False or sc.get("readOnlyRootFilesystem") is not True or sc.get("runAsNonRoot") is not True or (sc.get("capabilities") or {}).get("drop") != ["ALL"]: raise Deny("MISSION64_SECURITY_CONTEXT")
    nps=[x for x in value["items"] if x.get("kind")=="NetworkPolicy"]
    if len(nps)!=1 or nps[0].get("spec",{}).get("egress")!=[] or nps[0].get("spec",{}).get("ingress")!=[]: raise Deny("MISSION64_NETWORK_POLICY")


def mission64_apply()->str:
    manifest=mission64_manifest(); mission64_validate_manifest(manifest)
    raw=canonical(manifest)
    mission64_kubectl(["apply","-f","-"],payload=raw,timeout=180)
    return sha256(raw)


def mission64_pod_rows()->list[dict[str,Any]]:
    p=mission64_kubectl(["get","pods","-n",MISSION64_NAMESPACE,"-l","component=material-drone","-o","json"],timeout=30,check=False)
    if p.returncode!=0:
        text=(p.stderr or p.stdout).decode("utf-8","replace").lower()
        if "notfound" in text or "not found" in text:return []
        raise Deny("MISSION64_POD_READ:"+text[-1200:])
    data=json.loads(p.stdout.decode())
    rows=[]
    for x in data.get("items",[]):
        meta=x.get("metadata") or {}; st=x.get("status") or {}; labels=meta.get("labels") or {}
        if labels.get("component")!="material-drone":continue
        ready=any(c.get("type")=="Ready" and c.get("status")=="True" for c in st.get("conditions",[]) or [])
        rows.append({"name":meta.get("name"),"uid":meta.get("uid"),"logical_drone":labels.get("logical-drone"),"phase":st.get("phase"),"ready":ready,"pod_ip":st.get("podIP"),"restarts":sum(int(c.get("restartCount",0) or 0) for c in st.get("containerStatuses",[]) or [])})
    return sorted(rows,key=lambda r:r["name"] or "")


def mission64_deployment_state()->list[dict[str,Any]]:
    p=mission64_kubectl(["get","deployments","-n",MISSION64_NAMESPACE,"-o","json"],timeout=30,check=False)
    if p.returncode!=0:return []
    data=json.loads(p.stdout.decode()); out=[]
    for x in data.get("items",[]):
        m=x.get("metadata") or {}; s=x.get("spec") or {}; st=x.get("status") or {}; labels=m.get("labels") or {}
        if labels.get("component")!="material-drone":continue
        out.append({"name":m.get("name"),"logical_drone":labels.get("logical-drone"),"desired":int(s.get("replicas",0) or 0),"ready":int(st.get("readyReplicas",0) or 0),"available":int(st.get("availableReplicas",0) or 0)})
    return sorted(out,key=lambda r:r["name"] or "")


def mission64_read()->dict[str,Any]:
    spec=mission64_spec(); ks=mission64_k3s_state()
    if not ks["service_active"] or not ks["kubeconfig_exists"]:
        return {"mission_id":MISSION64_ID,"spec_digest":spec["spec_digest"],"state":"K3S_NOT_RUNNING","logical_drones":12,"materialized":0,"ready":0,"pods":[],"deployments":[],"k3s":ks}
    ns=mission64_kubectl(["get","namespace",MISSION64_NAMESPACE,"-o","json"],timeout=15,check=False)
    if ns.returncode!=0:
        return {"mission_id":MISSION64_ID,"spec_digest":spec["spec_digest"],"state":"ABSENT","logical_drones":12,"materialized":0,"ready":0,"pods":[],"deployments":[],"k3s":ks}
    pods=mission64_pod_rows(); deps=mission64_deployment_state(); ready=sum(1 for x in pods if x["ready"]); desired=sum(x["desired"] for x in deps)
    state="RUNNING" if len(pods)==64 and ready==64 and desired==64 else ("PAUSED" if desired==0 and len(pods)==0 else "CONVERGING")
    by={i.lower():{"role":r,"expected":n,"materialized":0,"ready":0} for i,r,n in MISSION64_LOGICAL}
    for row in pods:
        if row["logical_drone"] in by:
            by[row["logical_drone"]]["materialized"]+=1;by[row["logical_drone"]]["ready"]+=1 if row["ready"] else 0
    return {"mission_id":MISSION64_ID,"spec_digest":spec["spec_digest"],"state":state,"logical_drones":12,"materialized":len(pods),"ready":ready,"unique_uid_count":len({x["uid"] for x in pods if x.get("uid")}),"desired":desired,"by_logical":by,"pods":pods,"deployments":deps,"k3s":ks}


def mission64_wait(expected_ready:int, expected_pods:int, timeout:float=180)->dict[str,Any]:
    import time as _time
    end=_time.time()+timeout; last=None
    while _time.time()<end:
        last=mission64_read()
        if last.get("ready")==expected_ready and last.get("materialized")==expected_pods:return last
        _time.sleep(2)
    raise Deny("MISSION64_CONVERGENCE_TIMEOUT:"+json.dumps({k:last.get(k) for k in ("state","materialized","ready","desired")} if last else {}))


def mission64_receipt(request:dict[str,Any],result:dict[str,Any])->dict[str,Any]:
    payload={"schema_version":"1.0.0","timestamp":now(),"request_id":request["request_id"],"operation":request["operation"],"mission_id":MISSION64_ID,"spec_digest":mission64_spec()["spec_digest"],"source_head":request.get("source_head"),"source_tree":request.get("source_tree"),"result_digest":sha256(canonical(result)),"authority":"EXPLICIT_USER_AUTHORIZED_MISSION"}
    payload["receipt_digest"]=sha256(canonical(payload))
    path=MISSION64_STATE/"receipts"/(request["request_id"]+".json");atomic_json(path,payload)
    return {"control_receipt":payload}


def mission64_validate_execution()->dict[str,Any]:
 runtime=mission64_read()
 if runtime.get("state")!="RUNNING" or runtime.get("ready")!=64 or runtime.get("unique_uid_count")!=64:raise Deny("MISSION64_VALIDATE_NOT_READY")
 roles={i.lower():r for i,r,_ in MISSION64_LOGICAL};rows=[];fail=[]
 for pod in runtime.get("pods",[]):
  name=pod.get("name");lid=pod.get("logical_drone");role=roles.get(lid)
  if not name or not role:fail.append({"pod":name,"reason":"logical-role"});continue
  p=mission64_kubectl(["logs",name,"-n",MISSION64_NAMESPACE,"--tail=10"],timeout=15,check=False)
  text=(p.stdout if p.returncode==0 else p.stderr).decode("utf-8","replace")[-4096:]
  expected=f"MISSION={MISSION64_ID} LOGICAL={lid.upper()} ROLE={role} POD={name}"
  ok=p.returncode==0 and expected in text
  row={"pod":name,"uid":pod.get("uid"),"logical_drone":lid.upper(),"role":role,"receipt_line_sha256":sha256(expected.encode()),"ok":ok};rows.append(row)
  if not ok:fail.append({"pod":name,"reason":"execution-line-mismatch","tail":text[-300:]})
 if fail:raise Deny("MISSION64_EXECUTION_VALIDATION_FAILED:"+json.dumps(fail[:5],ensure_ascii=False))
 return {"mission_id":MISSION64_ID,"validated_pods":len(rows),"logical_drones":12,"ready":64,"unique_uid_count":64,"execution_digest":sha256(canonical(rows)),"rows":rows,"authority_effect":"NONE"}

def mission64_handle(request:dict[str,Any])->dict[str,Any]:
    op=request["operation"]; worker=op=="MISSION64_RESTART_ONE";head,tree,_=mission64_require_envelope(request,worker=worker)
    if op in {"MISSION64_START","MISSION64_RESUME"}: mission64_verify_current(head,tree)
    if op=="MISSION64_PRECHECK": result={"source_head":head,"source_tree":tree,"spec":mission64_spec(),"k3s":mission64_k3s_state(),"runtime":mission64_read()}
    elif op=="MISSION64_START":
        mission64_start_k3s(); before=mission64_read()
        if before["state"] not in {"ABSENT","PAUSED","CONVERGING"}: raise Deny("MISSION64_START_STATE:"+before["state"])
        manifest_sha=mission64_apply(); result=mission64_wait(64,64);result["manifest_sha256"]=manifest_sha
    elif op=="MISSION64_READ": result=mission64_read()
    elif op=="MISSION64_PAUSE":
        if mission64_read()["state"] not in {"RUNNING","CONVERGING"}: raise Deny("MISSION64_PAUSE_STATE")
        for i,_,_ in MISSION64_LOGICAL: mission64_kubectl(["scale","deployment",i.lower()+"-worker","-n",MISSION64_NAMESPACE,"--replicas=0"],timeout=30)
        result=mission64_wait(0,0)
    elif op=="MISSION64_RESUME":
        before=mission64_read()
        if before["state"] not in {"PAUSED","CONVERGING"}: raise Deny("MISSION64_RESUME_STATE:"+before["state"])
        for i,_,n in MISSION64_LOGICAL: mission64_kubectl(["scale","deployment",i.lower()+"-worker","-n",MISSION64_NAMESPACE,f"--replicas={n}"],timeout=30)
        result=mission64_wait(64,64)
    elif op=="MISSION64_RESTART_ONE":
        before=mission64_read();name=request.get("pod_name")
        row=next((x for x in before.get("pods",[]) if x.get("name")==name),None)
        if row is None or not re.fullmatch(r"ld(?:0[1-9]|1[0-2])-worker-[a-z0-9-]+",str(name)): raise Deny("MISSION64_POD_NAME_DENIED")
        old_uid=row["uid"];mission64_kubectl(["delete","pod",name,"-n",MISSION64_NAMESPACE,"--wait=false"],timeout=30)
        result=mission64_wait(64,64)
        if any(x.get("uid")==old_uid for x in result["pods"]): raise Deny("MISSION64_RESTART_UID_UNCHANGED")
        result["restarted_pod"]=name;result["old_uid"]=old_uid
    elif op=="MISSION64_VALIDATE": result=mission64_validate_execution()
    elif op=="MISSION64_STOP":
        mission64_kubectl(["delete","namespace",MISSION64_NAMESPACE,"--ignore-not-found=true","--wait=true","--timeout=120s"],timeout=140)
        result=mission64_read()
        if result["state"]!="ABSENT": raise Deny("MISSION64_STOP_NOT_ABSENT")
    else: raise Deny("MISSION64_OPERATION_UNREACHABLE")
    result.update(mission64_receipt(request,result));return result
# ---- end Mission64 extension ----------------------------------------------



# ---- Epoch3 Closure exact mission-scoped Kubernetes materializer ---------
E3_ID="EPOCH3-CLOSURE-DOCS-FEDERATION-GITHUB-R1"
E3_NAMESPACE="lion-epoch3-closure-r1"
E3_LPCL_DIGEST="be0c4204b0aeffa5db61019128f70b092db5d62ed4c4e6936b41d430a1b67951"
E3_LOGICAL=(
 ("LD01","MISSION_PLANNER",6),("LD02","AUTHORITY_CURRENTNESS",6),("LD03","FEDERATION_CURRENTNESS",6),("LD04","GITHUB_LINEAGE_AND_BRANCH",6),
 ("LD05","ARCHITECTURE_DOCUMENTATION",5),("LD06","SOURCE_PROVENANCE",5),("LD07","LOCAL_MODEL_DELEGATION",5),("LD08","MATERIAL_SCHEDULER",5),
 ("LD09","SECURITY_FALSIFIER",5),("LD10","VALIDATION",5),("LD11","PUBLICATION_AND_RECOVERY",5),("LD12","RECONCILIATION_AND_CARRIER",5),
)
E3_STATE=STATE_ROOT/"epoch3-closure-r1"

def e3_spec():
 v={"schema_version":"1.0.0","mission_id":E3_ID,"namespace":E3_NAMESPACE,"lpcl_digest":E3_LPCL_DIGEST,
    "logical_drones":[{"id":i,"role":r,"replicas":n} for i,r,n in E3_LOGICAL],"logical_drone_count":12,"material_pod_count":64,
    "image":MISSION64_IMAGE,"network":"DENY_ALL","authority_effect":"MISSION_SCOPED_K3S"}
 v["material_spec_digest"]=sha256(canonical(v));return v

def e3_require(request,worker=False):
 exp={"schema_version","request_id","operation","mission_id","source_head","source_tree","spec_digest"}
 if worker: exp.add("pod_name")
 if set(request)!=exp: raise Deny("E3_FIELD_SET")
 if request.get("mission_id")!=E3_ID: raise Deny("E3_ID_MISMATCH")
 if request.get("spec_digest")!=E3_LPCL_DIGEST: raise Deny("E3_LPCL_DIGEST_MISMATCH")
 head=require_hex40(request.get("source_head"),"source_head");tree=require_hex40(request.get("source_tree"),"source_tree")
 mission64_verify_current(head,tree)
 return head,tree

def e3_manifest():
 docs=[];labels={"lion.openai/epoch3":"true","lion.openai/spec":E3_LPCL_DIGEST[:16]}
 docs.append({"apiVersion":"v1","kind":"Namespace","metadata":{"name":E3_NAMESPACE,"labels":labels}})
 for lid,role,repl in E3_LOGICAL:
  name="e3-"+lid.lower()+"-worker";pl={**labels,"app":name,"component":"epoch3-material-drone","logical-drone":lid.lower()}
  docs.append({"apiVersion":"apps/v1","kind":"Deployment","metadata":{"name":name,"namespace":E3_NAMESPACE,"labels":pl},"spec":{"replicas":repl,"selector":{"matchLabels":{"app":name}},"strategy":{"type":"RollingUpdate","rollingUpdate":{"maxUnavailable":1,"maxSurge":1}},"template":{"metadata":{"labels":pl},"spec":{"automountServiceAccountToken":False,"terminationGracePeriodSeconds":3,"securityContext":{"runAsNonRoot":True,"runAsUser":1000,"runAsGroup":1000,"seccompProfile":{"type":"RuntimeDefault"}},"containers":[{"name":"drone","image":MISSION64_IMAGE,"imagePullPolicy":"IfNotPresent","command":["/bin/sh","-ec","echo MISSION=$MISSION_ID LOGICAL=$LOGICAL_DRONE ROLE=$LOGICAL_ROLE POD=$POD_NAME; while true; do sleep 3600; done"],"env":[{"name":"MISSION_ID","value":E3_ID},{"name":"LOGICAL_DRONE","value":lid},{"name":"LOGICAL_ROLE","value":role},{"name":"POD_NAME","valueFrom":{"fieldRef":{"fieldPath":"metadata.name"}}}],"resources":{"requests":{"cpu":"1m","memory":"8Mi"},"limits":{"cpu":"50m","memory":"32Mi"}},"securityContext":{"allowPrivilegeEscalation":False,"readOnlyRootFilesystem":True,"runAsNonRoot":True,"runAsUser":1000,"capabilities":{"drop":["ALL"]}}}]}}}})
 docs.append({"apiVersion":"networking.k8s.io/v1","kind":"NetworkPolicy","metadata":{"name":"deny-all","namespace":E3_NAMESPACE},"spec":{"podSelector":{},"policyTypes":["Ingress","Egress"],"ingress":[],"egress":[]}})
 return {"apiVersion":"v1","kind":"List","items":docs}

def e3_validate_manifest(v):
 deps=[x for x in v.get("items",[]) if x.get("kind")=="Deployment"]
 if len(deps)!=12 or sum(int(x["spec"]["replicas"]) for x in deps)!=64: raise Deny("E3_CARDINALITY")
 if [int(x["spec"]["replicas"]) for x in deps] != [x[2] for x in E3_LOGICAL]: raise Deny("E3_DISTRIBUTION")
 for d in deps:
  ps=d["spec"]["template"]["spec"]
  if ps.get("automountServiceAccountToken") is not False: raise Deny("E3_SERVICE_ACCOUNT")
  for forbidden in ("hostNetwork","hostPID","hostIPC"):
   if ps.get(forbidden) is True: raise Deny("E3_HOST_NAMESPACE")
  for vol in ps.get("volumes",[]) or []:
   if "hostPath" in vol: raise Deny("E3_HOSTPATH")
  c=ps["containers"][0];sc=c.get("securityContext") or {}
  if c.get("image")!=MISSION64_IMAGE or sc.get("allowPrivilegeEscalation") is not False or sc.get("readOnlyRootFilesystem") is not True or sc.get("runAsNonRoot") is not True or (sc.get("capabilities") or {}).get("drop") != ["ALL"]: raise Deny("E3_SECURITY")
 nps=[x for x in v.get("items",[]) if x.get("kind")=="NetworkPolicy"]
 if len(nps)!=1 or nps[0]["spec"].get("ingress")!=[] or nps[0]["spec"].get("egress")!=[]: raise Deny("E3_NETWORK")

def e3_rows():
 p=mission64_kubectl(["get","pods","-n",E3_NAMESPACE,"-l","component=epoch3-material-drone","-o","json"],timeout=30,check=False)
 if p.returncode!=0:
  t=(p.stderr or p.stdout).decode("utf-8","replace").lower()
  if "not found" in t or "notfound" in t:return []
  raise Deny("E3_POD_READ:"+t[-1200:])
 data=json.loads(p.stdout.decode());out=[]
 for x in data.get("items",[]):
  m=x.get("metadata") or {};st=x.get("status") or {};lab=m.get("labels") or {};ready=any(c.get("type")=="Ready" and c.get("status")=="True" for c in st.get("conditions",[]) or [])
  out.append({"name":m.get("name"),"uid":m.get("uid"),"logical_drone":lab.get("logical-drone"),"phase":st.get("phase"),"ready":ready,"pod_ip":st.get("podIP"),"restarts":sum(int(c.get("restartCount",0) or 0) for c in st.get("containerStatuses",[]) or [])})
 return sorted(out,key=lambda x:x.get("name") or "")

def e3_read():
 ks=mission64_k3s_state()
 if not ks["service_active"] or not ks["kubeconfig_exists"]: return {"mission_id":E3_ID,"spec_digest":E3_LPCL_DIGEST,"state":"K3S_NOT_RUNNING","logical_drones":12,"materialized":0,"ready":0,"pods":[],"k3s":ks}
 ns=mission64_kubectl(["get","namespace",E3_NAMESPACE,"-o","json"],timeout=15,check=False)
 if ns.returncode!=0:return {"mission_id":E3_ID,"spec_digest":E3_LPCL_DIGEST,"state":"ABSENT","logical_drones":12,"materialized":0,"ready":0,"pods":[],"k3s":ks}
 pods=e3_rows();ready=sum(1 for x in pods if x["ready"]);state="RUNNING" if len(pods)==64 and ready==64 else "CONVERGING"
 return {"mission_id":E3_ID,"spec_digest":E3_LPCL_DIGEST,"material_spec_digest":e3_spec()["material_spec_digest"],"state":state,"logical_drones":12,"materialized":len(pods),"ready":ready,"unique_uid_count":len({x['uid'] for x in pods if x.get('uid')}),"pods":pods,"k3s":ks}

def e3_wait(timeout=180):
 import time as _time;end=_time.time()+timeout;last=None
 while _time.time()<end:
  last=e3_read()
  if last.get("materialized")==64 and last.get("ready")==64:return last
  _time.sleep(2)
 raise Deny("E3_CONVERGENCE_TIMEOUT:"+json.dumps(last or {}))


def e3_wait_restarted_uid(old_uid,timeout=180,poll_interval=2):
 import time as _time;end=_time.time()+timeout;last=None
 while _time.time()<end:
  last=e3_read();pods=last.get("pods") or []
  old_present=any(x.get("uid")==old_uid for x in pods)
  if last.get("materialized")==64 and last.get("ready")==64 and last.get("unique_uid_count")==64 and not old_present:return last
  _time.sleep(poll_interval)
 evidence={"old_uid":old_uid,"old_uid_present":bool(last and any(x.get("uid")==old_uid for x in (last.get("pods") or []))),"materialized":(last or {}).get("materialized"),"ready":(last or {}).get("ready"),"unique_uid_count":(last or {}).get("unique_uid_count")}
 raise Deny("E3_RESTART_REPLACEMENT_TIMEOUT:"+json.dumps(evidence,sort_keys=True))

def e3_receipt(req,res):
 payload={"schema_version":"1.0.0","timestamp":now(),"request_id":req["request_id"],"operation":req["operation"],"mission_id":E3_ID,"lpcl_digest":E3_LPCL_DIGEST,"source_head":req.get("source_head"),"source_tree":req.get("source_tree"),"result_digest":sha256(canonical(res)),"authority":"EXPLICIT_UI_ACTIVATION"};payload["receipt_digest"]=sha256(canonical(payload));atomic_json(E3_STATE/"receipts"/(req["request_id"]+".json"),payload);return {"control_receipt":payload}

def e3_validate_execution():
 runtime=e3_read()
 if runtime.get("state")!="RUNNING" or runtime.get("ready")!=64 or runtime.get("unique_uid_count")!=64:raise Deny("E3_VALIDATE_NOT_READY")
 roles={i.lower():r for i,r,_ in E3_LOGICAL};rows=[];fails=[]
 for pod in runtime["pods"]:
  name=pod["name"];lid=pod["logical_drone"];role=roles.get(lid);p=mission64_kubectl(["logs",name,"-n",E3_NAMESPACE,"--tail=10"],timeout=15,check=False);text=(p.stdout if p.returncode==0 else p.stderr).decode("utf-8","replace")[-4096:];expected=f"MISSION={E3_ID} LOGICAL={lid.upper()} ROLE={role} POD={name}";ok=p.returncode==0 and expected in text;rows.append({"pod":name,"uid":pod.get("uid"),"logical_drone":lid.upper(),"role":role,"receipt_line_sha256":sha256(expected.encode()),"ok":ok});
  if not ok:fails.append({"pod":name,"tail":text[-300:]})
 if fails:raise Deny("E3_EXECUTION_VALIDATION_FAILED:"+json.dumps(fails[:5]))
 return {"mission_id":E3_ID,"validated_pods":64,"logical_drones":12,"ready":64,"unique_uid_count":64,"execution_digest":sha256(canonical(rows)),"rows":rows,"authority_effect":"NONE"}

def e3_component_handle(req):
 op=req.get("operation")
 expected={"schema_version","request_id","operation","mission_id","source_head","source_tree","spec_digest","logical_id"}
 if set(req)!=expected:raise Deny("E3_COMPONENT_FIELD_SET")
 if req.get("mission_id")!=E3_ID:raise Deny("E3_ID_MISMATCH")
 if req.get("spec_digest")!=E3_LPCL_DIGEST:raise Deny("E3_LPCL_DIGEST_MISMATCH")
 head=require_hex40(req.get("source_head"),"source_head");tree=require_hex40(req.get("source_tree"),"source_tree")
 mission64_verify_current(head,tree)
 lid=str(req.get("logical_id") or "").upper()
 row=next((x for x in E3_LOGICAL if x[0]==lid),None)
 if row is None:raise Deny("E3_LOGICAL_ID_DENIED")
 role,expected_replicas=row[1],row[2];dep="e3-"+lid.lower()+"-worker"
 def component_rows():return [x for x in e3_rows() if str(x.get("logical_drone") or "").upper()==lid]
 def wait_component(timeout=120,old_uids=None):
  import time as _time;end=_time.time()+timeout;last=[]
  while _time.time()<end:
   last=component_rows();ready=sum(1 for x in last if x.get("ready"));uids={x.get("uid") for x in last if x.get("uid")}
   if len(last)==expected_replicas and ready==expected_replicas and (old_uids is None or uids!=old_uids):return last
   _time.sleep(2)
  raise Deny("E3_COMPONENT_CONVERGENCE_TIMEOUT:"+lid+":"+json.dumps({"materialized":len(last),"ready":sum(1 for x in last if x.get('ready'))}))
 before=component_rows();before_uids={x.get("uid") for x in before if x.get("uid")}
 if op=="EPOCH3_M64_START_LOGICAL":
  mission64_kubectl(["scale","deployment",dep,"-n",E3_NAMESPACE,f"--replicas={expected_replicas}"],timeout=30);after=wait_component()
 elif op=="EPOCH3_M64_RESTART_LOGICAL":
  mission64_kubectl(["rollout","restart","deployment/"+dep,"-n",E3_NAMESPACE],timeout=30);after=wait_component(old_uids=before_uids)
 elif op=="EPOCH3_M64_VALIDATE_LOGICAL":after=wait_component()
 else:raise Deny("E3_COMPONENT_OPERATION")
 res={"mission_id":E3_ID,"logical_id":lid,"role":role,"operation":op,"expected":expected_replicas,"materialized":len(after),"ready":sum(1 for x in after if x.get('ready')),"uids":sorted(x.get('uid') for x in after if x.get('uid')),"authority_effect":"MISSION_SCOPED_K3S" if op!="EPOCH3_M64_VALIDATE_LOGICAL" else "NONE"}
 res.update(e3_receipt(req,res));return res

def e3_handle(req):
 op=req["operation"];head,tree=e3_require(req,worker=op=="EPOCH3_M64_RESTART_ONE")
 if op=="EPOCH3_M64_PRECHECK":res={"source_head":head,"source_tree":tree,"spec":e3_spec(),"k3s":mission64_k3s_state(),"runtime":e3_read()}
 elif op=="EPOCH3_M64_START":
  mission64_start_k3s();before=e3_read()
  if before["state"]=="RUNNING":res=before;res["idempotent"]=True
  else:
   manifest=e3_manifest();e3_validate_manifest(manifest);raw=canonical(manifest);mission64_kubectl(["apply","-f","-"],payload=raw,timeout=180);res=e3_wait();res["manifest_sha256"]=sha256(raw)
 elif op=="EPOCH3_M64_READ":res=e3_read()
 elif op=="EPOCH3_M64_RESTART_ONE":
  before=e3_read();name=req.get("pod_name");row=next((x for x in before.get("pods",[]) if x.get("name")==name),None)
  if row is None or not re.fullmatch(r"e3-ld(?:0[1-9]|1[0-2])-worker-[a-z0-9-]+",str(name)):raise Deny("E3_POD_NAME_DENIED")
  old=row["uid"];lid=str(row.get("logical_drone") or "").upper();before_role_uids={x.get("uid") for x in before.get("pods",[]) if str(x.get("logical_drone") or "").upper()==lid and x.get("uid")}
  mission64_kubectl(["delete","pod",name,"-n",E3_NAMESPACE,"--wait=false"],timeout=30);res=e3_wait_restarted_uid(old)
  after_role=[x for x in res.get("pods",[]) if str(x.get("logical_drone") or "").upper()==lid];after_role_uids={x.get("uid") for x in after_role if x.get("uid")};new_uids=after_role_uids-before_role_uids
  if len(new_uids)!=1:raise Deny("E3_RESTART_REPLACEMENT_IDENTITY_AMBIGUOUS:"+json.dumps({"logical_id":lid,"old_uid":old,"new_uids":sorted(new_uids)}))
  replacement_uid=next(iter(new_uids));replacement=next(x for x in after_role if x.get("uid")==replacement_uid)
  res["restarted_pod"]=name;res["old_uid"]=old;res["replacement_pod"]=replacement.get("name");res["replacement_uid"]=replacement_uid;res["restart_identity_verified"]=True
 elif op=="EPOCH3_M64_VALIDATE":res=e3_validate_execution()
 elif op=="EPOCH3_M64_STOP":
  mission64_kubectl(["delete","namespace",E3_NAMESPACE,"--ignore-not-found=true","--wait=true","--timeout=120s"],timeout=140);res=e3_read()
  if res["state"]!="ABSENT":raise Deny("E3_STOP_NOT_ABSENT")
 else:raise Deny("E3_OPERATION_UNREACHABLE")
 res.update(e3_receipt(req,res));return res
# ---- end Epoch3 materializer ---------------------------------------------



MISSION_CONTROL_V3_ROOT=Path("/var/lib/sentinelx/uploads/lion-mission-control-v3")
MISSION_CONTROL_V3_STAGE_ROOT=Path("/var/lib/sentinelx/uploads/lion-mission-control-v3.stage-current-master")
MISSION_CONTROL_V3_DEPLOY_STATE=STATE_ROOT/"mission-control-v3-deployment"
MISSION_CONTROL_V3_STAGE_IDENTITY=".lion-stage-identity.json"
MISSION_CONTROL_V3_REQUIRED_SHA256={"cyber_lion/contracts/action_ir.py":"ee019272301ab2b5b334ee386bc779d60c9279b20b301a8581917305faf75be8","cyber_lion/contracts/action_proposal_context.py":"b03a67a25ebee4dd2010002e33559d0f0b10baf9201c1750234794e1995ef97e","cyber_lion/contracts/action_proposal_projection.py":"9e41151578fb1d56588f1a061442ccb8a641bd0f25e4cbf37a6aa02a5a570da7","cyber_lion/contracts/action_runtime_binding.py":"5d08a7395b9d841fcbe1fa80a9394e7d97619fa4cfd6479ca2ee3d8a9a521a16","cyber_lion/contracts/builder_process_launch.py":"5b3e13cd3ae5228d8f4111c99d8282a93ddd9b7ac8cafc20ea701e05ca82fb21","cyber_lion/contracts/cognitive_continuity.py":"5a19dd7d12034f502c527ae9121f942640930e85b97949528dd0d63af6609b20","cyber_lion/contracts/enterprise_graph.py":"669b595200ae82639fd9934e3b2ff58f1c99db7836d288d66a3bd1d98c1c168d","cyber_lion/contracts/executor_provisioning.py":"a0b5035e633a869ac6b510f718751bd1c6502f532394ad54d3f470e19983a157","cyber_lion/contracts/executor_sandbox.py":"53a35d6ccdd4f5207b5617454bf867047c78e1029e977f8b318ca7841184d8f5","cyber_lion/contracts/mission_contract_profiles.py":"285baa010c458f01232649fde3510ac705e18692c6e13d0e2039bc35f083c580","cyber_lion/contracts/operator_intervention.py":"71894ed53a54bec256a6065c751d03cdd2dfbc2e784a9157bb3a8d3c0e9d953e","cyber_lion/contracts/phase_execution_contract.py":"2fdb1d0443bca3cd2f216338aa5d8f09febe9d6c9f35e562c24b3799cd36ecb6","cyber_lion/contracts/policy_gate.py":"0f344c74deff44fb5924ef6baa3416719e7458fa5aa3a7ad66bd75894f9ba34d","cyber_lion/contracts/process_ir.py":"be76382240e6ac0f874e122583a12340c5f92d0a92c3ced3ca6e9e23e3297529","cyber_lion/contracts/repository_maintenance_sandbox.py":"884894f071aab6d06bd9dc271348e9a3aeb1bfbce458b9182345535909099804","cyber_lion/contracts/runtime_currentness.py":"19cdb8f256b6aaf0e132aa0dea304cbfcde1958b7292b6f4744e4fe17719119e","cyber_lion/contracts/runtime_enforcement.py":"def310ff94cecbd98da16771b728ad81bc8304757416092811b748bda5fdeff0","cyber_lion/contracts/runtime_execution.py":"7ec7add190f19893a5486b0bc2a6dec221a55e97d99cd7c7424261b82a505fdf","cyber_lion/contracts/swarm_status.py":"ea6240ee37766d846cbad0f775b66d3f17ed2cf74436639f8bcbec202c1508cf","cyber_lion/enterprise/authority_grant.py":"05745e2f2c5da34fb46a36ee96f74b4bfbbf7708666dcd0530d04d140687bb00","cyber_lion/enterprise/authority_source.py":"00421095169e36746b439ab9b17c0a2bd04f016a6c59b256f9795e976e8f823a","cyber_lion/enterprise/authority_source_adapter.py":"f9df79b8dbf967dbb836f2b2346da7f77f9ae99dae10d780007122e5aef35079","cyber_lion/enterprise/authority_verification.py":"5ce8648e578cd25df2d7b9aea812c41c7776a33ba5310190f810c61dd55046cf","cyber_lion/enterprise/control_plane.py":"a575c69d1de1a35e2c7e7067ac4a5d228ca2e5b249546dbba3da55ab7f6e37eb","cyber_lion/enterprise/cooperative_context_resolver.py":"84c669b7eaef07250e770135d91aa328c5b18c30ca7404da677dd5a24489a0a6","cyber_lion/enterprise/cooperative_control_plane_materializer.py":"5f2fb77183cae45d9e0b7071d5dcb55d211d36a96cf94b58926b033d68846da6","cyber_lion/enterprise/cooperative_dependency_provider.py":"35d7609382682a6ccf6323fe0f5468987060afe89f4203ee7b5986f70c946abb","cyber_lion/enterprise/cooperative_provider_materialization.py":"b10f9689fe8beb0071ca448e66239d2318c430eeeec3a5b7a61b743158e558a5","cyber_lion/enterprise/cooperative_runtime_composition.py":"7fbc60740e8e23bd29dfb7729ca4a8073966ec053c99289195935fdb8d94f91d","cyber_lion/enterprise/cooperative_runtime_evidence_exporter.py":"3e0e174f513baaad18c2a69fb54eb067b7f696d11c012617b69efbc45f004e86","cyber_lion/enterprise/cooperative_runtime_evidence_sources.py":"5cbd0642e751aced9660b765f7d667bbfd2c27f83b24f3c82a4652275bc9d6ef","cyber_lion/enterprise/cooperative_runtime_preparation_provider.py":"7cd30cec01a01b7da1fa912828ac109fe07d4301dc4b50c8a17c56de21695a89","cyber_lion/enterprise/cooperative_runtime_preparer.py":"f83358e848ccbc477490a6884a07ea5dad71b0fae2f9d0c6b52e9205b0c93201","cyber_lion/enterprise/cooperative_runtime_root.py":"834055f1f7de29a9cff02b8c749e204a8b5f247130ae825060331e0343671e20","cyber_lion/enterprise/cooperative_runtime_writer.py":"1a2bc1d2a6d6465905a714ecec97d653750c0df97560269a81921798d81eb7c3","cyber_lion/enterprise/executor_sandbox.py":"26a5b2e31cc96dca90023c2e871ad950efd019174b50ea6fbbbb46c5e1dfdebe","cyber_lion/enterprise/live_authority_admission.py":"66116735855668e2fe5af0760c985bf41b63cac6605d0c80e78111ac53488f39","cyber_lion/enterprise/models.py":"e342492b276b2e43875519749154106b51712d3983f22912013f7b381343d45a","cyber_lion/enterprise/persistent_authority_state.py":"5e79eca835a3ff772f1f06c65dc394207223a9718b5eff06157ea60d1623369f","cyber_lion/enterprise/policy_gate.py":"4c5acc3573a6043b8202ff207a3155713ce1a5faa54af454129ddbd4045dc4d2","cyber_lion/enterprise/runtime_currentness.py":"69c5c2a8f4ce620ce1a6f8c89d85afd2e19104d12afa8b6514900e7e92271a36","cyber_lion/enterprise/runtime_enforcement.py":"a77497e312ac9450ea7c8f46d7c8e8ceb433f81450646e1766d6731cc280b086","cyber_lion/enterprise/runtime_execution.py":"d04c90d6c661a30e42e38b7d37f822f826e0fb720d5a72c4794a57211dc3f484","cyber_lion/enterprise/swarm_status_projection.py":"95d4868287a86e5527ddd998ffb00055d197fde02b4665e25105c776cfd27559","cyber_lion/enterprise/trusted_control_plane_providers.py":"e5d42ef3ba8b3e0a9ec973aef1082d15d5d34dae4d8b26754a556fe51f74a055","cyber_lion/enterprise/trusted_control_plane_service.py":"6e0e16842817c86fdcff4caaf6cc1f7477a4b88a3a51b0406664ffcb3fb505fa","cyber_lion/mission_control/__init__.py":"8d83b68f7ef8047dc9448bbd9ea0335a5a427fd6d6a3b2707c77a90d76f0448c","cyber_lion/mission_control/artifact_transfer.py":"1bee7f17dd0bffd88d89436f16b50b9811a2ff37ffae42971a64260475a578ba","cyber_lion/mission_control/control_plane_reconnaissance.py":"c44a30d3505aba200c000a72e4bb6129d76ad0dc3136a1a0a7ffe250bb3ebc7c","cyber_lion/mission_control/cooperative_artifacts.py":"bc84a9fe3cbd3892477c948101bc7c02b6126e7c04af1b918a28696f0de6fe6d","cyber_lion/mission_control/cooperative_materialization_registry.py":"6f9093422b1a1fc6657d916ff6b31b9a497dd66dfca03df95b667c424ffdb1f6","cyber_lion/mission_control/cooperative_preactivation.py":"45c082d45e024e43edc62e2f5f555d11eb1c8f2438e66ae1686a865f76c2245a","cyber_lion/mission_control/cooperative_preactivation_bootstrap.py":"7c9252ca92ad0f0f08d42fc9d5d2b9e0cafc1dff87e0527e1a81214ae489afbb","cyber_lion/mission_control/cooperative_process_bootstrap.py":"067ea3d9e8b04ace11e709f60951649d97d759efda20846565aa5407b31935c8","cyber_lion/mission_control/cooperative_production.py":"19cea3dd4e32ce4cb88963799113a93d70ecb372fa6ea11ed68493ab05b6c450","cyber_lion/mission_control/cooperative_readiness.py":"c7fd62ee216d23b5fffba80b4e0a47f32b467293146d5793a3e44d7e2b7841e1","cyber_lion/mission_control/cooperative_worker_bootstrap.py":"6840116fb24f36033f02deea3cb482468f69cdcfbd62209b02e017cce64d9717","cyber_lion/mission_control/cooperative_worker_runtime.py":"0df864ba28771c073d3c887ad82862806d83c454f26f14100eafca89f8ba12d7","cyber_lion/mission_control/dual_result_join.py":"7ce631308f4150525330a56421c55353906d49ad2217206fa4d7ff314bb8139f","cyber_lion/mission_control/execution_driver.py":"b666feb64277895b1861ab341caae1aa0acc09d463e396c75e5aa8797746dd5f","cyber_lion/mission_control/execution_driver_contract.py":"aa5c7390960c835968b72eb28be76b8e2e5d0e83bc9d66fe01fdc5bd13f79821","cyber_lion/mission_control/global_scheduler.py":"70742f0173d8965d4d190a3da52ede0261024547bb4babc51e55b31f300fd73f","cyber_lion/mission_control/lpcl_runtime_selection.py":"3804b73c8d12378538f4e3c51897c557c4d3220003ff74d54f9a78386730bff1","cyber_lion/mission_control/mission_reconciliation.py":"69066f4ef61bd3f7283c8077d20059f102ddc1291fc824edbd418993580e31ea","cyber_lion/mission_control/model_calls.py":"f5dea5c27eb0903134e6d72b775794d6dd0f7303d6ee2fc56a6097b618e334b7","cyber_lion/mission_control/operator_control.py":"694ca04ba6f7ff19375a3d378eb7d4bc17d16c82afa784bd28a85713f431a697","cyber_lion/mission_control/operator_swarm_session.py":"1f473ba8e935412e8491734f1de72d73d02934517275953502cffb08e0060ef8","cyber_lion/mission_control/phase_control.py":"89372056bf7668edc473b0b0dc04433d376dca3e041499fc0b4e6a52f69c319e","cyber_lion/mission_control/runtime_projection.py":"9a6d9d62c25bbc4a3c15aeb1731223fc7c08e62bf8099717a9c58e85aab0ed24","cyber_lion/mission_control/supervisor_projection.py":"d6ffc5c07caf5db6e4040c38962987c3c0c6effb2bfb022e88373c71e773fb80","cyber_lion/process_language/lpcl.py":"355af5b4073378adc4cc35254de4fc59ed6371fa125b3ffd27070a09ecad4b91","lion_firefox_broker_relay.py":"be178c21e5f5ee8cffb7afa2b902fd622351f4dca84bc0f2384f1cb6ac7daf03","lion_mission_lifecycle_db.py":"0ca42b937a21c498e9016e3f255ee796b30268ccff3dea642a468e293814a35a","lion_operator_client.py":"3171b674986015dc1c0e2ba5fa8907c669f1f655c0f0f7e6cecfe6bd7fc3ec0b","lion_operator_containment_helper.py":"378c1b36cc2ad3008cb17ad882039af9fd4ad49b3b3b41a2143a5c3615b705d8","lion_operator_gateway.py":"0a19c0f169e33e863e956013d46899805305407272319251fa478a56243e2279","lion_operator_provision.py":"b8486fc03be70baabb0801a2a02d068152208afc10ea5cc626d567266e23154a","lion_saas_broker.py":"a8d35ac62e93fa0054dd8aad367ec55f98b576faa3d503340c867b5de761da8b","lion_saas_session_bridge.py":"4b41e592d381c78a4cea528dce50de616c6d565b0741ac6b17f7fb5fc373a3d7","mission_control_compat.py":"f584066806fd190ff4f1752ab464e0d245172a56789f7852f0ed0df0e2fe93d0","mission_control_v3.py":"4dab86001b26f6be1474cd5113a8d59ed2c53ee29d2b522babcbb66c6b067b63","static/app.css":"f3c2351074e9a260063b6d3962bcd71b50f7ff48dd788cf4d18f9bab1816e0cf","static/app.js":"3baea82b0e2c8ae4d9b0eca36be2f7c755462b245e59c092adec47d85934ff9d","static/control-v3.js":"e7aaa6c32251df70079eb6af838e6c541f0835928d90ce06376cc22fe9041de0","static/index.html":"9edd4ab6317273c499e11fdb9b79a894ab2b13bdb0ae32f36ab2c9df0950954a","static/passive.js":"4d1ee6e0fafd2467c6c65c8ce69079e403a4464a57a37dc8de14447a67db1465","systemd/lion-operator-control.service":"48087f928e38a693852603c1f95ada80635bc13bc58da6b7a9b03aee0fbfd700","tools/lion_cooperative_worker_adapter.py":"ce1b178e79297ea286bbc0118c65133b8265aff8ae4ff8926de36e6c21c88cda","tools/lion_mission_lifecycle_db.py":"0ca42b937a21c498e9016e3f255ee796b30268ccff3dea642a468e293814a35a","tools/lion_saas_broker.py":"a8d35ac62e93fa0054dd8aad367ec55f98b576faa3d503340c867b5de761da8b","tools/lion_saas_session_bridge.py":"4b41e592d381c78a4cea528dce50de616c6d565b0741ac6b17f7fb5fc373a3d7"}
MISSION_CONTROL_V3_SOURCE_MAP={"cyber_lion/contracts/action_ir.py":"cyber_lion/contracts/action_ir.py","cyber_lion/contracts/action_proposal_context.py":"cyber_lion/contracts/action_proposal_context.py","cyber_lion/contracts/action_proposal_projection.py":"cyber_lion/contracts/action_proposal_projection.py","cyber_lion/contracts/action_runtime_binding.py":"cyber_lion/contracts/action_runtime_binding.py","cyber_lion/contracts/builder_process_launch.py":"cyber_lion/contracts/builder_process_launch.py","cyber_lion/contracts/cognitive_continuity.py":"cyber_lion/contracts/cognitive_continuity.py","cyber_lion/contracts/enterprise_graph.py":"cyber_lion/contracts/enterprise_graph.py","cyber_lion/contracts/executor_provisioning.py":"cyber_lion/contracts/executor_provisioning.py","cyber_lion/contracts/executor_sandbox.py":"cyber_lion/contracts/executor_sandbox.py","cyber_lion/contracts/mission_contract_profiles.py":"cyber_lion/contracts/mission_contract_profiles.py","cyber_lion/contracts/operator_intervention.py":"cyber_lion/contracts/operator_intervention.py","cyber_lion/contracts/phase_execution_contract.py":"cyber_lion/contracts/phase_execution_contract.py","cyber_lion/contracts/policy_gate.py":"cyber_lion/contracts/policy_gate.py","cyber_lion/contracts/process_ir.py":"cyber_lion/contracts/process_ir.py","cyber_lion/contracts/repository_maintenance_sandbox.py":"cyber_lion/contracts/repository_maintenance_sandbox.py","cyber_lion/contracts/runtime_currentness.py":"cyber_lion/contracts/runtime_currentness.py","cyber_lion/contracts/runtime_enforcement.py":"cyber_lion/contracts/runtime_enforcement.py","cyber_lion/contracts/runtime_execution.py":"cyber_lion/contracts/runtime_execution.py","cyber_lion/contracts/swarm_status.py":"cyber_lion/contracts/swarm_status.py","cyber_lion/enterprise/authority_grant.py":"cyber_lion/enterprise/authority_grant.py","cyber_lion/enterprise/authority_source.py":"cyber_lion/enterprise/authority_source.py","cyber_lion/enterprise/authority_source_adapter.py":"cyber_lion/enterprise/authority_source_adapter.py","cyber_lion/enterprise/authority_verification.py":"cyber_lion/enterprise/authority_verification.py","cyber_lion/enterprise/control_plane.py":"cyber_lion/enterprise/control_plane.py","cyber_lion/enterprise/cooperative_context_resolver.py":"cyber_lion/enterprise/cooperative_context_resolver.py","cyber_lion/enterprise/cooperative_control_plane_materializer.py":"cyber_lion/enterprise/cooperative_control_plane_materializer.py","cyber_lion/enterprise/cooperative_dependency_provider.py":"cyber_lion/enterprise/cooperative_dependency_provider.py","cyber_lion/enterprise/cooperative_provider_materialization.py":"cyber_lion/enterprise/cooperative_provider_materialization.py","cyber_lion/enterprise/cooperative_runtime_composition.py":"cyber_lion/enterprise/cooperative_runtime_composition.py","cyber_lion/enterprise/cooperative_runtime_evidence_exporter.py":"cyber_lion/enterprise/cooperative_runtime_evidence_exporter.py","cyber_lion/enterprise/cooperative_runtime_evidence_sources.py":"cyber_lion/enterprise/cooperative_runtime_evidence_sources.py","cyber_lion/enterprise/cooperative_runtime_preparation_provider.py":"cyber_lion/enterprise/cooperative_runtime_preparation_provider.py","cyber_lion/enterprise/cooperative_runtime_preparer.py":"cyber_lion/enterprise/cooperative_runtime_preparer.py","cyber_lion/enterprise/cooperative_runtime_root.py":"cyber_lion/enterprise/cooperative_runtime_root.py","cyber_lion/enterprise/cooperative_runtime_writer.py":"cyber_lion/enterprise/cooperative_runtime_writer.py","cyber_lion/enterprise/executor_sandbox.py":"cyber_lion/enterprise/executor_sandbox.py","cyber_lion/enterprise/live_authority_admission.py":"cyber_lion/enterprise/live_authority_admission.py","cyber_lion/enterprise/models.py":"cyber_lion/enterprise/models.py","cyber_lion/enterprise/persistent_authority_state.py":"cyber_lion/enterprise/persistent_authority_state.py","cyber_lion/enterprise/policy_gate.py":"cyber_lion/enterprise/policy_gate.py","cyber_lion/enterprise/runtime_currentness.py":"cyber_lion/enterprise/runtime_currentness.py","cyber_lion/enterprise/runtime_enforcement.py":"cyber_lion/enterprise/runtime_enforcement.py","cyber_lion/enterprise/runtime_execution.py":"cyber_lion/enterprise/runtime_execution.py","cyber_lion/enterprise/swarm_status_projection.py":"cyber_lion/enterprise/swarm_status_projection.py","cyber_lion/enterprise/trusted_control_plane_providers.py":"cyber_lion/enterprise/trusted_control_plane_providers.py","cyber_lion/enterprise/trusted_control_plane_service.py":"cyber_lion/enterprise/trusted_control_plane_service.py","cyber_lion/mission_control/__init__.py":"cyber_lion/mission_control/__init__.py","cyber_lion/mission_control/artifact_transfer.py":"cyber_lion/mission_control/artifact_transfer.py","cyber_lion/mission_control/control_plane_reconnaissance.py":"cyber_lion/mission_control/control_plane_reconnaissance.py","cyber_lion/mission_control/cooperative_artifacts.py":"cyber_lion/mission_control/cooperative_artifacts.py","cyber_lion/mission_control/cooperative_materialization_registry.py":"cyber_lion/mission_control/cooperative_materialization_registry.py","cyber_lion/mission_control/cooperative_preactivation.py":"cyber_lion/mission_control/cooperative_preactivation.py","cyber_lion/mission_control/cooperative_preactivation_bootstrap.py":"cyber_lion/mission_control/cooperative_preactivation_bootstrap.py","cyber_lion/mission_control/cooperative_process_bootstrap.py":"cyber_lion/mission_control/cooperative_process_bootstrap.py","cyber_lion/mission_control/cooperative_production.py":"cyber_lion/mission_control/cooperative_production.py","cyber_lion/mission_control/cooperative_readiness.py":"cyber_lion/mission_control/cooperative_readiness.py","cyber_lion/mission_control/cooperative_worker_bootstrap.py":"cyber_lion/mission_control/cooperative_worker_bootstrap.py","cyber_lion/mission_control/cooperative_worker_runtime.py":"cyber_lion/mission_control/cooperative_worker_runtime.py","cyber_lion/mission_control/dual_result_join.py":"cyber_lion/mission_control/dual_result_join.py","cyber_lion/mission_control/execution_driver.py":"cyber_lion/mission_control/execution_driver.py","cyber_lion/mission_control/execution_driver_contract.py":"cyber_lion/mission_control/execution_driver_contract.py","cyber_lion/mission_control/global_scheduler.py":"cyber_lion/mission_control/global_scheduler.py","cyber_lion/mission_control/lpcl_runtime_selection.py":"cyber_lion/mission_control/lpcl_runtime_selection.py","cyber_lion/mission_control/mission_reconciliation.py":"cyber_lion/mission_control/mission_reconciliation.py","cyber_lion/mission_control/model_calls.py":"cyber_lion/mission_control/model_calls.py","cyber_lion/mission_control/operator_control.py":"cyber_lion/mission_control/operator_control.py","cyber_lion/mission_control/operator_swarm_session.py":"cyber_lion/mission_control/operator_swarm_session.py","cyber_lion/mission_control/phase_control.py":"cyber_lion/mission_control/phase_control.py","cyber_lion/mission_control/runtime_projection.py":"cyber_lion/mission_control/runtime_projection.py","cyber_lion/mission_control/supervisor_projection.py":"cyber_lion/mission_control/supervisor_projection.py","cyber_lion/process_language/lpcl.py":"cyber_lion/process_language/lpcl.py","lion_firefox_broker_relay.py":"tools/lion_firefox_broker_relay.py","lion_mission_lifecycle_db.py":"tools/lion_mission_lifecycle_db.py","lion_operator_client.py":"tools/lion_operator_client.py","lion_operator_containment_helper.py":"tools/lion_operator_containment_helper.py","lion_operator_gateway.py":"tools/lion_operator_gateway.py","lion_operator_provision.py":"tools/lion_operator_provision.py","lion_saas_broker.py":"tools/lion_saas_broker.py","lion_saas_session_bridge.py":"tools/lion_saas_session_bridge.py","mission_control_compat.py":"tools/lion_mission_control_compat.py","mission_control_v3.py":"tools/lion_mission_control_v3.py","static/app.css":"deploy/mission-control/v3/app.css","static/app.js":"deploy/mission-control/v3/app.js","static/control-v3.js":"deploy/mission-control/v3/control-v3.js","static/index.html":"deploy/mission-control/v3/index.html","static/passive.js":"deploy/mission-control/v3/passive.js","systemd/lion-operator-control.service":"deploy/systemd/lion-operator-control.service","tools/lion_cooperative_worker_adapter.py":"tools/lion_cooperative_worker_adapter.py","tools/lion_mission_lifecycle_db.py":"tools/lion_mission_lifecycle_db.py","tools/lion_saas_broker.py":"tools/lion_saas_broker.py","tools/lion_saas_session_bridge.py":"tools/lion_saas_session_bridge.py"}
MISSION_CONTROL_V3_PATH=MISSION_CONTROL_V3_ROOT/"mission_control_v3.py"
MISSION_CONTROL_V3_SHA256=MISSION_CONTROL_V3_REQUIRED_SHA256["mission_control_v3.py"]
MISSION_CONTROL_V3_DROPIN=Path("/etc/systemd/system/lion-mission-control.service.d/99-v3-control.conf")
MISSION_CONTROL_V3_LOCATOR=Path("/run/lion-mission-control/listen.json")
MISSION_CONTROL_V3_UNIT="lion-mission-control.service"
MISSION_CONTROL_V3_DROPIN_TEXT='''[Service]
WorkingDirectory=/var/lib/sentinelx/uploads/lion-mission-control-v3
Environment="PYTHONPATH=/var/lib/sentinelx/uploads/lion-mission-control-v3"
ExecStart=
ExecStart=/usr/bin/python3 /var/lib/sentinelx/uploads/lion-mission-control-v3/mission_control_v3.py --host 127.0.0.1 --port 8766 --listen-state /run/lion-mission-control/listen.json --legacy-listen-state /run/lion-vkt-mission-control/listen.json
InaccessiblePaths=
InaccessiblePaths=-/run/lion-vkt-effect-admission.sock -/run/lion-k3s-vkt-r3/provider.sock -/run/lion-runner-exec.sock -/run/dbus/system_bus_socket
ReadWritePaths=/var/lib/sentinelx/uploads/lion-mission-control-v3
'''

def mission_control_v3_package_identity_at(root:Path)->dict[str,str]:
 observed={}
 for name,expected in sorted(MISSION_CONTROL_V3_REQUIRED_SHA256.items()):
  path=root/name
  if not path.is_file():raise Deny("MISSION_CONTROL_V3_PACKAGE_MISSING:"+name)
  actual=sha256_file(path)
  if actual!=expected:raise Deny("MISSION_CONTROL_V3_PACKAGE_IDENTITY:"+name+":"+actual)
  observed[name]=actual
 return observed


def mission_control_v3_package_identity()->dict[str,str]:
 return mission_control_v3_package_identity_at(MISSION_CONTROL_V3_ROOT)


def _mission_control_v3_source_envelope(request:dict[str,Any])->tuple[str,str]:
 compact={"schema_version","request_id","operation","source_head","source_tree"}
 if set(request)==compact:
  head=require_hex40(request.get("source_head"),"source_head")
  tree=require_hex40(request.get("source_tree"),"source_tree")
 else:
  # Backward-compatible admission for the historical Mission64 envelope.
  head,tree,_=mission64_require_envelope(request,worker=False)
 mission64_verify_current(head,tree)
 return head,tree


def _mission_control_v3_safe_rel(value:str,label:str)->Path:
 if not isinstance(value,str) or not value or value.startswith("/") or "\x00" in value:
  raise Deny(label)
 rel=Path(value)
 if any(part in {"",".",".."} for part in rel.parts):
  raise Deny(label)
 return rel


def _mission_control_v3_atomic_copy(src:Path,dst:Path)->None:
 if not src.is_file() or src.is_symlink():raise Deny("MISSION_CONTROL_V3_SOURCE_FILE:"+str(src))
 dst.parent.mkdir(parents=True,exist_ok=True)
 fd,tmpname=tempfile.mkstemp(prefix="."+dst.name+".",suffix=".tmp",dir=str(dst.parent));tmp=Path(tmpname)
 try:
  with src.open("rb") as inp,os.fdopen(fd,"wb") as out:
   shutil.copyfileobj(inp,out);out.flush();os.fsync(out.fileno())
  os.chmod(tmp,src.stat().st_mode & 0o777)
  os.replace(tmp,dst)
 finally:
  if tmp.exists():tmp.unlink()


def mission_control_v3_materialize_stage_from_checkout(
 checkout:Path,stage_root:Path,*,source_head:str,source_tree:str,request_id:str
)->dict[str,Any]:
 head=require_hex40(source_head,"source_head");tree=require_hex40(source_tree,"source_tree")
 require_hex64(request_id,"request_id")
 if not checkout.is_dir() or checkout.is_symlink():raise Deny("MISSION_CONTROL_V3_CHECKOUT_ROOT")
 parent=stage_root.parent;parent.mkdir(parents=True,exist_ok=True)
 tmp=Path(tempfile.mkdtemp(prefix="."+stage_root.name+".",dir=str(parent)))
 old_backup=None
 try:
  for target_name,source_name in sorted(MISSION_CONTROL_V3_SOURCE_MAP.items()):
   target_rel=_mission_control_v3_safe_rel(target_name,"MISSION_CONTROL_V3_TARGET_PATH")
   source_rel=_mission_control_v3_safe_rel(source_name,"MISSION_CONTROL_V3_SOURCE_PATH")
   src=checkout/source_rel
   dst=tmp/target_rel
   _mission_control_v3_atomic_copy(src,dst)
  package_identity=mission_control_v3_package_identity_at(tmp)
  package_digest=sha256(canonical(package_identity))
  identity={
   "schema":"lion.mission-control-v3-stage/v1",
   "request_id":request_id,
   "source_head":head,
   "source_tree":tree,
   "package_digest":package_digest,
   "file_count":len(package_identity),
   "staged_at":now(),
   "authority_effect":"BOUNDED_PACKAGE_STAGING",
   "runtime_effect":"NONE",
  }
  atomic_json(tmp/MISSION_CONTROL_V3_STAGE_IDENTITY,identity)
  if stage_root.exists():
   backup_dir=MISSION_CONTROL_V3_DEPLOY_STATE/"stage-backups"
   backup_dir.mkdir(parents=True,exist_ok=True)
   old_backup=backup_dir/(stage_root.name+"."+request_id+"."+datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
   os.replace(stage_root,old_backup)
  try:
   os.replace(tmp,stage_root)
  except Exception:
   if old_backup is not None and old_backup.exists() and not stage_root.exists():
    os.replace(old_backup,stage_root)
   raise
  return {
   "staged":True,
   "stage_root":str(stage_root),
   "source_head":head,
   "source_tree":tree,
   "package_digest":package_digest,
   "package_identity":package_identity,
   "file_count":len(package_identity),
   "previous_stage_backup":str(old_backup) if old_backup else None,
   "authority_effect":"BOUNDED_PACKAGE_STAGING",
   "runtime_effect":"NONE",
  }
 finally:
  if tmp.exists():shutil.rmtree(tmp,ignore_errors=True)


def _mission_control_v3_checkout_current_master(head:str,tree:str)->Path:
 td=Path(tempfile.mkdtemp(prefix="lion-mission-control-v3-stage-source-"))
 try:
  run(["/usr/bin/git","init",str(td)],timeout=30)
  run(["/usr/bin/git","-C",str(td),"remote","add","origin",MISSION64_MASTER_REPO],timeout=30)
  run(["/usr/bin/git","-C",str(td),"fetch","--no-tags","--depth=1","origin",f"refs/heads/{MISSION64_MASTER_BRANCH}"],timeout=180)
  actual_head=run(["/usr/bin/git","-C",str(td),"rev-parse","FETCH_HEAD"],capture=True,timeout=30).stdout.decode().strip()
  actual_tree=run(["/usr/bin/git","-C",str(td),"rev-parse","FETCH_HEAD^{tree}"],capture=True,timeout=30).stdout.decode().strip()
  if (actual_head,actual_tree)!=(head,tree):
   raise Deny("MISSION_CONTROL_V3_STAGE_SOURCE_DRIFT:"+actual_head+":"+actual_tree)
  run(["/usr/bin/git","-C",str(td),"checkout","--detach","FETCH_HEAD"],timeout=60)
  return td
 except Exception:
  shutil.rmtree(td,ignore_errors=True)
  raise


def mission_control_v3_stage_current_master(request:dict[str,Any])->dict[str,Any]:
 if set(request)!={"schema_version","request_id","operation","source_head","source_tree"}:
  raise Deny("MISSION_CONTROL_V3_STAGE_FIELD_SET")
 head,tree=_mission_control_v3_source_envelope(request)
 prior_receipt=(MISSION_CONTROL_V3_DEPLOY_STATE/"receipts"/(request["request_id"]+".stage.json"))
 if prior_receipt.exists():
  raise Deny("MISSION_CONTROL_V3_STAGE_REQUEST_REPLAY")
 checkout=_mission_control_v3_checkout_current_master(head,tree)
 try:
  result=mission_control_v3_materialize_stage_from_checkout(
   checkout,MISSION_CONTROL_V3_STAGE_ROOT,
   source_head=head,source_tree=tree,request_id=request["request_id"],
  )
 finally:
  shutil.rmtree(checkout,ignore_errors=True)
 receipt={
  "schema":"lion.mission-control-v3-stage-receipt/v1",
  "request_id":request["request_id"],
  "operation":request["operation"],
  "source_head":head,
  "source_tree":tree,
  "package_digest":result["package_digest"],
  "observed_at":now(),
  "authority_effect":"BOUNDED_PACKAGE_STAGING",
  "runtime_effect":"NONE",
 }
 receipt["receipt_digest"]=sha256(canonical(receipt))
 atomic_json(MISSION_CONTROL_V3_DEPLOY_STATE/"receipts"/(request["request_id"]+".stage.json"),receipt)
 return {**result,"control_receipt":receipt}


def _mission_control_v3_stage_readback(head:str,tree:str)->tuple[dict[str,str],dict[str,Any]]:
 package=mission_control_v3_package_identity_at(MISSION_CONTROL_V3_STAGE_ROOT)
 identity_path=MISSION_CONTROL_V3_STAGE_ROOT/MISSION_CONTROL_V3_STAGE_IDENTITY
 if not identity_path.is_file():raise Deny("MISSION_CONTROL_V3_STAGE_IDENTITY_MISSING")
 try:identity=json.loads(identity_path.read_text(encoding="utf-8"))
 except Exception as exc:raise Deny("MISSION_CONTROL_V3_STAGE_IDENTITY_INVALID") from exc
 expected_digest=sha256(canonical(package))
 if (
  identity.get("schema")!="lion.mission-control-v3-stage/v1"
  or identity.get("source_head")!=head
  or identity.get("source_tree")!=tree
  or identity.get("package_digest")!=expected_digest
  or identity.get("file_count")!=len(package)
 ):
  raise Deny("MISSION_CONTROL_V3_STAGE_IDENTITY_DRIFT")
 return package,identity


def _mission_control_v3_deploy_receipt(request:dict[str,Any],result:dict[str,Any],kind:str)->dict[str,Any]:
 receipt={
  "schema":"lion.mission-control-v3-deployment-receipt/v1",
  "request_id":request["request_id"],
  "operation":request["operation"],
  "kind":kind,
  "source_head":request.get("source_head"),
  "source_tree":request.get("source_tree"),
  "result_digest":sha256(canonical(result)),
  "observed_at":now(),
  "authority_effect":"BOUNDED_MISSION_CONTROL_DEPLOYMENT",
 }
 receipt["receipt_digest"]=sha256(canonical(receipt))
 atomic_json(MISSION_CONTROL_V3_DEPLOY_STATE/"receipts"/(request["request_id"]+".deploy.json"),receipt)
 return receipt


def mission_control_v3_install(request:dict[str,Any])->dict[str,Any]:
 head,tree=_mission_control_v3_source_envelope(request)
 stage_identity,stage_meta=_mission_control_v3_stage_readback(head,tree)
 if not MISSION_CONTROL_V3_ROOT.exists():
  MISSION_CONTROL_V3_ROOT.mkdir(parents=True,exist_ok=False)
 backup=MISSION_CONTROL_V3_DEPLOY_STATE/"deploy-backups"/request["request_id"]
 if backup.exists():raise Deny("MISSION_CONTROL_V3_DEPLOY_REQUEST_REPLAY")
 backup.mkdir(parents=True,exist_ok=False)
 package_existed={}
 dropin_existed=False
 service_was_active=False
 rollback_errors=[]
 try:
  service_was_active=_systemctl_exact("is-active","--quiet",MISSION_CONTROL_V3_UNIT,check=False).returncode==0
  for name in sorted(MISSION_CONTROL_V3_REQUIRED_SHA256):
   live=MISSION_CONTROL_V3_ROOT/name
   package_existed[name]=_backup_optional(live,backup/"package"/name)
  dropin_existed=_backup_optional(MISSION_CONTROL_V3_DROPIN,backup/"systemd"/MISSION_CONTROL_V3_DROPIN.name)
  for name in sorted(MISSION_CONTROL_V3_REQUIRED_SHA256):
   _live_package_copy(MISSION_CONTROL_V3_STAGE_ROOT/name,MISSION_CONTROL_V3_ROOT/name)
  live_identity=mission_control_v3_package_identity()
  if live_identity!=stage_identity:raise Deny("MISSION_CONTROL_V3_LIVE_STAGE_IDENTITY_MISMATCH")

  MISSION_CONTROL_V3_DROPIN.parent.mkdir(parents=True,exist_ok=True)
  drop_src=backup/"new-mission-control-dropin";drop_src.write_bytes(MISSION_CONTROL_V3_DROPIN_TEXT.encode())
  _atomic_copy_file(drop_src,MISSION_CONTROL_V3_DROPIN,0o644)
  _systemctl_exact("daemon-reload")
  _systemctl_exact("restart",MISSION_CONTROL_V3_UNIT)
  health=_wait_health(_mission_control_health,MISSION_CONTROL_V3_UNIT)
  locator=None
  if MISSION_CONTROL_V3_LOCATOR.is_file():
   locator=json.loads(MISSION_CONTROL_V3_LOCATOR.read_text(encoding="utf-8"))
  if not isinstance(locator,dict) or locator.get("port")!=8766 or locator.get("generation")!="MISSION_CONTROL_V3":
   raise Deny("MISSION_CONTROL_V3_LOCATOR_READBACK")
  db_path=MISSION_CONTROL_V3_ROOT/"mission-control-v3.db"
  db_integrity=_sqlite_integrity(db_path) if db_path.is_file() else "NOT_PRESENT"
  if db_path.is_file() and db_integrity!="ok":raise Deny("MISSION_CONTROL_V3_DB_INTEGRITY")
  result={
   "installed":True,
   "unit":MISSION_CONTROL_V3_UNIT,
   "port":8766,
   "source_head":head,
   "source_tree":tree,
   "source_sha256":live_identity["mission_control_v3.py"],
   "package_identity":live_identity,
   "package_digest":sha256(canonical(live_identity)),
   "stage_package_digest":stage_meta["package_digest"],
   "dropin_sha256":sha256_file(MISSION_CONTROL_V3_DROPIN),
   "locator":locator,
   "health":health,
   "db_integrity":db_integrity,
   "rollback_backup":str(backup),
   "authority_effect":"BOUNDED_MISSION_CONTROL_DEPLOYMENT",
  }
  result["control_receipt"]=_mission_control_v3_deploy_receipt(request,result,"PASS")
  return result
 except Exception as exc:
  for name,existed in package_existed.items():
   try:
    target=MISSION_CONTROL_V3_ROOT/name
    if existed:_live_package_copy(backup/"package"/name,target)
    elif target.exists():target.unlink()
   except Exception as rb:rollback_errors.append(name+":"+type(rb).__name__)
  try:_restore_optional(backup/"systemd"/MISSION_CONTROL_V3_DROPIN.name,MISSION_CONTROL_V3_DROPIN,dropin_existed)
  except Exception as rb:rollback_errors.append("dropin:"+type(rb).__name__)
  try:_systemctl_exact("daemon-reload")
  except Exception as rb:rollback_errors.append("daemon-reload:"+type(rb).__name__)
  if service_was_active:
   try:_systemctl_exact("restart",MISSION_CONTROL_V3_UNIT)
   except Exception as rb:rollback_errors.append("service-restart:"+type(rb).__name__)
  rollback={
   "schema":"lion.mission-control-v3-deployment-rollback/v1",
   "request_id":request["request_id"],
   "source_head":head,
   "source_tree":tree,
   "failure":type(exc).__name__+":"+str(exc),
   "rollback_errors":rollback_errors,
   "observed_at":now(),
   "authority_effect":"BOUNDED_MISSION_CONTROL_DEPLOYMENT",
  }
  atomic_json(backup/"rollback.json",rollback)
  raise Deny("MISSION_CONTROL_V3_INSTALL_FAILED:"+type(exc).__name__+":"+str(exc)+":rollback_errors="+str(len(rollback_errors))) from exc



# ---- Operator Intervention R1 branch-fixed transactional deployment -------
OPERATOR_INTERVENTION_TASK_ID="LION-OPERATOR-DRONE-SUPREMACY-AND-LIVE-MISSION-INTERVENTION-R1"
OPERATOR_INTERVENTION_BRANCH="mission/r23-autonomy-execution-fabric"
OPERATOR_INTERVENTION_STAGE_ROOT=Path("/var/lib/sentinelx/uploads/lion-mission-control-v3.stage-operator-intervention")
OPERATOR_INTERVENTION_STATE_ROOT=STATE_ROOT/"operator-intervention-r1"
OPERATOR_CONTROL_UNIT="lion-operator-control.service"
OPERATOR_CONTROL_UNIT_PACKAGE_REL="systemd/lion-operator-control.service"
OPERATOR_CONTROL_UNIT_PATH=Path("/etc/systemd/system/lion-operator-control.service")
OPERATOR_PROXY_KEY_PATH=MISSION_CONTROL_V3_ROOT/"operator-sentinelx-proxy.key"
OPERATOR_DB_PATH=MISSION_CONTROL_V3_ROOT/"mission-control-v3.db"


def operator_intervention_git_identity()->tuple[str,str]:
 td=Path(tempfile.mkdtemp(prefix="lion-operator-intervention-currentness-"))
 try:
  run(["/usr/bin/git","init",str(td)],timeout=30)
  run(["/usr/bin/git","-C",str(td),"remote","add","origin",REPO_URL],timeout=30)
  run(["/usr/bin/git","-C",str(td),"fetch","--no-tags","--depth=1","origin",f"refs/heads/{OPERATOR_INTERVENTION_BRANCH}"],timeout=180)
  head=run(["/usr/bin/git","-C",str(td),"rev-parse","FETCH_HEAD"],capture=True,timeout=30).stdout.decode().strip()
  tree=run(["/usr/bin/git","-C",str(td),"rev-parse","FETCH_HEAD^{tree}"],capture=True,timeout=30).stdout.decode().strip()
  return require_hex40(head,"operator-live-head"),require_hex40(tree,"operator-live-tree")
 finally:shutil.rmtree(td,ignore_errors=True)


def operator_intervention_require_envelope(request:dict[str,Any])->tuple[str,str]:
 expected={"schema_version","request_id","operation","task_id","source_head","source_tree"}
 if set(request)!=expected:raise Deny("OPERATOR_INTERVENTION_FIELD_SET")
 if request.get("task_id")!=OPERATOR_INTERVENTION_TASK_ID:raise Deny("OPERATOR_INTERVENTION_TASK_ID")
 head=require_hex40(request.get("source_head"),"source_head");tree=require_hex40(request.get("source_tree"),"source_tree")
 live_head,live_tree=operator_intervention_git_identity()
 if (head,tree)!=(live_head,live_tree):raise Deny("OPERATOR_INTERVENTION_LIVE_SOURCE_DRIFT:"+live_head+":"+live_tree)
 return head,tree


def _atomic_copy_file(src:Path,dst:Path,mode:int|None=None,owner:tuple[int,int]|None=None)->None:
 dst.parent.mkdir(parents=True,exist_ok=True)
 fd,tmpname=tempfile.mkstemp(prefix="."+dst.name+".",suffix=".tmp",dir=str(dst.parent));tmp=Path(tmpname)
 try:
  with src.open("rb") as inp,os.fdopen(fd,"wb") as out:
   shutil.copyfileobj(inp,out);out.flush();os.fsync(out.fileno())
  os.chmod(tmp,mode if mode is not None else (src.stat().st_mode & 0o777))
  if owner is not None and os.geteuid()==0:os.chown(tmp,owner[0],owner[1])
  os.replace(tmp,dst)
 finally:
  if tmp.exists():tmp.unlink()


def _live_package_owner()->tuple[int,int]:
 st=MISSION_CONTROL_V3_ROOT.stat();return st.st_uid,st.st_gid


def _ensure_live_package_parent(dst:Path)->tuple[int,int]:
 root=MISSION_CONTROL_V3_ROOT
 try:rel=dst.parent.relative_to(root)
 except ValueError as exc:raise Deny("LIVE_PACKAGE_PATH_ESCAPE") from exc
 owner=_live_package_owner();current=root
 for part in rel.parts:
  current=current/part;current.mkdir(exist_ok=True);os.chmod(current,0o755)
  if os.geteuid()==0:os.chown(current,owner[0],owner[1])
 return owner


def _live_package_copy(src:Path,dst:Path)->None:
 owner=_ensure_live_package_parent(dst);_atomic_copy_file(src,dst,owner=owner)


def _systemctl_exact(*args:str,check:bool=True)->subprocess.CompletedProcess[bytes]:
 proc=subprocess.run(["/bin/systemctl",*args],stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,shell=False,check=False,timeout=60)
 if check and proc.returncode!=0:raise Deny("OPERATOR_INTERVENTION_SYSTEMD:"+" ".join(args)+":"+(proc.stderr or proc.stdout).decode("utf-8","replace")[-2000:])
 return proc


def _sqlite_integrity(path:Path)->str:
 conn=sqlite3.connect("file:"+path.as_posix()+"?mode=ro",uri=True,timeout=5)
 try:return str(conn.execute("PRAGMA integrity_check").fetchone()[0])
 finally:conn.close()


def _operator_control_health()->dict[str,Any]:
 key=OPERATOR_PROXY_KEY_PATH.read_text(encoding="utf-8").strip()
 if len(key)<64:raise Deny("OPERATOR_PROXY_KEY_UNAVAILABLE")
 conn=http.client.HTTPConnection("127.0.0.1",8767,timeout=3)
 try:
  conn.request("GET","/health",headers={"X-LION-Operator-Proxy-Key":key,"User-Agent":"LION-Operator-Deploy-Readback/1"})
  res=conn.getresponse();raw=res.read(65536)
 finally:conn.close()
 if res.status!=200:raise Deny("OPERATOR_CONTROL_HEALTH_HTTP:"+str(res.status))
 value=json.loads(raw.decode("utf-8"))
 if value.get("status")!="ok" or value.get("authenticated_principal")!="OPERATOR_SENTINELX_PROXY":raise Deny("OPERATOR_CONTROL_HEALTH_IDENTITY")
 return value


def _mission_control_health()->dict[str,Any]:
 conn=http.client.HTTPConnection("127.0.0.1",8766,timeout=3)
 try:
  conn.request("GET","/health",headers={"User-Agent":"LION-Operator-Deploy-Readback/1"});res=conn.getresponse();raw=res.read(65536)
 finally:conn.close()
 if res.status!=200:raise Deny("MISSION_CONTROL_HEALTH_HTTP:"+str(res.status))
 value=json.loads(raw.decode("utf-8"))
 if value.get("status")!="ok":raise Deny("MISSION_CONTROL_HEALTH_STATE")
 return value


def _wait_health(fn,unit:str,timeout:float=20.0)->dict[str,Any]:
 import time as _time
 end=_time.time()+timeout;last=None
 while _time.time()<end:
  if _systemctl_exact("is-active","--quiet",unit,check=False).returncode==0:
   try:return fn()
   except Exception as exc:last=exc
  _time.sleep(.25)
 raise Deny("OPERATOR_INTERVENTION_NOT_READY:"+unit+":"+(type(last).__name__ if last else "UNKNOWN"))


def _backup_optional(src:Path,dst:Path)->bool:
 if not src.is_file():return False
 dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dst);return True


def _restore_optional(backup:Path,target:Path,existed:bool)->None:
 if existed:_atomic_copy_file(backup,target)
 elif target.exists():target.unlink()


def operator_intervention_receipt(request:dict[str,Any],result:dict[str,Any])->dict[str,Any]:
 payload={"schema":"lion.operator-intervention-deploy-receipt/v1","request_id":request["request_id"],"operation":request["operation"],"task_id":OPERATOR_INTERVENTION_TASK_ID,"source_head":request["source_head"],"source_tree":request["source_tree"],"result_digest":sha256(canonical(result)),"observed_at":now(),"authority":"BOUNDED_PRIVILEGED_ADMISSION"}
 payload["receipt_digest"]=sha256(canonical(payload));path=OPERATOR_INTERVENTION_STATE_ROOT/"receipts"/(request["request_id"]+".json");atomic_json(path,payload);return payload


def operator_intervention_deploy(request:dict[str,Any])->dict[str,Any]:
 head,tree=operator_intervention_require_envelope(request)
 stage_identity=mission_control_v3_package_identity_at(OPERATOR_INTERVENTION_STAGE_ROOT)
 if OPERATOR_CONTROL_UNIT_PACKAGE_REL not in stage_identity:raise Deny("OPERATOR_CONTROL_UNIT_NOT_IN_PACKAGE")
 if not OPERATOR_DB_PATH.is_file() or _sqlite_integrity(OPERATOR_DB_PATH)!="ok":raise Deny("OPERATOR_DB_INTEGRITY_PRECHECK")
 for secret in (MISSION_CONTROL_V3_ROOT/"operator-gateway.key",MISSION_CONTROL_V3_ROOT/"operator-sentinelx-proxy.key",MISSION_CONTROL_V3_ROOT/"operator-panel-proxy.key",MISSION_CONTROL_V3_ROOT/"operator-pairing.key"):
  if not secret.is_file() or len(secret.read_text(encoding="utf-8").strip())<64:raise Deny("OPERATOR_SECRET_PRECHECK:"+secret.name)
 backup=OPERATOR_INTERVENTION_STATE_ROOT/"deploy-backups"/request["request_id"]
 if backup.exists():raise Deny("OPERATOR_INTERVENTION_REQUEST_REPLAY")
 backup.mkdir(parents=True,exist_ok=False)
 package_existed={}
 for name in sorted(MISSION_CONTROL_V3_REQUIRED_SHA256):
  src=MISSION_CONTROL_V3_ROOT/name;package_existed[name]=_backup_optional(src,backup/"package"/name)
 dropin_existed=_backup_optional(MISSION_CONTROL_V3_DROPIN,backup/"systemd"/MISSION_CONTROL_V3_DROPIN.name)
 operator_unit_existed=_backup_optional(OPERATOR_CONTROL_UNIT_PATH,backup/"systemd"/OPERATOR_CONTROL_UNIT_PATH.name)
 operator_unit_enabled=_systemctl_exact("is-enabled","--quiet",OPERATOR_CONTROL_UNIT,check=False).returncode==0
 rollback_errors=[]
 try:
  for name in sorted(MISSION_CONTROL_V3_REQUIRED_SHA256):_live_package_copy(OPERATOR_INTERVENTION_STAGE_ROOT/name,MISSION_CONTROL_V3_ROOT/name)
  live_identity=mission_control_v3_package_identity()
  _atomic_copy_file(MISSION_CONTROL_V3_ROOT/OPERATOR_CONTROL_UNIT_PACKAGE_REL,OPERATOR_CONTROL_UNIT_PATH,0o644)
  drop_src=backup/"new-mission-control-dropin";drop_src.write_bytes(MISSION_CONTROL_V3_DROPIN_TEXT.encode());_atomic_copy_file(drop_src,MISSION_CONTROL_V3_DROPIN,0o644)
  _systemctl_exact("daemon-reload")
  _systemctl_exact("enable",OPERATOR_CONTROL_UNIT)
  _systemctl_exact("restart",OPERATOR_CONTROL_UNIT)
  operator_health=_wait_health(_operator_control_health,OPERATOR_CONTROL_UNIT)
  _systemctl_exact("restart",MISSION_CONTROL_V3_UNIT)
  mission_health=_wait_health(_mission_control_health,MISSION_CONTROL_V3_UNIT)
  if _sqlite_integrity(OPERATOR_DB_PATH)!="ok":raise Deny("OPERATOR_DB_INTEGRITY_POSTDEPLOY")
  locator=None
  if MISSION_CONTROL_V3_LOCATOR.is_file():
   locator=json.loads(MISSION_CONTROL_V3_LOCATOR.read_text(encoding="utf-8"))
  if not isinstance(locator,dict) or locator.get("port")!=8766 or locator.get("generation")!="MISSION_CONTROL_V3":raise Deny("MISSION_CONTROL_V3_LOCATOR_READBACK")
  result={"installed":True,"task_id":OPERATOR_INTERVENTION_TASK_ID,"source_head":head,"source_tree":tree,"package_identity":live_identity,"package_digest":sha256(canonical(live_identity)),"operator_unit_sha256":sha256_file(OPERATOR_CONTROL_UNIT_PATH),"operator_control_health":operator_health,"mission_control_health":mission_health,"locator":locator,"db_integrity":"ok","rollback_backup":str(backup),"authority_effect":"BOUNDED_OPERATOR_INTERVENTION_DEPLOY"}
  result["control_receipt"]=operator_intervention_receipt(request,result)
  return result
 except Exception as exc:
  # Roll back package and both unit definitions; preserve the original failure.
  try:_systemctl_exact("disable","--now",OPERATOR_CONTROL_UNIT,check=False)
  except Exception as rb:rollback_errors.append(type(rb).__name__+":"+str(rb))
  for name,existed in package_existed.items():
   try:
    target=MISSION_CONTROL_V3_ROOT/name
    if existed:_live_package_copy(backup/"package"/name,target)
    elif target.exists():target.unlink()
   except Exception as rb:rollback_errors.append(name+":"+type(rb).__name__)
  try:_restore_optional(backup/"systemd"/MISSION_CONTROL_V3_DROPIN.name,MISSION_CONTROL_V3_DROPIN,dropin_existed)
  except Exception as rb:rollback_errors.append("mission-dropin:"+type(rb).__name__)
  try:_restore_optional(backup/"systemd"/OPERATOR_CONTROL_UNIT_PATH.name,OPERATOR_CONTROL_UNIT_PATH,operator_unit_existed)
  except Exception as rb:rollback_errors.append("operator-unit:"+type(rb).__name__)
  try:_systemctl_exact("daemon-reload")
  except Exception as rb:rollback_errors.append("daemon-reload:"+type(rb).__name__)
  try:_systemctl_exact("restart",MISSION_CONTROL_V3_UNIT)
  except Exception as rb:rollback_errors.append("mission-restart:"+type(rb).__name__)
  if operator_unit_existed:
   try:
    if operator_unit_enabled:_systemctl_exact("enable",OPERATOR_CONTROL_UNIT)
    _systemctl_exact("restart",OPERATOR_CONTROL_UNIT)
   except Exception as rb:rollback_errors.append("operator-restart:"+type(rb).__name__)
  rollback={"schema":"lion.operator-intervention-rollback/v1","request_id":request["request_id"],"failure":type(exc).__name__+":"+str(exc),"rollback_errors":rollback_errors,"observed_at":now()};atomic_json(backup/"rollback.json",rollback)
  raise Deny("OPERATOR_INTERVENTION_DEPLOY_FAILED:"+type(exc).__name__+":"+str(exc)+":rollback_errors="+str(len(rollback_errors))) from exc
# ---- end Operator Intervention R1 deployment ------------------------------

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
                "MISSION64_CURRENTNESS_READ",
                "MISSION64_PRECHECK",
                "MISSION64_START",
                "MISSION64_READ",
                "MISSION64_PAUSE",
                "MISSION64_RESUME",
                "MISSION64_RESTART_ONE",
                "MISSION64_VALIDATE",
                "MISSION64_STOP",
                "MISSION_CONTROL_V3_STAGE_CURRENT_MASTER",
                "MISSION_CONTROL_V3_INSTALL",
                "OPERATOR_INTERVENTION_DEPLOY",
                "EPOCH3_M64_PRECHECK",
                "EPOCH3_M64_START",
                "EPOCH3_M64_READ",
                "EPOCH3_M64_RESTART_ONE",
                "EPOCH3_M64_VALIDATE",
                "EPOCH3_M64_STOP",
                "EPOCH3_M64_START_LOGICAL",
                "EPOCH3_M64_RESTART_LOGICAL",
                "EPOCH3_M64_VALIDATE_LOGICAL",
            ],
            "mission64": mission64_spec(),
        }

    if operation == "MISSION64_CURRENTNESS_READ":
        if set(request) != {"schema_version", "request_id", "operation"}:
            raise Deny("MISSION64_CURRENTNESS_FIELD_SET")
        head,tree=mission64_git_identity()
        return {
            "source_head":head,
            "source_tree":tree,
            "repository":MISSION64_MASTER_REPO,
            "branch":MISSION64_MASTER_BRANCH,
            "currentness_source":"GITHUB_MASTER_READ",
            "authority_effect":"NONE",
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

    if operation == "MISSION_CONTROL_V3_STAGE_CURRENT_MASTER":
        return mission_control_v3_stage_current_master(request)

    if operation == "MISSION_CONTROL_V3_INSTALL":
        return mission_control_v3_install(request)

    if operation == "OPERATOR_INTERVENTION_DEPLOY":
        return operator_intervention_deploy(request)

    if operation in {"EPOCH3_M64_START_LOGICAL","EPOCH3_M64_RESTART_LOGICAL","EPOCH3_M64_VALIDATE_LOGICAL"}:
        return e3_component_handle(request)

    if operation in {"EPOCH3_M64_PRECHECK","EPOCH3_M64_START","EPOCH3_M64_READ","EPOCH3_M64_RESTART_ONE","EPOCH3_M64_VALIDATE","EPOCH3_M64_STOP"}:
        return e3_handle(request)

    if operation in {"MISSION64_PRECHECK","MISSION64_START","MISSION64_READ","MISSION64_PAUSE","MISSION64_RESUME","MISSION64_RESTART_ONE","MISSION64_VALIDATE","MISSION64_STOP"}:
        return mission64_handle(request)

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