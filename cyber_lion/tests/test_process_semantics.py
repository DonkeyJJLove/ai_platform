from __future__ import annotations

import unittest

from cyber_lion.contracts.action_ir import CanonicalActionIR
from cyber_lion.contracts.action_proposal_context import ExplicitActionProposalContext, REQUIRED_CONTEXT_FIELDS, bind_lair_to_action_proposal
from cyber_lion.contracts.process_action import ActionIntentCandidate, ProcessTransitionOutcome
from cyber_lion.contracts.process_ir import CanonicalProcessIR, CurrentnessBasis, ProcessContextSnapshot
from cyber_lion.contracts.runtime_currentness import EffectTimeCurrentnessEvidence
from cyber_lion.contracts.runtime_enforcement import CanonicalPDPDecisionEvidence, RequestedRuntimeEffect, RuntimeAdmission, RuntimeIdentityBinding
from cyber_lion.contracts.runtime_execution import RuntimeExecutionReceipt
from cyber_lion.contracts.runtime_reconciliation import RuntimeEffectObservation, RuntimeReconciliationReceipt
from cyber_lion.enterprise.process_outcome_evidence import CanonicalDownstreamEvidence
from cyber_lion.enterprise.process_semantics import ProcessSemanticError, TransitionSelector, apply_transition_outcome


def process_model(action: bool = True):
    return {
        "schema_version":"1.0.0","process_id":"process:semantics","mission_ref":"mission:semantics","goal_ref":"goal:semantics",
        "scope":{"domains":["repository"],"resources":["repo:x/y"],"widening_allowed":False},"initial_state":"READY","states":["READY","DONE"],
        "dependencies":[{"dependency_id":"dep:baseline","required":True,"description":"exact baseline"}],
        "transitions":[{"transition_id":"advance","transition_class":"ACTION_REQUIRED" if action else "INTERNAL","source_states":["READY"],"trigger":"continue","dependencies":["dep:baseline"],"guards":["guard:scope"],"evidence_requirements":["evidence:verified"],"currentness_requirements":["currentness:exact"],"authority_requirements":["authority-context:write"] if action else [],"operator":"EMIT_ACTION_INTENT" if action else "VERIFY","expected_postconditions":["postcondition:done"],"outcome_map":{"PASS":"DONE","FAIL":"STOP","UNKNOWN":"HANDOFF","DRIFT":"HANDOFF","AUTHORITY_BOUNDARY":"HANDOFF"},"retry_policy":{"max_attempts":0,"on_exhausted":"HANDOFF"},"replay_policy":"DENY","idempotency_class":"IDEMPOTENT" if action else "PURE","resource_claims":{"read_scopes":["repo:x/y"],"write_scopes":["repo:x/y:candidate"] if action else [],"authority_budgets":["authority-context:write"] if action else [],"currentness_subjects":["currentness:exact"],"replay_domain":"semantics:advance","reconciliation_group":"semantics"}}],
        "scheduling_policy":{"strategy":"DECLARED_ORDER","order":["advance"],"priorities":{"advance":0},"max_wip":1,"parallel_safe_groups":[]},
        "termination_policy":{"terminal_states":["DONE"],"allow_no_legal_transition":False,"on_unknown":"HANDOFF"},"lineage":{"parent_process_digests":[],"generation":0,"source_refs":["test"]}}


def current_basis(state: str = "CURRENT"):
    return CurrentnessBasis(requirement_id="currentness:exact",subject="currentness:exact",observed_identity="git:exact-head",evidence_ref="evidence:git-readback",observed_at="2026-09-08T00:00:00+02:00",state=state,drift_rule="IDENTITY_CHANGED").sealed()


