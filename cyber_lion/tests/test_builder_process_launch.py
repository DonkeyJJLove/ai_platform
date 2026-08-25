from __future__ import annotations

import inspect
import sqlite3
import tempfile
import threading
import unittest
from dataclasses import replace
from pathlib import Path

from cyber_lion.enterprise.builder_process_launch import BuilderProcessLaunchBoundary
from cyber_lion.enterprise.persistent_authority_state import (
    PersistentAuthorityStateError,
    PersistentAuthorityStoreOrigin,
    PersistentBindingFinalization,
    PersistentBuilderEntryIssuanceRecord,
    PersistentBuilderInvocationIssuanceRecord,
    PersistentBuilderProcessHeldMaterialization,
    PersistentBuilderProcessLaunchReceipt,
    SQLiteAuthorityStateStore,
)

D = lambda c: c * 64
S = lambda c: c * 40
SCOPE = ("cyber_lion/example.py",)
RESOURCE = ("repo:DonkeyJJLove/ai_platform",)


def origin(path="/tmp/a.db"):
    return PersistentAuthorityStoreOrigin(
        "aso:" + D("e"), D("e"), "1.0.0", "/repo", path
    ).validate()


def entry_record(**changes):
    o = origin()
    data = dict(
        builder_entry_permit_id="bep:" + D("1"),
        builder_entry_permit_digest=D("2"),
        builder_entry_replay_digest=D("3"),
        repository="DonkeyJJLove/ai_platform",
        baseline_master_sha=S("a"),
        baseline_master_tree_sha=S("b"),
        action="BUILD_CANDIDATE",
        candidate_scope=SCOPE,
        resource_scope=RESOURCE,
        authority_epoch=1,
        authority_state_version=1,
        root_grant_id="root:r22",
        root_grant_digest=D("4"),
        current_authority_digest=D("5"),
        builder_subject_id="builder:r22",
        builder_instance_id="instance:r22",
        builder_capability_class="DETACHED_CANDIDATE_BUILD_ONLY",
        builder_identity_digest=D("6"),
        builder_implementation_digest=D("7"),
        builder_attestation_digest=D("8"),
        authority_store_origin_id=o.origin_id,
        authority_store_origin_digest=o.origin_digest,
        issued_at="2026-08-25T14:00:00Z",
    )
    data.update(changes)
    return PersistentBuilderEntryIssuanceRecord(**data)


def invocation_record(**changes):
    o = origin()
    data = dict(
        builder_invocation_permit_id="bip:" + D("1"),
        builder_invocation_permit_digest=D("2"),
        builder_invocation_replay_digest=D("3"),
        source_builder_entry_permit_id="bep:" + D("4"),
        source_builder_entry_permit_digest=D("5"),
        repository="DonkeyJJLove/ai_platform",
        baseline_master_sha=S("a"),
        baseline_master_tree_sha=S("b"),
        current_baseline_digest=D("6"),
        action="BUILD_CANDIDATE",
        candidate_scope=SCOPE,
        resource_scope=RESOURCE,
        authority_epoch=1,
        authority_state_version=1,
        root_grant_id="root:r22",
        root_grant_digest=D("7"),
        current_authority_digest=D("8"),
        builder_subject_id="builder:r22",
        builder_instance_id="instance:r22",
        builder_capability_class="DETACHED_CANDIDATE_BUILD_ONLY",
        builder_identity_digest=D("9"),
        builder_implementation_digest=D("a"),
        builder_attestation_digest=D("b"),
        current_builder_subject_digest=D("c"),
        authority_store_origin_id=o.origin_id,
        authority_store_origin_digest=o.origin_digest,
        issued_at="2026-08-25T14:00:00Z",
    )
    data.update(changes)
    return PersistentBuilderInvocationIssuanceRecord(**data)


