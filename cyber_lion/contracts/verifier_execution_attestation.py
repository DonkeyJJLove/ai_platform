"""Immutable contracts for verifier execution independence attestation B1.

All objects are evidence-only. They grant no repository authority, cannot consume
merge authority, mutate refs, or promote mission state.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
import re
from typing import Any, Mapping, Tuple

_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_REPO = re.compile(r"^[^/\s]+/[^/\s]+$")
_ROLES = frozenset({"BUILDER", "VERIFICATION_ATTACH", "VERIFIER"})
_RESULTS = frozenset({"PASS", "FAIL"})
_CI_STATES = frozenset({"SUCCESS", "FAILURE", "CANCELLED", "TIMED_OUT", "UNKNOWN"})


class VerifierExecutionAttestationError(ValueError):
    """Raised when verifier-execution evidence is malformed or ambiguous."""


def canonical_json(value: Mapping[str, Any]) -> bytes:
    return json.dumps(dict(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _text(value: Any, name: str, *, limit: int = 4096) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > limit or "\x00" in value:
        raise VerifierExecutionAttestationError(f"{name} is invalid")
    return value


def _sha40(value: Any, name: str) -> str:
    value = _text(value, name, limit=40)
    if not _SHA40.fullmatch(value):
        raise VerifierExecutionAttestationError(f"{name} must be full lowercase git SHA")
    return value


def _sha256(value: Any, name: str) -> str:
    value = _text(value, name, limit=64)
    if not _SHA256.fullmatch(value):
        raise VerifierExecutionAttestationError(f"{name} must be sha256 hex")
    return value


def _utc(value: Any, name: str) -> datetime:
    value = _text(value, name)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise VerifierExecutionAttestationError(f"{name} is invalid") from exc
    if parsed.tzinfo is None:
        raise VerifierExecutionAttestationError(f"{name} must be timezone-aware")
    return parsed.astimezone(timezone.utc)


@dataclass(frozen=True)
class ExactVerificationTarget:
    repository: str
    pr_number: int
    base_sha: str
    head_sha: str
    tree_sha: str
    ci_run_id: str
    mission_id: str
    slice_id: str

    def validate(self) -> "ExactVerificationTarget":
        if not isinstance(self.repository, str) or not _REPO.fullmatch(self.repository):
            raise VerifierExecutionAttestationError("repository must use owner/name form")
        if isinstance(self.pr_number, bool) or not isinstance(self.pr_number, int) or self.pr_number < 1:
            raise VerifierExecutionAttestationError("pr_number must be positive")
        for name in ("base_sha", "head_sha", "tree_sha"):
            _sha40(getattr(self, name), name)
        for name in ("ci_run_id", "mission_id", "slice_id"):
            _text(getattr(self, name), name)
        return self

    def canonical_dict(self) -> dict[str, Any]:
        self.validate()
        return asdict(self)

    def digest(self) -> str:
        return sha256(canonical_json(self.canonical_dict())).hexdigest()


@dataclass(frozen=True)
class FixedSourcePin:
    source_id: str
    source_instance_id: str
    source_implementation_digest: str
    trust_anchor_id: str

    def validate(self) -> "FixedSourcePin":
        for name in ("source_id", "source_instance_id", "trust_anchor_id"):
            _text(getattr(self, name), name)
        _sha256(self.source_implementation_digest, "source_implementation_digest")
        return self

    def binding(self) -> tuple[str, str, str, str]:
        self.validate()
        return (
            self.source_id,
            self.source_instance_id,
            self.source_implementation_digest,
            self.trust_anchor_id,
        )


@dataclass(frozen=True)
class ExecutorParticipationRecord:
    subject_id: str
    runtime_instance_id: str
    participation_role: str
    repository: str
    mission_id: str
    target_head_sha: str
    target_tree_sha: str
    provenance_ref: str
    evidence_digest: str
    trust_anchor_id: str
    observed_at: str

    def validate(self) -> "ExecutorParticipationRecord":
        for name in ("subject_id", "runtime_instance_id", "mission_id", "provenance_ref", "trust_anchor_id"):
            _text(getattr(self, name), name)
        if self.participation_role not in _ROLES:
            raise VerifierExecutionAttestationError("participation_role is invalid")
        if not _REPO.fullmatch(self.repository):
            raise VerifierExecutionAttestationError("repository must use owner/name form")
        _sha40(self.target_head_sha, "target_head_sha")
        _sha40(self.target_tree_sha, "target_tree_sha")
        _sha256(self.evidence_digest, "evidence_digest")
        _utc(self.observed_at, "observed_at")
        return self

    def canonical_dict(self) -> dict[str, Any]:
        self.validate()
        return asdict(self)

    def digest(self) -> str:
        return sha256(canonical_json(self.canonical_dict())).hexdigest()


@dataclass(frozen=True)
class TrustedParticipationHistory:
    source_id: str
    source_instance_id: str
    trust_anchor_id: str
    source_implementation_digest: str
    observed_at: str
    records: Tuple[ExecutorParticipationRecord, ...]
    history_digest: str

    def validate(self) -> "TrustedParticipationHistory":
        FixedSourcePin(
            self.source_id, self.source_instance_id,
            self.source_implementation_digest, self.trust_anchor_id,
        ).validate()
        _utc(self.observed_at, "observed_at")
        if type(self.records) is not tuple:
            raise VerifierExecutionAttestationError("records must be a tuple")
        digests: list[str] = []
        for record in self.records:
            if type(record) is not ExecutorParticipationRecord:
                raise VerifierExecutionAttestationError("participation record type is invalid")
            record.validate()
            digests.append(record.digest())
        if len(digests) != len(set(digests)):
            raise VerifierExecutionAttestationError("duplicate participation record")
        expected = sha256(canonical_json({
            "source_id": self.source_id,
            "source_instance_id": self.source_instance_id,
            "trust_anchor_id": self.trust_anchor_id,
            "source_implementation_digest": self.source_implementation_digest,
            "observed_at": self.observed_at,
            "record_digests": digests,
        })).hexdigest()
        _sha256(self.history_digest, "history_digest")
        if self.history_digest != expected:
            raise VerifierExecutionAttestationError("participation history digest mismatch")
        return self

    @classmethod
    def build(
        cls, *, source_id: str, source_instance_id: str, trust_anchor_id: str,
        source_implementation_digest: str, observed_at: str,
        records: Tuple[ExecutorParticipationRecord, ...],
    ) -> "TrustedParticipationHistory":
        raw = {
            "source_id": source_id,
            "source_instance_id": source_instance_id,
            "trust_anchor_id": trust_anchor_id,
            "source_implementation_digest": source_implementation_digest,
            "observed_at": observed_at,
            "record_digests": [record.validate().digest() for record in records],
        }
        return cls(
            source_id, source_instance_id, trust_anchor_id, source_implementation_digest,
            observed_at, records, sha256(canonical_json(raw)).hexdigest(),
        ).validate()

    def source_binding(self) -> tuple[str, str, str, str]:
        return FixedSourcePin(
            self.source_id, self.source_instance_id,
            self.source_implementation_digest, self.trust_anchor_id,
        ).binding()


@dataclass(frozen=True)
class TrustedCIEvidence:
    source_id: str
    source_instance_id: str
    source_implementation_digest: str
    trust_anchor_id: str
    repository: str
    pr_number: int
    base_sha: str
    head_sha: str
    tree_sha: str
    ci_run_id: str
    workflow: str
    conclusion: str
    observed_at: str
    provenance_ref: str
    evidence_digest: str

    def validate(self) -> "TrustedCIEvidence":
        FixedSourcePin(
            self.source_id, self.source_instance_id,
            self.source_implementation_digest, self.trust_anchor_id,
        ).validate()
        ExactVerificationTarget(
            self.repository, self.pr_number, self.base_sha, self.head_sha, self.tree_sha,
            self.ci_run_id, "ci-evidence-validation", "ci-evidence-validation",
        ).validate()
        _text(self.workflow, "workflow")
        if self.conclusion not in _CI_STATES:
            raise VerifierExecutionAttestationError("CI conclusion is invalid")
        _utc(self.observed_at, "observed_at")
        _text(self.provenance_ref, "provenance_ref")
        _sha256(self.evidence_digest, "evidence_digest")
        return self

    def source_binding(self) -> tuple[str, str, str, str]:
        return FixedSourcePin(
            self.source_id, self.source_instance_id,
            self.source_implementation_digest, self.trust_anchor_id,
        ).binding()

    def target_binding(self) -> tuple[object, ...]:
        self.validate()
        return (
            self.repository, self.pr_number, self.base_sha, self.head_sha,
            self.tree_sha, self.ci_run_id,
        )

    def digest(self) -> str:
        self.validate()
        return sha256(canonical_json(asdict(self))).hexdigest()


@dataclass(frozen=True)
class TrustedSemanticVerificationResult:
    source_id: str
    source_instance_id: str
    source_implementation_digest: str
    trust_anchor_id: str
    verification_id: str
    verifier_subject_id: str
    verifier_runtime_instance_id: str
    verifier_implementation_digest: str
    target_digest: str
    semantic_evidence_digest: str
    result: str
    observed_at: str
    provenance_ref: str
    evidence_digest: str

    def validate(self) -> "TrustedSemanticVerificationResult":
        FixedSourcePin(
            self.source_id, self.source_instance_id,
            self.source_implementation_digest, self.trust_anchor_id,
        ).validate()
        for name in ("verification_id", "verifier_subject_id", "verifier_runtime_instance_id", "provenance_ref"):
            _text(getattr(self, name), name)
        for name in (
            "verifier_implementation_digest", "target_digest",
            "semantic_evidence_digest", "evidence_digest",
        ):
            _sha256(getattr(self, name), name)
        if self.result not in _RESULTS:
            raise VerifierExecutionAttestationError("semantic verification result is invalid")
        _utc(self.observed_at, "observed_at")
        return self

    def source_binding(self) -> tuple[str, str, str, str]:
        return FixedSourcePin(
            self.source_id, self.source_instance_id,
            self.source_implementation_digest, self.trust_anchor_id,
        ).binding()

    def digest(self) -> str:
        self.validate()
        return sha256(canonical_json(asdict(self))).hexdigest()


@dataclass(frozen=True)
class VerifierExecutionAttestation:
    """Caller-visible request binding; it contains no self-declared PASS result."""
    attestation_id: str
    verifier_subject_id: str
    verifier_runtime_instance_id: str
    verifier_implementation_digest: str
    workload_identity_proof_digest: str
    runtime_attestation_digest: str
    target: ExactVerificationTarget
    participation_history_digest: str
    ci_evidence_digest: str
    semantic_verification_result_digest: str
    evidence_bundle_digest: str
    issued_at: str
    expires_at: str

    def validate(self) -> "VerifierExecutionAttestation":
        for name in ("attestation_id", "verifier_subject_id", "verifier_runtime_instance_id"):
            _text(getattr(self, name), name)
        for name in (
            "verifier_implementation_digest", "workload_identity_proof_digest",
            "runtime_attestation_digest", "participation_history_digest",
            "ci_evidence_digest", "semantic_verification_result_digest",
            "evidence_bundle_digest",
        ):
            _sha256(getattr(self, name), name)
        if type(self.target) is not ExactVerificationTarget:
            raise VerifierExecutionAttestationError("target must use exact contract type")
        self.target.validate()
        if _utc(self.issued_at, "issued_at") >= _utc(self.expires_at, "expires_at"):
            raise VerifierExecutionAttestationError("attestation validity window is invalid")
        return self

    def canonical_dict(self) -> dict[str, Any]:
        self.validate()
        value = asdict(self)
        value["target"] = self.target.canonical_dict()
        return value

    def digest(self) -> str:
        return sha256(canonical_json(self.canonical_dict())).hexdigest()


def evidence_bundle_digest(
    *, target: ExactVerificationTarget, workload_identity_proof_digest: str,
    runtime_attestation_digest: str, verifier_implementation_digest: str,
    participation_history_digest: str, ci_evidence_digest: str,
    semantic_verification_result_digest: str,
) -> str:
    target.validate()
    values = {
        "workload_identity_proof_digest": workload_identity_proof_digest,
        "runtime_attestation_digest": runtime_attestation_digest,
        "verifier_implementation_digest": verifier_implementation_digest,
        "participation_history_digest": participation_history_digest,
        "ci_evidence_digest": ci_evidence_digest,
        "semantic_verification_result_digest": semantic_verification_result_digest,
    }
    for name, value in values.items():
        _sha256(value, name)
    return sha256(canonical_json({"target_digest": target.digest(), **values})).hexdigest()
