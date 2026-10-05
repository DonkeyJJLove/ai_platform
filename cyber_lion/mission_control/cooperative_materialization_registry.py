"""Process-local binding for cooperative runtime materializers.

This registry is dependency injection, not authority. It cannot issue RuntimeAdmission,
change Mission Control scheduling, or infer readiness from model/LPCL payloads. The
trusted process composition root may install exactly one canonical pair of non-authorizing
materializers. Missing installation remains fail-closed.
"""
from __future__ import annotations

from dataclasses import dataclass
from threading import RLock
from typing import Any, Callable, Mapping

PROVIDER_ID = "COOPERATIVE_RUNTIME_MATERIALIZER_R1"
AUTHORITY_EFFECT = "NONE"


class CooperativeMaterializationRegistryError(RuntimeError):
    pass


@dataclass(frozen=True)
class CooperativeMaterializationProvider:
    write_materializer: Callable[[Mapping[str, Any]], Mapping[str, Any]]
    verify_materializer: Callable[[Mapping[str, Any]], Mapping[str, Any]]
    provider_id: str = PROVIDER_ID
    authority_effect: str = AUTHORITY_EFFECT

    def validate(self) -> "CooperativeMaterializationProvider":
        if type(self) is not CooperativeMaterializationProvider:
            raise CooperativeMaterializationRegistryError("exact provider type required")
        if self.provider_id != PROVIDER_ID or self.authority_effect != AUTHORITY_EFFECT:
            raise CooperativeMaterializationRegistryError("provider identity/authority mismatch")
        if not callable(self.write_materializer) or not callable(self.verify_materializer):
            raise CooperativeMaterializationRegistryError("materializer callables required")
        return self


class CooperativeMaterializationRegistry:
    """Exactly-once process-local materializer binding."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._provider: CooperativeMaterializationProvider | None = None

    def install(self, provider: CooperativeMaterializationProvider) -> CooperativeMaterializationProvider:
        if type(provider) is not CooperativeMaterializationProvider:
            raise CooperativeMaterializationRegistryError("exact provider type required")
        provider.validate()
        with self._lock:
            if self._provider is not None:
                raise CooperativeMaterializationRegistryError("provider already installed")
            self._provider = provider
            return provider

    def current(self) -> CooperativeMaterializationProvider | None:
        with self._lock:
            provider = self._provider
        if provider is None:
            return None
        return provider.validate()

    def require(self) -> CooperativeMaterializationProvider:
        provider = self.current()
        if provider is None:
            raise CooperativeMaterializationRegistryError("cooperative materializer not installed")
        return provider

    def status(self) -> dict[str, Any]:
        provider = self.current()
        return {
            "state": "READY" if provider is not None else "NOT_BOUND",
            "provider_id": provider.provider_id if provider is not None else PROVIDER_ID,
            "authority_effect": AUTHORITY_EFFECT,
        }
