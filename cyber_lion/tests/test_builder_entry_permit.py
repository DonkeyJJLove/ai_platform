import unittest
from unittest.mock import patch

from cyber_lion.contracts.builder_entry_permit import (
    BUILDER_CAPABILITY_CLASS,
    TrustedBuilderSubject,
)
from cyber_lion.contracts.build_authorization_consumption import (
    BuildAuthorizationConsumptionPermit,
    SCHEMA_VERSION as CVER,
    compute_consumption_replay_digest,
)
from cyber_lion.contracts.candidate_build_authorization import TrustedRepositoryBaseline
from cyber_lion.enterprise.builder_entry_permit import (
    BuilderEntryPermitEngine,
    BuilderEntryPermitError,
    PinnedTrustedBuilderSubjectSource,
    TrustedBuilderSubjectSource,
    PINNED_BUILDER_BACKEND_IDENTITY,
    PINNED_BUILDER_SOURCE_IMPLEMENTATION_DIGEST,
    compute_pinned_builder_source_attestation,
)
from cyber_lion.enterprise.candidate_build_authorization import (
    LiveAdmittedResourceAuthority,
    LiveResourceAuthorityAdmission,
)

D = lambda c: c * 64
S = lambda c: c * 40
REPO = "DonkeyJJLove/ai_platform"
MASTER = "f51bd8aa90a6040ca77f3b1f28b2f7c5a7499639"
TREE = "efde6fce25cf92fe0193faf3a4a24039f30a0c2b"
SCOPE = ("cyber_lion/example.py",)
RES = (f"repo-path:{REPO}:cyber_lion/example.py",)
NOW = "2026-08-25T01:30:00+00:00"


def live_receipt():
    return LiveAdmittedResourceAuthority(
        repository=REPO,
        mission_id="E004",
        grant_id="grant-R17",
        action="BUILD_CANDIDATE",
        resource_scope=RES,
        lineage_digest=D("3"),
        provenance_id="prov-R17",
        epoch=4,
        epoch_state_version=9,
        authority_ceiling="local_write",
        root_grant_id="root-R17",
        root_grant_digest=D("4"),
        authenticated_grant_digests=(D("1"), D("2")),
        leaf_key_id="key-R17",
        leaf_algorithm="ed25519",
        replay_digest=D("9"),
        admitted_at="2026-08-25T01:00:00+00:00",
    )


def baseline(sha=MASTER, tree=TREE, observed="2026-08-25T01:20:00+00:00"):
    return TrustedRepositoryBaseline(REPO, sha, tree, observed)


def source_permit(live=None):
    live = live or live_receipt()
    base = baseline()
    kwargs = dict(
        authorization_id="cba:" + D("a"),
        authorization_digest=D("b"),
        issuance_replay_digest=D("a"),
        repository=REPO,
        baseline_master_sha=MASTER,
        baseline_master_tree_sha=TREE,
        baseline_observation_digest=D("c"),
        current_baseline_digest=base.digest(),
        candidate_scope=SCOPE,
        resource_scope=RES,
        action="BUILD_CANDIDATE",
        grant_id="grant-R17",
        leaf_grant_digest=D("2"),
        authority_lineage_digest=D("3"),
        authority_provenance_id="prov-R17",
        authority_epoch=4,
        authority_state_version=9,
        root_grant_id="root-R17",
        root_grant_digest=D("4"),
        live_admission_digest=D("d"),
        current_authority_digest=live.digest(),
        authorization_valid_from="2026-08-25T00:00:00+00:00",
        authorization_expires_at="2026-08-26T00:00:00+00:00",
    )
    replay = compute_consumption_replay_digest(**kwargs)
    return BuildAuthorizationConsumptionPermit(
        schema_version=CVER,
        consumption_permit_id="cbcp:" + replay,
        checked_at="2026-08-25T01:20:00+00:00",
        consumption_replay_digest=replay,
        **kwargs,
    ).sealed()


