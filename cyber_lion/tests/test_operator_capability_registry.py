import importlib,sys,unittest
from unittest.mock import patch
from tools import lion_mission_control_compat

class OperatorCapabilityRegistryTests(unittest.TestCase):
    def test_registry_advertises_only_materialized_operator_executors(self):
        with patch.dict(sys.modules,{'mission_control_compat':lion_mission_control_compat}):
            mc=importlib.import_module('tools.lion_mission_control_v3')
        reg=mc.process_capability_registry_snapshot()['capabilities']
        self.assertEqual(reg['OPERATOR_INTERVENTION'][0]['capability_id'],'OPERATOR_CONTROL_R1')
        self.assertEqual(reg['OPERATOR_INTERVENTION'][0]['executor_id'],'LION_OPERATOR_CONTROL_GATEWAY')
        ids={x['capability_id'] for x in reg['OPERATOR_CONTAINMENT']}
        self.assertEqual(ids,{'OPERATOR_CONTAINMENT_R1','OPERATOR_EMERGENCY_CONTAINMENT_R1'})
        self.assertTrue(all(x['effect_ceiling']!='NONE' for x in reg['OPERATOR_CONTAINMENT']))
if __name__=='__main__':unittest.main()
