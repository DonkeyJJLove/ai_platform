from __future__ import annotations
import importlib,json,sqlite3,sys,tempfile,unittest
from pathlib import Path

class MissionHistoryLifecycleTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  tools=Path(__file__).resolve().parents[2]/'tools';sys.path.insert(0,str(tools)) if str(tools) not in sys.path else None
  compat=importlib.import_module('lion_mission_control_compat');sys.modules['mission_control_compat']=compat
  cls.mc=importlib.import_module('lion_mission_control_v3');cls.life=importlib.import_module('lion_mission_lifecycle_db');cls.local=importlib.import_module('lion_local_intelligence_runtime')
 def setUp(self):
  self.td=tempfile.TemporaryDirectory();self.addCleanup(self.td.cleanup);root=Path(self.td.name);self.old=(self.mc.DB,self.mc.LEGACY_DB);self.addCleanup(self._restore);self.mc.DB=root/'mc.db';self.mc.LEGACY_DB=root/'legacy.db'
  c=sqlite3.connect(self.mc.LEGACY_DB);c.execute('CREATE TABLE runs(run_id TEXT PRIMARY KEY,payload TEXT NOT NULL)');c.execute('INSERT INTO runs VALUES(?,?)',('vkt-r3-live',json.dumps({'process_class':'VKT_R3_384_DRONE_TEST','adapter_type':'VKT_R3','status':'RUNNING','source':{'head':'7'*40,'tree':'8'*40},'workload':{'pods':83},'metrics':{'ready':70},'evidence':{'class':'KUBERNETES_RUNTIME'}})));c.commit();c.close();self.mc.migrate()
  self.head='f937790d481489d9fafd2506f3e0148678c6fe4f';self.tree='66d9a0c5727294ddb8a3fa350ccd17455c29c90c';self.t1=self.mc.EPOCH3_LIFECYCLE_TARGET_1;self.t2=self.mc.EPOCH3_LIFECYCLE_TARGET_2;self.s=self.mc.EPOCH3_LIFECYCLE_SUCCESSOR;self._seed()
 def _restore(self):self.mc.DB,self.mc.LEGACY_DB=self.old
 def _add(self,c,mid,adapter,digest,state,runtime,auth,progress,phase=None,error=None):
  t=self.mc.now();c.execute('INSERT INTO missions(mission_id,title,adapter,spec_digest,source_head,source_tree,namespace,state,runtime_state,logical_count,material_target,materialized,ready,created_at,authorized_at,updated_at,last_error,spec_json) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(mid,mid,adapter,digest,'1'*40,'2'*40,None,state,runtime,128,64,64,64,t,t,t,error,'{}'));c.execute('INSERT INTO mission_process_specs(mission_id,title,objective,description,lpcl_digest,lpcl_text,protocols_json,authority_state,current_phase,progress,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(mid,mid,'o','d',digest,'x','[]',auth,phase,progress,t,t))
 def _seed(self):
  c=self.mc.connect();self._add(c,self.s,'LPCL_GENERIC_128L64M','a'*64,'COMPLETE','DRIVER_COMPLETE','EXPLICIT_USER_ACTIVATION',100);self.mc.ensure_driver(c,self.s,self.mc.now,initial_state='COMPLETE');self.mc._process_message(c,self.s,'CURRENTNESS','TEST','MISSION_CONTROL',None,{'event':'SUCCESSOR_SOURCE_CURRENTNESS_REBOUND','current_source_head':self.head,'current_source_tree':self.tree,'ancestry_verified':True},'INTERNAL')
  self._add(c,self.t1,'LPCL_REBOUND_EPOCH3_128L64M',self.mc.EPOCH3_LIFECYCLE_TARGET_1_DIGEST,'WAITING','DRIVER_WAITING','EXPLICIT_USER_ACTIVATION',33.333333333333336,'MISSION_CONTROL_DELTA_REFRESH');self.mc.ensure_driver(c,self.t1,self.mc.now,initial_state='STOPPED')
  self._add(c,self.t2,'LPCL_REBOUND_EPOCH3_64',self.mc.EPOCH3_LIFECYCLE_TARGET_2_DIGEST,'RUNNING','RUNNING','SUPERSEDED_BY_EXACT_LPCL',57,None,'historical bind failure')
  self._add(c,self.mc.EPOCH3_LIFECYCLE_TASK,'LPCL_GENERIC_128L64M',self.mc.EPOCH3_LIFECYCLE_TASK_DIGEST,'AUTHORIZED','NOT_STARTED','EXPLICIT_USER_ACTIVATION',0)
  for i in range(1,37):
   status='PASS' if i<=12 else ('WAITING' if i==13 else 'PENDING');pid='MISSION_CONTROL_DELTA_REFRESH' if i==13 else f'P{i:02d}';c.execute('INSERT INTO mission_phases(mission_id,phase_id,ordinal,title,status,progress,detail,started_at,finished_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)',(self.t1,pid,i,pid,status,100 if i<=12 else 0,None,None,None,self.mc.now()))
  c.commit();c.close()
 def _norm(self,head=None):
  c=self.mc.connect()
  try:return self.life.normalize_epoch3_terminal_lifecycle(c,target_1_mission_id=self.t1,target_1_expected_spec_digest=self.mc.EPOCH3_LIFECYCLE_TARGET_1_DIGEST,target_2_mission_id=self.t2,target_2_expected_spec_digest=self.mc.EPOCH3_LIFECYCLE_TARGET_2_DIGEST,successor_mission_id=self.s,expected_current_head=head or self.head,expected_current_tree=self.tree,now_fn=self.mc.now)
  finally:c.close()
 def test_protocol_extensions_are_canonical(self):
  e={'LIFECYCLE','HISTORY','LINEAGE'};self.assertTrue(e<=set(self.mc.PROTOCOLS));self.assertTrue(e<=set(self.local.LpclControlBridge.ALLOWED_PROTOCOLS))
 def test_vkt_is_preserved_legacy_history(self):
  c=self.mc.connect();x=self.life.mission_lifecycle_classification(c,'legacy::vkt-r3-live');p=self.life.mission_delete_preview(c,'legacy::vkt-r3-live',self.mc.MISSION);c.close();self.assertEqual(x['lifecycle_class'],'LEGACY_HISTORY');self.assertFalse(x['operational']);self.assertFalse(p['allowed']);self.assertEqual(p['reason'],'LEGACY_HISTORY_PRESERVATION_POLICY')
 def test_normalization_is_truth_preserving_and_idempotent(self):
  out=self._norm();self.assertFalse(out['already_normalized']);c=self.mc.connect();m1=c.execute('SELECT state,runtime_state FROM missions WHERE mission_id=?',(self.t1,)).fetchone();p1=c.execute('SELECT authority_state,current_phase,progress FROM mission_process_specs WHERE mission_id=?',(self.t1,)).fetchone();d1=c.execute('SELECT state,next_action FROM mission_execution_drivers WHERE mission_id=?',(self.t1,)).fetchone();m2=c.execute('SELECT state,runtime_state,last_error FROM missions WHERE mission_id=?',(self.t2,)).fetchone();v=c.execute('SELECT state FROM missions WHERE mission_id=?',('legacy::vkt-r3-live',)).fetchone()[0];r=c.execute("SELECT COUNT(*) FROM mission_action_receipts WHERE action='EPOCH3_LIFECYCLE_NORMALIZE'").fetchone()[0];c.close();self.assertEqual(tuple(m1),('SUPERSEDED','SUPERSEDED_BY:'+self.s));self.assertEqual(tuple(p1),('SUPERSEDED_BY_CURRENT_CONTROL_PLANE',None,33.333333333333336));self.assertEqual(tuple(d1),('SUPERSEDED','NONE_SUPERSEDED'));self.assertEqual(tuple(m2),('SUPERSEDED','HISTORICAL_SUPERSEDED','historical bind failure'));self.assertEqual(v,'RECORDED_RUNNING');self.assertEqual(r,2);self.assertTrue(self._norm()['already_normalized']);c=self.mc.connect();self.assertEqual(c.execute("SELECT COUNT(*) FROM mission_action_receipts WHERE action='EPOCH3_LIFECYCLE_NORMALIZE'").fetchone()[0],2);c.close()
 def test_normalization_fails_closed_on_source_drift_and_inflight(self):
  with self.assertRaisesRegex(ValueError,'SOURCE_CURRENTNESS'):self._norm('0'*40)
  c=self.mc.connect();c.execute("INSERT INTO mission_execution_assignments(assignment_id,mission_id,phase_id,logical_drone_id,material_drone_id,input_digest,input_json,state,lease_generation,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)",('a1',self.t1,'P14','LD01','MD01','1'*64,'{}','CLAIMED',1,self.mc.now()));c.commit();c.close()
  with self.assertRaisesRegex(ValueError,'CLAIMED_ASSIGNMENT'):self._norm()
 def test_registry_views_separate_history(self):
  self._norm();op={x['mission_id'] for x in self.mc.recent_process_missions('operational')};hist={x['mission_id'] for x in self.mc.recent_process_missions('history')};self.assertTrue({'legacy::vkt-r3-live',self.t1,self.t2}<=hist);self.assertFalse({'legacy::vkt-r3-live',self.t1,self.t2}&op);rows={x['mission_id']:x for x in self.mc.recent_process_missions('history')};self.assertEqual(rows['legacy::vkt-r3-live']['lifecycle_class'],'LEGACY_HISTORY');self.assertEqual(rows[self.t1]['lifecycle_class'],'SUPERSEDED')
 def test_both_panels_expose_history_toggle_and_backend_lifecycle_labels(self):
  root=Path(__file__).resolve().parents[2]
  mc=(root/'deploy/mission-control/v3/control-v3.js').read_text(encoding='utf-8')+(root/'deploy/mission-control/v3/index.html').read_text(encoding='utf-8')
  panel=(root/'cyber_lion/app_coordination/local_intelligence_gateway.py').read_text(encoding='utf-8')
  for src in (mc,panel):
   self.assertIn('History / Legacy',src);self.assertIn('lifecycle_class',src);self.assertIn('LEGACY_HISTORY',src);self.assertIn('SUPERSEDED',src)
  self.assertIn("execution_controls_allowed===false",mc);self.assertIn("execution_controls_allowed===false",panel)

 def test_dedicated_endpoint_requires_exact_activated_task_and_creates_one_backup(self):
  x={'task_mission_id':self.mc.EPOCH3_LIFECYCLE_TASK,'task_lpcl_digest':self.mc.EPOCH3_LIFECYCLE_TASK_DIGEST,'source_head':self.head,'source_tree':self.tree}
  first=self.mc.execute_epoch3_lifecycle_normalization(x);self.assertFalse(first['already_normalized']);self.assertEqual(first['backup']['integrity'],'ok');self.assertEqual(len(first['backup']['sha256']),64);self.assertTrue(Path(first['backup']['path']).is_file())
  c=self.mc.connect();bcount=c.execute("SELECT COUNT(*) FROM mission_rollback_points WHERE mission_id=? AND rollback_class='SQLITE_CONSISTENT_BACKUP'",(self.mc.EPOCH3_LIFECYCLE_TASK,)).fetchone()[0];rcount=c.execute("SELECT COUNT(*) FROM mission_action_receipts WHERE mission_id=? AND action='PRE_NORMALIZATION_DATABASE_BACKUP'",(self.mc.EPOCH3_LIFECYCLE_TASK,)).fetchone()[0];c.close();self.assertEqual((bcount,rcount),(1,1))
  replay=self.mc.execute_epoch3_lifecycle_normalization(x);self.assertTrue(replay['already_normalized']);self.assertIsNone(replay['backup']);c=self.mc.connect();self.assertEqual(c.execute("SELECT COUNT(*) FROM mission_rollback_points WHERE mission_id=? AND rollback_class='SQLITE_CONSISTENT_BACKUP'",(self.mc.EPOCH3_LIFECYCLE_TASK,)).fetchone()[0],1);c.execute("UPDATE mission_process_specs SET authority_state='NONE' WHERE mission_id=?",(self.mc.EPOCH3_LIFECYCLE_TASK,));c.commit();c.close();self.assertRaisesRegex(ValueError,'not explicitly activated',self.mc.execute_epoch3_lifecycle_normalization,x)

if __name__=='__main__':unittest.main()
