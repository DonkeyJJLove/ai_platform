"""Trusted runtime factories for the external Cyber-Lion control plane.

The factories are deliberately zero-argument so they can be loaded by
``build_service_from_environment``. All mutable state, verifier implementation material,
and credentials remain outside the repository tree. Repository-local provider state is
rejected fail-closed.
"""
from __future__ import annotations

import hashlib
import importlib.util
import os
from pathlib import Path
import re
from types import ModuleType
from typing import Callable, Final

from .trusted_control_plane_providers import (
    SQLiteTrustedControlPlaneStore,
    TrustedControlPlaneProviderError,
    TrustedSignatureVerifierAdapter,
)

RUNTIME_FACTORY_VERSION: Final = "1.0.0"
_ENV_NAME_RE: Final = re.compile(r"^[A-Z][A-Z0-9_]{0,127}$")
_CALLABLE_RE: Final = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,127}$")
_SHA256_RE: Final = re.compile(r"^[0-9a-f]{64}$")


class TrustedControlPlaneRuntimeError(RuntimeError):
    """Raised when trusted runtime provider configuration is unavailable or unsafe."""


def _required_env(name: str, *, limit: int = 4096) -> str:
    if not _ENV_NAME_RE.fullmatch(name):
        raise TrustedControlPlaneRuntimeError("trusted runtime configuration is invalid")
    value = os.environ.get(name)
    if (
        not isinstance(value, str)
        or not value.strip()
        or len(value) > limit
        or "\x00" in value
    ):
        raise TrustedControlPlaneRuntimeError("trusted runtime configuration is invalid")
    return value


def _runtime_version() -> None:
    if _required_env("LION_CP_RUNTIME_FACTORY_VERSION", limit=64) != RUNTIME_FACTORY_VERSION:
        raise TrustedControlPlaneRuntimeError("trusted runtime provider version mismatch")


def _repository_root() -> Path:
    raw = _required_env("LION_CP_REPOSITORY_ROOT", limit=4096)
    path = Path(raw)
    if not path.is_absolute():
        raise TrustedControlPlaneRuntimeError("trusted repository root is invalid")
    try:
        resolved = path.resolve(strict=True)
    except OSError as exc:
        raise TrustedControlPlaneRuntimeError("trusted repository root is invalid") from exc
    if not resolved.is_dir():
        raise TrustedControlPlaneRuntimeError("trusted repository root is invalid")
    return resolved


def _outside_repository(path: Path, *, repository_root: Path, must_exist: bool) -> Path:
    if not path.is_absolute():
        raise TrustedControlPlaneRuntimeError("trusted runtime path is invalid")
    try:
        resolved = path.resolve(strict=must_exist)
    except OSError as exc:
        raise TrustedControlPlaneRuntimeError("trusted runtime path is invalid") from exc
    if resolved == repository_root or repository_root in resolved.parents:
        raise TrustedControlPlaneRuntimeError("trusted runtime path must be outside repository")
    return resolved


def _database_path() -> Path:
    root = _repository_root()
    raw = _required_env("LION_CP_DATABASE_PATH", limit=4096)
    path = _outside_repository(Path(raw), repository_root=root, must_exist=False)
    try:
        parent = path.parent.resolve(strict=True)
    except OSError as exc:
        raise TrustedControlPlaneRuntimeError("trusted database parent is unavailable") from exc
    if not parent.is_dir():
        raise TrustedControlPlaneRuntimeError("trusted database parent is unavailable")
    return path


def _verifier_file() -> tuple[Path, str, str | None]:
    root = _repository_root()
    raw_path = _required_env("LION_CP_VERIFIER_MODULE_PATH", limit=4096)
    path = _outside_repository(Path(raw_path), repository_root=root, must_exist=True)
    if not path.is_file() or path.suffix != ".py":
        raise TrustedControlPlaneRuntimeError("trusted verifier material is invalid")

    expected_digest = _required_env("LION_CP_VERIFIER_BINDING_DIGEST", limit=64)
    if not _SHA256_RE.fullmatch(expected_digest):
        raise TrustedControlPlaneRuntimeError("trusted verifier binding is invalid")
    try:
        actual_digest = hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as exc:
        raise TrustedControlPlaneRuntimeError("trusted verifier material is unavailable") from exc
    if actual_digest != expected_digest:
        raise TrustedControlPlaneRuntimeError("trusted verifier binding mismatch")

    callable_name = _required_env("LION_CP_VERIFIER_CALLABLE", limit=128)
    if not _CALLABLE_RE.fullmatch(callable_name):
        raise TrustedControlPlaneRuntimeError("trusted verifier callable is invalid")

    ready_name = os.environ.get("LION_CP_VERIFIER_READY_CALLABLE")
    if ready_name is not None:
        if not isinstance(ready_name, str) or not _CALLABLE_RE.fullmatch(ready_name):
            raise TrustedControlPlaneRuntimeError("trusted verifier readiness callable is invalid")
    return path, callable_name, ready_name


def _load_external_module(path: Path) -> ModuleType:
    module_name = "_lion_external_verifier_" + hashlib.sha256(str(path).encode("utf-8")).hexdigest()[:20]
    try:
        spec = importlib.util.spec_from_file_location(module_name, path)
        if spec is None or spec.loader is None:
            raise TrustedControlPlaneRuntimeError("trusted verifier module is unavailable")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    except TrustedControlPlaneRuntimeError:
        raise
    except Exception as exc:
        raise TrustedControlPlaneRuntimeError("trusted verifier module failed closed") from exc
    return module


def build_store() -> SQLiteTrustedControlPlaneStore:
    """Build the persistent store from trusted environment-only configuration."""
    _runtime_version()
    path = _database_path()
    try:
        store = SQLiteTrustedControlPlaneStore(str(path))
    except Exception as exc:
        raise TrustedControlPlaneRuntimeError("trusted persistent store unavailable") from exc
    if store.ready() is not True:
        raise TrustedControlPlaneRuntimeError("trusted persistent store is not ready")
    return store


def build_verifier() -> TrustedSignatureVerifierAdapter:
    """Build a verifier whose implementation bytes are bound outside the repository."""
    _runtime_version()
    path, callable_name, ready_name = _verifier_file()
    module = _load_external_module(path)
    verifier = getattr(module, callable_name, None)
    if not callable(verifier):
        raise TrustedControlPlaneRuntimeError("trusted verifier callable is unavailable")

    ready: Callable[[], bool] | None = None
    if ready_name is not None:
        candidate = getattr(module, ready_name, None)
        if not callable(candidate):
            raise TrustedControlPlaneRuntimeError("trusted verifier readiness callable is unavailable")
        ready = candidate

    try:
        adapter = TrustedSignatureVerifierAdapter(verifier, ready=ready)
    except TrustedControlPlaneProviderError as exc:
        raise TrustedControlPlaneRuntimeError("trusted verifier adapter unavailable") from exc
    if adapter.ready() is not True:
        raise TrustedControlPlaneRuntimeError("trusted verifier is not ready")
    return adapter
