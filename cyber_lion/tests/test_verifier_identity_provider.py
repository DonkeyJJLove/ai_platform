from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import unittest

from cyber_lion.contracts.runtime_attestation import RuntimeAttestation
from cyber_lion.contracts.verifier_execution_attestation import (
    ExactVerificationTarget,
    ExecutorParticipationRecord,
    FixedSourcePin,
    TrustedParticipationHistory,
)
from cyber_lion.contracts.workload_identity import WorkloadIdentityProof
from cyber_lion.enterprise.runtime_attestation import (
    ExternalAttestationEvidence,
    InMemoryRuntimeReplayGuard,
    RuntimeAttestationVerifier,
)
from cyber_lion.enterprise.verifier_identity_provider import (
    RawRuntimeEvidence,
    RealVerifierParticipationSource,
    RealVerifierRuntimeAttestationSource,
    RealVerifierWorkloadIdentitySource,
    VerifierIdentityProviderError,
)

BASE = "1" * 40
HEAD = "2" * 40
TREE = "3" * 40
WORKFLOW = "4" * 40
MISSION = "LION-FLEET-CANONICAL-STATUS-REGISTRY-P0"
NOW = datetime(2026, 8, 21, 12, 30, tzinfo=timezone.utc)
ARTIFACT = b"real verifier implementation"
ARTIFACT_DIGEST = hashlib.sha256(ARTIFACT).hexdigest()


def target() -> ExactVerificationTarget:
    return ExactVerificationTarget(
        "DonkeyJJLove/ai_platform", 45, BASE, HEAD, TREE, "ci-1", MISSION, "VEA-B1"
    ).validate()


def pin(kind: str) -> FixedSourcePin:
    return FixedSourcePin(kind, kind + "-instance", "a" * 64, kind + "-root").validate()


def proof(*, issuer="issuer", repo="DonkeyJJLove/ai_platform", ref=HEAD,
          issued="2026-08-21T12:00:00+00:00", expires="2026-08-21T13:00:00+00:00"):
    return WorkloadIdentityProof(
        "1.0.0", "proof-1", "verifier-subject", "lion", "tenant", "org", "final-verifier",
        "prod", repo, ref, issuer, "key-1", "test", issued, expires, "sig",
    ).validate()


class Provider:
    def __init__(self, value): self.value = value
    def resolve(self, exact_target): return self.value


class WorkloadTests(unittest.TestCase):
    def source(self, value=None, verifier=lambda *_: True):
        return RealVerifierWorkloadIdentitySource(
            pin=pin("workload"), raw_provider=Provider(value or proof()),
            signature_verifier=verifier, clock=lambda: NOW,
            trust_domain="lion", tenant_id="tenant", organization_id="org",
            audience="final-verifier", environment="prod", issuer_id="issuer",
        )

    def test_valid_raw_proof_is_verified(self):
        result = self.source().resolve(target())
        self.assertEqual(result.subject_id, "verifier-subject")
        self.assertEqual(result.proof_digest, proof().digest())

    def test_provider_cannot_return_verified_object_or_wrong_type(self):
        with self.assertRaises(VerifierIdentityProviderError):
            self.source(value=object()).resolve(target())

    def test_wrong_repo_ref_issuer_and_expiry_deny(self):
        cases = (
            proof(repo="Other/repo"), proof(ref="9" * 40), proof(issuer="other"),
            proof(expires="2026-08-21T12:20:00+00:00"),
            proof(issued="2026-08-21T12:40:00+00:00", expires="2026-08-21T13:00:00+00:00"),
        )
        for value in cases:
            with self.subTest(value=value.proof_id), self.assertRaises(VerifierIdentityProviderError):
                self.source(value=value).resolve(target())

    def test_forged_signature_and_verifier_failure_deny(self):
        with self.assertRaises(VerifierIdentityProviderError):
            self.source(verifier=lambda *_: False).resolve(target())
        def boom(*_): raise RuntimeError("verifier down")
        with self.assertRaises(VerifierIdentityProviderError):
            self.source(verifier=boom).resolve(target())


def runtime_attestation(*, subject="verifier-subject", runtime="runtime-1", repo="DonkeyJJLove/ai_platform",
                        commit=HEAD, tree=TREE, mission=MISSION, issuer="runtime-issuer",
                        artifact_digest=ARTIFACT_DIGEST):
    return RuntimeAttestation(
        "1.0.0", "att-1", subject, repo, "repo-id", commit, tree,
        "workflow/ref", WORKFLOW, "run-1", 1, "github-hosted", runtime, mission,
        artifact_digest, issuer, "external:runtime", "2026-08-21T12:00:00+00:00",
        "2026-08-21T13:00:00+00:00",
    ).validate()


