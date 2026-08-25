from __future__ import annotations
import inspect
import sqlite3
from pathlib import Path
import tempfile
import threading
import unittest

from cyber_lion.enterprise.builder_process_launch import BuilderProcessLaunchBoundary
from cyber_lion.enterprise.persistent_authority_state import (
    PersistentAuthorityStateError, PersistentAuthorityStoreOrigin,
    PersistentBuilderProcessLaunchIntent, PersistentBuilderProcessHeldMaterialization,
    PersistentBuilderProcessLaunchReceipt, SQLiteAuthorityStateStore,
)

D=lambda c:c*64
S=lambda c:c*40

def origin(path):
    return PersistentAuthorityStoreOrigin("aso:"+D("e"),D("e"),"1.0.0","/repo",path).validate()

def intent(**changes):
    data=dict(launch_request_id="bplr:"+D("1"),launch_request_digest=D("2"),launch_replay_digest=D("1"),
        source_builder_start_admission_id="bsa:"+D("3"),source_builder_start_admission_digest=D("4"),
        source_builder_start_admission_replay_digest=D("3"),source_builder_start_issuance_record_id="bsair:bsa:"+D("3"),
        source_builder_start_issuance_record_digest=D("5"),repository="DonkeyJJLove/ai_platform",baseline_master_sha=S("a"),baseline_master_tree_sha=S("b"),
        authority_epoch=1,authority_state_version=1,root_grant_id="root",root_grant_digest=D("6"),expected_current_authority_digest=D("7"),
        builder_subject_id="builder",builder_instance_id="instance",builder_identity_digest=D("8"),builder_implementation_digest=D("9"),
        builder_attestation_digest=D("a"),expected_builder_subject_digest=D("b"),process_profile_id="bpp:"+D("c"),process_profile_digest=D("c"),
        launch_policy_digest=D("d"),runtime_provider_id="provider:r22",runtime_provider_identity_digest=D("e"),
        runtime_provider_implementation_digest=D("f"),runtime_provider_attestation_digest=D("0"),runtime_instance_identity="runtime:r22:1",
        authority_store_origin_id="aso:"+D("e"),authority_store_origin_digest=D("e"),prepared_at="2026-08-25T14:00:00Z")
    data.update(changes); return PersistentBuilderProcessLaunchIntent(**data).validate()

def held(**changes):
    data=dict(launch_id="launch:r22",launch_request_id="bplr:"+D("1"),launch_request_digest=D("2"),launch_replay_digest=D("1"),
        provider_id="provider:r22",provider_identity_digest=D("3"),provider_implementation_digest=D("4"),provider_attestation_digest=D("5"),
        runtime_instance_identity="runtime:r22:1",execution_environment_id="env:r22",process_handle_reference="pidfd:r22:1",
        process_identity_token="token:r22",held_identity_digest=D("6"),state="HELD_NOT_EXECUTING_BUILDER",
        prepared_at="2026-08-25T14:00:00Z",observed_at="2026-08-25T14:00:01Z",authority_store_origin_id="aso:"+D("e"),authority_store_origin_digest=D("e"))
    data.update(changes); return PersistentBuilderProcessHeldMaterialization(**data).validate()

def receipt(**changes):
    data=dict(launch_receipt_id="bplx:"+D("1"),launch_receipt_digest=D("2"),launch_request_id="bplr:"+D("1"),launch_request_digest=D("3"),launch_replay_digest=D("1"),
        source_builder_start_admission_id="bsa:"+D("4"),source_builder_start_admission_digest=D("5"),repository="DonkeyJJLove/ai_platform",baseline_master_sha=S("a"),baseline_master_tree_sha=S("b"),
        authority_digest_at_launch=D("6"),builder_subject_digest_at_launch=D("7"),process_profile_id="bpp:"+D("8"),process_profile_digest=D("8"),launch_policy_digest=D("9"),
        runtime_provider_id="provider:r22",runtime_provider_identity_digest=D("a"),runtime_provider_implementation_digest=D("b"),runtime_provider_attestation_digest=D("c"),
        runtime_instance_identity="runtime:r22:1",launch_id="launch:r22",execution_environment_id="env:r22",process_handle_reference="pidfd:r22:1",process_identity_token="token:r22",process_identity_digest=D("d"),
        launch_started_at="2026-08-25T14:00:00Z",launch_observed_at="2026-08-25T14:00:01Z",effect_class="BUILDER_PROCESS_START",effect_state="STARTED_OBSERVED",
        authority_store_origin_id="aso:"+D("e"),authority_store_origin_digest=D("e"))
    data.update(changes); return PersistentBuilderProcessLaunchReceipt(**data).validate()

