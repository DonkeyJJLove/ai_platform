from __future__ import annotations

import inspect
import os
from pathlib import Path
import tempfile
import unittest

import cyber_lion.enterprise.live_runtime_evidence_plane as plane


EXPECTED_NEGATIVES = {
    "authority-revoked-after-admission-before-effect",
    "authority-state-version-changed-before-effect",
    "policy-changed-before-effect",
    "observer-terminated-before-effect",
    "forged-authority-record",
    "forged-authority-signature",
    "forged-runtime-attestation",
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


class LiveRuntimeEvidencePlaneR2Tests(unittest.TestCase):
    def test_runtime_module_has_no_authority_minting_or_signing_secret_generation(self):
        source = inspect.getsource(plane)
        self.assertNotIn("import hmac", source)
        self.assertNotIn("import secrets", source)
        self.assertNotIn("_hmac_grant", source)
        self.assertNotIn("_build_live_authority", source)
        self.assertNotIn("genpkey", source)
        self.assertNotIn('"-sign"', source)
        self.assertIn("F009_AUTHORITY_BUNDLE_DIGEST", source)
        self.assertIn("_load_control_plane", source)
        self.assertIn("_openssl_verifier", source)

    def test_runtime_requires_parent_pinned_control_inputs(self):
        old_a = os.environ.pop("F009_AUTHORITY_BUNDLE_DIGEST", None)
        old_p = os.environ.pop("F009_PROVIDER_TRUST_DIGEST", None)
        try:
            with tempfile.TemporaryDirectory() as td:
                p = Path(td) / "x"
                p.write_bytes(b"x")
                with self.assertRaises(RuntimeError):
                    plane._pinned_file(p, "F009_AUTHORITY_BUNDLE_DIGEST")
        finally:
            if old_a is not None:
                os.environ["F009_AUTHORITY_BUNDLE_DIGEST"] = old_a
            if old_p is not None:
                os.environ["F009_PROVIDER_TRUST_DIGEST"] = old_p

    def test_proof_target_must_be_outside_repository(self):
        workspace = Path(os.environ.get("GITHUB_WORKSPACE", os.getcwd())).resolve()
        with self.assertRaises(RuntimeError):
            plane._safe_root(workspace / "forbidden-proof")

    def test_mandatory_negative_set_is_explicit_in_live_runner(self):
        source = inspect.getsource(plane.run_live_runtime_proof)
        for name in EXPECTED_NEGATIVES:
            self.assertIn(name, source)
        self.assertIn("if not all(negatives.values())", source)

    def test_distinct_process_boundaries_are_present(self):
        source = inspect.getsource(plane)
        self.assertIn("--attest", source)
        self.assertIn("--observer", source)
        self.assertIn("--control-mutate", source)
        self.assertIn("bootstrap/runtime process separation failed", source)


if __name__ == "__main__":
    unittest.main()
