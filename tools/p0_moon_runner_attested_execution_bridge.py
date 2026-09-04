from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import pwd
import socket
import stat
import subprocess

from cyber_lion.contracts.complete_mediation import EffectSurfaceInventory
from tools.p0_moon_runner_attested_bridge_contract import (
    AGENT,
    CONTROL_ISSUE,
    HOST,
    JOB_ID,
    MACHINE,
    OPERATIONS,
    OS_USER,
    POOL,
    RUNNER,
    UID,
    WORKFLOW,
    WORKFLOW_PATH,
    RunnerAttestationContractError,
    RunnerAttestedBridgeSpec,
    RunnerAttestedOperationReceipt,
    RunnerExecutionAttestation,
)
from tools.p0_moon_same_connection_denial_carrier import (
    MoonCarrierExecutionIdentity,
    MoonDenialExecutionCarrierCandidate,
    MoonObservationExecutionCarrierCandidate,
)

EXPECTED_SCAN_DIGEST = "d345e96fb1c7c8c4c1ee9bea5672b64d51f290ce7129c860dbf97a5a7907cae2"
RUNNER_METADATA_PATH = Path("/opt/lion/github-runner/.runner")
RUNNER_WORKER_PATH = Path("/opt/lion/github-runner/bin/Runner.Worker")
_ALLOWED_GIT_REV_PARSE = {"HEAD", "HEAD^{tree}"}


