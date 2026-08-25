from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from cyber_lion.startup_agent import (
    AIDrivenStartupAgent,
    BoundedLocalBuildRunner,
    LocalBuildExecutionGate,
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


def gate_for(spec: SoftwareBuildSpec, nonce: str = "n1") -> LocalBuildExecutionGate:
    return LocalBuildExecutionGate.seal(
        gate_event_id="test:authority:local-build",
        spec_id=spec.spec_id,
        authority_class=spec.authority_class,
        nonce=nonce,
    )


class LocalBuildTests(unittest.TestCase):
    def _prototype(self):
        exp = Experiment(
            "e1", "h1", "prototype", "Can it work?", 0.8, 24, 0.1,
            "local_prototype", "workflow works", "stop on infeasible latency",
        )
        spec = SoftwareBuildPlanner().from_experiment(H, exp)
        return spec, SafeTemplateBuilder().render(spec)

    def test_generated_prototype_compiles_and_tests_behind_gate(self):
        spec, files = self._prototype()
        receipt = BoundedLocalBuildRunner(timeout_seconds=10).run(spec, files, gate=gate_for(spec))
        self.assertEqual(receipt.status, "PASS")
        self.assertEqual(receipt.compile_returncode, 0)
        self.assertEqual(receipt.test_returncode, 0)
        self.assertIn("tests/test_service.py", receipt.files_written)
        self.assertEqual(receipt.gate_digest, gate_for(spec).gate_digest)
        self.assertGreaterEqual(len(receipt.observation_digests), 2)

    def test_direct_effect_without_gate_is_not_a_callable_run_path(self):
        spec, files = self._prototype()
        runner = BoundedLocalBuildRunner()
        with self.assertRaises(TypeError):
            runner.run(spec, files)

    def test_gate_replay_is_denied(self):
        spec, files = self._prototype()
        runner = BoundedLocalBuildRunner(timeout_seconds=10)
        gate = gate_for(spec)
        self.assertEqual(runner.run(spec, files, gate=gate).status, "PASS")
        with self.assertRaises(StartupModelError):
            runner.run(spec, files, gate=gate)

    def test_gate_surface_substitution_is_denied(self):
        spec, files = self._prototype()
        substituted = LocalBuildExecutionGate.seal(
            gate_event_id="test:authority:local-build",
            spec_id="other-spec",
            authority_class=spec.authority_class,
            nonce="n1",
        )
        with self.assertRaises(StartupModelError):
            BoundedLocalBuildRunner().run(spec, files, gate=substituted)

    def test_raw_command_effect_outside_active_gate_is_denied(self):
        runner = BoundedLocalBuildRunner()
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(StartupModelError):
                runner._run_command(["not-allowed"], cwd=Path(tmp), gate_digest="0" * 64)

    def test_external_authority_cannot_run_locally_as_if_safe(self):
        spec = SoftwareBuildSpec(
            "s", "h1", "e", "goal", "user", "intent_capture",
            ("app.py", "tests/test_app.py"), (), ("works",), ("gate",), (), "external_write",
        )
        files = SafeTemplateBuilder().render(spec)
        with self.assertRaises(StartupModelError):
            BoundedLocalBuildRunner().run(spec, files, gate=gate_for(spec))

    def test_runner_rejects_path_traversal_before_effect(self):
        spec = SoftwareBuildSpec(
            "s", "h1", "e", "goal", "user", "prototype",
            ("safe.py",), (), ("works",), ("gate",), (), "local_prototype",
        )
        with self.assertRaises(StartupModelError):
            BoundedLocalBuildRunner().run(spec, {"../escape.py": "x=1\n"}, gate=gate_for(spec))

    def test_orchestrator_requires_separate_execution_gate(self):
        agent = AIDrivenStartupAgent("s")
        plan = agent.plan([H])
        if plan.authority.decision == "ALLOW":
            with self.assertRaises(TypeError):
                agent.build_local(plan)
            receipt = agent.build_local(plan, execution_gate_event_id="test:execution-gate")
            self.assertEqual(receipt.status, "PASS")
        else:
            with self.assertRaises(StartupModelError):
                agent.build_local(plan, execution_gate_event_id="test:execution-gate")


if __name__ == "__main__":
    unittest.main()
