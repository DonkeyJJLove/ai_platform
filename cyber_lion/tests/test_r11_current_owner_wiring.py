"""R11 source-bound owner constructors: use original R6.21/16/17, disposable DB."""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import sqlite3
import unittest

from cyber_lion.mission_control import cooperative_preactivation as pre
from cyber_lion.mission_control.cooperative_current_owner_wiring import (
    CurrentOwnerSources,
    R11CurrentOwnerWiringError,
    assemble_original_owners,
)
from cyber_lion.mission_control.cooperative_preactivation_bootstrap import (
    CooperativeSourceBoundPreactivation,
)
from cyber_lion.enterprise.cooperative_runtime_preparation_provider import (
    CooperativeRuntimePreparationProvider,
)
from cyber_lion.enterprise.cooperative_control_plane_materializer import (
    CooperativeControlPlaneMaterializer,
)
from cyber_lion.enterprise.cooperative_runtime_root import (
    CooperativeRuntimeCompositionRoot,
)
from cyber_lion.enterprise.r11_runtime_admission_replay import (
    SQLiteR11RuntimeAdmissionReplayGuard,
)
from cyber_lion.enterprise.runtime_enforcement import (
    InMemoryRuntimeAdmissionReplayGuard,
)
from cyber_lion.tests.test_r11_preactivation_production_binding import (
    R11SourceBoundProductionAcceptance,
)


