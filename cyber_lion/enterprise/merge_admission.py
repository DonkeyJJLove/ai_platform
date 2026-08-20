"""Fail-closed GitHub merge admission bound to admitted Cyber-Lion authority.

This module is deliberately GitHub-effect specific. It supports a non-consuming live
admission path for CI evidence and a consuming path for one merge effect. Neither path
calls GitHub. Positive non-consuming evidence is not execution permission.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import re
from threading import Lock
from typing import Iterable

from .authority_grant import AuthorityGrant
from .authority_revocation import (
    AuthorityRevocationError,
    EpochAdmittedAuthorityLineage,
    authenticate_and_admit_authority_lineage,
)
from .authority_source import AuthorityLookupKey, AuthoritySource, AuthoritySourceError
from .authority_verification import AuthorityVerificationContext, IssuerKeyBinding, Verifier

_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_ALLOWED_MERGE_METHODS = frozenset({"merge", "squash", "rebase"})
_MERGE_ACTION = "merge_pull_request"


class MergeAdmissionError(ValueError):
    """Raised when an exact merge admission invariant cannot be satisfied."""


def _text(value: object, *, field_name: str, limit: int = 512) -> str:
    if (
        not isinstance(value, str)
        or not value.strip()
        or len(value) > limit
        or "\x00" in value
    ):
        raise MergeAdmissionError(f"{field_name} is invalid")
    return value


def _sha(value: object, *, field_name: str) -> str:
    value = _text(value, field_name=field_name, limit=40)
    if not _SHA_RE.fullmatch(value):
        raise MergeAdmissionError(f"{field_name} must be a full lowercase git SHA")
    return value


@dataclass(frozen=True)
class MergeIntent:
    """Requested GitHub merge effect. All fields participate in exact binding."""

    repository: str
    pr_number: int
    base_sha: str
    head_sha: str
    merge_method: str
    action: str = _MERGE_ACTION

    def validate(self) -> "MergeIntent":
        _text(self.repository, field_name="repository")
        if (
            not isinstance(self.pr_number, int)
            or isinstance(self.pr_number, bool)
            or self.pr_number <= 0
        ):
            raise MergeAdmissionError("pr_number must be a positive integer")
        _sha(self.base_sha, field_name="base_sha")
        _sha(self.head_sha, field_name="head_sha")
        if self.merge_method not in _ALLOWED_MERGE_METHODS:
            raise MergeAdmissionError("merge_method is unsupported")
        if self.action != _MERGE_ACTION:
            raise MergeAdmissionError("merge action must be merge_pull_request")
        return self

    def binding(self) -> tuple[str, int, str, str, str, str]:
        self.validate()
        return (
            self.repository,
            self.pr_number,
            self.base_sha,
            self.head_sha,
            self.merge_method,
            self.action,
        )


@dataclass(frozen=True)
class TrustedPullRequestState:
    """GitHub state obtained independently of the untrusted authority grant."""

    repository: str
    pr_number: int
    base_sha: str
    head_sha: str
    merge_method: str
    action: str = _MERGE_ACTION

    def validate(self) -> "TrustedPullRequestState":
        MergeIntent(
            repository=self.repository,
            pr_number=self.pr_number,
            base_sha=self.base_sha,
            head_sha=self.head_sha,
            merge_method=self.merge_method,
            action=self.action,
        ).validate()
        return self

    def binding(self) -> tuple[str, int, str, str, str, str]:
        self.validate()
        return (
            self.repository,
            self.pr_number,
            self.base_sha,
            self.head_sha,
            self.merge_method,
            self.action,
        )


def canonical_merge_resource(intent: MergeIntent) -> str:
    """Canonical resource token that an AuthorityGrant must contain exactly."""
    intent.validate()
    return (
        f"github:repo:{intent.repository}:pr:{intent.pr_number}:"
        f"base:{intent.base_sha}:head:{intent.head_sha}"
    )


def canonical_merge_method_constraint(intent: MergeIntent) -> str:
    intent.validate()
    return f"merge_method:{intent.merge_method}"


@dataclass(frozen=True)
class MergeAdmissionDecision:
    admission_id: str
    decision: str
    rationale: str
    repository: str
    pr_number: int
    base_sha: str
    head_sha: str
    merge_method: str
    grant_id: str | None = None
    grant_digest: str | None = None
    lineage_digest: str | None = None
    epoch: int | None = None

    def validate(self) -> "MergeAdmissionDecision":
        _text(self.admission_id, field_name="admission_id")
        _text(self.rationale, field_name="rationale", limit=1024)
        if self.decision not in {"ALLOW", "DENY"}:
            raise MergeAdmissionError("decision must be ALLOW or DENY")
        MergeIntent(
            self.repository,
            self.pr_number,
            self.base_sha,
            self.head_sha,
            self.merge_method,
        ).validate()
        if self.decision == "ALLOW":
            if not all(
                isinstance(value, str) and value
                for value in (self.grant_id, self.grant_digest, self.lineage_digest)
            ):
                raise MergeAdmissionError("ALLOW requires authority identity and digests")
            if (
                not isinstance(self.epoch, int)
                or isinstance(self.epoch, bool)
                or self.epoch < 0
            ):
                raise MergeAdmissionError("ALLOW requires a valid authority epoch")
        return self


@dataclass(frozen=True)
class NonConsumingMergeAdmissionEvidence:
    """Immutable positive live-admission evidence; never merge execution permission."""

    admission_id: str
    repository: str
    pr_number: int
    base_sha: str
    head_sha: str
    merge_method: str
    mission_id: str
    grant_id: str
    grant_digest: str
    lineage_digest: str
    source_lineage_digest: str
    epoch: int
    authority_provenance_id: str
    authority_source_kind: str

    def validate(self) -> "NonConsumingMergeAdmissionEvidence":
        _text(self.admission_id, field_name="admission_id")
        MergeIntent(
            self.repository,
            self.pr_number,
            self.base_sha,
            self.head_sha,
            self.merge_method,
        ).validate()
        for name, value in (
            ("mission_id", self.mission_id),
            ("grant_id", self.grant_id),
            ("grant_digest", self.grant_digest),
            ("lineage_digest", self.lineage_digest),
            ("source_lineage_digest", self.source_lineage_digest),
            ("authority_provenance_id", self.authority_provenance_id),
            ("authority_source_kind", self.authority_source_kind),
        ):
            _text(value, field_name=name)
        if self.authority_source_kind != "trusted-control-plane":
            raise MergeAdmissionError("non-consuming evidence requires trusted-control-plane source")
        if not isinstance(self.epoch, int) or isinstance(self.epoch, bool) or self.epoch < 0:
            raise MergeAdmissionError("non-consuming evidence epoch is invalid")
        return self


@dataclass(frozen=True)
class NonConsumingMergeAdmissionResult:
    """Fail-closed live admission result with positive evidence only on ALLOW."""

    admission_id: str
    decision: str
    rationale: str
    repository: str
    pr_number: int
    base_sha: str
    head_sha: str
    merge_method: str
    evidence: NonConsumingMergeAdmissionEvidence | None = None

    def validate(self) -> "NonConsumingMergeAdmissionResult":
        _text(self.admission_id, field_name="admission_id")
        _text(self.rationale, field_name="rationale", limit=1024)
        if self.decision not in {"ALLOW", "DENY"}:
            raise MergeAdmissionError("decision must be ALLOW or DENY")
        MergeIntent(
            self.repository,
            self.pr_number,
            self.base_sha,
            self.head_sha,
            self.merge_method,
        ).validate()
        if self.decision == "ALLOW":
            if type(self.evidence) is not NonConsumingMergeAdmissionEvidence:
                raise MergeAdmissionError("ALLOW requires exact non-consuming evidence")
            self.evidence.validate()
            expected = (
                self.admission_id,
                self.repository,
                self.pr_number,
                self.base_sha,
                self.head_sha,
                self.merge_method,
            )
            actual = (
                self.evidence.admission_id,
                self.evidence.repository,
                self.evidence.pr_number,
                self.evidence.base_sha,
                self.evidence.head_sha,
                self.evidence.merge_method,
            )
            if actual != expected:
                raise MergeAdmissionError("non-consuming evidence does not bind result")
        elif self.evidence is not None:
            raise MergeAdmissionError("DENY must not carry positive admission evidence")
        return self


@dataclass(frozen=True)
class MergeExecutionReceipt:
    receipt_id: str
    admission_id: str
    repository: str
    pr_number: int
    base_sha: str
    head_sha: str
    merge_sha: str
    merge_method: str
    grant_id: str
    grant_digest: str
    lineage_digest: str
    epoch: int
    executor: str
    outcome: str

    def validate(self) -> "MergeExecutionReceipt":
        _text(self.receipt_id, field_name="receipt_id")
        _text(self.admission_id, field_name="admission_id")
        _text(self.executor, field_name="executor")
        MergeIntent(
            self.repository,
            self.pr_number,
            self.base_sha,
            self.head_sha,
            self.merge_method,
        ).validate()
        _sha(self.merge_sha, field_name="merge_sha")
        for name, value in (
            ("grant_id", self.grant_id),
            ("grant_digest", self.grant_digest),
            ("lineage_digest", self.lineage_digest),
        ):
            _text(value, field_name=name)
        if not isinstance(self.epoch, int) or isinstance(self.epoch, bool) or self.epoch < 0:
            raise MergeAdmissionError("receipt epoch is invalid")
        if self.outcome not in {"SUCCEEDED", "FAILED", "PARTIAL", "ABORTED"}:
            raise MergeAdmissionError("invalid merge execution outcome")
        return self


class MergeAuthorityConsumptionOwner:
    """Process-local monotonic one-shot consumption owner for merge authority."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._consumed: dict[tuple[str, str, int], tuple[str, str, str, int]] = {}

    def consume(
        self,
        *,
        grant_id: str,
        grant_digest: str,
        lineage_digest: str,
        epoch: int,
    ) -> tuple[str, str, str, int]:
        _text(grant_id, field_name="grant_id")
        _text(grant_digest, field_name="grant_digest")
        _text(lineage_digest, field_name="lineage_digest")
        if not isinstance(epoch, int) or isinstance(epoch, bool) or epoch < 0:
            raise MergeAdmissionError("consumption epoch is invalid")
        replay_key = (grant_id, grant_digest, epoch)
        record = (grant_id, grant_digest, lineage_digest, epoch)
        with self._lock:
            if replay_key in self._consumed:
                raise MergeAdmissionError("merge authority has already been consumed")
            self._consumed[replay_key] = record
        return record

    def is_consumed(self, *, grant_id: str, grant_digest: str, epoch: int) -> bool:
        with self._lock:
            return (grant_id, grant_digest, epoch) in self._consumed


