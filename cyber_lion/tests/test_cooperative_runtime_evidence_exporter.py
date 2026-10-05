from __future__ import annotations

from dataclasses import replace
from hashlib import sha256
import sqlite3
from pathlib import Path
import unittest

from cyber_lion.tests import test_cooperative_context_resolver as resolver_fixtures
from cyber_lion.tests import test_runtime_execution as rt
from cyber_lion.tests import test_runtime_currentness as rc
from cyber_lion.enterprise.cooperative_context_resolver import CooperativeContextPin
from cyber_lion.enterprise.cooperative_runtime_evidence_exporter import (
    MAX_TTL_SECONDS,
    CooperativeRuntimeEvidenceExportError,
    CooperativeRuntimeEvidenceExporter,
)
from cyber_lion.enterprise.cooperative_runtime_evidence_sources import (
    SQLiteCooperativeRuntimeEvidencePublisher,
    SQLiteContextPinSource,
    SQLiteEffectTimeCurrentnessSource,
    SQLiteEvidenceRuntimeAdmissionSource,
    SQLiteFleetDispatchSource,
    SQLiteProvisioningBindingSource,
    SQLiteRuntimeIdentitySource,
    SQLiteTransferBindingSource,
)


class CooperativeRuntimeEvidenceExporterTests(unittest.TestCase):
    def setUp(self):
        self.fixture = resolver_fixtures.CooperativeContextResolverTests(
            'test_reads_current_exact_context_without_changing_database'
        )
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.f = self.fixture.f
        self.base = Path(self.f.temp.name).resolve()
        self.provider_db = self.base / 'provider-evidence.sqlite'
        self.publisher = SQLiteCooperativeRuntimeEvidencePublisher(self.provider_db)

    def transfer_binding(self, assignment_id, purpose):
        self.assertEqual(purpose, 'CONTEXT')
        return {
            'repository': 'DonkeyJJLove/ai_platform',
            'source_head': 'a' * 40,
            'mission_id': 'M1',
            'assignment_id': assignment_id,
            'conversation_id': 'conversation-export-fixture',
            'binding_epoch': 1,
            'generation': 1,
            'lease_generation': 1,
            'context_digest': sha256(b'export-context').hexdigest(),
            'projection_digest': sha256(b'export-projection').hexdigest(),
            'request_id': 'request-export-context',
            'producer_ref': 'MISSION_CONTROL',
        }

    def make_exporter(self, **changes):
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
            context_pin_source=lambda aid: self.fixture.pin,
            transfer_binding_source=self.transfer_binding,
            now_fn=lambda: self.f.now,
        )
        args.update(changes)
        return CooperativeRuntimeEvidenceExporter(**args)

    def counts(self):
        tables = (
            'runtime_admission_evidence', 'context_pin_evidence', 'dispatch_evidence',
            'provisioning_evidence', 'runtime_identity_evidence',
            'currentness_evidence', 'transfer_binding_evidence',
        )
        with sqlite3.connect(self.provider_db) as db:
            return {table: db.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0] for table in tables}

    def test_exports_only_after_complete_independent_observation_and_readback_matches(self):
        exporter = self.make_exporter()
        receipt = exporter.export_write_assignment(self.fixture.aid, ttl_seconds=10)
        self.assertEqual(receipt.assignment_id, self.fixture.aid)
        self.assertEqual(receipt.mission_id, 'M1')
        self.assertEqual(receipt.worker_id, 'MD001')
        self.assertEqual(receipt.authority_effect, 'NONE')
        self.assertFalse(receipt.execution_performed)
        self.assertTrue(all(value == 1 for value in self.counts().values()))

        clock = lambda: self.f.now
        admission = SQLiteEvidenceRuntimeAdmissionSource(
            self.provider_db, rt.trust(), now_fn=clock,
        ).resolve(self.f.binding.admission.admission_digest)
        self.assertEqual(admission, self.f.binding.admission)
        self.assertEqual(
            SQLiteContextPinSource(self.provider_db, now_fn=clock)(self.fixture.aid),
            self.fixture.pin,
        )
        self.assertEqual(
            SQLiteFleetDispatchSource(self.provider_db, now_fn=clock).current_dispatch('M1'),
            self.f.fd,
        )
        self.assertEqual(
            SQLiteProvisioningBindingSource(self.provider_db, now_fn=clock)(self.fixture.aid),
            self.f.pb,
        )
        self.assertEqual(
            SQLiteRuntimeIdentitySource(self.provider_db, now_fn=clock)(
                self.f.binding.identity.runtime_instance_id
            ),
            self.f.binding.identity,
        )
        current = SQLiteEffectTimeCurrentnessSource(
            self.provider_db, rc.trust(), now_fn=clock,
        )
        self.assertEqual(
            current.resolve_authority(self.f.binding.admission.admission_digest),
            self.f.authority,
        )
        self.assertEqual(
            current.current_policy_binding(self.f.binding.admission.policy_binding),
            self.f.binding.admission.policy_binding,
        )
        self.assertEqual(
            current.current_observability_state(
                self.f.binding.admission.runtime_identity_digest,
                self.f.binding.admission.requested_effect_digest,
            ),
            self.f.binding.admission.observability_state,
        )
        transfer = SQLiteTransferBindingSource(
            self.provider_db, now_fn=clock,
        )(self.fixture.aid, 'CONTEXT')
        self.assertEqual(transfer['assignment_id'], self.fixture.aid)

    def test_stale_admission_fails_before_first_provider_write(self):
        self.f.source.current = False
        with self.assertRaisesRegex(CooperativeRuntimeEvidenceExportError, 'stale'):
            self.make_exporter().export_write_assignment(self.fixture.aid)
        self.assertTrue(all(value == 0 for value in self.counts().values()))

    def test_dispatch_substitution_fails_before_first_provider_write(self):
        wrong = replace(self.f.fd, fencing_token='f' * 64)
        self.f.dispatch_source.current = wrong
        with self.assertRaisesRegex(CooperativeRuntimeEvidenceExportError, 'dispatch'):
            self.make_exporter().export_write_assignment(self.fixture.aid)
        self.assertTrue(all(value == 0 for value in self.counts().values()))

    def test_provisioning_substitution_fails_before_first_provider_write(self):
        wrong = replace(self.f.pb, runtime_instance_id='runtime:other')
        with self.assertRaisesRegex(CooperativeRuntimeEvidenceExportError, 'provisioning'):
            self.make_exporter(
                provisioning_binding_source=lambda aid: wrong
            ).export_write_assignment(self.fixture.aid)
        self.assertTrue(all(value == 0 for value in self.counts().values()))

    def test_currentness_change_fails_before_first_provider_write(self):
        self.f.currentness.policy = 'policy@2:sha256:' + ('b' * 64)
        with self.assertRaisesRegex(CooperativeRuntimeEvidenceExportError, 'policy currentness'):
            self.make_exporter().export_write_assignment(self.fixture.aid)
        self.assertTrue(all(value == 0 for value in self.counts().values()))

    def test_context_pin_assignment_substitution_is_denied(self):
        wrong = CooperativeContextPin(
            'assignment-other', self.fixture.pin.filename, self.fixture.pin.sha256
        ).validate()
        with self.assertRaisesRegex(CooperativeRuntimeEvidenceExportError, 'context pin'):
            self.make_exporter(
                context_pin_source=lambda aid: wrong
            ).export_write_assignment(self.fixture.aid)
        self.assertTrue(all(value == 0 for value in self.counts().values()))

    def test_transfer_binding_substitution_is_denied(self):
        def wrong(aid, purpose):
            value = dict(self.transfer_binding(aid, purpose))
            value['assignment_id'] = 'assignment-other'
            return value
        with self.assertRaisesRegex(CooperativeRuntimeEvidenceExportError, 'transfer binding'):
            self.make_exporter(
                transfer_binding_source=wrong
            ).export_write_assignment(self.fixture.aid)
        self.assertTrue(all(value == 0 for value in self.counts().values()))

    def test_source_identity_drift_is_denied_before_export(self):
        exporter = self.make_exporter()
        self.f.source.source_instance_id = 'other-admission-source'
        with self.assertRaisesRegex(CooperativeRuntimeEvidenceExportError, 'admission source substitution'):
            exporter.export_write_assignment(self.fixture.aid)
        self.assertTrue(all(value == 0 for value in self.counts().values()))

    def test_ttl_is_bounded(self):
        exporter = self.make_exporter()
        with self.assertRaisesRegex(CooperativeRuntimeEvidenceExportError, 'TTL'):
            exporter.export_write_assignment(
                self.fixture.aid, ttl_seconds=MAX_TTL_SECONDS + 1,
            )
        self.assertTrue(all(value == 0 for value in self.counts().values()))


if __name__ == '__main__':
    unittest.main()
