from __future__ import annotations

from dataclasses import replace
import hashlib
import importlib
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import cyber_lion.enterprise.trusted_control_plane_runtime as runtime
from cyber_lion.enterprise.persistent_authority_state import (
    PersistentAuthorityStateError,
    SQLiteAuthorityStateStore,
)
from cyber_lion.enterprise.trusted_control_plane_service import (
    PROVIDER_VERSION,
    TrustedControlPlaneService,
    build_service_from_environment,
)


class TrustedControlPlaneRuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        # Each test models an independent process lifetime.
        importlib.reload(runtime)

    def _external_verifier(self, directory: str, *, ready: bool = True) -> tuple[str, str]:
        path = Path(directory) / "external_verifier.py"
        path.write_text(
            "def verify(payload, signature, key_id, algorithm):\n"
            "    return signature == 'ok' and key_id == 'key-1' and algorithm == 'ed25519'\n"
            f"def ready():\n    return {ready!r}\n",
            encoding="utf-8",
        )
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        return str(path), digest

    def _env(self, *, repo_root: str, db_path: str, verifier_path: str, verifier_digest: str) -> dict[str, str]:
        return {
            "LION_CP_RUNTIME_FACTORY_VERSION": runtime.RUNTIME_FACTORY_VERSION,
            "LION_CP_REPOSITORY_ROOT": repo_root,
            "LION_CP_DATABASE_PATH": db_path,
            "LION_CP_VERIFIER_MODULE_PATH": verifier_path,
            "LION_CP_VERIFIER_BINDING_DIGEST": verifier_digest,
            "LION_CP_VERIFIER_CALLABLE": "verify",
            "LION_CP_VERIFIER_READY_CALLABLE": "ready",
        }

    def test_zero_argument_factories_build_outside_repository(self) -> None:
        with tempfile.TemporaryDirectory() as repo, tempfile.TemporaryDirectory() as external:
            verifier_path, verifier_digest = self._external_verifier(external)
            db_path = str(Path(external) / "control-plane.sqlite3")
            env = self._env(repo_root=repo, db_path=db_path, verifier_path=verifier_path, verifier_digest=verifier_digest)
            with patch.dict(os.environ, env, clear=True):
                store = runtime.build_store()
                authority_store = runtime.build_authority_state_store()
                verifier = runtime.build_verifier()
                origin = runtime.verify_authority_state_store_origin()
                self.assertTrue(store.ready())
                self.assertIs(type(authority_store), SQLiteAuthorityStateStore)
                self.assertTrue(authority_store.ready())
                self.assertEqual(authority_store.resolve_authority_store_origin(), origin)
                self.assertTrue(verifier.ready())
                self.assertTrue(verifier.verify(b"payload", "ok", "key-1", "ed25519"))
                self.assertFalse(verifier.verify(b"payload", "bad", "key-1", "ed25519"))

    def test_authority_state_factory_accepts_no_caller_path(self) -> None:
        with self.assertRaises(TypeError):
            runtime.build_authority_state_store("/tmp/caller-selected.sqlite")

    def test_missing_database_path_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as repo, tempfile.TemporaryDirectory() as external:
            verifier_path, verifier_digest = self._external_verifier(external)
            env = self._env(repo_root=repo, db_path=str(Path(external) / "cp.sqlite3"), verifier_path=verifier_path, verifier_digest=verifier_digest)
            env.pop("LION_CP_DATABASE_PATH")
            with patch.dict(os.environ, env, clear=True):
                with self.assertRaises(runtime.TrustedControlPlaneRuntimeError): runtime.build_store()
                with self.assertRaises(runtime.TrustedControlPlaneRuntimeError): runtime.build_authority_state_store()

    def test_repository_local_database_path_is_denied(self) -> None:
        with tempfile.TemporaryDirectory() as repo, tempfile.TemporaryDirectory() as external:
            verifier_path, verifier_digest = self._external_verifier(external)
            env = self._env(repo_root=repo, db_path=str(Path(repo) / "forbidden.sqlite3"), verifier_path=verifier_path, verifier_digest=verifier_digest)
            with patch.dict(os.environ, env, clear=True):
                with self.assertRaisesRegex(runtime.TrustedControlPlaneRuntimeError, "outside repository"): runtime.build_store()
                with self.assertRaisesRegex(runtime.TrustedControlPlaneRuntimeError, "outside repository"): runtime.build_authority_state_store()

    def test_repository_local_verifier_material_is_denied(self) -> None:
        with tempfile.TemporaryDirectory() as repo, tempfile.TemporaryDirectory() as external:
            verifier_path, verifier_digest = self._external_verifier(repo)
            env = self._env(repo_root=repo, db_path=str(Path(external) / "cp.sqlite3"), verifier_path=verifier_path, verifier_digest=verifier_digest)
            with patch.dict(os.environ, env, clear=True):
                with self.assertRaisesRegex(runtime.TrustedControlPlaneRuntimeError, "outside repository"): runtime.build_verifier()

    def test_missing_or_mismatched_verifier_material_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as repo, tempfile.TemporaryDirectory() as external:
            verifier_path, verifier_digest = self._external_verifier(external)
            env = self._env(repo_root=repo, db_path=str(Path(external) / "cp.sqlite3"), verifier_path=verifier_path, verifier_digest=verifier_digest)
            missing = dict(env); missing.pop("LION_CP_VERIFIER_MODULE_PATH")
            with patch.dict(os.environ, missing, clear=True):
                with self.assertRaises(runtime.TrustedControlPlaneRuntimeError): runtime.build_verifier()
            mismatch = dict(env); mismatch["LION_CP_VERIFIER_BINDING_DIGEST"] = "0" * 64
            with patch.dict(os.environ, mismatch, clear=True):
                with self.assertRaisesRegex(runtime.TrustedControlPlaneRuntimeError, "binding mismatch"): runtime.build_verifier()

    def test_verifier_readiness_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as repo, tempfile.TemporaryDirectory() as external:
            verifier_path, verifier_digest = self._external_verifier(external, ready=False)
            env = self._env(repo_root=repo, db_path=str(Path(external) / "cp.sqlite3"), verifier_path=verifier_path, verifier_digest=verifier_digest)
            with patch.dict(os.environ, env, clear=True):
                with self.assertRaisesRegex(runtime.TrustedControlPlaneRuntimeError, "not ready"): runtime.build_verifier()

    def test_factory_version_mismatch_denied(self) -> None:
        with tempfile.TemporaryDirectory() as repo, tempfile.TemporaryDirectory() as external:
            verifier_path, verifier_digest = self._external_verifier(external)
            env = self._env(repo_root=repo, db_path=str(Path(external) / "cp.sqlite3"), verifier_path=verifier_path, verifier_digest=verifier_digest)
            env["LION_CP_RUNTIME_FACTORY_VERSION"] = "9.9.9"
            with patch.dict(os.environ, env, clear=True):
                with self.assertRaisesRegex(runtime.TrustedControlPlaneRuntimeError, "version mismatch"): runtime.build_store()
                with self.assertRaisesRegex(runtime.TrustedControlPlaneRuntimeError, "version mismatch"): runtime.build_authority_state_store()
                with self.assertRaisesRegex(runtime.TrustedControlPlaneRuntimeError, "version mismatch"): runtime.build_verifier()

    def test_duplicate_origin_registration_denied(self) -> None:
        with tempfile.TemporaryDirectory() as repo, tempfile.TemporaryDirectory() as external:
            verifier_path, verifier_digest = self._external_verifier(external)
            env = self._env(repo_root=repo, db_path=str(Path(external) / "cp.sqlite3"), verifier_path=verifier_path, verifier_digest=verifier_digest)
            with patch.dict(os.environ, env, clear=True):
                runtime.build_authority_state_store()
                with self.assertRaises(runtime.TrustedControlPlaneRuntimeError): runtime.register_authority_state_store_origin_once()

    def test_origin_digest_substitution_denied(self) -> None:
        with tempfile.TemporaryDirectory() as repo, tempfile.TemporaryDirectory() as external:
            verifier_path, verifier_digest = self._external_verifier(external)
            env = self._env(repo_root=repo, db_path=str(Path(external) / "cp.sqlite3"), verifier_path=verifier_path, verifier_digest=verifier_digest)
            with patch.dict(os.environ, env, clear=True):
                origin = runtime.observe_authority_state_store_origin()
                forged = replace(origin, origin_digest="0" * 64)
                with self.assertRaises(PersistentAuthorityStateError): forged.validate()

    def test_process_anchor_denies_store_switch_before_open(self) -> None:
        with tempfile.TemporaryDirectory() as repo, tempfile.TemporaryDirectory() as external:
            verifier_path, verifier_digest = self._external_verifier(external)
            path_a = str(Path(external) / "a.sqlite3")
            path_b = str(Path(external) / "b.sqlite3")
            env_a = self._env(repo_root=repo, db_path=path_a, verifier_path=verifier_path, verifier_digest=verifier_digest)
            env_b = dict(env_a); env_b["LION_CP_DATABASE_PATH"] = path_b
            with patch.dict(os.environ, env_a, clear=True):
                runtime.build_authority_state_store()
            with patch.dict(os.environ, env_b, clear=True), patch.object(runtime, "SQLiteAuthorityStateStore", side_effect=AssertionError("alternate store must not open")):
                with self.assertRaisesRegex(runtime.TrustedControlPlaneRuntimeError, "process authority-store origin drift"):
                    runtime.build_authority_state_store()
            self.assertFalse(Path(path_b).exists())

    def test_first_origin_cannot_be_replaced_by_second_valid_origin(self) -> None:
        with tempfile.TemporaryDirectory() as repo, tempfile.TemporaryDirectory() as external:
            verifier_path, verifier_digest = self._external_verifier(external)
            env_a = self._env(repo_root=repo, db_path=str(Path(external) / "a.sqlite3"), verifier_path=verifier_path, verifier_digest=verifier_digest)
            env_b = dict(env_a); env_b["LION_CP_DATABASE_PATH"] = str(Path(external) / "b.sqlite3")
            with patch.dict(os.environ, env_a, clear=True): runtime.build_authority_state_store()
            with patch.dict(os.environ, env_b, clear=True):
                with self.assertRaises(runtime.TrustedControlPlaneRuntimeError): runtime.register_authority_state_store_origin_once()

    def test_origin_drift_does_not_initialize_second_store(self) -> None:
        with tempfile.TemporaryDirectory() as repo, tempfile.TemporaryDirectory() as external:
            verifier_path, verifier_digest = self._external_verifier(external)
            path_a = str(Path(external) / "a.sqlite3")
            path_b = str(Path(external) / "b.sqlite3")
            env_a = self._env(repo_root=repo, db_path=path_a, verifier_path=verifier_path, verifier_digest=verifier_digest)
            env_b = dict(env_a); env_b["LION_CP_DATABASE_PATH"] = path_b
            with patch.dict(os.environ, env_a, clear=True): runtime.build_authority_state_store()
            self.assertFalse(Path(path_b).exists())
            with patch.dict(os.environ, env_b, clear=True):
                with self.assertRaises(runtime.TrustedControlPlaneRuntimeError): runtime.build_authority_state_store()
            self.assertFalse(Path(path_b).exists())

    def test_build_service_from_environment_uses_zero_arg_factories(self) -> None:
        with tempfile.TemporaryDirectory() as repo, tempfile.TemporaryDirectory() as external:
            verifier_path, verifier_digest = self._external_verifier(external)
            env = self._env(repo_root=repo, db_path=str(Path(external) / "cp.sqlite3"), verifier_path=verifier_path, verifier_digest=verifier_digest)
            env.update({
                "CYBER_LION_CP_PROVIDER_VERSION": PROVIDER_VERSION,
                "CYBER_LION_CP_CREDENTIAL_ENV": "LION_CP_TEST_BEARER",
                "LION_CP_TEST_BEARER": "external-test-credential",
                "CYBER_LION_CP_STORE_PROVIDER": "cyber_lion.enterprise.trusted_control_plane_runtime:build_store",
                "CYBER_LION_CP_VERIFIER_PROVIDER": "cyber_lion.enterprise.trusted_control_plane_runtime:build_verifier",
            })
            with patch.dict(os.environ, env, clear=True):
                service = build_service_from_environment()
                self.assertIsInstance(service, TrustedControlPlaneService)
                response = service.dispatch(method="GET", target="/healthz", headers={"Authorization": "Bearer external-test-credential"})
                self.assertEqual(response.status, 200)
                self.assertEqual(response.payload["status"], "READY")

    def test_errors_do_not_echo_sensitive_environment_values(self) -> None:
        secret_marker = "DO-NOT-ECHO-SECRET-MARKER"
        with tempfile.TemporaryDirectory() as repo:
            env = {
                "LION_CP_RUNTIME_FACTORY_VERSION": runtime.RUNTIME_FACTORY_VERSION,
                "LION_CP_REPOSITORY_ROOT": repo,
                "LION_CP_DATABASE_PATH": secret_marker,
            }
            with patch.dict(os.environ, env, clear=True):
                with self.assertRaises(runtime.TrustedControlPlaneRuntimeError) as captured: runtime.build_store()
                self.assertNotIn(secret_marker, str(captured.exception))
                with self.assertRaises(runtime.TrustedControlPlaneRuntimeError) as captured: runtime.build_authority_state_store()
                self.assertNotIn(secret_marker, str(captured.exception))


if __name__ == "__main__":
    unittest.main()
