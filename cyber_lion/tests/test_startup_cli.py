from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from cyber_lion.startup_agent.cli import main, run_cycle
from cyber_lion.startup_agent.models import StartupModelError


VALID = {
    "startup_id": "s1",
    "hypotheses": [
        {
            "hypothesis_id": "h1",
            "customer": "AI team",
            "problem": "slow validation",
            "solution": "bounded build loop",
            "revenue_model": "B2B",
            "baseline": {
                "market_pull": 0.6,
                "evidence_strength": 0.5,
                "technical_feasibility": 0.4,
                "differentiation": 0.6,
                "distribution_access": 0.4,
                "delivery_velocity": 0.4,
                "security_readiness": 0.8,
                "unit_economics": 0.5,
                "learning_velocity": 0.8
            }
        }
    ],
    "observations": [
        {
            "observation_id": "o1",
            "hypothesis_id": "h1",
            "source": "customer-1",
            "source_class": "customer",
            "observed_at": "2026-08-18T10:00:00+00:00",
            "captured_at": "2026-08-18T10:10:00+00:00",
            "topic": "pain",
            "signal_kind": "pain",
            "direction": "supports",
            "magnitude": 0.8,
            "confidence": 0.9,
            "claim": "pain confirmed"
        }
    ]
}

# Explicit BUILD-stage fixture: market/evidence/differentiation are already strong,
# while technical feasibility and delivery velocity remain the dominant bottleneck.
# That deterministically selects a local_prototype experiment with autonomous ALLOW.
BUILD_LOCAL = json.loads(json.dumps(VALID))
BUILD_LOCAL["hypotheses"][0]["baseline"].update(
    {
        "market_pull": 0.82,
        "evidence_strength": 0.72,
        "technical_feasibility": 0.40,
        "differentiation": 0.72,
        "distribution_access": 0.62,
        "delivery_velocity": 0.42,
        "security_readiness": 0.82,
        "unit_economics": 0.62,
        "learning_velocity": 0.82,
    }
)


class StartupCliTests(unittest.TestCase):
    def test_run_cycle_returns_machine_readable_plan(self):
        result = run_cycle(VALID)
        self.assertEqual(result["startup_id"], "s1")
        self.assertEqual(result["selected_hypothesis"], "h1")
        self.assertTrue(result["scaffold_files"])
        self.assertIn("decision", result["authority"])
        self.assertEqual(result["freshness"]["total"], 1.0)

    def test_naive_timestamp_fails_closed(self):
        invalid = json.loads(json.dumps(VALID))
        invalid["observations"][0]["observed_at"] = "2026-08-18T10:00:00"
        with self.assertRaises(StartupModelError):
            run_cycle(invalid)

    def test_cli_writes_output_and_journal(self):
        with tempfile.TemporaryDirectory() as tmp:
            input_path = Path(tmp) / "input.json"
            output_path = Path(tmp) / "output.json"
            journal_path = Path(tmp) / "journal.jsonl"
            input_path.write_text(json.dumps(VALID), encoding="utf-8")
            rc = main([str(input_path), "--output", str(output_path), "--journal", str(journal_path)])
            self.assertEqual(rc, 0)
            self.assertTrue(output_path.exists())
            self.assertTrue(journal_path.exists())
            result = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(result["startup_id"], "s1")

    def test_build_local_runs_only_when_plan_allows_it(self):
        result = run_cycle(BUILD_LOCAL, build_local=True)
        self.assertEqual(result["experiment"]["experiment_type"], "prototype")
        self.assertEqual(result["authority"]["decision"], "ALLOW")
        self.assertIsNotNone(result["build_receipt"])
        self.assertEqual(result["build_receipt"]["status"], "PASS")

    def test_build_local_refuses_approval_required_plan(self):
        # Default fixture selects an external market experiment. --build-local must not bypass it.
        with self.assertRaises(StartupModelError):
            run_cycle(VALID, build_local=True)

    def test_cli_returns_error_code_for_bad_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.json"
            path.write_text(json.dumps({"startup_id": "s1", "hypotheses": []}), encoding="utf-8")
            self.assertEqual(main([str(path)]), 2)


if __name__ == "__main__":
    unittest.main()
