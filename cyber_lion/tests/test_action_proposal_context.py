from __future__ import annotations
import ast
from dataclasses import replace
from pathlib import Path
import unittest
from cyber_lion.contracts.action_ir import CanonicalActionIR
from cyber_lion.contracts.action_proposal_context import OPTIONAL_CONTEXT_FIELDS,REQUIRED_CONTEXT_FIELDS,ActionProposalContextBindingError,ExplicitActionProposalContext,bind_lair_to_action_proposal
from cyber_lion.enterprise.complete_mediation import EffectSurfaceScanner
class ExplicitActionProposalContextTests(unittest.TestCase):
    def ir_value(self):
        return {"schema_version":"1.0.0","action_id":"r19n.observe.1","kind":"repository.observe","intent_ref":"intent:r19n","mission_ref":"mission:r19n-source","autonomy_ref":"autonomy:lion","bean_ref":"bean:r19n","target":{"host":"github","environment":"candidate","runtime":"none"},"authority_request":{"domain":"repository","capability":"observe","grant_ref":None},"boundary":{"shell":False,"network":"DENY","filesystem_read":[],"filesystem_write":[],"process_children":[],"timeout_ms":1000,"max_processes":1,"memory_limit_bytes":1048576},"preconditions":["baseline-exact"],"expected_effects":[],"forbidden_effects":["execution","authority-minting"],"observation":{"observer_class":"deterministic_independent","required_events":["ir-validated"]},"reconciliation":{"mode":"EXACT","receipt":"REQUIRED"}}
    def context(self,ir,**changes):
        fields=tuple(sorted(REQUIRED_CONTEXT_FIELDS+OPTIONAL_CONTEXT_FIELDS)); values=dict(proposal_id="proposal:r19n",mission_id="mission:explicit",swarm_id="swarm:explicit",proposer_agent_id="agent:explicit",capability="capability.explicit",requested_authority="read",action_class="READ_FILE",target="workspace/explicit.txt",consequential=True,evidence_refs=("evidence:explicit",),required_observability=("trace",),verifier_agent_id="verifier:explicit",expected_lair_payload_digest=ir.payload_digest,field_provenance=tuple((name,f"context:{name}") for name in fields)); values.update(changes); return ExplicitActionProposalContext(**values)
    def test_complete_explicit_context_constructs_actionproposal_and_binds_payload_only_from_lair(self):
        ir=CanonicalActionIR.from_mapping(self.ir_value()); proposal=bind_lair_to_action_proposal(ir,self.context(ir)); self.assertEqual(proposal.payload_digest,ir.payload_digest); self.assertEqual((proposal.mission_id,proposal.capability,proposal.requested_authority,proposal.action_class,proposal.target),("mission:explicit","capability.explicit","read","READ_FILE","workspace/explicit.txt"))
    def test_context_values_are_not_inferred_from_lair_similar_names(self):
        ir=CanonicalActionIR.from_mapping(self.ir_value()); proposal=bind_lair_to_action_proposal(ir,self.context(ir)); raw=ir.as_dict(); self.assertNotEqual(proposal.mission_id,raw["mission_ref"]); self.assertNotEqual(proposal.capability,raw["authority_request"]["capability"]); self.assertNotEqual(proposal.action_class,raw["kind"]); self.assertNotEqual(proposal.target,str(raw["target"]))
    def test_payload_digest_mismatch_is_denied(self):
        ir=CanonicalActionIR.from_mapping(self.ir_value());
        with self.assertRaisesRegex(ActionProposalContextBindingError,"payload digest mismatch"): bind_lair_to_action_proposal(ir,self.context(ir,expected_lair_payload_digest="f"*64))
    def test_missing_or_ambiguous_provenance_is_denied(self):
        ir=CanonicalActionIR.from_mapping(self.ir_value()); ctx=self.context(ir)
        with self.assertRaisesRegex(ActionProposalContextBindingError,"cover exactly"): replace(ctx,field_provenance=ctx.field_provenance[:-1]).validate()
        with self.assertRaisesRegex(ActionProposalContextBindingError,"duplicates"): replace(ctx,field_provenance=ctx.field_provenance+(ctx.field_provenance[0],)).validate()
    def test_nonconsequential_optionality_matches_live_contract(self):
        ir=CanonicalActionIR.from_mapping(self.ir_value()); p=bind_lair_to_action_proposal(ir,self.context(ir,consequential=False,evidence_refs=(),required_observability=())); self.assertFalse(p.consequential); self.assertEqual(p.evidence_refs,()); self.assertEqual(p.required_observability,())
    def test_consequential_requires_evidence_and_observability(self):
        ir=CanonicalActionIR.from_mapping(self.ir_value())
        with self.assertRaisesRegex(ActionProposalContextBindingError,"ActionProposal context validation failed"): bind_lair_to_action_proposal(ir,self.context(ir,evidence_refs=()))
        with self.assertRaisesRegex(ActionProposalContextBindingError,"ActionProposal context validation failed"): bind_lair_to_action_proposal(ir,self.context(ir,required_observability=()))
    def test_exact_input_types_and_closed_context_surface(self):
        ir=CanonicalActionIR.from_mapping(self.ir_value())
        with self.assertRaisesRegex(ActionProposalContextBindingError,"exact CanonicalActionIR"): bind_lair_to_action_proposal(self.ir_value(),self.context(ir))
        with self.assertRaisesRegex(ActionProposalContextBindingError,"exact ExplicitActionProposalContext"): bind_lair_to_action_proposal(ir,{})
        values=self.context(ir).__dict__.copy(); values["unknown"]="x"
        with self.assertRaises(TypeError): ExplicitActionProposalContext(**values)
    def test_binder_source_has_no_effect_surface_or_runtime_policy_imports(self):
        path=Path("cyber_lion/contracts/action_proposal_context.py"); source=path.read_text(encoding="utf-8"); tree=ast.parse(source); forbidden={"runtime_execution","runtime_enforcement","policy_gate","effect_provider","executor_sandbox"}; imported=set()
        for node in ast.walk(tree):
            if isinstance(node,ast.ImportFrom) and node.module: imported.add(node.module.rsplit(".",1)[-1])
            elif isinstance(node,ast.Import): imported.update(alias.name.rsplit(".",1)[-1] for alias in node.names)
        self.assertFalse(imported&forbidden); inv=EffectSurfaceScanner().scan(repository="DonkeyJJLove/ai_platform",revision="0"*40,tree_digest="0"*40,sources={str(path):source}); self.assertEqual(inv.surfaces,())
    def test_context_digest_is_deterministic(self):
        ir=CanonicalActionIR.from_mapping(self.ir_value()); self.assertEqual(self.context(ir).digest(),self.context(ir).digest())
if __name__=="__main__": unittest.main()
