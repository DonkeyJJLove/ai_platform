from __future__ import annotations

from dataclasses import replace
import unittest

from cyber_lion.contracts.repository_expansion import (
    FleetBaseline,
    RegisteredRepository,
    RepositoryBaseline,
    RepositoryDependencyEdge,
    RepositoryExpansionContractError,
    VerificationEvidence,
)

A = "a" * 40
B = "b" * 40
C = "c" * 40


def _evidence(
    *,
    evidence_id: str = "lion:test:1",
    actor: str = "LION",
    scope: str = "TEST",
    result: str = "PASS",
    command: str | None = "python -m unittest discover -s cyber_lion/tests -p test_*.py -v",
    exit_code: int | None = 0,
    source_ref: str | None = "github-actions:run:1",
) -> VerificationEvidence:
    return VerificationEvidence(
        evidence_id=evidence_id,
        actor=actor,
        scope=scope,
        result=result,
        command=command,
        exit_code=exit_code,
        source_ref=source_ref,
    )


def _baseline(
    repository: str,
    branch: str,
    *,
    head: str = A,
    tree: str = B,
    dependencies: tuple[str, ...] = (),
    dependents: tuple[str, ...] = (),
    build_result: str = "UNKNOWN",
    test_result: str = "UNKNOWN",
    failure_classification: str = "UNKNOWN",
    known_preexisting_failures: tuple[str, ...] = (),
    manifest_present: bool = True,
    evidence: tuple[VerificationEvidence, ...] = (),
) -> RepositoryBaseline:
    return RepositoryBaseline(
        schema_version="1.0.0",
        repository=repository,
        branch=branch,
        head=head,
        tree=tree,
        dirty=None,
        build_result=build_result,
        test_result=test_result,
        failure_classification=failure_classification,
        known_preexisting_failures=known_preexisting_failures,
        dependencies=dependencies,
        dependents=dependents,
        public_contracts=(),
        security_boundaries=("proposal != authority",),
        manifest_present=manifest_present,
        evidence=evidence,
    )


def _edge() -> RepositoryDependencyEdge:
    return RepositoryDependencyEdge(
        source="DonkeyJJLove/ai_platform",
        target="DonkeyJJLove/writeups",
        relation="OBSERVES",
        contract="repository registry",
        version_assumption=None,
        failure_mode="stale research-corpus observation",
        security_impact="evidence provenance can become stale",
        test_coverage="R2E1 contract validation",
        evidence="cyber_lion/registry/repositories.json",
    )


def _fleet() -> FleetBaseline:
    return FleetBaseline(
        schema_version="1.0.0",
        baseline_id="R2E1-FLEET-BASELINE",
        registered=(
            RegisteredRepository("DonkeyJJLove/ai_platform", "master"),
            RegisteredRepository("DonkeyJJLove/writeups", "master"),
        ),
        observations=(
            _baseline(
                "DonkeyJJLove/ai_platform",
                "master",
                dependencies=("DonkeyJJLove/writeups",),
                test_result="PASS",
                evidence=(_evidence(),),
            ),
            _baseline(
                "DonkeyJJLove/writeups",
                "master",
                dependents=("DonkeyJJLove/ai_platform",),
                manifest_present=False,
            ),
        ),
        edges=(_edge(),),
    )


class VerificationEvidenceTests(unittest.TestCase):
    def test_pass_requires_literal_command(self):
        with self.assertRaisesRegex(RepositoryExpansionContractError, "command"):
            replace(_evidence(), command=None).validate()

    def test_pass_requires_literal_exit_code(self):
        with self.assertRaisesRegex(RepositoryExpansionContractError, "exit_code"):
            replace(_evidence(), exit_code=None).validate()

    def test_pass_requires_zero_exit_code(self):
        with self.assertRaisesRegex(RepositoryExpansionContractError, "exit_code=0"):
            replace(_evidence(), exit_code=3).validate()

    def test_fail_requires_nonzero_exit_code(self):
        with self.assertRaisesRegex(RepositoryExpansionContractError, "non-zero"):
            replace(_evidence(), result="FAIL", exit_code=0).validate()

    def test_unknown_is_first_class_but_cannot_claim_exit_code(self):
        value = replace(
            _evidence(),
            result="UNKNOWN",
            command=None,
            exit_code=None,
            source_ref="github-actions:no-functional-run-observed",
        ).validate()
        self.assertEqual(value.result, "UNKNOWN")
        with self.assertRaisesRegex(RepositoryExpansionContractError, "UNKNOWN cannot claim"):
            replace(value, exit_code=0).validate()

    def test_non_fleet_actor_is_rejected(self):
        with self.assertRaisesRegex(RepositoryExpansionContractError, "actor"):
            replace(_evidence(), actor="AUTHOR").validate()


