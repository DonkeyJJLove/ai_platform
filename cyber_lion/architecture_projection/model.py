from __future__ import annotations
from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import re
from typing import Final

RELATION_TYPES: Final = frozenset({
    "CONTAINS","IMPORTS","CALLS_STATIC","SOURCE_PROVENANCE","AUTHORITY_REFERENCE",
    "EFFECT_BOUNDARY","PERSISTENCE_BINDING","EVENT_CAUSALITY","FLEET_MEMBERSHIP",
    "EPOCH_TRANSITION","UNKNOWN",
})
DIAGRAM_TYPES: Final = frozenset({"component","class","sequence","state","deployment"})
ID_RE: Final = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,127}$")
_SHA40: Final = re.compile(r"^[0-9a-f]{40}$")
_SHA64: Final = re.compile(r"^[0-9a-f]{64}$")
_ID_DOMAIN: Final = b"LION/UML/PROJECTION-IDENTITY/1\0"
_MODEL_DOMAIN: Final = b"LION/UML/CANONICAL-DIAGRAM-MODEL/2\0"


def _nonempty(value: str, name: str) -> str:
    if not isinstance(value, str) or not value.strip() or "\x00" in value:
        raise ValueError(f"{name} must be non-empty text")
    return value


def _safe_id(value: str, name: str) -> str:
    if not isinstance(value, str) or not ID_RE.fullmatch(value):
        raise ValueError(f"{name} must be a PlantUML-safe identifier")
    return value


def canonical_projection_identity(*, relation_domain: str, canonical_source_path: str, semantic_kind: str, qualified_name: str) -> str:
    """Deterministic checkout-root-independent identity for projection facts."""
    parts = tuple(_nonempty(v, n) for v, n in (
        (relation_domain, "relation_domain"),
        (canonical_source_path, "canonical_source_path"),
        (semantic_kind, "semantic_kind"),
        (qualified_name, "qualified_name"),
    ))
    payload = json.dumps(parts, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return "n_" + sha256(_ID_DOMAIN + payload).hexdigest()[:32]


@dataclass(frozen=True, order=True)
class DiagramNode:
    node_id: str
    label: str
    kind: str
    source_path: str = ""
    source_digest: str = ""
    fact_class: str = "CANONICAL_FACT"
    authority_semantics: str = "NONE"

    def validate(self):
        _safe_id(self.node_id, "node_id")
        _nonempty(self.label, "label")
        _nonempty(self.kind, "kind")
        if self.fact_class not in {"CANONICAL_FACT", "DECLARED_NEXT_FRONTIER"}:
            raise ValueError("node fact_class invalid")
        if self.fact_class == "CANONICAL_FACT":
            _nonempty(self.source_path, "source_path")
            if not _SHA64.fullmatch(self.source_digest):
                raise ValueError("canonical fact source_digest invalid")
        else:
            _nonempty(self.source_path, "source_path")
            if self.source_digest and not _SHA64.fullmatch(self.source_digest):
                raise ValueError("frontier source_digest invalid")
        if self.authority_semantics not in {"NONE", "REFERENCE_ONLY"}:
            raise ValueError("diagram node cannot carry authority")
        return self


@dataclass(frozen=True, order=True)
class DiagramEdge:
    source: str
    target: str
    relation: str
    label: str = ""
    provenance_ref: str = ""
    runtime_proof: bool = False
    authority_effect: bool = False

    def validate(self):
        _safe_id(self.source, "edge source")
        _safe_id(self.target, "edge target")
        if self.relation not in RELATION_TYPES:
            raise ValueError("unknown relation type")
        if self.relation != "UNKNOWN":
            _nonempty(self.provenance_ref, "provenance_ref")
        if self.runtime_proof or self.authority_effect:
            raise ValueError("derived diagram cannot prove runtime or grant authority")
        return self


@dataclass(frozen=True, order=True)
class DiagramGroup:
    group_id: str
    label: str
    node_ids: tuple[str, ...]

    def validate(self):
        _safe_id(self.group_id, "group_id")
        _nonempty(self.label, "label")
        if tuple(sorted(set(self.node_ids))) != self.node_ids:
            raise ValueError("group node ids must be sorted unique")
        for node_id in self.node_ids:
            _safe_id(node_id, "group node id")
        return self


@dataclass(frozen=True)
class CanonicalDiagramModel:
    diagram_id: str
    diagram_type: str
    source_tree_sha: str
    nodes: tuple[DiagramNode, ...]
    edges: tuple[DiagramEdge, ...]
    groups: tuple[DiagramGroup, ...] = ()
    derived_only: bool = True
    authority_effect: str = "NONE"
    runtime_evidence: str = "NONE"

    def validate(self):
        _nonempty(self.diagram_id, "diagram_id")
        if self.diagram_type not in DIAGRAM_TYPES:
            raise ValueError("unsupported diagram type")
        if not _SHA40.fullmatch(self.source_tree_sha):
            raise ValueError("source tree sha invalid")
        if not self.derived_only or self.authority_effect != "NONE" or self.runtime_evidence != "NONE":
            raise ValueError("projection must remain non-authoritative")
        ids = []
        seen = {}
        for node in self.nodes:
            node.validate()
            previous = seen.get(node.node_id)
            if previous is not None and previous != node:
                raise ValueError("projection identity collision")
            seen[node.node_id] = node
            ids.append(node.node_id)
        if tuple(ids) != tuple(sorted(set(ids))):
            raise ValueError("nodes must be sorted unique")
        idset = set(ids)
        for edge in self.edges:
            edge.validate()
            if edge.source not in idset or edge.target not in idset:
                raise ValueError("dangling edge")
        if self.edges != tuple(sorted(set(self.edges))):
            raise ValueError("edges must be sorted unique")
        for group in self.groups:
            group.validate()
            if not set(group.node_ids).issubset(idset):
                raise ValueError("group references unknown node")
        if self.groups != tuple(sorted(set(self.groups))):
            raise ValueError("groups must be sorted unique")
        return self

    def canonical_payload(self):
        self.validate()
        return asdict(self)

    def canonical_bytes(self):
        return json.dumps(self.canonical_payload(), sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")

    def source_digest(self):
        return sha256(_MODEL_DOMAIN + self.canonical_bytes()).hexdigest()


@dataclass(frozen=True)
class DiagramProjectionManifest:
    source_tree_sha: str
    diagram_id: str
    diagram_source_digest: str
    plantuml_version: str
    plantuml_binary_digest: str
    rendering_mode: str
    generated_artifact_digest: str
    authority_effect: str = "NONE"
    runtime_evidence: str = "NONE"

    def validate(self):
        if not _SHA40.fullmatch(self.source_tree_sha):
            raise ValueError("source tree sha invalid")
        _nonempty(self.diagram_id, "diagram_id")
        for name in ("diagram_source_digest", "plantuml_binary_digest", "generated_artifact_digest"):
            if not _SHA64.fullmatch(getattr(self, name)):
                raise ValueError(f"{name} invalid")
        _nonempty(self.plantuml_version, "plantuml_version")
        if self.rendering_mode not in {"PUML_ONLY", "LOCAL_OFFLINE"}:
            raise ValueError("network rendering forbidden")
        if self.authority_effect != "NONE" or self.runtime_evidence != "NONE":
            raise ValueError("manifest cannot carry authority or runtime proof")
        return self
