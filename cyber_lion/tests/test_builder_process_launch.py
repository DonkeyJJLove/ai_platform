from __future__ import annotations

import inspect
import sqlite3
import tempfile
import threading
import unittest
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from cyber_lion.contracts.builder_process_launch import (
    BuilderExecutionGateEvidence, BuilderProcessIdentity, GATE_CLOSED, GATE_OPENED_ONCE,
    HELD_STATE, STARTED_STATE,
)
from cyber_lion.enterprise.builder_process_launch import BuilderProcessLaunchBoundary, BuilderProcessLaunchError
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
UTC = timezone.utc


def origin(path="/tmp/a.db"):
    return PersistentAuthorityStoreOrigin(
        "aso:" + D("e"), D("e"), "1.0.0", "/repo", path
    ).validate()


def entry_record(**changes):
    o = origin()
    data = dict(
        builder_entry_permit_id="bep:" + D("1"), builder_entry_permit_digest=D("2"), builder_entry_replay_digest=D("3"),
        repository="DonkeyJJLove/ai_platform", baseline_master_sha=S("a"), baseline_master_tree_sha=S("b"),
        action="BUILD_CANDIDATE", candidate_scope=SCOPE, resource_scope=RESOURCE, authority_epoch=1, authority_state_version=1,
        root_grant_id="root:r22", root_grant_digest=D("4"), current_authority_digest=D("5"), builder_subject_id="builder:r22",
        builder_instance_id="instance:r22", builder_capability_class="DETACHED_CANDIDATE_BUILD_ONLY", builder_identity_digest=D("6"),
        builder_implementation_digest=D("7"), builder_attestation_digest=D("8"), authority_store_origin_id=o.origin_id,
        authority_store_origin_digest=o.origin_digest, issued_at="2026-08-25T14:00:00Z",
    )
    data.update(changes); return PersistentBuilderEntryIssuanceRecord(**data)


def invocation_record(**changes):
    o = origin()
    data = dict(
        builder_invocation_permit_id="bip:" + D("1"), builder_invocation_permit_digest=D("2"), builder_invocation_replay_digest=D("3"),
        source_builder_entry_permit_id="bep:" + D("4"), source_builder_entry_permit_digest=D("5"), repository="DonkeyJJLove/ai_platform",
        baseline_master_sha=S("a"), baseline_master_tree_sha=S("b"), current_baseline_digest=D("6"), action="BUILD_CANDIDATE",
        candidate_scope=SCOPE, resource_scope=RESOURCE, authority_epoch=1, authority_state_version=1, root_grant_id="root:r22",
        root_grant_digest=D("7"), current_authority_digest=D("8"), builder_subject_id="builder:r22", builder_instance_id="instance:r22",
        builder_capability_class="DETACHED_CANDIDATE_BUILD_ONLY", builder_identity_digest=D("9"), builder_implementation_digest=D("a"),
        builder_attestation_digest=D("b"), current_builder_subject_digest=D("c"), authority_store_origin_id=o.origin_id,
        authority_store_origin_digest=o.origin_digest, issued_at="2026-08-25T14:00:00Z",
    )
    data.update(changes); return PersistentBuilderInvocationIssuanceRecord(**data)


def identity(state=HELD_STATE, **changes):
    data=dict(
        launch_id="launch:r22", builder_subject_id="builder:r22", builder_instance_id="instance:r22",
        process_profile_id="bpp:"+D("1"), process_profile_digest=D("1"), launch_policy_digest=D("2"),
        runtime_provider_id="provider:r22", runtime_provider_identity_digest=D("3"), runtime_instance_identity="runtime:r22",
        execution_environment_id="env:r22", process_handle_reference="pidfd:r22", process_identity_token="token:r22",
        execution_gate_id="gate:r22", started_at="2026-08-25T14:00:00Z", state=state,
    )
    data.update(changes); return BuilderProcessIdentity(**data).sealed()


def gate(state=GATE_CLOSED, **changes):
    data=dict(
        execution_gate_id="gate:r22", runtime_instance_identity="runtime:r22", launch_id="launch:r22",
        execution_environment_id="env:r22", builder_entrypoint_digest=D("4"), gate_state=state,
        gate_attestation_digest=D("5"), observed_at="2026-08-25T14:00:01Z",
    )
    data.update(changes); return BuilderExecutionGateEvidence(**data).sealed()


