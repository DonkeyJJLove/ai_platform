from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import tempfile
import unittest

from cyber_lion.contracts.fleet_repository_observation_source import (
    AncestryEvidence,
    LiveBranch,
    ObservationConfig,
    OwnershipEvidence,
)
from cyber_lion.enterprise.fleet_repository_observation_source import (
    RepositoryObservationSourceError,
    materialize_observation,
    produce_observation_bytes,
)

REPO = "DonkeyJJLove/ai_platform"
MASTER = "a" * 40
TREE = "b" * 40
BASE = "c" * 40
HEAD1 = "d" * 40
HEAD2 = "e" * 40


class FakeGitHub:
    def __init__(self, pages, *, after_pages=None, master=MASTER, tree=TREE, ancestry=None):
        self.pages = pages
        self.after_pages = after_pages if after_pages is not None else pages
        self.master = master
        self.tree = tree
        self.ancestry = ancestry or {}
        self.enumerations = 0

    def default_head(self, repository, default_branch):
        self.assert_binding(repository, default_branch)
        return self.master, self.tree

    def assert_binding(self, repository, default_branch):
        if repository != REPO or default_branch != "master":
            raise AssertionError("binding mismatch")

    def list_branches_page(self, repository, cursor):
        if repository != REPO:
            raise AssertionError("repo mismatch")
        active = self.pages if self.enumerations == 0 else self.after_pages
        index = 0 if cursor is None else int(cursor)
        page = active[index]
        next_cursor = str(index + 1) if index + 1 < len(active) else None
        if next_cursor is None:
            self.enumerations += 1
        return tuple(page), next_cursor

    def compare_to_default(self, repository, default_head, branch_head, branch):
        if repository != REPO or default_head != MASTER:
            raise AssertionError("compare binding mismatch")
        return self.ancestry.get(
            branch,
            AncestryEvidence(branch, "HEAD_ANCESTOR_OF_DEFAULT", 0, 1),
        )


class FakeOwnership:
    def __init__(self, values):
        self.values = values

    def resolve(self, repository, branch, branch_head):
        if repository != REPO:
            raise AssertionError("repo mismatch")
        return self.values[branch]


def owned(branch, *, provenance="ownership:registry", superseded=None, supersession_ref=None):
    return OwnershipEvidence(
        branch=branch,
        ownership_state="TERMINAL",
        mission_id="MISSION-" + branch.split("/")[-1].upper(),
        baseline_sha=BASE,
        superseded_by_branch=superseded,
        supersession_provenance_ref=supersession_ref,
        source_provenance_ref=provenance,
        epistemic_class="OBSERVED",
    )


