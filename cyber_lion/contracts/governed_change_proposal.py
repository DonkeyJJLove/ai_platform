"""Canonical non-effectful engineering-intent proposal derived from a verified EvolutionDelta."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import re
from typing import Any, Tuple

SCHEMA_VERSION = "1.0.0"
_DOMAIN = b"LION/E004-GOVERNED-CHANGE-PROPOSAL/1\0"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,255}$")
_RISK_CLASSES = frozenset({"GREEN", "AMBER", "RED"})


class GovernedChangeProposalContractError(ValueError):
    pass


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _text(value: Any, name: str, limit: int = 4096) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > limit or "\x00" in value:
        raise GovernedChangeProposalContractError(f"{name} invalid")
    return value


def _id(value: Any, name: str) -> str:
    value = _text(value, name, 256)
    if not _SAFE_ID.fullmatch(value):
        raise GovernedChangeProposalContractError(f"{name} invalid")
    return value


def _digest(value: Any, name: str) -> str:
    value = _text(value, name, 64)
    if not _SHA256.fullmatch(value):
        raise GovernedChangeProposalContractError(f"{name} must be sha256 hex")
    return value


def _refs(value: Any, name: str, *, nonempty: bool = False) -> Tuple[str, ...]:
    if type(value) is not tuple or (nonempty and not value):
        raise GovernedChangeProposalContractError(f"{name} must be tuple")
    for item in value:
        _text(item, name, 1024)
    if len(set(value)) != len(value):
        raise GovernedChangeProposalContractError(f"{name} must be unique")
    return value


def _scope(value: Any) -> Tuple[str, ...]:
    _refs(value, "candidate_scope", nonempty=True)
    for path in value:
        if path.startswith("/") or ".." in path.split("/") or "\\" in path or "\x00" in path:
            raise GovernedChangeProposalContractError("candidate_scope invalid")
    return value


@dataclass(frozen=True)
class GovernedChangeProposal:
    schema_version: str
    proposal_id: str
    epoch_id: str
    source_delta_id: str
    source_delta_digest: str
    source_epoch_transition_digest: str
    source_memory_head: str
    source_promotion_digest: str
    source_pdp_decision_digest: str
    target_component: str
    candidate_scope: Tuple[str, ...]
    dependency_ids: Tuple[str, ...]
    falsification_conditions: Tuple[str, ...]
    evidence_refs: Tuple[str, ...]
    risk_class: str
    authority_effect: str = "NONE"
    execution_effect: str = "NONE"
    proposal_digest: str = ""

    def canonical_payload(self) -> dict[str, Any]:
        value = asdict(self)
        value.pop("proposal_digest")
        for name in ("candidate_scope", "dependency_ids", "falsification_conditions", "evidence_refs"):
            value[name] = list(value[name])
        return value

    def compute_digest(self) -> str:
        return sha256(_DOMAIN + canonical_json(self.canonical_payload())).hexdigest()

    def validate(self) -> "GovernedChangeProposal":
        if self.schema_version != SCHEMA_VERSION:
            raise GovernedChangeProposalContractError("unsupported proposal schema")
        for name in ("proposal_id", "epoch_id", "source_delta_id"):
            _id(getattr(self, name), name)
        for name in (
            "source_delta_digest", "source_epoch_transition_digest", "source_memory_head",
            "source_promotion_digest", "source_pdp_decision_digest",
        ):
            _digest(getattr(self, name), name)
        _text(self.target_component, "target_component")
        _scope(self.candidate_scope)
        _refs(self.dependency_ids, "dependency_ids")
        _refs(self.falsification_conditions, "falsification_conditions", nonempty=True)
        _refs(self.evidence_refs, "evidence_refs", nonempty=True)
        if self.risk_class not in _RISK_CLASSES:
            raise GovernedChangeProposalContractError("invalid risk_class")
        if self.authority_effect != "NONE" or self.execution_effect != "NONE":
            raise GovernedChangeProposalContractError("proposal cannot carry effect authority")
        if self.proposal_digest:
            _digest(self.proposal_digest, "proposal_digest")
            if self.proposal_digest != self.compute_digest():
                raise GovernedChangeProposalContractError("proposal_digest mismatch")
        return self

    def sealed(self) -> "GovernedChangeProposal":
        self.validate()
        return GovernedChangeProposal(**{**asdict(self), "proposal_digest": self.compute_digest()}).validate()
