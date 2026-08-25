"""Fail-closed, non-effectful consumption boundary for BoundedCandidateBuildAuthorization."""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from typing import Protocol, Mapping, Any

from cyber_lion.contracts.build_authorization_consumption import (
    BuildAuthorizationConsumptionPermit,
    SCHEMA_VERSION,
    canonical_json,
)
from cyber_lion.contracts.candidate_build_authorization import (
    BoundedCandidateBuildAuthorization,
    TrustedRepositoryBaseline,
)
from cyber_lion.enterprise.candidate_build_authorization import (
    LiveAdmittedResourceAuthority,
    LiveResourceAuthorityAdmission,
)


class BuildAuthorizationConsumptionError(RuntimeError):
    pass


_REPLAY_DOMAIN = b"LION/E004-CANDIDATE-BUILD-AUTHORIZATION-CONSUMPTION/1\0"
_EFFECT_METHODS = frozenset({
    "execute", "write", "push", "merge", "deploy", "release", "create_branch",
    "create_pr", "run_test", "build_candidate", "consume_candidate", "issue_grant",
})


def _utc(value: str, *, name: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, ValueError) as exc:
        raise BuildAuthorizationConsumptionError(f"{name} invalid") from exc
    if parsed.tzinfo is None:
        raise BuildAuthorizationConsumptionError(f"{name} must be timezone-aware")
    return parsed.astimezone(timezone.utc)


def _digest(payload: object) -> str:
    return sha256(_REPLAY_DOMAIN + canonical_json(payload)).hexdigest()


class TrustedRepositoryBaselineSource(Protocol):
    def current(self, repository: str) -> TrustedRepositoryBaseline: ...


class F005StateSource(Protocol):
    def current(self) -> Mapping[str, Any]: ...


class ConsumptionReplayGuard(Protocol):
    def consume(self, replay_digest: str, *, consumed_at: str) -> bool: ...


class PersistentBuildAuthorizationConsumptionReplayGuard:
    DOMAIN = "candidate-build-authorization-consumption"

    def __init__(self, store: object) -> None:
        if not callable(getattr(store, "consume_replay", None)):
            raise BuildAuthorizationConsumptionError("persistent replay store unavailable")
        self._store = store

    def consume(self, replay_digest: str, *, consumed_at: str) -> bool:
        return self._store.consume_replay(self.DOMAIN, replay_digest, consumed_at)


