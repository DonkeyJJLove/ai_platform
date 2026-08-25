"""Trusted runtime factories for the external Cyber-Lion control plane.

The factories are deliberately zero-argument so they can be loaded by
``build_service_from_environment``. All mutable state, verifier implementation material,
and credentials remain outside the repository tree. Repository-local provider state is
rejected fail-closed.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
from types import ModuleType
from typing import Callable, Final

from .persistent_authority_state import (
    PersistentAuthorityStateError,
    PersistentAuthorityStoreOrigin,
    SQLiteAuthorityStateStore,
)
from .trusted_control_plane_providers import (
    SQLiteTrustedControlPlaneStore,
    TrustedControlPlaneProviderError,
    TrustedSignatureVerifierAdapter,
)

RUNTIME_FACTORY_VERSION: Final = "1.0.0"
AUTHORITY_STORE_ORIGIN_DOMAIN: Final = "LION/E004-CANONICAL-AUTHORITY-STATE-STORE-ORIGIN/1"
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


def _canonical_json(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def observe_authority_state_store_origin() -> PersistentAuthorityStoreOrigin:
    """Observe the candidate canonical origin from trusted process configuration."""
    _runtime_version()
    repository_root = _repository_root()
    database_path = _database_path()
    payload = {
        "runtime_factory_version": RUNTIME_FACTORY_VERSION,
        "repository_root": str(repository_root),
        "canonical_database_path": str(database_path),
    }
    digest = hashlib.sha256(
        AUTHORITY_STORE_ORIGIN_DOMAIN.encode("ascii") + b"\0" + _canonical_json(payload)
    ).hexdigest()
    return PersistentAuthorityStoreOrigin(
        origin_id=f"aso:{digest}",
        origin_digest=digest,
        runtime_factory_version=RUNTIME_FACTORY_VERSION,
        repository_root=str(repository_root),
        canonical_database_path=str(database_path),
    ).validate()


def _authority_state_store_for_origin(origin: PersistentAuthorityStoreOrigin) -> SQLiteAuthorityStateStore:
    try:
        store = SQLiteAuthorityStateStore(origin.canonical_database_path)
    except Exception as exc:
        raise TrustedControlPlaneRuntimeError("trusted authority-state store unavailable") from exc
    if type(store) is not SQLiteAuthorityStateStore or store.ready() is not True:
        raise TrustedControlPlaneRuntimeError("trusted authority-state store is not ready")
    return store


def register_authority_state_store_origin_once() -> PersistentAuthorityStoreOrigin:
    """Persist the first canonical authority-store origin; duplicate registration is denied."""
    origin = observe_authority_state_store_origin()
    store = _authority_state_store_for_origin(origin)
    try:
        return store.register_authority_store_origin(origin)
    except PersistentAuthorityStateError as exc:
        raise TrustedControlPlaneRuntimeError("canonical authority-state origin registration denied") from exc


def verify_authority_state_store_origin(
    expected_origin: PersistentAuthorityStoreOrigin | None = None,
) -> PersistentAuthorityStoreOrigin:
    """Reobserve configuration and prove it matches the durable and optional caller-held anchor."""
    observed = observe_authority_state_store_origin()
    if expected_origin is not None:
        if type(expected_origin) is not PersistentAuthorityStoreOrigin:
            raise TrustedControlPlaneRuntimeError("canonical authority-state expected origin invalid")
        expected_origin.validate()
        if observed != expected_origin:
            raise TrustedControlPlaneRuntimeError("canonical authority-state origin drift")
    store = _authority_state_store_for_origin(observed)
    try:
        anchored = store.resolve_authority_store_origin()
    except PersistentAuthorityStateError as exc:
        raise TrustedControlPlaneRuntimeError("canonical authority-state origin is not registered") from exc
    if anchored != observed:
        raise TrustedControlPlaneRuntimeError("canonical authority-state origin drift")
    if expected_origin is not None and anchored != expected_origin:
        raise TrustedControlPlaneRuntimeError("canonical authority-state origin mismatch")
    return anchored


def _ensure_authority_state_store_origin() -> tuple[PersistentAuthorityStoreOrigin, SQLiteAuthorityStateStore]:
    observed = observe_authority_state_store_origin()
    store = _authority_state_store_for_origin(observed)
    try:
        anchored = store.resolve_authority_store_origin()
    except PersistentAuthorityStateError:
        try:
            anchored = store.register_authority_store_origin(observed)
        except PersistentAuthorityStateError as exc:
            raise TrustedControlPlaneRuntimeError("canonical authority-state origin registration denied") from exc
    if anchored != observed:
        raise TrustedControlPlaneRuntimeError("canonical authority-state origin drift")
    return anchored, store


def build_store() -> SQLiteTrustedControlPlaneStore:
    """Build the persistent control-plane record store from trusted environment-only configuration."""
    _runtime_version()
    path = _database_path()
    try:
        store = SQLiteTrustedControlPlaneStore(str(path))
    except Exception as exc:
        raise TrustedControlPlaneRuntimeError("trusted persistent store unavailable") from exc
    if store.ready() is not True:
        raise TrustedControlPlaneRuntimeError("trusted persistent store is not ready")
    return store


def build_authority_state_store() -> SQLiteAuthorityStateStore:
    """Build the canonical authority-state store from its durable one-way origin anchor."""
    origin, store = _ensure_authority_state_store_origin()
    verified = verify_authority_state_store_origin(origin)
    if verified != origin:
        raise TrustedControlPlaneRuntimeError("canonical authority-state origin verification failed")
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
