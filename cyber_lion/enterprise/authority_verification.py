"""Provider-neutral authentication boundary for versioned AuthorityGrant contracts.

This module proves only that an AuthorityGrant payload was signed by the externally
bound issuer key for a trusted domain and expected mission context. Authentication
does not admit a grant as current, consult epoch/revocation state, or authorize an
effect.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable

from .authority_grant import AuthorityGrant, AuthorityGrantError

Verifier = Callable[[bytes, str, str, str], bool]
_DOMAIN_PREFIXES = {
    "1.0.0": b"CYBER-LION/AUTHORITY-GRANT/1.0.0\x00",
    "1.1.0": b"CYBER-LION/AUTHORITY-GRANT/1.1.0\x00",
}


class AuthorityVerificationError(AuthorityGrantError):
    """Raised when AuthorityGrant authentication cannot be proven."""


def _require_exact_authority_grant(grant: object) -> AuthorityGrant:
    """Reject polymorphic grant objects before any grant-controlled method executes."""
    if type(grant) is not AuthorityGrant:
        raise AuthorityVerificationError("grant must be exact AuthorityGrant")
    return grant


def _bounded_text(value: object, *, field_name: str, limit: int) -> str:
    if (
        not isinstance(value, str)
        or not value.strip()
        or len(value) > limit
        or "\x00" in value
    ):
        raise AuthorityVerificationError(f"{field_name} is invalid")
    return value


@dataclass(frozen=True)
class AuthorityVerificationContext:
    """Trusted expected context supplied outside the untrusted grant."""

    trust_domain: str
    tenant_id: str
    organization_id: str
    mission_id: str

    def validate(self) -> "AuthorityVerificationContext":
        _bounded_text(self.trust_domain, field_name="trust_domain", limit=256)
        _bounded_text(self.tenant_id, field_name="tenant_id", limit=256)
        _bounded_text(self.organization_id, field_name="organization_id", limit=256)
        _bounded_text(self.mission_id, field_name="mission_id", limit=256)
        return self


@dataclass(frozen=True)
class IssuerKeyBinding:
    """Externally trusted issuer-to-key binding; never selected by AuthorityGrant."""

    issuer_subject_id: str
    trust_domain: str
    key_id: str
    algorithm: str

    def validate(self) -> "IssuerKeyBinding":
        _bounded_text(
            self.issuer_subject_id, field_name="issuer_subject_id", limit=256
        )
        _bounded_text(self.trust_domain, field_name="trust_domain", limit=256)
        _bounded_text(self.key_id, field_name="key_id", limit=256)
        _bounded_text(self.algorithm, field_name="algorithm", limit=128)
        return self


@dataclass(frozen=True)
class AuthenticatedAuthorityGrant:
    """Authentication evidence only; this object carries no execution permission."""

    grant_id: str
    issuer_subject_id: str
    subject_id: str
    trust_domain: str
    tenant_id: str
    organization_id: str
    mission_id: str
    key_id: str
    algorithm: str
    signed_payload: bytes
    grant_digest: str


def authority_grant_signature_payload(
    grant: AuthorityGrant, trust_domain: str
) -> bytes:
    """Build deterministic domain-separated bytes for the grant's signed version."""
    grant = _require_exact_authority_grant(grant)
    _bounded_text(trust_domain, field_name="trust_domain", limit=256)
    try:
        canonical = grant.canonical_payload()
        prefix = _DOMAIN_PREFIXES[grant.schema_version]
    except AuthorityGrantError as exc:
        raise AuthorityVerificationError(
            "grant contract validation failed"
        ) from exc
    except KeyError as exc:
        raise AuthorityVerificationError(
            "unsupported authority-grant signed contract version"
        ) from exc
    return prefix + trust_domain.encode("utf-8") + b"\x00" + canonical


def authenticate_authority_grant(
    grant: AuthorityGrant,
    issuer_keys: Iterable[IssuerKeyBinding],
    verifier: Verifier,
    *,
    context: AuthorityVerificationContext,
) -> AuthenticatedAuthorityGrant:
    """Authenticate a grant without admitting it as current or executable authority."""
    grant = _require_exact_authority_grant(grant)
    if not isinstance(context, AuthorityVerificationContext):
        raise AuthorityVerificationError(
            "context must be AuthorityVerificationContext"
        )
    context.validate()
    try:
        grant.validate()
    except AuthorityGrantError as exc:
        raise AuthorityVerificationError(
            "grant contract validation failed"
        ) from exc

    expected_context = (
        context.tenant_id,
        context.organization_id,
        context.mission_id,
    )
    actual_context = (grant.tenant_id, grant.organization_id, grant.mission_id)
    if actual_context != expected_context:
        raise AuthorityVerificationError(
            "grant does not bind to expected authority context"
        )

    try:
        bindings = tuple(issuer_keys)
    except Exception as exc:
        raise AuthorityVerificationError(
            "issuer key bindings unavailable"
        ) from exc

    eligible: list[IssuerKeyBinding] = []
    for binding in bindings:
        if not isinstance(binding, IssuerKeyBinding):
            raise AuthorityVerificationError(
                "issuer key binding has invalid type"
            )
        binding.validate()
        if (
            binding.issuer_subject_id == grant.issuer_subject_id
            and binding.trust_domain == context.trust_domain
        ):
            eligible.append(binding)

    if len(eligible) != 1:
        raise AuthorityVerificationError(
            "issuer key binding is missing or ambiguous"
        )

    binding = eligible[0]
    payload = authority_grant_signature_payload(grant, context.trust_domain)
    try:
        accepted = verifier(
            payload, grant.signature, binding.key_id, binding.algorithm
        )
    except Exception as exc:
        raise AuthorityVerificationError(
            "authority-grant verifier failed closed"
        ) from exc
    if accepted is not True:
        raise AuthorityVerificationError(
            "authority-grant signature verification failed"
        )

    return AuthenticatedAuthorityGrant(
        grant_id=grant.grant_id,
        issuer_subject_id=grant.issuer_subject_id,
        subject_id=grant.subject_id,
        trust_domain=context.trust_domain,
        tenant_id=grant.tenant_id,
        organization_id=grant.organization_id,
        mission_id=grant.mission_id,
        key_id=binding.key_id,
        algorithm=binding.algorithm,
        signed_payload=payload,
        grant_digest=grant.digest(),
    )
