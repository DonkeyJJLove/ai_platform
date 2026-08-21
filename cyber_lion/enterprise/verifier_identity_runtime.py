"""Trusted composition root for real verifier identity providers.

All executable provider/verifier material is loaded from absolute paths outside the
repository and pinned by SHA-256 from trusted environment configuration.  The
factories are zero-argument so callers cannot select providers or trust pins.
"""
from __future__ import annotations

import hashlib
import importlib.util
import os
from datetime import datetime, timezone
from pathlib import Path
import re
from types import ModuleType
from typing import Callable, Final

from cyber_lion.contracts.verifier_execution_attestation import FixedSourcePin
from cyber_lion.enterprise.runtime_attestation import (
    ExternalAttestationVerifier,
    InMemoryRuntimeReplayGuard,
    RuntimeAttestationVerifier,
)
from cyber_lion.enterprise.verifier_identity_provider import (
    RealVerifierParticipationSource,
    RealVerifierRuntimeAttestationSource,
    RealVerifierWorkloadIdentitySource,
    VerifierIdentityProviderError,
)

RUNTIME_FACTORY_VERSION: Final = "1.0.0"
_SHA256_RE: Final = re.compile(r"^[0-9a-f]{64}$")
_CALLABLE_RE: Final = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,127}$")
_ENV_RE: Final = re.compile(r"^[A-Z][A-Z0-9_]{0,127}$")


class VerifierIdentityRuntimeError(RuntimeError):
    pass


def _required(name: str, *, limit: int = 4096) -> str:
    if not _ENV_RE.fullmatch(name):
        raise VerifierIdentityRuntimeError("trusted runtime configuration name is invalid")
    value = os.environ.get(name)
    if not isinstance(value, str) or not value.strip() or len(value) > limit or "\x00" in value:
        raise VerifierIdentityRuntimeError("trusted runtime configuration is unavailable")
    return value


def _version() -> None:
    if _required("LION_VI_RUNTIME_FACTORY_VERSION", limit=64) != RUNTIME_FACTORY_VERSION:
        raise VerifierIdentityRuntimeError("verifier identity runtime version mismatch")


def _repo_root() -> Path:
    raw = _required("LION_VI_REPOSITORY_ROOT")
    path = Path(raw)
    if not path.is_absolute():
        raise VerifierIdentityRuntimeError("repository root must be absolute")
    try:
        resolved = path.resolve(strict=True)
    except OSError as exc:
        raise VerifierIdentityRuntimeError("repository root is unavailable") from exc
    if not resolved.is_dir():
        raise VerifierIdentityRuntimeError("repository root is not a directory")
    return resolved


def _outside_repository(raw: str) -> Path:
    root = _repo_root()
    path = Path(raw)
    if not path.is_absolute():
        raise VerifierIdentityRuntimeError("external provider path must be absolute")
    try:
        resolved = path.resolve(strict=True)
    except OSError as exc:
        raise VerifierIdentityRuntimeError("external provider material is unavailable") from exc
    if resolved == root or root in resolved.parents or not resolved.is_file() or resolved.suffix != ".py":
        raise VerifierIdentityRuntimeError("provider material must be an external Python file")
    return resolved


def _load_module(prefix: str) -> tuple[ModuleType, str]:
    path = _outside_repository(_required(f"{prefix}_MODULE_PATH"))
    expected = _required(f"{prefix}_MODULE_DIGEST", limit=64)
    if not _SHA256_RE.fullmatch(expected):
        raise VerifierIdentityRuntimeError("provider digest pin is invalid")
    try:
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as exc:
        raise VerifierIdentityRuntimeError("provider bytes are unavailable") from exc
    if actual != expected:
        raise VerifierIdentityRuntimeError("provider implementation digest mismatch")
    module_name = "_lion_vi_" + hashlib.sha256((prefix + str(path)).encode()).hexdigest()[:20]
    try:
        spec = importlib.util.spec_from_file_location(module_name, path)
        if spec is None or spec.loader is None:
            raise VerifierIdentityRuntimeError("external module spec unavailable")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    except VerifierIdentityRuntimeError:
        raise
    except Exception as exc:
        raise VerifierIdentityRuntimeError("external provider module failed closed") from exc
    return module, actual


