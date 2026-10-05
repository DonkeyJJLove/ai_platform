"""R6.17 single-worker qualification over the R6.16 exported provider projection.

Synthetic authority/runtime fixtures only. No live container, mission claim or material
artifact effect is performed by this suite.
"""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import sqlite3
import unittest

from cyber_lion.contracts.runtime_execution import RuntimeAdmissionSourceTrustBinding
from cyber_lion.enterprise.cooperative_context_resolver import PinnedCooperativeContextResolver
from cyber_lion.enterprise.cooperative_runtime_evidence_sources import (
    SQLiteContextPinSource,
    SQLiteEffectTimeCurrentnessSource,
    SQLiteEvidenceRuntimeAdmissionSource,
    SQLiteFleetDispatchSource,
    SQLiteProvisioningBindingSource,
    SQLiteRuntimeIdentitySource,
    SQLiteTransferBindingSource,
)
from cyber_lion.enterprise.cooperative_runtime_root import (
    CooperativeRuntimeCompositionRoot,
    CooperativeRuntimeRootError,
)
from cyber_lion.mission_control import cooperative_production as cp
from cyber_lion.tests import test_cooperative_control_plane_materializer as control_fixture
from cyber_lion.tests import test_runtime_currentness as rc
from cyber_lion.tests import test_runtime_execution as rt


