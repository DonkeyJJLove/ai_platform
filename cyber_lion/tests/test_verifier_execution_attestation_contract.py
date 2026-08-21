from __future__ import annotations

from dataclasses import FrozenInstanceError
import unittest

from cyber_lion.contracts.verifier_execution_attestation import (
    ExactVerificationTarget,
    ExecutorParticipationRecord,
    TrustedParticipationHistory,
    VerifierExecutionAttestation,
    VerifierExecutionAttestationError,
    evidence_bundle_digest,
)


H = "a" * 40
T = "b" * 40
D = "c" * 64
D2 = "d" * 64
D3 = "e" * 64
D4 = "f" * 64


def target(**overrides):
    values = dict(
        repository="DonkeyJJLove/ai_platform",
        pr_number=44,
        base_sha="1" * 40,
        head_sha=H,
        tree_sha=T,
        ci_run_id="32477275518",
        mission_id="LION-FLEET-CANONICAL-STATUS-REGISTRY-P0",
        slice_id="STATUS-SOURCE-ADAPTERS-R2",
    )
    values.update(overrides)
    return ExactVerificationTarget(**values)


def record(role="BUILDER", subject="builder", runtime="builder-runtime"):
    return ExecutorParticipationRecord(
        subject_id=subject,
        runtime_instance_id=runtime,
        participation_role=role,
        repository="DonkeyJJLove/ai_platform",
        mission_id="LION-FLEET-CANONICAL-STATUS-REGISTRY-P0",
        target_head_sha=H,
        target_tree_sha=T,
        provenance_ref=f"trusted:{role}:{subject}",
        evidence_digest=D,
        trust_anchor_id="history-root",
        observed_at="2026-08-21T12:00:00+00:00",
    )


class VerifierExecutionAttestationContractTests(unittest.TestCase):
    def test_exact_target_is_immutable_and_digest_stable(self):
        value = target().validate()
        self.assertEqual(value.digest(), target().digest())
        with self.assertRaises(FrozenInstanceError):
            value.pr_number = 45

    def test_target_rejects_wrong_shapes(self):
        for kwargs in (
            {"repository": "bad"},
            {"pr_number": 0},
            {"base_sha": "abc"},
            {"head_sha": "ABC" + "0" * 37},
            {"tree_sha": "x" * 40},
            {"ci_run_id": ""},
        ):
            with self.subTest(kwargs=kwargs), self.assertRaises(VerifierExecutionAttestationError):
                target(**kwargs).validate()

    def test_participation_record_is_exact_and_role_bounded(self):
        record().validate()
        record("VERIFICATION_ATTACH").validate()
        with self.assertRaises(VerifierExecutionAttestationError):
            record("OWNER").validate()

    def test_history_digest_detects_tampering(self):
        history = TrustedParticipationHistory.build(
            source_id="trusted-history",
            trust_anchor_id="history-root",
            source_implementation_digest=D2,
            observed_at="2026-08-21T12:10:00+00:00",
            records=(record(), record("VERIFICATION_ATTACH", "attach", "attach-runtime")),
        )
        history.validate()
        bad = TrustedParticipationHistory(
            history.source_id,
            history.trust_anchor_id,
            history.source_implementation_digest,
            history.observed_at,
            history.records,
            D3,
        )
        with self.assertRaises(VerifierExecutionAttestationError):
            bad.validate()

    def test_history_rejects_duplicate_records(self):
        r = record()
        with self.assertRaises(VerifierExecutionAttestationError):
            TrustedParticipationHistory.build(
                source_id="trusted-history",
                trust_anchor_id="history-root",
                source_implementation_digest=D2,
                observed_at="2026-08-21T12:10:00+00:00",
                records=(r, r),
            )

    def test_evidence_bundle_binds_every_required_digest(self):
        first = evidence_bundle_digest(
            target=target(),
            workload_identity_proof_digest=D,
            runtime_attestation_digest=D2,
            verifier_implementation_digest=D3,
            participation_history_digest=D4,
            semantic_evidence_digest="0" * 64,
        )
        second = evidence_bundle_digest(
            target=target(pr_number=45),
            workload_identity_proof_digest=D,
            runtime_attestation_digest=D2,
            verifier_implementation_digest=D3,
            participation_history_digest=D4,
            semantic_evidence_digest="0" * 64,
        )
        self.assertNotEqual(first, second)

    def test_attestation_requires_valid_window_and_exact_types(self):
        history = TrustedParticipationHistory.build(
            source_id="trusted-history",
            trust_anchor_id="history-root",
            source_implementation_digest=D2,
            observed_at="2026-08-21T12:10:00+00:00",
            records=(record(), record("VERIFICATION_ATTACH", "attach", "attach-runtime")),
        )
        bundle = evidence_bundle_digest(
            target=target(),
            workload_identity_proof_digest=D,
            runtime_attestation_digest=D2,
            verifier_implementation_digest=D3,
            participation_history_digest=history.history_digest,
            semantic_evidence_digest="0" * 64,
        )
        value = VerifierExecutionAttestation(
            attestation_id="vea-1",
            verifier_subject_id="verifier",
            verifier_runtime_instance_id="runtime-verifier",
            verifier_implementation_digest=D3,
            workload_identity_proof_digest=D,
            runtime_attestation_digest=D2,
            target=target(),
            participation_history_digest=history.history_digest,
            evidence_bundle_digest=bundle,
            verification_result="PASS",
            external_attestation_ref="external:vea-1",
            issued_at="2026-08-21T12:00:00+00:00",
            expires_at="2026-08-21T13:00:00+00:00",
        )
        value.validate()
        self.assertEqual(value.digest(), value.digest())
        with self.assertRaises(VerifierExecutionAttestationError):
            VerifierExecutionAttestation(**{**value.__dict__, "expires_at": value.issued_at}).validate()


if __name__ == "__main__":
    unittest.main()
