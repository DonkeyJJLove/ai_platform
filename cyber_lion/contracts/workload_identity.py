"""Adapter-neutral cryptographic workload identity proof boundary."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import re
from typing import Callable

_REPO_RE = re.compile(r"^[^/\s]+/[^/\s]+$")
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
        values = (
            self.proof_id, self.subject_id, self.trust_domain, self.tenant_id,
            self.organization_id, self.audience, self.environment, self.repository,
            self.vcs_ref, self.issuer_id, self.key_id, self.algorithm, self.signature,
        )
        if self.schema_version != "1.0.0" or not all(v.strip() for v in values):
            raise WorkloadIdentityError("identity proof fields/schema are invalid")
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
    proof: WorkloadIdentityProof, verifier: Verifier, *, now: datetime
) -> VerifiedWorkloadIdentity:
    proof.validate()
    if now.tzinfo is None:
        raise WorkloadIdentityError("verification time must be timezone-aware")
    current = now.astimezone(timezone.utc)
    if current < _utc(proof.issued_at) or current >= _utc(proof.expires_at):
        raise WorkloadIdentityError("identity proof is not currently valid")
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
