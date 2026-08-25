"""Derive bounded non-effectful authority-admission requests from governed proposals."""
from __future__ import annotations

from hashlib import sha256
from typing import Dict, Tuple

from cyber_lion.contracts.governed_change_admission import (
    SCHEMA_VERSION,
    GovernedChangeAdmissionRequest,
    canonical_json,
)
from cyber_lion.contracts.governed_change_proposal import GovernedChangeProposal
from cyber_lion.contracts.policy_gate import GateRequested


class GovernedChangeAdmissionError(RuntimeError):
    pass


_ACTION_AUTHORITY = {
    "BUILD_CANDIDATE": "local_write",
    "RUN_TEST": "local_write",
    "REQUEST_PR": "external_write",
}
_ACTION_MIN_LANE = {action: "AMBER" for action in _ACTION_AUTHORITY}
_LANE_RANK = {"GREEN": 0, "AMBER": 1, "RED": 2}
_EFFECT_METHOD_NAMES = frozenset({
    "execute", "write", "push", "merge", "deploy", "release",
    "create_branch", "create_pr", "dispatch", "issue_grant", "revoke_grant",
})


def _trusted_repository(value: object) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > 512 or "\x00" in value:
        raise GovernedChangeAdmissionError("trusted_repository invalid")
    if value.startswith("/") or ".." in value.split("/") or "*" in value or value.count("/") != 1:
        raise GovernedChangeAdmissionError("trusted_repository invalid")
    return value


def _lane_for(proposal_risk: str, action: str) -> str:
    if proposal_risk not in _LANE_RANK:
        raise GovernedChangeAdmissionError("proposal risk class invalid")
    minimum = _ACTION_MIN_LANE[action]
    return proposal_risk if _LANE_RANK[proposal_risk] >= _LANE_RANK[minimum] else minimum


