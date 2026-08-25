from __future__ import annotations

from dataclasses import replace
from datetime import datetime
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from cyber_lion.contracts.builder_entry_permit import (
    BUILDER_CAPABILITY_CLASS,
    SCHEMA_VERSION as ENTRY_SCHEMA,
    BuilderEntryPermit,
    TrustedBuilderSubject,
    compute_builder_entry_replay_digest,
)
from cyber_lion.contracts.candidate_build_authorization import TrustedRepositoryBaseline
from cyber_lion.enterprise.builder_entry_permit import PinnedTrustedBuilderSubjectSource
from cyber_lion.enterprise.builder_invocation_permit import (
    BuilderInvocationPermitEngine,
    BuilderInvocationPermitError,
    PersistentBuilderEntryIssuanceSource,
)
from cyber_lion.enterprise.candidate_build_authorization import (
    LiveAdmittedResourceAuthority,
    LiveResourceAuthorityAdmission,
)
from cyber_lion.enterprise.persistent_authority_state import (
    PersistentAuthorityStoreOrigin,
    PersistentBuilderEntryIssuanceRecord,
    SQLiteAuthorityStateStore,
)
from cyber_lion.enterprise.trusted_control_plane_runtime import (
    build_authority_state_store,
    verify_authority_state_store_origin,
)

D = lambda c: c * 64
REPO = "DonkeyJJLove/ai_platform"
MASTER = "a94882bb80349482c287b76e027c93fe1ed6f1fe"
TREE = "886fbefc79b82b405e0400e53fe95bfc420f4c67"
SCOPE = ("cyber_lion/example.py",)
RES = (f"repo-path:{REPO}:cyber_lion/example.py",)
NOW = datetime.fromisoformat("2026-08-25T08:25:00+00:00")


def baseline(sha=MASTER, tree=TREE):
    return TrustedRepositoryBaseline(REPO, sha, tree, "2026-08-25T08:24:00+00:00")


def live_receipt():
    return LiveAdmittedResourceAuthority(
        repository=REPO,
        mission_id="E004",
        grant_id="grant-R19",
        action="BUILD_CANDIDATE",
        resource_scope=RES,
        lineage_digest=D("3"),
        provenance_id="prov-R19",
        epoch=4,
        epoch_state_version=9,
        authority_ceiling="local_write",
        root_grant_id="root-R19",
        root_grant_digest=D("4"),
        authenticated_grant_digests=(D("1"), D("2")),
        leaf_key_id="key-R19",
        leaf_algorithm="ed25519",
        replay_digest=D("9"),
        admitted_at="2026-08-25T08:00:00+00:00",
    )


def subject(identity="5", expires="2026-08-26T00:00:00+00:00"):
    return TrustedBuilderSubject(
        builder_subject_id="builder-R19",
        builder_instance_id="instance-R19",
        capability_class=BUILDER_CAPABILITY_CLASS,
        repository=REPO,
        candidate_scope=SCOPE,
        resource_scope=RES,
        identity_digest=D(identity),
        implementation_digest=D("6"),
        attestation_digest=D("7"),
        valid_from="2026-08-25T00:00:00+00:00",
        expires_at=expires,
    ).sealed()


def entry_permit(receipt=None, builder=None):
    receipt = receipt or live_receipt()
    builder = builder or subject()
    current = baseline()
    kwargs = dict(
        source_consumption_permit_id="cbcp:" + D("a"),
        source_consumption_permit_digest=D("b"),
        source_consumption_replay_digest=D("c"),
        repository=REPO,
        baseline_master_sha=MASTER,
        baseline_master_tree_sha=TREE,
        current_baseline_digest=current.digest(),
        action="BUILD_CANDIDATE",
        candidate_scope=SCOPE,
        resource_scope=RES,
        authority_epoch=4,
        authority_state_version=9,
        root_grant_id="root-R19",
        root_grant_digest=D("4"),
        current_authority_digest=receipt.digest(),
        builder_subject_id=builder.builder_subject_id,
        builder_instance_id=builder.builder_instance_id,
        builder_capability_class=builder.capability_class,
        builder_identity_digest=builder.identity_digest,
        builder_implementation_digest=builder.implementation_digest,
        builder_attestation_digest=builder.attestation_digest,
    )
    replay = compute_builder_entry_replay_digest(**kwargs)
    return BuilderEntryPermit(
        schema_version=ENTRY_SCHEMA,
        builder_entry_permit_id="bep:" + replay,
        checked_at="2026-08-25T08:20:00+00:00",
        builder_entry_replay_digest=replay,
        **kwargs,
    ).sealed()


