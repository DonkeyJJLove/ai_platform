from __future__ import annotations

import unittest

from cyber_lion.contracts.process_action import ActionIntentCandidate, ProcessActionContractError, ProcessTransitionOutcome
from cyber_lion.contracts.process_ir import CanonicalProcessIR, ProcessContextSnapshot
from cyber_lion.enterprise.process_semantics import ProcessSemanticError, TransitionSelector, apply_transition_outcome


def process_model(action: bool = True):
    return {
        "schema_version":"1.0.0","process_id":"process:semantics","mission_ref":"mission:semantics","goal_ref":"goal:semantics",
        "scope":{"domains":["repository"],"resources":["repo:x/y"],"widening_allowed":False},"initial_state":"READY","states":["READY","DONE"],
        "dependencies":[{"dependency_id":"dep:baseline","required":True,"description":"exact baseline"}],
        "transitions":[{"transition_id":"advance","transition_class":"ACTION_REQUIRED" if action else "INTERNAL","source_states":["READY"],"trigger":"continue","dependencies":["dep:baseline"],"guards":["guard:scope"],"evidence_requirements":["evidence:verified"],"currentness_requirements":["currentness:exact"],"authority_requirements":["authority-context:write"] if action else [],"operator":"EMIT_ACTION_INTENT" if action else "VERIFY","expected_postconditions":["postcondition:done"],"outcome_map":{"PASS":"DONE","FAIL":"STOP","UNKNOWN":"HANDOFF","DRIFT":"HANDOFF"},"retry_policy":{"max_attempts":0,"on_exhausted":"HANDOFF"},"replay_policy":"DENY","idempotency_class":"IDEMPOTENT" if action else "PURE","resource_claims":{"read_scopes":["repo:x/y"],"write_scopes":["repo:x/y:candidate"] if action else [],"authority_budgets":["authority-context:write"] if action else [],"currentness_subjects":["currentness:exact"],"replay_domain":"semantics:advance","reconciliation_group":"semantics"}}],
        "scheduling_policy":{"strategy":"DECLARED_ORDER","order":["advance"],"priorities":{"advance":0},"max_wip":1,"parallel_safe_groups":[]},
        "termination_policy":{"terminal_states":["DONE"],"allow_no_legal_transition":False,"on_unknown":"HANDOFF"},"lineage":{"parent_process_digests":[],"generation":0,"source_refs":["test"]}}


def context(ir: CanonicalProcessIR, *, authority=True, currentness=True):
    return ProcessContextSnapshot(process_ir_digest=ir.process_digest,process_state="READY",satisfied_dependencies=("dep:baseline",),satisfied_guards=("guard:scope",),satisfied_evidence_requirements=("evidence:verified",),satisfied_currentness_requirements=("currentness:exact",) if currentness else (),verified_authority_context_refs=("authority-context:write",) if authority else (),observed_at="2026-09-07T20:00:00Z").validate_for(ir)


class ProcessSemanticsTests(unittest.TestCase):
    def test_selects_first_legal_unfinished_transition(self):
        ir=CanonicalProcessIR.from_mapping(process_model()); decision=TransitionSelector(ir).select(context(ir)); self.assertEqual(decision.decision,"SELECTED"); self.assertEqual(decision.transition_id,"advance")

    def test_missing_authority_context_requires_handoff_not_grant(self):
        ir=CanonicalProcessIR.from_mapping(process_model()); self.assertEqual(TransitionSelector(ir).select(context(ir,authority=False)).decision,"HANDOFF_REQUIRED")

    def test_missing_currentness_is_unknown(self):
        ir=CanonicalProcessIR.from_mapping(process_model()); self.assertEqual(TransitionSelector(ir).select(context(ir,currentness=False)).decision,"UNKNOWN")

    def test_consequential_pass_requires_observation_and_reconciliation(self):
        ir=CanonicalProcessIR.from_mapping(process_model())
        with self.assertRaisesRegex(ProcessActionContractError,"consequential PASS"):
            ProcessTransitionOutcome(process_id="process:semantics",process_ir_digest=ir.process_digest,transition_id="advance",outcome="PASS",next_state="DONE",consequential=True,action_ref="action:1",admission_ref="admission:1",effect_ref="effect:1",currentness_basis_ref="currentness:1").sealed()

    def test_exact_outcome_advances_process_state(self):
        ir=CanonicalProcessIR.from_mapping(process_model()); outcome=ProcessTransitionOutcome(process_id="process:semantics",process_ir_digest=ir.process_digest,transition_id="advance",outcome="PASS",next_state="DONE",consequential=True,action_ref="action:1",proposal_digest="a"*64,admission_ref="admission:1",effect_ref="effect:1",observation_ref="observation:1",reconciliation_ref="reconciliation:1",currentness_basis_ref="currentness:1").sealed(); updated=apply_transition_outcome(ir,context(ir),outcome); self.assertEqual(updated.process_state,"DONE"); self.assertIn("advance",updated.completed_transitions); self.assertIn("observation:1",updated.observation_refs); self.assertIn("reconciliation:1",updated.reconciliation_refs)

    def test_state_substitution_is_denied(self):
        ir=CanonicalProcessIR.from_mapping(process_model()); outcome=ProcessTransitionOutcome(process_id="process:semantics",process_ir_digest=ir.process_digest,transition_id="advance",outcome="PASS",next_state="READY",consequential=True,action_ref="action:1",admission_ref="admission:1",effect_ref="effect:1",observation_ref="observation:1",reconciliation_ref="reconciliation:1",currentness_basis_ref="currentness:1").sealed()
        with self.assertRaisesRegex(ProcessSemanticError,"next-state substitution"): apply_transition_outcome(ir,context(ir),outcome)

    def test_action_intent_candidate_is_non_authoritative(self):
        ir=CanonicalProcessIR.from_mapping(process_model()); candidate=ActionIntentCandidate(process_id="process:semantics",process_ir_digest=ir.process_digest,transition_id="advance",mission_ref="mission:semantics",intent="prepare bounded repository candidate",target_class="repository",required_capability="repository.prepare_candidate",authority_requirement="authority-context:write",process_scope_digest="b"*64,expected_process_outcome="candidate-prepared",evidence_context_refs=("evidence:verified",),currentness_context_refs=("currentness:exact",)).sealed(); self.assertEqual(candidate.authority_effect,"NONE"); self.assertEqual(candidate.execution_effect,"NONE"); self.assertFalse(hasattr(candidate,"pdp_result")); self.assertFalse(hasattr(candidate,"runtime_admission"))


if __name__=="__main__": unittest.main()
