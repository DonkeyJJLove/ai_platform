"""Adapter-neutral runtime attestation contract for fleet execution evidence."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import re

_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_REPO = re.compile(r"^[^/\s]+/[^/\s]+$")


class RuntimeAttestationError(ValueError):
    """Raised when runtime attestation evidence is malformed or ambiguous."""


def _text(value: object, name: str, limit: int = 512) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > limit or "\x00" in value:
        raise RuntimeAttestationError(f"{name} is invalid")
    return value


def _utc(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, ValueError) as exc:
        raise RuntimeAttestationError("attestation timestamp is invalid") from exc
    if parsed.tzinfo is None:
        raise RuntimeAttestationError("attestation timestamps must be timezone-aware")
    return parsed.astimezone(timezone.utc)


@dataclass(frozen=True)
class RuntimeAttestation:
    """Untrusted runtime claim bundle. It is never admission evidence by itself."""

    schema_version: str
    attestation_id: str
    subject_id: str
    repository: str
    repository_id: str
    commit_sha: str
    tree_sha: str
    workflow_ref: str
    workflow_sha: str
    run_id: str
    run_attempt: int
    runner_environment: str
    runtime_instance_id: str
    mission_id: str
    authority_digest: str
    artifact_digest: str
    issuer: str
    provenance_ref: str
    issued_at: str
    expires_at: str

    def validate(self) -> "RuntimeAttestation":
        if self.schema_version != "1.0.0":
            raise RuntimeAttestationError("unsupported runtime attestation schema_version")
        for name in (
            "attestation_id", "subject_id", "repository", "repository_id", "workflow_ref",
            "run_id", "runner_environment", "runtime_instance_id", "mission_id", "issuer",
            "provenance_ref", "issued_at", "expires_at",
        ):
            _text(getattr(self, name), name)
        if not _REPO.fullmatch(self.repository):
            raise RuntimeAttestationError("repository must use owner/name form")
        for name in ("commit_sha", "tree_sha", "workflow_sha"):
            value = _text(getattr(self, name), name, 40)
            if not _SHA40.fullmatch(value):
                raise RuntimeAttestationError(f"{name} must be a full lowercase git SHA")
        for name in ("authority_digest", "artifact_digest"):
            value = _text(getattr(self, name), name, 64)
            if not _SHA256.fullmatch(value):
                raise RuntimeAttestationError(f"{name} must be sha256 hex")
        if isinstance(self.run_attempt, bool) or not isinstance(self.run_attempt, int) or self.run_attempt < 1:
            raise RuntimeAttestationError("run_attempt must be a positive integer")
        if _utc(self.issued_at) >= _utc(self.expires_at):
            raise RuntimeAttestationError("attestation validity window is invalid")
        return self

    def canonical_payload(self) -> bytes:
        self.validate()
        payload = {
            "artifact_digest": self.artifact_digest,
            "attestation_id": self.attestation_id,
            "authority_digest": self.authority_digest,
            "commit_sha": self.commit_sha,
            "expires_at": self.expires_at,
            "issued_at": self.issued_at,
            "issuer": self.issuer,
            "mission_id": self.mission_id,
            "provenance_ref": self.provenance_ref,
            "repository": self.repository,
            "repository_id": self.repository_id,
            "run_attempt": self.run_attempt,
            "run_id": self.run_id,
            "runner_environment": self.runner_environment,
            "runtime_instance_id": self.runtime_instance_id,
            "schema_version": self.schema_version,
            "subject_id": self.subject_id,
            "tree_sha": self.tree_sha,
            "workflow_ref": self.workflow_ref,
            "workflow_sha": self.workflow_sha,
        }
        return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")

    def digest(self) -> str:
        return hashlib.sha256(self.canonical_payload()).hexdigest()


@dataclass(frozen=True)
class RuntimeAttestationContext:
    repository: str
    repository_id: str
    commit_sha: str
    tree_sha: str
    workflow_ref: str
    workflow_sha: str
    run_id: str
    run_attempt: int
    mission_id: str
    authority_digest: str
    issuer: str

    def binding(self) -> tuple[object, ...]:
        return (
            self.repository, self.repository_id, self.commit_sha, self.tree_sha,
            self.workflow_ref, self.workflow_sha, self.run_id, self.run_attempt,
            self.mission_id, self.authority_digest, self.issuer,
        )
