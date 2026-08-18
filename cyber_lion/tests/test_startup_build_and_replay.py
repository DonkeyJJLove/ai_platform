from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from cyber_lion.startup_agent import (
    EvolutionJournal,
    EvolutionState,
    Experiment,
    ProductHypothesis,
    SafeTemplateBuilder,
    SoftwareBuildPlanner,
    VentureVector,
)
from cyber_lion.startup_agent.build_planner import SoftwareBuildSpec
from cyber_lion.startup_agent.models import StartupModelError


BASE = VentureVector(0.6, 0.5, 0.4, 0.6, 0.4, 0.4, 0.7, 0.5, 0.8)
H = ProductHypothesis("h1", "AI team", "slow validation", "bounded agentic build loop", "B2B", BASE)


class BuildPlannerTests(unittest.TestCase):
    def test_prototype_becomes_minimal_software_spec(self):
        exp = Experiment(
            "e1", "h1", "prototype", "Can it work?", 0.8, 24, 0.1,
            "local_prototype", "complete one end-to-end workflow", "stop on infeasible latency",
        )
        spec = SoftwareBuildPlanner().from_experiment(H, exp)
        self.assertEqual(spec.artifact_kind, "python_service_prototype")
        self.assertIn("tests/test_service.py", spec.components)
        self.assertIn("invalid input fails closed", spec.acceptance_tests)

    def test_commercial_build_keeps_financial_authority(self):
        exp = Experiment(
            "e2", "h1", "paid_pilot", "Will a buyer pay?", 0.9, 72, 0.2,
            "financial", "paid conversion", "stop after channel budget",
        )
        spec = SoftwareBuildPlanner().from_experiment(H, exp)
        self.assertEqual(spec.authority_class, "financial")
        self.assertTrue(any("financial authority gate" in x for x in spec.security_invariants))

    def test_template_builder_never_writes_and_rejects_traversal(self):
        spec = SoftwareBuildSpec(
            "s", "h1", "e", "goal", "user", "prototype",
            ("../escape.py",), (), ("test",), ("gate",), (), "local_prototype",
        )
        with self.assertRaises(StartupModelError):
            SafeTemplateBuilder().render(spec)

    def test_render_returns_auditable_file_map(self):
        exp = Experiment(
            "e3", "h1", "prototype", "Can it work?", 0.8, 12, 0.1,
            "local_prototype", "workflow works", "stop on failure",
        )
        spec = SoftwareBuildPlanner().from_experiment(H, exp)
        files = SafeTemplateBuilder().render(spec)
        self.assertIn("README.md", files)
        self.assertIn("domain.py", files)
        self.assertIn("no external side effects by default", files["domain.py"])


class JournalTests(unittest.TestCase):
    def _state(self, cycle, vector, previous=None):
        return EvolutionState(
            startup_id="startup",
            cycle=cycle,
            stage="BUILD",
            vector=vector,
            previous_vector=previous,
            active_hypothesis_id="h1",
            evidence_ids=[f"sig-{cycle}"],
            created_at=datetime(2026, 8, 18, 12 + cycle, tzinfo=timezone.utc),
        )

    def test_append_and_replay_preserves_state_chain(self):
        with tempfile.TemporaryDirectory() as tmp:
            journal = EvolutionJournal(Path(tmp) / "journal.jsonl")
            v1 = BASE
            v2 = VentureVector(0.7, 0.6, 0.5, 0.6, 0.4, 0.5, 0.7, 0.5, 0.9)
            journal.append(self._state(0, v1))
            journal.append(self._state(1, v2, v1))
            states = journal.replay()
            self.assertEqual(len(states), 2)
            self.assertEqual(states[-1].delta()["market_pull"], 0.1)
            self.assertEqual(journal.latest().cycle, 1)

    def test_replay_rejects_broken_cycle_sequence(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "journal.jsonl"
            journal = EvolutionJournal(path)
            journal.append(self._state(0, BASE))
            data = path.read_text(encoding="utf-8").replace('"cycle": 0', '"cycle": 2')
            path.write_text(data, encoding="utf-8")
            with self.assertRaises(ValueError):
                journal.replay()


if __name__ == "__main__":
    unittest.main()
