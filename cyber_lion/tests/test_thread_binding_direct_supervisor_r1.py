import tempfile,unittest
from pathlib import Path
from tools.lion_local_intelligence_runtime import ThreadStore
ROOT=Path(__file__).resolve().parents[2]

class ThreadBindingDirectSupervisorR1Tests(unittest.TestCase):
 def test_binding_persists_reopen_rebind_and_unbind_without_losing_messages(self):
  with tempfile.TemporaryDirectory() as td:
   path=Path(td)/'threads.db';store=ThreadStore(path);t=store('create',{});tid=t['thread_id']
   store('append_pair',{'thread_id':tid,'user':'u','assistant':'a','meta':{}})
   b1=store('bind_context',{'thread_id':tid,'mission_id':'M1','mission_phase_snapshot':'P1','channel':'SAAS_DIRECT','provider':'OPENAI','binding_state':'MISSION_BOUND'})
   self.assertEqual(b1['binding_revision'],1)
   reopened=ThreadStore(path);r=reopened('get',{'thread_id':tid});self.assertEqual((r['mission_id'],r['mission_phase_snapshot'],r['channel'],r['provider'],r['binding_revision'],r['binding_state']),('M1','P1','SAAS_DIRECT','OPENAI',1,'MISSION_BOUND'));self.assertEqual(len(r['messages']),2)
   b2=reopened('bind_context',{'thread_id':tid,'mission_id':'M2','mission_phase_snapshot':'P2','channel':'DUAL','provider':'OPENAI','binding_state':'MISSION_BOUND'});self.assertEqual(b2['binding_revision'],2)
   b3=reopened('bind_context',{'thread_id':tid,'mission_id':None,'mission_phase_snapshot':None,'channel':'LOCAL','provider':None,'binding_state':'MISSION_UNBOUND'});self.assertEqual(b3['binding_revision'],3)
   final=reopened('get',{'thread_id':tid});self.assertIsNone(final['mission_id']);self.assertEqual(final['channel'],'LOCAL');self.assertEqual(final['binding_state'],'MISSION_UNBOUND');self.assertEqual(len(final['messages']),2)
 def test_thread_list_order_is_creation_order_not_updated_at(self):
  with tempfile.TemporaryDirectory() as td:
   store=ThreadStore(Path(td)/'threads.db');a=store('create',{})['thread_id'];b=store('create',{})['thread_id'];store('append_pair',{'thread_id':a,'user':'late update','assistant':'x','meta':{}});rows=store('list',{})['threads'];self.assertEqual(rows[0]['thread_id'],b)
 def test_direct_bridge_service_has_secret_boundary_and_loopback(self):
  unit=(ROOT/'deploy/systemd/lion-direct-supervisor-bridge.service').read_text()
  self.assertIn('EnvironmentFile=-/etc/lion/direct-supervisor.env',unit);self.assertNotIn('OPENAI_API_KEY=',unit)
  self.assertIn('--host 127.0.0.1 --port 8768',unit);self.assertIn('NoNewPrivileges=true',unit);self.assertIn('ProtectSystem=strict',unit)
  self.assertIn('ReadWritePaths=/var/lib/sentinelx/uploads/lion-mission-control-v3',unit)
 def test_direct_bridge_source_has_no_provider_tools_and_bounded_resources(self):
  src=(ROOT/'tools/lion_direct_supervisor_bridge.py').read_text()
  self.assertIn("MAX_INFLIGHT=1",src);self.assertIn("MAX_INPUT_SIZE=8000",src);self.assertIn("MAX_OUTPUT_TOKENS=2048",src);self.assertIn("RETRY_MAX=0",src)
  self.assertIn("ALLOWED_PROVIDER_HOSTS={'api.openai.com'}",src);self.assertNotIn("'tools':",src);self.assertIn("Idempotency-Key",src)
if __name__=='__main__':unittest.main()
