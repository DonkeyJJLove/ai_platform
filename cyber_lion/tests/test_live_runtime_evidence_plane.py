from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
import unittest

from cyber_lion.enterprise.live_runtime_evidence_plane import run_live_runtime_proof


EXPECTED_ARTIFACTS = {
    "runtime-identity.json",
    "admission.json",
    "effect-currentness.json",
    "sandbox-execution-receipt.json",
    "independent-observation.json",
    "reconciliation-receipt.json",
    "replay-denial.json",
    "proof-manifest.json",
}

EXPECTED_NEGATIVES = {
    "authority-revoked-after-admission-before-effect",
    "authority-changed-after-admission-before-effect",
    "policy-changed-after-admission-before-effect",
    "observability-lost-after-admission-before-effect",
    "runtime-identity-substitution",
    "execution-subject-substitution",
    "workspace-substitution",
    "resource-substitution",
    "payload-substitution",
    "replayed-admission",
    "replayed-execution",
    "missing-independent-observation",
    "observer-effect-mismatch",
    "receipt-without-observed-effect",
    "effect-without-receipt",
    "partial-effect",
    "UNKNOWN-effect-state",
}


class LiveRuntimeEvidencePlaneTests(unittest.TestCase):
    def test_real_local_proof_is_bounded_and_reconciles(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            work = base / "work"
            artifacts = base / "artifacts"
            manifest = run_live_runtime_proof(work, artifacts)
            self.assertEqual(manifest["positive"]["reconciliation"], "MATCHED")
            self.assertEqual(manifest["positive"]["effect_digest"], manifest["positive"]["independent_effect_digest"])
            self.assertFalse(manifest["f005_runtime_resumed"])
            self.assertFalse(manifest["production_effect"])
            self.assertEqual(set(manifest["negative_results"]), EXPECTED_NEGATIVES)
            self.assertTrue(all(manifest["negative_results"].values()))
            self.assertEqual({p.name for p in artifacts.iterdir()}, EXPECTED_ARTIFACTS)
            for name, digest in manifest["artifact_digests"].items():
                self.assertEqual(len(digest), 64)
                self.assertTrue((artifacts / name).exists())

    def test_proof_target_must_be_outside_repository(self):
        workspace = Path(os.environ.get("GITHUB_WORKSPACE", os.getcwd())).resolve()
        with self.assertRaises(RuntimeError):
            run_live_runtime_proof(workspace / "forbidden-proof", Path(tempfile.mkdtemp()) / "artifacts")

    def test_manifest_is_machine_readable_and_contains_no_success_laundering(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            run_live_runtime_proof(base / "work", base / "artifacts")
            manifest = json.loads((base / "artifacts" / "proof-manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["positive"]["reconciliation"], "MATCHED")
            self.assertTrue(all(value is True for value in manifest["negative_results"].values()))


if __name__ == "__main__":
    unittest.main()
