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
)

NOW = datetime(2026, 8, 20, 15, 0, tzinfo=timezone.utc)
ARTIFACT = b"verified-executor-bytes-v1"
ARTIFACT_DIGEST = hashlib.sha256(ARTIFACT).hexdigest()
AUTH = "a" * 64
COMMIT = "1" * 40
TREE = "2" * 40
WORKFLOW_SHA = "3" * 40


def attestation(**changes) -> RuntimeAttestation:
    base = RuntimeAttestation(
        schema_version="1.0.0",
        attestation_id="att-1",
        subject_id="github-actions:job:n2-a",
        repository="DonkeyJJLove/ai_platform",
        repository_id="1102142315",
        commit_sha=COMMIT,
        tree_sha=TREE,
        workflow_ref="DonkeyJJLove/ai_platform/.github/workflows/fleet-attestation-n2.yml@refs/heads/mission/lion-fleet-control-plane-v0",
        workflow_sha=WORKFLOW_SHA,
        run_id="32390000000",
        run_attempt=1,
        runner_environment="github-hosted",
        runtime_instance_id="runtime-a",
        mission_id="LION-FLEET-EXECUTOR-ATTESTATION-V1",
        authority_digest=AUTH,
        artifact_digest=ARTIFACT_DIGEST,
        issuer="https://token.actions.githubusercontent.com",
        provenance_ref="github-attestation:att-1",
        issued_at="2026-08-20T14:59:00+00:00",
        expires_at="2026-08-20T15:10:00+00:00",
    )
    return replace(base, **changes)


def context() -> RuntimeAttestationContext:
    item = attestation()
    return RuntimeAttestationContext(
        repository=item.repository,
        repository_id=item.repository_id,
        commit_sha=item.commit_sha,
        tree_sha=item.tree_sha,
        workflow_ref=item.workflow_ref,
        workflow_sha=item.workflow_sha,
        run_id=item.run_id,
        run_attempt=item.run_attempt,
        mission_id=item.mission_id,
        authority_digest=item.authority_digest,
        issuer=item.issuer,
    )


class AnchoredBackend:
    def __init__(self, item: RuntimeAttestation) -> None:
        self.expected = item

    def verify_external(self, item: RuntimeAttestation) -> ExternalAttestationEvidence:
        if item.digest() != self.expected.digest():
            raise ValueError("external signature/provenance mismatch")
        return ExternalAttestationEvidence(
            attestation_digest=item.digest(),
            subject_id=item.subject_id,
            runtime_instance_id=item.runtime_instance_id,
            repository=item.repository,
            commit_sha=item.commit_sha,
            workflow_sha=item.workflow_sha,
            run_id=item.run_id,
            run_attempt=item.run_attempt,
            mission_id=item.mission_id,
            authority_digest=item.authority_digest,
            artifact_digest=item.artifact_digest,
            issuer=item.issuer,
            provenance_ref=item.provenance_ref,
            trust_anchor_id="github-artifact-attestation-root",
        )


class RuntimeAttestationTests(unittest.TestCase):
    def verifier(self, item: RuntimeAttestation | None = None) -> RuntimeAttestationVerifier:
        item = item or attestation()
        return RuntimeAttestationVerifier(
            external_verifier=AnchoredBackend(item),
            replay_guard=InMemoryRuntimeReplayGuard(),
        )

    def test_valid_attestation_binds_real_artifact_bytes(self) -> None:
        verified = self.verifier().verify(attestation(), artifact_bytes=ARTIFACT, now=NOW, context=context())
        self.assertEqual(verified.implementation_digest, ARTIFACT_DIGEST)

    def test_self_declared_wrong_implementation_digest_cannot_override_real_bytes(self) -> None:
        item = attestation(artifact_digest="f" * 64)
        with self.assertRaises(RuntimeAttestationVerificationError):
            self.verifier(item).verify(item, artifact_bytes=ARTIFACT, now=NOW, context=replace(context(), authority_digest=AUTH))

    def test_forged_attestation_payload_denied(self) -> None:
        trusted = attestation()
        forged = replace(trusted, repository="DonkeyJJLove/other")
        with self.assertRaises(RuntimeAttestationVerificationError):
            self.verifier(trusted).verify(forged, artifact_bytes=ARTIFACT, now=NOW, context=context())

    def test_wrong_repository_id_denied(self) -> None:
        with self.assertRaises(RuntimeAttestationVerificationError):
            self.verifier().verify(attestation(repository_id="999"), artifact_bytes=ARTIFACT, now=NOW, context=context())

    def test_wrong_commit_denied(self) -> None:
        with self.assertRaises(RuntimeAttestationVerificationError):
            self.verifier().verify(attestation(commit_sha="4" * 40), artifact_bytes=ARTIFACT, now=NOW, context=context())

    def test_wrong_workflow_sha_denied(self) -> None:
        with self.assertRaises(RuntimeAttestationVerificationError):
            self.verifier().verify(attestation(workflow_sha="4" * 40), artifact_bytes=ARTIFACT, now=NOW, context=context())

    def test_wrong_run_id_denied(self) -> None:
        with self.assertRaises(RuntimeAttestationVerificationError):
            self.verifier().verify(attestation(run_id="evil"), artifact_bytes=ARTIFACT, now=NOW, context=context())

    def test_wrong_mission_denied(self) -> None:
        with self.assertRaises(RuntimeAttestationVerificationError):
            self.verifier().verify(attestation(mission_id="other"), artifact_bytes=ARTIFACT, now=NOW, context=context())

    def test_wrong_authority_denied(self) -> None:
        with self.assertRaises(RuntimeAttestationVerificationError):
            self.verifier().verify(attestation(authority_digest="b" * 64), artifact_bytes=ARTIFACT, now=NOW, context=context())

    def test_artifact_modified_after_attestation_denied(self) -> None:
        with self.assertRaises(RuntimeAttestationVerificationError):
            self.verifier().verify(attestation(), artifact_bytes=ARTIFACT + b"tamper", now=NOW, context=context())

    def test_replay_denied(self) -> None:
        item = attestation()
        verifier = self.verifier(item)
        verifier.verify(item, artifact_bytes=ARTIFACT, now=NOW, context=context())
        with self.assertRaises(RuntimeAttestationVerificationError):
            verifier.verify(item, artifact_bytes=ARTIFACT, now=NOW, context=context())

    def test_external_backend_failure_fails_closed(self) -> None:
        class Broken:
            def verify_external(self, item):
                raise RuntimeError("backend unavailable")
        verifier = RuntimeAttestationVerifier(external_verifier=Broken(), replay_guard=InMemoryRuntimeReplayGuard())
        with self.assertRaises(RuntimeAttestationVerificationError):
            verifier.verify(attestation(), artifact_bytes=ARTIFACT, now=NOW, context=context())


if __name__ == "__main__":
    unittest.main()
