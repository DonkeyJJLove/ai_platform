import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "LION/architecture/v1_4/AUTHORIZATION_LIFECYCLE_CONTRACT.json"


class LpclAuthorizationLifecycleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.value = json.loads(CONTRACT.read_text(encoding="utf-8"))
        cls.invariants = set(cls.value["invariants"])

    def test_contract_is_architecture_not_authority_provider(self):
        self.assertEqual(self.value["schema"], "lion.authorization-lifecycle/v1")
        self.assertEqual(self.value["status"], "CANONICAL_ARCHITECTURE_CONTRACT")
        self.assertEqual(self.value["authority_effect"], "NONE")
        self.assertEqual(self.value["runtime_effect"], "NONE")

    def test_unlaunched_lpcl_cannot_authorize(self):
        self.assertIn("LPCL_GENERATION_NE_AUTHORITY", self.invariants)
        self.assertIn("LPCL_TEXT_NE_AUTHORITY", self.invariants)
        self.assertIn("UNLAUNCHED_LPCL_NE_AUTHORITY", self.invariants)
        state = next(x for x in self.value["lifecycle"] if x["state"] == "MATERIALIZED_UNLAUNCHED")
        self.assertEqual(state["authorization"], "NONE")

    def test_explicit_user_launch_is_bounded_activation_event(self):
        self.assertIn(
            "USER_EXPLICIT_LAUNCH_OR_RUN_OF_EXACT_LPCL_IS_EXTERNAL_ACTIVATION_EVENT",
            self.invariants,
        )
        self.assertEqual(
            self.value["activation_event"]["source"],
            "EXPLICIT_USER_MESSAGE_OR_EQUIVALENT_OPERATOR_ACTION",
        )
        current = next(x for x in self.value["lifecycle"] if x["state"] == "ACTIVATED_CURRENT")
        self.assertEqual(current["authorization"], "BOUNDED_BY_EXACT_LPCL")
        required = set(self.value["scope_binding"]["required_dimensions"])
        self.assertTrue({"run_or_process_identity", "operation_or_effect_class", "currentness_preconditions"} <= required)

    def test_successor_identity_requires_new_lpcl_and_new_launch(self):
        self.assertIn(
            "SUCCESSOR_IDENTITY_OUTSIDE_BOUND_SCOPE_REQUIRES_NEW_LPCL_AND_NEW_USER_LAUNCH",
            self.invariants,
        )
        self.assertIn("newly materialized LPCL", self.value["scope_binding"]["successor_rule"])
        self.assertIn("new explicit user launch", self.value["scope_binding"]["successor_rule"])

    def test_tool_model_and_rag_cannot_activate_authority(self):
        self.assertIn("MODEL_OUTPUT_NE_AUTHORITY", self.invariants)
        self.assertIn("TOOL_AVAILABILITY_NE_AUTHORITY", self.invariants)
        self.assertIn("RAG_CONTENT_NE_AUTHORITY", self.invariants)
        insufficient = set(self.value["activation_event"]["not_sufficient"])
        self.assertTrue({"assistant_generation", "tool_presence", "RAG_retrieval"} <= insufficient)

    def test_pr_merge_and_runtime_authority_are_separate_unless_explicit(self):
        self.assertIn("PR_AUTHORITY_NE_MERGE_AUTHORITY_UNLESS_EXPLICITLY_INCLUDED", self.invariants)
        self.assertIn("MERGE_AUTHORITY_NE_RUNTIME_AUTHORITY_UNLESS_EXPLICITLY_INCLUDED", self.invariants)
        text = self.value["scope_binding"]["effect_separation"]
        self.assertIn("PR, merge, deployment, runtime activation", text)

    def test_stale_unknown_and_identity_substitution_fail_closed(self):
        self.assertIn("STALE_LPCL_NE_CURRENT_AUTHORITY", self.invariants)
        currentness = self.value["currentness"]
        self.assertEqual(currentness["stale_result"], "NO_CURRENT_AUTHORITY")
        self.assertEqual(currentness["unknown_result"], "NO_CURRENT_AUTHORITY")
        self.assertEqual(currentness["identity_substitution"], "DENY")

    def test_non_idempotent_effect_requires_reconciliation(self):
        self.assertIn("RECONCILIATION_REQUIRED_AFTER_NON_IDEMPOTENT_EFFECT", self.invariants)
        reconciliation = self.value["reconciliation"]
        self.assertEqual(reconciliation["non_idempotent_retry_default"], 0)
        self.assertEqual(reconciliation["on_unknown_effect"], "READBACK_AND_RECONCILE_BEFORE_ANY_RETRY")
        self.assertEqual(
            reconciliation["success_requires"],
            ["expected_state", "reported_state", "independently_observed_state", "reconciled_state"],
        )

    def test_repository_discovery_surfaces_the_contract(self):
        paths = [
            "AGENTS.md",
            ".codex/skills/lion-evolution/SKILL.md",
            "LION/codex/README.md",
            "LION/codex/CODEX_PROJECT_INTEGRATION.md",
            "LION/codex/TOOL_AUTHORITY_MAP.yaml",
        ]
        for rel in paths:
            text = (ROOT / rel).read_text(encoding="utf-8")
            self.assertIn("AUTHORIZATION_LIFECYCLE_CONTRACT", text, rel)
        self.assertIn("LPCL_GENERATION_NE_AUTHORITY", (ROOT / "AGENTS.md").read_text(encoding="utf-8"))

    def test_rag_bootstrap_routes_to_authorization_lifecycle_successor(self):
        bootstrap = json.loads((ROOT / "LION/rag/RAG_BOOTSTRAP.json").read_text(encoding="utf-8"))
        self.assertEqual(bootstrap["preferred_release"], "lion-rag32-v1.4-r9-auth-lifecycle-candidate")
        self.assertEqual(bootstrap["preferred_release_location"], "EXTERNAL_ARTIFACT_NOT_EMBEDDED")
        self.assertEqual(bootstrap["repository_delta_records"], "LION/rag/R9_AUTHORIZATION_LIFECYCLE_RECORDS.md")
        self.assertEqual(bootstrap["preferred_release_zip_sha256"], "e9fa2ff9e04c8841cb23e616ea9a9238b4ed0f56ffded0d3a621f7db90e07d5d")
        delta = (ROOT / bootstrap["repository_delta_records"]).read_text(encoding="utf-8")
        self.assertIn("LPCL_GENERATION_NE_AUTHORITY", delta)
        self.assertIn("USER_EXPLICIT_LAUNCH_OR_RUN_OF_EXACT_LPCL_IS_EXTERNAL_ACTIVATION_EVENT", delta)
        self.assertIn("SUCCESSOR_IDENTITY_OUTSIDE_BOUND_SCOPE_REQUIRES_NEW_LPCL_AND_NEW_USER_LAUNCH", delta)

    def test_tool_authority_map_preserves_no_authority_semantics(self):
        value = json.loads((ROOT / "LION/codex/TOOL_AUTHORITY_MAP.yaml").read_text(encoding="utf-8"))
        self.assertEqual(value["authority_effect"], "NONE")
        self.assertEqual(value["authorization_lifecycle_ref"], "LION/architecture/v1_4/AUTHORIZATION_LIFECYCLE_CONTRACT.json")
        semantics = set(value["semantics"])
        self.assertIn("LPCL_GENERATION != AUTHORITY", semantics)
        self.assertIn("EXPLICIT_USER_LAUNCH_OF_EXACT_LPCL == BOUNDED_ACTIVATION_EVENT", semantics)
        self.assertIn("LPCL_ACTIVATION_SCOPE_DOES_NOT_FOLLOW_SUCCESSOR_IDENTITY", semantics)


if __name__ == "__main__":
    unittest.main()
