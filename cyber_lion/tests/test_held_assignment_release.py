from __future__ import annotations

from datetime import datetime, timezone
import json
import sqlite3
import unittest

from cyber_lion.mission_control import global_scheduler as g
from cyber_lion.mission_control import operator_control


def now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class HeldAssignmentReleaseTests(unittest.TestCase):
    def setUp(self):
        self.c = sqlite3.connect(":memory:")
        self.c.row_factory = sqlite3.Row
        self.c.executescript("""
        CREATE TABLE missions(mission_id TEXT PRIMARY KEY,state TEXT,updated_at TEXT);
        CREATE TABLE mission_execution_drivers(
          mission_id TEXT PRIMARY KEY,state TEXT,heartbeat_at TEXT,current_phase TEXT,
          generation INTEGER NOT NULL
        );
        """)
        g.migrate(self.c, now)
        operator_control.migrate(self.c, now)
        self.c.execute("INSERT INTO missions VALUES(?,?,?)", ("M1","RUNNING",now()))
        self.c.execute("INSERT INTO mission_execution_drivers VALUES(?,?,?,?,?)",
                       ("M1","ACTIVE",now(),"BUILD",1))
        self.c.commit()
        self.aid = g.create_held_assignment(
            self.c, "M1", "BUILD__COOP_WRITE", "LD001", "MD001",
            {"kind":"COOPERATIVE_ARTIFACT_WRITE","capability":"COOPERATIVE_ARTIFACT_PRODUCTION"},
            now, lease_generation=1,
        )

    def tearDown(self):
        self.c.close()

    def row(self):
        return self.c.execute(
            "SELECT * FROM mission_execution_assignments WHERE assignment_id=?",
            (self.aid,),
        ).fetchone()

    def evidence(self, **changes):
        row=self.row(); payload=json.loads(row["input_json"])
        value={
            "schema":g.ASSIGNMENT_RELEASE_EVIDENCE_SCHEMA,
            "assignment_id":row["assignment_id"],
            "mission_id":row["mission_id"],
            "material_drone_id":row["material_drone_id"],
            "lease_generation":int(row["lease_generation"]),
            "control_epoch":int(row["control_epoch"]),
            "context_revision":int(row["context_revision"]),
            "plan_revision":int(row["plan_revision"]),
            "capability":payload["capability"],
            "materialization_kind":"RUNTIME_CONTEXT",
            "provider_id":"COOPERATIVE_RUNTIME_WRITER_R5",
            "evidence_digest":"a"*64,
            "authority_effect":"NONE",
        }
        value.update(changes)
        return value

    def test_held_assignment_is_not_worker_visible_or_claimable(self):
        self.assertEqual(self.row()["state"], "HELD")
        self.assertEqual(g.pending_local_assignments(self.c, mission_id="M1"), [])
        with self.assertRaisesRegex(ValueError, "not ready"):
            g.claim_assignment(self.c, self.aid, now, expected_material_drone_id="MD001")

    def test_exact_release_becomes_ready_and_is_durably_evidenced(self):
        out=g.release_held_assignment(self.c,self.aid,self.evidence(),now)
        self.assertEqual(out["state"],"READY")
        pending=g.pending_local_assignments(self.c,mission_id="M1")
        self.assertEqual([x["assignment_id"] for x in pending],[self.aid])
        stored=g.held_assignment_release_evidence(self.c,self.aid)
        self.assertEqual(stored["evidence"]["provider_id"],"COOPERATIVE_RUNTIME_WRITER_R5")
        claimed=g.claim_assignment(self.c,self.aid,now,expected_material_drone_id="MD001")
        self.assertEqual(claimed["state"],"CLAIMED")

    def test_release_is_exactly_once(self):
        evidence=self.evidence()
        g.release_held_assignment(self.c,self.aid,evidence,now)
        with self.assertRaisesRegex(ValueError,"not held|already recorded"):
            g.release_held_assignment(self.c,self.aid,evidence,now)

    def test_control_revision_drift_blocks_release(self):
        self.c.execute("UPDATE mission_operator_control SET context_revision=context_revision+1 WHERE mission_id='M1'")
        self.c.commit()
        with self.assertRaisesRegex(ValueError,"control/context/plan drift"):
            g.release_held_assignment(self.c,self.aid,self.evidence(),now)
        self.assertEqual(self.row()["state"],"HELD")

    def test_driver_generation_drift_blocks_release(self):
        self.c.execute("UPDATE mission_execution_drivers SET generation=2 WHERE mission_id='M1'")
        self.c.commit()
        with self.assertRaisesRegex(ValueError,"stale assignment generation"):
            g.release_held_assignment(self.c,self.aid,self.evidence(),now)
        self.assertEqual(self.row()["state"],"HELD")

    def test_capability_revocation_blocks_release(self):
        row=self.row()
        self.c.execute(
            "INSERT INTO operator_capability_revocations VALUES(?,?,?,?,?,NULL)",
            ("M1","COOPERATIVE_ARTIFACT_PRODUCTION","cmd-1",int(row["control_epoch"]),now()),
        )
        self.c.commit()
        with self.assertRaisesRegex(ValueError,"capability revoked"):
            g.release_held_assignment(self.c,self.aid,self.evidence(),now)
        self.assertEqual(self.row()["state"],"HELD")

    def test_coordinate_substitution_blocks_release(self):
        with self.assertRaisesRegex(ValueError,"coordinate substitution"):
            g.release_held_assignment(
                self.c,self.aid,self.evidence(material_drone_id="MD002"),now
            )
        self.assertEqual(self.row()["state"],"HELD")


if __name__=="__main__":
    unittest.main()
