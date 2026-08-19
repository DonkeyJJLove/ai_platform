"""Mission-scoped monotonic epoch/revocation admission for AuthorityGrant v1.

This module adds epoch-specific revocation admission after cryptographic authentication.
A trusted process bootstrap must install exactly one canonical state per authority context;
normal admission callers cannot select a snapshot, owner, or registry. This module does
not authorize actions, check wall-clock currentness, persist revocation state, coordinate
multiple processes/nodes, or execute effects.
"""
from __future__ import annotations

from dataclasses import dataclass
from threading import Lock
from typing import Iterable

from .authority_grant import AuthorityGrant, AuthorityGrantError
from .authority_verification import (
    AuthenticatedAuthorityGrant,
    AuthorityVerificationContext,
    IssuerKeyBinding,
    Verifier,
    authenticate_authority_grant,
    authority_grant_signature_payload,
)


class AuthorityRevocationError(AuthorityGrantError):
    """Raised when epoch/revocation admission cannot be proven safely."""


def _bounded_text(value: object, *, field_name: str, limit: int = 256) -> str:
    if (
        not isinstance(value, str)
        or not value.strip()
        or len(value) > limit
        or "\x00" in value
    ):
        raise AuthorityRevocationError(f"{field_name} is invalid")
    return value


@dataclass(frozen=True)
class AuthorityEpochState:
    """Immutable mission-scoped epoch and revocation snapshot."""

    trust_domain: str
    tenant_id: str
    organization_id: str
    mission_id: str
    epoch: int
    revoked_grant_ids: tuple[str, ...] = ()

    def validate(self) -> "AuthorityEpochState":
        if type(self) is not AuthorityEpochState:
            raise AuthorityRevocationError("epoch state must be exact AuthorityEpochState")
        _bounded_text(self.trust_domain, field_name="trust_domain")
        _bounded_text(self.tenant_id, field_name="tenant_id")
        _bounded_text(self.organization_id, field_name="organization_id")
        _bounded_text(self.mission_id, field_name="mission_id")
        if not isinstance(self.epoch, int) or isinstance(self.epoch, bool) or self.epoch < 0:
            raise AuthorityRevocationError("epoch must be a non-negative integer")
        if type(self.revoked_grant_ids) is not tuple:
            raise AuthorityRevocationError("revoked_grant_ids must be an immutable tuple")
        for grant_id in self.revoked_grant_ids:
            _bounded_text(grant_id, field_name="revoked_grant_id")
        if len(set(self.revoked_grant_ids)) != len(self.revoked_grant_ids):
            raise AuthorityRevocationError("revoked_grant_ids must be unique")
        return self

    def authority_context(self) -> tuple[str, str, str, str]:
        return (
            self.trust_domain,
            self.tenant_id,
            self.organization_id,
            self.mission_id,
        )


@dataclass(frozen=True)
class EpochAdmittedAuthorityGrant:
    """Evidence that an authenticated grant is admitted in one exact mission epoch."""

    grant_id: str
    subject_id: str
    trust_domain: str
    tenant_id: str
    organization_id: str
    mission_id: str
    epoch: int
    grant_digest: str


def validate_epoch_transition(
    previous: AuthorityEpochState,
    candidate: AuthorityEpochState,
) -> AuthorityEpochState:
    """Require monotonic epoch and monotonic revocation within one epoch."""
    if type(previous) is not AuthorityEpochState or type(candidate) is not AuthorityEpochState:
        raise AuthorityRevocationError("epoch transition requires exact AuthorityEpochState")
    previous.validate()
    candidate.validate()

    if previous.authority_context() != candidate.authority_context():
        raise AuthorityRevocationError("authority epoch context cannot change")
    if candidate.epoch < previous.epoch:
        raise AuthorityRevocationError("authority epoch cannot roll back")
    if candidate.epoch == previous.epoch and not set(previous.revoked_grant_ids).issubset(
        candidate.revoked_grant_ids
    ):
        raise AuthorityRevocationError("revocation cannot be removed within the same epoch")
    return candidate


