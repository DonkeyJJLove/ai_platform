import sqlite3,unittest
from datetime import datetime,timezone
from cyber_lion.mission_control import execution_driver,global_scheduler,operator_control

def now():return datetime.now(timezone.utc).isoformat().replace('+00:00','Z')

class OperatorFullSATTests(unittest.TestCase):
    def setUp(self):
        self.c=sqlite3.connect(':memory:');self.c.row_factory=sqlite3.Row
        self.c.execute('CREATE TABLE missions(mission_id TEXT PRIMARY KEY,state TEXT,updated_at TEXT)');self.c.execute("INSERT INTO missions VALUES('SAT-M','RUNNING',?)",(now(),))
        self.c.execute('CREATE TABLE material_workers(mission_id TEXT,pod_name TEXT,logical_id TEXT)');self.c.executemany('INSERT INTO material_workers VALUES(?,?,?)',[('SAT-M','MD025','LD1'),('SAT-M','MD026','LD2')])
        self.c.execute('CREATE TABLE schema_migrations(version INTEGER,schema_id TEXT,applied_at TEXT,source_head TEXT,source_tree TEXT,migration_digest TEXT,note TEXT,UNIQUE(version,schema_id))')
        execution_driver.migrate(self.c,now,source_head='a'*40,source_tree='b'*40);global_scheduler.migrate(self.c,now);operator_control.migrate(self.c,now);operator_control.ensure_primary_operator(self.c,now);execution_driver.ensure_driver(self.c,'SAT-M',now,initial_state='ACTIVE')
        d=execution_driver.snapshot(self.c,'SAT-M');self.original=global_scheduler.create_assignment(self.c,'SAT-M','P1','LD1','MD025',{'remaining':'bounded-canary'},now,lease_generation=d['generation'])
    def cmd(self,cid,action,payload=None,target='mission:SAT-M'):
        x={'command_id':cid,'mission_id':'SAT-M','action':action,'target':target,'payload':payload or {}}
        if action in {'RESUME_SCOPE','RELEASE_CONTROL','AMEND_PLAN','REASSIGN','APPROVE_PROPOSAL'}:x['expected_revision']=operator_control.control_state(self.c,'SAT-M',now)['control_epoch']
        return operator_control.apply_command(self.c,x,now)
    def test_message_status_context_take_stop_reassign_release_resume_without_models(self):
        msg=self.cmd('sat-01','MESSAGE',{'content':'operator evidence'},'drone:MD025');self.assertEqual(msg['admission_state'],'ACCEPTED')
        status=self.cmd('sat-02','REQUEST_STATUS');self.assertEqual(status['result']['mission_id'],'SAT-M')
        ctx=self.cmd('sat-03','AMEND_CONTEXT',{'content':{'rule':'operator revision'}});self.assertEqual(ctx['result']['context_revision'],1)
        take=self.cmd('sat-04','TAKE_CONTROL');self.assertEqual(take['result']['control']['control_owner'],operator_control.PRIMARY_OPERATOR)
        stop=self.cmd('sat-05','STOP_SCOPE');self.assertEqual(stop['result']['control']['stop_latch'],1)
        move=self.cmd('sat-06','REASSIGN',{'assignment_id':self.original,'material_drone_id':'MD026'});new_id=move['result']['assignment_id'];self.assertEqual(move['result']['state'],'READY')
        release=self.cmd('sat-07','RELEASE_CONTROL');self.assertEqual(release['result']['control']['control_owner'],operator_control.AUTONOMOUS_OWNER);self.assertEqual(release['result']['control']['stop_latch'],1)
        resume=self.cmd('sat-08','RESUME_SCOPE',{'latch':'ALL'});self.assertTrue(resume['result']['driver_resume_required'])
        driver=execution_driver.activate(self.c,'SAT-M',now,next_action='SELECT_NEXT_PHASE',owner_id='sat-scheduler');operator_control.rebind_ready_assignments(self.c,'SAT-M',now,authority_owner=operator_control.AUTONOMOUS_OWNER,generation=driver['generation']);self.c.commit()
        claim=global_scheduler.claim_assignment(self.c,new_id,now,expected_material_drone_id='MD026');self.assertEqual(claim['state'],'CLAIMED')
        self.assertEqual(self.c.execute("SELECT COUNT(*) FROM operator_commands WHERE mission_id='SAT-M'").fetchone()[0],8)
        self.assertEqual(self.c.execute("SELECT COUNT(*) FROM operator_command_receipts WHERE command_id LIKE 'sat-%'").fetchone()[0],8)
        self.assertEqual(operator_control.control_state(self.c,'SAT-M')['control_owner'],operator_control.AUTONOMOUS_OWNER)
        self.assertEqual(operator_control.control_state(self.c,'SAT-M')['stop_latch'],0)
        self.assertEqual(operator_control.control_state(self.c,'SAT-M')['context_revision'],1)
        self.assertEqual(self.c.execute('SELECT state FROM mission_execution_assignments WHERE assignment_id=?',(self.original,)).fetchone()[0],'CANCELLED')
    def tearDown(self):self.c.close()
if __name__=='__main__':unittest.main()
