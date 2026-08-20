"""Immutable post-execution binding between runtime evidence and canonical authority."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re

_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_REPO = re.compile(r"^[^/\s]+/[^/\s]+$")


class RuntimeAuthorityBindingError(ValueError):
    """Raised when runtime/authority binding evidence is malformed or ambiguous."""


def _text(value: object, name: str, limit: int = 512) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > limit or "\x00" in value:
        raise RuntimeAuthorityBindingError(f"{name} is invalid")
    return value


def _sha40(value: object, name: str) -> str:
    value = _text(value, name, 40)
    if not _SHA40.fullmatch(value):
        raise RuntimeAuthorityBindingError(f"{name} must be full lowercase git SHA")
    return value


def _sha256(value: object, name: str) -> str:
    value = _text(value, name, 64)
    if not _SHA256.fullmatch(value):
        raise RuntimeAuthorityBindingError(f"{name} must be sha256 hex")
    return value


@dataclass(frozen=True)
class RuntimeEvidenceReference:
    """Reference to immutable, externally produced runtime evidence; never authority."""

    runtime_evidence_digest: str
    runtime_instance_id: str
    repository: str
    base_sha: str
    head_sha: str
    run_id: str
    run_attempt: int
    provenance_ref: str
    artifact_digest: str
    mission_id: str

    def validate(self) -> "RuntimeEvidenceReference":
        _sha256(self.runtime_evidence_digest, "runtime_evidence_digest")
        _sha256(self.artifact_digest, "artifact_digest")
        _sha40(self.base_sha, "base_sha")
        _sha40(self.head_sha, "head_sha")
        for name in ("runtime_instance_id", "run_id", "provenance_ref", "mission_id"):
            _text(getattr(self, name), name)
        if not isinstance(self.repository, str) or not _REPO.fullmatch(self.repository):
            raise RuntimeAuthorityBindingError("repository must use owner/name form")
        if isinstance(self.run_attempt, bool) or not isinstance(self.run_attempt, int) or self.run_attempt < 1:
            raise RuntimeAuthorityBindingError("run_attempt must be a positive integer")
        return self

    def binding(self) -> tuple[object, ...]:
        self.validate()
        return (
            self.runtime_evidence_digest,
            self.runtime_instance_id,
            self.repository,
            self.base_sha,
            self.head_sha,
            self.run_id,
            self.run_attempt,
            self.provenance_ref,
            self.artifact_digest,
            self.mission_id,
        )


@dataclass(frozen=True)
class AuthorityAttestationBinding:
    """Canonical linearized authority admission bound after execution to runtime evidence."""

    schema_version: str
    binding_id: str
    binding_nonce: str
    mission_id: str
    repository: str
    pr_number: int
    base_sha: str
    head_sha: str
    runtime_evidence_digest: str
    runtime_instance_id: str
    run_id: str
    run_attempt: int
    provenance_ref: str
    artifact_digest: str
    grant_id: str
    authority_lineage_digest: str
    authenticated_grant_digest: str
    authority_epoch: int
    authority_provenance_id: str
    authority_key_id: str
    authority_algorithm: str
    live_admission_digest: str
    live_admission_replay_digest: str
    authority_state_version: int
    authority_root_grant_digest: str
    authority_admitted_at: str
    live_finalization_digest: str
    live_finalization_key_digest: str
    authority_finalized_at: str

    def validate(self) -> "AuthorityAttestationBinding":
        if self.schema_version != "1.2.0":
            raise RuntimeAuthorityBindingError("unsupported binding schema_version")
        for name in (
            "binding_id", "binding_nonce", "mission_id", "runtime_instance_id", "run_id",
            "provenance_ref", "grant_id", "authority_provenance_id", "authority_key_id",
            "authority_algorithm", "authority_admitted_at", "authority_finalized_at",
        ):
            _text(getattr(self, name), name)
        if not isinstance(self.repository, str) or not _REPO.fullmatch(self.repository):
            raise RuntimeAuthorityBindingError("repository must use owner/name form")
        if isinstance(self.pr_number, bool) or not isinstance(self.pr_number, int) or self.pr_number < 1:
            raise RuntimeAuthorityBindingError("pr_number must be positive")
        if isinstance(self.run_attempt, bool) or not isinstance(self.run_attempt, int) or self.run_attempt < 1:
            raise RuntimeAuthorityBindingError("run_attempt must be positive")
        if isinstance(self.authority_epoch, bool) or not isinstance(self.authority_epoch, int) or self.authority_epoch < 0:
            raise RuntimeAuthorityBindingError("authority_epoch must be non-negative")
        if (
            isinstance(self.authority_state_version, bool)
            or not isinstance(self.authority_state_version, int)
            or self.authority_state_version < 1
        ):
            raise RuntimeAuthorityBindingError("authority_state_version must be positive")
        _sha40(self.base_sha, "base_sha")
        _sha40(self.head_sha, "head_sha")
        for name in (
            "runtime_evidence_digest", "artifact_digest", "authority_lineage_digest",
            "authenticated_grant_digest", "live_admission_digest",
            "live_admission_replay_digest", "authority_root_grant_digest",
            "live_finalization_digest", "live_finalization_key_digest",
        ):
            _sha256(getattr(self, name), name)
        return self

    def canonical_payload(self) -> bytes:
        self.validate()
        payload = {
            "artifact_digest": self.artifact_digest,
            "authenticated_grant_digest": self.authenticated_grant_digest,
            "authority_admitted_at": self.authority_admitted_at,
            "authority_algorithm": self.authority_algorithm,
            "authority_epoch": self.authority_epoch,
            "authority_finalized_at": self.authority_finalized_at,
            "authority_key_id": self.authority_key_id,
            "authority_lineage_digest": self.authority_lineage_digest,
            "authority_provenance_id": self.authority_provenance_id,
            "authority_root_grant_digest": self.authority_root_grant_digest,
            "authority_state_version": self.authority_state_version,
            "base_sha": self.base_sha,
            "binding_id": self.binding_id,
            "binding_nonce": self.binding_nonce,
            "grant_id": self.grant_id,
            "head_sha": self.head_sha,
            "live_admission_digest": self.live_admission_digest,
            "live_admission_replay_digest": self.live_admission_replay_digest,
            "live_finalization_digest": self.live_finalization_digest,
            "live_finalization_key_digest": self.live_finalization_key_digest,
            "mission_id": self.mission_id,
            "pr_number": self.pr_number,
            "provenance_ref": self.provenance_ref,
            "repository": self.repository,
            "run_attempt": self.run_attempt,
            "run_id": self.run_id,
            "runtime_evidence_digest": self.runtime_evidence_digest,
            "runtime_instance_id": self.runtime_instance_id,
            "schema_version": self.schema_version,
        }
        return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")

    def digest(self) -> str:
        return hashlib.sha256(self.canonical_payload()).hexdigest()


@dataclass(frozen=True)
class AuthorityBoundRuntimeEvidence:
    """Verified cross-binding. Evidence is not itself permission to execute an effect."""

    runtime_evidence_digest: str
    runtime_instance_id: str
    provenance_ref: str
    artifact_digest: str
    mission_id: str
    repository: str
    base_sha: str
    head_sha: str
    grant_id: str
    authority_lineage_digest: str
    authenticated_grant_digest: str
    authority_epoch: int
    authority_provenance_id: str
    authority_ceiling: str
    live_admission_digest: str
    live_admission_replay_digest: str
    authority_state_version: int
    authority_root_grant_digest: str
    authority_admitted_at: str
    live_finalization_digest: str
    live_finalization_key_digest: str
    authority_finalized_at: str
    binding_digest: str

    def validate(self) -> "AuthorityBoundRuntimeEvidence":
        for name in (
            "runtime_evidence_digest", "artifact_digest", "authority_lineage_digest",
            "authenticated_grant_digest", "live_admission_digest",
            "live_admission_replay_digest", "authority_root_grant_digest",
            "live_finalization_digest", "live_finalization_key_digest", "binding_digest",
        ):
            _sha256(getattr(self, name), name)
        _sha40(self.base_sha, "base_sha")
        _sha40(self.head_sha, "head_sha")
        for name in (
            "runtime_instance_id", "provenance_ref", "mission_id", "grant_id",
            "authority_provenance_id", "authority_ceiling", "authority_admitted_at",
            "authority_finalized_at",
        ):
            _text(getattr(self, name), name)
        if not isinstance(self.repository, str) or not _REPO.fullmatch(self.repository):
            raise RuntimeAuthorityBindingError("repository must use owner/name form")
        if isinstance(self.authority_epoch, bool) or not isinstance(self.authority_epoch, int) or self.authority_epoch < 0:
            raise RuntimeAuthorityBindingError("authority_epoch must be non-negative")
        if (
            isinstance(self.authority_state_version, bool)
            or not isinstance(self.authority_state_version, int)
            or self.authority_state_version < 1
        ):
            raise RuntimeAuthorityBindingError("authority_state_version must be positive")
        return self
