"""Read-only CI runtime for exact non-consuming merge authority admission.

The runtime receives trusted PR state and bootstrap bindings from its caller, composes the
existing trusted-control-plane authority source and process-local epoch/root bootstrap,
and evaluates ``admit_merge_non_consuming``. It never consumes authority, calls GitHub,
loads authority from a PR tree, or embeds credential material.
"""
from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass

from .authority_revocation import (
    AuthorityEpochState,
    AuthorityLineageRootAnchor,
    register_canonical_authority_epoch_state,
    register_canonical_authority_lineage_root_anchor,
)
from .authority_source import AuthorityLookupKey
from .authority_source_adapter import (
    AuthoritySourceTransport,
    TrustedControlPlaneAuthoritySource,
)
from .authority_verification import (
    AuthorityVerificationContext,
    IssuerKeyBinding,
    Verifier,
)
from .merge_admission import (
    MergeIntent,
    NonConsumingMergeAdmissionEvidence,
    TrustedPullRequestState,
    admit_merge_non_consuming,
)

_RUNTIME_VERSION = "1.0.0"
LookupExact = Callable[..., tuple[Mapping[str, object], ...]]


class CILiveAdmissionError(ValueError):
    """Raised when trusted CI runtime inputs cannot be proven canonical."""


def _text(value: object, *, field_name: str, limit: int = 512) -> str:
    if (
        not isinstance(value, str)
        or not value.strip()
        or len(value) > limit
        or "\x00" in value
    ):
        raise CILiveAdmissionError(f"{field_name} is invalid")
    return value


@dataclass(frozen=True)
class CILiveAdmissionBootstrap:
    """Trusted public bindings installed by the CI/platform bootstrap layer."""

    trust_domain: str
    tenant_id: str
    organization_id: str
    mission_id: str
    grant_id: str
    epoch: int
    root_grant_id: str
    root_grant_digest: str

    def validate(self) -> "CILiveAdmissionBootstrap":
        if type(self) is not CILiveAdmissionBootstrap:
            raise CILiveAdmissionError("bootstrap must be exact CILiveAdmissionBootstrap")
        for field_name in (
            "trust_domain",
            "tenant_id",
            "organization_id",
            "mission_id",
            "grant_id",
            "root_grant_id",
            "root_grant_digest",
        ):
            _text(getattr(self, field_name), field_name=field_name)
        if not isinstance(self.epoch, int) or isinstance(self.epoch, bool) or self.epoch < 0:
            raise CILiveAdmissionError("epoch must be a non-negative integer")
        if len(self.root_grant_digest) != 64 or any(
            char not in "0123456789abcdef" for char in self.root_grant_digest
        ):
            raise CILiveAdmissionError("root_grant_digest must be canonical sha256 hex")
        return self

    def verification_context(self) -> AuthorityVerificationContext:
        self.validate()
        return AuthorityVerificationContext(
            trust_domain=self.trust_domain,
            tenant_id=self.tenant_id,
            organization_id=self.organization_id,
            mission_id=self.mission_id,
        ).validate()


class ReadOnlyAuthorityControlPlaneTransport(AuthoritySourceTransport):
    """Concrete capability-reduced transport backed by one injected read callback."""

    __slots__ = ("_lookup",)

    def __init__(self, lookup: LookupExact) -> None:
        if not callable(lookup):
            raise CILiveAdmissionError("lookup must be callable")
        self._lookup = lookup

    def lookup_exact(
        self,
        *,
        repository: str,
        pr_number: int,
        base_sha: str,
        head_sha: str,
        mission_id: str,
        grant_id: str,
    ) -> tuple[Mapping[str, object], ...]:
        """Forward one exact authority lookup without exposing mutation operations."""
        return self._lookup(
            repository=repository,
            pr_number=pr_number,
            base_sha=base_sha,
            head_sha=head_sha,
            mission_id=mission_id,
            grant_id=grant_id,
        )


@dataclass(frozen=True)
class CILiveAdmissionReceipt:
    """Immutable CI outcome; positive evidence exists only when decision is ALLOW."""

    runtime_version: str
    admission_id: str
    decision: str
    rationale: str
    repository: str
    pr_number: int
    base_sha: str
    head_sha: str
    merge_method: str
    mission_id: str
    grant_id: str
    evidence: NonConsumingMergeAdmissionEvidence | None = None

    def validate(self) -> "CILiveAdmissionReceipt":
        if type(self) is not CILiveAdmissionReceipt:
            raise CILiveAdmissionError("receipt must be exact CILiveAdmissionReceipt")
        if self.runtime_version != _RUNTIME_VERSION:
            raise CILiveAdmissionError("runtime_version is unsupported")
        _text(self.admission_id, field_name="admission_id")
        _text(self.rationale, field_name="rationale", limit=1024)
        _text(self.mission_id, field_name="mission_id")
        _text(self.grant_id, field_name="grant_id")
        MergeIntent(
            repository=self.repository,
            pr_number=self.pr_number,
            base_sha=self.base_sha,
            head_sha=self.head_sha,
            merge_method=self.merge_method,
        ).validate()
        if self.decision not in {"ALLOW", "DENY"}:
            raise CILiveAdmissionError("decision must be ALLOW or DENY")
        if self.decision == "ALLOW":
            if type(self.evidence) is not NonConsumingMergeAdmissionEvidence:
                raise CILiveAdmissionError("ALLOW requires exact non-consuming evidence")
            self.evidence.validate()
            expected = (
                self.admission_id,
                self.repository,
                self.pr_number,
                self.base_sha,
                self.head_sha,
                self.merge_method,
                self.mission_id,
                self.grant_id,
            )
            actual = (
                self.evidence.admission_id,
                self.evidence.repository,
                self.evidence.pr_number,
                self.evidence.base_sha,
                self.evidence.head_sha,
                self.evidence.merge_method,
                self.evidence.mission_id,
                self.evidence.grant_id,
            )
            if actual != expected:
                raise CILiveAdmissionError("positive evidence does not bind exact CI receipt")
        elif self.evidence is not None:
            raise CILiveAdmissionError("DENY must not carry positive admission evidence")
        return self


