from __future__ import annotations

import hashlib
from pathlib import Path
import sqlite3
import unittest

from cyber_lion.enterprise.cooperative_runtime_root import CooperativeRuntimeCompositionRoot
from cyber_lion.mission_control import cooperative_production as cp
from cyber_lion.mission_control import global_scheduler
from cyber_lion.mission_control.cooperative_worker_runtime import CooperativeWorkerRuntimeRegistry
from cyber_lion.tests import test_runtime_currentness as rc
from cyber_lion.tests import test_runtime_execution as rt
from cyber_lion.tests.test_cooperative_worker_qualification import (
    CooperativeWorkerQualificationTests,
)


class CooperativeFunctionalAcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.q = CooperativeWorkerQualificationTests(
            "test_released_projection_qualifies_one_worker_without_claim_or_effect"
        )
        self.q.setUp()
        self.addCleanup(self.q.doCleanups)
        self.now = lambda: self.q.f.now.isoformat()

    def _migrate_current_scheduler_storage(self):
        with sqlite3.connect(self.q.control.fixture.db) as db:
            global_scheduler.migrate(db, self.now)
            self.assertEqual(db.execute("PRAGMA integrity_check").fetchone()[0], "ok")
            cols = {row[1] for row in db.execute("PRAGMA table_info(mission_execution_assignments)")}
        self.assertTrue({"created_at", "claimed_at", "finished_at"} <= cols)

    def _control(self, op, args):
        with sqlite3.connect(self.q.control.fixture.db) as db:
            db.row_factory = sqlite3.Row
            if op == "local_assignment_claim":
                return global_scheduler.claim_assignment(
                    db,
                    args["assignment_id"],
                    self.now,
                    expected_material_drone_id=args["material_drone_id"],
                    lease_seconds=120,
                )
            if op == "local_assignment_receipt":
                receipt = global_scheduler.record_receipt(
                    db,
                    args["assignment_id"],
                    args["result"],
                    self.now,
                    material_drone_id=args["material_drone_id"],
                    lease_generation=int(args["lease_generation"]),
                    status=args["status"],
                    effect_receipt_digest=args.get("effect_receipt_digest"),
                    authority_effect="NONE",
                )
                global_scheduler.store_assignment_payload(
                    db,
                    args["assignment_id"],
                    receipt["receipt_id"],
                    args["result"],
                    self.now,
                )
                return {**receipt, "status": args["status"], "result": args["result"]}
            raise AssertionError(op)

    def _row(self, assignment_id):
        with sqlite3.connect(self.q.control.fixture.db) as db:
            db.row_factory = sqlite3.Row
            row = db.execute(
                "SELECT * FROM mission_execution_assignments WHERE assignment_id=?",
                (assignment_id,),
            ).fetchone()
        self.assertIsNotNone(row)
        return dict(row)

    def _verifier_root(self):
        (
            admission,
            dispatch,
            provisioning,
            identity,
            currentness,
            provider_transfer,
            resolver,
        ) = self.q.external_sources()
        md2 = self.q.base / "worker-private" / "MD002"
        contexts = md2 / "contexts"
        verifiers = md2 / "verifiers"
        state = md2 / "state"
        for path in (contexts, verifiers, state):
            path.mkdir(parents=True, exist_ok=True)

        def transfer_source(assignment_id, purpose):
            if purpose == "CONTEXT":
                return provider_transfer(assignment_id, purpose)
            self.assertEqual(purpose, "VERIFY")
            row = self._row(assignment_id)
            return {
                "repository": "DonkeyJJLove/ai_platform",
                "source_head": "a" * 40,
                "mission_id": row["mission_id"],
                "assignment_id": row["assignment_id"],
                "conversation_id": "conversation-verifier-fixture",
                "binding_epoch": 1,
                "generation": int(row["lease_generation"]),
                "lease_generation": int(row["lease_generation"]),
                "context_digest": hashlib.sha256(b"verify-context").hexdigest(),
                "projection_digest": hashlib.sha256(b"verify-projection").hexdigest(),
                "request_id": "request-verifier-fixture",
                "producer_ref": "MISSION_CONTROL",
            }

        return CooperativeRuntimeCompositionRoot(
            mission_db=self.q.control.fixture.db,
            artifact_root=self.q.artifacts,
            context_parent=contexts,
            verifier_parent=verifiers,
            materialization_db=state / "materialization.sqlite",
            runtime_state_db=state / "runtime-state.sqlite",
            context_source=lambda aid: resolver(aid)(aid),
            qualification_context_source=lambda aid: resolver(aid).resolve_for_qualification(aid),
            upstream_admission_source=admission,
            upstream_admission_trust=rt.trust(),
            durable_admission_trust=self.q.durable_trust,
            authority_admission=self.q.f.live_authority,
            currentness_source=currentness,
            currentness_trust=rc.trust(),
            dispatch_source=dispatch,
            runtime_identity_source=identity,
            provisioning_binding_source=provisioning,
            transfer_binding_source=transfer_source,
            now_fn=lambda: self.q.f.now,
        )

    def test_historical_r617_fixture_migrates_under_current_scheduler_schema(self):
        self._migrate_current_scheduler_storage()

    def test_r616_r617_claim_write_and_independent_verify_end_to_end(self):
        self._migrate_current_scheduler_storage()

        release = self.q.release()
        builder_root = self.q.worker()
        qualification = builder_root.qualify_released_write_assignment(
            self.q.aid, material_worker_id="MD001"
        )
        self.assertFalse(qualification["execution_performed"])
        self.assertEqual(qualification["authority_effect"], "NONE")

        builder_registry = CooperativeWorkerRuntimeRegistry()
        self.assertIsNone(builder_registry.current("MD001"))
        builder_registry.install(builder_root)
        builder_runtime = builder_registry.current("MD001")
        self.assertIsNotNone(builder_runtime)

        write_row = self._row(self.q.aid)
        with sqlite3.connect(self.q.control.fixture.db) as db:
            db.row_factory = sqlite3.Row
            eligible, reason = global_scheduler.assignment_claim_eligibility(
                db,
                db.execute(
                    "SELECT * FROM mission_execution_assignments WHERE assignment_id=?",
                    (self.q.aid,),
                ).fetchone(),
            )
        self.assertTrue(eligible, reason)
        write_receipt = builder_runtime.process_once(self._control, [write_row])
        self.assertIsNotNone(write_receipt)
        self.assertEqual(write_receipt["status"], "PASS", write_receipt)

        verifier_root = self._verifier_root()
        with sqlite3.connect(self.q.control.fixture.db) as db:
            db.row_factory = sqlite3.Row
            verify_prepare = cp.advance_verify(
                db,
                mission_id="M1",
                build_phase_id="BUILD",
                verify_phase_id="VERIFY",
                generation=1,
                now_fn=self.now,
                verifier_worker_id="MD002",
                verify_materializer=verifier_root.verify_materializer,
            )
        self.assertEqual(verify_prepare["state"], "WAITING")
        self.assertEqual(verify_prepare["gate"], "ARTIFACT_VERIFY")
        verify_id = verify_prepare["assignment_id"]

        verifier_registry = CooperativeWorkerRuntimeRegistry()
        verifier_registry.install(verifier_root)
        verifier_runtime = verifier_registry.current("MD002")
        self.assertIsNotNone(verifier_runtime)
        verify_receipt = verifier_runtime.process_once(self._control, [self._row(verify_id)])
        self.assertIsNotNone(verify_receipt)
        self.assertEqual(verify_receipt["status"], "PASS", verify_receipt)

        with sqlite3.connect(self.q.control.fixture.db) as db:
            db.row_factory = sqlite3.Row
            write = dict(
                db.execute(
                    "SELECT state,claimed_at,finished_at FROM mission_execution_assignments WHERE assignment_id=?",
                    (self.q.aid,),
                ).fetchone()
            )
            verify = dict(
                db.execute(
                    "SELECT state,claimed_at,finished_at FROM mission_execution_assignments WHERE assignment_id=?",
                    (verify_id,),
                ).fetchone()
            )
            write_payload = global_scheduler.assignment_payload(db, self.q.aid)["result"]
            verify_payload = global_scheduler.assignment_payload(db, verify_id)["result"]
            release_record = global_scheduler.held_assignment_release_evidence(db, self.q.aid)

        self.assertEqual(write["state"], "PASS")
        self.assertTrue(write["claimed_at"])
        self.assertTrue(write["finished_at"])
        self.assertEqual(verify["state"], "PASS")
        self.assertTrue(verify["claimed_at"])
        self.assertTrue(verify["finished_at"])
        self.assertTrue(write_payload["readback_match"])
        self.assertEqual(write_payload["runtime_receipt"]["effect_state"], "OBSERVED")
        self.assertEqual(write_payload["authority_effect"], "NONE")
        self.assertTrue(verify_payload["digest_match"])
        self.assertEqual(verify_payload["artifact_sha256"], write_payload["artifact_sha256"])
        self.assertEqual(verify_payload["expected_producer_worker_id"], "MD001")
        self.assertEqual(verify_payload["verifier_worker_id"], "MD002")
        self.assertEqual(verify_payload["authority_effect"], "NONE")
        self.assertEqual(
            release_record["evidence"]["evidence_digest"],
            release["evidence_digest"],
        )

        files = [path for path in self.q.artifacts.rglob("*") if path.is_file()]
        self.assertEqual(len(files), 1)
        self.assertEqual(
            hashlib.sha256(files[0].read_bytes()).hexdigest(),
            write_payload["artifact_sha256"],
        )


if __name__ == "__main__":
    unittest.main()
