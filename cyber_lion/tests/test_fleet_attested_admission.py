from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
import hashlib
import unittest

from cyber_lion.contracts.runtime_attestation import RuntimeAttestation, RuntimeAttestationContext
from cyber_lion.enterprise.runtime_attestation import (
    ExternalAttestationEvidence,
    InMemoryRuntimeReplayGuard,
    RuntimeAttestationVerificationError,
    RuntimeAttestationVerifier,
    verify_n2_pair,
)

NOW = datetime(2026, 8, 20, 15, 0, tzinfo=timezone.utc)
ARTIFACT = b"fleet-runtime-verifier-v1"
DIGEST = hashlib.sha256(ARTIFACT).hexdigest()
AUTH = "a" * 64
COMMIT = "1" * 40
TREE = "2" * 40
WORKFLOW = "3" * 40
MISSION = "LION-FLEET-EXECUTOR-ATTESTATION-V1"
REPO = "DonkeyJJLove/ai_platform"


def item(slot: str) -> RuntimeAttestation:
    return RuntimeAttestation(
        schema_version="1.0.0",
        attestation_id=f"att-{slot}",
        subject_id=f"github-actions:n2:{slot}",
        repository=REPO,
        repository_id="1102142315",
        commit_sha=COMMIT,
        tree_sha=TREE,
        workflow_ref="DonkeyJJLove/ai_platform/.github/workflows/fleet-attestation-n2.yml@refs/heads/mission/lion-fleet-control-plane-v0",
        workflow_sha=WORKFLOW,
        run_id="32390000000",
        run_attempt=1,
        runner_environment="github-hosted",
        runtime_instance_id=f"runtime-{slot}",
        mission_id=MISSION,
        authority_digest=AUTH,
        artifact_digest=DIGEST,
        issuer="https://token.actions.githubusercontent.com",
        provenance_ref=f"github-attestation:n2:{slot}",
        issued_at="2026-08-20T14:59:00+00:00",
        expires_at="2026-08-20T15:10:00+00:00",
    )


def ctx(value: RuntimeAttestation) -> RuntimeAttestationContext:
    return RuntimeAttestationContext(
        repository=value.repository,
        repository_id=value.repository_id,
        commit_sha=value.commit_sha,
        tree_sha=value.tree_sha,
        workflow_ref=value.workflow_ref,
        workflow_sha=value.workflow_sha,
        run_id=value.run_id,
        run_attempt=value.run_attempt,
        mission_id=value.mission_id,
        authority_digest=value.authority_digest,
        issuer=value.issuer,
    )


class ExactBackend:
    def __init__(self, expected: RuntimeAttestation) -> None:
        self.expected = expected

    def verify_external(self, value: RuntimeAttestation) -> ExternalAttestationEvidence:
        if value.digest() != self.expected.digest():
            raise ValueError("attestation not externally anchored")
        return ExternalAttestationEvidence(
            attestation_digest=value.digest(),
            subject_id=value.subject_id,
            runtime_instance_id=value.runtime_instance_id,
            repository=value.repository,
            commit_sha=value.commit_sha,
            workflow_sha=value.workflow_sha,
            run_id=value.run_id,
            run_attempt=value.run_attempt,
            mission_id=value.mission_id,
            authority_digest=value.authority_digest,
            artifact_digest=value.artifact_digest,
            issuer=value.issuer,
            provenance_ref=value.provenance_ref,
            trust_anchor_id="github-artifact-attestation-root",
        )


def verified(value: RuntimeAttestation):
    verifier = RuntimeAttestationVerifier(
        external_verifier=ExactBackend(value),
        replay_guard=InMemoryRuntimeReplayGuard(),
    )
    return verifier.verify(value, artifact_bytes=ARTIFACT, now=NOW, context=ctx(value))


class AttestedN2Tests(unittest.TestCase):
    def test_two_distinct_verified_runtime_records_form_candidate_N2_evidence(self) -> None:
        first, second = verify_n2_pair(verified(item("a")), verified(item("b")))
        self.assertNotEqual(first.runtime_instance_id, second.runtime_instance_id)
        self.assertNotEqual(first.attestation_digest, second.attestation_digest)

    def test_one_executor_presented_as_two_denied(self) -> None:
        first = verified(item("a"))
        second_claim = replace(item("b"), runtime_instance_id="runtime-a")
        second = verified(second_claim)
        with self.assertRaises(RuntimeAttestationVerificationError):
            verify_n2_pair(first, second)

    def test_duplicate_runtime_evidence_denied(self) -> None:
        first = verified(item("a"))
        with self.assertRaises(RuntimeAttestationVerificationError):
            verify_n2_pair(first, first)

    def test_duplicate_provenance_reference_denied(self) -> None:
        first = verified(item("a"))
        second = verified(replace(item("b"), provenance_ref=first.provenance_ref))
        with self.assertRaises(RuntimeAttestationVerificationError):
            verify_n2_pair(first, second)

    def test_same_artifact_digest_does_not_by_itself_prove_or_disprove_N2(self) -> None:
        first, second = verify_n2_pair(verified(item("a")), verified(item("b")))
        self.assertEqual(first.artifact_digest, second.artifact_digest)
        self.assertNotEqual(first.runtime_instance_id, second.runtime_instance_id)

    def test_wrong_commit_breaks_common_mission_evidence(self) -> None:
        first = verified(item("a"))
        altered = replace(item("b"), commit_sha="4" * 40)
        second = verified(altered)
        with self.assertRaises(RuntimeAttestationVerificationError):
            verify_n2_pair(first, second)

    def test_wrong_authority_breaks_common_mission_evidence(self) -> None:
        first = verified(item("a"))
        altered = replace(item("b"), authority_digest="b" * 64)
        second = verified(altered)
        with self.assertRaises(RuntimeAttestationVerificationError):
            verify_n2_pair(first, second)


if __name__ == "__main__":
    unittest.main()