class R11OriginalCurrentOwnersTest(unittest.TestCase):
    def setUp(self):
        self.fixture=R11SourceBoundProductionAcceptance(
            "test_original_preactivation_stepper_runs_r621_r616_r617_and_is_idempotent"
        )
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        f=self.fixture
        # The original integration fixture uses an in-memory replay guard.
        # Replace only its disposable replay owner to prove production wiring
        # needs a durable, separately pinned database across process restarts.
        self.admission_replay=SQLiteR11RuntimeAdmissionReplayGuard(
            f.state/"r11-original-admission-replay.sqlite"
        )
        f.f.fixture.engine._replay=self.admission_replay
        export=f.r616.exporter
        self.inputs=CurrentOwnerSources(
            mission_db=f.f.mission_db,
            artifact_root=f.f.fixture.root,
            carrier_root=f.carriers,
            provider_evidence_db=f.provider_db,
            worker_context_parent=f.contexts,
            worker_verifier_parent=f.verifiers,
            worker_materialization_db=f.state/"r11-constructed-materialization.sqlite",
            worker_runtime_state_db=f.state/"r11-constructed-worker-runtime.sqlite",
            preparation_evidence_source=f.f.evidence_source,
            admission_engine=f.f.fixture.engine,
            admission_source=f.f.store,
            authority_admission=export.authority_admission,
            currentness_source=export.currentness_source,
            currentness_trust=export.currentness_trust,
            dispatch_source=export.dispatch_source,
            runtime_identity_source=export.runtime_identity_source,
            provisioning_binding_source=export.provisioning_binding_source,
            transfer_binding_source=export.transfer_binding_source,
            worker_durable_admission_trust=f.worker.durable_admission_trust,
            now_fn=export.now_fn,
        )

    def test_builds_three_original_types_same_physical_mission_db(self):
        prep,mat,root,worker=assemble_original_owners(self.inputs)
        self.assertIs(type(prep),CooperativeRuntimePreparationProvider)
        self.assertIs(type(mat),CooperativeControlPlaneMaterializer)
        self.assertIs(type(root),CooperativeRuntimeCompositionRoot)
        self.assertEqual(worker,"MD001")
        self.assertTrue(Path(prep.mission_db).samefile(mat.mission_db))
        self.assertTrue(Path(prep.mission_db).samefile(root.mission_db))
        self.assertIs(mat.exporter.context_source,prep)
        self.assertIs(mat.exporter.admission_source,prep.admission_source)
        self.assertTrue(Path(mat.exporter.publisher.path).samefile(
            root.upstream_admission_source.path
        ))
        self.assertEqual(
            root.upstream_admission_trust.binding(),mat.exporter.admission_trust.binding()
        )
        self.assertIs(
            CooperativeSourceBoundPreactivation(prep,mat,root,worker).validate().worker_root,
            root,
        )

    def test_qualifies_one_disposable_md001_without_effect_receipt(self):
        prep,mat,root,worker=assemble_original_owners(self.inputs)
        provider=CooperativeSourceBoundPreactivation(prep,mat,root,worker).provider()
        with sqlite3.connect(self.fixture.f.mission_db) as db:
            db.row_factory=sqlite3.Row
            first=pre.advance_preactivation(
                db,mission_id="M1",phase_id="BUILD",generation=1,
                provider=provider,now_fn=lambda:"2026-10-12T10:00:00+00:00",
            )
            second=pre.advance_preactivation(
                db,mission_id="M1",phase_id="BUILD",generation=1,
                provider=provider,now_fn=lambda:"2026-10-12T10:00:00+00:00",
            )
            state=db.execute(
                "SELECT state FROM mission_execution_assignments WHERE assignment_id=?",
                (self.fixture.f.aid,),
            ).fetchone()[0]
            receipts=db.execute(
                "SELECT COUNT(*) FROM mission_execution_receipts WHERE assignment_id=?",
                (self.fixture.f.aid,),
            ).fetchone()[0]
        self.assertEqual(first["state"],"PASS",first)
        self.assertEqual(second["state"],"PASS",second)
        self.assertEqual(state,"READY")
        self.assertEqual(receipts,0)
        self.assertEqual(prep.status(self.fixture.f.aid)["state"],"PUBLISHED")
        self.assertEqual(list(self.fixture.f.fixture.root.iterdir()),[])

    def test_in_memory_replay_cannot_be_wired_into_current_owners(self):
        self.fixture.f.fixture.engine._replay = InMemoryRuntimeAdmissionReplayGuard()
        with self.assertRaisesRegex(R11CurrentOwnerWiringError, "durable RuntimeAdmission replay"):
            assemble_original_owners(self.inputs)
        self.assertFalse(self.inputs.worker_materialization_db.exists())

    def test_durable_replay_sqlite_cannot_alias_original_runtime_state(self):
        self.fixture.f.fixture.engine._replay = SQLiteR11RuntimeAdmissionReplayGuard(
            self.admission_replay.path
        )
        guard=self.fixture.f.fixture.engine._replay
        guard.path=self.inputs.admission_source.path  # substitution of checked path
        with self.assertRaisesRegex(Exception, "identity drift|replay SQLite"):
            assemble_original_owners(self.inputs)
        self.assertFalse(self.inputs.worker_materialization_db.exists())

    def test_wrong_worker_is_denied_before_private_sqlite_init(self):
        with self.assertRaisesRegex(R11CurrentOwnerWiringError,"only MD001"):
            assemble_original_owners(replace(self.inputs,worker_id="MD032"))
        self.assertFalse(self.inputs.worker_materialization_db.exists())

    def test_missing_preparation_evidence_owner_is_denied(self):
        with self.assertRaisesRegex(R11CurrentOwnerWiringError,"independent preparation evidence"):
            assemble_original_owners(replace(self.inputs,preparation_evidence_source=None))
        self.assertFalse(self.inputs.worker_materialization_db.exists())

    def test_foreign_admission_engine_is_denied(self):
        with self.assertRaisesRegex(R11CurrentOwnerWiringError,"RuntimeAdmissionEngine"):
            assemble_original_owners(replace(self.inputs,admission_engine=object()))
        self.assertFalse(self.inputs.worker_materialization_db.exists())

    def test_canonical_sqlite_cannot_be_provider_evidence_target(self):
        with self.assertRaisesRegex(R11CurrentOwnerWiringError,"SQLite destinations"):
            assemble_original_owners(replace(
                self.inputs,provider_evidence_db=self.inputs.mission_db,
            ))
        self.assertFalse(self.inputs.worker_materialization_db.exists())

    def test_private_worker_context_cannot_alias_control_carrier(self):
        with self.assertRaisesRegex(R11CurrentOwnerWiringError,"root separation|worker private context"):
            assemble_original_owners(replace(
                self.inputs,worker_context_parent=self.inputs.carrier_root,
            ))
        self.assertFalse(self.inputs.worker_materialization_db.exists())

    def test_wrong_currentness_trust_cannot_be_used(self):
        class Mismatch:
            source_id="wrong"
        with self.assertRaisesRegex(R11CurrentOwnerWiringError,"source currentness/trust mismatch"):
            assemble_original_owners(replace(
                self.inputs,currentness_source=Mismatch(),
            ))
        self.assertFalse(self.inputs.worker_materialization_db.exists())


if __name__=="__main__":
    unittest.main()
