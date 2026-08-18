from __future__ import annotations

import unittest

from cyber_lion.enterprise import ActionProposal, AgentSpec, ExecutionControlPlane, MissionSpec, SwarmPlanner
from cyber_lion.enterprise.event_bridge import execution_event, gate_event, proposal_event


class EnterpriseEventBridgeTests(unittest.TestCase):
    def setUp(self):
        self.builder = AgentSpec(
            agent_id="builder",
            version="1.0.0",
            role="builder",
            mission="build",
            capabilities=("code.write",),
            authority_ceiling="external_write",
            observability_events=("DecisionProposed", "OutcomeObserved"),
        )
        self.verifier = AgentSpec(
            agent_id="verifier",
            version="1.0.0",
            role="verifier",
            mission="verify",
            capabilities=("security.verify",),
            is_verifier=True,
        )
        self.mission = MissionSpec(
            mission_id="m1",
            purpose="publish validated artifact",
            required_capabilities=("code.write",),
            authority_ceiling="external_write",
            risk_class="AMBER",
            max_agents=2,
            require_independent_verifier=True,
        )
        self.swarm = SwarmPlanner().plan(self.mission, [self.builder, self.verifier])
        self.proposal = ActionProposal(
            proposal_id="proposal:release-1",
            mission_id="m1",
            swarm_id=self.swarm.swarm_id,
            proposer_agent_id="builder",
            capability="code.write",
            requested_authority="external_write",
            action_class="publish.release",
            target="artifact:release-1",
            evidence_refs=("evidence:tests",),
            required_observability=("DecisionProposed", "OutcomeObserved"),
            verifier_agent_id="verifier",
            payload_digest="sha256:proposal",
        )

    def test_proposal_gate_execution_form_causal_chain(self):
        plane = ExecutionControlPlane()
        proposed = proposal_event(
            self.proposal,
            agent=self.builder,
            occurred_at="2026-08-18T15:00:00+00:00",
            correlation_id="corr:1",
            provenance_upstream=("evidence:tests",),
        )
        self.assertEqual(proposed.event_type, "DecisionProposed")
        self.assertEqual(proposed.authority.effective, "none")

        decision = plane.evaluate(
            proposal=self.proposal,
            mission=self.mission,
            swarm=self.swarm,
            agents={"builder": self.builder, "verifier": self.verifier},
            policy_ids=("policy:release",),
            observed_event_types=("DecisionProposed", "OutcomeObserved"),
            gate_event_id="gate:release-1",
        )
        gated = gate_event(
            decision,
            proposal_event_id=proposed.event_id,
            occurred_at="2026-08-18T15:00:01+00:00",
            correlation_id="corr:1",
        )
        self.assertEqual(gated.event_type, "GateApplied")
        self.assertEqual(gated.causation_id, proposed.event_id)
        self.assertEqual(gated.authority.effective, "external_write")

        receipt = plane.issue_receipt(
            proposal=self.proposal,
            decision=decision,
            executor_agent_id="builder",
            outcome="SUCCEEDED",
            effect_digest="sha256:effect",
            observed_events=("event:effect",),
        )
        executed = execution_event(
            receipt,
            proposal=self.proposal,
            decision=decision,
            occurred_at="2026-08-18T15:00:02+00:00",
            correlation_id="corr:1",
            policy_ids=("policy:release",),
        )
        self.assertEqual(executed.event_type, "ActionExecuted")
        self.assertEqual(executed.causation_id, gated.event_id)
        self.assertEqual(executed.authority.gate_event_id, gated.event_id)
        self.assertEqual(executed.payload["effect_digest"], "sha256:effect")

    def test_proposal_event_requires_real_upstream_provenance(self):
        with self.assertRaises(Exception):
            proposal_event(
                self.proposal,
                agent=self.builder,
                occurred_at="2026-08-18T15:00:00+00:00",
                correlation_id="corr:2",
                provenance_upstream=(),
            )


if __name__ == "__main__":
    unittest.main()
