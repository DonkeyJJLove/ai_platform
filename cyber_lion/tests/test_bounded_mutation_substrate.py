from __future__ import annotations

from datetime import datetime, timedelta, timezone
import sqlite3
import unittest

from cyber_lion.contracts.bounded_mutation import (
    MutationAdmission, MutationContractError, digest,
)
from cyber_lion.mission_control.bounded_mutation_substrate import (
    BoundedMutationSubstrate, MutationSubstrateError,
)


HEAD = "a" * 40
TREE = "b" * 40


def z(dt):
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


class Clock:
    def __init__(self):
        self.value = datetime(2026, 9, 26, 16, 0, tzinfo=timezone.utc)
    def __call__(self):
        return z(self.value)


def admission(pre, post, **overrides):
    c = Clock()
    value = {
        "MUTATION_ADMISSION_ID": "madm:test-001",
        "PARENT_MISSION_ID": "LION-R24-EPOCH-CLOSURE-SUPERVISOR-R1",
        "PHASE_ID": "P09_CONSOLIDATION_EXECUTION",
        "CHANGE_ID": "change:test-001",
        "ACTOR_ROLE": "BOUNDED_MUTATION_EXECUTOR",
        "TARGET_OBJECT": {"kind": "test-object", "id": "alpha"},
        "EXPECTED_PRE_STATE": pre,
        "EXPECTED_POST_STATE": post,
        "ALLOWED_EFFECT_CLASS": "MISSION_DB_WRITE_BOUNDED",
        "EFFECT_CEILING": "CONTROL_STATE",
        "SOURCE_IDENTITY": {"source_head": HEAD, "source_tree": TREE},
        "DEPENDENCY_SNAPSHOT": {"digest": digest({"dependency": "current"})},
        "ROLLBACK_PROCEDURE": {"id": "rollback:test"},
        "TEST_PROCEDURE": {"id": "test:test"},
        "READBACK_PROCEDURE": {"id": "readback:test"},
        "EXPIRATION": z(c.value + timedelta(minutes=10)),
        "SINGLE_USE_NONCE": "nonce:test:00000000000000000001",
    }
    value.update(overrides)
    return value


class BoundedMutationContractTests(unittest.TestCase):
    def test_exact_required_fields(self):
        pre, post = digest({"v": 1}), digest({"v": 2})
        value = admission(pre, post)
        value.pop("TEST_PROCEDURE")
        with self.assertRaises(MutationContractError):
            MutationAdmission.from_mapping(value)

    def test_effect_cannot_exceed_ceiling(self):
        pre, post = digest({"v": 1}), digest({"v": 2})
        with self.assertRaises(MutationContractError):
            MutationAdmission.from_mapping(admission(
                pre, post,
                ALLOWED_EFFECT_CLASS="RUNTIME_DEPLOY_BOUNDED",
                EFFECT_CEILING="CONTROL_STATE",
            ))

    def test_unknown_effect_denied(self):
        pre, post = digest({"v": 1}), digest({"v": 2})
        with self.assertRaises(MutationContractError):
            MutationAdmission.from_mapping(admission(
                pre, post, ALLOWED_EFFECT_CLASS="UNBOUNDED_ANYTHING",
            ))


