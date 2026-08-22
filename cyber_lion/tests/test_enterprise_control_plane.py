from __future__ import annotations

from dataclasses import asdict
from hashlib import sha256
import unittest

from cyber_lion.contracts.agent_registry import AgentRegistryProjection, canonical_json
from cyber_lion.enterprise import (
    ActionProposal,
    AgentSpec,
    EnterpriseModelError,
    ExecutionControlPlane,
    MissionSpec,
    SwarmPlanner,
)


def agent(
    agent_id: str,
    capabilities: tuple[str, ...],
    *,
    authority: str = "read",
    verifier: bool = False,
) -> AgentSpec:
    events = ("DecisionProposed", "GateRequested", "OutcomeObserved") if authority not in {"none", "read"} else ()
    return AgentSpec(
        agent_id=agent_id,
        version="1.0.0",
        role=agent_id,
        mission="enterprise test role",
        capabilities=capabilities,
        authority_ceiling=authority,
        execution_domain="test",
        observability_events=events,
        max_cost_units=1.0,
        is_verifier=verifier,
    )


def registry_projection(mission: MissionSpec, agents: tuple[AgentSpec, ...]) -> AgentRegistryProjection:
    specs = []
    for spec in sorted(agents, key=lambda item: (item.agent_id, item.version)):
        raw = asdict(spec)
        for key, value in list(raw.items()):
            if isinstance(value, tuple):
                raw[key] = list(value)
        specs.append(raw)
    payload = {
        "registry_id": "test-registry",
        "revision": 1,
        "event_head": "0" * 64,
        "mission_id": mission.mission_id,
        "required_capabilities": list(mission.required_capabilities),
        "candidate_specs": specs,
    }
    digest = sha256(canonical_json(payload)).hexdigest()
    return AgentRegistryProjection(
        "test-registry",
        1,
        "0" * 64,
        mission.mission_id,
        mission.required_capabilities,
        tuple(specs),
        digest,
    ).verify_digest()


class ExecutionControlPlaneTests(unittest.TestCase):
    def setUp(self):
        self.plane = ExecutionControlPlane()
        self.builder = agent("builder", ("code.write",), authority="external_write")
        self.verifier = agent("verifier", ("security.verify",), verifier=True)
        self.agents = {item.agent_id: item for item in (self.builder, self.verifier)}
        self.mission = MissionSpec(
            mission_id="release",
            purpose="prepare and validate external release",
            required_capabilities=("code.write",),
            authority_ceiling="external_write",
            risk_class="AMBER",
            max_agents=2,
            require_independent_verifier=True,
            max_total_cost_units=3.0,
        )
        projection = registry_projection(self.mission, (self.builder, self.verifier))
        self.swarm = SwarmPlanner().plan(self.mission, projection)

    def proposal(self, **changes) -> ActionProposal:
        values = dict(
            proposal_id="proposal:1",
            mission_id=self.mission.mission_id,
            swarm_id=self.swarm.swarm_id,
            proposer_agent_id="builder",
            capability="code.write",
            requested_authority="external_write",
            action_class="publish.release",
            target="artifact:test",
            consequential=True,
            evidence_refs=("evidence:test",),
            required_observability=("DecisionProposed", "OutcomeObserved"),
            verifier_agent_id="verifier",
            payload_digest="sha256:test",
        )
        values.update(changes)
        return ActionProposal(**values)

    def test_external_write_is_allowed_only_with_verifier_policy_and_observability(self):
        decision = self.plane.evaluate(
            proposal=self.proposal(),
            mission=self.mission,
            swarm=self.swarm,
            agents=self.agents,
            policy_ids=("policy:release-v1",),
            observed_event_types=("DecisionProposed", "OutcomeObserved"),
            gate_event_id="gate:1",
        )
        self.assertEqual(decision.decision, "ALLOW")
        self.assertEqual(decision.effective_authority, "external_write")
        self.assertEqual(decision.verifier_agent_id, "verifier")

    def test_authority_ceiling_violation_fails_closed(self):
        decision = self.plane.evaluate(
            proposal=self.proposal(requested_authority="privileged"),
            mission=self.mission,
            swarm=self.swarm,
            agents=self.agents,
            policy_ids=("policy:release-v1",),
            observed_event_types=("DecisionProposed", "OutcomeObserved"),
            gate_event_id="gate:2",
        )
        self.assertEqual(decision.decision, "DENY")
        self.assertEqual(decision.effective_authority, "none")

    def test_missing_observability_degrades_to_deny(self):
        decision = self.plane.evaluate(
            proposal=self.proposal(),
            mission=self.mission,
            swarm=self.swarm,
            agents=self.agents,
            policy_ids=("policy:release-v1",),
            observed_event_types=("DecisionProposed",),
            gate_event_id="gate:3",
        )
        self.assertEqual(decision.decision, "DENY")
        self.assertIn("observability", decision.rationale)

    def test_verifier_must_be_independent_and_swarm_admitted(self):
        decision = self.plane.evaluate(
            proposal=self.proposal(verifier_agent_id="builder"),
            mission=self.mission,
            swarm=self.swarm,
            agents=self.agents,
            policy_ids=("policy:release-v1",),
            observed_event_types=("DecisionProposed", "OutcomeObserved"),
            gate_event_id="gate:4",
        )
        self.assertEqual(decision.decision, "DENY")
        self.assertIn("independent verifier", decision.rationale)

    def test_receipt_requires_prior_allow_and_observed_effect(self):
        proposal = self.proposal()
        decision = self.plane.evaluate(
            proposal=proposal,
            mission=self.mission,
            swarm=self.swarm,
            agents=self.agents,
            policy_ids=("policy:release-v1",),
            observed_event_types=("DecisionProposed", "OutcomeObserved"),
            gate_event_id="gate:5",
        )
        receipt = self.plane.issue_receipt(
            proposal=proposal,
            decision=decision,
            executor_agent_id="builder",
            outcome="SUCCEEDED",
            effect_digest="sha256:effect",
            observed_events=("event:action-executed", "event:outcome"),
        )
        self.assertEqual(receipt.gate_event_id, "gate:5")
        self.assertEqual(receipt.outcome, "SUCCEEDED")

    def test_receipt_cannot_be_minted_after_deny(self):
        proposal = self.proposal(requested_authority="privileged")
        decision = self.plane.evaluate(
            proposal=proposal,
            mission=self.mission,
            swarm=self.swarm,
            agents=self.agents,
            policy_ids=("policy:release-v1",),
            observed_event_types=("DecisionProposed", "OutcomeObserved"),
            gate_event_id="gate:6",
        )
        with self.assertRaises(EnterpriseModelError):
            self.plane.issue_receipt(
                proposal=proposal,
                decision=decision,
                executor_agent_id="builder",
                outcome="ABORTED",
                effect_digest="sha256:none",
                observed_events=("event:denied",),
            )

    def test_consequential_proposal_requires_evidence_and_observability_contract(self):
        with self.assertRaises(EnterpriseModelError):
            self.proposal(evidence_refs=()).validate()
        with self.assertRaises(EnterpriseModelError):
            self.proposal(required_observability=()).validate()


if __name__ == "__main__":
    unittest.main()
