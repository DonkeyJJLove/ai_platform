from __future__ import annotations

from dataclasses import replace
from datetime import datetime
import inspect
import unittest
from unittest.mock import patch

from cyber_lion.contracts.builder_entry_permit import BUILDER_CAPABILITY_CLASS, TrustedBuilderSubject
from cyber_lion.contracts.builder_invocation_permit import (
    BuilderInvocationPermit,
    SCHEMA_VERSION as R19_SCHEMA,
    compute_builder_invocation_replay_digest,
)
from cyber_lion.contracts.candidate_build_authorization import TrustedRepositoryBaseline
from cyber_lion.enterprise.builder_entry_permit import PinnedTrustedBuilderSubjectSource
from cyber_lion.enterprise.builder_invocation_consumption import (
    BuilderInvocationConsumptionEngine,
    BuilderInvocationConsumptionError,
    PersistentBuilderInvocationIssuanceSource,
)
from cyber_lion.enterprise.candidate_build_authorization import LiveAdmittedResourceAuthority, LiveResourceAuthorityAdmission
from cyber_lion.enterprise.persistent_authority_state import PersistentBuilderInvocationIssuanceRecord

D = lambda c: c * 64
S = lambda c: c * 40
REPO = "DonkeyJJLove/ai_platform"
MASTER = S("1")
TREE = S("2")
SCOPE = ("cyber_lion/example.py",)
RES = (f"repo-path:{REPO}:cyber_lion/example.py",)
NOW = datetime.fromisoformat("2026-08-25T11:00:00+00:00")


class BaselineSource:
    def __init__(self, value): self.value = value
    def current(self, repository): return self.value


class F005:
    def __init__(self, state="QUARANTINED", effect="DENY"): self.value = {"state": state, "effect_authority": effect}
    def current(self): return self.value


class Replay:
    def __init__(self): self.seen = set(); self.calls = 0
    def consume(self, digest, *, consumed_at):
        self.calls += 1
        if digest in self.seen: return False
        self.seen.add(digest); return True


def baseline():
    return TrustedRepositoryBaseline(REPO, MASTER, TREE, "2026-08-25T10:50:00+00:00")


def authority():
    return LiveAdmittedResourceAuthority(
        repository=REPO, mission_id="E004", grant_id="grant-R20", action="BUILD_CANDIDATE",
        resource_scope=RES, lineage_digest=D("3"), provenance_id="prov-R20", epoch=4,
        epoch_state_version=9, authority_ceiling="local_write", root_grant_id="root-R20",
        root_grant_digest=D("4"), authenticated_grant_digests=(D("1"), D("2")),
        leaf_key_id="key-R20", leaf_algorithm="ed25519", replay_digest=D("5"),
        admitted_at="2026-08-25T10:45:00+00:00",
    )


def subject():
    return TrustedBuilderSubject(
        builder_subject_id="builder-R20", builder_instance_id="instance-01",
        capability_class=BUILDER_CAPABILITY_CLASS, repository=REPO,
        candidate_scope=SCOPE, resource_scope=RES, identity_digest=D("6"),
        implementation_digest=D("7"), attestation_digest=D("8"),
        valid_from="2026-08-25T10:00:00+00:00", expires_at="2026-08-25T12:00:00+00:00",
    ).sealed()


def invocation_permit():
    current = baseline(); live = authority(); builder = subject()
    kwargs = dict(
        source_builder_entry_permit_id="bep:" + D("9"),
        source_builder_entry_permit_digest=D("a"),
        source_builder_entry_replay_digest=D("b"),
        repository=REPO,
        baseline_master_sha=MASTER,
        baseline_master_tree_sha=TREE,
        current_baseline_digest=current.digest(),
        action="BUILD_CANDIDATE",
        candidate_scope=SCOPE,
        resource_scope=RES,
        authority_epoch=live.epoch,
        authority_state_version=live.epoch_state_version,
        root_grant_id=live.root_grant_id,
        root_grant_digest=live.root_grant_digest,
        current_authority_digest=live.digest(),
        builder_subject_id=builder.builder_subject_id,
        builder_instance_id=builder.builder_instance_id,
        builder_capability_class=builder.capability_class,
        builder_identity_digest=builder.identity_digest,
        builder_implementation_digest=builder.implementation_digest,
        builder_attestation_digest=builder.attestation_digest,
        current_builder_subject_digest=builder.subject_digest,
    )
    replay = compute_builder_invocation_replay_digest(**kwargs)
    return BuilderInvocationPermit(
        schema_version=R19_SCHEMA, builder_invocation_permit_id="bip:" + replay,
        checked_at="2026-08-25T10:55:00+00:00", builder_invocation_replay_digest=replay,
        **kwargs,
    ).sealed()


