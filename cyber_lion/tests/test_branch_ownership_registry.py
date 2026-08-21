from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest

from cyber_lion.contracts.branch_ownership_registry import (
    BranchOwnershipProviderConfig,
    BranchOwnershipRecord,
    BranchOwnershipRegistrySnapshot,
    REGISTRY_PATH,
)
from cyber_lion.enterprise.branch_ownership_registry import (
    BranchOwnershipRegistryError,
    FileBranchOwnershipRegistryProvider,
    canonical_registry_bytes,
)

REPO = "DonkeyJJLove/ai_platform"
HEAD = "a" * 40
BASE = "b" * 40


class BranchOwnershipRegistryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.registry = Path(self.tmp.name) / "branch-ownership-registry.json"
        self.config = BranchOwnershipProviderConfig(
            repository=REPO,
            source_instance_id="lion-runtime-reconciliation-source-01",
        ).validate()

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def record(self, **overrides):
        values = dict(
            repository=REPO,
            branch="mission/example",
            branch_head_sha=HEAD,
            ownership_state="TERMINAL",
            mission_id="MISSION-EXAMPLE",
            baseline_sha=BASE,
            superseded_by_branch=None,
            supersession_provenance_ref=None,
            source_provenance_ref="registry:test",
            epistemic_class="ANCHORED",
            record_revision=1,
        )
        values.update(overrides)
        return BranchOwnershipRecord(**values).validate()

    def snapshot(self, records=None, *, revision=1):
        if records is None:
            records = (self.record(),)
        return BranchOwnershipRegistrySnapshot.build(
            schema_version="1.0.0",
            repository=REPO,
            source_instance_id="lion-runtime-reconciliation-source-01",
            registry_revision=revision,
            observed_at="2026-08-21T21:00:00+00:00",
            records=tuple(records),
        )

    def write(self, snapshot):
        self.registry.write_bytes(canonical_registry_bytes(snapshot))

    def provider(self):
        return FileBranchOwnershipRegistryProvider(
            self.config,
            physical_registry_path=self.registry,
        )

    def test_owned_terminal(self):
        self.write(self.snapshot())
        evidence = self.provider().resolve(REPO, "mission/example", HEAD)
        self.assertEqual(evidence.ownership_state, "TERMINAL")
        self.assertEqual(evidence.mission_id, "MISSION-EXAMPLE")
        self.assertEqual(evidence.baseline_sha, BASE)

    def test_owned_active(self):
        record = self.record(ownership_state="ACTIVE")
        self.write(self.snapshot((record,)))
        evidence = self.provider().resolve(REPO, record.branch, HEAD)
        self.assertEqual(evidence.ownership_state, "ACTIVE")

    def test_unowned(self):
        record = self.record(
            ownership_state="UNOWNED",
            mission_id=None,
            baseline_sha=None,
            epistemic_class="OBSERVED",
        )
        self.write(self.snapshot((record,)))
        evidence = self.provider().resolve(REPO, record.branch, HEAD)
        self.assertEqual(evidence.ownership_state, "UNOWNED")
        self.assertIsNone(evidence.mission_id)

    def test_stale_head_denied(self):
        self.write(self.snapshot())
        with self.assertRaises(BranchOwnershipRegistryError):
            self.provider().resolve(REPO, "mission/example", "c" * 40)

    def test_unknown_denied(self):
        self.write(self.snapshot())
        with self.assertRaises(BranchOwnershipRegistryError):
            self.provider().resolve(REPO, "mission/missing", HEAD)
        with self.assertRaises(ValueError):
            self.record(ownership_state="UNKNOWN")

    def test_missing_baseline_and_mission_denied(self):
        with self.assertRaises(ValueError):
            self.record(baseline_sha=None)
        with self.assertRaises(ValueError):
            self.record(mission_id=None)

    def test_missing_provenance_denied(self):
        with self.assertRaises(ValueError):
            self.record(source_provenance_ref="")

    def test_conflict_and_duplicate_denied(self):
        first = self.record()
        duplicate = self.record()
        with self.assertRaises(ValueError):
            self.snapshot((first, duplicate))
        conflict = self.record(branch_head_sha="c" * 40, record_revision=2)
        with self.assertRaises(ValueError):
            self.snapshot((first, conflict))

    def test_supersession_requires_explicit_provenance(self):
        with self.assertRaises(ValueError):
            self.record(superseded_by_branch="mission/new", supersession_provenance_ref=None)
        record = self.record(
            superseded_by_branch="mission/new",
            supersession_provenance_ref="supersession:test",
        )
        self.write(self.snapshot((record,)))
        evidence = self.provider().resolve(REPO, record.branch, HEAD)
        self.assertEqual(evidence.superseded_by_branch, "mission/new")

    def test_registry_revision_rollback_and_collision_denied(self):
        first = self.snapshot(revision=2)
        self.write(first)
        provider = self.provider()
        provider.resolve(REPO, "mission/example", HEAD)

        rollback = BranchOwnershipRegistrySnapshot.build(
            schema_version="1.0.0",
            repository=REPO,
            source_instance_id="lion-runtime-reconciliation-source-01",
            registry_revision=1,
            observed_at="2026-08-21T21:01:00+00:00",
            records=(self.record(record_revision=2),),
        )
        self.write(rollback)
        with self.assertRaises(BranchOwnershipRegistryError):
            provider.resolve(REPO, "mission/example", HEAD)

        changed = BranchOwnershipRegistrySnapshot.build(
            schema_version="1.0.0",
            repository=REPO,
            source_instance_id="lion-runtime-reconciliation-source-01",
            registry_revision=2,
            observed_at="2026-08-21T21:02:00+00:00",
            records=(self.record(source_provenance_ref="registry:changed"),),
        )
        self.write(changed)
        with self.assertRaises(BranchOwnershipRegistryError):
            provider.resolve(REPO, "mission/example", HEAD)

    def test_deterministic_canonical_records(self):
        a = self.record(branch="mission/a", branch_head_sha="c" * 40)
        z = self.record(branch="mission/z", branch_head_sha="d" * 40)
        one = self.snapshot((z, a))
        two = self.snapshot((a, z))
        self.assertEqual(one.registry_digest, two.registry_digest)
        self.assertEqual(canonical_registry_bytes(one), canonical_registry_bytes(two))

    def test_provider_contract_path_is_exact(self):
        self.assertEqual(self.config.registry_path, REGISTRY_PATH)


if __name__ == "__main__":
    unittest.main()
