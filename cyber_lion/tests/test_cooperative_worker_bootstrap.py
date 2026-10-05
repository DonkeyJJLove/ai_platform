from __future__ import annotations

from dataclasses import replace
from hashlib import sha256
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from cyber_lion.tests import test_cooperative_context_resolver as resolver_fixtures
from cyber_lion.tests import test_runtime_execution as rt
from cyber_lion.tests import test_runtime_currentness as rc
from cyber_lion.contracts.runtime_execution import RuntimeAdmissionSourceTrustBinding
from cyber_lion.mission_control.cooperative_worker_bootstrap import (
    BOOTSTRAP_VERSION,
    TRUSTED_EXTERNAL_MODE,
    UNBOUND_MODE,
    CooperativeRuntimeBootstrapDependencies,
    CooperativeWorkerBootstrapError,
    bootstrap_process_runtime,
    build_root_from_environment,
    load_dependencies_from_environment,
    qualify_released_assignment_from_environment,
)
from cyber_lion.mission_control.cooperative_worker_runtime import (
    PROCESS_COOPERATIVE_RUNTIME,
    CooperativeWorkerRuntimeRegistry,
)


class CooperativeWorkerBootstrapTests(unittest.TestCase):
    def setUp(self):
        self.fixture = resolver_fixtures.CooperativeContextResolverTests(
            'test_reads_current_exact_context_without_changing_database'
        )
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.f = self.fixture.f
        self.base = Path(self.f.temp.name).resolve()

        self.repo_root = self.base / 'repo-root'
        self.repo_root.mkdir()

        self.private_root = self.base / 'private'
        self.private_root.mkdir()
        self.artifacts = self.private_root / 'artifacts'
        self.contexts = self.private_root / 'contexts'
        self.verifiers = self.private_root / 'verifiers'
        self.state = self.private_root / 'state'
        self.artifacts.mkdir()
        self.contexts.mkdir()
        self.verifiers.mkdir()
        self.state.mkdir()

        # Move the fixture artifact owner under the private root and rebind only
        # the synthetic fixture execution evidence used by this test.
        self.f.root.rmdir()
        self.f.root = self.artifacts
        self.f.binding = replace(self.f.binding, artifact_root=self.artifacts)

        self.durable_trust = RuntimeAdmissionSourceTrustBinding(
            'cooperative-bootstrap-admission',
            'cooperative-bootstrap-admission:fixture',
            rt.Z,
            'cooperative-bootstrap-root',
            rt.F,
        ).validate()

    def transfer_binding(self, assignment_id, purpose):
        return {
            'repository': 'DonkeyJJLove/ai_platform',
            'source_head': 'a' * 40,
            'mission_id': 'M1',
            'assignment_id': assignment_id,
            'conversation_id': 'conversation-bootstrap-fixture',
            'binding_epoch': 1,
            'generation': 1,
            'lease_generation': 1,
            'context_digest': sha256(b'bootstrap-context').hexdigest(),
            'projection_digest': sha256(b'bootstrap-projection').hexdigest(),
            'request_id': 'request-bootstrap-' + purpose.lower(),
            'producer_ref': 'MISSION_CONTROL' if purpose == 'CONTEXT' else 'MD001',
        }

    def dependencies(self):
        return CooperativeRuntimeBootstrapDependencies(
            context_source=lambda aid: self.f.context(aid),
            qualification_context_source=lambda aid: self.f.context(aid),
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
        ).validate()

    def environment(self, **changes):
        value = {
            'LION_COOPERATIVE_BOOTSTRAP_MODE': TRUSTED_EXTERNAL_MODE,
            'LION_COOPERATIVE_BOOTSTRAP_VERSION': BOOTSTRAP_VERSION,
            'LION_COOPERATIVE_REPOSITORY_ROOT': str(self.repo_root),
            'LION_COOPERATIVE_MISSION_DB_PATH': str(self.fixture.db),
            'LION_COOPERATIVE_PRIVATE_ROOT': str(self.private_root),
        }
        value.update(changes)
        return value

    def test_default_mode_is_unbound_and_does_not_install_root(self):
        registry = CooperativeWorkerRuntimeRegistry()
        out = bootstrap_process_runtime({}, registry=registry)
        self.assertEqual(out['state'], 'UNBOUND')
        self.assertEqual(out['mode'], UNBOUND_MODE)
        self.assertEqual(out['authority_effect'], 'NONE')
        self.assertIsNone(registry.current('MD001'))
        self.assertFalse((self.state / 'runtime-state.sqlite').exists())
        self.assertFalse((self.state / 'materialization.sqlite').exists())

    def test_unknown_bootstrap_mode_fails_closed(self):
        with self.assertRaisesRegex(CooperativeWorkerBootstrapError, 'unsupported'):
            bootstrap_process_runtime(
                {'LION_COOPERATIVE_BOOTSTRAP_MODE': 'AUTO_ALLOW'},
                registry=CooperativeWorkerRuntimeRegistry(),
            )

    def test_build_root_uses_preexisting_private_paths_and_does_not_issue_authority(self):
        root = build_root_from_environment(self.dependencies(), self.environment())
        self.assertEqual(root.artifact_root, self.artifacts)
        self.assertEqual(root.context_parent, self.contexts)
        self.assertEqual(root.verifier_parent, self.verifiers)
        self.assertTrue((self.state / 'runtime-state.sqlite').is_file())
        self.assertTrue((self.state / 'materialization.sqlite').is_file())
        self.assertEqual(root.worker_status_marker()['authority_effect'], 'NONE')

    def test_trusted_mode_installs_exact_root_once(self):
        registry = CooperativeWorkerRuntimeRegistry()
        deps = self.dependencies()
        with patch(
            'cyber_lion.mission_control.cooperative_worker_bootstrap.load_dependencies_from_environment',
            return_value=deps,
        ):
            out = bootstrap_process_runtime(self.environment(), registry=registry)
            self.assertEqual(out['state'], 'READY')
            self.assertEqual(out['provider']['provider_id'], 'COOPERATIVE_RUNTIME_WRITER_R5')
            self.assertEqual(out['authority_effect'], 'NONE')
            self.assertIsNotNone(registry.current('MD001'))
            with self.assertRaisesRegex(CooperativeWorkerBootstrapError, 'already installed'):
                bootstrap_process_runtime(self.environment(), registry=registry)

    def test_missing_private_subdirectory_fails_before_root_install(self):
        self.verifiers.rmdir()
        registry = CooperativeWorkerRuntimeRegistry()
        with patch(
            'cyber_lion.mission_control.cooperative_worker_bootstrap.load_dependencies_from_environment',
            return_value=self.dependencies(),
        ):
            with self.assertRaisesRegex(CooperativeWorkerBootstrapError, 'verifier'):
                bootstrap_process_runtime(self.environment(), registry=registry)
        self.assertIsNone(registry.current('MD001'))

    def test_external_dependency_module_must_be_outside_repo_and_digest_pinned(self):
        inside = self.repo_root / 'provider.py'
        inside.write_text('def build(): return object()\n', encoding='utf-8')
        env = self.environment(
            LION_COOPERATIVE_DEPENDENCY_MODULE_PATH=str(inside),
            LION_COOPERATIVE_DEPENDENCY_MODULE_SHA256=sha256(inside.read_bytes()).hexdigest(),
            LION_COOPERATIVE_DEPENDENCY_FACTORY='build',
        )
        with self.assertRaisesRegex(CooperativeWorkerBootstrapError, 'outside repository'):
            load_dependencies_from_environment(env)

        outside = self.base / 'provider.py'
        outside.write_text('def build(): return object()\n', encoding='utf-8')
        env['LION_COOPERATIVE_DEPENDENCY_MODULE_PATH'] = str(outside)
        env['LION_COOPERATIVE_DEPENDENCY_MODULE_SHA256'] = '0' * 64
        with self.assertRaisesRegex(CooperativeWorkerBootstrapError, 'digest mismatch'):
            load_dependencies_from_environment(env)

    def test_external_factory_wrong_type_is_rejected(self):
        outside = self.base / 'provider.py'
        outside.write_text('def build(): return object()\n', encoding='utf-8')
        env = self.environment(
            LION_COOPERATIVE_DEPENDENCY_MODULE_PATH=str(outside),
            LION_COOPERATIVE_DEPENDENCY_MODULE_SHA256=sha256(outside.read_bytes()).hexdigest(),
            LION_COOPERATIVE_DEPENDENCY_FACTORY='build',
        )
        with self.assertRaisesRegex(CooperativeWorkerBootstrapError, 'wrong type'):
            load_dependencies_from_environment(env)

    def test_qualification_entrypoint_requires_unbound_exact_worker_and_does_not_install_runtime(self):
        env = self.environment(
            LION_COOPERATIVE_BOOTSTRAP_MODE=UNBOUND_MODE,
            LION_MATERIAL_WORKER_ID='MD001',
        )
        expected = {
            'schema': 'lion.cooperative-worker-qualification/v1',
            'assignment_id': 'assignment-fixture-1',
            'worker_id': 'MD001',
            'execution_performed': False,
            'authority_effect': 'NONE',
        }

        class Root:
            def qualify_released_write_assignment(self, assignment_id, *, material_worker_id):
                self_args = (assignment_id, material_worker_id)
                if self_args != ('assignment-fixture-1', 'MD001'):
                    raise AssertionError(self_args)
                return dict(expected)

        before = PROCESS_COOPERATIVE_RUNTIME.current('MD001')
        with patch(
            'cyber_lion.mission_control.cooperative_worker_bootstrap.load_dependencies_from_environment',
            return_value=self.dependencies(),
        ), patch(
            'cyber_lion.mission_control.cooperative_worker_bootstrap.build_root_from_environment',
            return_value=Root(),
        ):
            out = qualify_released_assignment_from_environment(
                env,
                assignment_id='assignment-fixture-1',
                material_worker_id='MD001',
            )
        self.assertEqual(out['bootstrap_mode'], UNBOUND_MODE)
        self.assertEqual(out['bootstrap_version'], BOOTSTRAP_VERSION)
        self.assertFalse(out['execution_performed'])
        self.assertEqual(out['authority_effect'], 'NONE')
        self.assertIs(PROCESS_COOPERATIVE_RUNTIME.current('MD001'), before)

    def test_qualification_entrypoint_rejects_runtime_activation_and_worker_substitution(self):
        trusted = self.environment(LION_MATERIAL_WORKER_ID='MD001')
        with self.assertRaisesRegex(CooperativeWorkerBootstrapError, 'requires UNBOUND'):
            qualify_released_assignment_from_environment(
                trusted,
                assignment_id='assignment-fixture-1',
                material_worker_id='MD001',
            )
        unbound = self.environment(
            LION_COOPERATIVE_BOOTSTRAP_MODE=UNBOUND_MODE,
            LION_MATERIAL_WORKER_ID='MD001',
        )
        with self.assertRaisesRegex(CooperativeWorkerBootstrapError, 'worker/environment mismatch'):
            qualify_released_assignment_from_environment(
                unbound,
                assignment_id='assignment-fixture-1',
                material_worker_id='MD002',
            )

    def test_worker_bootstraps_before_first_status_publication(self):
        worker = (
            Path(__file__).resolve().parents[2]
            / 'LION/runtime_compat/r24/docker-autonomy/worker.py'
        ).read_text(encoding='utf-8')
        bootstrap = worker.index('COOPERATIVE_BOOTSTRAP = bootstrap_process_runtime()')
        first_status = worker.index('write_status(\n    state="STARTING"')
        self.assertLess(bootstrap, first_status)
        self.assertIn('"cooperative_runtime_bootstrap": COOPERATIVE_BOOTSTRAP', worker)


if __name__ == '__main__':
    unittest.main()
