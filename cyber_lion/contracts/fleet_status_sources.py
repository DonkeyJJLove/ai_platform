"""Immutable contracts for FCSR R2 status-source observations.

Source observations are descriptive evidence only. They cannot grant authority,
acquire or release leases, dispatch work, execute effects, or promote mission state.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
import re
from typing import Any, Mapping, Tuple

_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_REPO = re.compile(r"^[^/\s]+/[^/\s]+$")

SOURCE_KINDS = frozenset({
    "FLEET_CONTROL",
    "RUNTIME_ATTESTATION",
    "RUNTIME_AUTHORITY",
    "AUTHORITY_STATE",
    "LEASE_STATE",
    "SANDBOX",
    "VERIFICATION",
    "EFFECT",
    "RECONCILIATION",
    "RECEIPT",
    "REPOSITORY",
    "CI",
    "HEARTBEAT",
})

DIMENSIONS = frozenset({
    "IDENTITY",
    "MISSION",
    "RUNTIME",
    "HEARTBEAT",
    "AUTHORITY",
    "LEASE",
    "SANDBOX",
    "VERIFICATION",
    "EFFECT",
    "RECONCILIATION",
    "RECEIPT",
    "REPOSITORY",
    "CI",
})

SOURCE_EPISTEMIC_CLASSES = frozenset({"OBSERVED", "ANCHORED"})
DECISION_TYPES = frozenset({"FACT", "CONFLICT", "MISSING"})


class FleetStatusSourceContractError(ValueError):
    """Raised when status-source evidence is malformed or ambiguous."""


def _text(value: Any, name: str, *, optional: bool = False, limit: int = 4096) -> str | None:
    if optional and value is None:
        return None
    if not isinstance(value, str) or not value.strip() or len(value) > limit or "\x00" in value:
        raise FleetStatusSourceContractError(f"{name} is invalid")
    return value


def _sha40(value: Any, name: str, *, optional: bool = False) -> str | None:
    if optional and value is None:
        return None
    value = _text(value, name, limit=40)
    assert isinstance(value, str)
    if not _SHA40.fullmatch(value):
        raise FleetStatusSourceContractError(f"{name} must be a full lowercase git SHA")
    return value


def _sha256(value: Any, name: str) -> str:
    value = _text(value, name, limit=64)
    assert isinstance(value, str)
    if not _SHA256.fullmatch(value):
        raise FleetStatusSourceContractError(f"{name} must be sha256 hex")
    return value


def _utc(value: str, name: str) -> datetime:
    _text(value, name)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, ValueError) as exc:
        raise FleetStatusSourceContractError(f"{name} is invalid") from exc
    if parsed.tzinfo is None:
        raise FleetStatusSourceContractError(f"{name} must be timezone-aware")
    return parsed.astimezone(timezone.utc)


def _items(value: Any, name: str) -> Tuple[Tuple[str, str], ...]:
    if type(value) is not tuple:
        raise FleetStatusSourceContractError(f"{name} must be a tuple")
    keys: list[str] = []
    previous: str | None = None
    for item in value:
        if type(item) is not tuple or len(item) != 2:
            raise FleetStatusSourceContractError(f"{name} entries must be key/value tuples")
        key, raw = item
        _text(key, f"{name} key", limit=128)
        _text(raw, f"{name} value", limit=8192)
        if previous is not None and key <= previous:
            raise FleetStatusSourceContractError(f"{name} must be strictly key-sorted")
        previous = key
        keys.append(key)
    if len(keys) != len(set(keys)):
        raise FleetStatusSourceContractError(f"{name} keys must be unique")
    return value


def canonical_json(value: Mapping[str, Any]) -> bytes:
    return json.dumps(dict(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


@dataclass(frozen=True)
class StatusSourceIdentity:
    source_id: str
    source_kind: str
    source_instance_id: str
    source_implementation_digest: str
    trust_anchor_id: str

    def validate(self) -> "StatusSourceIdentity":
        for name in ("source_id", "source_instance_id", "trust_anchor_id"):
            _text(getattr(self, name), name)
        if self.source_kind not in SOURCE_KINDS:
            raise FleetStatusSourceContractError("source_kind is invalid")
        _sha256(self.source_implementation_digest, "source_implementation_digest")
        return self

    def canonical_dict(self) -> dict[str, Any]:
        self.validate()
        return asdict(self)

    def digest(self) -> str:
        return sha256(canonical_json(self.canonical_dict())).hexdigest()


@dataclass(frozen=True)
class StatusSourcePin:
    source_id: str
    source_kind: str
    source_instance_id: str
    source_implementation_digest: str
    trust_anchor_id: str
    identity_digest: str

    def validate(self) -> "StatusSourcePin":
        identity = StatusSourceIdentity(
            self.source_id,
            self.source_kind,
            self.source_instance_id,
            self.source_implementation_digest,
            self.trust_anchor_id,
        ).validate()
        _sha256(self.identity_digest, "identity_digest")
        if self.identity_digest != identity.digest():
            raise FleetStatusSourceContractError("source identity pin digest mismatch")
        return self

    def validate_identity(self, identity: StatusSourceIdentity) -> StatusSourceIdentity:
        self.validate()
        identity.validate()
        expected = (
            self.source_id,
            self.source_kind,
            self.source_instance_id,
            self.source_implementation_digest,
            self.trust_anchor_id,
            self.identity_digest,
        )
        actual = (
            identity.source_id,
            identity.source_kind,
            identity.source_instance_id,
            identity.source_implementation_digest,
            identity.trust_anchor_id,
            identity.digest(),
        )
        if actual != expected:
            raise FleetStatusSourceContractError("status source identity substitution denied")
        return identity


@dataclass(frozen=True)
class StatusSourceObservation:
    observation_id: str
    mission_id: str | None
    drone_id: str | None
    executor_id: str | None
    runtime_id: str | None
    repository: str | None
    baseline_sha: str | None
    dimension: str
    state: str
    value_items: Tuple[Tuple[str, str], ...]
    provenance_ref: str
    evidence_digest: str
    epistemic_class: str

    def validate(self) -> "StatusSourceObservation":
        _text(self.observation_id, "observation_id")
        for name in ("mission_id", "drone_id", "executor_id", "runtime_id"):
            _text(getattr(self, name), name, optional=True)
        if self.repository is not None:
            _text(self.repository, "repository")
            if not _REPO.fullmatch(self.repository):
                raise FleetStatusSourceContractError("repository must use owner/name form")
        _sha40(self.baseline_sha, "baseline_sha", optional=True)
        if self.dimension not in DIMENSIONS:
            raise FleetStatusSourceContractError("dimension is invalid")
        _text(self.state, "state", limit=128)
        _items(self.value_items, "value_items")
        _text(self.provenance_ref, "provenance_ref")
        _sha256(self.evidence_digest, "evidence_digest")
        if self.epistemic_class not in SOURCE_EPISTEMIC_CLASSES:
            raise FleetStatusSourceContractError("source epistemic_class must be OBSERVED or ANCHORED")
        if self.dimension not in {"REPOSITORY", "CI"} and self.mission_id is None:
            raise FleetStatusSourceContractError("mission-bound dimension requires mission_id")
        return self

    def value_dict(self) -> dict[str, str]:
        self.validate()
        return dict(self.value_items)

    def canonical_dict(self) -> dict[str, Any]:
        self.validate()
        value = asdict(self)
        value["value_items"] = [list(item) for item in self.value_items]
        return value

    def digest(self) -> str:
        return sha256(canonical_json(self.canonical_dict())).hexdigest()


@dataclass(frozen=True)
class StatusSourceRead:
    source_identity: StatusSourceIdentity
    source_observed_at: str
    observations: Tuple[StatusSourceObservation, ...]

    def validate(self) -> "StatusSourceRead":
        self.source_identity.validate()
        _utc(self.source_observed_at, "source_observed_at")
        if type(self.observations) is not tuple:
            raise FleetStatusSourceContractError("observations must be a tuple")
        ids: list[str] = []
        for observation in self.observations:
            if type(observation) is not StatusSourceObservation:
                raise FleetStatusSourceContractError("invalid source observation type")
            observation.validate()
            ids.append(observation.observation_id)
        if len(ids) != len(set(ids)):
            raise FleetStatusSourceContractError("duplicate observation_id in source read")
        return self

    def digest(self) -> str:
        self.validate()
        payload = {
            "source_identity": self.source_identity.canonical_dict(),
            "source_observed_at": self.source_observed_at,
            "observation_digests": [item.digest() for item in self.observations],
        }
        return sha256(canonical_json(payload)).hexdigest()


@dataclass(frozen=True)
class StatusSourceBatch:
    source_identity: StatusSourceIdentity
    source_sequence: int
    source_observed_at: str
    read_digest: str
    batch_digest: str
    source_chain_digest: str
    previous_source_chain_digest: str
    observations: Tuple[StatusSourceObservation, ...]

    def validate(self) -> "StatusSourceBatch":
        self.source_identity.validate()
        if isinstance(self.source_sequence, bool) or not isinstance(self.source_sequence, int) or self.source_sequence < 1:
            raise FleetStatusSourceContractError("source_sequence must be positive")
        _utc(self.source_observed_at, "source_observed_at")
        for name in ("read_digest", "batch_digest", "source_chain_digest", "previous_source_chain_digest"):
            _sha256(getattr(self, name), name)
        read = StatusSourceRead(self.source_identity, self.source_observed_at, self.observations).validate()
        if read.digest() != self.read_digest:
            raise FleetStatusSourceContractError("source read digest mismatch")
        expected_batch = sha256(canonical_json({
            "source_identity_digest": self.source_identity.digest(),
            "source_sequence": self.source_sequence,
            "source_observed_at": self.source_observed_at,
            "read_digest": self.read_digest,
        })).hexdigest()
        if expected_batch != self.batch_digest:
            raise FleetStatusSourceContractError("source batch digest mismatch")
        expected_chain = sha256(
            (self.previous_source_chain_digest + self.batch_digest).encode("ascii")
        ).hexdigest()
        if expected_chain != self.source_chain_digest:
            raise FleetStatusSourceContractError("source chain digest mismatch")
        return self


@dataclass(frozen=True)
class SourceCheckpoint:
    source_id: str
    source_identity_digest: str
    source_sequence: int
    source_observed_at: str
    read_digest: str
    batch_digest: str
    source_chain_digest: str

    def validate(self) -> "SourceCheckpoint":
        _text(self.source_id, "source_id")
        for name in ("source_identity_digest", "read_digest", "batch_digest", "source_chain_digest"):
            _sha256(getattr(self, name), name)
        if isinstance(self.source_sequence, bool) or not isinstance(self.source_sequence, int) or self.source_sequence < 1:
            raise FleetStatusSourceContractError("checkpoint source_sequence invalid")
        _utc(self.source_observed_at, "source_observed_at")
        return self


@dataclass(frozen=True)
class ReconciledStatusFact:
    mission_id: str
    dimension: str
    state: str
    value_items: Tuple[Tuple[str, str], ...]
    source_ids: Tuple[str, ...]
    evidence_refs: Tuple[str, ...]
    epistemic_class: str

    def validate(self) -> "ReconciledStatusFact":
        _text(self.mission_id, "mission_id")
        if self.dimension not in DIMENSIONS:
            raise FleetStatusSourceContractError("dimension invalid")
        _text(self.state, "state")
        _items(self.value_items, "value_items")
        for name, values in (("source_ids", self.source_ids), ("evidence_refs", self.evidence_refs)):
            if type(values) is not tuple or not values or len(set(values)) != len(values):
                raise FleetStatusSourceContractError(f"{name} must be a unique non-empty tuple")
            for item in values:
                _text(item, name)
        if self.epistemic_class not in SOURCE_EPISTEMIC_CLASSES:
            raise FleetStatusSourceContractError("reconciled fact epistemic_class invalid")
        return self

    def value_dict(self) -> dict[str, str]:
        self.validate()
        return dict(self.value_items)

    def digest(self) -> str:
        self.validate()
        payload = asdict(self)
        payload["value_items"] = [list(item) for item in self.value_items]
        payload["source_ids"] = list(self.source_ids)
        payload["evidence_refs"] = list(self.evidence_refs)
        return sha256(canonical_json(payload)).hexdigest()


@dataclass(frozen=True)
class SourceConflict:
    conflict_id: str
    conflict_type: str
    mission_id: str | None
    drone_id: str | None
    dimension: str
    source_ids: Tuple[str, ...]
    observation_ids: Tuple[str, ...]
    evidence_refs: Tuple[str, ...]
    observed_at: str

    def validate(self) -> "SourceConflict":
        _text(self.conflict_id, "conflict_id")
        _text(self.conflict_type, "conflict_type")
        _text(self.mission_id, "mission_id", optional=True)
        _text(self.drone_id, "drone_id", optional=True)
        if self.dimension not in DIMENSIONS:
            raise FleetStatusSourceContractError("conflict dimension invalid")
        for name, values in (
            ("source_ids", self.source_ids),
            ("observation_ids", self.observation_ids),
            ("evidence_refs", self.evidence_refs),
        ):
            if type(values) is not tuple or len(set(values)) != len(values):
                raise FleetStatusSourceContractError(f"{name} must be a unique tuple")
            for item in values:
                _text(item, name)
        if not self.source_ids:
            raise FleetStatusSourceContractError("conflict requires at least one source_id")
        _utc(self.observed_at, "observed_at")
        return self

    def digest(self) -> str:
        self.validate()
        payload = asdict(self)
        for name in ("source_ids", "observation_ids", "evidence_refs"):
            payload[name] = list(payload[name])
        return sha256(canonical_json(payload)).hexdigest()


@dataclass(frozen=True)
class MissingStatusSource:
    """Reconciler-owned statement that a required dimension has no current owner evidence."""

    mission_id: str
    drone_id: str | None
    dimension: str
    expected_source_kinds: Tuple[str, ...]
    observed_at: str

    def validate(self) -> "MissingStatusSource":
        _text(self.mission_id, "mission_id")
        _text(self.drone_id, "drone_id", optional=True)
        if self.dimension not in DIMENSIONS:
            raise FleetStatusSourceContractError("missing-source dimension invalid")
        if type(self.expected_source_kinds) is not tuple or not self.expected_source_kinds:
            raise FleetStatusSourceContractError("missing source requires expected_source_kinds")
        if len(set(self.expected_source_kinds)) != len(self.expected_source_kinds):
            raise FleetStatusSourceContractError("expected_source_kinds must be unique")
        for source_kind in self.expected_source_kinds:
            if source_kind not in SOURCE_KINDS:
                raise FleetStatusSourceContractError("expected source kind invalid")
        _utc(self.observed_at, "observed_at")
        return self

    def digest(self) -> str:
        self.validate()
        payload = asdict(self)
        payload["expected_source_kinds"] = list(self.expected_source_kinds)
        return sha256(canonical_json(payload)).hexdigest()