def _deny(intent: MergeIntent, admission_id: str, rationale: str) -> MergeAdmissionDecision:
    return MergeAdmissionDecision(
        admission_id=admission_id,
        decision="DENY",
        rationale=rationale,
        repository=intent.repository,
        pr_number=intent.pr_number,
        base_sha=intent.base_sha,
        head_sha=intent.head_sha,
        merge_method=intent.merge_method,
    ).validate()


def _deny_non_consuming(
    intent: MergeIntent, admission_id: str, rationale: str
) -> NonConsumingMergeAdmissionResult:
    return NonConsumingMergeAdmissionResult(
        admission_id=admission_id,
        decision="DENY",
        rationale=rationale,
        repository=intent.repository,
        pr_number=intent.pr_number,
        base_sha=intent.base_sha,
        head_sha=intent.head_sha,
        merge_method=intent.merge_method,
        evidence=None,
    ).validate()


def _bind_leaf(
    *,
    leaf: AuthorityGrant,
    admitted: EpochAdmittedAuthorityLineage,
    intent: MergeIntent,
) -> None:
    if type(leaf) is not AuthorityGrant:
        raise MergeAdmissionError("leaf must be exact AuthorityGrant")
    if type(admitted) is not EpochAdmittedAuthorityLineage:
        raise MergeAdmissionError("lineage admission evidence has invalid type")
    leaf.validate()
    if admitted.leaf_grant_id != leaf.grant_id:
        raise MergeAdmissionError("admitted lineage leaf does not match authority leaf")
    if not admitted.grant_digests or admitted.grant_digests[-1] != leaf.digest():
        raise MergeAdmissionError("admitted lineage digest does not match authority leaf")
    if admitted.mission_id != leaf.mission_id or admitted.epoch != leaf.epoch:
        raise MergeAdmissionError("admitted lineage context does not match authority leaf")
    if intent.action not in leaf.actions:
        raise MergeAdmissionError("authority leaf does not authorize merge action")
    if canonical_merge_resource(intent) not in leaf.resource_scope:
        raise MergeAdmissionError("authority leaf does not bind exact merge resource")
    if canonical_merge_method_constraint(intent) not in leaf.constraints:
        raise MergeAdmissionError("authority leaf does not bind exact merge method")


