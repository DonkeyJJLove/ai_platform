"""Exact non-authoritative binding between BeanSpec and candidate implementation."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import re
from typing import Any, Mapping, Tuple

from .bean import BeanContractError, BeanSpec

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
CANDIDATE_STATES = frozenset({"BUILT", "VERIFIED", "REJECTED", "SUPERSEDED"})


def _text(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip() or "\x00" in value:
        raise BeanContractError(f"{name} is invalid")
    return value


def _sha(value: Any, name: str) -> str:
    value = _text(value, name)
    if not _SHA256.fullmatch(value):
        raise BeanContractError(f"{name} must be sha256 hex")
    return value


def _tuple(value: Any, name: str, *, nonempty: bool = False) -> Tuple[str, ...]:
    if type(value) is not tuple or (nonempty and not value):
        raise BeanContractError(f"{name} must be an immutable tuple")
    for item in value:
        _text(item, name)
    if len(set(value)) != len(value):
        raise BeanContractError(f"{name} must be unique")
    return value


def _digest(domain: bytes, value: Mapping[str, Any]) -> str:
    raw = json.dumps(dict(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return sha256(domain + b"\0" + raw).hexdigest()


@dataclass(frozen=True)
class BeanCandidate:
    candidate_id: str
    bean_id: str
    spec_digest: str
    implementation_digest: str
    builder_identity_digest: str
    build_evidence_refs: Tuple[str, ...]
    acceptance_evidence_refs: Tuple[str, ...]
    verifier_identity_digests: Tuple[str, ...]
    verification_evidence_refs: Tuple[str, ...]
    state: str = "BUILT"
    previous_candidate_digest: str = ""
    authority_effect: str = "NONE"
    execution_effect: str = "NONE"
    repository_ref_effect: str = "NONE"
    external_effect: str = "NONE"

    def validate(self) -> "BeanCandidate":
        for name in ("candidate_id", "bean_id"):
            _text(getattr(self, name), name)
        for name in ("spec_digest", "implementation_digest", "builder_identity_digest"):
            _sha(getattr(self, name), name)
        _tuple(self.build_evidence_refs, "build_evidence_refs", nonempty=True)
        _tuple(self.acceptance_evidence_refs, "acceptance_evidence_refs")
        _tuple(self.verifier_identity_digests, "verifier_identity_digests")
        _tuple(self.verification_evidence_refs, "verification_evidence_refs")
        if self.state not in CANDIDATE_STATES:
            raise BeanContractError("invalid BeanCandidate state")
        if self.previous_candidate_digest:
            _sha(self.previous_candidate_digest, "previous_candidate_digest")
        for name in ("authority_effect", "execution_effect", "repository_ref_effect", "external_effect"):
            if getattr(self, name) != "NONE":
                raise BeanContractError(f"BeanCandidate cannot carry {name}")
        if self.state == "VERIFIED":
            if not self.verifier_identity_digests or not self.verification_evidence_refs or not self.acceptance_evidence_refs:
                raise BeanContractError("VERIFIED candidate requires verifier and acceptance evidence")
            if self.builder_identity_digest in self.verifier_identity_digests:
                raise BeanContractError("builder cannot be a final verifier of its own candidate")
        return self

    def canonical_payload(self) -> Mapping[str, Any]:
        return asdict(self)

    def digest(self) -> str:
        self.validate()
        return _digest(b"LION/BEAN-CANDIDATE/1", self.canonical_payload())


def bind_candidate_to_spec(candidate: BeanCandidate, spec: BeanSpec) -> None:
    candidate.validate()
    spec.validate()
    if candidate.bean_id != spec.bean_id:
        raise BeanContractError("candidate bean_id substitution detected")
    if candidate.spec_digest != spec.spec_digest():
        raise BeanContractError("candidate spec substitution detected")
    if spec.implementation_digest and candidate.implementation_digest != spec.implementation_digest:
        raise BeanContractError("candidate implementation substitution detected")


def verify_candidate(
    *,
    candidate: BeanCandidate,
    spec: BeanSpec,
    verifier_identity_digests: Tuple[str, ...],
    verification_evidence_refs: Tuple[str, ...],
    acceptance_evidence_refs: Tuple[str, ...],
) -> BeanCandidate:
    """Return a separately verified candidate; never authority or admission."""
    from dataclasses import replace

    bind_candidate_to_spec(candidate, spec)
    if candidate.state != "BUILT":
        raise BeanContractError("only BUILT candidate may enter verification")
    verified = replace(
        candidate,
        state="VERIFIED",
        verifier_identity_digests=verifier_identity_digests,
        verification_evidence_refs=verification_evidence_refs,
        acceptance_evidence_refs=acceptance_evidence_refs,
    )
    verified.validate()
    bind_candidate_to_spec(verified, spec)
    return verified
