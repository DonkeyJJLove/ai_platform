"""Immutable contracts for the LION Fleet Canonical Status Registry P0 R1R.

Status evidence is descriptive only. Nothing in this module grants authority,
acquires a lease, dispatches work, executes an effect, or promotes fleet scale.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import re
from typing import Any, Mapping, Tuple

_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_REPO = re.compile(r"^[^/\s]+/[^/\s]+$")

MISSION_PHASES = frozenset({
    "BOOTSTRAP", "PLAN", "AUTHORIZE", "IMPLEMENT", "VERIFY", "INTEGRATE",
    "OBSERVE", "RECONCILE", "CLOSE", "IDLE", "UNKNOWN",
})
MISSION_STATUSES = frozenset({
    "STARTING", "RUNNING", "WAITING", "BLOCKED", "DEGRADED", "FAILED",
    "DONE", "TERMINATED", "UNKNOWN", "UNREACHABLE",
})
CLOSURE_STATES = frozenset({"OPEN", "READY_TO_CLOSE", "CLOSED", "UNKNOWN"})
HEARTBEAT_STATES = frozenset({
    "NOT_EXPECTED", "WAITING_FIRST_HEARTBEAT", "HEALTHY", "STALE", "MISSING", "UNKNOWN",
})
LEASE_STATES = frozenset({"NONE", "ACTIVE", "STALE_HELD", "RELEASED", "UNKNOWN"})
AUTHORITY_STATES = frozenset({
    "NONE", "ACTIVE", "REVOKED", "EXPIRED", "UNUSABLE_STALE_OBSERVABILITY", "UNKNOWN",
})
SANDBOX_STATES = frozenset({"NONE", "STARTING", "RUNNING", "DEGRADED", "DEAD", "CLEANED", "UNKNOWN"})
VERIFICATION_STATES = frozenset({"PENDING", "PASS", "FAIL", "UNKNOWN"})
EFFECT_STATES = frozenset({
    "NONE", "PREPARED", "ATTEMPTED", "APPLIED", "FAILED_NO_EFFECT", "RECONCILE_REQUIRED", "UNKNOWN",
})
RECONCILIATION_STATES = frozenset({"NOT_REQUIRED", "PENDING", "RESOLVED", "FAILED", "UNKNOWN"})
DEPENDENCY_STATES = frozenset({"READY", "WAITING", "BLOCKED", "UNKNOWN"})
EVIDENCE_STATES = frozenset({"COMPLETE", "PARTIAL", "MISSING", "CONFLICT", "UNKNOWN"})
EPISTEMIC_CLASSES = frozenset({"OBSERVED", "ANCHORED", "INFERRED", "SIMULATED", "UNKNOWN"})
PROJECTION_KINDS = frozenset({"authority", "sandbox", "effect", "reconciliation"})
SCOPE_CLASS = "SINGLE_RUNTIME_DURABLE_FLEET_STATUS_ONLY"


class FleetStatusContractError(ValueError):
    """Raised when fleet-status evidence is malformed or ambiguous."""


def _text(value: Any, name: str, *, limit: int = 4096, optional: bool = False) -> str | None:
    if optional and value is None:
        return None
    if not isinstance(value, str) or not value.strip() or len(value) > limit or "\x00" in value:
        raise FleetStatusContractError(f"{name} is invalid")
    return value


def _sha40(value: Any, name: str, *, optional: bool = False) -> str | None:
    if optional and value is None:
        return None
    value = _text(value, name, limit=40)
    assert isinstance(value, str)
    if not _SHA40.fullmatch(value):
        raise FleetStatusContractError(f"{name} must be a full lowercase git SHA")
    return value


def _sha256(value: Any, name: str, *, optional: bool = False) -> str | None:
    if optional and value is None:
        return None
    value = _text(value, name, limit=64)
    assert isinstance(value, str)
    if not _SHA256.fullmatch(value):
        raise FleetStatusContractError(f"{name} must be sha256 hex")
    return value


def _enum(value: Any, name: str, allowed: frozenset[str]) -> str:
    if not isinstance(value, str) or value not in allowed:
        raise FleetStatusContractError(f"{name} is invalid")
    return value


def _string_tuple(value: Any, name: str, *, unique: bool = True) -> Tuple[str, ...]:
    if type(value) is not tuple:
        raise FleetStatusContractError(f"{name} must be a tuple")
    for item in value:
        _text(item, name)
    if unique and len(set(value)) != len(value):
        raise FleetStatusContractError(f"{name} must be unique")
    return value


def canonical_json(value: Mapping[str, Any]) -> bytes:
    return json.dumps(dict(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


@dataclass(frozen=True)
class FleetStatusIdentity:
    drone_id: str
    executor_id: str
    mission_id: str
    parent_mission_id: str
    repository: str
    baseline_sha: str
    baseline_tree_sha: str
    branch: str
    read_scope: Tuple[str, ...]
    write_scope: Tuple[str, ...]
    sandbox_id: str

    def validate(self) -> "FleetStatusIdentity":
        for name in ("drone_id", "executor_id", "mission_id", "parent_mission_id", "branch", "sandbox_id"):
            _text(getattr(self, name), name)
        if not _REPO.fullmatch(self.repository):
            raise FleetStatusContractError("repository must use owner/name form")
        _sha40(self.baseline_sha, "baseline_sha")
        _sha40(self.baseline_tree_sha, "baseline_tree_sha")
        _string_tuple(self.read_scope, "read_scope")
        _string_tuple(self.write_scope, "write_scope")
        return self

    def digest(self) -> str:
        self.validate()
        value = asdict(self)
        value["read_scope"] = list(self.read_scope)
        value["write_scope"] = list(self.write_scope)
        return sha256(canonical_json(value)).hexdigest()


@dataclass(frozen=True)
class VerificationTrustPins:
    """Composition-root pins for the one trusted verification source."""

    verifier_id: str
    verifier_identity_digest: str
    verifier_implementation_digest: str
    trust_anchor_id: str
    trust_anchor_digest: str

    def validate(self) -> "VerificationTrustPins":
        _text(self.verifier_id, "verifier_id")
        _sha256(self.verifier_identity_digest, "verifier_identity_digest")
        _sha256(self.verifier_implementation_digest, "verifier_implementation_digest")
        _text(self.trust_anchor_id, "trust_anchor_id")
        _sha256(self.trust_anchor_digest, "trust_anchor_digest")
        return self


@dataclass(frozen=True)
class TrustedVerificationEvidence:
    """Externally verified evidence. Store callers cannot provide this object directly."""

    verification_id: str
    mission_id: str
    drone_id: str
    executor_id: str
    verifier_id: str
    verifier_identity_digest: str
    verifier_implementation_digest: str
    trust_anchor_id: str
    trust_anchor_digest: str
    verification_state: str
    evidence_digest: str
    source_provenance_ref: str
    epistemic_class: str
    observed_at: str

    def validate(self) -> "TrustedVerificationEvidence":
        for name in (
            "verification_id", "mission_id", "drone_id", "executor_id", "verifier_id",
            "trust_anchor_id", "source_provenance_ref", "observed_at",
        ):
            _text(getattr(self, name), name)
        for name in (
            "verifier_identity_digest", "verifier_implementation_digest",
            "trust_anchor_digest", "evidence_digest",
        ):
            _sha256(getattr(self, name), name)
        _enum(self.verification_state, "verification_state", VERIFICATION_STATES)
        _enum(self.epistemic_class, "epistemic_class", EPISTEMIC_CLASSES)
        if self.verifier_id in {self.drone_id, self.executor_id}:
            raise FleetStatusContractError("verifier must be independent of drone and executor")
        if self.verification_state == "PASS" and self.epistemic_class not in {"OBSERVED", "ANCHORED"}:
            raise FleetStatusContractError("verification PASS requires OBSERVED or ANCHORED evidence")
        return self

    def binding_digest(self) -> str:
        self.validate()
        return sha256(canonical_json(asdict(self))).hexdigest()


@dataclass(frozen=True)
class DroneStatusRecord:
    drone_id: str
    executor_id: str
    runtime_id: str | None
    mission_id: str
    parent_mission_id: str
    mission_phase: str
    mission_status: str
    closure_state: str
    repository: str
    baseline_sha: str
    baseline_tree_sha: str
    branch: str
    branch_head: str | None
    read_scope: Tuple[str, ...]
    write_scope: Tuple[str, ...]
    authority_state: str
    authority_ref: str | None
    authority_observed_at: str | None
    lease_state: str
    active_lease_refs: Tuple[str, ...]
    sandbox_id: str
    sandbox_state: str
    sandbox_evidence_ref: str | None
    heartbeat_state: str
    heartbeat_sequence: int
    heartbeat_deadline_seconds: int | None
    heartbeat_age_seconds: float | None
    last_heartbeat_at: str | None
    current_operation: str | None
    current_blocker: str | None
    dependency_state: str
    verification_state: str
    verifier_id: str | None
    verification_ref: str | None
    effect_state: str
    effect_id: str | None
    effect_ref: str | None
    reconciliation_state: str
    reconciliation_ref: str | None
    evidence_state: str
    epistemic_class: str
    evidence_refs: Tuple[str, ...]
    last_receipt_id: str | None
    receipt_chain_head_digest: str | None
    last_observed_at: str

    def validate(self) -> "DroneStatusRecord":
        for name in (
            "drone_id", "executor_id", "mission_id", "parent_mission_id",
            "repository", "branch", "sandbox_id", "last_observed_at",
        ):
            _text(getattr(self, name), name)
        if not _REPO.fullmatch(self.repository):
            raise FleetStatusContractError("repository must use owner/name form")
        _text(self.runtime_id, "runtime_id", optional=True)
        _sha40(self.baseline_sha, "baseline_sha")
        _sha40(self.baseline_tree_sha, "baseline_tree_sha")
        _sha40(self.branch_head, "branch_head", optional=True)
        _enum(self.mission_phase, "mission_phase", MISSION_PHASES)
        _enum(self.mission_status, "mission_status", MISSION_STATUSES)
        _enum(self.closure_state, "closure_state", CLOSURE_STATES)
        _enum(self.authority_state, "authority_state", AUTHORITY_STATES)
        _enum(self.lease_state, "lease_state", LEASE_STATES)
        _enum(self.sandbox_state, "sandbox_state", SANDBOX_STATES)
        _enum(self.heartbeat_state, "heartbeat_state", HEARTBEAT_STATES)
        _enum(self.dependency_state, "dependency_state", DEPENDENCY_STATES)
        _enum(self.verification_state, "verification_state", VERIFICATION_STATES)
        _enum(self.effect_state, "effect_state", EFFECT_STATES)
        _enum(self.reconciliation_state, "reconciliation_state", RECONCILIATION_STATES)
        _enum(self.evidence_state, "evidence_state", EVIDENCE_STATES)
        _enum(self.epistemic_class, "epistemic_class", EPISTEMIC_CLASSES)
        for name in ("read_scope", "write_scope", "active_lease_refs", "evidence_refs"):
            _string_tuple(getattr(self, name), name)
        if isinstance(self.heartbeat_sequence, bool) or not isinstance(self.heartbeat_sequence, int) or self.heartbeat_sequence < 0:
            raise FleetStatusContractError("heartbeat_sequence is invalid")
        if self.heartbeat_deadline_seconds is not None and (
            isinstance(self.heartbeat_deadline_seconds, bool)
            or not isinstance(self.heartbeat_deadline_seconds, int)
            or self.heartbeat_deadline_seconds <= 0
        ):
            raise FleetStatusContractError("heartbeat_deadline_seconds is invalid")
        if self.heartbeat_age_seconds is not None and (
            isinstance(self.heartbeat_age_seconds, bool)
            or not isinstance(self.heartbeat_age_seconds, (int, float))
            or self.heartbeat_age_seconds < 0
        ):
            raise FleetStatusContractError("heartbeat_age_seconds is invalid")
        for name in (
            "authority_ref", "authority_observed_at", "sandbox_evidence_ref", "last_heartbeat_at",
            "current_operation", "current_blocker", "verifier_id", "verification_ref", "effect_id",
            "effect_ref", "reconciliation_ref", "last_receipt_id",
        ):
            _text(getattr(self, name), name, optional=True)
        _sha256(self.receipt_chain_head_digest, "receipt_chain_head_digest", optional=True)
        if self.mission_status == "DONE" and self.verification_state != "PASS":
            raise FleetStatusContractError("DONE requires independent verification PASS")
        if self.closure_state == "CLOSED" and self.mission_status not in {"DONE", "FAILED", "TERMINATED"}:
            raise FleetStatusContractError("CLOSED requires terminal mission")
        return self

    def canonical_dict(self) -> dict[str, Any]:
        self.validate()
        value = asdict(self)
        for name in ("read_scope", "write_scope", "active_lease_refs", "evidence_refs"):
            value[name] = list(value[name])
        return value


@dataclass(frozen=True)
class FleetAggregate:
    total_known_drones: int
    reachable_drones: int
    unreachable_drones: int
    active_missions: int
    idle_drones: int
    running_drones: int
    waiting_drones: int
    blocked_drones: int
    degraded_drones: int
    failed_drones: int
    done_not_closed: int
    missions_in_verification: int
    missions_in_reconciliation: int
    active_authority_count: int
    active_write_lease_count: int
    unresolved_effect_count: int
    stale_heartbeat_count: int
    unknown_state_count: int

    def validate(self) -> "FleetAggregate":
        for name, value in asdict(self).items():
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise FleetStatusContractError(f"aggregate {name} is invalid")
        if self.reachable_drones + self.unreachable_drones > self.total_known_drones:
            raise FleetStatusContractError("reachability exceeds fleet population")
        return self


@dataclass(frozen=True)
class FleetAnomaly:
    anomaly_id: str
    anomaly_type: str
    severity: str
    mission_id: str | None
    drone_id: str | None
    evidence_refs: Tuple[str, ...]
    observed_at: str

    def validate(self) -> "FleetAnomaly":
        _text(self.anomaly_id, "anomaly_id")
        _text(self.anomaly_type, "anomaly_type")
        if self.severity not in {"INFO", "WARNING", "ERROR", "BLOCKING"}:
            raise FleetStatusContractError("severity is invalid")
        _text(self.mission_id, "mission_id", optional=True)
        _text(self.drone_id, "drone_id", optional=True)
        _string_tuple(self.evidence_refs, "evidence_refs")
        _text(self.observed_at, "observed_at")
        return self


@dataclass(frozen=True)
class FleetStatusSnapshot:
    schema_version: str
    snapshot_id: str
    snapshot_revision: int
    snapshot_digest: str
    observed_at: str
    registry_instance_id: str
    scope_class: str
    aggregate: FleetAggregate
    drone_records: Tuple[DroneStatusRecord, ...]
    anomalies: Tuple[FleetAnomaly, ...]

    def validate(self) -> "FleetStatusSnapshot":
        if self.schema_version != "1.0.0":
            raise FleetStatusContractError("unsupported snapshot schema_version")
        for name in ("snapshot_id", "observed_at", "registry_instance_id"):
            _text(getattr(self, name), name)
        if self.scope_class != SCOPE_CLASS:
            raise FleetStatusContractError("scope_class is invalid")
        if isinstance(self.snapshot_revision, bool) or not isinstance(self.snapshot_revision, int) or self.snapshot_revision < 0:
            raise FleetStatusContractError("snapshot_revision is invalid")
        _sha256(self.snapshot_digest, "snapshot_digest")
        self.aggregate.validate()
        if type(self.drone_records) is not tuple or type(self.anomalies) is not tuple:
            raise FleetStatusContractError("snapshot collections must be tuples")
        ids = []
        for record in self.drone_records:
            if not isinstance(record, DroneStatusRecord):
                raise FleetStatusContractError("invalid drone record")
            record.validate()
            ids.append(record.drone_id)
        for anomaly in self.anomalies:
            if not isinstance(anomaly, FleetAnomaly):
                raise FleetStatusContractError("invalid anomaly")
            anomaly.validate()
        if len(ids) != len(set(ids)):
            raise FleetStatusContractError("duplicate drone_id in snapshot")
        if self.aggregate.total_known_drones != len(self.drone_records):
            raise FleetStatusContractError("aggregate population mismatch")
        return self

    def payload_without_digest(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "snapshot_id": self.snapshot_id,
            "snapshot_revision": self.snapshot_revision,
            "observed_at": self.observed_at,
            "registry_instance_id": self.registry_instance_id,
            "scope_class": self.scope_class,
            "aggregate": asdict(self.aggregate),
            "drone_records": [r.canonical_dict() for r in self.drone_records],
            "anomalies": [
                {
                    **asdict(a),
                    "evidence_refs": list(a.evidence_refs),
                }
                for a in self.anomalies
            ],
        }

    def recompute_digest(self) -> str:
        return sha256(canonical_json(self.payload_without_digest())).hexdigest()

    def to_wire(self) -> dict[str, Any]:
        self.validate()
        if self.recompute_digest() != self.snapshot_digest:
            raise FleetStatusContractError("snapshot digest mismatch")
        return {**self.payload_without_digest(), "snapshot_digest": self.snapshot_digest}
