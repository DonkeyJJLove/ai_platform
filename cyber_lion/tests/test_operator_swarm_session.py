import sqlite3
import unittest
from datetime import datetime, timezone

from cyber_lion.mission_control import execution_driver, global_scheduler, operator_control, operator_swarm_session


def now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00","Z")


class OperatorSwarmSessionTests(unittest.TestCase):
    def setUp(self):
        self.c=sqlite3.connect(":memory:")
        self.c.row_factory=sqlite3.Row
        self.c.execute("""CREATE TABLE missions(
            mission_id TEXT PRIMARY KEY,
            state TEXT NOT NULL,
            updated_at TEXT,
            authorized_at TEXT
        )""")
        stamp=now()
        self.c.execute("INSERT INTO missions VALUES(?,?,?,?)",("M1","RUNNING",stamp,stamp))
        self.c.execute("CREATE TABLE mission_process_specs(mission_id TEXT PRIMARY KEY,authority_state TEXT)")
        self.c.execute("INSERT INTO mission_process_specs VALUES(?,?)",("M1","EXPLICIT_USER_ACTIVATION"))
        self.c.execute("CREATE TABLE material_workers(mission_id TEXT,pod_name TEXT,logical_id TEXT)")
        self.c.executemany("INSERT INTO material_workers VALUES(?,?,?)",[
            ("M1","MD025","LD025"),("M1","MD026","LD026")
        ])
        self.c.execute("""CREATE TABLE schema_migrations(
            version INTEGER, schema_id TEXT, applied_at TEXT, source_head TEXT, source_tree TEXT,
            migration_digest TEXT, note TEXT, UNIQUE(version,schema_id)
        )""")
        execution_driver.migrate(self.c,now,source_head="a"*40,source_tree="b"*40)
        global_scheduler.migrate(self.c,now)
        operator_control.migrate(self.c,now)
        operator_control.ensure_primary_operator(self.c,now)
        operator_control.ensure_operator_proxy(self.c,now,mission_scope="*",actions={"MESSAGE","REQUEST_STATUS"})
        operator_swarm_session.migrate(self.c,now)
        execution_driver.ensure_driver(self.c,"M1",now,initial_state="ACTIVE")
        self.c.commit()

    def tearDown(self):
        self.c.close()

    def test_session_requires_explicit_activation(self):
        self.c.execute("UPDATE mission_process_specs SET authority_state='REGISTERED' WHERE mission_id='M1'")
        self.c.commit()
        with self.assertRaisesRegex(ValueError,"not explicitly activated"):
            operator_swarm_session.open_session(
                self.c,operator_control.PRIMARY_OPERATOR,"M1",now,
                duration_seconds=600,workers=("MD025","MD026")
            )

    def test_message_dispatch_is_durable_and_does_not_raise_authority(self):
        before=operator_control.control_state(self.c,"M1",now)
        opened=operator_swarm_session.open_session(
            self.c,operator_control.PRIMARY_OPERATOR,"M1",now,
            duration_seconds=600,workers=("MD025","MD026")
        )
        sid=opened["session"]["session_id"]
        sent=operator_swarm_session.send_message(
            self.c,operator_control.PRIMARY_OPERATOR,sid,"swarm-test-1",
            "drone:MD025","verify current binding",now,
            kind="REQUEST",correlation_id="corr-1",thread_id="thread-1"
        )
        self.assertEqual(sent["authority_effect"],"NONE")
        self.assertEqual(len(sent["assignments"]),1)
        assignment=self.c.execute(
            "SELECT * FROM mission_execution_assignments WHERE assignment_id=?",
            (sent["assignments"][0],)
        ).fetchone()
        self.assertEqual(assignment["material_drone_id"],"MD025")
        self.assertEqual(assignment["state"],"READY")
        message=self.c.execute(
            "SELECT * FROM operator_general_messages WHERE command_id='swarm-test-1'"
        ).fetchone()
        self.assertEqual(message["correlation_id"],"corr-1")
        self.assertEqual(message["thread_id"],"thread-1")
        after=operator_control.control_state(self.c,"M1")
        self.assertEqual(after["control_epoch"],before["control_epoch"])
        self.assertEqual(after["control_owner"],before["control_owner"])
        self.assertEqual(after["pause_latch"],before["pause_latch"])
        self.assertEqual(after["stop_latch"],before["stop_latch"])


if __name__=="__main__":
    unittest.main()
