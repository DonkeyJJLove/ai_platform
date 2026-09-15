from __future__ import annotations

import unittest

from cyber_lion.contracts.mission_contract_profiles import (
    GENERIC_ADAPTER_REPAIR_MISSION,
    POST_ASTRA_MISSION,
    SAAS_AUTOMATIC_MEDIATOR_MISSION,
    FIREFOX_PROJECT_MEDIATOR_SUCCESSOR_MISSION,
    migrated_contract_for,
    profile_phase_ids,
    post_astra_profile_phase_ids,
    saas_automatic_mediator_profile_phase_ids,
    firefox_project_mediator_successor_profile_phase_ids,
)
from cyber_lion.contracts.phase_execution_contract import preflight_execution_contracts


class MissionContractProfileTests(unittest.TestCase):
    PHASES = (
        "REPAIR_EXECUTION_BINDER",
        "REPAIR_BASE_TOPOLOGY_BOOTSTRAP",
        "IMPLEMENT_GENERIC_PHASE_COMPILER",
        "IMPLEMENT_GENERIC_PHASE_HANDLER",
        "MATERIALIZE_DRIVER",
        "GLOBAL_SCHEDULER_ACCEPTANCE",
        "DYNAMIC_DELEGATION_ACCEPTANCE",
        "RESTART_DURABILITY",
        "REAL_PANEL_MISSION_ACCEPTANCE",
        "RETRY_POST_ASTRA_SAAS_MISSION",
    )

    def test_profile_covers_every_effective_phase_after_initial_read_only_pair(self):
        self.assertEqual(profile_phase_ids(), self.PHASES)
        for ordinal, phase_id in enumerate(self.PHASES, 3):
            contract = migrated_contract_for(GENERIC_ADAPTER_REPAIR_MISSION, phase_id, ordinal)
            self.assertIsNotNone(contract, phase_id)
            contract.validate()
            self.assertEqual(contract.contract_source, "MIGRATED_EXPLICIT")
            self.assertTrue(contract.auto_resume)
            self.assertTrue(contract.verify_before_mutate)
            self.assertEqual(contract.binding_mode, "DYNAMIC")
            self.assertEqual(contract.on_missing_capability, "WAIT_AND_DISCOVER")
            self.assertTrue(contract.completion_predicates)

    def test_only_binder_repair_has_repository_effect_ceiling(self):
        for ordinal, phase_id in enumerate(self.PHASES, 3):
            contract = migrated_contract_for(GENERIC_ADAPTER_REPAIR_MISSION, phase_id, ordinal)
            if phase_id == "REPAIR_EXECUTION_BINDER":
                self.assertEqual(contract.effect_ceiling, "BOUNDED_REPOSITORY")
                self.assertEqual(contract.capability_classes, ("REPOSITORY_AND_RUNTIME_RECONCILIATION",))
                self.assertEqual(contract.execution_class, "VERIFY_THEN_REPAIR")
            else:
                self.assertEqual(contract.effect_ceiling, "NONE", phase_id)
                self.assertEqual(contract.capability_classes, ("MISSION_RUNTIME_RECONCILIATION",), phase_id)
                self.assertEqual(contract.execution_class, "VERIFY", phase_id)


    def test_post_astra_profile_is_exact_12_phase_read_only_closure(self):
        phases=post_astra_profile_phase_ids()
        self.assertEqual(len(phases),12)
        contracts=[migrated_contract_for(POST_ASTRA_MISSION,p,i) for i,p in enumerate(phases,1)]
        self.assertTrue(all(c is not None for c in contracts))
        for c in contracts:
            c.validate()
            self.assertEqual(c.effect_ceiling,'NONE')
            self.assertEqual(c.execution_class,'VERIFY')
            self.assertEqual(c.capability_classes,('MISSION_RUNTIME_RECONCILIATION',))
            self.assertEqual(c.completion_predicates,('POST_ASTRA_PHASE_EVIDENCE=PASS',))
        pf=preflight_execution_contracts(contracts,{'MISSION_RUNTIME_RECONCILIATION':({'capability_id':'POST_ASTRA_READ_ONLY_RECON','executor_id':'MISSION_CONTROL_PROCESS_CONTRACT_RECONCILER','effect_ceiling':'NONE'},)})
        self.assertEqual((pf.bound_count,pf.unbound_count,pf.invalid_count,pf.mission_readiness),(12,0,0,'READY_BOUND'))
        self.assertIsNone(migrated_contract_for('OTHER-MISSION',phases[0],1))


    def test_saas_automatic_mediator_profile_is_exact_32_phase_read_only_bootstrap(self):
        phases=saas_automatic_mediator_profile_phase_ids()
        self.assertEqual(len(phases),32)
        self.assertEqual(phases[0],"REACQUIRE_CANONICAL_SOURCE")
        self.assertEqual(phases[-1],"RETURN_TO_LION_SCAFFOLD")
        contracts=[migrated_contract_for(SAAS_AUTOMATIC_MEDIATOR_MISSION,p,i) for i,p in enumerate(phases,1)]
        self.assertTrue(all(c is not None for c in contracts))
        for c in contracts:
            c.validate()
            self.assertEqual(c.effect_ceiling,'NONE')
            self.assertEqual(c.execution_class,'VERIFY')
            self.assertEqual(c.capability_classes,('MISSION_RUNTIME_RECONCILIATION',))
            self.assertEqual(c.completion_predicates,('SAAS_MEDIATOR_PHASE_EVIDENCE=PASS',))
        pf=preflight_execution_contracts(contracts,{'MISSION_RUNTIME_RECONCILIATION':({'capability_id':'SAAS_MEDIATOR_BOOTSTRAP_RECON','executor_id':'MISSION_CONTROL_PROCESS_CONTRACT_RECONCILER','effect_ceiling':'NONE'},)})
        self.assertEqual((pf.bound_count,pf.unbound_count,pf.invalid_count,pf.mission_readiness),(32,0,0,'READY_BOUND'))
        self.assertIsNone(migrated_contract_for('OTHER-MISSION',phases[0],1))

    def test_firefox_project_mediator_successor_profile_is_exact_57_phase_read_only_bootstrap(self):
        phases=firefox_project_mediator_successor_profile_phase_ids()
        self.assertEqual(len(phases),57)
        self.assertEqual(phases[0],"REACQUIRE_CANONICAL_SOURCE")
        self.assertEqual(phases[4],"DISCOVER_FIREFOX_DEVELOPER")
        self.assertEqual(phases[46],"PRIMARY_REAL_ROUNDTRIP")
        self.assertEqual(phases[-1],"RETURN_TO_LION_SCAFFOLD")
        contracts=[migrated_contract_for(FIREFOX_PROJECT_MEDIATOR_SUCCESSOR_MISSION,p,i) for i,p in enumerate(phases,1)]
        self.assertTrue(all(c is not None for c in contracts))
        for c in contracts:
            c.validate()
            self.assertEqual(c.effect_ceiling,'NONE')
            self.assertEqual(c.execution_class,'VERIFY')
            self.assertEqual(c.capability_classes,('MISSION_RUNTIME_RECONCILIATION',))
            self.assertEqual(c.completion_predicates,('FIREFOX_MEDIATOR_PHASE_EVIDENCE=PASS',))
        pf=preflight_execution_contracts(contracts,{'MISSION_RUNTIME_RECONCILIATION':({'capability_id':'FIREFOX_MEDIATOR_SUCCESSOR_READ_ONLY_RECON','executor_id':'MISSION_CONTROL_PROCESS_CONTRACT_RECONCILER','effect_ceiling':'NONE'},)})
        self.assertEqual((pf.bound_count,pf.unbound_count,pf.invalid_count,pf.mission_readiness),(57,0,0,'READY_BOUND'))
        self.assertIsNone(migrated_contract_for('OTHER-MISSION',phases[0],1))

    def test_profile_is_exact_mission_scoped_and_does_not_infer_other_legacy_missions(self):
        self.assertIsNone(migrated_contract_for("UNRELATED-LEGACY-MISSION", "REPAIR_BASE_TOPOLOGY_BOOTSTRAP", 4))
        self.assertIsNone(migrated_contract_for(GENERIC_ADAPTER_REPAIR_MISSION, "UNKNOWN_PHASE", 13))


if __name__ == "__main__":
    unittest.main()
