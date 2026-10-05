from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import tempfile
import unittest

from cyber_lion.tests import test_cooperative_context_resolver as resolver_fixtures
from cyber_lion.tests import test_runtime_execution as rt
from cyber_lion.tests import test_runtime_currentness as rc
from cyber_lion.enterprise.cooperative_provider_materialization import (
    CooperativeProviderMaterializationError,
    build_runtime_writer_provider,
    materialize_context_reference,
    materialize_verifier_view,
    provider_status_marker,
)
from cyber_lion.mission_control.cooperative_artifacts import verify_text


class CooperativeProviderMaterializationTests(unittest.TestCase):
    def setUp(self):
        self.fixture = resolver_fixtures.CooperativeContextResolverTests(
            'test_reads_current_exact_context_without_changing_database'
        )
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.base = Path(self.fixture.f.temp.name)
        self.context_parent = self.base / 'context-carriers'
        self.verifier_parent = self.base / 'verifier-carriers'
        self.context_parent.mkdir()
        self.verifier_parent.mkdir()

    def binding(self, *, assignment_id=None, producer_ref='MISSION_CONTROL'):
        return {
            'repository': 'DonkeyJJLove/ai_platform',
            'source_head': 'a' * 40,
            'mission_id': 'M1',
            'assignment_id': assignment_id or self.fixture.aid,
            'conversation_id': 'conversation-fixture-1',
            'binding_epoch': 1,
            'generation': 1,
            'lease_generation': 1,
            'context_digest': sha256(b'context-fixture').hexdigest(),
            'projection_digest': sha256(b'projection-fixture').hexdigest(),
            'request_id': 'request-fixture-1',
            'producer_ref': producer_ref,
        }

    def context_materialization(self):
        return materialize_context_reference(
            context=self.fixture.f.context(self.fixture.aid),
            coordinates=self.fixture.record['coordinates'],
            expected_binding=self.binding(),
            private_parent=self.context_parent,
        )

    def build_provider(self, materialized):
        f = self.fixture.f
        resolver, provider = build_runtime_writer_provider(
            materialization=materialized,
            mission_db=self.fixture.db,
            admission_source=f.source,
            admission_trust=rt.trust(),
            authority_admission=f.live_authority,
            currentness_source=f.currentness,
            currentness_trust=rc.trust(),
            dispatch_source=f.dispatch_source,
            runtime_identity_source=lambda runtime: f.binding.identity,
            admission_guard=f.admission_guard,
            sandbox_guard=f.sandbox_guard,
            budget_source=lambda policy: f.budget,
            now_fn=lambda: f.now,
        )
        return resolver, provider

    def test_context_bundle_to_pinned_resolver_to_runtime_write_to_bounded_verifier(self):
        materialized = self.context_materialization()
        raw = json.loads((materialized.workspace / 'context.json').read_text(encoding='utf-8'))
        self.assertNotIn('admission', raw['execution'])
        self.assertEqual(
            raw['execution']['admission_digest'],
            self.fixture.f.binding.admission.admission_digest,
        )
        resolver, provider = self.build_provider(materialized)
        self.assertEqual(resolver(self.fixture.aid), self.fixture.f.context(self.fixture.aid))

        result = provider(
            claimed=self.fixture.f.claim,
            payload=self.fixture.f.payload,
            artifact_root=self.fixture.f.root,
            worker_id='MD001',
        )
        self.assertTrue(result['readback_match'])
        self.assertEqual(result['artifact_sha256'], sha256(self.fixture.f.data).hexdigest())

        verify_payload = {
            'kind': 'COOPERATIVE_ARTIFACT_VERIFY',
            'mission_id': 'M1',
            'source_assignment_id': self.fixture.aid,
            'generation': 1,
            'artifact_name': 'product.txt',
            'expected_sha256': sha256(self.fixture.f.data).hexdigest(),
            'expected_producer_worker_id': 'MD001',
        }
        view = materialize_verifier_view(
            artifact_root=self.fixture.f.root,
            verify_payload=verify_payload,
            expected_binding=self.binding(producer_ref='MD001'),
            private_parent=self.verifier_parent,
        )
        verified = verify_text(view.workspace, verify_payload, worker_id='MD002')
        self.assertTrue(verified['digest_match'])
        self.assertEqual(verified['artifact_sha256'], result['artifact_sha256'])
        self.assertNotEqual(materialized.workspace, view.workspace)

    def test_context_transfer_binding_is_independent_and_exact(self):
        before = list(self.context_parent.iterdir())
        bad = self.binding(assignment_id='another-assignment')
        with self.assertRaisesRegex(CooperativeProviderMaterializationError, 'assignment'):
            materialize_context_reference(
                context=self.fixture.f.context(self.fixture.aid),
                coordinates=self.fixture.record['coordinates'],
                expected_binding=bad,
                private_parent=self.context_parent,
            )
        self.assertEqual(list(self.context_parent.iterdir()), before)

    def test_tampered_private_context_is_rejected_before_provider_build(self):
        materialized = self.context_materialization()
        target = materialized.workspace / 'context.json'
        target.write_bytes(target.read_bytes() + b'\n')
        with self.assertRaises((ValueError, OSError)):
            self.build_provider(materialized)
        self.assertEqual(list(self.fixture.f.root.iterdir()), [])

    def test_verifier_transport_rejects_builder_byte_drift(self):
        materialized = self.context_materialization()
        _, provider = self.build_provider(materialized)
        provider(
            claimed=self.fixture.f.claim,
            payload=self.fixture.f.payload,
            artifact_root=self.fixture.f.root,
            worker_id='MD001',
        )
        target = self.fixture.f.root / self.fixture.f.resource
        target.write_bytes(b'changed bytes\n')
        verify_payload = {
            'kind': 'COOPERATIVE_ARTIFACT_VERIFY',
            'mission_id': 'M1',
            'source_assignment_id': self.fixture.aid,
            'generation': 1,
            'artifact_name': 'product.txt',
            'expected_sha256': sha256(self.fixture.f.data).hexdigest(),
            'expected_producer_worker_id': 'MD001',
        }
        with self.assertRaisesRegex(CooperativeProviderMaterializationError, 'digest mismatch'):
            materialize_verifier_view(
                artifact_root=self.fixture.f.root,
                verify_payload=verify_payload,
                expected_binding=self.binding(producer_ref='MD001'),
                private_parent=self.verifier_parent,
            )
        self.assertEqual(list(self.verifier_parent.iterdir()), [])

    def test_provider_marker_is_exact_and_non_authorizing(self):
        self.assertEqual(provider_status_marker(), {
            'state': 'READY',
            'provider_id': 'COOPERATIVE_RUNTIME_WRITER_R5',
            'context_resolver': 'PINNED_COOPERATIVE_CONTEXT_RESOLVER',
            'execution_engine': 'RUNTIME_EXECUTION_ENGINE',
            'authority_effect': 'NONE',
        })

    def test_provider_build_rejects_noncanonical_authority_revalidator(self):
        materialized = self.context_materialization()
        f = self.fixture.f
        with self.assertRaisesRegex(CooperativeProviderMaterializationError, 'LiveAuthorityAdmission'):
            build_runtime_writer_provider(
                materialization=materialized,
                mission_db=self.fixture.db,
                admission_source=f.source,
                admission_trust=rt.trust(),
                authority_admission=object(),
                currentness_source=f.currentness,
                currentness_trust=rc.trust(),
                dispatch_source=f.dispatch_source,
                runtime_identity_source=lambda runtime: f.binding.identity,
                admission_guard=f.admission_guard,
                sandbox_guard=f.sandbox_guard,
                budget_source=lambda policy: f.budget,
                now_fn=lambda: f.now,
            )


if __name__ == '__main__':
    unittest.main()
