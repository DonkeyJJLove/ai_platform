from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import subprocess
import unittest

from cyber_lion.architecture_projection.architecture_compiler import (
    ArchitectureCompiler,
    ArchitectureCompilerError,
    CandidateDesign,
    CandidateLayerBinding,
)
from cyber_lion.architecture_projection.flows import canonical_flows
from cyber_lion.architecture_projection.evolution_fitness import (
    EvolutionFitnessCandidate,
    EvolutionFitnessVector,
    EvolutionGateState,
)
from cyber_lion.architecture_projection.full_architecture import build_full_architecture_model
from cyber_lion.contracts.formalization_manifest_types import BaselineIdentity
from cyber_lion.contracts.formalization_registry import FormalizationRegistry
from cyber_lion.tests.architecture_projection_candidate import staged_sources, staged_tree


ROOT = Path(__file__).resolve().parents[2]
V15 = ROOT / "LION/architecture/v1_5"


def git(*args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(ROOT), *args],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    ).stdout.strip()


def registry() -> FormalizationRegistry:
    return FormalizationRegistry.from_dict(
        json.loads((V15 / "FORMALIZATION_REGISTRY_FEDERATION_R1.json").read_text(encoding="utf-8"))
    )


def owners() -> dict[str, str]:
    raw = json.loads((V15 / "semantic_owners.json").read_text(encoding="utf-8"))
    return {row["concept"]: row["primary"] for row in raw["owners"]}


def candidate(head: str, tree: str) -> CandidateDesign:
    return CandidateDesign(
        candidate_id="architecture-studio-compiler-r1",
        baseline=BaselineIdentity("DonkeyJJLove/ai_platform", "master", head, tree),
        target_component="architecture studio compiler",
        motivation="compile a source-bound design proposal through the existing architecture formalization spine",
        evidence_refs=("source:architecture_projection", "source:formalization_kernel"),
        expected_outcome="deterministic non-effectful EvolutionDelta and formalization impact preview",
        falsification_conditions=(
            "canonical flow substitution is rejected",
            "stale baseline is rejected",
            "unknown semantic owner is rejected",
        ),
        candidate_scope=(
            "cyber_lion/architecture_projection/architecture_compiler.py",
            "cyber_lion/architecture_projection/architecture_studio.py",
        ),
        dependency_ids=("architecture", "architecture_knowledge", "formalization"),
        risk_class="GREEN",
        change_class="ARCHITECTURE_CONCEPT",
        affected_concepts=("architecture", "formalization"),
        layer_bindings=(
            CandidateLayerBinding("architecture", ("ARCHITECTURE_PROJECTION",)),
            CandidateLayerBinding("formalization", ("ARCHITECTURE_PROJECTION",)),
        ),
        tests_required=("test:architecture-compiler",),
        evals_required=("eval:architecture-compiler",),
        falsifiers=("falsifier:no-authority-bypass",),
    ).validate()


