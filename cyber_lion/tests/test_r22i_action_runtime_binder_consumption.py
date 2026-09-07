from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
import inspect
from unittest.mock import patch
import unittest

import cyber_lion.enterprise.runtime_enforcement as runtime_enforcement_module
from cyber_lion.contracts.action_proposal_context import (
    ExplicitActionProposalContext,
    REQUIRED_CONTEXT_FIELDS,
)
from cyber_lion.contracts.action_runtime_binding import (
    RuntimeBindingCurrentness,
    bind_allowed_action_to_runtime_inputs,
)
from cyber_lion.contracts.executor_provisioning import (
    ExecutorProvisioningRequest,
    ProviderTrustBinding,
    ProvisionedExecutor,
)
from cyber_lion.contracts.policy_gate import GateApplied, GateRequested, PDPDecisionReceipt
from cyber_lion.contracts.runtime_enforcement import PDPSourceTrustBinding
from cyber_lion.enterprise.complete_mediation import EffectSurfaceScanner
from cyber_lion.enterprise.control_plane import ActionProposal
from cyber_lion.enterprise.live_authority_admission import LiveAdmittedAuthority, LiveAuthorityAdmission
from cyber_lion.enterprise.policy_gate import PDPResult
from cyber_lion.enterprise.runtime_enforcement import (
    InMemoryRuntimeAdmissionReplayGuard,
    RuntimeAdmissionEngine,
    RuntimeEnforcementError,
)

Z = "0" * 64
F = "f" * 64
POLICY = "policy@1:sha256:" + Z
NOW = datetime(2026, 9, 7, 20, 0, tzinfo=timezone.utc)


def proposal() -> ActionProposal:
    return ActionProposal(
        "proposal:r22i",
        "mission:r22i",
        "swarm:r22i",
        "agent:r22i",
        "read",
        "read",
        "READ_FILE",
        "workspace/input.txt",
        True,
        ("evidence:r22i",),
        ("trace",),
        payload_digest=Z,
    ).validate()


def context() -> ExplicitActionProposalContext:
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


def pdp_result(*, decision: str = "ALLOW", replay_key: str = Z) -> PDPResult:
    p = proposal()
    requested = GateRequested(
        "request:r22i",
        p.proposal_id,
        POLICY,
        Z,
        Z,
        Z,
        "HEALTHY",
        "GREEN",
        p.requested_authority,
        ("evidence:r22i",),
    ).sealed()
    applied = GateApplied(
        "gate:r22i",
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
        "receipt:r22i",
        requested.request_id,
        applied.gate_event_id,
        requested.request_digest,
        applied.decision_digest,
        replay_key,
    ).validate()
    return PDPResult(requested, applied, receipt)


def source_trust() -> PDPSourceTrustBinding:
    return PDPSourceTrustBinding("pdp", "pdp:1", Z, "pdp-anchor", Z).validate()


def currentness() -> RuntimeBindingCurrentness:
    return RuntimeBindingCurrentness(
        source_trust(),
        NOW,
        NOW - timedelta(minutes=1),
        NOW + timedelta(minutes=10),
    ).validate()


