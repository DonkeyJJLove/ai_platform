"""Deterministic, non-authoritative federation architecture knowledge contracts."""
from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from hashlib import sha256
import json
import re
from typing import Any, Mapping, Tuple

from cyber_lion.contracts.formalization_registry import validate_repository

SCHEMA_ID = "lion.federated-architecture-knowledge/v1"
DIGEST_DOMAIN = b"LION/FEDERATED-ARCHITECTURE-KNOWLEDGE/1\0"
AUTHORITY_EFFECT = "NONE"

ARTIFACT_CLASSES = frozenset({
    "HUMAN_ARCHITECTURE_DOCUMENT", "MACHINE_READABLE_ARCHITECTURE",
    "ARCHITECTURE_PROJECTION", "SEMANTIC_OWNER_MAP", "CONTRACT_CATALOG",
    "CAPABILITY_CATALOG", "REPOSITORY_MANIFEST", "FEDERATION_MANIFEST",
    "CURRENTNESS_CARRIER", "TRUTH_CARRIER", "TARGET_ARCHITECTURE",
    "AS_IS_ARCHITECTURE", "ROADMAP", "ADR", "PROCESS_CONTRACT",
    "RAG_ROUTING", "SOURCE_PROVENANCE", "EVIDENCE", "GAP_PROJECTION",
    "EVALUATION", "FORMALIZATION_ARTIFACT", "HISTORY", "SUPERSESSION_RECORD",
    "DEPLOYMENT_RUNTIME_IDENTITY", "GENERATED_DOCUMENTATION",
    "NONCANONICAL_OR_STALE_DOCUMENTATION",
})
EDGE_RELATIONS = frozenset({
    "GENERATED_FROM", "PROJECTS", "EXPLAINS", "OWNS", "MIRRORS",
    "CONSUMED_BY", "INVALIDATED_BY", "VALIDATED_BY", "SUPERSEDES",
    "DISCOVERED_FROM", "ROUTED_BY", "REFERENCES", "MATERIALIZES",
    "CONSTRAINS", "PROPOSES_CHANGE_TO",
})
CURRENTNESS = frozenset({
    "CURRENT", "STALE", "UNKNOWN", "SUPERSEDED", "TARGET_ONLY",
    "CONTRACT_ONLY", "PARTIALLY_IMPLEMENTED", "VERSIONED_STATIC",
})
INFLUENCE_CLASSES = frozenset({
    "EVOLUTION_INPUT", "EVOLUTION_CONSTRAINT", "EVOLUTION_PROJECTION",
    "EVOLUTION_VALIDATION", "EVOLUTION_MEMORY", "DISCOVERABILITY_ONLY",
    "HUMAN_ONLY", "UNUSED", "ACCIDENTAL_DEPENDENCY",
})
_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,255}$")
_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class ArchitectureKnowledgeError(ValueError):
    pass


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _id(value: str, name: str) -> str:
    if not isinstance(value, str) or not _SAFE_ID.fullmatch(value):
        raise ArchitectureKnowledgeError(f"{name} invalid")
    return value


def _text(value: str, name: str) -> str:
    if not isinstance(value, str) or not value.strip() or "\x00" in value:
        raise ArchitectureKnowledgeError(f"{name} invalid")
    return value


def _strings(values: Tuple[str, ...], name: str) -> Tuple[str, ...]:
    if type(values) is not tuple:
        raise ArchitectureKnowledgeError(f"{name} must be tuple")
    for item in values:
        _text(item, name)
    if len(values) != len(set(values)):
        raise ArchitectureKnowledgeError(f"{name} must be unique")
    return values


@dataclass(frozen=True)
class ArchitectureDocumentRecord:
    artifact_id: str
    repository: str
    path: str
    artifact_class: str
    semantic_owner_concept: str
    currentness: str
    generator: str | None
    source_refs: Tuple[str, ...]
    consumers: Tuple[str, ...]
    invalidated_by: Tuple[str, ...]
    validation_refs: Tuple[str, ...]
    influence_class: str
    supersedes: str | None = None
    superseded_by: str | None = None

    def validate(self) -> "ArchitectureDocumentRecord":
        _id(self.artifact_id, "artifact_id")
        validate_repository(self.repository)
        _text(self.path, "path")
        if self.path.startswith("/"):
            raise ArchitectureKnowledgeError("artifact path must be repository-relative")
        if self.artifact_class not in ARTIFACT_CLASSES:
            raise ArchitectureKnowledgeError("artifact_class invalid")
        _id(self.semantic_owner_concept, "semantic_owner_concept")
        if self.currentness not in CURRENTNESS:
            raise ArchitectureKnowledgeError("currentness invalid")
        if self.generator is not None:
            _text(self.generator, "generator")
        _strings(self.source_refs, "source_refs")
        _strings(self.consumers, "consumers")
        _strings(self.invalidated_by, "invalidated_by")
        _strings(self.validation_refs, "validation_refs")
        if self.influence_class not in INFLUENCE_CLASSES:
            raise ArchitectureKnowledgeError("influence_class invalid")
        if self.supersedes is not None:
            _id(self.supersedes, "supersedes")
        if self.superseded_by is not None:
            _id(self.superseded_by, "superseded_by")
        return self


