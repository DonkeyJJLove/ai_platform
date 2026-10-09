"""Mission-bound cognitive scaffolding; proposal-only projection for LOCAL/SAAS.

Built from exact Mission Control source and current canonical conversation binding.
This is data for the existing DUAL conversation path, never a second driver,
authorization, or a direct worker command.
"""
from __future__ import annotations

from hashlib import sha256
import json
import re
from typing import Any, Mapping

from cyber_lion.contracts.cognitive_continuity import validate_synchronization_checkpoint

_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_SHA64 = re.compile(r"^[0-9a-f]{64}$")
_ALLOWED_ROLES = frozenset({
    "ANALYST", "COORDINATOR", "BUILDER", "REVIEWER", "VERIFIER",
    "RESEARCHER", "SCOUT", "INTEGRATOR",
})
_PROVIDERS = ("LOCAL", "SAAS")


class MissionScaffoldError(ValueError):
    pass


def _require(condition: bool, reason: str) -> None:
    if not condition:
        raise MissionScaffoldError(reason)


def _canon(value: Mapping[str, Any]) -> bytes:
    return json.dumps(dict(value), sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def _digest(value: Mapping[str, Any]) -> str:
    return sha256(_canon(value)).hexdigest()


def _mission_source(mission: Mapping[str, Any]) -> tuple[str, str, str, str]:
    process = mission.get("process")
    _require(isinstance(process, Mapping), "MISSION_PROCESS_REQUIRED")
    text = process.get("lpcl_text")
    _require(isinstance(text, str) and 0 < len(text) <= 200000, "EXACT_LPCL_BYTES_REQUIRED")
    lpcl_digest = mission.get("spec_digest") or process.get("lpcl_digest")
    head, tree = mission.get("source_head"), mission.get("source_tree")
    _require(isinstance(lpcl_digest, str) and _SHA64.fullmatch(lpcl_digest) is not None,
             "LPCL_DIGEST_REQUIRED")
    _require(sha256(text.encode("utf-8")).hexdigest() == lpcl_digest,
             "EXACT_LPCL_SOURCE_MISMATCH")
    _require(isinstance(head, str) and _SHA40.fullmatch(head) is not None,
             "SOURCE_HEAD_REQUIRED")
    _require(isinstance(tree, str) and _SHA40.fullmatch(tree) is not None,
             "SOURCE_TREE_REQUIRED")
    return text, lpcl_digest, head, tree


def build_mission_scaffold(
    mission: Mapping[str, Any],
    conversation: Mapping[str, Any],
    checkpoint: Mapping[str, Any],
    *,
    provider_roles: Mapping[str, str],
    system_context_digest: str,
) -> dict[str, Any]:
    """Produce distinct, exact provider prompts from one shared context binding."""
    _require(isinstance(mission, Mapping) and isinstance(conversation, Mapping),
             "MISSION_CONVERSATION_REQUIRED")
    _require(isinstance(checkpoint, Mapping), "CHECKPOINT_REQUIRED")
    _require(type(provider_roles) is dict and set(provider_roles) == set(_PROVIDERS),
             "EXACT_PROVIDER_ROLES_REQUIRED")
    _require(isinstance(system_context_digest, str)
             and _SHA64.fullmatch(system_context_digest) is not None,
             "SYSTEM_CONTEXT_DIGEST_REQUIRED")

    text, lpcl_digest, head, tree = _mission_source(mission)
    mid = mission.get("mission_id")
    _require(isinstance(mid, str) and mid, "MISSION_ID_REQUIRED")
    binding = conversation.get("current_binding")
    _require(isinstance(binding, Mapping)
             and conversation.get("state") == "BOUND"
             and binding.get("state") == "BOUND"
             and binding.get("mission_id") == mid, "MISSION_BINDING_CURRENT_REQUIRED")
    cid = conversation.get("conversation_id")
    epoch = binding.get("binding_epoch")
    _require(isinstance(cid, str) and cid, "CONVERSATION_ID_REQUIRED")
    _require(type(epoch) is int and epoch >= 1, "BINDING_EPOCH_REQUIRED")
    for provider, role in provider_roles.items():
        _require(provider in _PROVIDERS and role in _ALLOWED_ROLES,
                 "PROVIDER_ROLE_NOT_DECLARED")

    validate_synchronization_checkpoint(
        checkpoint, mission_id=mid, lpcl_digest=lpcl_digest,
        source_head=head, source_tree=tree,
    )
    _require(checkpoint.get("conversation_id") == cid
             and checkpoint.get("binding_epoch") == epoch,
             "CHECKPOINT_BINDING_DRIFT")
    _require(checkpoint.get("shared_context_digest") == system_context_digest,
             "CHECKPOINT_CONTEXT_DRIFT")

    process = mission["process"]
    objective = str(process.get("objective") or "").strip()
    description = str(process.get("description") or "").strip()
    _require(0 < len(objective) <= 4000 and len(description) <= 8000,
             "MISSION_GOAL_INVALID")
    logical_count = mission.get("logical_count")
    material_target = mission.get("material_target")
    _require(type(logical_count) is int and 1 <= logical_count <= 512
             and type(material_target) is int and 0 <= material_target <= 4096,
             "MISSION_FLEET_TARGET_INVALID")
    declared_contracts = mission.get("phase_execution_contracts") or []
    _require(isinstance(declared_contracts, list) and len(declared_contracts) <= 64,
             "MISSION_CONTRACT_SET_INVALID")
    phase_contracts = []
    for contract in declared_contracts:
        _require(isinstance(contract, Mapping)
                 and contract.get("mission_id", mid) == mid,
                 "PHASE_CONTRACT_PARENT_DRIFT")
        phase_contracts.append({
            "phase_id": contract.get("phase_id"),
            "execution_class": contract.get("execution_class"),
            "effect_ceiling": contract.get("effect_ceiling"),
            "capability_classes": list(contract.get("capability_classes") or ()),
            "completion_predicates": list(contract.get("completion_predicates") or ()),
        })

    # The source text is never treated as a shell script. The complete source
    # identity stays available by digest; only bounded source-derived intent
    # and explicit provider role travel in prompt projections.
    shared = {
        "schema": "lion.mission-scaffold-shared/v1",
        "mission_id": mid,
        "conversation_id": cid,
        "binding_epoch": epoch,
        "lpcl_digest": lpcl_digest,
        "source_head": head,
        "source_tree": tree,
        "source_text_bytes_digest": sha256(text.encode("utf-8")).hexdigest(),
        "binding_context_digest": binding.get("context_digest"),
        "system_context_digest": system_context_digest,
        "synchronization_checkpoint_digest": checkpoint["checkpoint_digest"],
        "logical_drone_target": logical_count,
        "material_worker_target": material_target,
        "phase_execution_contracts": phase_contracts,
        "objective": objective,
        "description": description,
        "authority_effect": "NONE",
    }
    _require(isinstance(shared["binding_context_digest"], str)
             and _SHA64.fullmatch(shared["binding_context_digest"]) is not None,
             "CONVERSATION_CONTEXT_INVALID")
    shared_digest = _digest(shared)

    out: dict[str, dict[str, str]] = {}
    for provider in _PROVIDERS:
        projection = {
            "schema": "lion.mission-scaffold-provider-projection/v1",
            "provider": provider,
            "role": provider_roles[provider],
            "shared_scaffold_digest": shared_digest,
            "mission_id": mid,
            "conversation_id": cid,
            "binding_epoch": epoch,
            "synchronization_checkpoint_digest": checkpoint["checkpoint_digest"],
            "authority_effect": "NONE",
            "instruction": (
                "Work only on the mission objective and declared role. "
                "Return a bounded proposal and evidence needs. "
                "No shell execution, worker launch, completion claim or new authority."
            ),
        }
        projection_digest = _digest(projection)
        rendered = (
            "LION BOUND MISSION SCAFFOLD — non-authoritative\n"
            + _canon(shared).decode("utf-8") + "\n"
            + _canon(projection).decode("utf-8")
        )
        out[provider] = {
            "role": provider_roles[provider],
            "projection_digest": projection_digest,
            "scaffold_bytes_digest": sha256(rendered.encode("utf-8")).hexdigest(),
            "prompt": rendered,
        }

    return {
        "schema": "lion.bound-mission-scaffold/v1",
        "mission_id": mid,
        "conversation_id": cid,
        "binding_epoch": epoch,
        "synchronization_checkpoint_digest": checkpoint["checkpoint_digest"],
        "shared_context_digest": system_context_digest,
        "shared_scaffold_digest": shared_digest,
        "projections": out,
        "authority_effect": "NONE",
    }


def validate_for_chat(scaffold: Mapping[str, Any], plan: Mapping[str, Any]) -> None:
    """Reject an injected or stale scaffold before either provider is called."""
    _require(isinstance(scaffold, Mapping) and scaffold.get("authority_effect") == "NONE",
             "SCAFFOLD_NOT_TRUSTED")
    for key in ("mission_id", "conversation_id", "binding_epoch",
                "synchronization_checkpoint_digest", "shared_context_digest"):
        _require(scaffold.get(key) == plan.get(key),
                 "SCAFFOLD_CHAT_IDENTITY_DRIFT:" + key)
    projections = scaffold.get("projections")
    _require(isinstance(projections, Mapping) and set(projections) == set(_PROVIDERS),
             "SCAFFOLD_PROVIDER_SET_DRIFT")
    for provider in _PROVIDERS:
        value = projections[provider]
        _require(isinstance(value, Mapping), "SCAFFOLD_PROJECTION_MISSING")
        prompt = value.get("prompt")
        _require(isinstance(prompt, str) and 0 < len(prompt.encode("utf-8")) <= 32000,
                 "SCAFFOLD_PROMPT_INVALID")
        _require(sha256(prompt.encode("utf-8")).hexdigest()
                 == value.get("scaffold_bytes_digest"),
                 "SCAFFOLD_PROMPT_BYTES_DRIFT")
        try:
            header, shared_json, provider_json = prompt.split("\n", 2)
            shared = json.loads(shared_json)
            projection = json.loads(provider_json)
        except (ValueError, json.JSONDecodeError) as exc:
            raise MissionScaffoldError("SCAFFOLD_WIRE_PROJECTION_INVALID") from exc
        _require(header == "LION BOUND MISSION SCAFFOLD — non-authoritative"
                 and isinstance(shared, dict) and isinstance(projection, dict),
                 "SCAFFOLD_WIRE_PROJECTION_INVALID")
        _require(_digest(shared) == scaffold.get("shared_scaffold_digest")
                 and projection.get("shared_scaffold_digest") == scaffold.get("shared_scaffold_digest"),
                 "SCAFFOLD_SHARED_DIGEST_DRIFT")
        for k in ("mission_id", "conversation_id", "binding_epoch",
                  "synchronization_checkpoint_digest"):
            _require(shared.get(k) == plan.get(k),
                     "SCAFFOLD_SHARED_BINDING_DRIFT:" + k)
        _require(shared.get("system_context_digest") == plan.get("shared_context_digest")
                 and shared.get("source_text_bytes_digest") == shared.get("lpcl_digest")
                 and shared.get("authority_effect") == "NONE",
                 "SCAFFOLD_SHARED_SOURCE_OR_CONTEXT_DRIFT")
        _require(_digest(projection) == value.get("projection_digest")
                 and projection.get("provider") == provider
                 and projection.get("role") == value.get("role"),
                 "SCAFFOLD_PROVIDER_IDENTITY_DRIFT")
