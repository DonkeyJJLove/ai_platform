from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import re
from typing import Tuple

_SHA64 = re.compile(r"^[0-9a-f]{64}$")
_GIT40 = re.compile(r"^[0-9a-f]{40}$")
_CLASSES = frozenset({"POST_OBSERVATION_DECISION", "DOWNSTREAM_CURRENTNESS_GUARD"})
_EVIDENCE_CLASSES = frozenset({"ADMISSION_DECISION_NEGATIVE_EVIDENCE", "DOWNSTREAM_CURRENTNESS_NEGATIVE_EVIDENCE"})
RECORD_DOMAIN = b"LION/MOON-NON-BYPASS-NEGATIVE-EVIDENCE/1"
SATISFACTION_DOMAIN = b"LION/MOON-SECURITY-REQUIREMENT-EVIDENCE-SATISFACTION/1"
REPORT_DOMAIN = b"LION/MOON-SECURITY-BOUNDARY-EVIDENCE-REPORT/1"


class MoonSecurityBoundaryEvidenceContractError(ValueError):
    pass


def _text(value: str, name: str) -> str:
    if not isinstance(value, str) or not value.strip() or "\x00" in value:
        raise MoonSecurityBoundaryEvidenceContractError(f"{name} invalid")
    return value


def _sha64(value: str, name: str) -> str:
    _text(value, name)
    if _SHA64.fullmatch(value) is None:
        raise MoonSecurityBoundaryEvidenceContractError(f"{name} must be sha256")
    return value


def _git40(value: str, name: str) -> str:
    _text(value, name)
    if _GIT40.fullmatch(value) is None:
        raise MoonSecurityBoundaryEvidenceContractError(f"{name} must be git sha1")
    return value


def _tuple(value: Tuple[str, ...], name: str, *, required: bool = False) -> Tuple[str, ...]:
    if type(value) is not tuple or (required and not value):
        raise MoonSecurityBoundaryEvidenceContractError(f"{name} must be immutable tuple")
    for item in value:
        _text(item, name)
    return value


