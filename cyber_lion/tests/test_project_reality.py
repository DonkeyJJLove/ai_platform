from __future__ import annotations

from dataclasses import replace
from hashlib import sha256
import unittest

from cyber_lion.architecture_projection.evolution_fitness import (
    HARD_GATE_FIELDS,
    EvolutionFitnessCandidate,
    EvolutionFitnessVector,
)
from cyber_lion.architecture_projection.project_reality import (
    CandidateRealityBinding,
    GateObservation,
    PressureObservation,
    ProjectRealityAdapter,
    ProjectRealityError,
    build_project_claim_projection,
    build_project_reality_snapshot,
    system_snapshot_from_control_plane_observations,
)
from cyber_lion.contracts.enterprise_graph import (
    EnterpriseGraphProjection,
    GraphEdge,
    GraphNode,
    canonical_json,
)
from cyber_lion.contracts.evolutionary_state import SystemSnapshot, WorldSnapshot
from cyber_lion.contracts.semantic_relevance import EvidenceInstance, SemanticAtom


H40 = "a" * 40
T40 = "b" * 40
H64 = "c" * 64
K64 = "d" * 64
NOW = "2026-10-07T18:00:00Z"
FRESH = "2026-10-07T19:00:00Z"


def graph(*, include_authority: bool = False) -> EnterpriseGraphProjection:
    nodes = (
        GraphNode(
            "claim:artifact-loop",
            "ARTIFACT",
            "1",
            {"claim": "artifact loop is the next generative closure"},
            ("evidence:roadmap",),
        ).validate(),
        GraphNode(
            "claim:source-current",
            "EVIDENCE",
            "1",
            {"claim": "source identity is exact"},
            ("evidence:git",),
        ).validate(),
    )
    edges = [
        GraphEdge(
            "edge:source-supports-loop",
            "DATA_PROVENANCE",
            "SUPPORTS",
            "claim:source-current",
            "claim:artifact-loop",
            ("evidence:git",),
        ).validate()
    ]
    if include_authority:
        edges.append(
            GraphEdge(
                "edge:authority-ref",
                "AUTHORITY_REFERENCE",
                "AUTHORITY_REFERENCED_BY",
                "claim:source-current",
                "claim:artifact-loop",
                ("evidence:authority",),
            ).validate()
        )
    payload = {
        "graph_id": "project-reality",
        "nodes": [
            {
                "node_id": n.node_id,
                "node_type": n.node_type,
                "version": n.version,
                "payload": dict(n.payload),
                "provenance_refs": list(n.provenance_refs),
            }
            for n in nodes
        ],
        "edges": [
            {
                "edge_id": e.edge_id,
                "plane": e.plane,
                "edge_type": e.edge_type,
                "source_id": e.source_id,
                "target_id": e.target_id,
                "provenance_refs": list(e.provenance_refs),
                "causality_evidence_ref": e.causality_evidence_ref,
            }
            for e in edges
        ],
    }
    digest = sha256(canonical_json(payload)).hexdigest()
    return EnterpriseGraphProjection(
        "project-reality",
        1,
        "0" * 64,
        nodes,
        tuple(edges),
        digest,
    ).verify_digest()


def world(*, state: str = "CURRENT") -> WorldSnapshot:
    return WorldSnapshot(
        snapshot_id="world:operator-objective",
        observed_at=NOW,
        captured_at=NOW,
        epistemic_state=state,
        observations=(("operator_goal", "build a governed application factory"),),
        source_refs=("source:operator-goal",),
        evidence_refs=("evidence:operator-goal",),
        freshness_deadline=FRESH if state == "CURRENT" else "",
        limitations=(),
        contradictions=(),
    ).validate()


def system(*, state: str = "CURRENT") -> SystemSnapshot:
    return SystemSnapshot(
        snapshot_id="system:ai-platform",
        observed_at=NOW,
        captured_at=NOW,
        epistemic_state=state,
        repository="DonkeyJJLove/ai_platform",
        revision=H40,
        tree_digest=T40,
        implementation_facts=(
            ("architecture_compiler", "present"),
            ("dynamic_evolution_fitness", "candidate"),
        ),
        test_evidence_refs=("test:project-reality",),
        observation_refs=("observation:git-readback",),
        freshness_deadline=FRESH if state == "CURRENT" else "",
        unknowns=("runtime-provider-binding",) if state == "UNKNOWN" else (),
        contradictions=(),
    ).validate()


