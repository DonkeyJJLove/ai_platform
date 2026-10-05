from __future__ import annotations

from dataclasses import replace
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
import unittest

from cyber_lion.tests import test_cooperative_context_resolver as resolver_fixtures
from cyber_lion.tests import test_runtime_execution as rt
from cyber_lion.tests import test_runtime_currentness as rc
from cyber_lion.contracts.runtime_execution import RuntimeAdmissionSourceTrustBinding
from cyber_lion.enterprise.cooperative_runtime_root import (
    CooperativeRuntimeCompositionRoot,
    CooperativeRuntimeRootError,
    SQLiteCooperativeMaterializationStore,
)
from cyber_lion.mission_control.cooperative_artifacts import VERIFY_KIND, verify_text
from tools.lion_cooperative_worker_adapter import assignment_input


class CooperativeRuntimeRootTests(unittest.TestCase):
    def setUp(self):
        self.fixture = resolver_fixtures.CooperativeContextResolverTests(
            'test_reads_current_exact_context_without_changing_database'
        )
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.f = self.fixture.f
        self.base = Path(self.f.temp.name).resolve()
        self.context_parent = self.base / 'root-context'
        self.verifier_parent = self.base / 'root-verifier'
        self.context_parent.mkdir()
        self.verifier_parent.mkdir()
        self.material_db = self.base / 'materialization.sqlite'
        self.runtime_db = self.base / 'runtime-state.sqlite'
        self.durable_trust = RuntimeAdmissionSourceTrustBinding(
            'cooperative-runtime-admission',
            'cooperative-runtime-admission:fixture',
            rt.Z,
            'cooperative-runtime-root',
            rt.F,
        ).validate()
        self.sql(
            "UPDATE mission_execution_assignments SET state='HELD' WHERE assignment_id=?",
            (self.fixture.aid,),
        )
        self.root = self.make_root()

    def sql(self, text, args=()):
        with sqlite3.connect(self.fixture.db) as db:
            db.execute(text, args)
            db.commit()

    def transfer_binding(self, assignment_id, purpose):
        return {
            'repository': 'DonkeyJJLove/ai_platform',
            'source_head': 'a' * 40,
            'mission_id': 'M1',
            'assignment_id': assignment_id,
            'conversation_id': 'conversation-root-fixture',
            'binding_epoch': 1,
            'generation': 1,
            'lease_generation': 1,
            'context_digest': sha256(b'root-context').hexdigest(),
            'projection_digest': sha256(b'root-projection').hexdigest(),
            'request_id': 'request-root-' + purpose.lower(),
            'producer_ref': 'MISSION_CONTROL' if purpose == 'CONTEXT' else 'MD001',
        }

    def make_root(self, **changes):
        args = dict(
            mission_db=self.fixture.db,
            artifact_root=self.f.root,
            context_parent=self.context_parent,
            verifier_parent=self.verifier_parent,
            materialization_db=self.material_db,
            runtime_state_db=self.runtime_db,
            context_source=lambda aid: self.f.context(aid),
            upstream_admission_source=self.f.source,
            upstream_admission_trust=rt.trust(),
            durable_admission_trust=self.durable_trust,
            authority_admission=self.f.live_authority,
            currentness_source=self.f.currentness,
            currentness_trust=rc.trust(),
            dispatch_source=self.f.dispatch_source,
            runtime_identity_source=lambda runtime: self.f.binding.identity,
            provisioning_binding_source=lambda aid: self.f.pb,
            transfer_binding_source=self.transfer_binding,
            now_fn=lambda: self.f.now,
        )
        args.update(changes)
        return CooperativeRuntimeCompositionRoot(**args)

    def presented(self, aid):
        with sqlite3.connect(self.fixture.db) as db:
            db.row_factory = sqlite3.Row
            row = dict(db.execute(
                'SELECT * FROM mission_execution_assignments WHERE assignment_id=?',
                (aid,),
            ).fetchone())
        return {'assignment': row, 'input': assignment_input(row)}

    def claim_builder(self):
        self.sql(
            "UPDATE mission_execution_assignments SET state='CLAIMED' WHERE assignment_id=?",
            (self.fixture.aid,),
        )
        return self.presented(self.fixture.aid)['assignment']

    def test_materializer_copies_existing_admission_and_builds_writer_after_claim(self):
        provider = self.root.materialization_provider()
        out = provider.write_materializer(self.presented(self.fixture.aid))
        self.assertEqual(out['materialization_kind'], 'RUNTIME_CONTEXT')
        self.assertEqual(out['provider_id'], 'COOPERATIVE_RUNTIME_WRITER_R5')
        self.assertEqual(out['authority_effect'], 'NONE')
        self.assertEqual(len(out['evidence_digest']), 64)
        with sqlite3.connect(self.fixture.db) as db:
            self.assertEqual(
                db.execute(
                    'SELECT state FROM mission_execution_assignments WHERE assignment_id=?',
                    (self.fixture.aid,),
                ).fetchone()[0],
                'HELD',
            )
        materialized, worker, admission = self.root.store.resolve_context(self.fixture.aid)
        self.assertEqual(worker, 'MD001')
        self.assertEqual(admission, self.f.binding.admission.admission_digest)
        self.assertTrue(self.root.admission_source.is_current(admission))
        self.assertNotIn(
            'admission',
            json.loads((materialized.workspace / 'context.json').read_text(encoding='utf-8'))['execution'],
        )

        claimed = self.claim_builder()
        writer = self.root.writer_for_assignment(self.fixture.aid)
        result = writer(
            claimed=claimed,
            payload=self.f.payload,
            artifact_root=self.f.root,
            worker_id='MD001',
        )
        self.assertTrue(result['readback_match'])
        self.assertEqual((self.f.root / self.f.resource).read_bytes(), self.f.data)

    def test_reconstructed_root_uses_durable_context_admission_consumption_and_budget(self):
        self.root.write_materializer(self.presented(self.fixture.aid))
        claimed = self.claim_builder()
        restarted = self.make_root()
        result = restarted.writer_for_assignment(self.fixture.aid)(
            claimed=claimed,
            payload=self.f.payload,
            artifact_root=self.f.root,
            worker_id='MD001',
        )
        self.assertTrue(result['readback_match'])
        restarted_again = self.make_root()
        with self.assertRaisesRegex(Exception, 'replay'):
            restarted_again.writer_for_assignment(self.fixture.aid)(
                claimed=claimed,
                payload=self.f.payload,
                artifact_root=self.f.root,
                worker_id='MD001',
            )

    def test_upstream_admission_stale_after_materialization_blocks_worker_effect(self):
        self.root.write_materializer(self.presented(self.fixture.aid))
        claimed = self.claim_builder()
        self.f.source.current = False
        with self.assertRaisesRegex(CooperativeRuntimeRootError, 'stale before worker effect'):
            self.root.writer_for_assignment(self.fixture.aid)(
                claimed=claimed,
                payload=self.f.payload,
                artifact_root=self.f.root,
                worker_id='MD001',
            )
        self.assertEqual(list(self.f.root.iterdir()), [])

    def test_stale_upstream_admission_blocks_materialization_before_context_record(self):
        self.f.source.current = False
        with self.assertRaisesRegex(CooperativeRuntimeRootError, 'stale'):
            self.root.write_materializer(self.presented(self.fixture.aid))
        with sqlite3.connect(self.material_db) as db:
            self.assertEqual(
                db.execute('SELECT COUNT(*) FROM cooperative_context_materialization').fetchone()[0],
                0,
            )
        with sqlite3.connect(self.runtime_db) as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM runtime_admissions').fetchone()[0], 0)

    def test_provisioning_substitution_blocks_materialization(self):
        wrong = replace(self.f.pb, runtime_instance_id='runtime:other')
        root = self.make_root(provisioning_binding_source=lambda aid: wrong)
        with self.assertRaisesRegex(CooperativeRuntimeRootError, 'provisioning'):
            root.write_materializer(self.presented(self.fixture.aid))
        with sqlite3.connect(self.material_db) as db:
            self.assertEqual(
                db.execute('SELECT COUNT(*) FROM cooperative_context_materialization').fetchone()[0],
                0,
            )

    def test_currentness_source_substitution_blocks_root_construction(self):
        self.f.currentness.source_instance_id = 'other-currentness'
        with self.assertRaisesRegex(CooperativeRuntimeRootError, 'currentness source substitution'):
            self.make_root()

    def test_context_materialization_descriptor_survives_store_reconstruction(self):
        self.root.write_materializer(self.presented(self.fixture.aid))
        second = SQLiteCooperativeMaterializationStore(
            self.material_db,
            context_parent=self.context_parent,
            verifier_parent=self.verifier_parent,
        )
        materialized, worker, admission = second.resolve_context(self.fixture.aid)
        self.assertEqual(materialized.assignment_id, self.fixture.aid)
        self.assertEqual(worker, 'MD001')
        self.assertEqual(admission, self.f.binding.admission.admission_digest)

    def test_materialization_store_database_replacement_is_denied(self):
        self.root.write_materializer(self.presented(self.fixture.aid))
        replacement = self.base / 'replacement-materialization.sqlite'
        replacement.write_bytes(self.material_db.read_bytes())
        self.material_db.unlink()
        replacement.replace(self.material_db)
        with self.assertRaisesRegex(CooperativeRuntimeRootError, 'identity drift'):
            self.root.store.resolve_context(self.fixture.aid)

    def test_verifier_transfer_is_bound_to_distinct_verify_assignment_and_worker(self):
        self.root.write_materializer(self.presented(self.fixture.aid))
        claimed = self.claim_builder()
        self.root.writer_for_assignment(self.fixture.aid)(
            claimed=claimed,
            payload=self.f.payload,
            artifact_root=self.f.root,
            worker_id='MD001',
        )
        verify_aid = 'verify-assignment-root-1'
        verify_input = {
            'kind': VERIFY_KIND,
            'mission_id': 'M1',
            'source_assignment_id': self.fixture.aid,
            'generation': 1,
            'artifact_name': 'product.txt',
            'expected_sha256': sha256(self.f.data).hexdigest(),
            'expected_producer_worker_id': 'MD001',
            'capability': 'COOPERATIVE_ARTIFACT_VERIFY',
        }
        raw = json.dumps(
            verify_input, sort_keys=True, separators=(',', ':'), ensure_ascii=False
        )
        with sqlite3.connect(self.fixture.db) as db:
            db.execute(
                """INSERT INTO mission_execution_assignments(
                   assignment_id,mission_id,material_drone_id,logical_drone_id,phase_id,
                   lease_generation,state,lease_expires_at,input_json,input_digest,
                   control_epoch,context_revision,plan_revision,dispatch_authority
                   ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    verify_aid, 'M1', 'MD002', 'drone:2', 'VERIFY__COOP_VERIFY',
                    1, 'HELD', '2026-10-05T00:00:00Z', raw,
                    sha256(raw.encode('utf-8')).hexdigest(), 1, 0, 0, 'AUTONOMOUS',
                ),
            )
            db.commit()
        out = self.root.verify_materializer(self.presented(verify_aid))
        self.assertEqual(out['provider_id'], 'COOPERATIVE_ARTIFACT_TRANSFER_R1')
        materialized, worker = self.root.store.resolve_verifier(verify_aid)
        self.assertEqual(materialized.consumer_assignment_id, verify_aid)
        self.assertEqual(materialized.source_assignment_id, self.fixture.aid)
        self.assertEqual(worker, 'MD002')
        checked = verify_text(materialized.workspace, verify_input, worker_id='MD002')
        self.assertTrue(checked['digest_match'])
        self.assertEqual(self.root.verifier_workspace(verify_aid), materialized.workspace)

    def test_runtime_state_database_replacement_blocks_readiness(self):
        replacement = self.base / 'replacement-runtime-state.sqlite'
        replacement.write_bytes(self.runtime_db.read_bytes())
        self.runtime_db.unlink()
        replacement.replace(self.runtime_db)
        with self.assertRaisesRegex(CooperativeRuntimeRootError, 'runtime state DB identity drift'):
            self.root.worker_status_marker()

    def test_worker_status_marker_is_readiness_not_authority(self):
        self.assertEqual(self.root.worker_status_marker(), {
            'state': 'READY',
            'provider_id': 'COOPERATIVE_RUNTIME_WRITER_R5',
            'context_resolver': 'PINNED_COOPERATIVE_CONTEXT_RESOLVER',
            'execution_engine': 'RUNTIME_EXECUTION_ENGINE',
            'authority_effect': 'NONE',
        })


if __name__ == '__main__':
    unittest.main()