def _authenticate_and_bind(
    *,
    intent: MergeIntent,
    trusted_state: TrustedPullRequestState,
    lineage: tuple[AuthorityGrant, ...],
    issuer_keys: Iterable[IssuerKeyBinding],
    verifier: Verifier,
    context: AuthorityVerificationContext,
) -> tuple[EpochAdmittedAuthorityLineage, AuthorityGrant]:
    if type(trusted_state) is not TrustedPullRequestState:
        raise MergeAdmissionError("trusted_state must be exact TrustedPullRequestState")
    trusted_state.validate()
    if intent.binding() != trusted_state.binding():
        raise MergeAdmissionError("merge intent does not match trusted GitHub state")
    if type(lineage) is not tuple or not lineage:
        raise MergeAdmissionError("authority lineage is unavailable")
    admitted = authenticate_and_admit_authority_lineage(
        lineage,
        issuer_keys,
        verifier,
        context=context,
    )
    leaf = lineage[-1]
    _bind_leaf(leaf=leaf, admitted=admitted, intent=intent)
    return admitted, leaf


def _bind_lookup_key(
    *,
    intent: MergeIntent,
    lookup_key: AuthorityLookupKey,
    context: AuthorityVerificationContext,
) -> None:
    if type(lookup_key) is not AuthorityLookupKey:
        raise MergeAdmissionError("lookup_key must be exact AuthorityLookupKey")
    lookup_key.validate()
    context.validate()
    expected = (
        intent.repository,
        intent.pr_number,
        intent.base_sha,
        intent.head_sha,
        context.mission_id,
    )
    actual = (
        lookup_key.repository,
        lookup_key.pr_number,
        lookup_key.base_sha,
        lookup_key.head_sha,
        lookup_key.mission_id,
    )
    if actual != expected:
        raise MergeAdmissionError("authority lookup key does not bind exact trusted merge state")


