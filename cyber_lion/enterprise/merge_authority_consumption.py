"""Capability-separated durable merge-authority consumption contracts.

This module defines canonical keys and read/write capability interfaces only. It does
not implement a repository-local backend, persist authority state, or grant merge
permission. Observation callers receive only the read capability.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
import re

_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_DIGEST_RE = re.compile(r"^[0-9a-f]{64}$")
_ALLOWED_MERGE_METHODS = frozenset({"merge", "squash", "rebase"})


class MergeAuthorityConsumptionError(ValueError):
    """Raised when a durable consumption contract is malformed or unavailable."""


def _text(value: object, *, field_name: str, limit: int = 512) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > limit or "\x00" in value:
        raise MergeAuthorityConsumptionError(f"{field_name} is invalid")
    return value


def _sha(value: object, *, field_name: str) -> str:
    value = _text(value, field_name=field_name, limit=40)
    if not _SHA_RE.fullmatch(value):
        raise MergeAuthorityConsumptionError(f"{field_name} must be a full lowercase git SHA")
    return value


def _digest(value: object, *, field_name: str) -> str:
    value = _text(value, field_name=field_name, limit=64)
    if not _DIGEST_RE.fullmatch(value):
        raise MergeAuthorityConsumptionError(f"{field_name} must be canonical sha256 hex")
    return value


class MergeAuthorityConsumptionState(str, Enum):
    AVAILABLE = "AVAILABLE"
    RESERVED = "RESERVED"
    CONSUMED = "CONSUMED"
    ABORTED = "ABORTED"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class MergeAuthorityConsumptionKey:
    repository: str
    pr_number: int
    base_sha: str
    head_sha: str
    grant_id: str
    grant_digest: str
    lineage_digest: str
    epoch: int
    merge_method: str

    def validate(self) -> "MergeAuthorityConsumptionKey":
        if type(self) is not MergeAuthorityConsumptionKey:
            raise MergeAuthorityConsumptionError("consumption key must be exact MergeAuthorityConsumptionKey")
        _text(self.repository, field_name="repository")
        if not isinstance(self.pr_number, int) or isinstance(self.pr_number, bool) or self.pr_number <= 0:
            raise MergeAuthorityConsumptionError("pr_number must be a positive integer")
        _sha(self.base_sha, field_name="base_sha")
        _sha(self.head_sha, field_name="head_sha")
        _text(self.grant_id, field_name="grant_id")
        _digest(self.grant_digest, field_name="grant_digest")
        _digest(self.lineage_digest, field_name="lineage_digest")
        if not isinstance(self.epoch, int) or isinstance(self.epoch, bool) or self.epoch < 0:
            raise MergeAuthorityConsumptionError("epoch must be a non-negative integer")
        if self.merge_method not in _ALLOWED_MERGE_METHODS:
            raise MergeAuthorityConsumptionError("merge_method is unsupported")
        return self

    def binding(self) -> tuple[object, ...]:
        self.validate()
        return (
            self.repository,
            self.pr_number,
            self.base_sha,
            self.head_sha,
            self.grant_id,
            self.grant_digest,
            self.lineage_digest,
            self.epoch,
            self.merge_method,
        )


@dataclass(frozen=True)
class MergeAuthorityConsumptionObservation:
    key: MergeAuthorityConsumptionKey
    state: MergeAuthorityConsumptionState
    state_version: str
    provenance_id: str

    def validate(self) -> "MergeAuthorityConsumptionObservation":
        if type(self) is not MergeAuthorityConsumptionObservation:
            raise MergeAuthorityConsumptionError("consumption observation has invalid type")
        if type(self.key) is not MergeAuthorityConsumptionKey:
            raise MergeAuthorityConsumptionError("consumption observation key has invalid type")
        self.key.validate()
        if type(self.state) is not MergeAuthorityConsumptionState:
            raise MergeAuthorityConsumptionError("consumption state has invalid type")
        _text(self.state_version, field_name="state_version", limit=128)
        _text(self.provenance_id, field_name="provenance_id", limit=512)
        return self


class MergeAuthorityConsumptionReadCapability(ABC):
    """Read-only capability; intentionally exposes no reserve/consume operation."""

    @abstractmethod
    def observe_consumption_exact(
        self, key: MergeAuthorityConsumptionKey
    ) -> MergeAuthorityConsumptionObservation:
        raise NotImplementedError


class MergeAuthorityConsumptionWriteCapability(ABC):
    """Separate write capability for a future merge execution boundary."""

    @abstractmethod
    def consume_exact(
        self, key: MergeAuthorityConsumptionKey
    ) -> MergeAuthorityConsumptionObservation:
        raise NotImplementedError


class CallbackConsumptionReadCapability(MergeAuthorityConsumptionReadCapability):
    """Capability-reduced adapter around one trusted runtime read callback."""

    __slots__ = ("_callback",)

    def __init__(self, callback):
        if not callable(callback):
            raise MergeAuthorityConsumptionError("consumption read provider is not callable")
        self._callback = callback

    def observe_consumption_exact(
        self, key: MergeAuthorityConsumptionKey
    ) -> MergeAuthorityConsumptionObservation:
        key.validate()
        try:
            raw = self._callback(
                repository=key.repository,
                pr_number=key.pr_number,
                base_sha=key.base_sha,
                head_sha=key.head_sha,
                grant_id=key.grant_id,
                grant_digest=key.grant_digest,
                lineage_digest=key.lineage_digest,
                epoch=key.epoch,
                merge_method=key.merge_method,
            )
        except Exception as exc:
            raise MergeAuthorityConsumptionError("consumption read provider unavailable") from exc
        if not isinstance(raw, dict) or set(raw) != {"state", "state_version", "provenance_id"}:
            raise MergeAuthorityConsumptionError("consumption provider response is not canonical")
        try:
            state = MergeAuthorityConsumptionState(raw["state"])
        except Exception as exc:
            raise MergeAuthorityConsumptionError("consumption provider state is invalid") from exc
        return MergeAuthorityConsumptionObservation(
            key=key,
            state=state,
            state_version=raw["state_version"],
            provenance_id=raw["provenance_id"],
        ).validate()
