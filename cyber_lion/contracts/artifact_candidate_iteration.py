"""Deterministic, non-authoritative artifact-first candidate observation contract.

Long-running work must not depend on an interactive response stream remaining
available. The stream is observability only. Durable artifact/process evidence
drives the next bounded action.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import re
from typing import Any

SCHEMA_ID = "lion.artifact-candidate-observation/v1"
POLICY_SCHEMA_ID = "lion.artifact-candidate-poll-policy/v1"
AUTHORITY_EFFECT = "NONE"

STATES = frozenset({
    "PLANNED", "RUNNING", "CANDIDATE_AVAILABLE", "VERIFYING",
    "VERIFIED", "REJECTED", "UNKNOWN", "SUPERSEDED",
})
STREAM_STATES = frozenset({"NOT_USED", "AVAILABLE", "LOST", "EXPIRED"})
WORKER_STATES = frozenset({"UNKNOWN", "RUNNING", "TERMINAL"})
ACTIONS = frozenset({
    "OBSERVE_LATER", "VERIFY_ARTIFACT", "COMPLETE", "NEXT_GENERATION",
    "RECONCILE", "HANDOFF", "NOOP_SUPERSEDED",
})
HEX64 = re.compile(r"^[0-9a-f]{64}$")
IDENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,255}$")


class ArtifactCandidateObservationError(ValueError):
    pass


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _digest(value: Any) -> str:
    return sha256(_canonical(value)).hexdigest()


def _ident(value: str, name: str) -> str:
    if not isinstance(value, str) or IDENT.fullmatch(value) is None:
        raise ArtifactCandidateObservationError(f"{name} invalid")
    return value


def _hex64(value: str | None, name: str, *, required: bool = False) -> str | None:
    if value is None:
        if required:
            raise ArtifactCandidateObservationError(f"{name} required")
        return None
    if not isinstance(value, str) or HEX64.fullmatch(value) is None:
        raise ArtifactCandidateObservationError(f"{name} invalid")
    return value


@dataclass(frozen=True)
class ArtifactPollPolicy:
    initial_seconds: int = 2
    max_seconds: int = 30
    multiplier: int = 2
    max_polls: int = 120
    max_generations: int = 4
    max_elapsed_seconds: int = 1800
    authority_effect: str = AUTHORITY_EFFECT

    def validate(self) -> "ArtifactPollPolicy":
        if self.authority_effect != AUTHORITY_EFFECT:
            raise ArtifactCandidateObservationError("poll policy cannot carry authority")
        for name in ("initial_seconds", "max_seconds", "multiplier", "max_polls", "max_generations", "max_elapsed_seconds"):
            value = getattr(self, name)
            if type(value) is not int or value < 1:
                raise ArtifactCandidateObservationError(f"{name} invalid")
        if self.initial_seconds > self.max_seconds:
            raise ArtifactCandidateObservationError("initial_seconds exceeds max_seconds")
        if self.multiplier > 16:
            raise ArtifactCandidateObservationError("multiplier too large")
        return self

    def interval_seconds(self, poll_index: int) -> int:
        self.validate()
        if type(poll_index) is not int or poll_index < 0:
            raise ArtifactCandidateObservationError("poll_index invalid")
        return min(self.initial_seconds * (self.multiplier ** poll_index), self.max_seconds)

    def as_dict(self) -> dict[str, Any]:
        self.validate()
        value = {
            "schema": POLICY_SCHEMA_ID,
            "initial_seconds": self.initial_seconds,
            "max_seconds": self.max_seconds,
            "multiplier": self.multiplier,
            "max_polls": self.max_polls,
            "max_generations": self.max_generations,
            "max_elapsed_seconds": self.max_elapsed_seconds,
            "authority_effect": self.authority_effect,
        }
        value["policy_digest"] = _digest(value)
        return value


@dataclass(frozen=True)
class ArtifactCandidateObservation:
    run_id: str
    mission_id: str
    task_id: str
    generation: int
    attempt: int
    state: str
    source_digest: str
    stream_state: str
    worker_state: str
    observed_at: str
    artifact_ref: str | None = None
    artifact_digest: str | None = None
    verifier_receipt_digest: str | None = None
    terminal_reason: str | None = None
    authority_effect: str = AUTHORITY_EFFECT

    def validate(self) -> "ArtifactCandidateObservation":
        for value, name in ((self.run_id, "run_id"), (self.mission_id, "mission_id"), (self.task_id, "task_id")):
            _ident(value, name)
        if type(self.generation) is not int or self.generation < 1:
            raise ArtifactCandidateObservationError("generation invalid")
        if type(self.attempt) is not int or self.attempt < 1:
            raise ArtifactCandidateObservationError("attempt invalid")
        if self.state not in STATES:
            raise ArtifactCandidateObservationError("state invalid")
        if self.stream_state not in STREAM_STATES:
            raise ArtifactCandidateObservationError("stream_state invalid")
        if self.worker_state not in WORKER_STATES:
            raise ArtifactCandidateObservationError("worker_state invalid")
        _hex64(self.source_digest, "source_digest", required=True)
        if not isinstance(self.observed_at, str) or not self.observed_at.strip():
            raise ArtifactCandidateObservationError("observed_at invalid")
        if self.authority_effect != AUTHORITY_EFFECT:
            raise ArtifactCandidateObservationError("observation cannot carry authority")
        if self.artifact_ref is not None:
            _ident(self.artifact_ref, "artifact_ref")
        _hex64(self.artifact_digest, "artifact_digest")
        _hex64(self.verifier_receipt_digest, "verifier_receipt_digest")
        if (self.artifact_ref is None) != (self.artifact_digest is None):
            raise ArtifactCandidateObservationError("artifact_ref and artifact_digest must appear together")
        if self.state in {"CANDIDATE_AVAILABLE", "VERIFYING", "VERIFIED", "REJECTED"} and self.artifact_digest is None:
            raise ArtifactCandidateObservationError("artifact evidence required")
        if self.state in {"VERIFIED", "REJECTED"} and self.verifier_receipt_digest is None:
            raise ArtifactCandidateObservationError("verifier receipt required for terminal candidate")
        if self.state in {"VERIFIED", "REJECTED", "SUPERSEDED"} and self.worker_state == "RUNNING":
            raise ArtifactCandidateObservationError("terminal candidate cannot have running worker")
        return self

    def as_dict(self) -> dict[str, Any]:
        self.validate()
        value = {
            "schema": SCHEMA_ID,
            "run_id": self.run_id,
            "mission_id": self.mission_id,
            "task_id": self.task_id,
            "generation": self.generation,
            "attempt": self.attempt,
            "state": self.state,
            "source_digest": self.source_digest,
            "stream_state": self.stream_state,
            "worker_state": self.worker_state,
            "observed_at": self.observed_at,
            "artifact_ref": self.artifact_ref,
            "artifact_digest": self.artifact_digest,
            "verifier_receipt_digest": self.verifier_receipt_digest,
            "terminal_reason": self.terminal_reason,
            "authority_effect": self.authority_effect,
        }
        value["observation_digest"] = _digest(value)
        return value


@dataclass(frozen=True)
class ArtifactCandidateDecision:
    action: str
    reason: str
    next_poll_seconds: int | None
    authority_effect: str = AUTHORITY_EFFECT

    def validate(self) -> "ArtifactCandidateDecision":
        if self.action not in ACTIONS:
            raise ArtifactCandidateObservationError("decision action invalid")
        if not isinstance(self.reason, str) or not self.reason.strip():
            raise ArtifactCandidateObservationError("decision reason invalid")
        if self.next_poll_seconds is not None and (type(self.next_poll_seconds) is not int or self.next_poll_seconds < 1):
            raise ArtifactCandidateObservationError("next_poll_seconds invalid")
        if self.authority_effect != AUTHORITY_EFFECT:
            raise ArtifactCandidateObservationError("decision cannot carry authority")
        return self


def decide_next(observation: ArtifactCandidateObservation, policy: ArtifactPollPolicy, *, poll_index: int, elapsed_seconds: int) -> ArtifactCandidateDecision:
    """Choose a next observation recommendation; stream state is never authority."""
    observation.validate()
    policy.validate()
    if type(poll_index) is not int or poll_index < 0:
        raise ArtifactCandidateObservationError("poll_index invalid")
    if type(elapsed_seconds) is not int or elapsed_seconds < 0:
        raise ArtifactCandidateObservationError("elapsed_seconds invalid")

    if observation.state == "VERIFIED":
        return ArtifactCandidateDecision("COMPLETE", "verified artifact and verifier receipt are durable", None).validate()
    if observation.state == "REJECTED":
        if observation.generation < policy.max_generations:
            return ArtifactCandidateDecision("NEXT_GENERATION", "terminal rejected candidate is preserved; bounded successor generation is permitted", None).validate()
        return ArtifactCandidateDecision("HANDOFF", "generation budget exhausted after verified rejection", None).validate()
    if observation.state in {"CANDIDATE_AVAILABLE", "VERIFYING"}:
        return ArtifactCandidateDecision("VERIFY_ARTIFACT", "candidate bytes exist; verify/read back rather than wait on stream", None).validate()
    if observation.state == "SUPERSEDED":
        return ArtifactCandidateDecision("NOOP_SUPERSEDED", "superseded generation remains lineage only", None).validate()
    if observation.state == "UNKNOWN":
        return ArtifactCandidateDecision("RECONCILE", "unknown execution state forbids blind retry or successor generation", None).validate()
    if poll_index >= policy.max_polls or elapsed_seconds >= policy.max_elapsed_seconds:
        return ArtifactCandidateDecision("RECONCILE", "observation budget exhausted; reconcile durable worker/artifact state before retry", None).validate()
    return ArtifactCandidateDecision(
        "OBSERVE_LATER",
        "no terminal artifact evidence yet; continue bounded polling of durable state",
        policy.interval_seconds(poll_index),
    ).validate()
