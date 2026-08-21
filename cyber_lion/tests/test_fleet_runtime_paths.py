from __future__ import annotations

import unittest

from cyber_lion.contracts.fleet_runtime_paths import (
    FleetRuntimePathContractError,
    RUNTIME_ROOT_ENV,
    resolve_fleet_runtime_paths,
)

DEPLOYMENT_ROOT = r"C:\Users\d2j3\Documents\LION\runtime\f005"


class FleetRuntimePathTests(unittest.TestCase):
    def test_exact_deployment_root_derives_all_f005_paths(self):
        paths = resolve_fleet_runtime_paths({RUNTIME_ROOT_ENV: DEPLOYMENT_ROOT})
        self.assertEqual(paths.runtime_root, DEPLOYMENT_ROOT)
        self.assertEqual(paths.status_db_path, DEPLOYMENT_ROOT + r"\status.sqlite")
        self.assertEqual(paths.coordination_db_path, DEPLOYMENT_ROOT + r"\coordination.sqlite")
        self.assertEqual(paths.reconciliation_db_path, DEPLOYMENT_ROOT + r"\reconciliation.sqlite")
        self.assertEqual(paths.trust_root, DEPLOYMENT_ROOT + r"\trust")
        self.assertEqual(
            paths.branch_ownership_registry_path,
            DEPLOYMENT_ROOT + r"\reconciliation-source\branch-ownership-registry.json",
        )
        self.assertEqual(
            paths.repository_inventory_path,
            DEPLOYMENT_ROOT + r"\reconciliation-source\repository-inventory.json",
        )
        self.assertEqual(
            paths.fleet_convergence_snapshot_path,
            DEPLOYMENT_ROOT + r"\fleet-convergence-snapshot.json",
        )

    def test_missing_root_fails_closed(self):
        with self.assertRaises(FleetRuntimePathContractError):
            resolve_fleet_runtime_paths({})

    def test_relative_root_fails_closed(self):
        with self.assertRaises(FleetRuntimePathContractError):
            resolve_fleet_runtime_paths({RUNTIME_ROOT_ENV: r"runtime\f005"})

    def test_legacy_c_lion_root_is_denied(self):
        with self.assertRaises(FleetRuntimePathContractError):
            legacy = "C:" + r"\LION\runtime\f005"
            resolve_fleet_runtime_paths({RUNTIME_ROOT_ENV: legacy})

    def test_root_substitution_changes_every_derived_path_consistently(self):
        first = resolve_fleet_runtime_paths({RUNTIME_ROOT_ENV: DEPLOYMENT_ROOT})
        second = resolve_fleet_runtime_paths({RUNTIME_ROOT_ENV: r"D:\LION_DATA\runtime\f005"})
        self.assertNotEqual(first.runtime_root, second.runtime_root)
        for name in (
            "status_db_path",
            "coordination_db_path",
            "reconciliation_db_path",
            "trust_root",
            "verification_trust_path",
            "reconciliation_trust_path",
            "f005_h_pins_path",
            "trust_provisioning_receipt_path",
            "reconciliation_source_root",
            "branch_ownership_manifest_path",
            "branch_ownership_registry_path",
            "repository_inventory_path",
            "fleet_convergence_snapshot_path",
        ):
            self.assertTrue(getattr(first, name).startswith(first.runtime_root))
            self.assertTrue(getattr(second, name).startswith(second.runtime_root))


if __name__ == "__main__":
    unittest.main()