def _deny_receipt(
    *,
    pr_state: TrustedPullRequestState,
    bootstrap: CILiveAdmissionBootstrap,
    admission_id: str,
    rationale: str,
) -> CILiveAdmissionReceipt:
    return CILiveAdmissionReceipt(
        runtime_version=_RUNTIME_VERSION,
        admission_id=admission_id,
        decision="DENY",
        rationale=rationale,
        repository=pr_state.repository,
        pr_number=pr_state.pr_number,
        base_sha=pr_state.base_sha,
        head_sha=pr_state.head_sha,
        merge_method=pr_state.merge_method,
        mission_id=bootstrap.mission_id,
        grant_id=bootstrap.grant_id,
        evidence=None,
    ).validate()


def run_live_admission(
    *,
    pr_state: TrustedPullRequestState,
    bootstrap: CILiveAdmissionBootstrap,
    authority_transport: AuthoritySourceTransport,
    issuer_keys: Iterable[IssuerKeyBinding],
    verifier: Verifier,
    admission_id: str,
) -> CILiveAdmissionReceipt:
    """Evaluate one ephemeral fail-closed CI admission without consuming authority."""
    if type(pr_state) is not TrustedPullRequestState:
        raise CILiveAdmissionError("pr_state must be exact TrustedPullRequestState")
    pr_state.validate()
    if type(bootstrap) is not CILiveAdmissionBootstrap:
        raise CILiveAdmissionError("bootstrap must be exact CILiveAdmissionBootstrap")
    bootstrap.validate()
    _text(admission_id, field_name="admission_id")
    if not isinstance(authority_transport, AuthoritySourceTransport):
        raise CILiveAdmissionError("authority_transport must implement AuthoritySourceTransport")

    try:
        context = bootstrap.verification_context()
        register_canonical_authority_epoch_state(
            AuthorityEpochState(
                trust_domain=bootstrap.trust_domain,
                tenant_id=bootstrap.tenant_id,
                organization_id=bootstrap.organization_id,
                mission_id=bootstrap.mission_id,
                epoch=bootstrap.epoch,
            ).validate()
        )
        register_canonical_authority_lineage_root_anchor(
            context,
            bootstrap.epoch,
            AuthorityLineageRootAnchor(
                root_grant_id=bootstrap.root_grant_id,
                root_grant_digest=bootstrap.root_grant_digest,
            ).validate(),
        )
        lookup_key = AuthorityLookupKey(
            repository=pr_state.repository,
            pr_number=pr_state.pr_number,
            base_sha=pr_state.base_sha,
            head_sha=pr_state.head_sha,
            mission_id=bootstrap.mission_id,
            grant_id=bootstrap.grant_id,
        ).validate()
        result = admit_merge_non_consuming(
            intent=MergeIntent(
                repository=pr_state.repository,
                pr_number=pr_state.pr_number,
                base_sha=pr_state.base_sha,
                head_sha=pr_state.head_sha,
                merge_method=pr_state.merge_method,
            ).validate(),
            trusted_state=pr_state,
            authority_source=TrustedControlPlaneAuthoritySource(authority_transport),
            lookup_key=lookup_key,
            issuer_keys=issuer_keys,
            verifier=verifier,
            context=context,
            admission_id=admission_id,
        )
        return CILiveAdmissionReceipt(
            runtime_version=_RUNTIME_VERSION,
            admission_id=result.admission_id,
            decision=result.decision,
            rationale=result.rationale,
            repository=result.repository,
            pr_number=result.pr_number,
            base_sha=result.base_sha,
            head_sha=result.head_sha,
            merge_method=result.merge_method,
            mission_id=bootstrap.mission_id,
            grant_id=bootstrap.grant_id,
            evidence=result.evidence,
        ).validate()
    except Exception as exc:
        return _deny_receipt(
            pr_state=pr_state,
            bootstrap=bootstrap,
            admission_id=admission_id,
            rationale=str(exc) or "CI live admission failed closed",
        )


def admission_exit_code(receipt: CILiveAdmissionReceipt) -> int:
    """Return a deterministic process exit code: zero only for exact ALLOW."""
    if type(receipt) is not CILiveAdmissionReceipt:
        raise CILiveAdmissionError("receipt must be exact CILiveAdmissionReceipt")
    receipt.validate()
    return 0 if receipt.decision == "ALLOW" else 1