def _trusted_context(
    context: AuthorityVerificationContext,
) -> tuple[str, str, str, str]:
    return (
        context.trust_domain,
        context.tenant_id,
        context.organization_id,
        context.mission_id,
    )


class AuthorityEpochStateOwner:
    """Process-local monotonic owner; direct construction does not make it canonical."""

    def __init__(self, initial_state: AuthorityEpochState) -> None:
        if type(initial_state) is not AuthorityEpochState:
            raise AuthorityRevocationError(
                "initial state must be exact AuthorityEpochState"
            )
        initial_state.validate()
        self._lock = Lock()
        self._state = initial_state

    def current(self) -> AuthorityEpochState:
        """Return the immutable current state snapshot."""
        with self._lock:
            return self._state

    def advance(self, candidate: AuthorityEpochState) -> AuthorityEpochState:
        """Atomically replace current state only after a valid monotonic transition."""
        if type(candidate) is not AuthorityEpochState:
            raise AuthorityRevocationError(
                "candidate state must be exact AuthorityEpochState"
            )
        with self._lock:
            accepted = validate_epoch_transition(self._state, candidate)
            self._state = accepted
            return accepted

    def _require_context(
        self,
        trusted_context: tuple[str, str, str, str],
    ) -> None:
        with self._lock:
            if self._state.authority_context() != trusted_context:
                raise AuthorityRevocationError(
                    "epoch state owner does not bind to trusted authority context"
                )

    def _admit_authenticated(
        self,
        grant: AuthorityGrant,
        authenticated: AuthenticatedAuthorityGrant,
        *,
        context: AuthorityVerificationContext,
        trusted_context: tuple[str, str, str, str],
    ) -> EpochAdmittedAuthorityGrant:
        # Hold the owner lock across final currentness selection and admission so
        # advance() cannot interleave between state selection and revocation decision.
        with self._lock:
            if self._state.authority_context() != trusted_context:
                raise AuthorityRevocationError(
                    "epoch state owner does not bind to trusted authority context"
                )
            return _admit_authenticated_grant(
                grant,
                authenticated,
                context=context,
                epoch_state=self._state,
            )


class _AuthorityEpochRegistry:
    """One-shot process-local canonical owner registry keyed by authority context."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._owners: dict[tuple[str, str, str, str], AuthorityEpochStateOwner] = {}

    def register(self, initial_state: AuthorityEpochState) -> AuthorityEpochState:
        """Install the one canonical owner for a context; replacement is forbidden."""
        if type(initial_state) is not AuthorityEpochState:
            raise AuthorityRevocationError(
                "canonical initial state must be exact AuthorityEpochState"
            )
        initial_state.validate()
        key = initial_state.authority_context()
        candidate_owner = AuthorityEpochStateOwner(initial_state)
        with self._lock:
            if key in self._owners:
                raise AuthorityRevocationError(
                    "canonical authority epoch context is already registered"
                )
            self._owners[key] = candidate_owner
        return initial_state

    def resolve(
        self,
        trusted_context: tuple[str, str, str, str],
    ) -> AuthorityEpochStateOwner:
        """Resolve only the previously bootstrapped canonical owner for a context."""
        if type(trusted_context) is not tuple or len(trusted_context) != 4:
            raise AuthorityRevocationError("trusted authority context is invalid")
        with self._lock:
            owner = self._owners.get(trusted_context)
        if owner is None:
            raise AuthorityRevocationError(
                "canonical authority epoch context is not registered"
            )
        return owner

    def advance(self, candidate: AuthorityEpochState) -> AuthorityEpochState:
        """Advance the already-registered canonical owner for candidate's context."""
        if type(candidate) is not AuthorityEpochState:
            raise AuthorityRevocationError(
                "candidate state must be exact AuthorityEpochState"
            )
        candidate.validate()
        key = candidate.authority_context()
        with self._lock:
            owner = self._owners.get(key)
        if owner is None:
            raise AuthorityRevocationError(
                "canonical authority epoch context is not registered"
            )
        return owner.advance(candidate)