def issuance_record(permit: BuilderEntryPermit, origin: PersistentAuthorityStoreOrigin) -> PersistentBuilderEntryIssuanceRecord:
    return PersistentBuilderEntryIssuanceRecord(
        builder_entry_permit_id=permit.builder_entry_permit_id,
        builder_entry_permit_digest=permit.builder_entry_permit_digest,
        builder_entry_replay_digest=permit.builder_entry_replay_digest,
        repository=permit.repository,
        baseline_master_sha=permit.baseline_master_sha,
        baseline_master_tree_sha=permit.baseline_master_tree_sha,
        action=permit.action,
        candidate_scope=permit.candidate_scope,
        resource_scope=permit.resource_scope,
        authority_epoch=permit.authority_epoch,
        authority_state_version=permit.authority_state_version,
        root_grant_id=permit.root_grant_id,
        root_grant_digest=permit.root_grant_digest,
        current_authority_digest=permit.current_authority_digest,
        builder_subject_id=permit.builder_subject_id,
        builder_instance_id=permit.builder_instance_id,
        builder_capability_class=permit.builder_capability_class,
        builder_identity_digest=permit.builder_identity_digest,
        builder_implementation_digest=permit.builder_implementation_digest,
        builder_attestation_digest=permit.builder_attestation_digest,
        authority_store_origin_id=origin.origin_id,
        authority_store_origin_digest=origin.origin_digest,
        issued_at=permit.checked_at,
    ).validate()


class BaselineSource:
    def __init__(self, value): self.value = value
    def current(self, repository): return self.value


class F005:
    def __init__(self, state="QUARANTINED", effect="DENY"):
        self.value = {"state": state, "effect_authority": effect}
    def current(self): return self.value


class Replay:
    def __init__(self): self.seen = set(); self.calls = 0
    def consume(self, digest, *, consumed_at):
        self.calls += 1
        if digest in self.seen: return False
        self.seen.add(digest); return True


class BuilderInvocationPermitEngineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        repo_root = Path(self.tmp.name) / "repo"
        repo_root.mkdir()
        self.authority_path = str(Path(self.tmp.name) / "control-plane.sqlite")
        self.env = {
            "CYBER_LION_CP_PROVIDER_VERSION": "1.0.0",
            "CYBER_LION_CP_ENDPOINT": "https://control-plane.example",
            "CYBER_LION_CP_CREDENTIAL_ENV": "CYBER_LION_CP_TOKEN",
            "CYBER_LION_CP_TOKEN": "secret",
            "LION_CP_RUNTIME_FACTORY_VERSION": "1.0.0",
            "LION_CP_REPOSITORY_ROOT": str(repo_root),
            "LION_CP_DATABASE_PATH": self.authority_path,
        }

    def _source(self):
        with patch.dict("os.environ", self.env, clear=True):
            return PinnedTrustedBuilderSubjectSource()

    def _canonical_store(self):
        with patch.dict(os.environ, self.env, clear=True):
            return build_authority_state_store()

    def _seed_issuance(self, permit=None):
        value = permit or entry_permit()
        with patch.dict(os.environ, self.env, clear=True):
            store = build_authority_state_store()
            origin = verify_authority_state_store_origin()
            store.record_builder_entry_issuance(issuance_record(value, origin))
        return value

    def _engine(self, *, base=None, f005=None, replay=None, provenance_permit=None, seed=True):
        live = object.__new__(LiveResourceAuthorityAdmission)
        if seed:
            self._seed_issuance(provenance_permit or entry_permit())
        with patch.dict("os.environ", self.env, clear=True):
            return BuilderInvocationPermitEngine(
                live_authority=live,
                baseline_source=BaselineSource(base or baseline()),
                f005_state_source=f005 or F005(),
                builder_source=self._source(),
                replay_guard=replay or Replay(),
            )

    def _issue(self, engine, *, receipt=None, builder=None, permit=None, env=None):
        receipt = receipt or live_receipt()
        builder = builder or subject()
        permit = permit or entry_permit(receipt, builder)
        active_env = env or self.env
        with patch.dict("os.environ", active_env, clear=True), \
             patch.object(LiveResourceAuthorityAdmission, "revalidate", return_value=receipt), \
             patch.object(PinnedTrustedBuilderSubjectSource, "resolve_exact", return_value=builder):
            return engine.issue_permit(source_permit=permit, admitted_authority=receipt, trusted_now=NOW)

    def test_issues_exact_non_effectful_builder_invocation_permit(self):
        value = self._issue(self._engine())
        value.validate()
        self.assertEqual(value.source_builder_entry_permit_id, entry_permit().builder_entry_permit_id)
        self.assertEqual(value.current_builder_subject_digest, subject().subject_digest)
        self.assertEqual((value.authority_effect, value.execution_effect, value.repository_ref_effect, value.external_effect), ("NONE", "NONE", "NONE", "NONE"))

    def test_duplicate_builder_invocation_denied(self):
        replay = Replay(); engine = self._engine(replay=replay)
        self._issue(engine)
        with self.assertRaises(BuilderInvocationPermitError): self._issue(engine)
        self.assertEqual(replay.calls, 2)

    def test_coherent_source_checked_at_reseal_denied_before_replay(self):
        original = entry_permit(); replay = Replay(); engine = self._engine(replay=replay, provenance_permit=original)
        forged = replace(original, checked_at="2026-08-25T08:21:00+00:00", builder_entry_permit_digest="").sealed()
        self.assertNotEqual(forged.builder_entry_permit_digest, original.builder_entry_permit_digest)
        self.assertEqual(forged.builder_entry_replay_digest, original.builder_entry_replay_digest)
        with self.assertRaises(BuilderInvocationPermitError): self._issue(engine, permit=forged)
        self.assertEqual(replay.calls, 0)

    def test_missing_source_issuance_denied_before_replay(self):
        replay = Replay(); engine = self._engine(replay=replay, seed=False)
        with self.assertRaises(BuilderInvocationPermitError): self._issue(engine)
        self.assertEqual(replay.calls, 0)

    def test_caller_created_fake_issuance_store_and_source_cannot_be_injected(self):
        fake_store = SQLiteAuthorityStateStore(str(Path(self.tmp.name) / "fake.sqlite"))
        self.assertIs(type(fake_store), SQLiteAuthorityStateStore)
        with self.assertRaises(TypeError): PersistentBuilderEntryIssuanceSource(fake_store)
        live = object.__new__(LiveResourceAuthorityAdmission)
        with patch.dict("os.environ", self.env, clear=True):
            fake_source = PersistentBuilderEntryIssuanceSource()
            with self.assertRaises(TypeError):
                BuilderInvocationPermitEngine(
                    live_authority=live,
                    baseline_source=BaselineSource(baseline()),
                    f005_state_source=F005(),
                    builder_source=self._source(),
                    replay_guard=Replay(),
                    source_issuance=fake_source,
                )

    def _prepare_second_store_with_copied_record(self, permit: BuilderEntryPermit):
        with patch.dict(os.environ, self.env, clear=True):
            source_store = build_authority_state_store()
            source_record = source_store.resolve_builder_entry_issuance(permit.builder_entry_permit_id)
        env_b = dict(self.env)
        env_b["LION_CP_DATABASE_PATH"] = str(Path(self.tmp.name) / "second-control-plane.sqlite")
        with patch.dict(os.environ, env_b, clear=True):
            build_authority_state_store()
        with sqlite3.connect(env_b["LION_CP_DATABASE_PATH"]) as connection:
            connection.execute(
                "INSERT INTO builder_entry_issuance VALUES(?,?,?,?,?)",
                (
                    source_record.builder_entry_permit_id,
                    source_record.builder_entry_permit_digest,
                    source_record.builder_entry_replay_digest,
                    source_record.canonical_json(),
                    source_record.issued_at,
                ),
            )
        return env_b

    def test_r17_store_a_r19_store_b_denied_before_replay(self):
        permit = self._seed_issuance()
        replay = Replay()
        engine = self._engine(replay=replay, seed=False)
        env_b = self._prepare_second_store_with_copied_record(permit)
        with self.assertRaises(BuilderInvocationPermitError):
            self._issue(engine, permit=permit, env=env_b)
        self.assertEqual(replay.calls, 0)

    def test_exact_issuance_record_copied_to_second_store_denied(self):
        permit = self._seed_issuance()
        with patch.dict(os.environ, self.env, clear=True):
            source = PersistentBuilderEntryIssuanceSource()
        env_b = self._prepare_second_store_with_copied_record(permit)
        with patch.dict(os.environ, env_b, clear=True):
            with self.assertRaises(BuilderInvocationPermitError):
                source.resolve(permit.builder_entry_permit_id)

    def test_origin_failure_does_not_consume_r19_replay(self):
        permit = self._seed_issuance()
        replay = Replay(); engine = self._engine(replay=replay, seed=False)
        env_b = dict(self.env); env_b["LION_CP_DATABASE_PATH"] = str(Path(self.tmp.name) / "drift.sqlite")
        with self.assertRaises(BuilderInvocationPermitError):
            self._issue(engine, permit=permit, env=env_b)
        self.assertEqual(replay.calls, 0)

    def test_baseline_drift_denied_before_replay_burn(self):
        replay = Replay(); engine = self._engine(base=baseline(sha="0" * 40), replay=replay)
        with self.assertRaises(BuilderInvocationPermitError): self._issue(engine)
        self.assertEqual(replay.calls, 0)

    def test_authority_drift_denied_before_replay_burn(self):
        replay = Replay(); engine = self._engine(replay=replay)
        wrong = live_receipt(); wrong = wrong.__class__(**{**wrong.__dict__, "epoch_state_version": 10})
        with self.assertRaises(BuilderInvocationPermitError): self._issue(engine, receipt=wrong, permit=entry_permit())
        self.assertEqual(replay.calls, 0)

    def test_builder_currentness_drift_denied_before_replay_burn(self):
        replay = Replay(); engine = self._engine(replay=replay)
        with self.assertRaises(BuilderInvocationPermitError): self._issue(engine, builder=subject(identity="f"), permit=entry_permit())
        self.assertEqual(replay.calls, 0)

    def test_expired_builder_subject_denied_before_replay_burn(self):
        replay = Replay(); expired = subject(expires="2026-08-25T08:24:59+00:00"); permit = entry_permit(builder=expired)
        engine = self._engine(replay=replay, provenance_permit=permit)
        with self.assertRaises(BuilderInvocationPermitError): self._issue(engine, builder=expired, permit=permit)
        self.assertEqual(replay.calls, 0)

    def test_F005_drift_denied_before_replay_burn(self):
        replay = Replay(); engine = self._engine(f005=F005(state="ACTIVE", effect="ALLOW"), replay=replay)
        with self.assertRaises(BuilderInvocationPermitError): self._issue(engine)
        self.assertEqual(replay.calls, 0)

    def test_source_permit_must_be_exact_sealed_entry_permit(self):
        engine = self._engine()
        with self.assertRaises(BuilderInvocationPermitError): self._issue(engine, permit=object())

    def test_no_effect_surface(self):
        BuilderInvocationPermitEngine.assert_no_effect_surface()
        for name in ("start_builder", "build_candidate", "create_branch", "create_pr", "merge", "deploy", "release", "run_test", "issue_grant"):
            self.assertFalse(hasattr(BuilderInvocationPermitEngine, name))


if __name__ == "__main__":
    unittest.main()
