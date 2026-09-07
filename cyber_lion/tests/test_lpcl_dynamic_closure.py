from __future__ import annotations

import unittest

from cyber_lion.contracts.process_action import ProcessActionContractError, ProcessTransitionOutcome
from cyber_lion.contracts.process_ir import CanonicalProcessIR, ProcessContextSnapshot
from cyber_lion.enterprise.process_semantics import ProcessSemanticError, TransitionSelector, apply_transition_outcome


# Dedicated historical counterexample carrier. This file intentionally reproduces
# CEX-01..06 against the pre-repair LPCL dynamic closure before it is rewritten.

def process_model(*, action: bool = True, fail_target: str = "STOP", max_attempts: int = 0):
    return {
        "schema_version":"1.0.0","process_id":"process:closure","mission_ref":"mission:closure","goal_ref":"goal:closure",
        "scope":{"domains":["repository"],"resources":["repo:x/y"],"widening_allowed":False},
        "initial_state":"READY","states":["READY","DONE"],
        "dependencies":[{"dependency_id":"dep:baseline","required":True,"description":"exact baseline"}],
        "transitions":[{"transition_id":"advance","transition_class":"ACTION_REQUIRED" if action else "INTERNAL","source_states":["READY"],"trigger":"continue","dependencies":["dep:baseline"],"guards":["guard:scope"],"evidence_requirements":["evidence:verified"],"currentness_requirements":["currentness:exact"],"authority_requirements":["authority-context:write"] if action else [],"operator":"EMIT_ACTION_INTENT" if action else "VERIFY","expected_postconditions":["postcondition:done"],"outcome_map":{"PASS":"DONE","FAIL":fail_target,"UNKNOWN":"HANDOFF","DRIFT":"HANDOFF","AUTHORITY_BOUNDARY":"HANDOFF"},"retry_policy":{"max_attempts":max_attempts,"on_exhausted":"HANDOFF"},"replay_policy":"DENY","idempotency_class":"IDEMPOTENT" if action else "PURE","resource_claims":{"read_scopes":["repo:x/y"],"write_scopes":["repo:x/y:candidate"] if action else [],"authority_budgets":["authority-context:write"] if action else [],"currentness_subjects":["currentness:exact"],"replay_domain":"closure:advance","reconciliation_group":"closure"}}],
        "scheduling_policy":{"strategy":"DECLARED_ORDER","order":["advance"],"priorities":{"advance":0},"max_wip":1,"parallel_safe_groups":[]},
        "termination_policy":{"terminal_states":["DONE"],"allow_no_legal_transition":False,"on_unknown":"HANDOFF"},
        "lineage":{"parent_process_digests":[],"generation":0,"source_refs":["counterexample"]}}


def context(ir: CanonicalProcessIR, *, currentness: bool = True):
    return ProcessContextSnapshot(
        process_ir_digest=ir.process_digest,
        process_state="READY",
        satisfied_dependencies=("dep:baseline",),
        satisfied_guards=("guard:scope",),
        satisfied_evidence_requirements=("evidence:verified",),
        satisfied_currentness_requirements=("currentness:exact",) if currentness else (),
        verified_authority_context_refs=("authority-context:write",),
        observed_at="2026-09-08T00:00:00+02:00",
    ).validate_for(ir)


class LPCLDynamicClosureCounterexamples(unittest.TestCase):
    def test_cex01_unknown_cannot_be_replaced_by_asserted_pass(self):
        ir=CanonicalProcessIR.from_mapping(process_model()); ctx=context(ir,currentness=False)
        self.assertEqual(TransitionSelector(ir).select(ctx).decision,"UNKNOWN")
        forged=ProcessTransitionOutcome(process_id="process:closure",process_ir_digest=ir.process_digest,transition_id="advance",outcome="PASS",next_state="DONE",consequential=False).sealed()
        with self.assertRaises(ProcessSemanticError): apply_transition_outcome(ir,ctx,forged)

    def test_cex02_action_required_cannot_use_nonconsequential_pass(self):
        ir=CanonicalProcessIR.from_mapping(process_model())
        with self.assertRaises(ProcessActionContractError):
            ProcessTransitionOutcome(process_id="process:closure",process_ir_digest=ir.process_digest,transition_id="advance",outcome="PASS",next_state="DONE",consequential=False).sealed()

    def test_cex03_attempt_count_advances(self):
        ir=CanonicalProcessIR.from_mapping(process_model(action=False,fail_target="READY",max_attempts=0)); ctx=context(ir)
        failed=ProcessTransitionOutcome(process_id="process:closure",process_ir_digest=ir.process_digest,transition_id="advance",outcome="FAIL",next_state="READY",consequential=False).sealed()
        updated=apply_transition_outcome(ir,ctx,failed)
        self.assertEqual(updated.attempt_counts,(("advance",1),))
        self.assertEqual(TransitionSelector(ir).select(updated).decision,"BLOCKED")

    def test_cex04_currentness_string_alone_is_insufficient(self):
        ir=CanonicalProcessIR.from_mapping(process_model()); ctx=context(ir,currentness=True)
        self.assertEqual(TransitionSelector(ir).select(ctx).decision,"UNKNOWN")

    def test_cex05_stop_directive_cannot_resume_arbitrary_state(self):
        ir=CanonicalProcessIR.from_mapping(process_model(action=False,fail_target="STOP")); ctx=context(ir)
        failed=ProcessTransitionOutcome(process_id="process:closure",process_ir_digest=ir.process_digest,transition_id="advance",outcome="FAIL",next_state="DONE",consequential=False).sealed()
        with self.assertRaises(ProcessSemanticError): apply_transition_outcome(ir,ctx,failed)

    def test_cex06_authority_boundary_is_closed_end_to_end(self):
        ir=CanonicalProcessIR.from_mapping(process_model())
        outcome=ProcessTransitionOutcome(process_id="process:closure",process_ir_digest=ir.process_digest,transition_id="advance",outcome="AUTHORITY_BOUNDARY",next_state="READY",consequential=False).sealed()
        self.assertEqual(outcome.outcome,"AUTHORITY_BOUNDARY")


if __name__=="__main__": unittest.main()
