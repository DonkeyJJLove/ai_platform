from __future__ import annotations

from dataclasses import replace
import unittest

from cyber_lion.architecture_projection.current_truth import (
    CurrentTruthError,
    TruthSourceSpec,
    build_current_truth_projection,
    canonical_truth_source_specs,
)
from cyber_lion.architecture_projection.gap import canonical_target_gaps

H1 = "1" * 40
H2 = "2" * 40
T1 = "a" * 40
T2 = "b" * 40


def py_class(name: str) -> str:
    return f"class {name}:\n    pass\n"


class CurrentTruthProjectionTests(unittest.TestCase):
    def test_target_baseline_is_not_rewritten_by_current_truth(self):
        targets = canonical_target_gaps()
        self.assertTrue(any(row.target_id == "BeanSpec" and row.status == "TARGET_ONLY" for row in targets))

    def test_source_backed_target_only_is_resolved_in_implementation_plane(self):
        specs = (
            TruthSourceSpec("BeanSpec", "cyber_lion/contracts/bean.py", symbol="BeanSpec").validate(),
        )
        sources = {"cyber_lion/contracts/bean.py": py_class("BeanSpec")}
        projection = build_current_truth_projection(
            repository="DonkeyJJLove/ai_platform",
            baseline_head=H1,
            baseline_tree=T1,
            candidate_head=H2,
            candidate_tree=T2,
            expected_head=H2,
            expected_tree=T2,
            baseline_sources={},
            candidate_sources=sources,
            specs=specs,
        )
        self.assertEqual(projection.freshness, "CURRENT")
        self.assertEqual(projection.source_backed_target_only_ids, ())
        row = projection.implementations[0]
        self.assertEqual(row.target_status, "TARGET_ONLY")
        self.assertEqual(row.implementation_status, "IMPLEMENTED")
        self.assertEqual(row.plane, "CANDIDATE")

    def test_as_is_vs_candidate_is_derived_from_exact_source_bytes(self):
        specs = (
            TruthSourceSpec("BeanSpec", "cyber_lion/contracts/bean.py", symbol="BeanSpec").validate(),
            TruthSourceSpec("HybridRouter", "cyber_lion/hybrid_router.py", symbol="HybridRouter").validate(),
        )
        bean = py_class("BeanSpec")
        router = py_class("HybridRouter")
        projection = build_current_truth_projection(
            repository="DonkeyJJLove/ai_platform",
            baseline_head=H1,
            baseline_tree=T1,
            candidate_head=H2,
            candidate_tree=T2,
            expected_head=H2,
            expected_tree=T2,
            baseline_sources={"cyber_lion/contracts/bean.py": bean},
            candidate_sources={
                "cyber_lion/contracts/bean.py": bean,
                "cyber_lion/hybrid_router.py": router,
            },
            specs=specs,
        )
        self.assertEqual(projection.as_is_ids, ("BeanSpec",))
        self.assertEqual(projection.candidate_delta_ids, ("HybridRouter",))

    def test_head_or_tree_drift_is_stale_not_current(self):
        spec = (
            TruthSourceSpec("BeanSpec", "cyber_lion/contracts/bean.py", symbol="BeanSpec").validate(),
        )
        projection = build_current_truth_projection(
            repository="DonkeyJJLove/ai_platform",
            baseline_head=H1,
            baseline_tree=T1,
            candidate_head=H2,
            candidate_tree=T2,
            expected_head="3" * 40,
            expected_tree=T2,
            baseline_sources={},
            candidate_sources={"cyber_lion/contracts/bean.py": py_class("BeanSpec")},
            specs=spec,
        )
        self.assertEqual(projection.freshness, "STALE")
        with self.assertRaises(CurrentTruthError):
            replace(projection, freshness="CURRENT", projection_digest="").sealed()

    def test_missing_symbol_or_schema_token_fails_closed(self):
        cases = (
            (
                TruthSourceSpec("BeanSpec", "cyber_lion/contracts/bean.py", symbol="BeanSpec").validate(),
                py_class("Other"),
            ),
            (
                TruthSourceSpec(
                    "ActionSpec",
                    "cyber_lion/contracts/v1/action_spec.schema.json",
                    literal_token="lion://schemas/action-spec/v1.3-candidate",
                ).validate(),
                '{"$id":"wrong"}',
            ),
        )
        for spec, source in cases:
            with self.assertRaises(CurrentTruthError):
                build_current_truth_projection(
                    repository="DonkeyJJLove/ai_platform",
                    baseline_head=H1,
                    baseline_tree=T1,
                    candidate_head=H2,
                    candidate_tree=T2,
                    expected_head=H2,
                    expected_tree=T2,
                    baseline_sources={},
                    candidate_sources={spec.source_path: source},
                    specs=(spec,),
                )

    def test_global_complete_mediation_unknown_is_preserved_as_separate_truth(self):
        projection = build_current_truth_projection(
            repository="DonkeyJJLove/ai_platform",
            baseline_head=H1,
            baseline_tree=T1,
            candidate_head=H2,
            candidate_tree=T2,
            expected_head=H2,
            expected_tree=T2,
            baseline_sources={},
            candidate_sources={},
            specs=(),
        )
        self.assertIn("GlobalCompleteMediation", projection.unresolved_unknown_target_ids)
        self.assertEqual(projection.freshness, "CURRENT")

    def test_projection_is_deterministic_and_non_effectful(self):
        specs = (
            TruthSourceSpec("BeanSpec", "cyber_lion/contracts/bean.py", symbol="BeanSpec").validate(),
        )
        kwargs = dict(
            repository="DonkeyJJLove/ai_platform",
            baseline_head=H1,
            baseline_tree=T1,
            candidate_head=H2,
            candidate_tree=T2,
            expected_head=H2,
            expected_tree=T2,
            baseline_sources={},
            candidate_sources={"cyber_lion/contracts/bean.py": py_class("BeanSpec")},
            specs=specs,
        )
        first = build_current_truth_projection(**kwargs)
        second = build_current_truth_projection(**kwargs)
        self.assertEqual(first.digest(), second.digest())
        self.assertFalse(first.authority_effect)
        self.assertFalse(first.repository_effect)

    def test_canonical_specs_cover_current_candidate_planes(self):
        ids = {spec.target_id for spec in canonical_truth_source_specs()}
        self.assertTrue({
            "GoalContract", "WorldSnapshot", "SystemSnapshot", "Gap",
            "BeanSpec", "BeanCandidate", "BeanInstance", "CompositionContract", "CompositionEngine",
            "ActionSpec", "LCMS", "ReadonlyProcessAdapter", "HybridRouter", "PhysicalActionSpec",
        }.issubset(ids))


if __name__ == "__main__":
    unittest.main()
