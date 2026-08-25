"""Derive one non-effectful engineering proposal from one verified evolutionary epoch lineage."""
from __future__ import annotations

from hashlib import sha256
from typing import Dict, Tuple

from cyber_lion.contracts.evolutionary_epoch import EpochTransition
from cyber_lion.contracts.evolutionary_rnd import EvolutionDelta, PromotionDecision, RnDMemoryRecord
from cyber_lion.contracts.governed_change_proposal import (
    SCHEMA_VERSION,
    GovernedChangeProposal,
    canonical_json,
)
from cyber_lion.contracts.policy_gate import GateApplied
from cyber_lion.enterprise.evolutionary_epoch import EvolutionaryEpochEngine


class GovernedChangeProposalError(RuntimeError):
    pass


class GovernedChangeProposalEngine:
    """Fail-closed proposal derivation. It has no effect, authority, or repository API."""

    def __init__(self) -> None:
        self._consumed_sources: Dict[Tuple[str, str, str, str, str], str] = {}
        self._proposal_ids: Dict[str, str] = {}

    @staticmethod
    def _require_sealed(delta: EvolutionDelta, transition: EpochTransition,
                        promotion: PromotionDecision, gate: GateApplied) -> None:
        delta.validate(); transition.validate(); promotion.validate(); gate.validate()
        if not delta.delta_digest:
            raise GovernedChangeProposalError("unsealed EvolutionDelta denied")
        if not transition.transition_digest:
            raise GovernedChangeProposalError("unsealed EpochTransition denied")
        if not promotion.promotion_digest:
            raise GovernedChangeProposalError("unsealed PromotionDecision denied")
        if not gate.decision_digest:
            raise GovernedChangeProposalError("unsealed GateApplied denied")

    @staticmethod
    def _source_key(delta: EvolutionDelta, transition: EpochTransition,
                    promotion: PromotionDecision, gate: GateApplied) -> Tuple[str, str, str, str, str]:
        return (
            delta.delta_digest,
            transition.transition_digest,
            transition.memory_head,
            promotion.promotion_digest,
            gate.decision_digest,
        )

    @staticmethod
    def _proposal_id(source_key: Tuple[str, str, str, str, str]) -> str:
        digest = sha256(b"LION/E004-GCP-ID/1\0" + canonical_json(list(source_key))).hexdigest()
        return f"gcp:{digest}"

    def derive(self, *, delta: EvolutionDelta, transition: EpochTransition,
               promotion: PromotionDecision, gate: GateApplied,
               memory_record: RnDMemoryRecord,
               epoch_engine: EvolutionaryEpochEngine) -> GovernedChangeProposal:
        """Derive exactly one proposal from an already verified, committed epoch lineage."""
        self._require_sealed(delta, transition, promotion, gate)
        memory_record.validate()
        if not memory_record.memory_digest:
            raise GovernedChangeProposalError("unsealed committed memory record denied")
        if not isinstance(epoch_engine, EvolutionaryEpochEngine):
            raise GovernedChangeProposalError("canonical EvolutionaryEpochEngine required")

        if transition.state != "NEXT_EPOCH_CANDIDATE_READY":
            raise GovernedChangeProposalError("epoch is not next-candidate ready")
        if transition.evolution_delta_digest != delta.delta_digest:
            raise GovernedChangeProposalError("transition/delta substitution denied")
        if transition.promotion_digest != promotion.promotion_digest:
            raise GovernedChangeProposalError("transition/promotion substitution denied")
        if promotion.evolution_delta_digest != delta.delta_digest:
            raise GovernedChangeProposalError("promotion/delta substitution denied")
        if promotion.policy_decision_ref != f"pdp:{gate.decision_digest}":
            raise GovernedChangeProposalError("promotion/PDP substitution denied")
        if gate.decision != "ALLOW":
            raise GovernedChangeProposalError("PDP DENY cannot derive proposal")
        if gate.effective_authority != "none":
            raise GovernedChangeProposalError("proposal boundary requires zero PDP effect authority")

        # Reuse the canonical epoch readiness proof instead of duplicating weaker checks.
        try:
            epoch_engine.assert_next_epoch_ready(transition, delta, promotion, memory_record)
        except Exception as exc:
            raise GovernedChangeProposalError("canonical epoch readiness verification failed") from exc

        if "F005" in delta.target_component.upper() or any("F005" in dep.upper() for dep in delta.dependency_ids):
            raise GovernedChangeProposalError("F005 remains quarantined")
        if delta.authority_effect != "NONE" or delta.execution_effect != "NONE":
            raise GovernedChangeProposalError("EvolutionDelta effect assertion denied")

        source_key = self._source_key(delta, transition, promotion, gate)
        if source_key in self._consumed_sources:
            raise GovernedChangeProposalError("governed proposal source replay denied")

        proposal_id = self._proposal_id(source_key)
        proposal = GovernedChangeProposal(
            schema_version=SCHEMA_VERSION,
            proposal_id=proposal_id,
            epoch_id=transition.epoch_id,
            source_delta_id=delta.delta_id,
            source_delta_digest=delta.delta_digest,
            source_epoch_transition_digest=transition.transition_digest,
            source_memory_head=transition.memory_head,
            source_promotion_digest=promotion.promotion_digest,
            source_pdp_decision_digest=gate.decision_digest,
            target_component=delta.target_component,
            candidate_scope=tuple(delta.candidate_scope),
            dependency_ids=tuple(delta.dependency_ids),
            falsification_conditions=tuple(delta.falsification_conditions),
            evidence_refs=tuple(delta.evidence_refs),
            risk_class=delta.risk_class,
            authority_effect="NONE",
            execution_effect="NONE",
        ).sealed()

        prior = self._proposal_ids.get(proposal_id)
        if prior is not None and prior != proposal.proposal_digest:
            raise GovernedChangeProposalError("proposal identity substitution denied")
        self._proposal_ids[proposal_id] = proposal.proposal_digest
        self._consumed_sources[source_key] = proposal.proposal_digest
        return proposal

    def state_digest(self) -> str:
        payload = {
            "consumed_sources": [
                {"source": list(source), "proposal_digest": digest}
                for source, digest in sorted(self._consumed_sources.items())
            ],
            "proposal_ids": [
                {"proposal_id": proposal_id, "proposal_digest": digest}
                for proposal_id, digest in sorted(self._proposal_ids.items())
            ],
        }
        return sha256(b"LION/E004-GCP-ENGINE-STATE/1\0" + canonical_json(payload)).hexdigest()
