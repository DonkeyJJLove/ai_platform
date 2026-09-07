from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
import inspect
import unittest

import cyber_lion.contracts.action_runtime_binding as runtime_binding_module
import cyber_lion.contracts.model_plane_adapter as model_plane_module
from cyber_lion.contracts.action_proposal_context import (
    ExplicitActionProposalContext,
    REQUIRED_CONTEXT_FIELDS,
)
from cyber_lion.contracts.action_runtime_binding import (
    ActionRuntimeBindingError,
    RuntimeBindingCurrentness,
    bind_allowed_action_to_runtime_inputs,
)
from cyber_lion.contracts.executor_provisioning import (
    ExecutorProvisioningRequest,
    ProviderTrustBinding,
    ProvisionedExecutor,
)
from cyber_lion.contracts.model_plane_adapter import (
    ASTRA_RUNTIME_STATUS,
    ModelPlaneAdapterContractError,
    ModelPlaneCandidate,
    ModelPlaneIdentity,
    ModelPlaneRequest,
    validate_model_candidate,
)
from cyber_lion.contracts.policy_gate import GateApplied, GateRequested, PDPDecisionReceipt
from cyber_lion.contracts.runtime_enforcement import PDPSourceTrustBinding
from cyber_lion.enterprise.complete_mediation import EffectSurfaceScanner
from cyber_lion.enterprise.control_plane import ActionProposal
from cyber_lion.enterprise.policy_gate import PDPResult

Z = "0" * 64
F = "f" * 64
POLICY = "policy@1:sha256:" + Z
NOW = datetime(2026, 9, 7, 20, 0, tzinfo=timezone.utc)


def proposal() -> ActionProposal:
    return ActionProposal(
        proposal_id="proposal:r22f",
        mission_id="mission:r22f",
        swarm_id="swarm:r22f",
        proposer_agent_id="agent:r22f",
        capability="read",
        requested_authority="read",
        action_class="READ_FILE",
        target="workspace/input.txt",
        consequential=True,
        evidence_refs=("evidence:r22f",),
        required_observability=("trace",),
        payload_digest=Z,
    ).validate()


def explicit_context() -> ExplicitActionProposalContext:
    p = proposal()
    return ExplicitActionProposalContext(
        proposal_id=p.proposal_id,
        mission_id=p.mission_id,
        swarm_id=p.swarm_id,
        proposer_agent_id=p.proposer_agent_id,
        capability=p.capability,
        requested_authority=p.requested_authority,
        action_class=p.action_class,
        target=p.target,
        consequential=p.consequential,
        evidence_refs=p.evidence_refs,
        required_observability=p.required_observability,
        expected_lair_payload_digest=Z,
        field_provenance=tuple(
            (name, "evidence:" + name) for name in sorted(REQUIRED_CONTEXT_FIELDS)
        ),
    ).validate()


def pdp_result(*, decision: str = "ALLOW") -> PDPResult:
    p = proposal()
    requested = GateRequested(
        "request:r22f",
        p.proposal_id,
        POLICY,
        Z,
        Z,
        Z,
        "HEALTHY",
        "GREEN",
        p.requested_authority,
        ("evidence:r22f",),
    ).sealed()
    applied = GateApplied(
        "gate:r22f",
        requested.request_id,
        p.proposal_id,
        decision,
        p.requested_authority if decision == "ALLOW" else "none",
        POLICY,
        Z,
        Z,
        Z,
        "HEALTHY",
        "GREEN",
        "canonical",
    ).sealed()
    receipt = PDPDecisionReceipt(
        "receipt:r22f",
        requested.request_id,
        applied.gate_event_id,
        requested.request_digest,
        applied.decision_digest,
        Z,
    ).validate()
    return PDPResult(requested, applied, receipt)


def provisioned() -> ProvisionedExecutor:
    trust = ProviderTrustBinding("provider", "provider:1", Z, "provider-anchor", Z).validate()
    request = ExecutorProvisioningRequest(
        "1.0.0",
        "provision:r22f",
        "idem:r22f",
        "drone:r22f",
        "executor:r22f",
        "mission:r22f",
        "mission:parent",
        "DonkeyJJLove/ai_platform",
        "a" * 40,
        "b" * 40,
        "mission/r22f",
        ("cyber_lion",),
        ("cyber_lion/contracts/action_runtime_binding.py",),
        "python",
        Z,
        Z,
        Z,
        (),
        NOW.isoformat(),
    ).validate()
    return ProvisionedExecutor(
        "1.0.0",
        "provisioned:r22f",
        request.request_id,
        request.digest(),
        request.idempotency_key,
        request.drone_id,
        request.executor_id,
        "runtime:r22f",
        "sandbox:r22f",
        "workspace:r22f",
        request.mission_id,
        request.parent_mission_id,
        request.repository,
        request.baseline_sha,
        request.baseline_tree_sha,
        request.branch,
        request.read_scope,
        request.write_scope,
        request.runtime_class,
        request.image_digest,
        request.sandbox_profile_digest,
        request.resource_profile_digest,
        (),
        trust.provider_id,
        trust.provider_instance_id,
        trust.implementation_digest,
        trust.trust_anchor_id,
        trust.trust_anchor_digest,
        Z,
        "provider:evidence",
        NOW.isoformat(),
    ).validate_for(request, trust)