def builder_subject(instance="instance-01"):
    return TrustedBuilderSubject(
        builder_subject_id="builder-R17",
        builder_instance_id=instance,
        capability_class=BUILDER_CAPABILITY_CLASS,
        repository=REPO,
        candidate_scope=SCOPE,
        resource_scope=RES,
        identity_digest=D("5"),
        implementation_digest=D("6"),
        attestation_digest=D("7"),
        valid_from="2026-08-25T00:00:00+00:00",
        expires_at="2026-08-26T00:00:00+00:00",
    ).sealed()


def pinned_source(records):
    attestation = compute_pinned_builder_source_attestation(records)
    return PinnedTrustedBuilderSubjectSource(
        records,
        backend_identity=PINNED_BUILDER_BACKEND_IDENTITY,
        source_implementation_digest=PINNED_BUILDER_SOURCE_IMPLEMENTATION_DIGEST,
        source_attestation_digest=attestation,
    )


class BaselineSource:
    def __init__(self, value):
        self.value = value

    def current(self, repository):
        return self.value


class F005:
    def __init__(self, state="QUARANTINED", effect="DENY"):
        self.value = {"state": state, "effect_authority": effect}

    def current(self):
        return self.value


class Replay:
    def __init__(self):
        self.seen = set()
        self.calls = 0

    def consume(self, digest, *, consumed_at):
        self.calls += 1
        if digest in self.seen:
            return False
        self.seen.add(digest)
        return True


class ArbitraryResolver:
    source_kind = "trusted-control-plane"

    def resolve_exact(self, **kwargs):
        return builder_subject(kwargs.get("builder_instance_id", "instance-01"))


class CallerDefinedSource(TrustedBuilderSubjectSource):
    source_kind = "trusted-control-plane"

    def __init__(self, records):
        self.records = records

    def _lookup_exact(self, **kwargs):
        return self.records


def engine(*, base=None, f005=None, builders=None, replay=None):
    live = object.__new__(LiveResourceAuthorityAdmission)
    return (
        BuilderEntryPermitEngine(
            live_authority=live,
            baseline_source=BaselineSource(base or baseline()),
            f005_state_source=f005 or F005(),
            builder_source=builders or pinned_source((builder_subject(),)),
            replay_guard=replay or Replay(),
        ),
        live,
    )


