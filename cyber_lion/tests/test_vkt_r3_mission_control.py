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
 def test_source_is_read_only(self):
  text=(Path(__file__).resolve().parents[2]/'cyber_lion/vkt_r3/mission_control/source.py').read_text(); self.assertIn("'evidence'",text); self.assertNotIn("'materialize'",text); self.assertNotIn("'stop'",text); self.assertNotIn('kubectl',text)
 def test_server_binds_localhost_by_default(self):
  text=(Path(__file__).resolve().parents[2]/'tools/vkt_r3_mission_control.py').read_text(); self.assertIn("default='127.0.0.1'",text)
if __name__=='__main__': unittest.main()