def _load_callable(prefix: str) -> tuple[Callable[..., object], str]:
    module, digest = _load_module(prefix)
    name = _required(f"{prefix}_CALLABLE", limit=128)
    if not _CALLABLE_RE.fullmatch(name):
        raise VerifierIdentityRuntimeError("external callable name is invalid")
    value = getattr(module, name, None)
    if not callable(value):
        raise VerifierIdentityRuntimeError("external callable is unavailable")
    return value, digest


def _factory(prefix: str) -> tuple[object, str]:
    callable_obj, digest = _load_callable(prefix)
    try:
        value = callable_obj()
    except Exception as exc:
        raise VerifierIdentityRuntimeError("external provider factory failed closed") from exc
    if value is None:
        raise VerifierIdentityRuntimeError("external provider factory returned no provider")
    return value, digest


def _pin(kind: str, implementation_digest: str) -> FixedSourcePin:
    return FixedSourcePin(
        source_id=_required(f"LION_VI_{kind}_SOURCE_ID", limit=256),
        source_instance_id=_required(f"LION_VI_{kind}_SOURCE_INSTANCE_ID", limit=256),
        source_implementation_digest=implementation_digest,
        trust_anchor_id=_required(f"LION_VI_{kind}_TRUST_ANCHOR_ID", limit=256),
    ).validate()


def _clock() -> datetime:
    return datetime.now(timezone.utc)


def build_verifier_workload_source() -> RealVerifierWorkloadIdentitySource:
    _version()
    raw_provider, provider_digest = _factory("LION_VI_WORKLOAD_PROVIDER")
    verifier, _ = _load_callable("LION_VI_WORKLOAD_SIGNATURE_VERIFIER")
    try:
        return RealVerifierWorkloadIdentitySource(
            pin=_pin("WORKLOAD", provider_digest),
            raw_provider=raw_provider,
            signature_verifier=verifier,
            clock=_clock,
            trust_domain=_required("LION_VI_WORKLOAD_TRUST_DOMAIN", limit=256),
            tenant_id=_required("LION_VI_WORKLOAD_TENANT_ID", limit=256),
            organization_id=_required("LION_VI_WORKLOAD_ORGANIZATION_ID", limit=256),
            audience=_required("LION_VI_WORKLOAD_AUDIENCE", limit=256),
            environment=_required("LION_VI_WORKLOAD_ENVIRONMENT", limit=128),
            issuer_id=_required("LION_VI_WORKLOAD_ISSUER_ID", limit=256),
        )
    except VerifierIdentityProviderError as exc:
        raise VerifierIdentityRuntimeError("workload identity source construction failed") from exc


def build_verifier_runtime_source() -> RealVerifierRuntimeAttestationSource:
    _version()
    raw_provider, provider_digest = _factory("LION_VI_RUNTIME_PROVIDER")
    external_attester, _ = _factory("LION_VI_EXTERNAL_ATTESTER")
    if not callable(getattr(external_attester, "verify_external", None)):
        raise VerifierIdentityRuntimeError("external attester contract is invalid")
    verifier = RuntimeAttestationVerifier(
        external_verifier=external_attester,  # type: ignore[arg-type]
        replay_guard=InMemoryRuntimeReplayGuard(),
    )
    try:
        return RealVerifierRuntimeAttestationSource(
            pin=_pin("RUNTIME", provider_digest),
            raw_provider=raw_provider,
            verifier=verifier,
            clock=_clock,
            expected_issuer=_required("LION_VI_RUNTIME_ISSUER", limit=256),
        )
    except VerifierIdentityProviderError as exc:
        raise VerifierIdentityRuntimeError("runtime identity source construction failed") from exc


def build_verifier_participation_source() -> RealVerifierParticipationSource:
    _version()
    raw_provider, provider_digest = _factory("LION_VI_PARTICIPATION_PROVIDER")
    try:
        return RealVerifierParticipationSource(
            pin=_pin("PARTICIPATION", provider_digest),
            raw_provider=raw_provider,
        )
    except VerifierIdentityProviderError as exc:
        raise VerifierIdentityRuntimeError("participation source construction failed") from exc
