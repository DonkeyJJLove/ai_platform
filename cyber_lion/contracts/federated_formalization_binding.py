"""Non-effectful binding between one local AFM and an exact federation baseline."""
from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from typing import Any, Mapping, Tuple

from .formalization_registry import (
    FormalizationRegistryError,
    _id,
    _tuple_text,
    domain_digest,
    validate_repository,
    validate_sha40,
    validate_sha256,
)
from .repository_expansion import FleetBaseline, digest as fleet_digest

SCHEMA_ID = "lion.federated-formalization-binding/v1"
DIGEST_DOMAIN = b"LION/FEDERATED-FORMALIZATION-BINDING/1\0"
GRAPH_DIGEST_DOMAIN = b"LION/FEDERATED-FORMALIZATION-GRAPH/1\0"
AUTHORITY_EFFECT = EXECUTION_EFFECT = "NONE"
DISPOSITIONS = frozenset({"UPDATE", "VALIDATE_ONLY", "NOT_APPLICABLE"})


class FederatedFormalizationBindingError(FormalizationRegistryError):
    pass


@dataclass(frozen=True)
class RepositoryFormalizationDisposition:
    repository: str
    baseline_head: str
    baseline_tree: str
    disposition: str
    required_artifact_ids: Tuple[str, ...]

    def validate(self) -> "RepositoryFormalizationDisposition":
        validate_repository(self.repository)
        validate_sha40(self.baseline_head, "baseline_head")
        validate_sha40(self.baseline_tree, "baseline_tree")
        if self.disposition not in DISPOSITIONS:
            raise FederatedFormalizationBindingError("repository disposition invalid")
        _tuple_text(self.required_artifact_ids, "required_artifact_ids")
        if self.disposition == "UPDATE" and not self.required_artifact_ids:
            raise FederatedFormalizationBindingError("UPDATE repository requires artifacts")
        if self.disposition == "NOT_APPLICABLE" and self.required_artifact_ids:
            raise FederatedFormalizationBindingError("NOT_APPLICABLE cannot require artifacts")
        return self

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "RepositoryFormalizationDisposition":
        return cls(
            repository=value["repository"],
            baseline_head=value["baseline_head"],
            baseline_tree=value["baseline_tree"],
            disposition=value["disposition"],
            required_artifact_ids=tuple(value.get("required_artifact_ids", ())),
        ).validate()


def fleet_dependency_graph_digest(fleet: FleetBaseline) -> str:
    fleet.validate()
    rows = [
        edge.canonical_dict()
        for edge in sorted(
            fleet.edges,
            key=lambda edge: (
                edge.source,
                edge.target,
                edge.relation,
                edge.contract or "",
                edge.version_assumption or "",
                edge.failure_mode,
                edge.security_impact,
                edge.test_coverage,
                edge.evidence,
            ),
        )
    ]
    return fleet_digest(rows, GRAPH_DIGEST_DOMAIN)


@dataclass(frozen=True)
class FederatedFormalizationBinding:
    binding_id: str
    formalization_manifest_digest: str
    fleet_baseline_digest: str
    dependency_graph_digest: str
    repositories: Tuple[RepositoryFormalizationDisposition, ...]
    authority_effect: str = AUTHORITY_EFFECT
    execution_effect: str = EXECUTION_EFFECT
    binding_digest: str = ""
    schema_id: str = SCHEMA_ID

    def canonical_payload(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("binding_digest", None)
        data["repositories"] = [
            asdict(item) for item in sorted(self.repositories, key=lambda item: item.repository)
        ]
        return data

    def compute_digest(self) -> str:
        return domain_digest(DIGEST_DOMAIN, self.canonical_payload())

    def validate(self, fleet: FleetBaseline, *, require_digest: bool = True) -> "FederatedFormalizationBinding":
        fleet.validate()
        if self.schema_id != SCHEMA_ID:
            raise FederatedFormalizationBindingError("binding schema invalid")
        _id(self.binding_id, "binding_id")
        validate_sha256(self.formalization_manifest_digest, "formalization_manifest_digest")
        validate_sha256(self.fleet_baseline_digest, "fleet_baseline_digest")
        validate_sha256(self.dependency_graph_digest, "dependency_graph_digest")
        if self.authority_effect != AUTHORITY_EFFECT or self.execution_effect != EXECUTION_EFFECT:
            raise FederatedFormalizationBindingError("federated formalization cannot carry authority/effect")
        if self.fleet_baseline_digest != fleet.baseline_digest():
            raise FederatedFormalizationBindingError("fleet baseline digest mismatch")
        if self.dependency_graph_digest != fleet_dependency_graph_digest(fleet):
            raise FederatedFormalizationBindingError("dependency graph digest mismatch")
        if type(self.repositories) is not tuple or not self.repositories:
            raise FederatedFormalizationBindingError("repository dispositions required")
        validated = tuple(item.validate() for item in self.repositories)
        ids = [item.repository for item in validated]
        if len(ids) != len(set(ids)):
            raise FederatedFormalizationBindingError("duplicate repository disposition")
        pins = {
            item.repository: (item.expected_head, item.expected_tree)
            for item in fleet.registered
        }
        if set(ids) != set(pins):
            raise FederatedFormalizationBindingError("binding must exactly cover federation")
        for item in validated:
            if (item.baseline_head, item.baseline_tree) != pins[item.repository]:
                raise FederatedFormalizationBindingError("repository baseline substitution")
        if not any(item.disposition == "UPDATE" for item in validated):
            raise FederatedFormalizationBindingError("at least one UPDATE repository required")
        if require_digest:
            validate_sha256(self.binding_digest, "binding_digest")
            if self.binding_digest != self.compute_digest():
                raise FederatedFormalizationBindingError("binding digest mismatch")
        elif self.binding_digest:
            validate_sha256(self.binding_digest, "binding_digest")
        return self

    def sealed(self, fleet: FleetBaseline) -> "FederatedFormalizationBinding":
        self.validate(fleet, require_digest=False)
        return replace(self, binding_digest=self.compute_digest()).validate(fleet)

    def to_dict(self, fleet: FleetBaseline) -> dict[str, Any]:
        self.validate(fleet)
        return asdict(self)
