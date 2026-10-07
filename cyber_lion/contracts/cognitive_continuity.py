"""Canonical non-authoritative cognitive continuity validation contracts."""
from __future__ import annotations

from hashlib import sha256
import json
import re
from typing import Any, Mapping, Sequence

SYNC_SCHEMA_ID = "lion.thread-synchronization-checkpoint/v1"
READINESS_SCHEMA_ID = "lion.mission-cognitive-continuity/v1"
AUTHORITY_EFFECT = "NONE"

_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,255}$")
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_HEX40 = re.compile(r"^[0-9a-f]{40}$")
_PROVIDERS = frozenset({"LOCAL", "SAAS"})


class CognitiveContinuityContractError(ValueError):
    pass


def _canon(value: Any) -> bytes:
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise CognitiveContinuityContractError("strict JSON required") from exc


def _digest(value: Any) -> str:
    return sha256(_canon(value)).hexdigest()


def _id(value: Any, name: str) -> str:
    if not isinstance(value, str) or _ID.fullmatch(value) is None:
        raise CognitiveContinuityContractError(name)
    return value


def _hex(value: Any, name: str, width: int) -> str:
    pattern = _HEX64 if width == 64 else _HEX40
    if not isinstance(value, str) or pattern.fullmatch(value) is None:
        raise CognitiveContinuityContractError(name)
    return value


def validate_synchronization_checkpoint(
    value: Mapping[str, Any], *, mission_id: str, lpcl_digest: str, source_head: str, source_tree: str
) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise CognitiveContinuityContractError("synchronization checkpoint")
    required = {
        "schema", "mission_id", "lpcl_digest", "conversation_id", "predecessor_conversation_id",
        "binding_epoch", "consumer_role", "source_head", "source_tree", "shared_context_digest",
        "history_projection_digest", "history_message_ids", "artifact_refs", "open_dependencies",
        "last_reconciled_event", "currentness", "authority_effect", "checkpoint_digest",
    }
    if set(value) != required:
        raise CognitiveContinuityContractError("synchronization checkpoint fields")
    if value.get("schema") != SYNC_SCHEMA_ID or value.get("authority_effect") != AUTHORITY_EFFECT:
        raise CognitiveContinuityContractError("synchronization checkpoint schema/authority")
    if value.get("mission_id") != mission_id or value.get("lpcl_digest") != lpcl_digest:
        raise CognitiveContinuityContractError("synchronization checkpoint mission")
    if value.get("source_head") != source_head or value.get("source_tree") != source_tree:
        raise CognitiveContinuityContractError("synchronization checkpoint source")
    _id(value.get("conversation_id"), "conversation_id")
    predecessor = value.get("predecessor_conversation_id")
    if predecessor is not None:
        _id(predecessor, "predecessor_conversation_id")
        if predecessor == value.get("conversation_id"):
            raise CognitiveContinuityContractError("predecessor identity collapse")
    epoch = value.get("binding_epoch")
    if type(epoch) is not int or epoch < 1:
        raise CognitiveContinuityContractError("binding_epoch")
    _id(value.get("consumer_role"), "consumer_role")
    _hex(value.get("shared_context_digest"), "shared_context_digest", 64)
    _hex(value.get("history_projection_digest"), "history_projection_digest", 64)
    for name in ("history_message_ids", "artifact_refs", "open_dependencies"):
        items = value.get(name)
        if not isinstance(items, list) or items != sorted(set(items)):
            raise CognitiveContinuityContractError(name)
        if any(not isinstance(item, str) or not item for item in items):
            raise CognitiveContinuityContractError(name)
    if value.get("currentness") != "CURRENT":
        raise CognitiveContinuityContractError("synchronization checkpoint currentness")
    supplied = _hex(value.get("checkpoint_digest"), "checkpoint_digest", 64)
    payload = dict(value)
    payload.pop("checkpoint_digest", None)
    expected = sha256(b"LION/THREAD-SYNCHRONIZATION-CHECKPOINT/1\0" + _canon(payload)).hexdigest()
    if supplied != expected:
        raise CognitiveContinuityContractError("synchronization checkpoint digest mismatch")
    return value


def validate_cognitive_readiness_projection(
    value: Mapping[str, Any],
    *,
    mission_id: str,
    lpcl_digest: str,
    required_providers: Sequence[str],
    source_head: str | None = None,
    source_tree: str | None = None,
    conversation_id: str | None = None,
    binding_epoch: int | None = None,
) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise CognitiveContinuityContractError("readiness projection")
    required_fields = {
        "schema", "mission_id", "lpcl_digest", "conversation_id", "binding_epoch",
        "required_providers", "provider_paths", "shared_context_digest",
        "synchronization_checkpoint_digest", "source_head", "source_tree", "observed_at",
        "currentness", "state", "blockers", "authority_effect", "projection_digest",
    }
    if set(value) != required_fields:
        raise CognitiveContinuityContractError("readiness projection fields")
    if value.get("schema") != READINESS_SCHEMA_ID or value.get("authority_effect") != AUTHORITY_EFFECT:
        raise CognitiveContinuityContractError("readiness schema/authority")
    if value.get("mission_id") != mission_id or value.get("lpcl_digest") != lpcl_digest:
        raise CognitiveContinuityContractError("readiness mission binding")
    if source_head is not None and value.get("source_head") != source_head:
        raise CognitiveContinuityContractError("readiness source head")
    if source_tree is not None and value.get("source_tree") != source_tree:
        raise CognitiveContinuityContractError("readiness source tree")
    _hex(value.get("source_head"), "source_head", 40)
    _hex(value.get("source_tree"), "source_tree", 40)

    expected_providers = tuple(sorted(set(required_providers)))
    supplied_providers = value.get("required_providers")
    if not isinstance(supplied_providers, list) or tuple(supplied_providers) != expected_providers:
        raise CognitiveContinuityContractError("readiness provider requirements")
    if any(provider not in _PROVIDERS for provider in supplied_providers):
        raise CognitiveContinuityContractError("readiness provider")
    provider_paths = value.get("provider_paths")
    if not isinstance(provider_paths, Mapping) or set(provider_paths) != set(expected_providers):
        raise CognitiveContinuityContractError("provider path requirements")
    blockers = value.get("blockers")
    if not isinstance(blockers, list) or blockers != sorted(set(blockers)):
        raise CognitiveContinuityContractError("readiness blockers")

    if expected_providers:
        if conversation_id is not None and value.get("conversation_id") != conversation_id:
            raise CognitiveContinuityContractError("readiness conversation binding")
        _id(value.get("conversation_id"), "conversation_id")
        epoch = value.get("binding_epoch")
        if type(epoch) is not int or epoch < 1:
            raise CognitiveContinuityContractError("readiness binding epoch")
        if binding_epoch is not None and epoch != binding_epoch:
            raise CognitiveContinuityContractError("readiness conversation binding")
        _hex(value.get("shared_context_digest"), "shared_context_digest", 64)
        _hex(value.get("synchronization_checkpoint_digest"), "synchronization_checkpoint_digest", 64)
        if value.get("currentness") != "CURRENT" or value.get("state") != "READY" or blockers:
            raise CognitiveContinuityContractError("cognitive readiness not current")
    elif value.get("state") != "READY" or value.get("currentness") != "CURRENT":
        raise CognitiveContinuityContractError("non-cognitive readiness")

    supplied_digest = _hex(value.get("projection_digest"), "projection_digest", 64)
    payload = dict(value)
    payload.pop("projection_digest", None)
    if supplied_digest != _digest(payload):
        raise CognitiveContinuityContractError("readiness projection digest mismatch")
    return value
