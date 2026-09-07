from __future__ import annotations

import unittest

from cyber_lion.contracts.process_action import OUTCOMES, ProcessTransitionOutcome, TransitionDecisionRecord
from cyber_lion.contracts.process_ir import OUTCOME_LABELS, AttemptRecord, CanonicalProcessIR, CurrentnessBasis, ProcessContextSnapshot
from cyber_lion.enterprise.process_semantics import ProcessSemanticError, TransitionSelector, apply_transition_outcome


def process_model(*, action: bool = True, fail_target: str = "STOP", max_attempts: int = 0):
    return {
        "schema_version":"1.0.0","process_id":"process:closure","mission_ref":"mission:closure","goal_ref":"goal:closure",
        "scope":{"domains":["repository"],"resources":["repo:x/y"],"widening_allowed":False},
        "initial_state":"READY","states":["READY","DONE"],
        "dependencies":[{"dependency_id":"dep:baseline","required":True,"description":"exact baseline"}],
        "transitions":[{"transition_id":"advance","transition_class":"ACTION_REQUIRED" if action else "INTERNAL","source_states":["READY"],"trigger":"continue","dependencies":["dep:baseline"],"guards":["guard:scope"],"evidence_requirements":["evidence:verified"],"currentness_requirements":["currentness:exact"],"authority_requirements":["authority-context:write"] if action else [],"operator":"EMIT_ACTION_INTENT" if action else "VERIFY","expected_postconditions":["postcondition:done"],"outcome_map":{"PASS":"DONE","FAIL":fail_target,"UNKNOWN":"HANDOFF","DRIFT":"HANDOFF","AUTHORITY_BOUNDARY":"HANDOFF","BLOCKED":"STOP","COMPLETE":"COMPLETE"},"retry_policy":{"max_attempts":max_attempts,"on_exhausted":"HANDOFF"},"replay_policy":"DENY","idempotency_class":"IDEMPOTENT" if action else "PURE","resource_claims":{"read_scopes":["repo:x/y"],"write_scopes":["repo:x/y:candidate"] if action else [],"authority_budgets":["authority-context:write"] if action else [],"currentness_subjects":["currentness:exact"],"replay_domain":"closure:advance","reconciliation_group":"closure"}}],
        "scheduling_policy":{"strategy":"DECLARED_ORDER","order":["advance"],"priorities":{"advance":0},"max_wip":1,"parallel_safe_groups":[]},
        "termination_policy":{"terminal_states":["DONE"],"allow_no_legal_transition":False,"on_unknown":"HANDOFF"},
        "lineage":{"parent_process_digests":[],"generation":0,"source_refs":["counterexample"]}}


def current_basis(state: str = "CURRENT"):
    return CurrentnessBasis(requirement_id="currentness:exact",subject="currentness:exact",observed_identity="git:exact-head",evidence_ref="evidence:git-readback",observed_at="2026-09-08T00:00:00+02:00",state=state,drift_rule="IDENTITY_CHANGED").sealed()


def context(ir: CanonicalProcessIR, *, with_basis: bool = True):
    return ProcessContextSnapshot(process_ir_digest=ir.process_digest,process_state="READY",satisfied_dependencies=("dep:baseline",),satisfied_guards=("guard:scope",),satisfied_evidence_requirements=("evidence:verified",),satisfied_currentness_requirements=("currentness:exact",),currentness_bases=(current_basis(),) if with_basis else (),verified_authority_context_refs=("authority-context:write",),observed_at="2026-09-08T00:00:00+02:00").validate_for(ir)


def selected(ir, ctx):
    return TransitionSelector(ir).bind_selected(ctx)


def outcome(ir, decision, label, next_state, *, attempt=1, evidence=False, reconciliation=""):
    basis_ref = context(ir).currentness_bases[0].basis_digest
    return ProcessTransitionOutcome(process_id="process:closure",process_ir_digest=ir.process_digest,transition_id="advance",transition_decision_digest=decision.transition_decision_digest,attempt_number=attempt,outcome=label,next_state=next_state,action_ref="action:1" if evidence else "",proposal_digest="a"*64 if evidence else "",admission_ref="admission:1" if evidence else "",effect_ref="effect:1" if evidence else "",observation_ref="observation:1" if evidence else "",reconciliation_ref=reconciliation or ("reconciliation:1" if evidence else ""),currentness_basis_ref=basis_ref if evidence else "").sealed()


