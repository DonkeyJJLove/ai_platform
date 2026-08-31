from __future__ import annotations

from dataclasses import fields, replace
from pathlib import Path
import json
import unittest

from cyber_lion.contracts.repository_expansion import (
    FleetRegistryPinSnapshot,
    RegisteredRepository,
    RegistryMember,
    RepositoryExpansionContractError,
    RepositoryPinObservation,
    materialize_registry_pin_snapshot,
    registry_semantic_digest,
)


REGISTRY_PATH = Path("cyber_lion/registry/repositories.json")
MEMBERS = (
    ("DonkeyJJLove/ai_platform", "master"),
    ("DonkeyJJLove/chunk-chunk", "master"),
    ("DonkeyJJLove/glitchlab", "master"),
    ("DonkeyJJLove/HA2D", "master"),
    ("DonkeyJJLove/hipotezy_nadawcze_LLM", "main"),
    ("DonkeyJJLove/mosaic_lab_pro.py", "main"),
    ("DonkeyJJLove/sbom", "main"),
    ("DonkeyJJLove/swarm", "master"),
    ("DonkeyJJLove/SymulacjaKaskadySieciowej", "main"),
    ("DonkeyJJLove/writeups", "master"),
)


class FleetRegistryPinMaterializationTests(unittest.TestCase):
    def registry(self) -> bytes:
        return REGISTRY_PATH.read_bytes()

    def observations(self) -> tuple[RepositoryPinObservation, ...]:
        result = []
        for index, (repository, branch) in enumerate(MEMBERS, start=1):
            result.append(
                RepositoryPinObservation(
                    repository=repository,
                    default_branch=branch,
                    head=f"{index:040x}",
                    tree=f"{index + 100:040x}",
                    manifest_present=repository != "DonkeyJJLove/writeups",
                    source_ref=f"github-read:{repository}:{branch}:{index}",
                ).validate()
            )
        return tuple(result)

    def snapshot(self) -> FleetRegistryPinSnapshot:
        return materialize_registry_pin_snapshot(self.registry(), self.observations())

    def test_real_registry_materializes_exact_ten_members(self):
        snapshot = self.snapshot()
        self.assertEqual(len(snapshot.members), 10)
        self.assertEqual(len(snapshot.observations), 10)
        self.assertEqual(
            tuple((item.repository, item.default_branch) for item in snapshot.members),
            tuple(sorted(MEMBERS)),
        )
        self.assertEqual(snapshot.registry_digest, registry_semantic_digest(self.registry()))

    def test_registered_repository_projection_is_exact_and_sorted(self):
        snapshot = self.snapshot()
        registered = snapshot.registered_repositories()
        self.assertEqual(len(registered), 10)
        self.assertTrue(all(type(item) is RegisteredRepository for item in registered))
        self.assertEqual(
            tuple(item.repository for item in registered),
            tuple(sorted(repository for repository, _ in MEMBERS)),
        )
        by_repo = {item.repository: item for item in self.observations()}
        for item in registered:
            observed = by_repo[item.repository]
            self.assertEqual(item.default_branch, observed.default_branch)
            self.assertEqual(item.expected_head, observed.head)
            self.assertEqual(item.expected_tree, observed.tree)

    def test_missing_extra_and_duplicate_observations_are_rejected(self):
        observations = self.observations()
        with self.assertRaises(RepositoryExpansionContractError):
            materialize_registry_pin_snapshot(self.registry(), observations[:-1])
        extra = RepositoryPinObservation(
            "DonkeyJJLove/not-registered",
            "main",
            "a" * 40,
            "b" * 40,
            False,
            "github-read:extra",
        )
        with self.assertRaises(RepositoryExpansionContractError):
            materialize_registry_pin_snapshot(self.registry(), observations + (extra,))
        with self.assertRaises(RepositoryExpansionContractError):
            materialize_registry_pin_snapshot(self.registry(), observations + (observations[0],))

    def test_default_branch_substitution_is_rejected(self):
        observations = list(self.observations())
        observations[0] = replace(observations[0], default_branch="main")
        with self.assertRaises(RepositoryExpansionContractError):
            materialize_registry_pin_snapshot(self.registry(), tuple(observations))

    def test_malformed_head_tree_and_source_ref_are_rejected(self):
        observation = self.observations()[0]
        with self.assertRaises(RepositoryExpansionContractError):
            replace(observation, head="A" * 40).validate()
        with self.assertRaises(RepositoryExpansionContractError):
            replace(observation, tree="0" * 39).validate()
        with self.assertRaises(RepositoryExpansionContractError):
            replace(observation, source_ref="bad\x00source").validate()

    def test_snapshot_digest_is_order_independent(self):
        observations = self.observations()
        first = materialize_registry_pin_snapshot(self.registry(), observations)
        second = materialize_registry_pin_snapshot(self.registry(), tuple(reversed(observations)))
        self.assertEqual(first.snapshot_digest(), second.snapshot_digest())
        self.assertEqual(first.canonical_dict(), second.canonical_dict())

    def test_pin_change_changes_snapshot_without_changing_registry_digest(self):
        first = self.snapshot()
        observations = list(self.observations())
        observations[0] = replace(observations[0], head="f" * 40)
        second = materialize_registry_pin_snapshot(self.registry(), tuple(observations))
        self.assertEqual(first.registry_digest, second.registry_digest)
        self.assertNotEqual(first.snapshot_digest(), second.snapshot_digest())

    def test_manifest_absence_is_preserved_not_promoted(self):
        snapshot = self.snapshot()
        by_repo = {item.repository: item for item in snapshot.observations}
        self.assertFalse(by_repo["DonkeyJJLove/writeups"].manifest_present)
        self.assertTrue(all(
            item.manifest_present
            for item in snapshot.observations
            if item.repository != "DonkeyJJLove/writeups"
        ))
        changed = tuple(
            replace(item, manifest_present=True)
            if item.repository == "DonkeyJJLove/writeups"
            else item
            for item in snapshot.observations
        )
        promoted = FleetRegistryPinSnapshot(
            snapshot.schema_version,
            snapshot.registry_digest,
            snapshot.members,
            changed,
        ).validate()
        self.assertNotEqual(snapshot.snapshot_digest(), promoted.snapshot_digest())

    def test_pin_observation_cannot_claim_health_dependencies_or_authority(self):
        self.assertEqual(
            {field.name for field in fields(RepositoryPinObservation)},
            {"repository", "default_branch", "head", "tree", "manifest_present", "source_ref"},
        )
        forbidden = {
            "build_result", "test_result", "failure_classification", "dependencies",
            "dependents", "authority", "gate0", "result",
        }
        self.assertTrue(forbidden.isdisjoint({field.name for field in fields(RepositoryPinObservation)}))

    def test_registry_semantic_change_changes_registry_and_snapshot_digest(self):
        raw = json.loads(self.registry().decode("utf-8"))
        raw["repositories"][0]["maturity"] = "MIXED"
        changed = json.dumps(raw, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        self.assertNotEqual(registry_semantic_digest(self.registry()), registry_semantic_digest(changed))
        self.assertNotEqual(
            self.snapshot().snapshot_digest(),
            materialize_registry_pin_snapshot(changed, self.observations()).snapshot_digest(),
        )

    def test_registry_member_and_root_shape_are_fail_closed(self):
        raw = json.loads(self.registry().decode("utf-8"))
        raw["unexpected"] = True
        with self.assertRaises(RepositoryExpansionContractError):
            registry_semantic_digest(json.dumps(raw).encode("utf-8"))

        raw = json.loads(self.registry().decode("utf-8"))
        raw["repositories"][0]["unexpected"] = True
        with self.assertRaises(RepositoryExpansionContractError):
            registry_semantic_digest(json.dumps(raw).encode("utf-8"))

    def test_duplicate_registry_json_key_is_rejected(self):
        payload = b'{"schema_version":"1.0.0","schema_version":"1.0.0","generated_from":"x","repositories":[]}'
        with self.assertRaises(RepositoryExpansionContractError):
            registry_semantic_digest(payload)

    def test_registry_member_order_is_semantically_irrelevant(self):
        raw = json.loads(self.registry().decode("utf-8"))
        raw["repositories"] = list(reversed(raw["repositories"]))
        reordered = json.dumps(raw, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        first = self.snapshot()
        second = materialize_registry_pin_snapshot(reordered, tuple(reversed(self.observations())))
        self.assertEqual(first.registry_digest, second.registry_digest)
        self.assertEqual(first.snapshot_digest(), second.snapshot_digest())

    def test_registry_member_contract_is_minimal(self):
        member = RegistryMember("DonkeyJJLove/example", "main").validate()
        self.assertEqual(member.canonical_dict(), {"repository": "DonkeyJJLove/example", "default_branch": "main"})


if __name__ == "__main__":
    unittest.main()
