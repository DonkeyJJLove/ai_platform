"""Fail-closed fleet aggregate effect budget contracts.

Budget state can only restrict already-authenticated authority.  It never creates,
expands, delegates, or substitutes authority.  Reservations are exact-scope,
generation-bound, single-use coordination records for consequential effects.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import PurePosixPath
import re


class FleetEffectBudgetContractError(ValueError):
    pass


_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_BRANCH = re.compile(
    r"^(?!/)(?!.*//)(?!.*\.\.)(?!.*@\{)(?!.*[~^:?*\[\\])"
    r"(?!.*\.$)(?!.*\.lock(?:/|$))[A-Za-z0-9._/-]+$"
)
_SCHEMA = "1.0.0"
_ACTIVE = frozenset({"RESERVED"})
_TERMINAL = frozenset({"RELEASED", "FINALIZED", "EXPIRED"})


def _text(value: object, name: str, limit: int = 1024) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > limit or "\x00" in value:
        raise FleetEffectBudgetContractError(f"{name} is invalid")
    return value


def _digest(value: object, name: str) -> str:
    value = _text(value, name, 64)
    if not _DIGEST.fullmatch(value):
        raise FleetEffectBudgetContractError(f"{name} must be lowercase sha256")
    return value


def _positive(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise FleetEffectBudgetContractError(f"{name} must be a positive integer")
    return value


def _nonnegative(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise FleetEffectBudgetContractError(f"{name} must be a non-negative integer")
    return value


def _utc(value: str, name: str) -> datetime:
    _text(value, name)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise FleetEffectBudgetContractError(f"{name} is invalid") from exc
    if parsed.tzinfo is None:
        raise FleetEffectBudgetContractError(f"{name} must be timezone-aware")
    return parsed.astimezone(timezone.utc)


def _branch(value: str) -> str:
    value = _text(value, "branch", 255)
    if value.startswith("refs/") or not _BRANCH.fullmatch(value):
        raise FleetEffectBudgetContractError("branch is invalid")
    return value


def _paths(values: object) -> tuple[str, ...]:
    if type(values) is not tuple or not values or len(set(values)) != len(values):
        raise FleetEffectBudgetContractError("changed_paths must be a non-empty unique tuple")
    result: list[str] = []
    for raw in values:
        _text(raw, "changed_path")
        if "\\" in raw:
            raise FleetEffectBudgetContractError("changed_path must use POSIX separators")
        path = PurePosixPath(raw)
        if path.is_absolute() or ".." in path.parts or str(path) in {"", "."}:
            raise FleetEffectBudgetContractError("changed_path is unsafe")
        result.append(str(path))
    return tuple(result)


def _canon(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


@dataclass(frozen=True)
class FleetEffectEnvelope:
    envelope_id: str
    fleet_id: str
    generation: int
    policy_digest: str
    max_concurrent_writers: int
    max_active_repository_effects: int
    max_active_branch_effects: int
    max_active_path_effects: int
    valid_from: str
    expires_at: str
    schema_version: str = _SCHEMA

    def validate(self) -> "FleetEffectEnvelope":
        if self.schema_version != _SCHEMA:
            raise FleetEffectBudgetContractError("unsupported fleet effect envelope schema")
        _text(self.envelope_id, "envelope_id")
        _text(self.fleet_id, "fleet_id")
        _positive(self.generation, "generation")
        _digest(self.policy_digest, "policy_digest")
        _positive(self.max_concurrent_writers, "max_concurrent_writers")
        _positive(self.max_active_repository_effects, "max_active_repository_effects")
        _positive(self.max_active_branch_effects, "max_active_branch_effects")
        _positive(self.max_active_path_effects, "max_active_path_effects")
        start = _utc(self.valid_from, "valid_from")
        end = _utc(self.expires_at, "expires_at")
        if end <= start:
            raise FleetEffectBudgetContractError("envelope expiry must follow activation")
        return self

    def digest(self) -> str:
        self.validate()
        return sha256(b"LION/FLEET-EFFECT-ENVELOPE/1\0" + _canon(asdict(self))).hexdigest()


@dataclass(frozen=True)
class FleetEffectReservationRequest:
    reservation_id: str
    effect_id: str
    mission_id: str
    executor_id: str
    runtime_id: str
    repository: str
    branch: str
    changed_paths: tuple[str, ...]
    authority_effect_key: str
    authority_epoch: int
    envelope_generation: int
    requested_at: str
    expires_at: str
    schema_version: str = _SCHEMA

    def validate(self) -> "FleetEffectReservationRequest":
        if self.schema_version != _SCHEMA:
            raise FleetEffectBudgetContractError("unsupported reservation request schema")
        for name in ("reservation_id", "effect_id", "mission_id", "executor_id", "runtime_id", "repository"):
            _text(getattr(self, name), name)
        _branch(self.branch)
        _paths(self.changed_paths)
        _digest(self.authority_effect_key, "authority_effect_key")
        _nonnegative(self.authority_epoch, "authority_epoch")
        _positive(self.envelope_generation, "envelope_generation")
        requested = _utc(self.requested_at, "requested_at")
        expires = _utc(self.expires_at, "expires_at")
        if expires <= requested:
            raise FleetEffectBudgetContractError("reservation expiry must follow request time")
        return self

    def canonical_payload(self) -> bytes:
        self.validate()
        value = asdict(self)
        value["changed_paths"] = list(self.changed_paths)
        return _canon(value)

    def digest(self) -> str:
        return sha256(b"LION/FLEET-EFFECT-RESERVATION-REQUEST/1\0" + self.canonical_payload()).hexdigest()


@dataclass(frozen=True)
class FleetEffectReservation:
    reservation_id: str
    request_digest: str
    effect_id: str
    mission_id: str
    executor_id: str
    runtime_id: str
    repository: str
    branch: str
    changed_paths: tuple[str, ...]
    authority_effect_key: str
    authority_epoch: int
    envelope_id: str
    envelope_generation: int
    envelope_digest: str
    state: str
    reserved_at: str
    expires_at: str
    finalized_at: str | None = None
    schema_version: str = _SCHEMA

    def validate(self) -> "FleetEffectReservation":
        if self.schema_version != _SCHEMA:
            raise FleetEffectBudgetContractError("unsupported reservation schema")
        for name in ("reservation_id", "effect_id", "mission_id", "executor_id", "runtime_id", "repository", "envelope_id"):
            _text(getattr(self, name), name)
        for name in ("request_digest", "authority_effect_key", "envelope_digest"):
            _digest(getattr(self, name), name)
        _branch(self.branch)
        _paths(self.changed_paths)
        _nonnegative(self.authority_epoch, "authority_epoch")
        _positive(self.envelope_generation, "envelope_generation")
        reserved = _utc(self.reserved_at, "reserved_at")
        expires = _utc(self.expires_at, "expires_at")
        if expires <= reserved:
            raise FleetEffectBudgetContractError("reservation expiry must follow reservation time")
        if self.state not in _ACTIVE | _TERMINAL:
            raise FleetEffectBudgetContractError("reservation state is invalid")
        if self.state in _TERMINAL:
            if self.finalized_at is None:
                raise FleetEffectBudgetContractError("terminal reservation requires finalized_at")
            _utc(self.finalized_at, "finalized_at")
        elif self.finalized_at is not None:
            raise FleetEffectBudgetContractError("active reservation cannot be finalized")
        return self

    def digest(self) -> str:
        self.validate()
        value = asdict(self)
        value["changed_paths"] = list(self.changed_paths)
        return sha256(b"LION/FLEET-EFFECT-RESERVATION/1\0" + _canon(value)).hexdigest()


@dataclass(frozen=True)
class FleetEffectBudgetSnapshot:
    envelope_id: str
    envelope_generation: int
    envelope_digest: str
    active_writers: int
    active_repository_effects: tuple[tuple[str, int], ...]
    active_branch_effects: tuple[tuple[str, str, int], ...]
    active_path_effects: tuple[tuple[str, str, int], ...]
    active_reservation_ids: tuple[str, ...]
    observed_at: str
    schema_version: str = _SCHEMA

    def validate(self) -> "FleetEffectBudgetSnapshot":
        if self.schema_version != _SCHEMA:
            raise FleetEffectBudgetContractError("unsupported budget snapshot schema")
        _text(self.envelope_id, "envelope_id")
        _positive(self.envelope_generation, "envelope_generation")
        _digest(self.envelope_digest, "envelope_digest")
        _nonnegative(self.active_writers, "active_writers")
        _utc(self.observed_at, "observed_at")
        if type(self.active_reservation_ids) is not tuple or len(set(self.active_reservation_ids)) != len(self.active_reservation_ids):
            raise FleetEffectBudgetContractError("active reservation ids invalid")
        for item in self.active_reservation_ids:
            _text(item, "active_reservation_id")
        for row in self.active_repository_effects:
            if type(row) is not tuple or len(row) != 2:
                raise FleetEffectBudgetContractError("repository aggregate invalid")
            _text(row[0], "repository"); _nonnegative(row[1], "repository_count")
        for row in self.active_branch_effects:
            if type(row) is not tuple or len(row) != 3:
                raise FleetEffectBudgetContractError("branch aggregate invalid")
            _text(row[0], "repository"); _branch(row[1]); _nonnegative(row[2], "branch_count")
        for row in self.active_path_effects:
            if type(row) is not tuple or len(row) != 3:
                raise FleetEffectBudgetContractError("path aggregate invalid")
            _text(row[0], "repository"); _text(row[1], "path"); _nonnegative(row[2], "path_count")
        return self

    def digest(self) -> str:
        self.validate()
        value = asdict(self)
        value["active_repository_effects"] = [list(x) for x in self.active_repository_effects]
        value["active_branch_effects"] = [list(x) for x in self.active_branch_effects]
        value["active_path_effects"] = [list(x) for x in self.active_path_effects]
        value["active_reservation_ids"] = list(self.active_reservation_ids)
        return sha256(b"LION/FLEET-EFFECT-BUDGET-SNAPSHOT/1\0" + _canon(value)).hexdigest()
