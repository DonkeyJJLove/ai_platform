import pathlib,unittest
from cyber_lion.mission_control.models import clean_run
from cyber_lion.mission_control.schema import validate_event
class T(unittest.TestCase):
 def root(self):return pathlib.Path(__file__).resolve().parents[2]
 def test_read_only(self):
  r=self.root();s=(r/'cyber_lion/mission_control/server.py').read_text();a=(r/'cyber_lion/mission_control/adapters/oss_repository_test.py').read_text()
  self.assertIn('do_POST=do_PUT=do_PATCH=do_DELETE',s)
  for x in ('oss-start','oss-stop','kubectl','docker','sudo'):self.assertNotIn(x,a)
 def test_ui_no_controls_and_has_filters(self):
  r=self.root();j=(r/'cyber_lion/mission_control/static/app.js').read_text();h=(r/'cyber_lion/mission_control/static/index.html').read_text()
  for x in ('POST','DELETE','/start','/stop'):self.assertNotIn(x,j)
  for x in ('statusFilter','adapterFilter','processFilter'):self.assertIn(x,h)
 def test_malformed_event_denied(self):
  with self.assertRaises(ValueError):validate_event({'schema_version':'lion.observation-event/v1'})
 def test_unknown_never_promotes_to_pass(self):self.assertEqual(clean_run({'run_id':'x','status':'nonsense'})['status'],'UNKNOWN')
 def test_static_path_surface_is_allowlisted(self):
  s=(self.root()/'cyber_lion/mission_control/server.py').read_text();self.assertIn('STATIC_FILES',s);self.assertNotIn("lstrip('/')",s)
if __name__=='__main__':unittest.main()
