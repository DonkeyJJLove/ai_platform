from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
import tempfile
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
import cyber_lion.enterprise.builder_entry_permit as bep
import cyber_lion.enterprise.trusted_control_plane_runtime as cp_runtime
from cyber_lion.enterprise.builder_entry_permit import (
    BuilderEntryPermitEngine,
    BuilderEntryPermitError,
    PinnedBuilderControlPlaneBackend,
    PinnedTrustedBuilderSubjectSource,
    TrustedBuilderSubjectSource,
)
from cyber_lion.enterprise.candidate_build_authorization import (
    LiveAdmittedResourceAuthority,
    LiveResourceAuthorityAdmission,
)
from cyber_lion.enterprise.trusted_control_plane_providers import SQLiteTrustedControlPlaneStore

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


def builder_subject(instance="instance-01", identity="5"):
    return TrustedBuilderSubject(
        builder_subject_id="builder-R17",
        builder_instance_id=instance,
        capability_class=BUILDER_CAPABILITY_CLASS,
        repository=REPO,
        candidate_scope=SCOPE,
        resource_scope=RES,
        identity_digest=D(identity),
        implementation_digest=D("6"),
        attestation_digest=D("7"),
        valid_from="2026-08-25T00:00:00+00:00",
        expires_at="2026-08-26T00:00:00+00:00",
    ).sealed()


def builder_record(subject=None):
    subject = subject or builder_subject()
    return {
        "record_kind": "builder-subject",
        "lookup_key": {
            "repository": subject.repository,
            "builder_subject_id": subject.builder_subject_id,
            "builder_instance_id": subject.builder_instance_id,
            "candidate_scope_digest": bep._scope_digest(subject.candidate_scope, label="candidate_scope"),
            "resource_scope_digest": bep._scope_digest(subject.resource_scope, label="resource_scope"),
            "capability_class": subject.capability_class,
        },
        "subject": asdict(subject),
    }


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


class ArbitraryResolver:
    def resolve_exact(self, **kwargs): return builder_subject()


class CallerDefinedSource(TrustedBuilderSubjectSource):
    def _lookup_exact(self, **kwargs): return (builder_subject(),)


class BuilderEntryPermitEngineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = str(Path(self.tmp.name) / "control-plane.sqlite3")
        self.root = str(Path(__file__).resolve().parents[2])
        self.env = {
            "LION_CP_RUNTIME_FACTORY_VERSION": "1.0.0",
            "LION_CP_REPOSITORY_ROOT": self.root,
            "LION_CP_DATABASE_PATH": self.db,
        }

    def tearDown(self):
        self.tmp.cleanup()

    def _bootstrap(self, *records):
        store = SQLiteTrustedControlPlaneStore(self.db)
        for record in records:
            store.put_builder_subject_record(record)
        return store

    def _source(self, *records):
        self._bootstrap(*records)
        with patch.dict("os.environ", self.env, clear=False):
            return PinnedTrustedBuilderSubjectSource()

    def _engine(self, *, source=None, base=None, f005=None, replay=None):
        source = source or self._source(builder_record())
        live = object.__new__(LiveResourceAuthorityAdmission)
        return BuilderEntryPermitEngine(
            live_authority=live,
            baseline_source=BaselineSource(base or baseline()),
            f005_state_source=f005 or F005(),
            builder_source=source,
            replay_guard=replay or Replay(),
        )

    def _issue(self, entry, receipt=None):
        receipt = receipt or live_receipt()
        with patch.object(LiveResourceAuthorityAdmission, "revalidate", return_value=receipt):
            return entry.issue_permit(
                source_permit=source_permit(receipt),
                admitted_authority=receipt,
                builder_subject_id="builder-R17",
                builder_instance_id="instance-01",
                trusted_now=__import__("datetime").datetime.fromisoformat(NOW),
            )

    def test_issues_non_effectful_exact_builder_bound_permit(self):
        permit = self._issue(self._engine())
        self.assertEqual(permit.builder_subject_id, "builder-R17")
        self.assertEqual(permit.builder_instance_id, "instance-01")
        self.assertEqual((permit.authority_effect, permit.execution_effect, permit.repository_ref_effect, permit.external_effect), ("NONE", "NONE", "NONE", "NONE"))
        permit.validate()

    def test_local_record_loader_is_absent(self):
        self.assertFalse(hasattr(bep, "_load_pinned_builder_records"))
        self.assertFalse(hasattr(bep, "compute_pinned_builder_source_attestation"))

    def test_caller_cannot_supply_records_or_attestation(self):
        own = builder_subject()
        for constructor, kwargs in (
            (PinnedBuilderControlPlaneBackend, {"records": (own,)}),
            (PinnedTrustedBuilderSubjectSource, {"records": (own,)}),
            (PinnedTrustedBuilderSubjectSource, {"source_attestation_digest": D("8")}),
        ):
            with self.assertRaises(TypeError): constructor(**kwargs)

    def test_fake_runtime_monkeypatch_does_not_replace_pinned_import(self):
        self._bootstrap(builder_record())
        with patch.dict("os.environ", self.env, clear=False):
            with patch.object(cp_runtime, "build_store", side_effect=AssertionError("fake runtime used")):
                source = PinnedTrustedBuilderSubjectSource()
        source.verify_origin()

    def test_control_plane_unavailable_fails_closed(self):
        env = dict(self.env); env.pop("LION_CP_DATABASE_PATH")
        with patch.dict("os.environ", env, clear=True):
            with self.assertRaises(BuilderEntryPermitError):
                PinnedTrustedBuilderSubjectSource()

    def test_arbitrary_sources_and_subclasses_are_denied(self):
        live = object.__new__(LiveResourceAuthorityAdmission)
        for value in (ArbitraryResolver(), CallerDefinedSource()):
            with self.assertRaises(BuilderEntryPermitError):
                BuilderEntryPermitEngine(
                    live_authority=live,
                    baseline_source=BaselineSource(baseline()),
                    f005_state_source=F005(),
                    builder_source=value,
                    replay_guard=Replay(),
                )
        with self.assertRaises(TypeError):
            class BadBackend(PinnedBuilderControlPlaneBackend): pass
        with self.assertRaises(TypeError):
            class BadSource(PinnedTrustedBuilderSubjectSource): pass

    def test_zero_and_ambiguous_records_fail_without_replay_burn(self):
        for records in ((), (builder_record(), builder_record(builder_subject(identity="8")))):
            replay = Replay()
            source = self._source(*records)
            entry = self._engine(source=source, replay=replay)
            with self.assertRaises(BuilderEntryPermitError): self._issue(entry)
            self.assertEqual(replay.calls, 0)

    def test_wrong_record_kind_and_malformed_payload_are_denied(self):
        good = builder_record()
        store = SQLiteTrustedControlPlaneStore(self.db)
        wrong = dict(good); wrong["record_kind"] = "authority"
        with self.assertRaises(Exception): store.put_builder_subject_record(wrong)
        malformed = dict(good); malformed["subject"] = {"builder_subject_id": "x"}
        store.put_builder_subject_record(malformed)
        with patch.dict("os.environ", self.env, clear=False): source = PinnedTrustedBuilderSubjectSource()
        entry = self._engine(source=source, replay=Replay())
        with self.assertRaises(BuilderEntryPermitError): self._issue(entry)

    def test_subject_digest_and_builder_binding_substitutions_are_denied(self):
        original = builder_subject()
        for field, value in (
            ("identity_digest", D("8")),
            ("implementation_digest", D("8")),
            ("attestation_digest", D("8")),
        ):
            raw = asdict(original); raw[field] = value
            record = builder_record(); record["subject"] = raw
            replay = Replay(); source = self._source(record); entry = self._engine(source=source, replay=replay)
            with self.assertRaises(BuilderEntryPermitError): self._issue(entry)
            self.assertEqual(replay.calls, 0)

    def test_builder_instance_substitution_is_denied_before_replay(self):
        replay = Replay(); source = self._source(builder_record(builder_subject("instance-01")))
        entry = self._engine(source=source, replay=replay); receipt = live_receipt()
        with patch.object(LiveResourceAuthorityAdmission, "revalidate", return_value=receipt):
            with self.assertRaises(BuilderEntryPermitError):
                entry.issue_permit(
                    source_permit=source_permit(receipt), admitted_authority=receipt,
                    builder_subject_id="builder-R17", builder_instance_id="instance-02",
                    trusted_now=__import__("datetime").datetime.fromisoformat(NOW),
                )
        self.assertEqual(replay.calls, 0)

    def test_baseline_authority_and_f005_fail_before_replay(self):
        receipt = live_receipt()
        replay = Replay(); entry = self._engine(base=baseline(S("e"), TREE), replay=replay)
        with self.assertRaises(BuilderEntryPermitError): self._issue(entry, receipt)
        self.assertEqual(replay.calls, 0)

        drift = LiveAdmittedResourceAuthority(**{**receipt.__dict__, "epoch_state_version": 10})
        replay = Replay(); entry = self._engine(replay=replay)
        with patch.object(LiveResourceAuthorityAdmission, "revalidate", return_value=drift):
            with self.assertRaises(BuilderEntryPermitError):
                entry.issue_permit(source_permit=source_permit(receipt), admitted_authority=receipt, builder_subject_id="builder-R17", builder_instance_id="instance-01", trusted_now=__import__("datetime").datetime.fromisoformat(NOW))
        self.assertEqual(replay.calls, 0)

        replay = Replay(); entry = self._engine(f005=F005("ACTIVE", "ALLOW"), replay=replay)
        with self.assertRaises(BuilderEntryPermitError): self._issue(entry, receipt)
        self.assertEqual(replay.calls, 0)

    def test_duplicate_entry_is_denied(self):
        replay = Replay(); entry = self._engine(replay=replay)
        self._issue(entry)
        with self.assertRaises(BuilderEntryPermitError): self._issue(entry)

    def test_no_effect_surface(self):
        BuilderEntryPermitEngine.assert_no_effect_surface()


if __name__ == "__main__":
    unittest.main()
