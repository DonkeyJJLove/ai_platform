from __future__ import annotations

import unittest

from cyber_lion.contracts.process_action import ProcessTransitionOutcome
from cyber_lion.contracts.process_ir import CurrentnessBasis, ProcessContextSnapshot
from cyber_lion.enterprise.process_semantics import TransitionSelector, apply_transition_outcome
from cyber_lion.process_language.lpcl import parse_lpcl, render_lpcl
from cyber_lion.process_language.reference_processes import SCENARIOS, all_reference_processes


def basis(requirement: str):
    return CurrentnessBasis(requirement_id=requirement,subject=requirement,observed_identity="reference:exact",evidence_ref="evidence:reference-readback",observed_at="2026-09-08T00:00:00+02:00",state="CURRENT",drift_rule="IDENTITY_CHANGED").sealed()


class ProcessReferenceCorpusTests(unittest.TestCase):
    def test_all_required_scenarios_share_one_canonical_kernel(self):
        self.assertEqual(len(SCENARIOS),12); processes=all_reference_processes(); self.assertEqual(len({item.process_digest for item in processes}),12)
        for item in processes: self.assertEqual(parse_lpcl(render_lpcl(item)),item)

    def test_all_reference_scenarios_have_dynamic_closure(self):
        processes=all_reference_processes(); self.assertEqual(len(processes),12)
        for ir in processes:
            with self.subTest(process_id=ir.as_dict()["process_id"]):
                model=ir.as_dict(); transition=model["transitions"][0]; currentness=tuple(basis(req) for req in transition["currentness_requirements"])
                ctx=ProcessContextSnapshot(process_ir_digest=ir.process_digest,process_state=model["initial_state"],satisfied_dependencies=tuple(transition["dependencies"]),satisfied_guards=tuple(transition["guards"]),satisfied_evidence_requirements=tuple(transition["evidence_requirements"]),currentness_bases=currentness,verified_authority_context_refs=tuple(transition["authority_requirements"]),observed_at="2026-09-08T00:00:00+02:00").validate_for(ir)
                selected=TransitionSelector(ir).bind_selected(ctx)
                action=transition["transition_class"]=="ACTION_REQUIRED"
                outcome=ProcessTransitionOutcome(process_id=model["process_id"],process_ir_digest=ir.process_digest,transition_id=transition["transition_id"],transition_decision_digest=selected.transition_decision_digest,attempt_number=1,outcome="PASS",next_state="DONE",action_ref="action:reference" if action else "",proposal_digest="a"*64 if action else "",admission_ref="admission:reference" if action else "",effect_ref="effect:reference" if action else "",observation_ref="observation:reference" if action else "",reconciliation_ref="reconciliation:reference" if action else "",currentness_basis_ref=currentness[0].basis_digest if action else "").sealed()
                updated=apply_transition_outcome(ir,ctx,selected,outcome)
                self.assertEqual(updated.process_state,"DONE")
                self.assertEqual(TransitionSelector(ir).select(updated).decision,"COMPLETE")


if __name__=="__main__": unittest.main()