def provisioning(*, drone_id: str = "drone:r22i", mission_id: str = "mission:r22i"):
    trust = ProviderTrustBinding("provider", "provider:1", Z, "provider-anchor", Z).validate()
    request = ExecutorProvisioningRequest(
        "1.0.0",
        "provision:r22i:" + drone_id,
        "idem:r22i:" + drone_id,
        drone_id,
        "executor:r22i",
        mission_id,
        "mission:parent",
        "DonkeyJJLove/ai_platform",
        "a" * 40,
        "b" * 40,
        "mission/r22i",
        ("cyber_lion",),
        ("cyber_lion/contracts/action_runtime_binding.py",),
        "python",
        Z,
        Z,
        Z,
        (),
        NOW.isoformat(),
    ).validate()
    provisioned = ProvisionedExecutor(
        "1.0.0",
        "provisioned:r22i:" + drone_id,
        request.request_id,
        request.digest(),
        request.idempotency_key,
        request.drone_id,
        request.executor_id,
        "runtime:r22i:" + drone_id,
        "sandbox:r22i",
        "workspace:r22i",
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
    return request, trust, provisioned


def authority() -> LiveAdmittedAuthority:
    return LiveAdmittedAuthority(
        repository="DonkeyJJLove/ai_platform",
        pr_number=1,
        base_sha="a" * 40,
        head_sha="b" * 40,
        mission_id="mission:r22i",
        grant_id="grant:r22i",
        lineage_digest=Z,
        provenance_id="provenance:r22i",
        epoch=1,
        epoch_state_version=1,
        authority_ceiling="external_write",
        root_grant_id="grant:r22i",
        root_grant_digest=Z,
        authenticated_grant_digests=(Z,),
        leaf_key_id="key:r22i",
        leaf_algorithm="ed25519",
        replay_digest=Z,
        admitted_at=(NOW - timedelta(minutes=2)).isoformat(),
    ).validate()


class FakeAdmission(LiveAuthorityAdmission):
    def revalidate(self, admitted, *, now):
        return admitted


class FakePDPSource:
    source_id = "pdp"
    source_instance_id = "pdp:1"
    implementation_digest = Z
    trust_anchor_id = "pdp-anchor"
    trust_anchor_digest = Z

    def __init__(self, evidence):
        self.evidence = evidence

    def resolve(self, request_id, gate_event_id):
        return self.evidence

    def current_policy_binding(self, policy_binding):
        return policy_binding


def engine_for(p, c, result, cur, provisioned):
    _, _, evidence = bind_allowed_action_to_runtime_inputs(p, c, result, cur, provisioned)
    return RuntimeAdmissionEngine(
        authority_admission=FakeAdmission(),
        pdp_source=FakePDPSource(evidence),
        pdp_source_trust=source_trust(),
        replay_guard=InMemoryRuntimeAdmissionReplayGuard(),
    )


def admit(eng=None, *, p=None, c=None, result=None, cur=None, prov=None, auth=None):
    p = p or proposal()
    c = c or context()
    result = result or pdp_result()
    cur = cur or currentness()
    req, trust, pe = prov or provisioning()
    eng = eng or engine_for(p, c, result, cur, pe)
    return eng.admit_bound_action(
        proposal=p,
        context=c,
        pdp_result=result,
        currentness=cur,
        admitted_authority=auth or authority(),
        provisioned_executor=pe,
        provisioning_request=req,
        provider_trust=trust,
        trusted_now=NOW,
    )


class R22IActionRuntimeBinderConsumptionTests(unittest.TestCase):
    def test_exact_allow_path_consumes_binder_outputs_into_runtime_admission(self):
        p = proposal()
        c = context()
        result = pdp_result()
        cur = currentness()
        req, trust, pe = provisioning()
        effect, identity, evidence = bind_allowed_action_to_runtime_inputs(p, c, result, cur, pe)
        eng = engine_for(p, c, result, cur, pe)
        out = admit(eng, p=p, c=c, result=result, cur=cur, prov=(req, trust, pe))
        out.validate()
        self.assertEqual(out.requested_effect_digest, effect.digest())
        self.assertEqual(out.runtime_identity_digest, identity.digest())
        self.assertEqual(out.pdp_evidence_digest, evidence.evidence_digest)

    def test_deny_never_reaches_runtime_admission(self):
        allow = pdp_result()
        p = proposal()
        c = context()
        cur = currentness()
        req, trust, pe = provisioning()
        eng = engine_for(p, c, allow, cur, pe)
        with self.assertRaises(RuntimeEnforcementError):
            admit(eng, p=p, c=c, result=pdp_result(decision="DENY"), cur=cur, prov=(req, trust, pe))

    def test_stale_binder_currentness_is_denied(self):
        p = proposal()
        c = context()
        result = pdp_result()
        cur = currentness()
        req, trust, pe = provisioning()
        eng = engine_for(p, c, result, cur, pe)
        stale = replace(cur, expires_at=NOW)
        with self.assertRaises(RuntimeEnforcementError):
            admit(eng, p=p, c=c, result=result, cur=stale, prov=(req, trust, pe))

    def test_binder_and_admission_trusted_time_must_be_identical(self):
        p = proposal()
        c = context()
        result = pdp_result()
        cur = currentness()
        req, trust, pe = provisioning()
        eng = engine_for(p, c, result, cur, pe)
        shifted = replace(cur, trusted_now=NOW + timedelta(seconds=1))
        with self.assertRaises(RuntimeEnforcementError):
            eng.admit_bound_action(
                proposal=p,
                context=c,
                pdp_result=result,
                currentness=shifted,
                admitted_authority=authority(),
                provisioned_executor=pe,
                provisioning_request=req,
                provider_trust=trust,
                trusted_now=NOW,
            )

    def test_action_resource_payload_authority_and_context_substitutions_are_denied(self):
        p = proposal()
        result = pdp_result()
        cur = currentness()
        req, trust, pe = provisioning()
        eng = engine_for(p, context(), result, cur, pe)
        mutations = (
            replace(context(), action_class="WRITE_FILE"),
            replace(context(), target="workspace/other.txt"),
            replace(context(), expected_lair_payload_digest=F),
            replace(context(), requested_authority="external_write"),
        )
        for bad in mutations:
            with self.subTest(bad=bad):
                with self.assertRaises(RuntimeEnforcementError):
                    admit(eng, p=p, c=bad, result=result, cur=cur, prov=(req, trust, pe))

    def test_mission_and_provisioning_substitution_are_denied(self):
        p = proposal()
        c = context()
        result = pdp_result()
        cur = currentness()
        good = provisioning()
        eng = engine_for(p, c, result, cur, good[2])
        with self.assertRaises(RuntimeEnforcementError):
            admit(eng, p=p, c=c, result=result, cur=cur, prov=provisioning(mission_id="mission:other"))
        with self.assertRaises(RuntimeEnforcementError):
            admit(eng, p=p, c=c, result=result, cur=cur, prov=provisioning(drone_id="drone:other"))

    def test_runtime_identity_substitution_from_binder_is_denied(self):
        p = proposal()
        c = context()
        result = pdp_result()
        cur = currentness()
        req, trust, pe = provisioning()
        effect, identity, evidence = bind_allowed_action_to_runtime_inputs(p, c, result, cur, pe)
        eng = engine_for(p, c, result, cur, pe)
        bad_identity = replace(identity, runtime_instance_id="runtime:other")
        bad_effect = replace(effect, runtime_identity_digest=bad_identity.digest())
        with patch.object(
            runtime_enforcement_module,
            "bind_allowed_action_to_runtime_inputs",
            return_value=(bad_effect, bad_identity, evidence),
        ):
            with self.assertRaises(RuntimeEnforcementError):
                admit(eng, p=p, c=c, result=result, cur=cur, prov=(req, trust, pe))

    def test_pdp_receipt_substitution_is_denied_against_canonical_source(self):
        p = proposal()
        c = context()
        canonical = pdp_result()
        cur = currentness()
        req, trust, pe = provisioning()
        eng = engine_for(p, c, canonical, cur, pe)
        forged = pdp_result(replay_key=F)
        with self.assertRaises(RuntimeEnforcementError):
            admit(eng, p=p, c=c, result=forged, cur=cur, prov=(req, trust, pe))

    def test_replay_cannot_create_second_runtime_admission(self):
        p = proposal()
        c = context()
        result = pdp_result()
        cur = currentness()
        req, trust, pe = provisioning()
        eng = engine_for(p, c, result, cur, pe)
        admit(eng, p=p, c=c, result=result, cur=cur, prov=(req, trust, pe))
        with self.assertRaises(RuntimeEnforcementError):
            admit(eng, p=p, c=c, result=result, cur=cur, prov=(req, trust, pe))

    def test_high_level_path_accepts_no_caller_effect_or_runtime_identity(self):
        params = inspect.signature(RuntimeAdmissionEngine.admit_bound_action).parameters
        self.assertNotIn("effect", params)
        self.assertNotIn("runtime_identity", params)
        self.assertIn("pdp_result", params)
        self.assertIn("context", params)

    def test_integration_adds_no_effect_surface_or_alternate_executor(self):
        source = inspect.getsource(runtime_enforcement_module)
        inventory = EffectSurfaceScanner().scan(
            repository="DonkeyJJLove/ai_platform",
            revision="a" * 40,
            tree_digest="b" * 40,
            sources={"cyber_lion/enterprise/runtime_enforcement.py": source},
        )
        self.assertEqual(inventory.surfaces, ())
        self.assertEqual(inventory.unclassified_refs, ())
        method_source = inspect.getsource(RuntimeAdmissionEngine.admit_bound_action)
        self.assertNotIn("RuntimeExecutionEngine", method_source)
        self.assertNotIn(".execute(", method_source)


if __name__ == "__main__":
    unittest.main()
