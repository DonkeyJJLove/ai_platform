from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
import unittest

from cyber_lion.contracts.verifier_execution_attestation import (
    ExactVerificationTarget,
    ExecutorParticipationRecord,
    TrustedParticipationHistory,
    VerifierExecutionAttestation,
    evidence_bundle_digest,
)
from cyber_lion.contracts.workload_identity import VerifiedWorkloadIdentity
from cyber_lion.enterprise.runtime_attestation import VerifiedRuntimeAttestation
from cyber_lion.enterprise.verifier_execution_attestation import (
    InMemoryVerifierExecutionReplayGuard,
    VerifierExecutionAdmission,
    VerifierExecutionAdmissionError,
)


BASE = "1" * 40
HEAD = "a" * 40
TREE = "b" * 40
PROOF = "c" * 64
RUNTIME_ATTEST = "d" * 64
IMPL = "e" * 64
ARTIFACT = "f" * 64
SOURCE_IMPL = "0" * 64
SEMANTIC = "2" * 64
MISSION = "LION-FLEET-CANONICAL-STATUS-REGISTRY-P0"


def target(**overrides):
    values = dict(
        repository="DonkeyJJLove/ai_platform",
        pr_number=44,
        base_sha=BASE,
        head_sha=HEAD,
        tree_sha=TREE,
        ci_run_id="32477275518",
        mission_id=MISSION,
        slice_id="STATUS-SOURCE-ADAPTERS-R2",
    )
    values.update(overrides)
    return ExactVerificationTarget(**values).validate()


def participation(role, subject, runtime, *, head=HEAD, tree=TREE):
    return ExecutorParticipationRecord(
        subject_id=subject,
        runtime_instance_id=runtime,
        participation_role=role,
        repository="DonkeyJJLove/ai_platform",
        mission_id=MISSION,
        target_head_sha=head,
        target_tree_sha=tree,
        provenance_ref=f"history:{role}:{subject}:{runtime}",
        evidence_digest="3" * 64,
        trust_anchor_id="history-root",
        observed_at="2026-08-21T11:30:00+00:00",
    ).validate()


def good_history(records=None):
    if records is None:
        records = (
            participation("BUILDER", "builder-subject", "builder-runtime"),
            participation("VERIFICATION_ATTACH", "attach-subject", "attach-runtime"),
        )
    return TrustedParticipationHistory.build(
        source_id="trusted-execution-history",
        trust_anchor_id="history-root",
        source_implementation_digest=SOURCE_IMPL,
        observed_at="2026-08-21T11:40:00+00:00",
        records=tuple(records),
    )


class HistorySource:
    source_id = "trusted-execution-history"
    trust_anchor_id = "history-root"
    source_implementation_digest = SOURCE_IMPL

    def __init__(self, history=None, error=None):
        self.history = history if history is not None else good_history()
        self.error = error

    def resolve(self, exact_target):
        if self.error:
            raise self.error
        return self.history


def workload(subject="verifier-subject", proof=PROOF):
    return VerifiedWorkloadIdentity(
        subject_id=subject,
        trust_domain="lion",
        tenant_id="tenant",
        organization_id="org",
        audience="verifier",
        proof_digest=proof,
        key_id="key-1",
        issued_at="2026-08-21T11:00:00+00:00",
        expires_at="2026-08-21T13:00:00+00:00",
    )


def runtime(subject="verifier-subject", runtime_id="verifier-runtime", impl=IMPL, digest=RUNTIME_ATTEST):
    return VerifiedRuntimeAttestation(
        subject_id=subject,
        runtime_instance_id=runtime_id,
        repository="DonkeyJJLove/ai_platform",
        commit_sha=HEAD,
        workflow_sha="4" * 40,
        run_id="run-verifier",
        run_attempt=1,
        mission_id=MISSION,
        artifact_digest=ARTIFACT,
        implementation_digest=impl,
        attestation_digest=digest,
        provenance_ref="external:runtime-verifier",
        trust_anchor_id="runtime-root",
    )


