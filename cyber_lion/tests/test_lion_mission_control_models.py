import unittest
from cyber_lion.mission_control.models import clean_run
class T(unittest.TestCase):
 def test_unknown_degrades(self):self.assertEqual(clean_run({'run_id':'x','status':'MAGIC'})['status'],'UNKNOWN')
if __name__=='__main__':unittest.main()
