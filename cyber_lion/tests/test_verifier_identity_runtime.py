from __future__ import annotations

import hashlib
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from cyber_lion.enterprise.verifier_identity_provider import (
    RealVerifierParticipationSource,
    RealVerifierRuntimeAttestationSource,
    RealVerifierWorkloadIdentitySource,
)
from cyber_lion.enterprise.verifier_identity_runtime import (
    VerifierIdentityRuntimeError,
    build_verifier_participation_source,
    build_verifier_runtime_source,
    build_verifier_workload_source,
)


WORKLOAD_PROVIDER = '''\nclass Provider:\n    def resolve(self, target): raise RuntimeError("not invoked in construction test")\ndef build(): return Provider()\n'''
SIGNATURE_VERIFIER = '''\ndef verify(payload, signature, key_id, algorithm): return True\n'''
RUNTIME_PROVIDER = '''\nclass Provider:\n    def resolve(self, target): raise RuntimeError("not invoked in construction test")\ndef build(): return Provider()\n'''
EXTERNAL_ATTESTER = '''\nclass Attester:\n    def verify_external(self, attestation): raise RuntimeError("not invoked in construction test")\ndef build(): return Attester()\n'''
PARTICIPATION_PROVIDER = '''\nclass Provider:\n    def resolve(self, target): raise RuntimeError("not invoked in construction test")\ndef build(): return Provider()\n'''


class RuntimeCompositionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.repo = root / "repo"
        self.external = root / "external"
        self.repo.mkdir()
        self.external.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def _module(self, name: str, content: str) -> tuple[str, str]:
        path = self.external / f"{name}.py"
        path.write_text(content, encoding="utf-8")
        return str(path), hashlib.sha256(path.read_bytes()).hexdigest()

    def _base_env(self):
        return {
            "LION_VI_RUNTIME_FACTORY_VERSION": "1.0.0",
            "LION_VI_REPOSITORY_ROOT": str(self.repo),
            "LION_VI_WORKLOAD_SOURCE_ID": "workload-source",
            "LION_VI_WORKLOAD_SOURCE_INSTANCE_ID": "workload-instance",
            "LION_VI_WORKLOAD_TRUST_ANCHOR_ID": "workload-root",
            "LION_VI_WORKLOAD_TRUST_DOMAIN": "lion",
            "LION_VI_WORKLOAD_TENANT_ID": "tenant",
            "LION_VI_WORKLOAD_ORGANIZATION_ID": "org",
            "LION_VI_WORKLOAD_AUDIENCE": "final-verifier",
            "LION_VI_WORKLOAD_ENVIRONMENT": "prod",
            "LION_VI_WORKLOAD_ISSUER_ID": "issuer",
            "LION_VI_RUNTIME_SOURCE_ID": "runtime-source",
            "LION_VI_RUNTIME_SOURCE_INSTANCE_ID": "runtime-instance",
            "LION_VI_RUNTIME_TRUST_ANCHOR_ID": "runtime-root",
            "LION_VI_RUNTIME_ISSUER": "runtime-issuer",
            "LION_VI_PARTICIPATION_SOURCE_ID": "participation-source",
            "LION_VI_PARTICIPATION_SOURCE_INSTANCE_ID": "participation-instance",
            "LION_VI_PARTICIPATION_TRUST_ANCHOR_ID": "participation-root",
        }

    def _full_env(self):
        env = self._base_env()
        specs = {
            "LION_VI_WORKLOAD_PROVIDER": (WORKLOAD_PROVIDER, "build"),
            "LION_VI_WORKLOAD_SIGNATURE_VERIFIER": (SIGNATURE_VERIFIER, "verify"),
            "LION_VI_RUNTIME_PROVIDER": (RUNTIME_PROVIDER, "build"),
            "LION_VI_EXTERNAL_ATTESTER": (EXTERNAL_ATTESTER, "build"),
            "LION_VI_PARTICIPATION_PROVIDER": (PARTICIPATION_PROVIDER, "build"),
        }
        for prefix, (content, callable_name) in specs.items():
            path, digest = self._module(prefix.lower(), content)
            env[f"{prefix}_MODULE_PATH"] = path
            env[f"{prefix}_MODULE_DIGEST"] = digest
            env[f"{prefix}_CALLABLE"] = callable_name
        return env

    def test_zero_argument_factories_build_external_pinned_sources(self):
        env = self._full_env()
        with patch.dict(os.environ, env, clear=True):
            workload = build_verifier_workload_source()
            runtime = build_verifier_runtime_source()
            participation = build_verifier_participation_source()
        self.assertIsInstance(workload, RealVerifierWorkloadIdentitySource)
        self.assertIsInstance(runtime, RealVerifierRuntimeAttestationSource)
        self.assertIsInstance(participation, RealVerifierParticipationSource)
        for source in (workload, runtime, participation):
            public = {name for name in dir(source) if not name.startswith("_")}
            self.assertIn("resolve", public)
            self.assertTrue(public.isdisjoint({"merge", "update_ref", "write", "grant_authority", "deploy"}))

    def test_repository_local_provider_material_is_denied(self):
        env = self._full_env()
        local = self.repo / "provider.py"
        local.write_text(WORKLOAD_PROVIDER, encoding="utf-8")
        env["LION_VI_WORKLOAD_PROVIDER_MODULE_PATH"] = str(local)
        env["LION_VI_WORKLOAD_PROVIDER_MODULE_DIGEST"] = hashlib.sha256(local.read_bytes()).hexdigest()
        with patch.dict(os.environ, env, clear=True), self.assertRaises(VerifierIdentityRuntimeError):
            build_verifier_workload_source()

    def test_provider_digest_substitution_is_denied(self):
        env = self._full_env()
        env["LION_VI_RUNTIME_PROVIDER_MODULE_DIGEST"] = "0" * 64
        with patch.dict(os.environ, env, clear=True), self.assertRaises(VerifierIdentityRuntimeError):
            build_verifier_runtime_source()

    def test_callable_substitution_is_denied(self):
        env = self._full_env()
        env["LION_VI_PARTICIPATION_PROVIDER_CALLABLE"] = "missing"
        with patch.dict(os.environ, env, clear=True), self.assertRaises(VerifierIdentityRuntimeError):
            build_verifier_participation_source()

    def test_missing_or_wrong_runtime_configuration_fails_closed(self):
        env = self._full_env()
        env["LION_VI_RUNTIME_FACTORY_VERSION"] = "2.0.0"
        with patch.dict(os.environ, env, clear=True), self.assertRaises(VerifierIdentityRuntimeError):
            build_verifier_workload_source()
        del env["LION_VI_RUNTIME_FACTORY_VERSION"]
        with patch.dict(os.environ, env, clear=True), self.assertRaises(VerifierIdentityRuntimeError):
            build_verifier_workload_source()


if __name__ == "__main__":
    unittest.main()
