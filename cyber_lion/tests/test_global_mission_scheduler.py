import sqlite3
import unittest
from datetime import datetime, timezone

from cyber_lion.mission_control import global_scheduler as g


def now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class GlobalSchedulerTests(unittest.TestCase):
    def setUp(self):
        self.c = sqlite3.connect(":memory:")
        self.c.row_factory = sqlite3.Row
        self.c.executescript("""
        CREATE TABLE missions(mission_id TEXT PRIMARY KEY,state TEXT,updated_at TEXT,adapter TEXT,runtime_state TEXT,materialized INTEGER,ready INTEGER,last_error TEXT);
        CREATE TABLE mission_execution_drivers(mission_id TEXT PRIMARY KEY,state TEXT,heartbeat_at TEXT,current_phase TEXT);
        CREATE TABLE mission_phases(mission_id TEXT,phase_id TEXT,ordinal INTEGER,status TEXT);
        CREATE TABLE logical_drones(mission_id TEXT,logical_id TEXT,role TEXT,material_target INTEGER,materialized INTEGER,ready INTEGER,PRIMARY KEY(mission_id,logical_id));
        CREATE TABLE material_workers(mission_id TEXT,pod_name TEXT,pod_uid TEXT,logical_id TEXT,phase TEXT,ready INTEGER,restarts INTEGER,pod_ip TEXT,observed_at TEXT,PRIMARY KEY(mission_id,pod_name));
        """)
        g.migrate(self.c, now)

    def tearDown(self):
        self.c.close()

    def test_required_durable_tables_exist(self):
        tables={r[0] for r in self.c.execute("SELECT name FROM sqlite_master WHERE type='table'") }
        for name in ("mission_scheduler_state","mission_phase_execution_specs","mission_execution_assignments","mission_execution_receipts"):
            self.assertIn(name,tables)

    def test_unknown_handler_compiles_fail_closed(self):
        self.c.execute("INSERT INTO mission_phases VALUES('M','P1',1,'PENDING')")
        specs=g.compile_phase_specs(self.c,'M',{})
        self.assertEqual(specs[0]['handler_id'],'PHASE_HANDLER_NOT_REGISTERED')
        self.assertEqual(specs[0]['gate_class'],'WAITING')
        self.assertEqual(specs[0]['retry_policy'],'NO_AUTOMATIC_RETRY')

    def test_unknown_phase_resolver_is_pure_fail_closed(self):
        resolved=g.resolve_phase_execution_spec('__LION_UNKNOWN_HANDLER_CANARY__',{})
        self.assertEqual(resolved['handler_id'],'PHASE_HANDLER_NOT_REGISTERED')
        self.assertEqual(resolved['effect_class'],'NONE')
        self.assertEqual(resolved['gate_class'],'WAITING')
        self.assertEqual(resolved['retry_policy'],'NO_AUTOMATIC_RETRY')
        self.assertEqual(resolved['authority_class'],'NONE')

    def test_known_phase_resolver_preserves_registered_handler(self):
        configured={'KNOWN':{'handler_id':'VERIFY_KNOWN','effect_class':'CONTROL_STATE','gate_class':'EVIDENCE','retry_policy':'IDEMPOTENT','authority_class':'MISSION_CONTROL'}}
        resolved=g.resolve_phase_execution_spec('KNOWN',configured)
        self.assertEqual(resolved['handler_id'],'VERIFY_KNOWN')
        self.assertEqual(resolved['effect_class'],'CONTROL_STATE')
        self.assertEqual(resolved['gate_class'],'EVIDENCE')
        self.assertEqual(resolved['retry_policy'],'IDEMPOTENT')
        self.assertEqual(resolved['authority_class'],'MISSION_CONTROL')

    def test_waiting_run_does_not_block_active_run(self):
        for mid,state,ts in [('A','WAITING','2026-01-01T00:00:00Z'),('B','ACTIVE','2026-01-01T00:00:01Z')]:
            self.c.execute("INSERT INTO missions VALUES(?,?,?,?,?,?,?,?)",(mid,'RUNNING',ts,'x','x',0,0,None))
            self.c.execute("INSERT INTO mission_execution_drivers VALUES(?,?,?,?)",(mid,state,ts,'P'))
        pick=g.next_dispatch(self.c,now)
        self.assertEqual(pick['mission_id'],'B')
        snap=g.scheduler_snapshot(self.c)
        self.assertEqual(snap['queue_depth'],2)
        self.assertEqual(snap['active_run_count'],1)

    def test_default_128l64m_topology_is_exact_and_generic_adapter_is_preserved(self):
        self.c.execute("INSERT INTO missions VALUES(?,?,?,?,?,?,?,?)",('G','AUTHORIZED',now(),'LPCL_MISSION','NOT_STARTED',0,0,'x'))
        workers=[{'pod_name':f'p{i:02d}','pod_uid':f'uid-{i:02d}','phase':'Running','ready':1,'restarts':0,'pod_ip':f'10.0.0.{i+1}'} for i in range(64)]
        text=g.default_128l64m_topology_text()
        out=g.bind_128l64m(self.c,'G',text,workers,now,adapter='LPCL_GENERIC_128L64M',runtime_state='GENERIC_SHARED_HEALTHY_FLEET_128L64M')
        self.assertEqual((out['logical_count'],out['material_count'],out['assignments']),(128,64,128))
        row=self.c.execute("SELECT adapter,runtime_state FROM missions WHERE mission_id='G'").fetchone()
        self.assertEqual(tuple(row),('LPCL_GENERIC_128L64M','GENERIC_SHARED_HEALTHY_FLEET_128L64M'))

    def test_128l64m_binding_is_two_to_one_and_uid_exact(self):
        lp=[]
        for i in range(1,17):
            a=(i-1)*8+1;b=i*8;m1=(i-1)*4+1;m2=i*4
            lp += [f'COHORT_{i:02d}=',f'LD{a:03d}-LD{b:03d}','ROLE=',f'ROLE_{i:02d}','MATERIAL=',f'MD{m1:03d}-MD{m2:03d}']
        self.c.execute("INSERT INTO missions VALUES(?,?,?,?,?,?,?,?)",('M','AUTHORIZED',now(),'LPCL_MISSION','NOT_STARTED',0,0,'x'))
        workers=[{'pod_name':f'p{i:02d}','pod_uid':f'uid-{i:02d}','phase':'Running','ready':1,'restarts':0,'pod_ip':f'10.0.0.{i+1}'} for i in range(64)]
        out=g.bind_128l64m(self.c,'M','\n'.join(lp),workers,now)
        self.assertEqual(out['assignments'],128)
        self.assertEqual(self.c.execute("SELECT COUNT(*) FROM logical_drones WHERE mission_id='M'").fetchone()[0],128)
        self.assertEqual(self.c.execute("SELECT COUNT(*) FROM material_workers WHERE mission_id='M'").fetchone()[0],64)
        counts=[r[0] for r in self.c.execute("SELECT COUNT(*) FROM mission_execution_assignments WHERE mission_id='M' GROUP BY material_drone_id")]
        self.assertEqual(counts,[2]*64)

    def test_local_assignment_claim_is_durable_and_fenced(self):
        self.c.execute("INSERT INTO missions VALUES(?,?,?,?,?,?,?,?)",('M','RUNNING',now(),'x','x',0,0,None))
        aid=g.create_assignment(self.c,'M','LOCAL','LD001','MD001',{'prompt':'x'},now,lease_generation=1)
        pending=g.pending_local_assignments(self.c,mission_id='M')
        self.assertEqual([x['assignment_id'] for x in pending],[aid])
        with self.assertRaisesRegex(ValueError,'material identity mismatch'):
            g.claim_assignment(self.c,aid,now,expected_material_drone_id='MD002')
        out=g.claim_assignment(self.c,aid,now,expected_material_drone_id='MD001')
        self.assertEqual(out['state'],'CLAIMED')
        self.assertIn('\"prompt\":\"x\"',out['input_json'])
        self.assertEqual(g.pending_local_assignments(self.c,mission_id='M'),[])
        with self.assertRaisesRegex(ValueError,'not ready'):
            g.claim_assignment(self.c,aid,now,expected_material_drone_id='MD001')

    def test_duplicate_receipt_fails_closed_without_replacing_first(self):
        self.c.execute("INSERT INTO missions VALUES(?,?,?,?,?,?,?,?)",('M','RUNNING',now(),'x','x',0,0,None))
        aid=g.create_assignment(self.c,'M','P','LD001','MD001',{'x':1},now,lease_generation=1)
        a=g.record_internal_receipt(self.c,aid,{'ok':True},now)
        self.assertFalse(a['duplicate'])
        with self.assertRaisesRegex(ValueError,'assignment receipt duplicate'):
            g.record_internal_receipt(self.c,aid,{'ok':True},now)
        rows=self.c.execute('SELECT receipt_id FROM mission_execution_receipts WHERE assignment_id=?',(aid,)).fetchall()
        self.assertEqual([r[0] for r in rows],[a['receipt_id']])


    def test_assignment_payload_is_digest_bound_and_generic_action_receipt_is_exactly_once(self):
        self.c.execute("ALTER TABLE mission_execution_drivers ADD COLUMN generation INTEGER NOT NULL DEFAULT 1")
        self.c.execute("INSERT INTO missions VALUES(?,?,?,?,?,?,?,?)",('M','RUNNING',now(),'x','x',0,0,None))
        self.c.execute("INSERT INTO mission_execution_drivers(mission_id,state,heartbeat_at,current_phase,generation) VALUES(?,?,?,?,?)",('M','ACTIVE',now(),'P',1))
        aid=g.create_assignment(self.c,'M','P','LD001','MD025',{'kind':'LOCAL_MODEL_INFERENCE'},now,lease_generation=1)
        g.claim_assignment(self.c,aid,now,expected_material_drone_id='MD025')
        result={'kind':'LOCAL_MODEL_INFERENCE','response_text':'bounded plan','authority_effect':'NONE'}
        rec=g.record_receipt(self.c,aid,result,now,material_drone_id='MD025',lease_generation=1,status='PASS',authority_effect='NONE')
        stored=g.store_assignment_payload(self.c,aid,rec['receipt_id'],result,now)
        self.assertFalse(stored['idempotent']);self.assertEqual(g.assignment_payload(self.c,aid)['result'],result)
        stored2=g.store_assignment_payload(self.c,aid,rec['receipt_id'],result,now);self.assertTrue(stored2['idempotent'])
        action_ir={'schema_version':'1.0.0','action_id':'a','kind':'filesystem.read','intent_ref':'i','mission_ref':'M','autonomy_ref':'A','bean_ref':'B','target':{'host':'H','environment':'E','runtime':'R'},'authority_request':{'domain':'mission_control','capability':'READ','grant_ref':None},'boundary':{'shell':False,'network':'DENY','filesystem_read':['/tmp/x'],'filesystem_write':[],'process_children':[],'timeout_ms':1000,'max_processes':1,'memory_limit_bytes':1048576},'preconditions':['CURRENT'],'expected_effects':['READ_ONLY_EVIDENCE'],'forbidden_effects':['WRITE'],'observation':{'observer_class':'deterministic_independent','required_events':['READBACK']},'reconciliation':{'mode':'EXACT','receipt':'REQUIRED'}}
        plan=g.put_generic_phase_plan(self.c,mission_id='M',phase_id='P',planning_assignment_id=aid,planning_receipt_id=rec['receipt_id'],planning_result_digest=rec['result_digest'],planning_payload_state='RETAINED',state='CAPABILITY_RESOLUTION',capability='READ',target='/tmp/x',operation='READ',required_inputs={},expected_output={},authority_class='NONE',currentness_requirements=['CURRENT'],evidence_requirements=['READBACK'],rollback_class='NONE',dependencies=[rec['receipt_id']],action_ir=action_ir,action_ir_digest=g.digest(action_ir),now_fn=now,executor_id='TEST')
        evidence={'ok':True}
        out=g.record_generic_action_receipt(self.c,plan['plan_id'],now,status='PASS',evidence=evidence,authority_effect='NONE')
        self.assertEqual(out['status'],'PASS')
        with self.assertRaisesRegex(ValueError,'generic action receipt duplicate'):
            g.record_generic_action_receipt(self.c,plan['plan_id'],now,status='PASS',evidence=evidence,authority_effect='NONE')


if __name__ == '__main__':
    unittest.main()
