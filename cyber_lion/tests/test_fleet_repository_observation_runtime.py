from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest import mock

from cyber_lion.contracts.fleet_repository_observation_source import ObservationReceipt
from cyber_lion.enterprise import fleet_repository_observation_runtime as runtime


MASTER = "1" * 40
TREE = "2" * 40


class RuntimeCompositionTests(unittest.TestCase):
    def paths(self, root: Path):
        source = root / "reconciliation-source"
        return SimpleNamespace(
            repository_inventory_path=str(source / "repository-inventory.json"),
            branch_ownership_registry_path=str(source / "branch-ownership-registry.json"),
        )

    def test_runtime_composes_live_source_and_file_ownership_provider(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            paths = self.paths(root)
            github = object()
            provider = object()
            receipt = ObservationReceipt(
                repository="DonkeyJJLove/ai_platform",
                observed_master=MASTER,
                observed_master_tree=TREE,
                inventory_revision=7,
                branch_count=21,
                output_sha256="a" * 64,
                materialized=True,
                asserts_fleet_close=False,
            ).validate()
            with (
                mock.patch.object(runtime, "resolve_fleet_runtime_paths", return_value=paths),
                mock.patch.object(runtime.GitHubRESTReadSource, "from_environment", return_value=github),
                mock.patch.object(runtime, "FileBranchOwnershipRegistryProvider", return_value=provider) as provider_cls,
                mock.patch.object(runtime, "materialize_observation", return_value=receipt) as materialize,
            ):
                result = runtime.run_runtime_observation(
                    expected_master=MASTER,
                    expected_master_tree=TREE,
                    inventory_revision=7,
                )

            self.assertEqual(result["observed_master"], MASTER)
            self.assertTrue(result["materialized"])
            provider_config = provider_cls.call_args.args[0]
            self.assertEqual(provider_config.registry_path, paths.branch_ownership_registry_path)
            self.assertEqual(provider_config.minimum_registry_revision, 1)
            config = materialize.call_args.args[0]
            self.assertEqual(config.output_path, paths.repository_inventory_path)
            self.assertEqual(config.expected_master, MASTER)
            self.assertEqual(config.expected_master_tree, TREE)
            self.assertEqual(config.inventory_revision, 7)
            self.assertIs(materialize.call_args.kwargs["github"], github)
            self.assertIs(materialize.call_args.kwargs["ownership"], provider)

    def test_existing_output_is_denied_before_composition(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            paths = self.paths(root)
            output = Path(paths.repository_inventory_path)
            output.parent.mkdir(parents=True)
            output.write_bytes(b"existing")
            with mock.patch.object(runtime, "resolve_fleet_runtime_paths", return_value=paths):
                with self.assertRaises(runtime.RepositoryObservationRuntimeError):
                    runtime.run_runtime_observation(
                        expected_master=MASTER,
                        expected_master_tree=TREE,
                        inventory_revision=1,
                    )

    def test_cli_repository_substitution_is_denied(self):
        with self.assertRaises(runtime.RepositoryObservationRuntimeError):
            runtime.main([
                "--repository", "other/repo",
                "--expected-master", MASTER,
                "--expected-master-tree", TREE,
                "--inventory-revision", "1",
            ])

    def test_cli_inventory_revision_must_be_integer(self):
        with self.assertRaises(SystemExit):
            runtime.main([
                "--repository", "DonkeyJJLove/ai_platform",
                "--expected-master", MASTER,
                "--expected-master-tree", TREE,
                "--inventory-revision", "not-an-int",
            ])


if __name__ == "__main__":
    unittest.main()
