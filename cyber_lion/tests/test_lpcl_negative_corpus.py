from __future__ import annotations

import json
from pathlib import Path
import unittest

from cyber_lion.contracts.process_action import ActionIntentCandidate, ProcessActionContractError, ProcessTransitionOutcome, TransitionDecisionRecord
from cyber_lion.contracts.process_ir import CanonicalProcessIR, CurrentnessBasis, ProcessContextSnapshot, ProcessIRContractError
from cyber_lion.enterprise.process_semantics import ProcessSemanticError, TransitionSelector, apply_transition_outcome
from cyber_lion.process_language.legacy_run import LegacyRunAdapter, LegacyRunError


def model(*, action: bool = True, fail_target: str = "STOP", max_attempts: int = 0):
    return {
        "schema_version":"1.0.0","process_id":"process:negative","mission_ref":"mission:negative","goal_ref":"goal:negative",
        "scope":{"domains":["repository"],"resources":["repo:x/y"],"widening_allowed":False},
        "initial_state":"READY","states":["READY","DONE"],
        "dependencies":[{"dependency_id":"dep:baseline","required":True,"description":"exact baseline"}],
        "transitions":[{"transition_id":"advance","transition_class":"ACTION_REQUIRED" if action else "INTERNAL","source_states":["READY"],"trigger":"continue","dependencies":["dep:baseline"],"guards":["guard:scope"],"evidence_requirements":["evidence:verified"],"currentness_requirements":["currentness:exact"],"authority_requirements":["authority-context:write"] if action else [],"operator":"EMIT_ACTION_INTENT" if action else "VERIFY","expected_postconditions":["postcondition:done"],"outcome_map":{"PASS":"DONE","FAIL":fail_target,"UNKNOWN":"HANDOFF","DRIFT":"HANDOFF","AUTHORITY_BOUNDARY":"HANDOFF","BLOCKED":"STOP","COMPLETE":"COMPLETE"},"retry_policy":{"max_attempts":max_attempts,"on_exhausted":"HANDOFF"},"replay_policy":"DENY","idempotency_class":"IDEMPOTENT" if action else "PURE","resource_claims":{"read_scopes":["repo:x/y"],"write_scopes":["repo:x/y:candidate"] if action else [],"authority_budgets":["authority-context:write"] if action else [],"currentness_subjects":["currentness:exact"],"replay_domain":"negative:advance","reconciliation_group":"negative"}}],
        "scheduling_policy":{"strategy":"DECLARED_ORDER","order":["advance"],"priorities":{"advance":0},"max_wip":1,"parallel_safe_groups":[]},
        "termination_policy":{"terminal_states":["DONE"],"allow_no_legal_transition":False,"on_unknown":"HANDOFF"},
        "lineage":{"parent_process_digests":[],"generation":0,"source_refs":["negative-corpus"]}}


def basis(state: str = "CURRENT"):
    return CurrentnessBasis(requirement_id="currentness:exact",subject="currentness:exact",observed_identity="git:exact",evidence_ref="evidence:readback",observed_at="2026-09-08T00:00:00+02:00",state=state,drift_rule="IDENTITY_CHANGED").sealed()


def ctx(ir, *, authority=True, currentness=True, dependency=True):
    return ProcessContextSnapshot(process_ir_digest=ir.process_digest,process_state="READY",satisfied_dependencies=("dep:baseline",) if dependency else (),satisfied_guards=("guard:scope",),satisfied_evidence_requirements=("evidence:verified",),satisfied_currentness_requirements=("currentness:exact",),currentness_bases=(basis(),) if currentness else (),verified_authority_context_refs=("authority-context:write",) if authority else (),observed_at="2026-09-08T00:00:00+02:00").validate_for(ir)


def action_pass(ir, context, decision, *, observation=True, reconciliation=True):
    return ProcessTransitionOutcome(process_id=ir.as_dict()["process_id"],process_ir_digest=ir.process_digest,transition_id=decision.transition_id,transition_decision_digest=decision.transition_decision_digest,attempt_number=1,outcome="PASS",next_state="DONE",action_ref="action:1",proposal_digest="a"*64,admission_ref="admission:1",effect_ref="effect:1",observation_ref="observation:1" if observation else "",reconciliation_ref="reconciliation:1" if reconciliation else "",currentness_basis_ref=context.currentness_bases[0].basis_digest).sealed()


