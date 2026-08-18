from __future__ import annotations

import unittest

from cyber_lion.enterprise import (
    AgentSpec,
    EnterpriseModelError,
    MissionSpec,
    MosaicDelta,
    SwarmPlanner,
)


def agent(
    agent_id: str,
    capabilities: tuple[str, ...],
    *,
    authority: str = "read",
    cost: float = 1.0,
    verifier: bool = False,
    memory_write: bool = False,
    memory_policies: tuple[str, ...] = (),
) -> AgentSpec:
    events = ("DecisionProposed", "OutcomeObserved") if authority not in {"none", "read"} else ()
    return AgentSpec(
        agent_id=agent_id,
        version="1.0.0",
        role=agent_id,
        mission="mission-bound template",
        capabilities=capabilities,
        authority_ceiling=authority,
        execution_domain="test",
        observability_events=events,
        memory_write=memory_write,
        memory_policy_ids=memory_policies,
        max_cost_units=cost,
        is_verifier=verifier,
    )


class AgentContractTests(unittest.TestCase):
    def test_memory_write_requires_policy(self):
        with self.assertRaises(EnterpriseModelError):
            agent("memory", ("memory.write",), memory_write=True).validate()

    def test_consequential_authority_requires_observability(self):
        spec = AgentSpec(
            agent_id="builder",
            version="1",
            role="builder",
            mission="build",
            capabilities=("code.write",),
            authority_ceiling="local_write",
            observability_events=(),
        )
        with self.assertRaises(EnterpriseModelError):
            spec.validate()

    def test_memory_write_with_policy_is_valid(self):
        spec = agent(
            "memory",
            ("memory.write",),
            memory_write=True,
            memory_policies=("memory-policy-v1",),
        )
        self.assertIs(spec.validate(), spec)


class SwarmPlannerTests(unittest.TestCase):
    def setUp(self):
        self.planner = SwarmPlanner()
        self.catalog = [
            agent("research", ("research", "hypothesis"), cost=0.6),
            agent("architect", ("architecture", "code"), authority="local_write", cost=0.8),
            agent("security", ("security", "validation"), cost=0.7, verifier=True),
            agent("code-only", ("code",), authority="local_write", cost=0.5),
        ]

    def test_planner_builds_minimal_sufficient_mosaic(self):
        mission = MissionSpec(
            mission_id="m1",
            purpose="design and validate software",
            required_capabilities=("research", "architecture", "code", "security", "validation"),
            authority_ceiling="local_write",
            risk_class="AMBER",
            max_agents=4,
            max_total_cost_units=4.0,
        )
        swarm = self.planner.plan(mission, self.catalog)
        self.assertEqual(set(swarm.covered_capabilities), set(mission.required_capabilities))
        self.assertIn("research", swarm.member_agent_ids)
        self.assertIn("architect", swarm.member_agent_ids)
        self.assertIn("security", swarm.member_agent_ids)
        self.assertNotIn("code-only", swarm.member_agent_ids)
        self.assertEqual(swarm.topology, "hub_spoke_with_verifier")

    def test_missing_capability_fails_closed(self):
        mission = MissionSpec(
            mission_id="missing",
            purpose="need unavailable capability",
            required_capabilities=("research", "financial.audit"),
        )
        with self.assertRaises(EnterpriseModelError):
            self.planner.plan(mission, self.catalog)

    def test_red_mission_requires_independent_verifier(self):
        mission = MissionSpec(
            mission_id="red",
            purpose="privileged change",
            required_capabilities=("architecture", "code"),
            authority_ceiling="deploy",
            risk_class="RED",
            max_agents=3,
        )
        without_verifier = [item for item in self.catalog if not item.is_verifier]
        with self.assertRaises(EnterpriseModelError):
            self.planner.plan(mission, without_verifier)

        swarm = self.planner.plan(mission, self.catalog)
        self.assertTrue(swarm.verifier_agent_ids)
        self.assertEqual(swarm.topology, "segmented_peer_review")

    def test_budget_is_enforced(self):
        mission = MissionSpec(
            mission_id="budget",
            purpose="too small budget",
            required_capabilities=("research", "architecture"),
            authority_ceiling="local_write",
            max_total_cost_units=0.5,
        )
        with self.assertRaises(EnterpriseModelError):
            self.planner.plan(mission, self.catalog)


class MosaicDeltaTests(unittest.TestCase):
    def test_authority_expansion_requires_gate(self):
        delta = MosaicDelta(
            delta_id="d1",
            swarm_id="s1",
            authority_before="read",
            authority_after="external_write",
            reason="mission now requires external validation",
            evidence_refs=("evidence:1",),
        )
        with self.assertRaises(EnterpriseModelError):
            delta.validate()

    def test_authority_expansion_with_gate_is_explicit(self):
        delta = MosaicDelta(
            delta_id="d2",
            swarm_id="s1",
            authority_before="read",
            authority_after="external_write",
            reason="approved external validation",
            evidence_refs=("evidence:1",),
            gate_event_id="gate:123",
        )
        self.assertIs(delta.validate(), delta)

    def test_delta_requires_evidence(self):
        with self.assertRaises(EnterpriseModelError):
            MosaicDelta(
                delta_id="d3",
                swarm_id="s1",
                reason="unreferenced topology change",
            ).validate()


if __name__ == "__main__":
    unittest.main()
