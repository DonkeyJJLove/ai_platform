#!/usr/bin/env python3
"""R11 read-only R24 fleet recovery preflight.

This is a diagnostic of an existing Docker cohort and candidate *source*.
It never starts, stops, claims, provisions, registers or admits execution.
The existing MoonDockerComposeRuntime and cooperative readiness owners
retain the decisive contract checks.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cyber_lion.mission_control.cooperative_production import (
    CooperativeProductionError, bootstrap_readiness,
)
from cyber_lion.mission_control.docker_fleet_bootstrap_executor import (
    DockerFleetBootstrapError, MoonDockerComposeRuntime,
)
from cyber_lion.mission_control.material_worker_runtime import load_worker_identity

SCHEMA = "lion.r11-fleet-recovery-source-preflight/v1"
RUNTIME = Path("/srv/lion-e4-candidate-r1/r20-mission/r24-autonomy")
CANONICAL = Path("LION/runtime_compat/r24/docker-autonomy")
EXPECTED = tuple(f"MD{i:03d}" for i in range(1, 33))
ID_RE = re.compile(r"[0-9a-f]{40}\Z")
SOURCE_FILES = {
    "compose.yaml": (Path("compose.yaml"), CANONICAL / "compose.yaml"),
    "worker.py": (Path("worker.py"), CANONICAL / "worker.py"),
    "fleet-currentness.py": (Path("fleet-currentness.py"), CANONICAL / "fleet-currentness.py"),
    "material_worker_runtime.py": (
        Path("source/cyber_lion/mission_control/material_worker_runtime.py"),
        Path("cyber_lion/mission_control/material_worker_runtime.py"),
    ),
}


class PreflightError(ValueError):
    pass


def _read(argv: list[str], *, cwd: Path | None = None) -> str:
    # Exact argv allowlist. In particular 'docker compose up' must never
    # become executable merely because 'docker compose config' is permitted.
    inspect_names = [f"lion-r24-md{i:03d}" for i in range(1, 33)]
    inspect_ok = argv == [
        "docker", "inspect", "--format", "{{json .}}", *inspect_names
    ]
    compose_ok = (
        len(argv) == 11
        and argv[:6] == ["docker", "compose", "-p", "lion-r24-autonomy",
                          "--project-directory", str(RUNTIME)]
        and argv[6] == "-f"
        and (argv[7] == str(RUNTIME / "compose.yaml")
             or argv[7].endswith("/LION/runtime_compat/r24/docker-autonomy/compose.yaml"))
        and argv[8:] == ["config", "--format", "json"]
    )
    git_ok = (
        len(argv) == 5
        and argv[:2] == ["git", "-C"]
        and isinstance(argv[2], str) and Path(argv[2]).is_absolute()
        and argv[3] == "rev-parse"
        and argv[4] in {"HEAD", "HEAD^{tree}"}
    )
    if not (inspect_ok or compose_ok or git_ok):
        raise PreflightError("non-read-only command denied")
    try:
        value = subprocess.check_output(
            argv, cwd=cwd, text=True, stderr=subprocess.PIPE, timeout=25,
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        raise PreflightError("read-only command unavailable") from exc
    if len(value) > 8_000_000:
        raise PreflightError("observation size exceeded")
    return value


def _sha(path: Path) -> str | None:
    if not path.is_file() or path.is_symlink():
        return None
    return sha256(path.read_bytes()).hexdigest()


def _time(raw: object) -> datetime | None:
    if not isinstance(raw, str):
        return None
    try:
        value = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return value.astimezone(timezone.utc) if value.tzinfo is not None else None
    except (TypeError, ValueError, OverflowError):
        return None


def classify_containers(rows: list[dict]) -> dict:
    """Pure source-independent observation; never a runtime admission."""
    if type(rows) is not list or len(rows) != 32:
        return {"state": "UNKNOWN", "reason": "EXACT_32_CONTAINERS_NOT_OBSERVED",
                "observed": len(rows) if isinstance(rows, list) else None}
    names, ids, instances = set(), set(), set()
    stopped, running, exit_137, docker_oom = 0, 0, 0, 0
    finished: list[datetime] = []
    for idx, row in enumerate(rows, 1):
        if type(row) is not dict or any(
            field not in row for field in ("Name", "Id", "State", "Config")
        ):
            return {"state": "UNKNOWN", "reason": "CONTAINER_OBSERVATION_INCOMPLETE"}
        name, container_id = row["Name"], row["Id"]
        labels = (row.get("Config") or {}).get("Labels") or {}
        if (
            name != f"/lion-r24-md{idx:03d}"
            or labels.get("LION_MATERIAL_WORKER_ID") != EXPECTED[idx-1]
            or labels.get("LION_WORKER_PROFILE") != "LION_MATERIAL_EXECUTOR_V2"
            or labels.get("com.docker.compose.project") != "lion-r24-autonomy"
            or not isinstance(container_id, str) or len(container_id) != 64
            or name in names or container_id in ids
        ):
            return {"state": "UNKNOWN", "reason": "CONTAINER_IDENTITY_OR_PROJECT_DRIFT"}
        names.add(name)
        ids.add(container_id)
        instances.add((row.get("Image"), row.get("Config", {}).get("Image")))
        state = row["State"]
        if not isinstance(state, dict):
            return {"state": "UNKNOWN", "reason": "CONTAINER_STATE_UNAVAILABLE"}
        stopped += state.get("Status") == "exited"
        running += state.get("Status") == "running"
        exit_137 += state.get("ExitCode") == 137
        docker_oom += state.get("OOMKilled") is True
        finish = _time(state.get("FinishedAt"))
        if finish is not None:
            finished.append(finish)
    span = (max(finished)-min(finished)).total_seconds() if len(finished)==32 else None
    if stopped == 32:
        status = "STOPPED_COHORT"
    elif running == 32:
        status = "RUNNING_NOT_YET_QUALIFIED"
    else:
        status = "MIXED_COHORT"
    return {
        "state": status, "observed": 32, "running": running, "exited": stopped,
        "exit_code_137": exit_137, "docker_oomkilled": docker_oom,
        "finished_span_seconds": round(span, 6) if span is not None else None,
        "image_identity_pairs": len(instances),
        "authority_effect": "NONE",
    }


def classify_recovery(*, container: dict, installed_compose: str,
                      canonical_compose: str, installed_identity: str,
                      worker_readiness: str, file_comparison: dict,
                      missing_roots: list[str]) -> dict:
    """Categorize the migration need, never permit an effect."""
    drift = [name for name, pair in file_comparison.items()
             if pair["installed_sha256"] != pair["candidate_sha256"]]
    reasons = []
    if container.get("state") != "STOPPED_COHORT":
        reasons.append("EXACT_PARKED_COHORT_UNPROVEN")
    if installed_compose != "WORKER_MOUNT_COUNT_DRIFT:worker-01":
        reasons.append("INSTALLED_COMPOSE_CLASSIFICATION_CHANGED")
    if canonical_compose != "PASS_SOURCE_STRUCTURE":
        reasons.append("CANDIDATE_COMPOSE_INVALID")
    if installed_identity != "MaterialWorkerContractError:worker assignment capability drift":
        reasons.append("LEGACY_SOURCE_CLASSIFICATION_CHANGED")
    required_delta = {"compose.yaml", "worker.py", "material_worker_runtime.py"}
    if set(drift) != required_delta or any(
        not v.get("installed_sha256") or not v.get("candidate_sha256")
        for v in file_comparison.values()
    ):
        reasons.append("EXACT_LEGACY_SOURCE_DELTA_UNPROVEN")
    if set(missing_roots) != {"private", "provider-artifact", "unbound"}:
        reasons.append("PRIVATE_ROOT_LAYOUT_CHANGED")
    if worker_readiness != "worker observation stale or unavailable MD001":
        reasons.append("WORKER_READINESS_MUST_BE_RECLASSIFIED")
    if (
        container.get("observed") != 32 or container.get("exited") != 32
        or container.get("exit_code_137") != 32
        or container.get("docker_oomkilled") != 0
        or container.get("image_identity_pairs") != 1
        or type(container.get("finished_span_seconds")) not in (int, float)
        or not 0 <= container["finished_span_seconds"] <= 1
    ):
        reasons.append("EXACT_STOPPED_COHORT_EVIDENCE_CHANGED")
    known = not reasons
    return {
        "classification": "LEGACY_R24_COHORT_REQUIRES_GOVERNED_UPGRADE"
            if known else "UNKNOWN_OR_CHANGED_HOLD",
        "source_delta_files": sorted(drift),
        "blockers": reasons if reasons else [
            "SOURCE_REBUILD_NOT_ADMITTED", "EXACT_OPERATOR_LPCL_NOT_LAUNCHED",
            "PROVIDER_BOOTSTRAP_NOT_BOUND", "INDEPENDENT_RUNTIME_CURRENTNESS_REQUIRED",
        ],
        "operation_allowed": False,
        "restart_allowed": False,
        "ready": False,
        "authority_effect": "NONE",
    }


def analyze(*, source_root: Path, runtime: Path = RUNTIME,
            expected_head: str | None = None) -> dict:
    if runtime != RUNTIME or not runtime.is_dir() or runtime.is_symlink():
        raise PreflightError("canonical MOON runtime path required")
    if not source_root.is_absolute() or not source_root.is_dir() or source_root.is_symlink():
        raise PreflightError("source root unavailable")
    if expected_head is not None and not ID_RE.fullmatch(expected_head):
        raise PreflightError("expected HEAD malformed")
    git_head = _read(["git", "-C", str(source_root), "rev-parse", "HEAD"]).strip()
    git_tree = _read(["git", "-C", str(source_root), "rev-parse", "HEAD^{tree}"]).strip()
    if not ID_RE.fullmatch(git_head) or not ID_RE.fullmatch(git_tree):
        raise PreflightError("Git source ref malformed")
    if expected_head and git_head != expected_head:
        raise PreflightError("expected source ref drift")

    names = [f"lion-r24-md{i:03d}" for i in range(1, 33)]
    raw = _read(["docker", "inspect", "--format", "{{json .}}", *names])
    try:
        containers = [json.loads(line) for line in raw.splitlines()]
    except (ValueError, TypeError) as exc:
        raise PreflightError("Docker inspect malformed") from exc
    cohort = classify_containers(containers)

    def compose(path: Path) -> str:
        raw = _read(["docker", "compose", "-p", "lion-r24-autonomy",
                     "--project-directory", str(runtime),
                     "-f", str(path), "config", "--format", "json"])
        try:
            value = json.loads(raw)
        except ValueError as exc:
            raise PreflightError("Docker compose projection malformed") from exc
        try:
            MoonDockerComposeRuntime.validate_compose_security(value)
        except DockerFleetBootstrapError as exc:
            return str(exc)
        return "PASS_SOURCE_STRUCTURE"

    installed_compose = compose(runtime / "compose.yaml")
    canonical_compose = compose(source_root / CANONICAL / "compose.yaml")
    try:
        load_worker_identity(runtime / "identity.json", runtime / "worker.py",
                             runtime / "source/cyber_lion/mission_control/material_worker_runtime.py")
        installed_identity = "PASS"
    except Exception as exc:
        installed_identity = type(exc).__name__ + ":" + str(exc)[:160]
    try:
        bootstrap_readiness(runtime / "status", expected_workers=32)
        worker_readiness = "PASS"
    except CooperativeProductionError as exc:
        worker_readiness = str(exc)[:160]

    comparisons = {
        name: {
            "installed_sha256": _sha(runtime / paths[0]),
            "candidate_sha256": _sha(source_root / paths[1]),
        }
        for name, paths in SOURCE_FILES.items()
    }
    missing = [name for name in ("private", "provider-artifact", "unbound")
               if not (runtime / name).is_dir()]
    result = classify_recovery(
        container=cohort, installed_compose=installed_compose,
        canonical_compose=canonical_compose, installed_identity=installed_identity,
        worker_readiness=worker_readiness, file_comparison=comparisons,
        missing_roots=missing,
    )
    return {
        "schema": SCHEMA,
        "observed_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "scope": "MOON_SOURCE_ONLY_RECOVERY_CLASSIFICATION",
        "source_head": git_head, "source_tree": git_tree,
        "container_observation": cohort,
        "installed_compose": installed_compose,
        "candidate_compose": canonical_compose,
        "installed_worker_identity": installed_identity,
        "worker_status_readiness": worker_readiness,
        "file_sha256": comparisons, "missing_private_roots": missing,
        "assessment": result,
        "source_preflight_only": True,
        "mission_registered": "NOT_INFERRED",
        "runtime_effect": "NONE", "authority_effect": "NONE",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only R11 MOON R24 source recovery preflight")
    parser.add_argument("--source-root", type=Path, default=ROOT)
    parser.add_argument("--expected-head", default=None)
    args = parser.parse_args(argv)
    try:
        result = analyze(source_root=args.source_root, expected_head=args.expected_head)
    except (PreflightError, OSError, ValueError) as exc:
        print(json.dumps({
            "schema": SCHEMA, "result": "READBACK_UNKNOWN_FAIL_CLOSED",
            "error_class": type(exc).__name__,
            "authority_effect": "NONE", "runtime_effect": "NONE",
        }, sort_keys=True))
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    # Successful diagnosis is NOT an admissible deployment and never returns READY.
    return 0 if result["assessment"]["classification"] == (
        "LEGACY_R24_COHORT_REQUIRES_GOVERNED_UPGRADE"
    ) else 3


if __name__ == "__main__":
    raise SystemExit(main())