class LPCLExecutableNegativeCorpus(unittest.TestCase):
    def test_n01_pass_without_evidence(self):
        ir=CanonicalProcessIR.from_mapping(model()); context=ctx(ir); decision=TransitionSelector(ir).bind_selected(context); incomplete=ProcessTransitionOutcome(process_id="process:negative",process_ir_digest=ir.process_digest,transition_id="advance",transition_decision_digest=decision.transition_decision_digest,attempt_number=1,outcome="PASS",next_state="DONE").sealed()
        with self.assertRaisesRegex(ProcessSemanticError,"ACTION_REQUIRED PASS"): apply_transition_outcome(ir,context,decision,incomplete)

    def test_n02_current_without_currentness_basis(self):
        ir=CanonicalProcessIR.from_mapping(model()); self.assertEqual(TransitionSelector(ir).select(ctx(ir,currentness=False)).decision,"UNKNOWN")

    def test_n03_write_effect_encoded_directly(self):
        value=model(action=False); value["transitions"][0]["operator"]="WRITE_EFFECT"
        with self.assertRaisesRegex(ProcessIRContractError,"operator invalid"): CanonicalProcessIR.from_mapping(value)

    def test_n04_authority_requirement_not_grant(self):
        ir=CanonicalProcessIR.from_mapping(model()); self.assertEqual(TransitionSelector(ir).select(ctx(ir,authority=False)).decision,"HANDOFF_REQUIRED")

    def test_n05_process_self_mints_authority(self):
        ir=CanonicalProcessIR.from_mapping(model()); candidate=ActionIntentCandidate(process_id="process:negative",process_ir_digest=ir.process_digest,transition_id="advance",mission_ref="mission:negative",intent="x",target_class="repository",required_capability="repository.prepare_candidate",authority_requirement="authority-context:write",process_scope_digest="b"*64,expected_process_outcome="candidate",evidence_context_refs=("evidence:verified",),currentness_context_refs=(basis().basis_digest,),authority_effect="GRANT")
        with self.assertRaisesRegex(ProcessActionContractError,"non-authoritative"): candidate.validate()

    def test_n06_process_contains_pdp_decision(self):
        value=model(); value["pdp_decision"]="ALLOW"
        with self.assertRaisesRegex(ProcessIRContractError,"keys are not canonical"): CanonicalProcessIR.from_mapping(value)

    def test_n07_process_contains_runtime_admission(self):
        value=model(); value["runtime_admission"]={}
        with self.assertRaisesRegex(ProcessIRContractError,"keys are not canonical"): CanonicalProcessIR.from_mapping(value)

    def test_n08_process_selects_effect_provider(self):
        value=model(); value["effect_provider"]="provider:x"
        with self.assertRaisesRegex(ProcessIRContractError,"keys are not canonical"): CanonicalProcessIR.from_mapping(value)

    def test_n09_receipt_without_observation(self):
        ir=CanonicalProcessIR.from_mapping(model()); context=ctx(ir); decision=TransitionSelector(ir).bind_selected(context)
        with self.assertRaisesRegex(ProcessSemanticError,"ACTION_REQUIRED PASS"): apply_transition_outcome(ir,context,decision,action_pass(ir,context,decision,observation=False))

    def test_n10_observation_without_reconciliation(self):
        ir=CanonicalProcessIR.from_mapping(model()); context=ctx(ir); decision=TransitionSelector(ir).bind_selected(context)
        with self.assertRaisesRegex(ProcessSemanticError,"ACTION_REQUIRED PASS"): apply_transition_outcome(ir,context,decision,action_pass(ir,context,decision,reconciliation=False))

    def test_n11_unknown_does_not_promote_to_pass(self):
        ir=CanonicalProcessIR.from_mapping(model()); context=ctx(ir,currentness=False); self.assertEqual(TransitionSelector(ir).select(context).decision,"UNKNOWN"); forged=TransitionDecisionRecord(process_id="process:negative",process_ir_digest=ir.process_digest,process_context_digest=context.context_digest(ir),transition_id="advance",transition_class="ACTION_REQUIRED",decision="SELECTED",decision_basis="forged",selected_at=context.observed_at).sealed(); forged_outcome=ProcessTransitionOutcome(process_id="process:negative",process_ir_digest=ir.process_digest,transition_id="advance",transition_decision_digest=forged.transition_decision_digest,attempt_number=1,outcome="PASS",next_state="DONE",action_ref="a",proposal_digest="a"*64,admission_ref="r",effect_ref="e",observation_ref="o",reconciliation_ref="c",currentness_basis_ref="b"*64).sealed()
        with self.assertRaisesRegex(ProcessSemanticError,"currently legal selected transition"): apply_transition_outcome(ir,context,forged,forged_outcome)

    def test_n12_candidate_status_cannot_promote_inside_process_ir(self):
        value=model(); value["status"]="INTEGRATED"
        with self.assertRaisesRegex(ProcessIRContractError,"keys are not canonical"): CanonicalProcessIR.from_mapping(value)

    def test_n13_historical_run_never_executes_directly(self):
        adapter=LegacyRunAdapter(); candidate=adapter.semantic_candidate("RUN=SAFE-R1\n--repository=owner/repo\n"); self.assertEqual(candidate["execution_effect"],"NONE"); self.assertNotIn("executable",candidate)

    def test_n14_drifted_currentness_blocks_continuation(self):
        ir=CanonicalProcessIR.from_mapping(model()); context=ctx(ir); stale=ProcessContextSnapshot(**{**context.__dict__,"currentness_bases":(basis("STALE"),)}).validate_for(ir); self.assertEqual(TransitionSelector(ir).select(stale).decision,"UNKNOWN")

    def test_n15_unbounded_continue_rejected(self):
        value=model(action=False,fail_target="CONTINUE"); value["transitions"][0]["retry_policy"]["max_attempts"]=101
        with self.assertRaisesRegex(ProcessIRContractError,"max_attempts"): CanonicalProcessIR.from_mapping(value)

    def test_n16_unbounded_retry_rejected(self):
        value=model(action=False); value["transitions"][0]["retry_policy"]["max_attempts"]=-1
        with self.assertRaisesRegex(ProcessIRContractError,"max_attempts"): CanonicalProcessIR.from_mapping(value)

    def test_n17_cycle_without_bound_rejected(self):
        value=model(action=False,fail_target="READY"); value["transitions"][0]["outcome_map"]["PASS"]="READY"; value["transitions"][0]["retry_policy"]["max_attempts"]=101
        with self.assertRaisesRegex(ProcessIRContractError,"max_attempts"): CanonicalProcessIR.from_mapping(value)

    def test_n18_conflicting_parallel_writes_serialize(self):
        value=model(); first=value["transitions"][0]; second=json.loads(json.dumps(first)); first["transition_id"]="a"; second["transition_id"]="b"; first["resource_claims"]["replay_domain"]="negative:a"; second["resource_claims"]["replay_domain"]="negative:b"; value["transitions"]=[first,second]; value["scheduling_policy"]={"strategy":"DECLARED_ORDER","order":["a","b"],"priorities":{"a":0,"b":1},"max_wip":2,"parallel_safe_groups":[["a","b"]]}; ir=CanonicalProcessIR.from_mapping(value); context=ctx(ir); self.assertEqual(TransitionSelector(ir).select_parallel(context),("a",))

    def test_n19_scope_widening_rejected(self):
        value=model(); value["scope"]["widening_allowed"]=True
        with self.assertRaisesRegex(ProcessIRContractError,"widening_allowed"): CanonicalProcessIR.from_mapping(value)

    def test_n20_non_idempotent_retry_without_reconciliation_blocks(self):
        value=model(action=False,fail_target="READY",max_attempts=1); value["transitions"][0]["idempotency_class"]="NON_IDEMPOTENT"; value["transitions"][0]["replay_policy"]="RECONCILE_FIRST"; ir=CanonicalProcessIR.from_mapping(value); context=ctx(ir); decision=TransitionSelector(ir).bind_selected(context); failed=ProcessTransitionOutcome(process_id="process:negative",process_ir_digest=ir.process_digest,transition_id="advance",transition_decision_digest=decision.transition_decision_digest,attempt_number=1,outcome="FAIL",next_state="READY").sealed(); updated=apply_transition_outcome(ir,context,decision,failed); self.assertEqual(TransitionSelector(ir).select(updated).decision,"BLOCKED")

    def test_n21_dependency_bypass_blocked(self):
        ir=CanonicalProcessIR.from_mapping(model()); self.assertEqual(TransitionSelector(ir).select(ctx(ir,dependency=False)).decision,"BLOCKED")

    def test_n22_action_transition_requires_action_boundary(self):
        value=model(); value["transitions"][0]["operator"]="VERIFY"
        with self.assertRaisesRegex(ProcessIRContractError,"ACTION_REQUIRED"): CanonicalProcessIR.from_mapping(value)

    def test_n23_actionspec_execution_fields_do_not_leak_up(self):
        value=model(); value["transitions"][0]["executable"]="/bin/sh"
        with self.assertRaisesRegex(ProcessIRContractError,"keys are not canonical"): CanonicalProcessIR.from_mapping(value)

    def test_n24_process_profile_namespace_collision_rejected(self):
        value=model(); value["process_profile"]="builder-profile"
        with self.assertRaisesRegex(ProcessIRContractError,"keys are not canonical"): CanonicalProcessIR.from_mapping(value)

    def test_n25_legacy_phase_order_is_ambiguous(self):
        source="RUN=LEGACY-R25\nPHASE 1\n--repository=owner/repo\n--phase-2=x\n"; adapter=LegacyRunAdapter(); self.assertEqual(adapter.parse(source).classification,"AMBIGUOUS")
        with self.assertRaisesRegex(LegacyRunError,"cannot be promoted"): adapter.semantic_candidate(source)

    def test_declared_corpus_has_exact_executable_mapping(self):
        payload=json.loads(Path("cyber_lion/process_language/negative_corpus.json").read_text(encoding="utf-8")); declared={item["id"] for item in payload["cases"]}; executable={f"N{i:02d}" for i in range(1,26)}; self.assertEqual(declared,executable)


if __name__=="__main__": unittest.main()
