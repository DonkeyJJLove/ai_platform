from __future__ import annotations

from pathlib import Path
import unittest

from cyber_lion.contracts.process_ir import CanonicalProcessIR, ProcessIRContractError
from cyber_lion.enterprise.complete_mediation import EffectSurfaceScanner


def minimal_process(action: bool = False):
    return {
        "schema_version":"1.0.0","process_id":"process:test","mission_ref":"mission:test","goal_ref":"goal:test",
        "scope":{"domains":["repository"],"resources":["repo:example/test"],"widening_allowed":False},
        "initial_state":"READY","states":["READY","DONE"],"dependencies":[],
        "transitions":[{
            "transition_id":"step","transition_class":"ACTION_REQUIRED" if action else "INTERNAL","source_states":["READY"],"trigger":"start","dependencies":[],"guards":[],
            "evidence_requirements":["evidence:baseline"],"currentness_requirements":["currentness:exact"],"authority_requirements":["authority-context:write"] if action else [],
            "operator":"EMIT_ACTION_INTENT" if action else "REACQUIRE","expected_postconditions":["postcondition:bounded"],
            "outcome_map":{"PASS":"DONE","FAIL":"STOP","UNKNOWN":"HANDOFF","DRIFT":"HANDOFF"},
            "retry_policy":{"max_attempts":0,"on_exhausted":"HANDOFF"},"replay_policy":"DENY","idempotency_class":"IDEMPOTENT" if action else "PURE",
            "resource_claims":{"read_scopes":["repo:example/test"],"write_scopes":["repo:example/test:candidate"] if action else [],"authority_budgets":["authority-context:write"] if action else [],"currentness_subjects":["currentness:exact"],"replay_domain":"process:test:step","reconciliation_group":"process:test"}
        }],
        "scheduling_policy":{"strategy":"DECLARED_ORDER","order":["step"],"priorities":{"step":0},"max_wip":1,"parallel_safe_groups":[]},
        "termination_policy":{"terminal_states":["DONE"],"allow_no_legal_transition":False,"on_unknown":"HANDOFF"},
        "lineage":{"parent_process_digests":[],"generation":0,"source_refs":["test"]}
    }


class ProcessIRTests(unittest.TestCase):
    def test_canonical_representation_and_digest_are_deterministic(self):
        a=CanonicalProcessIR.from_mapping(minimal_process()); value=minimal_process(); reordered={key:value[key] for key in reversed(tuple(value))}; b=CanonicalProcessIR.from_mapping(reordered)
        self.assertEqual(a.canonical_bytes,b.canonical_bytes); self.assertEqual(a.process_digest,b.process_digest); self.assertEqual(len(a.process_digest),64)

    def test_unknown_root_and_duplicate_json_key_fail_closed(self):
        value=minimal_process(); value["shell"]=False
        with self.assertRaisesRegex(ProcessIRContractError,"keys are not canonical"): CanonicalProcessIR.from_mapping(value)
        with self.assertRaisesRegex(ProcessIRContractError,"duplicate JSON object key"): CanonicalProcessIR.from_json('{"schema_version":"1.0.0","schema_version":"1.0.0"}')

    def test_action_transition_requires_explicit_action_boundary_context(self):
        CanonicalProcessIR.from_mapping(minimal_process(action=True))
        for key in ("evidence_requirements","currentness_requirements","authority_requirements"):
            value=minimal_process(action=True); value["transitions"][0][key]=[]
            with self.assertRaisesRegex(ProcessIRContractError,"ACTION_REQUIRED"): CanonicalProcessIR.from_mapping(value)

    def test_internal_transition_cannot_emit_action_intent(self):
        value=minimal_process(); value["transitions"][0]["operator"]="EMIT_ACTION_INTENT"
        with self.assertRaisesRegex(ProcessIRContractError,"INTERNAL"): CanonicalProcessIR.from_mapping(value)

    def test_raw_shell_is_not_process_operator(self):
        value=minimal_process(); value["transitions"][0]["operator"]="RAW_SHELL"
        with self.assertRaisesRegex(ProcessIRContractError,"operator invalid"): CanonicalProcessIR.from_mapping(value)

    def test_non_idempotent_retry_requires_reconciliation_first(self):
        value=minimal_process(action=True); value["transitions"][0]["idempotency_class"]="NON_IDEMPOTENT"; value["transitions"][0]["retry_policy"]["max_attempts"]=1
        with self.assertRaisesRegex(ProcessIRContractError,"RECONCILE_FIRST"): CanonicalProcessIR.from_mapping(value)
        value["transitions"][0]["replay_policy"]="RECONCILE_FIRST"; CanonicalProcessIR.from_mapping(value)

    def test_scope_cannot_widen(self):
        value=minimal_process(); value["scope"]["widening_allowed"]=True
        with self.assertRaisesRegex(ProcessIRContractError,"widening_allowed"): CanonicalProcessIR.from_mapping(value)

    def test_contract_module_adds_no_effect_surface(self):
        source=Path("cyber_lion/contracts/process_ir.py").read_text(encoding="utf-8")
        inventory=EffectSurfaceScanner().scan(repository="DonkeyJJLove/ai_platform",revision="0"*40,tree_digest="0"*40,sources={"cyber_lion/contracts/process_ir.py":source})
        self.assertEqual(inventory.surfaces,())


if __name__=="__main__": unittest.main()