class BuilderEntryPermitEngineTests(unittest.TestCase):
    def test_issues_non_effectful_exact_builder_bound_permit(self):
        receipt = live_receipt()
        entry, _ = engine()
        with patch.object(
            LiveResourceAuthorityAdmission, "revalidate", return_value=receipt
        ):
            permit = entry.issue_permit(
                source_permit=source_permit(receipt),
                admitted_authority=receipt,
                builder_subject_id="builder-R17",
                builder_instance_id="instance-01",
                trusted_now=__import__("datetime").datetime.fromisoformat(NOW),
            )
        self.assertEqual(permit.builder_subject_id, "builder-R17")
        self.assertEqual(permit.builder_instance_id, "instance-01")
        self.assertEqual(permit.builder_capability_class, BUILDER_CAPABILITY_CLASS)
        self.assertEqual(
            (
                permit.authority_effect,
                permit.execution_effect,
                permit.repository_ref_effect,
                permit.external_effect,
            ),
            ("NONE", "NONE", "NONE", "NONE"),
        )
        permit.validate()

    def test_arbitrary_resolver_is_denied_at_composition_boundary(self):
        live = object.__new__(LiveResourceAuthorityAdmission)
        with self.assertRaises(BuilderEntryPermitError):
            BuilderEntryPermitEngine(
                live_authority=live,
                baseline_source=BaselineSource(baseline()),
                f005_state_source=F005(),
                builder_source=ArbitraryResolver(),
                replay_guard=Replay(),
            )

    def test_arbitrary_legacy_subclass_is_denied_at_composition_boundary(self):
        live = object.__new__(LiveResourceAuthorityAdmission)
        with self.assertRaises(BuilderEntryPermitError):
            BuilderEntryPermitEngine(
                live_authority=live,
                baseline_source=BaselineSource(baseline()),
                f005_state_source=F005(),
                builder_source=CallerDefinedSource((builder_subject(),)),
                replay_guard=Replay(),
            )

    def test_pinned_source_is_non_subclassable(self):
        with self.assertRaises(TypeError):

            class InvalidPinnedSubclass(PinnedTrustedBuilderSubjectSource):
                pass

    def test_source_origin_backend_implementation_and_attestation_are_pinned(self):
        records = (builder_subject(),)
        good = compute_pinned_builder_source_attestation(records)
        for kwargs in (
            dict(
                backend_identity="attacker-control-plane",
                source_implementation_digest=PINNED_BUILDER_SOURCE_IMPLEMENTATION_DIGEST,
                source_attestation_digest=good,
            ),
            dict(
                backend_identity=PINNED_BUILDER_BACKEND_IDENTITY,
                source_implementation_digest=D("8"),
                source_attestation_digest=good,
            ),
            dict(
                backend_identity=PINNED_BUILDER_BACKEND_IDENTITY,
                source_implementation_digest=PINNED_BUILDER_SOURCE_IMPLEMENTATION_DIGEST,
                source_attestation_digest=D("8"),
            ),
        ):
            with self.assertRaises(BuilderEntryPermitError):
                PinnedTrustedBuilderSubjectSource(records, **kwargs)

    def test_zero_and_ambiguous_pinned_snapshots_fail_without_replay_burn(self):
        receipt = live_receipt()
        now = __import__("datetime").datetime.fromisoformat(NOW)
        for records in ((), (builder_subject(), builder_subject())):
            replay = Replay()
            entry, _ = engine(builders=pinned_source(records), replay=replay)
            with patch.object(
                LiveResourceAuthorityAdmission, "revalidate", return_value=receipt
            ):
                with self.assertRaises(BuilderEntryPermitError):
                    entry.issue_permit(
                        source_permit=source_permit(receipt),
                        admitted_authority=receipt,
                        builder_subject_id="builder-R17",
                        builder_instance_id="instance-01",
                        trusted_now=now,
                    )
            self.assertEqual(replay.calls, 0)

    def test_wrong_type_or_unsealed_snapshot_record_is_rejected_at_origin(self):
        with self.assertRaises(BuilderEntryPermitError):
            compute_pinned_builder_source_attestation((object(),))

        sealed = builder_subject()
        unsealed = TrustedBuilderSubject(**{**sealed.__dict__, "subject_digest": ""})
        with self.assertRaises(BuilderEntryPermitError):
            compute_pinned_builder_source_attestation((unsealed,))

    def test_subject_digest_tampering_is_rejected_at_origin(self):
        original = builder_subject()
        for field, value in (
            ("identity_digest", D("8")),
            ("implementation_digest", D("8")),
            ("attestation_digest", D("8")),
        ):
            tampered = TrustedBuilderSubject(**{**original.__dict__, field: value})
            with self.assertRaises(BuilderEntryPermitError):
                compute_pinned_builder_source_attestation((tampered,))

    def test_source_attestation_rebinds_exact_record_snapshot(self):
        original_records = (builder_subject(),)
        attestation = compute_pinned_builder_source_attestation(original_records)
        changed_records = (builder_subject("instance-02"),)
        with self.assertRaises(BuilderEntryPermitError):
            PinnedTrustedBuilderSubjectSource(
                changed_records,
                backend_identity=PINNED_BUILDER_BACKEND_IDENTITY,
                source_implementation_digest=PINNED_BUILDER_SOURCE_IMPLEMENTATION_DIGEST,
                source_attestation_digest=attestation,
            )

    def test_duplicate_entry_is_denied(self):
        receipt = live_receipt()
        replay = Replay()
        entry, _ = engine(replay=replay)
        source = source_permit(receipt)
        now = __import__("datetime").datetime.fromisoformat(NOW)
        with patch.object(
            LiveResourceAuthorityAdmission, "revalidate", return_value=receipt
        ):
            entry.issue_permit(
                source_permit=source,
                admitted_authority=receipt,
                builder_subject_id="builder-R17",
                builder_instance_id="instance-01",
                trusted_now=now,
            )
            with self.assertRaises(BuilderEntryPermitError):
                entry.issue_permit(
                    source_permit=source,
                    admitted_authority=receipt,
                    builder_subject_id="builder-R17",
                    builder_instance_id="instance-01",
                    trusted_now=now,
                )

    def test_baseline_drift_fails_before_replay(self):
        receipt = live_receipt()
        replay = Replay()
        entry, _ = engine(base=baseline(S("e"), TREE), replay=replay)
        with patch.object(
            LiveResourceAuthorityAdmission, "revalidate", return_value=receipt
        ):
            with self.assertRaises(BuilderEntryPermitError):
                entry.issue_permit(
                    source_permit=source_permit(receipt),
                    admitted_authority=receipt,
                    builder_subject_id="builder-R17",
                    builder_instance_id="instance-01",
                    trusted_now=__import__("datetime").datetime.fromisoformat(NOW),
                )
        self.assertEqual(replay.calls, 0)

    def test_builder_instance_substitution_is_denied_before_replay(self):
        receipt = live_receipt()
        replay = Replay()
        entry, _ = engine(
            builders=pinned_source((builder_subject("instance-01"),)), replay=replay
        )
        with patch.object(
            LiveResourceAuthorityAdmission, "revalidate", return_value=receipt
        ):
            with self.assertRaises(BuilderEntryPermitError):
                entry.issue_permit(
                    source_permit=source_permit(receipt),
                    admitted_authority=receipt,
                    builder_subject_id="builder-R17",
                    builder_instance_id="instance-02",
                    trusted_now=__import__("datetime").datetime.fromisoformat(NOW),
                )
        self.assertEqual(replay.calls, 0)

    def test_f005_injection_fails_before_replay(self):
        receipt = live_receipt()
        replay = Replay()
        entry, _ = engine(f005=F005("ACTIVE", "ALLOW"), replay=replay)
        with patch.object(
            LiveResourceAuthorityAdmission, "revalidate", return_value=receipt
        ):
            with self.assertRaises(BuilderEntryPermitError):
                entry.issue_permit(
                    source_permit=source_permit(receipt),
                    admitted_authority=receipt,
                    builder_subject_id="builder-R17",
                    builder_instance_id="instance-01",
                    trusted_now=__import__("datetime").datetime.fromisoformat(NOW),
                )
        self.assertEqual(replay.calls, 0)

    def test_authority_drift_and_expired_builder_fail(self):
        receipt = live_receipt()
        drift = LiveAdmittedResourceAuthority(
            **{**receipt.__dict__, "epoch_state_version": 10}
        )
        replay = Replay()
        entry, _ = engine(replay=replay)
        with patch.object(
            LiveResourceAuthorityAdmission, "revalidate", return_value=drift
        ):
            with self.assertRaises(BuilderEntryPermitError):
                entry.issue_permit(
                    source_permit=source_permit(receipt),
                    admitted_authority=receipt,
                    builder_subject_id="builder-R17",
                    builder_instance_id="instance-01",
                    trusted_now=__import__("datetime").datetime.fromisoformat(NOW),
                )
        self.assertEqual(replay.calls, 0)

        expired = TrustedBuilderSubject(
            **{
                **builder_subject().__dict__,
                "expires_at": "2026-08-25T01:00:00+00:00",
                "subject_digest": "",
            }
        ).sealed()
        replay = Replay()
        entry, _ = engine(builders=pinned_source((expired,)), replay=replay)
        with patch.object(
            LiveResourceAuthorityAdmission, "revalidate", return_value=receipt
        ):
            with self.assertRaises(BuilderEntryPermitError):
                entry.issue_permit(
                    source_permit=source_permit(receipt),
                    admitted_authority=receipt,
                    builder_subject_id="builder-R17",
                    builder_instance_id="instance-01",
                    trusted_now=__import__("datetime").datetime.fromisoformat(NOW),
                )
        self.assertEqual(replay.calls, 0)

    def test_no_effect_surface(self):
        BuilderEntryPermitEngine.assert_no_effect_surface()


if __name__ == "__main__":
    unittest.main()
