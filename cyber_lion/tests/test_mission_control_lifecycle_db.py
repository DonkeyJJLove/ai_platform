from __future__ import annotations

import importlib
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import threading
import unittest
import urllib.parse
import urllib.request
from http.server import ThreadingHTTPServer


class MissionLifecycleDbTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tools = Path(__file__).resolve().parents[2] / "tools"
        if str(cls.tools) not in sys.path:
            sys.path.insert(0, str(cls.tools))
        compat = importlib.import_module("lion_mission_control_compat")
        sys.modules["mission_control_compat"] = compat
        cls.mc = importlib.import_module("lion_mission_control_v3")
        cls.life = importlib.import_module("lion_mission_lifecycle_db")

    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.addCleanup(self.td.cleanup)
        root = Path(self.td.name)
        self.old_db, self.old_legacy = self.mc.DB, self.mc.LEGACY_DB
        self.addCleanup(lambda: setattr(self.mc, "DB", self.old_db))
        self.addCleanup(lambda: setattr(self.mc, "LEGACY_DB", self.old_legacy))
        self.mc.DB = root / "mission-control.db"
        self.mc.LEGACY_DB = root / "legacy.db"
        c = sqlite3.connect(self.mc.LEGACY_DB)
        c.execute("CREATE TABLE runs(run_id TEXT PRIMARY KEY,payload TEXT NOT NULL)")
        payload = {
            "process_class": "VKT_R3_384_DRONE_TEST",
            "adapter_type": "VKT_R3",
            "status": "PASS",
            "source": {"head": "1" * 40, "tree": "2" * 40},
            "workload": {"pods": 384},
            "metrics": {"ready": 384},
            "evidence": {"class": "HISTORICAL_IMPORTED_EVIDENCE"},
        }
        c.execute("INSERT INTO runs VALUES(?,?)", ("legacy-vkt", json.dumps(payload)))
        c.commit(); c.close()
        self.mc.migrate()

    def test_migration_is_versioned_and_legacy_gaps_are_explicit(self):
        c = self.mc.connect()
        migration = c.execute("SELECT schema_id,version FROM schema_migrations").fetchone()
        self.assertEqual((migration["schema_id"], migration["version"]), (self.life.SCHEMA_ID, self.life.SCHEMA_VERSION))
        ctx = self.life.schema_context(c, "legacy::legacy-vkt")
        c.close()
        self.assertEqual(ctx["record_class"], "HISTORICAL_PRE_SCHEMA")
        self.assertIn("PRE_MISSION_PROCESS_SCHEMA:VKT_R3", ctx["source_stage"])
        fields = {x["field_name"] for x in ctx["missing_fields"]}
        self.assertIn("objective", fields)
        self.assertIn("current_phase", fields)
        self.assertIn("progress", fields)

    def test_delete_records_preserves_legacy_history(self):
        mid='legacy::legacy-vkt'
        c=self.mc.connect();self.addCleanup(c.close)
        preview=self.life.mission_delete_preview(c,mid,self.mc.MISSION)
        self.assertFalse(preview['allowed'])
        self.assertEqual(preview['reason'],'LEGACY_HISTORY_PRESERVATION_POLICY')
        self.assertEqual(preview['lifecycle']['lifecycle_class'],'LEGACY_HISTORY')
        with self.assertRaisesRegex(ValueError,'LEGACY_HISTORY_PRESERVATION_POLICY'):
            self.life.delete_mission_records(c,mid,preview['spec_digest'],self.mc.MISSION,self.mc.now)
        self.assertIsNotNone(c.execute('SELECT 1 FROM missions WHERE mission_id=?',(mid,)).fetchone())
        self.assertIsNotNone(c.execute('SELECT 1 FROM mission_lineage WHERE mission_id=?',(mid,)).fetchone())

    def test_delete_protects_shared_owner_and_current_active_records(self):
        c=self.mc.connect();self.addCleanup(c.close)
        self.assertIn('SHARED_RUNTIME_OWNER',self.life.mission_delete_preview(c,self.mc.MISSION,self.mc.MISSION)['reason'])
        mid='CURRENT-ACTIVE-DELETE-TEST';t=self.mc.now()
        c.execute('INSERT INTO missions(mission_id,title,adapter,spec_digest,source_head,source_tree,namespace,state,runtime_state,logical_count,material_target,materialized,ready,created_at,authorized_at,updated_at,last_error,spec_json) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(mid,'active','LPCL_GENERIC_128L64M','9'*64,'1'*40,'2'*40,None,'RUNNING','DRIVER_ACTIVE',1,0,0,0,t,t,t,None,'{}'))
        c.execute('INSERT INTO mission_process_specs(mission_id,title,objective,description,lpcl_digest,lpcl_text,protocols_json,authority_state,current_phase,progress,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(mid,'active','o','d','9'*64,'x','[]','EXPLICIT_USER_ACTIVATION','P1',0.0,t,t));c.commit()
        preview=self.life.mission_delete_preview(c,mid,self.mc.MISSION)
        self.assertFalse(preview['allowed']);self.assertIn('MISSION_STILL_ACTIVE',preview['reason'])

    def test_process_snapshot_decorates_historical_record_without_synthetic_process(self):
        out = self.mc.process_snapshot("legacy::legacy-vkt")
        self.assertIsNone(out["process"])
        self.assertEqual(out["schema_context"]["record_class"], "HISTORICAL_PRE_SCHEMA")
        self.assertEqual(out["lifecycle"]["lifecycle_class"], "LEGACY_HISTORY")
        self.assertEqual(out["lifecycle"]["record_class"], "RECORDED_OBSERVATION")
        self.assertFalse(out["lifecycle"]["execution_controls_allowed"])
        self.assertEqual(out["phases"], [])
        self.assertEqual(out["control_authority"], "NONE")
        self.assertEqual(out["capabilities"]["RESTART"]["state"], "DENIED_LEGACY_HISTORY_READ_ONLY")

    def test_encoded_legacy_id_round_trips_over_http(self):
        srv = ThreadingHTTPServer(("127.0.0.1", 0), self.mc.H)
        t = threading.Thread(target=srv.serve_forever, daemon=True); t.start()
        self.addCleanup(srv.server_close); self.addCleanup(srv.shutdown)
        encoded = urllib.parse.quote("legacy::legacy-vkt", safe="")
        with urllib.request.urlopen(f"http://127.0.0.1:{srv.server_port}/api/v3/missions/{encoded}/process", timeout=3) as r:
            self.assertEqual(r.status, 200)
            data = json.load(r)
        self.assertEqual(data["mission_id"], "legacy::legacy-vkt")
        self.assertEqual(data["schema_context"]["record_class"], "HISTORICAL_PRE_SCHEMA")

    def test_audit_creates_non_restorable_material_rollback_evidence(self):
        out = self.mc.mission_action("legacy::legacy-vkt", {"action": "AUDIT"})
        self.assertEqual(out["status"], "PASS")
        self.assertEqual(out["effect_class"], "NONE")
        self.assertFalse(out["result"]["rollback_point"]["restorable"])
        snap = self.mc.process_snapshot("legacy::legacy-vkt")
        self.assertEqual(len(snap["audits"]), 1)
        self.assertEqual(len(snap["rollback_points"]), 1)

    def test_legacy_history_rejects_execution_design_and_destructive_actions(self):
        for action,payload in [
            ('RESTART',{'reason':'replay'}),('REDESIGN',{'reason':'migrate'}),
            ('ADD_COMPONENT',{'component':{'component_id':'X'}}),('RESUME',{}),('STOP',{}),
        ]:
            with self.subTest(action=action):
                with self.assertRaisesRegex(ValueError,'LEGACY_HISTORY_READ_ONLY'):
                    self.mc.mission_action('legacy::legacy-vkt',{'action':action,**payload})
        snap=self.mc.process_snapshot('legacy::legacy-vkt')
        self.assertEqual(snap['design_revisions'],[])
        self.assertEqual(snap['capabilities']['REDESIGN']['state'],'DENIED_LEGACY_HISTORY_READ_ONLY')

    def test_start_component_contract_exists_but_fails_closed_without_exact_adapter(self):
        out = self.mc.mission_action(self.mc.MISSION, {"action": "START_COMPONENT", "component_id": "LD01"})
        self.assertEqual(out["effect_class"], "NONE")
        self.assertEqual(out["result"]["state"], "BLOCKED_EXACT_COMPONENT_ADAPTER_REQUIRED")
        cap = self.mc.process_snapshot(self.mc.MISSION)["capabilities"]["START_COMPONENT"]
        self.assertEqual(cap["state"], "ADAPTER_REQUIRED")

    def test_redesign_of_canonical_lpcl_compiles_registered_successor_without_authority(self):
        lpcl = """PROJECT=LION_EVOLUSION
MODE=AUTONOMOUS_EXECUTE
CONTROL_LANGUAGE=LPCL/1.1
MISSION_ID=TEST-CANONICAL
MISSION_TITLE=Canonical test
MISSION_OBJECTIVE=Test design revision compilation
MISSION_DESCRIPTION=Test only
PROTOCOLS=LPCL,AUTHORITY,CURRENTNESS,RECEIPT,CONTROL
LOGICAL_DRONE_COUNT=12
MATERIAL_DRONE_COUNT=64
CONTINUE_EXISTING_EPOCH3_MISSION=TRUE
CREATE_PARALLEL_COMPETING_EPOCH3_MISSION=FALSE
REUSE_EXISTING_HEALTHY_MATERIAL_FLEET=ALLOWED_AFTER_EXACT_IDENTITY_AND_MISSION_REBIND
PARENT_MISSION_ID=PARENT-X
LD01=A
LD02=B
LD03=C
LD04=D
LD05=E
LD06=F
LD07=G
LD08=H
LD09=I
LD10=J
LD11=K
LD12=L
PHASE_01=P1|One
"""
        import hashlib
        dg=hashlib.sha256(lpcl.encode()).hexdigest()
        self.mc.register_lpcl_mission({'mission_id':'TEST-CANONICAL','title':'Canonical test','objective':'Test design revision compilation','description':'Test only','lpcl_digest':dg,'lpcl_text':lpcl,'source_head':'1'*40,'source_tree':'2'*40,'logical_count':12,'material_target':64,'phases':[{'id':'P1','title':'One'}],'protocols':['LPCL','AUTHORITY','CURRENTNESS','RECEIPT','CONTROL']})
        out=self.mc.mission_action('TEST-CANONICAL',{'action':'REDESIGN','reason':'new scheduler policy'})
        succ=out['result']['successor'];self.assertEqual(succ['state'],'REGISTERED_AWAITING_EXPLICIT_ACTIVATION')
        snap=self.mc.process_snapshot('TEST-CANONICAL');self.assertEqual(len(snap['revision_compilations']),1)
        child=self.mc.process_snapshot(succ['successor_mission_id']);self.assertEqual(child['state'],'REGISTERED');self.assertEqual(child['process']['authority_state'],'NONE')
        with self.assertRaises(ValueError):self.mc.mission_action('TEST-CANONICAL',{'action':'ACTIVATE_REVISION','revision_id':out['result']['revision_id'],'lpcl_digest':'0'*64})

    def test_driver_phase_result_commits_phase_and_advances_cursor(self):
        lpcl = """PROJECT=LION_EVOLUSION
MODE=AUTONOMOUS_EXECUTE
CONTROL_LANGUAGE=LPCL/1.1
MISSION_ID=TEST-DRIVER-COMMIT
MISSION_TITLE=Driver commit test
MISSION_OBJECTIVE=Verify durable phase advancement
MISSION_DESCRIPTION=Test only
PROTOCOLS=LPCL,VALIDATION,RECEIPT
LOGICAL_DRONE_COUNT=12
MATERIAL_DRONE_COUNT=64
PHASE_01=P1|One
PHASE_02=P2|Two
"""
        import hashlib
        dg=hashlib.sha256(lpcl.encode()).hexdigest()
        self.mc.register_lpcl_mission({'mission_id':'TEST-DRIVER-COMMIT','title':'Driver commit test','objective':'Verify durable phase advancement','description':'Test only','lpcl_digest':dg,'lpcl_text':lpcl,'source_head':'1'*40,'source_tree':'2'*40,'logical_count':12,'material_target':64,'phases':[{'id':'P1','title':'One'},{'id':'P2','title':'Two'}],'protocols':['LPCL','VALIDATION','RECEIPT']})
        c=self.mc.connect()
        self.mc._driver_phase_result(c,'TEST-DRIVER-COMMIT','P1','PASS','done',{'event':'TEST_PASS'},'VALIDATION')
        c.close()
        c=self.mc.connect()
        p1=c.execute("SELECT status,progress FROM mission_phases WHERE mission_id='TEST-DRIVER-COMMIT' AND phase_id='P1'").fetchone()
        p2=c.execute("SELECT status FROM mission_phases WHERE mission_id='TEST-DRIVER-COMMIT' AND phase_id='P2'").fetchone()
        process=c.execute("SELECT current_phase,progress FROM mission_process_specs WHERE mission_id='TEST-DRIVER-COMMIT'").fetchone()
        c.close()
        self.assertEqual((p1['status'],p1['progress']),('PASS',100.0))
        self.assertEqual(p2['status'],'RUNNING')
        self.assertEqual(process['current_phase'],'P2')
        self.assertEqual(process['progress'],50.0)

    def test_refresh_legacy_reindexes_historical_source_without_promoting_authority(self):
        out = self.mc.mission_action("legacy::legacy-vkt", {"action": "REFRESH"})
        self.assertEqual(out["effect_class"], "NONE")
        self.assertEqual(out["result"]["effect"], "READ_ONLY_REINDEX")
        snap = self.mc.process_snapshot("legacy::legacy-vkt")
        self.assertEqual(snap["control_authority"], "NONE")


if __name__ == "__main__":
    unittest.main()
