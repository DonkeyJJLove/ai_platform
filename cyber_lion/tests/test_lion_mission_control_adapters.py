import unittest
from cyber_lion.mission_control.adapters import LPCLEventStreamAdapter
from cyber_lion.mission_control.adapters.vkt_r3 import VKTR3Adapter
class EmptyVKT(VKTR3Adapter):
 def __init__(self):pass
 def _read(self):return {'status':'PARTIAL','materialized':0,'router_state':{}}
class T(unittest.TestCase):
 def test_generic_adapter_no_control(self):self.assertEqual(LPCLEventStreamAdapter.adapter_id,'LPCL_EVENT_STREAM')
 def test_absent_vkt_is_not_phantom_run(self):self.assertEqual(EmptyVKT().discover_runs(),[])
if __name__=='__main__':unittest.main()
