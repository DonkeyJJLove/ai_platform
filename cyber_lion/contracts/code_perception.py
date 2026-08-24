"""Deterministic code-perception contracts.

These records describe source-derived facts. They are evidence only and never execution
or authority grants. Probabilistic interpretation belongs in a separate analysis plane.

R10 makes call semantics explicit: a ``CALLS`` edge is deterministic static call
evidence only. Its ``target_node_id`` may identify a source-derived lexical candidate,
but it never proves the callable selected by a future Python runtime. Exact runtime
callable identity belongs to a separate ``RuntimeCallTargetProof`` evidence class that
binds an exact CodeGraph plus independently produced runtime-observation evidence.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import re
from typing import Any, Mapping

from cyber_lion.contracts.enterprise_graph import canonical_json

_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_SYMBOL_KINDS = {"MODULE", "CLASS", "FUNCTION", "METHOD", "ASYNC_FUNCTION", "ASYNC_METHOD"}
_EDGE_TYPES = {"CONTAINS", "DEFINES", "IMPORTS", "CALLS", "INHERITS", "DECORATED_BY"}
_PARSE_PREFIXES = ("PARSED", "NOT_APPLICABLE", "PARSE_ERROR:")
_CALL_SEMANTICS_VERSION = "2.0.0"
_STATIC_CALL_SEMANTICS = "STATIC_CALL_EVIDENCE"
_SOURCE_RELATION_SEMANTICS = "SOURCE_RELATION"
_RUNTIME_TARGET_UNRESOLVED = "UNRESOLVED"
_RUNTIME_TARGET_NOT_APPLICABLE = "NOT_APPLICABLE"
_RUNTIME_PROOF_CLASS = "EXACT_RUNTIME_CALL_TARGET"
_RUNTIME_PROOF_ORIGIN = "DETERMINISTIC_RUNTIME_EVIDENCE"


class CodePerceptionError(ValueError):
    pass


def _text(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip() or "\x00" in value:
        raise CodePerceptionError(f"{name} invalid")
    return value


def _sha40(value: object, name: str) -> str:
    text = _text(value, name)
    if _SHA40.fullmatch(text) is None:
        raise CodePerceptionError(f"{name} must be 40-char lowercase git sha")
    return text


def _sha256(value: object, name: str) -> str:
    text = _text(value, name)
    if _SHA256.fullmatch(text) is None:
        raise CodePerceptionError(f"{name} must be sha256 hex")
    return text


def stable_digest(*parts: str) -> str:
    return sha256("\0".join(parts).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class SourceIdentity:
    repository: str
    source_commit_sha: str
    source_tree_sha: str

    def validate(self) -> "SourceIdentity":
        _text(self.repository, "repository")
        _sha40(self.source_commit_sha, "source_commit_sha")
        _sha40(self.source_tree_sha, "source_tree_sha")
        return self


@dataclass(frozen=True)
class FileRecord:
    repository: str
    source_commit_sha: str
    source_tree_sha: str
    file_id: str
    path: str
    blob_sha: str
    language: str
    size: int
    parse_state: str
    fact_origin: str = "DETERMINISTIC"
    authority_effect: bool = False

    def validate(self) -> "FileRecord":
        SourceIdentity(self.repository, self.source_commit_sha, self.source_tree_sha).validate()
        _sha256(self.file_id, "file_id")
        _text(self.path, "path")
        if self.path.startswith("/") or "\\" in self.path or ".." in self.path.split("/"):
            raise CodePerceptionError("path must be normalized repository-relative POSIX path")
        _sha40(self.blob_sha, "blob_sha")
        _text(self.language, "language")
        if not isinstance(self.size, int) or self.size < 0:
            raise CodePerceptionError("size invalid")
        if not isinstance(self.parse_state, str) or not self.parse_state.startswith(_PARSE_PREFIXES):
            raise CodePerceptionError("parse_state invalid")
        if self.fact_origin != "DETERMINISTIC" or self.authority_effect is not False:
            raise CodePerceptionError("source facts cannot be probabilistic or authoritative")
        expected = stable_digest("file", self.path, self.blob_sha)
        if self.file_id != expected:
            raise CodePerceptionError("file_id binding mismatch")
        return self


@dataclass(frozen=True)
class SymbolRecord:
    node_id: str
    kind: str
    qualified_name: str
    file_id: str
    blob_sha: str
    start_line: int
    start_col: int
    end_line: int
    end_col: int
    signature: str
    semantic_digest: str
    path: str
    fact_origin: str = "DETERMINISTIC"
    authority_effect: bool = False

    def validate(self) -> "SymbolRecord":
        _sha256(self.node_id, "node_id")
        if self.kind not in _SYMBOL_KINDS:
            raise CodePerceptionError("unknown symbol kind")
        _text(self.qualified_name, "qualified_name")
        _sha256(self.file_id, "file_id")
        _sha40(self.blob_sha, "blob_sha")
        _text(self.path, "path")
        _sha256(self.semantic_digest, "semantic_digest")
        if not isinstance(self.signature, str) or "\x00" in self.signature:
            raise CodePerceptionError("signature invalid")
        for name, value in (
            ("start_line", self.start_line), ("start_col", self.start_col),
            ("end_line", self.end_line), ("end_col", self.end_col),
        ):
            if not isinstance(value, int) or value < (1 if "line" in name else 0):
                raise CodePerceptionError(f"{name} invalid")
        if (self.end_line, self.end_col) < (self.start_line, self.start_col):
            raise CodePerceptionError("source range inverted")
        expected = stable_digest("symbol", self.path, self.qualified_name, self.kind)
        if self.node_id != expected:
            raise CodePerceptionError("node_id logical identity mismatch")
        if self.fact_origin != "DETERMINISTIC" or self.authority_effect is not False:
            raise CodePerceptionError("symbol facts cannot be probabilistic or authoritative")
        return self


@dataclass(frozen=True)
class CodeEdge:
    edge_id: str
    edge_type: str
    source_node_id: str
    target_node_id: str | None
    unresolved_target: str | None
    evidence_ref: str
    fact_origin: str = "DETERMINISTIC"
    authority_effect: bool = False

    @property
    def semantic_class(self) -> str:
        return _STATIC_CALL_SEMANTICS if self.edge_type == "CALLS" else _SOURCE_RELATION_SEMANTICS

    @property
    def runtime_target_state(self) -> str:
        return _RUNTIME_TARGET_UNRESOLVED if self.edge_type == "CALLS" else _RUNTIME_TARGET_NOT_APPLICABLE

    def validate(self) -> "CodeEdge":
        _sha256(self.edge_id, "edge_id")
        if self.edge_type not in _EDGE_TYPES:
            raise CodePerceptionError("unknown edge_type")
        _sha256(self.source_node_id, "source_node_id")
        if (self.target_node_id is None) == (self.unresolved_target is None):
            raise CodePerceptionError("edge requires exactly one resolved or unresolved source-derived target")
        target_identity: str
        if self.target_node_id is not None:
            target_identity = _sha256(self.target_node_id, "target_node_id")
        else:
            target_identity = "?" + _text(self.unresolved_target, "unresolved_target")
        _text(self.evidence_ref, "evidence_ref")
        expected = stable_digest(
            "edge", self.edge_type, self.source_node_id, target_identity, self.evidence_ref
        )
        if self.edge_id != expected:
            raise CodePerceptionError("edge_id binding mismatch")
        if self.fact_origin != "DETERMINISTIC" or self.authority_effect is not False:
            raise CodePerceptionError("code edges cannot be probabilistic or authoritative")
        return self

    def logical_payload(self) -> Mapping[str, Any]:
        self.validate()
        payload = asdict(self)
        payload["semantic_class"] = self.semantic_class
        payload["runtime_target_state"] = self.runtime_target_state
        return payload


@dataclass(frozen=True)
class CodeGraph:
    schema_version: str
    source: SourceIdentity
    files: tuple[FileRecord, ...]
    symbols: tuple[SymbolRecord, ...]
    edges: tuple[CodeEdge, ...]
    authority_effect: bool = False
    call_semantics_version: str = _CALL_SEMANTICS_VERSION

    def validate(self) -> "CodeGraph":
        if self.schema_version != "1.0.0":
            raise CodePerceptionError("unsupported code graph schema")
        if self.call_semantics_version != _CALL_SEMANTICS_VERSION:
            raise CodePerceptionError("unsupported call semantics version")
        self.source.validate()
        if type(self.files) is not tuple or type(self.symbols) is not tuple or type(self.edges) is not tuple:
            raise CodePerceptionError("graph collections must be tuples")
        if self.authority_effect is not False:
            raise CodePerceptionError("code graph is evidence, never authority")
        file_ids: set[str] = set()
        symbol_ids: set[str] = set()
        for item in self.files:
            item.validate()
            if item.file_id in file_ids:
                raise CodePerceptionError("duplicate file_id")
            if (item.repository, item.source_commit_sha, item.source_tree_sha) != (
                self.source.repository, self.source.source_commit_sha, self.source.source_tree_sha
            ):
                raise CodePerceptionError("file source binding mismatch")
            file_ids.add(item.file_id)
        for item in self.symbols:
            item.validate()
            if item.node_id in symbol_ids:
                raise CodePerceptionError("duplicate symbol node_id")
            if item.file_id not in file_ids:
                raise CodePerceptionError("symbol references unknown file")
            symbol_ids.add(item.node_id)
        valid_targets = file_ids | symbol_ids
        for edge in self.edges:
            edge.validate()
            if edge.source_node_id not in valid_targets:
                raise CodePerceptionError("dangling edge source")
            if edge.target_node_id is not None and edge.target_node_id not in valid_targets:
                raise CodePerceptionError("dangling edge target")
        return self

    def logical_payload(self) -> Mapping[str, Any]:
        self.validate()
        payload = asdict(self)
        payload["edges"] = tuple(edge.logical_payload() for edge in self.edges)
        return payload

    def canonical_bytes(self) -> bytes:
        return canonical_json(self.logical_payload())

    def digest(self) -> str:
        return sha256(self.canonical_bytes()).hexdigest()


@dataclass(frozen=True)
class RuntimeCallTargetProof:
    """Evidence binding an exact runtime callable target to one static CALLS edge.

    The source indexer never emits this record. Validation below checks shape and exact
    binding to a CodeGraph plus an external evidence digest; it does not authenticate
    the external observer or dereference the evidence. A consuming trust layer must
    independently verify the referenced runtime observation before treating it as an
    exact runtime-target proof. This record never grants authority.
    """

    proof_id: str
    repository: str
    source_commit_sha: str
    source_tree_sha: str
    code_graph_digest: str
    call_edge_id: str
    runtime_target_node_id: str
    observer_id: str
    evidence_ref: str
    evidence_digest: str
    proof_class: str = _RUNTIME_PROOF_CLASS
    fact_origin: str = _RUNTIME_PROOF_ORIGIN
    authority_effect: bool = False

    def validate(self, graph: CodeGraph | None = None) -> "RuntimeCallTargetProof":
        source = SourceIdentity(self.repository, self.source_commit_sha, self.source_tree_sha).validate()
        _sha256(self.proof_id, "proof_id")
        _sha256(self.code_graph_digest, "code_graph_digest")
        _sha256(self.call_edge_id, "call_edge_id")
        _sha256(self.runtime_target_node_id, "runtime_target_node_id")
        _text(self.observer_id, "observer_id")
        _text(self.evidence_ref, "evidence_ref")
        _sha256(self.evidence_digest, "evidence_digest")
        if self.proof_class != _RUNTIME_PROOF_CLASS:
            raise CodePerceptionError("runtime call target requires exact proof class")
        if self.fact_origin != _RUNTIME_PROOF_ORIGIN or self.authority_effect is not False:
            raise CodePerceptionError("runtime call proof must be deterministic evidence only")
        expected = stable_digest(
            "runtime-call-target-proof",
            source.repository,
            source.source_commit_sha,
            source.source_tree_sha,
            self.code_graph_digest,
            self.call_edge_id,
            self.runtime_target_node_id,
            self.observer_id,
            self.evidence_ref,
            self.evidence_digest,
            self.proof_class,
        )
        if self.proof_id != expected:
            raise CodePerceptionError("runtime call proof binding mismatch")
        if graph is not None:
            graph.validate()
            if source != graph.source:
                raise CodePerceptionError("runtime call proof source mismatch")
            if self.code_graph_digest != graph.digest():
                raise CodePerceptionError("runtime call proof graph digest mismatch")
            matches = [edge for edge in graph.edges if edge.edge_id == self.call_edge_id]
            if len(matches) != 1 or matches[0].edge_type != "CALLS":
                raise CodePerceptionError("runtime proof must bind exactly one CALLS edge")
            if matches[0].runtime_target_state != _RUNTIME_TARGET_UNRESOLVED:
                raise CodePerceptionError("static CALLS runtime target must remain unresolved")
            symbol_ids = {symbol.node_id for symbol in graph.symbols}
            if self.runtime_target_node_id not in symbol_ids:
                raise CodePerceptionError("runtime proof target must be a graph symbol")
        return self

    def canonical_bytes(self) -> bytes:
        self.validate()
        return canonical_json(asdict(self))


@dataclass(frozen=True)
class PerceptionManifest:
    schema_version: str
    repository: str
    source_commit_sha: str
    source_tree_sha: str
    generator_version: str
    generator_digest: str
    file_count: int
    python_file_count: int
    parsed_python_file_count: int
    parse_error_count: int
    symbol_count: int
    edge_count: int
    code_graph_digest: str
    generated_at_is_non_semantic: bool
    authority_effect: bool = False

    def validate(self, graph: CodeGraph | None = None) -> "PerceptionManifest":
        if self.schema_version != "1.0.0":
            raise CodePerceptionError("unsupported manifest schema")
        SourceIdentity(self.repository, self.source_commit_sha, self.source_tree_sha).validate()
        _text(self.generator_version, "generator_version")
        _sha256(self.generator_digest, "generator_digest")
        _sha256(self.code_graph_digest, "code_graph_digest")
        for name in (
            "file_count", "python_file_count", "parsed_python_file_count",
            "parse_error_count", "symbol_count", "edge_count",
        ):
            value = getattr(self, name)
            if not isinstance(value, int) or value < 0:
                raise CodePerceptionError(f"{name} invalid")
        if self.generated_at_is_non_semantic is not True:
            raise CodePerceptionError("generated_at must be explicitly non-semantic")
        if self.authority_effect is not False:
            raise CodePerceptionError("manifest cannot grant authority")
        if graph is not None:
            graph.validate()
            if self.code_graph_digest != graph.digest():
                raise CodePerceptionError("manifest graph digest mismatch")
            if (self.repository, self.source_commit_sha, self.source_tree_sha) != (
                graph.source.repository, graph.source.source_commit_sha, graph.source.source_tree_sha
            ):
                raise CodePerceptionError("manifest source binding mismatch")
            if self.file_count != len(graph.files) or self.symbol_count != len(graph.symbols) or self.edge_count != len(graph.edges):
                raise CodePerceptionError("manifest counts mismatch")
        return self

    def canonical_bytes(self) -> bytes:
        self.validate()
        return canonical_json(asdict(self))
