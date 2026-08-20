"""Live authority admission over canonical source + persistent epoch/revocation state.

Authentication, currentness, epoch/revocation, root-anchor, and replay are all required.
The result is evidence for downstream policy; it is not execution permission.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib

from .authority_grant import AuthorityGrant, AuthorityGrantError, validate_attenuation
from .authority_source import AuthorityLookupKey, AuthoritySource, AuthoritySourceError
from .authority_verification import (
    AuthenticatedAuthorityGrant,
    AuthorityVerificationContext,
    IssuerKeyBinding,
    Verifier,
    authenticate_authority_grant,
)
from .persistent_authority_state import (
    DurableReplayGuard,
    PersistentAuthorityStateError,
    PersistentEpochStateProvider,
    PersistentRootAnchorProvider,
)


class LiveAuthorityAdmissionError(RuntimeError):
    """Raised when current live authority cannot be proven fail-closed."""


@dataclass(frozen=True)
class LiveAdmittedAuthority:
    repository: str
    pr_number: int
    base_sha: str
    head_sha: str
    mission_id: str
    grant_id: str
    lineage_digest: str
    provenance_id: str
    epoch: int
    authority_ceiling: str
    authenticated_grant_digests: tuple[str, ...]
    replay_digest: str


class LiveAuthorityAdmission:
    """Compose exact canonical authority with durable current-state admission."""

    def __init__(
        self,
        *,
        authority_source: AuthoritySource,
        context: AuthorityVerificationContext,
        issuer_keys: tuple[IssuerKeyBinding, ...],
        signature_verifier: Verifier,
        epoch_provider: PersistentEpochStateProvider,
        root_provider: PersistentRootAnchorProvider,
        replay_guard: DurableReplayGuard,
    ) -> None:
        if not isinstance(authority_source, AuthoritySource):
            raise LiveAuthorityAdmissionError("authority_source is invalid")
        if type(context) is not AuthorityVerificationContext:
            raise LiveAuthorityAdmissionError("context is invalid")
        context.validate()
        if type(issuer_keys) is not tuple or not issuer_keys:
            raise LiveAuthorityAdmissionError("issuer_keys must be a non-empty tuple")
        for binding in issuer_keys:
            if not isinstance(binding, IssuerKeyBinding):
                raise LiveAuthorityAdmissionError("issuer key binding is invalid")
            binding.validate()
        if not callable(signature_verifier):
            raise LiveAuthorityAdmissionError("signature verifier is unavailable")
        self._source = authority_source
        self._context = context
        self._issuer_keys = issuer_keys
        self._verifier = signature_verifier
        self._epoch_provider = epoch_provider
        self._root_provider = root_provider
        self._replay_guard = replay_guard

    @staticmethod
    def _utc(value: str) -> datetime:
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except (AttributeError, ValueError) as exc:
            raise LiveAuthorityAdmissionError("grant timestamp is invalid") from exc
        if parsed.tzinfo is None:
            raise LiveAuthorityAdmissionError("grant timestamp must be timezone-aware")
        return parsed.astimezone(timezone.utc)

    def admit(
        self,
        *,
        repository: str,
        pr_number: int,
        base_sha: str,
        head_sha: str,
        mission_id: str,
        grant_id: str,
        now: datetime,
        replay_nonce: str,
    ) -> LiveAdmittedAuthority:
        if now.tzinfo is None:
            raise LiveAuthorityAdmissionError("trusted now must be timezone-aware")
        if mission_id != self._context.mission_id:
            raise LiveAuthorityAdmissionError("mission does not match trusted authority context")
        if not isinstance(replay_nonce, str) or not replay_nonce.strip():
            raise LiveAuthorityAdmissionError("replay_nonce is required")

        key = AuthorityLookupKey(repository, pr_number, base_sha, head_sha, mission_id, grant_id)
        try:
            record = self._source.resolve_exact(key)
        except AuthoritySourceError as exc:
            raise LiveAuthorityAdmissionError("canonical authority lookup failed closed") from exc
        record.validate()

        context_key = (
            self._context.trust_domain,
            self._context.tenant_id,
            self._context.organization_id,
            self._context.mission_id,
        )
        try:
            state = self._epoch_provider.current(context_key)
            root = self._root_provider.resolve(context_key, state.epoch)
        except PersistentAuthorityStateError as exc:
            raise LiveAuthorityAdmissionError("persistent authority state unavailable") from exc

        if not record.lineage:
            raise LiveAuthorityAdmissionError("authority lineage is empty")
        root_grant = record.lineage[0]
        if root.root_grant_id != root_grant.grant_id or root.root_grant_digest != root_grant.digest():
            raise LiveAuthorityAdmissionError("canonical root anchor mismatch")

        authenticated: list[AuthenticatedAuthorityGrant] = []
        previous: AuthorityGrant | None = None
        current = now.astimezone(timezone.utc)
        for grant in record.lineage:
            if type(grant) is not AuthorityGrant:
                raise LiveAuthorityAdmissionError("lineage contains invalid grant type")
            try:
                grant.validate()
            except AuthorityGrantError as exc:
                raise LiveAuthorityAdmissionError("grant contract is invalid") from exc
            if grant.epoch != state.epoch:
                raise LiveAuthorityAdmissionError("grant epoch is stale or future")
            if grant.grant_id in state.revoked_grant_ids:
                raise LiveAuthorityAdmissionError("grant is revoked")
            issued = self._utc(grant.issued_at)
            expires = self._utc(grant.expires_at)
            if current < issued:
                raise LiveAuthorityAdmissionError("grant is not yet current")
            if current >= expires:
                raise LiveAuthorityAdmissionError("grant is expired")
            if previous is not None:
                try:
                    validate_attenuation(previous, grant)
                except AuthorityGrantError as exc:
                    raise LiveAuthorityAdmissionError("authority attenuation failed") from exc
            try:
                auth = authenticate_authority_grant(
                    grant,
                    self._issuer_keys,
                    self._verifier,
                    context=self._context,
                )
            except Exception as exc:
                raise LiveAuthorityAdmissionError("authority signature authentication failed") from exc
            authenticated.append(auth)
            previous = grant

        leaf = record.lineage[-1]
        replay_material = (
            f"{record.lineage_digest}\x00{leaf.grant_id}\x00{repository}\x00{pr_number}\x00"
            f"{base_sha}\x00{head_sha}\x00{mission_id}\x00{state.epoch}\x00{replay_nonce}"
        ).encode("utf-8")
        replay_digest = hashlib.sha256(replay_material).hexdigest()
        try:
            accepted = self._replay_guard.consume(replay_digest, consumed_at=current.isoformat())
        except PersistentAuthorityStateError as exc:
            raise LiveAuthorityAdmissionError("durable replay state unavailable") from exc
        if accepted is not True:
            raise LiveAuthorityAdmissionError("authority admission replay rejected")

        return LiveAdmittedAuthority(
            repository=repository,
            pr_number=pr_number,
            base_sha=base_sha,
            head_sha=head_sha,
            mission_id=mission_id,
            grant_id=leaf.grant_id,
            lineage_digest=record.lineage_digest,
            provenance_id=record.provenance_id,
            epoch=state.epoch,
            authority_ceiling=leaf.authority_ceiling,
            authenticated_grant_digests=tuple(item.grant_digest for item in authenticated),
            replay_digest=replay_digest,
        )
