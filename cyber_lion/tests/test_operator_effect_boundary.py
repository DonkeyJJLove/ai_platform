import sqlite3
import tempfile
import unittest
import sys
from pathlib import Path
from unittest.mock import patch

from cyber_lion.mission_control import global_scheduler, operator_control
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'))
from tools import lion_mission_control_compat as _compat
sys.modules.setdefault('mission_control_compat',_compat)
import lion_mission_control_v3 as mc


class OperatorEffectBoundaryTests(unittest.TestCase):
    def test_generic_executor_is_fenced_after_takeover(self):
        c=sqlite3.connect(':memory:');c.row_factory=sqlite3.Row
        c.executescript('''
        CREATE TABLE missions(mission_id TEXT PRIMARY KEY,state TEXT,adapter TEXT,runtime_state TEXT,materialized INTEGER,ready INTEGER,source_head TEXT,source_tree TEXT,updated_at TEXT);
        CREATE TABLE mission_process_specs(mission_id TEXT PRIMARY KEY,lpcl_text TEXT);
        CREATE TABLE schema_migrations(version INTEGER,schema_id TEXT,applied_at TEXT,source_head TEXT,source_tree TEXT,migration_digest TEXT,note TEXT,UNIQUE(version,schema_id));
        ''')
        c.execute("INSERT INTO missions VALUES('M1','RUNNING',?,?,?,?,?,?,?)",(mc.LPCL_GENERIC_ADAPTER,'RUNNING',0,0,'a'*40,'b'*40,mc.now()))
        c.execute("INSERT INTO mission_process_specs VALUES('M1','')")
        global_scheduler.migrate(c,mc.now);operator_control.migrate(c,mc.now);operator_control.ensure_primary_operator(c,mc.now)
        c.execute('''INSERT INTO mission_generic_phase_plans(plan_id,mission_id,phase_id,planning_assignment_id,planning_receipt_id,planning_result_digest,planning_payload_state,state,capability,target,operation,required_inputs_json,expected_output_json,authority_class,currentness_requirements_json,evidence_requirements_json,rollback_class,dependencies_json,action_ir_json,action_ir_digest,executor_id,evidence_json,evidence_digest,effect_receipt_digest,created_at,updated_at)
                     VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                  ('P','M1','PH','A','R','d'*64,'RETAINED','CAPABILITY_RESOLUTION','MISSION_STATE_READ','x','VERIFY','{}','{}','NONE','[]','[]','NONE','[]','{}','e'*64,None,None,None,None,mc.now(),mc.now()))
        c.commit()
        operator_control.apply_command(c,{'command_id':'take','mission_id':'M1','action':'TAKE_CONTROL','target':'mission:M1','payload':{}},mc.now)
        plan=dict(c.execute("SELECT * FROM mission_generic_phase_plans WHERE plan_id='P'").fetchone())
        out=mc._generic_execute_read_plan(c,plan)
        self.assertEqual(out['gate'],'OPERATOR_CONTROL_FENCE')
        self.assertEqual(out['state'],'WAITING_AUTHORITY')
        self.assertEqual(c.execute("SELECT COUNT(*) FROM mission_generic_action_receipts").fetchone()[0],0)
        c.close()

    def test_legacy_material_restart_cannot_bypass_takeover(self):
        with tempfile.TemporaryDirectory() as td:
            db=Path(td)/'mc.db';c=sqlite3.connect(db);c.row_factory=sqlite3.Row
            c.executescript('''
            CREATE TABLE missions(mission_id TEXT PRIMARY KEY,state TEXT);
            CREATE TABLE material_workers(mission_id TEXT,pod_name TEXT);
            ''')
            c.execute('INSERT INTO missions VALUES(?,?)',(mc.MISSION,'RUNNING'));c.execute('INSERT INTO material_workers VALUES(?,?)',(mc.MISSION,'pod-a'))
            operator_control.migrate(c,mc.now);operator_control.ensure_primary_operator(c,mc.now)
            operator_control.apply_command(c,{'command_id':'take','mission_id':mc.MISSION,'action':'TAKE_CONTROL','target':'mission:'+mc.MISSION,'payload':{}},mc.now)
            c.close()
            with patch.object(mc,'DB',db):
                with self.assertRaisesRegex(ValueError,'operator control fence'):
                    mc.command('RESTART_ONE','pod-a')


if __name__=='__main__':unittest.main()