# This registry is the process-local canonical state authority. Trusted bootstrap code
# installs initial context state before normal admission. There is deliberately no
# unregister or owner-replacement path in this B2 slice.
_CANONICAL_AUTHORITY_EPOCH_REGISTRY = _AuthorityEpochRegistry()


def register_canonical_authority_epoch_state(
    initial_state: AuthorityEpochState,
) -> AuthorityEpochState:
    """Trusted-bootstrap installation of one canonical process-local context state."""
    return _CANONICAL_AUTHORITY_EPOCH_REGISTRY.register(initial_state)


def advance_canonical_authority_epoch_state(
    candidate: AuthorityEpochState,
) -> AuthorityEpochState:
    """Monotonically advance the canonical process-local state for its context."""
    return _CANONICAL_AUTHORITY_EPOCH_REGISTRY.advance(candidate)


def _admit_authenticated_grant(
    grant: AuthorityGrant,
    authenticated: AuthenticatedAuthorityGrant,
    *,
    context: AuthorityVerificationContext,
    epoch_state: AuthorityEpochState,
) -> EpochAdmittedAuthorityGrant:
    if type(authenticated) is not AuthenticatedAuthorityGrant:
        raise AuthorityRevocationError(
            "authentication result must be exact AuthenticatedAuthorityGrant"
        )

    expected_payload = authority_grant_signature_payload(grant, context.trust_domain)
    expected_digest = grant.digest()
    expected_binding = (
        grant.grant_id,
        grant.issuer_subject_id,
        grant.subject_id,
        context.trust_domain,
        grant.tenant_id,
        grant.organization_id,
        grant.mission_id,
        expected_payload,
        expected_digest,
    )
    actual_binding = (
        authenticated.grant_id,
        authenticated.issuer_subject_id,
        authenticated.subject_id,
        authenticated.trust_domain,
        authenticated.tenant_id,
        authenticated.organization_id,
        authenticated.mission_id,
        authenticated.signed_payload,
        authenticated.grant_digest,
    )
    if actual_binding != expected_binding:
        raise AuthorityRevocationError("authenticated grant binding does not match raw grant")

    if grant.epoch != epoch_state.epoch:
        raise AuthorityRevocationError("grant epoch is not the admitted mission epoch")
    if grant.grant_id in epoch_state.revoked_grant_ids:
        raise AuthorityRevocationError("grant is revoked in the admitted mission epoch")

    return EpochAdmittedAuthorityGrant(
        grant_id=grant.grant_id,
        subject_id=grant.subject_id,
        trust_domain=context.trust_domain,
        tenant_id=grant.tenant_id,
        organization_id=grant.organization_id,
        mission_id=grant.mission_id,
        epoch=grant.epoch,
        grant_digest=authenticated.grant_digest,
    )


def authenticate_and_admit_authority_grant(
    grant: AuthorityGrant,
    issuer_keys: Iterable[IssuerKeyBinding],
    verifier: Verifier,
    *,
    context: AuthorityVerificationContext,
) -> EpochAdmittedAuthorityGrant:
    """Authenticate, then admit only against the canonical current context state."""
    if type(grant) is not AuthorityGrant:
        raise AuthorityRevocationError("grant must be exact AuthorityGrant v1")
    if type(context) is not AuthorityVerificationContext:
        raise AuthorityRevocationError(
            "context must be exact AuthorityVerificationContext"
        )

    context.validate()
    trusted_context = _trusted_context(context)
    # Resolve the canonical owner before invoking the verifier. Unregistered contexts
    # fail closed, and normal callers have no owner/state/registry argument to select.
    epoch_state_owner = _CANONICAL_AUTHORITY_EPOCH_REGISTRY.resolve(trusted_context)
    epoch_state_owner._require_context(trusted_context)

    authenticated = authenticate_authority_grant(
        grant,
        issuer_keys,
        verifier,
        context=context,
    )
    # The owner identity cannot be replaced in the registry. Re-enter the same canonical
    # owner after authentication so epoch/revocation changes during verification are seen.
    return epoch_state_owner._admit_authenticated(
        grant,
        authenticated,
        context=context,
        trusted_context=trusted_context,
    )
