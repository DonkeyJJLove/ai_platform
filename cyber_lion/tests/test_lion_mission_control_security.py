import pathlib,unittest
class T(unittest.TestCase):
 def test_read_only(self):
  r=pathlib.Path(__file__).resolve().parents[2];s=(r/'cyber_lion/mission_control/server.py').read_text();a=(r/'cyber_lion/mission_control/adapters/oss_repository_test.py').read_text()
  self.assertIn('do_POST=do_PUT=do_PATCH=do_DELETE',s)
  for x in ('oss-start','oss-stop','kubectl','docker','sudo'): self.assertNotIn(x,a)
 def test_ui_no_controls(self):
  r=pathlib.Path(__file__).resolve().parents[2];j=(r/'cyber_lion/mission_control/static/app.js').read_text()
  for x in ('POST','DELETE','/start','/stop'):self.assertNotIn(x,j)
if __name__=='__main__':unittest.main()
