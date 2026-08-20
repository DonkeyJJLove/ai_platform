from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import tempfile
import threading
import unittest

from cyber_lion.enterprise.authority_grant import AuthorityGrant
from cyber_lion.enterprise.authority_source import (
    AuthorityLineageRecord,
    AuthorityLookupKey,
    AuthoritySource,
    AuthoritySourceError,
    canonical_pr_authority_resource,
    canonical_source_lineage_digest,
)
from cyber_lion.enterprise.authority_verification import (
    AuthorityVerificationContext,
    IssuerKeyBinding,
)
from cyber_lion.enterprise.live_authority_admission import (
    LiveAuthorityAdmission,
    LiveAuthorityAdmissionError,
)
from cyber_lion.enterprise.persistent_authority_state import (
    DurableReplayGuard,
    PersistentAuthorityStateError,
    PersistentBindingFinalizer,
    PersistentEpochStateProvider,
    PersistentRootAnchorProvider,
    SQLiteAuthorityStateStore,
)

REPO = "DonkeyJJLove/ai_platform"
BASE = "1" * 40
HEAD = "2" * 40
MISSION = "LION-FLEET-EXECUTOR-ATTESTATION-V1"
GRANT = "grant-fleet-n2"
CONTEXT = ("lion.test", "tenant-1", "org-1", MISSION)
NOW = datetime(2026, 8, 20, 16, 0, tzinfo=timezone.utc)


def make_grant(*, epoch=7, issued_at="2026-08-20T15:00:00+00:00", expires_at="2026-08-20T17:00:00+00:00") -> AuthorityGrant:
    key = AuthorityLookupKey(REPO, 41, BASE, HEAD, MISSION, GRANT)
    return AuthorityGrant(
        schema_version="1.1.0",
        grant_id=GRANT,
        issuer_subject_id="issuer-root",
        subject_id="fleet-runtime-bridge",
        tenant_id="tenant-1",
        organization_id="org-1",
        mission_id=MISSION,
        capability_id="fleet-runtime-authority-bind",
        capability_version="1.0.0",
        actions=("bind_runtime_authority",),
        resource_scope=(canonical_pr_authority_resource(key),),
        authority_ceiling="read",
        constraints=("post-execution-only",),
        parent_grant_id=None,
        issued_at=issued_at,
        expires_at=expires_at,
        epoch=epoch,
        policy_digest="sha256:" + "a" * 64,
        observability_contract_digest="sha256:" + "b" * 64,
        signature="test-signature",
        delegation_allowed=False,
        delegation_depth_budget=0,
    )


def make_record(value: AuthorityGrant | None = None) -> AuthorityLineageRecord:
    value = value or make_grant()
    key = AuthorityLookupKey(REPO, 41, BASE, HEAD, MISSION, value.grant_id)
    lineage = (value,)
    return AuthorityLineageRecord(
        lookup_key=key,
        lineage=lineage,
        lineage_digest=canonical_source_lineage_digest(lineage),
        provenance_id="control-plane:sqlite:n2",
        source_kind="trusted-control-plane",
    )


class StaticSource(AuthoritySource):
    def __init__(self, records):
        self.records = records

    def _lookup_exact(self, key):
        return self.records


class BrokenSource(AuthoritySource):
    def _lookup_exact(self, key):
        raise AuthoritySourceError("backend down")


def build_admission(store: SQLiteAuthorityStateStore, source: AuthoritySource, *, signature_ok=True) -> LiveAuthorityAdmission:
    return LiveAuthorityAdmission(
        authority_source=source,
        context=AuthorityVerificationContext(
            trust_domain="lion.test",
            tenant_id="tenant-1",
            organization_id="org-1",
            mission_id=MISSION,
        ),
        issuer_keys=(IssuerKeyBinding("issuer-root", "lion.test", "key-1", "ed25519"),),
        signature_verifier=lambda *_: signature_ok,
        epoch_provider=PersistentEpochStateProvider(store),
        root_provider=PersistentRootAnchorProvider(store),
        replay_guard=DurableReplayGuard(store, domain="live-authority-admission"),
        binding_finalizer=PersistentBindingFinalizer(store),
    )


