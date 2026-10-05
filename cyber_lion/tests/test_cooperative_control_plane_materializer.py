from __future__ import annotations

from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from cyber_lion.tests import test_cooperative_context_resolver as resolver_fixtures
from cyber_lion.tests import test_runtime_execution as rt
from cyber_lion.tests import test_runtime_currentness as rc
from cyber_lion.enterprise.cooperative_control_plane_materializer import (
    CooperativeControlPlaneMaterializer,
    CooperativeControlPlaneMaterializerError,
)
from cyber_lion.enterprise.cooperative_runtime_evidence_exporter import (
    CooperativeRuntimeEvidenceExporter,
)
from cyber_lion.enterprise.cooperative_runtime_evidence_sources import (
    SQLiteCooperativeRuntimeEvidencePublisher,
    SQLiteContextPinSource,
)
from cyber_lion.mission_control import cooperative_production as cp
from cyber_lion.mission_control import global_scheduler
from tools.lion_cooperative_worker_adapter import assignment_input


class CooperativeControlPlaneMaterializerTests(unittest.TestCase):
    def setUp(self):
        self.fixture = resolver_fixtures.CooperativeContextResolverTests(
            'test_reads_current_exact_context_without_changing_database'
        )
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.f = self.fixture.f
        self.base = Path(self.f.temp.name).resolve()
        self.provider_root = self.base / 'provider-contexts'
        self.provider_root.mkdir()
        self.provider_db = self.base / 'provider-evidence.sqlite'
        self.publisher = SQLiteCooperativeRuntimeEvidencePublisher(self.provider_db)
        with sqlite3.connect(self.fixture.db) as db:
            db.row_factory = sqlite3.Row
            db.executescript(
                '''
                CREATE TABLE IF NOT EXISTS mission_assignment_release_evidence(
                  assignment_id TEXT PRIMARY KEY,
                  mission_id TEXT NOT NULL,
                  evidence_digest TEXT NOT NULL,
                  evidence_json TEXT NOT NULL,
                  released_at TEXT NOT NULL
                );
                '''
            )
            db.execute(
                "UPDATE mission_execution_assignments SET state='HELD' WHERE assignment_id=?",
                (self.fixture.aid,),
            )
            db.commit()

    def transfer_binding(self, assignment_id, purpose):
        self.assertEqual(purpose, 'CONTEXT')
        return {
            'repository': 'DonkeyJJLove/ai_platform',
            'source_head': 'a' * 40,
            'mission_id': 'M1',
            'assignment_id': assignment_id,
            'conversation_id': 'conversation-sequence-fixture',
            'binding_epoch': 1,
            'generation': 1,
            'lease_generation': 1,
            'context_digest': 'c' * 64,
            'projection_digest': 'd' * 64,
            'request_id': 'request-sequence-context',
            'producer_ref': 'MISSION_CONTROL',
        }

    def exporter(self, **changes):
        args = dict(
            publisher=self.publisher,
            context_source=lambda aid: self.f.context(aid),
            admission_source=self.f.source,
            admission_trust=rt.trust(),
            authority_admission=self.f.live_authority,
            currentness_source=self.f.currentness,
            currentness_trust=rc.trust(),
            dispatch_source=self.f.dispatch_source,
            runtime_identity_source=lambda runtime: self.f.binding.identity,
            provisioning_binding_source=lambda aid: self.f.pb,
            context_pin_source=lambda aid: (_ for _ in ()).throw(
                AssertionError('template context pin source must be replaced')
            ),
            transfer_binding_source=self.transfer_binding,
            now_fn=lambda: self.f.now,
        )
        args.update(changes)
        return CooperativeRuntimeEvidenceExporter(**args)

    def materializer(self, **changes):
        args = dict(
            mission_db=self.fixture.db,
            provider_context_root=self.provider_root,
            exporter_template=self.exporter(),
            ttl_seconds=10,
        )
        args.update(changes)
        return CooperativeControlPlaneMaterializer(**args)

    def presented(self):
        with sqlite3.connect(self.fixture.db) as db:
            db.row_factory = sqlite3.Row
            row = dict(
                db.execute(
                    "SELECT * FROM mission_execution_assignments WHERE assignment_id=?",
                    (self.fixture.aid,),
                ).fetchone()
            )
        return {'assignment': row, 'input': assignment_input(row)}

    def table_counts(self):
        names = (
            'runtime_admission_evidence', 'context_pin_evidence', 'dispatch_evidence',
            'provisioning_evidence', 'runtime_identity_evidence',
            'currentness_evidence', 'transfer_binding_evidence',
        )
        with sqlite3.connect(self.provider_db) as db:
            return {
                name: db.execute('SELECT COUNT(*) FROM ' + name).fetchone()[0]
                for name in names
            }

    def state(self):
        with sqlite3.connect(self.fixture.db) as db:
            return db.execute(
                "SELECT state FROM mission_execution_assignments WHERE assignment_id=?",
                (self.fixture.aid,),
            ).fetchone()[0]

    def test_complete_sequence_then_existing_release_fence_sets_ready(self):
        mat = self.materializer()
        conn = sqlite3.connect(self.fixture.db)
        conn.row_factory = sqlite3.Row
        try:
            result = cp._materialize_and_release(
                conn,
                self.fixture.aid,
                materializer=mat,
                expected_kind=cp.WRITE_MATERIALIZATION_KIND,
                expected_provider=cp.WRITE_PROVIDER_ID,
                now_fn=lambda: self.f.now.isoformat(),
            )
        finally:
            conn.close()
        self.assertEqual(result['authority_effect'], 'NONE')
        self.assertEqual(result['materialization_kind'], cp.WRITE_MATERIALIZATION_KIND)
        self.assertEqual(result['provider_id'], cp.WRITE_PROVIDER_ID)
        self.assertEqual(len(result['evidence_digest']), 64)
        self.assertEqual(self.state(), 'READY')
        self.assertTrue(all(value == 1 for value in self.table_counts().values()))

        carriers = list(self.provider_root.glob('context-*.json'))
        self.assertEqual(len(carriers), 1)
        pin = SQLiteContextPinSource(
            self.provider_db, now_fn=lambda: self.f.now
        )(self.fixture.aid)
        self.assertEqual(pin.filename, carriers[0].name)
        self.assertEqual(pin.sha256, __import__('hashlib').sha256(carriers[0].read_bytes()).hexdigest())

        with sqlite3.connect(self.fixture.db) as db:
            db.row_factory = sqlite3.Row
            stored = global_scheduler.held_assignment_release_evidence(
                db, self.fixture.aid
            )
        self.assertIsNotNone(stored)
        self.assertEqual(stored['evidence']['provider_id'], cp.WRITE_PROVIDER_ID)
        self.assertEqual(stored['evidence']['authority_effect'], 'NONE')

    def test_stale_admission_leaves_assignment_held_and_no_final_carrier(self):
        self.f.source.current = False
        conn = sqlite3.connect(self.fixture.db)
        conn.row_factory = sqlite3.Row
        try:
            with self.assertRaisesRegex(Exception, 'stale'):
                cp._materialize_and_release(
                    conn,
                    self.fixture.aid,
                    materializer=self.materializer(),
                    expected_kind=cp.WRITE_MATERIALIZATION_KIND,
                    expected_provider=cp.WRITE_PROVIDER_ID,
                    now_fn=lambda: self.f.now.isoformat(),
                )
        finally:
            conn.close()
        self.assertEqual(self.state(), 'HELD')
        self.assertEqual(list(self.provider_root.iterdir()), [])
        self.assertTrue(all(value == 0 for value in self.table_counts().values()))

    def test_presented_assignment_substitution_fails_before_provider_write(self):
        presented = self.presented()
        presented['assignment']['material_drone_id'] = 'MD002'
        with self.assertRaisesRegex(CooperativeControlPlaneMaterializerError, 'substitution'):
            self.materializer()(presented)
        self.assertEqual(self.state(), 'HELD')
        self.assertEqual(list(self.provider_root.iterdir()), [])
        self.assertTrue(all(value == 0 for value in self.table_counts().values()))

    def test_export_failure_removes_pending_carrier_and_keeps_held(self):
        mat = self.materializer()
        with patch(
            'cyber_lion.enterprise.cooperative_control_plane_materializer.'
            'CooperativeRuntimeEvidenceExporter.export_write_assignment',
            side_effect=RuntimeError('publisher-failed'),
        ):
            with self.assertRaisesRegex(RuntimeError, 'publisher-failed'):
                mat(self.presented())
        self.assertEqual(self.state(), 'HELD')
        self.assertEqual(list(self.provider_root.iterdir()), [])

    def test_existing_final_carrier_fails_closed_before_export(self):
        mat = self.materializer()
        filename = mat._filename(self.fixture.aid)
        (self.provider_root / filename).write_bytes(b'foreign')
        with self.assertRaisesRegex(CooperativeControlPlaneMaterializerError, 'already exists'):
            mat(self.presented())
        self.assertEqual(self.state(), 'HELD')
        self.assertTrue(all(value == 0 for value in self.table_counts().values()))

    def test_mission_db_replacement_fails_closed(self):
        mat = self.materializer()
        replacement = self.base / 'mission-replacement.sqlite'
        replacement.write_bytes(Path(self.fixture.db).read_bytes())
        Path(self.fixture.db).unlink()
        replacement.replace(self.fixture.db)
        with self.assertRaisesRegex(CooperativeControlPlaneMaterializerError, 'identity drift'):
            mat(self.presented())
        self.assertTrue(all(value == 0 for value in self.table_counts().values()))

    def test_operator_pause_blocks_before_provider_write(self):
        with sqlite3.connect(self.fixture.db) as db:
            db.execute(
                "UPDATE mission_operator_control SET pause_latch=1 WHERE mission_id='M1'"
            )
            db.commit()
        with self.assertRaisesRegex(CooperativeControlPlaneMaterializerError, 'operator control fence'):
            self.materializer()(self.presented())
        self.assertEqual(self.state(), 'HELD')
        self.assertEqual(list(self.provider_root.iterdir()), [])
        self.assertTrue(all(value == 0 for value in self.table_counts().values()))

    def test_lpcl_byte_drift_blocks_before_provider_write(self):
        with sqlite3.connect(self.fixture.db) as db:
            db.execute(
                "UPDATE mission_process_specs SET lpcl_text=lpcl_text || ' drift' WHERE mission_id='M1'"
            )
            db.commit()
        with self.assertRaisesRegex(CooperativeControlPlaneMaterializerError, 'LPCL byte binding mismatch'):
            self.materializer()(self.presented())
        self.assertEqual(self.state(), 'HELD')
        self.assertEqual(list(self.provider_root.iterdir()), [])
        self.assertTrue(all(value == 0 for value in self.table_counts().values()))

    def test_context_root_replacement_fails_closed(self):
        mat = self.materializer()
        old = self.base / 'old-context-root'
        self.provider_root.rename(old)
        self.provider_root.mkdir()
        with self.assertRaisesRegex(CooperativeControlPlaneMaterializerError, 'identity drift'):
            mat(self.presented())
        self.assertTrue(all(value == 0 for value in self.table_counts().values()))


if __name__ == '__main__':
    unittest.main()