def context(ir: CanonicalProcessIR, *, authority=True, currentness=True):
    return ProcessContextSnapshot(process_ir_digest=ir.process_digest,process_state="READY",satisfied_dependencies=("dep:baseline",),satisfied_guards=("guard:scope",),satisfied_evidence_requirements=("evidence:verified",),satisfied_currentness_requirements=("currentness:exact",),currentness_bases=(current_basis(),) if currentness else (),verified_authority_context_refs=("authority-context:write",) if authority else (),observed_at="2026-09-08T00:00:00+02:00").validate_for(ir)


def canonical_action_pass(ir: CanonicalProcessIR, decision, basis: CurrentnessBasis, *, next_state: str = "DONE"):
    action_intent = ActionIntentCandidate(
        process_id="process:semantics",
        process_ir_digest=ir.process_digest,
        transition_id="advance",
        mission_ref="mission:semantics",
        intent="prepare bounded repository candidate",
        target_class="repository",
        required_capability="repository.prepare_candidate",
        authority_requirement="authority-context:write",
        process_scope_digest="1"*64,
        expected_process_outcome="candidate-prepared",
        evidence_context_refs=("evidence:verified",),
        currentness_context_refs=(basis.basis_digest,),
    ).sealed()
    action_ir = CanonicalActionIR.from_mapping({
        "schema_version":"1.0.0",
        "action_id":"action.lpcl-test",
        "kind":"filesystem.write",
        "intent_ref":action_intent.action_intent_digest,
        "mission_ref":"mission:semantics",
        "autonomy_ref":"autonomy:lpcl-test",
        "bean_ref":"bean:lpcl-test",
        "target":{"host":"test-host","environment":"test","runtime":"bounded-sandbox"},
        "authority_request":{"domain":"repository","capability":"repository.prepare_candidate","grant_ref":None},
        "boundary":{"shell":False,"network":"DENY","filesystem_read":[],"filesystem_write":["repo:x/y:candidate"],"process_children":[],"timeout_ms":1000,"max_processes":1,"memory_limit_bytes":1048576},
        "preconditions":["process-transition-selected"],
        "expected_effects":["candidate-write"],
        "forbidden_effects":["authority-change"],
        "observation":{"observer_class":"deterministic_independent","required_events":["effect.observed"]},
        "reconciliation":{"mode":"EXACT","receipt":"REQUIRED"},
    })
    proposal_context = ExplicitActionProposalContext(
        proposal_id="proposal:lpcl-test",
        mission_id="mission:semantics",
        swarm_id="swarm:lpcl-test",
        proposer_agent_id="agent:lpcl-test",
        capability="repository.prepare_candidate",
        requested_authority="local_write",
        action_class="WRITE_FILE",
        target="repo:x/y:candidate",
        consequential=True,
        evidence_refs=("evidence:verified",),
        required_observability=("effect.observed",),
        expected_lair_payload_digest=action_ir.payload_digest,
        field_provenance=tuple((name,f"evidence:proposal:{name}") for name in sorted(REQUIRED_CONTEXT_FIELDS)),
    )
    proposal = bind_lair_to_action_proposal(action_ir, proposal_context)
    pdp = CanonicalPDPDecisionEvidence(
        request_id="request:lpcl-test",gate_event_id="gate:lpcl-test",proposal_id=proposal.proposal_id,
        gate_decision_digest="2"*64,pdp_receipt_digest="3"*64,request_digest="4"*64,replay_key="5"*64,
        policy_binding="policy:lpcl-test",authority_lineage_digest="6"*64,observability_state="HEALTHY",
        source_id="pdp-source",source_instance_id="pdp-instance",source_implementation_digest="7"*64,
        trust_anchor_id="pdp-anchor",trust_anchor_digest="8"*64,
        issued_at="2026-09-08T00:00:00+02:00",expires_at="2026-09-08T01:00:00+02:00",
    ).sealed()
    identity = RuntimeIdentityBinding(
        workload_identity="workload:lpcl-test",execution_subject="subject:lpcl-test",runtime_instance_id="runtime:lpcl-test",
        sandbox_id="sandbox:lpcl-test",workspace_id="workspace:lpcl-test",runtime_attestation_digest="9"*64,provisioned_executor_digest="a"*64,
    ).validate()
    requested_effect = RequestedRuntimeEffect(
        effect_id="effect-request:lpcl-test",proposal_id=proposal.proposal_id,mission_id=proposal.mission_id,
        policy_binding=pdp.policy_binding,authority_lineage_digest=pdp.authority_lineage_digest,requested_authority=proposal.requested_authority,
        action_class=proposal.action_class,resource=proposal.target,payload_digest=action_ir.payload_digest,observability_state="HEALTHY",
        runtime_identity_digest=identity.digest(),
    ).validate()
    admission = RuntimeAdmission(
        admission_id="admission:lpcl-test",request_id=pdp.request_id,gate_event_id=pdp.gate_event_id,proposal_id=proposal.proposal_id,
        gate_decision_digest=pdp.gate_decision_digest,pdp_receipt_digest=pdp.pdp_receipt_digest,pdp_evidence_digest=pdp.evidence_digest,
        live_authority_digest="b"*64,authority_lineage_digest=pdp.authority_lineage_digest,policy_binding=pdp.policy_binding,
        effective_authority="local_write",requested_effect_digest=requested_effect.digest(),runtime_identity_digest=identity.digest(),
        provisioned_executor_digest=identity.provisioned_executor_digest,observability_state="HEALTHY",replay_key=pdp.replay_key,
    ).sealed()
    effect_currentness = EffectTimeCurrentnessEvidence(
        evidence_id="runtime-currentness:lpcl-test",admission_digest=admission.admission_digest,requested_effect_digest=admission.requested_effect_digest,
        runtime_identity_digest=admission.runtime_identity_digest,live_authority_digest=admission.live_authority_digest,
        authority_lineage_digest=admission.authority_lineage_digest,policy_binding=admission.policy_binding,observability_state=admission.observability_state,
        source_id="currentness-source",source_instance_id="currentness-instance",source_implementation_digest="c"*64,
        trust_anchor_id="currentness-anchor",trust_anchor_digest="d"*64,observed_at="2026-09-08T00:00:01+02:00",
    ).sealed()
    receipt = RuntimeExecutionReceipt(
        receipt_id="receipt:lpcl-test",execution_id="execution:lpcl-test",admission_digest=admission.admission_digest,
        request_digest="e"*64,sandbox_receipt_digest="f"*64,operation_digest="0"*64,mission_id=proposal.mission_id,
        executor_id="executor:lpcl-test",runtime_instance_id=identity.runtime_instance_id,sandbox_id=identity.sandbox_id,workspace_id=identity.workspace_id,
        dispatch_id="1"*64,fencing_token="2"*64,generation=1,action=requested_effect.action_class,resource=requested_effect.resource,
        payload_digest=requested_effect.payload_digest,outcome="SUCCEEDED",effect_state="OBSERVED",effect_digest="3"*64,
        observed_events=("effect.observed",),side_effect_refs=("side-effect:lpcl-test",),
    ).sealed()
    observation = RuntimeEffectObservation(
        observation_id="observation:lpcl-test",execution_id=receipt.execution_id,admission_digest=receipt.admission_digest,
        request_digest=receipt.request_digest,operation_digest=receipt.operation_digest,action=receipt.action,resource=receipt.resource,
        effect_state="OBSERVED",effect_digest=receipt.effect_digest,observed_events=receipt.observed_events,side_effect_refs=receipt.side_effect_refs,
        source_id="observer-source",source_instance_id="observer-instance",source_implementation_digest="4"*64,
        trust_anchor_id="observer-anchor",trust_anchor_digest="5"*64,observed_at="2026-09-08T00:00:02+02:00",
    ).sealed()
    reconciliation = RuntimeReconciliationReceipt(
        reconciliation_id="reconciliation:lpcl-test",runtime_execution_receipt_digest=receipt.receipt_digest,
        effect_observation_digest=observation.observation_digest,currentness_evidence_digest=effect_currentness.evidence_digest,
        execution_id=receipt.execution_id,admission_digest=admission.admission_digest,disposition="MATCHED",anomaly_codes=(),
        reconciled_effect_digest=receipt.effect_digest,reconciled_at="2026-09-08T00:00:03+02:00",
    ).sealed()
    evidence = CanonicalDownstreamEvidence(
        action_intent=action_intent,action_ir=action_ir,proposal_context=proposal_context,proposal=proposal,pdp_evidence=pdp,
        runtime_identity=identity,requested_effect=requested_effect,admission=admission,effect_currentness=effect_currentness,
        execution_receipt=receipt,effect_observation=observation,reconciliation=reconciliation,
    )
    outcome = ProcessTransitionOutcome(
        process_id="process:semantics",process_ir_digest=ir.process_digest,transition_id="advance",
        transition_decision_digest=decision.transition_decision_digest,attempt_number=1,outcome="PASS",next_state=next_state,
        action_ref=action_ir.payload_digest,proposal_digest=proposal_context.digest(),admission_ref=admission.admission_digest,
        effect_ref=receipt.effect_digest,observation_ref=observation.observation_digest,reconciliation_ref=reconciliation.reconciliation_digest,
        currentness_basis_ref=basis.basis_digest,
    ).sealed()
    return outcome,evidence


