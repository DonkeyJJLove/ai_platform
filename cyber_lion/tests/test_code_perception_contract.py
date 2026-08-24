import hashlib
import unittest

from cyber_lion.contracts.code_perception import (
    CodeEdge,
    CodeGraph,
    CodePerceptionError,
    FileRecord,
    RuntimeCallTargetProof,
    SourceIdentity,
    SymbolRecord,
    stable_digest,
)


def blob_sha(data: bytes) -> str:
    return hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()


class CodePerceptionContractTests(unittest.TestCase):
    def setUp(self):
        self.source = SourceIdentity("DonkeyJJLove/ai_platform", "a" * 40, "b" * 40).validate()
        data = b"def f():\n    return 1\n"
        self.blob = blob_sha(data)
        self.file_id = stable_digest("file", "pkg/a.py", self.blob)
        self.file = FileRecord(
            self.source.repository,
            self.source.source_commit_sha,
            self.source.source_tree_sha,
            self.file_id,
            "pkg/a.py",
            self.blob,
            "python",
            len(data),
            "PARSED",
        ).validate()
        self.node_id = stable_digest("symbol", "pkg/a.py", "pkg.a", "MODULE")
        self.symbol = SymbolRecord(
            self.node_id,
            "MODULE",
            "pkg.a",
            self.file_id,
            self.blob,
            1,
            0,
            2,
            0,
            "",
            "c" * 64,
            "pkg/a.py",
        ).validate()

    def _call_edge(self, *, resolved: bool = True) -> CodeEdge:
        evidence = "blob:x:L1:C0-L1:C1"
        target = self.node_id if resolved else None
        unresolved = None if resolved else "dynamic"
        identity = target if target is not None else "?dynamic"
        return CodeEdge(
            stable_digest("edge", "CALLS", self.node_id, identity, evidence),
            "CALLS",
            self.node_id,
            target,
            unresolved,
            evidence,
        ).validate()

    def _graph(self, edge: CodeEdge | None = None) -> CodeGraph:
        return CodeGraph(
            "1.0.0",
            self.source,
            (self.file,),
            (self.symbol,),
            () if edge is None else (edge,),
        ).validate()

    def _runtime_proof(
        self,
        graph: CodeGraph,
        edge: CodeEdge,
        *,
        call_edge_id: str | None = None,
        target: str | None = None,
        source: SourceIdentity | None = None,
        graph_digest: str | None = None,
        proof_class: str = "EXACT_RUNTIME_CALL_TARGET",
    ) -> RuntimeCallTargetProof:
        actual_source = source or self.source
        actual_call = call_edge_id or edge.edge_id
        actual_target = target or self.node_id
        actual_graph_digest = graph_digest or graph.digest()
        observer = "observer://independent-runtime-01"
        evidence_ref = "runtime-observer:run-123:call-1"
        evidence_digest = "7" * 64
        proof_id = stable_digest(
            "runtime-call-target-proof",
            actual_source.repository,
            actual_source.source_commit_sha,
            actual_source.source_tree_sha,
            actual_graph_digest,
            actual_call,
            actual_target,
            observer,
            evidence_ref,
            evidence_digest,
            proof_class,
        )
        return RuntimeCallTargetProof(
            proof_id,
            actual_source.repository,
            actual_source.source_commit_sha,
            actual_source.source_tree_sha,
            actual_graph_digest,
            actual_call,
            actual_target,
            observer,
            evidence_ref,
            evidence_digest,
            proof_class=proof_class,
        )

    def test_source_fact_identity_is_payload_bound(self):
        with self.assertRaisesRegex(CodePerceptionError, "file_id binding mismatch"):
            FileRecord(
                self.source.repository,
                self.source.source_commit_sha,
                self.source.source_tree_sha,
                "0" * 64,
                "pkg/a.py",
                self.blob,
                "python",
                1,
                "PARSED",
            ).validate()

    def test_llm_fact_and_authority_injection_are_denied(self):
        with self.assertRaisesRegex(CodePerceptionError, "probabilistic or authoritative"):
            FileRecord(
                self.source.repository,
                self.source.source_commit_sha,
                self.source.source_tree_sha,
                self.file_id,
                "pkg/a.py",
                self.blob,
                "python",
                1,
                "PARSED",
                fact_origin="LLM",
            ).validate()
        with self.assertRaisesRegex(CodePerceptionError, "evidence, never authority"):
            CodeGraph("1.0.0", self.source, (self.file,), (self.symbol,), (), authority_effect=True).validate()

    def test_edges_require_exactly_resolved_or_unresolved_source_target(self):
        self._call_edge(resolved=False)
        evidence = "blob:x:L1:C0-L1:C1"
        edge_id = stable_digest("edge", "CALLS", self.node_id, self.node_id, evidence)
        with self.assertRaisesRegex(CodePerceptionError, "exactly one"):
            CodeEdge(edge_id, "CALLS", self.node_id, self.node_id, "dynamic", evidence).validate()

    def test_calls_target_node_is_static_evidence_not_runtime_proof(self):
        edge = self._call_edge(resolved=True)
        self.assertEqual(edge.semantic_class, "STATIC_CALL_EVIDENCE")
        self.assertEqual(edge.runtime_target_state, "UNRESOLVED")
        payload = edge.logical_payload()
        self.assertEqual(payload["target_node_id"], self.node_id)
        self.assertEqual(payload["semantic_class"], "STATIC_CALL_EVIDENCE")
        self.assertEqual(payload["runtime_target_state"], "UNRESOLVED")

    def test_non_call_edges_are_source_relations_with_no_runtime_target_semantics(self):
        evidence = "blob:x:module"
        edge = CodeEdge(
            stable_digest("edge", "CONTAINS", self.file_id, self.node_id, evidence),
            "CONTAINS",
            self.file_id,
            self.node_id,
            None,
            evidence,
        ).validate()
        self.assertEqual(edge.semantic_class, "SOURCE_RELATION")
        self.assertEqual(edge.runtime_target_state, "NOT_APPLICABLE")

    def test_graph_serialization_binds_call_semantics_version(self):
        graph = self._graph(self._call_edge())
        payload = graph.logical_payload()
        self.assertEqual(payload["call_semantics_version"], "2.0.0")
        self.assertEqual(payload["edges"][0]["runtime_target_state"], "UNRESOLVED")
        with self.assertRaisesRegex(CodePerceptionError, "call semantics version"):
            CodeGraph(
                "1.0.0",
                self.source,
                (self.file,),
                (self.symbol,),
                (),
                call_semantics_version="1.0.0",
            ).validate()

    def test_runtime_target_requires_separate_exact_proof_class(self):
        edge = self._call_edge(resolved=True)
        graph = self._graph(edge)
        proof = self._runtime_proof(graph, edge).validate(graph)
        self.assertEqual(proof.proof_class, "EXACT_RUNTIME_CALL_TARGET")
        self.assertEqual(proof.code_graph_digest, graph.digest())
        self.assertEqual(edge.runtime_target_state, "UNRESOLVED")

    def test_runtime_proof_fails_closed_on_wrong_edge_source_target_graph_or_class(self):
        edge = self._call_edge(resolved=True)
        graph = self._graph(edge)
        with self.assertRaisesRegex(CodePerceptionError, "proof class"):
            self._runtime_proof(graph, edge, proof_class="STATIC_GUESS").validate(graph)
        with self.assertRaisesRegex(CodePerceptionError, "exactly one CALLS edge"):
            self._runtime_proof(graph, edge, call_edge_id="d" * 64).validate(graph)
        wrong_source = SourceIdentity(self.source.repository, "e" * 40, self.source.source_tree_sha).validate()
        with self.assertRaisesRegex(CodePerceptionError, "source mismatch"):
            self._runtime_proof(graph, edge, source=wrong_source).validate(graph)
        with self.assertRaisesRegex(CodePerceptionError, "graph symbol"):
            self._runtime_proof(graph, edge, target="f" * 64).validate(graph)
        with self.assertRaisesRegex(CodePerceptionError, "graph digest mismatch"):
            self._runtime_proof(graph, edge, graph_digest="9" * 64).validate(graph)

    def test_runtime_proof_requires_bound_observer_and_evidence_digest(self):
        edge = self._call_edge(resolved=True)
        graph = self._graph(edge)
        proof = self._runtime_proof(graph, edge)
        with self.assertRaisesRegex(CodePerceptionError, "observer_id invalid"):
            RuntimeCallTargetProof(
                proof.proof_id,
                proof.repository,
                proof.source_commit_sha,
                proof.source_tree_sha,
                proof.code_graph_digest,
                proof.call_edge_id,
                proof.runtime_target_node_id,
                "",
                proof.evidence_ref,
                proof.evidence_digest,
            ).validate(graph)
        with self.assertRaisesRegex(CodePerceptionError, "evidence_digest must be sha256"):
            RuntimeCallTargetProof(
                proof.proof_id,
                proof.repository,
                proof.source_commit_sha,
                proof.source_tree_sha,
                proof.code_graph_digest,
                proof.call_edge_id,
                proof.runtime_target_node_id,
                proof.observer_id,
                proof.evidence_ref,
                "bad",
            ).validate(graph)

    def test_graph_rejects_dangling_resolved_edge(self):
        evidence = "blob:x:L1:C0-L1:C1"
        target = "d" * 64
        edge = CodeEdge(
            stable_digest("edge", "CALLS", self.node_id, target, evidence),
            "CALLS",
            self.node_id,
            target,
            None,
            evidence,
        ).validate()
        with self.assertRaisesRegex(CodePerceptionError, "dangling edge target"):
            CodeGraph("1.0.0", self.source, (self.file,), (self.symbol,), (edge,)).validate()

    def test_canonical_graph_bytes_ignore_dict_insertion_concerns(self):
        graph = self._graph()
        self.assertEqual(graph.canonical_bytes(), graph.canonical_bytes())
        self.assertEqual(len(graph.digest()), 64)


if __name__ == "__main__":
    unittest.main()
