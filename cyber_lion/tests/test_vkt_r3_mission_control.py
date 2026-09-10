import tempfile,unittest
from pathlib import Path
from cyber_lion.vkt_r3.mission_control.models import normalize,verify_read_only
from cyber_lion.vkt_r3.mission_control.storage import Store

class MissionControlTests(unittest.TestCase):
 def sample(self): return {'materialized':384,'ready':384,'restart_count_total':0,'unique_uid_count':384,'pod_uid_set_sha256':'a'*64,'vendor_requests':0,'by_fleet':{'TIGER':{'ready':128},'SPECTRA':{'ready':128},'LION':{'ready':128}},'router_state':{'fresh_count':384,'fresh_by_fleet':{'TIGER':128,'SPECTRA':128,'LION':128},'messages_total':768,'ack_count':768,'ack_rate':1.0,'duplicates':0,'orphans':0,'cases_total':36,'cases_seen':36,'cases_proven':36,'participants':{},'mission':{'completed':True},'events':[{'event_id':'e1','timestamp':1,'event_type':'TEST_COMPLETED'}],'messages':[{'message_id':'m1','timestamp':1,'from_fleet':'TIGER','from_pod_uid':'u','to_fleet':'SPECTRA','case_id':'VKT-R3-CASE-01','phase':'TIGER_RELATION_ANALYSIS','correlation_id':'c','parent_message_id':None}]}}
 def test_normalize(self):
  x=normalize(self.sample()); self.assertEqual(x['fresh_drones'],384); self.assertEqual(x['cases_proven'],36); self.assertEqual(verify_read_only(x),[])
 def test_sqlite_roundtrip(self):
  with tempfile.TemporaryDirectory() as d:
   s=Store(str(Path(d)/'mc.db')); x=normalize(self.sample()); s.persist(x); self.assertEqual(s.latest()['messages_total'],768); self.assertEqual(len(s.export()['messages']),1)
 def test_legacy_source_remains_read_only(self):
  text=(Path(__file__).resolve().parents[2]/'cyber_lion/vkt_r3/mission_control/source.py').read_text(); self.assertIn("'evidence'",text); self.assertNotIn("'materialize'",text); self.assertNotIn("'stop'",text); self.assertNotIn('kubectl',text)
 def test_generic_server_binds_localhost_by_default(self):
  text=(Path(__file__).resolve().parents[2]/'tools/lion_mission_control.py').read_text(); self.assertIn("default='127.0.0.1'",text)
 def test_generic_local_service_runs_as_sentinelx_with_bounded_port_fallback(self):
  root=Path(__file__).resolve().parents[2]
  unit=(root/'deploy/mission-control/lion-mission-control.service').read_text()
  self.assertIn('User=sentinelx',unit); self.assertIn('--source-identity /opt/lion/k3s-vkt-r3/source-identity.json',unit)
  self.assertIn('RuntimeDirectory=lion-mission-control lion-vkt-mission-control',unit); self.assertIn('RuntimeDirectoryMode=0755',unit)
  for port in range(8765,8776): self.assertIn(str(port),unit)
  self.assertIn('--listen-state /run/lion-mission-control/listen.json',unit)
  self.assertIn('--legacy-listen-state /run/lion-vkt-mission-control/listen.json',unit)
  self.assertIn('/run/lion-mission-control-read.sock',unit)
  self.assertIn('InaccessiblePaths=',unit)
  self.assertIn('/run/lion-vkt-effect-admission.sock',unit)
 def test_generic_observer_has_no_mutating_provider_authority(self):
  root=Path(__file__).resolve().parents[2]
  package='\n'.join(p.read_text() for p in (root/'cyber_lion/mission_control').rglob('*.py'))
  self.assertNotIn('START_OSS_REPO_TEST',package)
  self.assertNotIn('STOP_OSS_REPO_TEST',package)
  self.assertNotIn('MATERIALIZE_VKT_PODS',package)
  self.assertNotIn('PREPARE_LOCAL_K8S',package)
  proxy=(root/'tools/lion_mission_control_read_proxy.py').read_text()
  self.assertIn('READ_POD_EVIDENCE',proxy); self.assertIn('READ_OSS_REPO_TEST_EVIDENCE',proxy)
  self.assertNotIn('START_OSS_REPO_TEST',proxy); self.assertNotIn('STOP_OSS_REPO_TEST',proxy)
 def test_legacy_port_fallback_code_is_preserved(self):
  import errno
  from unittest.mock import patch
  from cyber_lion.vkt_r3.mission_control import server as srv
  calls=[]
  class FakeHTTP:
   def __init__(self,address,handler):
    calls.append(address[1])
    if address[1] in (8765,8766): raise OSError(errno.EADDRINUSE,'busy')
   def serve_forever(self): return None
   def server_close(self): return None
  class FakeThread:
   def __init__(self,*a,**kw): pass
   def start(self): pass
  class FakeStop:
   def set(self): pass
  class FakeMC:
   stop_event=FakeStop()
   def loop(self): pass
  with tempfile.TemporaryDirectory() as d, patch.object(srv,'ThreadingHTTPServer',FakeHTTP), patch.object(srv.threading,'Thread',FakeThread):
   srv.serve(FakeMC(),'127.0.0.1',8765,[8766,8767],str(Path(d)/'listen.json'))
  self.assertEqual(calls,[8765,8766,8767])
 def test_installer_binds_canonical_master_and_bootstraps_generic_observer(self):
  root=Path(__file__).resolve().parents[2]
  install=(root/'deploy/k8s/vkt-r3/install.sh').read_text()
  bootstrap=(root/'deploy/k8s/vkt-r3/bootstrap-authority.sh').read_text()
  self.assertIn('"branch":"master"',install)
  self.assertIn('deploy/mission-control/install.sh',bootstrap)
  self.assertIn('lion-mission-control.service',bootstrap)
  self.assertNotIn('systemctl restart lion-vkt-mission-control.service',bootstrap)
  self.assertNotIn('mission/vkt-r3-pod-materialization-r2',install+bootstrap)
 def test_generic_operator_locator_is_explicitly_world_readable(self):
  root=Path(__file__).resolve().parents[2]
  server=(root/'cyber_lion/mission_control/server.py').read_text()
  self.assertIn('os.chmod(p, 0o644)',server)
 def test_static_path_resolution_is_root_bounded(self):
  from cyber_lion.mission_control.server import _safe_static_target as generic_target
  from cyber_lion.vkt_r3.mission_control.server import _safe_static_target as legacy_target
  self.assertIsNone(generic_target('/../../etc/passwd'))
  self.assertIsNone(legacy_target('/../../etc/passwd'))
  self.assertIsNotNone(generic_target('/index.html'))
  self.assertIsNotNone(legacy_target('/index.html'))
 def test_header_value_rejects_response_splitting(self):
  from cyber_lion.mission_control.server import _safe_header_value as generic_header
  from cyber_lion.vkt_r3.mission_control.server import _safe_header_value as legacy_header
  for helper in (generic_header,legacy_header):
   self.assertEqual(helper('text/plain'),'text/plain')
   with self.assertRaises(ValueError): helper('text/plain\r\nX-Evil: 1')

if __name__=='__main__': unittest.main()