class ArchitectureCompilerTests(unittest.TestCase):
    def setUp(self):
        self.head = git("rev-parse", "HEAD")
        self.tree = staged_tree(ROOT)
        self.architecture = build_full_architecture_model(
            source_tree_sha=self.tree,
            source_files=staged_sources(ROOT),
        )
        self.registry = registry()
        self.owners = owners()
        self.compiler = ArchitectureCompiler()

    def test_same_inputs_produce_same_evolution_delta_and_required_set(self):
        left = self.compiler.compile(
            candidate=candidate(self.head, self.tree),
            architecture=self.architecture,
            registry=self.registry,
            semantic_owners=self.owners,
            current_head=self.head,
            current_tree=self.tree,
        )
        right = self.compiler.compile(
            candidate=candidate(self.head, self.tree),
            architecture=self.architecture,
            registry=self.registry,
            semantic_owners=self.owners,
            current_head=self.head,
            current_tree=self.tree,
        )
        self.assertEqual(left.compilation_digest, right.compilation_digest)
        self.assertEqual(left.evolution_delta.delta_digest, right.evolution_delta.delta_digest)
        self.assertEqual(left.required_formalization_set.set_digest, right.required_formalization_set.set_digest)
        self.assertEqual(left.authority_effect, "NONE")
        self.assertEqual(left.execution_effect, "NONE")
        self.assertTrue(left.ends_before_admission)

    def test_compiler_routes_through_existing_required_formalization_set(self):
        result = self.compiler.compile(
            candidate=candidate(self.head, self.tree),
            architecture=self.architecture,
            registry=self.registry,
            semantic_owners=self.owners,
            current_head=self.head,
            current_tree=self.tree,
        )
        ids = {item.artifact_id for item in result.required_formalization_set.items}
        self.assertIn("architecture-projection", ids)
        self.assertIn("currentness-carriers", ids)
        self.assertEqual(result.formalization_manifest.authority_effect, "NONE")
        self.assertEqual(result.formalization_manifest.execution_effect, "NONE")

    def test_unknown_owner_fails_closed(self):
        incomplete = dict(self.owners)
        incomplete.pop("formalization", None)
        with self.assertRaisesRegex(ArchitectureCompilerError, "unknown semantic owner"):
            self.compiler.compile(
                candidate=candidate(self.head, self.tree),
                architecture=self.architecture,
                registry=self.registry,
                semantic_owners=incomplete,
                current_head=self.head,
                current_tree=self.tree,
            )

    def test_stale_currentness_fails_closed(self):
        with self.assertRaisesRegex(ArchitectureCompilerError, "stale or substituted"):
            self.compiler.compile(
                candidate=candidate(self.head, self.tree),
                architecture=self.architecture,
                registry=self.registry,
                semantic_owners=self.owners,
                current_head="f" * 40,
                current_tree=self.tree,
            )

    def test_canonical_flow_spine_cannot_be_substituted(self):
        broken = type(self.architecture)(
            source_tree_sha=self.architecture.source_tree_sha,
            elements=self.architecture.elements,
            flows=tuple(reversed(canonical_flows())),
            gaps=self.architecture.gaps,
            layout=self.architecture.layout,
        )
        with self.assertRaisesRegex(ArchitectureCompilerError, "FLOW-01..FLOW-10"):
            self.compiler.compile(
                candidate=candidate(self.head, self.tree),
                architecture=broken,
                registry=self.registry,
                semantic_owners=self.owners,
                current_head=self.head,
                current_tree=self.tree,
            )

    def test_required_evolution_eval_cases_are_materialized(self):
        cases = json.loads((ROOT / "LION/evals/evolution/evolution_cases.yaml").read_text(encoding="utf-8"))["cases"]
        ids = {case["id"] for case in cases}
        self.assertTrue({
            "ARCHITECTURE_COMPILER_DETERMINISTIC",
            "ARCHITECTURE_COMPILER_NO_AUTHORITY_BYPASS",
        } <= ids)

    def test_candidate_contract_has_no_history_version_lifecycle_or_currentness_authority(self):
        fields = set(CandidateDesign.__dataclass_fields__)
        self.assertFalse(fields.intersection({"history_relation", "version", "lifecycle", "currentness"}))
        ArchitectureCompiler.assert_no_effect_surface()

    def test_fitness_selection_feeds_one_design_into_existing_compiler(self):
        low = replace(
            candidate(self.head, self.tree),
            candidate_id="a-local-maintenance",
            target_component="local maintenance candidate",
            motivation="close one bounded local maintenance gap",
        ).validate()
        high = replace(
            candidate(self.head, self.tree),
            candidate_id="b-application-factory-loop",
            target_component="application factory artifact loop",
            motivation="close reusable SaaS LOCAL material artifact production and verification",
        ).validate()

        gate = EvolutionGateState(
            source_current=True,
            semantic_owner_bound=True,
            dependency_closure=True,
            authority_nonexpanding=True,
            effect_state_reconciled=True,
            collision_free=True,
            bounded_scope=True,
            evidence_bound=True,
            owner_resolved=True,
        ).validate()
        low_fitness = EvolutionFitnessCandidate(
            candidate_id=low.candidate_id,
            vector=EvolutionFitnessVector(
                capability_gain=400,
                federation_leverage=200,
                functional_value=500,
                generativity_gain=100,
                integration_closure=300,
                knowledge_feedback=200,
                recovery_strength=300,
                reuse_leverage=400,
                verification_strength=400,
                authority_risk=100,
                blast_radius=100,
                change_surface=200,
                currentness_debt=100,
                implementation_cost=250,
                operational_cost=150,
            ).validate(),
            gates=gate,
            evidence_refs=("evidence:maintenance",),
            repository_scope=("DonkeyJJLove/ai_platform",),
            task_family_count=1,
        ).validate()
        high_fitness = EvolutionFitnessCandidate(
            candidate_id=high.candidate_id,
            vector=EvolutionFitnessVector(
                capability_gain=850,
                federation_leverage=800,
                functional_value=850,
                generativity_gain=900,
                integration_closure=900,
                knowledge_feedback=750,
                recovery_strength=700,
                reuse_leverage=750,
                verification_strength=800,
                authority_risk=150,
                blast_radius=180,
                change_surface=350,
                currentness_debt=120,
                implementation_cost=500,
                operational_cost=300,
            ).validate(),
            gates=gate,
            evidence_refs=("evidence:artifact-loop",),
            repository_scope=("DonkeyJJLove/ai_platform",),
            task_family_count=2,
        ).validate()

        result = self.compiler.compile_selected(
            candidates=(low, high),
            fitness_candidates=(low_fitness, high_fitness),
            architecture=self.architecture,
            registry=self.registry,
            semantic_owners=self.owners,
            current_head=self.head,
            current_tree=self.tree,
        )
        self.assertEqual(result.selection.selected_candidate_id, high.candidate_id)
        self.assertEqual(result.compilation.candidate_digest, high.digest())
        self.assertTrue(result.result_digest)
        self.assertEqual(result.authority_effect, "NONE")
        self.assertEqual(result.execution_effect, "NONE")

    def test_fitness_selection_rejects_design_identity_mismatch(self):
        design = replace(candidate(self.head, self.tree), candidate_id="a-design").validate()
        gate = EvolutionGateState(
            source_current=True,
            semantic_owner_bound=True,
            dependency_closure=True,
            authority_nonexpanding=True,
            effect_state_reconciled=True,
            collision_free=True,
            bounded_scope=True,
            evidence_bound=True,
            owner_resolved=True,
        ).validate()
        wrong = EvolutionFitnessCandidate(
            candidate_id="b-other",
            vector=EvolutionFitnessVector(
                capability_gain=500,
                federation_leverage=500,
                functional_value=500,
                generativity_gain=500,
                integration_closure=500,
                knowledge_feedback=500,
                recovery_strength=500,
                reuse_leverage=500,
                verification_strength=500,
                authority_risk=100,
                blast_radius=100,
                change_surface=100,
                currentness_debt=100,
                implementation_cost=100,
                operational_cost=100,
            ).validate(),
            gates=gate,
            evidence_refs=("evidence:mismatch",),
            repository_scope=("DonkeyJJLove/ai_platform",),
            task_family_count=1,
        ).validate()
        with self.assertRaisesRegex(ArchitectureCompilerError, "identity mismatch"):
            self.compiler.compile_selected(
                candidates=(design,),
                fitness_candidates=(wrong,),
                architecture=self.architecture,
                registry=self.registry,
                semantic_owners=self.owners,
                current_head=self.head,
                current_tree=self.tree,
            )


if __name__ == "__main__":
    unittest.main()