def attestation(history=None, **overrides):
    h = history if history is not None else good_history()
    bundle = evidence_bundle_digest(
        target=target(),
        workload_identity_proof_digest=PROOF,
        runtime_attestation_digest=RUNTIME_ATTEST,
        verifier_implementation_digest=IMPL,
        participation_history_digest=h.history_digest,
        semantic_evidence_digest=SEMANTIC,
    )
    values = dict(
        attestation_id="vea-44",
        verifier_subject_id="verifier-subject",
        verifier_runtime_instance_id="verifier-runtime",
        verifier_implementation_digest=IMPL,
        workload_identity_proof_digest=PROOF,
        runtime_attestation_digest=RUNTIME_ATTEST,
        target=target(),
        participation_history_digest=h.history_digest,
        evidence_bundle_digest=bundle,
        verification_result="PASS",
        external_attestation_ref="external:vea-44",
        issued_at="2026-08-21T11:45:00+00:00",
        expires_at="2026-08-21T12:45:00+00:00",
    )
    values.update(overrides)
    return VerifierExecutionAttestation(**values)


def gate(source=None, replay=None, expected_target=None):
    return VerifierExecutionAdmission(
        expected_target=expected_target or target(),
        participation_source=source or HistorySource(),
        expected_participation_source_id="trusted-execution-history",
        expected_participation_trust_anchor_id="history-root",
        expected_participation_implementation_digest=SOURCE_IMPL,
        replay_guard=replay or InMemoryVerifierExecutionReplayGuard(),
    )


NOW = datetime(2026, 8, 21, 12, 0, tzinfo=timezone.utc)


