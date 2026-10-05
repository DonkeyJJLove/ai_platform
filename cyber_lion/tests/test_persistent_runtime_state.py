from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import sqlite3
import tempfile
import unittest

from cyber_lion.tests import test_runtime_execution as rt
from cyber_lion.tests import test_executor_sandbox as sb
from cyber_lion.contracts.executor_sandbox import SandboxOperation, SandboxResourceLimits
from cyber_lion.enterprise.runtime_execution import (
    RuntimeExecutionError,
    SQLiteAdmissionConsumptionGuard,
    SQLiteRuntimeAdmissionSource,
)
from cyber_lion.enterprise.executor_sandbox import (
    SandboxEnforcementError,
    SQLiteSandboxBudgetLedger,
    SQLiteSandboxReplayGuard,
)


class PersistentRuntimeExecutionStateTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name).resolve()

    def admission(self):
        identity=rt.identity()
        effect=rt.effect(identity)
        return rt.admission(effect,identity)

    def test_runtime_admission_source_roundtrip_and_restart(self):
        path=self.root/'runtime.sqlite'
        source=SQLiteRuntimeAdmissionSource(path,rt.trust())
        admission=self.admission()
        source.publish(
            admission,
            provenance_digest=sha256(b'canonical-runtime-admission-producer').hexdigest(),
            published_at=datetime(2026,10,5,12,0,tzinfo=timezone.utc),
        )
        self.assertEqual(source.resolve(admission.admission_digest),admission)
        self.assertTrue(source.is_current(admission.admission_digest))
        restarted=SQLiteRuntimeAdmissionSource(path,rt.trust())
        self.assertEqual(restarted.resolve(admission.admission_digest),admission)
        self.assertTrue(restarted.is_current(admission.admission_digest))

    def test_runtime_admission_source_rejects_publication_replay(self):
        path=self.root/'runtime.sqlite';source=SQLiteRuntimeAdmissionSource(path,rt.trust());admission=self.admission()
        kwargs=dict(
            provenance_digest=sha256(b'producer').hexdigest(),
            published_at='2026-10-05T12:00:00+00:00',
        )
        source.publish(admission,**kwargs)
        with self.assertRaisesRegex(RuntimeExecutionError,'publication replay'):
            source.publish(admission,**kwargs)

    def test_runtime_admission_source_detects_tampered_record(self):
        path=self.root/'runtime.sqlite';source=SQLiteRuntimeAdmissionSource(path,rt.trust());admission=self.admission()
        source.publish(admission,provenance_digest=sha256(b'producer').hexdigest(),
                       published_at='2026-10-05T12:00:00+00:00')
        with sqlite3.connect(path) as db:
            db.execute("UPDATE runtime_admissions SET admission_json=? WHERE admission_digest=?",
                       ('{}',admission.admission_digest))
            db.commit()
        with self.assertRaisesRegex(RuntimeExecutionError,'record invalid'):
            source.resolve(admission.admission_digest)
        self.assertFalse(source.is_current(admission.admission_digest))

    def test_admission_consumption_is_durable_and_exactly_once(self):
        path=self.root/'consume.sqlite'
        first=SQLiteAdmissionConsumptionGuard(path)
        digest=sha256(b'admission').hexdigest()
        self.assertTrue(first.consume(digest,'exec-1'))
        restarted=SQLiteAdmissionConsumptionGuard(path)
        self.assertFalse(restarted.consume(digest,'exec-2'))
        self.assertFalse(restarted.consume(digest,'exec-1'))
        self.assertTrue(restarted.consume(sha256(b'other').hexdigest(),'exec-2'))

    def test_runtime_state_database_replacement_is_denied(self):
        path=self.root/'runtime.sqlite'
        source=SQLiteRuntimeAdmissionSource(path,rt.trust())
        admission=self.admission()
        source.publish(admission,provenance_digest=sha256(b'producer').hexdigest(),
                       published_at='2026-10-05T12:00:00+00:00')
        replacement=self.root/'replacement.sqlite'
        replacement.write_bytes(path.read_bytes())
        path.unlink()
        replacement.replace(path)
        with self.assertRaisesRegex(RuntimeExecutionError,'identity drift'):
            source.resolve(admission.admission_digest)

    def test_runtime_admission_provenance_corruption_fails_closed(self):
        path=self.root/'runtime.sqlite';source=SQLiteRuntimeAdmissionSource(path,rt.trust());admission=self.admission()
        source.publish(admission,provenance_digest=sha256(b'producer').hexdigest(),
                       published_at='2026-10-05T12:00:00+00:00')
        with sqlite3.connect(path) as db:
            db.execute("UPDATE runtime_admissions SET provenance_digest='bad' WHERE admission_digest=?",
                       (admission.admission_digest,))
            db.commit()
        with self.assertRaisesRegex(RuntimeExecutionError,'provenance corrupt'):
            source.resolve(admission.admission_digest)
        self.assertFalse(source.is_current(admission.admission_digest))

    def test_admission_consumption_execution_id_cannot_bind_two_admissions(self):
        path=self.root/'consume.sqlite';guard=SQLiteAdmissionConsumptionGuard(path)
        self.assertTrue(guard.consume(sha256(b'a').hexdigest(),'exec-1'))
        self.assertFalse(guard.consume(sha256(b'b').hexdigest(),'exec-1'))


class PersistentSandboxStateTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name).resolve()

    def test_sandbox_replay_survives_restart(self):
        path=self.root/'sandbox.sqlite'
        first=SQLiteSandboxReplayGuard(path)
        self.assertTrue(first.consume('mission-a','op-1'))
        restarted=SQLiteSandboxReplayGuard(path)
        self.assertFalse(restarted.consume('mission-a','op-1'))
        self.assertTrue(restarted.consume('mission-b','op-1'))
        self.assertTrue(restarted.consume('mission-a','op-2'))

    def test_sandbox_budget_survives_restart_and_exhaustion_does_not_mutate(self):
        path=self.root/'budget.sqlite'
        limits=SandboxResourceLimits(2,3,100,1)
        policy=sb.policy(limits=limits)
        first=SQLiteSandboxBudgetLedger(policy,path)
        read=sb.op(policy,operation_id='read-1')
        first.reserve(read)
        self.assertEqual(first.snapshot().operations,1)

        restarted=SQLiteSandboxBudgetLedger(policy,path)
        payload=b'abc'
        write=sb.op(policy,'WRITE_FILE','cyber_lion/x.py',operation_id='write-1',payload=payload)
        restarted.reserve(write)
        self.assertEqual(restarted.snapshot().operations,2)
        self.assertEqual(restarted.snapshot().write_bytes,3)

        with self.assertRaisesRegex(SandboxEnforcementError,'budget exhausted'):
            restarted.reserve(sb.op(policy,operation_id='read-2'))
        self.assertEqual(restarted.snapshot().operations,2)
        self.assertEqual(restarted.snapshot().write_bytes,3)

    def test_sandbox_state_database_replacement_is_denied(self):
        path=self.root/'sandbox.sqlite'
        guard=SQLiteSandboxReplayGuard(path)
        replacement=self.root/'replacement.sqlite'
        replacement.write_bytes(path.read_bytes())
        path.unlink()
        replacement.replace(path)
        with self.assertRaisesRegex(SandboxEnforcementError,'identity drift'):
            guard.consume('mission-a','op-1')

    def test_budget_policy_substitution_is_denied(self):
        path=self.root/'budget.sqlite'
        policy=sb.policy()
        ledger=SQLiteSandboxBudgetLedger(policy,path)
        other=replace(policy,dispatch_id=sb.D('other-dispatch'))
        # Rebuild digest-consistent op under another policy.
        operation=SandboxOperation(
            'op-other',other.mission_id,other.drone_id,other.executor_id,
            other.sandbox_id,other.workspace_id,other.dispatch_id,other.fencing_token,
            other.generation,other.digest(),'READ_FILE','cyber_lion/a.py',
        )
        with self.assertRaisesRegex(SandboxEnforcementError,'policy substitution'):
            ledger.reserve(operation)
        self.assertEqual(ledger.snapshot().operations,0)

    def test_distinct_policy_digests_have_distinct_durable_budgets(self):
        path=self.root/'budget.sqlite'
        first_policy=sb.policy()
        second_policy=replace(first_policy,dispatch_id=sb.D('dispatch-2'))
        first=SQLiteSandboxBudgetLedger(first_policy,path)
        second=SQLiteSandboxBudgetLedger(second_policy,path)
        first.reserve(sb.op(first_policy,operation_id='first'))
        self.assertEqual(first.snapshot().operations,1)
        self.assertEqual(second.snapshot().operations,0)


if __name__=='__main__':
    unittest.main()
