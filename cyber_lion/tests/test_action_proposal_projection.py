from __future__ import annotations

import ast
from pathlib import Path
import unittest

from cyber_lion.contracts.action_ir import CanonicalActionIR
from cyber_lion.contracts.action_proposal_projection import (
    ACTION_PROPOSAL_FIELDS,
    BLOCKED_IMPLICIT_MAPPINGS,
    DIRECT_BINDINGS,
    UNRESOLVED_FIELDS,
    ActionProposalProjectionError,
    project_lair_to_action_proposal_static,
)
from cyber_lion.enterprise.complete_mediation import EffectSurfaceScanner


class ActionProposalStaticProjectionTests(unittest.TestCase):
    def minimal(self):
        return {
            "schema_version": "1.0.0",
            "action_id": "r19m.observe.1",
            "kind": "repository.observe",
            "intent_ref": "intent:r19m",
            "mission_ref": "mission:r19m",
            "autonomy_ref": "autonomy:lion",
            "bean_ref": "bean:r19m",
            "target": {"host": "github", "environment": "candidate", "runtime": "none"},
            "authority_request": {"domain": "repository", "capability": "observe", "grant_ref": None},
            "boundary": {
                "shell": False, "network": "DENY", "filesystem_read": [], "filesystem_write": [],
                "process_children": [], "timeout_ms": 1000, "max_processes": 1,
                "memory_limit_bytes": 1048576,
            },
            "preconditions": ["baseline-exact"],
            "expected_effects": [],
            "forbidden_effects": ["execution", "authority-minting"],
            "observation": {"observer_class": "deterministic_independent", "required_events": ["ir-validated"]},
            "reconciliation": {"mode": "EXACT", "receipt": "REQUIRED"},
        }

    def test_only_payload_digest_is_directly_projectable_to_actionproposal(self):
        ir = CanonicalActionIR.from_mapping(self.minimal())
        projection = project_lair_to_action_proposal_static(ir)
        self.assertEqual(projection.direct_bindings, ("payload_digest",))
        self.assertEqual(projection.action_proposal_payload_digest, ir.payload_digest)
        self.assertEqual(set(projection.unresolved_action_proposal_fields), set(ACTION_PROPOSAL_FIELDS) - {"payload_digest"})
        self.assertEqual(projection.unresolved_action_proposal_fields, UNRESOLVED_FIELDS)

    def test_known_non_isomorphic_mappings_are_explicitly_blocked(self):
        projection = project_lair_to_action_proposal_static(CanonicalActionIR.from_mapping(self.minimal()))
        self.assertEqual(projection.blocked_implicit_mappings, BLOCKED_IMPLICIT_MAPPINGS)
        self.assertNotIn("requested_authority", projection.direct_bindings)
        self.assertNotIn("action_class", projection.direct_bindings)
        self.assertNotIn("target", projection.direct_bindings)

    def test_projection_preserves_source_facts_without_relabeling_them(self):
        projection = project_lair_to_action_proposal_static(CanonicalActionIR.from_mapping(self.minimal()))
        self.assertEqual(projection.source_mission_ref, "mission:r19m")
        self.assertEqual(projection.source_authority_domain, "repository")
        self.assertEqual(projection.source_capability, "observe")
        self.assertEqual((projection.source_target_host, projection.source_target_environment, projection.source_target_runtime), ("github", "candidate", "none"))
        self.assertEqual(projection.source_required_events, ("ir-validated",))

    def test_projection_is_deterministic_and_non_effectful(self):
        ir = CanonicalActionIR.from_mapping(self.minimal())
        a = project_lair_to_action_proposal_static(ir)
        b = project_lair_to_action_proposal_static(ir)
        self.assertEqual(a, b)
        self.assertEqual(a.digest(), b.digest())
        self.assertEqual((a.authority_effect, a.execution_effect, a.transport_effect, a.policy_effect), ("NONE", "NONE", "NONE", "NONE"))

    def test_projection_module_does_not_construct_actionproposal_or_add_surface(self):
        path = Path("cyber_lion/contracts/action_proposal_projection.py")
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        calls = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                fn = node.func
                name = fn.id if isinstance(fn, ast.Name) else (fn.attr if isinstance(fn, ast.Attribute) else "")
                if name == "ActionProposal":
                    calls.append(node.lineno)
        self.assertEqual(calls, [])
        inv = EffectSurfaceScanner().scan(
            repository="DonkeyJJLove/ai_platform", revision="0" * 40, tree_digest="0" * 40,
            sources={str(path): source},
        )
        self.assertEqual(inv.surfaces, ())

    def test_exact_canonical_ir_type_is_required(self):
        with self.assertRaisesRegex(ActionProposalProjectionError, "exact CanonicalActionIR"):
            project_lair_to_action_proposal_static(self.minimal())  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