class VerifierExecutionAdmissionTests(unittest.TestCase):
    def test_distinct_subject_and_runtime_pass(self):
        result = gate().admit(
            attestation(), workload_identity=workload(), runtime_attestation=runtime(),
            semantic_evidence_digest=SEMANTIC, now=NOW,
        )
        self.assertEqual(result.verification_result, "PASS")
        self.assertEqual(result.verifier_subject_id, "verifier-subject")

    def test_same_builder_subject_new_runtime_denied(self):
        h = good_history((
            participation("BUILDER", "verifier-subject", "old-builder-runtime"),
            participation("VERIFICATION_ATTACH", "attach", "attach-runtime"),
        ))
        with self.assertRaises(VerifierExecutionAdmissionError):
            gate(HistorySource(h)).admit(attestation(h), workload_identity=workload(), runtime_attestation=runtime(), semantic_evidence_digest=SEMANTIC, now=NOW)

    def test_same_builder_runtime_new_label_denied(self):
        h = good_history((
            participation("BUILDER", "other-subject", "verifier-runtime"),
            participation("VERIFICATION_ATTACH", "attach", "attach-runtime"),
        ))
        with self.assertRaises(VerifierExecutionAdmissionError):
            gate(HistorySource(h)).admit(attestation(h), workload_identity=workload(), runtime_attestation=runtime(), semantic_evidence_digest=SEMANTIC, now=NOW)

    def test_same_verification_attach_subject_and_runtime_denied(self):
        for h in (
            good_history((participation("BUILDER", "builder", "builder-runtime"), participation("VERIFICATION_ATTACH", "verifier-subject", "attach-runtime"))),
            good_history((participation("BUILDER", "builder", "builder-runtime"), participation("VERIFICATION_ATTACH", "attach", "verifier-runtime"))),
        ):
            with self.subTest(history=h.history_digest), self.assertRaises(VerifierExecutionAdmissionError):
                gate(HistorySource(h)).admit(attestation(h), workload_identity=workload(), runtime_attestation=runtime(), semantic_evidence_digest=SEMANTIC, now=NOW)

    def test_missing_or_incomplete_participation_history_denied(self):
        empty = TrustedParticipationHistory.build(
            source_id="trusted-execution-history", trust_anchor_id="history-root",
            source_implementation_digest=SOURCE_IMPL,
            observed_at="2026-08-21T11:40:00+00:00", records=(),
        )
        incomplete = good_history((participation("BUILDER", "builder", "builder-runtime"),))
        for h in (empty, incomplete):
            with self.subTest(history=h.history_digest), self.assertRaises(VerifierExecutionAdmissionError):
                gate(HistorySource(h)).admit(attestation(h), workload_identity=workload(), runtime_attestation=runtime(), semantic_evidence_digest=SEMANTIC, now=NOW)

    def test_history_for_other_candidate_does_not_satisfy_exact_target(self):
        h = good_history((
            participation("BUILDER", "builder", "builder-runtime", head="9" * 40),
            participation("VERIFICATION_ATTACH", "attach", "attach-runtime", head="9" * 40),
        ))
        with self.assertRaises(VerifierExecutionAdmissionError):
            gate(HistorySource(h)).admit(attestation(h), workload_identity=workload(), runtime_attestation=runtime(), semantic_evidence_digest=SEMANTIC, now=NOW)

    def test_candidate_or_self_selected_history_source_denied_by_pins(self):
        source = HistorySource()
        source.source_id = "candidate-controlled-source"
        with self.assertRaises(VerifierExecutionAdmissionError):
            gate(source).admit(attestation(), workload_identity=workload(), runtime_attestation=runtime(), semantic_evidence_digest=SEMANTIC, now=NOW)

    def test_source_backend_failure_fails_closed(self):
        with self.assertRaises(VerifierExecutionAdmissionError):
            gate(HistorySource(error=RuntimeError("backend down"))).admit(attestation(), workload_identity=workload(), runtime_attestation=runtime(), semantic_evidence_digest=SEMANTIC, now=NOW)

    def test_workload_runtime_and_implementation_substitution_denied(self):
        cases = (
            dict(workload_identity=workload(subject="other"), runtime_attestation=runtime()),
            dict(workload_identity=workload(), runtime_attestation=runtime(runtime_id="other-runtime")),
            dict(workload_identity=workload(), runtime_attestation=runtime(impl="8" * 64)),
            dict(workload_identity=workload(), runtime_attestation=runtime(digest="7" * 64)),
        )
        for case in cases:
            with self.subTest(case=case), self.assertRaises(VerifierExecutionAdmissionError):
                gate().admit(attestation(), semantic_evidence_digest=SEMANTIC, now=NOW, **case)

    def test_wrong_exact_target_binding_denied(self):
        for changed in (
            target(repository="Other/repo"), target(pr_number=45), target(base_sha="5" * 40),
            target(head_sha="6" * 40), target(tree_sha="7" * 40), target(ci_run_id="999"),
        ):
            with self.subTest(target=changed), self.assertRaises(VerifierExecutionAdmissionError):
                gate().admit(attestation(target=changed), workload_identity=workload(), runtime_attestation=runtime(), semantic_evidence_digest=SEMANTIC, now=NOW)

    def test_evidence_bundle_mismatch_denied(self):
        with self.assertRaises(VerifierExecutionAdmissionError):
            gate().admit(attestation(evidence_bundle_digest="9" * 64), workload_identity=workload(), runtime_attestation=runtime(), semantic_evidence_digest=SEMANTIC, now=NOW)
        with self.assertRaises(VerifierExecutionAdmissionError):
            gate().admit(attestation(), workload_identity=workload(), runtime_attestation=runtime(), semantic_evidence_digest="8" * 64, now=NOW)

    def test_stale_future_and_replay_denied(self):
        stale = attestation(issued_at="2026-08-21T10:00:00+00:00", expires_at="2026-08-21T11:00:00+00:00")
        future = attestation(issued_at="2026-08-21T12:30:00+00:00", expires_at="2026-08-21T13:30:00+00:00")
        for value in (stale, future):
            with self.subTest(attestation=value.attestation_id), self.assertRaises(VerifierExecutionAdmissionError):
                gate().admit(value, workload_identity=workload(), runtime_attestation=runtime(), semantic_evidence_digest=SEMANTIC, now=NOW)
        replay = InMemoryVerifierExecutionReplayGuard()
        g = gate(replay=replay)
        value = attestation()
        g.admit(value, workload_identity=workload(), runtime_attestation=runtime(), semantic_evidence_digest=SEMANTIC, now=NOW)
        with self.assertRaises(VerifierExecutionAdmissionError):
            g.admit(value, workload_identity=workload(), runtime_attestation=runtime(), semantic_evidence_digest=SEMANTIC, now=NOW)

    def test_thread_role_ci_success_and_self_declaration_are_not_inputs(self):
        params = VerifierExecutionAdmission.admit.__code__.co_varnames[:VerifierExecutionAdmission.admit.__code__.co_argcount]
        self.assertNotIn("thread_role", params)
        self.assertNotIn("ci_success", params)
        self.assertNotIn("declared_role", params)

    def test_admission_has_no_authority_or_repository_mutation_surface(self):
        public = {name for name in dir(gate()) if not name.startswith("_")}
        self.assertEqual(public, {"admit"})
        forbidden = {"merge", "update_ref", "create_branch", "grant_authority", "consume_authority", "write"}
        self.assertTrue(public.isdisjoint(forbidden))


if __name__ == "__main__":
    unittest.main()