class BuildAuthorizationConsumptionEngine:
    """Issue one non-effectful single-use permit; never invoke a builder."""

    def __init__(
        self,
        *,
        live_authority: LiveResourceAuthorityAdmission,
        baseline_source: TrustedRepositoryBaselineSource,
        f005_state_source: F005StateSource,
        replay_guard: ConsumptionReplayGuard,
    ) -> None:
        if type(live_authority) is not LiveResourceAuthorityAdmission:
            raise BuildAuthorizationConsumptionError("live authority admission required")
        if not callable(getattr(baseline_source, "current", None)):
            raise BuildAuthorizationConsumptionError("trusted baseline source unavailable")
        if not callable(getattr(f005_state_source, "current", None)):
            raise BuildAuthorizationConsumptionError("F005 state source unavailable")
        if not callable(getattr(replay_guard, "consume", None)):
            raise BuildAuthorizationConsumptionError("consumption replay guard unavailable")
        self._live = live_authority
        self._baseline_source = baseline_source
        self._f005 = f005_state_source
        self._replay = replay_guard

    @staticmethod
    def _validate_authorization(value: object) -> BoundedCandidateBuildAuthorization:
        if type(value) is not BoundedCandidateBuildAuthorization:
            raise BuildAuthorizationConsumptionError("exact BoundedCandidateBuildAuthorization required")
        try:
            value.validate()
        except Exception as exc:
            raise BuildAuthorizationConsumptionError("authorization contract invalid") from exc
        if not value.authorization_digest or value.authorization_digest != value.compute_digest():
            raise BuildAuthorizationConsumptionError("authorization must be sealed")
        if value.authorization_id != f"cba:{value.issuance_replay_digest}":
            raise BuildAuthorizationConsumptionError("authorization identity/source mismatch")
        if value.state != "AUTHORIZATION_ISSUED" or value.action != "BUILD_CANDIDATE":
            raise BuildAuthorizationConsumptionError("authorization state/action invalid")
        if value.requested_authority != "local_write" or value.effective_authority_ceiling != "local_write":
            raise BuildAuthorizationConsumptionError("authorization authority class invalid")
        return value

    @staticmethod
    def _validate_live(value: object) -> LiveAdmittedResourceAuthority:
        if type(value) is not LiveAdmittedResourceAuthority:
            raise BuildAuthorizationConsumptionError("exact LiveAdmittedResourceAuthority required")
        try:
            value.validate()
        except Exception as exc:
            raise BuildAuthorizationConsumptionError("live authority receipt invalid") from exc
        return value

    @staticmethod
    def _check_f005(state: Mapping[str, Any]) -> None:
        if not isinstance(state, Mapping):
            raise BuildAuthorizationConsumptionError("F005 state unavailable")
        if state.get("state") != "QUARANTINED" or state.get("effect_authority") != "DENY":
            raise BuildAuthorizationConsumptionError("F005 quarantine invariant failed")

    def issue_permit(
        self,
        *,
        authorization: BoundedCandidateBuildAuthorization,
        admitted_authority: LiveAdmittedResourceAuthority,
        trusted_now: datetime,
    ) -> BuildAuthorizationConsumptionPermit:
        authorization = self._validate_authorization(authorization)
        admitted_authority = self._validate_live(admitted_authority)
        if not isinstance(trusted_now, datetime) or trusted_now.tzinfo is None:
            raise BuildAuthorizationConsumptionError("trusted_now must be timezone-aware")
        now = trusted_now.astimezone(timezone.utc)
        if now < _utc(authorization.valid_from, name="authorization valid_from"):
            raise BuildAuthorizationConsumptionError("authorization not yet valid")
        if now >= _utc(authorization.expires_at, name="authorization expires_at"):
            raise BuildAuthorizationConsumptionError("authorization expired")

        current_baseline = self._baseline_source.current(authorization.repository)
        if type(current_baseline) is not TrustedRepositoryBaseline:
            raise BuildAuthorizationConsumptionError("trusted baseline type invalid")
        current_baseline.validate()
        if (
            current_baseline.repository != authorization.repository
            or current_baseline.master_sha != authorization.baseline_master_sha
            or current_baseline.master_tree_sha != authorization.baseline_master_tree_sha
            or current_baseline.digest() != authorization.baseline_observation_digest
        ):
            raise BuildAuthorizationConsumptionError("authorization baseline stale or substituted")

        try:
            current_authority = self._live.revalidate(admitted_authority, now=now)
        except Exception as exc:
            raise BuildAuthorizationConsumptionError("current authority revalidation failed") from exc
        if type(current_authority) is not LiveAdmittedResourceAuthority:
            raise BuildAuthorizationConsumptionError("revalidated authority type invalid")
        current_authority.validate()

        expected = (
            authorization.repository,
            authorization.grant_id,
            authorization.leaf_grant_digest,
            authorization.authority_lineage_digest,
            authorization.authority_provenance_id,
            authorization.authority_epoch,
            authorization.authority_state_version,
            authorization.root_grant_id,
            authorization.root_grant_digest,
            authorization.live_admission_digest,
            authorization.resource_scope,
            "BUILD_CANDIDATE",
        )
        actual = (
            current_authority.repository,
            current_authority.grant_id,
            current_authority.leaf_grant_digest,
            current_authority.lineage_digest,
            current_authority.provenance_id,
            current_authority.epoch,
            current_authority.epoch_state_version,
            current_authority.root_grant_id,
            current_authority.root_grant_digest,
            current_authority.digest(),
            current_authority.resource_scope,
            current_authority.action,
        )
        if actual != expected:
            raise BuildAuthorizationConsumptionError("authorization/current authority binding mismatch")
        if current_authority.authority_ceiling not in {"local_write", "external_write", "financial", "deploy", "privileged"}:
            raise BuildAuthorizationConsumptionError("current authority cannot contain local_write")

        self._check_f005(self._f005.current())

        replay_payload = {
            "authorization_id": authorization.authorization_id,
            "authorization_digest": authorization.authorization_digest,
            "issuance_replay_digest": authorization.issuance_replay_digest,
            "repository": authorization.repository,
            "baseline_master_sha": authorization.baseline_master_sha,
            "baseline_master_tree_sha": authorization.baseline_master_tree_sha,
            "current_baseline_digest": current_baseline.digest(),
            "candidate_scope": list(authorization.candidate_scope),
            "resource_scope": list(authorization.resource_scope),
            "action": "BUILD_CANDIDATE",
            "grant_id": authorization.grant_id,
            "leaf_grant_digest": authorization.leaf_grant_digest,
            "authority_lineage_digest": authorization.authority_lineage_digest,
            "authority_epoch": authorization.authority_epoch,
            "authority_state_version": authorization.authority_state_version,
            "root_grant_id": authorization.root_grant_id,
            "root_grant_digest": authorization.root_grant_digest,
            "live_admission_digest": authorization.live_admission_digest,
            "current_authority_digest": current_authority.digest(),
        }
        replay_digest = _digest(replay_payload)
        checked_at = now.isoformat()
        if self._replay.consume(replay_digest, consumed_at=checked_at) is not True:
            raise BuildAuthorizationConsumptionError("authorization consumption replay denied")

        permit = BuildAuthorizationConsumptionPermit(
            schema_version=SCHEMA_VERSION,
            consumption_permit_id=f"cbcp:{replay_digest}",
            authorization_id=authorization.authorization_id,
            authorization_digest=authorization.authorization_digest,
            issuance_replay_digest=authorization.issuance_replay_digest,
            repository=authorization.repository,
            baseline_master_sha=authorization.baseline_master_sha,
            baseline_master_tree_sha=authorization.baseline_master_tree_sha,
            baseline_observation_digest=authorization.baseline_observation_digest,
            action="BUILD_CANDIDATE",
            candidate_scope=authorization.candidate_scope,
            resource_scope=authorization.resource_scope,
            grant_id=authorization.grant_id,
            leaf_grant_digest=authorization.leaf_grant_digest,
            authority_lineage_digest=authorization.authority_lineage_digest,
            authority_provenance_id=authorization.authority_provenance_id,
            authority_epoch=authorization.authority_epoch,
            authority_state_version=authorization.authority_state_version,
            root_grant_id=authorization.root_grant_id,
            root_grant_digest=authorization.root_grant_digest,
            live_admission_digest=authorization.live_admission_digest,
            authorization_valid_from=authorization.valid_from,
            authorization_expires_at=authorization.expires_at,
            checked_at=checked_at,
            current_baseline_digest=current_baseline.digest(),
            current_authority_digest=current_authority.digest(),
            consumption_replay_digest=replay_digest,
        ).sealed()
        return permit

    @classmethod
    def assert_no_effect_surface(cls) -> None:
        for name in _EFFECT_METHODS:
            if hasattr(cls, name):
                raise BuildAuthorizationConsumptionError(f"effect surface present: {name}")
