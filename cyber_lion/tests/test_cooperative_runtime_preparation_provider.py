from __future__ import annotations

from dataclasses import asdict
from datetime import timedelta
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
import unittest

from cyber_lion.enterprise.cooperative_runtime_preparation_provider import (
    JOURNAL_SCHEMA,
    PREPARED,
    PREPARING,
    PUBLISHED,
    UNKNOWN,
    CooperativeRuntimePreparationProvider,
    CooperativeRuntimePreparationProviderError,
)
from cyber_lion.enterprise.cooperative_control_plane_materializer import (
    CooperativeControlPlaneMaterializer,
)
from cyber_lion.enterprise.cooperative_runtime_evidence_exporter import (
    CooperativeRuntimeEvidenceExporter,
)
from cyber_lion.enterprise.cooperative_runtime_evidence_sources import (
    SQLiteCooperativeRuntimeEvidencePublisher,
)
from cyber_lion.enterprise.cooperative_runtime_preparer import (
    prepare_cooperative_runtime_context,
)
from cyber_lion.enterprise.runtime_execution import SQLiteRuntimeAdmissionSource
from cyber_lion.mission_control import (
    cooperative_production as cp,
    execution_driver,
    global_scheduler,
    operator_control,
)
from cyber_lion.tests import test_executor_sandbox as sb
from cyber_lion.tests import test_runtime_currentness as rc
from cyber_lion.tests import test_runtime_execution as rt
from cyber_lion.tests.test_cooperative_runtime_preparer import (
    D,
    HEAD,
    NOW,
    REPO,
    TREE,
    FakeAdmission,
    CooperativeRuntimePreparerTests,
)