def _digest(domain: bytes, value: object) -> str:
    raw = json.dumps(asdict(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=list).encode()
    return sha256(domain + b"\0" + raw).hexdigest()


@dataclass(frozen=True)
class SecurityBoundaryNegativeEvidenceRecord:
    attack_id: str
    classification: str
    target_surface_digest: str
    required_evidence_class: str
    requirement_digest: str
    policy_pep_name: str
    evidence_boundary_pep_name: str
    pep_digest: str
    source_path: str
    source_blob_sha: str
    revision: str
    tree: str
    verifier_identity_digest: str
    input_cases: Tuple[str, ...]
    expected_denial: str
    observed_denials: Tuple[str, ...]
    observed_exception_types: Tuple[str, ...]
    execution_mode: str
    network_effect: bool
    filesystem_effect: bool
    database_effect: bool
    authority_mutation: bool
    repository_mutation: bool
    target_mutation: bool
    evidence_refs: Tuple[str, ...]
    record_digest: str = ""

    def validate(self) -> "SecurityBoundaryNegativeEvidenceRecord":
        for name in ("attack_id", "policy_pep_name", "evidence_boundary_pep_name", "source_path", "expected_denial", "execution_mode"):
            _text(getattr(self, name), name)
        _sha64(self.target_surface_digest, "target_surface_digest")
        _sha64(self.requirement_digest, "requirement_digest")
        _sha64(self.pep_digest, "pep_digest")
        _sha64(self.verifier_identity_digest, "verifier_identity_digest")
        _git40(self.source_blob_sha, "source_blob_sha")
        _git40(self.revision, "revision")
        _git40(self.tree, "tree")
        _tuple(self.input_cases, "input_cases", required=True)
        _tuple(self.observed_denials, "observed_denials", required=True)
        _tuple(self.observed_exception_types, "observed_exception_types", required=True)
        _tuple(self.evidence_refs, "evidence_refs", required=True)
        if self.classification not in _CLASSES:
            raise MoonSecurityBoundaryEvidenceContractError("classification invalid")
        if self.required_evidence_class not in _EVIDENCE_CLASSES:
            raise MoonSecurityBoundaryEvidenceContractError("evidence class invalid")
        expected_class = {
            "POST_OBSERVATION_DECISION": "ADMISSION_DECISION_NEGATIVE_EVIDENCE",
            "DOWNSTREAM_CURRENTNESS_GUARD": "DOWNSTREAM_CURRENTNESS_NEGATIVE_EVIDENCE",
        }[self.classification]
        if self.required_evidence_class != expected_class:
            raise MoonSecurityBoundaryEvidenceContractError("classification/evidence mismatch")
        if self.execution_mode != "PURE_BOUNDARY_DIRECT":
            raise MoonSecurityBoundaryEvidenceContractError("negative evidence must execute pure boundary directly")
        if len(self.input_cases) != len(self.observed_denials) or len(self.input_cases) != len(self.observed_exception_types):
            raise MoonSecurityBoundaryEvidenceContractError("negative evidence case cardinality mismatch")
        if any(value != self.expected_denial for value in self.observed_denials):
            raise MoonSecurityBoundaryEvidenceContractError("negative evidence denial mismatch")
        if any(value != "MoonFileWriteMediationError" for value in self.observed_exception_types):
            raise MoonSecurityBoundaryEvidenceContractError("negative evidence exception type mismatch")
        if any((self.network_effect, self.filesystem_effect, self.database_effect, self.authority_mutation, self.repository_mutation, self.target_mutation)):
            raise MoonSecurityBoundaryEvidenceContractError("effect-free evidence record carries effect")
        expected = _digest(RECORD_DOMAIN, self._without_digest())
        if self.record_digest and self.record_digest != expected:
            raise MoonSecurityBoundaryEvidenceContractError("negative evidence record digest mismatch")
        return self

    def _without_digest(self) -> "SecurityBoundaryNegativeEvidenceRecord":
        if not self.record_digest:
            return self
        payload = asdict(self)
        payload["record_digest"] = ""
        for name in ("input_cases", "observed_denials", "observed_exception_types", "evidence_refs"):
            payload[name] = tuple(payload[name])
        return SecurityBoundaryNegativeEvidenceRecord(**payload)

    def sealed(self) -> "SecurityBoundaryNegativeEvidenceRecord":
        self.validate()
        if self.record_digest:
            return self
        return SecurityBoundaryNegativeEvidenceRecord(**{**asdict(self), "record_digest": _digest(RECORD_DOMAIN, self)}).validate()

    def digest(self) -> str:
        return self.sealed().record_digest


@dataclass(frozen=True)
class SecurityRequirementEvidenceSatisfaction:
    attack_id: str
    classification: str
    required_evidence_class: str
    requirement_digest: str
    evidence_record_digest: str
    status: str
    evidence_refs: Tuple[str, ...]

    def validate(self) -> "SecurityRequirementEvidenceSatisfaction":
        _text(self.attack_id, "attack_id")
        if self.classification not in _CLASSES:
            raise MoonSecurityBoundaryEvidenceContractError("satisfaction class invalid")
        if self.required_evidence_class not in _EVIDENCE_CLASSES:
            raise MoonSecurityBoundaryEvidenceContractError("satisfaction evidence class invalid")
        _sha64(self.requirement_digest, "requirement_digest")
        _sha64(self.evidence_record_digest, "evidence_record_digest")
        if self.status != "CANONICAL_NEGATIVE_EVIDENCE_PRESENT":
            raise MoonSecurityBoundaryEvidenceContractError("security evidence status invalid")
        _tuple(self.evidence_refs, "evidence_refs", required=True)
        return self

    def digest(self) -> str:
        self.validate()
        return _digest(SATISFACTION_DOMAIN, self)


@dataclass(frozen=True)
class SecurityBoundaryEvidenceReport:
    inventory_digest: str
    taxonomy_digest: str
    policy_v2_digest: str
    policy_v2_topology_report_digest: str
    negative_evidence_record_digests: Tuple[str, ...]
    satisfaction_digests: Tuple[str, ...]
    closure_record_digests: Tuple[str, ...]
    global_carrier_digest: str
    remaining_security_requirement_keys: Tuple[str, ...]
    global_status: str
    next_evidence_plan: Tuple[str, ...]
    evidence_refs: Tuple[str, ...]

    def validate(self) -> "SecurityBoundaryEvidenceReport":
        for name in ("inventory_digest", "taxonomy_digest", "policy_v2_digest", "policy_v2_topology_report_digest", "global_carrier_digest"):
            _sha64(getattr(self, name), name)
        _tuple(self.negative_evidence_record_digests, "negative_evidence_record_digests", required=True)
        _tuple(self.satisfaction_digests, "satisfaction_digests", required=True)
        _tuple(self.closure_record_digests, "closure_record_digests", required=True)
        _tuple(self.remaining_security_requirement_keys, "remaining_security_requirement_keys")
        _tuple(self.next_evidence_plan, "next_evidence_plan", required=True)
        _tuple(self.evidence_refs, "evidence_refs", required=True)
        if len(self.negative_evidence_record_digests) != 2 or len(self.satisfaction_digests) != 2:
            raise MoonSecurityBoundaryEvidenceContractError("two security evidence records required")
        if len(self.closure_record_digests) != 7:
            raise MoonSecurityBoundaryEvidenceContractError("seven closure records required")
        if self.remaining_security_requirement_keys:
            raise MoonSecurityBoundaryEvidenceContractError("rehomed security requirements remain unsatisfied")
        if self.global_status != "UNKNOWN":
            raise MoonSecurityBoundaryEvidenceContractError("global status must remain UNKNOWN")
        return self

    def digest(self) -> str:
        self.validate()
        return _digest(REPORT_DOMAIN, self)