def admit_merge_non_consuming(
    *,
    intent: MergeIntent,
    trusted_state: TrustedPullRequestState,
    authority_source: AuthoritySource,
    lookup_key: AuthorityLookupKey,
    issuer_keys: Iterable[IssuerKeyBinding],
    verifier: Verifier,
    context: AuthorityVerificationContext,
    admission_id: str,
) -> NonConsumingMergeAdmissionResult:
    """Resolve trusted authority and admit exact live PR state without consuming it."""
    if type(intent) is not MergeIntent:
        raise MergeAdmissionError("intent must be exact MergeIntent")
    intent.validate()
    _text(admission_id, field_name="admission_id")
    try:
        if type(context) is not AuthorityVerificationContext:
            raise MergeAdmissionError("context must be exact AuthorityVerificationContext")
        if not isinstance(authority_source, AuthoritySource):
            raise MergeAdmissionError("authority_source must implement AuthoritySource")
        _bind_lookup_key(intent=intent, lookup_key=lookup_key, context=context)
        record = authority_source.resolve_exact(lookup_key)
        admitted, leaf = _authenticate_and_bind(
            intent=intent,
            trusted_state=trusted_state,
            lineage=record.lineage,
            issuer_keys=issuer_keys,
            verifier=verifier,
            context=context,
        )
        if leaf.grant_id != lookup_key.grant_id:
            raise MergeAdmissionError("authority leaf does not match exact lookup grant_id")
        evidence = NonConsumingMergeAdmissionEvidence(
            admission_id=admission_id,
            repository=intent.repository,
            pr_number=intent.pr_number,
            base_sha=intent.base_sha,
            head_sha=intent.head_sha,
            merge_method=intent.merge_method,
            mission_id=context.mission_id,
            grant_id=leaf.grant_id,
            grant_digest=leaf.digest(),
            lineage_digest=admitted.lineage_digest,
            source_lineage_digest=record.lineage_digest,
            epoch=admitted.epoch,
            authority_provenance_id=record.provenance_id,
            authority_source_kind=record.source_kind,
        ).validate()
        return NonConsumingMergeAdmissionResult(
            admission_id=admission_id,
            decision="ALLOW",
            rationale="exact trusted authority, current epoch, and live GitHub state admitted without consumption",
            repository=intent.repository,
            pr_number=intent.pr_number,
            base_sha=intent.base_sha,
            head_sha=intent.head_sha,
            merge_method=intent.merge_method,
            evidence=evidence,
        ).validate()
    except Exception as exc:
        return _deny_non_consuming(
            intent,
            admission_id,
            str(exc) or "non-consuming merge admission failed closed",
        )


