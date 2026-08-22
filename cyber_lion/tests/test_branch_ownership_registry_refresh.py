from __future__ import annotations

from dataclasses import dataclass, replace
from hashlib import sha256
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from cyber_lion.contracts.branch_ownership_registry import BranchOwnershipRecord, BranchOwnershipRegistrySnapshot
from cyber_lion.contracts.branch_ownership_registry_refresh import BranchOwnershipRefreshManifest
from cyber_lion.enterprise.branch_ownership_registry import canonical_registry_bytes, load_registry_snapshot
from cyber_lion.enterprise.branch_ownership_registry_refresh import (
    BranchOwnershipRegistryRefreshError,
    refresh_branch_ownership_registry,
)

REPO = "DonkeyJJLove/ai_platform"
ROOT = r"C:\Users\d2j3\Documents\LION\runtime\f005"
MASTER = "a" * 40
TREE = "b" * 40
BASE = "c" * 40


@dataclass(frozen=True)
class Branch:
    branch: str
    head_sha: str


@dataclass(frozen=True)
class Comparison:
    ancestry: str


class FakeGitHub:
    def __init__(self, branches, *, ancestry="DEFAULT_ANCESTOR_OF_HEAD", after=None):
        self.branches = tuple(branches)
        self.after = tuple(after) if after is not None else None
        self.enumerations = 0
        self.ancestry = ancestry

    def default_head(self, repository, default_branch):
        self.assert_repo(repository)
        if default_branch != "master":
            raise AssertionError(default_branch)
        return MASTER, TREE

    def list_branches_page(self, repository, cursor):
        self.assert_repo(repository)
        if cursor is not None:
            raise AssertionError("fake has one page")
        self.enumerations += 1
        if self.enumerations > 1 and self.after is not None:
            return self.after, None
        return self.branches, None

    def compare_to_default(self, repository, base, head, branch):
        self.assert_repo(repository)
        if not base or not head or not branch:
            raise AssertionError("missing comparison binding")
        return Comparison(self.ancestry)

    @staticmethod
    def assert_repo(repository):
        if repository != REPO:
            raise AssertionError(repository)


