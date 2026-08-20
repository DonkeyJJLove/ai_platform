"""Live authority admission over canonical source + persistent epoch/revocation state.

Authentication, currentness, epoch/revocation, root-anchor, and replay are all required.
The result is evidence for downstream policy; it is not execution permission.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json

from .authority_grant import AuthorityGrant, AuthorityGrantError, validate_attenuation
from .authority_source import AuthorityLookupKey, AuthorityLineageRecord, AuthoritySource, AuthoritySourceError
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
    PersistentEpochSnapshot,
    PersistentEpochStateProvider,
    PersistentRootAnchor,
    PersistentRootAnchorProvider,
)


class LiveAuthorityAdmissionError(RuntimeError):
    """Raised when current live authority cannot be proven fail-closed."""


def _sha256(value: object, *, name: str) -> str:
    if not isinstance(value, str) or len(value) != 64:
        raise LiveAuthorityAdmissionError(f"{name} is invalid")
    try:
        int(value, 16)
    except ValueError as exc:
        raise LiveAuthorityAdmissionError(f"{name} is invalid") from exc
    if value.lower() != value:
        raise LiveAuthorityAdmissionError(f"{name} is invalid")
    return value


def _text(value: object, *, name: str, limit: int = 512) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > limit or "\x00" in value:
        raise LiveAuthorityAdmissionError(f"{name} is invalid")
    return value


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
    epoch_state_version: int
    authority_ceiling: str
    root_grant_id: str
    root_grant_digest: str
    authenticated_grant_digests: tuple[str, ...]
    leaf_key_id: str
    leaf_algorithm: str
    replay_digest: str
    admitted_at: str

    def validate(self) -> "LiveAdmittedAuthority":
        for name in (
            "repository", "base_sha", "head_sha", "mission_id", "grant_id",
            "provenance_id", "authority_ceiling", "root_grant_id", "leaf_key_id",
            "leaf_algorithm", "admitted_at",
        ):
            _text(getattr(self, name), name=name)
        if not isinstance(self.pr_number, int) or isinstance(self.pr_number, bool) or self.pr_number <= 0:
            raise LiveAuthorityAdmissionError("pr_number is invalid")
        if not isinstance(self.epoch, int) or isinstance(self.epoch, bool) or self.epoch < 0:
            raise LiveAuthorityAdmissionError("epoch is invalid")
        if (
            not isinstance(self.epoch_state_version, int)
            or isinstance(self.epoch_state_version, bool)
            or self.epoch_state_version < 1
        ):
            raise LiveAuthorityAdmissionError("epoch_state_version is invalid")
        for name in ("lineage_digest", "root_grant_digest", "replay_digest"):
            _sha256(getattr(self, name), name=name)
        if type(self.authenticated_grant_digests) is not tuple or not self.authenticated_grant_digests:
            raise LiveAuthorityAdmissionError("authenticated_grant_digests are invalid")
        for item in self.authenticated_grant_digests:
            _sha256(item, name="authenticated_grant_digest")
        self._utc(self.admitted_at)
        return self

    @staticmethod
    def _utc(value: str) -> datetime:
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except (AttributeError, ValueError) as exc:
            raise LiveAuthorityAdmissionError("admitted_at is invalid") from exc
        if parsed.tzinfo is None:
            raise LiveAuthorityAdmissionError("admitted_at must be timezone-aware")
        return parsed.astimezone(timezone.utc)

    @property
    def leaf_grant_digest(self) -> str:
        self.validate()
        return self.authenticated_grant_digests[-1]

    def canonical_payload(self) -> bytes:
        self.validate()
        return json.dumps(
            {
                "admitted_at": self.admitted_at,
                "authenticated_grant_digests": list(self.authenticated_grant_digests),
                "authority_ceiling": self.authority_ceiling,
                "base_sha": self.base_sha,
                "epoch": self.epoch,
                "epoch_state_version": self.epoch_state_version,
                "grant_id": self.grant_id,
                "head_sha": self.head_sha,
                "leaf_algorithm": self.leaf_algorithm,
                "leaf_key_id": self.leaf_key_id,
                "lineage_digest": self.lineage_digest,
                "mission_id": self.mission_id,
                "pr_number": self.pr_number,
                "provenance_id": self.provenance_id,
                "replay_digest": self.replay_digest,
                "repository": self.repository,
                "root_grant_digest": self.root_grant_digest,
                "root_grant_id": self.root_grant_id,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")

    def digest(self) -> str:
        return hashlib.sha256(self.canonical_payload()).hexdigest()


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
        if not callable(getattr(epoch_provider, "current", None)):
            raise LiveAuthorityAdmissionError("epoch provider is unavailable")
        if not callable(getattr(root_provider, "resolve", None)):
            raise LiveAuthorityAdmissionError("root provider is unavailable")
        if not callable(getattr(replay_guard, "consume", None)):
            raise LiveAuthorityAdmissionError("replay guard is unavailable")
        self._source = authority_source
        self._context = context
        self._issuer_keys = issuer_keys
        self._verifier = signature_verifier
        self._epoch_provider = epoch_provider
        self._root_provider = root_provider
        self._replay_guard = replay_guard

    @property
    def context(self) -> AuthorityVerificationContext:
        return self._context

    def _context_key(self) -> tuple[str, str, str, str]:
        return (
            self._context.trust_domain,
            self._context.tenant_id,
            self._context.organization_id,
            self._context.mission_id,
        )

    def _snapshot(
        self, key: AuthorityLookupKey
    ) -> tuple[AuthorityLineageRecord, PersistentEpochSnapshot, PersistentRootAnchor]:
        try:
            record = self._source.resolve_exact(key)
            state = self._epoch_provider.current(self._context_key())
            root = self._root_provider.resolve(self._context_key(), state.epoch)
        except Exception as exc:
            raise LiveAuthorityAdmissionError("canonical authority state unavailable") from exc
        record.validate()
        return record, state, root

    def _authenticate_record(
        self,
        record: AuthorityLineageRecord,
        state: PersistentEpochSnapshot,
        root: PersistentRootAnchor,
        *,
        now: datetime,
    ) -> tuple[AuthenticatedAuthorityGrant, ...]:
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
        return tuple(authenticated)

    @staticmethod
    def _same_snapshot(
        before: tuple[AuthorityLineageRecord, PersistentEpochSnapshot, PersistentRootAnchor],
        after: tuple[AuthorityLineageRecord, PersistentEpochSnapshot, PersistentRootAnchor],
    ) -> bool:
        b_record, b_state, b_root = before
        a_record, a_state, a_root = after
        return (
            b_record.lookup_key.binding() == a_record.lookup_key.binding()
            and b_record.lineage_digest == a_record.lineage_digest
            and b_record.provenance_id == a_record.provenance_id
            and tuple(item.digest() for item in b_record.lineage)
            == tuple(item.digest() for item in a_record.lineage)
            and b_state == a_state
            and b_root == a_root
        )

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
        before = self._snapshot(key)
        record, state, root = before
        authenticated = self._authenticate_record(record, state, root, now=now)

        after = self._snapshot(key)
        if not self._same_snapshot(before, after):
            raise LiveAuthorityAdmissionError("authority state changed during authentication")

        leaf = record.lineage[-1]
        replay_material = (
            f"{record.lineage_digest}\x00{leaf.grant_id}\x00{repository}\x00{pr_number}\x00"
            f"{base_sha}\x00{head_sha}\x00{mission_id}\x00{state.epoch}\x00{state.version}\x00{replay_nonce}"
        ).encode("utf-8")
        replay_digest = hashlib.sha256(replay_material).hexdigest()
        current = now.astimezone(timezone.utc)
        try:
            accepted = self._replay_guard.consume(replay_digest, consumed_at=current.isoformat())
        except PersistentAuthorityStateError as exc:
            raise LiveAuthorityAdmissionError("durable replay state unavailable") from exc
        if accepted is not True:
            raise LiveAuthorityAdmissionError("authority admission replay rejected")

        receipt = LiveAdmittedAuthority(
            repository=repository,
            pr_number=pr_number,
            base_sha=base_sha,
            head_sha=head_sha,
            mission_id=mission_id,
            grant_id=leaf.grant_id,
            lineage_digest=record.lineage_digest,
            provenance_id=record.provenance_id,
            epoch=state.epoch,
            epoch_state_version=state.version,
            authority_ceiling=leaf.authority_ceiling,
            root_grant_id=root.root_grant_id,
            root_grant_digest=root.root_grant_digest,
            authenticated_grant_digests=tuple(item.grant_digest for item in authenticated),
            leaf_key_id=authenticated[-1].key_id,
            leaf_algorithm=authenticated[-1].algorithm,
            replay_digest=replay_digest,
            admitted_at=current.isoformat(),
        )
        return receipt.validate()

    def revalidate(self, admitted: LiveAdmittedAuthority, *, now: datetime) -> LiveAdmittedAuthority:
        if type(admitted) is not LiveAdmittedAuthority:
            raise LiveAuthorityAdmissionError("live admission receipt must be exact LiveAdmittedAuthority")
        admitted.validate()
        if now.tzinfo is None:
            raise LiveAuthorityAdmissionError("trusted now must be timezone-aware")
        if admitted.mission_id != self._context.mission_id:
            raise LiveAuthorityAdmissionError("admission receipt mission mismatch")

        key = AuthorityLookupKey(
            admitted.repository,
            admitted.pr_number,
            admitted.base_sha,
            admitted.head_sha,
            admitted.mission_id,
            admitted.grant_id,
        )
        before = self._snapshot(key)
        record, state, root = before
        authenticated = self._authenticate_record(record, state, root, now=now)
        after = self._snapshot(key)
        if not self._same_snapshot(before, after):
            raise LiveAuthorityAdmissionError("authority state changed during revalidation")
        leaf = record.lineage[-1]

        expected = (
            record.lineage_digest,
            record.provenance_id,
            state.epoch,
            state.version,
            leaf.authority_ceiling,
            root.root_grant_id,
            root.root_grant_digest,
            tuple(item.grant_digest for item in authenticated),
            authenticated[-1].key_id,
            authenticated[-1].algorithm,
        )
        actual = (
            admitted.lineage_digest,
            admitted.provenance_id,
            admitted.epoch,
            admitted.epoch_state_version,
            admitted.authority_ceiling,
            admitted.root_grant_id,
            admitted.root_grant_digest,
            admitted.authenticated_grant_digests,
            admitted.leaf_key_id,
            admitted.leaf_algorithm,
        )
        if actual != expected:
            raise LiveAuthorityAdmissionError("live admission receipt is stale or forged")
        return admitted
