"""Read-only trusted merge-authority observation contract and evaluator.

The observer is evidence-only. It receives capability-reduced trusted runtime callbacks,
records raw provider cardinality before unique resolution, verifies every lineage hop,
observes epoch/revocation through the public authority-revocation snapshot API, binds
validity to an injected trusted clock, and reads durable consumption state without any
write capability. Positive evidence is never merge execution permission.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
from enum import Enum
from hashlib import sha256
import json
import re
from typing import Callable, Mapping

from .authority_revocation import observe_canonical_authority_epoch_state
from .authority_source import AuthorityLookupKey
from .authority_source_adapter import TrustedControlPlaneAuthoritySource
from .authority_verification import AuthorityVerificationContext, authenticate_authority_grant
from .ci_live_admission import ReadOnlyAuthorityControlPlaneTransport
from .merge_admission import (
    MergeIntent,
    TrustedPullRequestState,
    canonical_merge_method_constraint,
    canonical_merge_resource,
)
from .merge_authority_consumption import (
    CallbackConsumptionReadCapability,
    MergeAuthorityConsumptionKey,
    MergeAuthorityConsumptionState,
)
from .pr_authority_bootstrap import (
    PRAuthorityBootstrapLookupKey,
    decode_pr_authority_bootstrap_record,
)

_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_DIGEST_RE = re.compile(r"^[0-9a-f]{64}$")
_OBSERVATION_SCHEMA = "1.0.0"
_OBSERVATION_DOMAIN = b"CYBER-LION/MERGE-AUTHORITY-OBSERVATION/1.0.0\x00"
_SECRET_TERMS = ("credential", "token", "secret", "private_key", "bearer", "password")


class MergeAuthorityObservationError(ValueError):
    pass


class ObservationTruth(str, Enum):
    YES = "YES"
    NO = "NO"
    UNAVAILABLE = "UNAVAILABLE"


@dataclass(frozen=True)
class ProviderIdentityEvidence:
    provider_role: str
    provider_version: str
    implementation_identity: str
    trusted_base_sha: str
    configuration_public_digest: str
    source_kind: str

    def validate(self) -> "ProviderIdentityEvidence":
        if type(self) is not ProviderIdentityEvidence:
            raise MergeAuthorityObservationError("provider identity has invalid type")
        for name in (
            "provider_role",
            "provider_version",
            "implementation_identity",
            "source_kind",
        ):
            value = getattr(self, name)
            if not isinstance(value, str) or not value or "\x00" in value or len(value) > 512:
                raise MergeAuthorityObservationError(f"{name} is invalid")
        if not _SHA_RE.fullmatch(self.trusted_base_sha):
            raise MergeAuthorityObservationError("trusted_base_sha is invalid")
        if not _DIGEST_RE.fullmatch(self.configuration_public_digest):
            raise MergeAuthorityObservationError("configuration_public_digest is invalid")
        lowered = json.dumps(asdict(self), sort_keys=True).lower()
        if any(term in lowered for term in _SECRET_TERMS):
            raise MergeAuthorityObservationError("provider identity contains forbidden secret-bearing field")
        return self


@dataclass(frozen=True)
class TrustedAuthorityClockObservation:
    observed_at: str
    trusted_clock_source_id: str

    def validate(self) -> "TrustedAuthorityClockObservation":
        if type(self) is not TrustedAuthorityClockObservation:
            raise MergeAuthorityObservationError("clock observation has invalid type")
        if not isinstance(self.trusted_clock_source_id, str) or not self.trusted_clock_source_id.strip():
            raise MergeAuthorityObservationError("trusted_clock_source_id is invalid")
        try:
            parsed = datetime.fromisoformat(self.observed_at.replace("Z", "+00:00"))
        except Exception as exc:
            raise MergeAuthorityObservationError("observed_at is invalid") from exc
        if parsed.tzinfo is None:
            raise MergeAuthorityObservationError("observed_at must be timezone-aware")
        if parsed.utcoffset() != timezone.utc.utcoffset(parsed):
            parsed = parsed.astimezone(timezone.utc)
        canonical = parsed.isoformat().replace("+00:00", "Z")
        if canonical != self.observed_at:
            raise MergeAuthorityObservationError("observed_at must be canonical UTC")
        return self

    def datetime_utc(self) -> datetime:
        self.validate()
        return datetime.fromisoformat(self.observed_at.replace("Z", "+00:00"))


@dataclass(frozen=True)
class TrustedMergeAuthorityObservation:
    schema_version: str
    observation_id: str
    repository: str
    pr_number: int
    base_sha: str
    head_sha: str
    provider_available: ObservationTruth
    provider_query_executed: ObservationTruth
    provider_response_valid: ObservationTruth
    authority_record_cardinality: int | None
    bootstrap_record_cardinality: int | None
    authority_record_id: str | None
    authority_provenance_id: str | None
    mission_id: str | None
    grant_id: str | None
    grant_digest: str | None
    lineage_digest: str | None
    epoch: int | None
    signature_hop_count: int | None
    signature_valid_hop_count: int | None
    signature_valid: ObservationTruth
    epoch_current: ObservationTruth
    revoked: ObservationTruth
    not_yet_valid: ObservationTruth
    expired: ObservationTruth
    consumed: ObservationTruth
    action_exact: ObservationTruth
    resource_exact: ObservationTruth
    merge_method_exact: ObservationTruth
    scope_exact: ObservationTruth
    authority_current: ObservationTruth
    action: str
    merge_method: str
    observed_at: str | None
    trusted_clock_source_id: str | None
    bootstrap_provider_identity: ProviderIdentityEvidence | None
    authority_provider_identity: ProviderIdentityEvidence | None
    verifier_provider_identity: ProviderIdentityEvidence | None
    clock_provider_identity: ProviderIdentityEvidence | None
    consumption_provider_identity: ProviderIdentityEvidence | None
    authority_source_kind: str | None
    authority_effect: ObservationTruth
    merge_authorization_inferred: ObservationTruth
    observation_digest: str

    def semantic_payload(self) -> dict[str, object]:
        value = asdict(self)
        value.pop("observation_digest", None)
        for key, item in list(value.items()):
            if isinstance(item, ObservationTruth):
                value[key] = item.value
        return value

    def expected_digest(self) -> str:
        encoded = json.dumps(
            self.semantic_payload(), sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")
        return sha256(_OBSERVATION_DOMAIN + encoded).hexdigest()

    def validate(self) -> "TrustedMergeAuthorityObservation":
        if type(self) is not TrustedMergeAuthorityObservation:
            raise MergeAuthorityObservationError("observation has invalid type")
        if self.schema_version != _OBSERVATION_SCHEMA:
            raise MergeAuthorityObservationError("observation schema is unsupported")
        if not isinstance(self.observation_id, str) or not self.observation_id.strip():
            raise MergeAuthorityObservationError("observation_id is invalid")
        TrustedPullRequestState(
            repository=self.repository,
            pr_number=self.pr_number,
            base_sha=self.base_sha,
            head_sha=self.head_sha,
            merge_method=self.merge_method,
        ).validate()
        if self.action != "merge_pull_request":
            raise MergeAuthorityObservationError("action must remain merge_pull_request")
        for field_name in (
            "provider_available",
            "provider_query_executed",
            "provider_response_valid",
            "signature_valid",
            "epoch_current",
            "revoked",
            "not_yet_valid",
            "expired",
            "consumed",
            "action_exact",
            "resource_exact",
            "merge_method_exact",
            "scope_exact",
            "authority_current",
            "authority_effect",
            "merge_authorization_inferred",
        ):
            if type(getattr(self, field_name)) is not ObservationTruth:
                raise MergeAuthorityObservationError(f"{field_name} must be exact ObservationTruth")
        if self.authority_effect is not ObservationTruth.NO:
            raise MergeAuthorityObservationError("authority_effect must be NO")
        if self.merge_authorization_inferred is not ObservationTruth.NO:
            raise MergeAuthorityObservationError("merge_authorization_inferred must be NO")
        for name in ("authority_record_cardinality", "bootstrap_record_cardinality"):
            value = getattr(self, name)
            if value is not None and (not isinstance(value, int) or isinstance(value, bool) or value < 0):
                raise MergeAuthorityObservationError(f"{name} is invalid")
        for name in ("signature_hop_count", "signature_valid_hop_count"):
            value = getattr(self, name)
            if value is not None and (not isinstance(value, int) or isinstance(value, bool) or value < 0):
                raise MergeAuthorityObservationError(f"{name} is invalid")
        if self.epoch is not None and (not isinstance(self.epoch, int) or isinstance(self.epoch, bool) or self.epoch < 0):
            raise MergeAuthorityObservationError("epoch is invalid")
        if self.observation_digest != self.expected_digest():
            raise MergeAuthorityObservationError("observation_digest mismatch")
        public = json.dumps(self.semantic_payload(), sort_keys=True).lower()
        if any(f'"{term}"' in public for term in _SECRET_TERMS):
            raise MergeAuthorityObservationError("observation contains forbidden secret-bearing field")
        return self

    def to_public_dict(self) -> dict[str, object]:
        self.validate()
        value = self.semantic_payload()
        value["observation_digest"] = self.observation_digest
        return value


def _truth(value: bool) -> ObservationTruth:
    return ObservationTruth.YES if value else ObservationTruth.NO


def provider_identity(
    *, role: str, provider_version: str, implementation_identity: str,
    trusted_base_sha: str, public_configuration: Mapping[str, object], source_kind: str,
) -> ProviderIdentityEvidence:
    encoded = json.dumps(dict(public_configuration), sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return ProviderIdentityEvidence(
        provider_role=role,
        provider_version=provider_version,
        implementation_identity=implementation_identity,
        trusted_base_sha=trusted_base_sha,
        configuration_public_digest=sha256(b"CYBER-LION/PROVIDER-PUBLIC-BINDING/1\0" + encoded).hexdigest(),
        source_kind=source_kind,
    ).validate()


def _clock_observation(clock_provider: Callable[[], Mapping[str, object]]) -> TrustedAuthorityClockObservation:
    try:
        raw = clock_provider()
    except Exception as exc:
        raise MergeAuthorityObservationError("trusted clock provider unavailable") from exc
    if not isinstance(raw, Mapping) or set(raw) != {"observed_at", "trusted_clock_source_id"}:
        raise MergeAuthorityObservationError("trusted clock response is not canonical")
    return TrustedAuthorityClockObservation(
        observed_at=raw["observed_at"], trusted_clock_source_id=raw["trusted_clock_source_id"]
    ).validate()


def _grant_window(lineage, observed_at: datetime) -> tuple[ObservationTruth, ObservationTruth]:
    not_yet = False
    expired = False
    for grant in lineage:
        issued = datetime.fromisoformat(grant.issued_at.replace("Z", "+00:00")).astimezone(timezone.utc)
        expires = datetime.fromisoformat(grant.expires_at.replace("Z", "+00:00")).astimezone(timezone.utc)
        not_yet = not_yet or observed_at < issued
        expired = expired or observed_at >= expires
    return _truth(not_yet), _truth(expired)


def _seal(observation: TrustedMergeAuthorityObservation) -> TrustedMergeAuthorityObservation:
    provisional = replace(observation, observation_digest="0" * 64)
    return replace(provisional, observation_digest=provisional.expected_digest()).validate()


def observe_trusted_merge_authority(
    *,
    pr_state: TrustedPullRequestState,
    observation_id: str,
    bootstrap_lookup_exact: Callable[..., tuple[Mapping[str, object], ...]],
    authority_lookup_exact: Callable[..., tuple[Mapping[str, object], ...]],
    verifier: Callable[[bytes, str, str, str], bool],
    clock_provider: Callable[[], Mapping[str, object]],
    consumption_read_provider: Callable[..., Mapping[str, object]],
    bootstrap_provider_identity: ProviderIdentityEvidence,
    authority_provider_identity: ProviderIdentityEvidence,
    verifier_provider_identity: ProviderIdentityEvidence,
    clock_provider_identity: ProviderIdentityEvidence,
    consumption_provider_identity: ProviderIdentityEvidence,
) -> TrustedMergeAuthorityObservation:
    """Execute one exact, non-consuming observation against injected read capabilities."""
    pr_state.validate()
    for item in (
        bootstrap_provider_identity, authority_provider_identity, verifier_provider_identity,
        clock_provider_identity, consumption_provider_identity,
    ):
        item.validate()

    intent = MergeIntent(
        repository=pr_state.repository,
        pr_number=pr_state.pr_number,
        base_sha=pr_state.base_sha,
        head_sha=pr_state.head_sha,
        merge_method=pr_state.merge_method,
    ).validate()

    common = dict(
        schema_version=_OBSERVATION_SCHEMA,
        observation_id=observation_id,
        repository=pr_state.repository,
        pr_number=pr_state.pr_number,
        base_sha=pr_state.base_sha,
        head_sha=pr_state.head_sha,
        action="merge_pull_request",
        merge_method=pr_state.merge_method,
        bootstrap_provider_identity=bootstrap_provider_identity,
        authority_provider_identity=authority_provider_identity,
        verifier_provider_identity=verifier_provider_identity,
        clock_provider_identity=clock_provider_identity,
        consumption_provider_identity=consumption_provider_identity,
        authority_effect=ObservationTruth.NO,
        merge_authorization_inferred=ObservationTruth.NO,
    )

    try:
        bootstrap_raw = bootstrap_lookup_exact(
            repository=pr_state.repository,
            pr_number=pr_state.pr_number,
            base_sha=pr_state.base_sha,
            head_sha=pr_state.head_sha,
            merge_method=pr_state.merge_method,
        )
    except Exception:
        return _seal(TrustedMergeAuthorityObservation(
            **common,
            provider_available=ObservationTruth.NO,
            provider_query_executed=ObservationTruth.YES,
            provider_response_valid=ObservationTruth.UNAVAILABLE,
            authority_record_cardinality=None,
            bootstrap_record_cardinality=None,
            authority_record_id=None,
            authority_provenance_id=None,
            mission_id=None,
            grant_id=None,
            grant_digest=None,
            lineage_digest=None,
            epoch=None,
            signature_hop_count=None,
            signature_valid_hop_count=None,
            signature_valid=ObservationTruth.UNAVAILABLE,
            epoch_current=ObservationTruth.UNAVAILABLE,
            revoked=ObservationTruth.UNAVAILABLE,
            not_yet_valid=ObservationTruth.UNAVAILABLE,
            expired=ObservationTruth.UNAVAILABLE,
            consumed=ObservationTruth.UNAVAILABLE,
            action_exact=ObservationTruth.UNAVAILABLE,
            resource_exact=ObservationTruth.UNAVAILABLE,
            merge_method_exact=ObservationTruth.UNAVAILABLE,
            scope_exact=ObservationTruth.UNAVAILABLE,
            authority_current=ObservationTruth.NO,
            observed_at=None,
            trusted_clock_source_id=None,
            authority_source_kind=None,
            observation_digest="0" * 64,
        ))

    if type(bootstrap_raw) is not tuple:
        raise MergeAuthorityObservationError("bootstrap provider result must be immutable tuple")
    bootstrap_count = len(bootstrap_raw)
    if bootstrap_count != 1:
        return _seal(TrustedMergeAuthorityObservation(
            **common,
            provider_available=ObservationTruth.YES,
            provider_query_executed=ObservationTruth.YES,
            provider_response_valid=ObservationTruth.YES,
            authority_record_cardinality=None,
            bootstrap_record_cardinality=bootstrap_count,
            authority_record_id=None,
            authority_provenance_id=None,
            mission_id=None,
            grant_id=None,
            grant_digest=None,
            lineage_digest=None,
            epoch=None,
            signature_hop_count=None,
            signature_valid_hop_count=None,
            signature_valid=ObservationTruth.UNAVAILABLE,
            epoch_current=ObservationTruth.UNAVAILABLE,
            revoked=ObservationTruth.UNAVAILABLE,
            not_yet_valid=ObservationTruth.UNAVAILABLE,
            expired=ObservationTruth.UNAVAILABLE,
            consumed=ObservationTruth.UNAVAILABLE,
            action_exact=ObservationTruth.UNAVAILABLE,
            resource_exact=ObservationTruth.UNAVAILABLE,
            merge_method_exact=ObservationTruth.UNAVAILABLE,
            scope_exact=ObservationTruth.UNAVAILABLE,
            authority_current=ObservationTruth.NO,
            observed_at=None,
            trusted_clock_source_id=None,
            authority_source_kind=None,
            observation_digest="0" * 64,
        ))

    bootstrap = decode_pr_authority_bootstrap_record(bootstrap_raw[0])
    expected_bootstrap_key = PRAuthorityBootstrapLookupKey(
        repository=pr_state.repository,
        pr_number=pr_state.pr_number,
        base_sha=pr_state.base_sha,
        head_sha=pr_state.head_sha,
        merge_method=pr_state.merge_method,
    ).validate()
    if bootstrap.lookup_key.binding() != expected_bootstrap_key.binding():
        raise MergeAuthorityObservationError("bootstrap record does not bind exact PR state")

    authority_key = AuthorityLookupKey(
        repository=pr_state.repository,
        pr_number=pr_state.pr_number,
        base_sha=pr_state.base_sha,
        head_sha=pr_state.head_sha,
        mission_id=bootstrap.mission_id,
        grant_id=bootstrap.grant_id,
    ).validate()
    try:
        authority_raw = authority_lookup_exact(
            repository=authority_key.repository,
            pr_number=authority_key.pr_number,
            base_sha=authority_key.base_sha,
            head_sha=authority_key.head_sha,
            mission_id=authority_key.mission_id,
            grant_id=authority_key.grant_id,
        )
    except Exception:
        authority_raw = None
    if authority_raw is None:
        authority_count = None
    elif type(authority_raw) is not tuple:
        raise MergeAuthorityObservationError("authority provider result must be immutable tuple")
    else:
        authority_count = len(authority_raw)

    if authority_count != 1:
        return _seal(TrustedMergeAuthorityObservation(
            **common,
            provider_available=ObservationTruth.YES if authority_raw is not None else ObservationTruth.NO,
            provider_query_executed=ObservationTruth.YES,
            provider_response_valid=ObservationTruth.YES if authority_raw is not None else ObservationTruth.UNAVAILABLE,
            authority_record_cardinality=authority_count,
            bootstrap_record_cardinality=bootstrap_count,
            authority_record_id=None,
            authority_provenance_id=None,
            mission_id=bootstrap.mission_id,
            grant_id=bootstrap.grant_id,
            grant_digest=None,
            lineage_digest=None,
            epoch=bootstrap.epoch,
            signature_hop_count=None,
            signature_valid_hop_count=None,
            signature_valid=ObservationTruth.UNAVAILABLE,
            epoch_current=ObservationTruth.UNAVAILABLE,
            revoked=ObservationTruth.UNAVAILABLE,
            not_yet_valid=ObservationTruth.UNAVAILABLE,
            expired=ObservationTruth.UNAVAILABLE,
            consumed=ObservationTruth.UNAVAILABLE,
            action_exact=ObservationTruth.UNAVAILABLE,
            resource_exact=ObservationTruth.UNAVAILABLE,
            merge_method_exact=ObservationTruth.UNAVAILABLE,
            scope_exact=ObservationTruth.UNAVAILABLE,
            authority_current=ObservationTruth.NO,
            observed_at=None,
            trusted_clock_source_id=None,
            authority_source_kind=None,
            observation_digest="0" * 64,
        ))

    source = TrustedControlPlaneAuthoritySource(
        ReadOnlyAuthorityControlPlaneTransport(lambda **_: authority_raw)
    )
    record = source.resolve_exact(authority_key)
    lineage = record.lineage
    context: AuthorityVerificationContext = bootstrap.to_live_admission_bootstrap().verification_context()

    signature_hops = len(lineage)
    signature_valid_hops = 0
    signature_state = ObservationTruth.YES
    for grant in lineage:
        try:
            authenticate_authority_grant(
                grant, bootstrap.issuer_key_bindings, verifier, context=context
            )
            signature_valid_hops += 1
        except Exception:
            signature_state = ObservationTruth.NO
    if signature_hops == 0:
        signature_state = ObservationTruth.UNAVAILABLE

    epoch_snapshot = observe_canonical_authority_epoch_state(context)
    epoch_current = _truth(all(grant.epoch == epoch_snapshot.epoch for grant in lineage))
    revoked = _truth(any(grant.grant_id in epoch_snapshot.revoked_grant_ids for grant in lineage))

    clock = _clock_observation(clock_provider)
    observed_dt = clock.datetime_utc()
    not_yet_valid, expired = _grant_window(lineage, observed_dt)

    leaf = lineage[-1]
    action_exact = _truth(intent.action in leaf.actions)
    resource_exact = _truth(canonical_merge_resource(intent) in leaf.resource_scope)
    method_exact = _truth(canonical_merge_method_constraint(intent) in leaf.constraints)
    scope_exact = _truth(
        action_exact is ObservationTruth.YES
        and resource_exact is ObservationTruth.YES
        and method_exact is ObservationTruth.YES
    )

    consumption_key = MergeAuthorityConsumptionKey(
        repository=pr_state.repository,
        pr_number=pr_state.pr_number,
        base_sha=pr_state.base_sha,
        head_sha=pr_state.head_sha,
        grant_id=leaf.grant_id,
        grant_digest=leaf.digest(),
        lineage_digest=record.lineage_digest,
        epoch=leaf.epoch,
        merge_method=pr_state.merge_method,
    ).validate()
    try:
        consumption = CallbackConsumptionReadCapability(
            consumption_read_provider
        ).observe_consumption_exact(consumption_key)
        if consumption.state is MergeAuthorityConsumptionState.CONSUMED:
            consumed = ObservationTruth.YES
        elif consumption.state is MergeAuthorityConsumptionState.AVAILABLE:
            consumed = ObservationTruth.NO
        else:
            consumed = ObservationTruth.UNAVAILABLE
    except Exception:
        consumed = ObservationTruth.UNAVAILABLE

    current = _truth(
        bootstrap_count == 1
        and authority_count == 1
        and signature_state is ObservationTruth.YES
        and epoch_current is ObservationTruth.YES
        and revoked is ObservationTruth.NO
        and not_yet_valid is ObservationTruth.NO
        and expired is ObservationTruth.NO
        and consumed is ObservationTruth.NO
        and scope_exact is ObservationTruth.YES
    )

    return _seal(TrustedMergeAuthorityObservation(
        **common,
        provider_available=ObservationTruth.YES,
        provider_query_executed=ObservationTruth.YES,
        provider_response_valid=ObservationTruth.YES,
        authority_record_cardinality=authority_count,
        bootstrap_record_cardinality=bootstrap_count,
        authority_record_id=record.lineage_digest,
        authority_provenance_id=record.provenance_id,
        mission_id=bootstrap.mission_id,
        grant_id=leaf.grant_id,
        grant_digest=leaf.digest(),
        lineage_digest=record.lineage_digest,
        epoch=leaf.epoch,
        signature_hop_count=signature_hops,
        signature_valid_hop_count=signature_valid_hops,
        signature_valid=signature_state,
        epoch_current=epoch_current,
        revoked=revoked,
        not_yet_valid=not_yet_valid,
        expired=expired,
        consumed=consumed,
        action_exact=action_exact,
        resource_exact=resource_exact,
        merge_method_exact=method_exact,
        scope_exact=scope_exact,
        authority_current=current,
        observed_at=clock.observed_at,
        trusted_clock_source_id=clock.trusted_clock_source_id,
        authority_source_kind=record.source_kind,
        observation_digest="0" * 64,
    ))
