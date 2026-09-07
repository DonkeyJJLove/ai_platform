from __future__ import annotations

import ast
from dataclasses import replace
from datetime import datetime
from pathlib import Path
import unittest

from cyber_lion.contracts.action_proposal_pdp_handoff import (
    ActionProposalPDPHandoffError,
    CanonicalPDPAdmissionContext,
    handoff_action_proposal_to_canonical_pdp,
)
from cyber_lion.enterprise.complete_mediation import EffectSurfaceScanner
from cyber_lion.enterprise.policy_gate import CanonicalPolicyDecisionPoint, PolicyGateError, PDPResult
from cyber_lion.tests.test_policy_gate import NOW, fixture, graph, status


def context(parts, **changes):
    _, _, key, agents, mission, swarm, _, policy = parts
    values = dict(
        request_id="r19p:request",
        gate_event_id="r19p:gate",
        mission=mission,
        swarm=swarm,
        agents=agents,
        policy=policy,
        authority_key=key,
        graph_projection=graph(),
        status=status(),
        observability_state="HEALTHY",
        observed_event_types=("trace",),
        evidence_refs=("graph:r19p", "status:r19p", "authority:r19p"),
        trusted_now=NOW,
    )
    values.update(changes)
    return CanonicalPDPAdmissionContext(**values)


class CanonicalPDPAdmissionHandoffTests(unittest.TestCase):
    def test_complete_context_reaches_existing_pdp_and_preserves_exact_result(self):
        parts = fixture()
        td, pdp, _, _, _, _, proposal, _ = parts
        out = handoff_action_proposal_to_canonical_pdp(proposal, pdp, context(parts))
        self.assertIs(type(out), PDPResult)
        self.assertEqual(out.applied.decision, "ALLOW")
        self.assertEqual(out.applied.proposal_id, proposal.proposal_id)
        td.cleanup()

    def test_exact_proposal_pdp_and_context_types_are_required(self):
        parts = fixture(); td, pdp, _, _, _, _, proposal, _ = parts; ctx = context(parts)
        with self.assertRaisesRegex(ActionProposalPDPHandoffError, "exact ActionProposal"):
            handoff_action_proposal_to_canonical_pdp({}, pdp, ctx)
        with self.assertRaisesRegex(ActionProposalPDPHandoffError, "exact CanonicalPolicyDecisionPoint"):
            handoff_action_proposal_to_canonical_pdp(proposal, object(), ctx)
        with self.assertRaisesRegex(ActionProposalPDPHandoffError, "exact CanonicalPDPAdmissionContext"):
            handoff_action_proposal_to_canonical_pdp(proposal, pdp, {})
        td.cleanup()

    def test_proposal_mission_and_swarm_substitution_are_denied_before_pdp(self):
        parts = fixture(); td, pdp, _, _, _, _, proposal, _ = parts; ctx = context(parts)
        with self.assertRaisesRegex(ActionProposalPDPHandoffError, "proposal/mission"):
            handoff_action_proposal_to_canonical_pdp(replace(proposal, mission_id="other"), pdp, ctx)
        with self.assertRaisesRegex(ActionProposalPDPHandoffError, "proposal/swarm"):
            handoff_action_proposal_to_canonical_pdp(replace(proposal, swarm_id="other"), pdp, ctx)
        td.cleanup()

    def test_swarm_mission_and_agent_key_identity_substitution_are_denied(self):
        parts = fixture(); td, pdp, _, agents, mission, swarm, proposal, _ = parts
        with self.assertRaisesRegex(ActionProposalPDPHandoffError, "swarm/mission"):
            handoff_action_proposal_to_canonical_pdp(proposal, pdp, context(parts, swarm=replace(swarm, mission_id="other")))
        with self.assertRaisesRegex(ActionProposalPDPHandoffError, "key/AgentSpec"):
            handoff_action_proposal_to_canonical_pdp(proposal, pdp, context(parts, agents={"other": agents["a"]}))
        td.cleanup()

    def test_naive_time_and_missing_evidence_fail_before_pdp(self):
        parts = fixture(); td, pdp, _, _, _, _, proposal, _ = parts
        with self.assertRaisesRegex(ActionProposalPDPHandoffError, "timezone-aware"):
            handoff_action_proposal_to_canonical_pdp(proposal, pdp, context(parts, trusted_now=datetime(2026, 8, 23, 10, 0)))
        with self.assertRaisesRegex(ActionProposalPDPHandoffError, "evidence_refs required"):
            handoff_action_proposal_to_canonical_pdp(proposal, pdp, context(parts, evidence_refs=()))
        td.cleanup()

    def test_pdp_deny_is_returned_unchanged_not_promoted_or_converted(self):
        parts = fixture(requested="external_write")
        td, pdp, _, _, _, _, proposal, _ = parts
        out = handoff_action_proposal_to_canonical_pdp(proposal, pdp, context(parts, observability_state="DEGRADED"))
        self.assertEqual((out.applied.decision, out.applied.effective_authority), ("DENY", "none"))
        td.cleanup()

    def test_existing_pdp_replay_semantics_are_preserved(self):
        parts = fixture(); td, pdp, _, _, _, _, proposal, _ = parts; ctx = context(parts)
        first = handoff_action_proposal_to_canonical_pdp(proposal, pdp, ctx)
        self.assertIs(handoff_action_proposal_to_canonical_pdp(proposal, pdp, ctx), first)
        with self.assertRaises(PolicyGateError):
            handoff_action_proposal_to_canonical_pdp(proposal, pdp, replace(ctx, evidence_refs=("changed",)))
        td.cleanup()

    def test_handoff_has_zero_effect_surface_and_no_runtime_execution_imports(self):
        path = Path("cyber_lion/contracts/action_proposal_pdp_handoff.py")
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        forbidden = {
            "subprocess", "socket", "requests", "runtime_execution", "runtime_enforcement",
            "effect_provider", "executor_sandbox", "executor_provisioning",
        }
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.rsplit(".", 1)[-1])
            elif isinstance(node, ast.Import):
                imported.update(alias.name.rsplit(".", 1)[-1] for alias in node.names)
        self.assertFalse(imported & forbidden)
        names = {node.func.id for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)}
        self.assertFalse(names & {"RuntimeAdmission", "RuntimeExecutionRequest", "RequestedRuntimeEffect"})
        inv = EffectSurfaceScanner().scan(
            repository="DonkeyJJLove/ai_platform", revision="0" * 40, tree_digest="0" * 40,
            sources={str(path): source},
        )
        self.assertEqual(inv.surfaces, ())


if __name__ == "__main__":
    unittest.main()