def admit_merge(
    *,
    intent: MergeIntent,
    trusted_state: TrustedPullRequestState,
    lineage: tuple[AuthorityGrant, ...],
    issuer_keys: Iterable[IssuerKeyBinding],
    verifier: Verifier,
    context: AuthorityVerificationContext,
    consumption_owner: MergeAuthorityConsumptionOwner,
    admission_id: str,
) -> MergeAdmissionDecision:
    """Authenticate/admit lineage, exact-bind GitHub state, and consume once."""
    if type(intent) is not MergeIntent:
        raise MergeAdmissionError("intent must be exact MergeIntent")
    intent.validate()
    _text(admission_id, field_name="admission_id")
    try:
        if type(consumption_owner) is not MergeAuthorityConsumptionOwner:
            raise MergeAdmissionError("consumption owner has invalid type")
        admitted, leaf = _authenticate_and_bind(
            intent=intent,
            trusted_state=trusted_state,
            lineage=lineage,
            issuer_keys=issuer_keys,
            verifier=verifier,
            context=context,
        )
        grant_digest = leaf.digest()
        consumption_owner.consume(
            grant_id=leaf.grant_id,
            grant_digest=grant_digest,
            lineage_digest=admitted.lineage_digest,
            epoch=admitted.epoch,
        )
        return MergeAdmissionDecision(
            admission_id=admission_id,
            decision="ALLOW",
            rationale="exact merge authority, lineage, current epoch, and GitHub state admitted",
            repository=intent.repository,
            pr_number=intent.pr_number,
            base_sha=intent.base_sha,
            head_sha=intent.head_sha,
            merge_method=intent.merge_method,
            grant_id=leaf.grant_id,
            grant_digest=grant_digest,
            lineage_digest=admitted.lineage_digest,
            epoch=admitted.epoch,
        ).validate()
    except (AuthorityRevocationError, AuthoritySourceError, MergeAdmissionError, ValueError, TypeError) as exc:
        return _deny(intent, admission_id, str(exc) or "merge admission failed closed")


def issue_merge_execution_receipt(
    *,
    decision: MergeAdmissionDecision,
    merge_sha: str,
    executor: str,
    outcome: str,
) -> MergeExecutionReceipt:
    """Create an immutable receipt only for an already-allowed exact merge."""
    if type(decision) is not MergeAdmissionDecision:
        raise MergeAdmissionError("decision must be exact MergeAdmissionDecision")
    decision.validate()
    if decision.decision != "ALLOW":
        raise MergeAdmissionError("cannot issue merge receipt for denied admission")
    assert decision.grant_id is not None
    assert decision.grant_digest is not None
    assert decision.lineage_digest is not None
    assert decision.epoch is not None
    payload = (
        f"{decision.admission_id}\x00{decision.repository}\x00{decision.pr_number}\x00"
        f"{decision.base_sha}\x00{decision.head_sha}\x00{merge_sha}\x00"
        f"{decision.merge_method}\x00{decision.grant_digest}\x00"
        f"{decision.lineage_digest}\x00{decision.epoch}\x00{executor}\x00{outcome}"
    ).encode("utf-8")
    receipt_id = "merge-receipt:" + hashlib.sha256(payload).hexdigest()
    return MergeExecutionReceipt(
        receipt_id=receipt_id,
        admission_id=decision.admission_id,
        repository=decision.repository,
        pr_number=decision.pr_number,
        base_sha=decision.base_sha,
        head_sha=decision.head_sha,
        merge_sha=merge_sha,
        merge_method=decision.merge_method,
        grant_id=decision.grant_id,
        grant_digest=decision.grant_digest,
        lineage_digest=decision.lineage_digest,
        epoch=decision.epoch,
        executor=executor,
        outcome=outcome,
    ).validate()
