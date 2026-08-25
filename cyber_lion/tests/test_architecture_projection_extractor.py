import unittest
from pathlib import Path
from cyber_lion.architecture_projection.extractor import ArchitectureProjectionExtractor, available_projection_names

CANONICAL_TREE = "4388748d063f940c077c4233e535acbc9a3b04a4"


def fixture_sources():
    return {
        "cyber_lion/contracts/builder_entry_permit.py": "class BuilderEntryPermit: pass\n",
        "cyber_lion/contracts/builder_invocation_permit.py": "class BuilderInvocationPermit: pass\n",
        "cyber_lion/contracts/builder_invocation_consumption.py": "class BuilderInvocationConsumptionPermit: pass\n",
        "cyber_lion/contracts/builder_start_admission.py": "class BuilderStartAdmission: pass\nrepository_ref_mutation='DENY'\n",
        "cyber_lion/enterprise/builder_process_launch.py": "class BuilderProcessLaunchBoundary: pass\n",
        "cyber_lion/contracts/builder_process_launch.py": "class BuilderProcessLaunchRequest: pass\nHELD_STATE='HELD_NOT_EXECUTING_BUILDER'\nSTARTED_STATE='STARTED_OBSERVED'\nEFFECT_CLASS='BUILDER_PROCESS_START'\n",
        "cyber_lion/enterprise/persistent_authority_state.py": "class SQLiteAuthorityStateStore: pass\nbuilder_process_launch_intent='x'\nbuilder_process_held_materialization='x'\nbuilder_process_launch_receipt='x'\n",
        "cyber_lion/enterprise/swarm_governor.py": "class SwarmGovernorLeaseStore: pass\n",
        "cyber_lion/contracts/swarm_governance.py": "class SwarmFormation: pass\nclass RoleAssignment: pass\nROLES={'VERIFIER'}\n",
        "cyber_lion/enterprise/evolutionary_epoch.py": "class EvolutionaryEpochEngine: pass\n_EVENT_MAP={}\n_EPOCH_FORWARD={}\nNEXT_EPOCH_CANDIDATE_READY='NEXT_EPOCH_CANDIDATE_READY'\n",
        "cyber_lion/startup_agent/orchestrator.py": "class AIDrivenStartupAgent:\n def plan(self): pass\n def build_local(self): pass\n @staticmethod\n def apply_outcome(): pass\n",
        "cyber_lion/contracts/repository_mutation.py": "class DetachedRepositoryCandidate: pass\n",
        "cyber_lion/enterprise/repository_mutation_pep.py": "class RepositoryMutationPEP: pass\n",
        "cyber_lion/enterprise/repository_mutation_state.py": "class RepositoryAttachJournal: pass\n",
        "cyber_lion/contracts/events.py": "class EventEnvelope: pass\nEVENT_TYPES={'GateRequested','GateApplied','ActionExecuted'}\n",
        "cyber_lion/enterprise/conformance.py": "class ReadOnlyProviderSnapshot: pass\n",
        "cyber_lion/enterprise/policy_gate.py": "_CONTAINS={'local_write': {'read','local_write'}}\n",
    }


