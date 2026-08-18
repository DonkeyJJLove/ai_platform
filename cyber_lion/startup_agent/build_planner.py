"""Translate validated startup experiments into minimal software build specifications.

The planner creates an auditable artifact plan. It does not write files or deploy anything;
execution remains a separate capability behind the Cyber-Lion authority boundary.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import PurePosixPath
from typing import Dict, List, Tuple

from .models import Experiment, ProductHypothesis, StartupModelError


@dataclass(frozen=True)
class SoftwareBuildSpec:
    spec_id: str
    hypothesis_id: str
    experiment_id: str
    product_goal: str
    target_user: str
    artifact_kind: str
    components: Tuple[str, ...]
    interfaces: Tuple[str, ...]
    acceptance_tests: Tuple[str, ...]
    security_invariants: Tuple[str, ...]
    non_goals: Tuple[str, ...]
    authority_class: str = "local_prototype"

    def validate(self) -> "SoftwareBuildSpec":
        if not all([self.spec_id, self.hypothesis_id, self.experiment_id, self.product_goal, self.target_user]):
            raise StartupModelError("build spec identity/goal/user required")
        if not self.components or not self.acceptance_tests or not self.security_invariants:
            raise StartupModelError("build spec requires components, tests and security invariants")
        if self.authority_class not in {"analysis", "local_prototype", "external_write", "deploy", "financial"}:
            raise StartupModelError("unknown build authority class")
        return self


class SoftwareBuildPlanner:
    """Create the smallest build that can answer the selected experiment question."""

    def from_experiment(self, hypothesis: ProductHypothesis, experiment: Experiment) -> SoftwareBuildSpec:
        hypothesis.validate(); experiment.validate()
        if experiment.hypothesis_id != hypothesis.hypothesis_id:
            raise StartupModelError("experiment/hypothesis mismatch")

        common_security = (
            "no secret committed to source",
            "all external effects require explicit authority gate",
            "input validation at every deterministic execution boundary",
            "observable outcome emitted for the experiment correlation id",
        )

        if experiment.experiment_type == "prototype":
            return SoftwareBuildSpec(
                spec_id=f"build-{experiment.experiment_id}",
                hypothesis_id=hypothesis.hypothesis_id,
                experiment_id=experiment.experiment_id,
                product_goal=f"Prove the smallest end-to-end workflow for: {hypothesis.solution}",
                target_user=hypothesis.customer,
                artifact_kind="python_service_prototype",
                components=("domain.py", "service.py", "metrics.py", "tests/test_service.py", "README.md"),
                interfaces=("POST /run-like domain function", "structured result object", "experiment metrics output"),
                acceptance_tests=(
                    experiment.success_metric,
                    "one happy-path workflow completes end-to-end",
                    "invalid input fails closed",
                    "runtime exposes latency/cost/result metrics",
                ),
                security_invariants=common_security,
                non_goals=("production deployment", "full UI", "multi-tenant auth", "premature scaling"),
            ).validate()

        if experiment.experiment_type in {"landing_page", "problem_smoke_test"}:
            return SoftwareBuildSpec(
                spec_id=f"build-{experiment.experiment_id}",
                hypothesis_id=hypothesis.hypothesis_id,
                experiment_id=experiment.experiment_id,
                product_goal=f"Measure qualified intent for: {hypothesis.solution}",
                target_user=hypothesis.customer,
                artifact_kind="intent_capture_prototype",
                components=("app.py", "copy.json", "events.py", "tests/test_events.py", "README.md"),
                interfaces=("render proposition", "record anonymous intent event", "export aggregate metrics"),
                acceptance_tests=(experiment.success_metric, "no PII required for baseline intent measurement"),
                security_invariants=common_security,
                non_goals=("production marketing site", "CRM automation", "automated outbound"),
                authority_class="external_write",
            ).validate()

        if experiment.experiment_type in {"paid_pilot", "pricing_test"}:
            return SoftwareBuildSpec(
                spec_id=f"build-{experiment.experiment_id}",
                hypothesis_id=hypothesis.hypothesis_id,
                experiment_id=experiment.experiment_id,
                product_goal=f"Support a bounded commercial validation of: {hypothesis.solution}",
                target_user=hypothesis.customer,
                artifact_kind="pilot_ops_prototype",
                components=("pilot.py", "pricing.py", "audit.py", "tests/test_pilot.py", "README.md"),
                interfaces=("quote calculation", "pilot state transition", "audit receipt"),
                acceptance_tests=(experiment.success_metric, "every commercial state transition has an audit record"),
                security_invariants=common_security + ("no payment or contract commitment without financial authority gate",),
                non_goals=("automated payment capture", "contract signing", "production billing"),
                authority_class="financial",
            ).validate()

        # Interviews/retention/concierge can still need lightweight instrumentation, not a product rewrite.
        return SoftwareBuildSpec(
            spec_id=f"build-{experiment.experiment_id}",
            hypothesis_id=hypothesis.hypothesis_id,
            experiment_id=experiment.experiment_id,
            product_goal=f"Instrument evidence collection for: {experiment.question}",
            target_user=hypothesis.customer,
            artifact_kind="evidence_instrumentation",
            components=("capture.py", "schema.py", "summary.py", "tests/test_capture.py", "README.md"),
            interfaces=("record observation", "export aggregate evidence"),
            acceptance_tests=(experiment.success_metric, "every observation includes source and timestamp"),
            security_invariants=common_security,
            non_goals=("full product build", "external automation"),
            authority_class="analysis",
        ).validate()


class SafeTemplateBuilder:
    """Generate an in-memory file map from a build spec.

    It intentionally does not touch the filesystem. A later execution capability may write
    the returned files after path validation and an appropriate authority decision.
    """

    def render(self, spec: SoftwareBuildSpec) -> Dict[str, str]:
        spec.validate()
        files: Dict[str, str] = {}
        for component in spec.components:
            path = PurePosixPath(component)
            if path.is_absolute() or ".." in path.parts:
                raise StartupModelError(f"unsafe component path: {component}")
            if path.suffix == ".py":
                files[component] = self._python_template(component, spec)
            elif path.name.lower() == "readme.md":
                files[component] = self._readme_template(spec)
            elif path.suffix == ".json":
                files[component] = "{}\n"
            else:
                files[component] = ""
        return files

    @staticmethod
    def _python_template(component: str, spec: SoftwareBuildSpec) -> str:
        if component.startswith("tests/"):
            return (
                '"""Generated experiment test scaffold."""\n'
                "import unittest\n\n"
                "class GeneratedExperimentTest(unittest.TestCase):\n"
                "    def test_acceptance_contract_is_explicit(self):\n"
                f"        self.assertTrue({bool(spec.acceptance_tests)!r})\n\n"
                "if __name__ == '__main__':\n"
                "    unittest.main()\n"
            )
        return (
            f'"""Generated scaffold for {spec.spec_id}; no external side effects by default."""\n'
            "from __future__ import annotations\n\n"
            "def describe() -> dict:\n"
            "    return {\n"
            f"        'spec_id': {spec.spec_id!r},\n"
            f"        'goal': {spec.product_goal!r},\n"
            f"        'authority_class': {spec.authority_class!r},\n"
            "    }\n"
        )

    @staticmethod
    def _readme_template(spec: SoftwareBuildSpec) -> str:
        tests = "\n".join(f"- {item}" for item in spec.acceptance_tests)
        invariants = "\n".join(f"- {item}" for item in spec.security_invariants)
        return (
            f"# {spec.spec_id}\n\n"
            f"Goal: {spec.product_goal}\n\n"
            f"Target user: {spec.target_user}\n\n"
            "## Acceptance tests\n\n"
            f"{tests}\n\n"
            "## Security invariants\n\n"
            f"{invariants}\n"
        )
