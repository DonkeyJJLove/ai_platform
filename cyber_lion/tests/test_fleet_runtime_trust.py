from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import tempfile
import unittest

from cyber_lion.contracts.fleet_runtime_trust import (
    F005_H_PINS_PATH,
    PROVISIONING_RECEIPT_PATH,
    RECONCILIATION_TRUST_PATH,
    REPOSITORY,
    RUNTIME_INSTANCE_ID,
    VERIFICATION_TRUST_PATH,
    RuntimeTrustProvisioningConfig,
)
from cyber_lion.enterprise.fleet_runtime_trust import (
    FleetRuntimeTrustError,
    provision_runtime_trust,
)
from cyber_lion.enterprise.verifier_identity_runtime import RUNTIME_FACTORY_VERSION


MASTER = sha256(b"F005-I-test-master").hexdigest()[:40]
TREE = sha256(b"F005-I-test-tree").hexdigest()[:40]


class RuntimeTrustProvisioningTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.repo = self.base / "repo"
        self.external = self.base / "external"
        self.output = self.base / "runtime" / "f005" / "trust"
        self.repo.mkdir()
        self.external.mkdir()

        self.verifier_impl = self.external / "verifier.bin"
        self.reconciliation_impl = self.external / "reconciliation.bin"
        self.verifier_impl.write_bytes(b"verified external verifier implementation")
        self.reconciliation_impl.write_bytes(
            b"verified external reconciliation implementation"
        )

        self.verification_anchor = self.external / "verification-anchor.json"
        self.reconciliation_anchor = self.external / "reconciliation-anchor.json"
        self._write_json(
            self.verification_anchor,
            {
                "schema_version": "1.0.0",
                "kind": "VERIFICATION_TRUST_ANCHOR",
                "repository": REPOSITORY,
                "runtime_instance_id": RUNTIME_INSTANCE_ID,
                "trust_anchor_id": "verification-root-prod",
                "anchor": {"type": "external-manifest", "reference": "verification-root-v1"},
            },
        )
        self._write_json(
            self.reconciliation_anchor,
            {
                "schema_version": "1.0.0",
                "kind": "RECONCILIATION_TRUST_ANCHOR",
                "repository": REPOSITORY,
                "runtime_instance_id": RUNTIME_INSTANCE_ID,
                "trust_anchor_id": "reconciliation-root-prod",
                "anchor": {"type": "external-manifest", "reference": "reconciliation-root-v1"},
            },
        )

        self.verification_manifest = self.external / "verification-runtime.json"
        self.reconciliation_manifest = self.external / "reconciliation-runtime.json"
        self._rewrite_runtime_manifests()

    def tearDown(self) -> None:
        self.tmp.cleanup()

    @staticmethod
    def _write_json(path: Path, value: dict) -> None:
        path.write_text(
            json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )

    @staticmethod
    def _digest(path: Path) -> str:
        return sha256(path.read_bytes()).hexdigest()

    def _rewrite_runtime_manifests(self) -> None:
        self._write_json(
            self.verification_manifest,
            {
                "schema_version": "1.0.0",
                "kind": "VERIFICATION_RUNTIME_TRUST",
                "repository": REPOSITORY,
                "runtime_instance_id": RUNTIME_INSTANCE_ID,
                "runtime_factory_version": RUNTIME_FACTORY_VERSION,
                "verifier_id": "verifier-prod-01",
                "verifier_identity": {
                    "subject": "verifier-prod-01",
                    "environment": "lion-runtime",
                },
                "verifier_implementation_sha256": self._digest(self.verifier_impl),
                "trust_anchor_id": "verification-root-prod",
                "trust_anchor_sha256": self._digest(self.verification_anchor),
            },
        )
        self._write_json(
            self.reconciliation_manifest,
            {
                "schema_version": "1.0.0",
                "kind": "RECONCILIATION_RUNTIME_TRUST",
                "repository": REPOSITORY,
                "runtime_instance_id": RUNTIME_INSTANCE_ID,
                "source_id": "reconciliation-source-prod",
                "source_instance_id": "reconciliation-source-prod-01",
                "source_identity": {
                    "provider": "repository-evidence",
                    "environment": "lion-runtime",
                },
                "source_implementation_sha256": self._digest(
                    self.reconciliation_impl
                ),
                "trust_anchor_id": "reconciliation-root-prod",
                "trust_anchor_sha256": self._digest(self.reconciliation_anchor),
            },
        )

    def config(self, **overrides) -> RuntimeTrustProvisioningConfig:
        values = dict(
            repository=REPOSITORY,
            current_master=MASTER,
            current_master_tree=TREE,
            runtime_instance_id=RUNTIME_INSTANCE_ID,
            expected_verifier_id="verifier-prod-01",
            expected_verification_trust_anchor_id="verification-root-prod",
            expected_reconciliation_source_id="reconciliation-source-prod",
            expected_reconciliation_source_instance_id="reconciliation-source-prod-01",
            expected_reconciliation_trust_anchor_id="reconciliation-root-prod",
        )
        values.update(overrides)
        return RuntimeTrustProvisioningConfig(**values).validate()

    def provision(self, **overrides):
        values = dict(
            config=self.config(),
            repository_root=str(self.repo),
            verification_manifest_path=str(self.verification_manifest),
            verifier_implementation_path=str(self.verifier_impl),
            verification_anchor_manifest_path=str(self.verification_anchor),
            reconciliation_manifest_path=str(self.reconciliation_manifest),
            reconciliation_implementation_path=str(self.reconciliation_impl),
            reconciliation_anchor_manifest_path=str(self.reconciliation_anchor),
            physical_output_root=self.output,
        )
        values.update(overrides)
        return provision_runtime_trust(**values)

    def test_provisions_exact_f005_h_pin_shape_without_success_claims(self):
        receipt = self.provision()
        self.assertFalse(receipt.asserts_verification_pass)
        self.assertFalse(receipt.asserts_fleet_closure)

        pins = json.loads((self.output / "f005-h-pins.json").read_text(encoding="utf-8"))
        self.assertEqual(set(pins), {"verification", "reconciliation"})
        self.assertEqual(
            set(pins["verification"]),
            {
                "verifier_id",
                "verifier_identity_digest",
                "verifier_implementation_digest",
                "trust_anchor_id",
                "trust_anchor_digest",
            },
        )
        self.assertEqual(
            set(pins["reconciliation"]),
            {
                "source_id",
                "source_instance_id",
                "source_implementation_digest",
                "trust_anchor_id",
            },
        )
        serialized = json.dumps(pins, sort_keys=True)
        self.assertNotIn("verification_state", serialized)
        self.assertNotIn("PASS", serialized)
        self.assertNotIn("closable", serialized)
        self.assertNotIn("closure_state", serialized)

    def test_digests_are_derived_from_exact_external_bytes(self):
        self.provision()
        verification = json.loads(
            (self.output / "verification-trust.json").read_text(encoding="utf-8")
        )
        reconciliation = json.loads(
            (self.output / "reconciliation-trust.json").read_text(encoding="utf-8")
        )
        self.assertEqual(
            verification["verifier_implementation_digest"], self._digest(self.verifier_impl)
        )
        self.assertEqual(
            verification["trust_anchor_digest"], self._digest(self.verification_anchor)
        )
        self.assertEqual(
            reconciliation["source_implementation_digest"],
            self._digest(self.reconciliation_impl),
        )

    def test_missing_external_material_fails_closed(self):
        missing = self.external / "missing-verifier.bin"
        with self.assertRaises(FleetRuntimeTrustError):
            self.provision(verifier_implementation_path=str(missing))
        self.assertFalse(self.output.exists())

    def test_external_material_inside_repository_is_denied(self):
        inside = self.repo / "verifier.bin"
        inside.write_bytes(self.verifier_impl.read_bytes())
        with self.assertRaises(FleetRuntimeTrustError):
            self.provision(verifier_implementation_path=str(inside))
        self.assertFalse(self.output.exists())

    def test_verifier_implementation_digest_mismatch_is_denied(self):
        self.verifier_impl.write_bytes(b"substituted verifier bytes")
        with self.assertRaises(FleetRuntimeTrustError):
            self.provision()
        self.assertFalse(self.output.exists())

    def test_verification_trust_anchor_substitution_is_denied(self):
        anchor = json.loads(self.verification_anchor.read_text(encoding="utf-8"))
        anchor["trust_anchor_id"] = "substituted-root"
        self._write_json(self.verification_anchor, anchor)
        with self.assertRaises(FleetRuntimeTrustError):
            self.provision()
        self.assertFalse(self.output.exists())

    def test_reconciliation_source_instance_substitution_is_denied(self):
        wrong = self.config(
            expected_reconciliation_source_instance_id="different-source-instance"
        )
        with self.assertRaises(FleetRuntimeTrustError):
            self.provision(config=wrong)
        self.assertFalse(self.output.exists())

    def test_runtime_factory_version_is_bound_to_existing_verifier_contract(self):
        manifest = json.loads(self.verification_manifest.read_text(encoding="utf-8"))
        manifest["runtime_factory_version"] = "unsupported-version"
        self._write_json(self.verification_manifest, manifest)
        with self.assertRaises(FleetRuntimeTrustError):
            self.provision()
        self.assertFalse(self.output.exists())

    def test_existing_outputs_are_immutable_and_idempotent(self):
        first = self.provision()
        second = self.provision()
        self.assertEqual(first.receipt_id, second.receipt_id)
        pins_path = self.output / "f005-h-pins.json"
        pins_path.write_text("{}\n", encoding="utf-8")
        with self.assertRaises(FleetRuntimeTrustError):
            self.provision()

    def test_partial_output_set_is_denied(self):
        self.output.mkdir(parents=True)
        (self.output / "verification-trust.json").write_text("{}\n", encoding="utf-8")
        with self.assertRaises(FleetRuntimeTrustError):
            self.provision()

    def test_contract_binds_exact_runtime_outputs(self):
        config = self.config()
        self.assertTrue(config.verification_trust_path.endswith("verification-trust.json"))
        self.assertTrue(config.reconciliation_trust_path.endswith("reconciliation-trust.json"))
        self.assertTrue(config.f005_h_pins_path.endswith("f005-h-pins.json"))
        self.assertTrue(
            config.provisioning_receipt_path.endswith("trust-provisioning-receipt.json")
        )
        self.assertEqual(config.verification_trust_path, VERIFICATION_TRUST_PATH)
        self.assertEqual(config.reconciliation_trust_path, RECONCILIATION_TRUST_PATH)
        self.assertEqual(config.f005_h_pins_path, F005_H_PINS_PATH)
        self.assertEqual(config.provisioning_receipt_path, PROVISIONING_RECEIPT_PATH)


if __name__ == "__main__":
    unittest.main()