class BuilderProcessLaunchTests(unittest.TestCase):
    def test_boundary_requires_effect_clock_and_no_runtime_provider_argument(self):
        self.assertIn("effect_clock", inspect.signature(BuilderProcessLaunchBoundary).parameters)
        params = inspect.signature(BuilderProcessLaunchBoundary.launch).parameters
        self.assertNotIn("runtime_provider", params)
        self.assertNotIn("trusted_now", params)
        src = inspect.getsource(__import__("cyber_lion.enterprise.builder_process_launch", fromlist=["x"]))
        self.assertIn("observe_gate", src)
        self.assertIn("GATE_CLOSED", src)
        self.assertIn("GATE_OPENED_ONCE", src)

    def test_store_ready_requires_eleven_tables(self):
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / "a.db")
            store = SQLiteAuthorityStateStore(path)
            self.assertEqual(len(store.REQUIRED_TABLES), 11)
            self.assertTrue(store.ready())
            with sqlite3.connect(path) as connection:
                cols = {row[1] for row in connection.execute("PRAGMA table_info(builder_process_held_materialization)")}
            self.assertIn("execution_gate_id", cols)
            self.assertIn("execution_gate_digest", cols)

    def test_persistent_held_and_receipt_reject_numeric_pid(self):
        o = origin()
        held = PersistentBuilderProcessHeldMaterialization(
            "launch:x", "bplr:" + D("1"), D("2"), D("1"), "provider:x", D("3"), D("4"), D("5"),
            "runtime:x", "env:x", "pidfd:x", "token:x", D("6"), "gate:x", D("7"), "CLOSED",
            D("8"), D("9"), "HELD_NOT_EXECUTING_BUILDER", "2026-08-25T14:00:00Z",
            "2026-08-25T14:00:01Z", o.origin_id, o.origin_digest,
        ).validate()
        with self.assertRaises(PersistentAuthorityStateError):
            replace(held, process_handle_reference="123").validate()
        receipt = PersistentBuilderProcessLaunchReceipt(
            "bplx:" + D("1"), D("2"), "bplr:" + D("1"), D("3"), D("1"), "bsa:" + D("4"), D("5"),
            "DonkeyJJLove/ai_platform", S("a"), S("b"), D("6"), D("7"), "bpp:" + D("8"), D("8"),
            D("9"), "provider:x", D("a"), D("b"), D("c"), "runtime:x", "launch:x", "env:x",
            "pidfd:x", "token:x", D("d"), "gate:x", D("e"), D("f"), D("0"),
            "2026-08-25T14:00:00Z", "2026-08-25T14:00:01Z", "BUILDER_PROCESS_START",
            "STARTED_OBSERVED", "CLOSED_TO_OPENED_ONCE", o.origin_id, o.origin_digest,
        ).validate()
        with self.assertRaises(PersistentAuthorityStateError):
            replace(receipt, process_handle_reference="77").validate()
        with self.assertRaises(PersistentAuthorityStateError):
            replace(receipt, gate_transition="OPEN").validate()

    def test_concurrent_launch_replay_one_winner(self):
        with tempfile.TemporaryDirectory() as directory:
            store = SQLiteAuthorityStateStore(str(Path(directory) / "a.db"))
            barrier = threading.Barrier(6)
            out = []
            lock = threading.Lock()

            def worker():
                barrier.wait()
                value = store.consume_replay("builder-process-launch", D("1"), "2026-08-25T14:00:00Z")
                with lock:
                    out.append(value)

            threads = [threading.Thread(target=worker) for _ in range(6)]
            [thread.start() for thread in threads]
            [thread.join() for thread in threads]
            self.assertEqual(out.count(True), 1)

    def test_pre_r22_builder_entry_epoch_and_state_floor(self):
        entry_record().validate()
        for changes in (
            {"authority_epoch": -1},
            {"authority_epoch": True},
            {"authority_state_version": 0},
            {"authority_state_version": True},
        ):
            with self.assertRaises(PersistentAuthorityStateError):
                entry_record(**changes).validate()

    def test_pre_r22_builder_invocation_epoch_and_state_floor(self):
        invocation_record().validate()
        for changes in (
            {"authority_epoch": -1},
            {"authority_epoch": True},
            {"authority_state_version": 0},
            {"authority_state_version": True},
        ):
            with self.assertRaises(PersistentAuthorityStateError):
                invocation_record(**changes).validate()

    def test_pre_r22_binding_finalization_floor(self):
        valid = PersistentBindingFinalization(
            "lion.test", "tenant", "org", "mission", 1, 1, "grant", "root", D("1"), D("2"),
            D("3"), "nonce", D("4"), "2026-08-25T14:00:00Z",
        )
        valid.validate()
        with self.assertRaises(PersistentAuthorityStateError):
            replace(valid, epoch=-1).validate()
        with self.assertRaises(PersistentAuthorityStateError):
            replace(valid, epoch=True).validate()
        with self.assertRaises(PersistentAuthorityStateError):
            replace(valid, authority_state_version=0).validate()
        with self.assertRaises(PersistentAuthorityStateError):
            replace(valid, authority_state_version=True).validate()

    def test_pre_r22_bootstrap_and_monotonicity_floor(self):
        context = ("lion.test", "tenant", "org", "mission")
        with tempfile.TemporaryDirectory() as directory:
            store = SQLiteAuthorityStateStore(str(Path(directory) / "a.db"))
            for bad_epoch in (-1, True):
                with self.assertRaises(PersistentAuthorityStateError):
                    store.bootstrap_context(context, epoch=bad_epoch)
            store.bootstrap_context(context, epoch=7, revoked_grant_ids=("a",))
            with self.assertRaises(PersistentAuthorityStateError):
                store.advance_epoch(context, epoch=6, revoked_grant_ids=("a",))
            with self.assertRaises(PersistentAuthorityStateError):
                store.advance_epoch(context, epoch=7, revoked_grant_ids=())


if __name__ == "__main__":
    unittest.main()