def currentness() -> RuntimeBindingCurrentness:
    return RuntimeBindingCurrentness(
        PDPSourceTrustBinding("pdp", "pdp:1", Z, "pdp-anchor", Z).validate(),
        NOW,
        NOW - timedelta(minutes=1),
        NOW + timedelta(minutes=10),
    ).validate()


class ActionRuntimeBindingTests(unittest.TestCase):
    def test_allow_materializes_only_exact_inert_runtime_inputs(self):
        effect, identity, evidence = bind_allowed_action_to_runtime_inputs(
            proposal(), explicit_context(), pdp_result(), currentness(), provisioned()
        )
        effect.validate()
        identity.validate()
        evidence.validate()
        self.assertEqual(effect.proposal_id, "proposal:r22f")
        self.assertEqual(effect.runtime_identity_digest, identity.digest())
        self.assertEqual(evidence.proposal_id, effect.proposal_id)

    def test_deny_cannot_be_materialized(self):
        with self.assertRaises(ActionRuntimeBindingError):
            bind_allowed_action_to_runtime_inputs(
                proposal(), explicit_context(), pdp_result(decision="DENY"), currentness(), provisioned()
            )

    def test_context_substitution_is_denied(self):
        bad = replace(explicit_context(), target="workspace/other.txt")
        with self.assertRaises(ActionRuntimeBindingError):
            bind_allowed_action_to_runtime_inputs(
                proposal(), bad, pdp_result(), currentness(), provisioned()
            )

    def test_stale_currentness_is_denied(self):
        stale = replace(currentness(), expires_at=NOW)
        with self.assertRaises(ActionRuntimeBindingError):
            bind_allowed_action_to_runtime_inputs(
                proposal(), explicit_context(), pdp_result(), stale, provisioned()
            )

    def test_binder_exposes_no_effect_surface(self):
        inventory = EffectSurfaceScanner().scan(
            repository="DonkeyJJLove/ai_platform",
            revision="a" * 40,
            tree_digest="b" * 40,
            sources={
                "cyber_lion/contracts/action_runtime_binding.py": inspect.getsource(runtime_binding_module)
            },
        )
        self.assertEqual(inventory.surfaces, ())
        self.assertEqual(inventory.unclassified_refs, ())


class ModelPlaneAdapterTests(unittest.TestCase):
    def test_astra_target_is_compatibility_only_and_non_effectful(self):
        identity = ModelPlaneIdentity("provider:test", "model:test", Z).validate()
        self.assertEqual(identity.runtime_status, ASTRA_RUNTIME_STATUS)
        request = ModelPlaneRequest(
            "model-request:r22f",
            identity.digest(),
            Z,
            F,
            "ACTION_PROPOSAL_CANDIDATE",
            "canonical-pdp",
            "provider-adapter",
            ("ACTION_PROPOSAL_CANDIDATE", "BLUEPRINT_CANDIDATE"),
        ).validate()
        candidate = ModelPlaneCandidate(
            request.request_id,
            request.digest(),
            identity.digest(),
            request.requested_output_kind,
            Z,
        ).validate()
        self.assertIs(validate_model_candidate(identity, request, candidate), candidate)
        self.assertEqual(candidate.authority_effect, "NONE")
        self.assertEqual(candidate.runtime_effect, "NONE")

    def test_model_candidate_cannot_claim_authority(self):
        identity = ModelPlaneIdentity("provider:test", "model:test", Z).validate()
        request = ModelPlaneRequest(
            "model-request:r22f",
            identity.digest(),
            Z,
            F,
            "BLUEPRINT_CANDIDATE",
            "deterministic-boundary",
            "inference-boundary",
            ("BLUEPRINT_CANDIDATE",),
        ).validate()
        with self.assertRaises(ModelPlaneAdapterContractError):
            ModelPlaneCandidate(
                request.request_id,
                request.digest(),
                identity.digest(),
                request.requested_output_kind,
                Z,
                authority_effect="read",
            ).validate()

    def test_model_contract_exposes_no_effect_surface(self):
        inventory = EffectSurfaceScanner().scan(
            repository="DonkeyJJLove/ai_platform",
            revision="a" * 40,
            tree_digest="b" * 40,
            sources={
                "cyber_lion/contracts/model_plane_adapter.py": inspect.getsource(model_plane_module)
            },
        )
        self.assertEqual(inventory.surfaces, ())
        self.assertEqual(inventory.unclassified_refs, ())


if __name__ == "__main__":
    unittest.main()
