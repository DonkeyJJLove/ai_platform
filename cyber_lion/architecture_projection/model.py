from __future__ import annotations
from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from typing import Final

RELATION_TYPES: Final = frozenset({
    "CONTAINS","IMPORTS","CALLS_STATIC","SOURCE_PROVENANCE","AUTHORITY_REFERENCE",
    "EFFECT_BOUNDARY","PERSISTENCE_BINDING","EVENT_CAUSALITY","FLEET_MEMBERSHIP",
    "EPOCH_TRANSITION","UNKNOWN",
})
DIAGRAM_TYPES: Final = frozenset({"component","class","sequence","state","deployment"})


def _nonempty(value: str, name: str) -> str:
    if not isinstance(value, str) or not value.strip() or "\x00" in value:
        raise ValueError(f"{name} must be non-empty text")
    return value

@dataclass(frozen=True, order=True)
class DiagramNode:
    node_id: str
    label: str
    kind: str
    source_path: str = ""
    authority_semantics: str = "NONE"
    def validate(self):
        _nonempty(self.node_id,"node_id"); _nonempty(self.label,"label"); _nonempty(self.kind,"kind")
        if self.authority_semantics not in {"NONE","REFERENCE_ONLY"}: raise ValueError("diagram node cannot carry authority")
        return self

@dataclass(frozen=True, order=True)
class DiagramEdge:
    source: str
    target: str
    relation: str
    label: str = ""
    runtime_proof: bool = False
    authority_effect: bool = False
    def validate(self):
        _nonempty(self.source,"source"); _nonempty(self.target,"target")
        if self.relation not in RELATION_TYPES: raise ValueError("unknown relation type")
        if self.runtime_proof or self.authority_effect: raise ValueError("derived diagram cannot prove runtime or grant authority")
        return self

@dataclass(frozen=True, order=True)
class DiagramGroup:
    group_id: str
    label: str
    node_ids: tuple[str, ...]
    def validate(self):
        _nonempty(self.group_id,"group_id"); _nonempty(self.label,"label")
        if tuple(sorted(set(self.node_ids))) != self.node_ids: raise ValueError("group node ids must be sorted unique")
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
        _nonempty(self.diagram_id,"diagram_id")
        if self.diagram_type not in DIAGRAM_TYPES: raise ValueError("unsupported diagram type")
        if len(self.source_tree_sha)!=40 or any(c not in "0123456789abcdef" for c in self.source_tree_sha): raise ValueError("source tree sha invalid")
        if not self.derived_only or self.authority_effect!="NONE" or self.runtime_evidence!="NONE": raise ValueError("projection must remain non-authoritative")
        ids=[]
        for n in self.nodes: n.validate(); ids.append(n.node_id)
        if tuple(ids)!=tuple(sorted(set(ids))): raise ValueError("nodes must be sorted unique")
        idset=set(ids)
        for e in self.edges:
            e.validate()
            if e.source not in idset or e.target not in idset: raise ValueError("dangling edge")
        if self.edges!=tuple(sorted(set(self.edges))): raise ValueError("edges must be sorted unique")
        for g in self.groups: g.validate()
        if self.groups!=tuple(sorted(set(self.groups))): raise ValueError("groups must be sorted unique")
        return self
    def canonical_payload(self):
        self.validate(); return asdict(self)
    def canonical_bytes(self):
        return json.dumps(self.canonical_payload(),sort_keys=True,separators=(",",":"),ensure_ascii=False).encode("utf-8")
    def source_digest(self): return sha256(b"LION/UML/CANONICAL-DIAGRAM-MODEL/1\0"+self.canonical_bytes()).hexdigest()

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
        for name in ("diagram_source_digest","plantuml_binary_digest","generated_artifact_digest"):
            value=getattr(self,name)
            if len(value)!=64 or any(c not in "0123456789abcdef" for c in value): raise ValueError(f"{name} invalid")
        if len(self.source_tree_sha)!=40: raise ValueError("source tree sha invalid")
        if self.rendering_mode not in {"PUML_ONLY","LOCAL_OFFLINE"}: raise ValueError("network rendering forbidden")
        if self.authority_effect!="NONE" or self.runtime_evidence!="NONE": raise ValueError("manifest cannot carry authority or runtime proof")
        return self
