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
MISSION_CONTROL_V3_REQUIRED_SHA256={
 "cyber_lion/mission_control/__init__.py": "8d83b68f7ef8047dc9448bbd9ea0335a5a427fd6d6a3b2707c77a90d76f0448c",
 "cyber_lion/mission_control/dual_result_join.py": "7ce631308f4150525330a56421c55353906d49ad2217206fa4d7ff314bb8139f",
 "cyber_lion/mission_control/execution_driver.py": "409a9a5a19f900ca4e042634dbebb9776d4dbd03c9e4a02a41ef319f35dcbc65",
 "cyber_lion/mission_control/execution_driver_contract.py": "aa5c7390960c835968b72eb28be76b8e2e5d0e83bc9d66fe01fdc5bd13f79821",
 "cyber_lion/mission_control/global_scheduler.py": "a0f80231ea8d10de1a6942985e7716175070bc7e4772e48d81182da6cdcf0858",
 "cyber_lion/mission_control/phase_control.py": "89372056bf7668edc473b0b0dc04433d376dca3e041499fc0b4e6a52f69c319e",
 "cyber_lion/mission_control/runtime_projection.py": "9a6d9d62c25bbc4a3c15aeb1731223fc7c08e62bf8099717a9c58e85aab0ed24",
 "cyber_lion/mission_control/supervisor_projection.py": "d6ffc5c07caf5db6e4040c38962987c3c0c6effb2bfb022e88373c71e773fb80",
 "lion_mission_lifecycle_db.py": "9b2d37e1d6e3273800a31cb5417143deb117916444be1cef0c18f0339b8a915f",
 "lion_saas_session_bridge.py": "48721d123c4604c8b0870f30fe6e4945fe399e4912258391c4845b6dc1629d9a",
 "mission_control_compat.py": "67ce2f6b7f40336ca09012e7a7e414c0f2feb52fcf78947dce628427d70fd4e7",
 "mission_control_v3.py": "56c31ed6ded6ba19ca115ef68267f1a5eb8b66c195eb0fd53c1de3c59b00cb52",
 "static/app.css": "a74f12624834fe0184ec46b3239ff2acc563af184e3ba731cf31c0b0fc989d7c",
 "static/app.js": "c052ffb1645c11a48c5287935d11d60141aed46f648d8115e050a9d6c92ef087",
 "static/control-v3.js": "7b83f6f897056fce26f4b19f2deababfc697daec9bd0b928691fe56eeb3ce9f4",
 "static/index.html": "d913d55fa0fb3b45d1a18bc30f922dfc8cb5c9e8ba7d00f8ddd1d84c2f9de68f",
 "static/passive.js": "4d1ee6e0fafd2467c6c65c8ce69079e403a4464a57a37dc8de14447a67db1465"
}
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

def mission_control_v3_package_identity()->dict[str,str]:
 observed={}
 for name,expected in sorted(MISSION_CONTROL_V3_REQUIRED_SHA256.items()):
  path=MISSION_CONTROL_V3_ROOT/name
  if not path.is_file():raise Deny("MISSION_CONTROL_V3_PACKAGE_MISSING:"+name)
  actual=sha256_file(path)
  if actual!=expected:raise Deny("MISSION_CONTROL_V3_PACKAGE_IDENTITY:"+name+":"+actual)
  observed[name]=actual
 return observed

def mission_control_v3_install(request:dict[str,Any])->dict[str,Any]:
 head,tree,_=mission64_require_envelope(request,worker=False);mission64_verify_current(head,tree)
 package_identity=mission_control_v3_package_identity()
 MISSION_CONTROL_V3_DROPIN.parent.mkdir(parents=True,exist_ok=True)
 current=MISSION_CONTROL_V3_DROPIN.read_bytes() if MISSION_CONTROL_V3_DROPIN.is_file() else None
 if current is not None:
  backup=MISSION64_STATE/"mission-control-backups"/("99-v3-control."+sha256(current)+"."+datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")+".bak");backup.parent.mkdir(parents=True,exist_ok=True);backup.write_bytes(current);os.chmod(backup,0o400)
 raw=MISSION_CONTROL_V3_DROPIN_TEXT.encode();fd,tmpname=tempfile.mkstemp(prefix=".99-v3-control.",suffix=".tmp",dir=str(MISSION_CONTROL_V3_DROPIN.parent));tmp=Path(tmpname)
 try:
  with os.fdopen(fd,"wb") as h:h.write(raw);h.flush();os.fsync(h.fileno())
  os.chmod(tmp,0o644);os.replace(tmp,MISSION_CONTROL_V3_DROPIN)
 finally:
  if tmp.exists():tmp.unlink()
 for argv in (["/bin/systemctl","daemon-reload"],["/bin/systemctl","restart",MISSION_CONTROL_V3_UNIT]):
  proc=subprocess.run(argv,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,shell=False,check=False,timeout=60)
  if proc.returncode!=0:raise Deny("MISSION_CONTROL_V3_SYSTEMD:"+(proc.stderr or proc.stdout).decode("utf-8","replace")[-2000:])
 import time as _time
 end=_time.time()+20;loc=None
 while _time.time()<end:
  active=subprocess.run(["/bin/systemctl","is-active","--quiet",MISSION_CONTROL_V3_UNIT],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,check=False).returncode==0
  if active and MISSION_CONTROL_V3_LOCATOR.is_file():
   try:
    loc=json.loads(MISSION_CONTROL_V3_LOCATOR.read_text(encoding="utf-8"))
    if loc.get("port")==8766 and loc.get("generation")=="MISSION_CONTROL_V3":break
   except Exception:pass
  _time.sleep(.25)
 else:raise Deny("MISSION_CONTROL_V3_NOT_READY")
 result={"installed":True,"unit":MISSION_CONTROL_V3_UNIT,"port":8766,"source_sha256":package_identity["mission_control_v3.py"],"package_identity":package_identity,"package_digest":sha256(canonical(package_identity)),"dropin_sha256":sha256(raw),"locator":loc}
 result.update(mission64_receipt(request,result));return result


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
                "MISSION64_PRECHECK",
                "MISSION64_START",
                "MISSION64_READ",
                "MISSION64_PAUSE",
                "MISSION64_RESUME",
                "MISSION64_RESTART_ONE",
                "MISSION64_VALIDATE",
                "MISSION64_STOP",
                "MISSION_CONTROL_V3_INSTALL",
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

    if operation == "MISSION_CONTROL_V3_INSTALL":
        return mission_control_v3_install(request)

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