class RepositoryBaselineTests(unittest.TestCase):
    def test_test_pass_requires_literal_test_scope_evidence(self):
        baseline = _baseline(
            "DonkeyJJLove/ai_platform",
            "master",
            test_result="PASS",
            evidence=(replace(_evidence(), scope="HYGIENE"),),
        )
        with self.assertRaisesRegex(RepositoryExpansionContractError, "test PASS"):
            baseline.validate()

    def test_build_pass_requires_build_evidence(self):
        baseline = _baseline(
            "DonkeyJJLove/ai_platform",
            "master",
            build_result="PASS",
            evidence=(_evidence(),),
        )
        with self.assertRaisesRegex(RepositoryExpansionContractError, "build PASS"):
            baseline.validate()

    def test_known_failure_classification_requires_entries(self):
        baseline = _baseline(
            "DonkeyJJLove/ai_platform",
            "master",
            failure_classification="KNOWN_PREEXISTING_FAILURES",
        )
        with self.assertRaisesRegex(RepositoryExpansionContractError, "known failures"):
            baseline.validate()

    def test_invalid_head_is_rejected(self):
        with self.assertRaisesRegex(RepositoryExpansionContractError, "head"):
            _baseline("DonkeyJJLove/ai_platform", "master", head="not-a-sha").validate()

    def test_evidence_hash_is_deterministic(self):
        baseline = _baseline("DonkeyJJLove/ai_platform", "master")
        self.assertEqual(baseline.evidence_hash(), baseline.evidence_hash())
        self.assertEqual(len(baseline.evidence_hash()), 64)


class FleetBaselineTests(unittest.TestCase):
    def test_gate0_passes_inventory_with_unknown_health_without_upgrading_it(self):
        fleet = _fleet()
        decision = fleet.gate0()
        self.assertEqual(decision.result, "PASS")
        by_repo = {item.repository: item for item in fleet.observations}
        self.assertEqual(by_repo["DonkeyJJLove/writeups"].test_result, "UNKNOWN")
        self.assertFalse(by_repo["DonkeyJJLove/writeups"].manifest_present)

    def test_missing_repository_observation_is_rejected(self):
        fleet = _fleet()
        with self.assertRaisesRegex(RepositoryExpansionContractError, "exactly cover"):
            replace(fleet, observations=fleet.observations[:1]).validate()

    def test_duplicate_repository_observation_is_rejected(self):
        fleet = _fleet()
        with self.assertRaisesRegex(RepositoryExpansionContractError, "duplicate repository observation"):
            replace(fleet, observations=(fleet.observations[0], fleet.observations[0])).validate()

    def test_default_branch_substitution_is_rejected(self):
        fleet = _fleet()
        changed = replace(fleet.observations[0], branch="main")
        with self.assertRaisesRegex(RepositoryExpansionContractError, "registered default"):
            replace(fleet, observations=(changed, fleet.observations[1])).validate()

    def test_dependency_projection_must_match_graph(self):
        fleet = _fleet()
        changed = replace(fleet.observations[0], dependencies=())
        with self.assertRaisesRegex(RepositoryExpansionContractError, "dependencies disagree"):
            replace(fleet, observations=(changed, fleet.observations[1])).validate()

    def test_edge_cannot_escape_registered_fleet(self):
        fleet = _fleet()
        edge = replace(_edge(), target="Other/repository")
        changed_writeups = replace(fleet.observations[1], dependents=())
        changed_ai = replace(fleet.observations[0], dependencies=("Other/repository",))
        with self.assertRaisesRegex(RepositoryExpansionContractError, "escapes registered fleet"):
            replace(fleet, observations=(changed_ai, changed_writeups), edges=(edge,)).validate()

    def test_duplicate_edge_is_rejected(self):
        fleet = _fleet()
        with self.assertRaisesRegex(RepositoryExpansionContractError, "duplicate dependency edge"):
            replace(fleet, edges=(_edge(), _edge())).validate()

    def test_baseline_digest_is_stable_and_gate_bound(self):
        fleet = _fleet()
        digest = fleet.baseline_digest()
        decision = fleet.gate0()
        self.assertEqual(len(digest), 64)
        self.assertEqual(decision.baseline_digest, digest)


if __name__ == "__main__":
    unittest.main()
