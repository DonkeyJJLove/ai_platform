from __future__ import annotations

from datetime import datetime, timezone
import inspect
from pathlib import Path
import sqlite3
import tempfile
import unittest

from cyber_lion.contracts.fleet_reconciliation import ReconciliationTrustPins
from cyber_lion.contracts.fleet_runtime_composition import (
    COORDINATION_DB_PATH,
    RECONCILIATION_DB_PATH,
    RUNTIME_ROOT,
    STATUS_DB_PATH,
    FleetRuntimeCompositionContractError,
    RuntimeCompositionConfig,
)
from cyber_lion.contracts.fleet_status import VerificationTrustPins
from cyber_lion.enterprise import fleet_runtime_composition as composition_module
from cyber_lion.enterprise.fleet_runtime_composition import (
    FleetRuntimeCompositionError,
    bootstrap_runtime_composition,
    open_runtime_composition,
)

REPO = "DonkeyJJLove/ai_platform"
MASTER = "6" * 40
TREE = "9" * 40
NOW = datetime(2026, 8, 21, 18, 0, tzinfo=timezone.utc)
VPINS = VerificationTrustPins(
    verifier_id="F005-H-verifier",
    verifier_identity_digest="1" * 64,
    verifier_implementation_digest="2" * 64,
    trust_anchor_id="F005-H-verification-anchor",
    trust_anchor_digest="3" * 64,
)
RPINS = ReconciliationTrustPins(
    source_id="F005-H-repository-source",
    source_instance_id="F005-H-repository-source-01",
    source_implementation_digest="4" * 64,
    trust_anchor_id="F005-H-reconciliation-anchor",
)


class RuntimeCompositionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "runtime" / "f005"
        self.paths = {
            "root": self.root,
            "status": self.root / "status.sqlite",
            "coordination": self.root / "coordination.sqlite",
            "reconciliation": self.root / "reconciliation.sqlite",
        }

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def config(self, **overrides) -> RuntimeCompositionConfig:
        values = dict(
            repository=REPO,
            current_master=MASTER,
            current_master_tree=TREE,
            composition_instance_id="lion-runtime-01",
            registry_instance_id="fleet-status-runtime-01",
            coordinator_instance_id="fleet-coordinator-runtime-01",
            verification_pins=VPINS,
            reconciliation_pins=RPINS,
        )
        values.update(overrides)
        return RuntimeCompositionConfig(**values).validate()

    def bootstrap(self, config: RuntimeCompositionConfig | None = None):
        return bootstrap_runtime_composition(
            config or self.config(),
            clock=lambda: NOW,
            physical_paths=self.paths,
        )

    def test_contract_binds_exact_windows_runtime_paths(self):
        config = self.config()
        self.assertEqual(config.runtime_root, RUNTIME_ROOT)
        self.assertEqual(config.status_db_path, STATUS_DB_PATH)
        self.assertEqual(config.coordination_db_path, COORDINATION_DB_PATH)
        self.assertEqual(config.reconciliation_db_path, RECONCILIATION_DB_PATH)
        with self.assertRaises(FleetRuntimeCompositionContractError):
            self.config(status_db_path=r"C:\LION\runtime\other\status.sqlite")

    def test_bootstrap_uses_canonical_stores_and_empty_state_is_not_closable(self):
        receipt = self.bootstrap()
        self.assertTrue(self.paths["status"].is_file())
        self.assertTrue(self.paths["coordination"].is_file())
        self.assertTrue(self.paths["reconciliation"].is_file())
        self.assertEqual(receipt.state_classification, "EMPTY_NOT_CLOSABLE")
        self.assertFalse(receipt.closable)
        self.assertEqual(receipt.status_mission_count, 0)
        self.assertEqual(receipt.coordination_mission_count, 0)
        self.assertEqual(receipt.reconciliation_inventory_count, 0)

        status = sqlite3.connect(self.paths["status"])
        coordination = sqlite3.connect(self.paths["coordination"])
        reconciliation = sqlite3.connect(self.paths["reconciliation"])
        try:
            self.assertEqual(status.execute("SELECT COUNT(*) FROM fleet_identity").fetchone()[0], 0)
            self.assertEqual(status.execute("SELECT COUNT(*) FROM fleet_runtime").fetchone()[0], 0)
            self.assertEqual(status.execute("SELECT COUNT(*) FROM fleet_receipt").fetchone()[0], 0)
            self.assertEqual(
                coordination.execute(
                    "SELECT COUNT(*) FROM fleet_coordination_mission"
                ).fetchone()[0],
                0,
            )
            self.assertEqual(
                reconciliation.execute(
                    "SELECT COUNT(*) FROM reconciliation_report"
                ).fetchone()[0],
                0,
            )
        finally:
            status.close()
            coordination.close()
            reconciliation.close()

    def test_canonical_schema_is_derived_from_store_constructors(self):
        canonical = composition_module._derive_canonical_schema_fingerprints(
            self.config(),
            verification_source=composition_module.FailClosedVerificationSource(),
            clock=lambda: NOW,
        )
        status_names = {
            item["name"] for item in canonical["status"]["objects"]
        }
        coordination_names = {
            item["name"] for item in canonical["coordination"]["objects"]
        }
        self.assertIn("fleet_source_batch", status_names)
        self.assertIn("fleet_source_observation", status_names)
        self.assertIn("fleet_source_checkpoint", status_names)
        self.assertIn("fleet_event_no_update", status_names)
        self.assertIn("fleet_coordination_dependency", coordination_names)
        self.assertIn("fleet_coordination_plan", coordination_names)
        self.assertIn("fleet_coordination_plan_no_update", coordination_names)

    def test_bootstrap_reopen_preserves_semantic_state(self):
        first = self.bootstrap()
        second = self.bootstrap()
        self.assertEqual(first.composition_id, second.composition_id)
        self.assertEqual(first.composition_digest, second.composition_digest)
        self.assertEqual(first.state_classification, "EMPTY_NOT_CLOSABLE")
        self.assertEqual(second.state_classification, "EMPTY_NOT_CLOSABLE")

    def test_existing_projection_path_is_reused_without_writes(self):
        self.bootstrap()
        runtime = open_runtime_composition(
            self.config(), clock=lambda: NOW, physical_paths=self.paths
        )
        try:
            before = runtime.semantic_fingerprint()
            snapshot = runtime.status_snapshot()
            after = runtime.semantic_fingerprint()
            self.assertEqual(snapshot.aggregate.total_known_drones, 0)
            self.assertEqual(before, after)
        finally:
            runtime.close()

    def test_partial_bootstrap_is_denied(self):
        self.root.mkdir(parents=True)
        self.paths["status"].touch()
        with self.assertRaises(FleetRuntimeCompositionError):
            open_runtime_composition(
                self.config(), clock=lambda: NOW, physical_paths=self.paths
            )

    def test_registry_instance_substitution_is_denied_before_reopen(self):
        self.bootstrap()
        wrong = self.config(registry_instance_id="other-registry")
        with self.assertRaises(FleetRuntimeCompositionError):
            open_runtime_composition(wrong, clock=lambda: NOW, physical_paths=self.paths)

    def test_coordinator_instance_substitution_is_denied_before_reopen(self):
        self.bootstrap()
        wrong = self.config(coordinator_instance_id="other-coordinator")
        with self.assertRaises(FleetRuntimeCompositionError):
            open_runtime_composition(wrong, clock=lambda: NOW, physical_paths=self.paths)

    def test_missing_canonical_table_is_denied_without_silent_repair(self):
        self.bootstrap()
        conn = sqlite3.connect(self.paths["status"])
        conn.execute("DROP TABLE fleet_source_checkpoint")
        conn.commit()
        conn.close()

        with self.assertRaises(FleetRuntimeCompositionError):
            open_runtime_composition(
                self.config(), clock=lambda: NOW, physical_paths=self.paths
            )

        conn = sqlite3.connect(self.paths["status"])
        try:
            names = {
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            }
            self.assertNotIn("fleet_source_checkpoint", names)
        finally:
            conn.close()

    def test_missing_canonical_column_is_denied(self):
        self.bootstrap()
        conn = sqlite3.connect(self.paths["status"])
        conn.execute("PRAGMA foreign_keys=OFF")
        conn.execute("ALTER TABLE fleet_mission RENAME TO fleet_mission_original")
        conn.execute("CREATE TABLE fleet_mission(mission_id TEXT PRIMARY KEY)")
        conn.execute("DROP TABLE fleet_mission_original")
        conn.commit()
        conn.close()
        with self.assertRaises(FleetRuntimeCompositionError):
            open_runtime_composition(
                self.config(), clock=lambda: NOW, physical_paths=self.paths
            )

    def test_missing_canonical_trigger_is_denied(self):
        self.bootstrap()
        conn = sqlite3.connect(self.paths["status"])
        conn.execute("DROP TRIGGER fleet_event_no_update")
        conn.commit()
        conn.close()
        with self.assertRaises(FleetRuntimeCompositionError):
            open_runtime_composition(
                self.config(), clock=lambda: NOW, physical_paths=self.paths
            )

    def test_altered_canonical_schema_with_extra_object_is_denied(self):
        self.bootstrap()
        conn = sqlite3.connect(self.paths["reconciliation"])
        conn.execute("CREATE TABLE unexpected_schema_object(value TEXT)")
        conn.commit()
        conn.close()
        with self.assertRaises(FleetRuntimeCompositionError):
            open_runtime_composition(
                self.config(), clock=lambda: NOW, physical_paths=self.paths
            )

    def test_configuration_digest_binds_repository_instances_and_trust_pins(self):
        original = self.config()
        changed = self.config(composition_instance_id="lion-runtime-02")
        changed_pins = self.config(
            reconciliation_pins=ReconciliationTrustPins(
                source_id=RPINS.source_id,
                source_instance_id="other-source-instance",
                source_implementation_digest=RPINS.source_implementation_digest,
                trust_anchor_id=RPINS.trust_anchor_id,
            )
        )
        changed_repository = self.config(repository="DonkeyJJLove/other")
        self.assertNotEqual(original.digest(), changed.digest())
        self.assertNotEqual(original.digest(), changed_pins.digest())
        self.assertNotEqual(original.digest(), changed_repository.digest())

    def test_composition_does_not_duplicate_persistence_ddl_or_fabricate_state(self):
        source = inspect.getsource(composition_module)
        self.assertNotIn("CREATE TABLE IF NOT EXISTS", source)
        self.assertNotIn("CREATE TRIGGER IF NOT EXISTS", source)
        for forbidden in (
            ".register_identity(",
            ".bind_runtime(",
            ".record_heartbeat(",
            ".record_inventory(",
            ".issue_convergence_receipt(",
            ".close_mission(",
        ):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()