"""Post-execution bridge from immutable runtime evidence to canonical authority."""
from __future__ import annotations

from dataclasses import dataclass
from threading import Lock
from typing import Protocol

from cyber_lion.contracts.runtime_authority_binding import (
    AuthorityAttestationBinding,
    AuthorityBoundRuntimeEvidence,
    RuntimeAuthorityBindingError,
    RuntimeEvidenceReference,
)
from .authority_grant import AuthorityGrant
from .authority_source import AuthorityLookupKey, AuthoritySource, AuthoritySourceError
from .authority_verification import AuthenticatedAuthorityGrant


class RuntimeAuthorityBridgeError(RuntimeAuthorityBindingError):
    """Raised when runtime evidence cannot be bound to canonical authority safely."""


class AuthorityGrantAuthenticator(Protocol):
    def authenticate(self, grant: AuthorityGrant) -> AuthenticatedAuthorityGrant:
        """Authenticate a canonical grant using trust material external to the runtime."""
        ...


@dataclass(frozen=True)
class RuntimeAuthorityReplayKey:
    runtime_evidence_digest: str
    authority_lineage_digest: str
    authenticated_grant_digest: str
    binding_nonce: str


class RuntimeAuthorityReplayGuard(Protocol):
    def consume(self, key: RuntimeAuthorityReplayKey) -> bool: ...


