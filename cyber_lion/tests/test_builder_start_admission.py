from __future__ import annotations

from dataclasses import replace
import inspect
import sqlite3
from pathlib import Path
import tempfile
import threading
import unittest

from cyber_lion.contracts.builder_start_admission import compute_launch_policy_digest, compute_process_profile_digest
from cyber_lion.enterprise.builder_start_admission import BuilderStartAdmissionEngine
from cyber_lion.enterprise.persistent_authority_state import (
    PersistentAuthorityStateError,
    PersistentAuthorityStoreOrigin,
    PersistentBuilderInvocationConsumptionIssuanceRecord,
    PersistentBuilderStartAdmissionIssuanceRecord,
    SQLiteAuthorityStateStore,
)

D = lambda c: c * 64
S = lambda c: c * 40
REPO = "DonkeyJJLove/ai_platform"
SCOPE = ("cyber_lion/example.py",)
RES = (f"repo-path:{REPO}:cyber_lion/example.py",)


def origin(path: str) -> PersistentAuthorityStoreOrigin:
    return PersistentAuthorityStoreOrigin(
        origin_id="aso:" + D("e"), origin_digest=D("e"), runtime_factory_version="1.0.0",
        repository_root="/repo", canonical_database_path=path,
    ).validate()


def r20_record(**changes):
    value = PersistentBuilderInvocationConsumptionIssuanceRecord(
        invocation_consumption_permit_id="bicp:" + D("1"), invocation_consumption_permit_digest=D("2"),
        invocation_consumption_replay_digest=D("1"), source_builder_invocation_permit_id="bip:" + D("3"),
        source_builder_invocation_permit_digest=D("4"), source_builder_invocation_replay_digest=D("3"),
        source_builder_entry_permit_id="bep:" + D("5"), source_builder_entry_permit_digest=D("6"),
        repository=REPO, baseline_master_sha=S("a"), baseline_master_tree_sha=S("b"), current_baseline_digest=D("7"),
        action="BUILD_CANDIDATE", candidate_scope=SCOPE, resource_scope=RES, authority_epoch=1, authority_state_version=1,
        root_grant_id="root", root_grant_digest=D("c"), current_authority_digest=D("d"), builder_subject_id="builder",
        builder_instance_id="instance", builder_capability_class="DETACHED_CANDIDATE_BUILD_ONLY", builder_identity_digest=D("8"),
        builder_implementation_digest=D("9"), builder_attestation_digest=D("a"), current_builder_subject_digest=D("b"),
        authority_store_origin_id="aso:" + D("e"), authority_store_origin_digest=D("e"), issued_at="2026-08-25T12:00:00+00:00",
    )
    return replace(value, **changes).validate()


def r21_record(**changes):
    value = PersistentBuilderStartAdmissionIssuanceRecord(
        builder_start_admission_id="bsa:" + D("1"), builder_start_admission_digest=D("2"),
        builder_start_admission_replay_digest=D("1"), source_invocation_consumption_permit_id="bicp:" + D("3"),
        source_invocation_consumption_permit_digest=D("4"), source_invocation_consumption_replay_digest=D("3"),
        source_builder_invocation_permit_id="bip:" + D("5"), source_builder_invocation_permit_digest=D("6"),
        source_builder_entry_permit_id="bep:" + D("7"), source_builder_entry_permit_digest=D("8"), repository=REPO,
        baseline_master_sha=S("a"), baseline_master_tree_sha=S("b"), current_baseline_digest=D("9"), action="BUILD_CANDIDATE",
        candidate_scope=SCOPE, resource_scope=RES, authority_epoch=1, authority_state_version=1, root_grant_id="root",
        root_grant_digest=D("a"), current_authority_digest=D("b"), builder_subject_id="builder", builder_instance_id="instance",
        builder_capability_class="DETACHED_CANDIDATE_BUILD_ONLY", builder_identity_digest=D("c"), builder_implementation_digest=D("d"),
        builder_attestation_digest=D("e"), current_builder_subject_digest=D("f"), process_profile_id="bpp:" + D("0"),
        process_profile_digest=D("0"), launch_policy_digest=D("1"), authority_store_origin_id="aso:" + D("e"),
        authority_store_origin_digest=D("e"), issued_at="2026-08-25T12:10:00+00:00",
    )
    return replace(value, **changes).validate()