class CooperativeRuntimePreparationProviderTests(unittest.TestCase):
    def setUp(self):
        self.fixture = CooperativeRuntimePreparerTests(
            "test_exact_evidence_prepares_context_without_artifact_effect"
        )
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.base = Path(self.fixture.temp.name).resolve()
        self.mission_db = self.base / "mission-provider.sqlite"
        stamp = NOW.isoformat()
        lpcl = "MISSION=M1\nPHASE=BUILD\n"
        lpcl_digest = sha256(lpcl.encode("utf-8")).hexdigest()

        with sqlite3.connect(self.mission_db) as db:
            db.row_factory = sqlite3.Row
            db.executescript(
                """
                CREATE TABLE schema_migrations(
                  version INTEGER PRIMARY KEY,
                  schema_id TEXT NOT NULL,
                  applied_at TEXT NOT NULL,
                  source_head TEXT,
                  source_tree TEXT,
                  migration_digest TEXT,
                  note TEXT
                );
                CREATE TABLE missions(
                  mission_id TEXT PRIMARY KEY,title TEXT NOT NULL,adapter TEXT NOT NULL,
                  spec_digest TEXT NOT NULL,source_head TEXT,source_tree TEXT,namespace TEXT,
                  state TEXT NOT NULL,runtime_state TEXT,logical_count INTEGER NOT NULL,
                  material_target INTEGER NOT NULL,materialized INTEGER NOT NULL DEFAULT 0,
                  ready INTEGER NOT NULL DEFAULT 0,created_at TEXT NOT NULL,authorized_at TEXT,
                  updated_at TEXT NOT NULL,last_error TEXT,spec_json TEXT NOT NULL
                );
                CREATE TABLE mission_process_specs(
                  mission_id TEXT PRIMARY KEY,title TEXT NOT NULL,objective TEXT NOT NULL,
                  description TEXT NOT NULL,lpcl_digest TEXT,lpcl_text TEXT,
                  protocols_json TEXT NOT NULL,authority_state TEXT NOT NULL,
                  current_phase TEXT,progress REAL NOT NULL DEFAULT 0,
                  created_at TEXT NOT NULL,updated_at TEXT NOT NULL
                );
                """
            )
            db.execute(
                "INSERT INTO missions VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    "M1","R621 fixture","LPCL_MISSION",lpcl_digest,HEAD,TREE,None,
                    "RUNNING","DRIVER_ACTIVE",1,1,1,1,stamp,stamp,stamp,None,"{}",
                ),
            )
            db.execute(
                "INSERT INTO mission_process_specs VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    "M1","R621 fixture","durable cooperative preparation","integration fixture",
                    lpcl_digest,lpcl,"[]","EXPLICIT_USER_ACTIVATION","BUILD",0.0,stamp,stamp,
                ),
            )
            db.commit()
            operator_control.migrate(db, lambda: stamp)
            execution_driver.migrate(
                db, lambda: stamp, source_head=HEAD, source_tree=TREE
            )
            global_scheduler.migrate(db, lambda: stamp)
            operator_control.ensure_control_state(db, "M1", lambda: stamp)
            execution_driver.ensure_driver(
                db, "M1", lambda: stamp, initial_state="ACTIVE"
            )
            db.execute(
                "UPDATE mission_execution_drivers SET current_phase='BUILD',"
                " lease_expires_at=?, heartbeat_at=?, updated_at=? WHERE mission_id='M1'",
                ((NOW + timedelta(minutes=10)).isoformat(), stamp, stamp),
            )
            original = json.loads(self.fixture.assignment["input_json"])
            self.aid = global_scheduler.create_held_assignment(
                db,
                "M1",
                "BUILD__COOP_WRITE",
                "LD001",
                "MD001",
                original,
                lambda: stamp,
                lease_generation=1,
            )

        self.runtime_state = self.base / "runtime-state.sqlite"
        self.store = SQLiteRuntimeAdmissionSource(self.runtime_state, rt.trust())

    def evidence_source(self, assignment_id):
        if assignment_id != self.aid:
            raise AssertionError("evidence assignment substitution")
        return self.fixture.evidence

    def provider(self, *, engine=None):
        return CooperativeRuntimePreparationProvider(
            mission_db=self.mission_db,
            artifact_root=self.fixture.root,
            evidence_source=self.evidence_source,
            admission_engine=engine or self.fixture.engine,
            admission_source=self.store,
            now_fn=lambda: self.fixture.NOW if hasattr(self.fixture, "NOW") else __import__(
                "cyber_lion.tests.test_cooperative_runtime_preparer",
                fromlist=["NOW"],
            ).NOW,
        )

    def journal(self):
        with sqlite3.connect(self.runtime_state) as db:
            db.row_factory = sqlite3.Row
            row = db.execute(
                "SELECT * FROM cooperative_runtime_preparations WHERE assignment_id=?",
                (self.aid,),
            ).fetchone()
        return dict(row) if row else None

    def assignment(self):
        with sqlite3.connect(self.mission_db) as db:
            db.row_factory = sqlite3.Row
            return dict(
                db.execute(
                    "SELECT * FROM mission_execution_assignments WHERE assignment_id=?",
                    (self.aid,),
                ).fetchone()
            )

    def test_exact_preparation_publishes_durable_admission_and_is_repeatable(self):
        provider = self.provider()
        context = provider(self.aid)
        self.assertEqual(provider.status(self.aid)["state"], PUBLISHED)
        self.assertEqual(
            self.store.resolve(context.execution.admission.admission_digest),
            context.execution.admission,
        )
        self.assertEqual(provider(self.aid), context)
        self.assertEqual(list(self.fixture.root.rglob("*")), [])
        self.assertEqual(provider.admission_trust().binding(), rt.trust().binding())

    def test_restart_from_published_journal_does_not_replay_admission(self):
        first = self.provider()
        context = first(self.aid)
        # Simulate crash after durable publish but before journal finalization.
        with sqlite3.connect(self.runtime_state) as db, db:
            db.execute(
                "UPDATE cooperative_runtime_preparations SET state=?,completed_at=NULL "
                "WHERE assignment_id=?",
                (PREPARED,self.aid),
            )
        second = self.provider(engine=self.fixture.engine)
        recovered = second(self.aid)
        self.assertEqual(recovered, context)
        self.assertEqual(second.status(self.aid)["state"], PUBLISHED)
        self.assertEqual(list(self.fixture.root.rglob("*")), [])

    def test_restart_from_prepared_before_publish_finishes_publication(self):
        provider = self.provider()
        assignment = self.assignment()
        context = prepare_cooperative_runtime_context(
            assignment=assignment,
            artifact_root=self.fixture.root,
            evidence=self.fixture.evidence,
            admission_engine=self.fixture.engine,
            trusted_now=__import__(
                "cyber_lion.tests.test_cooperative_runtime_preparer",
                fromlist=["NOW"],
            ).NOW,
        )
        admission = context.execution.admission
        provenance = provider._provenance(
            assignment,self.fixture.evidence,admission
        )
        raw = json.dumps(
            asdict(admission),sort_keys=True,separators=(",",":"),
            ensure_ascii=False,allow_nan=False,
        )
        with sqlite3.connect(self.runtime_state) as db, db:
            db.execute(
                "INSERT INTO cooperative_runtime_preparations VALUES(?,?,?,?,?,?,?,?,?)",
                (
                    self.aid,assignment["input_digest"],PREPARED,
                    admission.admission_digest,raw,provenance,
                    __import__(
                        "cyber_lion.tests.test_cooperative_runtime_preparer",
                        fromlist=["NOW"],
                    ).NOW.isoformat(),
                    None,JOURNAL_SCHEMA,
                ),
            )
        self.assertFalse(self.store.is_current(admission.admission_digest))
        recovered = self.provider(engine=self.fixture.engine)(self.aid)
        self.assertEqual(recovered, context)
        self.assertTrue(self.store.is_current(admission.admission_digest))
        self.assertEqual(self.journal()["state"], PUBLISHED)

    def test_preparing_without_durable_admission_is_unknown_and_not_retried(self):
        provider = self.provider()
        assignment = self.assignment()
        with sqlite3.connect(self.runtime_state) as db, db:
            db.execute(
                "INSERT INTO cooperative_runtime_preparations VALUES(?,?,?,?,?,?,?,?,?)",
                (
                    self.aid,assignment["input_digest"],PREPARING,
                    None,None,None,
                    __import__(
                        "cyber_lion.tests.test_cooperative_runtime_preparer",
                        fromlist=["NOW"],
                    ).NOW.isoformat(),
                    None,JOURNAL_SCHEMA,
                ),
            )
        with self.assertRaisesRegex(
            CooperativeRuntimePreparationProviderError, UNKNOWN
        ):
            provider(self.aid)
        self.assertEqual(self.journal()["state"], PREPARING)
        self.assertEqual(list(self.fixture.root.rglob("*")), [])
        with sqlite3.connect(self.runtime_state) as db:
            self.assertEqual(
                db.execute("SELECT COUNT(*) FROM runtime_admissions").fetchone()[0],
                0,
            )

    def test_provider_drives_existing_r616_to_ready_from_current_ledger(self):
        provider = self.provider()
        provider_root = self.base / "provider-contexts"
        provider_root.mkdir()
        provider_db = self.base / "provider-evidence.sqlite"
        publisher = SQLiteCooperativeRuntimeEvidencePublisher(provider_db)
        currentness = rc.Source(
            self.fixture.authority,
            policy=self.fixture.evidence.pdp_result.applied.policy_binding,
            obs=self.fixture.evidence.pdp_result.applied.observability_state,
        )
        dispatch = sb.DispatchSource(self.fixture.dispatch)

        def transfer_binding(aid, purpose):
            self.assertEqual(aid, self.aid)
            self.assertEqual(purpose, "CONTEXT")
            return {
                "repository": REPO,
                "source_head": HEAD,
                "mission_id": "M1",
                "assignment_id": aid,
                "conversation_id": "conversation-r621",
                "binding_epoch": 1,
                "generation": 1,
                "lease_generation": 1,
                "context_digest": D("r621-context"),
                "projection_digest": D("r621-projection"),
                "request_id": "request-r621-context",
                "producer_ref": "MISSION_CONTROL",
            }

        exporter = CooperativeRuntimeEvidenceExporter(
            publisher=publisher,
            context_source=provider,
            admission_source=self.store,
            admission_trust=provider.admission_trust(),
            authority_admission=FakeAdmission(),
            currentness_source=currentness,
            currentness_trust=rc.trust(),
            dispatch_source=dispatch,
            runtime_identity_source=lambda runtime: provider(self.aid).execution.identity,
            provisioning_binding_source=lambda aid: provider(aid).provisioning,
            context_pin_source=lambda aid: (_ for _ in ()).throw(
                AssertionError("R6.16 must replace template context pin source")
            ),
            transfer_binding_source=transfer_binding,
            now_fn=lambda: NOW,
        )
        materializer = CooperativeControlPlaneMaterializer(
            mission_db=self.mission_db,
            provider_context_root=provider_root,
            exporter_template=exporter,
            ttl_seconds=10,
        )

        with sqlite3.connect(self.mission_db) as db:
            db.row_factory = sqlite3.Row
            result = cp._materialize_and_release(
                db,
                self.aid,
                materializer=materializer,
                expected_kind=cp.WRITE_MATERIALIZATION_KIND,
                expected_provider=cp.WRITE_PROVIDER_ID,
                now_fn=lambda: NOW.isoformat(),
            )

        self.assertEqual(result["authority_effect"], "NONE")
        self.assertEqual(result["provider_id"], cp.WRITE_PROVIDER_ID)
        self.assertEqual(provider.status(self.aid)["state"], PUBLISHED)
        context = provider._cache[self.aid](self.aid)
        self.assertTrue(
            self.store.is_current(context.execution.admission.admission_digest)
        )
        self.assertEqual(list(self.fixture.root.rglob("*")), [])

        with sqlite3.connect(self.mission_db) as db:
            db.row_factory = sqlite3.Row
            row = dict(
                db.execute(
                    "SELECT * FROM mission_execution_assignments WHERE assignment_id=?",
                    (self.aid,),
                ).fetchone()
            )
            release = global_scheduler.held_assignment_release_evidence(db, self.aid)
        self.assertEqual(row["state"], "READY")
        self.assertIsNotNone(release)
        self.assertEqual(release["evidence"]["provider_id"], cp.WRITE_PROVIDER_ID)
        self.assertEqual(release["evidence"]["authority_effect"], "NONE")

        with sqlite3.connect(provider_db) as db:
            counts = {
                name: db.execute("SELECT COUNT(*) FROM " + name).fetchone()[0]
                for name in (
                    "runtime_admission_evidence",
                    "context_pin_evidence",
                    "dispatch_evidence",
                    "provisioning_evidence",
                    "runtime_identity_evidence",
                    "currentness_evidence",
                    "transfer_binding_evidence",
                )
            }
        self.assertTrue(all(value == 1 for value in counts.values()))
        self.assertEqual(len(list(provider_root.glob("context-*.json"))), 1)

    def test_assignment_no_longer_held_is_rejected_before_preparation(self):
        with sqlite3.connect(self.mission_db) as db, db:
            db.execute(
                "UPDATE mission_execution_assignments SET state='READY' WHERE assignment_id=?",
                (self.aid,),
            )
        with self.assertRaisesRegex(
            CooperativeRuntimePreparationProviderError, "not HELD"
        ):
            self.provider()(self.aid)
        self.assertEqual(list(self.fixture.root.rglob("*")), [])


if __name__ == "__main__":
    unittest.main()