def reality(*, state: str = "CURRENT"):
    return build_project_reality_snapshot(
        snapshot_id="project-reality:r1",
        observed_at=NOW,
        epistemic_state=state,
        source_repository="DonkeyJJLove/ai_platform",
        source_head=H40,
        source_tree=T40,
        world=world(state="CURRENT" if state == "CURRENT" else "STALE"),
        systems=(system(state="CURRENT" if state == "CURRENT" else "STALE"),),
        federation_snapshot_ref="federation:snapshot",
        federation_digest=H64,
        architecture_knowledge_ref="architecture-knowledge:v1",
        architecture_knowledge_digest=K64,
        enterprise_graph=graph(),
        currentness_refs=("currentness:git", "currentness:mission-control"),
        evidence_refs=("evidence:git", "evidence:mission-control"),
        unknowns=("runtime:provider-binding",) if state == "UNKNOWN" else (),
        contradictions=("source/runtime conflict",) if state == "CONFLICTED" else (),
    )


def atom() -> SemanticAtom:
    evidence = (
        EvidenceInstance(
            evidence_ref="evidence:git",
            root_ref="root:git",
            content_digest="1" * 64,
            observed_at=NOW,
            currentness="CURRENT",
        ).validate(),
        EvidenceInstance(
            evidence_ref="evidence:runtime",
            root_ref="root:runtime",
            content_digest="2" * 64,
            observed_at=NOW,
            currentness="CURRENT",
        ).validate(),
    )
    return SemanticAtom(
        atom_id="atom:artifact-loop",
        semantic_key="artifact-loop",
        proposition_core="first closed SaaS LOCAL material artifact loop is the next closure",
        relation_signature=("SUPPORTS",),
        scope=("DonkeyJJLove/ai_platform",),
        temporal_state="CURRENT",
        evidence=evidence,
        source_representation_refs=("representation:project-reality",),
    ).sealed()


def gate_observations(candidate_id: str, *, unknown_gate: str | None = None):
    return tuple(
        GateObservation(
            candidate_id=candidate_id,
            gate_name=name,
            state="UNKNOWN" if name == unknown_gate else "PASS",
            evidence_ref=f"evidence:gate:{name}",
            source_digest="3" * 64,
            observed_at=NOW,
        ).validate()
        for name in sorted(name for name, _ in HARD_GATE_FIELDS)
    )


def binding(candidate_id: str, r, *, unknown_gate: str | None = None):
    return CandidateRealityBinding(
        candidate_id=candidate_id,
        project_reality_ref=r.snapshot_id,
        project_reality_digest=r.snapshot_digest,
        gate_observations=gate_observations(candidate_id, unknown_gate=unknown_gate),
        evidence_refs=("evidence:candidate-binding",),
    ).sealed()


def vector() -> EvolutionFitnessVector:
    return EvolutionFitnessVector(
        capability_gain=800,
        federation_leverage=700,
        functional_value=850,
        generativity_gain=900,
        integration_closure=900,
        knowledge_feedback=800,
        recovery_strength=700,
        reuse_leverage=800,
        verification_strength=850,
        authority_risk=150,
        blast_radius=200,
        change_surface=350,
        currentness_debt=200,
        implementation_cost=500,
        operational_cost=300,
    ).validate()


def candidate(candidate_id: str, r) -> EvolutionFitnessCandidate:
    context = ProjectRealityAdapter().build_evolution_context(
        reality=r,
        binding=binding(candidate_id, r),
        pressure_observations=(),
    )
    return EvolutionFitnessCandidate(
        candidate_id=candidate_id,
        vector=vector(),
        gates=context.gates,
        evidence_refs=("evidence:fitness-vector",),
        repository_scope=("DonkeyJJLove/ai_platform",),
        task_family_count=2,
    ).validate()