class LPCLDynamicClosureCounterexamples(unittest.TestCase):
    def test_cex01_unknown_cannot_be_replaced_by_pass(self):
        ir=CanonicalProcessIR.from_mapping(process_model()); ctx=context(ir,with_basis=False); self.assertEqual(TransitionSelector(ir).select(ctx).decision,"UNKNOWN")
        forged=TransitionDecisionRecord(process_id="process:closure",process_ir_digest=ir.process_digest,process_context_digest=ctx.context_digest(ir),transition_id="advance",transition_class="ACTION_REQUIRED",decision="SELECTED",decision_basis="forged",selected_at=ctx.observed_at).sealed()
        forged_outcome=ProcessTransitionOutcome(process_id="process:closure",process_ir_digest=ir.process_digest,transition_id="advance",transition_decision_digest=forged.transition_decision_digest,attempt_number=1,outcome="PASS",next_state="DONE",action_ref="action:1",proposal_digest="a"*64,admission_ref="admission:1",effect_ref="effect:1",observation_ref="observation:1",reconciliation_ref="reconciliation:1",currentness_basis_ref="b"*64).sealed()
        with self.assertRaisesRegex(ProcessSemanticError,"currently legal selected transition"): apply_transition_outcome(ir,ctx,forged,forged_outcome)

    def test_cex02_action_required_forces_consequential_evidence(self):
        ir=CanonicalProcessIR.from_mapping(process_model()); ctx=context(ir); decision=selected(ir,ctx); incomplete=outcome(ir,decision,"PASS","DONE",evidence=False)
        with self.assertRaisesRegex(ProcessSemanticError,"ACTION_REQUIRED PASS"): apply_transition_outcome(ir,ctx,decision,incomplete)

    def test_cex03_attempt_count_increments_after_failed_attempt(self):
        ir=CanonicalProcessIR.from_mapping(process_model(action=False,fail_target="READY",max_attempts=1)); ctx=context(ir); decision=selected(ir,ctx); updated=apply_transition_outcome(ir,ctx,decision,outcome(ir,decision,"FAIL","READY")); self.assertEqual(updated.attempt_counts,(("advance",1),)); self.assertEqual(updated.attempt_records[0].attempt_number,1)

    def test_cex03b_zero_retry_policy_prevents_second_attempt(self):
        ir=CanonicalProcessIR.from_mapping(process_model(action=False,fail_target="READY",max_attempts=0)); ctx=context(ir); decision=selected(ir,ctx); updated=apply_transition_outcome(ir,ctx,decision,outcome(ir,decision,"FAIL","READY")); self.assertEqual(TransitionSelector(ir).select(updated).decision,"BLOCKED")

    def test_cex03c_retry_limit_is_exact(self):
        ir=CanonicalProcessIR.from_mapping(process_model(action=False,fail_target="READY",max_attempts=1)); ctx=context(ir); d1=selected(ir,ctx); ctx1=apply_transition_outcome(ir,ctx,d1,outcome(ir,d1,"FAIL","READY",attempt=1)); d2=selected(ir,ctx1); ctx2=apply_transition_outcome(ir,ctx1,d2,outcome(ir,d2,"FAIL","READY",attempt=2)); self.assertEqual(TransitionSelector(ir).select(ctx2).decision,"BLOCKED")

    def test_cex04_bare_currentness_string_is_not_currentness_basis(self):
        ir=CanonicalProcessIR.from_mapping(process_model()); self.assertEqual(TransitionSelector(ir).select(context(ir,with_basis=False)).decision,"UNKNOWN")

    def test_cex04b_stale_basis_blocks_transition(self):
        ir=CanonicalProcessIR.from_mapping(process_model()); ctx=context(ir); stale=ProcessContextSnapshot(**{**ctx.__dict__,"currentness_bases":(current_basis("STALE"),)}).validate_for(ir); self.assertEqual(TransitionSelector(ir).select(stale).decision,"UNKNOWN")

    def test_cex04c_unknown_basis_propagates_unknown(self):
        ir=CanonicalProcessIR.from_mapping(process_model()); ctx=context(ir); unknown=ProcessContextSnapshot(**{**ctx.__dict__,"currentness_bases":(current_basis("UNKNOWN"),)}).validate_for(ir); self.assertEqual(TransitionSelector(ir).select(unknown).decision,"UNKNOWN")

    def _directive(self, directive, label):
        model=process_model(action=False,fail_target=directive); model["transitions"][0]["outcome_map"][label]=directive; ir=CanonicalProcessIR.from_mapping(model); ctx=context(ir); return ir,ctx,selected(ir,ctx)

    def test_cex05_stop_is_terminal_control_semantics(self):
        ir,ctx,d=self._directive("STOP","FAIL"); updated=apply_transition_outcome(ir,ctx,d,outcome(ir,d,"FAIL","READY")); self.assertEqual(updated.process_control,"TERMINATED"); self.assertEqual(TransitionSelector(ir).select(updated).decision,"BLOCKED")

    def test_cex05b_handoff_does_not_allow_state_substitution(self):
        ir,ctx,d=self._directive("HANDOFF","FAIL")
        with self.assertRaisesRegex(ProcessSemanticError,"directive outcome"): apply_transition_outcome(ir,ctx,d,outcome(ir,d,"FAIL","DONE"))

    def test_cex05c_defer_does_not_allow_state_substitution(self):
        ir,ctx,d=self._directive("DEFER","FAIL")
        with self.assertRaisesRegex(ProcessSemanticError,"directive outcome"): apply_transition_outcome(ir,ctx,d,outcome(ir,d,"FAIL","DONE"))

    def test_cex05d_continue_uses_exact_declared_semantics(self):
        ir,ctx,d=self._directive("CONTINUE","FAIL"); updated=apply_transition_outcome(ir,ctx,d,outcome(ir,d,"FAIL","READY")); self.assertEqual(updated.process_state,"READY"); self.assertEqual(updated.process_control,"ACTIVE")

    def test_cex05e_complete_requires_exact_control_semantics(self):
        ir,ctx,d=self._directive("COMPLETE","FAIL"); updated=apply_transition_outcome(ir,ctx,d,outcome(ir,d,"FAIL","READY")); self.assertEqual(updated.process_control,"COMPLETE"); self.assertEqual(TransitionSelector(ir).select(updated).decision,"COMPLETE")

    def test_cex06_outcome_vocabularies_are_identical(self):
        self.assertEqual(OUTCOME_LABELS,OUTCOMES)

    def test_cex07_unselected_transition_outcome_rejected(self):
        ir=CanonicalProcessIR.from_mapping(process_model()); ctx=context(ir); d=selected(ir,ctx); forged=TransitionDecisionRecord(**{**d.__dict__,"transition_decision_digest":"","decision_basis":"forged"}).sealed(); forged_outcome=outcome(ir,forged,"PASS","DONE",evidence=True)
        with self.assertRaisesRegex(ProcessSemanticError,"decision binding mismatch|currently legal|canonical selection"): apply_transition_outcome(ir,ctx,forged,forged_outcome)

    def test_cex08_selected_transition_digest_substitution_rejected(self):
        ir=CanonicalProcessIR.from_mapping(process_model()); ctx=context(ir); d=selected(ir,ctx); forged=ProcessTransitionOutcome(**{**outcome(ir,d,"PASS","DONE",evidence=True).__dict__,"transition_decision_digest":"f"*64,"transition_outcome_digest":""}).sealed()
        with self.assertRaisesRegex(ProcessSemanticError,"decision binding mismatch"): apply_transition_outcome(ir,ctx,d,forged)

    def test_cex09_process_context_digest_substitution_rejected(self):
        ir=CanonicalProcessIR.from_mapping(process_model()); ctx=context(ir); d=selected(ir,ctx); changed=ProcessContextSnapshot(**{**ctx.__dict__,"observed_at":"2026-09-08T00:01:00+02:00"}).validate_for(ir)
        with self.assertRaisesRegex(ProcessSemanticError,"ProcessContext binding"): apply_transition_outcome(ir,changed,d,outcome(ir,d,"PASS","DONE",evidence=True))

    def test_cex10_reconciliation_for_wrong_attempt_does_not_enable_retry(self):
        model=process_model(action=False,fail_target="READY",max_attempts=1); t=model["transitions"][0]; t["idempotency_class"]="NON_IDEMPOTENT"; t["replay_policy"]="RECONCILE_FIRST"; ir=CanonicalProcessIR.from_mapping(model); ctx=context(ir); d=selected(ir,ctx); ctx1=apply_transition_outcome(ir,ctx,d,outcome(ir,d,"FAIL","READY",attempt=1)); wrong=AttemptRecord(transition_id="advance",attempt_number=2,outcome="FAIL",reconciliation_ref="reconciliation:wrong").sealed()
        with self.assertRaisesRegex(Exception,"attempt_counts|duplicate attempt|lineage"): ProcessContextSnapshot(**{**ctx1.__dict__,"attempt_records":ctx1.attempt_records+(wrong,)}).validate_for(ir)

    def test_non_idempotent_retry_requires_bound_reconciliation_evidence(self):
        model=process_model(action=False,fail_target="READY",max_attempts=1); t=model["transitions"][0]; t["idempotency_class"]="NON_IDEMPOTENT"; t["replay_policy"]="RECONCILE_FIRST"; ir=CanonicalProcessIR.from_mapping(model); ctx=context(ir); d=selected(ir,ctx); ctx1=apply_transition_outcome(ir,ctx,d,outcome(ir,d,"FAIL","READY",attempt=1)); self.assertEqual(TransitionSelector(ir).select(ctx1).decision,"BLOCKED")
        ir2=CanonicalProcessIR.from_mapping(model); ctx2=context(ir2); d2=selected(ir2,ctx2); reconciled=outcome(ir2,d2,"FAIL","READY",attempt=1,reconciliation="reconciliation:attempt-1"); ctx3=apply_transition_outcome(ir2,ctx2,d2,reconciled); self.assertEqual(TransitionSelector(ir2).select(ctx3).decision,"SELECTED")


if __name__=="__main__": unittest.main()