class BuilderStartAdmissionTests(unittest.TestCase):
    def test_constructor_has_no_caller_selected_store_or_profile_surface(self):
        params = set(inspect.signature(BuilderStartAdmissionEngine).parameters)
        for forbidden in ("store", "origin", "replay_guard", "issuance_source", "process_profile", "launch_policy"):
            self.assertNotIn(forbidden, params)

    def test_no_effect_surface(self):
        BuilderStartAdmissionEngine.assert_no_effect_surface()
        for name in ("start_builder", "spawn", "popen", "fork", "exec", "build_candidate", "allocate_workspace"):
            self.assertFalse(hasattr(BuilderStartAdmissionEngine, name))

    def test_process_profile_and_launch_policy_are_deterministic(self):
        kwargs = dict(repository=REPO, action="BUILD_CANDIDATE", candidate_scope=SCOPE, resource_scope=RES,
                      builder_subject_id="builder-R21", builder_instance_id="instance-21", builder_capability_class="DETACHED_CANDIDATE_BUILD_ONLY",
                      builder_identity_digest=D("8"), builder_implementation_digest=D("9"), builder_attestation_digest=D("a"), current_builder_subject_digest=D("b"))
        self.assertEqual(compute_process_profile_digest(**kwargs), compute_process_profile_digest(**kwargs))
        self.assertEqual(compute_launch_policy_digest(), compute_launch_policy_digest())

    def test_canonical_store_owns_r20_r21_schema_and_ready(self):
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / "authority.sqlite")
            store = SQLiteAuthorityStateStore(path)
            self.assertTrue(store.ready())
            with sqlite3.connect(path) as c:
                tables = {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            self.assertIn("builder_invocation_consumption_issuance", tables)
            self.assertIn("builder_start_admission_issuance", tables)
            with sqlite3.connect(path) as c:
                c.execute("DROP TABLE builder_invocation_consumption_issuance")
            self.assertFalse(store.ready())

    def test_r20_r21_origin_and_unique_id_digest_replay_are_enforced(self):
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / "authority.sqlite")
            store = SQLiteAuthorityStateStore(path); store.register_authority_store_origin(origin(path))
            a = r20_record(); store.record_builder_invocation_consumption_issuance(a)
            self.assertEqual(store.resolve_builder_invocation_consumption_issuance(a.invocation_consumption_permit_id), a)
            for changed in (
                {"invocation_consumption_permit_id": "bicp:" + D("f")},
                {"invocation_consumption_permit_digest": D("f")},
                {"invocation_consumption_replay_digest": D("f")},
            ):
                with self.assertRaises(PersistentAuthorityStateError):
                    store.record_builder_invocation_consumption_issuance(r20_record(**changed))
            b = r21_record(); store.record_builder_start_admission_issuance(b)
            self.assertEqual(store.resolve_builder_start_admission_issuance(b.builder_start_admission_id), b)
            with self.assertRaises(PersistentAuthorityStateError):
                store.record_builder_start_admission_issuance(r21_record(authority_store_origin_id="aso:"+D("f"), authority_store_origin_digest=D("f")))

    def test_concurrent_r21_recording_has_single_winner(self):
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / "authority.sqlite")
            store = SQLiteAuthorityStateStore(path); store.register_authority_store_origin(origin(path)); value = r21_record()
            barrier = threading.Barrier(6); results=[]; lock=threading.Lock()
            def worker():
                barrier.wait()
                try: store.record_builder_start_admission_issuance(value); ok=True
                except PersistentAuthorityStateError: ok=False
                with lock: results.append(ok)
            threads=[threading.Thread(target=worker) for _ in range(6)]
            [t.start() for t in threads]; [t.join() for t in threads]
            self.assertEqual(results.count(True),1); self.assertEqual(results.count(False),5)

if __name__ == "__main__": unittest.main()