class InMemoryRuntimeAuthorityReplayGuard:
    """Process-local reference guard for bounded experiments; not durable production state."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._seen: set[RuntimeAuthorityReplayKey] = set()

    def consume(self, key: RuntimeAuthorityReplayKey) -> bool:
        with self._lock:
            if key in self._seen:
                return False
            self._seen.add(key)
            return True


class RuntimeAuthorityBridge:
    """Resolve authority from an external AuthoritySource and bind it to immutable runtime evidence."""

    def __init__(
        self,
        *,
        authority_source: AuthoritySource,
        authenticator: AuthorityGrantAuthenticator,
        replay_guard: RuntimeAuthorityReplayGuard,
        repository: str,
        pr_number: int,
        base_sha: str,
        head_sha: str,
        mission_id: str,
    ) -> None:
        if not isinstance(authority_source, AuthoritySource):
            raise RuntimeAuthorityBridgeError("authority_source must be AuthoritySource")
        if not callable(getattr(authenticator, "authenticate", None)):
            raise RuntimeAuthorityBridgeError("authenticator is invalid")
        if not callable(getattr(replay_guard, "consume", None)):
            raise RuntimeAuthorityBridgeError("replay_guard is invalid")
        self._authority_source = authority_source
        self._authenticator = authenticator
        self._replay_guard = replay_guard
        self._repository = repository
        self._pr_number = pr_number
        self._base_sha = base_sha
        self._head_sha = head_sha
        self._mission_id = mission_id
        AuthorityLookupKey(
            repository=repository,
            pr_number=pr_number,
            base_sha=base_sha,
            head_sha=head_sha,
            mission_id=mission_id,
            grant_id="validation-placeholder",
        ).validate()

    def bind(
        self,
        runtime: RuntimeEvidenceReference,
        *,
        grant_id: str,
        binding_nonce: str,
    ) -> AuthorityBoundRuntimeEvidence:
        if not isinstance(runtime, RuntimeEvidenceReference):
            raise RuntimeAuthorityBridgeError("runtime evidence reference is required")
        runtime.validate()
        if (
            runtime.repository != self._repository
            or runtime.base_sha != self._base_sha
            or runtime.head_sha != self._head_sha
            or runtime.mission_id != self._mission_id
        ):
            raise RuntimeAuthorityBridgeError("runtime evidence does not match bridge context")
        if not isinstance(grant_id, str) or not grant_id.strip():
            raise RuntimeAuthorityBridgeError("grant_id is required")
        if not isinstance(binding_nonce, str) or not binding_nonce.strip():
            raise RuntimeAuthorityBridgeError("binding_nonce is required")

        key = AuthorityLookupKey(
            repository=self._repository,
            pr_number=self._pr_number,
            base_sha=self._base_sha,
            head_sha=self._head_sha,
            mission_id=self._mission_id,
            grant_id=grant_id,
        )
        try:
            record = self._authority_source.resolve_exact(key)
        except AuthoritySourceError as exc:
            raise RuntimeAuthorityBridgeError("canonical authority unavailable") from exc
        record.validate()
        leaf = record.lineage[-1]
        if type(leaf) is not AuthorityGrant:
            raise RuntimeAuthorityBridgeError("authority leaf has invalid type")

        try:
            authenticated = self._authenticator.authenticate(leaf)
        except Exception as exc:
            raise RuntimeAuthorityBridgeError("authority authentication failed closed") from exc
        if not isinstance(authenticated, AuthenticatedAuthorityGrant):
            raise RuntimeAuthorityBridgeError("authority authentication result is invalid")
        if (
            authenticated.grant_id != leaf.grant_id
            or authenticated.mission_id != self._mission_id
            or authenticated.grant_digest != leaf.digest()
        ):
            raise RuntimeAuthorityBridgeError("authenticated grant binding mismatch")

        binding = AuthorityAttestationBinding(
            schema_version="1.0.0",
            binding_id=f"runtime-authority:{runtime.runtime_evidence_digest}:{record.lineage_digest}",
            binding_nonce=binding_nonce,
            mission_id=self._mission_id,
            repository=self._repository,
            pr_number=self._pr_number,
            base_sha=self._base_sha,
            head_sha=self._head_sha,
            runtime_evidence_digest=runtime.runtime_evidence_digest,
            runtime_instance_id=runtime.runtime_instance_id,
            run_id=runtime.run_id,
            run_attempt=runtime.run_attempt,
            provenance_ref=runtime.provenance_ref,
            artifact_digest=runtime.artifact_digest,
            grant_id=leaf.grant_id,
            authority_lineage_digest=record.lineage_digest,
            authenticated_grant_digest=authenticated.grant_digest,
            authority_epoch=leaf.epoch,
            authority_provenance_id=record.provenance_id,
            authority_key_id=authenticated.key_id,
            authority_algorithm=authenticated.algorithm,
        ).validate()

        replay_key = RuntimeAuthorityReplayKey(
            runtime.runtime_evidence_digest,
            record.lineage_digest,
            authenticated.grant_digest,
            binding_nonce,
        )
        try:
            accepted = self._replay_guard.consume(replay_key)
        except Exception as exc:
            raise RuntimeAuthorityBridgeError("runtime-authority replay guard failed closed") from exc
        if accepted is not True:
            raise RuntimeAuthorityBridgeError("runtime-authority binding replay rejected")

        return AuthorityBoundRuntimeEvidence(
            runtime_evidence_digest=runtime.runtime_evidence_digest,
            runtime_instance_id=runtime.runtime_instance_id,
            provenance_ref=runtime.provenance_ref,
            artifact_digest=runtime.artifact_digest,
            mission_id=self._mission_id,
            repository=self._repository,
            base_sha=self._base_sha,
            head_sha=self._head_sha,
            grant_id=leaf.grant_id,
            authority_lineage_digest=record.lineage_digest,
            authenticated_grant_digest=authenticated.grant_digest,
            authority_epoch=leaf.epoch,
            authority_provenance_id=record.provenance_id,
            authority_ceiling=leaf.authority_ceiling,
            binding_digest=binding.digest(),
        ).validate()


def verify_authority_bound_n2_pair(
    first: AuthorityBoundRuntimeEvidence,
    second: AuthorityBoundRuntimeEvidence,
) -> tuple[AuthorityBoundRuntimeEvidence, AuthorityBoundRuntimeEvidence]:
    """Validate two distinct runtime records under one compatible canonical authority root."""
    if not isinstance(first, AuthorityBoundRuntimeEvidence) or not isinstance(second, AuthorityBoundRuntimeEvidence):
        raise RuntimeAuthorityBridgeError("N2 pair requires authority-bound runtime evidence")
    first.validate()
    second.validate()
    common_first = (
        first.mission_id,
        first.repository,
        first.base_sha,
        first.head_sha,
        first.grant_id,
        first.authority_lineage_digest,
        first.authenticated_grant_digest,
        first.authority_epoch,
        first.authority_provenance_id,
        first.authority_ceiling,
    )
    common_second = (
        second.mission_id,
        second.repository,
        second.base_sha,
        second.head_sha,
        second.grant_id,
        second.authority_lineage_digest,
        second.authenticated_grant_digest,
        second.authority_epoch,
        second.authority_provenance_id,
        second.authority_ceiling,
    )
    if common_first != common_second:
        raise RuntimeAuthorityBridgeError("N2 runtime evidence does not share one authority root")
    if first.runtime_instance_id == second.runtime_instance_id:
        raise RuntimeAuthorityBridgeError("one runtime instance cannot satisfy authority-bound N2")
    if first.runtime_evidence_digest == second.runtime_evidence_digest:
        raise RuntimeAuthorityBridgeError("duplicate runtime evidence cannot satisfy authority-bound N2")
    if first.provenance_ref == second.provenance_ref:
        raise RuntimeAuthorityBridgeError("duplicate provenance cannot satisfy authority-bound N2")
    if first.binding_digest == second.binding_digest:
        raise RuntimeAuthorityBridgeError("duplicate authority binding cannot satisfy N2")
    return (first, second)