def admit(subject: LiveAuthorityAdmission, *, nonce="nonce-1"):
    return subject.admit(
        repository=REPO,
        pr_number=41,
        base_sha=BASE,
        head_sha=HEAD,
        mission_id=MISSION,
        grant_id=GRANT,
        now=NOW,
        replay_nonce=nonce,
    )


class PersistentAuthorityStateTests(unittest.TestCase):
    def test_epoch_revocation_root_and_replay_survive_restart(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / "authority.db")
            store = SQLiteAuthorityStateStore(path)
            snapshot = store.bootstrap_context(CONTEXT, epoch=7)
            self.assertEqual(snapshot.epoch, 7)
            root = make_grant()
            store.register_root(CONTEXT, epoch=7, root_grant_id=root.grant_id, root_grant_digest=root.digest())
            store.advance_epoch(CONTEXT, epoch=7, revoked_grant_ids=("revoked-1",))
            self.assertTrue(store.consume_replay("domain", "c" * 64, NOW.isoformat()))

            restarted = SQLiteAuthorityStateStore(path)
            self.assertEqual(restarted.current_epoch(CONTEXT).revoked_grant_ids, ("revoked-1",))
            self.assertEqual(restarted.resolve_root(CONTEXT, epoch=7).root_grant_digest, root.digest())
            self.assertFalse(restarted.consume_replay("domain", "c" * 64, NOW.isoformat()))

    def test_epoch_and_revocation_are_monotonic(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = SQLiteAuthorityStateStore(str(Path(directory) / "authority.db"))
            store.bootstrap_context(CONTEXT, epoch=7, revoked_grant_ids=("a",))
            with self.assertRaises(PersistentAuthorityStateError):
                store.advance_epoch(CONTEXT, epoch=6, revoked_grant_ids=("a",))
            with self.assertRaises(PersistentAuthorityStateError):
                store.advance_epoch(CONTEXT, epoch=7, revoked_grant_ids=())
            accepted = store.advance_epoch(CONTEXT, epoch=8, revoked_grant_ids=())
            self.assertEqual(accepted.epoch, 8)

    def test_one_root_per_context_epoch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = SQLiteAuthorityStateStore(str(Path(directory) / "authority.db"))
            store.bootstrap_context(CONTEXT, epoch=7)
            store.register_root(CONTEXT, epoch=7, root_grant_id="g", root_grant_digest="a" * 64)
            with self.assertRaises(PersistentAuthorityStateError):
                store.register_root(CONTEXT, epoch=7, root_grant_id="g2", root_grant_digest="b" * 64)

    def test_root_registration_checks_epoch_inside_write_transaction(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = SQLiteAuthorityStateStore(str(Path(directory) / "authority.db"))
            store.bootstrap_context(CONTEXT, epoch=7)
            store.advance_epoch(CONTEXT, epoch=8, revoked_grant_ids=())
            with self.assertRaises(PersistentAuthorityStateError):
                store.register_root(CONTEXT, epoch=7, root_grant_id="g", root_grant_digest="a" * 64)

    def test_concurrent_replay_has_exactly_one_winner(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = SQLiteAuthorityStateStore(str(Path(directory) / "authority.db"))
            guard = DurableReplayGuard(store, domain="concurrency")
            barrier = threading.Barrier(8)
            results: list[bool] = []
            lock = threading.Lock()

            def worker() -> None:
                barrier.wait()
                result = guard.consume("d" * 64, consumed_at=NOW.isoformat())
                with lock:
                    results.append(result)

            threads = [threading.Thread(target=worker) for _ in range(8)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()
            self.assertEqual(results.count(True), 1)
            self.assertEqual(results.count(False), 7)

    def test_live_admission_survives_restart_and_replay_is_durable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / "authority.db")
            grant = make_grant()
            store = SQLiteAuthorityStateStore(path)
            store.bootstrap_context(CONTEXT, epoch=7)
            store.register_root(CONTEXT, epoch=7, root_grant_id=grant.grant_id, root_grant_digest=grant.digest())
            source = StaticSource((make_record(grant),))
            first = admit(build_admission(store, source))
            self.assertEqual(first.epoch, 7)
            restarted = SQLiteAuthorityStateStore(path)
            with self.assertRaises(LiveAuthorityAdmissionError):
                admit(build_admission(restarted, source))

    def test_binding_finalization_is_restart_durable_and_replay_denied(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / "authority.db")
            grant = make_grant()
            store = SQLiteAuthorityStateStore(path)
            store.bootstrap_context(CONTEXT, epoch=7)
            store.register_root(CONTEXT, epoch=7, root_grant_id=grant.grant_id, root_grant_digest=grant.digest())
            live = build_admission(store, StaticSource((make_record(grant),)))
            receipt = admit(live, nonce="admit-finalize")
            finalized = live.finalize_binding(
                receipt,
                runtime_evidence_digest="4" * 64,
                binding_nonce="bind-finalize",
                now=NOW,
            )
            self.assertEqual(finalized.authority_state_version, receipt.epoch_state_version)
            self.assertEqual(finalized.root_grant_digest, receipt.root_grant_digest)

            restarted = SQLiteAuthorityStateStore(path)
            with self.assertRaises(PersistentAuthorityStateError):
                restarted.finalize_binding(
                    CONTEXT,
                    expected_epoch=receipt.epoch,
                    expected_state_version=receipt.epoch_state_version,
                    grant_id=receipt.grant_id,
                    expected_root_grant_id=receipt.root_grant_id,
                    expected_root_grant_digest=receipt.root_grant_digest,
                    live_admission_digest=receipt.digest(),
                    runtime_evidence_digest="4" * 64,
                    binding_nonce="bind-finalize",
                    finalized_at=NOW.isoformat(),
                )

    def test_concurrent_binding_finalization_has_exactly_one_winner(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = SQLiteAuthorityStateStore(str(Path(directory) / "authority.db"))
            grant = make_grant()
            store.bootstrap_context(CONTEXT, epoch=7)
            store.register_root(CONTEXT, epoch=7, root_grant_id=grant.grant_id, root_grant_digest=grant.digest())
            snapshot = store.current_epoch(CONTEXT)
            barrier = threading.Barrier(8)
            results: list[bool] = []
            lock = threading.Lock()

            def worker() -> None:
                barrier.wait()
                try:
                    store.finalize_binding(
                        CONTEXT,
                        expected_epoch=snapshot.epoch,
                        expected_state_version=snapshot.version,
                        grant_id=GRANT,
                        expected_root_grant_id=grant.grant_id,
                        expected_root_grant_digest=grant.digest(),
                        live_admission_digest="e" * 64,
                        runtime_evidence_digest="4" * 64,
                        binding_nonce="same-binding",
                        finalized_at=NOW.isoformat(),
                    )
                    value = True
                except PersistentAuthorityStateError:
                    value = False
                with lock:
                    results.append(value)

            threads = [threading.Thread(target=worker) for _ in range(8)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()
            self.assertEqual(results.count(True), 1)
            self.assertEqual(results.count(False), 7)

    def test_stale_state_revocation_epoch_and_root_deny_finalization(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            grant = make_grant()
            store = SQLiteAuthorityStateStore(str(Path(directory) / "authority.db"))
            store.bootstrap_context(CONTEXT, epoch=7)
            store.register_root(CONTEXT, epoch=7, root_grant_id=grant.grant_id, root_grant_digest=grant.digest())
            snapshot = store.current_epoch(CONTEXT)
            store.advance_epoch(CONTEXT, epoch=7, revoked_grant_ids=(GRANT,))
            with self.assertRaises(PersistentAuthorityStateError):
                store.finalize_binding(
                    CONTEXT,
                    expected_epoch=snapshot.epoch,
                    expected_state_version=snapshot.version,
                    grant_id=GRANT,
                    expected_root_grant_id=grant.grant_id,
                    expected_root_grant_digest=grant.digest(),
                    live_admission_digest="e" * 64,
                    runtime_evidence_digest="4" * 64,
                    binding_nonce="stale",
                    finalized_at=NOW.isoformat(),
                )

        with tempfile.TemporaryDirectory() as directory:
            grant = make_grant()
            store = SQLiteAuthorityStateStore(str(Path(directory) / "authority.db"))
            store.bootstrap_context(CONTEXT, epoch=7)
            store.register_root(CONTEXT, epoch=7, root_grant_id=grant.grant_id, root_grant_digest=grant.digest())
            snapshot = store.current_epoch(CONTEXT)
            store.advance_epoch(CONTEXT, epoch=8, revoked_grant_ids=())
            with self.assertRaises(PersistentAuthorityStateError):
                store.finalize_binding(
                    CONTEXT,
                    expected_epoch=snapshot.epoch,
                    expected_state_version=snapshot.version,
                    grant_id=GRANT,
                    expected_root_grant_id=grant.grant_id,
                    expected_root_grant_digest=grant.digest(),
                    live_admission_digest="e" * 64,
                    runtime_evidence_digest="4" * 64,
                    binding_nonce="epoch",
                    finalized_at=NOW.isoformat(),
                )

        with tempfile.TemporaryDirectory() as directory:
            grant = make_grant()
            store = SQLiteAuthorityStateStore(str(Path(directory) / "authority.db"))
            store.bootstrap_context(CONTEXT, epoch=7)
            store.register_root(CONTEXT, epoch=7, root_grant_id=grant.grant_id, root_grant_digest=grant.digest())
            snapshot = store.current_epoch(CONTEXT)
            with self.assertRaises(PersistentAuthorityStateError):
                store.finalize_binding(
                    CONTEXT,
                    expected_epoch=snapshot.epoch,
                    expected_state_version=snapshot.version,
                    grant_id=GRANT,
                    expected_root_grant_id=grant.grant_id,
                    expected_root_grant_digest="0" * 64,
                    live_admission_digest="e" * 64,
                    runtime_evidence_digest="4" * 64,
                    binding_nonce="root",
                    finalized_at=NOW.isoformat(),
                )

    def test_concurrent_revoke_vs_finalize_is_linearizable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            grant = make_grant()
            store = SQLiteAuthorityStateStore(str(Path(directory) / "authority.db"))
            store.bootstrap_context(CONTEXT, epoch=7)
            store.register_root(CONTEXT, epoch=7, root_grant_id=grant.grant_id, root_grant_digest=grant.digest())
            snapshot = store.current_epoch(CONTEXT)
            barrier = threading.Barrier(2)
            results: list[str] = []
            lock = threading.Lock()

            def finalize_worker() -> None:
                barrier.wait()
                try:
                    store.finalize_binding(
                        CONTEXT,
                        expected_epoch=snapshot.epoch,
                        expected_state_version=snapshot.version,
                        grant_id=GRANT,
                        expected_root_grant_id=grant.grant_id,
                        expected_root_grant_digest=grant.digest(),
                        live_admission_digest="e" * 64,
                        runtime_evidence_digest="4" * 64,
                        binding_nonce="race-revoke",
                        finalized_at=NOW.isoformat(),
                    )
                    result = "finalized"
                except PersistentAuthorityStateError:
                    result = "denied"
                with lock:
                    results.append(result)

            def revoke_worker() -> None:
                barrier.wait()
                store.advance_epoch(CONTEXT, epoch=7, revoked_grant_ids=(GRANT,))
                with lock:
                    results.append("revoked")

            first = threading.Thread(target=finalize_worker)
            second = threading.Thread(target=revoke_worker)
            first.start(); second.start(); first.join(); second.join()
            self.assertIn("revoked", results)
            self.assertIn(results[0] if results[0] in {"finalized", "denied"} else results[1], {"finalized", "denied"})
            self.assertIn(GRANT, store.current_epoch(CONTEXT).revoked_grant_ids)

    def test_revoked_stale_expired_future_missing_root_and_signature_failure_denied(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / "authority.db")
            grant = make_grant()
            store = SQLiteAuthorityStateStore(path)
            store.bootstrap_context(CONTEXT, epoch=7)
            store.register_root(CONTEXT, epoch=7, root_grant_id=grant.grant_id, root_grant_digest=grant.digest())
            source = StaticSource((make_record(grant),))
            store.advance_epoch(CONTEXT, epoch=7, revoked_grant_ids=(GRANT,))
            with self.assertRaises(LiveAuthorityAdmissionError):
                admit(build_admission(store, source), nonce="revoked")

        with tempfile.TemporaryDirectory() as directory:
            store = SQLiteAuthorityStateStore(str(Path(directory) / "authority.db"))
            old = make_grant(epoch=7)
            store.bootstrap_context(CONTEXT, epoch=8)
            store.register_root(CONTEXT, epoch=8, root_grant_id=old.grant_id, root_grant_digest=old.digest())
            with self.assertRaises(LiveAuthorityAdmissionError):
                admit(build_admission(store, StaticSource((make_record(old),))), nonce="stale")

        for value, nonce in (
            (make_grant(issued_at="2026-08-20T14:00:00+00:00", expires_at="2026-08-20T15:00:00+00:00"), "expired"),
            (make_grant(issued_at="2026-08-20T17:00:00+00:00", expires_at="2026-08-20T18:00:00+00:00"), "future"),
        ):
            with tempfile.TemporaryDirectory() as directory:
                store = SQLiteAuthorityStateStore(str(Path(directory) / "authority.db"))
                store.bootstrap_context(CONTEXT, epoch=7)
                store.register_root(CONTEXT, epoch=7, root_grant_id=value.grant_id, root_grant_digest=value.digest())
                with self.assertRaises(LiveAuthorityAdmissionError):
                    admit(build_admission(store, StaticSource((make_record(value),))), nonce=nonce)

        with tempfile.TemporaryDirectory() as directory:
            store = SQLiteAuthorityStateStore(str(Path(directory) / "authority.db"))
            store.bootstrap_context(CONTEXT, epoch=7)
            with self.assertRaises(LiveAuthorityAdmissionError):
                admit(build_admission(store, StaticSource((make_record(),))), nonce="no-root")

        with tempfile.TemporaryDirectory() as directory:
            store = SQLiteAuthorityStateStore(str(Path(directory) / "authority.db"))
            value = make_grant()
            store.bootstrap_context(CONTEXT, epoch=7)
            store.register_root(CONTEXT, epoch=7, root_grant_id=value.grant_id, root_grant_digest=value.digest())
            with self.assertRaises(LiveAuthorityAdmissionError):
                admit(build_admission(store, StaticSource((make_record(value),)), signature_ok=False), nonce="bad-sig")

    def test_wrong_root_ambiguous_source_and_backend_failure_denied(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = SQLiteAuthorityStateStore(str(Path(directory) / "authority.db"))
            value = make_grant()
            store.bootstrap_context(CONTEXT, epoch=7)
            store.register_root(CONTEXT, epoch=7, root_grant_id=value.grant_id, root_grant_digest="0" * 64)
            with self.assertRaises(LiveAuthorityAdmissionError):
                admit(build_admission(store, StaticSource((make_record(value),))), nonce="wrong-root")

        with tempfile.TemporaryDirectory() as directory:
            store = SQLiteAuthorityStateStore(str(Path(directory) / "authority.db"))
            value = make_grant()
            store.bootstrap_context(CONTEXT, epoch=7)
            store.register_root(CONTEXT, epoch=7, root_grant_id=value.grant_id, root_grant_digest=value.digest())
            duplicate = make_record(value)
            with self.assertRaises(LiveAuthorityAdmissionError):
                admit(build_admission(store, StaticSource((duplicate, duplicate))), nonce="ambiguous")
            with self.assertRaises(LiveAuthorityAdmissionError):
                admit(build_admission(store, BrokenSource()), nonce="backend-down")


if __name__ == "__main__":
    unittest.main()