def issuance_record(permit=None):
    permit = permit or invocation_permit()
    return PersistentBuilderInvocationIssuanceRecord(
        builder_invocation_permit_id=permit.builder_invocation_permit_id,
        builder_invocation_permit_digest=permit.builder_invocation_permit_digest,
        builder_invocation_replay_digest=permit.builder_invocation_replay_digest,
        source_builder_entry_permit_id=permit.source_builder_entry_permit_id,
        source_builder_entry_permit_digest=permit.source_builder_entry_permit_digest,
        repository=permit.repository, baseline_master_sha=permit.baseline_master_sha,
        baseline_master_tree_sha=permit.baseline_master_tree_sha,
        current_baseline_digest=permit.current_baseline_digest, action=permit.action,
        candidate_scope=permit.candidate_scope, resource_scope=permit.resource_scope,
        authority_epoch=permit.authority_epoch, authority_state_version=permit.authority_state_version,
        root_grant_id=permit.root_grant_id, root_grant_digest=permit.root_grant_digest,
        current_authority_digest=permit.current_authority_digest,
        builder_subject_id=permit.builder_subject_id, builder_instance_id=permit.builder_instance_id,
        builder_capability_class=permit.builder_capability_class,
        builder_identity_digest=permit.builder_identity_digest,
        builder_implementation_digest=permit.builder_implementation_digest,
        builder_attestation_digest=permit.builder_attestation_digest,
        current_builder_subject_digest=permit.current_builder_subject_digest,
        authority_store_origin_id="aso:" + D("c"), authority_store_origin_digest=D("c"),
        issued_at=permit.checked_at,
    ).validate()


class BuilderInvocationConsumptionTests(unittest.TestCase):
    def _engine(self, *, replay=None, base=None, f005=None, record=None, builder=None, live=None):
        replay = replay or Replay(); builder = builder or subject(); live = live or authority()
        source = object.__new__(PinnedTrustedBuilderSubjectSource)
        admission = object.__new__(LiveResourceAuthorityAdmission)
        record = record or issuance_record()
        patches = (
            patch.object(PinnedTrustedBuilderSubjectSource, "verify_origin", return_value=None),
            patch.object(PinnedTrustedBuilderSubjectSource, "resolve_exact", return_value=builder),
            patch.object(PersistentBuilderInvocationIssuanceSource, "__init__", return_value=None),
            patch.object(PersistentBuilderInvocationIssuanceSource, "resolve", return_value=record),
            patch.object(LiveResourceAuthorityAdmission, "revalidate", return_value=live),
        )
        for item in patches: item.start(); self.addCleanup(item.stop)
        return BuilderInvocationConsumptionEngine(
            live_authority=admission, baseline_source=BaselineSource(base or baseline()),
            f005_state_source=f005 or F005(), builder_source=source, replay_guard=replay,
        ), replay

    def test_issues_non_effectful_consumption_permit(self):
        engine, replay = self._engine()
        value = engine.issue_permit(source_permit=invocation_permit(), admitted_authority=authority(), trusted_now=NOW)
        self.assertEqual(value.state, "BUILDER_INVOCATION_CONSUMPTION_PERMIT_ISSUED")
        self.assertEqual((value.authority_effect, value.execution_effect, value.repository_ref_effect, value.external_effect), ("NONE", "NONE", "NONE", "NONE"))
        self.assertEqual(replay.calls, 1)
        value.validate()

    def test_missing_or_conflicting_durable_provenance_denied_before_replay(self):
        replay = Replay(); engine, _ = self._engine(replay=replay)
        with patch.object(PersistentBuilderInvocationIssuanceSource, "resolve", side_effect=BuilderInvocationConsumptionError("missing")):
            with self.assertRaises(BuilderInvocationConsumptionError):
                engine.issue_permit(source_permit=invocation_permit(), admitted_authority=authority(), trusted_now=NOW)
        self.assertEqual(replay.calls, 0)

        altered = replace(invocation_permit(), checked_at="2026-08-25T10:56:00+00:00", builder_invocation_permit_digest="").sealed()
        replay = Replay(); engine, _ = self._engine(replay=replay, record=issuance_record())
        with self.assertRaises(BuilderInvocationConsumptionError):
            engine.issue_permit(source_permit=altered, admitted_authority=authority(), trusted_now=NOW)
        self.assertEqual(replay.calls, 0)

    def test_currentness_failures_do_not_burn_replay(self):
        stale = TrustedRepositoryBaseline(REPO, S("e"), TREE, "2026-08-25T10:50:00+00:00")
        for kwargs in (
            {"base": stale},
            {"f005": F005("ACTIVE", "ALLOW")},
            {"builder": replace(subject(), attestation_digest=D("f"), subject_digest="").sealed()},
        ):
            replay = Replay(); engine, _ = self._engine(replay=replay, **kwargs)
            with self.assertRaises(BuilderInvocationConsumptionError):
                engine.issue_permit(source_permit=invocation_permit(), admitted_authority=authority(), trusted_now=NOW)
            self.assertEqual(replay.calls, 0)

    def test_duplicate_consumption_denied(self):
        replay = Replay(); engine, _ = self._engine(replay=replay)
        permit = invocation_permit()
        engine.issue_permit(source_permit=permit, admitted_authority=authority(), trusted_now=NOW)
        with self.assertRaises(BuilderInvocationConsumptionError):
            engine.issue_permit(source_permit=permit, admitted_authority=authority(), trusted_now=NOW)
        self.assertEqual(replay.calls, 2)

    def test_caller_selected_provenance_dependencies_are_not_constructor_surface(self):
        sig = inspect.signature(BuilderInvocationConsumptionEngine)
        for name in ("store", "issuance_source", "origin", "provenance_recorder"):
            self.assertNotIn(name, sig.parameters)

    def test_no_effect_surface(self):
        BuilderInvocationConsumptionEngine.assert_no_effect_surface()
        for name in ("start_builder", "build_candidate", "execute", "merge", "deploy", "release"):
            self.assertFalse(hasattr(BuilderInvocationConsumptionEngine, name))


if __name__ == "__main__":
    unittest.main()
