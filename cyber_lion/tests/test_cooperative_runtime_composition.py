"""Original assignment adapter + original enforcement + real filesystem.

Authority/currentness sources are explicit synthetic test fixtures. These tests
prove composition and refusal, NOT live issuance, Docker isolation or LPCL launch.
"""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import tempfile
import unittest

from cyber_lion.tests import test_runtime_execution as rt
from cyber_lion.tests import test_executor_sandbox as sb
from cyber_lion.tests import test_runtime_currentness as rc
from cyber_lion.contracts.runtime_currentness import EffectTimeCurrentnessEvidence
from cyber_lion.contracts.runtime_execution import RuntimeExecutionReceipt
from cyber_lion.enterprise.executor_sandbox import (
    InMemorySandboxReplayGuard, SandboxBudgetLedger, SQLiteSandboxBudgetLedger,
)
from cyber_lion.enterprise.runtime_execution import SQLiteAdmissionConsumptionGuard
from cyber_lion.enterprise.cooperative_runtime_writer import CooperativeExecutionBinding
from cyber_lion.enterprise.cooperative_runtime_composition import (
    CooperativeRuntimeContext, CooperativeRuntimeWriterProvider,
)
from tools.lion_cooperative_worker_adapter import cooperative_assignment_once
from cyber_lion.mission_control.cooperative_artifacts import verify_text


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()


class CooperativeRuntimeCompositionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'artifacts'
        self.root.mkdir()
        self.guard_path = Path(self.temp.name) / 'fixture-consumption.sqlite'
        self.data = 'testowy produkt: żółw\n'.encode()
        self.resource = 'M1/g00000001/product.txt'
        original = {
            'kind': 'COOPERATIVE_ARTIFACT_WRITE', 'mission_id': 'M1',
            'generation': 1, 'artifact_name': 'product.txt', 'content': self.data.decode(),
            'expected_sha256': sha256(self.data).hexdigest(),
            'producer_model_call_id': 'modelcall-fixture-1',
            'parent_response_digest': sha256(self.data).hexdigest(),
        }
        self.payload = {**original, 'assignment_id': 'assignment-fixture-1'}
        self.claim = {
            'assignment_id': 'assignment-fixture-1', 'mission_id': 'M1',
            'material_drone_id': 'MD001', 'lease_generation': 1, 'state': 'CLAIMED',
            'lease_expires_at': '2026-10-05T00:00:00Z',
            'input_json': canonical(original).decode(),
            'input_digest': sha256(canonical(original)).hexdigest(),
        }
        self.now = datetime(2026, 10, 4, 23, 0, tzinfo=timezone.utc)
        self.fd = sb.dispatch(mission_id='M1', drone_id='drone:1', write_scope=(self.resource,))
        self.pb = sb.provisioning(
            mission_id='M1', drone_id='drone:1', executor_id='executor:1',
            runtime_instance_id='runtime:1', sandbox_id='sandbox:1', workspace_id='workspace:1',
            runtime_attestation_digest=rt.Z, provisioned_executor_digest=rt.Z,
            read_scope=('M1',), write_scope=(self.resource,),
        )
        self.rb = sb.runtime(sandbox_id='sandbox:1', workspace_id='workspace:1')
        self.policy = sb.policy(
            fd=self.fd, pb=self.pb, mission_id='M1', drone_id='drone:1', executor_id='executor:1',
            sandbox_id='sandbox:1', workspace_id='workspace:1', runtime_instance_id='runtime:1',
            runtime_attestation_digest=rt.Z, runtime_binding_digest=self.rb.digest(),
            read_scope=('M1',), write_scope=(self.resource,), test_scope=('M1',),
        )
        identity = rt.identity()
        effect = rt.effect(identity, mission_id='M1', resource=self.resource,
                           payload_digest=sha256(self.data).hexdigest())
        self.authority = replace(rc.authority(), mission_id='M1', authority_ceiling='local_write')
        admission = rt.admission(effect, identity, live_authority_digest=self.authority.digest())
        request = rt.request(admission, effect, identity, execution_id='assignment-fixture-1',
                             dispatch_id=self.fd.dispatch_id, fencing_token=self.fd.fencing_token,
                             payload_size=len(self.data))
        self.binding = CooperativeExecutionBinding(
            'assignment-fixture-1', 'MD001', self.claim['input_digest'], self.root,
            admission, request, effect, identity,
        )
        self.source = rt.AdmissionSource(admission)
        self.live_authority = rc.FakeAdmission()
        self.currentness = rc.Source(self.authority, policy=effect.policy_binding)
        self.dispatch_source = sb.DispatchSource(self.fd)
        self.budget = SandboxBudgetLedger(self.policy)
        self.admission_guard = SQLiteAdmissionConsumptionGuard(self.guard_path)
        self.sandbox_guard = InMemorySandboxReplayGuard()
        self.lookups = []
        self.provider = self.make_provider()

    def context(self, assignment_id):
        self.lookups.append(assignment_id)
        return CooperativeRuntimeContext(self.binding, self.policy, self.rb, self.fd, self.pb)

    def make_provider(self, **overrides):
        params = dict(
            context_source=self.context, admission_source=self.source, admission_trust=rt.trust(),
            authority_admission=self.live_authority, currentness_source=self.currentness,
            currentness_trust=rc.trust(), dispatch_source=self.dispatch_source,
            admission_guard=self.admission_guard, sandbox_guard=self.sandbox_guard,
            budget_source=lambda p: self.budget, now_fn=lambda: self.now,
        )
        params.update(overrides)
        return CooperativeRuntimeWriterProvider(**params)

    def write(self, provider=None, **overrides):
        params = dict(claimed=self.claim, payload=self.payload, artifact_root=self.root, worker_id='MD001')
        params.update(overrides)
        return (provider or self.provider)(**params)

    def assert_no_artifact(self):
        self.assertEqual(list(self.root.iterdir()), [])

    def test_assignment_adapter_to_runtime_to_artifact_to_second_worker(self):
        calls = []
        row = {**self.claim, 'state': 'READY'}
        def control(operation, args):
            calls.append((operation, args))
            if operation == 'local_assignment_claim':
                return dict(self.claim)
            if operation == 'local_assignment_receipt':
                return {'receipt_id': 'fixture-receipt', **args}
            raise AssertionError(operation)
        receipt = cooperative_assignment_once(
            control, material_drone_id='MD001', artifact_root=self.root,
            pending=[row], admitted_writer=self.provider, now_fn=lambda: self.now,
        )
        self.assertEqual(receipt['status'], 'PASS', receipt)
        result = receipt['result']
        self.assertEqual((self.root / self.resource).read_bytes(), self.data)
        self.assertEqual(receipt['effect_receipt_digest'], result['runtime_receipt']['receipt_digest'])
        effect = dict(result['runtime_receipt'])
        effect['observed_events'] = tuple(effect['observed_events'])
        effect['side_effect_refs'] = tuple(effect['side_effect_refs'])
        RuntimeExecutionReceipt(**effect).validate()
        evidence = EffectTimeCurrentnessEvidence(**result['effect_time_currentness']).validate()
        self.assertEqual(evidence.admission_digest, self.binding.admission.admission_digest)
        self.assertEqual(evidence.observability_state, 'HEALTHY')
        verified = verify_text(self.root, {
            'kind': 'COOPERATIVE_ARTIFACT_VERIFY', 'mission_id': 'M1',
            'source_assignment_id': self.claim['assignment_id'], 'generation': 1,
            'artifact_name': 'product.txt', 'expected_sha256': sha256(self.data).hexdigest(),
            'expected_producer_worker_id': 'MD001',
        }, worker_id='MD002')
        self.assertTrue(verified['digest_match'])
        # Initial resolution plus mandatory revalidation at the filesystem boundary.
        # Both lookups must retain the identical assignment; one lookup is no longer sufficient.
        self.assertEqual(self.lookups, ['assignment-fixture-1', 'assignment-fixture-1'])
        self.assertEqual([x[0] for x in calls], ['local_assignment_claim', 'local_assignment_receipt'])

    def test_revocation_between_claim_and_effect_prevents_write(self):
        self.live_authority.fail = True
        with self.assertRaisesRegex(rt.RuntimeExecutionError, 'sandbox execution'):
            self.write()
        self.assert_no_artifact()

    def test_policy_change_before_effect_prevents_write(self):
        self.currentness.policy = 'policy@2:sha256:' + rt.F
        with self.assertRaises(rt.RuntimeExecutionError):
            self.write()
        self.assert_no_artifact()

    def test_observer_lost_before_effect_prevents_write(self):
        self.currentness.obs = 'LOST'
        with self.assertRaises(rt.RuntimeExecutionError):
            self.write()
        self.assert_no_artifact()

    def test_authority_epoch_changes_before_effect_prevent_write(self):
        self.live_authority.changed = True
        with self.assertRaises(rt.RuntimeExecutionError):
            self.write()
        self.assert_no_artifact()

    def test_failed_effect_time_guard_consumes_admission_not_silent_retry(self):
        self.live_authority.fail = True
        with self.assertRaises(rt.RuntimeExecutionError):
            self.write()
        self.live_authority.fail = False
        with self.assertRaisesRegex(rt.RuntimeExecutionError, 'replay'):
            self.write(self.make_provider())
        self.assert_no_artifact()

    def test_reconstructed_provider_preserves_durable_consumption(self):
        self.write()
        restarted_guard = SQLiteAdmissionConsumptionGuard(self.guard_path)
        replacement = self.make_provider(admission_guard=restarted_guard,
                                         sandbox_guard=InMemorySandboxReplayGuard())
        with self.assertRaisesRegex(rt.RuntimeExecutionError, 'replay'):
            self.write(replacement)
        self.assertEqual((self.root / self.resource).read_bytes(), self.data)
        self.assertEqual(self.budget.snapshot().operations, 1)

    def test_reconstructed_provider_does_not_reset_budget(self):
        from cyber_lion.contracts.executor_sandbox import SandboxOperation, SandboxResourceLimits
        self.policy = replace(self.policy, resource_limits=SandboxResourceLimits(1, 1000, 1000, 1))
        self.budget = SandboxBudgetLedger(self.policy)
        reserved = SandboxOperation('fixture-prior', 'M1', 'drone:1', 'executor:1',
                                    'sandbox:1', 'workspace:1', self.fd.dispatch_id,
                                    self.fd.fencing_token, 1, self.policy.digest(), 'READ_FILE', 'M1/input')
        self.budget.reserve(reserved)
        with self.assertRaises(rt.RuntimeExecutionError):
            self.write(self.make_provider())
        self.assertEqual(self.budget.snapshot().operations, 1)
        self.assert_no_artifact()

    def test_reconstructed_provider_preserves_durable_budget_state(self):
        from cyber_lion.contracts.executor_sandbox import SandboxOperation, SandboxResourceLimits
        self.policy = replace(self.policy, resource_limits=SandboxResourceLimits(1, 1000, 1000, 1))
        budget_path = Path(self.temp.name) / 'fixture-budget.sqlite'
        first = SQLiteSandboxBudgetLedger(self.policy, budget_path)
        reserved = SandboxOperation(
            'fixture-prior-persistent', 'M1', 'drone:1', 'executor:1',
            'sandbox:1', 'workspace:1', self.fd.dispatch_id, self.fd.fencing_token,
            1, self.policy.digest(), 'READ_FILE', 'M1/input',
        )
        first.reserve(reserved)
        replacement = self.make_provider(
            budget_source=lambda p: SQLiteSandboxBudgetLedger(p, budget_path),
        )
        with self.assertRaises(rt.RuntimeExecutionError):
            self.write(replacement)
        self.assertEqual(SQLiteSandboxBudgetLedger(self.policy, budget_path).snapshot().operations, 1)
        self.assert_no_artifact()

    def test_stale_runtime_admission_prevents_write(self):
        self.source.current = False
        with self.assertRaisesRegex(rt.RuntimeExecutionError, 'stale'):
            self.write()
        self.assert_no_artifact()

    def test_forged_runtime_admission_prevents_write(self):
        forged = replace(self.binding.admission, admission_id='other', admission_digest='').sealed()
        self.binding = replace(self.binding, admission=forged,
                               request=replace(self.binding.request, admission_digest=forged.admission_digest))
        with self.assertRaisesRegex(rt.RuntimeExecutionError, 'forged|substituted'):
            self.write()
        self.assert_no_artifact()

    def test_admission_source_substitution_prevents_write(self):
        self.source.source_instance_id = 'wrong-source'
        with self.assertRaisesRegex(rt.RuntimeExecutionError, 'substitution'):
            self.write()
        self.assert_no_artifact()

    def test_currentness_source_substitution_prevents_write(self):
        self.currentness.source_instance_id = 'wrong-currentness-source'
        with self.assertRaisesRegex(rc.RuntimeCurrentnessError, 'substitution'):
            self.write()
        self.assert_no_artifact()

    def test_missing_canonical_context_does_not_create_workspace(self):
        provider = self.make_provider(context_source=lambda aid: None)
        with self.assertRaisesRegex(ValueError, 'context unavailable'):
            self.write(provider)
        self.assert_no_artifact()

    def test_context_lookup_cannot_return_another_assignment(self):
        self.binding = replace(self.binding, assignment_id='another-assignment')
        with self.assertRaisesRegex(ValueError, 'another assignment'):
            self.write()
        self.assert_no_artifact()

    def test_stale_dispatch_fence_is_denied(self):
        self.dispatch_source.current = replace(self.fd, fencing_token=rt.F)
        with self.assertRaises(rt.RuntimeExecutionError):
            self.write()
        self.assert_no_artifact()

    def test_expired_claim_is_denied(self):
        with self.assertRaisesRegex(ValueError, 'expired'):
            self.write(claimed={**self.claim, 'lease_expires_at': '2026-10-04T22:59:00Z'})
        self.assert_no_artifact()

    def test_wrong_claim_generation_is_denied(self):
        with self.assertRaisesRegex(ValueError, 'coordinates'):
            self.write(claimed={**self.claim, 'lease_generation': 2})
        self.assert_no_artifact()

    def test_substituted_workspace_is_denied(self):
        with self.assertRaisesRegex(ValueError, 'root substitution'):
            self.write(artifact_root=self.root.parent)
        self.assert_no_artifact()

    def test_wrong_worker_is_denied(self):
        with self.assertRaises(ValueError):
            self.write(worker_id='MD002')
        self.assert_no_artifact()

    def test_input_digest_substitution_is_denied(self):
        with self.assertRaisesRegex(ValueError, 'digest'):
            self.write(claimed={**self.claim, 'input_digest': rt.F})
        self.assert_no_artifact()

    def test_policy_must_be_scoped_to_single_artifact(self):
        self.fd = replace(self.fd, write_scope=('M1',))
        self.pb = replace(self.pb, write_scope=('M1',))
        self.policy = replace(self.policy, write_scope=('M1',),
                              fleet_dispatch_binding_digest=self.fd.digest(),
                              provisioning_binding_digest=self.pb.digest())
        with self.assertRaisesRegex(ValueError, 'single-artifact'):
            self.write()
        self.assert_no_artifact()

    def test_runtime_attestation_substitution_is_denied(self):
        self.binding = replace(self.binding, identity=replace(self.binding.identity,
                                                              runtime_attestation_digest=rt.F))
        with self.assertRaisesRegex(ValueError, 'attestation'):
            self.write()
        self.assert_no_artifact()

    def test_missing_canonical_revalidator_rejected_at_construction(self):
        with self.assertRaisesRegex(ValueError, 'revalidator'):
            self.make_provider(authority_admission=None)
        self.assert_no_artifact()

    def test_missing_budget_rejected(self):
        with self.assertRaisesRegex(ValueError, 'budget unavailable'):
            self.write(self.make_provider(budget_source=lambda p: None))
        self.assert_no_artifact()

    def test_receipt_transport_loss_does_not_repeat_effect(self):
        calls = []
        def control(op, args):
            calls.append(op)
            if op == 'local_assignment_claim':
                return dict(self.claim)
            raise ConnectionError('receipt delivery unknown')
        with self.assertRaises(ConnectionError):
            cooperative_assignment_once(control, material_drone_id='MD001', artifact_root=self.root,
                                        pending=[{**self.claim, 'state': 'READY'}],
                                        admitted_writer=self.provider, now_fn=lambda: self.now)
        self.assertEqual((self.root / self.resource).read_bytes(), self.data)
        self.assertEqual(calls, ['local_assignment_claim', 'local_assignment_receipt'])
        with self.assertRaisesRegex(rt.RuntimeExecutionError, 'replay'):
            self.write(self.make_provider())


if __name__ == '__main__':
    unittest.main()
