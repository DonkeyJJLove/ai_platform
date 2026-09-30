from dataclasses import replace
import unittest

from cyber_lion.architecture_projection.architecture_knowledge import (
    ArchitectureDocumentEdge,
    ArchitectureDocumentRecord,
    ArchitectureKnowledgeError,
    FederatedArchitectureKnowledge,
    classify_document_currentness,
)

D="d"*64
A="a"*40
B="b"*40


def doc(artifact_id="repo-manifest",repository="DonkeyJJLove/ai_platform",path="cyber-lion.repository.json"):
    return ArchitectureDocumentRecord(
        artifact_id=artifact_id,
        repository=repository,
        path=path,
        artifact_class="REPOSITORY_MANIFEST",
        semantic_owner_concept="repository_roles",
        currentness="CURRENT",
        generator=None,
        source_refs=("git:HEAD",),
        consumers=("reasoner",),
        invalidated_by=("SOURCE_CHANGE",),
        validation_refs=("manifest schema",),
        influence_class="EVOLUTION_CONSTRAINT",
    ).validate()


class ArchitectureKnowledgeTests(unittest.TestCase):
    def test_sealed_graph_is_deterministic_and_non_authoritative(self):
        left=doc()
        right=doc("global-registry","DonkeyJJLove/ai_platform","cyber_lion/registry/repositories.json")
        edge=ArchitectureDocumentEdge(left.artifact_id,right.artifact_id,"PROJECTS","registry projection").validate()
        value=FederatedArchitectureKnowledge(D,(left,right),(edge,)).sealed()
        self.assertEqual(value.validate(),value)
        self.assertEqual(value.authority_effect,"NONE")
        self.assertEqual(value.knowledge_digest,value.compute_digest())

    def test_unknown_edge_target_is_denied(self):
        left=doc()
        edge=ArchitectureDocumentEdge(left.artifact_id,"missing","REFERENCES","bad").validate()
        with self.assertRaisesRegex(ArchitectureKnowledgeError,"unknown artifact"):
            FederatedArchitectureKnowledge(D,(left,),(edge,)).sealed()

    def test_duplicate_document_id_is_denied(self):
        left=doc()
        with self.assertRaisesRegex(ArchitectureKnowledgeError,"duplicate"):
            FederatedArchitectureKnowledge(D,(left,left),()).sealed()

    def test_target_only_does_not_promote_to_current(self):
        self.assertEqual(
            classify_document_currentness(
                observed_head=A,observed_tree=B,current_head=A,current_tree=B,target_only=True
            ),
            "TARGET_ONLY",
        )

    def test_exact_identity_is_required_for_current(self):
        self.assertEqual(
            classify_document_currentness(observed_head=A,observed_tree=B,current_head=A,current_tree=B),
            "CURRENT",
        )
        self.assertEqual(
            classify_document_currentness(observed_head=A,observed_tree=B,current_head="c"*40,current_tree=B),
            "STALE",
        )


if __name__=="__main__":
    unittest.main()