class ProjectRealityTests(unittest.TestCase):
    def test_existing_control_plane_observation_normalizes_to_current_system_snapshot(self):
        observations = {
            "schema": "lion.control-plane-reconnaissance/v1",
            "mission_id": "mission:artifact-loop",
            "phase_id": "RECON",
            "domains": {
                "panel": {
                    "repo": {
                        "local_head": H40,
                        "local_tree": T40,
                        "github_master": {"head": H40, "tree": T40},
                    },
                    "thread_db": {
                        "integrity": "ok",
                        "identity_digest": "6" * 64,
                    },
                    "saas_projection": {
                        "transport": "CHATGPT_SENTINELX_MCP",
                        "pending_count": 0,
                    },
                },
                "mission_control": {
                    "mission": {
                        "mission_id": "mission:artifact-loop",
                        "state": "REGISTERED",
                        "runtime_state": "NOT_STARTED",
                        "source_head": "7" * 40,
                        "source_tree": "8" * 40,
                    },
                    "process": {"current_phase": None},
                    "db": {"integrity": "ok"},
                },
                "broker": {
                    "pending_count": 0,
                    "responded_count": 3,
                    "receipt_count": 3,
                    "active_binding": {
                        "status": "BOUND",
                        "authority_effect": "NONE",
                    },
                },
            },
            "authority_effect": "NONE",
        }
        snap = system_snapshot_from_control_plane_observations(
            snapshot_id="system:control-plane",
            observed_at=NOW,
            captured_at=NOW,
            freshness_deadline=FRESH,
            repository="DonkeyJJLove/ai_platform",
            current_head=H40,
            current_tree=T40,
            observations=observations,
            observation_ref="mission-control:evidence:1",
        )
        self.assertEqual(snap.epistemic_state, "CURRENT")
        facts = dict(snap.implementation_facts)
        self.assertEqual(facts["github_master_head"], H40)
        self.assertEqual(facts["focus_mission_source_current"], "false")
        self.assertEqual(facts["thread_db_integrity"], "ok")

    def test_control_plane_source_substitution_becomes_conflicted(self):
        observations = {
            "schema": "lion.control-plane-reconnaissance/v1",
            "mission_id": "mission:x",
            "phase_id": "RECON",
            "domains": {
                "panel": {
                    "repo": {
                        "github_master": {"head": "9" * 40, "tree": T40},
                    },
                    "thread_db": {"integrity": "ok", "identity_digest": "6" * 64},
                    "saas_projection": {},
                },
                "mission_control": {"mission": {}, "process": {}, "db": {"integrity": "ok"}},
            },
        }
        snap = system_snapshot_from_control_plane_observations(
            snapshot_id="system:conflicted",
            observed_at=NOW,
            captured_at=NOW,
            freshness_deadline=FRESH,
            repository="DonkeyJJLove/ai_platform",
            current_head=H40,
            current_tree=T40,
            observations=observations,
            observation_ref="mission-control:evidence:2",
        )
        self.assertEqual(snap.epistemic_state, "CONFLICTED")
        self.assertTrue(snap.contradictions)
        self.assertEqual(snap.freshness_deadline, "")

    def test_missing_control_plane_domain_remains_unknown(self):
        observations = {
            "schema": "lion.control-plane-reconnaissance/v1",
            "mission_id": "mission:x",
            "phase_id": "RECON",
            "domains": {
                "panel": {
                    "repo": {
                        "github_master": {"head": H40, "tree": T40},
                    },
                    "thread_db": {"integrity": "ok", "identity_digest": "6" * 64},
                    "saas_projection": {},
                },
            },
        }
        snap = system_snapshot_from_control_plane_observations(
            snapshot_id="system:unknown",
            observed_at=NOW,
            captured_at=NOW,
            freshness_deadline=FRESH,
            repository="DonkeyJJLove/ai_platform",
            current_head=H40,
            current_tree=T40,
            observations=observations,
            observation_ref="mission-control:evidence:3",
        )
        self.assertEqual(snap.epistemic_state, "UNKNOWN")
        self.assertIn("mission_control_observation_missing", snap.unknowns)

    def test_project_reality_is_deterministic_and_source_bound(self):
        left = reality()
        right = reality()
        self.assertEqual(left.snapshot_digest, right.snapshot_digest)
        changed = replace(left, source_tree="e" * 40, snapshot_digest="").sealed()
        self.assertNotEqual(left.snapshot_digest, changed.snapshot_digest)
        self.assertEqual(left.authority_effect, "NONE")
        self.assertEqual(left.effect, "NONE")

    def test_claim_projection_reuses_enterprise_graph_and_semantic_atoms(self):
        r = reality()
        g = graph()
        projection = build_project_claim_projection(
            projection_id="claims:project-reality",
            reality=r,
            graph=g,
            atoms=(atom(),),
            graph_node_refs=("claim:artifact-loop", "claim:source-current"),
            graph_edge_refs=("edge:source-supports-loop",),
        )
        self.assertEqual(projection.evidence_root_refs, ("root:git", "root:runtime"))
        self.assertEqual(projection.atom_bindings[0].independent_root_count, 2)
        self.assertEqual(projection.authority_effect, "NONE")

    def test_claim_projection_rejects_graph_widening_and_authority_edges(self):
        r = reality()
        with self.assertRaisesRegex(ProjectRealityError, "node widening"):
            build_project_claim_projection(
                projection_id="claims:widened",
                reality=r,
                graph=graph(),
                atoms=(atom(),),
                graph_node_refs=("claim:not-present",),
                graph_edge_refs=(),
            )
        ga = graph(include_authority=True)
        ra = replace(
            r,
            enterprise_graph_digest=ga.projection_digest,
            snapshot_digest="",
        ).sealed()
        with self.assertRaisesRegex(ProjectRealityError, "data-provenance"):
            build_project_claim_projection(
                projection_id="claims:authority-edge",
                reality=ra,
                graph=ga,
                atoms=(atom(),),
                graph_node_refs=("claim:artifact-loop", "claim:source-current"),
                graph_edge_refs=("edge:authority-ref",),
            )

    def test_unknown_gate_fails_closed_and_is_preserved(self):
        r = reality()
        ctx = ProjectRealityAdapter().build_evolution_context(
            reality=r,
            binding=binding("candidate:1", r, unknown_gate="effect_state_reconciled"),
            pressure_observations=(),
        )
        self.assertFalse(ctx.gates.effect_state_reconciled)
        self.assertEqual(ctx.unknown_gates, ("effect_state_reconciled",))

    def test_non_current_reality_cannot_claim_source_current(self):
        r = reality(state="UNKNOWN")
        with self.assertRaisesRegex(ProjectRealityError, "non-current"):
            ProjectRealityAdapter().build_evolution_context(
                reality=r,
                binding=binding("candidate:1", r),
                pressure_observations=(),
            )

    def test_pressure_is_evidence_bound_and_feeds_fitness_candidate(self):
        r = reality()
        b = binding("candidate:factory-loop", r)
        ctx = ProjectRealityAdapter().build_evolution_context(
            reality=r,
            binding=b,
            pressure_observations=(
                PressureObservation(
                    dimension="generativity_gain",
                    value=700,
                    evidence_ref="mission-intent:application-factory",
                    source_digest="4" * 64,
                    source_class="OPERATOR_OBJECTIVE",
                    observed_at=NOW,
                ).validate(),
                PressureObservation(
                    dimension="integration_closure",
                    value=900,
                    evidence_ref="gap:first-artifact-loop",
                    source_digest="5" * 64,
                    source_class="OBSERVED_STATE",
                    observed_at=NOW,
                ).validate(),
            ),
        )
        raw = EvolutionFitnessCandidate(
            candidate_id="candidate:factory-loop",
            vector=vector(),
            gates=replace(ctx.gates, source_current=False),
            evidence_refs=("evidence:fitness-vector",),
            repository_scope=("DonkeyJJLove/ai_platform",),
            task_family_count=2,
        ).validate()
        bound = ProjectRealityAdapter().bind_fitness_candidate(candidate=raw, context=ctx)
        self.assertTrue(bound.gates.source_current)
        self.assertEqual(tuple(x.dimension for x in ctx.pressures), ("generativity_gain", "integration_closure"))
        self.assertIn(f"project-reality:{r.snapshot_digest}", bound.evidence_refs)

    def test_candidate_identity_mismatch_fails_closed(self):
        r = reality()
        ctx = ProjectRealityAdapter().build_evolution_context(
            reality=r,
            binding=binding("candidate:a", r),
        )
        other = EvolutionFitnessCandidate(
            candidate_id="candidate:b",
            vector=vector(),
            gates=ctx.gates,
            evidence_refs=("evidence:b",),
            repository_scope=("DonkeyJJLove/ai_platform",),
            task_family_count=1,
        ).validate()
        with self.assertRaisesRegex(ProjectRealityError, "candidate mismatch"):
            ProjectRealityAdapter().bind_fitness_candidate(candidate=other, context=ctx)

    def test_evolution_eval_cases_cover_project_reality_failures(self):
        import json
        from pathlib import Path
        root = Path(__file__).resolve().parents[2]
        cases = json.loads(
            (root / "LION/evals/evolution/evolution_cases.yaml").read_text(encoding="utf-8")
        )["cases"]
        ids = {item["id"] for item in cases}
        self.assertTrue(
            {
                "PROJECT_REALITY_UNKNOWN_CANNOT_SATISFY_SOURCE_CURRENT",
                "PROJECT_CLAIM_PROJECTION_CANNOT_USE_AUTHORITY_EDGE",
                "MENTAL_MATRIX_NARRATIVE_CANNOT_PROMOTE_EPISTEMIC_CLASS",
            }
            <= ids
        )

    def test_adapter_has_no_effect_surface(self):
        ProjectRealityAdapter.assert_no_effect_surface()


if __name__ == "__main__":
    unittest.main()
