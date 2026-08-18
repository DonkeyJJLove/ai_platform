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
        if value.get("schema_version") != "1.0.0":
            raise EnterpriseModelError("unsupported repository manifest schema_version")
        try:
            repo = value["repository"]
            cyber = value["cyber_lion"]
            authority = value["authority"]
            observability = value["observability"]
            security = value["security"]
            epistemic = value["epistemic"]
            manifest = cls(
                repository_id=str(repo["id"]),
                url=str(repo["url"]),
                owner=str(repo["owner"]),
                default_branch=str(repo["default_branch"]),
                tile_id=str(cyber["tile_id"]),
                roles=tuple(cyber["roles"]),
                layers=tuple(cyber["layers"]),
                dispositions=tuple(cyber["disposition"]),
                capabilities=tuple(value["capabilities"]),
                maximum_authority=str(authority["maximum_level"]),
                required_gates=tuple(authority["required_gates"]),
                logs=tuple(observability["logs"]),
                metrics=tuple(observability["metrics"]),
                traces=tuple(observability["traces"]),
                trust_boundaries=tuple(security["trust_boundaries"]),
                epistemic_status=str(epistemic["status"]),
                epistemic_confidence=epistemic.get("confidence"),
            )
        except (KeyError, TypeError) as exc:
            raise EnterpriseModelError(f"invalid repository manifest structure: {exc}") from exc
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