class ExternalVerifier:
    def verify_external(self, att):
        return ExternalAttestationEvidence(
            att.digest(), att.subject_id, att.runtime_instance_id, att.repository, att.commit_sha,
            att.workflow_sha, att.run_id, att.run_attempt, att.mission_id, att.artifact_digest,
            att.issuer, att.provenance_ref, "external-root",
        )


class RuntimeTests(unittest.TestCase):
    def source(self, raw=None, external=None, clock=lambda: NOW):
        verifier = RuntimeAttestationVerifier(
            external_verifier=external or ExternalVerifier(), replay_guard=InMemoryRuntimeReplayGuard()
        )
        return RealVerifierRuntimeAttestationSource(
            pin=pin("runtime"), raw_provider=Provider(raw or RawRuntimeEvidence(runtime_attestation(), ARTIFACT)),
            verifier=verifier, clock=clock, expected_issuer="runtime-issuer",
        )

    def test_valid_external_runtime_is_verified_from_real_bytes(self):
        result = self.source().resolve(target())
        self.assertEqual(result.subject_id, "verifier-subject")
        self.assertEqual(result.runtime_instance_id, "runtime-1")
        self.assertEqual(result.implementation_digest, ARTIFACT_DIGEST)

    def test_wrong_target_or_artifact_denied(self):
        cases = (
            RawRuntimeEvidence(runtime_attestation(repo="Other/repo"), ARTIFACT),
            RawRuntimeEvidence(runtime_attestation(commit="8" * 40), ARTIFACT),
            RawRuntimeEvidence(runtime_attestation(tree="7" * 40), ARTIFACT),
            RawRuntimeEvidence(runtime_attestation(mission="other"), ARTIFACT),
            RawRuntimeEvidence(runtime_attestation(issuer="other"), ARTIFACT),
            RawRuntimeEvidence(runtime_attestation(), b"tampered"),
        )
        for raw in cases:
            with self.assertRaises(VerifierIdentityProviderError):
                self.source(raw=raw).resolve(target())

    def test_external_attester_failure_denies(self):
        class Bad:
            def verify_external(self, att): raise RuntimeError("down")
        with self.assertRaises(VerifierIdentityProviderError):
            self.source(external=Bad()).resolve(target())

    def test_runtime_replay_denied(self):
        verifier = RuntimeAttestationVerifier(
            external_verifier=ExternalVerifier(), replay_guard=InMemoryRuntimeReplayGuard()
        )
        source = RealVerifierRuntimeAttestationSource(
            pin=pin("runtime"), raw_provider=Provider(RawRuntimeEvidence(runtime_attestation(), ARTIFACT)),
            verifier=verifier, clock=lambda: NOW, expected_issuer="runtime-issuer",
        )
        source.resolve(target())
        with self.assertRaises(VerifierIdentityProviderError):
            source.resolve(target())


def participation(role, subject, runtime):
    return ExecutorParticipationRecord(
        subject, runtime, role, "DonkeyJJLove/ai_platform", MISSION, HEAD, TREE,
        f"external:{role}:{subject}", "b" * 64, "history-root", "2026-08-21T12:00:00+00:00"
    ).validate()


def history(records):
    p = pin("participation")
    return TrustedParticipationHistory.build(
        source_id=p.source_id, source_instance_id=p.source_instance_id,
        trust_anchor_id=p.trust_anchor_id, source_implementation_digest=p.source_implementation_digest,
        observed_at="2026-08-21T12:10:00+00:00", records=tuple(records),
    )


class ParticipationTests(unittest.TestCase):
    def test_exact_builder_and_attach_history_passes(self):
        value = history((participation("BUILDER", "builder", "br"), participation("VERIFICATION_ATTACH", "attach", "ar")))
        result = RealVerifierParticipationSource(pin=pin("participation"), raw_provider=Provider(value)).resolve(target())
        self.assertEqual(result.history_digest, value.history_digest)

    def test_missing_or_ambiguous_history_denied(self):
        cases = (
            history((participation("BUILDER", "builder", "br"),)),
            history((participation("VERIFICATION_ATTACH", "attach", "ar"),)),
            history((participation("BUILDER", "b1", "br1"), participation("BUILDER", "b2", "br2"), participation("VERIFICATION_ATTACH", "a", "ar"))),
            history((participation("BUILDER", "b", "br"), participation("VERIFICATION_ATTACH", "a1", "ar1"), participation("VERIFICATION_ATTACH", "a2", "ar2"))),
        )
        for value in cases:
            with self.assertRaises(VerifierIdentityProviderError):
                RealVerifierParticipationSource(pin=pin("participation"), raw_provider=Provider(value)).resolve(target())


if __name__ == "__main__":
    unittest.main()
