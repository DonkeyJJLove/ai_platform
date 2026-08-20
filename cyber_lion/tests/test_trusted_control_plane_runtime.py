from __future__ import annotations

import hashlib
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from cyber_lion.enterprise.trusted_control_plane_runtime import (
    RUNTIME_FACTORY_VERSION,
    TrustedControlPlaneRuntimeError,
    build_store,
    build_verifier,
)
from cyber_lion.enterprise.trusted_control_plane_service import (
    PROVIDER_VERSION,
    TrustedControlPlaneService,
    build_service_from_environment,
)


class TrustedControlPlaneRuntimeTests(unittest.TestCase):
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
            "LION_CP_RUNTIME_FACTORY_VERSION": RUNTIME_FACTORY_VERSION,
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
            env = self._env(
                repo_root=repo,
                db_path=db_path,
                verifier_path=verifier_path,
                verifier_digest=verifier_digest,
            )
            with patch.dict(os.environ, env, clear=True):
                store = build_store()
                verifier = build_verifier()
                self.assertTrue(store.ready())
                self.assertTrue(verifier.ready())
                self.assertTrue(verifier.verify(b"payload", "ok", "key-1", "ed25519"))
                self.assertFalse(verifier.verify(b"payload", "bad", "key-1", "ed25519"))

    def test_missing_database_path_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as repo, tempfile.TemporaryDirectory() as external:
            verifier_path, verifier_digest = self._external_verifier(external)
            env = self._env(
                repo_root=repo,
                db_path=str(Path(external) / "cp.sqlite3"),
                verifier_path=verifier_path,
                verifier_digest=verifier_digest,
            )
            env.pop("LION_CP_DATABASE_PATH")
            with patch.dict(os.environ, env, clear=True):
                with self.assertRaises(TrustedControlPlaneRuntimeError):
                    build_store()

    def test_repository_local_database_path_is_denied(self) -> None:
        with tempfile.TemporaryDirectory() as repo, tempfile.TemporaryDirectory() as external:
            verifier_path, verifier_digest = self._external_verifier(external)
            env = self._env(
                repo_root=repo,
                db_path=str(Path(repo) / "forbidden.sqlite3"),
                verifier_path=verifier_path,
                verifier_digest=verifier_digest,
            )
            with patch.dict(os.environ, env, clear=True):
                with self.assertRaisesRegex(TrustedControlPlaneRuntimeError, "outside repository"):
                    build_store()

    def test_repository_local_verifier_material_is_denied(self) -> None:
        with tempfile.TemporaryDirectory() as repo, tempfile.TemporaryDirectory() as external:
            verifier_path, verifier_digest = self._external_verifier(repo)
            env = self._env(
                repo_root=repo,
                db_path=str(Path(external) / "cp.sqlite3"),
                verifier_path=verifier_path,
                verifier_digest=verifier_digest,
            )
            with patch.dict(os.environ, env, clear=True):
                with self.assertRaisesRegex(TrustedControlPlaneRuntimeError, "outside repository"):
                    build_verifier()

    def test_missing_or_mismatched_verifier_material_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as repo, tempfile.TemporaryDirectory() as external:
            verifier_path, verifier_digest = self._external_verifier(external)
            env = self._env(
                repo_root=repo,
                db_path=str(Path(external) / "cp.sqlite3"),
                verifier_path=verifier_path,
                verifier_digest=verifier_digest,
            )
            missing = dict(env)
            missing.pop("LION_CP_VERIFIER_MODULE_PATH")
            with patch.dict(os.environ, missing, clear=True):
                with self.assertRaises(TrustedControlPlaneRuntimeError):
                    build_verifier()

            mismatch = dict(env)
            mismatch["LION_CP_VERIFIER_BINDING_DIGEST"] = "0" * 64
            with patch.dict(os.environ, mismatch, clear=True):
                with self.assertRaisesRegex(TrustedControlPlaneRuntimeError, "binding mismatch"):
                    build_verifier()

    def test_verifier_readiness_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as repo, tempfile.TemporaryDirectory() as external:
            verifier_path, verifier_digest = self._external_verifier(external, ready=False)
            env = self._env(
                repo_root=repo,
                db_path=str(Path(external) / "cp.sqlite3"),
                verifier_path=verifier_path,
                verifier_digest=verifier_digest,
            )
            with patch.dict(os.environ, env, clear=True):
                with self.assertRaisesRegex(TrustedControlPlaneRuntimeError, "not ready"):
                    build_verifier()

    def test_factory_version_mismatch_denied(self) -> None:
        with tempfile.TemporaryDirectory() as repo, tempfile.TemporaryDirectory() as external:
            verifier_path, verifier_digest = self._external_verifier(external)
            env = self._env(
                repo_root=repo,
                db_path=str(Path(external) / "cp.sqlite3"),
                verifier_path=verifier_path,
                verifier_digest=verifier_digest,
            )
            env["LION_CP_RUNTIME_FACTORY_VERSION"] = "9.9.9"
            with patch.dict(os.environ, env, clear=True):
                with self.assertRaisesRegex(TrustedControlPlaneRuntimeError, "version mismatch"):
                    build_store()
                with self.assertRaisesRegex(TrustedControlPlaneRuntimeError, "version mismatch"):
                    build_verifier()

    def test_build_service_from_environment_uses_zero_arg_factories(self) -> None:
        with tempfile.TemporaryDirectory() as repo, tempfile.TemporaryDirectory() as external:
            verifier_path, verifier_digest = self._external_verifier(external)
            env = self._env(
                repo_root=repo,
                db_path=str(Path(external) / "cp.sqlite3"),
                verifier_path=verifier_path,
                verifier_digest=verifier_digest,
            )
            env.update(
                {
                    "CYBER_LION_CP_PROVIDER_VERSION": PROVIDER_VERSION,
                    "CYBER_LION_CP_CREDENTIAL_ENV": "LION_CP_TEST_BEARER",
                    "LION_CP_TEST_BEARER": "external-test-credential",
                    "CYBER_LION_CP_STORE_PROVIDER": (
                        "cyber_lion.enterprise.trusted_control_plane_runtime:build_store"
                    ),
                    "CYBER_LION_CP_VERIFIER_PROVIDER": (
                        "cyber_lion.enterprise.trusted_control_plane_runtime:build_verifier"
                    ),
                }
            )
            with patch.dict(os.environ, env, clear=True):
                service = build_service_from_environment()
                self.assertIsInstance(service, TrustedControlPlaneService)
                response = service.dispatch(
                    method="GET",
                    target="/healthz",
                    headers={"Authorization": "Bearer external-test-credential"},
                )
                self.assertEqual(response.status, 200)
                self.assertEqual(response.payload["status"], "READY")

    def test_errors_do_not_echo_sensitive_environment_values(self) -> None:
        secret_marker = "DO-NOT-ECHO-SECRET-MARKER"
        with tempfile.TemporaryDirectory() as repo:
            env = {
                "LION_CP_RUNTIME_FACTORY_VERSION": RUNTIME_FACTORY_VERSION,
                "LION_CP_REPOSITORY_ROOT": repo,
                "LION_CP_DATABASE_PATH": secret_marker,
            }
            with patch.dict(os.environ, env, clear=True):
                with self.assertRaises(TrustedControlPlaneRuntimeError) as captured:
                    build_store()
                self.assertNotIn(secret_marker, str(captured.exception))


if __name__ == "__main__":
    unittest.main()