@dataclass(frozen=True, order=True)
class ArchitectureDocumentEdge:
    source_artifact_id: str
    target_artifact_id: str
    relation: str
    evidence_ref: str

    def validate(self) -> "ArchitectureDocumentEdge":
        _id(self.source_artifact_id, "source_artifact_id")
        _id(self.target_artifact_id, "target_artifact_id")
        if self.source_artifact_id == self.target_artifact_id:
            raise ArchitectureKnowledgeError("self edge denied")
        if self.relation not in EDGE_RELATIONS:
            raise ArchitectureKnowledgeError("edge relation invalid")
        _text(self.evidence_ref, "evidence_ref")
        return self


@dataclass(frozen=True)
class FederatedArchitectureKnowledge:
    federation_digest: str
    documents: Tuple[ArchitectureDocumentRecord, ...]
    edges: Tuple[ArchitectureDocumentEdge, ...]
    authority_effect: str = AUTHORITY_EFFECT
    knowledge_digest: str = ""
    schema_id: str = SCHEMA_ID

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "federation_digest": self.federation_digest,
            "documents": [asdict(x) for x in sorted(self.documents, key=lambda x: x.artifact_id)],
            "edges": [asdict(x) for x in sorted(self.edges)],
            "authority_effect": self.authority_effect,
        }

    def compute_digest(self) -> str:
        return sha256(DIGEST_DOMAIN + canonical_json(self.canonical_payload())).hexdigest()

    def validate(self, *, require_digest: bool = True) -> "FederatedArchitectureKnowledge":
        if self.schema_id != SCHEMA_ID:
            raise ArchitectureKnowledgeError("schema_id invalid")
        if not _SHA256.fullmatch(self.federation_digest):
            raise ArchitectureKnowledgeError("federation_digest invalid")
        if self.authority_effect != "NONE":
            raise ArchitectureKnowledgeError("architecture knowledge cannot carry authority")
        if type(self.documents) is not tuple or not self.documents:
            raise ArchitectureKnowledgeError("documents required")
        docs = tuple(x.validate() for x in self.documents)
        ids = [x.artifact_id for x in docs]
        if len(ids) != len(set(ids)):
            raise ArchitectureKnowledgeError("duplicate artifact_id")
        known = set(ids)
        if type(self.edges) is not tuple:
            raise ArchitectureKnowledgeError("edges must be tuple")
        for edge in self.edges:
            edge.validate()
            if edge.source_artifact_id not in known or edge.target_artifact_id not in known:
                raise ArchitectureKnowledgeError("edge references unknown artifact")
        if require_digest:
            if not _SHA256.fullmatch(self.knowledge_digest):
                raise ArchitectureKnowledgeError("knowledge_digest invalid")
            if self.knowledge_digest != self.compute_digest():
                raise ArchitectureKnowledgeError("knowledge_digest mismatch")
        elif self.knowledge_digest and not _SHA256.fullmatch(self.knowledge_digest):
            raise ArchitectureKnowledgeError("knowledge_digest invalid")
        return self

    def sealed(self) -> "FederatedArchitectureKnowledge":
        self.validate(require_digest=False)
        return replace(self, knowledge_digest=self.compute_digest()).validate()


def classify_document_currentness(
    *, observed_head: str, observed_tree: str, current_head: str, current_tree: str,
    target_only: bool = False, contract_only: bool = False,
) -> str:
    for value in (observed_head, observed_tree, current_head, current_tree):
        if not _SHA40.fullmatch(value):
            raise ArchitectureKnowledgeError("currentness identity must be sha40")
    if target_only:
        return "TARGET_ONLY"
    if contract_only:
        return "CONTRACT_ONLY"
    if observed_head == current_head and observed_tree == current_tree:
        return "CURRENT"
    return "STALE"
