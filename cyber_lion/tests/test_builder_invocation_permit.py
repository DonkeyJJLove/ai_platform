from __future__ import annotations

from datetime import datetime
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
)
from cyber_lion.enterprise.candidate_build_authorization import (
    LiveAdmittedResourceAuthority,
    LiveResourceAuthorityAdmission,
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
        self.env = {
            "CYBER_LION_CP_PROVIDER_VERSION": "1.0.0",
            "CYBER_LION_CP_ENDPOINT": "https://control-plane.example",
            "CYBER_LION_CP_CREDENTIAL_ENV": "CYBER_LION_CP_TOKEN",
            "CYBER_LION_CP_TOKEN": "secret",
        }

    def _source(self):
        with patch.dict("os.environ", self.env, clear=True):
            return PinnedTrustedBuilderSubjectSource()

    def _engine(self, *, base=None, f005=None, replay=None):
        live = object.__new__(LiveResourceAuthorityAdmission)
        return BuilderInvocationPermitEngine(
            live_authority=live,
            baseline_source=BaselineSource(base or baseline()),
            f005_state_source=f005 or F005(),
            builder_source=self._source(),
            replay_guard=replay or Replay(),
        )

    def _issue(self, engine, *, receipt=None, builder=None, permit=None):
        receipt = receipt or live_receipt()
        builder = builder or subject()
        permit = permit or entry_permit(receipt, builder)
        with patch.dict("os.environ", self.env, clear=True), \
             patch.object(LiveResourceAuthorityAdmission, "revalidate", return_value=receipt), \
             patch.object(PinnedTrustedBuilderSubjectSource, "resolve_exact", return_value=builder):
            return engine.issue_permit(
                source_permit=permit,
                admitted_authority=receipt,
                trusted_now=NOW,
            )

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

    def test_baseline_drift_denied_before_replay_burn(self):
        replay = Replay(); engine = self._engine(base=baseline(sha="0" * 40), replay=replay)
        with self.assertRaises(BuilderInvocationPermitError): self._issue(engine)
        self.assertEqual(replay.calls, 0)

    def test_authority_drift_denied_before_replay_burn(self):
        replay = Replay(); engine = self._engine(replay=replay)
        wrong = live_receipt()
        wrong = wrong.__class__(**{**wrong.__dict__, "epoch_state_version": 10})
        with self.assertRaises(BuilderInvocationPermitError):
            self._issue(engine, receipt=wrong, permit=entry_permit())
        self.assertEqual(replay.calls, 0)

    def test_builder_currentness_drift_denied_before_replay_burn(self):
        replay = Replay(); engine = self._engine(replay=replay)
        with self.assertRaises(BuilderInvocationPermitError):
            self._issue(engine, builder=subject(identity="f"), permit=entry_permit())
        self.assertEqual(replay.calls, 0)

    def test_expired_builder_subject_denied_before_replay_burn(self):
        replay = Replay(); engine = self._engine(replay=replay)
        expired = subject(expires="2026-08-25T08:24:59+00:00")
        with self.assertRaises(BuilderInvocationPermitError):
            self._issue(engine, builder=expired, permit=entry_permit(builder=expired))
        self.assertEqual(replay.calls, 0)

    def test_F005_drift_denied_before_replay_burn(self):
        replay = Replay(); engine = self._engine(f005=F005(state="ACTIVE", effect="ALLOW"), replay=replay)
        with self.assertRaises(BuilderInvocationPermitError): self._issue(engine)
        self.assertEqual(replay.calls, 0)

    def test_source_permit_must_be_exact_sealed_entry_permit(self):
        engine = self._engine()
        with self.assertRaises(BuilderInvocationPermitError):
            self._issue(engine, permit=object())

    def test_no_effect_surface(self):
        BuilderInvocationPermitEngine.assert_no_effect_surface()
        for name in ("start_builder", "build_candidate", "create_branch", "create_pr", "merge", "deploy", "release", "run_test", "issue_grant"):
            self.assertFalse(hasattr(BuilderInvocationPermitEngine, name))


if __name__ == "__main__":
    unittest.main()
