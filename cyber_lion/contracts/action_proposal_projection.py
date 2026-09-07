"""Deterministic, non-effectful static projection from CanonicalActionIR toward ActionProposal.

The live contracts declare exactly one canonical cross-contract binding today:
CanonicalActionIR.payload_digest -> ActionProposal.payload_digest.  Every other
ActionProposal field requires external context or an explicit semantic mapping and is
therefore preserved as unresolved here rather than guessed.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import re
from typing import Tuple

from .action_ir import CanonicalActionIR

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_SCHEMA = "1.0.0"

ACTION_PROPOSAL_FIELDS = (
    "proposal_id",
    "mission_id",
    "swarm_id",
    "proposer_agent_id",
    "capability",
    "requested_authority",
    "action_class",
    "target",
    "consequential",
    "evidence_refs",
    "required_observability",
    "verifier_agent_id",
    "payload_digest",
)
DIRECT_BINDINGS = ("payload_digest",)
UNRESOLVED_FIELDS = tuple(name for name in ACTION_PROPOSAL_FIELDS if name not in DIRECT_BINDINGS)
BLOCKED_IMPLICIT_MAPPINGS = (
    "authority_request->requested_authority",
    "kind->action_class",
    "structured_target->target",
)


class ActionProposalProjectionError(ValueError):
    pass


def _text(value: object, name: str) -> str:
    if type(value) is not str or not value or "\x00" in value:
        raise ActionProposalProjectionError(f"{name} invalid")
    return value


@dataclass(frozen=True)
class ActionProposalStaticProjection:
    source_action_id: str
    source_mission_ref: str
    source_kind: str
    source_authority_domain: str
    source_capability: str
    source_grant_ref: str | None
    source_target_host: str
    source_target_environment: str
    source_target_runtime: str
    source_required_events: Tuple[str, ...]
    source_expected_effects: Tuple[str, ...]
    source_forbidden_effects: Tuple[str, ...]
    lair_payload_digest: str
    action_proposal_payload_digest: str
    direct_bindings: Tuple[str, ...] = DIRECT_BINDINGS
    unresolved_action_proposal_fields: Tuple[str, ...] = UNRESOLVED_FIELDS
    blocked_implicit_mappings: Tuple[str, ...] = BLOCKED_IMPLICIT_MAPPINGS
    authority_effect: str = "NONE"
    execution_effect: str = "NONE"
    transport_effect: str = "NONE"
    policy_effect: str = "NONE"
    schema_version: str = _SCHEMA

    def validate(self) -> "ActionProposalStaticProjection":
        if self.schema_version != _SCHEMA:
            raise ActionProposalProjectionError("unsupported projection schema")
        for name in (
            "source_action_id", "source_mission_ref", "source_kind",
            "source_authority_domain", "source_capability", "source_target_host",
            "source_target_environment", "source_target_runtime",
        ):
            _text(getattr(self, name), name)
        if self.source_grant_ref is not None and type(self.source_grant_ref) is not str:
            raise ActionProposalProjectionError("source_grant_ref invalid")
        for name in ("source_required_events", "source_expected_effects", "source_forbidden_effects"):
            value = getattr(self, name)
            if type(value) is not tuple or any(type(item) is not str or not item for item in value):
                raise ActionProposalProjectionError(f"{name} invalid")
            if len(value) != len(set(value)):
                raise ActionProposalProjectionError(f"{name} duplicates")
        if not _SHA256.fullmatch(self.lair_payload_digest):
            raise ActionProposalProjectionError("lair_payload_digest invalid")
        if self.action_proposal_payload_digest != self.lair_payload_digest:
            raise ActionProposalProjectionError("payload digest binding mismatch")
        if self.direct_bindings != DIRECT_BINDINGS:
            raise ActionProposalProjectionError("direct binding set is closed")
        if self.unresolved_action_proposal_fields != UNRESOLVED_FIELDS:
            raise ActionProposalProjectionError("unresolved field set is closed")
        if self.blocked_implicit_mappings != BLOCKED_IMPLICIT_MAPPINGS:
            raise ActionProposalProjectionError("blocked implicit mapping set is closed")
        if (self.authority_effect, self.execution_effect, self.transport_effect, self.policy_effect) != (
            "NONE", "NONE", "NONE", "NONE"
        ):
            raise ActionProposalProjectionError("static projection cannot carry effects")
        return self

    def digest(self) -> str:
        self.validate()
        raw = json.dumps(asdict(self), sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        return sha256(b"LION/ACTION-PROPOSAL-STATIC-PROJECTION/1\0" + raw).hexdigest()


def project_lair_to_action_proposal_static(ir: CanonicalActionIR) -> ActionProposalStaticProjection:
    if type(ir) is not CanonicalActionIR:
        raise ActionProposalProjectionError("exact CanonicalActionIR required")
    ir.validate()
    value = ir.as_dict()
    authority = value["authority_request"]
    target = value["target"]
    return ActionProposalStaticProjection(
        source_action_id=value["action_id"],
        source_mission_ref=value["mission_ref"],
        source_kind=value["kind"],
        source_authority_domain=authority["domain"],
        source_capability=authority["capability"],
        source_grant_ref=authority["grant_ref"],
        source_target_host=target["host"],
        source_target_environment=target["environment"],
        source_target_runtime=target["runtime"],
        source_required_events=tuple(value["observation"]["required_events"]),
        source_expected_effects=tuple(value["expected_effects"]),
        source_forbidden_effects=tuple(value["forbidden_effects"]),
        lair_payload_digest=ir.payload_digest,
        action_proposal_payload_digest=ir.payload_digest,
    ).validate()