class BuilderProcessLaunchTests(unittest.TestCase):
    def test_boundary_has_no_direct_os_or_repository_effect_implementation(self):
        source=inspect.getsource(__import__("cyber_lion.enterprise.builder_process_launch",fromlist=["x"]))
        for forbidden in ("import subprocess", "os.fork", "os.exec", "ExecutorSandbox", "RuntimeCompositionRoot", "repository_mutation_pep"):
            self.assertNotIn(forbidden,source)
        self.assertIn("prepare_launch",source); self.assertIn("observe_held",source); self.assertIn("commit_start",source); self.assertIn("freeze_or_kill",source)

    def test_launch_caller_cannot_supply_executable_provider(self):
        params=set(inspect.signature(BuilderProcessLaunchBoundary.launch).parameters)
        self.assertNotIn("runtime_provider",params)
        constructor=set(inspect.signature(BuilderProcessLaunchBoundary).parameters)
        self.assertIn("provider_source",constructor)

    def test_store_ready_requires_eleven_tables(self):
        with tempfile.TemporaryDirectory() as directory:
            path=str(Path(directory)/"authority.sqlite"); store=SQLiteAuthorityStateStore(path)
            self.assertEqual(len(store.REQUIRED_TABLES),11); self.assertTrue(store.ready())
            with sqlite3.connect(path) as c:names={r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            for name in ("builder_process_launch_intent","builder_process_held_materialization","builder_process_launch_receipt"):self.assertIn(name,names)
            with sqlite3.connect(path) as c:c.execute("DROP TABLE builder_process_held_materialization")
            self.assertFalse(store.ready())

    def test_launch_intent_held_and_receipt_are_exact_and_unique(self):
        with tempfile.TemporaryDirectory() as directory:
            path=str(Path(directory)/"authority.sqlite"); store=SQLiteAuthorityStateStore(path); store.register_authority_store_origin(origin(path))
            i=intent(); store.record_builder_process_launch_intent(i); self.assertEqual(store.resolve_builder_process_launch_intent(i.launch_request_id),i)
            h=held(); store.record_builder_process_held_materialization(h); self.assertEqual(store.resolve_builder_process_held_materialization(h.launch_id),h)
            for changed in ({"launch_id":"launch:r22:2"},{"held_identity_digest":D("f")},{"process_identity_token":"token:r22:2"}):
                with self.assertRaises(PersistentAuthorityStateError):store.record_builder_process_held_materialization(held(**changed))
            r=receipt(); store.record_builder_process_launch_receipt(r); self.assertEqual(store.resolve_builder_process_launch_receipt(r.launch_receipt_id),r)

    def test_concurrent_launch_replay_has_single_winner(self):
        with tempfile.TemporaryDirectory() as directory:
            store=SQLiteAuthorityStateStore(str(Path(directory)/"authority.sqlite")); barrier=threading.Barrier(8); values=[]; lock=threading.Lock()
            def worker():
                barrier.wait();ok=store.consume_replay("builder-process-launch",D("1"),"2026-08-25T14:00:00Z")
                with lock:values.append(ok)
            ts=[threading.Thread(target=worker) for _ in range(8)];[t.start() for t in ts];[t.join() for t in ts]
            self.assertEqual(values.count(True),1);self.assertEqual(values.count(False),7)

    def test_durable_held_is_before_final_currentness_and_commit(self):
        source=inspect.getsource(BuilderProcessLaunchBoundary.launch)
        self.assertLess(source.index("record_builder_process_held_materialization"),source.index("_currentness"))
        self.assertLess(source.index("_currentness"),source.index("commit_start"))

    def test_restart_recovery_never_commits_start(self):
        source=inspect.getsource(BuilderProcessLaunchBoundary.contain_held_after_restart)
        self.assertIn("resolve_builder_process_held_materialization",source)
        self.assertIn("observe_held",source);self.assertIn("freeze_or_kill",source)
        self.assertNotIn("commit_start",source)

    def test_pre_r22_exact_lookup_binding_checks_are_restored(self):
        source=inspect.getsource(SQLiteAuthorityStateStore)
        for marker in (
            "builder entry issuance lookup binding mismatch",
            "builder invocation issuance lookup binding mismatch",
            "builder invocation consumption issuance lookup binding mismatch",
            "builder start admission issuance lookup binding mismatch",
        ):
            self.assertIn(marker,source)

if __name__=="__main__":unittest.main()