class CooperativeWorkerQualificationTests(unittest.TestCase):
    def setUp(self):
        self.control = control_fixture.CooperativeControlPlaneMaterializerTests(
            "test_complete_sequence_then_existing_release_fence_sets_ready"
        )
        self.control.setUp()
        self.addCleanup(self.control.doCleanups)
        self.f = self.control.f
        self.aid = self.control.fixture.aid
        self.base = self.control.base

        self.worker_root = self.base / "worker-private" / "MD001"
        self.artifacts = self.worker_root / "artifacts"
        self.contexts = self.worker_root / "contexts"
        self.verifiers = self.worker_root / "verifiers"
        self.state = self.worker_root / "state"
        for path in (self.artifacts, self.contexts, self.verifiers, self.state):
            path.mkdir(parents=True, exist_ok=True)

        # The exported canonical context must name the exact private artifact root
        # that the single qualified worker will later use.
        self.f.root = self.artifacts
        self.f.binding = replace(self.f.binding, artifact_root=self.artifacts)

        self.durable_trust = RuntimeAdmissionSourceTrustBinding(
            "cooperative-qualification-admission",
            "cooperative-qualification-admission:fixture",
            rt.Z,
            "cooperative-qualification-root",
            rt.F,
        ).validate()

    def release(self):
        connection = sqlite3.connect(self.control.fixture.db)
        connection.row_factory = sqlite3.Row
        try:
            result = cp._materialize_and_release(
                connection,
                self.aid,
                materializer=self.control.materializer(),
                expected_kind=cp.WRITE_MATERIALIZATION_KIND,
                expected_provider=cp.WRITE_PROVIDER_ID,
                now_fn=lambda: self.f.now.isoformat(),
            )
        finally:
            connection.close()
        self.assertEqual(result["authority_effect"], "NONE")
        self.assertEqual(self.assignment_state(), "READY")
        return result

    def assignment_state(self):
        with sqlite3.connect(self.control.fixture.db) as db:
            return db.execute(
                "SELECT state FROM mission_execution_assignments WHERE assignment_id=?",
                (self.aid,),
            ).fetchone()[0]

    def assignment_receipt_count(self):
        with sqlite3.connect(self.control.fixture.db) as db:
            exists = db.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='mission_execution_receipts'"
            ).fetchone()
            if not exists:
                return 0
            return db.execute(
                "SELECT COUNT(*) FROM mission_execution_receipts WHERE assignment_id=?",
                (self.aid,),
            ).fetchone()[0]

    def private_counts(self):
        with sqlite3.connect(self.state / "materialization.sqlite") as db:
            contexts = db.execute(
                "SELECT COUNT(*) FROM cooperative_context_materialization"
            ).fetchone()[0]
        with sqlite3.connect(self.state / "runtime-state.sqlite") as db:
            admissions = db.execute("SELECT COUNT(*) FROM runtime_admissions").fetchone()[0]
        return contexts, admissions

    def external_sources(self):
        now_fn = lambda: self.f.now
        admission = SQLiteEvidenceRuntimeAdmissionSource(
            self.control.provider_db, rt.trust(), now_fn=now_fn
        )
        pins = SQLiteContextPinSource(self.control.provider_db, now_fn=now_fn)
        dispatch = SQLiteFleetDispatchSource(self.control.provider_db, now_fn=now_fn)
        provisioning = SQLiteProvisioningBindingSource(
            self.control.provider_db, now_fn=now_fn
        )
        identity = SQLiteRuntimeIdentitySource(self.control.provider_db, now_fn=now_fn)
        currentness = SQLiteEffectTimeCurrentnessSource(
            self.control.provider_db, rc.trust(), now_fn=now_fn
        )
        transfer = SQLiteTransferBindingSource(self.control.provider_db, now_fn=now_fn)

        def resolver(assignment_id):
            pin = pins(assignment_id)
            return PinnedCooperativeContextResolver(
                mission_db=self.control.fixture.db,
                context_directory=self.control.provider_root,
                pins=(pin,),
                admission_source=admission,
                admission_trust=rt.trust(),
                dispatch_source=dispatch,
                runtime_identity_source=identity,
                now_fn=now_fn,
            )

        return admission, dispatch, provisioning, identity, currentness, transfer, resolver

    def worker(self):
        admission, dispatch, provisioning, identity, currentness, transfer, resolver = (
            self.external_sources()
        )
        return CooperativeRuntimeCompositionRoot(
            mission_db=self.control.fixture.db,
            artifact_root=self.artifacts,
            context_parent=self.contexts,
            verifier_parent=self.verifiers,
            materialization_db=self.state / "materialization.sqlite",
            runtime_state_db=self.state / "runtime-state.sqlite",
            context_source=lambda aid: resolver(aid)(aid),
            qualification_context_source=lambda aid: resolver(aid).resolve_for_qualification(aid),
            upstream_admission_source=admission,
            upstream_admission_trust=rt.trust(),
            durable_admission_trust=self.durable_trust,
            authority_admission=self.f.live_authority,
            currentness_source=currentness,
            currentness_trust=rc.trust(),
            dispatch_source=dispatch,
            runtime_identity_source=identity,
            provisioning_binding_source=provisioning,
            transfer_binding_source=transfer,
            now_fn=lambda: self.f.now,
        )

    def test_released_projection_qualifies_one_worker_without_claim_or_effect(self):
        release = self.release()
        provider_carrier = next(self.control.provider_root.glob("context-*.json"))
        provider_bytes = provider_carrier.read_bytes()
        worker = self.worker()
        before_receipts = self.assignment_receipt_count()

        result = worker.qualify_released_write_assignment(
            self.aid, material_worker_id="MD001"
        )

        self.assertEqual(result["schema"], "lion.cooperative-worker-qualification/v1")
        self.assertEqual(result["worker_id"], "MD001")
        self.assertEqual(result["provider_id"], "COOPERATIVE_RUNTIME_WRITER_R5")
        self.assertEqual(result["authority_effect"], "NONE")
        self.assertTrue(result["writer_factory_built"])
        self.assertFalse(result["execution_performed"])
        self.assertEqual(len(result["qualification_digest"]), 64)
        self.assertEqual(result["control_plane_evidence_digest"], release["evidence_digest"])
        self.assertEqual(self.assignment_state(), "READY")
        self.assertEqual(self.assignment_receipt_count(), before_receipts)
        self.assertEqual(list(self.artifacts.iterdir()), [])
        self.assertEqual(provider_carrier.read_bytes(), provider_bytes)
        self.assertEqual(self.private_counts(), (1, 1))

        materialized, bound_worker, admission_digest = worker.store.resolve_context(self.aid)
        self.assertEqual(bound_worker, "MD001")
        self.assertEqual(materialized.workspace.parent, self.contexts)
        self.assertEqual(
            materialized.pin.sha256, result["private_context_pin_sha256"]
        )
        self.assertEqual(
            materialized.transfer_sha256, result["private_transfer_sha256"]
        )
        self.assertTrue(worker.admission_source.is_current(admission_digest))

        # Effect resolver is intentionally still CLAIMED-only.
        with self.assertRaisesRegex(Exception, "assignment/driver not active"):
            worker.context_source(self.aid)
        self.assertEqual(self.assignment_state(), "READY")
        self.assertEqual(list(self.artifacts.iterdir()), [])

    def test_ready_without_canonical_release_record_is_not_qualifiable(self):
        with sqlite3.connect(self.control.fixture.db) as db:
            db.execute(
                "UPDATE mission_execution_assignments SET state=? WHERE assignment_id=?",
                ("READY", self.aid),
            )
            db.commit()
        worker = self.worker()
        with self.assertRaisesRegex(
            CooperativeRuntimeRootError, "release evidence unavailable"
        ):
            worker.qualify_released_write_assignment(
                self.aid, material_worker_id="MD001"
            )
        self.assertEqual(self.private_counts(), (0, 0))
        self.assertEqual(list(self.artifacts.iterdir()), [])

    def test_wrong_worker_is_rejected_before_private_import(self):
        self.release()
        worker = self.worker()
        with self.assertRaisesRegex(
            CooperativeRuntimeRootError, "worker substitution"
        ):
            worker.qualify_released_write_assignment(
                self.aid, material_worker_id="MD002"
            )
        self.assertEqual(self.private_counts(), (0, 0))
        self.assertEqual(list(self.contexts.iterdir()), [])
        self.assertEqual(list(self.artifacts.iterdir()), [])
        self.assertEqual(self.assignment_state(), "READY")

    def test_tampered_provider_carrier_is_rejected_before_private_import(self):
        self.release()
        carrier = next(self.control.provider_root.glob("context-*.json"))
        carrier.write_bytes(carrier.read_bytes() + b" ")
        worker = self.worker()
        with self.assertRaisesRegex(Exception, "pin mismatch"):
            worker.qualify_released_write_assignment(
                self.aid, material_worker_id="MD001"
            )
        self.assertEqual(self.private_counts(), (0, 0))
        self.assertEqual(list(self.contexts.iterdir()), [])
        self.assertEqual(list(self.artifacts.iterdir()), [])
        self.assertEqual(self.assignment_state(), "READY")

    def test_provider_database_replacement_is_rejected_by_bound_read_sources(self):
        self.release()
        worker = self.worker()
        replacement = self.base / "replacement-provider.sqlite"
        replacement.write_bytes(self.control.provider_db.read_bytes())
        self.control.provider_db.unlink()
        replacement.replace(self.control.provider_db)
        with self.assertRaisesRegex(Exception, "identity drift"):
            worker.qualify_released_write_assignment(
                self.aid, material_worker_id="MD001"
            )
        self.assertEqual(self.private_counts(), (0, 0))
        self.assertEqual(list(self.contexts.iterdir()), [])
        self.assertEqual(list(self.artifacts.iterdir()), [])
        self.assertEqual(self.assignment_state(), "READY")

    def test_successful_qualification_replay_is_denied_without_duplicate_workspace(self):
        self.release()
        worker = self.worker()
        worker.qualify_released_write_assignment(
            self.aid, material_worker_id="MD001"
        )
        first_workspaces = tuple(sorted(path.name for path in self.contexts.iterdir()))
        self.assertEqual(len(first_workspaces), 1)
        with self.assertRaisesRegex(Exception, "publication replay denied"):
            worker.qualify_released_write_assignment(
                self.aid, material_worker_id="MD001"
            )
        self.assertEqual(
            tuple(sorted(path.name for path in self.contexts.iterdir())),
            first_workspaces,
        )
        self.assertEqual(self.private_counts(), (1, 1))
        self.assertEqual(list(self.artifacts.iterdir()), [])
        self.assertEqual(self.assignment_state(), "READY")

    def test_stale_provider_admission_is_rejected_before_private_import(self):
        self.release()
        with sqlite3.connect(self.control.provider_db) as db:
            db.execute(
                "UPDATE runtime_admission_evidence SET expires_at=?",
                ("2020-01-01T00:00:00+00:00",),
            )
            db.commit()
        worker = self.worker()
        with self.assertRaisesRegex(Exception, "stale"):
            worker.qualify_released_write_assignment(
                self.aid, material_worker_id="MD001"
            )
        self.assertEqual(self.private_counts(), (0, 0))
        self.assertEqual(list(self.contexts.iterdir()), [])
        self.assertEqual(list(self.artifacts.iterdir()), [])
        self.assertEqual(self.assignment_state(), "READY")


if __name__ == "__main__":
    unittest.main()
