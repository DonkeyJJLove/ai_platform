import json
import sqlite3
import unittest
from datetime import datetime, timezone

from cyber_lion.mission_control import hmk9d_process


def now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00","Z")


class Hmk9dProcessTests(unittest.TestCase):
    def setUp(self):
        self.c=sqlite3.connect(":memory:")
        self.c.row_factory=sqlite3.Row
        self.c.executescript("""
        CREATE TABLE mission_execution_assignments(
          assignment_id TEXT PRIMARY KEY,mission_id TEXT,phase_id TEXT,logical_drone_id TEXT,
          material_drone_id TEXT,input_json TEXT,state TEXT,created_at TEXT
        );
        CREATE TABLE mission_execution_receipts(
          receipt_id TEXT PRIMARY KEY,assignment_id TEXT,mission_id TEXT,phase_id TEXT,
          result_digest TEXT,effect_receipt_digest TEXT,authority_effect TEXT,status TEXT,observed_at TEXT
        );
        CREATE TABLE mission_model_calls(
          model_call_id TEXT PRIMARY KEY,assignment_id TEXT,provider TEXT,model_declared TEXT,
          transport TEXT,state TEXT,material_worker_id TEXT,logical_drone_id TEXT,created_at TEXT
        );
        CREATE TABLE operator_messages(
          message_id TEXT PRIMARY KEY,correlation_id TEXT,causation_id TEXT,kind TEXT,
          content TEXT,applied_assignment_id TEXT,created_at TEXT
        );
        """)
        hmk9d_process.migrate(self.c,now)

    def tearDown(self):
        self.c.close()

    def test_profile_has_exact_axes_and_nine_bridges(self):
        self.assertEqual(hmk9d_process.AXES,("T","S","R","E","I","F","A","P","D"))
        self.assertEqual(hmk9d_process.CONVERSATION_PATH,(
            "PLAN_PAUSE","CORE_PERIPH","SILENCE_EXHALE","VILLAGE_CITY",
            "EDGE_PATIENCE","LOCUS_MEDIUM_MANDATE","HUMAN_AI",
            "THRESHOLD_TRANSITION","SEMANTICS_ENERGY",
        ))
        for bridge in hmk9d_process.BRIDGES.values():
            self.assertEqual(set(bridge["delta"]),set(hmk9d_process.AXES))

    def test_dispatch_prefix_is_retry_safe_and_authority_none(self):
        pid=hmk9d_process.ensure_conversation_process(self.c,"M1","thread-1","m1",now)
        first=hmk9d_process.dispatch_prefix(
            self.c,pid,message_id="m1",correlation_id="thread-1",scope_target="mission:M1",
            logical_drone_id="LD1",material_worker_id="MD1",dispatch_authority="AUTONOMOUS",
            history_count=0,now_fn=now,
        )
        self.assertEqual(len(first),6)
        again=hmk9d_process.dispatch_prefix(
            self.c,pid,message_id="m1",correlation_id="thread-1",scope_target="mission:M1",
            logical_drone_id="LD1",material_worker_id="MD1",dispatch_authority="AUTONOMOUS",
            history_count=0,now_fn=now,
        )
        self.assertEqual(again,[])
        run=self.c.execute("SELECT * FROM hmk9d_process_runs WHERE process_id=?",(pid,)).fetchone()
        self.assertEqual(run["current_ordinal"],6)
        self.assertEqual(run["authority_effect"],"NONE")
        steps=self.c.execute("SELECT * FROM hmk9d_process_steps WHERE process_id=? ORDER BY ordinal",(pid,)).fetchall()
        self.assertEqual(len(steps),6)
        self.assertTrue(all(x["authority_effect"]=="NONE" for x in steps))
        self.assertTrue(all(x["energy_basis"]=="DECLARED_BRIDGE_VECTOR_L1_MEAN_NOT_EMPIRICAL_RISK" for x in steps))

    def test_observed_model_receipt_and_response_complete_process(self):
        pid=hmk9d_process.ensure_conversation_process(self.c,"M1","thread-1","m1",now)
        hmk9d_process.dispatch_prefix(
            self.c,pid,message_id="m1",correlation_id="thread-1",scope_target="mission:M1",
            logical_drone_id="LD1",material_worker_id="MD1",dispatch_authority="AUTONOMOUS",
            history_count=0,now_fn=now,
        )
        payload={"hmk9d_process_id":pid,"operator_message_ids":["m1"],"purpose":"OPERATOR_BUS_CONVERSATION_R1","conversation_protocol_version":3}
        self.c.execute("INSERT INTO mission_execution_assignments VALUES(?,?,?,?,?,?,?,?)",
                       ("a1","M1","OPERATOR_BUS_X","LD1","MD1",json.dumps(payload),"PASS",now()))
        self.c.execute("INSERT INTO mission_model_calls VALUES(?,?,?,?,?,?,?,?,?)",
                       ("mc1","a1","LION_LOCAL_MODEL","gpt-oss-20b-MXFP4","LOCAL","RESPONSE_RECONCILED","MD1","LD1",now()))
        self.c.execute("INSERT INTO mission_execution_receipts VALUES(?,?,?,?,?,?,?,?,?)",
                       ("r1","a1","M1","OPERATOR_BUS_X","d"*64,None,"NONE","PASS",now()))
        self.c.execute("INSERT INTO operator_messages VALUES(?,?,?,?,?,?,?)",
                       ("reply1","thread-1","m1","RESPONSE","answer","a1",now()))
        self.c.commit()
        out=hmk9d_process.reconcile_observed(self.c,now)
        self.assertEqual(out["steps_advanced"],3)
        run=self.c.execute("SELECT * FROM hmk9d_process_runs WHERE process_id=?",(pid,)).fetchone()
        self.assertEqual(run["status"],"COMPLETE")
        self.assertEqual(run["current_ordinal"],9)
        projection=hmk9d_process.thread_projection(self.c,"thread-1")
        self.assertEqual(projection["authority_effect"],"NONE")
        self.assertEqual(len(projection["processes"]),1)
        self.assertEqual(len(projection["processes"][0]["steps"]),9)
        human=projection["processes"][0]["steps"][6]
        self.assertEqual(human["bridge_id"],"HUMAN_AI")
        self.assertEqual(human["evidence"]["model_call_id"],"mc1")
        threshold=projection["processes"][0]["steps"][7]
        self.assertIn("NO_AUTHORITY_GRANTED",threshold["evidence"]["meaning"])

    def test_bridge_order_fails_closed(self):
        pid=hmk9d_process.ensure_conversation_process(self.c,"M1","thread-1","m1",now)
        with self.assertRaisesRegex(ValueError,"bridge order"):
            hmk9d_process.advance(self.c,pid,"HUMAN_AI",{},now)


if __name__=="__main__":
    unittest.main()