class RunnerAttestationError(RuntimeError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _validate_local_identity(*, uid: int, user: str, hostname: str, machine_id: str) -> None:
    if (uid, user, hostname, machine_id) != (UID, OS_USER, HOST, MACHINE):
        raise RunnerAttestationError("local execution identity mismatch")


def _validate_runner_metadata_payload(payload: object) -> None:
    if not isinstance(payload, dict):
        raise RunnerAttestationError("local runner metadata invalid")
    if (
        payload.get("agentId"),
        payload.get("agentName"),
        payload.get("poolName"),
    ) != (AGENT, RUNNER, POOL):
        raise RunnerAttestationError("local runner metadata mismatch")


def _load_runner_metadata() -> dict[str, object]:
    try:
        metadata_stat = RUNNER_METADATA_PATH.lstat()
    except FileNotFoundError as exc:
        raise RunnerAttestationError("local runner metadata unavailable") from exc
    if (
        stat.S_ISLNK(metadata_stat.st_mode)
        or not stat.S_ISREG(metadata_stat.st_mode)
        or metadata_stat.st_uid != UID
        or (metadata_stat.st_mode & 0o077) != 0
    ):
        raise RunnerAttestationError("local runner metadata identity unsafe")
    try:
        payload = json.loads(RUNNER_METADATA_PATH.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RunnerAttestationError("local runner metadata unreadable") from exc
    _validate_runner_metadata_payload(payload)
    return payload


def _validate_github_environment(env: dict[str, str]) -> None:
    required = (
        "GITHUB_ACTIONS",
        "GITHUB_RUN_ID",
        "GITHUB_JOB",
        "GITHUB_WORKFLOW",
        "GITHUB_WORKFLOW_REF",
        "GITHUB_REF",
        "GITHUB_SHA",
        "GITHUB_WORKSPACE",
        "RUNNER_NAME",
    )
    for name in required:
        if not env.get(name):
            raise RunnerAttestationError(f"{name} missing")
    if env["GITHUB_ACTIONS"] != "true":
        raise RunnerAttestationError("GITHUB_ACTIONS invalid")
    if env["RUNNER_NAME"] != RUNNER:
        raise RunnerAttestationError("RUNNER_NAME mismatch")
    if env["GITHUB_JOB"] != JOB_ID:
        raise RunnerAttestationError("GITHUB_JOB mismatch")
    if env["GITHUB_WORKFLOW"] != WORKFLOW:
        raise RunnerAttestationError("GITHUB_WORKFLOW mismatch")
    if not env["GITHUB_RUN_ID"].isdigit() or int(env["GITHUB_RUN_ID"]) <= 0:
        raise RunnerAttestationError("GITHUB_RUN_ID invalid")
    workflow_prefix = f"DonkeyJJLove/ai_platform/{WORKFLOW_PATH}@"
    if env["GITHUB_WORKFLOW_REF"] != workflow_prefix + env["GITHUB_REF"]:
        raise RunnerAttestationError("GITHUB_WORKFLOW_REF mismatch")


def _git_value(workspace: Path, selector: str) -> str:
    if selector not in _ALLOWED_GIT_REV_PARSE:
        raise RunnerAttestationError("git selector denied")
    result = subprocess.run(
        ["git", "rev-parse", selector],
        cwd=workspace,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise RunnerAttestationError("git identity unavailable")
    value = result.stdout.strip()
    if len(value) != 40 or any(ch not in "0123456789abcdef" for ch in value):
        raise RunnerAttestationError("git identity malformed")
    return value


def _parent_pid(pid: int) -> int:
    for line in Path(f"/proc/{pid}/status").read_text(encoding="utf-8").splitlines():
        if line.startswith("PPid:"):
            return int(line.split()[1])
    return 0


def _attested_worker_ancestor() -> str:
    expected_worker = RUNNER_WORKER_PATH.resolve()
    pid = os.getpid()
    seen: set[int] = set()
    while pid > 1 and pid not in seen:
        seen.add(pid)
        try:
            executable = Path(os.readlink(f"/proc/{pid}/exe")).resolve()
        except OSError:
            executable = None
        if executable == expected_worker:
            worker_stat = RUNNER_WORKER_PATH.stat()
            if worker_stat.st_uid != 0 or (worker_stat.st_mode & 0o022):
                raise RunnerAttestationError("Runner.Worker binary trust invalid")
            return _sha256_file(RUNNER_WORKER_PATH)
        try:
            pid = _parent_pid(pid)
        except (OSError, ValueError):
            break
    raise RunnerAttestationError("GitHub Runner.Worker ancestry missing")


def capture_runner_attestation() -> RunnerExecutionAttestation:
    uid = os.geteuid()
    try:
        user = pwd.getpwuid(uid).pw_name
    except KeyError as exc:
        raise RunnerAttestationError("OS principal unavailable") from exc
    hostname = socket.gethostname()
    machine_id = Path("/etc/machine-id").read_text(encoding="ascii").strip()
    _validate_local_identity(uid=uid, user=user, hostname=hostname, machine_id=machine_id)
    _load_runner_metadata()

    env = {
        key: os.environ.get(key, "")
        for key in (
            "GITHUB_ACTIONS",
            "GITHUB_RUN_ID",
            "GITHUB_JOB",
            "GITHUB_WORKFLOW",
            "GITHUB_WORKFLOW_REF",
            "GITHUB_REF",
            "GITHUB_SHA",
            "GITHUB_WORKSPACE",
            "RUNNER_NAME",
        )
    }
    _validate_github_environment(env)

    workspace = Path(env["GITHUB_WORKSPACE"]).resolve()
    if workspace != Path.cwd().resolve():
        raise RunnerAttestationError("workspace/cwd mismatch")
    revision = _git_value(workspace, "HEAD")
    tree = _git_value(workspace, "HEAD^{tree}")
    if revision != env["GITHUB_SHA"]:
        raise RunnerAttestationError("GITHUB_SHA mismatch")
    worker_binary_sha256 = _attested_worker_ancestor()

    return RunnerExecutionAttestation(
        revision=revision,
        tree=tree,
        runner_name=RUNNER,
        runner_agent_id=AGENT,
        pool_name=POOL,
        os_user=user,
        uid=uid,
        hostname=hostname,
        machine_id=machine_id,
        github_actions=env["GITHUB_ACTIONS"],
        run_id=env["GITHUB_RUN_ID"],
        job_id=env["GITHUB_JOB"],
        workflow=env["GITHUB_WORKFLOW"],
        workflow_ref=env["GITHUB_WORKFLOW_REF"],
        github_ref=env["GITHUB_REF"],
        github_sha=env["GITHUB_SHA"],
        worker_binary_sha256=worker_binary_sha256,
        observed_at=_now(),
    ).sealed()


def _carrier_identity(attestation: RunnerExecutionAttestation) -> MoonCarrierExecutionIdentity:
    attestation.validate()
    return MoonCarrierExecutionIdentity(
        attestation.revision,
        attestation.tree,
        attestation.runner_name,
        attestation.runner_agent_id,
        attestation.hostname,
        attestation.machine_id,
        CONTROL_ISSUE,
    ).validate()


def execute_fixed_operation(operation: str) -> RunnerAttestedOperationReceipt:
    if operation not in OPERATIONS:
        raise RunnerAttestationError("unknown operation")
    attestation = capture_runner_attestation()
    identity = _carrier_identity(attestation)
    if operation == "OBSERVE_SCHEMA":
        result_receipt = MoonObservationExecutionCarrierCandidate.execute_schema(identity)
        result = "OBSERVED"
    elif operation == "OBSERVE_SAME_CONNECTION_PRAGMA":
        result_receipt = MoonObservationExecutionCarrierCandidate.execute_same_connection_pragma(identity)
        result = "OBSERVED"
    else:
        attack_id = operation.removeprefix("DENY_")
        result_receipt = MoonDenialExecutionCarrierCandidate.execute(attack_id, identity)
        result = "DENIED"
    return RunnerAttestedOperationReceipt(
        attestation_digest=attestation.attestation_digest,
        run_id=attestation.run_id,
        job_id=attestation.job_id,
        workflow_ref=attestation.workflow_ref,
        revision=attestation.revision,
        tree=attestation.tree,
        runner_name=attestation.runner_name,
        runner_agent_id=attestation.runner_agent_id,
        os_user=attestation.os_user,
        uid=attestation.uid,
        hostname=attestation.hostname,
        machine_id=attestation.machine_id,
        operation=operation,
        result=result,
        result_digest=result_receipt.receipt_digest,
        observed_at=_now(),
    ).sealed()


def bridge_spec(revision: str) -> RunnerAttestedBridgeSpec:
    return RunnerAttestedBridgeSpec(
        revision=revision,
        workflow_path=WORKFLOW_PATH,
        operations=OPERATIONS,
        runner_name=RUNNER,
        runner_agent_id=AGENT,
        os_user=OS_USER,
        uid=UID,
        hostname=HOST,
        machine_id=MACHINE,
        control_issue=CONTROL_ISSUE,
        permissions=("contents:read",),
        workflow_dispatch_only=True,
        independent_post_run_verify=True,
        require_run_head_sha_exact=True,
        require_job_runner_name_exact=True,
        require_job_runner_id_if_exposed=True,
        require_job_terminal=True,
        require_receipt_identity_match=True,
        generic_shell=False,
        arbitrary_command=False,
        arbitrary_path=False,
        arbitrary_module=False,
        live_execution=False,
        state="CANDIDATE_UNATTACHED",
    ).validate()


def materialize_bridge_candidate(*, inventory: EffectSurfaceInventory) -> RunnerAttestedBridgeSpec:
    inventory.validate()
    if inventory.scan_digest != EXPECTED_SCAN_DIGEST:
        raise RunnerAttestationError("production scan digest drift")
    return bridge_spec(inventory.revision)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--operation", required=True, choices=OPERATIONS)
    args = parser.parse_args(argv)
    receipt = execute_fixed_operation(args.operation)
    print(json.dumps(asdict(receipt), sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