class BoundedMutationSubstrateTests(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()
        self.conn = sqlite3.connect(":memory:")
        self.state = {"v": 1}
        self.pre = digest(self.state)
        self.post_state = {"v": 2}
        self.post = digest(self.post_state)

    def substrate(self, *, bound=True):
        def executor(_admission):
            self.state = dict(self.post_state)
            return {"applied": True}
        bindings = {
            "MISSION_DB_WRITE_BOUNDED": ("TEST_EXECUTOR", executor)
        } if bound else {}
        return BoundedMutationSubstrate(self.conn, bindings, now_fn=self.clock)

    def readback(self, _admission):
        return digest(self.state)

    def test_success_consumes_once_and_reconciles(self):
        s = self.substrate()
        s.issue(admission(self.pre, self.post))
        receipt = s.execute(
            "madm:test-001",
            observed_pre_state=self.pre,
            readback=self.readback,
            test=lambda _a: {"status": "PASS"},
            rollback=lambda _a: self.state.update({"v": 1}),
        )
        self.assertEqual(receipt["status"], "RECONCILED")
        self.assertTrue(receipt["receipt_is_evidence_not_authority"])
        self.assertEqual(s.snapshot()["counts"]["bounded_mutation_consumptions"], 1)
        with self.assertRaisesRegex(MutationSubstrateError, "replay"):
            s.execute(
                "madm:test-001",
                observed_pre_state=self.pre,
                readback=self.readback,
                test=lambda _a: {"status": "PASS"},
                rollback=lambda _a: None,
            )

    def test_unbound_effect_denied_before_consumption(self):
        s = self.substrate(bound=False)
        s.issue(admission(self.pre, self.post))
        with self.assertRaisesRegex(MutationSubstrateError, "no bound executor"):
            s.execute(
                "madm:test-001",
                observed_pre_state=self.pre,
                readback=self.readback,
                test=lambda _a: {"status": "PASS"},
                rollback=lambda _a: None,
            )
        self.assertEqual(s.snapshot()["counts"]["bounded_mutation_consumptions"], 0)

    def test_stale_prestate_denied_before_consumption(self):
        s = self.substrate()
        s.issue(admission(self.pre, self.post))
        with self.assertRaisesRegex(MutationSubstrateError, "pre-state"):
            s.execute(
                "madm:test-001",
                observed_pre_state=digest({"v": 999}),
                readback=self.readback,
                test=lambda _a: {"status": "PASS"},
                rollback=lambda _a: None,
            )
        self.assertEqual(s.snapshot()["counts"]["bounded_mutation_consumptions"], 0)

    def test_expired_denied_before_consumption(self):
        s = self.substrate()
        expired = z(self.clock.value - timedelta(seconds=1))
        s.issue(admission(self.pre, self.post, EXPIRATION=expired))
        with self.assertRaisesRegex(MutationSubstrateError, "expired"):
            s.execute(
                "madm:test-001",
                observed_pre_state=self.pre,
                readback=self.readback,
                test=lambda _a: {"status": "PASS"},
                rollback=lambda _a: None,
            )
        self.assertEqual(s.snapshot()["counts"]["bounded_mutation_consumptions"], 0)

    def test_poststate_mismatch_rolls_back(self):
        s = self.substrate()
        wrong_expected = digest({"v": 3})
        s.issue(admission(self.pre, wrong_expected))
        receipt = s.execute(
            "madm:test-001",
            observed_pre_state=self.pre,
            readback=self.readback,
            test=lambda _a: {"status": "PASS"},
            rollback=lambda _a: self.state.update({"v": 1}),
        )
        self.assertEqual(receipt["status"], "ROLLED_BACK")
        self.assertEqual(receipt["observed_post_state"], self.pre)

    def test_nonce_reuse_denied_at_issue(self):
        s = self.substrate()
        first = admission(self.pre, self.post)
        s.issue(first)
        second = admission(
            self.pre, self.post,
            MUTATION_ADMISSION_ID="madm:test-002",
            CHANGE_ID="change:test-002",
        )
        with self.assertRaisesRegex(MutationSubstrateError, "replay/nonce"):
            s.issue(second)

    def test_receipt_is_immutable(self):
        s = self.substrate()
        s.issue(admission(self.pre, self.post))
        s.execute(
            "madm:test-001",
            observed_pre_state=self.pre,
            readback=self.readback,
            test=lambda _a: {"status": "PASS"},
            rollback=lambda _a: None,
        )
        with self.assertRaises(sqlite3.DatabaseError):
            self.conn.execute("UPDATE bounded_mutation_receipts SET status='FORGED'")


if __name__ == "__main__":
    unittest.main()
