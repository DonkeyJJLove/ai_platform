from __future__ import annotations

from hashlib import sha256
import json
import sqlite3
import unittest
from unittest.mock import patch

from cyber_lion.mission_control import cooperative_production as cp


class CooperativeProductionStepperTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript("""
        CREATE TABLE mission_execution_assignments(
          assignment_id TEXT PRIMARY KEY, mission_id TEXT NOT NULL, phase_id TEXT NOT NULL,
          logical_drone_id TEXT NOT NULL, material_drone_id TEXT NOT NULL,
          input_digest TEXT NOT NULL, input_json TEXT NOT NULL DEFAULT '{}',
          state TEXT NOT NULL, lease_generation INTEGER NOT NULL,
          control_epoch INTEGER NOT NULL DEFAULT 0, context_revision INTEGER NOT NULL DEFAULT 0,
          plan_revision INTEGER NOT NULL DEFAULT 0, dispatch_authority TEXT NOT NULL DEFAULT 'AUTONOMOUS',
          created_at TEXT NOT NULL, claimed_at TEXT, lease_expires_at TEXT, finished_at TEXT
        );
        CREATE TABLE mission_execution_receipts(
          receipt_id TEXT PRIMARY KEY, assignment_id TEXT NOT NULL, mission_id TEXT NOT NULL,
          phase_id TEXT NOT NULL, result_digest TEXT NOT NULL, effect_receipt_digest TEXT,
          authority_effect TEXT NOT NULL, status TEXT NOT NULL, observed_at TEXT NOT NULL
        );
        CREATE TABLE mission_assignment_payloads(
          assignment_id TEXT PRIMARY KEY, receipt_id TEXT NOT NULL, mission_id TEXT NOT NULL,
          phase_id TEXT NOT NULL, result_digest TEXT NOT NULL, result_json TEXT NOT NULL,
          created_at TEXT NOT NULL
        );
        """)
        self.counter = 0
        self.mission = "LION-COOPERATIVE-PRODUCTION-PILOT-R2"
        self.phase = "LOCAL_MODEL_BUILD"
        self.now = lambda: "2026-10-04T21:30:00Z"

    def fake_create(self, conn, mission_id, phase_id, logical_drone_id, material_drone_id, input_value, now_fn, *, lease_generation, dispatch_authority="AUTONOMOUS", initial_state="READY"):
        self.counter += 1
        aid = f"assignment-{self.counter}"
        raw = json.dumps(input_value, sort_keys=True, separators=(",", ":"))
        conn.execute(
            "INSERT INTO mission_execution_assignments VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (aid, mission_id, phase_id, logical_drone_id, material_drone_id,
             sha256(raw.encode()).hexdigest(), raw, initial_state, lease_generation, 0, 0, 0,
             dispatch_authority, now_fn(), None, None, None),
        )
        conn.commit()
        return aid

    def fake_create_held(self, conn, mission_id, phase_id, logical_drone_id, material_drone_id, input_value, now_fn, *, lease_generation, dispatch_authority="AUTONOMOUS"):
        return self.fake_create(
            conn, mission_id, phase_id, logical_drone_id, material_drone_id,
            input_value, now_fn, lease_generation=lease_generation,
            dispatch_authority=dispatch_authority, initial_state="HELD",
        )

    def fake_release(self, conn, assignment_id, evidence, now_fn):
        row=conn.execute("SELECT state FROM mission_execution_assignments WHERE assignment_id=?",(assignment_id,)).fetchone()
        if not row or row["state"]!="HELD":
            raise ValueError("assignment not held")
        conn.execute("UPDATE mission_execution_assignments SET state='READY' WHERE assignment_id=?",(assignment_id,))
        conn.commit()
        return {"assignment_id":assignment_id,"state":"READY","release_evidence_digest":"f"*64,"authority_effect":"NONE"}

    @staticmethod
    def write_materializer(_presented):
        return {"materialization_kind":cp.WRITE_MATERIALIZATION_KIND,
                "provider_id":cp.WRITE_PROVIDER_ID,
                "evidence_digest":"a"*64,"authority_effect":"NONE"}

    @staticmethod
    def verify_materializer(_presented):
        return {"materialization_kind":cp.VERIFY_MATERIALIZATION_KIND,
                "provider_id":cp.VERIFY_PROVIDER_ID,
                "evidence_digest":"b"*64,"authority_effect":"NONE"}

    def complete(self, aid, result):
        row = self.conn.execute("SELECT mission_id,phase_id FROM mission_execution_assignments WHERE assignment_id=?", (aid,)).fetchone()
        dg = sha256(json.dumps(result, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        rid = "receipt-" + aid
        self.conn.execute("UPDATE mission_execution_assignments SET state='PASS',finished_at=? WHERE assignment_id=?", (self.now(), aid))
        self.conn.execute("INSERT INTO mission_execution_receipts VALUES(?,?,?,?,?,?,?,?,?)",
                          (rid, aid, row["mission_id"], row["phase_id"], dg, None, "NONE", "PASS", self.now()))
        self.conn.execute("INSERT INTO mission_assignment_payloads VALUES(?,?,?,?,?,?,?)",
                          (aid, rid, row["mission_id"], row["phase_id"], dg, json.dumps(result), self.now()))
        self.conn.commit()

    def test_model_write_verify_chain(self):
        with patch("cyber_lion.mission_control.cooperative_production.global_scheduler.create_assignment", side_effect=self.fake_create),              patch("cyber_lion.mission_control.cooperative_production.global_scheduler.create_held_assignment", side_effect=self.fake_create_held),              patch("cyber_lion.mission_control.cooperative_production.global_scheduler.release_held_assignment", side_effect=self.fake_release):
            self._model_write_verify_chain()

    def _model_write_verify_chain(self):
        first = cp.advance_production(self.conn, mission_id=self.mission, phase_id=self.phase, generation=1, now_fn=self.now, write_materializer=self.write_materializer, verify_materializer=self.verify_materializer)
        self.assertEqual(first["gate"], "MODEL_ASSIGNMENT")
        model_id = first["assignment_id"]
        model_result = {
            "kind": "LOCAL_MODEL_INFERENCE",
            "model": "gpt-oss-20b-MXFP4",
            "model_call_id": "modelcall-0123456789abcdef",
            "response_text": "purpose=cooperative-production\nmission=" + self.mission + "\nstatus=generated-by-local-model.",
            "response_digest": "a" * 64,
            "authority_effect": "NONE",
        }
        self.complete(model_id, model_result)

        second = cp.advance_production(self.conn, mission_id=self.mission, phase_id=self.phase, generation=1, now_fn=self.now, write_materializer=self.write_materializer, verify_materializer=self.verify_materializer)
        self.assertEqual(second["gate"], "ARTIFACT_WRITE")
        write_id = second["assignment_id"]
        write_input = json.loads(self.conn.execute("SELECT input_json FROM mission_execution_assignments WHERE assignment_id=?", (write_id,)).fetchone()[0])
        expected = write_input["expected_sha256"]
        self.complete(write_id, {
            "kind": "COOPERATIVE_ARTIFACT_WRITE",
            "artifact_sha256": expected,
            "artifact_path": "/gate/products/" + self.mission + "/g00000001/lion-pilot-artifact.txt",
            "producer_worker_id": "MD001",
            "authority_effect": "NONE",
        })

        third = cp.advance_production(self.conn, mission_id=self.mission, phase_id=self.phase, generation=1, now_fn=self.now, write_materializer=self.write_materializer, verify_materializer=self.verify_materializer)
        self.assertEqual(third["gate"], "ARTIFACT_VERIFY")
        verify_id = third["assignment_id"]
        self.complete(verify_id, {
            "kind": "COOPERATIVE_ARTIFACT_VERIFY",
            "artifact_sha256": expected,
            "digest_match": True,
            "verifier_worker_id": "MD002",
            "authority_effect": "NONE",
        })

        final = cp.advance_production(self.conn, mission_id=self.mission, phase_id=self.phase, generation=1, now_fn=self.now, write_materializer=self.write_materializer, verify_materializer=self.verify_materializer)
        self.assertEqual(final["state"], "PASS")
        self.assertEqual(final["builder_worker_id"], "MD001")
        self.assertEqual(final["verifier_worker_id"], "MD002")
        self.assertEqual(final["artifact_sha256"], expected)
        self.assertNotEqual(final["write_assignment_id"], final["verify_assignment_id"])

    def test_split_build_then_verify(self):
        with patch("cyber_lion.mission_control.cooperative_production.global_scheduler.create_assignment", side_effect=self.fake_create),              patch("cyber_lion.mission_control.cooperative_production.global_scheduler.create_held_assignment", side_effect=self.fake_create_held),              patch("cyber_lion.mission_control.cooperative_production.global_scheduler.release_held_assignment", side_effect=self.fake_release):
            self._split_build_then_verify()

    def _split_build_then_verify(self):
        first = cp.advance_build(self.conn, mission_id=self.mission, phase_id=self.phase, generation=1, now_fn=self.now, write_materializer=self.write_materializer)
        model_id = first["assignment_id"]
        self.complete(model_id, {
            "kind": "LOCAL_MODEL_INFERENCE",
            "model_call_id": "modelcall-0123456789abcdef",
            "response_text": "purpose=cooperative-production\\nmission=" + self.mission + "\\nstatus=generated-by-local-model.",
            "response_digest": "a" * 64,
            "authority_effect": "NONE",
        })
        second = cp.advance_build(self.conn, mission_id=self.mission, phase_id=self.phase, generation=1, now_fn=self.now, write_materializer=self.write_materializer)
        write_id = second["assignment_id"]
        payload = json.loads(self.conn.execute("SELECT input_json FROM mission_execution_assignments WHERE assignment_id=?", (write_id,)).fetchone()[0])
        expected = payload["expected_sha256"]
        self.complete(write_id, {
            "kind": "COOPERATIVE_ARTIFACT_WRITE",
            "artifact_name": "lion-pilot-artifact.txt",
            "artifact_sha256": expected,
            "artifact_path": "/gate/products/" + self.mission + "/g00000001/lion-pilot-artifact.txt",
            "producer_worker_id": "MD001",
            "authority_effect": "NONE",
        })
        built = cp.advance_build(self.conn, mission_id=self.mission, phase_id=self.phase, generation=1, now_fn=self.now, write_materializer=self.write_materializer)
        self.assertEqual(built["state"], "PASS")
        third = cp.advance_verify(self.conn, mission_id=self.mission, build_phase_id=self.phase, verify_phase_id="INDEPENDENT_VERIFY", generation=1, now_fn=self.now, verify_materializer=self.verify_materializer)
        verify_id = third["assignment_id"]
        self.complete(verify_id, {
            "kind": "COOPERATIVE_ARTIFACT_VERIFY",
            "artifact_sha256": expected,
            "digest_match": True,
            "verifier_worker_id": "MD002",
            "authority_effect": "NONE",
        })
        verified = cp.advance_verify(self.conn, mission_id=self.mission, build_phase_id=self.phase, verify_phase_id="INDEPENDENT_VERIFY", generation=1, now_fn=self.now, verify_materializer=self.verify_materializer)
        self.assertEqual(verified["state"], "PASS")
        self.assertEqual(verified["builder_worker_id"], "MD001")
        self.assertEqual(verified["verifier_worker_id"], "MD002")

    def test_write_assignment_remains_held_without_runtime_context_materializer(self):
        with patch("cyber_lion.mission_control.cooperative_production.global_scheduler.create_assignment", side_effect=self.fake_create),              patch("cyber_lion.mission_control.cooperative_production.global_scheduler.create_held_assignment", side_effect=self.fake_create_held):
            first=cp.advance_build(self.conn,mission_id=self.mission,phase_id=self.phase,generation=1,now_fn=self.now)
            self.complete(first["assignment_id"],{
                "kind":"LOCAL_MODEL_INFERENCE","model_call_id":"modelcall-0123456789abcdef",
                "response_text":"purpose=cooperative-production\nmission="+self.mission+"\nstatus=generated-by-local-model.",
                "response_digest":"a"*64,"authority_effect":"NONE",
            })
            held=cp.advance_build(self.conn,mission_id=self.mission,phase_id=self.phase,generation=1,now_fn=self.now)
            self.assertEqual(held["gate"],"RUNTIME_CONTEXT_PROVIDER_REQUIRED")
            row=self.conn.execute("SELECT state FROM mission_execution_assignments WHERE assignment_id=?",(held["assignment_id"],)).fetchone()
            self.assertEqual(row["state"],"HELD")
            again=cp.advance_build(
                self.conn,mission_id=self.mission,phase_id=self.phase,generation=1,now_fn=self.now,
                write_materializer=lambda _: (_ for _ in ()).throw(AssertionError("must not auto-retry materializer")),
            )
            self.assertEqual(again["assignment_id"],held["assignment_id"])
            self.assertEqual(again["gate"],"RUNTIME_CONTEXT_PROVIDER_REQUIRED")

    def put_cross_model_bundle(self, bundle_digest="c" * 64):
        self.conn.executescript("""
        CREATE TABLE IF NOT EXISTS mission_artifacts(
          artifact_id TEXT PRIMARY KEY,
          mission_id TEXT NOT NULL,
          phase_id TEXT,
          artifact_type TEXT NOT NULL,
          schema_id TEXT NOT NULL,
          revision INTEGER NOT NULL DEFAULT 1,
          content_digest TEXT NOT NULL,
          content_json TEXT NOT NULL,
          authority_effect TEXT NOT NULL,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          UNIQUE(mission_id,artifact_type,phase_id)
        );
        """)
        content = {
            "schema": "lion.control-plane-intelligence-bundle/v1",
            "mission_id": self.mission,
            "bundle_digest": bundle_digest,
            "findings": [{"finding": "source-current", "status": "PASS"}],
            "root_cause_candidates": [],
            "local_model_trajectories": [{
                "phase_id": "CROSS_MODEL_RECON",
                "trajectory_role": "PRIMARY_RECONSTRUCTION",
                "evidence_bundle_digest": "e" * 64,
                "result_digest": "1" * 64,
                "response_digest": "2" * 64,
                "state": "PASS",
            }],
            "saas_advisories": [{
                "phase_id": "CROSS_MODEL_RECON",
                "evidence_bundle_digest": "e" * 64,
                "advisory_role": "INDEPENDENT_ADVISORY_TRAJECTORY",
                "request_id": "request-cross-model",
                "state": "RESPONDED",
                "response_digest": "3" * 64,
                "receipt_digest": "4" * 64,
            }],
            "cross_model_agreements": [],
            "cross_model_disagreements": [{
                "phase_id": "CROSS_MODEL_RECON",
                "resolution": "FALSIFICATION_OR_UNKNOWN",
            }],
            "unknowns": [{"claim": "remaining-unknown"}],
            "authority_effect": "NONE",
        }
        cp.global_scheduler.put_artifact(
            self.conn,
            self.mission,
            "CONTROL_PLANE_INTELLIGENCE_BUNDLE",
            content,
            self.now,
            schema_id=content["schema"],
            authority_effect="NONE",
        )
        return cp.global_scheduler.artifact(
            self.conn,
            self.mission,
            "CONTROL_PLANE_INTELLIGENCE_BUNDLE",
        )

    def test_build_binds_cross_model_intelligence_into_model_and_write_provenance(self):
        bundle = self.put_cross_model_bundle()
        with patch("cyber_lion.mission_control.cooperative_production.global_scheduler.create_assignment", side_effect=self.fake_create), \
             patch("cyber_lion.mission_control.cooperative_production.global_scheduler.create_held_assignment", side_effect=self.fake_create_held), \
             patch("cyber_lion.mission_control.cooperative_production.global_scheduler.release_held_assignment", side_effect=self.fake_release):
            first = cp.advance_build(
                self.conn, mission_id=self.mission, phase_id=self.phase,
                generation=1, now_fn=self.now, write_materializer=self.write_materializer,
            )
            model_id = first["assignment_id"]
            model_input = json.loads(self.conn.execute(
                "SELECT input_json FROM mission_execution_assignments WHERE assignment_id=?",
                (model_id,),
            ).fetchone()[0])
            self.assertEqual(
                model_input["source_intelligence_bundle_digest"],
                bundle["content"]["bundle_digest"],
            )
            self.assertIn(
                bundle["content"]["bundle_digest"],
                model_input["messages"][0]["content"],
            )
            self.complete(model_id, {
                "kind": "LOCAL_MODEL_INFERENCE",
                "model_call_id": "modelcall-cross-model",
                "response_text": "cross-model artifact\nsource=" + bundle["content"]["bundle_digest"],
                "response_digest": "a" * 64,
                "authority_effect": "NONE",
            })

            second = cp.advance_build(
                self.conn, mission_id=self.mission, phase_id=self.phase,
                generation=1, now_fn=self.now, write_materializer=self.write_materializer,
            )
            self.assertEqual(second["gate"], "ARTIFACT_WRITE")
            write_id = second["assignment_id"]
            write_input = json.loads(self.conn.execute(
                "SELECT input_json FROM mission_execution_assignments WHERE assignment_id=?",
                (write_id,),
            ).fetchone()[0])
            self.assertEqual(
                write_input["source_intelligence_bundle_digest"],
                bundle["content"]["bundle_digest"],
            )
            expected = write_input["expected_sha256"]
            self.complete(write_id, {
                "kind": "COOPERATIVE_ARTIFACT_WRITE",
                "artifact_name": "lion-pilot-artifact.txt",
                "artifact_sha256": expected,
                "artifact_path": "/gate/products/" + self.mission + "/g00000001/lion-pilot-artifact.txt",
                "producer_worker_id": "MD001",
                "authority_effect": "NONE",
            })
            final = cp.advance_build(
                self.conn, mission_id=self.mission, phase_id=self.phase,
                generation=1, now_fn=self.now, write_materializer=self.write_materializer,
            )
        self.assertEqual(final["state"], "PASS")
        self.assertEqual(
            final["source_intelligence_bundle_digest"],
            bundle["content"]["bundle_digest"],
        )

    def test_cross_model_intelligence_drift_blocks_before_write_assignment(self):
        first_bundle = self.put_cross_model_bundle("c" * 64)
        with patch("cyber_lion.mission_control.cooperative_production.global_scheduler.create_assignment", side_effect=self.fake_create), \
             patch("cyber_lion.mission_control.cooperative_production.global_scheduler.create_held_assignment", side_effect=self.fake_create_held), \
             patch("cyber_lion.mission_control.cooperative_production.global_scheduler.release_held_assignment", side_effect=self.fake_release):
            first = cp.advance_build(
                self.conn, mission_id=self.mission, phase_id=self.phase,
                generation=1, now_fn=self.now, write_materializer=self.write_materializer,
            )
            self.complete(first["assignment_id"], {
                "kind": "LOCAL_MODEL_INFERENCE",
                "model_call_id": "modelcall-cross-model",
                "response_text": "candidate",
                "response_digest": "a" * 64,
                "authority_effect": "NONE",
            })
            self.put_cross_model_bundle("d" * 64)
            with self.assertRaisesRegex(cp.CooperativeProductionError, "intelligence drift"):
                cp.advance_build(
                    self.conn, mission_id=self.mission, phase_id=self.phase,
                    generation=1, now_fn=self.now, write_materializer=self.write_materializer,
                )
        count = self.conn.execute(
            "SELECT COUNT(*) FROM mission_execution_assignments WHERE phase_id=?",
            (self.phase + cp.WRITE_SUFFIX,),
        ).fetchone()[0]
        self.assertEqual(count, 0)
        self.assertEqual(
            first_bundle["content"]["bundle_digest"],
            "c" * 64,
        )

    def test_registry_effect_ceilings(self):
        reg = cp.capability_registry_entries()
        self.assertEqual(reg[cp.CAPABILITY_BOOTSTRAP][0]["effect_ceiling"], "NONE")
        self.assertEqual(reg[cp.CAPABILITY_PRODUCTION][0]["effect_ceiling"], "BOUNDED_MATERIAL")
        self.assertEqual(reg[cp.CAPABILITY_VERIFY][0]["effect_ceiling"], "NONE")


if __name__ == "__main__":
    unittest.main()