class BranchOwnershipRegistryRefreshTests(unittest.TestCase):
    def setUp(self):
        self.env = mock.patch.dict(os.environ, {"LION_FLEET_RUNTIME_ROOT": ROOT}, clear=False)
        self.env.start()
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.manifest_path = root / "branch-ownership-manifest.json"
        self.registry_path = root / "branch-ownership-registry.json"
        self.patch_paths = mock.patch(
            "cyber_lion.enterprise.branch_ownership_registry_refresh.resolve_fleet_runtime_paths",
            return_value=type("Paths", (), {
                "branch_ownership_manifest_path": str(self.manifest_path),
                "branch_ownership_registry_path": str(self.registry_path),
            })(),
        )
        self.patch_paths.start()
        old_record = self.record("master", MASTER, state="UNOWNED", revision=1)
        old = BranchOwnershipRegistrySnapshot.build(
            schema_version="1.0.0",
            repository=REPO,
            source_instance_id="lion-runtime-reconciliation-source-01",
            registry_revision=1,
            observed_at="2026-08-21T23:57:00+00:00",
            records=(old_record,),
        )
        self.registry_path.write_bytes(canonical_registry_bytes(old))
        self.old = old

    def tearDown(self):
        self.patch_paths.stop()
        self.tmp.cleanup()
        self.env.stop()

    def record(self, branch, head, *, state="TERMINAL", revision=2):
        mission = None if state == "UNOWNED" else f"MISSION-{branch}"
        baseline = None if state == "UNOWNED" else BASE
        return BranchOwnershipRecord(
            repository=REPO,
            branch=branch,
            branch_head_sha=head,
            ownership_state=state,
            mission_id=mission,
            baseline_sha=baseline,
            superseded_by_branch=None,
            supersession_provenance_ref=None,
            source_provenance_ref=f"manifest:{branch}",
            epistemic_class="ANCHORED",
            record_revision=revision,
        ).validate()

    def write_manifest(self, records, **overrides):
        values = dict(
            schema_version="1.0.0",
            repository=REPO,
            source_instance_id="lion-runtime-reconciliation-source-01",
            previous_registry_revision=1,
            previous_registry_digest=self.old.registry_digest,
            target_registry_revision=2,
            expected_master=MASTER,
            expected_master_tree=TREE,
            observed_at="2026-08-22T03:30:00+00:00",
            records=tuple(records),
        )
        values.update(overrides)
        manifest = BranchOwnershipRefreshManifest.build(**values)
        raw = json.dumps(manifest.canonical_dict(), sort_keys=True, separators=(",", ":")).encode()
        self.manifest_path.write_bytes(raw)
        return manifest, sha256(raw).hexdigest()

    def run_refresh(self, records, *, github=None, **manifest_overrides):
        manifest, digest = self.write_manifest(records, **manifest_overrides)
        live = [Branch(r.branch, r.branch_head_sha) for r in manifest.records]
        github = github or FakeGitHub(live)
        result = refresh_branch_ownership_registry(
            expected_master=MASTER,
            expected_master_tree=TREE,
            manifest_sha256=digest,
            github=github,
            manifest_path=self.manifest_path,
            registry_path=self.registry_path,
        )
        return manifest, result

    def test_valid_one_to_two_refresh_is_atomic_and_resolvable(self):
        records = (
            self.record("master", MASTER, state="UNOWNED"),
            self.record("mission/x", "e" * 40),
        )
        manifest, result = self.run_refresh(records)
        snapshot = load_registry_snapshot(self.registry_path.read_bytes())
        self.assertEqual(snapshot.registry_revision, 2)
        self.assertEqual(snapshot.registry_digest, result["registry_digest"])
        self.assertEqual(tuple(r.branch for r in snapshot.records), ("master", "mission/x"))
        self.assertEqual(result["runtime_effect"], "BRANCH_OWNERSHIP_REGISTRY_REPLACED_ONCE")
        self.assertEqual(result["manifest_digest"], manifest.manifest_digest)

    def test_previous_revision_digest_and_exact_increment_are_required(self):
        records = (self.record("master", MASTER, state="UNOWNED"),)
        for kwargs in (
            {"previous_registry_revision": 2, "target_registry_revision": 3},
            {"previous_registry_digest": "f" * 64},
        ):
            with self.subTest(kwargs=kwargs), self.assertRaises(BranchOwnershipRegistryRefreshError):
                self.run_refresh(records, **kwargs)
        with self.assertRaises(ValueError):
            BranchOwnershipRefreshManifest.build(
                schema_version="1.0.0",
                repository=REPO,
                source_instance_id="lion-runtime-reconciliation-source-01",
                previous_registry_revision=1,
                previous_registry_digest=self.old.registry_digest,
                target_registry_revision=3,
                expected_master=MASTER,
                expected_master_tree=TREE,
                observed_at="2026-08-22T03:30:00+00:00",
                records=records,
            )

    def test_manifest_byte_digest_substitution_denied(self):
        records = (self.record("master", MASTER, state="UNOWNED"),)
        self.write_manifest(records)
        with self.assertRaises(BranchOwnershipRegistryRefreshError):
            refresh_branch_ownership_registry(
                expected_master=MASTER,
                expected_master_tree=TREE,
                manifest_sha256="f" * 64,
                github=FakeGitHub([Branch("master", MASTER)]),
                manifest_path=self.manifest_path,
                registry_path=self.registry_path,
            )

    def test_branch_set_missing_extra_or_head_drift_denied(self):
        records = (
            self.record("master", MASTER, state="UNOWNED"),
            self.record("mission/x", "e" * 40),
        )
        cases = (
            [Branch("master", MASTER)],
            [Branch("master", MASTER), Branch("mission/x", "f" * 40)],
            [Branch("master", MASTER), Branch("mission/x", "e" * 40), Branch("extra", "1" * 40)],
        )
        for live in cases:
            with self.subTest(live=live), self.assertRaises(BranchOwnershipRegistryRefreshError):
                self.run_refresh(records, github=FakeGitHub(live))

    def test_branch_set_race_denied(self):
        records = (self.record("master", MASTER, state="UNOWNED"),)
        github = FakeGitHub([Branch("master", MASTER)], after=[Branch("master", "f" * 40)])
        with self.assertRaises(BranchOwnershipRegistryRefreshError):
            self.run_refresh(records, github=github)

    def test_active_terminal_baseline_must_be_ancestral(self):
        records = (
            self.record("master", MASTER, state="UNOWNED"),
            self.record("mission/x", "e" * 40),
        )
        with self.assertRaises(BranchOwnershipRegistryRefreshError):
            self.run_refresh(
                records,
                github=FakeGitHub(
                    [Branch(r.branch, r.branch_head_sha) for r in records],
                    ancestry="DIVERGED",
                ),
            )

    def test_existing_record_contract_rejects_unknown_or_invalid_bindings(self):
        with self.assertRaises(ValueError):
            self.record("mission/x", "e" * 40, state="UNKNOWN")
        with self.assertRaises(ValueError):
            replace(self.record("mission/x", "e" * 40), mission_id=None).validate()
        with self.assertRaises(ValueError):
            replace(self.record("master", MASTER, state="UNOWNED"), mission_id="X").validate()
        with self.assertRaises(ValueError):
            replace(self.record("mission/x", "e" * 40), superseded_by_branch="mission/y").validate()

    def test_current_registry_change_before_effect_denied(self):
        records = (self.record("master", MASTER, state="UNOWNED"),)
        _, digest = self.write_manifest(records)
        real = Path.read_bytes
        calls = {"n": 0}

        def changed(path):
            raw = real(path)
            if path == self.registry_path:
                calls["n"] += 1
                if calls["n"] >= 2:
                    return raw + b" "
            return raw

        with mock.patch.object(Path, "read_bytes", changed):
            with self.assertRaises(BranchOwnershipRegistryRefreshError):
                refresh_branch_ownership_registry(
                    expected_master=MASTER,
                    expected_master_tree=TREE,
                    manifest_sha256=digest,
                    github=FakeGitHub([Branch("master", MASTER)]),
                    manifest_path=self.manifest_path,
                    registry_path=self.registry_path,
                )

    def test_runtime_effect_is_single_registry_file(self):
        records = (self.record("master", MASTER, state="UNOWNED"),)
        _, result = self.run_refresh(records)
        self.assertEqual(result["registry_path"], str(self.registry_path))
        self.assertEqual(set(Path(self.tmp.name).iterdir()), {self.manifest_path, self.registry_path})


if __name__ == "__main__":
    unittest.main()
