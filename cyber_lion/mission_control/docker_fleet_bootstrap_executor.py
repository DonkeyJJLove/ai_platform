"""Bounded one-shot Docker fleet bootstrap effect consumer for LION R24.

This executor does NOT issue authority or admission, schedule assignments,
change mission DB state, or run scripts emitted by models. Only a canonical,
durably sourced RuntimeAdmission from the existing admission path can cross
this effect boundary. Existing legacy worker identity drift blocks any effect.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Any, Callable, Mapping, Protocol

from cyber_lion.contracts.runtime_enforcement import (
    RuntimeAdmission, RuntimeIdentityBinding, RequestedRuntimeEffect,
)
from cyber_lion.contracts.runtime_execution import RuntimeAdmissionSourceTrustBinding
from cyber_lion.enterprise.live_authority_admission import LiveAdmittedAuthority, LiveAuthorityAdmission
from cyber_lion.enterprise.runtime_execution import (
    SQLiteRuntimeAdmissionSource, SQLiteAdmissionConsumptionGuard,
)
from cyber_lion.mission_control.docker_local_fleet_plan import (
    classify_existing_docker_runtime, deterministic_fleet_plan, inspect_observed_fleet,
)

ACTION = "DOCKER_FLEET_BOOTSTRAP"
RESOURCE = "docker://MOON/lion-r24-autonomy"
EXECUTOR_ID = "LION_R24_DOCKER_BOOTSTRAP_EXECUTOR"
PROJECT = "lion-r24-autonomy"
RUNTIME_PATH = Path("/srv/lion-e4-candidate-r1/r20-mission/r24-autonomy")
CURRENTNESS_PATH = Path("/mnt/c/Users/d2j3/AppData/Local/LION/r24-autonomy/fleet-currentness.json")


class DockerFleetBootstrapError(RuntimeError):
    pass


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise DockerFleetBootstrapError(code)


def _canon(value: Mapping[str, Any]) -> bytes:
    return json.dumps(dict(value), ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def _strict_object(path: Path) -> dict[str, Any]:
    _require(path.is_file() and not path.is_symlink(), "RUNTIME_FILE_UNAVAILABLE")
    raw = path.read_bytes()
    _require(len(raw) <= 2**20, "RUNTIME_SOURCE_TOO_LARGE")
    def unique(pairs):
        d = {}
        for k, v in pairs:
            _require(k not in d, "DUPLICATE_RUNTIME_KEY")
            d[k] = v
        return d
    try:
        obj = json.loads(raw.decode("utf-8"), object_pairs_hook=unique)
    except (UnicodeError, ValueError, TypeError) as exc:
        raise DockerFleetBootstrapError("MALFORMED_RUNTIME_JSON") from exc
    _require(type(obj) is dict, "RUNTIME_OBJECT_EXPECTED")
    return obj


def _require_plan(plan: Mapping[str, Any]) -> None:
    # Existing sealed source-only planner owns the topology declaration.
    _require(isinstance(plan, Mapping), "BOOTSTRAP_PLAN_REQUIRED")
    no_fleet = {"host": "MOON", "docker_engine": "docker-desktop",
                "currentness": {"workers": []}}
    inspect_observed_fleet(plan, no_fleet)
    _require(plan.get("host") == "MOON"
             and plan.get("compose_project") == PROJECT
             and plan.get("material_count") == 32,
             "EXACT_MOON_FLEET_REQUIRED")


def _canonical_admission(
    source: Any,
    trust: RuntimeAdmissionSourceTrustBinding,
    admission: RuntimeAdmission,
    effect: RequestedRuntimeEffect,
    identity: RuntimeIdentityBinding,
    plan: Mapping[str, Any],
    admitted_authority: LiveAdmittedAuthority,
    authority_verifier: LiveAuthorityAdmission,
) -> RuntimeAdmission:
    _require(type(trust) is RuntimeAdmissionSourceTrustBinding,
             "ADMISSION_SOURCE_TRUST_REQUIRED")
    trust.validate()
    actual = (
        getattr(source, "source_id", None),
        getattr(source, "source_instance_id", None),
        getattr(source, "implementation_digest", None),
        getattr(source, "trust_anchor_id", None),
        getattr(source, "trust_anchor_digest", None),
    )
    _require(actual == trust.binding(), "ADMISSION_SOURCE_SUBSTITUTION")
    _require(type(admission) is RuntimeAdmission
             and type(effect) is RequestedRuntimeEffect
             and type(identity) is RuntimeIdentityBinding,
             "EXACT_RUNTIME_TYPES_REQUIRED")
    admission.validate()
    effect.validate()
    identity.validate()
    try:
        canonical = source.resolve(admission.admission_digest)
        current = source.is_current(admission.admission_digest)
    except Exception as exc:
        raise DockerFleetBootstrapError("CANONICAL_ADMISSION_UNAVAILABLE") from exc
    _require(type(canonical) is RuntimeAdmission and canonical == admission
             and current is True, "STALE_OR_SUBSTITUTED_ADMISSION")
    _require(effect.action_class == ACTION and effect.resource == RESOURCE,
             "EFFECT_CLASS_OR_RESOURCE_DENIED")
    _require(effect.payload_digest == plan["plan_digest"]
             and admission.requested_effect_digest == effect.digest(),
             "FLEET_PLAN_EFFECT_DIGEST_DRIFT")
    _require(effect.mission_id == plan["mission_id"]
             and effect.runtime_identity_digest == identity.digest(),
             "FLEET_EFFECT_IDENTITY_DRIFT")
    _require(identity.execution_subject == EXECUTOR_ID
             and identity.workload_identity == EXECUTOR_ID
             and identity.runtime_instance_id == "MOON_DOCKER_DESKTOP_R24",
             "WRONG_BOOTSTRAP_EXECUTOR")
    _require(admission.runtime_identity_digest == identity.digest()
             and admission.provisioned_executor_digest == identity.provisioned_executor_digest,
             "PROVISIONED_RUNTIME_IDENTITY_DRIFT")
    _require(type(admitted_authority) is LiveAdmittedAuthority
             and type(authority_verifier) is LiveAuthorityAdmission,
             "EXACT_LIVE_AUTHORITY_REQUIRED")
    admitted_authority.validate()
    _require(admitted_authority.mission_id == plan["mission_id"]
             and admitted_authority.digest() == admission.live_authority_digest
             and admitted_authority.lineage_digest == admission.authority_lineage_digest,
             "LIVE_AUTHORITY_SUBSTITUTION")
    try:
        fresh_authority = authority_verifier.revalidate(
            admitted_authority, now=datetime.now(timezone.utc),
        )
    except Exception as exc:
        raise DockerFleetBootstrapError("LIVE_AUTHORITY_REVALIDATION_FAILED") from exc
    _require(type(fresh_authority) is LiveAdmittedAuthority
             and fresh_authority == admitted_authority,
             "LIVE_AUTHORITY_NOT_CURRENT")
    _require(admission.authority_lineage_digest == effect.authority_lineage_digest
             and admission.policy_binding == effect.policy_binding
             and admission.observability_state == effect.observability_state
             and admission.effective_authority == effect.requested_authority
             and admission.effective_authority.lower() not in ("none", "read_only"),
             "RUNTIME_ADMISSION_SCOPE_DRIFT")
    return canonical


def _activated_source(mission: Mapping[str, Any], plan: Mapping[str, Any]) -> None:
    _require(isinstance(mission, Mapping), "CANONICAL_MISSION_MISSING")
    _require(mission.get("mission_id") == plan["mission_id"]
             and mission.get("source_head") == plan["source_head"]
             and mission.get("source_tree") == plan["source_tree"]
             and mission.get("spec_digest") == plan["lpcl_digest"],
             "MISSION_SOURCE_OR_IDENTITY_DRIFT")
    _require(mission.get("state") in ("AUTHORIZED", "RUNNING")
             and (mission.get("process") or {}).get("authority_state")
             == "EXPLICIT_USER_ACTIVATION",
             "EXPLICIT_OPERATOR_LPCL_ACTIVATION_REQUIRED")
    _require(mission.get("adapter") in (None, "LPCL_DOCKER_LOCAL_MODEL", "LPCL_MISSION"),
             "BOOTSTRAP_MISSION_ADAPTER_DRIFT")
    operator = mission.get("operator_control") or {}
    _require(isinstance(operator, Mapping) and operator.get("autonomy_allowed") is not False,
             "OPERATOR_FENCE_CLOSED")


class FleetRuntime(Protocol):
    """Narrow host executor. It never issues an admission or mission state."""
    def compose_config(self) -> Mapping[str, Any]: ...
    def identity_and_receipt(self) -> tuple[dict[str, Any], dict[str, Any]]: ...
    def runtime_attestation(self) -> dict[str, Any]: ...
    def container_inventory(self) -> list[dict[str, Any]]: ...
    def start_exact_compose(self) -> None: ...
    def observe_currentness(self) -> dict[str, Any]: ...
    def persist_receipt(self, receipt: Mapping[str, Any]) -> str: ...


class MoonDockerComposeRuntime:
    """Concrete MOON R24 Compose adapter; no arbitrary path or shell command."""

    def __init__(self, *, runtime: Path = RUNTIME_PATH):
        _require(runtime == RUNTIME_PATH, "UNAPPROVED_DOCKER_RUNTIME_ROOT")
        _require(runtime.is_dir() and not runtime.is_symlink()
                 and runtime.resolve(strict=True) == runtime,
                 "RUNTIME_ROOT_UNAVAILABLE")
        self.runtime = runtime

    @staticmethod
    def _run(args: list[str], *, cwd: Path | None = None, timeout: int = 60) -> str:
        try:
            return subprocess.check_output(args, cwd=cwd, timeout=timeout,
                                           stderr=subprocess.PIPE).decode("utf-8")
        except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
            raise DockerFleetBootstrapError("DOCKER_COMMAND_FAILED") from exc

    def compose_config(self) -> Mapping[str, Any]:
        value = json.loads(self._run([
            "docker", "compose", "-p", PROJECT,
            "-f", str(self.runtime / "compose.yaml"), "config", "--format", "json",
        ], cwd=self.runtime, timeout=35))
        _require(isinstance(value, dict), "COMPOSE_CONFIG_INVALID")
        self.validate_compose_security(value)
        return value

    @staticmethod
    def validate_compose_security(value: Mapping[str, Any]) -> None:
        services = value.get("services")
        _require(isinstance(services, Mapping) and len(services) == 32,
                 "UNBOUNDED_COMPOSE_SERVICE_SET")
        ro = {
            "/src", "/runtime/worker.py", "/identity/current.json",
            "/cooperative-provider-artifact", "/cooperative-provider",
            "/cooperative-control", "/mission-control",
        }
        rw = {"/status", "/gate", "/cooperative"}
        for index in range(1, 33):
            name = f"worker-{index:02d}"
            service = services.get(name)
            _require(isinstance(service, Mapping), "WORKER_SERVICE_MISSING")
            _require(service.get("image") == "lion-r20-worker:r1"
                     and service.get("entrypoint") == ["python3", "/runtime/worker.py"]
                     and service.get("read_only") is True
                     and service.get("privileged") in (None, False)
                     and "ALL" in (service.get("cap_drop") or [])
                     and not service.get("cap_add")
                     and "no-new-privileges:true" in (service.get("security_opt") or [])
                     and service.get("network_mode") != "host"
                     and not service.get("devices") and not service.get("ports")
                     and int(service.get("pids_limit") or 0) == 128
                     and str(service.get("mem_limit")) == "536870912"
                     and float(service.get("cpus") or 0) == 0.5,
                     "WORKER_SANDBOX_SECURITY_DRIFT:" + name)
            volumes = service.get("volumes")
            _require(isinstance(volumes, list) and len(volumes) == len(ro | rw),
                     "WORKER_MOUNT_COUNT_DRIFT:" + name)
            mounts = {}
            for item in volumes:
                _require(isinstance(item, Mapping)
                         and item.get("type") == "bind"
                         and isinstance(item.get("target"), str)
                         and isinstance(item.get("source"), str)
                         and item["target"] not in mounts,
                         "INVALID_WORKER_MOUNT:" + name)
                mounts[item["target"]] = item
            _require(set(mounts) == ro | rw, "WORKER_MOUNT_SCOPE_DRIFT:" + name)
            _require(all(mounts[t].get("read_only") is True for t in ro)
                     and all(mounts[t].get("read_only") in (None, False) for t in rw),
                     "WORKER_MOUNT_RW_DRIFT:" + name)
            for t in ("/src", "/runtime/worker.py", "/identity/current.json",
                      "/status", "/gate", "/cooperative"):
                _require(str(mounts[t]["source"]).startswith(
                    str(RUNTIME_PATH) + "/"),
                    "WORKER_MOUNT_OUTSIDE_RUNTIME:" + name)
            _require(mounts["/cooperative"]["source"].endswith(f"/private/MD{index:03d}"),
                     "WORKER_PRIVATE_DIRECTORY_DRIFT:" + name)

    def identity_and_receipt(self) -> tuple[dict[str, Any], dict[str, Any]]:
        from cyber_lion.mission_control.material_worker_runtime import load_worker_identity
        identity = load_worker_identity(
            self.runtime / "identity.json",
            self.runtime / "worker.py",
            self.runtime / "source/cyber_lion/mission_control/material_worker_runtime.py",
        )
        receipt = _strict_object(self.runtime / "materialization-receipt.json")
        # The old materializer may have produced a receipt for a *different*
        # source revision. Never repair that evidence by rewriting the receipt.
        for k in ("source_head", "source_tree", "identity_digest",
                  "worker_source_sha256", "runtime_contract_sha256", "compose_sha256"):
            _require(identity.get(k) == receipt.get(k),
                     "PREPARED_RUNTIME_SOURCE_RECEIPT_DRIFT:" + k)
        compose = self.runtime / "compose.yaml"
        _require(compose.is_file() and not compose.is_symlink()
                 and sha256(compose.read_bytes()).hexdigest() == identity.get("compose_sha256"),
                 "PREPARED_COMPOSE_BYTES_DRIFT")
        return identity, receipt

    def runtime_attestation(self) -> dict[str, Any]:
        info = self._run([
            "docker", "info", "--format", "{{.Name}}|{{.OSType}}",
        ], timeout=15).strip()
        _require(info == "docker-desktop|linux", "UNTRUSTED_DOCKER_ENGINE")
        image_id = self._run([
            "docker", "image", "inspect", "lion-r20-worker:r1",
            "--format", "{{.Id}}",
        ], timeout=20).strip()
        _require(len(image_id) == 71 and image_id.startswith("sha256:")
                 and all(x in "0123456789abcdef" for x in image_id[7:]),
                 "DOCKER_IMAGE_IDENTITY_MISSING")
        identity, _ = self.identity_and_receipt()
        return {
            "schema": "lion.r24-docker-fleet-attestation/v1",
            "host": "MOON", "docker_engine": "docker-desktop",
            "image_id": image_id,
            "source_head": identity["source_head"],
            "source_tree": identity["source_tree"],
            "compose_sha256": identity["compose_sha256"],
            "worker_source_sha256": identity["worker_source_sha256"],
            "runtime_contract_sha256": identity["runtime_contract_sha256"],
        }

    def container_inventory(self) -> list[dict[str, Any]]:
        names = [x.strip() for x in self._run([
            "docker", "ps", "-a", "--filter",
            "label=LION_WORKER_PROFILE=LION_MATERIAL_EXECUTOR_V2",
            "--format", "{{.Names}}",
        ], timeout=25).splitlines() if x.strip()]
        _require(len(names) <= 32 and len(set(names)) == len(names),
                 "UNEXPECTED_LION_CONTAINER_COUNT")
        if not names:
            return []
        parsed = json.loads(self._run(["docker", "inspect", *names], timeout=25))
        return [{
            "name": v["Name"],
            "container_id": v["Id"],
            "state": v["State"]["Status"],
            "labels": v["Config"]["Labels"],
        } for v in parsed]

    def start_exact_compose(self) -> None:
        # --no-recreate explicitly prevents replacing another mission's
        # containers. The caller must already possess a consumed admission.
        self._run([
            "docker", "compose", "-p", PROJECT,
            "-f", str(self.runtime / "compose.yaml"),
            "up", "-d", "--no-recreate",
        ], cwd=self.runtime, timeout=120)

    def observe_currentness(self) -> dict[str, Any]:
        # This existing producer queries docker inspect + worker heartbeats and
        # seals its JSON projection. Calling it is *not* an authority grant.
        self._run([sys.executable, str(self.runtime / "fleet-currentness.py")],
                  cwd=self.runtime, timeout=35)
        return _strict_object(CURRENTNESS_PATH)

    def persist_receipt(self, receipt: Mapping[str, Any]) -> str:
        data = _canon(receipt) + b"\n"
        target_dir = self.runtime / "fleet-bootstrap-receipts"
        _require(not target_dir.is_symlink(), "RECEIPT_STORAGE_SYMLINK")
        target_dir.mkdir(mode=0o700, exist_ok=True)
        _require(target_dir.is_dir() and target_dir.resolve(strict=True) == target_dir,
                 "RECEIPT_STORAGE_DRIFT")
        admission_digest = receipt.get("admission_digest")
        _require(isinstance(admission_digest, str)
                 and len(admission_digest) == 64
                 and all(c in "0123456789abcdef" for c in admission_digest),
                 "RECEIPT_ADMISSION_IDENTITY_INVALID")
        target = target_dir / (admission_digest + ".json")
        fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        return sha256(data).hexdigest()


class DockerFleetBootstrapExecutor:
    """Typed one-shot effect boundary; no model- or UI-provided raw argv."""

    def __init__(
        self, *,
        admission_source: Any,
        admission_source_trust: RuntimeAdmissionSourceTrustBinding,
        consumption_guard: Any,
        mission_source: Callable[[str], Mapping[str, Any]],
        fleet_runtime: FleetRuntime,
        authority_verifier: LiveAuthorityAdmission,
        readiness_checks: int = 90,
        sleep: Callable[[float], None] = time.sleep,
    ):
        _require(type(admission_source) is SQLiteRuntimeAdmissionSource,
                 "DURABLE_CANONICAL_ADMISSION_SOURCE_REQUIRED")
        _require(type(consumption_guard) is SQLiteAdmissionConsumptionGuard,
                 "DURABLE_ADMISSION_CONSUMPTION_REQUIRED")
        _require(callable(mission_source), "CANONICAL_MISSION_SOURCE_REQUIRED")
        self.source = admission_source
        self.trust = admission_source_trust
        self.guard = consumption_guard
        self.mission_source = mission_source
        _require(type(authority_verifier) is LiveAuthorityAdmission,
                 "LIVE_AUTHORITY_VERIFIER_REQUIRED")
        self.authority_verifier = authority_verifier
        _require(type(readiness_checks) is int and 1 <= readiness_checks <= 120,
                 "BOUNDED_READINESS_BUDGET_REQUIRED")
        _require(callable(sleep), "READINESS_SLEEP_REQUIRED")
        self.readiness_checks = readiness_checks
        self.sleep = sleep
        self.runtime = fleet_runtime

    def execute(
        self, *,
        plan: Mapping[str, Any],
        admission: RuntimeAdmission,
        effect: RequestedRuntimeEffect,
        runtime_identity: RuntimeIdentityBinding,
        admitted_authority: LiveAdmittedAuthority,
        execution_id: str,
    ) -> dict[str, Any]:
        _require_plan(plan)
        _require(isinstance(execution_id, str) and 0 < len(execution_id) <= 256,
                 "EXECUTION_ID_REQUIRED")
        canonical = _canonical_admission(
            self.source, self.trust, admission, effect, runtime_identity, plan,
            admitted_authority, self.authority_verifier,
        )
        mission = self.mission_source(plan["mission_id"])
        _activated_source(mission, plan)
        # Validate exact configured R24 Compose and independently pinned
        # materialized source, not the caller's proposed worker inventory.
        compose = self.runtime.compose_config()
        deterministic_fleet_plan(mission, compose)
        identity, receipt = self.runtime.identity_and_receipt()
        attestation = self.runtime.runtime_attestation()
        _require(sha256(_canon(attestation)).hexdigest()
                 == runtime_identity.runtime_attestation_digest,
                 "DOCKER_IMAGE_AND_SOURCE_ATTESTATION_DRIFT")
        current = self.runtime.container_inventory()
        pre = classify_existing_docker_runtime(plan, current, identity, receipt)
        _require(pre["state"] in ("ABSENT", "RESTART_CANDIDATE", "OBSERVED_RUNNING"),
                 "DOCKER_PRE_EFFECT_BLOCKED:" + pre["reason"])
        # Even if no containers exist, an independently prepared runtime must
        # already match this exact LPCL source and its own materialization receipt.
        _require(identity.get("source_head") == plan["source_head"]
                 and identity.get("source_tree") == plan["source_tree"]
                 and receipt.get("source_head") == identity.get("source_head")
                 and receipt.get("identity_digest") == identity.get("identity_digest"),
                 "MATERIALIZED_RUNTIME_NOT_FOR_THIS_SOURCE")

        if pre["state"] == "OBSERVED_RUNNING":
            currentness = self.runtime.observe_currentness()
            check = inspect_observed_fleet(plan, {
                "host": "MOON", "docker_engine": "docker-desktop",
                "currentness": currentness,
            })
            _require(check["state"] == "SOURCE_BOUND_READY",
                     "RUNNING_COHORT_NOT_RECONCILED")
            return {
                "schema": "lion.r24-docker-bootstrap-effect/v1",
                "result": "ALREADY_SOURCE_BOUND_READY",
                "mission_id": plan["mission_id"],
                "plan_digest": plan["plan_digest"],
                "admission_digest": canonical.admission_digest,
                "effect_applied": False,
                "fleet_currentness_digest": currentness["currentness_digest"],
                "authority_effect": "NONE",
            }

        # The final re-read protects the interval between source preflight and
        # actual effect. Source/admission might have become stale meanwhile.
        _activated_source(self.mission_source(plan["mission_id"]), plan)
        _canonical_admission(self.source, self.trust, admission, effect,
                             runtime_identity, plan, admitted_authority,
                             self.authority_verifier)
        _require(self.runtime.compose_config() == compose
                 and self.runtime.identity_and_receipt() == (identity, receipt)
                 and self.runtime.runtime_attestation() == attestation,
                 "PREPARED_RUNTIME_CHANGED_PRE_EFFECT")
        _require(self.runtime.container_inventory() == current,
                 "DOCKER_INVENTORY_CHANGED_PRE_EFFECT")
        try:
            consumed = self.guard.consume(canonical.admission_digest, execution_id)
        except Exception as exc:
            raise DockerFleetBootstrapError("ADMISSION_CONSUMPTION_UNAVAILABLE") from exc
        _require(consumed is True, "DUPLICATE_DOCKER_BOOTSTRAP_ADMISSION")

        observed = None
        error = None
        try:
            self.runtime.start_exact_compose()
            for probe in range(self.readiness_checks):
                try:
                    observed = self.runtime.observe_currentness()
                    check = inspect_observed_fleet(plan, {
                        "host": "MOON", "docker_engine": "docker-desktop",
                        "currentness": observed,
                    })
                    if check["state"] == "SOURCE_BOUND_READY":
                        break
                except (DockerFleetBootstrapError, ValueError, OSError):
                    # A transient heartbeat/observer read must not trigger a
                    # second docker compose up. Retry observation only.
                    pass
                if probe + 1 < self.readiness_checks:
                    self.sleep(1.0)
            else:
                raise DockerFleetBootstrapError("DOCKER_READINESS_PROOF_NOT_OBSERVED")
        except Exception as exc:
            # The admission is consumed; a repeated start is forbidden until
            # another authorized mission action independently reconciles it.
            error = type(exc).__name__
        record = {
            "schema": "lion.r24-docker-bootstrap-effect/v1",
            "result": "OBSERVED" if error is None else "EFFECT_UNKNOWN_RECONCILE",
            "mission_id": plan["mission_id"],
            "plan_digest": plan["plan_digest"],
            "source_head": plan["source_head"],
            "source_tree": plan["source_tree"],
            "execution_id": execution_id,
            "admission_digest": canonical.admission_digest,
            "requested_effect_digest": effect.digest(),
            "runtime_identity_digest": runtime_identity.digest(),
            "preflight_state": pre["state"],
            "effect_applied": True,
            "fleet_currentness_digest": observed.get("currentness_digest") if error is None else None,
            "reported_error_class": error,
            "retries_permitted": False,
            "authority_effect": "ALREADY_ADMITTED_BOUNDED_MATERIAL_EFFECT",
        }
        receipt_digest = self.runtime.persist_receipt(record)
        return {**record, "receipt_sha256": receipt_digest}