class GovernedChangeAdmissionEngine:
    """Fail-closed request derivation. This object cannot issue or execute authority."""

    def __init__(self) -> None:
        self._consumed_sources: Dict[Tuple[str, str, str], str] = {}
        self._request_ids: Dict[str, str] = {}
        self._gate_request_ids: Dict[str, str] = {}

    @staticmethod
    def _require_sealed_proposal(proposal: GovernedChangeProposal) -> None:
        if type(proposal) is not GovernedChangeProposal:
            raise GovernedChangeAdmissionError("exact GovernedChangeProposal required")
        proposal.validate()
        if not proposal.proposal_digest:
            raise GovernedChangeAdmissionError("unsealed proposal denied")
        if proposal.proposal_digest != proposal.compute_digest():
            raise GovernedChangeAdmissionError("proposal digest mismatch")
        if proposal.authority_effect != "NONE" or proposal.execution_effect != "NONE":
            raise GovernedChangeAdmissionError("proposal effect assertion denied")
        if "F005" in proposal.target_component.upper() or any(
            "F005" in dep.upper() for dep in proposal.dependency_ids
        ):
            raise GovernedChangeAdmissionError("F005 remains quarantined")

    @staticmethod
    def _request_id(source_key: Tuple[str, str, str]) -> str:
        digest = sha256(b"LION/E004-GCA-REQUEST-ID/1\0" + canonical_json(list(source_key))).hexdigest()
        return f"gca:{digest}"

    @staticmethod
    def _resources(repository: str, proposal: GovernedChangeProposal) -> Tuple[str, ...]:
        resources = tuple(f"repo-path:{repository}:{path}" for path in proposal.candidate_scope)
        if len(resources) != len(proposal.candidate_scope):
            raise GovernedChangeAdmissionError("resource derivation cardinality mismatch")
        return resources

    def derive_request(
        self,
        *,
        proposal: GovernedChangeProposal,
        action_class: str,
        trusted_repository: str,
    ) -> GovernedChangeAdmissionRequest:
        self._require_sealed_proposal(proposal)
        repository = _trusted_repository(trusted_repository)
        if action_class not in _ACTION_AUTHORITY:
            raise GovernedChangeAdmissionError("unsupported or consequential action denied")

        source_key = (proposal.proposal_digest, action_class, repository)
        if source_key in self._consumed_sources:
            raise GovernedChangeAdmissionError("admission request source replay denied")

        request_id = self._request_id(source_key)
        resources = self._resources(repository, proposal)
        request = GovernedChangeAdmissionRequest(
            schema_version=SCHEMA_VERSION,
            request_id=request_id,
            proposal_id=proposal.proposal_id,
            proposal_digest=proposal.proposal_digest,
            epoch_id=proposal.epoch_id,
            source_delta_digest=proposal.source_delta_digest,
            source_epoch_transition_digest=proposal.source_epoch_transition_digest,
            source_memory_head=proposal.source_memory_head,
            source_promotion_digest=proposal.source_promotion_digest,
            repository=repository,
            target_component=proposal.target_component,
            candidate_scope=tuple(proposal.candidate_scope),
            requested_action=action_class,
            requested_resource_scope=resources,
            risk_class=proposal.risk_class,
            lane=_lane_for(proposal.risk_class, action_class),
            requested_authority=_ACTION_AUTHORITY[action_class],
            evidence_refs=tuple(proposal.evidence_refs),
            authority_effect="NONE",
            execution_effect="NONE",
        ).sealed()

        prior = self._request_ids.get(request_id)
        if prior is not None and prior != request.admission_request_digest:
            raise GovernedChangeAdmissionError("request identity substitution denied")
        self._request_ids[request_id] = request.admission_request_digest
        self._consumed_sources[source_key] = request.admission_request_digest
        return request

    def derive_gate_request(
        self,
        *,
        admission_request: GovernedChangeAdmissionRequest,
        gate_request_id: str,
        policy_binding: str,
        authority_lineage_digest: str,
        enterprise_graph_digest: str,
        status_digest: str,
        observability_state: str,
    ) -> GateRequested:
        if type(admission_request) is not GovernedChangeAdmissionRequest:
            raise GovernedChangeAdmissionError("exact admission request required")
        admission_request.validate()
        if not admission_request.admission_request_digest:
            raise GovernedChangeAdmissionError("unsealed admission request denied")
        if admission_request.authority_effect != "NONE" or admission_request.execution_effect != "NONE":
            raise GovernedChangeAdmissionError("effectful admission request denied")
        if not isinstance(gate_request_id, str) or not gate_request_id.strip():
            raise GovernedChangeAdmissionError("fresh gate_request_id required")
        if gate_request_id in self._gate_request_ids:
            raise GovernedChangeAdmissionError("gate request replay denied")

        evidence_refs = tuple(dict.fromkeys((
            admission_request.proposal_digest,
            admission_request.admission_request_digest,
            *admission_request.evidence_refs,
        )))
        gate = GateRequested(
            request_id=gate_request_id,
            proposal_id=admission_request.request_id,
            policy_binding=policy_binding,
            authority_lineage_digest=authority_lineage_digest,
            enterprise_graph_digest=enterprise_graph_digest,
            status_digest=status_digest,
            observability_state=observability_state,
            lane=admission_request.lane,
            requested_authority=admission_request.requested_authority,
            evidence_refs=evidence_refs,
        ).sealed().validate()
        if gate.proposal_id != admission_request.request_id:
            raise GovernedChangeAdmissionError("gate proposal binding mismatch")
        if gate.lane != admission_request.lane or gate.requested_authority != admission_request.requested_authority:
            raise GovernedChangeAdmissionError("gate action/authority binding mismatch")
        self._gate_request_ids[gate_request_id] = gate.request_digest
        return gate

    def state_digest(self) -> str:
        payload = {
            "consumed_sources": [
                {"source": list(source), "request_digest": digest}
                for source, digest in sorted(self._consumed_sources.items())
            ],
            "request_ids": [
                {"request_id": request_id, "request_digest": digest}
                for request_id, digest in sorted(self._request_ids.items())
            ],
            "gate_request_ids": [
                {"gate_request_id": request_id, "gate_digest": digest}
                for request_id, digest in sorted(self._gate_request_ids.items())
            ],
        }
        return sha256(b"LION/E004-GCA-ENGINE-STATE/1\0" + canonical_json(payload)).hexdigest()

    @classmethod
    def assert_no_effect_surface(cls) -> None:
        for name in _EFFECT_METHOD_NAMES:
            if hasattr(cls, name):
                raise GovernedChangeAdmissionError(f"effect surface present: {name}")
