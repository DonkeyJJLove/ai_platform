import unittest
from cyber_lion.mission_control.adapters import LPCLEventStreamAdapter
class T(unittest.TestCase):
 def test_generic_adapter_no_control(self):self.assertEqual(LPCLEventStreamAdapter.adapter_id,'LPCL_EVENT_STREAM')
if __name__=='__main__':unittest.main()
