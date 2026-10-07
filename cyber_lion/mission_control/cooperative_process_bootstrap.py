"""Fail-closed Mission Control composition bootstrap for cooperative materializers.

The existing cooperative Mission Control registry is dependency injection, not an
authority source.  This bootstrap supplies the missing process-composition edge:
a SHA-256 pinned external module may return one exact
CooperativeProcessBootstrapDependencies object containing:

* the R6.16 CooperativeControlPlaneMaterializer for WRITE materialization; and
* an existing CooperativeRuntimeCompositionRoot whose verify_materializer owns
  verifier-transfer materialization.

The bootstrap never constructs RuntimeAdmission, live authority, dispatch,
provisioning or currentness evidence.  It never creates/releases/claims an
assignment and never executes an artifact.  Default mode is UNBOUND.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import importlib.util
import os
from pathlib import Path
import re
import stat
from types import ModuleType
from typing import Mapping

from cyber_lion.enterprise.cooperative_control_plane_materializer import (
    CooperativeControlPlaneMaterializer,
)
from cyber_lion.enterprise.cooperative_runtime_root import (
    CooperativeRuntimeCompositionRoot,
)
from cyber_lion.mission_control.cooperative_materialization_registry import (
    CooperativeMaterializationProvider,
    CooperativeMaterializationRegistry,
)

SCHEMA_ID = "lion.cooperative-process-bootstrap/v1"
BOOTSTRAP_VERSION = "1.0.0"
UNBOUND_MODE = "UNBOUND"
TRUSTED_EXTERNAL_MODE = "TRUSTED_EXTERNAL_R1"
AUTHORITY_EFFECT = "NONE"
EXECUTION_EFFECT = "NONE"

_SAFE_FACTORY = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,127}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_FORBIDDEN_EFFECT_METHODS = frozenset({
    "authorize", "admit", "execute", "write", "push", "merge",
    "deploy", "release", "schedule", "dispatch",
})


class CooperativeProcessBootstrapError(RuntimeError):
    pass


def _require(condition: bool, reason: str) -> None:
    if not condition:
        raise CooperativeProcessBootstrapError(reason)


def _required(environment: Mapping[str, str], name: str, *, limit: int = 4096) -> str:
    value = environment.get(name)
    _require(
        isinstance(value, str)
        and bool(value.strip())
        and len(value) <= limit
        and "\x00" not in value,
        "cooperative process bootstrap configuration:" + name,
    )
    return value


def _direct_directory(value: str | Path, label: str) -> Path:
    path = Path(value)
    _require(path.is_absolute() and path.is_dir() and not path.is_symlink(), label)
    resolved = path.resolve(strict=True)
    _require(path == resolved, label + " symlink indirection")
    _require(stat.S_ISDIR(resolved.stat().st_mode), label + " directory type")
    return resolved


def _direct_file(value: str | Path, label: str) -> Path:
    path = Path(value)
    _require(path.is_absolute() and path.is_file() and not path.is_symlink(), label)
    resolved = path.resolve(strict=True)
    _require(path == resolved, label + " symlink indirection")
    st = resolved.stat()
    _require(stat.S_ISREG(st.st_mode) and st.st_nlink == 1, label + " regular file")
    return resolved


def _outside_repository(path: Path, repository_root: Path, label: str) -> Path:
    _require(
        path != repository_root and repository_root not in path.parents,
        label + " must be outside repository",
    )
    return path


def _same_file(left: Path, right: Path) -> bool:
    try:
        a, b = left.stat(), right.stat()
    except OSError as exc:
        raise CooperativeProcessBootstrapError("Mission Control DB identity unavailable") from exc
    return (a.st_dev, a.st_ino) == (b.st_dev, b.st_ino)


@dataclass(frozen=True)
class CooperativeProcessBootstrapDependencies:
    """Exact already-composed non-authorizing process dependencies."""

    write_materializer: CooperativeControlPlaneMaterializer
    verifier_root: CooperativeRuntimeCompositionRoot
    authority_effect: str = AUTHORITY_EFFECT

    def validate(self) -> "CooperativeProcessBootstrapDependencies":
        _require(
            type(self) is CooperativeProcessBootstrapDependencies,
            "exact process bootstrap dependencies required",
        )
        _require(
            type(self.write_materializer) is CooperativeControlPlaneMaterializer,
            "exact R6.16 control-plane materializer required",
        )
        _require(
            type(self.verifier_root) is CooperativeRuntimeCompositionRoot,
            "exact cooperative runtime composition root required",
        )
        _require(self.authority_effect == AUTHORITY_EFFECT, "process dependencies cannot grant authority")
        _require(
            _same_file(self.write_materializer.mission_db, self.verifier_root.mission_db),
            "write/verifier Mission Control DB identity mismatch",
        )
        return self

    def materialization_provider(self) -> CooperativeMaterializationProvider:
        self.validate()
        return CooperativeMaterializationProvider(
            write_materializer=self.write_materializer,
            verify_materializer=self.verifier_root.verify_materializer,
        ).validate()


def _load_module(path: Path, expected_digest: str) -> ModuleType:
    _require(_SHA256.fullmatch(expected_digest) is not None, "process dependency module digest")
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise CooperativeProcessBootstrapError("process dependency module unavailable") from exc
    actual = sha256(raw).hexdigest()
    _require(actual == expected_digest, "process dependency module digest mismatch")
    module_name = "_lion_cooperative_process_dependencies_" + actual[:20]
    try:
        spec = importlib.util.spec_from_file_location(module_name, path)
        _require(spec is not None and spec.loader is not None, "process dependency module unavailable")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    except CooperativeProcessBootstrapError:
        raise
    except Exception as exc:
        raise CooperativeProcessBootstrapError("process dependency module failed closed") from exc
    return module


def load_process_dependencies_from_environment(
    environment: Mapping[str, str],
) -> tuple[CooperativeProcessBootstrapDependencies, str]:
    repository_root = _direct_directory(
        _required(environment, "LION_COOPERATIVE_PROCESS_REPOSITORY_ROOT"),
        "cooperative process repository root",
    )
    module_path = _outside_repository(
        _direct_file(
            _required(environment, "LION_COOPERATIVE_PROCESS_DEPENDENCY_MODULE_PATH"),
            "cooperative process dependency module",
        ),
        repository_root,
        "cooperative process dependency module",
    )
    expected = _required(
        environment, "LION_COOPERATIVE_PROCESS_DEPENDENCY_MODULE_SHA256", limit=64
    )
    factory_name = _required(
        environment, "LION_COOPERATIVE_PROCESS_DEPENDENCY_FACTORY", limit=128
    )
    _require(_SAFE_FACTORY.fullmatch(factory_name) is not None, "process dependency factory name")
    module = _load_module(module_path, expected)
    factory = getattr(module, factory_name, None)
    _require(callable(factory), "process dependency factory unavailable")
    try:
        value = factory()
    except Exception as exc:
        raise CooperativeProcessBootstrapError("process dependency factory failed closed") from exc
    _require(
        type(value) is CooperativeProcessBootstrapDependencies,
        "process dependency factory returned wrong type",
    )
    return value.validate(), expected


def bootstrap_process_materializers(
    environment: Mapping[str, str] | None = None,
    *,
    registry: CooperativeMaterializationRegistry,
) -> dict[str, object]:
    """Install one exact process materializer pair or remain explicitly UNBOUND."""
    env = os.environ if environment is None else environment
    _require(
        type(registry) is CooperativeMaterializationRegistry,
        "exact cooperative materialization registry required",
    )
    mode = env.get("LION_COOPERATIVE_PROCESS_BOOTSTRAP_MODE", UNBOUND_MODE)
    if mode == UNBOUND_MODE:
        _require(registry.current() is None, "UNBOUND process mode cannot coexist with provider")
        return {
            "schema": SCHEMA_ID,
            "state": "UNBOUND",
            "mode": UNBOUND_MODE,
            "bootstrap_version": BOOTSTRAP_VERSION,
            "provider_id": "COOPERATIVE_RUNTIME_MATERIALIZER_R1",
            "authority_effect": AUTHORITY_EFFECT,
            "execution_effect": EXECUTION_EFFECT,
        }

    _require(mode == TRUSTED_EXTERNAL_MODE, "unsupported cooperative process bootstrap mode")
    _require(
        _required(env, "LION_COOPERATIVE_PROCESS_BOOTSTRAP_VERSION", limit=64)
        == BOOTSTRAP_VERSION,
        "cooperative process bootstrap version mismatch",
    )
    _require(registry.current() is None, "cooperative process materializer already installed")
    deps, module_digest = load_process_dependencies_from_environment(env)
    provider = deps.materialization_provider()
    installed = registry.install(provider)
    _require(installed is provider and registry.current() is provider, "process materializer install readback")
    return {
        "schema": SCHEMA_ID,
        "state": "READY",
        "mode": TRUSTED_EXTERNAL_MODE,
        "bootstrap_version": BOOTSTRAP_VERSION,
        "provider_id": provider.provider_id,
        "dependency_module_sha256": module_digest,
        "authority_effect": AUTHORITY_EFFECT,
        "execution_effect": EXECUTION_EFFECT,
    }


def assert_no_effect_surface() -> None:
    public = {
        name.lower()
        for name in globals()
        if not name.startswith("_")
    }
    if public & _FORBIDDEN_EFFECT_METHODS:
        raise CooperativeProcessBootstrapError("direct effect surface exposed")
