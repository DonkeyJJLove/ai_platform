"""Bounded bootstrap for installing the R6.10 cooperative runtime root in a worker.

The bootstrap does not create authority or infer it from environment variables. Environment
configuration only identifies trusted dependency material and private storage. The external
factory must return already-existing canonical admission/provisioning/currentness owners.

Default mode is UNBOUND: source deployment alone therefore cannot make a cooperative worker
READY. TRUSTED_EXTERNAL_R1 is fail-closed and requires a pinned external dependency module
outside the repository plus a private per-worker state root.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import importlib.util
import os
from pathlib import Path
import re
import stat
from types import ModuleType
from typing import Any, Callable, Mapping

from cyber_lion.contracts.executor_sandbox import ProvisioningBinding
from cyber_lion.contracts.runtime_currentness import CurrentnessSourceTrustBinding
from cyber_lion.contracts.runtime_enforcement import RuntimeIdentityBinding
from cyber_lion.contracts.runtime_execution import RuntimeAdmissionSourceTrustBinding
from cyber_lion.enterprise.cooperative_runtime_composition import CooperativeRuntimeContext
from cyber_lion.enterprise.cooperative_runtime_root import CooperativeRuntimeCompositionRoot
from cyber_lion.enterprise.live_authority_admission import LiveAuthorityAdmission
from cyber_lion.mission_control.cooperative_worker_runtime import (
    PROCESS_COOPERATIVE_RUNTIME,
    CooperativeWorkerRuntimeRegistry,
)

BOOTSTRAP_VERSION = "1.0.0"
UNBOUND_MODE = "UNBOUND"
TRUSTED_EXTERNAL_MODE = "TRUSTED_EXTERNAL_R1"
_PROVIDER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,127}$")
_SHA = re.compile(r"^[0-9a-f]{64}$")


class CooperativeWorkerBootstrapError(RuntimeError):
    pass


def _require(condition: bool, reason: str) -> None:
    if not condition:
        raise CooperativeWorkerBootstrapError(reason)


def _required(environment: Mapping[str, str], name: str, *, limit: int = 4096) -> str:
    value = environment.get(name)
    _require(
        isinstance(value, str)
        and bool(value.strip())
        and len(value) <= limit
        and "\x00" not in value,
        "cooperative bootstrap configuration:" + name,
    )
    return value


def _direct_directory(value: str | Path, label: str) -> Path:
    path = Path(value)
    _require(path.is_absolute() and path.is_dir() and not path.is_symlink(), label)
    resolved = path.resolve(strict=True)
    _require(path == resolved, label + " symlink indirection")
    st = resolved.stat()
    _require(stat.S_ISDIR(st.st_mode), label + " directory type")
    return resolved


def _direct_file(value: str | Path, label: str) -> Path:
    path = Path(value)
    _require(path.is_absolute() and path.is_file() and not path.is_symlink(), label)
    resolved = path.resolve(strict=True)
    _require(path == resolved, label + " symlink indirection")
    st = resolved.stat()
    _require(stat.S_ISREG(st.st_mode) and st.st_nlink == 1, label + " private regular file")
    return resolved


def _outside_repository(path: Path, repository_root: Path, label: str) -> Path:
    _require(path != repository_root and repository_root not in path.parents, label + " must be outside repository")
    return path


@dataclass(frozen=True)
class CooperativeRuntimeBootstrapDependencies:
    """Already-existing canonical owners supplied by a pinned trusted module."""

    context_source: Callable[[str], CooperativeRuntimeContext]
    qualification_context_source: Callable[[str], CooperativeRuntimeContext]
    upstream_admission_source: Any
    upstream_admission_trust: RuntimeAdmissionSourceTrustBinding
    durable_admission_trust: RuntimeAdmissionSourceTrustBinding
    authority_admission: LiveAuthorityAdmission
    currentness_source: Any
    currentness_trust: CurrentnessSourceTrustBinding
    dispatch_source: Any
    runtime_identity_source: Callable[[str], RuntimeIdentityBinding]
    provisioning_binding_source: Callable[[str], ProvisioningBinding]
    transfer_binding_source: Callable[[str, str], Mapping[str, Any]]
    now_fn: Callable[[], datetime] = lambda: datetime.now(timezone.utc)
    authority_effect: str = "NONE"

    def validate(self) -> "CooperativeRuntimeBootstrapDependencies":
        _require(type(self) is CooperativeRuntimeBootstrapDependencies, "exact bootstrap dependencies required")
        _require(self.authority_effect == "NONE", "bootstrap dependencies cannot grant authority")
        _require(type(self.upstream_admission_trust) is RuntimeAdmissionSourceTrustBinding,
                 "upstream admission trust type")
        _require(type(self.durable_admission_trust) is RuntimeAdmissionSourceTrustBinding,
                 "durable admission trust type")
        _require(type(self.currentness_trust) is CurrentnessSourceTrustBinding,
                 "currentness trust type")
        self.upstream_admission_trust.validate()
        self.durable_admission_trust.validate()
        self.currentness_trust.validate()
        _require(isinstance(self.authority_admission, LiveAuthorityAdmission),
                 "canonical LiveAuthorityAdmission required")
        for callback, label in (
            (self.context_source, "context source"),
            (self.qualification_context_source, "qualification context source"),
            (self.runtime_identity_source, "runtime identity source"),
            (self.provisioning_binding_source, "provisioning binding source"),
            (self.transfer_binding_source, "transfer binding source"),
            (self.now_fn, "trusted clock"),
        ):
            _require(callable(callback), label)
        _require(callable(getattr(self.upstream_admission_source, "resolve", None))
                 and callable(getattr(self.upstream_admission_source, "is_current", None)),
                 "upstream admission source")
        _require(callable(getattr(self.currentness_source, "resolve_authority", None))
                 and callable(getattr(self.currentness_source, "current_policy_binding", None))
                 and callable(getattr(self.currentness_source, "current_observability_state", None)),
                 "effect-time currentness source")
        _require(callable(getattr(self.dispatch_source, "current_dispatch", None)), "dispatch source")
        observed = self.now_fn()
        _require(isinstance(observed, datetime) and observed.tzinfo is not None, "trusted zoned clock")
        return self


def _load_module(path: Path, expected_digest: str) -> ModuleType:
    _require(_SHA.fullmatch(expected_digest) is not None, "trusted dependency digest")
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise CooperativeWorkerBootstrapError("trusted dependency module unavailable") from exc
    actual = sha256(raw).hexdigest()
    _require(actual == expected_digest, "trusted dependency module digest mismatch")
    module_name = "_lion_cooperative_runtime_dependencies_" + actual[:20]
    try:
        spec = importlib.util.spec_from_file_location(module_name, path)
        _require(spec is not None and spec.loader is not None, "trusted dependency module unavailable")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    except CooperativeWorkerBootstrapError:
        raise
    except Exception as exc:
        raise CooperativeWorkerBootstrapError("trusted dependency module failed closed") from exc
    return module


def load_dependencies_from_environment(
    environment: Mapping[str, str],
) -> CooperativeRuntimeBootstrapDependencies:
    repository_root = _direct_directory(
        _required(environment, "LION_COOPERATIVE_REPOSITORY_ROOT"),
        "cooperative repository root",
    )
    module_path = _outside_repository(
        _direct_file(
            _required(environment, "LION_COOPERATIVE_DEPENDENCY_MODULE_PATH"),
            "trusted dependency module",
        ),
        repository_root,
        "trusted dependency module",
    )
    expected = _required(environment, "LION_COOPERATIVE_DEPENDENCY_MODULE_SHA256", limit=64)
    callable_name = _required(environment, "LION_COOPERATIVE_DEPENDENCY_FACTORY", limit=128)
    _require(_PROVIDER_RE.fullmatch(callable_name) is not None, "trusted dependency factory name")
    module = _load_module(module_path, expected)
    factory = getattr(module, callable_name, None)
    _require(callable(factory), "trusted dependency factory unavailable")
    try:
        value = factory()
    except Exception as exc:
        raise CooperativeWorkerBootstrapError("trusted dependency factory failed closed") from exc
    _require(type(value) is CooperativeRuntimeBootstrapDependencies,
             "trusted dependency factory returned wrong type")
    return value.validate()


def build_root_from_environment(
    dependencies: CooperativeRuntimeBootstrapDependencies,
    environment: Mapping[str, str],
) -> CooperativeRuntimeCompositionRoot:
    deps = dependencies.validate()
    repository_root = _direct_directory(
        _required(environment, "LION_COOPERATIVE_REPOSITORY_ROOT"),
        "cooperative repository root",
    )
    mission_db = _outside_repository(
        _direct_file(
            _required(environment, "LION_COOPERATIVE_MISSION_DB_PATH"),
            "cooperative Mission Control DB",
        ),
        repository_root,
        "cooperative Mission Control DB",
    )
    private_root = _outside_repository(
        _direct_directory(
            _required(environment, "LION_COOPERATIVE_PRIVATE_ROOT"),
            "cooperative private root",
        ),
        repository_root,
        "cooperative private root",
    )
    artifact_root = _direct_directory(private_root / "artifacts", "cooperative artifact root")
    context_parent = _direct_directory(private_root / "contexts", "cooperative context root")
    verifier_parent = _direct_directory(private_root / "verifiers", "cooperative verifier root")
    state_root = _direct_directory(private_root / "state", "cooperative state root")

    return CooperativeRuntimeCompositionRoot(
        mission_db=mission_db,
        artifact_root=artifact_root,
        context_parent=context_parent,
        verifier_parent=verifier_parent,
        materialization_db=state_root / "materialization.sqlite",
        runtime_state_db=state_root / "runtime-state.sqlite",
        context_source=deps.context_source,
        qualification_context_source=deps.qualification_context_source,
        upstream_admission_source=deps.upstream_admission_source,
        upstream_admission_trust=deps.upstream_admission_trust,
        durable_admission_trust=deps.durable_admission_trust,
        authority_admission=deps.authority_admission,
        currentness_source=deps.currentness_source,
        currentness_trust=deps.currentness_trust,
        dispatch_source=deps.dispatch_source,
        runtime_identity_source=deps.runtime_identity_source,
        provisioning_binding_source=deps.provisioning_binding_source,
        transfer_binding_source=deps.transfer_binding_source,
        now_fn=deps.now_fn,
    )


def qualify_released_assignment_from_environment(
    environment: Mapping[str, str] | None = None,
    *,
    assignment_id: str,
    material_worker_id: str,
) -> dict[str, Any]:
    """Qualify one worker-private projection while normal runtime stays UNBOUND."""
    env = os.environ if environment is None else environment
    _require(
        env.get("LION_COOPERATIVE_BOOTSTRAP_MODE", UNBOUND_MODE) == UNBOUND_MODE,
        "worker qualification requires UNBOUND runtime",
    )
    _require(
        _required(env, "LION_COOPERATIVE_BOOTSTRAP_VERSION", limit=64) == BOOTSTRAP_VERSION,
        "cooperative bootstrap version mismatch",
    )
    configured_worker = _required(env, "LION_MATERIAL_WORKER_ID", limit=128)
    _require(configured_worker == material_worker_id, "qualification worker/environment mismatch")
    deps = load_dependencies_from_environment(env)
    root = build_root_from_environment(deps, env)
    result = root.qualify_released_write_assignment(
        assignment_id,
        material_worker_id=material_worker_id,
    )
    _require(result.get("execution_performed") is False, "qualification executed effect")
    _require(result.get("authority_effect") == "NONE", "qualification authority")
    return {
        **result,
        "bootstrap_version": BOOTSTRAP_VERSION,
        "bootstrap_mode": UNBOUND_MODE,
    }


def bootstrap_process_runtime(
    environment: Mapping[str, str] | None = None,
    *,
    registry: CooperativeWorkerRuntimeRegistry = PROCESS_COOPERATIVE_RUNTIME,
) -> dict[str, Any]:
    env = os.environ if environment is None else environment
    _require(type(registry) is CooperativeWorkerRuntimeRegistry, "exact worker runtime registry required")
    mode = env.get("LION_COOPERATIVE_BOOTSTRAP_MODE", UNBOUND_MODE)
    if mode == UNBOUND_MODE:
        _require(registry.current("MD001") is None, "UNBOUND mode cannot coexist with installed root")
        return {
            "schema": "lion.cooperative-worker-bootstrap/v1",
            "state": "UNBOUND",
            "mode": UNBOUND_MODE,
            "bootstrap_version": BOOTSTRAP_VERSION,
            "authority_effect": "NONE",
        }
    _require(mode == TRUSTED_EXTERNAL_MODE, "unsupported cooperative bootstrap mode")
    _require(
        _required(env, "LION_COOPERATIVE_BOOTSTRAP_VERSION", limit=64) == BOOTSTRAP_VERSION,
        "cooperative bootstrap version mismatch",
    )
    _require(registry.current("MD001") is None, "cooperative runtime already installed")
    deps = load_dependencies_from_environment(env)
    root = build_root_from_environment(deps, env)
    registry.install(root)
    marker = root.worker_status_marker()
    return {
        "schema": "lion.cooperative-worker-bootstrap/v1",
        "state": "READY",
        "mode": TRUSTED_EXTERNAL_MODE,
        "bootstrap_version": BOOTSTRAP_VERSION,
        "provider": marker,
        "authority_effect": "NONE",
    }
