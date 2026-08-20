"""Deterministic contracts for detached repository mutation and exact ref attachment.

The contracts separate an untrusted detached candidate from independently verified
evidence, live authority, one exact compare-and-swap ref effect, and a post-effect
observation receipt. They are a reference enforcement core only: deployed provider,
observer, verification-source and composition-root trust remain external obligations.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from pathlib import PurePosixPath
import re
from typing import Final

_SHA_RE: Final = re.compile(r"^[0-9a-f]{40}$")
_DIGEST_RE: Final = re.compile(r"^[0-9a-f]{64}$")
_BRANCH_RE: Final = re.compile(
    r"^(?!/)(?!.*//)(?!.*\.\.)(?!.*@\{)(?!.*[~^:?*\[\\])"
    r"(?!.*\.$)(?!.*\.lock(?:/|$))[A-Za-z0-9._/-]+$"
)
_ATTACH_ACTION: Final = "fast_forward_ref"
_SCHEMA_VERSION: Final = "1.1.0"


class RepositoryMutationContractError(ValueError):
    """Raised when a repository-mutation contract is malformed or ambiguous."""


def _text(value: object, *, name: str, limit: int = 512) -> str:
    if (
        not isinstance(value, str)
        or not value.strip()
        or len(value) > limit
        or "\x00" in value
    ):
        raise RepositoryMutationContractError(f"{name} is invalid")
    return value


def _sha(value: object, *, name: str) -> str:
    value = _text(value, name=name, limit=40)
    if not _SHA_RE.fullmatch(value):
        raise RepositoryMutationContractError(
            f"{name} must be a full lowercase git SHA"
        )
    return value


def _digest(value: object, *, name: str) -> str:
    value = _text(value, name=name, limit=64)
    if not _DIGEST_RE.fullmatch(value):
        raise RepositoryMutationContractError(
            f"{name} must be a lowercase sha256 hex digest"
        )
    return value


def _branch(value: object) -> str:
    value = _text(value, name="branch", limit=255)
    if value.startswith("refs/") or not _BRANCH_RE.fullmatch(value):
        raise RepositoryMutationContractError("branch is invalid")
    return value


def _paths(values: object) -> tuple[str, ...]:
    if type(values) is not tuple or not values:
        raise RepositoryMutationContractError(
            "changed_paths must be a non-empty immutable tuple"
        )
    if len(set(values)) != len(values):
        raise RepositoryMutationContractError("changed_paths must be unique")
    normalized: list[str] = []
    for raw in values:
        _text(raw, name="changed_path", limit=1024)
        if "\\" in raw:
            raise RepositoryMutationContractError(
                "changed_paths must use repository-relative POSIX paths"
            )
        path = PurePosixPath(raw)
        if path.is_absolute() or ".." in path.parts or str(path) in {"", "."}:
            raise RepositoryMutationContractError("changed_path is unsafe")
        normalized.append(str(path))
    return tuple(normalized)


def changed_paths_digest(changed_paths: tuple[str, ...]) -> str:
    values = _paths(changed_paths)
    payload = json.dumps(
        list(values), separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return sha256(b"LION/REPOSITORY-CHANGED-PATHS/1.0.0\x00" + payload).hexdigest()


@dataclass(frozen=True)
class DetachedRepositoryCandidate:
    """Untrusted detached Git commit prepared by a builder."""

    repository: str
    branch: str
    expected_head_sha: str
    expected_parent_sha: str
    candidate_commit_sha: str
    candidate_tree_sha: str
    changed_paths: tuple[str, ...]
    builder_id: str
    prepared_at: str
    schema_version: str = _SCHEMA_VERSION

    def validate(self) -> "DetachedRepositoryCandidate":
        if self.schema_version != _SCHEMA_VERSION:
            raise RepositoryMutationContractError("unsupported detached candidate schema")
        _text(self.repository, name="repository")
        _branch(self.branch)
        _sha(self.expected_head_sha, name="expected_head_sha")
        _sha(self.expected_parent_sha, name="expected_parent_sha")
        _sha(self.candidate_commit_sha, name="candidate_commit_sha")
        _sha(self.candidate_tree_sha, name="candidate_tree_sha")
        _paths(self.changed_paths)
        _text(self.builder_id, name="builder_id")
        _text(self.prepared_at, name="prepared_at")
        if self.expected_parent_sha != self.expected_head_sha:
            raise RepositoryMutationContractError(
                "candidate parent must equal exact expected head"
            )
        if self.candidate_commit_sha == self.expected_head_sha:
            raise RepositoryMutationContractError(
                "candidate commit must differ from expected head"
            )
        return self

    def canonical_payload(self) -> bytes:
        self.validate()
        value = asdict(self)
        value["changed_paths"] = list(self.changed_paths)
        return json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")

    def digest(self) -> str:
        return sha256(
            b"LION/DETACHED-REPOSITORY-CANDIDATE/1.1.0\x00"
            + self.canonical_payload()
        ).hexdigest()


@dataclass(frozen=True)
class TrustedVerifierPin:
    """Composition-root pin for the independent candidate verifier."""

    verifier_id: str
    verifier_identity_digest: str
    verifier_implementation_digest: str
    verification_source_id: str
    verification_source_identity_digest: str
    verification_source_implementation_digest: str

    def validate(self) -> "TrustedVerifierPin":
        _text(self.verifier_id, name="verifier_id")
        _digest(self.verifier_identity_digest, name="verifier_identity_digest")
        _digest(
            self.verifier_implementation_digest,
            name="verifier_implementation_digest",
        )
        _text(self.verification_source_id, name="verification_source_id")
        _digest(
            self.verification_source_identity_digest,
            name="verification_source_identity_digest",
        )
        _digest(
            self.verification_source_implementation_digest,
            name="verification_source_implementation_digest",
        )
        return self

    def digest(self) -> str:
        self.validate()
        return sha256(
            b"LION/TRUSTED-VERIFIER-PIN/1.1.0\x00"
            + json.dumps(asdict(self), sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()


@dataclass(frozen=True)
class TrustedDependencyPin:
    """Composition-root identity/implementation pin for effect or observation ports."""

    dependency_id: str
    identity_digest: str
    implementation_digest: str
    deployment_evidence_digest: str

    def validate(self) -> "TrustedDependencyPin":
        _text(self.dependency_id, name="dependency_id")
        _digest(self.identity_digest, name="identity_digest")
        _digest(self.implementation_digest, name="implementation_digest")
        _digest(self.deployment_evidence_digest, name="deployment_evidence_digest")
        if self.deployment_evidence_digest == "0" * 64:
            raise RepositoryMutationContractError(
                "deployment evidence digest must not be the zero sentinel"
            )
        return self

    def digest(self) -> str:
        self.validate()
        return sha256(
            b"LION/TRUSTED-DEPENDENCY-PIN/1.1.0\x00"
            + json.dumps(asdict(self), sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()


@dataclass(frozen=True)
class VerifiedDetachedCandidate:
    """Independent verification record for one exact detached candidate."""

    candidate_digest: str
    repository: str
    branch: str
    expected_head_sha: str
    expected_parent_sha: str
    candidate_commit_sha: str
    candidate_tree_sha: str
    changed_paths_digest: str
    verifier_id: str
    verifier_identity_digest: str
    verifier_implementation_digest: str
    evidence_refs: tuple[str, ...]
    verified_at: str
    schema_version: str = _SCHEMA_VERSION

    def validate_for(
        self,
        candidate: DetachedRepositoryCandidate,
        *,
        pin: TrustedVerifierPin,
    ) -> "VerifiedDetachedCandidate":
        if type(candidate) is not DetachedRepositoryCandidate:
            raise RepositoryMutationContractError(
                "verification requires exact DetachedRepositoryCandidate"
            )
        if type(pin) is not TrustedVerifierPin:
            raise RepositoryMutationContractError("trusted verifier pin is invalid")
        candidate.validate()
        pin.validate()
        if self.schema_version != _SCHEMA_VERSION:
            raise RepositoryMutationContractError("unsupported verification schema")
        _digest(self.candidate_digest, name="candidate_digest")
        _text(self.repository, name="repository")
        _branch(self.branch)
        _sha(self.expected_head_sha, name="expected_head_sha")
        _sha(self.expected_parent_sha, name="expected_parent_sha")
        _sha(self.candidate_commit_sha, name="candidate_commit_sha")
        _sha(self.candidate_tree_sha, name="candidate_tree_sha")
        _digest(self.changed_paths_digest, name="changed_paths_digest")
        _text(self.verifier_id, name="verifier_id")
        _digest(self.verifier_identity_digest, name="verifier_identity_digest")
        _digest(
            self.verifier_implementation_digest,
            name="verifier_implementation_digest",
        )
        if type(self.evidence_refs) is not tuple or not self.evidence_refs:
            raise RepositoryMutationContractError(
                "verified candidate requires evidence_refs"
            )
        if len(set(self.evidence_refs)) != len(self.evidence_refs):
            raise RepositoryMutationContractError("evidence_refs must be unique")
        for ref in self.evidence_refs:
            _text(ref, name="evidence_ref", limit=1024)
        _text(self.verified_at, name="verified_at")

        expected_candidate = (
            candidate.digest(),
            candidate.repository,
            candidate.branch,
            candidate.expected_head_sha,
            candidate.expected_parent_sha,
            candidate.candidate_commit_sha,
            candidate.candidate_tree_sha,
            changed_paths_digest(candidate.changed_paths),
        )
        actual_candidate = (
            self.candidate_digest,
            self.repository,
            self.branch,
            self.expected_head_sha,
            self.expected_parent_sha,
            self.candidate_commit_sha,
            self.candidate_tree_sha,
            self.changed_paths_digest,
        )
        if actual_candidate != expected_candidate:
            raise RepositoryMutationContractError(
                "verification does not bind exact detached candidate"
            )
        if self.verifier_id == candidate.builder_id:
            raise RepositoryMutationContractError(
                "builder cannot be the independent candidate verifier"
            )
        expected_verifier = (
            pin.verifier_id,
            pin.verifier_identity_digest,
            pin.verifier_implementation_digest,
        )
        actual_verifier = (
            self.verifier_id,
            self.verifier_identity_digest,
            self.verifier_implementation_digest,
        )
        if actual_verifier != expected_verifier:
            raise RepositoryMutationContractError(
                "verification record is not issued by the pinned verifier"
            )
        return self

    def canonical_payload(self) -> bytes:
        value = asdict(self)
        value["evidence_refs"] = list(self.evidence_refs)
        return json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")

    def digest(self) -> str:
        _digest(self.candidate_digest, name="candidate_digest")
        return sha256(
            b"LION/VERIFIED-DETACHED-CANDIDATE/1.1.0\x00"
            + self.canonical_payload()
        ).hexdigest()


class CandidateVerificationSource(ABC):
    """Fail-closed source owned by the trusted PEP composition root."""

    source_id: str
    source_identity_digest: str
    source_implementation_digest: str

    def validate_pin(self, pin: TrustedVerifierPin) -> None:
        if type(pin) is not TrustedVerifierPin:
            raise RepositoryMutationContractError("trusted verifier pin is invalid")
        pin.validate()
        actual = (
            getattr(self, "source_id", None),
            getattr(self, "source_identity_digest", None),
            getattr(self, "source_implementation_digest", None),
        )
        expected = (
            pin.verification_source_id,
            pin.verification_source_identity_digest,
            pin.verification_source_implementation_digest,
        )
        if actual != expected:
            raise RepositoryMutationContractError(
                "verification source does not match trusted composition-root pin"
            )

    @abstractmethod
    def _lookup_exact(
        self, candidate_digest: str
    ) -> tuple[VerifiedDetachedCandidate, ...]:
        raise NotImplementedError

    def resolve_exact(
        self,
        candidate: DetachedRepositoryCandidate,
        *,
        pin: TrustedVerifierPin,
    ) -> VerifiedDetachedCandidate:
        self.validate_pin(pin)
        if type(candidate) is not DetachedRepositoryCandidate:
            raise RepositoryMutationContractError(
                "candidate must be exact DetachedRepositoryCandidate"
            )
        candidate.validate()
        candidates = self._lookup_exact(candidate.digest())
        if type(candidates) is not tuple:
            raise RepositoryMutationContractError(
                "verification source result must be an immutable tuple"
            )
        if len(candidates) == 0:
            raise RepositoryMutationContractError("candidate verification not found")
        if len(candidates) > 1:
            raise RepositoryMutationContractError(
                "candidate verification lookup is ambiguous"
            )
        record = candidates[0]
        if type(record) is not VerifiedDetachedCandidate:
            raise RepositoryMutationContractError(
                "verification source returned invalid record type"
            )
        return record.validate_for(candidate, pin=pin)


@dataclass(frozen=True)
class ExactRefAttachIntent:
    """One exact fast-forward effect; force-update is intentionally unrepresentable."""

    repository: str
    branch: str
    mission_id: str
    expected_head_sha: str
    expected_parent_sha: str
    candidate_commit_sha: str
    candidate_tree_sha: str
    candidate_verification_digest: str
    action: str = _ATTACH_ACTION
    schema_version: str = _SCHEMA_VERSION

    def validate(self) -> "ExactRefAttachIntent":
        if self.schema_version != _SCHEMA_VERSION:
            raise RepositoryMutationContractError("unsupported attach intent schema")
        _text(self.repository, name="repository")
        _branch(self.branch)
        _text(self.mission_id, name="mission_id")
        _sha(self.expected_head_sha, name="expected_head_sha")
        _sha(self.expected_parent_sha, name="expected_parent_sha")
        _sha(self.candidate_commit_sha, name="candidate_commit_sha")
        _sha(self.candidate_tree_sha, name="candidate_tree_sha")
        _digest(
            self.candidate_verification_digest,
            name="candidate_verification_digest",
        )
        if self.expected_parent_sha != self.expected_head_sha:
            raise RepositoryMutationContractError(
                "attach parent must equal expected head"
            )
        if self.action != _ATTACH_ACTION:
            raise RepositoryMutationContractError(
                "attach action must be fast_forward_ref"
            )
        return self

    def canonical_payload(self) -> bytes:
        self.validate()
        return json.dumps(
            asdict(self), sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")

    def digest(self) -> str:
        return sha256(
            b"LION/EXACT-REF-ATTACH-INTENT/1.1.0\x00" + self.canonical_payload()
        ).hexdigest()


@dataclass(frozen=True)
class TrustedRefState:
    repository: str
    branch: str
    head_sha: str
    observed_at: str

    def validate(self) -> "TrustedRefState":
        _text(self.repository, name="repository")
        _branch(self.branch)
        _sha(self.head_sha, name="head_sha")
        _text(self.observed_at, name="observed_at")
        return self


@dataclass(frozen=True)
class AttachProviderResult:
    status: str
    provider_id: str

    def validate(self) -> "AttachProviderResult":
        if self.status not in {"APPLIED", "FAILED_NO_EFFECT", "UNKNOWN"}:
            raise RepositoryMutationContractError("attach provider status is invalid")
        _text(self.provider_id, name="provider_id")
        return self


@dataclass(frozen=True)
class RepositoryAttachAdmission:
    admission_id: str
    decision: str
    rationale: str
    effect_id: str
    authority_effect_key: str
    intent_digest: str
    candidate_digest: str
    verification_digest: str
    runtime_binding_digest: str
    live_admission_digest: str | None = None
    grant_id: str | None = None
    grant_digest: str | None = None
    authority_epoch: int | None = None

    def validate(self) -> "RepositoryAttachAdmission":
        _text(self.admission_id, name="admission_id")
        _text(self.rationale, name="rationale", limit=2048)
        _text(self.effect_id, name="effect_id")
        _digest(self.authority_effect_key, name="authority_effect_key")
        _digest(self.intent_digest, name="intent_digest")
        _digest(self.candidate_digest, name="candidate_digest")
        _digest(self.verification_digest, name="verification_digest")
        _digest(self.runtime_binding_digest, name="runtime_binding_digest")
        if self.decision not in {"ALLOW", "DENY"}:
            raise RepositoryMutationContractError(
                "admission decision must be ALLOW or DENY"
            )
        if self.decision == "ALLOW":
            _digest(self.live_admission_digest, name="live_admission_digest")
            _text(self.grant_id, name="grant_id")
            _digest(self.grant_digest, name="grant_digest")
            if (
                not isinstance(self.authority_epoch, int)
                or isinstance(self.authority_epoch, bool)
                or self.authority_epoch < 0
            ):
                raise RepositoryMutationContractError(
                    "ALLOW requires valid authority_epoch"
                )
        return self

    def canonical_payload(self) -> bytes:
        self.validate()
        return json.dumps(
            asdict(self), sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")

    def digest(self) -> str:
        return sha256(
            b"LION/REPOSITORY-ATTACH-ADMISSION/1.1.0\x00"
            + self.canonical_payload()
        ).hexdigest()


@dataclass(frozen=True)
class RepositoryEffectReceipt:
    effect_id: str
    admission_id: str
    admission_digest: str
    repository: str
    branch: str
    expected_head_sha: str
    candidate_commit_sha: str
    candidate_tree_sha: str
    observed_head_sha: str
    verification_digest: str
    grant_digest: str
    provider_id: str
    observer_id: str
    observed_at: str
    outcome: str = "SUCCEEDED"

    def validate(self) -> "RepositoryEffectReceipt":
        for name in (
            "effect_id", "admission_id", "repository", "provider_id",
            "observer_id", "observed_at",
        ):
            _text(getattr(self, name), name=name)
        _digest(self.admission_digest, name="admission_digest")
        _branch(self.branch)
        _sha(self.expected_head_sha, name="expected_head_sha")
        _sha(self.candidate_commit_sha, name="candidate_commit_sha")
        _sha(self.candidate_tree_sha, name="candidate_tree_sha")
        _sha(self.observed_head_sha, name="observed_head_sha")
        _digest(self.verification_digest, name="verification_digest")
        _digest(self.grant_digest, name="grant_digest")
        if self.outcome != "SUCCEEDED":
            raise RepositoryMutationContractError(
                "effect receipt only represents exact success"
            )
        if self.observed_head_sha != self.candidate_commit_sha:
            raise RepositoryMutationContractError(
                "success receipt requires exact candidate ref observation"
            )
        return self

    def digest(self) -> str:
        self.validate()
        return sha256(
            b"LION/REPOSITORY-EFFECT-RECEIPT/1.1.0\x00"
            + json.dumps(
                asdict(self), sort_keys=True, separators=(",", ":"), ensure_ascii=False
            ).encode("utf-8")
        ).hexdigest()


def canonical_attach_resource(intent: ExactRefAttachIntent) -> str:
    intent.validate()
    return (
        f"github:repo:{intent.repository}:ref:refs/heads/{intent.branch}:"
        f"expected:{intent.expected_head_sha}:"
        f"candidate:{intent.candidate_commit_sha}:tree:{intent.candidate_tree_sha}"
    )


def canonical_verification_constraint(intent: ExactRefAttachIntent) -> str:
    intent.validate()
    return f"verification:{intent.candidate_verification_digest}"


def canonical_authority_effect_key(
    *, mission_id: str, grant_id: str, grant_digest: str, epoch: int
) -> str:
    _text(mission_id, name="mission_id")
    _text(grant_id, name="grant_id")
    _digest(grant_digest, name="grant_digest")
    if not isinstance(epoch, int) or isinstance(epoch, bool) or epoch < 0:
        raise RepositoryMutationContractError("epoch is invalid")
    material = f"{mission_id}\x00{grant_id}\x00{grant_digest}\x00{epoch}".encode("utf-8")
    return sha256(
        b"LION/REPOSITORY-AUTHORITY-EFFECT/1.1.0\x00" + material
    ).hexdigest()


def canonical_runtime_binding_digest(
    verifier_pin: TrustedVerifierPin,
    effect_pin: TrustedDependencyPin,
    observer_pin: TrustedDependencyPin,
) -> str:
    if type(verifier_pin) is not TrustedVerifierPin:
        raise RepositoryMutationContractError("trusted verifier pin is invalid")
    if type(effect_pin) is not TrustedDependencyPin or type(observer_pin) is not TrustedDependencyPin:
        raise RepositoryMutationContractError("trusted dependency pin is invalid")
    material = json.dumps(
        {
            "verifier_pin": verifier_pin.digest(),
            "effect_pin": effect_pin.digest(),
            "observer_pin": observer_pin.digest(),
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return sha256(b"LION/REPOSITORY-RUNTIME-BINDING/1.1.0\x00" + material).hexdigest()