class RepositoryObservationSourceTests(unittest.TestCase):
    def config(self):
        return ObservationConfig(REPO, MASTER, TREE, 1).validate()

    def clock(self):
        return datetime(2026, 8, 21, 21, 0, 0, tzinfo=timezone.utc)

    def stable_source(self):
        pages = [
            [LiveBranch("master", MASTER), LiveBranch("mission/a", HEAD1)],
            [LiveBranch("mission/b", HEAD2)],
        ]
        ancestry = {
            "mission/a": AncestryEvidence("mission/a", "HEAD_ANCESTOR_OF_DEFAULT", 0, 2),
            "mission/b": AncestryEvidence("mission/b", "DIVERGED", 1, 3),
        }
        ownership = FakeOwnership({"mission/a": owned("mission/a"), "mission/b": owned("mission/b")})
        return FakeGitHub(pages, ancestry=ancestry), ownership

    def test_pagination_complete_and_deterministic_output(self):
        github, ownership = self.stable_source()
        raw1, receipt1 = produce_observation_bytes(self.config(), github=github, ownership=ownership, clock=self.clock)
        github2, ownership2 = self.stable_source()
        raw2, receipt2 = produce_observation_bytes(self.config(), github=github2, ownership=ownership2, clock=self.clock)
        self.assertEqual(raw1, raw2)
        self.assertEqual(receipt1.output_sha256, receipt2.output_sha256)
        self.assertEqual(receipt1.branch_count, 2)
        text = raw1.decode("utf-8")
        self.assertLess(text.index('"branch":"mission/a"'), text.index('"branch":"mission/b"'))
        self.assertNotIn('"branch":"master"', text)

    def test_branch_set_race_denied(self):
        pages = [[LiveBranch("master", MASTER), LiveBranch("mission/a", HEAD1)]]
        after = [[LiveBranch("master", MASTER), LiveBranch("mission/a", HEAD2)]]
        github = FakeGitHub(pages, after_pages=after)
        ownership = FakeOwnership({"mission/a": owned("mission/a")})
        with self.assertRaises(RepositoryObservationSourceError):
            produce_observation_bytes(self.config(), github=github, ownership=ownership, clock=self.clock)

    def test_unknown_ownership_denied(self):
        pages = [[LiveBranch("master", MASTER), LiveBranch("mission/a", HEAD1)]]
        unknown = OwnershipEvidence("mission/a", "UNKNOWN", None, None, None, None, "ownership:registry", "OBSERVED")
        with self.assertRaises(RepositoryObservationSourceError):
            produce_observation_bytes(self.config(), github=FakeGitHub(pages), ownership=FakeOwnership({"mission/a": unknown}), clock=self.clock)

    def test_missing_baseline_denied(self):
        pages = [[LiveBranch("master", MASTER), LiveBranch("mission/a", HEAD1)]]
        bad = OwnershipEvidence("mission/a", "TERMINAL", "MISSION-A", None, None, None, "ownership:registry", "OBSERVED")
        with self.assertRaises(RepositoryObservationSourceError):
            produce_observation_bytes(self.config(), github=FakeGitHub(pages), ownership=FakeOwnership({"mission/a": bad}), clock=self.clock)

    def test_missing_provenance_denied(self):
        pages = [[LiveBranch("master", MASTER), LiveBranch("mission/a", HEAD1)]]
        bad = OwnershipEvidence("mission/a", "TERMINAL", "MISSION-A", BASE, None, None, "", "OBSERVED")
        with self.assertRaises(RepositoryObservationSourceError):
            produce_observation_bytes(self.config(), github=FakeGitHub(pages), ownership=FakeOwnership({"mission/a": bad}), clock=self.clock)

    def test_unknown_ancestry_denied(self):
        pages = [[LiveBranch("master", MASTER), LiveBranch("mission/a", HEAD1)]]
        ancestry = {"mission/a": AncestryEvidence("mission/a", "UNKNOWN", None, None)}
        with self.assertRaises(RepositoryObservationSourceError):
            produce_observation_bytes(self.config(), github=FakeGitHub(pages, ancestry=ancestry), ownership=FakeOwnership({"mission/a": owned("mission/a")}), clock=self.clock)

    def test_supersession_requires_explicit_provenance(self):
        pages = [[LiveBranch("master", MASTER), LiveBranch("mission/a", HEAD1)]]
        bad = owned("mission/a", superseded="mission/b", supersession_ref=None)
        with self.assertRaises(RepositoryObservationSourceError):
            produce_observation_bytes(self.config(), github=FakeGitHub(pages), ownership=FakeOwnership({"mission/a": bad}), clock=self.clock)

    def test_master_drift_denied_before_observation(self):
        github, ownership = self.stable_source()
        github.master = "f" * 40
        with self.assertRaises(RepositoryObservationSourceError):
            produce_observation_bytes(self.config(), github=github, ownership=ownership, clock=self.clock)

    def test_materialization_is_exclusive_and_immutable(self):
        github, ownership = self.stable_source()
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp).resolve() / "repository-inventory.json"
            receipt = materialize_observation(self.config(), github=github, ownership=ownership, clock=self.clock, physical_output=target)
            self.assertTrue(receipt.materialized)
            self.assertTrue(target.is_file())
            github2, ownership2 = self.stable_source()
            with self.assertRaises(RepositoryObservationSourceError):
                materialize_observation(self.config(), github=github2, ownership=ownership2, clock=self.clock, physical_output=target)


if __name__ == "__main__":
    unittest.main()
