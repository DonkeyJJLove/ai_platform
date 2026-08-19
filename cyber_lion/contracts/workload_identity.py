"""Adapter-neutral cryptographic workload identity proof boundary."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import re
from typing import Callable

_REPO_RE = re.compile(r"^[^/\s]+/[^/\s]+$")
_MAX_LENGTHS = {
    "proof_id": 256, "subject_id": 256, "trust_domain": 256, "tenant_id": 256,
    "organization_id": 256, "audience": 256, "environment": 128, "vcs_ref": 256,
    "issuer_id": 256, "key_id": 256, "algorithm": 128, "signature": 8192,
}
Verifier = Callable[[bytes, str, str, str], bool]


class WorkloadIdentityError(ValueError):
    pass


def _utc(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise WorkloadIdentityError("invalid identity proof timestamp") from exc
    if parsed.tzinfo is None:
        raise WorkloadIdentityError("identity proof timestamps must be timezone-aware")
    return parsed.astimezone(timezone.utc)


@dataclass(frozen=True)
class WorkloadIdentityProof:
    schema_version: str
    proof_id: str
    subject_id: str
    trust_domain: str
    tenant_id: str
    organization_id: str
    audience: str
    environment: str
    repository: str
    vcs_ref: str
    issuer_id: str
    key_id: str
    algorithm: str
    issued_at: str
    expires_at: str
    signature: str

    def validate(self) -> "WorkloadIdentityProof":
        names = (
            "proof_id", "subject_id", "trust_domain", "tenant_id", "organization_id",
            "audience", "environment", "repository", "vcs_ref", "issuer_id", "key_id",
            "algorithm", "issued_at", "expires_at", "signature",
        )
        values = {name: getattr(self, name) for name in names}
        if self.schema_version != "1.0.0" or any(
            not isinstance(value, str) or not value.strip() for value in values.values()
        ):
            raise WorkloadIdentityError("identity proof fields/schema are invalid")
        if any(len(values[name]) > limit for name, limit in _MAX_LENGTHS.items()):
            raise WorkloadIdentityError("identity proof field exceeds schema maxLength")
        if not _REPO_RE.fullmatch(self.repository):
            raise WorkloadIdentityError("repository must use owner/name form")
        if _utc(self.issued_at) >= _utc(self.expires_at):
            raise WorkloadIdentityError("identity proof validity window is invalid")
        return self

    def canonical_payload(self) -> bytes:
        payload = {
            "algorithm": self.algorithm, "audience": self.audience,
            "environment": self.environment, "expires_at": self.expires_at,
            "issued_at": self.issued_at, "issuer_id": self.issuer_id,
            "key_id": self.key_id, "organization_id": self.organization_id,
            "proof_id": self.proof_id, "repository": self.repository,
            "schema_version": self.schema_version, "subject_id": self.subject_id,
            "tenant_id": self.tenant_id, "trust_domain": self.trust_domain,
            "vcs_ref": self.vcs_ref,
        }
        return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")

    def digest(self) -> str:
        return hashlib.sha256(self.canonical_payload() + b"." + self.signature.encode()).hexdigest()


@dataclass(frozen=True)
class WorkloadIdentityContext:
    trust_domain: str
    tenant_id: str
    organization_id: str
    audience: str
    environment: str
    repository: str
    vcs_ref: str
    issuer_id: str


@dataclass(frozen=True)
class VerifiedWorkloadIdentity:
    subject_id: str
    trust_domain: str
    tenant_id: str
    organization_id: str
    audience: str
    proof_digest: str
    key_id: str
    issued_at: str
    expires_at: str


def verify_workload_identity(
    proof: WorkloadIdentityProof, verifier: Verifier, *, now: datetime,
    context: WorkloadIdentityContext,
) -> VerifiedWorkloadIdentity:
    proof.validate()
    if now.tzinfo is None:
        raise WorkloadIdentityError("verification time must be timezone-aware")
    current = now.astimezone(timezone.utc)
    if current < _utc(proof.issued_at) or current >= _utc(proof.expires_at):
        raise WorkloadIdentityError("identity proof is not currently valid")
    actual = (
        proof.trust_domain, proof.tenant_id, proof.organization_id, proof.audience,
        proof.environment, proof.repository, proof.vcs_ref, proof.issuer_id,
    )
    expected = (
        context.trust_domain, context.tenant_id, context.organization_id, context.audience,
        context.environment, context.repository, context.vcs_ref, context.issuer_id,
    )
    if actual != expected:
        raise WorkloadIdentityError("identity proof context mismatch")
    try:
        accepted = verifier(proof.canonical_payload(), proof.signature, proof.key_id, proof.algorithm)
    except Exception as exc:
        raise WorkloadIdentityError("identity verifier failed closed") from exc
    if accepted is not True:
        raise WorkloadIdentityError("identity proof verification failed")
    return VerifiedWorkloadIdentity(
        proof.subject_id, proof.trust_domain, proof.tenant_id, proof.organization_id,
        proof.audience, proof.digest(), proof.key_id, proof.issued_at, proof.expires_at,
    )
