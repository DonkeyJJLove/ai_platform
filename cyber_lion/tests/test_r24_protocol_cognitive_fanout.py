from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from cyber_lion.mission_control import execution_driver, global_scheduler, operator_control
from tools.lion_operator_gateway import dispatch_protocol_message


def now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class FakeRuntime:
    def __init__(self, db: Path):
        self.db=db
    def connect(self):
        c=sqlite3.connect(self.db,timeout=2)
        c.row_factory=sqlite3.Row
        c.execute("PRAGMA foreign_keys=ON")
        return c


class R24ProtocolCognitiveFanoutTests(unittest.TestCase):
    def setUp(self):
        self.td=tempfile.TemporaryDirectory()
        self.addCleanup(self.td.cleanup)
        self.db=Path(self.td.name)/"mc.db"
        c=sqlite3.connect(self.db);c.row_factory=sqlite3.Row
        c.execute("CREATE TABLE missions(mission_id TEXT PRIMARY KEY,state TEXT NOT NULL DEFAULT 'RUNNING',updated_at TEXT)")
        c.execute("INSERT INTO missions VALUES('M1','RUNNING',?)",(now(),))
        c.execute("CREATE TABLE material_workers(mission_id TEXT,pod_name TEXT,logical_id TEXT)")
        c.executemany("INSERT INTO material_workers VALUES(?,?,?)",[
            ("M1","MD001","LD001"),("M1","MD002","LD002"),
        ])
        c.execute("CREATE TABLE logical_drones(mission_id TEXT,logical_id TEXT,role TEXT)")
        c.executemany("INSERT INTO logical_drones VALUES(?,?,?)",[
            ("M1","LD001","ANALYST"),("M1","LD002","VERIFIER"),
        ])
        c.execute("""CREATE TABLE schema_migrations(
          version INTEGER,schema_id TEXT,applied_at TEXT,source_head TEXT,source_tree TEXT,
          migration_digest TEXT,note TEXT,UNIQUE(version,schema_id))""")
        execution_driver.migrate(c,now,source_head="a"*40,source_tree="b"*40)
        global_scheduler.migrate(c,now)
        operator_control.migrate(c,now)
        operator_control.ensure_primary_operator(c,now)
        execution_driver.ensure_driver(c,"M1",now,initial_state="ACTIVE")
        generation=execution_driver.snapshot(c,"M1")["generation"]
        for logical,material in (("LD001","MD001"),("LD002","MD002")):
            value={"material_worker_id":material,"binding_class":"DOCKER_LOCAL_MODEL"}
            c.execute("""INSERT INTO mission_execution_assignments(
              assignment_id,mission_id,phase_id,logical_drone_id,material_drone_id,
              input_digest,input_json,state,lease_generation,control_epoch,context_revision,
              plan_revision,dispatch_authority,created_at,claimed_at,finished_at)
              VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
              ("topology-"+logical,"M1","__TOPOLOGY__",logical,material,
               operator_control.digest(value),json.dumps(value,sort_keys=True),"BOUND",
               generation,0,0,0,"AUTONOMOUS",now(),now(),now()))
        c.commit();c.close()
        self.runtime=FakeRuntime(self.db)

    def _message(self, cid="broadcast"):
        c=self.runtime.connect()
        try:
            value={
                "command_id":cid,"mission_id":"M1","action":"MESSAGE",
                "target":"swarm:M1","payload":{"content":"Cele misji, zgłaszać wszyscy."},
                "correlation_id":"a"*32,
            }
            out=operator_control.apply_command(c,value,now)
            return out["result"]
        finally:c.close()

    def test_swarm_freezes_four_exact_recipients_and_creates_one_assignment_each(self):
        msg=self._message()
        self.assertEqual(msg["recipient_count"],4)
        self.assertEqual(set(msg["recipients"]),{
            "drone:LD001","drone:LD002","worker:MD001","worker:MD002",
        })
        self.assertTrue(msg["fanout_id"].startswith("fanout-"))
        self.assertEqual(len(msg["recipient_set_digest"]),64)
        out=dispatch_protocol_message(self.runtime,msg["message_id"])
        self.assertEqual(out["state"],"COMPLETE_DISPATCH")
        self.assertEqual(len(out["created"]),4)
        self.assertEqual({x["participant_id"] for x in out["created"]},set(msg["recipients"]))
        c=self.runtime.connect()
        try:
            rows=c.execute("SELECT input_json FROM mission_execution_assignments WHERE input_json LIKE '%PROTOCOL_FANOUT_R1%'").fetchall()
            payloads=[json.loads(r["input_json"]) for r in rows]
            self.assertEqual(len(payloads),4)
            self.assertEqual({x["responding_participant_id"] for x in payloads},set(msg["recipients"]))
            self.assertEqual({x["fanout_id"] for x in payloads},{msg["fanout_id"]})
        finally:c.close()

    def test_replay_does_not_duplicate_protocol_assignments(self):
        msg=self._message()
        first=dispatch_protocol_message(self.runtime,msg["message_id"])
        second=dispatch_protocol_message(self.runtime,msg["message_id"])
        self.assertEqual(len(first["created"]),4)
        self.assertEqual(len(second["created"]),0)
        self.assertEqual(len(second["existing"]),4)

    def test_new_participant_does_not_join_existing_frozen_fanout(self):
        msg=self._message()
        c=self.runtime.connect()
        try:
            c.execute("INSERT INTO logical_drones VALUES('M1','LD003','LATE')")
            c.execute("INSERT INTO material_workers VALUES('M1','MD003','LD003')")
            c.commit()
        finally:c.close()
        out=dispatch_protocol_message(self.runtime,msg["message_id"])
        self.assertEqual(out["expected"],4)
        self.assertEqual({x["participant_id"] for x in out["created"]},{
            "drone:LD001","drone:LD002","worker:MD001","worker:MD002",
        })

    def test_pause_fences_new_cognitive_assignments(self):
        msg=self._message()
        c=self.runtime.connect()
        try:
            operator_control.apply_command(c,{
                "command_id":"pause","mission_id":"M1","action":"PAUSE_SCOPE",
                "target":"mission:M1","payload":{},
            },now)
        finally:c.close()
        out=dispatch_protocol_message(self.runtime,msg["message_id"])
        self.assertEqual(out["state"],"FENCED")
        self.assertEqual(out["created"],0)
        c=self.runtime.connect()
        try:
            self.assertEqual(c.execute("SELECT COUNT(*) FROM mission_execution_assignments WHERE input_json LIKE '%PROTOCOL_FANOUT_R1%'").fetchone()[0],0)
        finally:c.close()


if __name__=="__main__":
    unittest.main()
