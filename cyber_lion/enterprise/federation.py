"""Repository federation registry for the Cyber-Lion AI-Native enterprise.

Repository manifests describe organizational capability and trust boundaries. Loading a
manifest enables discovery only; it never grants runtime credentials or action authority.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, Mapping, Tuple

from .models import EnterpriseModelError, authority_rank


_ALLOWED_LAYERS = {"INF", "SEM", "MAND"}
_ALLOWED_DISPOSITIONS = {
    "KEEP", "REFINE", "EXTRACT", "GENERALIZE", "INTEGRATE",
    "DEPRECATE", "EXPERIMENTAL", "UNKNOWN",
}
_MANIFEST_ROOT_KEYS = frozenset({
    "schema_version", "repository", "cyber_lion", "capabilities",
    "authority", "observability", "security", "epistemic",
})
_REPOSITORY_KEYS = frozenset({"id", "url", "owner", "default_branch", "vcs_ref"})
_CYBER_LION_KEYS = frozenset({"tile_id", "roles", "layers", "disposition"})
_AUTHORITY_KEYS = frozenset({"maximum_level", "required_gates"})
_OBSERVABILITY_KEYS = frozenset({"logs", "metrics", "traces"})
_SECURITY_KEYS = frozenset({"trust_boundaries"})
_EPISTEMIC_KEYS = frozenset({"status", "confidence"})


def _exact_object(value: object, name: str, keys: frozenset[str]) -> dict[str, Any]:
    if type(value) is not dict or set(value) != keys:
        raise EnterpriseModelError(f"{name} shape invalid")
    return value


def _native_string(value: object, name: str) -> str:
    if type(value) is not str:
        raise EnterpriseModelError(f"{name} must be string")
    return value


def _native_string_list(value: object, name: str) -> tuple[str, ...]:
    if type(value) is not list or any(type(item) is not str for item in value):
        raise EnterpriseModelError(f"{name} must be array of strings")
    return tuple(value)


@dataclass(frozen=True)
class RepositoryManifest:
    repository_id: str
    url: str
    owner: str
    default_branch: str
    tile_id: str
    roles: Tuple[str, ...]
    layers: Tuple[str, ...]
    dispositions: Tuple[str, ...]
    capabilities: Tuple[str, ...]
    maximum_authority: str
    required_gates: Tuple[str, ...]
    logs: Tuple[str, ...]
    metrics: Tuple[str, ...]
    traces: Tuple[str, ...]
    trust_boundaries: Tuple[str, ...]
    epistemic_status: str
    epistemic_confidence: float | None

    def validate(self) -> "RepositoryManifest":
        if not all((self.repository_id, self.url, self.owner, self.default_branch, self.tile_id)):
            raise EnterpriseModelError("repository manifest identity fields are required")
        if not self.roles or not self.capabilities:
            raise EnterpriseModelError("repository manifest requires roles and capabilities")
        if len(set(self.capabilities)) != len(self.capabilities):
            raise EnterpriseModelError("repository capabilities must be unique")
        if not set(self.layers).issubset(_ALLOWED_LAYERS) or not self.layers:
            raise EnterpriseModelError("repository manifest contains invalid or empty layers")
        if not set(self.dispositions).issubset(_ALLOWED_DISPOSITIONS) or not self.dispositions:
            raise EnterpriseModelError("repository manifest contains invalid or empty dispositions")
        authority_rank(self.maximum_authority)
        if authority_rank(self.maximum_authority) > authority_rank("read") and not self.required_gates:
            raise EnterpriseModelError("consequential repository authority requires required_gates")
        if not self.trust_boundaries:
            raise EnterpriseModelError("repository manifest requires explicit trust_boundaries")
        if self.epistemic_confidence is not None and not 0.0 <= self.epistemic_confidence <= 1.0:
            raise EnterpriseModelError("epistemic confidence must be in [0,1]")
        return self

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "RepositoryManifest":
        root = _exact_object(value, "repository manifest", _MANIFEST_ROOT_KEYS)
        if root.get("schema_version") != "1.0.0":
            raise EnterpriseModelError("unsupported repository manifest schema_version")

        repo = _exact_object(root.get("repository"), "repository", _REPOSITORY_KEYS)
        cyber = _exact_object(root.get("cyber_lion"), "cyber_lion", _CYBER_LION_KEYS)
        authority = _exact_object(root.get("authority"), "authority", _AUTHORITY_KEYS)
        observability = _exact_object(root.get("observability"), "observability", _OBSERVABILITY_KEYS)
        security = _exact_object(root.get("security"), "security", _SECURITY_KEYS)
        epistemic = _exact_object(root.get("epistemic"), "epistemic", _EPISTEMIC_KEYS)

        vcs_ref = repo.get("vcs_ref")
        if vcs_ref is not None and type(vcs_ref) is not str:
            raise EnterpriseModelError("repository.vcs_ref must be string or null")
        confidence = epistemic.get("confidence")
        if confidence is not None and (
            isinstance(confidence, bool) or not isinstance(confidence, (int, float))
        ):
            raise EnterpriseModelError("epistemic.confidence must be number or null")

        manifest = cls(
            repository_id=_native_string(repo.get("id"), "repository.id"),
            url=_native_string(repo.get("url"), "repository.url"),
            owner=_native_string(repo.get("owner"), "repository.owner"),
            default_branch=_native_string(repo.get("default_branch"), "repository.default_branch"),
            tile_id=_native_string(cyber.get("tile_id"), "cyber_lion.tile_id"),
            roles=_native_string_list(cyber.get("roles"), "cyber_lion.roles"),
            layers=_native_string_list(cyber.get("layers"), "cyber_lion.layers"),
            dispositions=_native_string_list(cyber.get("disposition"), "cyber_lion.disposition"),
            capabilities=_native_string_list(root.get("capabilities"), "capabilities"),
            maximum_authority=_native_string(authority.get("maximum_level"), "authority.maximum_level"),
            required_gates=_native_string_list(authority.get("required_gates"), "authority.required_gates"),
            logs=_native_string_list(observability.get("logs"), "observability.logs"),
            metrics=_native_string_list(observability.get("metrics"), "observability.metrics"),
            traces=_native_string_list(observability.get("traces"), "observability.traces"),
            trust_boundaries=_native_string_list(security.get("trust_boundaries"), "security.trust_boundaries"),
            epistemic_status=_native_string(epistemic.get("status"), "epistemic.status"),
            epistemic_confidence=confidence,
        )
        return manifest.validate()


@dataclass
class RepositoryFederationRegistry:
    """Deterministic discovery index over repository manifests."""

    _repositories: Dict[str, RepositoryManifest] = field(default_factory=dict)
    _tiles: Dict[str, str] = field(default_factory=dict)

    def register(self, manifest: RepositoryManifest) -> None:
        manifest.validate()
        current = self._repositories.get(manifest.repository_id)
        if current is not None and current != manifest:
            raise EnterpriseModelError(
                f"repository manifest changed under same repository id: {manifest.repository_id}"
            )
        tile_owner = self._tiles.get(manifest.tile_id)
        if tile_owner is not None and tile_owner != manifest.repository_id:
            raise EnterpriseModelError(
                f"tile_id collision: {manifest.tile_id} already owned by {tile_owner}"
            )
        self._repositories[manifest.repository_id] = manifest
        self._tiles[manifest.tile_id] = manifest.repository_id

    def register_mapping(self, value: Mapping[str, Any]) -> RepositoryManifest:
        manifest = RepositoryManifest.from_mapping(value)
        self.register(manifest)
        return manifest

    def get(self, repository_id: str) -> RepositoryManifest:
        try:
            return self._repositories[repository_id]
        except KeyError as exc:
            raise KeyError(f"unknown repository manifest: {repository_id}") from exc

    def discover_capability(self, capability: str) -> Tuple[RepositoryManifest, ...]:
        return tuple(
            sorted(
                (m for m in self._repositories.values() if capability in m.capabilities),
                key=lambda m: (authority_rank(m.maximum_authority), m.repository_id),
            )
        )

    def discover_layer(self, layer: str) -> Tuple[RepositoryManifest, ...]:
        if layer not in _ALLOWED_LAYERS:
            raise EnterpriseModelError(f"unknown enterprise layer: {layer}")
        return tuple(sorted((m for m in self._repositories.values() if layer in m.layers), key=lambda m: m.repository_id))

    def all(self) -> Tuple[RepositoryManifest, ...]:
        return tuple(sorted(self._repositories.values(), key=lambda m: m.repository_id))
