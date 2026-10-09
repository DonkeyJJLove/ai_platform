"""Source-bound cognitive continuity projections for LION.

This module composes existing mission/conversation/provider evidence into
non-authoritative synchronization and readiness projections.  It owns no
conversation store, transport, scheduler, provider session, or authority.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from hashlib import sha256
import json
import re
from typing import Any, Iterable, Mapping, Sequence
from cyber_lion.contracts.phase_execution_contract import (
    PhaseExecutionContractError,
    required_cognitive_providers,
)

SYNC_SCHEMA_ID = "lion.thread-synchronization-checkpoint/v1"
READINESS_SCHEMA_ID = "lion.mission-cognitive-continuity/v1"
AUTHORITY_EFFECT = "NONE"

_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,255}$")
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_HEX40 = re.compile(r"^[0-9a-f]{40}$")
PROVIDERS = frozenset({"LOCAL", "SAAS"})
READINESS_STATES = frozenset({"READY", "WAITING", "BLOCKED", "UNKNOWN"})
CURRENTNESS_STATES = frozenset({"CURRENT", "STALE", "UNKNOWN"})

class CognitiveContinuityError(ValueError):
    pass


def _canon(value: Any) -> bytes:
    try:
        return json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise CognitiveContinuityError("strict JSON required") from exc


def _digest(value: Any) -> str:
    return sha256(_canon(value)).hexdigest()


def _text(value: Any, name: str, maximum: int = 4096) -> str:
    if not isinstance(value, str) or not value or len(value) > maximum or "\x00" in value:
        raise CognitiveContinuityError(name)
    return value


def _id(value: Any, name: str) -> str:
    value = _text(value, name, 256)
    if _ID.fullmatch(value) is None:
        raise CognitiveContinuityError(name)
    return value


def _hex(value: Any, name: str, width: int) -> str:
    pattern = _HEX64 if width == 64 else _HEX40
    if not isinstance(value, str) or pattern.fullmatch(value) is None:
        raise CognitiveContinuityError(name)
    return value


def _meta(value: Any) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, Mapping) else {}
    return {}


def provider_requirements(phase_contracts: Sequence[Mapping[str, Any]]) -> tuple[str, ...]:
    try:
        return required_cognitive_providers(phase_contracts)
    except PhaseExecutionContractError as exc:
        raise CognitiveContinuityError(str(exc)) from exc


def active_saas_bridge(bridges: Iterable[Mapping[str, Any]]) -> Mapping[str, Any] | None:
    rows = [
        dict(row) for row in bridges
        if isinstance(row, Mapping) and row.get("external_system") in {"CHATGPT_SAAS", "CHATGPT_PROJECT"}
    ]
    superseded: set[str] = set()
    for row in rows:
        supplied = _meta(_meta(row.get("provenance_json")).get("supplied"))
        old = supplied.get("supersedes_bridge_id")
        if isinstance(old, str):
            superseded.add(old)
    active = [row for row in rows if row.get("bridge_id") not in superseded]
    active.sort(key=lambda row: (float(row.get("created_at") or 0), str(row.get("bridge_id") or "")))
    return active[-1] if active else None


def history_projection(messages: Iterable[Mapping[str, Any]], *, limit: int = 32) -> dict[str, Any]:
    if type(limit) is not int or not 1 <= limit <= 128:
        raise CognitiveContinuityError("history limit")
    rows = []
    for message in messages:
        if not isinstance(message, Mapping):
            raise CognitiveContinuityError("history message")
        message_id = _id(message.get("message_id"), "message_id")
        content = message.get("content")
        if not isinstance(content, str):
            raise CognitiveContinuityError("message content")
        rows.append({
            "message_id": message_id,
            "role": str(message.get("role") or "UNKNOWN"),
            "created_at": message.get("created_at"),
            "lane_id": message.get("lane_id"),
            "correlation_id": message.get("correlation_id"),
            "causation_id": message.get("causation_id"),
            "context_digest": message.get("context_digest"),
            "content_digest": sha256(content.encode("utf-8")).hexdigest(),
        })
    rows.sort(key=lambda row: (str(row.get("created_at") or ""), row["message_id"]))
    rows = rows[-limit:]
    payload = {"messages": rows, "selection": "LATEST_CANONICAL_BOUNDED", "limit": limit}
    return {**payload, "history_projection_digest": _digest(payload)}


@dataclass(frozen=True)
class SynchronizationCheckpoint:
    mission_id: str
    lpcl_digest: str
    conversation_id: str
    predecessor_conversation_id: str | None
    binding_epoch: int
    consumer_role: str
    source_head: str
    source_tree: str
    shared_context_digest: str
    history_projection_digest: str
    history_message_ids: tuple[str, ...]
    artifact_refs: tuple[str, ...]
    open_dependencies: tuple[str, ...]
    last_reconciled_event: str | None
    currentness: str
    authority_effect: str = AUTHORITY_EFFECT
    checkpoint_digest: str = ""

    def validate(self, *, require_digest: bool = True) -> "SynchronizationCheckpoint":
        _id(self.mission_id, "mission_id")
        _hex(self.lpcl_digest, "lpcl_digest", 64)
        _id(self.conversation_id, "conversation_id")
        if self.predecessor_conversation_id is not None:
            _id(self.predecessor_conversation_id, "predecessor_conversation_id")
            if self.predecessor_conversation_id == self.conversation_id:
                raise CognitiveContinuityError("predecessor identity collapse")
        if type(self.binding_epoch) is not int or self.binding_epoch < 1:
            raise CognitiveContinuityError("binding_epoch")
        _id(self.consumer_role, "consumer_role")
        _hex(self.source_head, "source_head", 40)
        _hex(self.source_tree, "source_tree", 40)
        _hex(self.shared_context_digest, "shared_context_digest", 64)
        _hex(self.history_projection_digest, "history_projection_digest", 64)
        for values, name in (
            (self.history_message_ids, "history_message_ids"),
            (self.artifact_refs, "artifact_refs"),
            (self.open_dependencies, "open_dependencies"),
        ):
            if type(values) is not tuple or tuple(sorted(set(values))) != values:
                raise CognitiveContinuityError(name)
            for item in values:
                _text(item, name, 512)
        if self.last_reconciled_event is not None:
            _text(self.last_reconciled_event, "last_reconciled_event", 512)
        if self.currentness not in CURRENTNESS_STATES:
            raise CognitiveContinuityError("currentness")
        if self.authority_effect != AUTHORITY_EFFECT:
            raise CognitiveContinuityError("authority_effect")
        if require_digest:
            _hex(self.checkpoint_digest, "checkpoint_digest", 64)
            if self.checkpoint_digest != self.compute_digest():
                raise CognitiveContinuityError("checkpoint digest mismatch")
        return self

    def digest_payload(self) -> dict[str, Any]:
        value = asdict(self)
        value.pop("checkpoint_digest", None)
        value["schema"] = SYNC_SCHEMA_ID
        return value

    def compute_digest(self) -> str:
        return sha256(b"LION/THREAD-SYNCHRONIZATION-CHECKPOINT/1\0" + _canon(self.digest_payload())).hexdigest()

    def sealed(self) -> "SynchronizationCheckpoint":
        self.validate(require_digest=False)
        return replace(self, checkpoint_digest=self.compute_digest()).validate()

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        value = asdict(self)
        # On the wire these immutable internal tuples become JSON arrays.
        # The strict receiving contract requires lists even for in-process calls.
        for key in ("history_message_ids", "artifact_refs", "open_dependencies"):
            value[key] = list(value[key])
        return {"schema": SYNC_SCHEMA_ID, **value}


def build_synchronization_checkpoint(
    *,
    mission_id: str,
    lpcl_digest: str,
    source_head: str,
    source_tree: str,
    conversation: Mapping[str, Any],
    messages: Sequence[Mapping[str, Any]],
    consumer_role: str,
    shared_context_digest: str,
    artifact_refs: Sequence[str] = (),
    open_dependencies: Sequence[str] = (),
    last_reconciled_event: str | None = None,
    currentness: str = "CURRENT",
) -> SynchronizationCheckpoint:
    if not isinstance(conversation, Mapping):
        raise CognitiveContinuityError("conversation")
    binding = conversation.get("current_binding")
    if not isinstance(binding, Mapping):
        raise CognitiveContinuityError("current binding missing")
    if conversation.get("state") != "BOUND" or binding.get("state") != "BOUND":
        raise CognitiveContinuityError("conversation not bound")
    if binding.get("mission_id") != mission_id:
        raise CognitiveContinuityError("mission conversation mismatch")
    lineage = conversation.get("lineage")
    predecessor = lineage.get("predecessor_conversation_id") if isinstance(lineage, Mapping) else None
    history = history_projection(messages)
    return SynchronizationCheckpoint(
        mission_id=_id(mission_id, "mission_id"),
        lpcl_digest=_hex(lpcl_digest, "lpcl_digest", 64),
        conversation_id=_id(conversation.get("conversation_id"), "conversation_id"),
        predecessor_conversation_id=predecessor,
        binding_epoch=int(binding.get("binding_epoch")),
        consumer_role=_id(consumer_role, "consumer_role"),
        source_head=_hex(source_head, "source_head", 40),
        source_tree=_hex(source_tree, "source_tree", 40),
        shared_context_digest=_hex(shared_context_digest, "shared_context_digest", 64),
        history_projection_digest=history["history_projection_digest"],
        history_message_ids=tuple(sorted(row["message_id"] for row in history["messages"])),
        artifact_refs=tuple(sorted(set(str(x) for x in artifact_refs))),
        open_dependencies=tuple(sorted(set(str(x) for x in open_dependencies))),
        last_reconciled_event=last_reconciled_event,
        currentness=currentness,
    ).sealed()


def _provider_message_evidence(
    messages: Sequence[Mapping[str, Any]],
    lane_ids: set[str],
    synchronization_checkpoint_digest: str | None = None,
) -> dict[str, Any]:
    response = None
    for message in messages:
        if not isinstance(message, Mapping) or message.get("lane_id") not in lane_ids:
            continue
        if message.get("role") != "ASSISTANT":
            continue
        meta = _meta(message.get("metadata"))
        response_meta = _meta(meta.get("response_meta"))
        observed_sync = (
            meta.get("synchronization_checkpoint_digest")
            or response_meta.get("synchronization_checkpoint_digest")
        )
        if synchronization_checkpoint_digest is not None and observed_sync != synchronization_checkpoint_digest:
            continue
        candidate = {
            "message_id": message.get("message_id"),
            "provider_session_ref": meta.get("provider_session_ref"),
            "provider_session_ref_class": meta.get("provider_session_ref_class"),
            "projection_digest": response_meta.get("projection_digest"),
            "actual_payload_bytes_digest": response_meta.get("actual_payload_bytes_digest"),
            "response_digest": response_meta.get("response_digest"),
            "receipt_digest": response_meta.get("receipt_digest"),
            "synchronization_checkpoint_digest": observed_sync,
            "created_at": message.get("created_at"),
        }
        if response is None or str(candidate.get("created_at") or "") >= str(response.get("created_at") or ""):
            response = candidate
    return response or {}


def build_mission_cognitive_continuity(
    *,
    mission_id: str,
    lpcl_digest: str,
    source_head: str,
    source_tree: str,
    phase_contracts: Sequence[Mapping[str, Any]],
    conversation: Mapping[str, Any] | None,
    messages: Sequence[Mapping[str, Any]] = (),
    provider_capabilities: Mapping[str, Mapping[str, Any]] | None = None,
    expected_conversation_id: str | None = None,
    expected_binding_epoch: int | None = None,
    shared_context_digest: str | None = None,
    synchronization_checkpoint_digest: str | None = None,
    observed_at: str = "UNKNOWN",
) -> dict[str, Any]:
    required = provider_requirements(phase_contracts)
    blockers: list[str] = []
    provider_paths: dict[str, Any] = {}
    provider_capabilities = provider_capabilities or {}

    if not required:
        payload = {
            "schema": READINESS_SCHEMA_ID,
            "mission_id": _id(mission_id, "mission_id"),
            "lpcl_digest": _hex(lpcl_digest, "lpcl_digest", 64),
            "conversation_id": None,
            "binding_epoch": None,
            "required_providers": [],
            "provider_paths": {},
            "shared_context_digest": None,
            "synchronization_checkpoint_digest": None,
            "source_head": _hex(source_head, "source_head", 40),
            "source_tree": _hex(source_tree, "source_tree", 40),
            "observed_at": observed_at,
            "currentness": "CURRENT",
            "state": "READY",
            "blockers": [],
            "authority_effect": "NONE",
        }
        return {**payload, "projection_digest": _digest(payload)}

    if not isinstance(conversation, Mapping):
        blockers.append("CANONICAL_CONVERSATION_REQUIRED")
        conversation = {}
    conversation_id = conversation.get("conversation_id")
    binding = conversation.get("current_binding") if isinstance(conversation.get("current_binding"), Mapping) else None
    if conversation.get("state") != "BOUND" or binding is None or binding.get("state") != "BOUND":
        blockers.append("CURRENT_BOUND_CONVERSATION_REQUIRED")
    if binding is not None and binding.get("mission_id") != mission_id:
        blockers.append("MISSION_CONVERSATION_BINDING_MISMATCH")
    if expected_conversation_id is not None and conversation_id != expected_conversation_id:
        blockers.append("CONVERSATION_ID_MISMATCH")
    epoch = int(binding.get("binding_epoch")) if binding and isinstance(binding.get("binding_epoch"), int) else None
    if expected_binding_epoch is not None and epoch != expected_binding_epoch:
        blockers.append("BINDING_EPOCH_MISMATCH")

    current_lanes = [
        row for row in (conversation.get("lanes") or ())
        if isinstance(row, Mapping) and epoch is not None and int(row.get("binding_epoch") or -1) == epoch
    ]
    bridge = active_saas_bridge(conversation.get("external_bridges") or ())
    for provider in required:
        lanes = [row for row in current_lanes if row.get("provider") == provider]
        lane_ids = {str(row.get("lane_id")) for row in lanes if row.get("lane_id")}
        path_blockers: list[str] = []
        if not lanes:
            path_blockers.append(provider + "_LANE_REQUIRED")
        if any(row.get("state") not in {"READY", "ACTIVE"} for row in lanes):
            path_blockers.append(provider + "_LANE_NOT_READY")
        capability = provider_capabilities.get(provider) if isinstance(provider_capabilities, Mapping) else None
        if not isinstance(capability, Mapping) or capability.get("currentness") != "CURRENT":
            path_blockers.append(provider + "_CAPABILITY_CURRENTNESS_REQUIRED")
        elif capability.get("text_input") != "SUPPORTED":
            path_blockers.append(provider + "_TEXT_INPUT_REQUIRED")
        evidence = _provider_message_evidence(
            messages, lane_ids, synchronization_checkpoint_digest
        )
        if provider == "SAAS":
            if bridge is None:
                path_blockers.append("SAAS_BRIDGE_REQUIRED")
            if not any(row.get("provider_session_ref") for row in lanes):
                path_blockers.append("SAAS_PROVIDER_SESSION_EVIDENCE_REQUIRED")
        else:
            # LOCAL is stateless in the current canonical path; a fabricated
            # provider session is not required.  Response evidence remains
            # distinct from provider session identity.
            if lanes and evidence and evidence.get("provider_session_ref_class") not in {
                None, "UNKNOWN_NOT_PROVIDER_ATTESTED"
            }:
                path_blockers.append("LOCAL_SYNTHETIC_PROVIDER_SESSION_DENIED")
        for field, blocker in (
            ("projection_digest", provider + "_PROJECTION_DIGEST_REQUIRED"),
            ("actual_payload_bytes_digest", provider + "_ACTUAL_PAYLOAD_DIGEST_REQUIRED"),
            ("response_digest", provider + "_RESPONSE_DIGEST_REQUIRED"),
        ):
            if _HEX64.fullmatch(str(evidence.get(field) or "")) is None:
                path_blockers.append(blocker)
        provider_paths[provider] = {
            "lane_ids": sorted(lane_ids),
            "provider_session_refs": sorted(
                str(row.get("provider_session_ref")) for row in lanes if row.get("provider_session_ref")
            ),
            "bridge_id": bridge.get("bridge_id") if provider == "SAAS" and bridge else None,
            "external_thread_ref": bridge.get("external_thread_ref") if provider == "SAAS" and bridge else None,
            "projection_digest": evidence.get("projection_digest"),
            "actual_payload_bytes_digest": evidence.get("actual_payload_bytes_digest"),
            "response_digest": evidence.get("response_digest"),
            "blockers": sorted(set(path_blockers)),
        }
        blockers.extend(path_blockers)

    if _HEX64.fullmatch(str(shared_context_digest or "")) is None:
        blockers.append("SHARED_CONTEXT_DIGEST_REQUIRED")
    if _HEX64.fullmatch(str(synchronization_checkpoint_digest or "")) is None:
        blockers.append("SYNCHRONIZATION_CHECKPOINT_REQUIRED")

    blockers = sorted(set(blockers))
    currentness = "CURRENT" if not blockers else "UNKNOWN"
    state = "READY" if not blockers else "WAITING"
    payload = {
        "schema": READINESS_SCHEMA_ID,
        "mission_id": _id(mission_id, "mission_id"),
        "lpcl_digest": _hex(lpcl_digest, "lpcl_digest", 64),
        "conversation_id": conversation_id,
        "binding_epoch": epoch,
        "required_providers": list(required),
        "provider_paths": provider_paths,
        "shared_context_digest": shared_context_digest,
        "synchronization_checkpoint_digest": synchronization_checkpoint_digest,
        "source_head": _hex(source_head, "source_head", 40),
        "source_tree": _hex(source_tree, "source_tree", 40),
        "observed_at": observed_at,
        "currentness": currentness,
        "state": state,
        "blockers": blockers,
        "authority_effect": "NONE",
    }
    return {**payload, "projection_digest": _digest(payload)}


def validate_activation_readiness(
    projection: Mapping[str, Any],
    *,
    mission_id: str,
    lpcl_digest: str,
    required_providers: Sequence[str],
    conversation_id: str,
    binding_epoch: int,
) -> Mapping[str, Any]:
    if not isinstance(projection, Mapping):
        raise CognitiveContinuityError("readiness projection")
    if projection.get("schema") != READINESS_SCHEMA_ID:
        raise CognitiveContinuityError("readiness schema")
    if projection.get("authority_effect") != "NONE":
        raise CognitiveContinuityError("readiness authority")
    if projection.get("mission_id") != mission_id or projection.get("lpcl_digest") != lpcl_digest:
        raise CognitiveContinuityError("readiness mission binding")
    if projection.get("conversation_id") != conversation_id or projection.get("binding_epoch") != binding_epoch:
        raise CognitiveContinuityError("readiness conversation binding")
    if tuple(projection.get("required_providers") or ()) != tuple(sorted(set(required_providers))):
        raise CognitiveContinuityError("readiness provider requirements")
    if projection.get("currentness") != "CURRENT" or projection.get("state") != "READY":
        raise CognitiveContinuityError("cognitive readiness not current")
    if projection.get("blockers"):
        raise CognitiveContinuityError("cognitive readiness blockers")
    supplied = projection.get("projection_digest")
    if _HEX64.fullmatch(str(supplied or "")) is None:
        raise CognitiveContinuityError("readiness projection digest")
    payload = dict(projection)
    payload.pop("projection_digest", None)
    if supplied != _digest(payload):
        raise CognitiveContinuityError("readiness projection digest mismatch")
    return projection