class FakeClock:
    def __init__(self,*values): self.values=list(values); self.calls=0
    def now(self):
        self.calls+=1
        if not self.values: raise AssertionError("unexpected clock read")
        return self.values.pop(0)


class FakeRuntime:
    def __init__(self,*,gate_sequence,started=None,observed=None):
        self.gates=list(gate_sequence); self.started=started or identity(STARTED_STATE); self.observed=observed
        self.commit_calls=0; self.freeze_calls=0
    def observe_gate(self,launch_id):
        if not self.gates: raise AssertionError("unexpected gate observation")
        value=self.gates.pop(0)
        if isinstance(value,Exception): raise value
        return value
    def commit_start(self,request,held,closed): self.commit_calls+=1; return self.started
    def observe_launch(self,launch_id): return self.started if self.observed is None else self.observed
    def freeze_or_kill(self,launch_id): self.freeze_calls+=1


def effect_fence_boundary(effect_now,currentness):
    value=BuilderProcessLaunchBoundary.__new__(BuilderProcessLaunchBoundary)
    value._clock=FakeClock(effect_now); value._currentness=currentness
    return value


def currentness_ok(descriptor):
    return lambda **kwargs:(D("a"),SimpleNamespace(subject_digest=D("b")),descriptor)


class BuilderProcessLaunchTests(unittest.TestCase):
    def test_boundary_requires_effect_clock_and_no_runtime_provider_argument(self):
        self.assertIn("effect_clock", inspect.signature(BuilderProcessLaunchBoundary).parameters)
        params = inspect.signature(BuilderProcessLaunchBoundary.launch).parameters
        self.assertNotIn("runtime_provider", params); self.assertNotIn("trusted_now", params)
        src = inspect.getsource(__import__("cyber_lion.enterprise.builder_process_launch", fromlist=["x"]))
        self.assertIn("observe_gate", src); self.assertIn("GATE_CLOSED", src); self.assertIn("GATE_OPENED_ONCE", src)
        self.assertIn("verify_origin", src)

    def test_store_ready_requires_eleven_tables(self):
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / "a.db"); store = SQLiteAuthorityStateStore(path)
            self.assertEqual(len(store.REQUIRED_TABLES), 11); self.assertTrue(store.ready())
            with sqlite3.connect(path) as connection:
                cols = {row[1] for row in connection.execute("PRAGMA table_info(builder_process_held_materialization)")}
            self.assertIn("execution_gate_id", cols); self.assertIn("execution_gate_digest", cols)

    def test_persistent_held_and_receipt_reject_numeric_pid(self):
        o = origin()
        held = PersistentBuilderProcessHeldMaterialization(
            "launch:x", "bplr:" + D("1"), D("2"), D("1"), "provider:x", D("3"), D("4"), D("5"),
            "runtime:x", "env:x", "pidfd:x", "token:x", D("6"), "gate:x", D("7"), "CLOSED",
            D("8"), D("9"), "HELD_NOT_EXECUTING_BUILDER", "2026-08-25T14:00:00Z",
            "2026-08-25T14:00:01Z", o.origin_id, o.origin_digest,
        ).validate()
        with self.assertRaises(PersistentAuthorityStateError): replace(held, process_handle_reference="123").validate()
        receipt = PersistentBuilderProcessLaunchReceipt(
            "bplx:" + D("1"), D("2"), "bplr:" + D("1"), D("3"), D("1"), "bsa:" + D("4"), D("5"),
            "DonkeyJJLove/ai_platform", S("a"), S("b"), D("6"), D("7"), "bpp:" + D("8"), D("8"),
            D("9"), "provider:x", D("a"), D("b"), D("c"), "runtime:x", "launch:x", "env:x",
            "pidfd:x", "token:x", D("d"), "gate:x", D("e"), D("f"), D("0"),
            "2026-08-25T14:00:00Z", "2026-08-25T14:00:01Z", "BUILDER_PROCESS_START",
            "STARTED_OBSERVED", "CLOSED_TO_OPENED_ONCE", o.origin_id, o.origin_digest,
        ).validate()
        with self.assertRaises(PersistentAuthorityStateError): replace(receipt, process_handle_reference="77").validate()
        with self.assertRaises(PersistentAuthorityStateError): replace(receipt, gate_transition="OPEN").validate()

    def test_concurrent_launch_replay_one_winner(self):
        with tempfile.TemporaryDirectory() as directory:
            store = SQLiteAuthorityStateStore(str(Path(directory) / "a.db")); barrier = threading.Barrier(6); out = []; lock = threading.Lock()
            def worker():
                barrier.wait(); value = store.consume_replay("builder-process-launch", D("1"), "2026-08-25T14:00:00Z")
                with lock: out.append(value)
            threads = [threading.Thread(target=worker) for _ in range(6)]; [thread.start() for thread in threads]; [thread.join() for thread in threads]
            self.assertEqual(out.count(True), 1)

    def test_effect_clock_expiry_after_held_denies_before_commit(self):
        initial=datetime(2026,8,25,14,0,tzinfo=UTC); effect=datetime(2026,8,25,14,1,tzinfo=UTC); descriptor=SimpleNamespace(runtime_instance_identity="runtime:r22")
        def expired(**kwargs):
            self.assertEqual(kwargs["trusted_now"],effect)
            raise BuilderProcessLaunchError("authority currentness failed")
        boundary=effect_fence_boundary(effect,expired); runtime=FakeRuntime(gate_sequence=[gate()])
        with self.assertRaisesRegex(BuilderProcessLaunchError,"authority currentness failed"):
            boundary._commit_after_effect_fence(admission=object(),admitted_authority=object(),descriptor=descriptor,runtime=runtime,request=object(),held=identity(),closed=gate(),initial_now=initial)
        self.assertEqual(boundary._clock.calls,1); self.assertEqual(runtime.commit_calls,0)

    def test_builder_expiry_after_held_denies_before_commit(self):
        initial=datetime(2026,8,25,14,0,tzinfo=UTC); effect=datetime(2026,8,25,14,2,tzinfo=UTC); descriptor=SimpleNamespace(runtime_instance_identity="runtime:r22")
        def expired(**kwargs):
            self.assertEqual(kwargs["trusted_now"],effect)
            raise BuilderProcessLaunchError("builder outside validity")
        boundary=effect_fence_boundary(effect,expired); runtime=FakeRuntime(gate_sequence=[gate()])
        with self.assertRaisesRegex(BuilderProcessLaunchError,"builder outside validity"):
            boundary._commit_after_effect_fence(admission=object(),admitted_authority=object(),descriptor=descriptor,runtime=runtime,request=object(),held=identity(),closed=gate(),initial_now=initial)
        self.assertEqual(runtime.commit_calls,0)

    def test_gate_drift_opened_before_commit_denies_without_commit(self):
        initial=datetime(2026,8,25,14,0,tzinfo=UTC); effect=datetime(2026,8,25,14,1,tzinfo=UTC); descriptor=SimpleNamespace(runtime_instance_identity="runtime:r22")
        boundary=effect_fence_boundary(effect,currentness_ok(descriptor)); runtime=FakeRuntime(gate_sequence=[gate(GATE_OPENED_ONCE)])
        with self.assertRaises(BuilderProcessLaunchError):
            boundary._commit_after_effect_fence(admission=object(),admitted_authority=object(),descriptor=descriptor,runtime=runtime,request=object(),held=identity(),closed=gate(),initial_now=initial)
        self.assertEqual(runtime.commit_calls,0)

    def test_gate_unknown_before_commit_denies_without_commit(self):
        initial=datetime(2026,8,25,14,0,tzinfo=UTC); effect=datetime(2026,8,25,14,1,tzinfo=UTC); descriptor=SimpleNamespace(runtime_instance_identity="runtime:r22")
        boundary=effect_fence_boundary(effect,currentness_ok(descriptor)); runtime=FakeRuntime(gate_sequence=[BuilderProcessLaunchError("unknown gate")])
        with self.assertRaisesRegex(BuilderProcessLaunchError,"unknown gate"):
            boundary._commit_after_effect_fence(admission=object(),admitted_authority=object(),descriptor=descriptor,runtime=runtime,request=object(),held=identity(),closed=gate(),initial_now=initial)
        self.assertEqual(runtime.commit_calls,0)

    def test_post_commit_gate_not_opened_once_contains_and_denies(self):
        initial=datetime(2026,8,25,14,0,tzinfo=UTC); effect=datetime(2026,8,25,14,1,tzinfo=UTC); descriptor=SimpleNamespace(runtime_instance_identity="runtime:r22")
        closed=gate(); boundary=effect_fence_boundary(effect,currentness_ok(descriptor)); runtime=FakeRuntime(gate_sequence=[closed,closed])
        with self.assertRaisesRegex(BuilderProcessLaunchError,"post-commit"):
            boundary._commit_after_effect_fence(admission=object(),admitted_authority=object(),descriptor=descriptor,runtime=runtime,request=object(),held=identity(),closed=closed,initial_now=initial)
        self.assertEqual(runtime.commit_calls,1); self.assertEqual(runtime.freeze_calls,1)

    def test_post_commit_process_identity_drift_contains_and_denies(self):
        initial=datetime(2026,8,25,14,0,tzinfo=UTC); effect=datetime(2026,8,25,14,1,tzinfo=UTC); descriptor=SimpleNamespace(runtime_instance_identity="runtime:r22")
        closed=gate(); opened=gate(GATE_OPENED_ONCE); started=identity(STARTED_STATE); drift=identity(STARTED_STATE,process_identity_token="token:other")
        boundary=effect_fence_boundary(effect,currentness_ok(descriptor)); runtime=FakeRuntime(gate_sequence=[closed,opened],started=started,observed=drift)
        with self.assertRaisesRegex(BuilderProcessLaunchError,"continuity unknown"):
            boundary._commit_after_effect_fence(admission=object(),admitted_authority=object(),descriptor=descriptor,runtime=runtime,request=object(),held=identity(),closed=closed,initial_now=initial)
        self.assertEqual(runtime.commit_calls,1); self.assertEqual(runtime.freeze_calls,1)

    def test_valid_effect_fence_commits_once_after_fresh_time_and_gate(self):
        initial=datetime(2026,8,25,14,0,tzinfo=UTC); effect=datetime(2026,8,25,14,1,tzinfo=UTC); descriptor=SimpleNamespace(runtime_instance_identity="runtime:r22")
        closed=gate(); opened=gate(GATE_OPENED_ONCE); boundary=effect_fence_boundary(effect,currentness_ok(descriptor)); runtime=FakeRuntime(gate_sequence=[closed,opened])
        authority,subject,started,opened_result=boundary._commit_after_effect_fence(admission=object(),admitted_authority=object(),descriptor=descriptor,runtime=runtime,request=object(),held=identity(),closed=closed,initial_now=initial)
        self.assertEqual(authority,D("a")); self.assertEqual(subject.subject_digest,D("b")); self.assertEqual(started.state,STARTED_STATE); self.assertEqual(opened_result.gate_state,GATE_OPENED_ONCE)
        self.assertEqual(runtime.commit_calls,1); self.assertEqual(runtime.freeze_calls,0); self.assertEqual(boundary._clock.calls,1)

    def test_pre_r22_builder_entry_epoch_and_state_floor(self):
        entry_record().validate()
        for changes in ({"authority_epoch": -1},{"authority_epoch": True},{"authority_state_version": 0},{"authority_state_version": True}):
            with self.assertRaises(PersistentAuthorityStateError): entry_record(**changes).validate()

    def test_pre_r22_builder_invocation_epoch_and_state_floor(self):
        invocation_record().validate()
        for changes in ({"authority_epoch": -1},{"authority_epoch": True},{"authority_state_version": 0},{"authority_state_version": True}):
            with self.assertRaises(PersistentAuthorityStateError): invocation_record(**changes).validate()

    def test_pre_r22_binding_finalization_floor(self):
        valid = PersistentBindingFinalization("lion.test", "tenant", "org", "mission", 1, 1, "grant", "root", D("1"), D("2"), D("3"), "nonce", D("4"), "2026-08-25T14:00:00Z")
        valid.validate()
        for changes in ({"epoch":-1},{"epoch":True},{"authority_state_version":0},{"authority_state_version":True}):
            with self.assertRaises(PersistentAuthorityStateError): replace(valid,**changes).validate()

    def test_pre_r22_bootstrap_and_monotonicity_floor(self):
        context = ("lion.test", "tenant", "org", "mission")
        with tempfile.TemporaryDirectory() as directory:
            store = SQLiteAuthorityStateStore(str(Path(directory) / "a.db"))
            for bad_epoch in (-1, True):
                with self.assertRaises(PersistentAuthorityStateError): store.bootstrap_context(context, epoch=bad_epoch)
            store.bootstrap_context(context, epoch=7, revoked_grant_ids=("a",))
            with self.assertRaises(PersistentAuthorityStateError): store.advance_epoch(context, epoch=6, revoked_grant_ids=("a",))
            with self.assertRaises(PersistentAuthorityStateError): store.advance_epoch(context, epoch=7, revoked_grant_ids=())

if __name__ == "__main__": unittest.main()
