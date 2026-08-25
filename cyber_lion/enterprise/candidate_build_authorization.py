"""Fail-closed pre-PR authority admission and bounded candidate-build authorization.

This module has no repository, branch, PR, runtime, merge, deploy, release, grant-issuance,
or sandbox effect ports.  It composes already-existing authority authentication/currentness
primitives with exact R9/PDP evidence and emits one immutable authorization artifact.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
from typing import Iterable, Protocol

from cyber_lion.contracts.candidate_build_authorization import (
    BoundedCandidateBuildAuthorization,
    CandidateBuildAuthorizationContractError,
    ResourceAuthorityLookupKey,
    SCHEMA_VERSION,
    TrustedRepositoryBaseline,
    canonical_json,
)
from cyber_lion.contracts.governed_change_admission import GovernedChangeAdmissionRequest
from cyber_lion.contracts.policy_gate import GateApplied, GateRequested, PDPDecisionReceipt
from cyber_lion.enterprise.authority_grant import AuthorityGrant, AuthorityGrantError, validate_attenuation
from cyber_lion.enterprise.authority_source import canonical_source_lineage_digest
from cyber_lion.enterprise.authority_verification import (
    AuthenticatedAuthorityGrant,
    AuthorityVerificationContext,
    IssuerKeyBinding,
    Verifier,
    authenticate_authority_grant,
)


class CandidateBuildAuthorizationError(RuntimeError):
    pass


_AUTHORITY_CONTAINS = {
    "none": {"none"},
    "read": {"none", "read"},
    "local_write": {"none", "read", "local_write"},
    "external_write": {"none", "read", "local_write", "external_write"},
    "financial": {"none", "read", "local_write", "external_write", "financial"},
    "deploy": {"none", "read", "local_write", "external_write", "deploy"},
    "privileged": {"none", "read", "local_write", "external_write", "financial", "deploy", "privileged"},
}
_ISSUANCE_DOMAIN = b"LION/E004-CANDIDATE-BUILD-AUTHORIZATION-ISSUANCE/1\0"
_LIVE_RESOURCE_ADMISSION_DOMAIN = b"LION/E004-LIVE-RESOURCE-AUTHORITY-ADMISSION/1\0"
_EFFECT_METHODS = frozenset({
    "execute", "write", "push", "merge", "deploy", "release", "create_branch",
    "create_pr", "run_test", "build_candidate", "issue_grant", "revoke_grant",
})


def _utc(value: str, *, name: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, ValueError) as exc:
        raise CandidateBuildAuthorizationError(f"{name} invalid") from exc
    if parsed.tzinfo is None:
        raise CandidateBuildAuthorizationError(f"{name} must be timezone-aware")
    return parsed.astimezone(timezone.utc)


def _digest_payload(domain: bytes, payload: object) -> str:
    return sha256(domain + canonical_json(payload)).hexdigest()


def _contains(parent: str, child: str) -> bool:
    try:
        return child in _AUTHORITY_CONTAINS[parent]
    except KeyError as exc:
        raise CandidateBuildAuthorizationError("unknown authority class") from exc


@dataclass(frozen=True)
class ResourceAuthorityLineageRecord:
    """Trusted-control-plane lineage bound to one exact pre-PR resource subject."""

    lookup_key: ResourceAuthorityLookupKey
    lineage: tuple[AuthorityGrant, ...]
    lineage_digest: str
    provenance_id: str
    source_kind: str = "trusted-control-plane"

    def validate(self) -> "ResourceAuthorityLineageRecord":
        if type(self.lookup_key) is not ResourceAuthorityLookupKey:
            raise CandidateBuildAuthorizationError("resource lookup key type invalid")
        self.lookup_key.validate()
        if type(self.lineage) is not tuple or not self.lineage:
            raise CandidateBuildAuthorizationError("resource authority lineage must be non-empty tuple")
        if self.source_kind != "trusted-control-plane":
            raise CandidateBuildAuthorizationError("resource authority must come from trusted-control-plane")
        if not isinstance(self.provenance_id, str) or not self.provenance_id.strip():
            raise CandidateBuildAuthorizationError("authority provenance invalid")
        previous: AuthorityGrant | None = None
        for grant in self.lineage:
            if type(grant) is not AuthorityGrant:
                raise CandidateBuildAuthorizationError("lineage entry type invalid")
            grant.validate()
            if grant.mission_id != self.lookup_key.mission_id:
                raise CandidateBuildAuthorizationError("lineage mission mismatch")
            if previous is None:
                if grant.parent_grant_id is not None:
                    raise CandidateBuildAuthorizationError("lineage root must not declare parent")
            else:
                try:
                    validate_attenuation(previous, grant)
                except AuthorityGrantError as exc:
                    raise CandidateBuildAuthorizationError("authority lineage attenuation failed") from exc
            previous = grant
        leaf = self.lineage[-1]
        if leaf.grant_id != self.lookup_key.grant_id:
            raise CandidateBuildAuthorizationError("lineage leaf grant mismatch")
        if self.lookup_key.action not in leaf.actions:
            raise CandidateBuildAuthorizationError("leaf does not authorize BUILD_CANDIDATE")
        if not set(self.lookup_key.resource_scope).issubset(set(leaf.resource_scope)):
            raise CandidateBuildAuthorizationError("leaf resource scope does not contain exact requested scope")
        expected = canonical_source_lineage_digest(self.lineage)
        if self.lineage_digest != expected:
            raise CandidateBuildAuthorizationError("resource authority lineage digest mismatch")
        return self


class ResourceAuthoritySource(ABC):
    """Same authority plane, pre-PR subject: exact read only, no mutation surface."""

    @abstractmethod
    def _lookup_resource_exact(
        self, key: ResourceAuthorityLookupKey
    ) -> tuple[ResourceAuthorityLineageRecord, ...]:
        raise NotImplementedError

    def resolve_resource_exact(self, key: ResourceAuthorityLookupKey) -> ResourceAuthorityLineageRecord:
        if type(key) is not ResourceAuthorityLookupKey:
            raise CandidateBuildAuthorizationError("exact ResourceAuthorityLookupKey required")
        key.validate()
        records = self._lookup_resource_exact(key)
        if type(records) is not tuple:
            raise CandidateBuildAuthorizationError("resource authority candidates must be immutable tuple")
        if len(records) == 0:
            raise CandidateBuildAuthorizationError("resource authority lineage not found")
        if len(records) > 1:
            raise CandidateBuildAuthorizationError("resource authority lineage lookup ambiguous")
        record = records[0]
        if type(record) is not ResourceAuthorityLineageRecord:
            raise CandidateBuildAuthorizationError("resource authority record type invalid")
        record.validate()
        if record.lookup_key.binding() != key.binding():
            raise CandidateBuildAuthorizationError("resource authority record key substitution denied")
        return record


class ResourceAuthorityTransport(Protocol):
    def lookup_resource_exact(
        self, *, repository: str, mission_id: str, grant_id: str,
        action: str, resource_scope: tuple[str, ...]
    ) -> tuple[ResourceAuthorityLineageRecord, ...]: ...


class TrustedControlPlaneResourceAuthoritySource(ResourceAuthoritySource):
    """Capability-reduced adapter over one trusted pre-PR exact-read transport."""

    __slots__ = ("_transport",)

    def __init__(self, transport: ResourceAuthorityTransport) -> None:
        if not callable(getattr(transport, "lookup_resource_exact", None)):
            raise CandidateBuildAuthorizationError("resource authority transport unavailable")
        self._transport = transport

    def _lookup_resource_exact(
        self, key: ResourceAuthorityLookupKey
    ) -> tuple[ResourceAuthorityLineageRecord, ...]:
        key.validate()
        try:
            records = self._transport.lookup_resource_exact(
                repository=key.repository,
                mission_id=key.mission_id,
                grant_id=key.grant_id,
                action=key.action,
                resource_scope=key.resource_scope,
            )
        except Exception as exc:
            raise CandidateBuildAuthorizationError("resource authority source unavailable") from exc
        if type(records) is not tuple:
            raise CandidateBuildAuthorizationError("resource authority transport result must be immutable tuple")
        return records


@dataclass(frozen=True)
class LiveAdmittedResourceAuthority:
    repository: str
    mission_id: str
    grant_id: str
    action: str
    resource_scope: tuple[str, ...]
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

    def validate(self) -> "LiveAdmittedResourceAuthority":
        ResourceAuthorityLookupKey(
            self.repository, self.mission_id, self.grant_id, self.action, self.resource_scope
        ).validate()
        for value in (self.lineage_digest, self.root_grant_digest, self.replay_digest):
            if not isinstance(value, str) or len(value) != 64:
                raise CandidateBuildAuthorizationError("live resource authority digest invalid")
        if not isinstance(self.epoch, int) or isinstance(self.epoch, bool) or self.epoch < 0:
            raise CandidateBuildAuthorizationError("live resource authority epoch invalid")
        if not isinstance(self.epoch_state_version, int) or isinstance(self.epoch_state_version, bool) or self.epoch_state_version < 1:
            raise CandidateBuildAuthorizationError("live resource authority state version invalid")
        if self.authority_ceiling not in _AUTHORITY_CONTAINS:
            raise CandidateBuildAuthorizationError("live resource authority ceiling invalid")
        if not isinstance(self.provenance_id, str) or not self.provenance_id.strip():
            raise CandidateBuildAuthorizationError("live resource authority provenance invalid")
        if not isinstance(self.root_grant_id, str) or not self.root_grant_id.strip():
            raise CandidateBuildAuthorizationError("live resource authority root invalid")
        if type(self.authenticated_grant_digests) is not tuple or not self.authenticated_grant_digests:
            raise CandidateBuildAuthorizationError("authenticated grant digests missing")
        if any(not isinstance(x, str) or len(x) != 64 for x in self.authenticated_grant_digests):
            raise CandidateBuildAuthorizationError("authenticated grant digest invalid")
        if not self.leaf_key_id or not self.leaf_algorithm:
            raise CandidateBuildAuthorizationError("leaf key identity missing")
        _utc(self.admitted_at, name="admitted_at")
        return self

    @property
    def leaf_grant_digest(self) -> str:
        self.validate()
        return self.authenticated_grant_digests[-1]

    def digest(self) -> str:
        self.validate()
        value = asdict(self)
        value["resource_scope"] = list(self.resource_scope)
        value["authenticated_grant_digests"] = list(self.authenticated_grant_digests)
        return _digest_payload(b"LION/E004-LIVE-ADMITTED-RESOURCE-AUTHORITY/1\0", value)


class LiveResourceAuthorityAdmission:
    """Authenticate and admit one pre-PR resource lineage against current persistent state."""

    def __init__(
        self, *, authority_source: ResourceAuthoritySource,
        context: AuthorityVerificationContext, issuer_keys: tuple[IssuerKeyBinding, ...],
        signature_verifier: Verifier, epoch_provider: object, root_provider: object,
        replay_guard: object,
    ) -> None:
        if not isinstance(authority_source, ResourceAuthoritySource):
            raise CandidateBuildAuthorizationError("resource authority source invalid")
        if type(context) is not AuthorityVerificationContext:
            raise CandidateBuildAuthorizationError("authority context invalid")
        context.validate()
        if type(issuer_keys) is not tuple or not issuer_keys:
            raise CandidateBuildAuthorizationError("issuer keys missing")
        for binding in issuer_keys:
            if not isinstance(binding, IssuerKeyBinding):
                raise CandidateBuildAuthorizationError("issuer key binding invalid")
            binding.validate()
        if not callable(signature_verifier):
            raise CandidateBuildAuthorizationError("signature verifier unavailable")
        if not callable(getattr(epoch_provider, "current", None)):
            raise CandidateBuildAuthorizationError("epoch provider unavailable")
        if not callable(getattr(root_provider, "resolve", None)):
            raise CandidateBuildAuthorizationError("root provider unavailable")
        if not callable(getattr(replay_guard, "consume", None)):
            raise CandidateBuildAuthorizationError("resource authority replay guard unavailable")
        self._source = authority_source
        self._context = context
        self._issuer_keys = issuer_keys
        self._verifier = signature_verifier
        self._epoch_provider = epoch_provider
        self._root_provider = root_provider
        self._replay_guard = replay_guard

    def _context_key(self) -> tuple[str, str, str, str]:
        return (
            self._context.trust_domain, self._context.tenant_id,
            self._context.organization_id, self._context.mission_id,
        )

    def _snapshot(self, key: ResourceAuthorityLookupKey):
        try:
            record = self._source.resolve_resource_exact(key)
            state = self._epoch_provider.current(self._context_key())
            root = self._root_provider.resolve(self._context_key(), state.epoch)
        except Exception as exc:
            raise CandidateBuildAuthorizationError("canonical pre-PR authority state unavailable") from exc
        record.validate()
        return record, state, root

    def _authenticate(self, record: ResourceAuthorityLineageRecord, state: object, root: object, *, now: datetime) -> tuple[AuthenticatedAuthorityGrant, ...]:
        lineage = record.lineage
        if root.root_grant_id != lineage[0].grant_id or root.root_grant_digest != lineage[0].digest():
            raise CandidateBuildAuthorizationError("resource authority root anchor mismatch")
        authenticated: list[AuthenticatedAuthorityGrant] = []
        previous: AuthorityGrant | None = None
        current = now.astimezone(timezone.utc)
        for grant in lineage:
            grant.validate()
            if grant.epoch != state.epoch:
                raise CandidateBuildAuthorizationError("resource authority grant epoch stale or future")
            if grant.grant_id in state.revoked_grant_ids:
                raise CandidateBuildAuthorizationError("resource authority grant revoked")
            if current < _utc(grant.issued_at, name="grant issued_at"):
                raise CandidateBuildAuthorizationError("resource authority grant not yet current")
            if current >= _utc(grant.expires_at, name="grant expires_at"):
                raise CandidateBuildAuthorizationError("resource authority grant expired")
            if previous is not None:
                try:
                    validate_attenuation(previous, grant)
                except AuthorityGrantError as exc:
                    raise CandidateBuildAuthorizationError("resource authority attenuation failed") from exc
            try:
                authenticated.append(authenticate_authority_grant(
                    grant, self._issuer_keys, self._verifier, context=self._context
                ))
            except Exception as exc:
                raise CandidateBuildAuthorizationError("resource authority signature authentication failed") from exc
            previous = grant
        return tuple(authenticated)

    @staticmethod
    def _same_snapshot(before: tuple[object, object, object], after: tuple[object, object, object]) -> bool:
        br, bs, broot = before
        ar, ass, aroot = after
        return (
            br.lookup_key.binding() == ar.lookup_key.binding()
            and br.lineage_digest == ar.lineage_digest
            and br.provenance_id == ar.provenance_id
            and tuple(x.digest() for x in br.lineage) == tuple(x.digest() for x in ar.lineage)
            and bs == ass and broot == aroot
        )

    def admit(self, *, key: ResourceAuthorityLookupKey, now: datetime, replay_nonce: str) -> LiveAdmittedResourceAuthority:
        if type(key) is not ResourceAuthorityLookupKey:
            raise CandidateBuildAuthorizationError("exact resource authority key required")
        key.validate()
        if key.mission_id != self._context.mission_id:
            raise CandidateBuildAuthorizationError("resource authority mission/context mismatch")
        if not isinstance(now, datetime) or now.tzinfo is None:
            raise CandidateBuildAuthorizationError("trusted now must be timezone-aware")
        if not isinstance(replay_nonce, str) or not replay_nonce.strip():
            raise CandidateBuildAuthorizationError("resource authority replay nonce required")
        before = self._snapshot(key)
        record, state, root = before
        authenticated = self._authenticate(record, state, root, now=now)
        after = self._snapshot(key)
        if not self._same_snapshot(before, after):
            raise CandidateBuildAuthorizationError("resource authority changed during authentication")
        leaf = record.lineage[-1]
        replay_payload = {
            "key_digest": key.digest(), "lineage_digest": record.lineage_digest,
            "leaf_grant_digest": leaf.digest(), "epoch": state.epoch,
            "state_version": state.version, "nonce": replay_nonce,
        }
        replay_digest = _digest_payload(_LIVE_RESOURCE_ADMISSION_DOMAIN, replay_payload)
        accepted = self._replay_guard.consume(replay_digest, consumed_at=now.astimezone(timezone.utc).isoformat())
        if accepted is not True:
            raise CandidateBuildAuthorizationError("resource authority admission replay rejected")
        receipt = LiveAdmittedResourceAuthority(
            repository=key.repository, mission_id=key.mission_id, grant_id=leaf.grant_id,
            action=key.action, resource_scope=key.resource_scope,
            lineage_digest=record.lineage_digest, provenance_id=record.provenance_id,
            epoch=state.epoch, epoch_state_version=state.version,
            authority_ceiling=leaf.authority_ceiling,
            root_grant_id=root.root_grant_id, root_grant_digest=root.root_grant_digest,
            authenticated_grant_digests=tuple(item.grant_digest for item in authenticated),
            leaf_key_id=authenticated[-1].key_id, leaf_algorithm=authenticated[-1].algorithm,
            replay_digest=replay_digest, admitted_at=now.astimezone(timezone.utc).isoformat(),
        )
        return receipt.validate()

    def revalidate(self, admitted: LiveAdmittedResourceAuthority, *, now: datetime) -> LiveAdmittedResourceAuthority:
        if type(admitted) is not LiveAdmittedResourceAuthority:
            raise CandidateBuildAuthorizationError("exact live resource authority receipt required")
        admitted.validate()
        if not isinstance(now, datetime) or now.tzinfo is None:
            raise CandidateBuildAuthorizationError("trusted now must be timezone-aware")
        key = ResourceAuthorityLookupKey(
            admitted.repository, admitted.mission_id, admitted.grant_id,
            admitted.action, admitted.resource_scope,
        ).validate()
        before = self._snapshot(key)
        record, state, root = before
        authenticated = self._authenticate(record, state, root, now=now)
        after = self._snapshot(key)
        if not self._same_snapshot(before, after):
            raise CandidateBuildAuthorizationError("resource authority changed during revalidation")
        leaf = record.lineage[-1]
        expected = (
            record.lineage_digest, record.provenance_id, state.epoch, state.version,
            leaf.authority_ceiling, root.root_grant_id, root.root_grant_digest,
            tuple(x.grant_digest for x in authenticated), authenticated[-1].key_id,
            authenticated[-1].algorithm,
        )
        actual = (
            admitted.lineage_digest, admitted.provenance_id, admitted.epoch,
            admitted.epoch_state_version, admitted.authority_ceiling,
            admitted.root_grant_id, admitted.root_grant_digest,
            admitted.authenticated_grant_digests, admitted.leaf_key_id,
            admitted.leaf_algorithm,
        )
        if actual != expected:
            raise CandidateBuildAuthorizationError("live resource authority receipt stale or forged")
        return admitted


class TrustedRepositoryBaselineSource(Protocol):
    def current(self, repository: str) -> TrustedRepositoryBaseline: ...


class AuthorizationIssuanceReplayGuard(Protocol):
    def consume(self, replay_digest: str, *, consumed_at: str) -> bool: ...


class PersistentAuthorizationIssuanceReplayGuard:
    """Adapter over the existing persistent replay store using a separate issuance domain."""

    DOMAIN = "candidate-build-authorization-issuance"

    def __init__(self, store: object) -> None:
        if not callable(getattr(store, "consume_replay", None)):
            raise CandidateBuildAuthorizationError("persistent replay store unavailable")
        self._store = store

    def consume(self, replay_digest: str, *, consumed_at: str) -> bool:
        return self._store.consume_replay(self.DOMAIN, replay_digest, consumed_at)


class CandidateBuildAuthorizationEngine:
    """Issue one non-effectful candidate-build authorization; never consume or execute it."""

    def __init__(
        self, *, live_authority: LiveResourceAuthorityAdmission,
        baseline_source: TrustedRepositoryBaselineSource,
        issuance_replay_guard: AuthorizationIssuanceReplayGuard,
    ) -> None:
        if type(live_authority) is not LiveResourceAuthorityAdmission:
            raise CandidateBuildAuthorizationError("live resource authority admission required")
        if not callable(getattr(baseline_source, "current", None)):
            raise CandidateBuildAuthorizationError("trusted repository baseline source unavailable")
        if not callable(getattr(issuance_replay_guard, "consume", None)):
            raise CandidateBuildAuthorizationError("authorization issuance replay guard unavailable")
        self._live = live_authority
        self._baseline_source = baseline_source
        self._replay = issuance_replay_guard

    @staticmethod
    def _require_exact_sealed(value: object, expected_type: type, digest_attr: str, compute_name: str = "compute_digest") -> None:
        if type(value) is not expected_type:
            raise CandidateBuildAuthorizationError(f"exact {expected_type.__name__} required")
        value.validate()
        digest = getattr(value, digest_attr)
        if not digest:
            raise CandidateBuildAuthorizationError(f"unsealed {expected_type.__name__} denied")
        compute = getattr(value, compute_name)
        if digest != compute():
            raise CandidateBuildAuthorizationError(f"{expected_type.__name__} digest mismatch")

    @staticmethod
    def _bind_pdp(
        admission: GovernedChangeAdmissionRequest, request: GateRequested,
        applied: GateApplied, receipt: PDPDecisionReceipt,
    ) -> None:
        CandidateBuildAuthorizationEngine._require_exact_sealed(
            admission, GovernedChangeAdmissionRequest, "admission_request_digest"
        )
        CandidateBuildAuthorizationEngine._require_exact_sealed(request, GateRequested, "request_digest")
        CandidateBuildAuthorizationEngine._require_exact_sealed(applied, GateApplied, "decision_digest")
        if type(receipt) is not PDPDecisionReceipt:
            raise CandidateBuildAuthorizationError("exact PDPDecisionReceipt required")
        receipt.validate()
        if admission.requested_action != "BUILD_CANDIDATE" or admission.requested_authority != "local_write":
            raise CandidateBuildAuthorizationError("admission is not exact BUILD_CANDIDATE/local_write")
        if admission.authority_effect != "NONE" or admission.execution_effect != "NONE":
            raise CandidateBuildAuthorizationError("effectful admission request denied")
        if "F005" in admission.target_component.upper() or any("F005" in x.upper() for x in (*admission.candidate_scope, *admission.requested_resource_scope)):
            raise CandidateBuildAuthorizationError("F005 remains quarantined")
        expected = (
            admission.request_id,
            request.request_digest,
            request.request_id,
            request.request_id,
            request.proposal_id,
            request.policy_binding,
            request.authority_lineage_digest,
            request.enterprise_graph_digest,
            request.status_digest,
            request.observability_state,
            request.lane,
            request.requested_authority,
        )
        actual = (
            request.proposal_id,
            receipt.request_digest,
            applied.request_id,
            receipt.request_id,
            applied.proposal_id,
            applied.policy_binding,
            applied.authority_lineage_digest,
            applied.enterprise_graph_digest,
            applied.status_digest,
            applied.observability_state,
            applied.lane,
            applied.effective_authority,
        )
        if actual != expected:
            raise CandidateBuildAuthorizationError("R9 GateRequested/PDP binding mismatch")
        if applied.gate_event_id != receipt.gate_event_id or applied.decision_digest != receipt.decision_digest:
            raise CandidateBuildAuthorizationError("GateApplied/PDP receipt binding mismatch")
        if applied.decision != "ALLOW":
            raise CandidateBuildAuthorizationError("PDP DENY cannot authorize candidate build")
        if request.requested_authority != "local_write" or applied.effective_authority != "local_write":
            raise CandidateBuildAuthorizationError("candidate build PDP authority must remain local_write")
        if request.observability_state != "HEALTHY":
            raise CandidateBuildAuthorizationError("local_write requires HEALTHY observability")

    def issue(
        self, *, admission_request: GovernedChangeAdmissionRequest,
        gate_request: GateRequested, gate_applied: GateApplied,
        pdp_receipt: PDPDecisionReceipt, grant_id: str,
        trusted_now: datetime,
    ) -> BoundedCandidateBuildAuthorization:
        if not isinstance(trusted_now, datetime) or trusted_now.tzinfo is None:
            raise CandidateBuildAuthorizationError("trusted_now must be timezone-aware")
        self._bind_pdp(admission_request, gate_request, gate_applied, pdp_receipt)
        if not isinstance(grant_id, str) or not grant_id.strip():
            raise CandidateBuildAuthorizationError("grant_id required")

        key = ResourceAuthorityLookupKey(
            repository=admission_request.repository,
            mission_id=self._live._context.mission_id,
            grant_id=grant_id,
            action="BUILD_CANDIDATE",
            resource_scope=tuple(admission_request.requested_resource_scope),
        ).validate()
        admitted = self._live.admit(
            key=key, now=trusted_now,
            replay_nonce=f"candidate-build:{admission_request.admission_request_digest}:{gate_applied.decision_digest}",
        )
        admitted = self._live.revalidate(admitted, now=trusted_now)
        record = self._live._source.resolve_resource_exact(key)
        leaf = record.lineage[-1]
        leaf.validate()

        if gate_request.authority_lineage_digest != admitted.lineage_digest:
            raise CandidateBuildAuthorizationError("PDP authority lineage does not match live resource authority")
        if leaf.digest() != admitted.leaf_grant_digest:
            raise CandidateBuildAuthorizationError("live authority leaf digest mismatch")
        if leaf.mission_id != admitted.mission_id or leaf.grant_id != admitted.grant_id:
            raise CandidateBuildAuthorizationError("live authority leaf identity mismatch")
        if "BUILD_CANDIDATE" not in leaf.actions:
            raise CandidateBuildAuthorizationError("authority leaf lacks BUILD_CANDIDATE")
        if not set(admission_request.requested_resource_scope).issubset(set(leaf.resource_scope)):
            raise CandidateBuildAuthorizationError("authorization resource scope exceeds grant")
        if not _contains(leaf.authority_ceiling, "local_write"):
            raise CandidateBuildAuthorizationError("authority leaf ceiling cannot contain local_write")
        if not gate_request.policy_binding.endswith(leaf.policy_digest):
            raise CandidateBuildAuthorizationError("PDP policy binding does not match authority grant policy")

        baseline = self._baseline_source.current(admission_request.repository)
        if type(baseline) is not TrustedRepositoryBaseline:
            raise CandidateBuildAuthorizationError("trusted repository baseline type invalid")
        baseline.validate()
        if baseline.repository != admission_request.repository:
            raise CandidateBuildAuthorizationError("trusted baseline repository substitution denied")

        issuance_payload = {
            "admission_request_digest": admission_request.admission_request_digest,
            "gate_request_digest": gate_request.request_digest,
            "gate_decision_digest": gate_applied.decision_digest,
            "pdp_replay_key": pdp_receipt.replay_key,
            "live_admission_digest": admitted.digest(),
            "leaf_grant_digest": leaf.digest(),
            "authority_epoch": admitted.epoch,
            "authority_state_version": admitted.epoch_state_version,
            "repository": admission_request.repository,
            "baseline_master_sha": baseline.master_sha,
            "baseline_master_tree_sha": baseline.master_tree_sha,
            "action": "BUILD_CANDIDATE",
            "resource_scope": list(admission_request.requested_resource_scope),
        }
        issuance_digest = _digest_payload(_ISSUANCE_DOMAIN, issuance_payload)
        consumed_at = trusted_now.astimezone(timezone.utc).isoformat()
        if self._replay.consume(issuance_digest, consumed_at=consumed_at) is not True:
            raise CandidateBuildAuthorizationError("candidate build authorization issuance replay denied")

        authorization_id = f"cba:{issuance_digest}"
        valid_from = consumed_at
        expires_at = leaf.expires_at
        if _utc(valid_from, name="valid_from") >= _utc(expires_at, name="expires_at"):
            raise CandidateBuildAuthorizationError("authorization validity window empty")

        authorization = BoundedCandidateBuildAuthorization(
            schema_version=SCHEMA_VERSION,
            authorization_id=authorization_id,
            admission_request_id=admission_request.request_id,
            admission_request_digest=admission_request.admission_request_digest,
            gate_request_id=gate_request.request_id,
            gate_request_digest=gate_request.request_digest,
            gate_event_id=gate_applied.gate_event_id,
            gate_decision_digest=gate_applied.decision_digest,
            pdp_receipt_id=pdp_receipt.receipt_id,
            pdp_request_id=pdp_receipt.request_id,
            pdp_request_digest=pdp_receipt.request_digest,
            pdp_decision_digest=pdp_receipt.decision_digest,
            pdp_replay_key=pdp_receipt.replay_key,
            policy_binding=gate_request.policy_binding,
            grant_id=admitted.grant_id,
            leaf_grant_digest=admitted.leaf_grant_digest,
            authority_lineage_digest=admitted.lineage_digest,
            authority_provenance_id=admitted.provenance_id,
            authority_epoch=admitted.epoch,
            authority_state_version=admitted.epoch_state_version,
            root_grant_id=admitted.root_grant_id,
            root_grant_digest=admitted.root_grant_digest,
            live_admission_digest=admitted.digest(),
            authority_admitted_at=admitted.admitted_at,
            repository=admission_request.repository,
            baseline_master_sha=baseline.master_sha,
            baseline_master_tree_sha=baseline.master_tree_sha,
            baseline_observation_digest=baseline.digest(),
            candidate_scope=tuple(admission_request.candidate_scope),
            resource_scope=tuple(admission_request.requested_resource_scope),
            action="BUILD_CANDIDATE",
            requested_authority="local_write",
            effective_authority_ceiling="local_write",
            valid_from=valid_from,
            expires_at=expires_at,
            issuance_replay_digest=issuance_digest,
        ).sealed()
        if authorization.authorization_id != f"cba:{authorization.issuance_replay_digest}":
            raise CandidateBuildAuthorizationError("authorization identity/source substitution denied")
        return authorization

    @classmethod
    def assert_no_effect_surface(cls) -> None:
        for name in _EFFECT_METHODS:
            if hasattr(cls, name):
                raise CandidateBuildAuthorizationError(f"effect surface present: {name}")
