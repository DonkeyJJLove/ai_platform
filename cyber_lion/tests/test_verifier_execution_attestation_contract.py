from __future__ import annotations

from dataclasses import FrozenInstanceError
import unittest

from cyber_lion.contracts.verifier_execution_attestation import (
    ExactVerificationTarget,
    ExecutorParticipationRecord,
    FixedSourcePin,
    TrustedCIEvidence,
    TrustedParticipationHistory,
    TrustedSemanticVerificationResult,
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
D5 = "0" * 64


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


def pin(name="source"):
    return FixedSourcePin(name, f"{name}-instance", D2, f"{name}-root").validate()


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


def history():
    p = pin("history")
    return TrustedParticipationHistory.build(
        source_id=p.source_id,
        source_instance_id=p.source_instance_id,
        trust_anchor_id=p.trust_anchor_id,
        source_implementation_digest=p.source_implementation_digest,
        observed_at="2026-08-21T12:10:00+00:00",
        records=(record(), record("VERIFICATION_ATTACH", "attach", "attach-runtime")),
    )


def ci():
    p = pin("ci")
    return TrustedCIEvidence(
        p.source_id, p.source_instance_id, p.source_implementation_digest, p.trust_anchor_id,
        "DonkeyJJLove/ai_platform", 44, "1" * 40, H, T, "32477275518",
        "Cyber-Lion Core", "SUCCESS", "2026-08-21T12:11:00+00:00",
        "github:run:32477275518", D3,
    ).validate()


def semantic():
    p = pin("semantic")
    return TrustedSemanticVerificationResult(
        p.source_id, p.source_instance_id, p.source_implementation_digest, p.trust_anchor_id,
        "sem-44", "verifier-subject", "verifier-runtime", D4,
        target().digest(), D5, "PASS", "2026-08-21T12:12:00+00:00",
        "semantic:verified:44", D3,
    ).validate()


class ContractTests(unittest.TestCase):
    def test_target_exact_and_immutable(self):
        value = target().validate()
        self.assertEqual(value.digest(), target().digest())
        with self.assertRaises(FrozenInstanceError):
            value.pr_number = 45

    def test_target_rejects_wrong_shapes(self):
        for kwargs in (
            {"repository": "bad"}, {"pr_number": 0}, {"base_sha": "abc"},
            {"head_sha": "ABC" + "0" * 37}, {"tree_sha": "x" * 40}, {"ci_run_id": ""},
        ):
            with self.subTest(kwargs=kwargs), self.assertRaises(VerifierExecutionAttestationError):
                target(**kwargs).validate()

    def test_source_pin_is_exact(self):
        pin().validate()
        with self.assertRaises(VerifierExecutionAttestationError):
            FixedSourcePin("x", "i", "bad", "root").validate()

    def test_history_digest_detects_tampering(self):
        value = history()
        bad = TrustedParticipationHistory(
            value.source_id, value.source_instance_id, value.trust_anchor_id,
            value.source_implementation_digest, value.observed_at, value.records, D3,
        )
        with self.assertRaises(VerifierExecutionAttestationError):
            bad.validate()

    def test_ci_evidence_is_typed_and_digestable(self):
        value = ci()
        self.assertEqual(value.conclusion, "SUCCESS")
        with self.assertRaises(VerifierExecutionAttestationError):
            TrustedCIEvidence(**{**value.__dict__, "conclusion": "GREEN"}).validate()

    def test_semantic_result_is_typed_and_digestable(self):
        value = semantic()
        self.assertEqual(value.result, "PASS")
        with self.assertRaises(VerifierExecutionAttestationError):
            TrustedSemanticVerificationResult(**{**value.__dict__, "result": "GREEN"}).validate()

    def test_attestation_has_no_self_declared_result_or_external_ref(self):
        fields = VerifierExecutionAttestation.__dataclass_fields__
        self.assertNotIn("verification_result", fields)
        self.assertNotIn("external_attestation_ref", fields)

    def test_evidence_bundle_binds_ci_and_semantic_results(self):
        h = history()
        c = ci()
        s = semantic()
        first = evidence_bundle_digest(
            target=target(),
            workload_identity_proof_digest=D,
            runtime_attestation_digest=D2,
            verifier_implementation_digest=D4,
            participation_history_digest=h.history_digest,
            ci_evidence_digest=c.digest(),
            semantic_verification_result_digest=s.digest(),
        )
        second = evidence_bundle_digest(
            target=target(),
            workload_identity_proof_digest=D,
            runtime_attestation_digest=D2,
            verifier_implementation_digest=D4,
            participation_history_digest=h.history_digest,
            ci_evidence_digest="9" * 64,
            semantic_verification_result_digest=s.digest(),
        )
        self.assertNotEqual(first, second)


if __name__ == "__main__":
    unittest.main()
