from __future__ import annotations

import unittest

from cyber_lion.startup_agent import (
    AIDrivenStartupAgent,
    BoundedLocalBuildRunner,
    ProductHypothesis,
    SafeTemplateBuilder,
    SoftwareBuildPlanner,
    VentureVector,
)
from cyber_lion.startup_agent.build_planner import SoftwareBuildSpec
from cyber_lion.startup_agent.models import Experiment, StartupModelError


H = ProductHypothesis(
    "h1",
    "AI team",
    "slow validation",
    "bounded agentic build loop",
    "B2B",
    VentureVector(0.6, 0.5, 0.4, 0.6, 0.4, 0.4, 0.7, 0.5, 0.8),
)


class LocalBuildTests(unittest.TestCase):
    def test_generated_prototype_compiles_and_tests(self):
        exp = Experiment(
            "e1", "h1", "prototype", "Can it work?", 0.8, 24, 0.1,
            "local_prototype", "workflow works", "stop on infeasible latency",
        )
        spec = SoftwareBuildPlanner().from_experiment(H, exp)
        files = SafeTemplateBuilder().render(spec)
        receipt = BoundedLocalBuildRunner(timeout_seconds=10).run(spec, files)
        self.assertEqual(receipt.status, "PASS")
        self.assertEqual(receipt.compile_returncode, 0)
        self.assertEqual(receipt.test_returncode, 0)
        self.assertIn("tests/test_service.py", receipt.files_written)

    def test_external_authority_cannot_run_locally_as_if_safe(self):
        spec = SoftwareBuildSpec(
            "s", "h1", "e", "goal", "user", "intent_capture",
            ("app.py", "tests/test_app.py"), (), ("works",), ("gate",), (), "external_write",
        )
        files = SafeTemplateBuilder().render(spec)
        with self.assertRaises(StartupModelError):
            BoundedLocalBuildRunner().run(spec, files)

    def test_runner_rejects_path_traversal(self):
        spec = SoftwareBuildSpec(
            "s", "h1", "e", "goal", "user", "prototype",
            ("safe.py",), (), ("works",), ("gate",), (), "local_prototype",
        )
        with self.assertRaises(StartupModelError):
            BoundedLocalBuildRunner().run(spec, {"../escape.py": "x=1\n"})

    def test_orchestrator_build_local_respects_authority(self):
        agent = AIDrivenStartupAgent("s")
        plan = agent.plan([H])
        if plan.authority.decision == "ALLOW":
            receipt = agent.build_local(plan)
            self.assertEqual(receipt.status, "PASS")
        else:
            with self.assertRaises(StartupModelError):
                agent.build_local(plan)


if __name__ == "__main__":
    unittest.main()
