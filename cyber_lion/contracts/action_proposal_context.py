"""Explicit, non-effectful context binding from canonical LAIR to ActionProposal."""
from __future__ import annotations
from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import re
from typing import Tuple
from .action_ir import CanonicalActionIR
from .action_proposal_projection import BLOCKED_IMPLICIT_MAPPINGS, DIRECT_BINDINGS, project_lair_to_action_proposal_static
from cyber_lion.enterprise.control_plane import ActionProposal
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_SCHEMA = "1.0.0"
REQUIRED_CONTEXT_FIELDS = ("proposal_id","mission_id","swarm_id","proposer_agent_id","capability","requested_authority","action_class","target","consequential","evidence_refs","required_observability")
OPTIONAL_CONTEXT_FIELDS = ("verifier_agent_id",)
class ActionProposalContextBindingError(ValueError): pass
def _text(value: object, name: str) -> str:
    if type(value) is not str or not value or "\x00" in value: raise ActionProposalContextBindingError(f"{name} invalid")
    return value
def _refs(value: object, name: str) -> Tuple[str, ...]:
    if type(value) is not tuple or any(type(item) is not str or not item or "\x00" in item for item in value): raise ActionProposalContextBindingError(f"{name} invalid")
    if len(value) != len(set(value)): raise ActionProposalContextBindingError(f"{name} duplicates")
    return value
@dataclass(frozen=True)
class ExplicitActionProposalContext:
    proposal_id: str
    mission_id: str
    swarm_id: str
    proposer_agent_id: str
    capability: str
    requested_authority: str
    action_class: str
    target: str
    consequential: bool
    evidence_refs: Tuple[str, ...]
    required_observability: Tuple[str, ...]
    expected_lair_payload_digest: str
    field_provenance: Tuple[Tuple[str, str], ...]
    verifier_agent_id: str | None = None
    schema_version: str = _SCHEMA
    def validate(self) -> "ExplicitActionProposalContext":
        if self.schema_version != _SCHEMA: raise ActionProposalContextBindingError("unsupported context schema")
        for name in ("proposal_id","mission_id","swarm_id","proposer_agent_id","capability","requested_authority","action_class","target"): _text(getattr(self,name),name)
        if type(self.consequential) is not bool: raise ActionProposalContextBindingError("consequential invalid")
        _refs(self.evidence_refs,"evidence_refs"); _refs(self.required_observability,"required_observability")
        if self.verifier_agent_id is not None: _text(self.verifier_agent_id,"verifier_agent_id")
        if not _SHA256.fullmatch(self.expected_lair_payload_digest): raise ActionProposalContextBindingError("expected_lair_payload_digest invalid")
        if type(self.field_provenance) is not tuple: raise ActionProposalContextBindingError("field_provenance invalid")
        names=[]
        for item in self.field_provenance:
            if type(item) is not tuple or len(item)!=2: raise ActionProposalContextBindingError("field_provenance invalid")
            field_name,ref=item; _text(field_name,"field_provenance field"); _text(ref,"field_provenance ref"); names.append(field_name)
        if len(names)!=len(set(names)): raise ActionProposalContextBindingError("field_provenance duplicates")
        expected=set(REQUIRED_CONTEXT_FIELDS)
        if self.verifier_agent_id is not None: expected.add("verifier_agent_id")
        if set(names)!=expected: raise ActionProposalContextBindingError("field_provenance must cover exactly supplied semantic fields")
        if tuple(names)!=tuple(sorted(names)): raise ActionProposalContextBindingError("field_provenance must be sorted by field name")
        return self
    def digest(self)->str:
        self.validate(); raw=json.dumps(asdict(self),sort_keys=True,separators=(",",":"),ensure_ascii=False).encode("utf-8"); return sha256(b"LION/ACTION-PROPOSAL-EXPLICIT-CONTEXT/1\0"+raw).hexdigest()
def bind_lair_to_action_proposal(ir: CanonicalActionIR, context: ExplicitActionProposalContext) -> ActionProposal:
    if type(ir) is not CanonicalActionIR: raise ActionProposalContextBindingError("exact CanonicalActionIR required")
    if type(context) is not ExplicitActionProposalContext: raise ActionProposalContextBindingError("exact ExplicitActionProposalContext required")
    ir.validate(); context.validate(); projection=project_lair_to_action_proposal_static(ir)
    if projection.direct_bindings!=DIRECT_BINDINGS: raise ActionProposalContextBindingError("static direct binding set drift")
    if projection.blocked_implicit_mappings!=BLOCKED_IMPLICIT_MAPPINGS: raise ActionProposalContextBindingError("static blocked mapping set drift")
    if context.expected_lair_payload_digest!=ir.payload_digest: raise ActionProposalContextBindingError("context/LAIR payload digest mismatch")
    if projection.action_proposal_payload_digest!=ir.payload_digest: raise ActionProposalContextBindingError("static projection payload binding mismatch")
    try:
        return ActionProposal(proposal_id=context.proposal_id,mission_id=context.mission_id,swarm_id=context.swarm_id,proposer_agent_id=context.proposer_agent_id,capability=context.capability,requested_authority=context.requested_authority,action_class=context.action_class,target=context.target,consequential=context.consequential,evidence_refs=context.evidence_refs,required_observability=context.required_observability,verifier_agent_id=context.verifier_agent_id,payload_digest=ir.payload_digest).validate()
    except Exception as exc: raise ActionProposalContextBindingError("ActionProposal context validation failed") from exc
