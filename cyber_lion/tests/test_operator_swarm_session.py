import json
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
        assignment_payload=json.loads(assignment["input_json"])
        self.assertEqual(assignment_payload["trusted_participant_context"]["material_worker"],"worker:MD025")
        self.assertEqual(assignment_payload["trusted_participant_context"]["cognitive_executor"],"model:local")
        self.assertEqual(assignment_payload["evidence_classes"],["TRUSTED_TOPOLOGY_CONTEXT","OPERATOR_MESSAGE"])
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

    def test_verifier_record_requires_independent_evidence_for_supported_claim(self):
        source={"material_worker":"worker:MD025","logical_drone":"drone:LD025","cognitive_executor":"model:local"}
        verifier={"material_worker":"worker:MD026","logical_drone":"drone:LD026","cognitive_executor":"model:local"}
        valid={
            "schema":"lion.swarm-verifier-record/v1",
            "source_participant":"worker:MD025",
            "claims":[{
                "claim":"The source material participant is worker:MD025.",
                "evidence":[{"class":"TRUSTED_TOPOLOGY_CONTEXT","ref":"TRUSTED_SOURCE_CONTEXT_JSON.material_worker"}],
                "verdict":"SUPPORTED_BY_TRUSTED_CONTEXT"
            }],
            "unknowns":[],
            "summary":"Participant identity is supported by trusted source context."
        }
        parsed=operator_swarm_session._parse_verifier_record(json.dumps(valid),source,verifier)
        self.assertEqual(parsed["claims"][0]["verdict"],"SUPPORTED_BY_TRUSTED_CONTEXT")
        invalid=json.loads(json.dumps(valid))
        invalid["claims"][0]["evidence"]=[{"class":"MODEL_CLAIM","ref":"UNTRUSTED_PRIMARY_RESPONSE"}]
        with self.assertRaisesRegex(ValueError,"independent trusted evidence"):
            operator_swarm_session._parse_verifier_record(json.dumps(invalid),source,verifier)

    def test_verifier_record_rejects_nonexistent_trusted_context_ref(self):
        source={"material_worker":"worker:MD025","logical_drone":"drone:LD025"}
        verifier={"material_worker":"worker:MD026","logical_drone":"drone:LD026"}
        value={
            "schema":"lion.swarm-verifier-record/v1",
            "source_participant":"worker:MD025",
            "claims":[{
                "claim":"An invented signature exists.",
                "evidence":[{"class":"TRUSTED_TOPOLOGY_CONTEXT","ref":"TRUSTED_SOURCE_CONTEXT_JSON.signature"}],
                "verdict":"SUPPORTED_BY_TRUSTED_CONTEXT"
            }],
            "unknowns":[],
            "summary":"Invalid evidence reference."
        }
        with self.assertRaisesRegex(ValueError,"trusted-context ref"):
            operator_swarm_session._parse_verifier_record(json.dumps(value),source,verifier)


if __name__=="__main__":
    unittest.main()