class ProcessSemanticsTests(unittest.TestCase):
    def test_selects_first_legal_unfinished_transition(self):
        ir=CanonicalProcessIR.from_mapping(process_model()); decision=TransitionSelector(ir).select(context(ir)); self.assertEqual(decision.decision,"SELECTED"); self.assertEqual(decision.transition_id,"advance")

    def test_missing_authority_context_requires_handoff_not_grant(self):
        ir=CanonicalProcessIR.from_mapping(process_model()); self.assertEqual(TransitionSelector(ir).select(context(ir,authority=False)).decision,"HANDOFF_REQUIRED")

    def test_missing_currentness_is_unknown(self):
        ir=CanonicalProcessIR.from_mapping(process_model()); self.assertEqual(TransitionSelector(ir).select(context(ir,currentness=False)).decision,"UNKNOWN")

    def test_stale_currentness_is_unknown(self):
        ir=CanonicalProcessIR.from_mapping(process_model()); ctx=context(ir); ctx=ProcessContextSnapshot(**{**ctx.__dict__,"currentness_bases":(current_basis("STALE"),)}).validate_for(ir); self.assertEqual(TransitionSelector(ir).select(ctx).decision,"UNKNOWN")

    def test_exact_outcome_advances_process_state_only_from_bound_selection(self):
        ir=CanonicalProcessIR.from_mapping(process_model()); ctx=context(ir); selected=TransitionSelector(ir).bind_selected(ctx); outcome,evidence=canonical_action_pass(ir,selected,ctx.currentness_bases[0]); updated=apply_transition_outcome(ir,ctx,selected,outcome,downstream_evidence=evidence); self.assertEqual(updated.process_state,"DONE"); self.assertIn("advance",updated.completed_transitions); self.assertIn(evidence.effect_observation.observation_digest,updated.observation_refs); self.assertIn(evidence.reconciliation.reconciliation_digest,updated.reconciliation_refs); self.assertEqual(updated.attempt_counts,(("advance",1),))

    def test_decision_context_substitution_is_denied(self):
        ir=CanonicalProcessIR.from_mapping(process_model()); ctx=context(ir); selected=TransitionSelector(ir).bind_selected(ctx); changed=ProcessContextSnapshot(**{**ctx.__dict__,"observed_at":"2026-09-08T00:01:00+02:00"}).validate_for(ir); outcome,_=canonical_action_pass(ir,selected,ctx.currentness_bases[0]);
        with self.assertRaisesRegex(ProcessSemanticError,"ProcessContext binding"): apply_transition_outcome(ir,changed,selected,outcome)

    def test_state_substitution_is_denied(self):
        ir=CanonicalProcessIR.from_mapping(process_model()); ctx=context(ir); selected=TransitionSelector(ir).bind_selected(ctx); outcome,evidence=canonical_action_pass(ir,selected,ctx.currentness_bases[0],next_state="READY")
        with self.assertRaisesRegex(ProcessSemanticError,"next-state substitution"): apply_transition_outcome(ir,ctx,selected,outcome,downstream_evidence=evidence)

    def test_action_required_pass_requires_complete_downstream_evidence(self):
        ir=CanonicalProcessIR.from_mapping(process_model()); ctx=context(ir); selected=TransitionSelector(ir).bind_selected(ctx); incomplete=ProcessTransitionOutcome(process_id="process:semantics",process_ir_digest=ir.process_digest,transition_id="advance",transition_decision_digest=selected.transition_decision_digest,attempt_number=1,outcome="PASS",next_state="DONE",action_ref="action:1",proposal_digest="a"*64,admission_ref="admission:1",effect_ref="effect:1",currentness_basis_ref=ctx.currentness_bases[0].basis_digest).sealed();
        with self.assertRaisesRegex(ProcessSemanticError,"ACTION_REQUIRED PASS"): apply_transition_outcome(ir,ctx,selected,incomplete)

    def test_complete_self_attested_strings_cannot_close_action_pass(self):
        ir=CanonicalProcessIR.from_mapping(process_model()); ctx=context(ir); selected=TransitionSelector(ir).bind_selected(ctx); forged=ProcessTransitionOutcome(process_id="process:semantics",process_ir_digest=ir.process_digest,transition_id="advance",transition_decision_digest=selected.transition_decision_digest,attempt_number=1,outcome="PASS",next_state="DONE",action_ref="action:forged",proposal_digest="a"*64,admission_ref="admission:forged",effect_ref="effect:forged",observation_ref="observation:forged",reconciliation_ref="reconciliation:forged",currentness_basis_ref=ctx.currentness_bases[0].basis_digest).sealed()
        with self.assertRaisesRegex(ProcessSemanticError,"independently materialized canonical downstream evidence"): apply_transition_outcome(ir,ctx,selected,forged)

    def test_downstream_observation_substitution_is_denied(self):
        ir=CanonicalProcessIR.from_mapping(process_model()); ctx=context(ir); selected=TransitionSelector(ir).bind_selected(ctx); outcome,evidence=canonical_action_pass(ir,selected,ctx.currentness_bases[0]); forged=ProcessTransitionOutcome(**{**outcome.__dict__,"observation_ref":"observation:forged","transition_outcome_digest":""}).sealed()
        with self.assertRaisesRegex(ProcessSemanticError,"observation_ref"): apply_transition_outcome(ir,ctx,selected,forged,downstream_evidence=evidence)

    def test_action_intent_candidate_is_non_authoritative(self):
        ir=CanonicalProcessIR.from_mapping(process_model()); candidate=ActionIntentCandidate(process_id="process:semantics",process_ir_digest=ir.process_digest,transition_id="advance",mission_ref="mission:semantics",intent="prepare bounded repository candidate",target_class="repository",required_capability="repository.prepare_candidate",authority_requirement="authority-context:write",process_scope_digest="b"*64,expected_process_outcome="candidate-prepared",evidence_context_refs=("evidence:verified",),currentness_context_refs=(current_basis().basis_digest,)).sealed(); self.assertEqual(candidate.authority_effect,"NONE"); self.assertEqual(candidate.execution_effect,"NONE"); self.assertFalse(hasattr(candidate,"pdp_result")); self.assertFalse(hasattr(candidate,"runtime_admission"))


if __name__=="__main__": unittest.main()
