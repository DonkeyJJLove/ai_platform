"""Read-only adapters from live LION source owners into FCSR R2 observations.

Adapters never receive FleetStatusStore and expose no mutation, authority, lease, or
effect capability. Missing providers remain absent; no synthetic liveness is created.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
from typing import Callable, Protocol, Sequence

from cyber_lion.contracts.fleet_status import TrustedVerificationEvidence
from cyber_lion.contracts.fleet_status_sources import (
    StatusSourceIdentity,
    StatusSourceObservation,
    StatusSourceRead,
    canonical_json,
)


class FleetStatusAdapterError(RuntimeError):
    pass


def _now(clock: Callable[[], datetime]) -> str:
    value = clock()
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise FleetStatusAdapterError("adapter trusted clock must be timezone-aware")
    return value.astimezone(timezone.utc).isoformat()


def _items(values: dict[str, object]) -> tuple[tuple[str, str], ...]:
    normalized: list[tuple[str, str]] = []
    for key, value in values.items():
        if isinstance(value, (dict, list, tuple)):
            raw = json.dumps(value, sort_keys=True, separators=(",", ":"))
        elif value is None:
            raw = "null"
        elif isinstance(value, bool):
            raw = "true" if value else "false"
        else:
            raw = str(value)
        normalized.append((str(key), raw))
    return tuple(sorted(normalized))


def _digest(values: dict[str, object]) -> str:
    return sha256(canonical_json(values)).hexdigest()


def _observation_id(source_id: str, mission_id: str | None, dimension: str, evidence_digest: str, suffix: str = "") -> str:
    return sha256(f"{source_id}|{mission_id}|{dimension}|{evidence_digest}|{suffix}".encode()).hexdigest()


class ReadOnlyStatusSource(Protocol):
    @property
    def source_identity(self) -> StatusSourceIdentity: ...
    def read(self) -> StatusSourceRead: ...


class FleetControlRegistry(Protocol):
    def mission_ids(self) -> tuple[str, ...]: ...
    def spec(self, mission_id: str): ...
    def state(self, mission_id: str) -> str: ...
    def snapshot(self) -> tuple[tuple[str, str, int], ...]: ...


class FleetControlStatusAdapter:
    """Reads MissionRegistry-style state; integer heartbeat counters are not liveness."""

    def __init__(self, source_identity: StatusSourceIdentity, registry: FleetControlRegistry, clock: Callable[[], datetime]) -> None:
        if source_identity.source_kind != "FLEET_CONTROL":
            raise FleetStatusAdapterError("FleetControl adapter requires FLEET_CONTROL source identity")
        self._identity = source_identity.validate()
        self._registry = registry
        self._clock = clock

    @property
    def source_identity(self) -> StatusSourceIdentity:
        return self._identity

    def read(self) -> StatusSourceRead:
        observed_at = _now(self._clock)
        snapshot = dict((mission_id, (state, heartbeat)) for mission_id, state, heartbeat in self._registry.snapshot())
        observations: list[StatusSourceObservation] = []
        for mission_id in self._registry.mission_ids():
            spec = self._registry.spec(mission_id)
            state = self._registry.state(mission_id)
            snap = snapshot.get(mission_id)
            if snap is None or snap[0] != state:
                raise FleetStatusAdapterError("FleetControl snapshot/state disagreement")
            identity_values = {
                "drone_id": spec.drone_id,
                "parent_mission_id": spec.parent_mission_id,
                "repository": spec.repository,
                "baseline_sha": spec.baseline_sha,
                "branch": spec.branch,
                "sandbox_id": spec.sandbox_id,
                "read_scope": tuple(spec.read_scope),
                "write_scope": tuple(spec.write_scope),
            }
            identity_digest = _digest(identity_values)
            observations.append(StatusSourceObservation(
                _observation_id(self._identity.source_id, mission_id, "IDENTITY", identity_digest),
                mission_id, spec.drone_id, None, None, spec.repository, spec.baseline_sha,
                "IDENTITY", "OBSERVED", _items(identity_values),
                f"fleet-control:{mission_id}:{identity_digest}", identity_digest, "OBSERVED",
            ).validate())
            mission_values = {
                "closure_state": "OPEN",
                "dependency_state": "UNKNOWN",
                "fcp_heartbeat_sequence": snap[1],
                "phase": "UNKNOWN",
            }
            mission_digest = _digest({"mission_id": mission_id, "state": state, **mission_values})
            observations.append(StatusSourceObservation(
                _observation_id(self._identity.source_id, mission_id, "MISSION", mission_digest),
                mission_id, spec.drone_id, None, None, spec.repository, spec.baseline_sha,
                "MISSION", state, _items(mission_values),
                f"fleet-control-state:{mission_id}:{mission_digest}", mission_digest, "OBSERVED",
            ).validate())
        return StatusSourceRead(self._identity, observed_at, tuple(observations)).validate()


class VerifiedRuntimeProvider(Protocol):
    def list_verified_runtime(self) -> tuple[object, ...]: ...


class RuntimeAttestationStatusAdapter:
    def __init__(self, source_identity: StatusSourceIdentity, provider: VerifiedRuntimeProvider, clock: Callable[[], datetime]) -> None:
        if source_identity.source_kind != "RUNTIME_ATTESTATION":
            raise FleetStatusAdapterError("runtime adapter requires RUNTIME_ATTESTATION identity")
        self._identity = source_identity.validate()
        self._provider = provider
        self._clock = clock

    @property
    def source_identity(self) -> StatusSourceIdentity:
        return self._identity

    def read(self) -> StatusSourceRead:
        observed_at = _now(self._clock)
        observations = []
        for runtime in self._provider.list_verified_runtime():
            required = (
                "subject_id", "runtime_instance_id", "repository", "commit_sha", "run_id",
                "run_attempt", "mission_id", "artifact_digest", "implementation_digest",
                "attestation_digest", "provenance_ref", "trust_anchor_id",
            )
            if any(not hasattr(runtime, name) for name in required):
                raise FleetStatusAdapterError("runtime provider returned incomplete verified evidence")
            tree_sha = getattr(runtime, "tree_sha", None)
            values = {
                "artifact_digest": runtime.artifact_digest,
                "attestation_digest": runtime.attestation_digest,
                "commit_sha": runtime.commit_sha,
                "executor_id": runtime.subject_id,
                "implementation_digest": runtime.implementation_digest,
                "provenance_ref": runtime.provenance_ref,
                "repository": runtime.repository,
                "run_attempt": runtime.run_attempt,
                "run_id": runtime.run_id,
                "runtime_id": runtime.runtime_instance_id,
                "trust_anchor_id": runtime.trust_anchor_id,
            }
            if tree_sha:
                values["tree_sha"] = tree_sha
            evidence_digest = _digest(values)
            observations.append(StatusSourceObservation(
                _observation_id(self._identity.source_id, runtime.mission_id, "RUNTIME", evidence_digest, runtime.runtime_instance_id),
                runtime.mission_id, None, runtime.subject_id, runtime.runtime_instance_id,
                runtime.repository, None, "RUNTIME", "VERIFIED", _items(values),
                runtime.provenance_ref, evidence_digest, "ANCHORED",
            ).validate())
        return StatusSourceRead(self._identity, observed_at, tuple(observations)).validate()


class AuthorityBoundRuntimeProvider(Protocol):
    def list_authority_bound_runtime(self) -> tuple[object, ...]: ...


class RuntimeAuthorityStatusAdapter:
    """Corroborating authority binding only; BOUND never means current ACTIVE permission."""

    def __init__(self, source_identity: StatusSourceIdentity, provider: AuthorityBoundRuntimeProvider, clock: Callable[[], datetime]) -> None:
        if source_identity.source_kind != "RUNTIME_AUTHORITY":
            raise FleetStatusAdapterError("runtime-authority adapter requires RUNTIME_AUTHORITY identity")
        self._identity = source_identity.validate()
        self._provider = provider
        self._clock = clock

    @property
    def source_identity(self) -> StatusSourceIdentity:
        return self._identity

    def read(self) -> StatusSourceRead:
        observed_at = _now(self._clock)
        observations = []
        for binding in self._provider.list_authority_bound_runtime():
            required = (
                "runtime_instance_id", "provenance_ref", "mission_id", "repository", "base_sha",
                "head_sha", "grant_id", "authority_epoch", "authority_state_version",
                "authority_root_grant_digest", "binding_digest",
            )
            if any(not hasattr(binding, name) for name in required):
                raise FleetStatusAdapterError("runtime-authority provider returned incomplete evidence")
            authority_values = {
                "authority_epoch": binding.authority_epoch,
                "authority_state_version": binding.authority_state_version,
                "base_sha": binding.base_sha,
                "grant_id": binding.grant_id,
                "head_sha": binding.head_sha,
                "root_grant_digest": binding.authority_root_grant_digest,
                "runtime_id": binding.runtime_instance_id,
            }
            observations.append(StatusSourceObservation(
                _observation_id(self._identity.source_id, binding.mission_id, "AUTHORITY", binding.binding_digest),
                binding.mission_id, None, None, binding.runtime_instance_id, binding.repository, binding.base_sha,
                "AUTHORITY", "BOUND", _items(authority_values), binding.provenance_ref,
                binding.binding_digest, "ANCHORED",
            ).validate())
            runtime_values = {
                "commit_sha": binding.head_sha,
                "repository": binding.repository,
                "runtime_id": binding.runtime_instance_id,
            }
            runtime_digest = _digest({"binding_digest": binding.binding_digest, **runtime_values})
            observations.append(StatusSourceObservation(
                _observation_id(self._identity.source_id, binding.mission_id, "RUNTIME", runtime_digest),
                binding.mission_id, None, None, binding.runtime_instance_id, binding.repository, binding.base_sha,
                "RUNTIME", "BOUND", _items(runtime_values), binding.provenance_ref,
                runtime_digest, "ANCHORED",
            ).validate())
        return StatusSourceRead(self._identity, observed_at, tuple(observations)).validate()


@dataclass(frozen=True)
class AuthorityStatusView:
    mission_id: str
    state: str
    grant_id: str
    authority_epoch: int
    authority_state_version: int
    observed_at: str
    provenance_ref: str
    evidence_digest: str


class PersistentAuthorityProvider(Protocol):
    def list_authority_status(self) -> tuple[AuthorityStatusView, ...]: ...


class PersistentAuthorityStatusAdapter:
    def __init__(self, source_identity: StatusSourceIdentity, provider: PersistentAuthorityProvider, clock: Callable[[], datetime]) -> None:
        if source_identity.source_kind != "AUTHORITY_STATE":
            raise FleetStatusAdapterError("persistent authority adapter requires AUTHORITY_STATE identity")
        self._identity = source_identity.validate()
        self._provider = provider
        self._clock = clock

    @property
    def source_identity(self) -> StatusSourceIdentity:
        return self._identity

    def read(self) -> StatusSourceRead:
        views = self._provider.list_authority_status()
        latest = _now(self._clock)
        observations = tuple(StatusSourceObservation(
            _observation_id(self._identity.source_id, item.mission_id, "AUTHORITY", item.evidence_digest),
            item.mission_id, None, None, None, None, None, "AUTHORITY", item.state,
            _items({"authority_epoch": item.authority_epoch, "authority_state_version": item.authority_state_version, "grant_id": item.grant_id, "source_record_observed_at": item.observed_at}),
            item.provenance_ref, item.evidence_digest, "ANCHORED",
        ).validate() for item in views)
        return StatusSourceRead(self._identity, latest, observations).validate()


@dataclass(frozen=True)
class RepositoryEffectView:
    mission_id: str
    effect_id: str
    state: str
    repository: str
    expected_head_sha: str
    candidate_commit_sha: str
    observed_head_sha: str | None
    observed_at: str
    provenance_ref: str
    evidence_digest: str


class RepositoryEffectProvider(Protocol):
    def list_effect_states(self) -> tuple[RepositoryEffectView, ...]: ...


class RepositoryEffectStatusAdapter:
    def __init__(self, source_identity: StatusSourceIdentity, provider: RepositoryEffectProvider, clock: Callable[[], datetime]) -> None:
        if source_identity.source_kind != "EFFECT":
            raise FleetStatusAdapterError("repository effect adapter requires EFFECT identity")
        self._identity = source_identity.validate()
        self._provider = provider
        self._clock = clock

    @property
    def source_identity(self) -> StatusSourceIdentity:
        return self._identity

    def read(self) -> StatusSourceRead:
        views = self._provider.list_effect_states()
        latest = _now(self._clock)
        observations = tuple(StatusSourceObservation(
            _observation_id(self._identity.source_id, item.mission_id, "EFFECT", item.evidence_digest, item.effect_id),
            item.mission_id, None, None, None, item.repository, item.expected_head_sha,
            "EFFECT", item.state,
            _items({
                "candidate_commit_sha": item.candidate_commit_sha,
                "effect_id": item.effect_id,
                "expected_head_sha": item.expected_head_sha,
                "observed_head_sha": item.observed_head_sha,
                "source_record_observed_at": item.observed_at,
            }),
            item.provenance_ref, item.evidence_digest, "ANCHORED",
        ).validate() for item in views)
        return StatusSourceRead(self._identity, latest, observations).validate()


class VerificationEvidenceProvider(Protocol):
    def list_verification_evidence(self) -> tuple[TrustedVerificationEvidence, ...]: ...


class TrustedVerificationStatusAdapter:
    def __init__(self, source_identity: StatusSourceIdentity, provider: VerificationEvidenceProvider, clock: Callable[[], datetime]) -> None:
        if source_identity.source_kind != "VERIFICATION":
            raise FleetStatusAdapterError("verification adapter requires VERIFICATION identity")
        self._identity = source_identity.validate()
        self._provider = provider
        self._clock = clock

    @property
    def source_identity(self) -> StatusSourceIdentity:
        return self._identity

    def read(self) -> StatusSourceRead:
        observed_at = _now(self._clock)
        observations = []
        for evidence in self._provider.list_verification_evidence():
            if type(evidence) is not TrustedVerificationEvidence:
                raise FleetStatusAdapterError("verification provider returned wrong type")
            evidence.validate()
            values = {
                "executor_id": evidence.executor_id,
                "verification_id": evidence.verification_id,
                "verifier_id": evidence.verifier_id,
                "verifier_identity_digest": evidence.verifier_identity_digest,
                "verifier_implementation_digest": evidence.verifier_implementation_digest,
                "trust_anchor_id": evidence.trust_anchor_id,
                "trust_anchor_digest": evidence.trust_anchor_digest,
            }
            observations.append(StatusSourceObservation(
                _observation_id(self._identity.source_id, evidence.mission_id, "VERIFICATION", evidence.evidence_digest),
                evidence.mission_id, evidence.drone_id, evidence.executor_id, None, None, None,
                "VERIFICATION", evidence.verification_state, _items(values),
                evidence.source_provenance_ref, evidence.evidence_digest, evidence.epistemic_class,
            ).validate())
        return StatusSourceRead(self._identity, observed_at, tuple(observations)).validate()


@dataclass(frozen=True)
class RepositoryStateView:
    mission_id: str
    repository: str
    branch: str
    baseline_sha: str
    baseline_tree_sha: str
    branch_head_sha: str
    branch_tree_sha: str
    observed_at: str
    provenance_ref: str
    evidence_digest: str


class RepositoryStateProvider(Protocol):
    def list_repository_states(self) -> tuple[RepositoryStateView, ...]: ...


class RepositoryStateStatusAdapter:
    def __init__(self, source_identity: StatusSourceIdentity, provider: RepositoryStateProvider, clock: Callable[[], datetime]) -> None:
        if source_identity.source_kind != "REPOSITORY":
            raise FleetStatusAdapterError("repository adapter requires REPOSITORY identity")
        self._identity = source_identity.validate()
        self._provider = provider
        self._clock = clock

    @property
    def source_identity(self) -> StatusSourceIdentity:
        return self._identity

    def read(self) -> StatusSourceRead:
        views = self._provider.list_repository_states()
        latest = _now(self._clock)
        observations = tuple(StatusSourceObservation(
            _observation_id(self._identity.source_id, item.mission_id, "REPOSITORY", item.evidence_digest, item.branch),
            item.mission_id, None, None, None, item.repository, item.baseline_sha, "REPOSITORY", "OBSERVED",
            _items({
                "baseline_sha": item.baseline_sha,
                "baseline_tree_sha": item.baseline_tree_sha,
                "repository": item.repository,
                "branch": item.branch,
                "branch_head_sha": item.branch_head_sha,
                "branch_tree_sha": item.branch_tree_sha,
                "source_record_observed_at": item.observed_at,
            }),
            item.provenance_ref, item.evidence_digest, "ANCHORED",
        ).validate() for item in views)
        return StatusSourceRead(self._identity, latest, observations).validate()


@dataclass(frozen=True)
class CIStatusView:
    mission_id: str
    repository: str
    head_sha: str
    workflow: str
    run_id: str
    state: str
    observed_at: str
    provenance_ref: str
    evidence_digest: str


class CIStatusProvider(Protocol):
    def list_ci_status(self) -> tuple[CIStatusView, ...]: ...


class CIStatusAdapter:
    def __init__(self, source_identity: StatusSourceIdentity, provider: CIStatusProvider, clock: Callable[[], datetime]) -> None:
        if source_identity.source_kind != "CI":
            raise FleetStatusAdapterError("CI adapter requires CI identity")
        self._identity = source_identity.validate()
        self._provider = provider
        self._clock = clock

    @property
    def source_identity(self) -> StatusSourceIdentity:
        return self._identity

    def read(self) -> StatusSourceRead:
        views = self._provider.list_ci_status()
        latest = _now(self._clock)
        observations = tuple(StatusSourceObservation(
            _observation_id(self._identity.source_id, item.mission_id, "CI", item.evidence_digest, item.run_id),
            item.mission_id, None, None, None, item.repository, item.head_sha, "CI", item.state,
            _items({"head_sha": item.head_sha, "run_id": item.run_id, "workflow": item.workflow, "source_record_observed_at": item.observed_at}),
            item.provenance_ref, item.evidence_digest, "ANCHORED",
        ).validate() for item in views)
        return StatusSourceRead(self._identity, latest, observations).validate()


@dataclass(frozen=True)
class HeartbeatStatusView:
    mission_id: str
    runtime_id: str
    sequence: int
    deadline_seconds: int
    observed_at: str
    provenance_ref: str
    evidence_digest: str


class HeartbeatStatusProvider(Protocol):
    def list_heartbeat_status(self) -> tuple[HeartbeatStatusView, ...]: ...


class HeartbeatStatusAdapter:
    def __init__(self, source_identity: StatusSourceIdentity, provider: HeartbeatStatusProvider, clock: Callable[[], datetime]) -> None:
        if source_identity.source_kind != "HEARTBEAT":
            raise FleetStatusAdapterError("heartbeat adapter requires HEARTBEAT identity")
        self._identity = source_identity.validate()
        self._provider = provider
        self._clock = clock

    @property
    def source_identity(self) -> StatusSourceIdentity:
        return self._identity

    def read(self) -> StatusSourceRead:
        views = self._provider.list_heartbeat_status()
        latest = _now(self._clock)
        observations = tuple(StatusSourceObservation(
            _observation_id(self._identity.source_id, item.mission_id, "HEARTBEAT", item.evidence_digest, item.runtime_id),
            item.mission_id, None, None, item.runtime_id, None, None, "HEARTBEAT", "OBSERVED",
            _items({"deadline_seconds": item.deadline_seconds, "heartbeat_observed_at": item.observed_at, "runtime_id": item.runtime_id, "sequence": item.sequence}),
            item.provenance_ref, item.evidence_digest, "ANCHORED",
        ).validate() for item in views)
        return StatusSourceRead(self._identity, latest, observations).validate()


@dataclass(frozen=True)
class SimpleStatusView:
    mission_id: str
    state: str
    observed_at: str
    provenance_ref: str
    evidence_digest: str
    value_items: tuple[tuple[str, str], ...] = ()


class SimpleStatusProvider(Protocol):
    def list_status(self) -> tuple[SimpleStatusView, ...]: ...


class _SimpleAdapter:
    KIND = ""
    DIMENSION = ""

    def __init__(self, source_identity: StatusSourceIdentity, provider: SimpleStatusProvider, clock: Callable[[], datetime]) -> None:
        if source_identity.source_kind != self.KIND:
            raise FleetStatusAdapterError(f"{self.DIMENSION} adapter requires {self.KIND} identity")
        self._identity = source_identity.validate()
        self._provider = provider
        self._clock = clock

    @property
    def source_identity(self) -> StatusSourceIdentity:
        return self._identity

    def read(self) -> StatusSourceRead:
        views = self._provider.list_status()
        latest = _now(self._clock)
        observations = tuple(StatusSourceObservation(
            _observation_id(self._identity.source_id, item.mission_id, self.DIMENSION, item.evidence_digest),
            item.mission_id, None, None, None, None, None, self.DIMENSION, item.state,
            item.value_items, item.provenance_ref, item.evidence_digest, "ANCHORED",
        ).validate() for item in views)
        return StatusSourceRead(self._identity, latest, observations).validate()


class LeaseStatusAdapter(_SimpleAdapter):
    KIND = "LEASE_STATE"
    DIMENSION = "LEASE"


class SandboxStatusAdapter(_SimpleAdapter):
    KIND = "SANDBOX"
    DIMENSION = "SANDBOX"


class ReconciliationStatusAdapter(_SimpleAdapter):
    KIND = "RECONCILIATION"
    DIMENSION = "RECONCILIATION"


class ReceiptStatusAdapter(_SimpleAdapter):
    KIND = "RECEIPT"
    DIMENSION = "RECEIPT"
