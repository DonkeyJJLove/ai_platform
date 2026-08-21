from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from cyber_lion.contracts.fleet_reconciliation import ReconciliationTrustPins
from cyber_lion.contracts.fleet_runtime_reconciliation_ingestion import (
    RuntimeReconciliationIngestionConfig,
)
from cyber_lion.contracts.fleet_runtime_paths import resolve_fleet_runtime_paths
from cyber_lion.enterprise.fleet_reconciliation import ReconciliationStore
from cyber_lion.enterprise.fleet_runtime_reconciliation_ingestion import (
    RuntimeReconciliationIngestionError,
    ingest_repository_inventory,
)

REPO = "DonkeyJJLove/ai_platform"
MASTER = "a" * 40
TREE = "b" * 40
DEPLOYMENT_ROOT = r"C:\Users\d2j3\Documents\LION\runtime\f005"
PINS = ReconciliationTrustPins(
    source_id="lion-runtime-reconciliation-source",
    source_instance_id="lion-runtime-reconciliation-source-01",
    source_implementation_digest="1" * 64,
    trust_anchor_id="lion-runtime-reconciliation-root-01",
).validate()


class RuntimeReconciliationIngestionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.env = mock.patch.dict(os.environ, {"LION_FLEET_RUNTIME_ROOT": DEPLOYMENT_ROOT}, clear=False)
        self.env.start()
        self.logical = resolve_fleet_runtime_paths()
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.repo_root = root / "repo"
        self.repo_root.mkdir()
        self.external = root / "external"
        self.external.mkdir()
        self.observation = self.external / "repository-inventory.json"
        self.trust = self.external / "reconciliation-trust.json"
        self.db = self.external / "reconciliation.sqlite"
        self.trust.write_text(json.dumps({
            "source_id": PINS.source_id,
            "source_instance_id": PINS.source_instance_id,
            "source_implementation_digest": PINS.source_implementation_digest,
            "trust_anchor_id": PINS.trust_anchor_id,
        }, sort_keys=True, separators=(",", ":")), encoding="utf-8")
        store = ReconciliationStore(self.db, trust_pins=PINS, clock=lambda: datetime.now(timezone.utc))
        store.close()

    def tearDown(self) -> None:
        self.tmp.cleanup()
        self.env.stop()

    def observation_value(self, *, revision: int = 1, master: str = MASTER, observed_at: str = "2026-08-21T20:45:00+00:00", branches=None):
        if branches is None:
            branches = [{
                "branch": "mission/example",
                "branch_head_sha": "c" * 40,
                "mission_id": "MISSION-EXAMPLE",
                "baseline_sha": "d" * 40,
                "ownership_state": "TERMINAL",
                "ancestry_state": "HEAD_ANCESTOR_OF_DEFAULT",
                "ahead_by": 0,
                "behind_by": 1,
                "superseded_by_branch": None,
                "supersession_provenance_ref": None,
                "source_provenance_ref": "runtime-observation:test",
                "epistemic_class": "OBSERVED",
                "observed_at": observed_at,
            }]
        return {
            "schema_version": "1.0.0",
            "repository": REPO,
            "inventory_revision": revision,
            "default_branch": "master",
            "default_head_sha": master,
            "observed_at": observed_at,
            "branches": branches,
        }

    def write_observation(self, value) -> str:
        raw = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
        self.observation.write_bytes(raw)
        return sha256(raw).hexdigest()

    def trust_digest(self) -> str:
        return sha256(self.trust.read_bytes()).hexdigest()

    def config(self, observation_digest: str, *, master: str = MASTER) -> RuntimeReconciliationIngestionConfig:
        return RuntimeReconciliationIngestionConfig(
            repository=REPO,
            current_master=master,
            current_master_tree=TREE,
            source_instance_id=PINS.source_instance_id,
            observation_sha256=observation_digest,
            trust_sha256=self.trust_digest(),
        ).validate()

    def ingest(self, config):
        return ingest_repository_inventory(
            config,
            observation_file=self.logical.repository_inventory_path,
            reconciliation_trust_file=self.logical.reconciliation_trust_path,
            repository_root=str(self.repo_root),
            physical_paths={
                "observation": self.observation,
                "trust": self.trust,
                "reconciliation": self.db,
            },
        )

    def test_contract_binds_exact_runtime_paths(self):
        cfg = self.config("2" * 64)
        self.assertEqual(cfg.reconciliation_db_path, self.logical.reconciliation_db_path)
        self.assertEqual(cfg.observation_path, self.logical.repository_inventory_path)
        self.assertEqual(cfg.reconciliation_trust_path, self.logical.reconciliation_trust_path)

    def test_first_ingest_records_exact_one_inventory_head_only(self):
        digest = self.write_observation(self.observation_value())
        receipt = self.ingest(self.config(digest))
        self.assertEqual(receipt.inventory_revision, 1)
        self.assertEqual(receipt.branch_count, 1)
        self.assertFalse(receipt.report_generated)
        self.assertFalse(receipt.convergence_receipt_generated)
        self.assertFalse(receipt.convergence_receipt_consumed)
        self.assertFalse(receipt.fleet_close_asserted)
        import sqlite3
        conn = sqlite3.connect(self.db)
        try:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM reconciliation_inventory_head").fetchone()[0], 1)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM reconciliation_report").fetchone()[0], 0)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM convergence_receipt").fetchone()[0], 0)
        finally:
            conn.close()

    def test_monotonic_second_ingest_advances_exactly_once(self):
        first = self.write_observation(self.observation_value())
        first_receipt = self.ingest(self.config(first))
        second_value = self.observation_value(revision=2, observed_at="2026-08-21T20:46:00+00:00")
        second_value["branches"][0]["branch_head_sha"] = "e" * 40
        second = self.write_observation(second_value)
        second_receipt = self.ingest(self.config(second))
        self.assertEqual(first_receipt.inventory_revision, 1)
        self.assertEqual(second_receipt.inventory_revision, 2)
        self.assertNotEqual(first_receipt.inventory_digest, second_receipt.inventory_digest)

    def test_replay_inventory_is_denied(self):
        digest = self.write_observation(self.observation_value())
        cfg = self.config(digest)
        self.ingest(cfg)
        with self.assertRaises(RuntimeReconciliationIngestionError):
            self.ingest(cfg)

    def test_source_substitution_is_denied(self):
        value = json.loads(self.trust.read_text(encoding="utf-8"))
        value["source_instance_id"] = "attacker-source"
        raw = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
        self.trust.write_bytes(raw)
        digest = self.write_observation(self.observation_value())
        cfg = RuntimeReconciliationIngestionConfig(
            repository=REPO,
            current_master=MASTER,
            current_master_tree=TREE,
            source_instance_id=PINS.source_instance_id,
            observation_sha256=digest,
            trust_sha256=sha256(raw).hexdigest(),
        ).validate()
        with self.assertRaises(RuntimeReconciliationIngestionError):
            self.ingest(cfg)

    def test_master_drift_is_denied(self):
        digest = self.write_observation(self.observation_value(master="f" * 40))
        with self.assertRaises(RuntimeReconciliationIngestionError):
            self.ingest(self.config(digest))

    def test_empty_or_incomplete_observation_is_denied(self):
        digest = self.write_observation(self.observation_value(branches=[]))
        with self.assertRaises(RuntimeReconciliationIngestionError):
            self.ingest(self.config(digest))
        bad = self.observation_value()
        del bad["branches"][0]["ownership_state"]
        digest = self.write_observation(bad)
        with self.assertRaises(RuntimeReconciliationIngestionError):
            self.ingest(self.config(digest))

    def test_digest_substitution_is_denied_before_write(self):
        self.write_observation(self.observation_value())
        with self.assertRaises(RuntimeReconciliationIngestionError):
            self.ingest(self.config("9" * 64))


if __name__ == "__main__":
    unittest.main()
