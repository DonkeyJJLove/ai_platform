"""Mission-scoped monotonic epoch/revocation admission for AuthorityGrant.

This module adds epoch-specific revocation admission after cryptographic authentication.
A trusted process bootstrap must install exactly one canonical state per authority context;
normal admission callers cannot select a snapshot, owner, or registry.

Full-lineage admission composes the existing single-grant authentication and one-hop
attenuation primitives. A trusted root anchor is supplied from outside the candidate
lineage, every hop is authenticated, and final epoch/revocation admission is atomic
against one canonical state snapshot. Lineage evidence is not execution permission.

This module does not authorize actions, check wall-clock currentness, persist revocation
state, coordinate multiple processes/nodes, or execute effects.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import re
from threading import Lock
from typing import Iterable

from .authority_grant import (
    AuthorityGrant,
    AuthorityGrantError,
    validate_attenuation,
)
from .authority_verification import (
    AuthenticatedAuthorityGrant,
    AuthorityVerificationContext,
    IssuerKeyBinding,
    Verifier,
    authenticate_authority_grant,
    authority_grant_signature_payload,
)

_GRANT_DIGEST_RE = re.compile(r"^[0-9a-f]{64}$")
_LINEAGE_DOMAIN_PREFIX = b"CYBER-LION/AUTHORITY-LINEAGE/1.0.0\x00"


class AuthorityRevocationError(AuthorityGrantError):
    """Raised when epoch/revocation or lineage admission cannot be proven safely."""


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


@dataclass(frozen=True)
class AuthorityLineageRootAnchor:
    """Trusted external identity of the exact root grant for one lineage."""

    root_grant_id: str
    root_grant_digest: str

    def validate(self) -> "AuthorityLineageRootAnchor":
        if type(self) is not AuthorityLineageRootAnchor:
            raise AuthorityRevocationError(
                "root anchor must be exact AuthorityLineageRootAnchor"
            )
        _bounded_text(self.root_grant_id, field_name="root_grant_id")
        if (
            not isinstance(self.root_grant_digest, str)
            or not _GRANT_DIGEST_RE.fullmatch(self.root_grant_digest)
        ):
            raise AuthorityRevocationError("root_grant_digest must be canonical sha256 hex")
        return self


@dataclass(frozen=True)
class EpochAdmittedAuthorityLineage:
    """Authenticated root-to-leaf lineage evidence; never execution permission."""

    root_grant_id: str
    leaf_grant_id: str
    leaf_subject_id: str
    grant_ids: tuple[str, ...]
    grant_digests: tuple[str, ...]
    lineage_digest: str
    trust_domain: str
    tenant_id: str
    organization_id: str
    mission_id: str
    epoch: int


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

    def _admit_authenticated_lineage(
        self,
        lineage: tuple[AuthorityGrant, ...],
        authenticated_lineage: tuple[AuthenticatedAuthorityGrant, ...],
        *,
        context: AuthorityVerificationContext,
        trusted_context: tuple[str, str, str, str],
    ) -> tuple[EpochAdmittedAuthorityGrant, ...]:
        """Admit every authenticated hop against one exact current state snapshot."""
        if type(lineage) is not tuple or type(authenticated_lineage) is not tuple:
            raise AuthorityRevocationError("lineage admission requires immutable tuples")
        if not lineage or len(lineage) != len(authenticated_lineage):
            raise AuthorityRevocationError("lineage authentication evidence is incomplete")

        with self._lock:
            if self._state.authority_context() != trusted_context:
                raise AuthorityRevocationError(
                    "epoch state owner does not bind to trusted authority context"
                )
            return tuple(
                _admit_authenticated_grant(
                    grant,
                    authenticated,
                    context=context,
                    epoch_state=self._state,
                )
                for grant, authenticated in zip(lineage, authenticated_lineage)
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
# unregister or owner-replacement path in this slice.
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
        raise AuthorityRevocationError(
            "authenticated grant binding does not match raw grant"
        )

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


def _lineage_digest(grant_digests: tuple[str, ...]) -> str:
    if type(grant_digests) is not tuple or not grant_digests:
        raise AuthorityRevocationError("grant_digests must be a non-empty immutable tuple")
    if any(
        not isinstance(value, str) or not _GRANT_DIGEST_RE.fullmatch(value)
        for value in grant_digests
    ):
        raise AuthorityRevocationError("grant_digests contain invalid values")
    payload = _LINEAGE_DOMAIN_PREFIX + b"\x00".join(
        value.encode("ascii") for value in grant_digests
    )
    return hashlib.sha256(payload).hexdigest()


def authenticate_and_admit_authority_grant(
    grant: AuthorityGrant,
    issuer_keys: Iterable[IssuerKeyBinding],
    verifier: Verifier,
    *,
    context: AuthorityVerificationContext,
) -> EpochAdmittedAuthorityGrant:
    """Authenticate, then admit only against the canonical current context state."""
    if type(grant) is not AuthorityGrant:
        raise AuthorityRevocationError("grant must be exact AuthorityGrant")
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


def authenticate_and_admit_authority_lineage(
    lineage: tuple[AuthorityGrant, ...],
    issuer_keys: Iterable[IssuerKeyBinding],
    verifier: Verifier,
    *,
    context: AuthorityVerificationContext,
    root_anchor: AuthorityLineageRootAnchor,
) -> EpochAdmittedAuthorityLineage:
    """Authenticate and atomically admit one explicitly ordered trusted-root lineage."""
    if type(lineage) is not tuple or not lineage:
        raise AuthorityRevocationError("lineage must be a non-empty immutable tuple")
    if any(type(grant) is not AuthorityGrant for grant in lineage):
        raise AuthorityRevocationError("lineage must contain exact AuthorityGrant values")
    if type(context) is not AuthorityVerificationContext:
        raise AuthorityRevocationError(
            "context must be exact AuthorityVerificationContext"
        )
    if type(root_anchor) is not AuthorityLineageRootAnchor:
        raise AuthorityRevocationError(
            "root_anchor must be exact AuthorityLineageRootAnchor"
        )

    context.validate()
    root_anchor.validate()

    root = lineage[0]
    if root.parent_grant_id is not None:
        raise AuthorityRevocationError("trusted lineage root must not have a parent")

    grant_ids = tuple(grant.grant_id for grant in lineage)
    if len(set(grant_ids)) != len(grant_ids):
        raise AuthorityRevocationError("lineage grant IDs must be unique and acyclic")

    if root.grant_id != root_anchor.root_grant_id:
        raise AuthorityRevocationError("lineage root does not match trusted root grant ID")
    root_digest = root.digest()
    if root_digest != root_anchor.root_grant_digest:
        raise AuthorityRevocationError("lineage root does not match trusted root digest")

    for parent, child in zip(lineage, lineage[1:]):
        validate_attenuation(parent, child)

    try:
        bindings = tuple(issuer_keys)
    except Exception as exc:
        raise AuthorityRevocationError("issuer key bindings unavailable") from exc

    trusted_context = _trusted_context(context)
    # Resolve before cryptographic verification so unregistered contexts fail before any
    # external verifier call. Re-enter the same owner after every signature is checked.
    epoch_state_owner = _CANONICAL_AUTHORITY_EPOCH_REGISTRY.resolve(trusted_context)
    epoch_state_owner._require_context(trusted_context)

    authenticated_lineage = tuple(
        authenticate_authority_grant(
            grant,
            bindings,
            verifier,
            context=context,
        )
        for grant in lineage
    )

    admitted = epoch_state_owner._admit_authenticated_lineage(
        lineage,
        authenticated_lineage,
        context=context,
        trusted_context=trusted_context,
    )
    grant_digests = tuple(item.grant_digest for item in admitted)

    return EpochAdmittedAuthorityLineage(
        root_grant_id=root.grant_id,
        leaf_grant_id=lineage[-1].grant_id,
        leaf_subject_id=lineage[-1].subject_id,
        grant_ids=grant_ids,
        grant_digests=grant_digests,
        lineage_digest=_lineage_digest(grant_digests),
        trust_domain=context.trust_domain,
        tenant_id=context.tenant_id,
        organization_id=context.organization_id,
        mission_id=context.mission_id,
        epoch=admitted[0].epoch,
    )
