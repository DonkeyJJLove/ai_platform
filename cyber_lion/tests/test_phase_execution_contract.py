from __future__ import annotations
import unittest
from cyber_lion.contracts.phase_execution_contract import (
    PhaseExecutionContract, PhaseExecutionContractError, compile_panel_phase_contracts,
    preflight_execution_contracts, SCHEMA_ID,
)

class PhaseExecutionContractTests(unittest.TestCase):
    def declared_pairs(self):
        return {
            'PHASE_01_EXECUTION_CLASS':'VERIFY_THEN_REPAIR',
            'PHASE_01_CAPABILITY_CLASS':'REPOSITORY_AND_RUNTIME_RECONCILIATION',
            'PHASE_01_EFFECT_CEILING':'BOUNDED_REPOSITORY',
            'PHASE_01_BINDING_MODE':'DYNAMIC',
            'PHASE_01_ON_MISSING_CAPABILITY':'WAIT_AND_DISCOVER',
            'PHASE_01_AUTO_RESUME':'TRUE',
            'PHASE_01_VERIFY_BEFORE_MUTATE':'TRUE',
            'PHASE_01_CURRENTNESS':'EXACT_CURRENT_REPOSITORY,CURRENT_MISSION_RUNTIME',
            'PHASE_01_EVIDENCE':'LIVE_RUNTIME_READBACK,FOCUSED_REGRESSION',
            'PHASE_01_COMPLETION_01':'POSTCONDITION=PASS',
        }

    def test_lpcl_1_2_declared_contract_and_dynamic_preflight(self):
        c=compile_panel_phase_contracts(self.declared_pairs(),'M1',[{'id':'REPAIR'}],'LPCL/1.2')[0]
        self.assertEqual(c.as_dict()['schema'],SCHEMA_ID)
        self.assertEqual(c.contract_source,'DECLARED')
        pf=preflight_execution_contracts((c,),{})
        self.assertEqual(pf.mission_readiness,'WAITING_FOR_CAPABILITIES')
        self.assertEqual(pf.phases[0]['state'],'VALID_UNBOUND_WAITING')
        bound=preflight_execution_contracts((c,),{'REPOSITORY_AND_RUNTIME_RECONCILIATION':({'capability_id':'cap1','effect_ceiling':'NONE'},)})
        self.assertEqual(bound.mission_readiness,'READY_BOUND')
        self.assertEqual(bound.phases[0]['state'],'VALID_BOUND')

    def test_lpcl_1_1_compiles_safe_legacy_contract_without_mutation_authority(self):
        c=compile_panel_phase_contracts({},'M1',[{'id':'REPAIR'}],'LPCL/1.1')[0]
        self.assertEqual(c.contract_source,'LEGACY_INFERRED_SAFE')
        self.assertEqual(c.effect_ceiling,'NONE')
        self.assertEqual(c.binding_mode,'DYNAMIC')
        self.assertEqual(c.on_missing_capability,'WAIT_AND_DISCOVER')
        self.assertTrue(c.auto_resume)

    def test_verify_then_repair_requires_verify_before_mutate(self):
        pairs=self.declared_pairs();pairs['PHASE_01_VERIFY_BEFORE_MUTATE']='FALSE'
        with self.assertRaisesRegex(PhaseExecutionContractError,'verify_before_mutate'):
            compile_panel_phase_contracts(pairs,'M1',[{'id':'REPAIR'}],'LPCL/1.2')

    def test_lpcl_1_2_requires_complete_execution_contract(self):
        pairs=self.declared_pairs();del pairs['PHASE_01_EVIDENCE']
        with self.assertRaisesRegex(PhaseExecutionContractError,'missing execution contract fields'):
            compile_panel_phase_contracts(pairs,'M1',[{'id':'REPAIR'}],'LPCL/1.2')

    def test_effect_ceiling_is_not_authority_and_narrower_capability_may_bind(self):
        c=compile_panel_phase_contracts(self.declared_pairs(),'M1',[{'id':'REPAIR'}],'LPCL/1.2')[0]
        pf=preflight_execution_contracts((c,),{'REPOSITORY_AND_RUNTIME_RECONCILIATION':({'capability_id':'readonly','effect_ceiling':'NONE'},)})
        self.assertEqual(pf.bound_count,1)
        self.assertEqual(c.effect_ceiling,'BOUNDED_REPOSITORY')

if __name__=='__main__':unittest.main()