class ArchitectureProjectionExtractorTests(unittest.TestCase):
    def test_same_input_same_projection_and_order_independent(self):
        extractor = ArchitectureProjectionExtractor(source_tree_sha="b" * 40)
        first = extractor.extract_python({"b.py": "import os\ndef z(): pass\n", "a.py": "class A: pass\n"})
        second = extractor.extract_python({"a.py": "class A: pass\n", "b.py": "import os\ndef z(): pass\n"})
        self.assertEqual(first, second)
        self.assertEqual(first.source_digest(), second.source_digest())

    def test_path_punctuation_does_not_collide(self):
        extractor = ArchitectureProjectionExtractor(source_tree_sha="b" * 40)
        model = extractor.extract_python({"a-b.py": "class A: pass\n", "a_b.py": "class A: pass\n"})
        module_nodes = [n for n in model.nodes if n.kind == "module"]
        self.assertEqual(len(module_nodes), 2)
        self.assertEqual(len({n.node_id for n in module_nodes}), 2)

    def test_direct_local_calls_static_but_attribute_dispatch_not_promoted(self):
        extractor = ArchitectureProjectionExtractor(source_tree_sha="b" * 40)
        model = extractor.extract_python({"a.py": "def b(): pass\ndef a(x):\n b()\n x.b()\n"})
        static_edges = [e for e in model.edges if e.relation == "CALLS_STATIC"]
        self.assertEqual(len(static_edges), 1)
        self.assertTrue(all(not e.runtime_proof for e in static_edges))

    def test_calls_static_does_not_cross_nested_function_scope(self):
        extractor = ArchitectureProjectionExtractor(source_tree_sha="b" * 40)
        model = extractor.extract_python({"a.py": "def target(): pass\ndef outer():\n def nested():\n  target()\n"})
        outer = next(n for n in model.nodes if n.label == "outer")
        target = next(n for n in model.nodes if n.label == "target")
        self.assertFalse(any(e.source == outer.node_id and e.target == target.node_id and e.relation == "CALLS_STATIC" for e in model.edges))

    def test_calls_static_does_not_cross_lambda_or_nested_class_scope(self):
        extractor = ArchitectureProjectionExtractor(source_tree_sha="b" * 40)
        text = "def target(): pass\ndef outer():\n f=lambda: target()\n class Inner:\n  def method(self): target()\n"
        model = extractor.extract_python({"a.py": text})
        outer = next(n for n in model.nodes if n.label == "outer")
        target = next(n for n in model.nodes if n.label == "target")
        self.assertFalse(any(e.source == outer.node_id and e.target == target.node_id and e.relation == "CALLS_STATIC" for e in model.edges))

    def test_required_projection_set_and_r17_r22_chain(self):
        self.assertEqual(len(available_projection_names()), 10)
        extractor = ArchitectureProjectionExtractor(source_tree_sha="c" * 40, source_files=fixture_sources())
        model = extractor.named_projection("authority-and-effect-chain-R17-R22")
        labels = [n.label for n in model.nodes]
        for label in ("BuilderEntryPermit", "BuilderInvocationPermit", "BuilderInvocationConsumptionPermit", "BuilderStartAdmission", "BuilderProcessLaunchBoundary", "BuilderProcessCompletionObservation"):
            self.assertIn(label, labels)
        frontier = next(n for n in model.nodes if n.label == "BuilderProcessCompletionObservation")
        self.assertEqual(frontier.fact_class, "DECLARED_NEXT_FRONTIER")
        self.assertEqual(frontier.authority_semantics, "NONE")

    def test_every_named_projection_is_source_bound_in_unit_fixture(self):
        extractor = ArchitectureProjectionExtractor(source_tree_sha="d" * 40, source_files=fixture_sources())
        for name in available_projection_names():
            model = extractor.named_projection(name)
            self.assertTrue(model.nodes)
            for node in model.nodes:
                self.assertTrue(node.source_path)
                if node.fact_class == "CANONICAL_FACT":
                    self.assertEqual(len(node.source_digest), 64)

    def test_all_ten_named_projections_build_from_real_checkout(self):
        repo_root = Path(__file__).resolve().parents[2]
        extractor = ArchitectureProjectionExtractor(source_tree_sha=CANONICAL_TREE, source_root=repo_root)
        for name in available_projection_names():
            model = extractor.named_projection(name)
            self.assertTrue(model.nodes, name)
            for node in model.nodes:
                self.assertTrue(node.source_path, name)
                if node.fact_class == "CANONICAL_FACT":
                    path = repo_root / node.source_path
                    self.assertTrue(path.is_file(), f"{name}: {node.source_path}")
                    self.assertEqual(len(node.source_digest), 64)

    def test_nonexistent_source_and_required_token_fail_closed(self):
        extractor = ArchitectureProjectionExtractor(source_tree_sha="d" * 40, source_files={"real.py": "class Real: pass\n"})
        with self.assertRaises(ValueError):
            extractor._fact(path="missing.py", label="X", kind="component", token="X")
        with self.assertRaises(ValueError):
            extractor._fact(path="real.py", label="X", kind="component", token="Missing")

    def test_relevant_source_change_changes_projection_content_and_digest(self):
        sources = fixture_sources()
        first = ArchitectureProjectionExtractor(source_tree_sha="d" * 40, source_files=sources).named_projection("capability-map")
        changed = dict(sources)
        changed["cyber_lion/enterprise/conformance.py"] += "EXTRA_READ_CAPABILITY='X'\n"
        second = ArchitectureProjectionExtractor(source_tree_sha="d" * 40, source_files=changed).named_projection("capability-map")
        self.assertNotEqual(first, second)
        self.assertNotEqual(first.source_digest(), second.source_digest())

    def test_unrelated_source_change_leaves_projection_semantics_stable(self):
        sources = fixture_sources()
        first = ArchitectureProjectionExtractor(source_tree_sha="d" * 40, source_files=sources).named_projection("capability-map")
        changed = dict(sources)
        changed["unrelated.py"] = "x=1\n"
        second = ArchitectureProjectionExtractor(source_tree_sha="d" * 40, source_files=changed).named_projection("capability-map")
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
